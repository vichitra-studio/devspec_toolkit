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

from unit.verify._support import write_json

from ._support import API, CRITERION, FIXTURE, TP, attest, binding_item, commit_all, context, edit_binding, edit_code, edit_doc, graph_of, host_with, run

ALPHA = "ver-alpha"
GUARD_TEXT = "expected line"
PASSING_COMMAND = "echo expected line"
FAILING = "echo expected line; exit 3"


def _valid(host: Path, binding_id: str = ALPHA, stage: str = "dev") -> Validity:
    """The validity of the evidence file of *binding_id* written by a run at *stage*, on *host* as it is now."""
    graph, ctx = graph_of(host), context(host)
    binding = binding_of(graph.by_id[binding_id], graph)
    [evidence] = [e for e in evidence_for(binding, ctx) if e.stage == stage]
    return evidence_valid(evidence, binding, graph, ctx)


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
    assert _valid(host) == (True, None)


def test_a_rebind_that_changes_the_guard_or_the_commands_without_a_run_is_stale_hash(host: Path) -> None:
    """S22: the evidence rests on the binding too; the commands that are bound now were never run."""
    edit_binding(host, ALPHA, lambda record: record.update(output_guard="expected"))
    assert _valid(host) == (False, STALE_HASH)
    edit_binding(host, ALPHA, lambda record: record.update(output_guard=GUARD_TEXT, commands=["true"]))
    assert _valid(host) == (False, STALE_HASH)
    edit_binding(host, ALPHA, lambda record: record.update(commands=[PASSING_COMMAND]))
    assert _valid(host) == (True, None)


def test_a_rewrite_of_the_binding_that_changes_nothing_leaves_the_evidence_valid(host: Path) -> None:
    edit_binding(host, ALPHA, lambda record: record.update(commands=list(record["commands"])))
    assert _valid(host) == (True, None)


def test_a_node_added_to_proves_after_the_run_is_stale_hash_until_the_run_is_repeated(tmp_path: Path) -> None:
    """The run hashed the nodes the binding proved then; a node proved only now was never hashed and is stale, not skipped."""
    host = host_with(tmp_path, binding_item(ALPHA, proves=(CRITERION,)))
    run(host, [ALPHA])
    assert _valid(host) == (True, None)
    edit_doc(host, "05_interface_contracts.json", lambda doc: doc["apis"][0].update(name="Confirm a Password Reset"))
    edit_binding(host, ALPHA, lambda record: record.update(proves=[CRITERION, API]))
    assert _valid(host) == (False, STALE_HASH)
    run(host, [ALPHA])
    assert _valid(host) == (True, None)


def test_evidence_written_before_the_binding_was_recorded_is_stale_hash(host: Path) -> None:
    """A file with no hash for the binding itself (written by an earlier toolkit) reads as stale: run again."""
    path = host / "spec" / "extras" / "verification" / "evd-alpha-dev.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    del document["records"][0]["recorded_hashes"][ALPHA]
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    assert _valid(host) == (False, STALE_HASH)


def test_edited_fixture_is_stale_hash(host: Path) -> None:
    edit_doc(host, "08_fixtures.json", lambda doc: doc["fixtures"][0].update(description="The confirm endpoint now answers 404 for a stale token."))
    assert _valid(host) == (False, STALE_HASH)


def test_a_binding_that_states_no_proves_goes_stale_when_a_node_its_verifier_proves_is_edited(tmp_path: Path) -> None:
    """A record with no ``proves`` proves every target of its verifier (the worked example's record): a run records their hashes too."""
    host = host_with(tmp_path, binding_item(ALPHA, proves=()))
    [evidence] = run(host, [ALPHA])
    assert {"ac-password-reset-3", "api-password-reset-confirm"} <= set(evidence.recorded_hashes)
    graph, ctx = graph_of(host), context(host)
    assert evidence_valid(evidence_for(binding_of(graph.by_id[ALPHA], graph), ctx)[0], binding_of(graph.by_id[ALPHA], graph), graph, ctx) == (True, None)
    edit_doc(host, "04_fr_list.json", lambda doc: doc["functional_requirements"][0]["acceptance_criteria"][2].update(text="A reset link older than 31 minutes is refused with HTTP 410."))
    graph, ctx = graph_of(host), context(host)
    binding = binding_of(graph.by_id[ALPHA], graph)
    assert evidence_valid(evidence_for(binding, ctx)[0], binding, graph, ctx) == (False, STALE_HASH)


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


def _lock_pointer(name: str) -> dict[str, object]:
    return {"type": "json-pointer", "file": "package-lock.json", "pointer": f"/packages/node_modules~1{name}/version"}


