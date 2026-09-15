import pytest
from pydantic import ValidationError

from app.analyzer import analyze_repository
from app.ingestion import IngestionError
from app.models import AtlasDocument
from app.settings import Settings


def analyze(root, **limits):
    return analyze_repository(root, "https://github.com/org/repo.git", "main",
                              Settings(**limits), lambda *_: None)


def write_sources(root, sources):
    for path, content in sources.items():
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        (root / path).write_text(content, encoding="utf-8")


def resolved_imports(atlas):
    by_id = {node.id: node for node in atlas.nodes}
    return {(by_id[edge.source].path, by_id[edge.source].label, by_id[edge.target].path)
            for edge in atlas.relationships
            if edge.type == "RESOLVES_TO" and by_id[edge.source].kind == "import"}


def test_python_and_tool_caches_are_not_indexed(tmp_path):
    write_sources(tmp_path, {
        "app/main.py": "def run():\n    return 1\n",
        "app/__pycache__/main.cpython-312.pyc": "compiled",
        ".pytest_cache/v/cache/lastfailed": "{}",
        ".mypy_cache/3.12/app.meta.json": "{}",
        ".ruff_cache/content": "cache",
    })
    atlas = analyze(tmp_path)
    assert [node.path for node in atlas.nodes if node.kind == "file"] == ["app/main.py"]


def test_tsconfig_path_aliases_resolve_as_data_only(tmp_path):
    write_sources(tmp_path, {
        "tsconfig.base.json": '{\n  // Shared aliases\n  "compilerOptions": {\n'
                              '    "baseUrl": ".",\n'
                              '    "paths": {"@/*": ["./src/*"], "@config": ["./config/index.ts"],},\n'
                              '  },\n}\n',
        "tsconfig.json": '{ "extends": "./tsconfig.base.json", /* inherited */ '
                         '"compilerOptions": {"strict": true} }',
        "src/app.ts": 'import { a } from "@/lib/a"; import cfg from "@config"; '
                      'import { b } from "lib2/b"; import { d } from "@/dup"; '
                      'import { m } from "@/missing"; import { e } from "@/x/../../../outside"; '
                      'import React from "react";',
        "src/lib/a.ts": "export const a = 1;",
        "src/dup.ts": "export const d = 1;",
        "src/dup/index.ts": "export const d = 2;",
        "config/index.ts": "export default {};",
        "lib2/b.ts": "export const b = 2;",
        "packages/web/tsconfig.json": '{"compilerOptions": {"paths": {"@/*": ["./app/*"]}}}',
        "packages/web/app/page.tsx": 'import { w } from "@/widget";',
        "packages/web/app/widget.tsx": "export const w = 1;",
        "packages/loop/tsconfig.json": '{"extends": "./tsconfig.json"}',
        "packages/loop/index.ts": 'import { c } from "@/cycle";',
    })
    atlas = analyze(tmp_path)
    # Ambiguous (@/dup), missing and repository-escaping targets stay unresolved.
    assert resolved_imports(atlas) == {
        ("src/app.ts", "@/lib/a", "src/lib/a.ts"),
        ("src/app.ts", "@config", "config/index.ts"),
        ("src/app.ts", "lib2/b", "lib2/b.ts"),
        ("packages/web/app/page.tsx", "@/widget", "packages/web/app/widget.tsx"),
    }
    local = {node.label: node.attributes["local_import"]
             for node in atlas.nodes if node.kind == "import"}
    assert local == {"@/lib/a": True, "@config": True, "lib2/b": True, "@/dup": True,
                     "@/missing": True, "@/x/../../../outside": True, "react": False,
                     "@/widget": True, "@/cycle": True}
    assert all(edge.resolution == "inferred"
               for edge in atlas.relationships if edge.type == "RESOLVES_TO")


def test_python_absolute_imports_resolve_from_the_enclosing_project_root(tmp_path):
    write_sources(tmp_path, {
        # A same-named root folder (here a Next.js app/) must not capture backend imports.
        "app/page.tsx": "export default function Page() { return null; }",
        "backend/pyproject.toml": '[project]\nname = "api"\ndependencies = []\n',
        "backend/app/__init__.py": "",
        "backend/app/main.py": "from app.jobs import run\nimport app.models\nimport fastapi\n",
        "backend/app/jobs.py": "def run():\n    return 1\n",
        "backend/app/models.py": "VALUE = 1\n",
        "backend/tests/test_jobs.py": "from app.jobs import run\n",
        "worker/setup.cfg": "[metadata]\nname = worker\n",
        "worker/src/tasks/__init__.py": "",
        "worker/src/tasks/queue.py": "from tasks.util import helper\n",
        "worker/src/tasks/util.py": "def helper():\n    return 1\n",
    })
    atlas = analyze(tmp_path)
    assert resolved_imports(atlas) == {
        ("backend/app/main.py", "app.jobs", "backend/app/jobs.py"),
        ("backend/app/main.py", "app.models", "backend/app/models.py"),
        ("backend/tests/test_jobs.py", "app.jobs", "backend/app/jobs.py"),
        ("worker/src/tasks/queue.py", "tasks.util", "worker/src/tasks/util.py"),
    }
    fastapi = next(node for node in atlas.nodes
                   if node.kind == "import" and node.label == "fastapi")
    assert fastapi.attributes["local_import"] is False


def test_imports_are_classified_as_local_or_external(tmp_path):
    # The Architecture map counts only local imports as unresolved gaps.
    sources = {
        "web/app.ts": 'import React from "react"; import { x } from "../lib/core"; '
                      'import { y } from "./missing"; import { z } from "@/lib/z"; '
                      'import scoped from "@scope/pkg";',
        "lib/core.ts": "export const x = 1;",
        "svc/__init__.py": "",
        "svc/main.py": "import os\nimport requests\nfrom svc.helper import run\n"
                       "from svc.gone import thing\nfrom . import sibling\n",
        "svc/helper.py": "def run():\n    return 1\n",
        "go.mod": "module example.com/app\n\ngo 1.22\n",
        "cmd/main.go": 'package main\n\nimport (\n\t"fmt"\n\t"example.com/app/internal/util"\n)\n',
        "internal/util/util.go": "package util\n",
        "Api.cs": "using System;\nusing MyApp.Services;\nclass Api {}\n",
    }
    for path, content in sources.items():
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / path).write_text(content, encoding="utf-8")
    atlas = analyze(tmp_path)
    local = {node.label: node.attributes["local_import"]
             for node in atlas.nodes if node.kind == "import"}
    assert local == {
        "react": False, "../lib/core": True, "./missing": True,
        "@/lib/z": True, "@scope/pkg": False,
        "os": False, "requests": False, "svc.helper": True, "svc.gone": True, ".": True,
        "fmt": False, "example.com/app/internal/util": True,
        "System": False, "MyApp.Services": False,
    }


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
