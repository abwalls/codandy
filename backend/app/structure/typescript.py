"""TypeScript interfaces and object type aliases from syntax; nothing is compiled or run."""

from tree_sitter import Node, Parser

from app.structure.common import MAX_NAME, RawType, clip, line_range


def text_of(node: Node, data: bytes) -> str:
    return data[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def type_names(node: Node, data: bytes) -> list[str]:
    names: list[str] = []
    stack = [node]
    while stack and len(names) < 40:
        current = stack.pop()
        if current.type == "type_identifier":
            names.append(text_of(current, data))
        stack.extend(reversed(current.named_children))
    return names


def typescript_types(path: str, data: bytes, parser: Parser) -> list[RawType]:
    tree = parser.parse(data)
    found = []
    stack = [tree.root_node]
    while stack:
        node = stack.pop()
        stack.extend(reversed(node.named_children))
        body, kind = None, "interface"
        if node.type == "interface_declaration":
            body = node.child_by_field_name("body")
        elif node.type == "type_alias_declaration":
            value = node.child_by_field_name("value")
            if value is not None and value.type == "object_type":
                body, kind = value, "type_alias"
        name = node.child_by_field_name("name") if body is not None else None
        if name is None:
            continue
        declared = RawType(name=text_of(name, data)[:MAX_NAME], language="TypeScript", kind=kind,
                           path=path,
                           lines=line_range(node.start_point.row + 1, node.end_point.row + 1))
        parameters = node.child_by_field_name("type_parameters")
        local_parameters = {text_of(name, data) for parameter in parameters.named_children
                            if (name := parameter.child_by_field_name("name")) is not None} if parameters else set()
        for clause in node.named_children:
            if clause.type != "extends_type_clause":
                continue
            for item in clause.named_children:
                base = item.child_by_field_name("name") if item.type == "generic_type" else item
                if base is not None and base.type in {"type_identifier", "nested_type_identifier"}:
                    declared.references.append((None, text_of(base, data).rsplit(".", 1)[-1],
                                                "extends", item.start_point.row + 1))
        for member in body.named_children:
            if member.type != "property_signature":
                continue
            key = member.child_by_field_name("name")
            annotation = member.child_by_field_name("type")
            if key is None:
                continue
            marker = "?" if any(child.type == "?" for child in member.children) else ""
            label = text_of(key, data).strip("\"'")[:MAX_NAME] + marker
            line = member.start_point.row + 1
            declared.members.append(
                (label, clip(text_of(annotation, data).lstrip(":")) if annotation else "", line))
            if annotation is not None:
                for reference in dict.fromkeys(type_names(annotation, data)):
                    declared.references.append((label, reference, "field_type", line))
        declared.references = [reference for reference in declared.references if reference[1] not in local_parameters]
        found.append(declared)
    return found
