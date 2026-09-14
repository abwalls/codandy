"""Syntax facts only: never load repository tooling or include source bodies."""

import hashlib
import json
import os
import posixpath
import re
import time
import tomllib
import xml.etree.ElementTree as ET
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import tree_sitter_c_sharp
import tree_sitter_go
import tree_sitter_javascript
import tree_sitter_python
import tree_sitter_typescript
from tree_sitter import Language, Parser

from app.dependency_versions import enrich_central_nuget, enrich_dependencies, go_requirements
from app.ingestion import IngestionError, check_workspace
from app.models import AtlasDocument, AtlasNode, AtlasRelationship, Evidence
from app.reporting import generate_report
from app.settings import Settings

EXCLUDED_DIRS = {".git", ".codandy", ".codeatlas", "node_modules", "bin", "obj", "dist", "build",
                 ".venv", "vendor", ".next", ".ssh", ".aws", ".azure"}
SECRET_NAME = re.compile(
    r"(^\.env|^id_(rsa|ed25519|ecdsa)|credential|secret|^\.npmrc$|^\.pypirc$|"
    r"^\.netrc$|^appsettings.*\.json$|^web\.config$|^nuget\.config$|"
    r"\.(pem|key|pfx|p12|keystore|jks)$)", re.IGNORECASE)
# Suffix -> (technology label, grammar factory). Grammars load lazily per repository.
LANGUAGES = {
    ".cs": ("C#", tree_sitter_c_sharp.language),
    ".ts": ("TypeScript", tree_sitter_typescript.language_typescript),
    ".tsx": ("TypeScript", tree_sitter_typescript.language_tsx),
    ".js": ("JavaScript", tree_sitter_javascript.language),
    ".jsx": ("JavaScript", tree_sitter_javascript.language),
    ".mjs": ("JavaScript", tree_sitter_javascript.language),
    ".cjs": ("JavaScript", tree_sitter_javascript.language),
    ".py": ("Python", tree_sitter_python.language),
    ".pyi": ("Python", tree_sitter_python.language),
    ".go": ("Go", tree_sitter_go.language),
}
# Grammar node types are language-specific; same-named types carry the same meaning here.
DECLARATIONS = {
    "class_declaration": "class", "interface_declaration": "interface",
    "method_declaration": "method", "function_declaration": "function",
    "enum_declaration": "enum", "type_alias_declaration": "type",
    "record_declaration": "class", "struct_declaration": "class",
    # TypeScript/JavaScript class members and abstract/generator forms.
    "method_definition": "method", "abstract_class_declaration": "class",
    "generator_function_declaration": "function",
    # Python.
    "class_definition": "class", "function_definition": "function",
    # Go interface method signatures; Go type_spec is resolved from its body node.
    "method_elem": "method",
}
GO_TYPE_BODIES = {"struct_type": "class", "interface_type": "interface"}
# Import source text lives in different fields per grammar; the first present field wins.
IMPORT_SOURCE_FIELDS = {
    "import_statement": ("source", "name"), "import_from_statement": ("module_name",),
    "import_spec": ("path",), "using_directive": ("source",),
}
CALL_TYPES = {"invocation_expression", "call_expression", "call"}
STRING_TYPES = {"string", "string_literal", "interpreted_string_literal", "raw_string_literal"}
ROUTE_VERBS = {
    "MapGet": "GET", "MapPost": "POST", "MapPut": "PUT", "MapDelete": "DELETE",
    "MapPatch": "PATCH", "get": "GET", "post": "POST", "put": "PUT", "delete": "DELETE",
    "patch": "PATCH",
    # Go/gin-style uppercase receivers.
    "GET": "GET", "POST": "POST", "PUT": "PUT", "DELETE": "DELETE", "PATCH": "PATCH",
    # Method-agnostic registrations; the verb is not stated in source.
    "route": "ANY", "HandleFunc": "ANY", "Handle": "ANY",
}
# Dynamic-code APIs by language label; syntax only, binding and input trust unknown.
DYNAMIC_CODE_APIS = {"TypeScript": {"eval"}, "JavaScript": {"eval"},
                     "Python": {"eval", "exec"}}
