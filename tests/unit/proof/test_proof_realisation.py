"""Realisation status of the links of closed milestones (the four states of Figure 20), the unresolved list, and the closed criterion's frozen links."""
from __future__ import annotations

from pathlib import Path

from specdev_tools.graph.build import build_graph
from specdev_tools.graph.check import run_graph_check
from specdev_tools.graph.resolve import resolve_graph
from specdev_tools.proof.realisation import CURRENT, OUTDATED, REMOVED, SUPERSEDED
from specdev_tools.trace.lockfile import read_lock
from specdev_tools.validation.graph_checks import run_graph_checks
from specdev_tools.validation.graph_checks.context import GraphCheckContext
from specdev_tools.validation.spec_check import run_spec_check_json
from unit.graph._synth import ROOT
from unit.verify._support import edit_doc

from ._closed import (
    API, CRITERION, FR, MILESTONE, TASK_CRITERION, accept, add_milestone, closed_example, criterion, delete_criterion, delete_fr, reword_criterion,
    rows, statuses, unresolved, with_removal,
)

KEY = (TASK_CRITERION, CRITERION)
NEW_TEXT = "A reset link older than 31 minutes is refused with HTTP 410 and the password stays as it was."


def _change_milestone(host: Path, *, done: bool) -> None:
    add_milestone(host, "ms-token-ttl", [criterion("tc-ttl-31", refines=[CRITERION])], done=done)


def test_current_to_outdated_to_superseded(tmp_path: Path) -> None:
    host = closed_example(tmp_path)
    assert statuses(host)[KEY] == CURRENT
    reword_criterion(host, CRITERION, NEW_TEXT)
    assert statuses(host)[KEY] == OUTDATED
    _change_milestone(host, done=False)
    assert statuses(host)[KEY] == OUTDATED
    edit_doc(host, "16_impl_context.json", lambda doc: doc["plan"]["milestone_index"][-1].update(status="done"))
    assert statuses(host)[KEY] == SUPERSEDED
    assert statuses(host)[("tc-ttl-31", CRITERION)] == CURRENT
    [superseded] = [row for row in rows(host) if row.criterion == TASK_CRITERION and row.target == CRITERION]
    assert superseded.superseded_by == "ms-token-ttl"


def test_current_to_removed(tmp_path: Path) -> None:
    host = closed_example(tmp_path)
    delete_criterion(host, CRITERION)
    [row] = [row for row in rows(host) if row.target == CRITERION]
    assert (row.state, row.current_hash, row.containers) == (REMOVED, None, (FR,))


def test_outdated_to_removed(tmp_path: Path) -> None:
    host = closed_example(tmp_path)
    reword_criterion(host, CRITERION, NEW_TEXT)
    assert statuses(host)[KEY] == OUTDATED
    delete_criterion(host, CRITERION)
    assert statuses(host)[KEY] == REMOVED


def test_superseded_to_removed(tmp_path: Path) -> None:
    host = closed_example(tmp_path)
    reword_criterion(host, CRITERION, NEW_TEXT)
    _change_milestone(host, done=True)
    assert statuses(host)[KEY] == SUPERSEDED
    delete_criterion(host, CRITERION)
    assert (statuses(host)[KEY], statuses(host)[("tc-ttl-31", CRITERION)]) == (REMOVED, REMOVED)


def test_removed_stays_removed(tmp_path: Path) -> None:
    host = closed_example(tmp_path)
    delete_criterion(host, CRITERION)
    _change_milestone(host, done=True)
    assert statuses(host)[KEY] == REMOVED
    assert REMOVED not in (OUTDATED, SUPERSEDED)


def test_multi_target_criterion_with_one_target_deleted(tmp_path: Path) -> None:
    host = closed_example(tmp_path)
    edit_doc(host, "14_roadmap.json", lambda doc: doc["milestones"][0]["tasks"][0]["acceptance_criteria"][0].update(refines=[CRITERION, API]))
    accept(host, TASK_CRITERION)
    delete_criterion(host, CRITERION)
    assert (statuses(host)[(TASK_CRITERION, CRITERION)], statuses(host)[(TASK_CRITERION, API)]) == (REMOVED, CURRENT)


def test_alias_rename_keeps_current(tmp_path: Path) -> None:
    host = closed_example(tmp_path)

    def rename(doc: dict) -> None:
        for fr in doc["functional_requirements"]:
            for found in fr["acceptance_criteria"]:
                if found["criterion_id"] == CRITERION:
                    found.update(criterion_id="ac-password-reset-3b", aliases=[CRITERION])

    edit_doc(host, "04_fr_list.json", rename)
    assert statuses(host)[KEY] == CURRENT


