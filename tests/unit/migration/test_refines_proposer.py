"""The ``refines`` proposer (WI-M10-09): scoring, classes, the candidate set and what it writes.

The tests run on ``tests/fixtures/migration/refines_gold`` (invented: see its README for the two halves) or on a copy of
it that a test edits.  The 0.95 gate is a fixture gate (ruling P5): the command prints no precision.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

from specdev_tools.graph.names import CRITERION, REFINES, TASK_CRITERION
from specdev_tools.migration import proposers
from specdev_tools.migration.proposers import ProposeResult, refines
from specdev_tools.migration.worklist import WORKLIST_FILE

from ._proposer_support import copy_gold, edit, labels, task_criterion, tree_of
from .test_runner_core import REAL_ROOT, tree_digest

SCORED, TUNE = "scored", "tune"
MIN_SCORED_PROPOSALS = 20
GATE = 0.95
INVARIANT_TEXT = "A member never holds more than six seed packets on loan at the same time."


@pytest.fixture
def host(tmp_path) -> Path:
    return copy_gold(tmp_path)


def run(host: Path) -> ProposeResult:
    return refines.propose(tree_of(host))


def by_about(result: ProposeResult) -> dict:
    return {proposal.data["about"]: proposal for proposal in result.proposals}


def auto_of_half(result: ProposeResult, gold: dict, half: str) -> list:
    return [p for p in result.proposals if p.category == refines.CLASS_AUTO and gold[p.data["about"]]["half"] == half]


def test_precision_at_0_6_on_04_targets_is_at_least_0_95_on_the_fixture(host):
    gold = labels(host)
    result = run(host)
    assert refines.MIN_SCORE == 0.6
    assert all(p.data["score"] >= refines.MIN_SCORE for p in result.proposals if p.category == refines.CLASS_AUTO)
    for half in (TUNE, SCORED):
        auto = auto_of_half(result, gold, half)
        right = [p for p in auto if p.data["target"] == gold[p.data["about"]]["refines"]]
        assert len(auto) >= MIN_SCORED_PROPOSALS or half == TUNE, f"{half}: only {len(auto)} auto-eligible proposals: an abstaining proposer passes a precision gate"
        assert len(right) / len(auto) >= GATE, f"{half}: {len(right)} of {len(auto)} right"


def test_proposals_never_use_shared_ids(host):
    """A criterion that carries the id of an acceptance criterion is judged by its text; an id defined twice is never proposed."""
    edit(host, "14_roadmap.json", lambda d: task_criterion(d, "tc-borrow-packet-4").update(criterion_id="ac-borrow-packet-1"))
    edit(host, "14_roadmap.json", lambda d: task_criterion(d, "tc-borrow-packet-3").update(text="ac-borrow-packet-3"))
    tree = tree_of(host)
    assert "ac-borrow-packet-1" in tree.graph.dups
    result = refines.propose(tree)
    proposals = by_about(result)
    assert "ac-borrow-packet-1" not in {p.data["target"] for p in result.proposals}
    assert proposals["ac-borrow-packet-1"].category != refines.CLASS_AUTO
    assert proposals["tc-borrow-packet-3"].category == refines.CLASS_NONE, "an id written in the text is not a word to score"
    assert proposals["tc-borrow-packet-1"].category != refines.CLASS_AUTO, "its gold target is the shared id: no proposal may name it"


def test_non_04_proposals_are_never_auto_eligible(host):
    edit(host, "14_roadmap.json", lambda d: task_criterion(d, "tc-borrow-packet-1").update(text=INVARIANT_TEXT))
    result = run(host)
    other = [p for p in result.proposals if p.data["target_kind"] not in (None, CRITERION)]
    assert other and all(p.category == refines.CLASS_JUDGEMENT for p in other)
    exact = by_about(result)["tc-borrow-packet-1"]
    assert exact.data["target"] == "inv-six-packet-limit" and exact.data["score"] > 0.9
    assert exact.category == refines.CLASS_JUDGEMENT


def _schema_kinds() -> tuple[str, ...]:
    schema = json.loads((REAL_ROOT / "schema" / "14_roadmap.schema.json").read_text(encoding="utf-8"))
    criterion = schema["allOf"][1]["properties"]["milestones"]["items"]["properties"]["tasks"]["items"]["properties"]["acceptance_criteria"]["items"]
    return tuple(criterion["properties"]["refines"]["x-link"]["kinds"])


def test_candidate_kinds_are_read_from_the_refines_x_link_of_schema_14(host):
    tree = tree_of(host)
    assert refines.candidate_kinds(tree.graph) == _schema_kinds()
    decl = tree.graph.decls[TASK_CRITERION]
    narrowed = tuple(dataclasses.replace(link, kinds=("fr",)) if link.field == REFINES else link for link in decl.links)
    tree.graph.decls[TASK_CRITERION] = dataclasses.replace(decl, links=narrowed)
    result = refines.propose(tree)
    assert {p.data["target_kind"] for p in result.proposals} == {None, "fr"}


def test_a_task_with_no_fr_refs_in_the_capture_is_class_none(host):
    proposals = by_about(run(host))
    for criterion_id in ("tc-board-deck-1", "tc-site-hosting-1"):  # one task has `legacy_fr_refs: []`, the other no such key
        assert proposals[criterion_id].category == refines.CLASS_NONE
        assert proposals[criterion_id].data["target"] is None
        assert "names no FR and no invariant" in proposals[criterion_id].item.evidence


def test_several_nodes_stating_one_rule_propose_the_most_downstream_and_list_the_alternative(host):
    rule = next(a for a in _json(host, "04_fr_list.json")["functional_requirements"] if a["fr_id"] == "fr-borrow-packet")["acceptance_criteria"][1]["text"]

    def state_the_rule_again(data):
        error = data["apis"][0]["errors"][0]
        error.pop("code")
        error["message"] = rule

    edit(host, "05_interface_contracts.json", state_the_rule_again)
    edit(host, "14_roadmap.json", lambda d: task_criterion(d, "tc-borrow-packet-2").update(text=rule))
    proposal = by_about(run(host))["tc-borrow-packet-2"]
    assert proposal.data["target"] == "err-borrow-limit-reached", "05 is downstream of 04"
    assert [a["id"] for a in proposal.data["alternatives"]][0] == "ac-borrow-packet-2"
    assert proposal.category == refines.CLASS_JUDGEMENT, "the best candidate is not unique"
    assert "ac-borrow-packet-2" in proposal.item.proposal


def test_the_proposer_writes_only_worklist_json(host):
    before = tree_digest(host)
    outcome = proposers.propose(host / "spec", kind=proposers.KIND_REFINES, toolkit_root=REAL_ROOT, git_root=host, dry_run=False)
    after = tree_digest(host)
    assert {rel for rel in after if before.get(rel) != after[rel]} == {f"spec/{WORKLIST_FILE}"}
    assert outcome.added == len(outcome.result.proposals) > 0
    again = proposers.propose(host / "spec", kind=proposers.KIND_REFINES, toolkit_root=REAL_ROOT, git_root=host, dry_run=False)
    assert again.added == 0 and tree_digest(host) == after


def test_a_dry_run_adds_nothing(host):
    before = tree_digest(host)
    outcome = proposers.propose(host / "spec", kind=proposers.KIND_REFINES, toolkit_root=REAL_ROOT, git_root=host, dry_run=True)
    assert outcome.added == 0 and outcome.result.proposals and tree_digest(host) == before


def test_a_criterion_that_already_refines_or_removes_gets_no_proposal(host):
    edit(host, "14_roadmap.json", lambda d: task_criterion(d, "tc-borrow-packet-1").update(refines=["ac-borrow-packet-1"]))
    edit(host, "14_roadmap.json", lambda d: task_criterion(d, "tc-borrow-packet-2").update(removes=["ac-borrow-packet-2"]))
    proposals = by_about(run(host))
    assert "tc-borrow-packet-1" not in proposals and "tc-borrow-packet-2" not in proposals
    assert "tc-borrow-packet-3" in proposals


def test_an_id_the_migration_renamed_is_mapped_through_the_capture(host):
    """A legacy `fr_refs` entry that no node has any more reaches the node it was renamed to (ruling P20)."""
    edit(host, "extras/migration/capture.json", lambda d: d.update(renames=[{"old": "fr-borrow-packet-old", "new": "fr-borrow-packet", "kind": "fr", "file": "04_fr_list.json"}]))
    edit(host, "extras/migration/capture.json", lambda d: next(r for r in d["task_status"] if r["task"] == "task-borrow-packet").update(legacy_fr_refs=["fr-borrow-packet-old"]))
    proposal = by_about(run(host))["tc-borrow-packet-1"]
    assert proposal.data["target"] == "ac-borrow-packet-1" and proposal.category == refines.CLASS_AUTO


def test_an_id_no_node_has_is_named_in_the_evidence(host):
    edit(host, "extras/migration/capture.json", lambda d: next(r for r in d["task_status"] if r["task"] == "task-borrow-packet").update(legacy_fr_refs=["fr-borrow-packet", "fr-gone"]))
    assert "no node has fr-gone" in by_about(run(host))["tc-borrow-packet-1"].item.evidence


def test_the_counts_add_up_and_every_item_is_stable(host):
    result = run(host)
    assert result.counts["task criteria"] == len(result.proposals) == sum(result.counts[klass] for klass in refines.CLASSES)
    ids = [p.item.id for p in result.proposals]
    assert len(set(ids)) == len(ids) and all(i.startswith("wl-14-refines-") for i in ids)
    assert ids == [p.item.id for p in run(host).proposals]


def _json(host: Path, rel: str):
    return json.loads((host / "spec" / rel).read_text(encoding="utf-8"))
