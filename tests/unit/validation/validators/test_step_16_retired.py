"""WI-M8-11: the step-16 codes whose input the plan schema lost are gone, and so is the 16b route."""
from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.core.errors import ERROR_CODES
from specdev_tools.core.step_paths import get_step_from_path, refine_impl_context_substep
from specdev_tools.validation.validate import DEEP_VALIDATORS, validate_file
from specdev_tools.validation.validators import step_16a
from unit.lifecycle._support import PLAN, example_spec, load, toolkit_root

ROOT = Path(toolkit_root())
RETIRED = ("E301", "E302", "E305", "E306", "E307", "W599", "W600", "W601")
SOURCE_FOLDERS = ("tools/specdev_tools", "prompts", ".claude", "docs/developers")
SOURCE_SUFFIXES = {".py", ".md", ".json", ".yaml", ".yml"}
REWRITES_TAG = "M8 " + "rewrites"
LINKED_TEST_NAME = "LINKED_TEST_FILE" + "_NOT_FOUND"


def _source_files(*folders: str) -> list[Path]:
    return [
        path for folder in folders for path in sorted((ROOT / folder).rglob("*"))
        if path.is_file() and path.suffix in SOURCE_SUFFIXES and "__pycache__" not in path.parts and ".egg-info" not in str(path)
    ]


@pytest.mark.parametrize("code", RETIRED)
def test_retired_codes_are_not_registered(code: str) -> None:
    assert code not in ERROR_CODES


def test_e303_stays_registered_for_governance_check() -> None:
    assert ERROR_CODES["E303"] == "COMMIT_MESSAGE_MISMATCH"
    emitters = [path for path in _source_files("tools/specdev_tools") if path.name != "errors.py" and '"E303"' in path.read_text(encoding="utf-8")]
    assert [path.name for path in emitters] == ["governance.py"]


def test_step_16b_validator_module_is_gone() -> None:
    assert not (ROOT / "tools/specdev_tools/validation/validators/step_16b.py").exists()
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("specdev_tools.validation.validators.step_16b")


def test_16b_route_maps_to_16a_validator(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pipeline step 16b is still a step of ``step_order.json``: ``validate --step 16b`` runs the 16a checks."""
    monkeypatch.setattr(step_16a, "validate_step_16a", lambda *args: ["16a ran"])
    assert DEEP_VALIDATORS["16b"]({}, "root", {}) == ["16a ran"]


def test_plan_with_execution_records_validates_as_16a_16c_no_16b_dispatch(tmp_path: Path) -> None:
    spec = example_spec(tmp_path)
    plan: dict[str, Any] = load(spec, PLAN)
    plan["execution"] = {"records": [{"record_id": "rec-0001", "about": ["PWRESET_CONFIRM_EXPIRED_01"], "action": "a01", "outcome": "done"}]}
    assert get_step_from_path(PLAN) == "16a"
    assert refine_impl_context_substep("16a", plan) == "16a"
    plan["review"] = {"verdict": "needs_work"}
    assert refine_impl_context_substep("16a", plan) == "16c"
    path = spec / PLAN
    path.write_text(json.dumps(plan), encoding="utf-8")
    assert not [e for e in validate_file(str(ROOT), str(path), spec_root=str(spec)) if "execution" in e.message and "unexpected" in e.message]


def test_validate_module_imports() -> None:
    importlib.import_module("specdev_tools.validation.validate")


def test_no_m8_rewrites_tag_remains() -> None:
    found = [
        str(path.relative_to(ROOT)) for path in _source_files("tools/specdev_tools", "tests")
        if REWRITES_TAG in path.read_text(encoding="utf-8") and path != Path(__file__).resolve()
    ]
    assert found == []


def test_no_linked_test_file_not_found_in_tools_prompts_claude_docs() -> None:
    found = [str(path.relative_to(ROOT)) for path in _source_files(*SOURCE_FOLDERS) if LINKED_TEST_NAME in path.read_text(encoding="utf-8")]
    claude_md = ROOT / "CLAUDE.md"
    assert found == [] and LINKED_TEST_NAME not in claude_md.read_text(encoding="utf-8")
