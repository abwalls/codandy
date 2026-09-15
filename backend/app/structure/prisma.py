"""Prisma schema declarations read as text.

Datasource and generator blocks are skipped without keeping their contents, so connection
URLs and generator settings never reach the structure document.
"""

import re
from dataclasses import dataclass, field

from app.structure.common import MAX_NAME, RawEntity, RawField, RawLink, clip, line_range

BLOCK_START = re.compile(
    rf"(model|view|enum|type|datasource|generator)\s+([A-Za-z_]\w{{0,{MAX_NAME - 1}}})\s*\{{")
FIELD = re.compile(r"([A-Za-z_]\w{0,127})\s+([A-Za-z_]\w{0,127})(\([^)]{0,200}\))?(\[\])?(\?)?"
                   r"(?:\s+(.*))?")
LIST_ARGUMENT = r"\b{name}\s*:\s*\[([^\]]*)\]"


def strip_comment(line: str) -> str:
    """Drop a // comment that is not inside a string literal."""
    quoted = False
    index = 0
    while index < len(line):
        char = line[index]
        if quoted and char == "\\":
            index += 2
            continue
        if char == '"':
            quoted = not quoted
        elif not quoted and line.startswith("//", index):
            return line[:index]
        index += 1
    return line


@dataclass
class PrismaField:
    name: str
    type: str
    arguments: str
    list: bool
    optional: bool
    attributes: str
    line: int


@dataclass
class PrismaBlock:
    kind: str
    name: str
    start: int
    end: int = 0
    fields: list[PrismaField] = field(default_factory=list)
    block_attributes: list[str] = field(default_factory=list)


def parse_prisma(text: str) -> list[PrismaBlock]:
    blocks = []
    current: PrismaBlock | None = None
    for number, raw in enumerate(text.splitlines(), start=1):
        line = strip_comment(raw).strip()
        if not line:
            continue
        if current is None:
            match = BLOCK_START.fullmatch(line)
            if match:
                current = PrismaBlock(match.group(1), match.group(2), number)
            continue
        if line == "}":
            current.end = number
            if current.kind in {"model", "view", "enum", "type"}:
                blocks.append(current)
            current = None
            continue
        if current.kind in {"datasource", "generator", "enum"}:
            continue
        if line.startswith("@@"):
            current.block_attributes.append(line)
            continue
        match = FIELD.fullmatch(line)
        if match:
            current.fields.append(PrismaField(
                name=match.group(1), type=match.group(2), arguments=match.group(3) or "",
                list=bool(match.group(4)), optional=bool(match.group(5)),
                attributes=match.group(6) or "", line=number))
    return blocks


def attribute_arguments(attributes: str, name: str) -> str | None:
    """Text inside @name(...), or "" for a bare @name, or None when absent."""
    match = re.search(rf"(?<!@)@{name}\b", attributes)
    if not match:
        return None
    start = match.end()
    if start >= len(attributes) or attributes[start] != "(":
        return ""
    depth, quoted = 0, False
    for position in range(start, len(attributes)):
        char = attributes[position]
        if quoted:
            if char == '"' and attributes[position - 1] != "\\":
                quoted = False
        elif char == '"':
            quoted = True
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return attributes[start + 1:position]
    return None


def names_in(text: str | None, argument: str) -> list[str]:
    if not text:
        return []
    match = re.search(LIST_ARGUMENT.format(name=argument), text)
    if not match:
        return []
    return [clip(item.strip(), MAX_NAME) for item in match.group(1).split(",")
            if re.fullmatch(r"\s*[A-Za-z_]\w*\s*", item)]


def relation_name(arguments: str | None) -> str:
    if not arguments:
        return ""
    match = re.match(r'\s*"([^"]{1,128})"', arguments) or re.search(
        r'\bname\s*:\s*"([^"]{1,128})"', arguments)
    return match.group(1) if match else ""


def block_list(attribute: str, name: str) -> list[str] | None:
    match = re.match(rf"@@{name}\(\s*(?:fields\s*:\s*)?\[([^\]]*)\]", attribute)
    if not match:
        return None
    return [item.strip() for item in match.group(1).split(",")
            if re.fullmatch(r"\s*[A-Za-z_]\w*\s*", item)]


def block_string(attribute: str, name: str) -> str | None:
    match = re.match(rf'@@{name}\(\s*(?:name\s*:\s*)?"([^"]{{1,128}})"', attribute)
    return match.group(1) if match else None


