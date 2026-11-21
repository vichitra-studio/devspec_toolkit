"""Proof of an obligation at a gate: the statuses, the routing per kind, the close mode and the findings of a gate."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from specdev_tools.core.errors import FindingError
from specdev_tools.proof.proof import (
    NO_VERIFIER, NOT_REQUIRED, PENDING_STAGE, PROVEN, UNBOUND, UNPROVEN, proof, proof_errors, verifier_proof,
)
from specdev_tools.proof.validity import NO_EVIDENCE, NONZERO_EXIT, STALE_TREE, evidence_for
from specdev_tools.verify.records import binding_of, records_folder, write_binding
from unit.graph._synth import ROOT

from ._support import (
    API, ci_host, commit_all, edit_binding, CRITERION, FIXTURE, INVARIANT, NFR, OTHER_FIXTURE, REUSED_BINDING, add_fixture, attest, binding_item, context, edit_code, edit_doc, graph_of,
    host_with, prove, run,
)

ALPHA = "ver-alpha"
FAILING = "echo expected line; exit 3"
TASK_CRITERION = "tc-confirm-expired-token"
CLI_RULE = "rule-spec-check-on-every-pr"
THREAT = "threat-reset-token-replay"
SECOND = "fix-second-expired-token"


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


def test_ci_binding_is_proven_at_cap_ci_from_transient_evidence_without_a_file(tmp_path: Path) -> None:
    host = ci_host(tmp_path, ran=False)
    transient = run(host, [ALPHA], stage="ci", record=False)
    assert list((host / "spec" / "extras" / "verification").glob("evd-*")) == []
    assert prove(host, CRITERION, "ci").status == UNPROVEN
    assert prove(host, CRITERION, "ci", transient_evidence=transient).status == PROVEN


def test_failing_transient_run_is_unproven(tmp_path: Path) -> None:
    host = ci_host(tmp_path, commands=(FAILING,), ran=False)
    transient = run(host, [ALPHA], stage="ci", record=False)
    result = prove(host, CRITERION, "ci", transient_evidence=transient)
    assert (result.status, result.shortfalls[0].reason) == (UNPROVEN, NONZERO_EXIT)


def test_close_mode_ci_binding_with_dev_evidence_is_proven(tmp_path: Path) -> None:
    host = _bound(tmp_path, binding_item("ver-beta", proves=(CRITERION,), stage="ci"))
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
    edit_binding(host, ALPHA, lambda record: record.update(stage="ci"))
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
    edit_binding(host, ALPHA, lambda record: record.update(stage="staging"))
    assert verifier_proof(graph_of(host), context(host), FIXTURE, "staging").shortfalls[0].reason == "STALE_HASH"
    edit_doc(host, "02a_delivery_baseline.json", lambda doc: doc["environments"]["staging"].update(scope="out"))
    assert verifier_proof(graph_of(host), context(host), FIXTURE, "staging").status == NOT_REQUIRED
    host = host_with(tmp_path, binding_item(ALPHA), binding_item("ver-late", proves=(CRITERION,), stage="staging"), name="lower")
    run(host, [ALPHA])
    assert verifier_proof(graph_of(host), context(host), FIXTURE, "staging").shortfalls[0].reason == "STAGE_TOO_LOW"


def test_the_advice_for_a_stale_third_party_version_names_the_repository_before_the_run(tmp_path: Path) -> None:
    """A run records the version the repository declares: running again does not clear it until the declared version is the pin."""
    host = host_with(tmp_path, binding_item(ALPHA, proves=(API,)))
    run(host, [ALPHA], installed={"tp-argon2": "0.41.1"})
    edit_doc(host, "02_system_sketch.json", lambda doc: doc["third_parties"][0].update(pin="0.42.0"))
    [error] = proof_errors(graph_of(host), context(host), [API], "dev")
    assert (error.code, error.subcode) == ("E347", "STALE_TP_VERSION")
    assert "equal the pin" in error.message and "third-party check" in error.message
    assert error.message.endswith("then run `specdev verify run ver-alpha --stage dev`")


def test_a_node_whose_stage_cannot_be_told_is_not_proven_and_proof_errors_reports_e334(tmp_path: Path) -> None:
    """An environment that is not a stage was read as ``dev``; now the proof raises and the gate's findings carry E334 for the node."""
    host = _bound(tmp_path)
    edit_doc(host, "02a_delivery_baseline.json", lambda doc: doc["environments"].update(qa={"scope": "in"}))
    edit_doc(host, "12_ci_gates.json", lambda doc: doc["jobs"].append({"job_id": "job-qa-smoke", "name": "QA smoke", "realises": ["qa"]}))
    with pytest.raises(FindingError) as caught:
        prove(host, "qa")
    assert caught.value.error.code == "E334"
    errors = proof_errors(graph_of(host), context(host), [CRITERION, "qa"], "dev")
    assert [(e.code, e.node_id) for e in errors] == [("E334", "qa")]
    assert "environment 'qa' is not a stage" in errors[0].message


