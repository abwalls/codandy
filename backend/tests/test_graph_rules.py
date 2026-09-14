from app.graph_rules import strongly_connected_components


def test_cycles_exclude_acyclic_neighbors_and_include_self_import():
    assert strongly_connected_components({
        "entry": {"a"}, "a": {"b"}, "b": {"a", "leaf"},
        "self": {"self"}, "empty": set(),
    }) == [["a", "b"], ["self"]]


def test_deep_graph_does_not_recurse():
    graph = {str(i): {str(i + 1)} for i in range(5000)}
    assert strongly_connected_components(graph) == []
    graph["5000"] = {"0"}
    components = strongly_connected_components(graph)
    assert len(components) == 1
    assert len(components[0]) == 5001
