import pytest
from pydantic import ValidationError

from app.analyzer import analyze_repository
from app.ingestion import IngestionError
from app.models import AtlasDocument
from app.settings import Settings


def analyze(root, **limits):
    return analyze_repository(root, "https://github.com/org/repo.git", "main",
                              Settings(**limits), lambda *_: None)


def test_mixed_repository(tmp_path):
    sources = {
        "package.json": '{"dependencies":{"react":"19","typescript":"5"}}',
        "Api.csproj": '<Project Sdk="Microsoft.NET.Sdk.Web" />',
        "Api.cs": 'using System; class Api { public void Run() { '
                  'app.MapGet("/health", () => "ok"); } }',
        "View.tsx": 'import React from "react"; export const View = () => <div />;',
        "View.test.ts": 'export function testView() {}',
        "README.md": "Inventory only",
        ".env": "DO_NOT_REPORT_ME",
        "credentials.json": "DO_NOT_REPORT_ME",
    }
    for path, content in sources.items():
        (tmp_path / path).write_text(content, encoding="utf-8")
    atlas = analyze(tmp_path)
    assert set(atlas.technologies) == {"React", "TypeScript", "C#", "Node.js",
                                       ".NET", "ASP.NET Core"}
    assert atlas.counts["files"] == 6
    assert atlas.counts["projects"] == 2
    assert atlas.counts["tests"] == 1
    assert atlas.counts["routes"] == 1
    assert {"Api", "Run", "View", "testView"} <= {n.label for n in atlas.nodes}
    imports = [e for e in atlas.relationships if e.type == "IMPORTS"]
    assert len(imports) == 2
    assert all(e.resolution == "unresolved" for e in imports)
    assert "DO_NOT_REPORT_ME" not in atlas.model_dump_json()
    assert not any(n.path in {".env", "credentials.json"} for n in atlas.nodes)
    assert AtlasDocument.model_validate_json(atlas.model_dump_json()) == atlas


def test_ids_survive_line_shifts_and_duplicate_references(tmp_path):
    path = tmp_path / "index.ts"
    source = ('import "react"; import "react"; '
              'app.get("/health", () => {}); app.get("/health", () => {}); '
              'export function run() {}')
    path.write_text(source)
    before = analyze(tmp_path)
    path.write_text("// unrelated comment\n\n" + source)
    after = analyze(tmp_path)
    assert [n.id for n in before.nodes] == [n.id for n in after.nodes]
    assert len({n.id for n in before.nodes}) == len(before.nodes)
    assert before.counts["routes"] == 2
    assert next(n for n in before.nodes if n.kind == "route").evidence[0].lines == "1-1"
    assert next(n for n in after.nodes if n.kind == "route").evidence[0].lines == "3-3"


def test_excluded_directories_and_oversized_sources(tmp_path):
    for directory in ("node_modules", ".aws", "secrets"):
        (tmp_path / directory).mkdir()
        (tmp_path / directory / "hidden.ts").write_text("function hidden() {}")
    (tmp_path / "large.ts").write_text(" " * 1025 + "function hidden() {}")
    atlas = analyze(tmp_path, max_source_bytes=1024)
    assert atlas.counts["files"] == 1
    assert atlas.counts["symbols"] == 0
    assert atlas.counts["skipped"] == 1


def test_graph_limit(tmp_path):
    (tmp_path / "index.ts").write_text("\n".join(f"function f{i}() {{}}" for i in range(20)))
    with pytest.raises(IngestionError, match="graph node limit"):
        analyze(tmp_path, max_nodes=10)


def test_schema_rejects_duplicate_ids_and_dangling_edges(tmp_path):
    (tmp_path / "index.ts").write_text("function run() {}")
    data = analyze(tmp_path).model_dump()
    data["nodes"].append(data["nodes"][0])
    with pytest.raises(ValidationError, match="Duplicate node"):
        AtlasDocument.model_validate(data)
    data["nodes"].pop()
    data["relationships"][0]["target"] = "missing"
    with pytest.raises(ValidationError, match="missing node"):
        AtlasDocument.model_validate(data)


def test_python_declarations_routes_and_module_resolution(tmp_path):
    sources = {
        "pyproject.toml": '[project]\nname = "svc"\ndependencies = ["fastapi>=0.1", "pydantic~=2"]\n'
                          '[project.optional-dependencies]\ndev = ["pytest>=8"]\n',
        "api.py": 'import os\nfrom pathlib import Path\nfrom .helpers import assist\n'
                  'class Service:\n    def run(self):\n        work()\n'
                  'def work(): pass\n'
                  '@app.get("/items")\ndef list_items(): return []\n'
                  '@app.route("/legacy")\ndef legacy(): return eval("1")\n',
        "helpers.py": "def assist(): pass\n",
    }
    for path, content in sources.items():
        (tmp_path / path).write_text(content, encoding="utf-8")
    atlas = analyze(tmp_path)
    assert {"Python", "FastAPI", "Pydantic"} <= set(atlas.technologies)
    kinds = {(n.label, n.kind) for n in atlas.nodes}
    # A def inside a class is a method; a module-level def stays a function.
    assert ("Service", "class") in kinds
    assert ("run", "method") in kinds
    assert ("work", "function") in kinds
    # FastAPI states the verb; @app.route does not, so it is recorded as ANY.
    routes = {n.label for n in atlas.nodes if n.kind == "route"}
    assert routes == {"GET /items", "ANY /legacy"}
    by_id = {n.id: n for n in atlas.nodes}
    handlers = {(by_id[e.source].label, by_id[e.target].label)
                for e in atlas.relationships if e.type == "ROUTES_TO"}
    assert handlers == {("GET /items", "list_items"), ("ANY /legacy", "legacy")}
    # Only the relative import resolves; os and pathlib stay unresolved.
    resolved = [e for e in atlas.relationships if e.type == "RESOLVES_TO"]
    assert len(resolved) == 1
    assert by_id[resolved[0].source].label == ".helpers"
    assert by_id[resolved[0].target].path == "helpers.py"
    assert {n.attributes.get("rule") for n in atlas.nodes if n.kind == "observation"} == {
        "dynamic-code"}
    dependencies = {n.label for n in atlas.nodes if n.kind == "dependency"}
    # Names only: never version specifiers or markers.
    assert dependencies == {"fastapi", "pydantic", "pytest"}


