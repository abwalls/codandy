"""Iterative graph operations on indexed local imports (never runtime execution)."""


def strongly_connected_components(adjacency: dict[str, set[str]]) -> list[list[str]]:
    """Return cyclic components, including self imports, without recursion limits."""
    vertices = set(adjacency)
    reverse: dict[str, set[str]] = {node: set() for node in vertices}
    for source, targets in adjacency.items():
        for target in targets:
            vertices.add(target)
            reverse.setdefault(target, set()).add(source)
    visited, order = set(), []
    for start in sorted(vertices):
        if start in visited:
            continue
        visited.add(start)
        stack = [(start, iter(sorted(adjacency.get(start, ()))))]
        while stack:
            node, children = stack[-1]
            child = next(children, None)
            if child is None:
                order.append(node)
                stack.pop()
            elif child not in visited:
                visited.add(child)
                stack.append((child, iter(sorted(adjacency.get(child, ())))))
    visited.clear()
    result = []
    for start in reversed(order):
        if start in visited:
            continue
        component, stack = [], [start]
        visited.add(start)
        while stack:
            node = stack.pop()
            component.append(node)
            for parent in sorted(reverse.get(node, ())):
                if parent not in visited:
                    visited.add(parent)
                    stack.append(parent)
        if len(component) > 1 or start in adjacency.get(start, ()):
            result.append(sorted(component))
    return sorted(result)
