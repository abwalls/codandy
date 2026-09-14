import json

import pytest

from app import dependency_checks
from app.analyzer import analyze_repository
from app.dependency_versions import exact_version, safe_version
from app.models import AtlasNode
from app.settings import Settings


def analyze(tmp_path, files):
    for path, content in files.items():
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return analyze_repository(tmp_path, "https://github.com/org/repo.git", None, Settings(), lambda *_: None)


def test_npm_versions_lockfile_and_scopes(tmp_path):
    atlas = analyze(tmp_path, {
        "package.json": json.dumps({"dependencies": {"react": "^18.0.0", "private": "https://user:password@example.com/archive"}, "peerDependencies": {"react": ">=18"}}),
        "package-lock.json": json.dumps({"lockfileVersion": 3, "packages": {"node_modules/react": {"version": "18.2.0"}}}),
    })
    nodes = [node for node in atlas.nodes if node.kind == "dependency"]
    react = next(node for node in nodes if node.label == "react" and node.attributes["group"] == "dependencies")
    assert react.attributes["declared_version"] == "^18.0.0"
    assert react.attributes["checked_version"] == "18.2.0"
    assert react.attributes["version_basis"] == "lockfile"
    assert react.evidence[-1].path == "package-lock.json"
    assert "password" not in atlas.model_dump_json()
    assert len(nodes) == 3


def test_nuget_python_and_go_versions(tmp_path):
    atlas = analyze(tmp_path, {
        "api/App.csproj": '<Project><ItemGroup><PackageReference Include="Example.Core"><Version>1.0.0</Version></PackageReference></ItemGroup></Project>',
        "api/packages.lock.json": json.dumps({"dependencies": {"net8.0": {"Example.Core": {"resolved": "1.2.0"}}}}),
        "requirements.txt": 'fastapi==0.116.0\nrequests>=2.0\n',
        "go.mod": 'module example.com/service\nrequire golang.org/x/text v0.14.0\n',
    })
    by_name = {node.label: node for node in atlas.nodes if node.kind == "dependency"}
    assert by_name["Example.Core"].attributes["checked_version"] == "1.2.0"
    assert by_name["fastapi"].attributes["checked_version"] == "0.116.0"
    assert by_name["requests"].attributes["version_basis"] == "unknown"
    assert by_name["golang.org/x/text"].attributes["checked_version"] == "v0.14.0"


@pytest.mark.parametrize("value", ["https://secret@host/pkg", "file:../private", "$(TOKEN)", "workspace:*", "DO_NOT_EXPOSE", None, {}])
def test_unsafe_or_unsupported_versions_are_withheld(value):
    assert safe_version(value) == ""


def node(version="1.0.0"):
    return AtlasNode(id="dependency:test", kind="dependency", label="example", detail="", path="package.json", confidence=100,
                     attributes={"ecosystem": "npm", "checked_version": version, "version_basis": "declared"})


def test_registry_and_advisory_results_are_separate(monkeypatch):
    calls = []

    def response(url, body=None):
        calls.append((url, body))
        if "registry.npmjs.org" in url:
            return {"version": "2.0.0"}
        return {"vulns": [{"id": "GHSA-test-1234", "summary": "Example risk"}, {"id": "withdrawn", "withdrawn": "2020"}]}

    monkeypatch.setattr(dependency_checks, "public_json", response)
    result = dependency_checks.check_dependency(node())
    assert result["update_status"] == "newer_available"
    assert result["vulnerability_status"] == "reported"
    assert len(result["advisories"]) == 1
    assert calls[-1][1] == {"package": {"name": "example", "ecosystem": "npm"}, "version": "1.0.0"}


def test_network_failure_is_not_a_clean_audit(monkeypatch):
    def fail(*args):
        raise OSError("private diagnostic")

    monkeypatch.setattr(dependency_checks, "public_json", fail)
    result = dependency_checks.check_dependency(node())
    assert result["registry_status"] == "unavailable"
    assert result["vulnerability_status"] == "unavailable"
    assert "private diagnostic" not in json.dumps(result)


def test_unknown_version_does_not_query_advisories(monkeypatch):
    def response(url, body=None):
        assert body is None
        return {"version": "2.0.0"}

    monkeypatch.setattr(dependency_checks, "public_json", response)
    assert dependency_checks.check_dependency(node(""))["vulnerability_status"] == "unknown_version"


def test_metadata_client_rejects_custom_hosts_before_network():
    with pytest.raises(ValueError, match="Unapproved"):
        dependency_checks.public_json("http://127.0.0.1:8000/secret")


def test_advisory_pagination_is_not_claimed_complete(monkeypatch):
    monkeypatch.setattr(dependency_checks, "public_json", lambda *args: {"next_page_token": "next"})
    result = dependency_checks.check_dependency(node())
    assert result["vulnerability_status"] == "incomplete"
    assert result["advisories_truncated"]


