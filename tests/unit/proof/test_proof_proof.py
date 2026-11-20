"""Proof of an obligation at a gate: the statuses, the routing per kind, the close mode and the findings of a gate."""
from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.proof.proof import (
    NO_VERIFIER, NOT_REQUIRED, PENDING_STAGE, PROVEN, UNBOUND, UNPROVEN, proof, proof_errors, verifier_proof,
)
from specdev_tools.proof.validity import NO_EVIDENCE, NONZERO_EXIT, STALE_TREE, node_evidence
from specdev_tools.verify.records import records_folder, write_binding
from unit.graph._synth import ROOT

from ._support import (
    API, CRITERION, FIXTURE, INVARIANT, NFR, OTHER_FIXTURE, REUSED_BINDING, add_fixture, attest, binding_item, context, edit_code, edit_doc, graph_of,
    host_with, prove, run,
)

ALPHA = "ver-alpha"
FAILING = "echo expected line; exit 3"
TASK_CRITERION = "tc-confirm-expired-token"
CLI_RULE = "rule-spec-check-on-every-pr"
THREAT = "threat-reset-token-replay"
SECOND = "fix-second-expired-token"


def _edit_binding(host: Path, binding_id: str, edit: Callable[[dict[str, Any]], None]) -> None:
    path = host / "spec" / "extras" / "verification" / f"{binding_id}.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    edit(document["records"][0])
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def _bound(tmp_path: Path, *extra: dict[str, Any], run_ids: tuple[str, ...] = (ALPHA,)) -> Path:
    host = host_with(tmp_path, binding_item(ALPHA), *extra)
    if run_ids:
        run(host, list(run_ids))
    return host


def test_an_unrun_binding_is_unproven_with_no_evidence_and_a_run_proves_it(tmp_path: Path) -> None:
    host = _bound(tmp_path, run_ids=())
    result = prove(host, CRITERION)
    assert (result.status, result.shortfalls[0].reason, result.shortfalls[0].binding) == (UNPROVEN, NO_EVIDENCE, ALPHA)
    run(host, [ALPHA])
    assert prove(host, CRITERION).status == prove(host, API).status == PROVEN


def test_a_verifier_with_no_binding_is_unbound_and_an_obligation_with_no_verifier_is_no_verifier(tmp_path: Path) -> None:
    host = _bound(tmp_path)
    assert (prove(host, INVARIANT).status, prove(host, INVARIANT).shortfalls[0].reason) == (UNBOUND, "UNBOUND")
    assert prove(host, NFR, "prod").status == NO_VERIFIER


def test_obligation_with_two_fixtures_one_failing_is_unproven(tmp_path: Path) -> None:
    host = host_with(tmp_path, binding_item(ALPHA), binding_item("ver-second", verifier=SECOND, proves=(CRITERION,), commands=(FAILING,)))
    add_fixture(host, fixture_id=SECOND, verifies=[CRITERION])
    run(host, [ALPHA, "ver-second"])
    result = prove(host, CRITERION)
    assert result.status == UNPROVEN
    assert [(s.verifier, s.reason) for s in result.shortfalls] == [(SECOND, NONZERO_EXIT)]


def test_nfr_prod_at_cap_ci_is_pending_stage(tmp_path: Path) -> None:
    host = host_with(tmp_path, binding_item("ver-latency", verifier="fix-latency", proves=(NFR,), stage="prod"))
    add_fixture(host, fixture_id="fix-latency", verifies=[NFR])
    edit_doc(host, "07_nfrs.json", lambda doc: doc["nfrs"][0].update(stage="prod"))
    assert prove(host, NFR, "ci").status == PENDING_STAGE
    assert prove(host, NFR, "prod").status == UNPROVEN


def test_task_criterion_without_verified_by_is_no_verifier_and_e348(tmp_path: Path) -> None:
    host = _bound(tmp_path)
    assert prove(host, TASK_CRITERION).status == PROVEN
    edit_doc(host, "14_roadmap.json", lambda doc: doc["milestones"][0]["tasks"][0]["acceptance_criteria"][0].pop("verified_by"))
    assert prove(host, TASK_CRITERION).status == NO_VERIFIER
    [error] = proof_errors(graph_of(host), context(host), [TASK_CRITERION], "dev")
    assert (error.code, error.subcode, error.node_id, error.owner) == ("E348", "NO_VERIFIER", TASK_CRITERION, "step:14")


