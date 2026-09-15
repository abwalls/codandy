"""Build structure-0.1 from the files the analyzer indexed. Declarations are read as text only.

Only atlas file nodes are candidates, so the analyzer's excluded directories and secret-named
files are never opened here either. Every path is re-checked against the workspace root and
links are not followed.
"""

import posixpath
import time
from collections import defaultdict
from pathlib import Path

import tree_sitter_python
import tree_sitter_typescript
from tree_sitter import Language, Parser

from app.models import AtlasDocument
from app.settings import Settings
from app.sources import _inside
from app.structure.common import (
    MAX_NAME,
    RawEntity,
    RawLink,
    RawType,
    clip,
    line_range,
    structure_id,
)
from app.structure.models import (
    EXTRACTION_FAILED,
    DataType,
    Entity,
    EntityField,
    EntityLink,
    LinkEnd,
    SchemaSource,
    StructureDocument,
    StructureEvidence,
    TypeLink,
    TypeMember,
    validate_against_atlas,
)
from app.structure.prisma import parse_prisma, prisma_declarations
from app.structure.python_models import model_declarations, read_classes
from app.structure.sql import SqlSchema
from app.structure.typescript import typescript_types

MAX_ENTITIES = 2_000
MAX_FIELDS = 300
MAX_TYPES = 5_000
MAX_MEMBERS = 300
MAX_LINKS = 20_000
LIMITATIONS = [
    ("Data models are declarations read from Prisma schemas, SQL DDL files, and SQLAlchemy and "
     "Django model classes. Nothing is imported, migrated or connected to, so a live database "
     "can differ from these declarations."),
    ("SQL files are applied in path order within each project directory, reading CREATE TABLE, "
     "CREATE VIEW, ALTER TABLE ADD/DROP and DROP TABLE statements. Conditional logic, procedures, "
     "data changes and dialect-specific behavior are not evaluated."),
    ("Data contracts are Pydantic models, dataclasses and TypedDicts in Python, and TypeScript "
     "interfaces and object type aliases. Zod schemas, C# and Go types, intersections and "
     "declaration (.d.ts) files are not read yet."),
    ("Contract links follow type names: a type declared in the same file or in a resolved local "
     "import is resolved, a unique repository-wide name is inferred, and ambiguous names are not "
     "linked."),
]
TYPE_REASONS = {
    "pydantic": "Pydantic model declaration", "dataclass": "Dataclass declaration",
    "typed_dict": "TypedDict declaration", "interface": "TypeScript interface declaration",
    "type_alias": "TypeScript object type alias",
}


def read_bytes(root: Path, path: str, limit: int) -> bytes | None:
    target = _inside(root, path)
    if target is None:
        return None
    try:
        with target.open("rb") as handle:
            data = handle.read(limit + 1)
    except OSError:
        return None
    return None if len(data) > limit or b"\0" in data else data


def decode(data: bytes | None) -> str | None:
    if data is None:
        return None
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return None


def imported_files(atlas: AtlasDocument) -> dict[str, set[str]]:
    """File path -> local files its imports resolve to."""
    nodes = {node.id: node for node in atlas.nodes}
    resolved: dict[str, set[str]] = defaultdict(set)
    for edge in atlas.relationships:
        target = nodes.get(edge.target)
        if (edge.type == "RESOLVES_TO" and edge.resolution != "unresolved" and target is not None
                and target.kind == "file"):
            resolved[edge.source].add(target.path)
    imports: dict[str, set[str]] = defaultdict(set)
    for edge in atlas.relationships:
        if edge.type == "IMPORTS" and edge.source in nodes:
            imports[nodes[edge.source].path] |= resolved.get(edge.target, set())
    return imports


def build_structure(root: Path, atlas: AtlasDocument, limits: Settings,
                    deadline: float | None = None) -> StructureDocument:
    """Diagrams never fail the analysis: any extraction error becomes a visible limitation."""
    try:
        return extract_structure(root, atlas, limits, deadline)
    except Exception:  # noqa: BLE001 - contain extractor defects to the diagrams
        return StructureDocument(limitations=[EXTRACTION_FAILED])


