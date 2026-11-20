"""Evidence validity: each reason a stored run stops proving its binding, and what leaves it valid."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from specdev_tools.proof.validity import (
    GUARD_NOT_MATCHED, NONZERO_EXIT, STAGE_TOO_LOW, STALE_HASH, STALE_TP_VERSION, STALE_TREE, Validity, attestation_valid, evidence_for, evidence_valid,
)
from specdev_tools.verify.records import attestations_about
from specdev_tools.verify.records import binding_of

from ._support import API, CRITERION, FIXTURE, TP, attest, binding_item, commit_all, context, edit_code, edit_doc, graph_of, host_with, run

ALPHA = "ver-alpha"
FAILING = "echo expected line; exit 3"


def _valid(host: Path, binding_id: str = ALPHA, stage: str = "dev") -> Validity:
    """The validity of the evidence file of *binding_id* written by a run at *stage*, on *host* as it is now."""
    graph, ctx = graph_of(host), context(host)
    binding = binding_of(graph.by_id[binding_id], graph)
    [evidence] = [e for e in evidence_for(binding, ctx) if e.stage == stage]
    return evidence_valid(evidence, binding, graph, ctx)


def _edit_record(host: Path, binding_id: str, edit) -> None:
    path = host / "spec" / "extras" / "verification" / f"{binding_id}.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    edit(document["records"][0])
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


@pytest.fixture
def host(tmp_path: Path) -> Path:
    host = host_with(tmp_path, binding_item(ALPHA))
    run(host, [ALPHA])
    return host


def test_a_fresh_passing_run_is_valid(host: Path) -> None:
    assert _valid(host) == (True, None)


def test_guard_not_matched_is_reported(tmp_path: Path) -> None:
    host = host_with(tmp_path, binding_item(ALPHA, guard="no such line"))
    run(host, [ALPHA])
    assert _valid(host) == (False, GUARD_NOT_MATCHED)


def test_nonzero_exit_is_reported(tmp_path: Path) -> None:
    host = host_with(tmp_path, binding_item(ALPHA, commands=(FAILING,)))
    run(host, [ALPHA])
    assert _valid(host) == (False, NONZERO_EXIT)


def test_edited_code_is_stale_tree(host: Path) -> None:
    edit_code(host)
    assert _valid(host) == (False, STALE_TREE)


def test_spec_plan_anchor_and_lock_edits_leave_evidence_valid(host: Path) -> None:
    edit_doc(host, "16_impl_context.json", lambda doc: doc["plan"]["milestone_index"][0].update(summary="Confirm endpoint, second pass."))
    edit_doc(host, "impl_context/ms_account_recovery_plan.json", lambda doc: doc.update(note="a plan edit"))
    lock = host / "spec" / "extras" / "trace.lock.json"
    lock.write_text(lock.read_text(encoding="utf-8").rstrip() + "\n\n", encoding="utf-8")
    seed = host / "docs"
    next(seed.rglob("*.md")).write_text("a seed edit\n", encoding="utf-8")
    _edit_record(host, ALPHA, lambda record: record.update(output_guard="expected"))
    assert _valid(host) == (True, None)


def test_edited_fixture_is_stale_hash(host: Path) -> None:
    edit_doc(host, "08_fixtures.json", lambda doc: doc["fixtures"][0].update(description="The confirm endpoint now answers 404 for a stale token."))
    assert _valid(host) == (False, STALE_HASH)


def test_edited_proved_criterion_is_stale_hash(host: Path) -> None:
    edit_doc(host, "04_fr_list.json", lambda doc: doc["functional_requirements"][0]["acceptance_criteria"][2].update(text="A reset link older than 31 minutes is refused with HTTP 410."))
    assert _valid(host) == (False, STALE_HASH)


def test_pin_bump_is_stale_tp_version(tmp_path: Path) -> None:
    host = host_with(tmp_path, binding_item(ALPHA, proves=(API,)))
    run(host, [ALPHA], installed={TP: "0.41.1"})
    assert _valid(host) == (True, None)
    edit_doc(host, "02_system_sketch.json", lambda doc: doc["third_parties"][0].update(pin="0.42.0"))
    assert _valid(host) == (False, STALE_TP_VERSION)


def test_a_third_party_the_evidence_omits_is_skipped(tmp_path: Path) -> None:
    host = host_with(tmp_path, binding_item(ALPHA, proves=(API,)))
    run(host, [ALPHA])
    edit_doc(host, "02_system_sketch.json", lambda doc: doc["third_parties"][0].update(pin="0.42.0"))
    assert _valid(host) == (True, None)


def test_evidence_below_the_binding_stage_is_stage_too_low(host: Path) -> None:
    _edit_record(host, ALPHA, lambda record: record.update(stage="ci"))
    assert _valid(host) == (False, STAGE_TOO_LOW)


def test_later_stage_evidence_satisfies_a_dev_binding_not_the_reverse(host: Path) -> None:
    run(host, [ALPHA], stage="ci")
    assert _valid(host, stage="ci") == (True, None)
    _edit_record(host, ALPHA, lambda record: record.update(stage="staging"))
    assert _valid(host, stage="ci") == (False, STAGE_TOO_LOW)
    _edit_record(host, ALPHA, lambda record: record.update(stage="dev"))
    assert _valid(host, stage="dev") == (True, None)


def test_pass_then_fail_on_one_tree_leaves_the_binding_unsatisfied(host: Path) -> None:
    _edit_record(host, ALPHA, lambda record: record.update(commands=[FAILING]))
    run(host, [ALPHA])
    assert _valid(host) == (False, NONZERO_EXIT)


def test_pass_at_dev_then_failing_ci_leaves_the_dev_file_valid(host: Path) -> None:
    _edit_record(host, ALPHA, lambda record: record.update(commands=[FAILING]))
    run(host, [ALPHA], stage="ci")
    assert _valid(host, stage="dev") == (True, None)
    assert _valid(host, stage="ci") == (False, NONZERO_EXIT)


def test_rerun_overwrites_rather_than_adds_a_file(host: Path) -> None:
    run(host, [ALPHA])
    run(host, [ALPHA])
    graph, ctx = graph_of(host), context(host)
    assert len(evidence_for(binding_of(graph.by_id[ALPHA], graph), ctx)) == 1
    assert [path.name for path in (host / "spec" / "extras" / "verification").glob("evd-*")] == ["evd-alpha-dev.json"]


def test_identical_command_cross_binding_satisfaction(tmp_path: Path) -> None:
    host = host_with(tmp_path, binding_item(ALPHA), binding_item("ver-beta", proves=(CRITERION,), stage="ci"))
    run(host, [ALPHA], stage="ci")
    graph, ctx = graph_of(host), context(host)
    beta = binding_of(graph.by_id["ver-beta"], graph)
    [evidence] = evidence_for(binding_of(graph.by_id[ALPHA], graph), ctx)
    assert evidence.stage == "ci" and evidence_valid(evidence, beta, graph, ctx) == (True, None)


def test_cross_binding_hash_reads_the_second_bindings_own_targets(tmp_path: Path) -> None:
    host = host_with(tmp_path, binding_item(ALPHA, proves=(CRITERION,)), binding_item("ver-beta", proves=(CRITERION, API)))
    run(host, [ALPHA])
    graph, ctx = graph_of(host), context(host)
    [evidence] = evidence_for(binding_of(graph.by_id[ALPHA], graph), ctx)
    assert evidence_valid(evidence, binding_of(graph.by_id[ALPHA], graph), graph, ctx) == (True, None)
    beta = binding_of(graph.by_id["ver-beta"], graph)
    assert evidence_valid(evidence, beta, graph, ctx) == (False, STALE_HASH)
    edit_doc(host, "05_interface_contracts.json", lambda doc: doc["apis"][0].update(name="Confirm a Password Reset"))
    graph = graph_of(host)
    assert evidence_valid(evidence, binding_of(graph.by_id["ver-beta"], graph), graph, context(host)) == (False, STALE_HASH)


def test_a_binding_without_a_run_has_no_evidence_files(tmp_path: Path) -> None:
    host = host_with(tmp_path, binding_item(ALPHA))
    graph = graph_of(host)
    assert evidence_for(binding_of(graph.by_id[ALPHA], graph), context(host)) == []


def _attestation_validity(host: Path) -> Validity:
    graph = graph_of(host)
    [attestation] = attestations_about(graph, FIXTURE)
    return attestation_valid(attestation, FIXTURE, graph, context(host))


def test_attestation_evidence_is_valid_on_the_tree_and_hash_and_stale_after_a_change(tmp_path: Path) -> None:
    host = host_with(tmp_path)
    attest(host, FIXTURE)
    assert _attestation_validity(host) == (True, None)
    edit_doc(host, "08_fixtures.json", lambda doc: doc["fixtures"][0].update(description="The confirm endpoint answers 404 for a stale token."))
    assert _attestation_validity(host) == (False, STALE_HASH)
    edit_doc(host, "08_fixtures.json", lambda doc: doc["fixtures"][0].update(description="The confirm endpoint rejects a token issued 31 minutes earlier and leaves the password unchanged."))
    edit_code(host)
    assert _attestation_validity(host) == (False, STALE_TREE)


def test_a_committed_edit_of_the_code_is_stale_tree_too(host: Path) -> None:
    edit_code(host, "committed change\n")
    commit_all(host)
    assert _valid(host) == (False, STALE_TREE)
