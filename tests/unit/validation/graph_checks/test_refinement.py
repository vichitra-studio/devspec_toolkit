"""The refinement check (E745): the verifier of a task criterion verifies the obligation it refines (WI-M6b-05)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.core.errors import link_target
from specdev_tools.validation.graph_checks import run_graph_checks
from specdev_tools.validation.graph_checks.context import GraphCheckContext
from specdev_tools.validation.graph_checks.refinement import check_refinement, covering_verifiers
from unit.graph._synth import EXAMPLE_SPEC, HASH_SEEDS

from ._order_support import seeded
from ._bindings_support import Bindings
from ._example_support import context_of_spec, edited_example
from ._built_support import closed_milestone, node, spec


def _e745(ctx: GraphCheckContext) -> list[tuple[str | None, str | None]]:
    return [(error.node_id, error.target) for error in check_refinement(ctx, "merge")]


def _criterion(refines: list[str], verified_by: list[str], **fields: object):
    return node("tc-1", "task-criterion", parent="task-1", refines=refines, verified_by=verified_by, **fields)


def _base(*nodes):
    return [node("fr-a", "fr"), node("ac-a-1", "criterion", parent="fr-a"), node("task-1", "task"), *nodes]


def test_doc_example_tc1_fx1_and_tc2_fx2_pass() -> None:
    context = context_of_spec(EXAMPLE_SPEC)
    assert check_refinement(context, "merge") == []


def test_closed_milestone_criterion_with_a_deleted_fixture_gives_no_e745() -> None:
    nodes = [
        *closed_milestone("ms-1"), node("fr-a", "fr"), node("task-1", "task", parent="ms-1"),
        _criterion(["fr-a"], ["fix-deleted"]),
    ]
    assert _e745(spec(*nodes)) == []
    open_nodes = [node for node in nodes if node.kind not in ("anchor-row",)]
    assert _e745(spec(*open_nodes)) == [("tc-1", link_target("refines", "fr-a"))]


def test_removal_criterion_gives_no_e745() -> None:
    removal = node("tc-remove", "task-criterion", parent="task-1", removes=["fr-a"], verified_by=["fix-gone"])
    fixture = node("fix-gone", "fixture", removes=["fr-a"])
    assert _e745(spec(*_base(removal, fixture))) == []


def test_criterion_whose_fixture_verifies_something_else_gives_e745() -> None:
    nodes = _base(node("fr-b", "fr"), node("fix-1", "fixture", verifies=["fr-b"]), _criterion(["fr-a"], ["fix-1"]))
    assert _e745(spec(*nodes)) == [("tc-1", link_target("refines", "fr-a"))]


def test_fixture_verifying_a_descendant_covers_the_ancestor() -> None:
    nodes = _base(node("fix-1", "fixture", verifies=["ac-a-1"]), _criterion(["fr-a"], ["fix-1"]))
    assert _e745(spec(*nodes)) == []


def test_fixture_verifying_an_ancestor_covers_the_descendant() -> None:
    nodes = _base(node("fix-1", "fixture", verifies=["fr-a"]), _criterion(["ac-a-1"], ["fix-1"]))
    assert _e745(spec(*nodes)) == []


def test_job_realising_the_obligation_covers_it() -> None:
    nodes = _base(node("gate-1", "gate"), node("job-1", "job", realises=["gate-1"]), _criterion(["gate-1"], ["job-1"]))
    assert _e745(spec(*nodes)) == []


def test_rule_named_in_verified_by_covers_itself() -> None:
    nodes = _base(node("rule-1", "rule"), node("rule-2", "rule"), _criterion(["rule-1"], ["rule-1"]))
    assert _e745(spec(*nodes)) == []
    other = _base(node("rule-1", "rule"), node("rule-2", "rule"), _criterion(["rule-1"], ["rule-2"]))
    assert _e745(spec(*other)) == [("tc-1", link_target("refines", "rule-1"))]


def test_extra_verifiers_seam_stub_covers_an_obligation(bindings: Bindings) -> None:
    context = spec(*_base(node("fix-1", "fixture"), _criterion(["fr-a"], ["fix-1"])))
    assert _e745(context) != []
    bindings.seams(extra_verifiers=lambda verifier: {"fr-a"})
    assert _e745(spec(*_base(node("fix-1", "fixture"), _criterion(["fr-a"], ["fix-1"])))) == []


def test_e745_is_one_finding_per_criterion_and_refined_obligation() -> None:
    nodes = _base(node("fr-b", "fr"), node("fix-1", "fixture", verifies=["ac-a-1"]), _criterion(["fr-a", "fr-b"], ["fix-1"]))
    assert _e745(spec(*nodes)) == [("tc-1", link_target("refines", "fr-b"))]
    uncovered = _base(node("fr-b", "fr"), _criterion(["fr-a", "fr-b"], []))
    assert _e745(spec(*uncovered)) == [("tc-1", link_target("refines", "fr-a")), ("tc-1", link_target("refines", "fr-b"))]


def test_finding_names_the_criterion_and_is_owned_by_step_14() -> None:
    (error,) = check_refinement(spec(*_base(_criterion(["fr-a"], []))), "merge")
    assert (error.code, error.node_id, error.owner) == ("E745", "tc-1", "step:14")
    assert "tc-1" in error.message and "fr-a" in error.message


def test_covering_verifiers_lists_the_verifiers_that_cover_in_link_order() -> None:
    nodes = _base(
        node("fix-1", "fixture", verifies=["fr-b"]), node("fix-2", "fixture", verifies=["fr-a"]),
        node("fix-3", "fixture", verifies=["ac-a-1"]), _criterion(["fr-a"], ["fix-1", "fix-2", "fix-3"]),
    )
    context = spec(*nodes)
    found = covering_verifiers(context, context.graph.by_id["tc-1"], context.graph.by_id["fr-a"])
    assert [verifier.id for verifier in found] == ["fix-2", "fix-3"]


def test_refinement_does_not_read_a_not_applicable_node() -> None:
    inapplicable_criterion = _criterion(["fr-a"], [], lifecycle="not_applicable")
    assert _e745(spec(*_base(inapplicable_criterion))) == []
    inapplicable_verifier = node("fix-1", "fixture", verifies=["fr-a"], lifecycle="not_applicable")
    assert _e745(spec(*_base(inapplicable_verifier, _criterion(["fr-a"], ["fix-1"])))) == [("tc-1", link_target("refines", "fr-a"))]


def _scenario(reverse: bool) -> list[list[str | None]]:
    nodes = [
        *_base(node("fr-b", "fr")), node("tc-2", "task-criterion", parent="task-1", refines=["fr-b", "fr-a"], verified_by=[]),
        _criterion(["fr-b", "fr-a"], []),
    ]
    return [[error.node_id, error.target] for error in check_refinement(spec(*reversed(nodes) if reverse else nodes), "merge")]


@pytest.mark.parametrize("seed", HASH_SEEDS)
def test_refinement_reports_in_the_same_order_whatever_the_hash_seed(seed: int) -> None:
    expected = _scenario(False)
    assert len(expected) == 4
    assert seeded(seed, __name__, "_scenario", True) == expected


def test_fixture_that_mitigates_a_refined_threat_covers_it() -> None:
    nodes = _base(node("threat-1", "threat", mitigated_by=["fix-1"]), node("fix-1", "fixture"), _criterion(["threat-1"], ["fix-1"]))
    assert _e745(spec(*nodes)) == []


def test_fixture_that_mitigates_nothing_of_the_threat_gives_e745() -> None:
    nodes = _base(node("threat-1", "threat", mitigated_by=["fix-1"]), node("fix-1", "fixture"), node("fix-2", "fixture"), _criterion(["threat-1"], ["fix-2"]))
    assert _e745(spec(*nodes)) == [("tc-1", link_target("refines", "threat-1"))]


def test_verifier_of_a_mitigating_obligation_covers_the_edge_case() -> None:
    nodes = _base(node("ec-1", "edge-case", mitigated_by=["ac-a-1"]), node("fix-1", "fixture", verifies=["ac-a-1"]), _criterion(["ec-1"], ["fix-1"]))
    assert _e745(spec(*nodes)) == []


def test_a_criterion_that_refines_a_threat_and_lists_its_fixtures_clears_both_e740_and_e745(tmp_path: Path) -> None:
    """The run of review B-1 on the worked example: the threat and the edge case are used by a criterion that refines them, and its verifier is a fixture they name in ``mitigated_by``."""

    def refine(doc: dict[str, Any]) -> None:
        task = doc["milestones"][0]["tasks"][0]
        task["acceptance_criteria"].append({
            "criterion_id": "tc-x",
            "text": "A replayed or expired reset link never sets a password, whatever the second it is redeemed in.",
            "refines": ["threat-reset-token-replay", "ec-token-at-expiry-second"],
            "verified_by": ["fix-password-reset-expired-token"],
        })

    def findings(spec: Path) -> list[tuple[str, str | None]]:
        context = context_of_spec(spec)
        return [(error.code, error.node_id) for error in run_graph_checks(context, "merge", only={"E740", "E745"})]

    before = findings(edited_example(tmp_path / "before"))
    spec = edited_example(tmp_path / "after", **{"14_roadmap.json": refine})
    after = findings(spec)
    assert ("E740", "threat-reset-token-replay") in before and ("E740", "ec-token-at-expiry-second") in before
    assert [found for found in after if found[1] in ("threat-reset-token-replay", "ec-token-at-expiry-second", "tc-x")] == []
    assert not [found for found in after if found[0] == "E745"]


def test_a_threat_whose_mitigated_by_names_no_node_is_covered_by_nothing_and_does_not_fail() -> None:
    nodes = _base(node("threat-1", "threat", mitigated_by=["no-such-id"]), node("fix-1", "fixture", verifies=["ac-a-1"]), _criterion(["threat-1"], ["fix-1"]))
    assert _e745(spec(*nodes)) == [("tc-1", link_target("refines", "threat-1"))]
