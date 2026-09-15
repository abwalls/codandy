"""SQLAlchemy and Django models, and Pydantic, dataclass and TypedDict contracts, from syntax.

Modules are parsed with tree-sitter and never imported, so metaclasses, app registries and ORM
configuration never run. Only plain facts are kept once a file's tree has been read.
"""

import re
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field

from tree_sitter import Node, Parser

from app.structure.common import (
    MAX_NAME,
    RawEntity,
    RawField,
    RawLink,
    RawType,
    clip,
    line_range,
)

MAX_ASSIGNMENTS = 1_000
DJANGO_BASES = {"models.Model", "django.db.models.Model"}
DJANGO_RELATIONS = {"ForeignKey", "OneToOneField", "ManyToManyField"}
COLUMN_CALLS = {"Column", "mapped_column"}
NOT_COLUMN_TYPES = {"ForeignKey", "Sequence", "Identity", "Computed", "FetchedValue",
                    "CheckConstraint", "Index"}
ANNOTATION_WRAPPERS = {"Mapped", "WriteOnlyMapped", "DynamicMapped", "list", "List", "set",
                       "Set", "Optional", "None"}


@dataclass
class Call:
    function: str
    args: list["Value"]
    kwargs: dict[str, "Value"]


@dataclass
class Value:
    kind: str  # string | name | call | bool | none | other
    text: str
    call: Call | None = None


@dataclass
class Annotation:
    text: str
    names: list[str]


@dataclass
class Assignment:
    name: str
    annotation: Annotation | None
    value: Value | None
    line: int


@dataclass(eq=False)
class ClassInfo:
    path: str
    root: str
    name: str
    lines: str
    bases: list[str]
    decorators: list[str]
    assignments: list[Assignment]
    meta: dict[str, Value] = field(default_factory=dict)
    mentions_django: bool = False

    @property
    def start(self) -> int:
        return int(self.lines.split("-", 1)[0])


def last(name: str) -> str:
    return name.rsplit(".", 1)[-1]


