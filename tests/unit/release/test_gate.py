"""The release gate (WI-M9-03): what blocks a release, what is only listed, and that each fact keeps the code of the milestone that defined it.

The worked example is not release-ready, so ``release_host`` (``_support``) parks every obligation and a test brings one condition
back at a time.  The gate runs on the checkout and never walks history.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import patch

from specdev_tools.core.errors import ERROR_CODES
from specdev_tools.proof.proof import proof_errors
from specdev_tools.release.gate import RelievedNode
from specdev_tools.trace.lockfile import read_lock, write_lock
from specdev_tools.validation.graph_checks.context import GraphCheckContext
from specdev_tools.validation.graph_checks.scaffold import scaffold_scan
from unit.graph._synth import ROOT, git
from unit.lifecycle._record_support import closed_row
from unit.proof._closed import add_milestone, closed_example, criterion, reword_criterion
from unit.proof._support import attest, ci_host, context, edit_code
from unit.release._support import SCAFFOLD, advance, codes, commit, declare, gate, latency_host, nodes_of, release_host, set_scope, stamp, tag
from unit.trace._lock_support import lock_for
from unit.verify._support import edit_doc, graph_of

MS = "ms-account-recovery"
NFR, THREAT = "nfr-latency-reset-email", "threat-reset-token-replay"
RULE = "rule-security-review-of-token-handling"
INVARIANT = "inv-reset-token-single-use"
FR = "fr-password-reset-request"
CRITERION = "ac-password-reset-3"
DESIGN = "milestone-account-recovery"
NEW_TEXT = "A reset link older than 31 minutes is refused with HTTP 410 and the password stays as it was."


def _relock(host: Path) -> None:
    write_lock(str(host / "spec"), lock_for(graph_of(host), host))


def test_gate_passes_on_clean_fixture(tmp_path: Path) -> None:
    result = gate(release_host(tmp_path))
    assert result.passed and result.errors == () and result.relieved == ()
    assert "W937" in [warning.code for warning in result.warnings]
    assert result.listed and {item.code for item in result.listed} == {"W933"} and not result.notes


# --- every closed milestone is signed off (E913) ----------------------------------------------------------------------------


def test_unsigned_closed_milestone_blocks(tmp_path: Path) -> None:
    host = release_host(tmp_path)
    edit_doc(host, "16_impl_context.json", lambda doc: doc["plan"]["milestone_index"][0].update(status="done"))
    blocked = gate(host)
    [unsigned] = [error for error in blocked.errors if error.code == "E913"]
    assert unsigned.node_id == MS and unsigned.owner == "close-gate" and "not closed with a close record" in unsigned.message
    closed_row(host)  # a close record that names its sign-off
    assert "E913" not in codes(gate(host))


# --- every in-scope obligation is built (E914), relieved nodes count as built ------------------------------------------------


def test_unbuilt_in_scope_obligation_blocks(tmp_path: Path) -> None:
    blocked = gate(release_host(tmp_path, INVARIANT))
    assert not blocked.passed and nodes_of(blocked, "E914") == {INVARIANT}
    [error] = [error for error in blocked.errors if error.code == "E914"]
    assert "is an obligation of this release and is not built" in error.message and error.file == "06_invariants.json"
    assert gate(release_host(tmp_path, name="parked")).passed  # parked (scope later), the same host passes


def test_relieved_node_satisfies_ancestor_and_is_listed_in_result(tmp_path: Path) -> None:
    result = gate(latency_host(tmp_path, run_it=False))
    assert result.relieved == (RelievedNode(NFR, "staging"),)  # it is built but for the proof that waits for staging
    for code in ("E914", "E347", "E348"):
        assert NFR not in nodes_of(result, code)


# --- dev and CI proof for this tree (E347 / E348) -----------------------------------------------------------------------------


def _proof_findings(result: Any, binding: str) -> list[str]:
    return [error.message for error in result.errors if error.code == "E347" and f"binding {binding} " in error.message]


def test_missing_ci_evidence_for_this_tree_blocks(tmp_path: Path) -> None:
    (tmp_path / "unrun").mkdir()
    (tmp_path / "run").mkdir()
    missing = _proof_findings(gate(ci_host(tmp_path / "unrun", ran=False)), "ver-alpha")
    assert missing and all("NO_EVIDENCE" in message for message in missing)
    assert _proof_findings(gate(ci_host(tmp_path / "run", ran=True)), "ver-alpha") == []


def test_evidence_for_other_tree_blocks(tmp_path: Path) -> None:
    host = ci_host(tmp_path, ran=True)
    edit_code(host)
    commit(host, "the code moved after the run")
    stale = _proof_findings(gate(host), "ver-alpha")
    assert stale and all("STALE_TREE" in message for message in stale)


# --- realisations (E343 / E344) -------------------------------------------------------------------------------------------------


def test_outdated_realisation_with_open_change_milestone_blocks(tmp_path: Path) -> None:
    host = closed_example(tmp_path)
    assert "E343" not in codes(gate(host))
    reword_criterion(host, CRITERION, NEW_TEXT)
    [outdated] = [error for error in gate(host).errors if error.code == "E343"]
    assert outdated.node_id == CRITERION and outdated.owner == "release-gate" and "carry the change in a milestone and close it" in outdated.message
    add_milestone(host, "ms-token-ttl", [criterion("tc-ttl-31", refines=[CRITERION])], done=False)
    [open_change] = [error for error in gate(host).errors if error.code == "E343"]
    assert "close its change milestone ms-token-ttl" in open_change.message  # a milestone that carries the change but is open still blocks
    edit_doc(host, "16_impl_context.json", lambda doc: doc["plan"]["milestone_index"][-1].update(status="done"))
    assert "E343" not in codes(gate(host))


# --- rules enforced by review (E830) ---------------------------------------------------------------------------------------------


def test_unattested_review_rule_blocks(tmp_path: Path) -> None:
    host = release_host(tmp_path, RULE)
    [unattested] = [error for error in gate(host).errors if error.code == "E830"]
    assert unattested.node_id == RULE and unattested.owner == "release-gate" and "NO_ATTESTATION" in unattested.message
    attest(host, RULE)
    assert "E830" not in codes(gate(host))


# --- release-mode graph checks (E746, E928) --------------------------------------------------------------------------------------


def test_release_mode_graph_checks_scaffold_row_untracked_blocks(tmp_path: Path) -> None:
    host = release_host(tmp_path)
    git(host, "rm", "-q", SCAFFOLD)
    commit(host, "the scaffold file is gone")
    blocked = gate(host)
    assert nodes_of(blocked, "E746") == {"scaffold-password-reset-confirm"} and "(release mode)" in [e for e in blocked.errors if e.code == "E746"][0].message
    spec = str(host / "spec")
    graph_context = GraphCheckContext.from_graph(graph_of(host), read_lock(spec), str(ROOT), git_root=str(host), spec_root=spec)
    assert scaffold_scan(graph_context, None, "merge").findings == []  # the API is not built, so merge mode does not ask for its file
    git(host, "checkout", "-q", "HEAD~1", "--", SCAFFOLD)
    assert "E746" not in codes(gate(host))


def test_unrealised_09_milestone_blocks_E928(tmp_path: Path) -> None:
    host = release_host(tmp_path)
    schedules = graph_of(host).by_id[DESIGN]
    edit_doc(host, "09_impl_plan.json", lambda doc: doc["milestones"][0].update(schedules=[NFR]))
    _relock(host)
    [error] = [error for error in gate(host).errors if error.code == "E928"]
    assert error.node_id == DESIGN == schedules.id and error.owner == "release-gate" and "realised by no roadmap milestone" in error.message
    edit_doc(host, "09_impl_plan.json", lambda doc: doc["milestones"][0].update(schedules=["fr-password-reset", "risk-reset-link-takeover"]))
    _relock(host)
    assert "E928" not in codes(gate(host))


def test_release_gate_reuses_m7_m8_codes_no_parallel_codes(tmp_path: Path) -> None:
    """Each fact has the code of the milestone that defined it: the proof findings are ``proof_errors``' own, the realisation findings E343, the review rule E830, the scaffold E746."""
    host = ci_host(tmp_path, ran=False)
    result = gate(host)
    graph, scope = graph_of(host), [node.id for node in graph_of(host).nodes if node.role in ("obligation-system", "obligation-delivery") and node.scope in (None, "in")]
    direct = {(error.code, error.message) for error in proof_errors(graph, context(host), scope, "ci")}
    assert direct and direct <= {(error.code, error.message) for error in result.errors} and {code for code, _ in direct} == {"E347", "E348"}
    emitted = set(codes(result)) | set(codes(gate(closed_example(tmp_path, name="closed")))) | set(codes(gate(release_host(tmp_path, RULE, name="review"))))
    assert {"E347", "E348", "E830", "E914"} <= emitted
    assert not {"E918", "E919", "E922"} & set(ERROR_CODES)  # no parallel codes: unscheduled and unlinked work are spec-check's E566, E567, E740


