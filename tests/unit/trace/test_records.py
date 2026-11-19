"""Verification and evidence records (WI-M5-15): the two schemas, the registry kinds and the ``records`` check (E774)."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.core.errors import SpecError
from specdev_tools.core.loaders import iter_spec_artifacts
from specdev_tools.core.schema_validate import validate_data_against_schema
from specdev_tools.graph.build import build_graph
from specdev_tools.graph.check import run_graph_check
from specdev_tools.trace.lockfile import Lock
from specdev_tools.trace.records import check_records
from specdev_tools.trace.suspects import lock_links, missing_entries
from specdev_tools.validation.spec_check import run_spec_check_json

from ..graph._synth import EXAMPLE_SPEC, ROOT, copy_example, write_json
from ._lock_support import lock_for

VERIFICATION_URI = "vc:extras:verification-record"
EVIDENCE_URI = "vc:extras:evidence-record"
VER_REL = "extras/verification/ver-password-reset-expired-token.json"
FIXTURE = "fix-password-reset-expired-token"
OUTPUT_HASH = "sha256:" + "c0ffee5e" * 8

DOC_VERIFICATION = {
    "verification_id": "ver-password-reset-expired-token",
    "verifies": [FIXTURE],
    "stage": "dev",
    "commands": ['npx vitest run tests/contract/password-reset-confirm.test.ts -t "expired token"'],
    "output_guard": "expired token .*passed",
}
DOC_STAGING_VERIFICATION = {
    "verification_id": "ver-reset-email-delivery-staging",
    "verifies": ["fix-reset-email-delivery-time"],
    "stage": "staging",
    "commands": ["./scripts/synthetic-reset.sh --env staging --max-seconds 60"],
    "output_guard": "delivered in [0-9]+ s",
}
DOC_RUN = {
    "evidence_id": "evd-20261202-0007",
    "about": ["ver-password-reset-expired-token"],
    "exit_code": 0,
    "guard_matched": True,
    "output_hash": OUTPUT_HASH,
    "tested_tree": "9a41c7e2",
    "stage": "dev",
    "installed_versions": {"tp-argon2": "0.41.1"},
}
DOC_ATTESTATION = {
    "evidence_id": "evd-attest-reset-link-copy",
    "type": "attestation",
    "about": [FIXTURE],
    "tested_tree": "9a41c7e2",
    "stage": "staging",
}


def _wrap(uri: str, *records: dict[str, Any]) -> dict[str, Any]:
    return {"$schema": uri, "records": list(records)}


def _verification_file(record: dict[str, Any]) -> dict[str, Any]:
    return _wrap(VERIFICATION_URI, record)


def _evidence_file(record: dict[str, Any]) -> dict[str, Any]:
    return _wrap(EVIDENCE_URI, record)


def _spec(tmp_path: Path, **files: dict[str, Any]) -> Path:
    """The worked example in *tmp_path* with each ``<name>=<document>`` written to ``extras/verification/<name>.json``."""
    spec = copy_example(tmp_path / "spec")
    for name, document in files.items():
        write_json(spec, f"extras/verification/{name.replace('_', '-')}.json", document)
    return spec


def _findings(spec: Path) -> list[SpecError]:
    return check_records(str(spec), str(ROOT), build_graph(str(spec), str(ROOT)))


def _messages(errors: list[SpecError]) -> str:
    return "\n".join(error.message for error in errors)


def test_verification_record_validates_section12_example() -> None:
    for record in (DOC_VERIFICATION, DOC_STAGING_VERIFICATION):
        assert validate_data_against_schema(str(ROOT), _verification_file(record)) == []
    without_stage = {key: value for key, value in DOC_VERIFICATION.items() if key != "stage"}
    assert validate_data_against_schema(str(ROOT), _verification_file(without_stage)) == []


def test_evidence_record_validates_run_and_attestation() -> None:
    assert validate_data_against_schema(str(ROOT), _evidence_file(DOC_RUN)) == []
    assert validate_data_against_schema(str(ROOT), _evidence_file(DOC_ATTESTATION)) == []
    run_with_default_type = {key: value for key, value in DOC_RUN.items() if key != "stage"}
    assert validate_data_against_schema(str(ROOT), _evidence_file(run_with_default_type)) == []


def _without(record: dict[str, Any], key: str) -> dict[str, Any]:
    return {name: value for name, value in record.items() if name != key}


@pytest.mark.parametrize(
    ("document", "word"),
    [
        (_verification_file(_without(DOC_VERIFICATION, "output_guard")), "output_guard"),
        (_verification_file({**DOC_VERIFICATION, "output_guard": ""}), "non-empty"),
        (_verification_file({**DOC_VERIFICATION, "stage": "production"}), "production"),
        (_verification_file({**DOC_VERIFICATION, "commands": []}), "non-empty"),
        (_verification_file({**DOC_VERIFICATION, "verifies": []}), "non-empty"),
        (_verification_file({**DOC_VERIFICATION, "verification_id": "evd-password-reset"}), "does not match"),
        (_evidence_file({**DOC_RUN, "stage": "prod-ish"}), "prod-ish"),
        (_evidence_file({**DOC_RUN, "output_hash": "sha256:c0ffee5e"}), "does not match"),
        (_evidence_file(_without(DOC_RUN, "guard_matched")), "guard_matched"),
        (_evidence_file(_without(DOC_RUN, "exit_code")), "exit_code"),
        (_evidence_file({**DOC_ATTESTATION, "exit_code": 0}), "False schema"),
        (_evidence_file({**DOC_RUN, "type": "attestation"}), "False schema"),
        (_evidence_file({**DOC_RUN, "about": []}), "non-empty"),
    ],
    ids=[
        "no-guard", "empty-guard", "unknown-stage", "no-commands", "no-targets", "wrong-prefix",
        "unknown-evidence-stage", "short-hash", "run-without-guard-result", "run-without-exit-code",
        "attestation-with-exit-code", "attestation-with-run-fields", "about-empty",
    ],
)
def test_schema_rejects_missing_guard_unknown_stage_or_bad_hash(document: dict[str, Any], word: str) -> None:
    violations = validate_data_against_schema(str(ROOT), document)
    assert violations
    assert any(word in message for _path, message in violations)


def _finding_codes(spec: Path) -> list[tuple[str, str, str | None]]:
    """Every finding of the ``graph`` and ``records`` checks of ``spec-check`` over *spec* as ``(check, code, node id)``."""
    checks = run_spec_check_json(str(ROOT), str(spec))[1]["checks"]
    return [(name, item["code"], item.get("node_id")) for name, check in checks.items() if name in {"graph", "records"} for item in check.get("findings", [])]


def test_record_links_resolve_and_unresolved_is_e700(tmp_path: Path) -> None:
    clean = _spec(tmp_path / "clean")
    assert _findings(clean) == [] and _finding_codes(clean) == []
    broken = _verification_file({**DOC_VERIFICATION, "verifies": ["fix-no-such-fixture"]})
    spec = _spec(tmp_path / "broken", ver_password_reset_expired_token=broken)
    assert _findings(spec) == []
    assert _finding_codes(spec) == [("graph", "E700", "ver-password-reset-expired-token")]


def test_a_link_to_a_former_id_resolves(tmp_path: Path) -> None:
    spec = _spec(tmp_path, ver_password_reset_expired_token=_verification_file({**DOC_VERIFICATION, "verifies": ["fix-old-name"]}))
    fixtures = json.loads((spec / "08_fixtures.json").read_text(encoding="utf-8"))
    item = next(row for row in fixtures["fixtures"] if row["fixture_id"] == FIXTURE)
    item["aliases"] = ["fix-old-name"]
    write_json(spec, "08_fixtures.json", fixtures)
    graph = build_graph(str(spec), str(ROOT))
    assert check_records(str(spec), str(ROOT), graph) == []
    assert run_graph_check(str(spec), str(ROOT), graph=graph, lock=lock_for(graph, spec.parent)) == []


def test_records_have_no_lock_entries_and_no_e701(tmp_path: Path) -> None:
    spec = _spec(tmp_path, evd_20261202_0007=_evidence_file(DOC_RUN))
    graph = build_graph(str(spec), str(ROOT))
    records = {node.id for node in graph.nodes if node.role == "record" and node.kind in {"verification-record", "evidence-record"}}
    assert records == {"ver-password-reset-expired-token", "evd-20261202-0007"}
    assert {item.holder.id for item in lock_links(graph)}.isdisjoint(records)
    lock = lock_for(graph, spec.parent)
    assert missing_entries(graph, lock) == []
    assert records.isdisjoint({entry.source for entry in lock.entries})
    assert run_graph_check(str(spec), str(ROOT), graph=graph, lock=lock) == []
    unlocked = missing_entries(graph, Lock(()))
    assert unlocked and records.isdisjoint({link.holder.id for link in unlocked})


def test_artifact_loader_skips_records(tmp_path: Path) -> None:
    spec = _spec(tmp_path, evd_20261202_0007=_evidence_file(DOC_RUN))
    listed = {Path(path).name for path in iter_spec_artifacts(str(spec))}
    assert "ver-password-reset-expired-token.json" not in listed
    assert "evd-20261202-0007.json" not in listed
    assert "00_charter.json" in listed


def test_record_file_with_two_records_is_refused_by_the_schema(tmp_path: Path) -> None:
    second = {**DOC_VERIFICATION, "verification_id": "ver-password-reset-reused-token", "verifies": ["fix-password-reset-reused-token"]}
    document = _wrap(VERIFICATION_URI, DOC_VERIFICATION, second)
    assert any("maxItems" in message or "too long" in message for _path, message in validate_data_against_schema(str(ROOT), document))
    spec = _spec(tmp_path, ver_password_reset_expired_token=document)
    errors = _findings(spec)
    assert [error.code for error in errors] == ["E774"]
    assert errors[0].file == VER_REL and "records" in errors[0].message
    assert "verification_id" not in errors[0].message and len(errors[0].message) < 200  # not the whole value


def test_evidence_record_is_not_read_as_a_verification_record(tmp_path: Path) -> None:
    spec = _spec(tmp_path, evd_20261202_0007=_evidence_file(DOC_RUN))
    graph = build_graph(str(spec), str(ROOT))
    in_records = [(node.id, node.kind) for node in graph.nodes if node.file.startswith("extras/verification/")]
    assert in_records == [
        ("evd-20261202-0007", "evidence-record"),
        ("ver-password-reset-expired-token", "verification-record"),
    ]
    assert not graph.dups
    assert run_graph_check(str(spec), str(ROOT), graph=graph, lock=lock_for(graph, spec.parent)) == []
    assert validate_data_against_schema(str(ROOT), {**_evidence_file(DOC_RUN), "$schema": VERIFICATION_URI})
    assert validate_data_against_schema(str(ROOT), {**_verification_file(DOC_VERIFICATION), "$schema": EVIDENCE_URI})
    assert _findings(spec) == []


@pytest.mark.parametrize(
    ("name", "document", "word"),
    [
        ("ver-password-reset-expired-token", _evidence_file(DOC_RUN), "no record found"),
        ("evd-20261202-0007", _verification_file(DOC_VERIFICATION), "no record found"),
        ("ver-other-name", _verification_file(DOC_VERIFICATION), "is not the record id"),
        ("notes", {"hello": "world"}, "$schema"),
    ],
    ids=["evidence-in-a-ver-file", "verification-in-an-evd-file", "stem-differs-from-id", "no-schema"],
)
def test_a_record_file_must_be_the_kind_and_the_id_its_name_declares(
    tmp_path: Path, name: str, document: dict[str, Any], word: str
) -> None:
    spec = _spec(tmp_path)
    (spec / VER_REL).unlink()
    write_json(spec, f"extras/verification/{name}.json", document)
    errors = _findings(spec)
    assert errors
    assert {error.code for error in errors} == {"E774"}
    assert word in _messages(errors)


def test_an_unreadable_record_file_is_e774(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    (spec / "extras" / "verification" / "ver-broken.json").write_text("{not json", encoding="utf-8")
    assert [(error.code, error.file) for error in _findings(spec)] == [("E774", "extras/verification/ver-broken.json")]


def test_registry_holds_verification_and_evidence_kinds() -> None:
    registry = json.loads((ROOT / "tools" / "entry_key_registry.json").read_text(encoding="utf-8"))["registry"]
    held = {
        key: [(array["kind"], array["role"], array["id_field"], array["array_path"]) for array in registry[key]["arrays"]]
        for key in ("extras/verification/ver-*.json", "extras/verification/evd-*.json")
    }
    assert held == {
        "extras/verification/ver-*.json": [("verification-record", "record", "verification_id", ".records")],
        "extras/verification/evd-*.json": [("evidence-record", "record", "evidence_id", ".records")],
    }
    assert {registry[key]["step"] for key in held} == {"extras"}


def test_check_records_accepts_about_array_for_at_deploy_record(tmp_path: Path) -> None:
    """``about`` is an array of node ids that the graph resolves, one by one (the M8 at-deploy record uses the same field)."""
    plan_item = next(node.id for node in build_graph(str(EXAMPLE_SPEC), str(ROOT)).nodes if node.kind == "plan-item")
    attestation = {**DOC_ATTESTATION, "about": [plan_item, FIXTURE]}
    spec = _spec(tmp_path, evd_attest_reset_link_copy=_evidence_file(attestation))
    assert _finding_codes(spec) == []
    unresolved = {**DOC_ATTESTATION, "about": [plan_item, "PWRESET_NO_SUCH_01", "fix-no-such-fixture"]}
    other = _spec(tmp_path / "other", evd_attest_reset_link_copy=_evidence_file(unresolved))
    assert _finding_codes(other) == [("graph", "E700", "evd-attest-reset-link-copy")] * 2


def test_spec_check_reports_records_as_one_check(tmp_path: Path) -> None:
    clean = run_spec_check_json(str(ROOT), str(copy_example(tmp_path / "clean")))[1]["checks"]["records"]
    assert clean["status"] == "PASS" and clean["findings"] == []
    broken = _spec(tmp_path / "broken", ver_password_reset_expired_token=_verification_file({**DOC_VERIFICATION, "output_guard": ""}))
    errors, context = run_spec_check_json(str(ROOT), str(broken))
    assert context["checks"]["records"]["status"] == "FAIL"
    assert [finding["code"] for finding in context["checks"]["records"]["findings"]] == ["E774"]
    assert "E774" in {error.code for error in errors}


def test_spec_check_skips_records_when_there_is_no_record_file(tmp_path: Path) -> None:
    spec = copy_example(tmp_path / "spec")
    (spec / VER_REL).unlink()
    assert run_spec_check_json(str(ROOT), str(spec))[1]["checks"]["records"] == {"status": "SKIP", "reason": "no record files"}


def test_the_worked_example_record_is_the_section12_record() -> None:
    document = json.loads((EXAMPLE_SPEC / VER_REL).read_text(encoding="utf-8"))
    assert document == _verification_file(copy.deepcopy(DOC_VERIFICATION))