def _declare_sources(host: Path, *names: str) -> None:
    """Declare the lock file as the source of the pin of each third party in *names* (``tp-<name>``); a spec edit, so the code tree stays."""
    write_json(host / "spec" / "common" / "host_declarations.json", {"$schema": "vc:host-declarations", "pin_sources": {f"tp-{name}": [_lock_pointer(name)] for name in names}})


def _host_with_lock(tmp_path: Path) -> Path:
    """The example with a lock file that reads each pin, one binding of the API, committed (the lock is code: it is there before the run)."""
    host = host_with(tmp_path, binding_item(ALPHA, proves=(API,)))
    write_json(host / "package-lock.json", {"packages": {"node_modules/argon2": {"version": "0.41.1"}, "node_modules/mailrelay": {"version": "api-v3"}, "node_modules/sms": {"version": "1.0.0"}}})
    commit_all(host)
    return host


def test_a_source_declared_after_the_run_for_a_third_party_the_evidence_omits_is_stale_tp_version(tmp_path: Path) -> None:
    """The run recorded no version for the relied-on third parties (no source then); with a source now the pass rests on a version nobody recorded."""
    host = _host_with_lock(tmp_path)
    run(host, [ALPHA])
    assert _valid(host) == (True, None)
    _declare_sources(host, "argon2")
    assert _valid(host) == (False, STALE_TP_VERSION)
    run(host, [ALPHA])
    assert _valid(host) == (True, None)


def test_a_reliance_that_appears_after_the_run_and_has_a_source_is_stale_tp_version(tmp_path: Path) -> None:
    """A component connection that reaches a new third party changes the hash of no node the evidence rests on."""
    host = _host_with_lock(tmp_path)
    _declare_sources(host, "argon2", "mailrelay")
    run(host, [ALPHA])
    assert _valid(host) == (True, None)
    edit_doc(host, "02_system_sketch.json", lambda doc: doc["third_parties"].append({"third_party_id": "tp-sms", "name": "sms", "pin": "1.0.0", "derives_from": ["seed-accounts"]}))
    edit_doc(host, "02_system_sketch.json", lambda doc: doc["connections"][0]["connects_to"].append("tp-sms"))
    assert _valid(host) == (True, None), "no declared source for tp-sms yet: nothing to compare"
    _declare_sources(host, "argon2", "mailrelay", "sms")
    assert _valid(host) == (False, STALE_TP_VERSION)
    run(host, [ALPHA])
    assert _valid(host) == (True, None)


def test_a_run_after_the_rename_of_a_third_party_records_its_version_and_a_pin_bump_is_stale(tmp_path: Path) -> None:
    """``pin_sources`` keeps the id the author wrote: the run reads it through the aliases, so the renamed third party is compared with its pin."""
    host = _host_with_lock(tmp_path)
    _declare_sources(host, "argon2", "mailrelay")
    renamed = "tp-argon2-lib"
    edit_doc(host, "02_system_sketch.json", lambda doc: doc["third_parties"][0].update(third_party_id=renamed, aliases=[TP]))
    edit_doc(host, "05_interface_contracts.json", lambda doc: doc["apis"][0].update(relies_on=[renamed]))
    [evidence] = run(host, [ALPHA])
    assert dict(evidence.installed_versions)[renamed] == "0.41.1"
    assert _valid(host) == (True, None)
    edit_doc(host, "02_system_sketch.json", lambda doc: doc["third_parties"][0].update(pin="0.99.0"))
    assert _valid(host) == (False, STALE_TP_VERSION)


def test_a_declared_source_of_a_third_party_the_proved_nodes_do_not_rely_on_is_not_asked_for(tmp_path: Path) -> None:
    host = _host_with_lock(tmp_path)
    _declare_sources(host, "argon2", "mailrelay")
    run(host, [ALPHA])
    edit_doc(host, "02_system_sketch.json", lambda doc: doc["third_parties"].append({"third_party_id": "tp-sms", "name": "sms", "pin": "1.0.0", "derives_from": ["seed-accounts"]}))
    _declare_sources(host, "argon2", "mailrelay", "sms")
    assert _valid(host) == (True, None)


def test_evidence_below_the_binding_stage_is_stage_too_low(tmp_path: Path) -> None:
    """A sibling binding with the same commands and guard at a higher stage is not satisfied by the dev run of the first."""
    host = host_with(tmp_path, binding_item(ALPHA), binding_item("ver-beta", proves=(CRITERION,), stage="ci"))
    run(host, [ALPHA])
    graph, ctx = graph_of(host), context(host)
    [evidence] = evidence_for(binding_of(graph.by_id[ALPHA], graph), ctx)
    assert evidence_valid(evidence, binding_of(graph.by_id["ver-beta"], graph), graph, ctx) == (False, STAGE_TOO_LOW)


