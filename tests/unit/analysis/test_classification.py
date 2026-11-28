"""Classifier unit tests: ``place`` on a hand-built graph, no file I/O."""
from __future__ import annotations

import pytest

from specdev_tools.analysis.upstream_backlog import UNPLACED, Placement, expand, group_key, place, Record
from specdev_tools.core.ambiguity_items import AmbiguityItem, shape_of
from specdev_tools.graph.model import Graph, Node, SpecShape

_RANKS = {"seed": -1, "00": 0, "04": 4, "05": 5, "06": 6, "14": 14, "16": 16}
_KIND_STEPS = {"criterion": ("04",), "api": ("05",), "fr": ("04",)}


def _node(node_id: str, kind: str, step: str, *, aliases: tuple[str, ...] = ()) -> Node:
    file = "docs/seed/seed.md" if step == "seed" else f"{step}_x.json"
    return Node(node_id, kind, step, None, file, "", None, (), "active", None, (), node_id, aliases=aliases)


@pytest.fixture
def graph() -> Graph:
    nodes = [
        _node("seed-accounts", "seed", "seed"),
        _node("fr-a", "fr", "04", aliases=("fr-old-a",)),
        _node("ac-a-3", "criterion", "04"),
        _node("api-b", "api", "05"),
    ]
    return Graph.from_nodes(nodes, shape=SpecShape(step_ranks=_RANKS, kind_steps=_KIND_STEPS))


def _item(raw: dict, step: str = "16a") -> AmbiguityItem:
    return AmbiguityItem("/s/impl_context/ms_x_plan.json", step, ".plan.ambiguities", raw, shape_of(raw))


def test_items_about_a_seed_and_a_node_give_groups_seed_and_04(graph):
    seed_item = _item({"id": "amb-1", "about": ["seed-accounts"]})
    node_item = _item({"id": "amb-2", "about": ["ac-a-3"]})
    assert place(seed_item, graph).groups == ("seed",)
    assert place(node_item, graph).groups == ("04",)
    groups = sorted({*place(seed_item, graph).groups, *place(node_item, graph).groups}, key=lambda g: group_key(g, graph))
    assert groups == ["seed", "04"]


def test_item_about_nodes_of_two_steps_appears_in_each_and_counts_once(graph):
    item = _item({"id": "amb-1", "about": ["fr-a", "api-b"]})
    placement = place(item, graph)
    assert placement.groups == ("04", "05")
    occurrences = expand(Record(item, "impl_context/ms_x_plan.json", placement))
    assert [(r.group, r.also_in) for r in occurrences] == [("04", ()), ("05", ("04",))]


def test_alias_in_about_resolves_to_the_node(graph):
    assert place(_item({"id": "amb-1", "about": ["fr-old-a"]}), graph).groups == ("04",)


@pytest.mark.parametrize(
    "impact, expected",
    [
        (["spec/14_roadmap.json:t-1", "spec/04_fr_list.json:fr-x"], "04"),
        (["spec/04_fr_list.json:fr-x", "spec/14_roadmap.json:t-1"], "04"),
        (["SCREAMING", "spec/06_invariants.json"], "06"),
    ],
)
def test_legacy_item_with_impact_lands_in_the_earliest_step_flagged_legacy(graph, impact, expected):
    item = _item({"id": "amb-1", "severity": "high", "status": "tracking", "impact": impact}, step="16b")
    assert place(item, graph).groups == (expected,)
    assert item.shape == "legacy"


@pytest.mark.parametrize("raw", [
    {"id": "amb-1", "severity": "low", "impact": ["SCREAMING_TOKEN"]},
    {"id": "amb-2", "severity": "low", "impact": []},
    {"id": "amb-3", "severity": "low"},
])
def test_legacy_item_without_a_step_in_impact_is_unplaced(graph, raw):
    assert place(_item(raw), graph) == Placement((UNPLACED,), (), ())


def test_silent_spec_item_lands_in_the_step_of_its_missing_kind(graph):
    item = _item({"id": "amb-1", "about": ["api-b"], "missing_kind": "criterion"})
    placement = place(item, graph)
    assert placement.groups == ("04",)
    assert [p["id"] for p in placement.impact] == ["api-b"]


def test_item_whose_about_does_not_resolve_is_unplaced(graph):
    assert place(_item({"id": "amb-1", "about": ["fr-nowhere"]}), graph).groups == (UNPLACED,)


def test_item_with_one_resolved_target_is_placed_by_it(graph):
    assert place(_item({"id": "amb-1", "about": ["fr-nowhere", "api-b"]}), graph).groups == ("05",)


def test_group_order_is_seed_then_steps_then_unplaced(graph):
    shuffled = [UNPLACED, "05", "seed", "04"]
    assert sorted(shuffled, key=lambda g: group_key(g, graph)) == ["seed", "04", "05", UNPLACED]


def test_derived_impact_points_at_the_files_of_non_seed_nodes(graph):
    placement = place(_item({"id": "amb-1", "about": ["seed-accounts", "fr-a"]}), graph)
    assert placement.impact == ({"file": "spec/04_x.json", "id": "fr-a"},)
