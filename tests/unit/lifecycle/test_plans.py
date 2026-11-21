"""Plan discovery and the freeze: ``find_plan`` maps a milestone id to the plan file that names it in its file-level key."""
from __future__ import annotations

import functools
import json
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.core.errors import FindingError
from specdev_tools.lifecycle import anchor_store, frozen, plans
from specdev_tools.core.plan_files import find_plan, plan_files
from specdev_tools.validation.open_items import check_open_items

from ._support import MILESTONE, PLAN, closed_record, example_spec, toolkit_root


def _write_plan(spec_root: Path, name: str, body: Any) -> Path:
    plan_dir = spec_root / "impl_context"
    plan_dir.mkdir(exist_ok=True)
    path = plan_dir / name
    path.write_text(body if isinstance(body, str) else json.dumps(body), encoding="utf-8")
    return path


def test_find_plan_by_file_level_milestone(tmp_path: Path) -> None:
    _write_plan(tmp_path, "ms_a_plan.json", {"milestone": "ms-a", "plan": {}})
    wanted = _write_plan(tmp_path, "ms_b_plan.json", {"milestone": "ms-b", "plan": {}})
    assert find_plan(tmp_path, "ms-b") == wanted
    assert find_plan(str(tmp_path), "ms-b") == wanted


def test_find_plan_matches_the_key_not_the_file_name(tmp_path: Path) -> None:
    wanted = _write_plan(tmp_path, "ms_maintain_backup_plan.json", {"milestone": "ms-maintain-backup-recovery"})
    assert find_plan(tmp_path, "ms-maintain-backup-recovery") == wanted
    assert find_plan(tmp_path, "ms-maintain-backup") is None


def test_find_plan_returns_none_when_no_plan_names_the_milestone(tmp_path: Path) -> None:
    _write_plan(tmp_path, "ms_a_plan.json", {"milestone": "ms-a"})
    assert find_plan(tmp_path, "ms-other") is None


def test_find_plan_returns_none_without_an_impl_context_directory(tmp_path: Path) -> None:
    assert find_plan(tmp_path, "ms-a") is None


@pytest.mark.parametrize(
    "body",
    [
        {"plan": {}},  # a plan written before the key existed
        {"milestone": ["ms-a"]},
        {"milestone": 7},
        ["ms-a"],
        "{not json,",
        "",
    ],
)
def test_find_plan_skips_a_file_it_cannot_use(tmp_path: Path, body: Any) -> None:
    _write_plan(tmp_path, "ms_a_unusable_plan.json", body)
    wanted = _write_plan(tmp_path, "ms_b_good_plan.json", {"milestone": "ms-a"})
    assert find_plan(tmp_path, "ms-a") == wanted


def test_a_stray_json_file_in_impl_context_is_no_plan(tmp_path: Path) -> None:
    # `PLAN_FILE_GLOB` is the one spelling of "a plan file": `aaa_notes.json` holding a `milestone` key is not one.
    _write_plan(tmp_path, "aaa_notes.json", {"milestone": "ms-x"})
    wanted = _write_plan(tmp_path, "ms_b_plan.json", {"milestone": "ms-x"})
    assert [p.name for p in plan_files(tmp_path)] == ["ms_b_plan.json"]
    assert find_plan(tmp_path, "ms-x") == wanted


def test_find_plan_returns_the_first_match_in_name_order(tmp_path: Path) -> None:
    first = _write_plan(tmp_path, "ms_a_plan.json", {"milestone": "ms-a"})
    _write_plan(tmp_path, "ms_b_plan.json", {"milestone": "ms-a"})
    assert find_plan(tmp_path, "ms-a") == first


def _error_of(call: Any) -> Any:
    with pytest.raises(FindingError) as caught:
        call()
    return caught.value.error


def test_require_plan_missing_key_message(tmp_path: Path) -> None:
    _write_plan(tmp_path, "ms_old_plan.json", {"plan": {}})
    error = _error_of(lambda: plans.require_plan(tmp_path, "ms-a"))
    assert (error.code, error.subcode) == ("E803", "MILESTONE_KEY_MISSING")
    assert "add it with `specdev json patch <plan file> '.milestone' '\"<milestone-id>\"'` (the plan has no `milestone` key)" in error.message


