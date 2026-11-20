"""``links_clause``: what removing a node leaves behind, as the clause of the advice "remove it" (E742, E747, E748)."""
from __future__ import annotations

from dataclasses import replace

from specdev_tools.graph.build import build_graph
from specdev_tools.graph.model import SpecShape
from specdev_tools.validation.graph_checks.removal import links_clause
from unit.graph._synth import EXAMPLE_SPEC, ROOT

from ._built_support import STEP_RANKS, declared, graph_of, node

_DECLS = build_graph(str(EXAMPLE_SPEC), str(ROOT)).decls


def _clause(target: str, *nodes) -> str:
    graph = graph_of([node(target, "fixture"), node("fix-2", "fixture"), *(declared(item, _DECLS) for item in nodes)], decls=_DECLS, shape=SpecShape(step_ranks=STEP_RANKS))
    return links_clause(graph, target)


def test_nothing_linking_the_node_gives_no_clause() -> None:
    assert _clause("fix-1") == ""


def test_the_clause_counts_the_nodes_not_the_links_and_lists_their_steps_in_order() -> None:
    clause = _clause(
        "fix-1", node("threat-1", "threat", step="11", mitigated_by=["fix-1"]), node("ec-1", "edge-case", step="11", mitigated_by=["fix-1", "fix-2"]),
        node("job-1", "job", step="10", depends_on=["fix-1"]),
    )
    assert clause == "(3 nodes, in steps 10, 11)"


def test_a_holder_whose_required_list_would_be_empty_is_counted_apart() -> None:
    only = node("ec-1", "edge-case", step="11", mitigated_by=["fix-1"])
    other = node("ec-2", "edge-case", step="11", mitigated_by=["fix-1", "fix-2"])
    third = node("ec-3", "edge-case", step="11", mitigated_by=["fix-1"])
    assert _clause("fix-1", only) == "(1 node, in step 11; it holds no other entry and needs one first)"
    assert _clause("fix-1", only, other) == "(2 nodes, in step 11; 1 of them holds no other entry and needs one first)"
    assert _clause("fix-1", only, third, other) == "(3 nodes, in step 11; 2 of them hold no other entry and need one first)"


def test_a_list_that_is_not_required_is_never_left_empty() -> None:
    assert _clause("fix-1", node("threat-1", "threat", step="11", mitigated_by=["fix-1"])) == "(1 node, in step 11)"


def test_a_link_written_with_a_retired_name_counts_and_the_same_node_twice_is_one_node() -> None:
    renamed = replace(node("fix-1", "fixture"), aliases=("fix-old",))
    graph = graph_of(
        [renamed, declared(node("ec-1", "edge-case", step="11", mitigated_by=["fix-old", "fix-1"]), _DECLS)], decls=_DECLS, shape=SpecShape(step_ranks=STEP_RANKS),
    )
    assert links_clause(graph, "fix-1") == "(1 node, in step 11; it holds no other entry and needs one first)"
