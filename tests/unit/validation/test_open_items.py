"""Tests for the open-item gates and the deletion of resolved items (WI-M6a-06)."""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from specdev_tools.core.config import reset_config
from specdev_tools.core.errors import PROMOTABLE_PAIRS, FindingError, SpecError
from specdev_tools.trace.lockfile import LockError, with_write_lock
from specdev_tools.validation.open_items import check_open_items, default_frozen, delete_resolved_items
from specdev_tools.validation.check_registry import _check_result
from specdev_tools.validation.validate import validate_file

from .._ambiguity_support import plan_doc, unified_item
from ..graph._synth import write_json

ROOT = Path(__file__).resolve().parents[3]
EXAMPLE_SPEC = ROOT / "tests" / "fixtures" / "graph_example" / "spec"
SIX_AMBIGUITIES = ROOT / "tests" / "fixtures" / "analysis" / "upstream_backlog" / "plan_with_six_ambiguities.json"
STEP_FILE = "05_interface_contracts.json"
ANCHOR_FILE = "16_impl_context.json"
PLAN_A = "impl_context/ms_alpha_plan.json"
PLAN_B = "impl_context/ms_beta_plan.json"


def _legacy(item_id: str, status: str) -> dict:
    return {"id": item_id, "description": "old question", "severity": "low", "status": status, "impact": ["x"]}


def _is_frozen_only(*names: str):
    frozen = {Path(name).name for name in names}
    return lambda plan_path: plan_path.name in frozen


def _codes(errors: list[SpecError]) -> list[str]:
    return [error.code for error in errors]


@pytest.fixture
def spec(tmp_path: Path) -> Path:
    """A spec folder with one unified item in step 05, one in plan alpha's ``plan.ambiguities``, one in plan beta."""
    folder = tmp_path / "spec"
    write_json(folder, STEP_FILE, {"ambiguities": [unified_item("amb-reset-seed", decision="use the seed value")]})
    write_json(folder, PLAN_A, plan_doc(emergent=[unified_item("amb-emergent")]))
    write_json(folder, PLAN_B, plan_doc(plan_items=[unified_item("amb-beta")]))
    return folder


@pytest.fixture
def example_copy(tmp_path: Path) -> Path:
    """A copy of the worked example's spec folder (the graph a write plans from)."""
    destination = tmp_path / "example_spec"
    shutil.copytree(EXAMPLE_SPEC, destination)
    return destination


def test_step_gate_item_is_w630_owned_by_its_step(spec: Path) -> None:
    errors = check_open_items(spec, gate="step")

    by_node = {error.node_id: error for error in errors}
    assert _codes(errors) == ["W630"] * 3
    assert by_node["amb-reset-seed"].owner == "step:05"
    assert by_node["amb-emergent"].owner == "step:16b"
    assert by_node["amb-beta"].owner == "step:16a"
    assert by_node["amb-reset-seed"].file == STEP_FILE
    assert "about fr-login" in by_node["amb-reset-seed"].message


@pytest.mark.parametrize(
    ("extra", "answer"),
    [({"decision": "use the seed value"}, "known: apply in the batch pass"), ({}, "needed from the operator")],
)
def test_w630_says_whether_the_answer_is_known(tmp_path: Path, extra: dict, answer: str) -> None:
    write_json(tmp_path, STEP_FILE, {"ambiguities": [unified_item("amb-x", **extra)]})

    (error,) = check_open_items(tmp_path, gate="step")

    assert f"answer {answer}" in error.message


def test_w630_names_the_missing_kind_and_its_parent(tmp_path: Path) -> None:
    write_json(tmp_path, STEP_FILE, {"ambiguities": [unified_item("amb-x", missing_kind="acceptance-criterion", about=["fr-a"])]})

    (error,) = check_open_items(tmp_path, gate="step")

    assert "about missing acceptance-criterion in fr-a" in error.message


def test_merge_gate_item_is_e631_owned_by_merge_check(spec: Path) -> None:
    errors = check_open_items(spec, gate="merge")

    assert _codes(errors) == ["E631"] * 3
    assert {error.owner for error in errors} == {"merge-check"}


def test_deleting_the_item_removes_e631(spec: Path) -> None:
    write_json(spec, STEP_FILE, {"ambiguities": []})
    (spec / PLAN_A).unlink()
    (spec / PLAN_B).unlink()

    assert check_open_items(spec, gate="merge") == []


def test_close_gate_item_in_the_milestone_plan_is_e632(spec: Path) -> None:
    errors = check_open_items(spec, gate="close", plan_path=spec / PLAN_A)

    assert _codes(errors) == ["E632"]
    assert errors[0].node_id == "amb-emergent"
    assert errors[0].owner == "close-gate"


