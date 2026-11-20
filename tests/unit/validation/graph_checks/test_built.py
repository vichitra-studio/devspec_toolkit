"""The built computation: the hash-based branches, the lifecycle gate and the order of its result (WI-M6b-04)."""
from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

from specdev_tools.validation.graph_checks.built import BuiltState, compute_built
from specdev_tools.validation.graph_checks.design_milestones import unrealised_design_milestones
from unit.graph._synth import HASH_SEEDS

from ._built_support import built_context, closed_work, context_of, current_lock, graph_of, node
from ._order_support import seeded

LEAF_KINDS = ("invariant", "nfr", "api-error", "criterion")


def _state(ctx, node_id):
    return compute_built(ctx)[node_id].state


@pytest.mark.parametrize("kind", LEAF_KINDS)
def test_leaf_built_iff_a_counting_refinement_exists(kind: str) -> None:
    leaves = [node("o-1", kind), node("o-2", kind)]
    ctx = built_context(leaves, {"tc-1": "o-1"})
    result = compute_built(ctx)
    assert result["o-1"].state is BuiltState.BUILT and result["o-1"].via == ("tc-1",)
    assert result["o-2"].state is BuiltState.NOT_BUILT


def test_hash_mismatch_makes_a_refined_node_not_built() -> None:
    nodes, documents = closed_work({"tc-1": "inv-1"})
    graph = graph_of([node("inv-1", "invariant"), *nodes], documents)
    assert _state(context_of(graph, current_lock(graph)), "inv-1") is BuiltState.BUILT
    assert _state(context_of(graph, current_lock(graph, stale=["tc-1"])), "inv-1") is BuiltState.NOT_BUILT


def test_a_changed_obligation_is_not_built_until_it_is_refined_again() -> None:
    nodes, documents = closed_work({"tc-1": "inv-1"})
    accepted = graph_of([node("inv-1", "invariant"), *nodes], documents)
    lock = current_lock(accepted)
    edited = graph_of([node("inv-1", "invariant", links=[("assumes", "asm-1")]), *nodes], documents)
    assert _state(context_of(edited, lock), "inv-1") is BuiltState.NOT_BUILT


def test_milestone_not_closed_makes_it_not_built() -> None:
    ctx = built_context([node("inv-1", "invariant")], {"tc-1": "inv-1"}, done=False)
    assert _state(ctx, "inv-1") is BuiltState.NOT_BUILT


@pytest.mark.parametrize(("disposition", "state"), [
    ("deferred", BuiltState.NOT_BUILT), ("wont_do", BuiltState.NOT_BUILT), (None, BuiltState.BUILT),
])
def test_deferred_or_wont_do_criterion_gives_no_count(disposition: str | None, state: BuiltState) -> None:
    ctx = built_context([node("inv-1", "invariant")], {"tc-1": "inv-1"}, disposition=disposition)
    assert _state(ctx, "inv-1") is state


def test_missing_lock_entry_gives_no_count() -> None:
    nodes, documents = closed_work({"tc-1": "inv-1"})
    graph = graph_of([node("inv-1", "invariant"), *nodes], documents)
    assert _state(context_of(graph, current_lock(graph, skip=["tc-1"])), "inv-1") is BuiltState.NOT_BUILT
    assert _state(context_of(graph, None), "inv-1") is BuiltState.NOT_BUILT


def test_a_lock_entry_written_with_an_alias_is_found_under_the_alias() -> None:
    renamed = replace(node("inv-1", "invariant"), aliases=("inv-old-name",))
    nodes, documents = closed_work({"tc-1": "inv-old-name"})
    graph = graph_of([renamed, *nodes], documents)
    assert "inv-old-name" not in graph.by_id and _state(context_of(graph, current_lock(graph)), "inv-1") is BuiltState.BUILT


def test_api_with_only_built_errors_is_not_built() -> None:
    api = node("api-1", "api", step="05", children=["err-1"])
    error = node("err-1", "api-error", step="05", parent="api-1")
    result = compute_built(built_context([api, error], {"tc-1": "err-1"}))
    assert result["err-1"].state is BuiltState.BUILT
    assert result["api-1"].state is BuiltState.NOT_BUILT


def test_api_refined_directly_is_built() -> None:
    api = node("api-1", "api", step="05", children=["err-1"])
    error = node("err-1", "api-error", step="05", parent="api-1")
    result = compute_built(built_context([api, error], {"tc-1": "api-1"}))
    assert result["api-1"].state is BuiltState.BUILT and result["err-1"].state is BuiltState.NOT_BUILT


def _fr_with(*criteria: str, scope: dict[str, str] | None = None) -> list:
    scopes = scope or {}
    return [node("fr-1", "fr", children=criteria)] + [
        node(cid, "criterion", parent="fr-1", scope=scopes.get(cid)) for cid in criteria
    ]


def test_fr_with_all_criteria_built_is_built() -> None:
    ctx = built_context(_fr_with("ac-1", "ac-2"), {"tc-1": "ac-1", "tc-2": "ac-2"})
    result = compute_built(ctx)
    assert result["fr-1"].state is BuiltState.BUILT and result["fr-1"].via == ("ac-1", "ac-2")
    partial = compute_built(built_context(_fr_with("ac-1", "ac-2"), {"tc-1": "ac-1"}))
    assert partial["fr-1"].state is BuiltState.NOT_BUILT and partial["fr-1"].via == ("ac-2",)


