"""The cross-cutting obligation check (E744): a task an obligation reaches carries a criterion that refines it (WI-M6b-06)."""
from __future__ import annotations

from dataclasses import replace

import pytest

from specdev_tools.core.errors import link_target
from specdev_tools.graph.build import build_graph
from specdev_tools.graph.model import Node
from specdev_tools.validation.graph_checks.context import GraphCheckContext
from specdev_tools.validation.graph_checks.cross_cutting import check_cross_cutting
from unit.graph._synth import EXAMPLE_SPEC, HASH_SEEDS, ROOT

from ._order_support import seeded
from ._built_support import closed_milestone, node, spec

NFR = "nfr-mobile"


def _e744(ctx: GraphCheckContext) -> list[tuple[str | None, str | None]]:
    return [(error.node_id, error.target) for error in check_cross_cutting(ctx, "merge")]


def _gap(task: str, obligation: str = NFR) -> tuple[str, str]:
    return task, link_target("refines", obligation)


def _task(task_id: str, *refines: str, parent: str | None = None, **fields: object) -> list[Node]:
    criterion = node(f"tc-{task_id}", "task-criterion", parent=task_id, refines=list(refines))
    return [node(task_id, "task", parent=parent, **fields), criterion]


def _lineage(fr: str, capability: str, component: str | None = None) -> list[Node]:
    """An FR under a capability with one criterion; an API of the FR provided by *component* when one is given."""
    nodes = [node(capability, "capability"), node(fr, "fr", derives_from=[capability]), node(f"ac-{fr}", "criterion", parent=fr)]
    if component:
        nodes += [node(component, "component"), node(f"api-{fr}", "api", derives_from=[fr], provided_by=[component])]
    return nodes


def _devspec_288(*, shared: str | None = None) -> list[Node]:
    """NFR over fr-a under cap-x; T1 refines fr-a's criterion, T2 refines fr-b's (a different capability, or cap-x when *shared* is ``cap``)."""
    second_cap = "cap-x" if shared == "cap" else "cap-y"
    nodes = [*_lineage("fr-a", "cap-x"), *([] if shared == "cap" else [node("cap-y", "capability")])]
    nodes += [node("fr-b", "fr", derives_from=[second_cap]), node("ac-fr-b", "criterion", parent="fr-b")]
    return [*nodes, node(NFR, "nfr", constrains=["fr-a"]), *_task("t1", "ac-fr-a"), *_task("t2", "ac-fr-b")]


def test_nfr_constraining_a_fr_binds_the_task_refining_its_criterion() -> None:
    nodes = [*_lineage("fr-a", "cap-x"), node(NFR, "nfr", constrains=["fr-a"]), *_task("t1", "ac-fr-a")]
    assert _e744(spec(*nodes)) == [_gap("t1")]


def test_adding_a_refining_criterion_clears_e744() -> None:
    nodes = [*_lineage("fr-a", "cap-x"), node(NFR, "nfr", constrains=["fr-a"]), *_task("t1", "ac-fr-a", NFR)]
    assert _e744(spec(*nodes)) == []
    two_criteria = [*nodes[:-1], node("tc-t1-b", "task-criterion", parent="t1", refines=[NFR])]
    assert _e744(spec(*two_criteria)) == []


def test_closed_milestone_task_is_excluded() -> None:
    nodes = [*_lineage("fr-a", "cap-x"), node(NFR, "nfr", constrains=["fr-a"]), *closed_milestone("ms-1"), *_task("t1", "ac-fr-a", parent="ms-1")]
    assert _e744(spec(*nodes)) == []
    assert _e744(spec(*[node for node in nodes if node.kind != "anchor-row"])) == [_gap("t1")]


def test_not_applicable_task_is_excluded() -> None:
    nodes = [*_lineage("fr-a", "cap-x"), node(NFR, "nfr", constrains=["fr-a"]), *_task("t1", "ac-fr-a", lifecycle="not_applicable")]
    assert _e744(spec(*nodes)) == []
    deprecated = [*nodes[:-2], *_task("t1", "ac-fr-a", lifecycle="deprecated")]
    assert _e744(spec(*deprecated)) == [_gap("t1")]