def extract_structure(root: Path, atlas: AtlasDocument, limits: Settings,
                      deadline: float | None = None) -> StructureDocument:
    limitations = list(LIMITATIONS)
    counts: dict[str, int] = defaultdict(int)
    files = sorted(node.path for node in atlas.nodes if node.kind == "file")
    manifest_dirs = sorted({posixpath.dirname(node.path) for node in atlas.nodes
                            if node.kind == "project"}, key=len, reverse=True)

    def project_root(path: str) -> str:
        return next((directory for directory in manifest_dirs
                     if not directory or path.startswith(directory + "/")), "")

    stopped = False

    def expired() -> bool:
        nonlocal stopped
        stopped = stopped or (deadline is not None and time.monotonic() > deadline)
        return stopped

    def load(path: str) -> bytes | None:
        data = read_bytes(root, path, limits.max_source_bytes)
        if data is None:
            counts["unreadable_files"] += 1
        return data

    prisma_files: dict[str, list[str]] = defaultdict(list)
    sql_files: dict[str, list[str]] = defaultdict(list)
    python_files, script_files = [], []
    for path in files:
        lower = path.lower()
        if lower.endswith(".prisma"):
            prisma_files[project_root(path)].append(path)
        elif lower.endswith(".sql"):
            sql_files[project_root(path)].append(path)
        elif lower.endswith(".py"):
            python_files.append(path)
        elif lower.endswith((".ts", ".tsx")) and not lower.endswith(".d.ts"):
            script_files.append(path)

    groups: dict[tuple[str, str], tuple[list[RawEntity], list[RawLink]]] = {}
    for directory, paths in sorted(prisma_files.items()):
        parsed = []
        for path in paths:
            if expired():
                break
            text = decode(load(path))
            if text is not None:
                parsed.append((path, parse_prisma(text)))
                counts["parsed_files"] += 1
        entities, links, duplicates = prisma_declarations(parsed)
        counts["duplicate_declarations"] += duplicates
        groups[("prisma", directory)] = (entities, links)

    for directory, paths in sorted(sql_files.items()):
        schema = SqlSchema()
        for path in paths:
            if expired():
                break
            text = decode(load(path))
            if text is not None:
                schema.apply(path, text)
                counts["parsed_files"] += 1
        if schema.truncated:
            limitations.append(
                f"SQL under {directory or 'the repository root'} exceeded the token or statement "
                "budget, so later statements were not read.")
        counts["skipped_statements"] += schema.skipped
        groups[("sql", directory)] = schema.declarations()

    raw_types: list[RawType] = []
    if python_files and not expired():
        parser = Parser(Language(tree_sitter_python.language()))
        classes = []
        for path in python_files:
            if expired():
                break
            data = load(path)
            if data is not None and b"class " in data:
                classes.extend(read_classes(path, project_root(path), data, parser))
                counts["parsed_files"] += 1
        model_groups, python_types = model_declarations(classes)
        groups.update(model_groups)
        raw_types.extend(python_types)

    parsers: dict[str, Parser] = {}
    for path in script_files:
        if expired():
            break
        data = load(path)
        if data is None or (b"interface" not in data and b"type " not in data):
            continue
        suffix = "tsx" if path.lower().endswith(".tsx") else "ts"
        if suffix not in parsers:
            language = (tree_sitter_typescript.language_tsx() if suffix == "tsx"
                        else tree_sitter_typescript.language_typescript())
            parsers[suffix] = Parser(Language(language))
        raw_types.extend(typescript_types(path, data, parsers[suffix]))
        counts["parsed_files"] += 1

    declarations = {(node.path, node.label, node.evidence[0].lines): node.id
                    for node in atlas.nodes
                    if node.kind in {"class", "interface", "type"} and node.evidence}
    sources, entities, entity_links = assemble_entities(groups, declarations, counts)
    types, type_links = assemble_types(raw_types, imported_files(atlas), declarations, counts)

    if stopped:
        limitations.append("Data model extraction reached its time budget, so these diagrams are "
                           "partial.")
    if counts["skipped_statements"]:
        limitations.append(f"{counts['skipped_statements']} SQL statements could not be read as "
                           "supported declarations.")
    if counts["unreadable_files"]:
        limitations.append(f"{counts['unreadable_files']} candidate files were oversized, binary, "
                           "linked or not UTF-8 and were not read for diagrams.")
    for label, key, total in (("tables and models", "omitted_entities", MAX_ENTITIES),
                              ("types", "omitted_types", MAX_TYPES)):
        if counts[key]:
            limitations.append(f"Only the first {total} {label} are kept; {counts[key]} more "
                               "were omitted.")
    counts.update(entities=len(entities), entity_links=len(entity_links), types=len(types),
                  type_links=len(type_links))
    document = StructureDocument(sources=sources, entities=entities, entity_links=entity_links,
                                 types=types, type_links=type_links, counts=dict(counts),
                                 limitations=limitations)
    validate_against_atlas(document, atlas)
    return document


def unique_id(base: str, used: set[str]) -> str:
    identity, ordinal = base, 1
    while identity in used:
        ordinal += 1
        identity = f"{base}-{ordinal}"
    used.add(identity)
    return identity