# --- the neighbour answers of the "proven" branches (round 1, B-4, A3, A4) --------------------------------------------


def test_a_binding_that_proves_only_one_node_does_not_bind_the_other_obligation_of_its_verifier(tmp_path: Path) -> None:
    host = host_with(tmp_path, binding_item(ALPHA, proves=(CRITERION,)))
    run(host, [ALPHA])
    assert prove(host, CRITERION).status == PROVEN
    result = prove(host, API)
    assert (result.status, result.shortfalls[0].reason) == (UNBOUND, "UNBOUND")


def test_an_attestation_below_the_stage_the_obligation_needs_is_stage_too_low(tmp_path: Path) -> None:
    host = host_with(tmp_path)
    manual = "fix-latency-manual"
    add_fixture(host, fixture_id=manual, verifies=[NFR], mode="manual", manual_reason="A person times the delivery of the reset email.")
    attest(host, manual, stage="dev")
    result = prove(host, NFR, "staging")
    assert (result.status, result.shortfalls[0].reason) == (UNPROVEN, "STAGE_TOO_LOW")
    attest(host, manual, stage="staging", evidence_id="evd-attest-two")
    assert prove(host, NFR, "staging").status == PROVEN


def test_a_sibling_binding_with_another_guard_gets_no_credit_for_a_run_it_did_not_make(tmp_path: Path) -> None:
    """Same verifier, same commands, another guard: the run of the first is not a run of the second."""
    host = host_with(tmp_path, binding_item(ALPHA, proves=(CRITERION,)), binding_item("ver-beta", proves=(API,), guard="expected"))
    run(host, [ALPHA])
    assert prove(host, CRITERION).status == PROVEN
    result = prove(host, API)
    assert (result.status, result.shortfalls[0].reason, result.shortfalls[0].binding) == (UNPROVEN, NO_EVIDENCE, "ver-beta")


def test_an_evidence_file_that_is_about_another_binding_is_not_the_evidence_of_this_one(tmp_path: Path) -> None:
    host = host_with(tmp_path, binding_item(ALPHA))
    run(host, [ALPHA])
    edit_binding(host, "evd-alpha-dev", lambda record: record.update(about=["ver-someone-else"]))
    graph = graph_of(host)
    assert evidence_for(binding_of(graph.by_id[ALPHA], graph), context(host)) == []
    assert prove(host, CRITERION).shortfalls[0].reason == NO_EVIDENCE


def test_the_hashes_of_a_context_follow_the_graph_it_is_asked_about(tmp_path: Path) -> None:
    host = host_with(tmp_path)
    ctx = context(host)
    before = dict(ctx.content_hashes(graph_of(host)))
    edit_doc(host, "04_fr_list.json", lambda doc: doc["functional_requirements"][0]["acceptance_criteria"][2].update(text="A reset link older than 31 minutes is refused with HTTP 410."))
    after = ctx.content_hashes(graph_of(host))
    assert after[CRITERION] != before[CRITERION]


def test_an_unproven_verifier_outweighs_a_pending_one(tmp_path: Path) -> None:
    host = host_with(tmp_path, binding_item(ALPHA, proves=(CRITERION,)), binding_item("ver-late", verifier=SECOND, proves=(CRITERION,), stage="ci"))
    add_fixture(host, fixture_id=SECOND, verifies=[CRITERION])
    result = prove(host, CRITERION, "dev")
    assert (result.status, [s.verifier for s in result.shortfalls]) == (UNPROVEN, [FIXTURE])


def test_a_manual_fixture_that_also_has_a_binding_record_is_not_proven_by_an_attestation(tmp_path: Path) -> None:
    """The attestation covers a manual fixture with no binding at all; a record that names it (by hand) leaves it to the binding rules."""
    host = host_with(tmp_path, binding_item(ALPHA, proves=(CRITERION,)))
    edit_doc(host, "08_fixtures.json", lambda doc: doc["fixtures"][0].update(mode="manual", manual_reason="A person reads the mail relay log."))
    attest(host, FIXTURE)
    result = prove(host, API)
    assert (result.status, result.shortfalls[0].reason) == (UNBOUND, "UNBOUND")


def test_the_advice_for_a_failing_run_says_to_fix_it_before_running(tmp_path: Path) -> None:
    host = host_with(tmp_path, binding_item(ALPHA, commands=(FAILING,)))
    run(host, [ALPHA])
    [first, *_rest] = proof_errors(graph_of(host), context(host), [CRITERION], "dev")
    assert first.subcode == NONZERO_EXIT and "the commands failed; fix it, then run `specdev verify run ver-alpha --stage dev`" in first.message


