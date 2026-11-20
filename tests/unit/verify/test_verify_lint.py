"""The lint of verification records (E330, E334, a ``proves`` id that names no node) and the pruning of records by ``attest --prune``."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.core.errors import SpecError
from specdev_tools.graph.build import build_graph
from specdev_tools.graph.check import run_graph_check
from specdev_tools.graph.kinds import RECORD_ROLE
from specdev_tools.verify.lint import PROVES_UNKNOWN_CODE, lint_verification_records, orphan_records, prune_orphan_records
from unit.graph._synth import ROOT
from unit.trace._lock_support import lock_for, run_on_example

from ._support import edit_doc, example_host, graph_of, write_json

FIXTURE = "fix-password-reset-expired-token"
BINDING = "ver-password-reset-expired-token"
CRITERION = "ac-password-reset-3"
RECORDS = "extras/verification"
VERIFICATION_URI = "vc:extras:verification-record"
EVIDENCE_URI = "vc:extras:evidence-record"
OUTPUT_HASH = "sha256:" + "c0ffee5e" * 8
DOC_STAGING_BINDING = {
    "verification_id": "ver-reset-email-delivery-staging",
    "verifies": ["fix-reset-email-delivery-time"],
    "stage": "staging",
    "commands": ["./scripts/synthetic-reset.sh --env staging --max-seconds 60"],
    "output_guard": "delivered in [0-9]+ s",
}


def _evidence(evidence_id: str, about: str) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "about": [about],
        "exit_code": 0,
        "guard_matched": True,
        "output_hash": OUTPUT_HASH,
        "tested_tree": "9a41c7e2",
        "stage": "dev",
        "installed_versions": {},
    }


def _write_record(host: Path, uri: str, record: dict[str, Any], name: str) -> None:
    write_json(host / "spec" / RECORDS / f"{name}.json", {"$schema": uri, "records": [record]})


def _edit_binding(host: Path, edit: Any) -> None:
    path = host / "spec" / RECORDS / f"{BINDING}.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    edit(document["records"][0])
    write_json(path, document)


def _delete_fixture(host: Path) -> None:
    edit_doc(host, "08_fixtures.json", lambda doc: doc.update(fixtures=[f for f in doc["fixtures"] if f["fixture_id"] != FIXTURE]))


def _alias_criterion(doc: dict[str, Any]) -> None:
    for fr in doc["functional_requirements"]:
        for criterion in fr.get("acceptance_criteria", ()):
            if criterion["criterion_id"] == CRITERION:
                criterion["aliases"] = ["ac-gone-1"]


def _record_files(host: Path) -> list[str]:
    return sorted(path.name for path in (host / "spec" / RECORDS).glob("*.json"))


def _prune(host: Path, *flags: str) -> tuple[int, str]:
    return run_on_example(host, "attest", "--prune", *flags)


def _graph_findings(host: Path) -> list[SpecError]:
    """The E700 findings of the ``graph`` check whose holder is a record."""
    graph = graph_of(host)
    findings = run_graph_check(str(host / "spec"), str(ROOT), graph=graph, lock=lock_for(graph, host))
    return [error for error in findings if error.code == "E700" and graph.by_id[error.node_id].role == RECORD_ROLE]


@pytest.fixture
def host(tmp_path: Path) -> Path:
    return example_host(tmp_path)


@pytest.fixture
def bound(host: Path) -> Path:
    """The example host with a run's evidence about the binding of the example, and an attestation about its fixture."""
    _write_record(host, EVIDENCE_URI, _evidence("evd-password-reset-expired-token-dev", BINDING), "evd-password-reset-expired-token-dev")
    return host


def test_deleted_fixture_gives_e700_for_its_binding_and_evidence(bound: Path) -> None:
    attestation = {"evidence_id": "evd-attest-expired", "type": "attestation", "about": [FIXTURE], "tested_tree": "9a41c7e2"}
    _write_record(bound, EVIDENCE_URI, attestation, "evd-attest-expired")
    _delete_fixture(bound)
    holders = {error.node_id for error in _graph_findings(bound)}
    assert holders == {BINDING, "evd-attest-expired"}


def test_prune_dry_run_lists_both_files_and_deletes_nothing(bound: Path) -> None:
    _delete_fixture(bound)
    before = _record_files(bound)
    code, out = _prune(bound, "--dry-run")
    assert code == 0, out
    assert "would remove 2 orphan records" in out
    assert f"{RECORDS}/{BINDING}.json" in out and f"{RECORDS}/evd-password-reset-expired-token-dev.json" in out
    assert _record_files(bound) == before


def test_prune_removes_both_files_and_the_check_is_clean(bound: Path) -> None:
    _delete_fixture(bound)
    code, out = _prune(bound)
    assert code == 0 and "removed 2 orphan records" in out, out
    assert _record_files(bound) == []
    assert _graph_findings(bound) == []
    assert orphan_records(graph_of(bound)) == []