def test_component_reach_through_an_api() -> None:
    nodes = [
        *_lineage("fr-a", "cap-x", "svc"), *_lineage("fr-b", "cap-y"), node(NFR, "nfr", constrains=["svc"]),
        *_task("t1", "api-fr-a"), *_task("t2", "ac-fr-b"),
    ]
    assert _e744(spec(*nodes)) == [_gap("t1")]


def test_connection_reach_is_its_source_component() -> None:
    nodes = [
        *_lineage("fr-a", "cap-x", "svc"), node("svc-b", "component"), node("conn", "connection", derives_from=["svc"], connects_to=["svc-b"]),
        node(NFR, "nfr", constrains=["conn"]), *_task("t1", "api-fr-a"), *_task("t2", "svc-b"),
    ]
    assert _e744(spec(*nodes)) == [_gap("t1")]


def test_devspec_288_shaped_fixture_t1_only() -> None:
    assert _e744(spec(*_devspec_288())) == [_gap("t1")]
    cleared = [*_devspec_288()[:-4], *_task("t1", "ac-fr-a", NFR), *_task("t2", "ac-fr-b")]
    assert _e744(spec(*cleared)) == []


def test_shared_capability_binds_the_second_task_too() -> None:
    assert _e744(spec(*_devspec_288(shared="cap"))) == [_gap("t1"), _gap("t2")]


def test_api_error_lineage_reaches_the_capability_through_its_criterion() -> None:
    """A task criterion that refines an API error falls under what constrains the FR of the criterion the error derives from."""
    nodes = [*_lineage("fr-a", "cap-x"), node("err-a", "api-error", derives_from=["ac-fr-a"]), node(NFR, "nfr", constrains=["fr-a"]), *_task("t1", "err-a")]
    assert _e744(spec(*nodes)) == [_gap("t1")]


def test_a_not_applicable_criterion_that_refines_the_obligation_does_not_clear_it() -> None:
    nodes = [*_lineage("fr-a", "cap-x"), node(NFR, "nfr", constrains=["fr-a"]), *_task("t1", "ac-fr-a")]
    parked = node("tc-t1-b", "task-criterion", parent="t1", refines=[NFR], lifecycle="not_applicable")
    assert _e744(spec(*nodes, parked)) == [_gap("t1")]
    assert _e744(spec(*nodes, replace(parked, lifecycle="active"))) == []


def test_scope_later_or_out_obligation_is_not_checked() -> None:
    for scope in ("later", "out"):
        nodes = [*_lineage("fr-a", "cap-x"), node(NFR, "nfr", scope=scope, constrains=["fr-a"]), *_task("t1", "ac-fr-a")]
        assert _e744(spec(*nodes)) == []


def test_e744_finding_carries_task_node_id_and_refines_target() -> None:
    nodes = [*_lineage("fr-a", "cap-x"), node(NFR, "nfr", constrains=["fr-a"]), *_task("t1", "ac-fr-a")]
    (error,) = check_cross_cutting(spec(*nodes), "merge")
    assert (error.code, error.node_id, error.target, error.owner) == ("E744", "t1", f"refines->{NFR}", "step:14")
    assert all(name in error.message for name in ("t1", NFR, "cap-x"))


def test_graph_example_gives_exactly_one_e744() -> None:
    context = GraphCheckContext.from_graph(build_graph(str(EXAMPLE_SPEC), str(ROOT)), None)
    assert _e744(context) == [_gap("task-implement-password-reset-confirm", "nfr-latency-reset-email")]


def _scenario(reverse: bool) -> list[list[str | None]]:
    nodes = [*_devspec_288(shared="cap"), node("nfr-b", "nfr", constrains=["fr-a"])]
    return [[error.node_id, error.target] for error in check_cross_cutting(spec(*reversed(nodes) if reverse else nodes), "merge")]


@pytest.mark.parametrize("seed", HASH_SEEDS)
def test_cross_cutting_reports_in_the_same_order_whatever_the_hash_seed(seed: int) -> None:
    expected = _scenario(False)
    assert len(expected) == 4
    assert seeded(seed, __name__, "_scenario", True) == expected