def test_later_stage_evidence_satisfies_a_dev_binding_not_the_reverse(tmp_path: Path) -> None:
    host = host_with(tmp_path, binding_item(ALPHA), binding_item("ver-beta", proves=(CRITERION,), stage="staging"))
    run(host, [ALPHA], stage="ci")
    assert _valid(host, stage="ci") == (True, None)
    graph, ctx = graph_of(host), context(host)
    [evidence] = evidence_for(binding_of(graph.by_id[ALPHA], graph), ctx)
    assert evidence_valid(evidence, binding_of(graph.by_id["ver-beta"], graph), graph, ctx) == (False, STAGE_TOO_LOW)


def test_pass_then_fail_on_one_tree_leaves_the_binding_unsatisfied(host: Path) -> None:
    edit_binding(host, ALPHA, lambda record: record.update(commands=[FAILING]))
    run(host, [ALPHA])
    assert _valid(host) == (False, NONZERO_EXIT)


def test_a_failing_run_after_a_rebind_leaves_the_earlier_file_stale(host: Path) -> None:
    """The dev file was written for the earlier commands: after the rebind it is stale, and the ci run of the new commands fails."""
    edit_binding(host, ALPHA, lambda record: record.update(commands=[FAILING]))
    run(host, [ALPHA], stage="ci")
    assert _valid(host, stage="dev") == (False, STALE_HASH)
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


def test_a_sibling_file_is_stale_for_both_bindings_once_the_binding_that_ran_changes(tmp_path: Path) -> None:
    """The file is evidence of the run of the binding that wrote it, as that binding then read: the only record of which commands ran is its hash."""
    host = host_with(tmp_path, binding_item(ALPHA), binding_item("ver-beta", proves=(CRITERION,), stage="ci"))
    run(host, [ALPHA], stage="ci")
    edit_binding(host, ALPHA, lambda record: record.update(stage="prod"))
    graph, ctx = graph_of(host), context(host)
    [evidence] = evidence_for(binding_of(graph.by_id[ALPHA], graph), ctx)
    assert evidence_valid(evidence, binding_of(graph.by_id["ver-beta"], graph), graph, ctx) == (False, STALE_HASH)
    assert evidence_valid(evidence, binding_of(graph.by_id[ALPHA], graph), graph, ctx) == (False, STALE_HASH)


def test_two_siblings_changed_to_the_same_new_commands_get_no_credit_for_the_old_run(tmp_path: Path) -> None:
    """Both bindings now name a command that never ran; that they agree with each other proves nothing."""
    host = host_with(tmp_path, binding_item(ALPHA), binding_item("ver-beta", proves=(CRITERION,), stage="ci"))
    run(host, [ALPHA], stage="ci")
    for binding_id in (ALPHA, "ver-beta"):
        edit_binding(host, binding_id, lambda record: record.update(commands=["false"], output_guard="NEVER PRINTED"))
    graph, ctx = graph_of(host), context(host)
    [evidence] = evidence_for(binding_of(graph.by_id[ALPHA], graph), ctx)
    assert evidence_valid(evidence, binding_of(graph.by_id["ver-beta"], graph), graph, ctx) == (False, STALE_HASH)


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


def test_an_attestation_survives_the_rename_of_the_attested_node(tmp_path: Path) -> None:
    """The keys of ``recorded_hashes`` are read through the aliases, as the ``about`` of the attestation is."""
    host = host_with(tmp_path)
    attest(host, FIXTURE)
    renamed = "fix-password-reset-expired-token-v2"
    edit_doc(host, "08_fixtures.json", lambda doc: doc["fixtures"][0].update(fixture_id=renamed, aliases=[FIXTURE]))
    graph = graph_of(host)
    [attestation] = attestations_about(graph, renamed)
    assert attestation_valid(attestation, renamed, graph, context(host)) == (True, None)


def test_run_evidence_survives_the_rename_of_the_verifier_and_of_a_proved_node(host: Path) -> None:
    """The keys of ``recorded_hashes`` keep the ids the run read; they are read through the aliases, as the keys of an attestation are."""
    renamed = "fix-password-reset-expired-token-v2"
    edit_doc(host, "08_fixtures.json", lambda doc: doc["fixtures"][0].update(fixture_id=renamed, aliases=[FIXTURE]))
    assert _valid(host) == (True, None)
    edit_doc(host, "05_interface_contracts.json", lambda doc: doc["apis"][0].update(api_id="api-password-reset-confirm-v2", aliases=[API]))
    assert _valid(host) == (True, None)


def test_a_committed_edit_of_the_code_is_stale_tree_too(host: Path) -> None:
    edit_code(host, "committed change\n")
    commit_all(host)
    assert _valid(host) == (False, STALE_TREE)