def test_prune_removes_evidence_about_a_pruned_verification_record(bound: Path) -> None:
    _delete_fixture(bound)
    graph = graph_of(bound)
    assert [node.id for node in orphan_records(graph)] == ["evd-password-reset-expired-token-dev", BINDING]
    removed = prune_orphan_records(str(bound / "spec"), graph)
    assert [path.name for path in removed] == ["evd-password-reset-expired-token-dev.json", f"{BINDING}.json"]
    assert _record_files(bound) == []


def test_prune_keeps_a_record_that_still_has_a_target(bound: Path) -> None:
    _edit_binding(bound, lambda record: record.update(verifies=[FIXTURE, "fix-password-reset-reused-token"]))
    _delete_fixture(bound)
    assert orphan_records(graph_of(bound)) == []
    assert prune_orphan_records(str(bound / "spec"), graph_of(bound)) == []


def test_prune_still_passes_on_a_host_with_no_verification_records(host: Path) -> None:
    (host / "spec" / RECORDS / f"{BINDING}.json").unlink()
    code, out = _prune(host)
    assert code == 0 and out.strip() == "attest --prune: no orphan entries"


def test_prune_text_and_json_name_the_removed_records(bound: Path) -> None:
    _delete_fixture(bound)
    document = json.loads(_prune(bound, "--dry-run", "--json")[1])
    assert document["written"] is False
    assert document["pruned_records"] == [f"{RECORDS}/evd-password-reset-expired-token-dev.json", f"{RECORDS}/{BINDING}.json"]
    document = json.loads(_prune(bound, "--json")[1])
    assert document["written"] is True and len(document["pruned_records"]) == 2


def test_stage_edit_after_binding_gives_e330(host: Path) -> None:
    assert lint_verification_records(graph_of(host)) == []
    _edit_binding(host, lambda record: record.update(stage="ci"))
    (finding,) = lint_verification_records(graph_of(host))
    assert finding.code == "E330" and finding.node_id == BINDING
    assert "stage 'ci' does not match the stage 'dev'" in finding.message
    _edit_binding(host, lambda record: record.update(stage="dev"))
    assert lint_verification_records(graph_of(host)) == []


def test_a_retired_binding_is_not_a_stage_mismatch(host: Path) -> None:
    edit_doc(host, "02a_delivery_baseline.json", lambda doc: doc["environments"].update(qa={"scope": "out"}))
    _edit_binding(host, lambda record: record.update(stage="qa"))
    assert [error.code for error in lint_verification_records(graph_of(host))] == []


def test_unknown_environment_stage_gives_e334(host: Path) -> None:
    edit_doc(host, "02a_delivery_baseline.json", lambda doc: doc["environments"].update(qa={"scope": "in"}))
    edit_doc(host, "12_ci_gates.json", lambda doc: doc["jobs"].append({"job_id": "job-qa-smoke", "name": "QA smoke", "realises": ["qa"]}))
    record = {"verification_id": "ver-qa-smoke", "verifies": ["job-qa-smoke"], "stage": "ci", "commands": ["true"], "output_guard": "ok"}
    _write_record(host, VERIFICATION_URI, record, "ver-qa-smoke")
    (finding,) = lint_verification_records(graph_of(host))
    assert (finding.code, finding.node_id) == ("E334", "ver-qa-smoke")
    assert "environment 'qa' is not a stage" in finding.message


def test_a_proves_id_that_names_no_node_is_a_finding_and_a_renamed_one_is_not(host: Path) -> None:
    _edit_binding(host, lambda record: record.update(proves=[CRITERION, "ac-gone-1"]))
    (finding,) = lint_verification_records(graph_of(host))
    assert finding.code == PROVES_UNKNOWN_CODE and "'ac-gone-1'" in finding.message
    edit_doc(host, "04_fr_list.json", _alias_criterion)
    assert lint_verification_records(graph_of(host)) == []


def test_lint_passes_on_the_doc_12_20_records(host: Path) -> None:
    _write_record(host, VERIFICATION_URI, DOC_STAGING_BINDING, DOC_STAGING_BINDING["verification_id"])
    graph = graph_of(host)
    assert BINDING in graph.by_id and DOC_STAGING_BINDING["verification_id"] in graph.by_id
    assert lint_verification_records(graph) == []


def test_lint_findings_carry_the_merge_check_owner_and_file(host: Path) -> None:
    _edit_binding(host, lambda record: record.update(stage="staging", proves=[CRITERION, "ac-gone-1"]))
    findings = lint_verification_records(build_graph(str(host / "spec"), str(ROOT)))
    assert sorted(error.code for error in findings) == ["E330", PROVES_UNKNOWN_CODE]
    assert {(error.owner, error.file) for error in findings} == {("merge-check", f"{RECORDS}/{BINDING}.json")}


def test_the_records_check_of_spec_check_carries_the_lint_findings(host: Path) -> None:
    from specdev_tools.validation.spec_check import _records_result

    _edit_binding(host, lambda record: record.update(stage="staging"))
    result = _records_result(build_graph(str(host / "spec"), str(ROOT)), str(ROOT), str(host / "spec"))
    assert result["status"] == "FAIL" and "E330" in str(result)