def assemble_entities(groups, declarations, counts):
    sources: list[SchemaSource] = []
    entities: list[Entity] = []
    links: list[EntityLink] = []
    used: set[str] = set()
    for kind, directory in sorted(groups):
        raw_entities, raw_links = groups[(kind, directory)]
        source_id = structure_id("schema", kind, directory)
        ids: dict[RawEntity, str] = {}
        for raw in raw_entities:
            if len(entities) >= MAX_ENTITIES:
                counts["omitted_entities"] += 1
                continue
            ids[raw] = unique_id(structure_id("entity", kind, directory, raw.path,
                                              raw.namespace or "", raw.name), used)
            entities.append(Entity(
                id=ids[raw], source_id=source_id, name=raw.name[:MAX_NAME], table=raw.table,
                namespace=raw.namespace, kind=raw.kind,
                fields=[EntityField(**vars(item)) for item in raw.fields[:MAX_FIELDS]],
                omitted_fields=max(0, len(raw.fields) - MAX_FIELDS),
                node_id=declarations.get((raw.path, raw.name, raw.lines)),
                evidence=[StructureEvidence(path=raw.path, lines=raw.lines, reason=raw.reason),
                          *(StructureEvidence(path=path, lines=lines, reason=reason)
                            for path, lines, reason in raw.more_evidence)]))
        if not ids:
            continue
        index: dict[str, list[RawEntity]] = defaultdict(list)
        for raw in ids:
            for key in raw.keys:
                index[key].append(raw)
        files = {raw.path for raw in ids}
        joined: set[frozenset[str]] = set()
        # Declared links first, so an ORM view of the same foreign key can be recognized.
        for link in sorted(raw_links, key=lambda item: item.unless_linked):
            if link.source not in ids or len(links) >= MAX_LINKS:
                counts["omitted_links"] += 1
                continue
            if link.target_entity is not None:
                candidates = [link.target_entity] if link.target_entity in ids else []
            else:
                candidates = [raw for raw in index.get(link.target_key, [])] if link.target_key else []
            resolution = ("resolved" if len(candidates) == 1
                          else "ambiguous" if candidates else "unresolved")
            target = ids[candidates[0]] if resolution == "resolved" else None
            pair = frozenset((ids[link.source], target or ""))
            if link.unless_linked and target is not None and pair in joined:
                continue
            if link.basis == "declared" and target is not None:
                joined.add(pair)
            identity = unique_id(structure_id(
                "entity-link", ids[link.source], ",".join(link.source_fields),
                link.target_key or link.target_name, ",".join(link.target_fields), link.label,
                link.basis), used)
            links.append(EntityLink(
                id=identity, source_id=source_id,
                source=LinkEnd(entity=ids[link.source], name=link.source.name[:MAX_NAME],
                               fields=link.source_fields[:20],
                               cardinality=link.source_cardinality,
                               optional=link.source_optional),
                target=LinkEnd(entity=target, name=clip(link.target_name, MAX_NAME),
                               fields=link.target_fields[:20],
                               cardinality=link.target_cardinality,
                               optional=link.target_optional),
                label=clip(link.label, MAX_NAME), basis=link.basis, resolution=resolution,
                evidence=[StructureEvidence(path=link.path, lines=link.lines, reason=link.reason)]))
            files.add(link.path)
        sources.append(SchemaSource(id=source_id, kind=kind, root=directory, files=sorted(files)))
    return sources, entities, links


def assemble_types(raw_types: list[RawType], imports, declarations, counts):
    ordered = sorted(raw_types, key=lambda item: (item.path, int(item.lines.split("-")[0]),
                                                  item.name))
    kept = ordered[:MAX_TYPES]
    counts["omitted_types"] += len(ordered) - len(kept)
    used: set[str] = set()
    ids: dict[RawType, str] = {}
    types = []
    by_name: dict[tuple[str, str], list[RawType]] = defaultdict(list)
    for raw in kept:
        ids[raw] = unique_id(structure_id("type", raw.language, raw.path, raw.name), used)
        by_name[(raw.language, raw.name)].append(raw)
        types.append(DataType(
            id=ids[raw], name=raw.name, language=raw.language, kind=raw.kind, path=raw.path,
            members=[TypeMember(name=name, type=text, line=line)
                     for name, text, line in raw.members[:MAX_MEMBERS]],
            omitted_members=max(0, len(raw.members) - MAX_MEMBERS),
            node_id=declarations.get((raw.path, raw.name, raw.lines)),
            evidence=[StructureEvidence(path=raw.path, lines=raw.lines,
                                        reason=TYPE_REASONS[raw.kind])]))
    links, seen = [], set()
    for raw in kept:
        for member, name, kind, line in raw.references:
            candidates = [item for item in by_name.get((raw.language, name), [])
                          if kind == "field_type" or item is not raw]
            if not candidates:
                continue
            same = [item for item in candidates if item.path == raw.path]
            imported = [item for item in candidates if item.path in imports.get(raw.path, ())]
            if same:
                pool, resolution, reason = same, "resolved", "declared in the same file"
            elif imported:
                pool, resolution, reason = imported, "resolved", "declared in a resolved local import"
            else:
                pool, resolution, reason = (candidates, "inferred",
                                            "unique type name in the repository; import not verified")
            if len(pool) != 1:
                counts["ambiguous_type_references"] += 1
                continue
            key = (ids[raw], ids[pool[0]], kind, member or "")
            if key in seen:
                continue
            seen.add(key)
            if len(links) >= MAX_LINKS:
                counts["omitted_type_links"] += 1
                continue
            label = "Base type" if kind == "extends" else "Member type"
            links.append(TypeLink(
                id=structure_id("type-link", *key), source=key[0], target=key[1], kind=kind,
                member=member, resolution=resolution,
                evidence=[StructureEvidence(path=raw.path, lines=line_range(line),
                                            reason=f"{label} {reason}")]))
    return types, links
