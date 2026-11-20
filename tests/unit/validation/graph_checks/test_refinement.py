"""The refinement check (E745): the verifier of a task criterion verifies the obligation it refines (WI-M6b-05)."""
from __future__ import annotations

import json

import pytest

from specdev_tools.core.errors import SpecError, link_target
from specdev_tools.graph.build import build_graph
from specdev_tools.validation.graph_checks.context import GraphCheckContext, bind_seams
from specdev_tools.validation.graph_checks.refinement import check_refinement, covering_verifiers
from unit.graph._synth import EXAMPLE_SPEC, HASH_SEEDS, ROOT, run_python_seeded

from .graph_builder import closed_milestone, row, spec


def _e745(ctx: GraphCheckContext) -> list[tuple[str | None, str | None]]:
    return [(error.node_id, error.target) for error in check_refinement(ctx, "merge")]


def _criterion(refines: list[str], verified_by: list[str], **fields: object):
    return row("tc-1", "task-criterion", parent="task-1", refines=refines, verified_by=verified_by, **fields)


def _base(*nodes):
    return [row("fr-a", "fr"), row("ac-a-1", "criterion", parent="fr-a"), row("task-1", "task"), *nodes]


def test_doc_example_tc1_fx1_and_tc2_fx2_pass() -> None:
    context = GraphCheckContext.from_graph(build_graph(str(EXAMPLE_SPEC), str(ROOT)), None)
    assert check_refinement(context, "merge") == []


def test_closed_milestone_criterion_with_a_deleted_fixture_gives_no_e745() -> None:
    nodes = [
        *closed_milestone("ms-1"), row("fr-a", "fr"), row("task-1", "task", parent="ms-1"),
        _criterion(["fr-a"], ["fix-deleted"]),
    ]
    assert _e745(spec(*nodes)) == []
    open_nodes = [node for node in nodes if node.kind not in ("anchor-row",)]
    assert _e745(spec(*open_nodes)) == [("tc-1", link_target("refines", "fr-a"))]


def test_removal_criterion_gives_no_e745() -> None:
    removal = row("tc-remove", "task-criterion", parent="task-1", removes=["fr-a"], verified_by=["fix-gone"])
    fixture = row("fix-gone", "fixture", removes=["fr-a"])
    assert _e745(spec(*_base(removal, fixture))) == []


def test_criterion_whose_fixture_verifies_something_else_gives_e745() -> None:
    nodes = _base(row("fr-b", "fr"), row("fix-1", "fixture", verifies=["fr-b"]), _criterion(["fr-a"], ["fix-1"]))
    assert _e745(spec(*nodes)) == [("tc-1", link_target("refines", "fr-a"))]


def test_fixture_verifying_a_descendant_covers_the_ancestor() -> None:
    nodes = _base(row("fix-1", "fixture", verifies=["ac-a-1"]), _criterion(["fr-a"], ["fix-1"]))
    assert _e745(spec(*nodes)) == []


def test_fixture_verifying_an_ancestor_covers_the_descendant() -> None:
    nodes = _base(row("fix-1", "fixture", verifies=["fr-a"]), _criterion(["ac-a-1"], ["fix-1"]))
    assert _e745(spec(*nodes)) == []


def test_job_realising_the_obligation_covers_it() -> None:
    nodes = _base(row("gate-1", "gate"), row("job-1", "job", realises=["gate-1"]), _criterion(["gate-1"], ["job-1"]))
    assert _e745(spec(*nodes)) == []


def test_rule_named_in_verified_by_covers_itself() -> None:
    nodes = _base(row("rule-1", "rule"), row("rule-2", "rule"), _criterion(["rule-1"], ["rule-1"]))
    assert _e745(spec(*nodes)) == []
    other = _base(row("rule-1", "rule"), row("rule-2", "rule"), _criterion(["rule-1"], ["rule-2"]))
    assert _e745(spec(*other)) == [("tc-1", link_target("refines", "rule-1"))]


def test_extra_verifiers_seam_stub_covers_an_obligation() -> None:
    context = spec(*_base(row("fix-1", "fixture"), _criterion(["fr-a"], ["fix-1"])))
    assert _e745(context) != []
    restore = bind_seams(extra_verifiers=lambda verifier: {"fr-a"})
    try:
        assert _e745(spec(*_base(row("fix-1", "fixture"), _criterion(["fr-a"], ["fix-1"])))) == []
    finally:
        restore()


def test_e745_is_one_finding_per_criterion_and_refined_obligation() -> None:
    nodes = _base(row("fr-b", "fr"), row("fix-1", "fixture", verifies=["ac-a-1"]), _criterion(["fr-a", "fr-b"], ["fix-1"]))
    assert _e745(spec(*nodes)) == [("tc-1", link_target("refines", "fr-b"))]
    uncovered = _base(row("fr-b", "fr"), _criterion(["fr-a", "fr-b"], []))
    assert _e745(spec(*uncovered)) == [("tc-1", link_target("refines", "fr-a")), ("tc-1", link_target("refines", "fr-b"))]


def test_finding_names_the_criterion_and_is_owned_by_step_14() -> None:
    (error,) = check_refinement(spec(*_base(_criterion(["fr-a"], []))), "merge")
    assert (error.code, error.node_id, error.owner) == ("E745", "tc-1", "step:14")
    assert "tc-1" in error.message and "fr-a" in error.message


def test_covering_verifiers_lists_the_verifiers_that_cover_in_link_order() -> None:
    nodes = _base(
        row("fix-1", "fixture", verifies=["fr-b"]), row("fix-2", "fixture", verifies=["fr-a"]),
        row("fix-3", "fixture", verifies=["ac-a-1"]), _criterion(["fr-a"], ["fix-1", "fix-2", "fix-3"]),
    )
    context = spec(*nodes)
    found = covering_verifiers(context, context.graph.by_id["tc-1"], context.graph.by_id["fr-a"])
    assert [verifier.id for verifier in found] == ["fix-2", "fix-3"]


def test_refinement_does_not_read_a_not_applicable_node() -> None:
    inapplicable_criterion = _criterion(["fr-a"], [], lifecycle="not_applicable")
    assert _e745(spec(*_base(inapplicable_criterion))) == []
    inapplicable_verifier = row("fix-1", "fixture", verifies=["fr-a"], lifecycle="not_applicable")
    assert _e745(spec(*_base(inapplicable_verifier, _criterion(["fr-a"], ["fix-1"])))) == [("tc-1", link_target("refines", "fr-a"))]


def _scenario(reverse: bool) -> list[SpecError]:
    nodes = [
        *_base(row("fr-b", "fr")), row("tc-2", "task-criterion", parent="task-1", refines=["fr-b", "fr-a"], verified_by=[]),
        _criterion(["fr-b", "fr-a"], []),
    ]
    return check_refinement(spec(*reversed(nodes) if reverse else nodes), "merge")


_ORDER_CODE = """
import json
from unit.validation.graph_checks.test_refinement import _scenario
print(json.dumps([[error.node_id, error.target] for error in _scenario(True)]))
"""


@pytest.mark.parametrize("seed", HASH_SEEDS)
def test_refinement_reports_in_the_same_order_whatever_the_hash_seed(seed: int) -> None:
    expected = [[error.node_id, error.target] for error in _scenario(False)]
    assert len(expected) == 4
    assert json.loads(run_python_seeded(seed, _ORDER_CODE)) == expected