@pytest.mark.parametrize("value", ["[1.0.0", "1.0.0]", "==1.0.0]", ">=1.0.0", "[1.0,2.0)"])
def test_ranges_and_unbalanced_brackets_are_not_exact_versions(value):
    assert exact_version(value) == ""


def test_npm_partial_version_is_a_range(tmp_path):
    atlas = analyze(tmp_path, {"package.json": '{"dependencies":{"example":"1.2"}}'})
    dependency = next(node for node in atlas.nodes if node.kind == "dependency")
    assert dependency.attributes["declared_version"] == "1.2"
    assert "checked_version" not in dependency.attributes


def test_conflicting_python_constraints_do_not_choose_one_version(tmp_path):
    atlas = analyze(tmp_path, {"requirements.txt": "requests==2.0.0\nrequests==3.0.0\nrequests==2.0.0\n"})
    dependency = next(node for node in atlas.nodes if node.kind == "dependency")
    assert dependency.attributes["version_basis"] == "unknown"
    assert "checked_version" not in dependency.attributes


@pytest.mark.parametrize("constraint,expected", [("1.0.0", None), ("[1.0.0]", "1.0.0"), ("[1.0,2.0)", None)])
def test_nuget_minimum_is_not_an_exact_version(tmp_path, constraint, expected):
    atlas = analyze(tmp_path, {"App.csproj": f'<Project><PackageReference Include="Example" Version="{constraint}" /></Project>'})
    dependency = next(node for node in atlas.nodes if node.kind == "dependency")
    assert dependency.attributes.get("checked_version") == expected


def test_go_replacements_and_exclusions_are_not_requirements(tmp_path):
    atlas = analyze(tmp_path, {"go.mod": """module example.com/app
require (
    example.com/required v1.0.0
)
replace (
    example.com/required v1.0.0 => ../local
    example.com/other v2.0.0 => ../other
)
exclude (
    example.com/excluded v1.0.0
)
"""})
    dependencies = [node for node in atlas.nodes if node.kind == "dependency"]
    assert len(dependencies) == 1
    assert dependencies[0].label == "example.com/required"
    assert dependencies[0].attributes["declared_version"] == "v1.0.0"
    assert dependencies[0].attributes["version_basis"] == "unknown"
    assert "replacement" in dependencies[0].attributes["version_note"]


def test_central_nuget_candidates_are_evidence_not_selected_versions(tmp_path):
    atlas = analyze(tmp_path, {
        "src/App.csproj": '<Project><PackageReference Include="Example.Core" /></Project>',
        "Directory.Packages.props": '<Project><ItemGroup><PackageVersion Include="example.core" Version="[1.0.0]" />'
                                    '<PackageVersion Include="Example.Core" Version="2.0.0" Condition="false" /></ItemGroup></Project>',
    })
    dependency = next(node for node in atlas.nodes if node.kind == "dependency")
    assert dependency.attributes["central_version_candidates"] == "2.0.0 | [1.0.0]"
    assert dependency.attributes["central_version_file"] == "Directory.Packages.props"
    assert dependency.evidence[-1].path == "Directory.Packages.props"
    assert "checked_version" not in dependency.attributes
    assert dependency.attributes["version_basis"] == "unknown"


def test_central_nuget_uses_nearest_file_without_import_evaluation(tmp_path):
    atlas = analyze(tmp_path, {
        "src/App.csproj": '<Project><PackageReference Include="Example" /></Project>',
        "Directory.Packages.props": '<Project><PackageVersion Include="Example" Version="1.0.0" /></Project>',
        "src/Directory.Packages.props": '<Project><Import Project="../Directory.Packages.props" />'
                                        '<PackageVersion Update="Example"><Version>2.0.0</Version></PackageVersion></Project>',
    })
    dependency = next(node for node in atlas.nodes if node.kind == "dependency")
    assert dependency.attributes["central_version_candidates"] == "2.0.0"
    assert dependency.attributes["central_version_file"] == "src/Directory.Packages.props"


@pytest.mark.parametrize("content", ['<Project><PackageVersion Include="Example" Version="https://DO_NOT_EXPOSE/" /></Project>',
                                     '<!DOCTYPE Project [<!ENTITY value "DO_NOT_EXPOSE">]><Project />',
                                     '<Project invalid'])
def test_unsafe_or_invalid_central_metadata_is_not_retained(tmp_path, content):
    atlas = analyze(tmp_path, {"App.csproj": '<Project><PackageReference Include="Example" /></Project>',
                              "Directory.Packages.props": content})
    assert "DO_NOT_EXPOSE" not in atlas.model_dump_json()
    dependency = next(node for node in atlas.nodes if node.kind == "dependency")
    assert "central_version_candidates" not in dependency.attributes
