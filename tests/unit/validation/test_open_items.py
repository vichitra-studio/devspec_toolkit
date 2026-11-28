"""Tests for the open-item gates."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from specdev_tools.core.config import reset_config
from specdev_tools.core.errors import PROMOTABLE_PAIRS, SpecError
from specdev_tools.validation.open_items import check_open_items, default_frozen
from specdev_tools.validation.check_registry import check_result

from .._ambiguity_support import plan_doc, unified_item
from ..graph._synth import write_json

ROOT = Path(__file__).resolve().parents[3]
SIX_AMBIGUITIES = ROOT / "tests" / "fixtures" / "analysis" / "upstream_backlog" / "plan_with_six_ambiguities.json"
STEP_FILE = "05_interface_contracts.json"
ANCHOR_FILE = "16_impl_context.json"
PLAN_A = "impl_context/ms_alpha_plan.json"
PLAN_B = "impl_context/ms_beta_plan.json"


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

    result = check_result(check_open_items(spec, gate="step"))

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


def test_an_item_with_no_id_is_named_so_without_a_double_space(tmp_path: Path) -> None:
    write_json(tmp_path, STEP_FILE, {"ambiguities": [{"description": "no id", "about": ["fr-login"]}]})
    (error,) = check_open_items(tmp_path, gate="step")
    assert error.message.startswith("open item (no id) in ") and "  " not in error.message and error.node_id is None


def _unreadable_04_folder(tmp_path: Path) -> list[SpecError]:
    write_json(tmp_path, STEP_FILE, {"ambiguities": [unified_item("amb-x")]})
    (tmp_path / "04_fr_list.json").mkdir()
    return check_open_items(tmp_path, gate="step")


def test_an_unreadable_file_is_one_e520_owned_by_its_step_that_says_it_cannot_read(tmp_path: Path) -> None:
    unreadable = [e for e in _unreadable_04_folder(tmp_path) if e.code == "E520"]
    assert [(e.file, e.owner) for e in unreadable] == [("04_fr_list.json", "step:04")]
    assert "cannot read" in unreadable[0].message


def test_the_e520_of_an_unreadable_file_ends_the_list(tmp_path: Path) -> None:
    errors = _unreadable_04_folder(tmp_path)
    assert [e.code for e in errors][-1] == "E520" and [e.code for e in errors].count("E520") == 1


def test_an_unreadable_plan_file_is_owned_by_a_plan_step(tmp_path: Path) -> None:
    (tmp_path / "impl_context" / "ms_a_plan.json").mkdir(parents=True)
    (error,) = check_open_items(tmp_path, gate="merge")
    assert error.code == "E520" and error.owner in {"step:16a", "step:16b", "step:16c"}
