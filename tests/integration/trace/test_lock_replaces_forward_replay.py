"""The trace lock replaces file-level forward replay (WI-M5-04, WI-M6c-02): whitespace cannot clear a replay.

The worked example sits in a git repository; ``spec-check``, ``validate_dir`` and ``stale`` read the same lock.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.validation.spec_check import run_spec_check_json
from specdev_tools.validation.validate import validate_dir

from unit.graph._synth import ROOT, git, run_cli
from unit.trace._lock_support import EXAMPLE_HOST
from unit.trace.test_suspects import CRITERION, Example

EDIT = " Also reject a token issued for another account."
BASE_BRANCH = "main"
FEATURE_BRANCH = "feature"


@pytest.fixture
def host(tmp_path: Path) -> Example:
    """The worked example (spec, seed docs and a current lock) committed on ``main``, with the branch ``feature`` checked out."""
    root = tmp_path / "host"
    shutil.copytree(EXAMPLE_HOST, root)
    git(root, "init", "-q", "-b", BASE_BRANCH)
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "base")
    git(root, "checkout", "-q", "-b", FEATURE_BRANCH)
    return Example(root)


def _edit_criterion(example: Example) -> None:
    example.edit_item(CRITERION, lambda item: item.update(text=item["text"] + EDIT))


def _spec_check_checks(example: Example) -> dict[str, Any]:
    _errors, context = run_spec_check_json(str(ROOT), str(example.spec), git_root=str(example.host), spec_root=str(example.spec))
    return context["checks"]


def _finding_codes(check: dict[str, Any]) -> list[str]:
    return [finding["code"] for finding in check["findings"]]


def test_whitespace_touch_of_downstream_files_does_not_clear_replay(host: Example) -> None:
    """DEVSPEC-224 verification 1: the old check cleared a replay once every downstream file was in the diff."""
    _edit_criterion(host)
    for path in sorted(host.spec.glob("[0-9][0-9]*_*.json")):
        path.write_text(json.dumps(json.loads(path.read_text(encoding="utf-8")), indent=4) + "\n\n", encoding="utf-8")
    trace_lock = _spec_check_checks(host)["trace-lock"]
    assert trace_lock["status"] == "FAIL"
    assert "E763" in _finding_codes(trace_lock)


def test_all_missing_downstream_reported_not_first_only(host: Example) -> None:
    """DEVSPEC-224 verification 2: a step 04 edit (no link targets a step 03 node) leaves the suspects of every untouched downstream step listed, not the first."""
    _edit_criterion(host)
    code, out = run_cli(
        "stale", "--json", "--repo-root", str(ROOT), "--spec-root", str(host.spec), "--git-root", str(host.host)
    )
    assert code == 0, out
    steps = {step["step"] for step in json.loads(out)["steps"]}
    graph = host.graph()
    flagged = {graph.by_id[error["node_id"]].step for error in _spec_check_checks(host)["trace-lock"]["findings"] if error["code"] == "E763"}
    assert {"05", "06"} <= steps
    assert {"05", "06"} <= flagged


def test_validate_dir_runs_suspect_check(host: Example) -> None:
    """The CI path (``validate-all``) reports the suspect links, default on, with no flag."""
    _edit_criterion(host)
    failures = validate_dir(str(ROOT), str(host.spec), git_root=str(host.host), spec_root=str(host.spec))
    assert "E763" in {error.code for error in failures}


def test_validate_dir_reports_nothing_for_a_current_lock(host: Example) -> None:
    failures = validate_dir(str(ROOT), str(host.spec), git_root=str(host.host), spec_root=str(host.spec))
    assert {"E761", "E762", "E763", "E882"}.isdisjoint(error.code for error in failures)
