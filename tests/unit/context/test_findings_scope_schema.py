"""The ``scope`` of a findings file (``vc:infra:findings``) takes a plan-item id as the plan schema spells it (ruling L12)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from specdev_tools.validation.validate import validate_file

ROOT = Path(__file__).resolve().parents[3]


def _errors(tmp_path: Path, scope: str) -> list[str]:
    path = tmp_path / "findings.json"
    path.write_text(
        json.dumps({"$schema": "vc:infra:findings", "round": 1, "scope": scope, "generated_at": 1700000000, "findings": []}),
        encoding="utf-8",
    )
    return [error.message for error in validate_file(str(ROOT), str(path))]


@pytest.mark.parametrize("scope", ["PWRESET_CONFIRM_EXPIRED_01", "step-04", "ms-batch-1-plan", "steps-04-05-cross"])
def test_scope_accepts_a_plan_item_id_and_the_old_forms(tmp_path: Path, scope: str) -> None:
    assert _errors(tmp_path, scope) == []


@pytest.mark.parametrize("scope", ["PWRESET CONFIRM", "Pw_Reset", "PWRESET-CONFIRM", ""])
def test_scope_refuses_a_space_a_mixed_case_id_or_nothing(tmp_path: Path, scope: str) -> None:
    errors = _errors(tmp_path, scope)
    assert errors and all("scope" in error for error in errors)