# --- scope: listed, not blocking; unscheduled and unlinked work is spec-check's -------------------------------------------------------


def test_later_and_out_scope_listed_not_blocking(tmp_path: Path) -> None:
    host = release_host(tmp_path)
    set_scope(host, "rule-spec-check-on-every-pr", "out")
    result = gate(host)
    assert result.passed and {item.code for item in result.listed} == {"W933"}
    by_node = {item.node_id: item.message for item in result.listed}
    assert "scope out" in by_node["rule-spec-check-on-every-pr"] and "scope later" in by_node[NFR] and "listed, not blocking" in by_node[NFR]


def test_unscheduled_in_scope_obligation_blocks(tmp_path: Path) -> None:
    """N1: no E918.  An in-scope FR no task criterion reaches is E566 (and E740) in every mode, which the gate's static state carries."""
    blocked = gate(release_host(tmp_path, FR))
    assert not blocked.passed and nodes_of(blocked, "E566") == {FR} and FR in nodes_of(blocked, "E740")


def test_unlinked_legacy_work_blocks(tmp_path: Path) -> None:
    """N1: no E919.  A task criterion that refines or removes nothing is refused by the step-14 schema, which the gate's static state carries."""
    host = release_host(tmp_path)
    add_milestone(host, "ms-legacy", [criterion("tc-legacy-thing")], done=False)
    blocked = gate(host)
    refusal = [error for error in blocked.errors if error.code == "E520" and "ms-legacy" not in error.message and "acceptance_criteria" in error.message]
    assert not blocked.passed and refusal and "14_roadmap.json" in refusal[0].message


