"""Reading a stored evidence record: only a well-formed run record is evidence; anything else reads as no evidence (the records check reports it)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.verify.records import evidence_from_item, read_evidence, record_file

RUN: dict[str, Any] = {
    "evidence_id": "evd-alpha-dev", "about": ["ver-alpha"], "type": "run", "stage": "dev", "tested_tree": "9a41c7e2",
    "exit_code": 0, "guard_matched": True, "output_hash": "sha256:" + "c0ffee5e" * 8, "installed_versions": {},
}


def _store(folder: Path, records: list[dict[str, Any]]) -> None:
    (folder / record_file("evd-alpha-dev")).write_text(json.dumps({"$schema": "vc:extras:evidence-record", "records": records}), encoding="utf-8")


def test_a_well_formed_run_record_is_evidence(tmp_path: Path) -> None:
    _store(tmp_path, [RUN])
    evidence = read_evidence(str(tmp_path), "evd-alpha-dev")
    assert evidence is not None and evidence.about == ("ver-alpha",) and evidence.passed


@pytest.mark.parametrize("change", [{"stage": "qa"}, {"type": "install-check"}, {"type": "attestation"}, {"about": []}, {"exit_code": "0"}])
def test_a_record_that_is_not_a_well_formed_run_record_is_no_evidence(change: dict[str, Any]) -> None:
    assert evidence_from_item({**RUN, **change}) is None


def test_a_file_with_two_records_or_none_is_no_evidence(tmp_path: Path) -> None:
    _store(tmp_path, [RUN, {**RUN, "evidence_id": "evd-other-dev"}])
    assert read_evidence(str(tmp_path), "evd-alpha-dev") is None
    _store(tmp_path, [])
    assert read_evidence(str(tmp_path), "evd-alpha-dev") is None


def test_a_record_file_with_two_records_is_read_as_no_record_for_signoff_and_deploy(tmp_path: Path) -> None:
    """The one reading of "the record" of a record file is exactly one: sign-off and at-deploy files agree (``check-records`` reports the second record)."""
    from specdev_tools.verify.records import deploy_records, signoff_records

    one = {"signoff_id": "so-ms-a-0001", "about": ["ms-a"], "tree": "t", "git_author": {"name": "n", "email": "e"}}
    two = {**one, "signoff_id": "so-ms-a-0002"}
    signoffs = tmp_path / "extras" / "signoff"
    signoffs.mkdir(parents=True)
    (signoffs / "so-ms-a-0001.json").write_text(json.dumps({"records": [one]}), encoding="utf-8")
    (signoffs / "so-ms-a-0002.json").write_text(json.dumps({"records": [two, one]}), encoding="utf-8")
    assert [r.signoff_id for r in signoff_records(tmp_path, "ms-a")] == ["so-ms-a-0001"]
    verification = tmp_path / "extras" / "verification"
    verification.mkdir(parents=True)
    (verification / "dep-0001.json").write_text(json.dumps({"records": [{"deploy_id": "dep-0001"}]}), encoding="utf-8")
    (verification / "dep-0002.json").write_text(json.dumps({"records": [{"deploy_id": "dep-0002"}, {"deploy_id": "dep-0003"}]}), encoding="utf-8")
    assert [r["deploy_id"] for r in deploy_records(tmp_path)] == ["dep-0001"]
