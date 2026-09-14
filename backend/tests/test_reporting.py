import pytest
from pydantic import ValidationError

from app.analyzer import analyze_repository
from app.models import AtlasDocument
from app.settings import Settings


def analyze(tmp_path, files):
    for path, data in files.items():
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(data, encoding="utf-8")
    return analyze_repository(tmp_path, "https://github.com/org/repo.git", None,
                              Settings(), lambda *_: None)


def test_structure_dependencies_and_developer_guide(tmp_path):
    atlas = analyze(tmp_path, {
        "package.json": '{"scripts":{"dev":"DO_NOT_EXPOSE","test":"DO_NOT_EXPOSE"},'
                        '"dependencies":{"react":"DO_NOT_EXPOSE"}}',
        "client/package.json": '{}',
        "client/View.tsx": 'export function View() { return <div />; }',
        "server/Api.csproj": '<Project><ItemGroup><PackageReference Include="Example.Core" />'
                             '<PackageReference Include="Example.Core" /></ItemGroup></Project>',
        "server/Api.cs": 'class Api {}',
        "client/View.test.ts": 'function example() {}',
        "README.md": 'DO_NOT_EXPOSE',
    })
    assert "DO_NOT_EXPOSE" not in atlas.model_dump_json()
    assert {n.label for n in atlas.nodes if n.kind == "task"} == {"dev", "test"}
    assert {n.label for n in atlas.nodes if n.kind == "dependency"} == {"react", "Example.Core"}
    projects = [i for i in atlas.report.architecture.items if i.category == "project"]
    client = next(i for i in projects if i.title == "client/package.json")
    assert client.metrics["files"] == 2
    assert any(i.category == "inferred_boundary" and i.title == "Client boundary"
               for i in atlas.report.architecture.items)
    assert any(i.category == "external_dependency" and i.title == "2 declared dependencies"
               for i in atlas.report.architecture.items)
    assert {i.title for i in atlas.report.guide.items} >= {
        "UI declarations", "Candidate tests", "Project configuration", "Documentation", "Declared tasks"}
    assert atlas.report.recommendations.status == "not_detected"


def test_dotnet_project_references_are_static_indexed_candidates(tmp_path):
    atlas = analyze(tmp_path, {
        "Api/Api.csproj": '<Project><ItemGroup Condition="false"><ProjectReference Include="..\\Domain\\Domain.csproj" ReferenceOutputAssembly="false" />'
                          '<PackageReference Include="Example.Core" Version="1.0.0" /></ItemGroup></Project>',
        "Domain/Domain.csproj": '<Project xmlns="http://schemas.microsoft.com/developer/msbuild/2003" />',
    })
    by_id = {node.id: node for node in atlas.nodes}
    reference = next(node for node in atlas.nodes if node.kind == "project_reference")
    edge = next(edge for edge in atlas.relationships if edge.source == reference.id and edge.type == "RESOLVES_TO")
    assert edge.resolution == "inferred"
    assert by_id[edge.target].path == "Domain/Domain.csproj"
    report = next(item for item in atlas.report.architecture.items if item.category == "project_dependency")
    assert report.metrics == {"declarations": 1, "matched_paths": 1, "unresolved": 0}
    assert report.steps[0].type == "RESOLVES_TO"
    project = next(item for item in atlas.report.architecture.items if item.category == "project" and item.title == "Api/Api.csproj")
    assert project.metrics["declared_dependencies"] == 1
    assert AtlasDocument.model_validate_json(atlas.model_dump_json()) == atlas


@pytest.mark.parametrize("include", ["$(DO_NOT_EXPOSE)/Domain.csproj", "https://DO_NOT_EXPOSE/Domain.csproj",
                                    "../../DO_NOT_EXPOSE.csproj", "../secret/Domain.csproj", "../*/Domain.csproj"])
def test_project_references_do_not_resolve_or_disclose_unindexed_paths(tmp_path, include):
    atlas = analyze(tmp_path, {
        "Api/Api.csproj": f'<Project><ProjectReference Include="{include}" /></Project>',
        "Domain/Domain.csproj": '<Project />',
        "secret/Domain.csproj": '<Project />',
    })
    reference = next(node for node in atlas.nodes if node.kind == "project_reference")
    assert reference.attributes["resolution"] == "unresolved"
    assert "DO_NOT_EXPOSE" not in atlas.model_dump_json()
    assert not any(edge.type == "RESOLVES_TO" for edge in atlas.relationships)
    report = next(item for item in atlas.report.architecture.items if item.category == "project_dependency")
    assert report.metrics["unresolved"] == 1


def test_project_reference_identity_survives_other_project_additions(tmp_path):
    files = {"Api/Api.csproj": '<Project><ProjectReference Include="../Domain/Domain.csproj" /></Project>',
             "Domain/Domain.csproj": '<Project />'}
    before = analyze(tmp_path, files)
    files["A/A.csproj"] = '<Project><ProjectReference Include="../Domain/Domain.csproj" /></Project>'
    after = analyze(tmp_path, files)
    before_id = next(node.id for node in before.nodes if node.kind == "project_reference")
    after_id = next(node.id for node in after.nodes if node.kind == "project_reference" and node.path == "Api/Api.csproj")
    assert before_id == after_id


def test_local_import_resolution_is_conservative(tmp_path):
    atlas = analyze(tmp_path, {
        "src/main.ts": 'import "./unique"; import "./ambiguous"; import "../../outside"; '
                       'import "@alias/foo"; import "./mapped.js";',
        "src/unique/index.ts": 'export function run() {}',
        "src/ambiguous.ts": '', "src/ambiguous.tsx": '', "src/mapped.ts": '',
    })
    by_id = {n.id: n for n in atlas.nodes}
    resolutions = [e for e in atlas.relationships if e.type == "RESOLVES_TO"]
    assert {by_id[e.source].label for e in resolutions} == {"./unique", "./mapped.js"}
    assert all(e.resolution == "inferred" for e in resolutions)
    assert len(atlas.report.flows.items) == 2
    assert all(i.category == "module_dependency" for i in atlas.report.flows.items)


