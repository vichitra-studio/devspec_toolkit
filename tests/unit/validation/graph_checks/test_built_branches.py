"""The coarse, constraint and evidence branches of the built computation, and its provider seam (WI-M6b-04)."""
from __future__ import annotations

from dataclasses import replace

import pytest

from specdev_tools.graph.model import Node
from specdev_tools.validation.graph_checks.built import (
    EVIDENCE_KINDS,
    BuiltComputation,
    BuiltResult,
    BuiltState,
    compute_built,
    walk_derivations,
)

from ._bindings_support import Bindings
from ._built_support import built_context, link, node

BUILT, NOT_BUILT, PENDING = BuiltState.BUILT, BuiltState.NOT_BUILT, BuiltState.PENDING_EVIDENCE


def _coarse_with(*derived: Node) -> list[Node]:
    return [node("scope-1", "scope-item", step="00"), *derived]


def _capability(cap_id: str = "cap-1") -> Node:
    return node(cap_id, "capability", step="01", links=[("derives_from", "scope-1")])


def test_coarse_parent_with_a_pending_child_is_pending() -> None:
    nodes = _coarse_with(_capability(), node("rule-1", "rule", step="10", links=[("derives_from", "scope-1")]), node("inv-1", "invariant"))
    ctx = built_context([*nodes, node("fr-1", "fr", links=[("derives_from", "cap-1")], children=["ac-1"]), node("ac-1", "criterion", parent="fr-1")], {"tc-1": "ac-1"})
    result = compute_built(ctx)
    assert result["cap-1"].state is BUILT
    assert result["scope-1"].state is PENDING and result["scope-1"].via == ("rule-1",)


def test_pending_child_with_a_not_built_sibling_is_not_built() -> None:
    nodes = _coarse_with(_capability(), node("rule-1", "rule", step="10", links=[("derives_from", "scope-1")]))
    result = compute_built(built_context(nodes))
    assert result["cap-1"].state is NOT_BUILT
    assert result["scope-1"].state is NOT_BUILT and result["scope-1"].via == ("cap-1",)


def test_register_built_provider_first_match_decides(bindings: Bindings) -> None:
    nodes = [node("inv-1", "invariant"), node("inv-2", "invariant"), node("nfr-1", "nfr", step="07")]
    ctx = built_context(nodes)
    answer = lambda state: (lambda _run, found: BuiltResult(state, f"{state.value} for {found.id}"))  # noqa: E731
    restore_all = bindings.provider(lambda found: found.kind == "invariant", answer(BUILT))
    restore_second = bindings.provider(lambda found: found.id == "inv-2", answer(PENDING))
    result = compute_built(ctx)
    assert (result["inv-1"].state, result["inv-2"].state, result["nfr-1"].state) == (BUILT, BUILT, NOT_BUILT)
    assert result["inv-2"].reason == "BUILT for inv-2"
    restore_second()
    restore_all()
    assert compute_built(ctx)["inv-1"].state is NOT_BUILT


def test_a_provider_gets_the_state_of_another_node_from_the_same_run(bindings: Bindings) -> None:
    """The computation handed to a provider answers for any node through the memo of the run: a node is computed once, however it is reached."""
    asked: list[str] = []

    def about_inv_2(_run: BuiltComputation, found: Node) -> BuiltResult:
        asked.append(found.id)
        return BuiltResult(BUILT, "stub")

    def about_inv_1(run: BuiltComputation, found: Node) -> BuiltResult:
        other = run.ctx.graph.by_id["inv-2"]
        return BuiltResult(run.result_of(other).state, "follows inv-2", (other.id,))

    bindings.provider(lambda found: found.id == "inv-1", about_inv_1)
    bindings.provider(lambda found: found.id == "inv-2", about_inv_2)
    result = compute_built(built_context([node("inv-1", "invariant"), node("inv-2", "invariant")]))
    assert (result["inv-1"].state, result["inv-1"].via, result["inv-2"].state) == (BUILT, ("inv-2",), BUILT)
    assert asked == ["inv-2"]


def test_providers_that_ask_each_other_end_in_the_cycle_guard(bindings: Bindings) -> None:
    def ask(other: str):
        def provider(run: BuiltComputation, found: Node) -> BuiltResult:
            return BuiltResult(run.result_of(run.ctx.graph.by_id[other]).state, f"{found.id} follows {other}")

        return provider

    bindings.provider(lambda found: found.id == "inv-1", ask("inv-2"))
    bindings.provider(lambda found: found.id == "inv-2", ask("inv-1"))
    result = compute_built(built_context([node("inv-1", "invariant"), node("inv-2", "invariant")]))
    assert (result["inv-1"].state, result["inv-2"].state) == (NOT_BUILT, NOT_BUILT)


def test_a_provider_is_not_asked_about_a_node_out_of_play(bindings: Bindings) -> None:
    asked: list[str] = []

    def provider(_run, found: Node) -> BuiltResult:
        asked.append(found.id)
        return BuiltResult(BUILT, "stub")

    bindings.provider(lambda found: found.kind == "invariant", provider)
    result = compute_built(built_context([node("inv-1", "invariant"), node("inv-later", "invariant", scope="later")]))
    assert asked == ["inv-1"] and result["inv-later"].state is BuiltState.IGNORED