# --- retired stages, first release, no history walk -------------------------------------------------------------------------------------


def test_staging_scope_out_skips_staging_and_emits_W936(tmp_path: Path) -> None:
    host = release_host(tmp_path)
    assert "W936" not in [warning.code for warning in gate(host).warnings]
    set_scope(host, "staging", "out")
    result = gate(host)
    [skipped] = [warning for warning in result.warnings if warning.code == "W936"]
    assert result.passed and skipped.node_id == "staging" and "stage staging is skipped" in skipped.message


def test_first_release_emits_W937(tmp_path: Path) -> None:
    result = gate(release_host(tmp_path))
    [warning] = [warning for warning in result.warnings if warning.code == "W937"]
    assert result.previous is None and "first release" in warning.message and warning.owner == "release-gate"


def test_a_host_with_no_declared_pattern_is_refused_by_the_next_release_step(tmp_path: Path) -> None:
    host = release_host(tmp_path)
    (host / "spec" / "common" / "host_declarations.json").unlink()
    result = gate(host)
    assert "E911" in codes(result)


def test_gate_does_not_walk_history(tmp_path: Path) -> None:
    host = release_host(tmp_path)
    stamp(host, "1.2.0")
    declare(host)
    commit(host, "release one")
    tag(host, "v1.0.0")
    advance(host)
    advance(host, "two")
    seen: list[list[str]] = []
    real = subprocess.run

    def spy(command: list[str], *args: Any, **kwargs: Any) -> Any:
        if command[:1] == ["git"]:
            seen.append(command[3:])
        return real(command, *args, **kwargs)

    with patch("specdev_tools.graph.gitview.subprocess.run", spy):
        result = gate(host)
    verbs = [call[0] for call in seen if call]
    assert result.previous is not None and result.previous.tag == "v1.0.0"
    assert "log" not in verbs and verbs.count("tag") == 2  # the previous release, and the release before it (which tells what P closed)
    assert all("--count" in call for call in seen if call[:1] == ["rev-list"]) and "rev-list" in verbs  # rev-list only to place the previous tag