def text_of(node: Node, data: bytes) -> str:
    return data[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def dotted(node: Node | None, data: bytes) -> str | None:
    if node is None or node.type not in {"identifier", "attribute"}:
        return None
    value = text_of(node, data)
    return value if re.fullmatch(r"[A-Za-z_][\w.]{0,199}", value) else None


def string_content(node: Node, data: bytes) -> str | None:
    if any(child.type == "interpolation" for child in node.named_children):
        return None
    return "".join(text_of(child, data) for child in node.named_children
                   if child.type == "string_content")


def value_of(node: Node, data: bytes, depth: int = 0) -> Value:
    if node.type == "string":
        content = string_content(node, data)
        return Value("other", "f-string") if content is None else Value("string", content[:512])
    if node.type in {"true", "false"}:
        return Value("bool", node.type)
    if node.type == "none":
        return Value("none", "None")
    name = dotted(node, data)
    if name:
        return Value("name", name)
    if node.type == "call" and depth < 4:
        function = dotted(node.child_by_field_name("function"), data)
        arguments = node.child_by_field_name("arguments")
        if function and arguments is not None and arguments.type == "argument_list":
            args, kwargs = [], {}
            for child in arguments.named_children[:40]:
                if child.type == "keyword_argument":
                    key, value = child.child_by_field_name("name"), child.child_by_field_name("value")
                    if key is not None and value is not None:
                        kwargs[text_of(key, data)] = value_of(value, data, depth + 1)
                elif child.type not in {"comment", "list_splat", "dictionary_splat"}:
                    args.append(value_of(child, data, depth + 1))
            return Value("call", function, Call(function, args, kwargs))
    return Value("other", clip(text_of(node, data), 80))


def annotation_of(node: Node, data: bytes) -> Annotation:
    names: list[str] = []
    stack = [node]
    while stack and len(names) < 40:
        current = stack.pop()
        if current.type == "identifier":
            names.append(text_of(current, data))
            continue
        if current.type == "string":
            # Forward references such as "Order" name types inside string annotations.
            names.extend(re.findall(r"[A-Za-z_]\w*", string_content(current, data) or "")[:20])
            continue
        stack.extend(reversed(current.named_children))
    return Annotation(clip(text_of(node, data)), names)


def assignment_of(statement: Node, data: bytes) -> tuple[str, Node | None, Node | None, int] | None:
    if statement.type != "expression_statement" or not statement.named_children:
        return None
    assignment = statement.named_children[0]
    if assignment.type != "assignment":
        return None
    left = assignment.child_by_field_name("left")
    if left is None or left.type != "identifier":
        return None
    return (text_of(left, data)[:MAX_NAME], assignment.child_by_field_name("type"),
            assignment.child_by_field_name("right"), assignment.start_point.row + 1)


def read_class(node: Node, path: str, root: str, data: bytes) -> ClassInfo | None:
    name = node.child_by_field_name("name")
    if name is None:
        return None
    bases = []
    superclasses = node.child_by_field_name("superclasses")
    for child in superclasses.named_children if superclasses is not None else []:
        if child.type == "subscript":
            child = child.child_by_field_name("value") or child
        base = dotted(child, data)
        if base:
            bases.append(base)
    decorators = []
    parent = node.parent
    if parent is not None and parent.type == "decorated_definition":
        for decorator in parent.named_children:
            if decorator.type != "decorator" or not decorator.named_children:
                continue
            inner = decorator.named_children[0]
            if inner.type == "call":
                inner = inner.child_by_field_name("function") or inner
            label = dotted(inner, data)
            if label:
                decorators.append(label)
    info = ClassInfo(path=path, root=root, name=text_of(name, data)[:MAX_NAME],
                     lines=line_range(node.start_point.row + 1, node.end_point.row + 1),
                     bases=bases, decorators=decorators, assignments=[],
                     mentions_django=b"django" in data)
    body = node.child_by_field_name("body")
    for statement in body.named_children if body is not None else []:
        found = assignment_of(statement, data)
        if found and len(info.assignments) < MAX_ASSIGNMENTS:
            label, annotation, right, line = found
            info.assignments.append(Assignment(
                label, annotation_of(annotation, data) if annotation is not None else None,
                value_of(right, data) if right is not None else None, line))
        elif statement.type == "class_definition":
            inner_name = statement.child_by_field_name("name")
            inner_body = statement.child_by_field_name("body")
            if inner_name is None or inner_body is None or text_of(inner_name, data) != "Meta":
                continue
            for item in inner_body.named_children:
                meta = assignment_of(item, data)
                if meta and meta[2] is not None:
                    info.meta[meta[0]] = value_of(meta[2], data)
    return info


def read_classes(path: str, root: str, data: bytes, parser: Parser) -> list[ClassInfo]:
    tree = parser.parse(data)
    classes = []
    stack = [tree.root_node]
    while stack:
        node = stack.pop()
        if node.type == "class_definition":
            info = read_class(node, path, root, data)
            if info is not None:
                classes.append(info)
        stack.extend(reversed(node.named_children))
    return classes


def flag(value: Value | None) -> bool | None:
    if value is None or value.kind != "bool":
        return None
    return value.text == "true"


def keyword(call: Call | None, name: str) -> bool | None:
    return flag(call.kwargs.get(name)) if call is not None else None


def assigned(info: ClassInfo, name: str) -> Value | None:
    return next((item.value for item in info.assignments if item.name == name), None)


def column_call(assignment: Assignment) -> Call | None:
    value = assignment.value
    if value is not None and value.kind == "call" and last(value.text) in COLUMN_CALLS:
        return value.call
    return None


def optional(annotation_text: str) -> bool:
    return bool(re.search(r"\bOptional\[|\bNone\b", annotation_text))


def classify(classes: list[ClassInfo]) -> tuple[
        dict[ClassInfo, str], Callable[[ClassInfo, str], ClassInfo | None]]:
    by_name: dict[str, list[ClassInfo]] = defaultdict(list)
    for info in classes:
        by_name[info.name].append(info)

    def base_class(info: ClassInfo, base: str) -> ClassInfo | None:
        candidates = [candidate for candidate in by_name.get(last(base), []) if candidate is not info]
        same = [candidate for candidate in candidates if candidate.path == info.path]
        pool = same or candidates
        return pool[0] if len(pool) == 1 else None

    def direct(info: ClassInfo) -> str | None:
        if any(base in DJANGO_BASES or (base == "Model" and info.mentions_django)
               for base in info.bases):
            return "django"
        tablename = assigned(info, "__tablename__")
        if (tablename is not None and tablename.kind == "string") or (
                any(column_call(item) for item in info.assignments)
                and any(last(base) == "Model" for base in info.bases)):
            return "sqlalchemy"
        if any(last(base) == "BaseModel" for base in info.bases):
            return "pydantic"
        if any(last(base) == "TypedDict" for base in info.bases):
            return "typed_dict"
        if any(last(decorator) == "dataclass" for decorator in info.decorators):
            return "dataclass"
        return None

    kinds = {info: kind for info in classes if (kind := direct(info))}
    for _ in range(20):
        changed = False
        for info in classes:
            if info in kinds:
                continue
            for base in info.bases:
                parent = base_class(info, base)
                if parent is not None and kinds.get(parent) in {"django", "pydantic", "typed_dict"}:
                    kinds[info] = kinds[parent]
                    changed = True
                    break
        if not changed:
            break
    return kinds, base_class


def model_declarations(classes: list[ClassInfo]):
    """(groups keyed by (kind, project root), data contract types)."""
    kinds, base_class = classify(classes)
    groups: dict[tuple[str, str], tuple[list[RawEntity], list[RawLink]]] = defaultdict(
        lambda: ([], []))
    django = {}
    for info in classes:
        if kinds.get(info) != "django" or flag(info.meta.get("abstract")) or flag(
                info.meta.get("proxy")):
            continue
        table = info.meta.get("db_table")
        entity = RawEntity(name=info.name, kind="model", path=info.path, lines=info.lines,
                           reason="Django model class",
                           table=table.text[:MAX_NAME] if table and table.kind == "string" else None,
                           keys=(f"class:{info.name}",))
        django[info] = entity
        groups[("django", info.root)][0].append(entity)
    for info, entity in django.items():
        django_members(info, entity, django, kinds, base_class, groups[("django", info.root)][1])

    for info in classes:
        if kinds.get(info) != "sqlalchemy" or flag(assigned(info, "__abstract__")):
            continue
        tablename = assigned(info, "__tablename__")
        table = tablename.text[:MAX_NAME] if tablename and tablename.kind == "string" else None
        entity = RawEntity(name=info.name, kind="model", path=info.path, lines=info.lines,
                           reason="SQLAlchemy mapped class", table=table,
                           keys=(f"class:{info.name}", *([f"table:{table.lower()}"] if table else [])))
        entities, links = groups[("sqlalchemy", info.root)]
        entities.append(entity)
        sqlalchemy_members(info, entity, kinds, base_class, links)

    types = []
    for info in classes:
        kind = kinds.get(info)
        if kind not in {"pydantic", "dataclass", "typed_dict"}:
            continue
        declared = RawType(name=info.name, language="Python", kind=kind, path=info.path,
                           lines=info.lines)
        for item in info.assignments:
            if (item.annotation is None or item.name.startswith("_") or item.name == "model_config"
                    or re.match(r"(?:typing\.)?ClassVar\b", item.annotation.text)):
                continue
            declared.members.append((item.name, item.annotation.text, item.line))
            for name in dict.fromkeys(item.annotation.names):
                declared.references.append((item.name, name, "field_type", item.line))
        for base in info.bases:
            declared.references.append((None, last(base), "extends", info.start))
        types.append(declared)
    return dict(groups), types


def inherited(info: ClassInfo, kinds, base_class, include, seen=frozenset()):
    """Assignments from qualifying base classes first, then the class's own."""
    found = []
    for base in info.bases:
        parent = base_class(info, base)
        if parent is not None and parent not in seen and include(parent):
            found.extend(inherited(parent, kinds, base_class, include, seen | {info}))
    return found + [(item, info) for item in info.assignments]


def django_target(value: Value | None, info: ClassInfo, entity: RawEntity):
    """(display name, lookup key or None, pre-resolved entity)."""
    if value is None:
        return "unknown model", None, None
    if value.kind == "string":
        if value.text == "self":
            return info.name, f"class:{info.name}", entity
        name = last(value.text)[:MAX_NAME]
        return name, f"class:{name}", None
    if value.kind == "name":
        if value.text.endswith("AUTH_USER_MODEL"):
            # The configured user model lives in settings, which are never evaluated.
            return clip(value.text, MAX_NAME), None, None
        name = last(value.text)[:MAX_NAME]
        return name, f"class:{name}", None
    return clip(value.text, MAX_NAME), None, None


def django_members(info, entity, django, kinds, base_class, links):
    def abstract_parent(parent):
        return kinds.get(parent) == "django" and bool(flag(parent.meta.get("abstract")))

    for assignment, owner in inherited(info, kinds, base_class, abstract_parent):
        value = assignment.value
        if value is None or value.kind != "call":
            continue
        call = value.call
        kind = last(call.function)
        if not (call.function.startswith("models.") or kind.endswith("Field")
                or kind in DJANGO_RELATIONS):
            continue
        line = assignment.line if owner.path == info.path else None
        # Django's documented defaults: null=False, unique=False, primary_key=False.
        null = keyword(call, "null")
        primary = keyword(call, "primary_key") is True
        unique = keyword(call, "unique") is True
        evidence = (owner.path, line_range(assignment.line))
        if kind not in DJANGO_RELATIONS:
            entity.fields.append(RawField(assignment.name, kind, primary, unique, False,
                                          bool(null), line))
            continue
        target = call.args[0] if call.args else call.kwargs.get("to")
        name, key, resolved = django_target(target, info, entity)
        if kind == "ManyToManyField":
            if "through" in call.kwargs:
                continue  # the through model's own foreign keys show this relationship
            links.append(RawLink(entity, [], key, name, [], "many", "many", True, True,
                                 assignment.name, "orm_relation", *evidence,
                                 "Django ManyToManyField (join table managed by Django)", resolved))
            continue
        one = kind == "OneToOneField" or unique
        entity.fields.append(RawField(assignment.name, clip(f"{kind} → {name}", 60), primary, one,
                                      True, bool(null), line))
        to_field = call.kwargs.get("to_field")
        links.append(RawLink(entity, [assignment.name], key, name,
                             [to_field.text[:MAX_NAME]] if to_field and to_field.kind == "string" else [],
                             "one" if one else "many", "one", True, bool(null), assignment.name,
                             "declared", *evidence, f"Django {kind}", resolved))
    if not any(item.primary for item in entity.fields):
        entity.fields.insert(0, RawField("id", "AutoField (implicit)", primary=True, nullable=False))
    for base in info.bases:
        parent = base_class(info, base)
        if parent in django:
            links.append(RawLink(entity, [], f"class:{parent.name}", parent.name, [], "one", "one",
                                 True, False, "multi-table inheritance", "orm_relation", info.path,
                                 line_range(info.start),
                                 "Django multi-table inheritance (implicit one-to-one link)",
                                 django[parent]))


def sqlalchemy_members(info, entity, kinds, base_class, links):
    def mixin(parent):
        return (any(column_call(item) for item in parent.assignments)
                and (kinds.get(parent) != "sqlalchemy" or bool(flag(assigned(parent, "__abstract__")))))

    foreign_links = []
    related = set()
    for assignment, owner in inherited(info, kinds, base_class, mixin):
        if assignment.name.startswith("__"):
            continue
        call = assignment.value.call if assignment.value and assignment.value.kind == "call" else None
        function = last(call.function) if call else ""
        annotation = assignment.annotation
        match = re.fullmatch(r"(?:\w+\.)?Mapped\[(.*)\]", annotation.text) if annotation else None
        inner = match.group(1) if match else None
        line = assignment.line if owner.path == info.path else None
        evidence = (owner.path, line_range(assignment.line))
        if function in COLUMN_CALLS or (call is None and inner is not None):
            args = call.args if call else []
            column_type = next((arg.text for arg in args if arg.kind == "name" or (
                arg.kind == "call" and last(arg.text) not in NOT_COLUMN_TYPES)), "") or inner or ""
            foreign = [arg.call for arg in args
                       if arg.kind == "call" and last(arg.text) == "ForeignKey"]
            primary = keyword(call, "primary_key") is True
            nullable = keyword(call, "nullable")
            if nullable is None:
                if primary:
                    nullable = False
                elif inner is not None and function in {"", "mapped_column"}:
                    # SQLAlchemy 2.0 derives NOT NULL from a non-Optional Mapped[] annotation.
                    nullable = optional(inner)
            column = RawField(assignment.name, clip(column_type, 60), primary,
                              keyword(call, "unique") is True, bool(foreign), nullable, line)
            entity.fields.append(column)
            for key in foreign:
                target = key.args[0] if key.args else None
                if target is not None and target.kind == "string" and target.text.count(".") >= 1:
                    parts = target.text.split(".")
                    name, lookup = ".".join(parts[:-1]), "table:" + ".".join(
                        part.lower() for part in parts[:-1][-2:])
                elif target is not None and target.kind == "name" and "." in target.text:
                    owner_name, _ = target.text.rsplit(".", 1)
                    parts = target.text.split(".")
                    name, lookup = last(owner_name), f"class:{last(owner_name)}"
                else:
                    continue
                link = RawLink(entity, [assignment.name], lookup, clip(name, MAX_NAME),
                               [parts[-1][:MAX_NAME]], "many", "one", True, nullable,
                               assignment.name, "declared", *evidence, "SQLAlchemy ForeignKey column")
                links.append(link)
                foreign_links.append((link, column))
        elif function == "relationship":
            target = call.args[0] if call.args else None
            names = ([target.text] if target is not None and target.kind in {"string", "name"}
                     else [name for name in (annotation.names if annotation else [])
                           if name not in ANNOTATION_WRAPPERS])
            if not names:
                continue
            name = last(names[0])[:MAX_NAME]
            many = bool(annotation and re.search(r"\b(?:list|List|set|Set)\[", annotation.text))
            uselist = keyword(call, "uselist")
            secondary = call.kwargs.get("secondary")
            pair = (frozenset((info.name, name)), secondary.text if secondary else "")
            if pair in related:
                continue
            related.add(pair)
            if secondary is not None:
                links.append(RawLink(entity, [], f"class:{name}", name, [], "many", "many", True,
                                     True, assignment.name, "orm_relation", *evidence,
                                     "SQLAlchemy relationship() with a secondary association table"))
            else:
                cardinality = ("many" if (many if uselist is None else uselist)
                               else "one" if uselist is False else "unknown")
                links.append(RawLink(entity, [], f"class:{name}", name, [], "unknown", cardinality,
                                     None, None, assignment.name, "orm_relation", *evidence,
                                     "SQLAlchemy relationship() without a foreign key on this class",
                                     unless_linked=True))
    primary = [item for item in entity.fields if item.primary]
    for link, column in foreign_links:
        if column.unique or (column.primary and len(primary) == 1):
            link.source_cardinality = "one"