def test_a_child_out_of_scope_is_left_out_of_the_denominator() -> None:
    ctx = built_context(_fr_with("ac-1", "ac-2", scope={"ac-2": "later"}), {"tc-1": "ac-1"})
    result = compute_built(ctx)
    assert result["ac-2"].state is BuiltState.IGNORED and result["fr-1"].state is BuiltState.BUILT


def test_parent_with_no_in_scope_child_needs_a_direct_refinement() -> None:
    parent = _fr_with("ac-1", scope={"ac-1": "out"})
    assert _state(built_context(parent), "fr-1") is BuiltState.NOT_BUILT
    assert _state(built_context(parent, {"tc-1": "fr-1"}), "fr-1") is BuiltState.BUILT


def test_capability_with_zero_frs_is_not_built() -> None:
    cap = node("cap-1", "capability", step="01")
    result = compute_built(built_context([cap]))["cap-1"]
    assert result.state is BuiltState.NOT_BUILT and result.via == ()


def _graph_with_every_state():
    nodes, documents = closed_work({"tc-1": "inv-1"})
    return [
        node("inv-1", "invariant", step="06"),
        node("inv-dep", "invariant", step="06", lifecycle="deprecated"),
        node("inv-gone", "invariant", step="06", lifecycle="not_applicable"),
        node("inv-later", "invariant", step="06", scope="later"),
        node("inv-out", "invariant", step="06", scope="out"),
        node("cn-ctx", "component", "context", step="02"),
        *nodes,
    ], documents


def test_out_of_play_and_context_nodes_are_ignored() -> None:
    nodes, documents = _graph_with_every_state()
    graph = graph_of(nodes, documents)
    result = compute_built(context_of(graph, current_lock(graph)))
    assert "inv-gone" not in result
    assert result["inv-dep"].state is BuiltState.NOT_BUILT
    assert {result[i].state for i in ("inv-later", "inv-out", "cn-ctx", "ms-m", "tc-1", "anchor-m")} == {BuiltState.IGNORED}
    assert result["inv-1"].state is BuiltState.BUILT
    assert compute_built(context_of(graph, current_lock(graph)), "inv-gone")["inv-gone"].state is BuiltState.IGNORED


def test_deprecated_obligation_still_counts_as_a_child() -> None:
    nodes = [node("fr-1", "fr", children=["ac-1", "ac-2"]), node("ac-1", "criterion", parent="fr-1"), node("ac-2", "criterion", parent="fr-1", lifecycle="deprecated")]
    assert _state(built_context(nodes, {"tc-1": "ac-1"}), "fr-1") is BuiltState.NOT_BUILT


def test_derivation_cycle_is_guarded() -> None:
    first = node("scope-1", "scope-item", step="00", links=[("derives_from", "cap-1")])
    second = node("cap-1", "capability", step="01", links=[("derives_from", "scope-1")])
    result = compute_built(built_context([first, second]))
    assert {result["scope-1"].state, result["cap-1"].state} == {BuiltState.NOT_BUILT}


def test_unrealised_design_milestones() -> None:
    schedule = lambda mid, *targets: node(mid, "design-milestone", "plan", step="09", links=[("schedules", t) for t in targets])  # noqa: E731
    nodes = [
        node("fr-1", "fr"), node("fr-2", "fr"), schedule("dm-realised", "fr-1"), schedule("dm-open", "fr-2"),
        schedule("dm-nothing"), node("dm-gone", "design-milestone", "plan", step="09", lifecycle="not_applicable", links=[("schedules", "fr-2")]),
    ]
    ctx = built_context(nodes, {"tc-1": "fr-1"})
    assert [milestone.id for milestone in unrealised_design_milestones(ctx)] == ["dm-nothing", "dm-open"]


def _order_nodes():
    return [
        node("cap-1", "capability", step="01"), node("fr-1", "fr", children=["ac-1", "ac-2"]),
        node("ac-1", "criterion", parent="fr-1"), node("ac-2", "criterion", parent="fr-1"),
        node("inv-1", "invariant", step="06"), node("rule-1", "rule", step="10"),
    ]


def _scenario(reverse: bool) -> list[list[Any]]:
    """The built state of every node of ``_order_nodes`` (listed in reverse, its criteria refining in reverse, when *reverse*)."""
    nodes, refines = _order_nodes(), {"tc-1": "inv-1", "tc-2": "ac-2"}
    ctx = built_context(list(reversed(nodes)) if reverse else nodes, dict(reversed(list(refines.items()))) if reverse else refines)
    return [[i, r.state.value, r.reason, list(r.via)] for i, r in compute_built(ctx).items()]


@pytest.mark.parametrize("seed", HASH_SEEDS)
def test_built_reports_in_the_same_order_whatever_the_hash_seed(seed: int) -> None:
    ctx = built_context(_order_nodes(), {"tc-1": "inv-1", "tc-2": "ac-2"})
    expected = _scenario(False)
    assert seeded(seed, __name__, "_scenario", True) == expected
    assert [row[0] for row in expected] == sorted((row[0] for row in expected), key=lambda i: (ctx.graph.shape.step_key(ctx.graph.by_id[i].step), i))