def test_close_gate_ignores_another_milestones_plan(spec: Path) -> None:
    errors = check_open_items(spec, gate="close", plan_path=spec / PLAN_B)

    assert [error.node_id for error in errors] == ["amb-beta"]


def test_close_gate_needs_the_plan_path(spec: Path) -> None:
    with pytest.raises(ValueError, match="plan_path"):
        check_open_items(spec, gate="close")


def test_item_in_a_frozen_plan_is_w633_and_a_live_plan_item_is_e631(spec: Path) -> None:
    errors = check_open_items(spec, gate="merge", frozen=_is_frozen_only(PLAN_A))

    by_node = {error.node_id: error.code for error in errors}
    assert by_node == {"amb-reset-seed": "E631", "amb-emergent": "W633", "amb-beta": "E631"}
    assert {error.owner for error in errors} == {"merge-check"}


def test_step_gate_leaves_out_the_items_of_a_frozen_plan(spec: Path) -> None:
    errors = check_open_items(spec, gate="step", frozen=_is_frozen_only(PLAN_A))

    assert sorted(error.node_id for error in errors) == ["amb-beta", "amb-reset-seed"]


def test_default_frozen_freezes_no_plan(spec: Path) -> None:
    assert default_frozen(spec / PLAN_A) is False
    assert _codes(check_open_items(spec, gate="merge")).count("W633") == 0


@pytest.fixture
def _fresh_config():
    reset_config()
    yield
    reset_config()


def test_w630_is_not_promotable_under_warnings_as_errors(
    spec: Path, monkeypatch: pytest.MonkeyPatch, _fresh_config: None
) -> None:
    monkeypatch.setenv("SPECDEV_WARNINGS_AS_ERRORS", "1")
    monkeypatch.delenv("SPECDEV_PROMOTE_CODES", raising=False)
    reset_config()

    result = _check_result(check_open_items(spec, gate="step"))

    assert result["status"] == "WARN"
    assert result["error_count"] == 0
    assert {error.code for error in result["errors"]} == {"W630"}
    assert not {"W630", "W633", "E631", "E632"} & set(PROMOTABLE_PAIRS)


def test_legacy_fixture_gives_one_summary_w630_and_five_e631(tmp_path: Path) -> None:
    (tmp_path / "impl_context").mkdir()
    shutil.copy(SIX_AMBIGUITIES, tmp_path / "impl_context" / "ms_custom_pages_brand_plan.json")

    step = check_open_items(tmp_path, gate="step")
    merge = check_open_items(tmp_path, gate="merge")

    assert _codes(step) == ["W630"]
    assert step[0].message.startswith("5 legacy open items in impl_context/ms_custom_pages_brand_plan.json")
    assert step[0].owner == "step:16b"
    assert _codes(merge) == ["E631"] * 5


def test_anchor_items_are_live_open_items(tmp_path: Path) -> None:
    write_json(tmp_path, ANCHOR_FILE, {"plan": {"ambiguities": [unified_item("amb-anchor")]}})

    step = check_open_items(tmp_path, gate="step", frozen=lambda _path: True)
    merge = check_open_items(tmp_path, gate="merge", frozen=lambda _path: True)

    assert (_codes(step), step[0].owner) == (["W630"], "step:16")
    assert _codes(merge) == ["E631"]


def test_an_unreadable_file_ends_the_list_with_e520(tmp_path: Path) -> None:
    write_json(tmp_path, "04_fr_list.json", {"ambiguities": [unified_item("amb-first")]})
    (tmp_path / STEP_FILE).write_text("{not json", encoding="utf-8")

    errors = check_open_items(tmp_path, gate="merge")

    assert _codes(errors) == ["E631", "E520"]
    assert errors[1].message.startswith("cannot read ")
    assert errors[1].file == STEP_FILE


def _legacy_items() -> list[dict]:
    return [_legacy("amb-done-1", "resolved"), _legacy("amb-open", "tracking"), _legacy("amb-done-2", "resolved")]


def _example_with_items(spec_dir: Path) -> None:
    """Resolved legacy items in the anchor and in both arrays of the example plan, plus items that must stay."""
    anchor = json.loads((spec_dir / ANCHOR_FILE).read_text(encoding="utf-8"))
    anchor["plan"]["ambiguities"] = _legacy_items()
    write_json(spec_dir, ANCHOR_FILE, anchor)
    plan_file = spec_dir / "impl_context" / "ms_account_recovery_plan.json"
    plan = json.loads(plan_file.read_text(encoding="utf-8"))
    plan["plan"]["ambiguities"] = [_legacy("amb-plan-done", "resolved"), unified_item("amb-plan-open")]
    plan["execution"] = {"emergent_ambiguities": [unified_item("amb-keep"), _legacy("amb-emergent-done", "resolved")]}
    write_json(plan_file.parent, plan_file.name, plan)


