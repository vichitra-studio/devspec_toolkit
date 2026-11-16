"""Plan discovery: ``find_plan`` maps a milestone id to the plan file that names it in its file-level key."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.lifecycle.plans import find_plan


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
    _write_plan(tmp_path, "a_unusable.json", body)
    wanted = _write_plan(tmp_path, "b_good.json", {"milestone": "ms-a"})
    assert find_plan(tmp_path, "ms-a") == wanted


def test_find_plan_returns_the_first_match_in_name_order(tmp_path: Path) -> None:
    first = _write_plan(tmp_path, "a_plan.json", {"milestone": "ms-a"})
    _write_plan(tmp_path, "b_plan.json", {"milestone": "ms-a"})
    assert find_plan(tmp_path, "ms-a") == first