def _constraint(component_users: list[Node], *extra: Node) -> list[Node]:
    return [
        node("con-1", "constraint", step="00"),
        node("cn-1", "component", "context", step="02", links=[("derives_from", "con-1")]),
        *component_users, *extra,
    ]


@pytest.mark.parametrize("field", ["provided_by", "constrains"])
def test_constraint_component_branch_positive(field: str) -> None:
    user = node("user-1", "api" if field == "provided_by" else "invariant", step="05", links=[(field, "cn-1")])
    result = compute_built(built_context(_constraint([user]), {"tc-1": "user-1"}))
    assert result["con-1"].state is BUILT and result["con-1"].via == ("cn-1",)


def test_constraint_component_used_through_a_connection_it_is_the_source_of() -> None:
    connection = node("conn-1", "connection", "context", step="02", links=[("derives_from", "cn-1")])
    user = node("nfr-1", "nfr", step="07", links=[("constrains", "conn-1")])
    result = compute_built(built_context(_constraint([user], connection), {"tc-1": "nfr-1"}))
    assert result["con-1"].state is BUILT


@pytest.mark.parametrize("case", ["no user", "user not built", "user out of scope"])
def test_constraint_component_branch_negative(case: str) -> None:
    users = {
        "no user": [], "user not built": [node("user-1", "invariant", links=[("constrains", "cn-1")])],
        "user out of scope": [node("user-1", "invariant", scope="out", links=[("constrains", "cn-1")])],
    }[case]
    result = compute_built(built_context(_constraint(users)))
    assert result["con-1"].state is NOT_BUILT and result["con-1"].via == ()


@pytest.mark.parametrize(("pin", "state"), [("OK", BUILT), ("MISMATCH", NOT_BUILT), ("UNKNOWN", PENDING)])
def test_constraint_third_party_with_a_stub_pin_provider_ok_and_mismatch(pin: str, state: BuiltState, bindings: Bindings) -> None:
    nodes = [
        node("con-1", "constraint", step="00"),
        node("tp-1", "third-party", "context", step="02", links=[("derives_from", "con-1")]),
        node("nfr-1", "nfr", step="07", links=[("relies_on", "tp-1")]),
    ]
    bindings.seams(pin_matches=lambda _third_party: pin)
    result = compute_built(built_context(nodes, {"tc-1": "nfr-1"}))
    assert result["con-1"].state is state and result["con-1"].via == ("tp-1",)


def test_constraint_third_party_nobody_relies_on_does_not_count() -> None:
    nodes = [node("con-1", "constraint", step="00"), node("tp-1", "third-party", "context", step="02", links=[("derives_from", "con-1")])]
    assert compute_built(built_context(nodes))["con-1"].state is NOT_BUILT


def test_constraint_derived_by_a_gate_is_pending_and_a_not_built_derivation_wins() -> None:
    gate = node("gate-1", "gate", "obligation-delivery", step="02a", links=[("derives_from", "con-1")])
    component_unused = node("cn-1", "component", "context", step="02", links=[("derives_from", "con-1")])
    third = node("tp-1", "third-party", "context", step="02", links=[("derives_from", "con-1")])
    result = compute_built(built_context([node("con-1", "constraint", step="00"), gate, component_unused, third]))
    assert result["con-1"].state is PENDING and result["con-1"].via == ("gate-1",)


@pytest.mark.parametrize("kind", sorted(EVIDENCE_KINDS))
def test_evidence_kinds_return_pending_evidence(kind: str) -> None:
    role = "obligation-delivery" if kind in {"environment", "gate", "secret"} else "obligation-system"
    assert compute_built(built_context([node("x-1", kind, role)]))["x-1"].state is PENDING


@pytest.mark.parametrize(("built", "state"), [(True, BUILT), (False, NOT_BUILT)])
def test_built_reads_the_declared_built_links(built: bool, state: BuiltState) -> None:
    """A verb no code names counts for the coarse branch exactly when the registry declares its link ``built``."""
    invariant = replace(node("inv-1", "invariant", step="06"), links=(link("inv-1", "new_verb", "scope-1", built=built),))
    result = compute_built(built_context([node("scope-1", "scope-item", step="00"), invariant], {"tc-1": "inv-1"}))
    assert result["inv-1"].state is BUILT
    assert result["scope-1"].state is state


def test_walk_derivations_follows_the_given_verbs_to_a_fixed_point() -> None:
    nodes = [
        node("a-1", "capability", step="01", links=[("derives_from", "b-1")]), node("b-1", "scope-item", step="00", links=[("derives_from", "a-1")]),
        node("c-1", "fr", links=[("derives_from", "a-1")]), node("d-1", "fr", links=[("assumes", "b-1")]),
        node("e-1", "fr", scope="out", links=[("derives_from", "c-1")]),
    ]
    ctx = built_context(nodes)
    start = ctx.graph.by_id["b-1"]
    assert [found.id for found in walk_derivations(ctx, start, ["derives_from"])] == ["a-1", "c-1"]
    assert [found.id for found in walk_derivations(ctx, start, ["assumes"])] == ["d-1"]
    assert walk_derivations(ctx, start, []) == []