def test_a_threat_with_one_unproven_mitigation_is_unproven(tmp_path: Path) -> None:
    """A3: the threat has two mitigations (the invariant and the expired-token fixture); only the invariant is run."""
    host = host_with(tmp_path, binding_item(ALPHA), binding_item(REUSED_BINDING, verifier=OTHER_FIXTURE, proves=(INVARIANT,)))
    run(host, [REUSED_BINDING])
    result = prove(host, THREAT)
    assert (result.status, [s.verifier for s in result.shortfalls]) == (UNPROVEN, [FIXTURE])


def test_a_verifier_with_two_bindings_at_the_cap_is_unproven_when_the_second_fails(tmp_path: Path) -> None:
    """A4: both bindings are due at dev; the first has a run, the second none."""
    host = host_with(tmp_path, binding_item(ALPHA, proves=(CRITERION,)), binding_item("ver-api", proves=(API,), commands=("echo api line",), guard="api line"))
    run(host, [ALPHA])
    result = verifier_proof(graph_of(host), context(host), FIXTURE, "dev")
    assert (result.status, result.shortfalls[0].binding) == (UNPROVEN, "ver-api")
    run(host, ["ver-api"])
    assert verifier_proof(graph_of(host), context(host), FIXTURE, "dev").status == PROVEN


def test_a_binding_that_never_ran_whose_only_countable_file_is_a_siblings_that_does_not_cover_it_has_no_evidence(tmp_path: Path) -> None:
    """Same verifier, same commands and guard, disjoint nodes: the sibling's file recorded none of this binding's nodes, so it is not evidence of it: run it (NO_EVIDENCE), not re-run it (STALE_HASH)."""
    host = host_with(tmp_path, binding_item(ALPHA, proves=(CRITERION,)), binding_item("ver-beta", proves=(API,)))
    run(host, [ALPHA])
    result = prove(host, API)
    assert (result.status, result.shortfalls[0].reason, result.shortfalls[0].binding) == (UNPROVEN, NO_EVIDENCE, "ver-beta")


def test_a_binding_of_a_verifier_that_proves_nothing_is_proven_by_the_run_of_a_sibling_with_the_same_commands_and_guard(tmp_path: Path) -> None:
    """The one path that reaches the credit of another binding's file: a rule has no node to prove, so two bindings of it (the second with ``--id``) cannot overlap."""
    one, two = binding_item("ver-rule-one", verifier=CLI_RULE, proves=(), stage="ci"), binding_item("ver-rule-two", verifier=CLI_RULE, proves=(), stage="ci")
    host = host_with(tmp_path, one, two)
    run(host, ["ver-rule-one"], stage="ci")
    assert [path.name for path in (host / "spec" / "extras" / "verification").glob("evd-*")] == ["evd-rule-one-ci.json"]
    assert prove(host, CLI_RULE, "ci").status == PROVEN
    edit_binding(host, "ver-rule-one", lambda record: record.update(output_guard="expected"))
    assert prove(host, CLI_RULE, "ci").status == UNPROVEN


def test_two_bindings_that_share_commands_each_get_their_own_file_from_one_execution(tmp_path: Path) -> None:
    """``verify run`` runs a group of bindings with the same commands and guard once and writes one file for each binding: with disjoint nodes the files are not shared."""
    counter = tmp_path / "executions.txt"
    commands = (f"echo once >> {counter}; echo expected line",)
    add = {"fixture_id": SECOND, "verifies": [CRITERION, NFR]}
    host = host_with(tmp_path, binding_item("ver-one", verifier=SECOND, proves=(CRITERION,), commands=commands), binding_item("ver-two", verifier=SECOND, proves=(NFR,), stage="staging", commands=commands))
    add_fixture(host, **add)
    commit_all(host)
    first, second = run(host, ["ver-one", "ver-two"], stage="staging")
    assert counter.read_text(encoding="utf-8").splitlines() == ["once"]
    assert (first.evidence_id, second.evidence_id) == ("evd-one-staging", "evd-two-staging")
    assert first.output_hash == second.output_hash and first.about == ("ver-one",) and second.about == ("ver-two",)
    assert prove(host, NFR, "staging").status == PROVEN


def test_a_retired_binding_is_left_out_of_the_proof_of_its_verifier(tmp_path: Path) -> None:
    """A binding whose stage names an environment that is out of scope is not asked for: the live binding alone decides."""
    host = host_with(tmp_path, binding_item(ALPHA, proves=(CRITERION,)), binding_item("ver-late", proves=(API,), stage="staging"))
    run(host, [ALPHA])
    assert verifier_proof(graph_of(host), context(host), FIXTURE, "staging").status == UNPROVEN
    edit_doc(host, "02a_delivery_baseline.json", lambda doc: doc["environments"]["staging"].update(scope="out"))
    assert verifier_proof(graph_of(host), context(host), FIXTURE, "staging").status == PROVEN