def test_require_plan_names_the_milestone_no_plan_carries(tmp_path: Path) -> None:
    wanted = _write_plan(tmp_path, "ms_a_plan.json", {"milestone": "ms-a"})
    assert plans.require_plan(tmp_path, "ms-a") == wanted
    error = _error_of(lambda: plans.require_plan(tmp_path, "ms-b"))
    assert (error.code, error.subcode) == ("E803", "MILESTONE_NOT_FOUND")
    assert "ms-b" in error.message


def test_legacy_plan_with_spec_ref_readable(tmp_path: Path) -> None:
    legacy = {
        "milestone": "ms-a",
        "milestone_ref": "ms-a",
        "plan": {"spec_alignment": {"checklist": [{"id": "A_ONE_01", "spec_ref": {"task_id": "tk-a"}}]}},
        "execution": {"final_status": "complete"},
        "review": {"fixture_status": {"ci_status": "green"}},
    }
    path = _write_plan(tmp_path, "ms_a_plan.json", legacy)
    assert find_plan(tmp_path, "ms-a") == path
    assert plans.plan_hash(path).startswith("sha256:")


def test_is_frozen_follows_the_row_status(tmp_path: Path) -> None:
    spec = example_spec(tmp_path)
    plan = spec / PLAN
    assert not frozen.is_frozen(spec, MILESTONE) and not frozen.is_frozen_path(spec, plan)
    anchor_store.write_row_state(spec, MILESTONE, "done", close=closed_record(), repo_root=toolkit_root())
    assert frozen.is_frozen(spec, MILESTONE) and frozen.is_frozen_path(spec, plan)
    assert not frozen.is_frozen(spec, "ms-other")
    assert not frozen.is_frozen_path(spec, spec / "16_impl_context.json")


def test_frozen_partial_makes_an_open_item_legacy_at_the_merge_gate(tmp_path: Path) -> None:
    spec = example_spec(tmp_path)
    plan = spec / PLAN
    document = json.loads(plan.read_text(encoding="utf-8"))
    document["execution"] = {"emergent_ambiguities": [{"id": "amb-one", "description": "Is the limit per user?", "about": ["tc-confirm-expired-token"]}]}
    plan.write_text(json.dumps(document, indent=2), encoding="utf-8")
    is_frozen = functools.partial(frozen.is_frozen_path, spec)

    def codes() -> list[tuple[str, str]]:
        return [(error.code, error.owner or "") for error in check_open_items(str(spec), gate="merge", frozen=is_frozen)]

    live = codes()
    anchor_store.write_row_state(spec, MILESTONE, "done", close=closed_record(), repo_root=toolkit_root())
    legacy = codes()
    assert [code for code, _ in live] == ["E631"]
    assert [code for code, _ in legacy] == ["W633"]


def test_plan_hash_stable_under_key_order(tmp_path: Path) -> None:
    first = _write_plan(tmp_path, "a.json", '{"b": 1, "a": {"y": [1, 2], "x": "é"}}')
    second = _write_plan(tmp_path, "b.json", '{\n  "a": {"x": "é", "y": [1, 2]},\n  "b": 1\n}\n')
    third = _write_plan(tmp_path, "c.json", '{"a": {"x": "é", "y": [2, 1]}, "b": 1}')
    assert plans.plan_hash(first) == plans.plan_hash(second) != plans.plan_hash(third)
    assert plans.plan_hash(first).startswith("sha256:") and len(plans.plan_hash(first)) == len("sha256:") + 64


def test_plan_hash_refuses_a_file_that_is_not_json(tmp_path: Path) -> None:
    assert _error_of(lambda: plans.plan_hash(_write_plan(tmp_path, "x.json", "{not json"))).code == "E520"


def _closed_example(tmp_path: Path) -> Path:
    spec = example_spec(tmp_path)
    close = closed_record(plan_hash=plans.plan_hash(spec / PLAN))
    anchor_store.write_row_state(spec, MILESTONE, "done", close=close, repo_root=toolkit_root())
    return spec


