"""Each listing of nodes uses the one order key at its call site (M4 round 4, R4-1).

``test_lookup_and_order`` tests the key.  These tests fail when a listing stops using it: each builds a graph in
which the id order is not the step order, and two steps that the step order does not rank differ by name.
"""
from __future__ import annotations

import pytest

from specdev_tools.graph import queries
from specdev_tools.graph.build import build_graph
from specdev_tools.graph.kinds import LinkDecl
from specdev_tools.graph.model import Graph, Link, LoadError, Node, SpecShape
from specdev_tools.graph.recipes import build_pack, load_recipes
from specdev_tools.graph.resolve import resolve_graph
from specdev_tools.graph.trace import trace_node

from ._synth import EXAMPLE_SPEC, ROOT

_DECL = LinkDecl(field="derives_from", kinds=("*",), required=False, built=True, same_step_kinds=())
_RANKS = {"s1": 0, "s2": 1, "s3": 2}

# (id, step) in the order the step order gives; the id order of the same nodes is the reverse, and the two unranked
# steps ("xx", "yy") hold ids in the reverse of their name order.
_BY_STEP_ORDER = [("z-1", "s1"), ("m-2", "s2"), ("z-x", "xx"), ("a-y", "yy")]


def _node(node_id: str, step: str, targets: tuple[str, ...] = ()) -> Node:
    links = tuple(Link(node_id, _DECL.field, target, _DECL) for target in targets)
    return Node(node_id, "fr", step, "obligation-system", f"{step}.json", ".fr[0]", None, (), "active", None, links, node_id)


@pytest.fixture(scope="module")
def synthetic() -> Graph:
    """``entry`` (step s3) links up to the four nodes and the four link down to it."""
    members = [_node(node_id, step) for node_id, step in _BY_STEP_ORDER]
    uppers = [_node("entry", "s3", tuple(node_id for node_id, _ in _BY_STEP_ORDER))]
    return Graph.from_nodes([*members, *uppers], shape=SpecShape(step_ranks=_RANKS))


def _step_order_ids() -> list[str]:
    return [node_id for node_id, _ in _BY_STEP_ORDER]


def test_the_fixture_has_an_id_order_that_is_not_the_step_order() -> None:
    assert sorted(_step_order_ids()) != _step_order_ids()


def test_trace_side_lists_by_step_then_id(synthetic: Graph) -> None:
    side = trace_node(synthetic, "entry", ("up",)).up
    assert side is not None
    assert [node.id for node in side.nodes] == _step_order_ids()


def test_trace_reached_lists_by_step_then_id(synthetic: Graph) -> None:
    result = trace_node(synthetic, "entry", ("up",))
    assert [node.id for node in result.reached] == [*_step_order_ids()[:2], "entry", *_step_order_ids()[2:]]


def test_candidates_list_by_step_then_id() -> None:
    graph = build_graph(str(EXAMPLE_SPEC), str(ROOT))
    found = [item.id for item in queries.candidates(graph, "mitigated_by", kind="threat").candidates]
    assert found != sorted(found), "the example must hold candidates whose id order is not their step order"
    nodes = {node.id: node for node in graph.nodes}
    assert found == sorted(found, key=lambda node_id: graph.shape.order_key(nodes[node_id]))


def test_pack_whole_kind_and_matched_entries_list_by_step_then_id() -> None:
    graph = build_graph(str(EXAMPLE_SPEC), str(ROOT))
    pack = build_pack(graph, load_recipes(str(ROOT)), "16b", "PWRESET_CONFIRM_EXPIRED_01")
    found = [entry.id for entry in pack.sections["universal"] if entry.id in graph.by_id]  # the pointer row is not a node
    assert found != sorted(found), "the example must hold entries whose id order is not their step order"
    assert found == sorted(found, key=lambda node_id: graph.shape.order_key(graph.by_id[node_id]))


def _missing_target_graph(steps: tuple[str, ...], unreadable: tuple[str, ...] = ()) -> Graph:
    """A holder whose link target is in no file; the kind ``X`` is declared by each of *steps*.

    Each of *steps* has a file in the spec folder when it is in *unreadable* (the build skipped it) and none otherwise.
    """
    decl = LinkDecl(field="derives_from", kinds=("X",), required=False, built=True, same_step_kinds=())
    holder = Node("holder", "H", "s9", "obligation-system", "s9.json", ".h[0]", None, (), "active", None,
                  (Link("holder", "derives_from", "ghost", decl),), "")
    shape = SpecShape(
        step_ranks={"zb": 0, "za": 1, "s9": 9},
        kind_steps={"X": steps},
        files_by_step={step: (f"{step}.json",) for step in unreadable},
    )
    return Graph.from_nodes([holder], load_errors=[LoadError(f"{step}.json", "unreadable") for step in unreadable], shape=shape)


def test_steps_named_for_an_absent_target_come_in_step_order() -> None:
    """``zb`` is before ``za`` in the step order; ``xx`` and ``yy`` are not ranked, so they follow, by name."""
    (error,) = resolve_graph(_missing_target_graph(("yy", "za", "xx", "zb")))
    assert "no file of step zb, za, xx, yy exists" in error.message


def test_the_unreadable_file_named_is_the_one_of_the_first_step_in_step_order() -> None:
    """Both files were skipped; ``zb`` is before ``za`` in the step order, though not by name."""
    (error,) = resolve_graph(_missing_target_graph(("za", "zb"), unreadable=("za", "zb")))
    assert "the file zb.json of step zb could not be read" in error.message