def test_all_retired_verifier_is_skipped(tmp_path: Path) -> None:
    host = host_with(tmp_path, binding_item(ALPHA, stage="staging"))
    edit_doc(host, "02a_delivery_baseline.json", lambda doc: doc["environments"]["staging"].update(scope="out"))
    assert prove(host, CRITERION, "staging").status == NOT_REQUIRED
    add_fixture(host, fixture_id=SECOND, verifies=[CRITERION])
    write_binding(records_folder(str(host / "spec")), str(ROOT), binding_item("ver-second", verifier=SECOND, proves=(CRITERION,)))
    run(host, ["ver-second"])
    assert prove(host, CRITERION, "staging").status == PROVEN


def test_manual_fixture_with_valid_attestation_is_proven_and_unproven_without(tmp_path: Path) -> None:
    host = host_with(tmp_path)
    edit_doc(host, "08_fixtures.json", lambda doc: doc["fixtures"][0].update(mode="manual", manual_reason="A person reads the mail relay log."))
    result = prove(host, CRITERION)
    assert (result.status, result.shortfalls[0].reason) == (UNPROVEN, NO_EVIDENCE)
    attest(host, FIXTURE)
    assert prove(host, CRITERION).status == PROVEN
    edit_code(host)
    assert prove(host, CRITERION).shortfalls[0].reason == STALE_TREE
    edit_doc(host, "08_fixtures.json", lambda doc: doc["fixtures"][0].update(manual_reason="A person reads the relay log of the staging mailer."))
    assert prove(host, CRITERION).status == UNPROVEN


def _ci_host(tmp_path: Path, commands: tuple[str, ...] = ("echo expected line",)) -> Path:
    host = host_with(tmp_path, binding_item(ALPHA, stage="ci", commands=commands))
    return host


def test_ci_binding_is_proven_at_cap_ci_from_transient_evidence_without_a_file(tmp_path: Path) -> None:
    host = _ci_host(tmp_path)
    transient = run(host, [ALPHA], stage="ci", record=False)
    assert list((host / "spec" / "extras" / "verification").glob("evd-*")) == []
    assert prove(host, CRITERION, "ci").status == UNPROVEN
    assert prove(host, CRITERION, "ci", transient_evidence=transient).status == PROVEN


def test_failing_transient_run_is_unproven(tmp_path: Path) -> None:
    host = _ci_host(tmp_path, (FAILING,))
    transient = run(host, [ALPHA], stage="ci", record=False)
    result = prove(host, CRITERION, "ci", transient_evidence=transient)
    assert (result.status, result.shortfalls[0].reason) == (UNPROVEN, NONZERO_EXIT)


def test_close_mode_ci_binding_with_dev_evidence_is_proven(tmp_path: Path) -> None:
    host = _bound(tmp_path)
    _edit_binding(host, ALPHA, lambda record: record.update(stage="ci"))
    assert prove(host, CRITERION, "dev", treat_ci_as_dev=True).status == PROVEN
    assert prove(host, CRITERION, "ci").status == UNPROVEN


def test_close_mode_ignores_a_staging_binding(tmp_path: Path) -> None:
    host = _bound(tmp_path, binding_item("ver-late", verifier=SECOND, proves=(CRITERION,), stage="staging"))
    add_fixture(host, fixture_id=SECOND, verifies=[CRITERION])
    assert prove(host, CRITERION, "dev", treat_ci_as_dev=True).status == PROVEN
    assert prove(host, CRITERION, "dev").status == PENDING_STAGE
    only_late = host_with(tmp_path, binding_item("ver-late", verifier=SECOND, proves=(CRITERION,), stage="staging"), name="late")
    add_fixture(only_late, fixture_id=SECOND, verifies=[CRITERION])
    edit_doc(only_late, "08_fixtures.json", lambda doc: doc["fixtures"].pop(0))
    assert prove(only_late, CRITERION, "dev", treat_ci_as_dev=True).status == NOT_REQUIRED
    assert proof_errors(graph_of(only_late), context(only_late), [CRITERION], "dev", treat_ci_as_dev=True) == []


def test_plain_cap_dev_leaves_the_ci_binding_pending_stage(tmp_path: Path) -> None:
    host = _bound(tmp_path)
    _edit_binding(host, ALPHA, lambda record: record.update(stage="ci"))
    assert prove(host, CRITERION, "dev").status == PENDING_STAGE