SCRIPT_SUFFIXES = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")
# tsconfig/jsconfig files are read as data for import path aliases; TypeScript never runs.
TS_CONFIG_NAME = re.compile(r"[tj]sconfig(?:\.[A-Za-z0-9_-]+)*\.json")
MAX_TS_CONFIG_BYTES = 256_000
# A directory holding one of these is a root for absolute Python imports.
PYTHON_PROJECT_FILES = {"pyproject.toml", "setup.py", "setup.cfg", "requirements.txt"}
# Which manifest kinds may own a source file of each language.
LANGUAGE_MANIFESTS = {
    "TypeScript": ("package.json",), "JavaScript": ("package.json",),
    "C#": (".csproj", ".fsproj", ".vbproj"),
    "Python": ("pyproject.toml", "requirements.txt"), "Go": ("go.mod",),
}
REQUIREMENT_NAME = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]{0,99})")
BASE_LIMITATIONS = [
    ("Syntax indexing supports C#, TypeScript/TSX, JavaScript/JSX, Python and Go; other files "
     "are inventory only."),
    ("Local imports link to unique source-path candidates only: relative TypeScript/JavaScript "
     "specifiers and tsconfig/jsconfig paths and baseUrl aliases (relative extends only), "
     "relative Python modules and absolute modules under the enclosing Python project root "
     "(including src/) or the repository root, and Go package directories under the declared "
     "module path. Bundler aliases, package exports/imports fields, project references, build "
     "tags and installed-package resolution are not evaluated. Other imports remain "
     "unresolved."),
    ("Routes are inferred literal candidates from minimal-API, Express, Flask/FastAPI decorator "
     "and Go mux/gin registration syntax. Method-agnostic registrations are recorded as ANY "
     "because the verb is not stated in source. Controller prefixes, router mount prefixes, "
     "middleware, dynamic paths and framework file routing are not reconstructed."),
    ("Tests are candidate test files, not executed test cases. Components are function declarations "
     "or arrow functions; React semantics are not verified."),
    ("Reports summarize static structure and partial route/local-call paths. Runtime behavior, "
     "named architecture patterns, exploitability, and AI explanations are not verified."),
    ("Sensitive paths, binary content and oversized sources are excluded, and the atlas artifact "
     "itself carries no source bodies. The source viewer reads text retained by the analysis "
     "service, which expires with the report. This is not a secrets audit."),
]


def identity(kind: str, path: str, name: str = "") -> str:
    return f"{kind}:" + hashlib.sha256(f"{path}\0{name}".encode()).hexdigest()[:24]


def python_requirements(entries: object) -> list[str]:
    """Distribution names only: never versions, markers, URLs or requirement options."""
    names = []
    if not isinstance(entries, list):
        return names
    for entry in entries:
        if not isinstance(entry, str):
            continue
        match = REQUIREMENT_NAME.match(entry.strip())
        if match:
            names.append(match.group(1))
    return names


def jsonc_loads(text: str):
    """Parse tsconfig-style JSON (comments, trailing commas) as data; nothing is evaluated."""
    output = []
    index, length, in_string = 0, len(text), False
    while index < length:
        char = text[index]
        if in_string:
            if char == "\\":
                output.append(text[index:index + 2])
                index += 2
                continue
            in_string = char != '"'
        elif char == '"':
            in_string = True
        elif text.startswith("//", index):
            end = text.find("\n", index)
            index = length if end < 0 else end
            continue
        elif text.startswith("/*", index):
            end = text.find("*/", index + 2)
            index = length if end < 0 else end + 2
            continue
        elif char in "}]":
            # Drop a trailing comma before the closing bracket; strings are already copied.
            position = len(output) - 1
            while position >= 0 and output[position].isspace():
                position -= 1
            if position >= 0 and output[position] == ",":
                del output[position]
        output.append(char)
        index += 1
    return json.loads("".join(output))


def reference_name(references: dict, kind: str, name: str) -> str:
    key = (kind, name)
    references[key] = references.get(key, 0) + 1
    return f"{name}#{references[key]}"