@pytest.mark.parametrize(("file", "source"), [
    ("Api.cs", ('class Api { void Handle() { Save(); } void Save() {} '
               'void Configure() { app.MapGet("/health", Handle); } }')),
    ("api.ts", 'function handle() { save(); } function save() {} app.get("/health", handle);'),
    ("inline.ts", 'function save() {} app.get("/health", () => { save(); });'),
    ("Inline.cs", ('class Api { void Save() {} void Configure() { '
                  'app.MapGet("/health", () => { Save(); }); } }')),
])
def test_route_paths_are_backed_by_graph_edges(tmp_path, file, source):
    atlas = analyze(tmp_path, {file: source})
    route = next(i for i in atlas.report.flows.items if i.category == "route_flow")
    assert any(step.type == "ROUTES_TO" for step in route.steps)
    assert any(step.type == "CALLS" for step in route.steps)
    assert all(step.resolution == "inferred" for step in route.steps)
    assert AtlasDocument.model_validate_json(atlas.model_dump_json()) == atlas


def test_ambiguous_methods_do_not_get_call_links(tmp_path):
    atlas = analyze(tmp_path, {"Api.cs": 'class Api { void Save(int x) {} void Save(string x) {} '
                            'void Run() { Save(1); } }'})
    assert not any(e.type == "CALLS" for e in atlas.relationships)


def test_recommendations_have_evidence_and_verification(tmp_path):
    atlas = analyze(tmp_path, {"View.tsx": 'function large() {\n' + '\n' * 85 + 'return 1;\n}\n'
                             'function render(value: string) { eval(value); '
                             'return <div dangerouslySetInnerHTML={{ __html: value }} />; }'})
    recommendations = atlas.report.recommendations.items
    assert len(recommendations) == 3
    assert {i.category for i in recommendations} == {"maintainability", "potential_security_risk"}
    assert all(i.evidence and i.node_ids and i.approach and i.verification for i in recommendations)
    assert all(i.basis == "inferred" for i in recommendations)
    assert "not a clean security audit" in " ".join(atlas.report.recommendations.limitations)


def test_schema_rejects_invented_report_steps(tmp_path):
    atlas = analyze(tmp_path, {"main.ts": 'import "./other";', "other.ts": ''})
    data = atlas.model_dump()
    data["report"]["flows"]["items"][0]["steps"][0]["type"] = "CALLS"
    with pytest.raises(ValidationError, match="existing relationship"):
        AtlasDocument.model_validate(data)


def test_empty_unsupported_repository_has_no_fabricated_flows(tmp_path):
    atlas = analyze(tmp_path, {"script.py": 'def unsupported(): pass'})
    assert atlas.report.flows.status == "not_detected"
    assert atlas.report.guide.status == "not_detected"
    assert atlas.report.recommendations.status == "not_detected"
    assert "1 files" in atlas.report.summary


def test_dependency_inventory_is_aggregated_and_bounded(tmp_path):
    import json

    atlas = analyze(tmp_path, {"package.json": json.dumps({
        "dependencies": {f"package-{i}": "1" for i in range(120)}})})
    cards = [i for i in atlas.report.architecture.items
             if i.category == "external_dependency"]
    assert len(cards) == 1
    assert cards[0].metrics["manifest_declarations"] == 120
    assert len(cards[0].node_ids) == 100
    assert len([n for n in atlas.nodes if n.kind == "dependency"]) == 120


def test_cross_folder_imports_are_grouped_and_graph_backed(tmp_path):
    atlas = analyze(tmp_path, {
        "client/main.ts": 'import "../shared/util"; import "@unknown/external";',
        "client/other.ts": 'import "../shared/util";',
        "shared/util.ts": 'export function util() {}',
        "shared/local.ts": 'import "./util";',
    })
    cards = [i for i in atlas.report.architecture.items
             if i.category == "boundary_dependency"]
    assert len(cards) == 1
    card = cards[0]
    assert card.title == "client imports shared"
    assert card.metrics == {"import_paths": 2, "importing_files": 2, "target_files": 1}
    assert len(card.steps) == 4
    assert card.basis == "inferred"
    assert AtlasDocument.model_validate_json(atlas.model_dump_json()) == atlas


def test_schema_rejects_report_evidence_from_uncited_locations(tmp_path):
    atlas = analyze(tmp_path, {"src/main.ts": "export function run() {}"})
    data = atlas.model_dump()
    data["report"]["architecture"]["items"][0]["evidence"][0]["path"] = "invented.ts"
    with pytest.raises(ValidationError, match="cited nodes"):
        AtlasDocument.model_validate(data)


def test_import_cycle_recommendation_uses_existing_links(tmp_path):
    atlas = analyze(tmp_path, {
        "a.ts": 'import "./b";', "b.ts": 'import "./a"; import "./leaf";',
        "leaf.ts": '', "entry.ts": 'import "./a";',
    })
    cycles = [i for i in atlas.report.recommendations.items if i.category == "import_cycle"]
    assert len(cycles) == 1
    assert cycles[0].metrics == {"files_in_component": 2, "internal_import_paths": 2}
    assert len(cycles[0].steps) == 4
    assert cycles[0].verification and cycles[0].approach
    assert AtlasDocument.model_validate_json(atlas.model_dump_json()) == atlas