def test_frozen_plan_drift_reports_e827_after_a_hand_edit(tmp_path: Path) -> None:
    spec = _closed_example(tmp_path)
    assert frozen.frozen_plan_drift(spec, MILESTONE) is None
    assert frozen.check_frozen_plans(str(spec)).errors == ()
    plan = spec / PLAN
    plan.write_text(plan.read_text(encoding="utf-8").replace("30 minutes", "31 minutes"), encoding="utf-8")
    message = frozen.frozen_plan_drift(spec, MILESTONE)
    assert message is not None and "ms_account_recovery_plan.json" in message and "changed after milestone ms-account-recovery was closed" in message
    (finding,) = frozen.check_frozen_plans(str(spec)).errors
    assert (finding.code, finding.node_id, finding.file) == ("E827", MILESTONE, "impl_context/ms_account_recovery_plan.json")


def test_a_recorded_migration_makes_the_edited_plan_current(tmp_path: Path) -> None:
    spec = _closed_example(tmp_path)
    plan = spec / PLAN
    plan.write_text(plan.read_text(encoding="utf-8").replace("30 minutes", "31 minutes"), encoding="utf-8")
    assert frozen.frozen_plan_drift(spec, MILESTONE) is not None
    anchor_store.append_close_migration(spec, MILESTONE, plans.plan_hash(plan), "wording", repo_root=toolkit_root())
    assert frozen.frozen_plan_drift(spec, MILESTONE) is None


def test_frozen_plan_drift_is_silent_for_a_legacy_close_without_a_hash(tmp_path: Path) -> None:
    spec = example_spec(tmp_path)
    anchor_store.write_row_state(spec, MILESTONE, "done", close={"signed_off_by": "legacy-migration", "source": "14.status"}, repo_root=toolkit_root())
    plan = spec / PLAN
    plan.write_text(plan.read_text(encoding="utf-8").replace("30 minutes", "31 minutes"), encoding="utf-8")
    assert frozen.frozen_plan_drift(spec, MILESTONE) is None


def test_the_last_migration_decides_the_hash_a_closed_plan_must_have() -> None:
    first, second, third = (f"sha256:{digit * 64}" for digit in "123")
    close = {"plan_hash": first, "migrations": [{"hash_after": second}, {"hash_after": third}]}
    assert plans.stored_plan_hash(close) == third
    assert plans.stored_plan_hash({"plan_hash": first, "migrations": []}) == first
    assert plans.stored_plan_hash({"plan_hash": first}) == first
    assert plans.stored_plan_hash(None) is None


def test_a_closed_plan_is_compared_with_the_last_of_two_migrations(tmp_path: Path) -> None:
    spec = example_spec(tmp_path)
    now = plans.plan_hash(spec / PLAN)
    close = closed_record(plan_hash="sha256:" + "1" * 64)
    close["migrations"] = [{"hash_after": "sha256:" + "2" * 64, "note": "first"}, {"hash_after": now, "note": "second"}]
    anchor_store.write_row_state(spec, MILESTONE, "done", close=close, repo_root=toolkit_root())
    assert frozen.frozen_plan_drift(spec, MILESTONE) is None
    close["migrations"].reverse()
    anchor_store.write_row_state(spec, MILESTONE, "done", close=close, repo_root=toolkit_root())
    assert frozen.frozen_plan_drift(spec, MILESTONE) is not None


def test_a_plan_saved_under_another_name_is_not_a_missing_key(tmp_path: Path) -> None:
    saved = _write_plan(tmp_path, "account_recovery_plan.json", {"milestone": "ms-a", "plan": {}})
    error = _error_of(lambda: plans.require_plan(tmp_path, "ms-a"))
    assert (error.code, error.subcode) == ("E803", "MILESTONE_NOT_FOUND")
    assert "align" not in error.message and "impl_context/ms_*_plan.json" in error.message and "`milestone` key" in error.message
    named = saved.rename(saved.with_name("ms_a_plan.json"))
    assert plans.require_plan(tmp_path, "ms-a") == named
