"""Guards the native parser stack the analyzer depends on.

tree-sitter 0.26.0 corrupts process memory when a walk reads a node's
start_point/end_point and then its named_children, which segfaults the analyzer
on ordinary sources. The analyzer does exactly that for every declaration, so
the working range is pinned and asserted here rather than discovered in
production as a dead worker process.
"""

from importlib.metadata import version

import pytest
from tree_sitter import Language, Parser

from app.analyzer import LANGUAGES

VERIFIED_CORE = {"0.25"}


def test_tree_sitter_core_stays_in_the_verified_range():
    installed = version("tree-sitter")
    series = ".".join(installed.split(".")[:2])
    assert series in VERIFIED_CORE, (
        f"tree-sitter {installed} has not been verified against the point/named_children "
        "walk the analyzer performs. Re-run the analyzer test suite against a real "
        "multi-file repository before widening VERIFIED_CORE."
    )


@pytest.mark.parametrize("suffix", sorted(LANGUAGES))
def test_every_registered_grammar_loads_and_walks(suffix):
    label, factory = LANGUAGES[suffix]
    parser = Parser(Language(factory()))
    tree = parser.parse(b"")
    stack = [tree.root_node]
    while stack:
        node = stack.pop()
        # The exact access order that trips the broken core release.
        assert node.start_point.row >= 0
        assert node.end_point.row >= 0
        stack.extend(reversed(node.named_children))
    assert label