def prisma_declarations(files: list[tuple[str, list[PrismaBlock]]]):
    """Entities and links for the Prisma schema files of one project directory."""
    models: dict[str, tuple[str, PrismaBlock]] = {}
    duplicates = 0
    for path, blocks in files:
        for block in blocks:
            if block.kind not in {"model", "view"}:
                continue
            if block.name in models:
                duplicates += 1
                continue
            models[block.name] = (path, block)

    entities: dict[str, RawEntity] = {}
    keys: dict[str, set[str]] = {}
    unique_sets: dict[str, list[set[str]]] = {}
    for name, (path, block) in models.items():
        primary, table, namespace, uniques = set(), None, None, []
        for attribute in block.block_attributes:
            primary |= set(block_list(attribute, "id") or [])
            composite = block_list(attribute, "unique")
            if composite:
                uniques.append(set(composite))
            table = block_string(attribute, "map") or table
            namespace = block_string(attribute, "schema") or namespace
        entity = RawEntity(
            name=name, kind="table" if block.kind == "model" else "view", path=path,
            lines=line_range(block.start, block.end),
            reason=f"Prisma {block.kind} declaration", table=table or name, namespace=namespace,
            keys=(f"model:{name}",))
        for item in block.fields:
            if item.type in models:
                continue
            singles = [group for group in uniques if len(group) == 1]
            entity.fields.append(RawField(
                name=item.name, type=clip(item.type + item.arguments + ("[]" if item.list else ""), 60),
                primary=item.name in primary or attribute_arguments(item.attributes, "id") is not None,
                unique=(attribute_arguments(item.attributes, "unique") is not None
                        or {item.name} in singles),
                nullable=item.optional, line=item.line))
        entities[name] = entity
        keys[name] = {item.name for item in entity.fields if item.primary}
        unique_sets[name] = uniques

    links: list[RawLink] = []
    seen_many = set()
    for name, (path, block) in models.items():
        entity = entities[name]
        for item in block.fields:
            arguments = attribute_arguments(item.attributes, "relation")
            foreign = names_in(arguments, "fields")
            if item.type not in models:
                if arguments is not None:
                    # A relation to a model this schema does not declare.
                    links.append(RawLink(
                        source=entity, source_fields=foreign, target_key=f"model:{item.type}",
                        target_name=item.type, target_fields=names_in(arguments, "references"),
                        source_cardinality="many", target_cardinality="one", source_optional=True,
                        target_optional=item.optional, label=item.name, basis="declared",
                        path=path, lines=line_range(item.line), reason="Prisma @relation field"))
                continue
            if foreign:
                for column in foreign:
                    declared = entity.field_named(column)
                    if declared:
                        declared.foreign = True
                singular = len(foreign) == 1 and (
                    (declared := entity.field_named(foreign[0])) is not None
                    and (declared.unique or (declared.primary and len(keys[name]) == 1)))
                one = singular or set(foreign) == keys[name] or set(foreign) in unique_sets[name]
                links.append(RawLink(
                    source=entity, source_fields=foreign, target_key=f"model:{item.type}",
                    target_name=item.type, target_fields=names_in(arguments, "references"),
                    source_cardinality="one" if one else "many", target_cardinality="one",
                    source_optional=True, target_optional=item.optional, label=item.name,
                    basis="declared", path=path, lines=line_range(item.line),
                    reason="Prisma @relation with fields and references"))
            elif item.list:
                relation = relation_name(arguments)
                _, other = models[item.type]
                back = [candidate for candidate in other.fields
                        if candidate.type == name and candidate is not item
                        and relation_name(attribute_arguments(candidate.attributes, "relation"))
                        == relation]
                if back and all(candidate.list for candidate in back):
                    pair = (*sorted((name, item.type)), relation)
                    if pair in seen_many:
                        continue
                    seen_many.add(pair)
                    links.append(RawLink(
                        source=entity, source_fields=[], target_key=f"model:{item.type}",
                        target_name=item.type, target_fields=[], source_cardinality="many",
                        target_cardinality="many", source_optional=True, target_optional=True,
                        label=relation or item.name, basis="orm_relation", path=path,
                        lines=line_range(item.line),
                        reason="Prisma implicit many-to-many relation (join table managed by Prisma)"))
    return list(entities.values()), links, duplicates
