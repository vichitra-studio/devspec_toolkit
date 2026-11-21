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
