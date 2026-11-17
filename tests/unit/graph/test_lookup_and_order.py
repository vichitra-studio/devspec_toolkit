"""One lookup of an id and one order of nodes: ``Graph.find`` and ``SpecShape.order_key`` (round 3, D-1 and D-2)."""
from __future__ import annotations

from pathlib import Path

import pytest

from specdev_tools.graph import queries
from specdev_tools.graph.build import build_graph
from specdev_tools.graph.lifecycle import plan_lifecycle_change
from specdev_tools.graph.model import UNRANKED, Graph, Node, SpecShape
from specdev_tools.graph.recipes import build_pack, load_recipes
from specdev_tools.graph.trace import trace_node

from ._synth import EXAMPLE_SPEC, ROOT

_FR = "fr-password-reset"
_PLAN_ITEM = "PWRESET_CONFIRM_EXPIRED_01"
_ALIASES = {"fr-old-name": _FR, "plan-old-name": _PLAN_ITEM}


@pytest.fixture
def aliased() -> Graph:
    """The worked example with an alias index filled by hand (M4 builds it empty)."""
    graph = build_graph(str(EXAMPLE_SPEC), str(ROOT))
    graph.alias_index.update(_ALIASES)
    return graph


def test_find_looks_up_an_id_then_an_alias(aliased: Graph) -> None:
    assert aliased.find(_FR) is aliased.by_id[_FR]
    assert aliased.find("fr-old-name") is aliased.by_id[_FR]
    assert aliased.find("no-such-node") is None


def test_an_id_wins_over_an_alias_of_the_same_name(aliased: Graph) -> None:
    aliased.alias_index["ac-password-reset-3"] = _FR
    assert aliased.find("ac-password-reset-3") is aliased.by_id["ac-password-reset-3"]


def test_node_finds_a_node_by_its_alias(aliased: Graph) -> None:
    assert [view.id for view in queries.node_view(aliased, ["fr-old-name"]).views] == [_FR]


def test_candidates_for_finds_the_holder_by_its_alias(aliased: Graph) -> None:
    by_alias = queries.candidates(aliased, "realises", for_id="plan-old-name")
    by_id = queries.candidates(aliased, "realises", for_id=_PLAN_ITEM)
    assert by_alias == by_id and by_id.total > 0


def test_trace_finds_the_entry_by_its_alias(aliased: Graph) -> None:
    assert trace_node(aliased, "fr-old-name").entry.id == _FR


def test_node_status_plans_the_change_of_the_node_an_alias_names(aliased: Graph) -> None:
    change = plan_lifecycle_change(aliased, "fr-old-name", "deprecated")
    assert (change.node_id, change.old, change.new) == (_FR, "active", "deprecated")


def test_a_recipe_starts_from_the_node_an_alias_names(aliased: Graph) -> None:
    table = load_recipes(str(ROOT))
    assert build_pack(aliased, table, "16b", "plan-old-name").start.id == _PLAN_ITEM


def _node(node_id: str, step: str | None) -> Node:
    return Node(node_id, "fr", step, None, "f.json", "", None, (), "active", None, (), "")


def test_order_key_is_rank_then_step_then_id() -> None:
    shape = SpecShape(step_ranks={"04": 4, "05": 5})
    nodes = [_node("b", "05"), _node("a", "zz"), _node("c", None), _node("a", "04"), _node("a", "yy")]
    assert [(n.step, n.id) for n in sorted(nodes, key=shape.order_key)] == [
        ("04", "a"), ("05", "b"), (None, "c"), ("yy", "a"), ("zz", "a"),
    ]
    assert shape.order_key(_node("c", None))[0] == UNRANKED


def test_step_key_orders_steps_the_way_a_node_is_ordered() -> None:
    shape = SpecShape(step_ranks={"04": 4})
    assert sorted(["zz", "04", "aa"], key=shape.step_key) == ["04", "aa", "zz"]