def test_go_types_routes_and_package_resolution(tmp_path):
    sources = {
        "go.mod": "module example.com/app\n\ngo 1.22\n\nrequire (\n"
                  "\tgithub.com/gin-gonic/gin v1.9.1\n)\n",
        "main.go": 'package main\nimport (\n "fmt"\n "example.com/app/store"\n)\n'
                   "type Server struct{ n int }\ntype Repo interface{ Get() error }\n"
                   "func (s *Server) Handle() { save() }\nfunc save() {}\n"
                   'func main() { http.HandleFunc("/health", Handle); r.GET("/users", Handle) }\n',
        "store/store.go": "package store\nfunc Load() {}\n",
    }
    for path, content in sources.items():
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / path).write_text(content, encoding="utf-8")
    atlas = analyze(tmp_path)
    assert {"Go", "Gin"} <= set(atlas.technologies)
    kinds = {(n.label, n.kind) for n in atlas.nodes}
    # One Go node type declares structs, interfaces and aliases; the body decides.
    assert ("Server", "class") in kinds
    assert ("Repo", "interface") in kinds
    assert ("Handle", "method") in kinds
    assert ("save", "function") in kinds
    assert {n.label for n in atlas.nodes if n.kind == "route"} == {"ANY /health", "GET /users"}
    by_id = {n.id: n for n in atlas.nodes}
    # Go imports address a package directory, and stdlib stays unresolved.
    resolved = [e for e in atlas.relationships if e.type == "RESOLVES_TO"]
    assert len(resolved) == 1
    assert by_id[resolved[0].source].label == "example.com/app/store"
    assert by_id[resolved[0].target].kind == "directory"
    assert {n.label for n in atlas.nodes if n.kind == "dependency"} == {"github.com/gin-gonic/gin"}


def test_javascript_class_members_and_relative_imports(tmp_path):
    sources = {
        "package.json": '{"dependencies":{"express":"^4"}}',
        "app.js": 'import "./util";\nclass Widget { render() {} }\nfunction free() {}\n'
                  "const arrow = () => { free(); };\napp.get(\"/js\", free);\n",
        "util.js": "export function u() {}\n",
        "view.jsx": "export function View(){ return <div "
                    "dangerouslySetInnerHTML={{__html: x}} />; }\n",
    }
    for path, content in sources.items():
        (tmp_path / path).write_text(content, encoding="utf-8")
    atlas = analyze(tmp_path)
    assert {"JavaScript", "Express"} <= set(atlas.technologies)
    kinds = {(n.label, n.kind) for n in atlas.nodes}
    assert ("Widget", "class") in kinds
    assert ("render", "method") in kinds
    assert ("free", "function") in kinds
    assert {n.label for n in atlas.nodes if n.kind == "route"} == {"GET /js"}
    assert {n.attributes.get("rule") for n in atlas.nodes if n.kind == "observation"} == {
        "raw-html"}
    by_id = {n.id: n for n in atlas.nodes}
    resolved = [e for e in atlas.relationships if e.type == "RESOLVES_TO"]
    assert [by_id[e.target].path for e in resolved] == ["util.js"]


def test_typescript_class_members_are_indexed(tmp_path):
    (tmp_path / "svc.ts").write_text(
        "export class Svc { doWork() { return 1; } helper() {} }\nfunction free() {}\n",
        encoding="utf-8")
    atlas = analyze(tmp_path)
    # method_definition is the TypeScript/JavaScript class-member node type.
    assert {(n.label, n.kind) for n in atlas.nodes if n.kind in {"class", "method", "function"}} == {
        ("Svc", "class"), ("doWork", "method"), ("helper", "method"), ("free", "function")}
    assert atlas.counts["symbols"] == 4


def test_requirements_and_invalid_manifests_are_bounded(tmp_path):
    sources = {
        "requirements.txt": "flask==3.0.0\n# comment\n-r other.txt\n--hash=abc\n\ndjango>=4\n",
        "broken/pyproject.toml": "this is not [ valid toml\n",
        "app.py": "print(1)\n",
    }
    for path, content in sources.items():
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / path).write_text(content, encoding="utf-8")
    atlas = analyze(tmp_path)
    assert {"Flask", "Django"} <= set(atlas.technologies)
    # Requirement options and comments are not package names.
    assert {n.label for n in atlas.nodes if n.kind == "dependency"} == {"flask", "django"}
    assert any("Invalid TOML" in line for line in atlas.limitations)
    AtlasDocument.model_validate(atlas.model_dump())