def _all_ids(spec_dir: Path, relative: str, *keys: str) -> list[str]:
    doc = json.loads((spec_dir / relative).read_text(encoding="utf-8"))
    for key in keys:
        doc = doc[key]
    return [item["id"] for item in doc]


def test_delete_resolved_items_dry_run_counts_and_changes_nothing(example_copy: Path) -> None:
    _example_with_items(example_copy)
    before = {path: path.read_bytes() for path in example_copy.rglob("*.json")}

    counts = delete_resolved_items(example_copy, ROOT)

    assert counts == {ANCHOR_FILE: 2, "impl_context/ms_account_recovery_plan.json": 2}
    assert {path: path.read_bytes() for path in example_copy.rglob("*.json")} == before


def test_delete_resolved_items_apply_keeps_unresolved_and_the_plan_validates(example_copy: Path) -> None:
    plan_file = example_copy / "impl_context" / "ms_account_recovery_plan.json"
    baseline = [error.code for error in validate_file(str(ROOT), str(plan_file), include_id_slice=False)]
    _example_with_items(example_copy)

    counts = delete_resolved_items(example_copy, ROOT, apply=True)

    assert counts == {ANCHOR_FILE: 2, "impl_context/ms_account_recovery_plan.json": 2}
    assert _all_ids(example_copy, ANCHOR_FILE, "plan", "ambiguities") == ["amb-open"]
    relative = "impl_context/ms_account_recovery_plan.json"
    assert _all_ids(example_copy, relative, "plan", "ambiguities") == ["amb-plan-open"]
    assert _all_ids(example_copy, relative, "execution", "emergent_ambiguities") == ["amb-keep"]
    assert [error.code for error in validate_file(str(ROOT), str(plan_file), include_id_slice=False)] == baseline
    assert delete_resolved_items(example_copy, ROOT) == {}


def test_delete_resolved_items_refuses_beside_an_unreadable_spec_file(example_copy: Path) -> None:
    _example_with_items(example_copy)
    (example_copy / "04_fr_list.json").write_text("{not json", encoding="utf-8")

    for apply in (False, True):
        with pytest.raises(FindingError) as refused:
            delete_resolved_items(example_copy, ROOT, apply=apply)
        assert refused.value.error.code == "E520"
        assert "04_fr_list.json" in refused.value.error.message
    assert len(_all_ids(example_copy, ANCHOR_FILE, "plan", "ambiguities")) == 3


def test_delete_resolved_items_refuses_while_the_write_lock_is_held(example_copy: Path) -> None:
    _example_with_items(example_copy)

    with with_write_lock(str(example_copy)), pytest.raises(LockError) as refused:
        delete_resolved_items(example_copy, ROOT, apply=True)

    assert refused.value.error.code == "E769"
    assert len(_all_ids(example_copy, ANCHOR_FILE, "plan", "ambiguities")) == 3


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores the read-only mode")
def test_delete_resolved_items_on_a_read_only_folder_ends_in_e520(example_copy: Path) -> None:
    _example_with_items(example_copy)
    original_mode = example_copy.stat().st_mode
    example_copy.chmod(0o555)
    try:
        with pytest.raises(FindingError) as refused:
            delete_resolved_items(example_copy, ROOT, apply=True)
    finally:
        example_copy.chmod(original_mode)

    assert refused.value.error.code == "E520"
    assert refused.value.error.message.startswith(f"cannot write {ANCHOR_FILE}: ")
    assert len(_all_ids(example_copy, ANCHOR_FILE, "plan", "ambiguities")) == 3


def test_an_item_with_no_id_is_named_so_without_a_double_space(tmp_path: Path) -> None:
    write_json(tmp_path, STEP_FILE, {"ambiguities": [{"description": "no id", "about": ["fr-login"]}]})
    (error,) = check_open_items(tmp_path, gate="step")
    assert error.message.startswith("open item (no id) in ") and "  " not in error.message and error.node_id is None


def test_an_unreadable_file_ends_the_list_with_one_e520_owned_by_its_step(tmp_path: Path) -> None:
    write_json(tmp_path, STEP_FILE, {"ambiguities": [unified_item("amb-x")]})
    (tmp_path / "04_fr_list.json").mkdir()
    errors = check_open_items(tmp_path, gate="step")
    unreadable = [e for e in errors if e.code == "E520"]
    assert [(e.file, e.owner) for e in unreadable] == [("04_fr_list.json", "step:04")]
    assert "cannot read" in unreadable[0].message and errors[-1] is unreadable[0]


def test_an_unreadable_plan_file_is_owned_by_a_plan_step(tmp_path: Path) -> None:
    (tmp_path / "impl_context" / "ms_a_plan.json").mkdir(parents=True)
    (error,) = check_open_items(tmp_path, gate="merge")
    assert error.code == "E520" and error.owner in {"step:16a", "step:16b", "step:16c"}
