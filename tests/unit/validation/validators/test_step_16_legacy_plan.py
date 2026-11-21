"""Ruling L2: the plan schema is one strict shape, except that the plan of a legacy-closed milestone is not judged by it."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.core.errors import SpecError
from specdev_tools.lifecycle import anchor_store
from specdev_tools.validation.validate import validate_file
from specdev_tools.validation.validators.step_16 import is_legacy_closed_plan
from unit.lifecycle._support import MILESTONE, PLAN, closed_record, example_spec, load, toolkit_root

LEGACY_CLOSE = {"signed_off_by": "legacy-migration", "source": "14.status"}


def _make_1_1_1_plan(spec: Path) -> Path:
    """The example plan as a 1.1.1 plan holds it: the item carries ``spec_ref`` and no ``realises``."""
    path = spec / PLAN
    plan: dict[str, Any] = load(spec, PLAN)
    item = plan["plan"]["spec_alignment"]["checklist"][0]
    del item["realises"]
    item["spec_ref"] = {"type": "fr", "id": "fr-password-reset-confirm"}
    path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    return path


def _errors(spec: Path) -> list[SpecError]:
    return validate_file(toolkit_root(), str(spec / PLAN), spec_root=str(spec))


def _findings(spec: Path) -> list[str]:
    return [error.message for error in _errors(spec)]


def test_spec_ref_without_realises_ok_when_legacy_closed(tmp_path: Path) -> None:
    spec = example_spec(tmp_path)
    _make_1_1_1_plan(spec)
    anchor_store.write_row_state(spec, MILESTONE, "done", close=LEGACY_CLOSE, repo_root=toolkit_root())
    assert is_legacy_closed_plan(str(spec / PLAN), str(spec))
    assert not [message for message in _findings(spec) if "realises" in message or "spec_ref" in message]
    assert "E304" not in {error.code for error in _errors(spec)}  # no plan item realises a criterion, and none is asked to


def test_open_plan_with_only_spec_ref_fails(tmp_path: Path) -> None:
    spec = example_spec(tmp_path)
    _make_1_1_1_plan(spec)
    assert not is_legacy_closed_plan(str(spec / PLAN), str(spec))
    messages = " ".join(_findings(spec))
    assert "'realises' is a required property" in messages and "'spec_ref' was unexpected" in messages
    assert "E304" in {error.code for error in _errors(spec)}


def test_plan_closed_under_1_2_0_with_only_spec_ref_fails(tmp_path: Path) -> None:
    spec = example_spec(tmp_path)
    _make_1_1_1_plan(spec)
    anchor_store.write_row_state(spec, MILESTONE, "done", close=closed_record(), repo_root=toolkit_root())
    assert not is_legacy_closed_plan(str(spec / PLAN), str(spec))
    assert "'realises' is a required property" in " ".join(_findings(spec))


@pytest.mark.parametrize("without", ["milestone", "anchor"])
def test_a_plan_whose_milestone_row_cannot_be_found_is_not_legacy_closed(tmp_path: Path, without: str) -> None:
    spec = example_spec(tmp_path)
    anchor_store.write_row_state(spec, MILESTONE, "done", close=LEGACY_CLOSE, repo_root=toolkit_root())
    if without == "milestone":
        plan = load(spec, PLAN)
        del plan["milestone"]
        (spec / PLAN).write_text(json.dumps(plan), encoding="utf-8")
    else:
        (spec / "16_impl_context.json").unlink()
    assert not is_legacy_closed_plan(str(spec / PLAN), str(spec))