def test_proof_errors_returns_e347_and_e348_for_the_failing_cases(tmp_path: Path) -> None:
    host = _bound(tmp_path)
    edit_code(host)
    errors = proof_errors(graph_of(host), context(host), [CRITERION, INVARIANT, "no-such-node", API], "dev")
    assert [(e.code, e.subcode, e.node_id, e.owner) for e in errors] == [
        ("E347", STALE_TREE, CRITERION, "step:04"), ("E348", "UNBOUND", INVARIANT, "step:06"), ("E347", STALE_TREE, API, "step:05"),
    ]
    assert "specdev verify run ver-alpha --stage dev" in errors[0].message and "specdev verify bind fix-password-reset-reused-token" in errors[1].message


def test_command_rule_is_proven_by_cli_command_membership(tmp_path: Path) -> None:
    host = host_with(tmp_path)
    assert prove(host, CLI_RULE).status == PROVEN
    edit_doc(host, "10_governance.json", lambda doc: doc["rules"][1].update(cli_command="no-such-command"))
    assert prove(host, CLI_RULE).status == NO_VERIFIER


def test_review_rule_is_proven_by_an_attestation(tmp_path: Path) -> None:
    host = host_with(tmp_path)
    rule = "rule-security-review-of-token-handling"
    assert prove(host, rule).status == UNPROVEN
    attest(host, rule)
    assert prove(host, rule).status == PROVEN


def test_threat_is_proven_when_all_mitigations_are_proven(tmp_path: Path) -> None:
    host = _bound(tmp_path, binding_item(REUSED_BINDING, verifier=OTHER_FIXTURE, proves=(INVARIANT,)), run_ids=(ALPHA,))
    assert prove(host, THREAT).status == UNPROVEN
    run(host, [REUSED_BINDING])
    assert prove(host, THREAT).status == PROVEN
    edit_code(host)
    assert prove(host, THREAT).status == UNPROVEN


def test_fr_is_proven_when_all_its_criteria_are(tmp_path: Path) -> None:
    host = _bound(tmp_path)
    result = prove(host, "fr-password-reset")
    assert (result.status, result.shortfalls[0].reason, result.shortfalls[0].verifier) == (NO_VERIFIER, "NO_VERIFIER", "ac-password-reset-1")
    for number in (1, 2):
        add_fixture(host, fixture_id=f"fix-criterion-{number}", verifies=[f"ac-password-reset-{number}"])
        write_binding(records_folder(str(host / "spec")), str(ROOT), binding_item(f"ver-criterion-{number}", verifier=f"fix-criterion-{number}", proves=(f"ac-password-reset-{number}",)))
    run(host, ["ver-criterion-1", "ver-criterion-2"])
    assert prove(host, "fr-password-reset").status == PROVEN
    edit_code(host)
    assert prove(host, "fr-password-reset").status == UNPROVEN


@pytest.mark.parametrize("cap", ["later", ""])
def test_a_cap_that_is_not_a_stage_is_refused(tmp_path: Path, cap: str) -> None:
    host = host_with(tmp_path)
    with pytest.raises(ValueError):
        proof(graph_of(host), context(host), CRITERION, cap)


def test_verifier_proof_for_no_binding_no_evidence_other_tree_lower_stage_and_retired_binding(tmp_path: Path) -> None:
    host = host_with(tmp_path)
    graph, ctx = graph_of(host), context(host)
    assert verifier_proof(graph, ctx, FIXTURE, "dev").status == UNBOUND
    host = host_with(tmp_path, binding_item(ALPHA), name="bound")
    assert [(r.status, r.shortfalls[0].reason) for r in [verifier_proof(graph_of(host), context(host), FIXTURE, "dev")]] == [(UNPROVEN, NO_EVIDENCE)]
    run(host, [ALPHA])
    assert verifier_proof(graph_of(host), context(host), FIXTURE, "dev").status == PROVEN
    edit_code(host)
    assert verifier_proof(graph_of(host), context(host), FIXTURE, "dev").shortfalls[0].reason == STALE_TREE
    run(host, [ALPHA])
    _edit_binding(host, ALPHA, lambda record: record.update(stage="staging"))
    assert verifier_proof(graph_of(host), context(host), FIXTURE, "staging").shortfalls[0].reason == "STAGE_TOO_LOW"
    edit_doc(host, "02a_delivery_baseline.json", lambda doc: doc["environments"]["staging"].update(scope="out"))
    assert verifier_proof(graph_of(host), context(host), FIXTURE, "staging").status == NOT_REQUIRED


def test_node_evidence_lists_the_evidence_of_the_bindings_that_prove_the_node(tmp_path: Path) -> None:
    host = _bound(tmp_path)
    assert [e.evidence_id for e in node_evidence(graph_of(host), context(host), CRITERION)] == ["evd-alpha-dev"]
    assert node_evidence(graph_of(host), context(host), INVARIANT) == []
