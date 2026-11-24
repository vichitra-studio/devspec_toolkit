"""``origin`` of a finding (``vc:infra:findings``): optional, three values, and a ``regression`` is never ``introduced-on-branch``."""
from __future__ import annotations

import json
from pathlib import Path

from specdev_tools.validation.validate import validate_file

ROOT = Path(__file__).resolve().parents[3]


def _errors(tmp_path: Path, **finding_fields: str) -> list[str]:
    finding = {"kind": "bug", "location": "fr-password-reset#description", "signature": "abc12345", "message": "m", "severity": "P1"}
    document = {"$schema": "vc:infra:findings", "round": 1, "scope": "step-04", "generated_at": 1700000000, "findings": [finding | finding_fields]}
    path = tmp_path / "findings.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return [error.message for error in validate_file(str(ROOT), str(path))]


def test_bug_with_origin_introduced_on_branch_validates(tmp_path: Path) -> None:
    assert _errors(tmp_path, kind="bug", origin="introduced-on-branch") == []


def test_regression_with_origin_introduced_on_branch_is_rejected(tmp_path: Path) -> None:
    assert _errors(tmp_path, kind="regression", origin="introduced-on-branch")


def test_regression_with_pre_existing_origin_validates(tmp_path: Path) -> None:
    assert _errors(tmp_path, kind="regression", origin="pre-existing-on-main") == []


def test_unknown_origin_is_rejected(tmp_path: Path) -> None:
    assert _errors(tmp_path, origin="made-up")


def test_a_finding_without_origin_still_validates(tmp_path: Path) -> None:
    assert _errors(tmp_path) == []