def analyze_repository(root: Path, url: str, ref: str | None, limits: Settings,
                       progress: Callable[[str, int], None]) -> AtlasDocument:
    deadline = time.monotonic() + limits.analysis_timeout_seconds
    check_workspace(root, limits)
    nodes: list[AtlasNode] = []
    edges: list[AtlasRelationship] = []
    technologies: set[str] = set()
    limitations = list(BASE_LIMITATIONS)
    counts = {"files": 0, "symbols": 0, "routes": 0, "tests": 0, "projects": 0, "skipped": 0}
    pending_calls = {}
    pending_handlers = []
    pending_project_references = []
    project_reference_counts = {}
    declarations = {}
    parents = {}
    file_ids = {}
    node_kinds = {}

    def guard():
        if time.monotonic() > deadline:
            raise IngestionError("Static analysis timed out")
        if len(nodes) >= limits.max_nodes:
            raise IngestionError("Repository exceeds graph node limit")

    def add(kind, path, name, reason, line=None, confidence=100, parent=None):
        guard()
        evidence = Evidence(path=path, lines=line, reason=reason)
        node = AtlasNode(id=identity(kind, path, name), kind=kind, label=name,
                         detail=reason, path=path, confidence=confidence, evidence=[evidence])
        nodes.append(node)
        node_kinds[node.id] = kind
        if parent:
            parents[node.id] = parent
            edges.append(AtlasRelationship(source=parent, target=node.id, type="CONTAINS",
                                           resolution="resolved", confidence=100,
                                           evidence=[evidence]))
        return node.id

    def link(source, target, kind, reason, *, resolution="inferred", confidence=80, lines=None):
        edges.append(AtlasRelationship(source=source, target=target, type=kind,
            resolution=resolution, confidence=confidence,
            evidence=[Evidence(path=path, lines=lines, reason=reason)]))

    repo_id = add("repository", "", url.removeprefix("https://github.com/").removesuffix(".git"),
                  "Submitted repository")
    files = []
    for directory, directories, filenames in os.walk(root):
        guard()
        directories[:] = sorted(d for d in directories
                                if d.lower() not in EXCLUDED_DIRS and not SECRET_NAME.search(d))
        for name in sorted(filenames):
            path = Path(directory) / name
            if SECRET_NAME.search(name):
                counts["skipped"] += 1
            else:
                files.append(path)
    parser_cache: dict[str, Parser] = {}

    def parser_for(suffix: str) -> Parser:
        if suffix not in parser_cache:
            parser_cache[suffix] = Parser(Language(LANGUAGES[suffix][1]()))
        return parser_cache[suffix]

    go_modules: dict[str, str] = {}
    ts_configs: dict[str, str] = {}
    python_projects: set[str] = set()

    def declare_python_dependencies(path, project_id, requirements):
        declared = set()
        for name in requirements:
            if name in declared or name.lower() == "python":
                continue
            declared.add(name)
            for label, technology in (("fastapi", "FastAPI"), ("django", "Django"),
                                      ("flask", "Flask"), ("pydantic", "Pydantic")):
                if name.lower() == label:
                    technologies.add(technology)
            dep_id = add("dependency", path, name, "Declared Python dependency")
            link(project_id, dep_id, "DEPENDS_ON", "Manifest dependency declaration",
                 resolution="resolved", confidence=100)
    directory_ids = {".": repo_id}
    for index, file in enumerate(files):
        guard()
        path = file.relative_to(root).as_posix()
        parent_path = Path(path).parent
        for directory in reversed([parent_path, *parent_path.parents]):
            key = directory.as_posix()
            if key not in directory_ids:
                directory_ids[key] = add("directory", key, directory.name, "Repository directory",
                                         parent=directory_ids[directory.parent.as_posix()])
        file_id = add("file", path, file.name, "Repository file",
                      parent=directory_ids[parent_path.as_posix()])
        file_ids[path] = file_id
        counts["files"] += 1
        if file.name in PYTHON_PROJECT_FILES:
            python_projects.add(posixpath.dirname(path))
        suffix = file.suffix.lower()
        if suffix in LANGUAGES:
            technologies.add(LANGUAGES[suffix][0])
        if re.search(r"(^|[./_-])(tests?|specs?)([./_-]|$)", path, re.IGNORECASE) or re.search(
                r"Tests?\.cs$", path):
            counts["tests"] += 1
            add("test", path, file.name, "Test file naming convention", confidence=70,
                parent=file_id)
        manifest = (file.name in {"package.json", "pyproject.toml", "requirements.txt", "go.mod"}
                    or suffix in {".csproj", ".fsproj", ".vbproj"})
        if manifest:
            counts["projects"] += 1
            project_id = add("project", path, file.name, "Project manifest", parent=file_id)
        if file.stat().st_size > limits.max_source_bytes:
            counts["skipped"] += 1
            continue
        if TS_CONFIG_NAME.fullmatch(file.name):
            # Read as data for import path aliases only; TypeScript itself is never run.
            config = file.read_bytes()
            if len(config) <= MAX_TS_CONFIG_BYTES and b"\0" not in config:
                try:
                    ts_configs[path] = config.decode("utf-8-sig")
                except UnicodeDecodeError:
                    pass
            continue
        if suffix not in LANGUAGES and not manifest:
            continue
        data = file.read_bytes()
        if b"\0" in data:
            counts["skipped"] += 1
            continue
        if manifest:
            if file.name == "package.json":
                technologies.add("Node.js")
                try:
                    package = json.loads(data)
                    for group in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
                        dependencies = package.get(group, {})
                        for dependency, label in {"react": "React", "next": "Next.js",
                                                  "typescript": "TypeScript", "express": "Express",
                                                  "vue": "Vue", "@angular/core": "Angular",
                                                  "svelte": "Svelte"}.items():
                            if isinstance(dependencies, dict) and dependency in dependencies:
                                technologies.add(label)
                        if isinstance(dependencies, dict):
                            for dependency in sorted(dependencies)[:500]:
                                if re.fullmatch(r"(?:@[a-z0-9_.-]+/)?[a-z0-9_.-]{1,100}", dependency):
                                    dep_id = add("dependency", path, f"{group}:{dependency}",
                                                 "Declared package dependency")
                                    nodes[-1].label = dependency
                                    nodes[-1].attributes = {"group": group}
                                    link(project_id, dep_id, "DEPENDS_ON", "Manifest dependency declaration",
                                         resolution="resolved", confidence=100)
                    scripts = package.get("scripts", {})
                    if isinstance(scripts, dict):
                        for name in sorted(scripts)[:100]:
                            if re.fullmatch(r"(?:build|dev|start|test|lint|check|typecheck)(?::[a-z0-9_-]+)?", name):
                                add("task", path, name, "Declared package task name; command not executed",
                                    parent=project_id)
                except (ValueError, AttributeError, UnicodeError):
                    counts["skipped"] += 1
            elif suffix in {".csproj", ".fsproj", ".vbproj"}:
                technologies.add(".NET")
                if b'Microsoft.NET.Sdk.Web' in data:
                    technologies.add("ASP.NET Core")
                if not re.search(br"<!\s*(?:DOCTYPE|ENTITY)", data, re.IGNORECASE):
                    try:
                        document = ET.fromstring(data)
                        package_names = set()
                        for reference in document.iter():
                            if reference.tag.rsplit("}", 1)[-1] == "ProjectReference":
                                include = reference.attrib.get("Include", "")
                                key = (path, include)
                                project_reference_counts[key] = project_reference_counts.get(key, 0) + 1
                                reference_id = add("project_reference", path,
                                    f"{include}#{project_reference_counts[key]}",
                                    "ProjectReference declaration; MSBuild conditions and metadata are not evaluated",
                                    parent=project_id)
                                nodes[-1].label = "Unresolved project reference"
                                pending_project_references.append((project_id, reference_id, include))
                                continue
                            if reference.tag.rsplit("}", 1)[-1] != "PackageReference":
                                continue
                            name = reference.attrib.get("Include", "")
                            if re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", name) and name not in package_names:
                                package_names.add(name)
                                dep_id = add("dependency", path, name, "Declared NuGet dependency")
                                link(project_id, dep_id, "DEPENDS_ON", "Manifest PackageReference",
                                     resolution="resolved", confidence=100)
                    except ET.ParseError:
                        limitations.append(f"Invalid project XML in {path}; dependency detection skipped.")
            elif file.name == "pyproject.toml":
                technologies.add("Python")
                try:
                    document = tomllib.loads(data.decode("utf-8"))
                except (tomllib.TOMLDecodeError, UnicodeDecodeError):
                    limitations.append(f"Invalid TOML in {path}; dependency detection skipped.")
                else:
                    project_table = document.get("project")
                    requirements = []
                    if isinstance(project_table, dict):
                        requirements.extend(python_requirements(project_table.get("dependencies")))
                        extras = project_table.get("optional-dependencies")
                        if isinstance(extras, dict):
                            for group in sorted(extras):
                                requirements.extend(python_requirements(extras[group]))
                    poetry = document.get("tool", {})
                    poetry = poetry.get("poetry", {}) if isinstance(poetry, dict) else {}
                    if isinstance(poetry, dict) and isinstance(poetry.get("dependencies"), dict):
                        requirements.extend(python_requirements(list(poetry["dependencies"])))
                    declare_python_dependencies(path, project_id, requirements)
            elif file.name == "requirements.txt":
                technologies.add("Python")
                try:
                    listing = data.decode("utf-8").splitlines()
                except UnicodeDecodeError:
                    limitations.append(f"Undecodable requirements in {path}; dependencies skipped.")
                else:
                    # Requirement options (-r, -e, --hash) and URLs are not package names.
                    declare_python_dependencies(path, project_id, python_requirements(
                        [line for line in listing
                         if line.strip() and not line.lstrip().startswith(("#", "-"))]))
            elif file.name == "go.mod":
                technologies.add("Go")
                try:
                    listing = data.decode("utf-8")
                except UnicodeDecodeError:
                    limitations.append(f"Undecodable go.mod in {path}; dependencies skipped.")
                else:
                    module = re.search(r"^module\s+(\S{1,200})\s*$", listing, re.MULTILINE)
                    if module:
                        go_modules[posixpath.dirname(path)] = module.group(1)
                        nodes[-1].attributes["module"] = module.group(1)
                    seen_requires = set()
                    for require, _ in go_requirements(listing):
                        if require in seen_requires or require == "go":
                            continue
                        seen_requires.add(require)
                        for label, technology in (("gin-gonic/gin", "Gin"),
                                                  ("labstack/echo", "Echo"),
                                                  ("go-chi/chi", "Chi")):
                            if label in require:
                                technologies.add(technology)
                        dep_id = add("dependency", path, require, "Declared Go module requirement")
                        link(project_id, dep_id, "DEPENDS_ON", "go.mod require directive",
                             resolution="resolved", confidence=100)
            continue
        # Byte-input parsing cannot be interrupted; guard immediately afterward.
        # JobStore's process boundary enforces the hard native-parser deadline.
        language = LANGUAGES[suffix][0]
        tree = parser_for(suffix).parse(data)
        guard()
        if tree.root_node.has_error:
            limitations.append(f"Syntax errors in {path}; partial declarations only.")
        stack = [(tree.root_node, file_id)]
        seen: dict[tuple[str, str], int] = {}
        references: dict[tuple[str, str], int] = {}
        handler_scopes = {}
        # Python registers routes on the decorator, so the handler name lives on the
        # definition below it rather than in the call arguments.
        decorator_targets: dict[int, str] = {}
        if language == "Python":
            scan = [tree.root_node]
            while scan:
                guard()
                current = scan.pop()
                if current.type == "decorated_definition":
                    definition = current.child_by_field_name("definition")
                    named = definition.child_by_field_name("name") if definition else None
                    if named:
                        decorated_name = data[named.start_byte:named.end_byte].decode(
                            "utf-8", errors="replace")
                        for decorator in current.named_children:
                            if decorator.type != "decorator":
                                continue
                            for inner in decorator.named_children:
                                if inner.type == "call":
                                    decorator_targets[inner.start_byte] = decorated_name
                scan.extend(current.named_children)

        while stack:
            guard()
            syntax, parent = stack.pop()
            parent = handler_scopes.get(syntax.start_byte, parent)
            if syntax.type in {"comment", "ERROR"}:
                continue
            kind = DECLARATIONS.get(syntax.type)
            if syntax.type == "variable_declarator":
                value = syntax.child_by_field_name("value")
                if value and value.type in {"arrow_function", "function_expression"}:
                    kind = "function"
            elif syntax.type == "type_spec":
                # Go names struct, interface and alias types with one node type.
                body = next((c for c in syntax.named_children if c.type in GO_TYPE_BODIES), None)
                kind = GO_TYPE_BODIES[body.type] if body else "type"
            elif kind == "function" and node_kinds.get(parent) == "class":
                # Python declares methods with the same node type as free functions.
                kind = "method"
            name_node = syntax.child_by_field_name("name")
            lines = f"{syntax.start_point.row + 1}-{syntax.end_point.row + 1}"
            if kind and name_node:
                name = data[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="replace")
                key = (parent, name)
                seen[key] = seen.get(key, 0) + 1
                # Parent and overload ordinal distinguish duplicate declarations without line IDs.
                qualified = f"{parent}/{name}#{seen[key]}"
                node_id = add(kind, path, qualified, "Syntax declaration", lines, parent=parent)
                nodes[-1].label = name
                nodes[-1].attributes["line_count"] = syntax.end_point.row - syntax.start_point.row + 1
                declarations.setdefault((parent, name), []).append(node_id)
                parent = node_id
                counts["symbols"] += 1
            if syntax.type in IMPORT_SOURCE_FIELDS:
                sources = []
                for field in IMPORT_SOURCE_FIELDS[syntax.type]:
                    sources = [n for n in syntax.children_by_field_name(field) if n is not None]
                    if sources:
                        break
                if not sources and syntax.type == "using_directive":
                    fallback = next((n for n in reversed(syntax.named_children)
                                     if n.type in {"identifier", "qualified_name"}), None)
                    sources = [fallback] if fallback else []
                for source in sources:
                    # Python aliases wrap the module name in an aliased_import node.
                    if source.type == "aliased_import":
                        source = source.child_by_field_name("name") or source
                    name = data[source.start_byte:source.end_byte].decode(
                        "utf-8", errors="replace").strip("\"'`")
                    # Only import-like strings, never arbitrary literals/URLs/credentials.
                    if re.fullmatch(r"[@\w./-]{1,200}", name):
                        target = add("import", path, reference_name(references, "import", name),
                                     "Unresolved import reference", lines, confidence=80)
                        nodes[-1].label = name
                        nodes[-1].attributes["language"] = language
                        edges.append(AtlasRelationship(source=file_id, target=target,
                            type="IMPORTS", resolution="unresolved", confidence=80,
                            evidence=nodes[-1].evidence))
            if syntax.type in CALL_TYPES:
                function = syntax.child_by_field_name("function")
                args = syntax.child_by_field_name("arguments")
                if function and args:
                    method = data[function.start_byte:function.end_byte].decode(
                        "utf-8", errors="replace").rsplit(".", 1)[-1]
                    if function.type == "identifier" and re.fullmatch(r"[A-Za-z_$][\w$]*", method):
                        pending_calls.setdefault((parent, method, path), lines)
                    if (function.type == "identifier"
                            and method in DYNAMIC_CODE_APIS.get(language, frozenset())):
                        add("observation", path, reference_name(references, "risk", "dynamic-code"),
                            f"Direct {method} call syntax; input trust and identifier binding unknown",
                            lines, confidence=65, parent=parent)
                        nodes[-1].attributes["rule"] = "dynamic-code"
                    verb = ROUTE_VERBS.get(method)
                    literal = args.named_children[0] if args.named_children else None
                    if literal and literal.type == "argument" and literal.named_children:
                        literal = literal.named_children[0]
                    if verb and literal and literal.type in STRING_TYPES:
                        route = data[literal.start_byte:literal.end_byte].decode(
                            "utf-8", errors="replace").strip("\"'`")
                        if re.fullmatch(r"/[\w/{}/:.-]{0,200}", route):
                            label = f"{verb} {route}"
                            route_id = add("route", path, reference_name(references, "route", label),
                                "Inferred literal route candidate", lines, confidence=65,
                                parent=file_id)
                            nodes[-1].label = label
                            counts["routes"] += 1
                            handler = args.named_children[-1]
                            if handler.type == "argument" and handler.named_children:
                                handler = handler.named_children[0]
                            decorated = decorator_targets.get(syntax.start_byte)
                            if decorated:
                                pending_handlers.append((route_id, parent, decorated, path, lines))
                            elif handler.type == "identifier":
                                handler_name = data[handler.start_byte:handler.end_byte].decode("utf-8", errors="replace")
                                pending_handlers.append((route_id, parent, handler_name, path, lines))
                            elif handler.type in {"arrow_function", "lambda_expression", "function_expression"}:
                                handler_id = add("handler", path, route_id, "Inline route handler syntax",
                                    f"{handler.start_point.row + 1}-{handler.end_point.row + 1}",
                                    parent=parent)
                                nodes[-1].label = f"{label} handler"
                                nodes[-1].attributes["line_count"] = handler.end_point.row - handler.start_point.row + 1
                                counts["symbols"] += 1
                                handler_scopes[handler.start_byte] = handler_id
                                link(route_id, handler_id, "ROUTES_TO", "Inline handler argument", lines=lines,
                                     confidence=65)
            if language in {"TypeScript", "JavaScript"} and syntax.type == "jsx_attribute":
                attribute = syntax.named_children[0] if syntax.named_children else None
                if attribute and data[attribute.start_byte:attribute.end_byte] == b"dangerouslySetInnerHTML":
                    add("observation", path, reference_name(references, "risk", "raw-html"),
                        "Raw HTML JSX attribute; input trust and sanitization unknown", lines,
                        confidence=65, parent=parent)
                    nodes[-1].attributes["rule"] = "raw-html"
            stack.extend((child, parent) for child in reversed(syntax.named_children))
        if index % 100 == 0:
            progress("indexing", 35 + int(50 * (index + 1) / max(1, len(files))))
    progress("linking", 85)
    by_id = {node.id: node for node in nodes}

    def local_declaration(scope, name):
        while scope:
            candidates = declarations.get((scope, name), [])
            if candidates:
                return candidates[0] if len(candidates) == 1 else None
            scope = parents.get(scope)
        return None

    for (source, name, path), lines in pending_calls.items():
        guard()
        target = local_declaration(source, name)
        if target and by_id[source].kind in {"function", "method", "handler"}:
            link(source, target, "CALLS", "Unique lexical declaration name candidate; binding not verified",
                 lines=lines, confidence=75)
    for route, scope, name, path, lines in pending_handlers:
        target = local_declaration(scope, name)
        if target:
            link(route, target, "ROUTES_TO", "Named handler argument matches local declaration",
                 lines=lines, confidence=65)
    def go_module_for(file_path):
        """The declared module of the nearest enclosing go.mod, if any."""
        best_dir, best_module = None, None
        for module_dir, module_path in go_modules.items():
            if module_dir and not file_path.startswith(module_dir + "/"):
                continue
            if best_dir is None or len(module_dir) > len(best_dir):
                best_dir, best_module = module_dir, module_path
        return best_dir, best_module

    def python_roots_for(file_path):
        """Absolute-import prefixes: enclosing Python projects (src/ layout first), nearest
        project first, then the repository root."""
        prefixes = []
        for project in sorted(python_projects, key=len, reverse=True):
            if project and not file_path.startswith(project + "/"):
                continue
            for folder in (posixpath.join(project, "src"), project):
                if folder and folder in directory_ids and f"{folder}/" not in prefixes:
                    prefixes.append(f"{folder}/")
        return [*prefixes, ""]

    parsed_ts_configs: dict[str, object] = {}

    def ts_options(config_path, chain=()):
        """baseUrl and paths for one config, with relative `extends` applied as data."""
        if config_path in chain or len(chain) > 8 or config_path not in ts_configs:
            return {}
        if config_path not in parsed_ts_configs:
            try:
                parsed_ts_configs[config_path] = jsonc_loads(ts_configs[config_path])
            except (ValueError, RecursionError):
                parsed_ts_configs[config_path] = None
                limitations.append(
                    f"Unreadable {config_path}; its import path aliases were not applied.")
        document = parsed_ts_configs[config_path]
        if not isinstance(document, dict):
            return {}
        config_dir = posixpath.dirname(config_path)
        options = {}
        extends = document.get("extends")
        for parent in extends if isinstance(extends, list) else [extends]:
            # Package extends (e.g. @tsconfig/node20) would need installed packages.
            if isinstance(parent, str) and parent.startswith("."):
                target = posixpath.normpath(posixpath.join(config_dir, parent))
                options.update(ts_options(target if target.endswith(".json") else target + ".json",
                                          (*chain, config_path)))
        compiler = document.get("compilerOptions")
        if isinstance(compiler, dict):
            if isinstance(compiler.get("baseUrl"), str):
                options["base_url"] = posixpath.normpath(
                    posixpath.join(config_dir, compiler["baseUrl"]))
            if isinstance(compiler.get("paths"), dict):
                options["paths"] = compiler["paths"]
                options["paths_dir"] = config_dir
        return options

    def inside_repository(candidate):
        return (candidate not in {"", ".", ".."} and not candidate.startswith(("../", "/"))
                and ":" not in candidate)

    def ts_alias_bases(file_path, label):
        """(label matched a declared paths alias, candidate base paths) from the nearest
        tsconfig.json or jsconfig.json above the importing file."""
        folder, config = posixpath.dirname(file_path), None
        while config is None:
            config = next((candidate for name in ("tsconfig.json", "jsconfig.json")
                           if (candidate := posixpath.join(folder, name)) in ts_configs), None)
            if config is None and not folder:
                return False, []
            folder = posixpath.dirname(folder)
        options = ts_options(config)
        paths = options.get("paths", {})
        # TypeScript resolves paths from baseUrl when set, otherwise from the defining config.
        root = options.get("base_url", options.get("paths_dir", ""))
        best = None
        for pattern, targets in paths.items():
            if not isinstance(pattern, str) or not isinstance(targets, list) or pattern.count("*") > 1:
                continue
            if pattern == label:
                best = (float("inf"), targets, "")
            elif "*" in pattern:
                prefix, suffix = pattern.split("*")
                if (len(label) >= len(prefix) + len(suffix) and label.startswith(prefix)
                        and label.endswith(suffix) and (best is None or len(prefix) > best[0])):
                    best = (len(prefix), targets, label[len(prefix):len(label) - len(suffix)])
        if best:
            bases = []
            for target in best[1][:20]:
                if isinstance(target, str):
                    candidate = posixpath.normpath(posixpath.join(root, target.replace("*", best[2])))
                    if inside_repository(candidate):
                        bases.append(candidate)
            return True, bases
        if "base_url" in options:
            candidate = posixpath.normpath(posixpath.join(options["base_url"], label))
            if inside_repository(candidate):
                return False, [candidate]
        return False, []

    def script_candidates(base):
        candidates = [base, *(base + suffix for suffix in SCRIPT_SUFFIXES),
                      *(base + "/index" + suffix for suffix in SCRIPT_SUFFIXES)]
        if base.endswith((".js", ".jsx")):
            # TypeScript sources are imported with their emitted JavaScript extension.
            stem = base.rsplit(".", 1)[0]
            candidates.extend([stem + ".ts", stem + ".tsx"])
        return candidates

    def unique_script_target(bases):
        """The first alias target with any indexed candidate decides; ambiguity stays unresolved."""
        for base in bases:
            found = {file_ids[c] for c in script_candidates(base) if c in file_ids}
            if found:
                return found.pop() if len(found) == 1 else None
        return None

    for imported in [node for node in nodes if node.kind == "import"]:
        guard()
        path = imported.path
        directory = posixpath.dirname(path)
        label = imported.label
        language = imported.attributes.get("language")
        # Marks imports that name repository source, so a failed resolution is a real gap
        # rather than a package, standard-library module or namespace.
        imported.attributes["local_import"] = False
        candidates = []
        if language in {"TypeScript", "JavaScript"}:
            if not label.startswith("."):
                matched, bases = ts_alias_bases(path, label)
                # A declared alias, or the conventional @/ alias (npm scopes are always
                # @scope/name), names the project's own source even when unresolved.
                imported.attributes["local_import"] = matched or label.startswith("@/")
                target = unique_script_target(bases)
                if target:
                    imported.attributes["local_import"] = True
                    link(imported.id, target, "RESOLVES_TO",
                         "Unique source-path candidate through a tsconfig/jsconfig path alias; "
                         "bundler aliases are not evaluated",
                         lines=imported.evidence[0].lines, confidence=80)
                continue
            imported.attributes["local_import"] = True
            base = posixpath.normpath(posixpath.join(directory, label))
            if base.startswith(("../", "/")):
                continue
            candidates = script_candidates(base)
        elif language == "Python":
            if label.startswith("."):
                imported.attributes["local_import"] = True
                # Leading dots select the package level; the first dot is this directory.
                levels = len(label) - len(label.lstrip("."))
                base = directory
                for _ in range(levels - 1):
                    base = posixpath.dirname(base)
                remainder = label[levels:].replace(".", "/")
                base = posixpath.normpath(posixpath.join(base, remainder)) if remainder else base
            else:
                module = label.replace(".", "/")
                head = module.split("/", 1)[0]
                # Absolute modules are tried from the nearest enclosing Python project root
                # (and its src/) before the repository root; the first root holding the
                # module decides. os, requests and other installed modules stay non-local.
                roots = python_roots_for(path)
                imported.attributes["local_import"] = any(
                    f"{prefix}{head}.py" in file_ids or f"{prefix}{head}/__init__.py" in file_ids
                    or f"{prefix}{head}" in directory_ids for prefix in roots)
                base = next((f"{prefix}{module}" for prefix in roots
                             if any(f"{prefix}{module}{suffix}" in file_ids
                                    for suffix in (".py", ".pyi", "/__init__.py"))), module)
            if not base or base in {"."} or base.startswith(("../", "/")):
                continue
            candidates = [base + ".py", base + ".pyi", base + "/__init__.py"]
        elif language == "Go":
            # Go imports address package directories, not files.
            module_dir, module_path = go_module_for(path)
            if module_path and (label == module_path or label.startswith(module_path + "/")):
                imported.attributes["local_import"] = True
                remainder = label[len(module_path):].strip("/")
                base = posixpath.normpath(posixpath.join(module_dir or "", remainder))
                target = directory_ids.get(base if base != "" else ".")
                if target:
                    link(imported.id, target, "RESOLVES_TO",
                         "Go package directory under the declared module path",
                         lines=imported.evidence[0].lines, confidence=85)
            continue
        else:
            continue
        targets = {file_ids[c] for c in candidates if c in file_ids}
        if len(targets) == 1:
            link(imported.id, targets.pop(), "RESOLVES_TO", "Unique local source-path candidate",
                 lines=imported.evidence[0].lines, confidence=85)
    projects = [node for node in nodes if node.kind == "project"]
    projects_by_path = {project.path: project for project in projects
                        if project.path.lower().endswith((".csproj", ".fsproj", ".vbproj"))}
    for project_id, reference_id, include in pending_project_references:
        guard()
        reference = by_id[reference_id]
        path = reference.path
        reference.attributes["resolution"] = "unresolved"
        # Match indexed manifests only, with no disk access or MSBuild expression evaluation.
        literal = include.replace("\\", "/")
        if not literal or len(literal) > 1024 or literal.startswith("/") or re.search(r"[:$@%*?;\x00-\x1f]", literal):
            continue
        candidate = posixpath.normpath(posixpath.join(posixpath.dirname(path), literal))
        target = projects_by_path.get(candidate)
        if target is None:
            continue
        reference.label = f"Project reference: {target.path}"
        reference.attributes["resolution"] = "inferred"
        reference.attributes["target_path"] = target.path
        link(reference_id, target.id, "RESOLVES_TO", "Literal ProjectReference matches an indexed manifest; build inclusion not verified",
             confidence=85)
        link(project_id, target.id, "DEPENDS_ON", "Declared project reference candidate; build and assembly-reference metadata not evaluated",
             confidence=85)
    if pending_project_references:
        limitations.append("ProjectReference links match literal paths to indexed .NET manifests only. "
                            "MSBuild conditions, properties, imports, globs, Remove/Update operations and reference metadata "
                            "are not evaluated; links do not prove build inclusion or runtime assembly dependencies.")
    projects_by_directory = {}
    for project in projects:
        projects_by_directory.setdefault(posixpath.dirname(project.path), []).append(project)
    for path, file_id in file_ids.items():
        guard()
        directory = posixpath.dirname(path)
        while True:
            candidates = projects_by_directory.get(directory, [])
            allowed = LANGUAGE_MANIFESTS.get(
                LANGUAGES.get(posixpath.splitext(path)[1].lower(), ("", None))[0])
            if allowed:
                names = {entry for entry in allowed if not entry.startswith(".")}
                suffixes = tuple(entry for entry in allowed if entry.startswith("."))
                candidates = [p for p in candidates
                              if posixpath.basename(p.path) in names
                              or (suffixes and p.path.lower().endswith(suffixes))]
            if candidates:
                if len(candidates) == 1 and candidates[0].path != path:
                    link(candidates[0].id, file_id, "CONTAINS", "Nearest unambiguous manifest directory",
                         confidence=85)
                break
            if not directory:
                break
            directory = posixpath.dirname(directory)
    counts["relationships"] = len(edges)
    atlas = AtlasDocument(repository={"url": url, "ref": ref or "default",
                         "analyzed_at": datetime.now(UTC).isoformat()},
                         technologies=sorted(technologies), nodes=nodes, relationships=edges,
                         counts=counts, limitations=limitations)
    progress("reporting", 88)
    enrich_dependencies(root, atlas, limits.max_source_bytes)
    enrich_central_nuget(root, atlas, limits.max_source_bytes)
    atlas.report = generate_report(atlas)
    return AtlasDocument.model_validate(atlas.model_dump())