def test_id_reuse_with_new_meaning_is_outdated(tmp_path: Path) -> None:
    host = closed_example(tmp_path)

    def reuse(doc: dict) -> None:
        for fr in doc["functional_requirements"]:
            for found in fr["acceptance_criteria"]:
                if found["criterion_id"] == CRITERION:
                    found["text"] = "A reset email arrives within sixty seconds of the request."

    edit_doc(host, "04_fr_list.json", reuse)
    assert statuses(host)[KEY] == OUTDATED


def test_unresolved_realisations_on_the_doc_13_4_fixture_and_empty_once_closed(tmp_path: Path) -> None:
    host = closed_example(tmp_path)
    assert unresolved(host) == []
    reword_criterion(host, CRITERION, NEW_TEXT)
    [outdated] = unresolved(host)
    assert (outdated.code, outdated.kind, outdated.milestone, outdated.target, outdated.existing_milestone) == ("E343", OUTDATED, MILESTONE, CRITERION, None)
    _change_milestone(host, done=False)
    assert [(entry.kind, entry.existing_milestone) for entry in unresolved(host)] == [(OUTDATED, "ms-token-ttl")]
    edit_doc(host, "16_impl_context.json", lambda doc: doc["plan"]["milestone_index"][-1].update(status="done"))
    assert unresolved(host) == []
    delete_fr(host, FR)
    [removed] = [entry for entry in unresolved(host) if entry.milestone == MILESTONE]
    assert {entry.milestone for entry in unresolved(host)} == {MILESTONE, "ms-token-ttl"}
    assert (removed.code, removed.kind, removed.current_hash, removed.existing_milestone) == ("E344", REMOVED, None, None)
    with_removal(host, removes=[FR])
    assert unresolved(host) == []


def test_removal_of_the_fr_is_matched_through_target_containers(tmp_path: Path) -> None:
    host = closed_example(tmp_path)
    delete_fr(host, FR)
    with_removal(host, removes=[FR], done=False)
    [entry] = unresolved(host)
    assert (entry.kind, entry.existing_milestone) == (REMOVED, "ms-retire-reset")
    edit_doc(host, "16_impl_context.json", lambda doc: doc["plan"]["milestone_index"][-1].update(status="done"))
    assert unresolved(host) == []
    assert read_lock(str(host / "spec")).get(TASK_CRITERION, "refines", CRITERION).target_containers == (FR,)


def test_unmatched_removes_stays_removed(tmp_path: Path) -> None:
    host = closed_example(tmp_path)
    delete_fr(host, FR)
    with_removal(host, removes=["fr-something-else"])
    assert [(entry.kind, entry.target) for entry in unresolved(host)] == [(REMOVED, CRITERION)]


def test_no_e343_or_e344_is_raised_by_spec_check(tmp_path: Path) -> None:
    host = closed_example(tmp_path)
    reword_criterion(host, CRITERION, NEW_TEXT)
    delete_criterion(host, "ac-password-reset-1")
    assert unresolved(host)
    spec = str(host / "spec")
    errors, _context = run_spec_check_json(str(ROOT), spec, git_root=str(host), spec_root=spec, project_canon_dir=f"{spec}/canon")
    assert not {error.code for error in errors} & {"E343", "E344"}


def test_deleting_a_closed_removal_fixture_and_a_closed_verified_by_target_reports_zero_errors(tmp_path: Path) -> None:
    host = closed_example(tmp_path)
    delete_fr(host, FR)
    with_removal(host, removes=[FR])
    edit_doc(host, "08_fixtures.json", lambda doc: doc["fixtures"].__setitem__(slice(None), [f for f in doc["fixtures"] if f["fixture_id"] not in ("fix-reset-gone", "fix-password-reset-reused-token")]))
    frozen = {TASK_CRITERION, "tc-confirm-reused-token", "tc-retire-reset"}
    graph = build_graph(str(host / "spec"), str(ROOT))
    lock = read_lock(str(host / "spec"))
    findings = [*run_graph_check(str(host / "spec"), str(ROOT), graph=graph, lock=lock), *run_graph_checks(GraphCheckContext.from_graph(graph, lock), "merge")]
    assert [(error.code, error.node_id) for error in findings if error.node_id in frozen] == []
    assert {error.node_id for error in resolve_graph(graph) if error.code == "E700"} >= {TASK_CRITERION, "tc-confirm-reused-token", "tc-retire-reset"}
