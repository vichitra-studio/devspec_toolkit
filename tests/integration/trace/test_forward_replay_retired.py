"""File-level forward replay is retired (WI-M5-04): the trace lock reports what it used to, whitespace cannot clear it.

The worked example sits in a git repository; ``spec-check``, ``validate_dir``, ``stale`` and the deprecated
``forward-replay-check`` read the same lock.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from specdev_tools import cli
from specdev_tools.validation.spec_check import run_spec_check_json
from specdev_tools.validation.validate import validate_dir

from unit.graph._synth import ROOT, git, run_cli
from unit.trace._lock_support import EXAMPLE_HOST
from unit.trace.test_suspects import CRITERION, Example

FR_FILE = "04_fr_list.json"
EDIT = " Also reject a token issued for another account."
DEPRECATION = "forward-replay-check is deprecated; use `specdev stale`"
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


def _commit(example: Example, message: str) -> None:
    git(example.host, "add", "-A")
    git(example.host, "commit", "-q", "-m", message)


def _spec_check_checks(example: Example) -> dict[str, Any]:
    _errors, context = run_spec_check_json(str(ROOT), str(example.spec), git_root=str(example.host), spec_root=str(example.spec))
    return context["checks"]


def _finding_codes(check: dict[str, Any]) -> list[str]:
    return [finding["code"] for finding in check["findings"]]


def _alias(example: Example, *args: str, capsys: pytest.CaptureFixture[str]) -> tuple[int, dict[str, Any], str]:
    """Run ``forward-replay-check --json``: the exit code, the parsed stdout and the stderr."""
    argv = [
        "specdev", "forward-replay-check", "--json", "--base-ref", BASE_BRANCH, *args,
        "--repo-root", str(ROOT), "--spec-root", str(example.spec), "--git-root", str(example.host),
    ]
    with patch("specdev_tools.cli.check_venv", return_value=None), patch.object(sys, "argv", argv):
        try:
            cli.main()
            code = 0
        except SystemExit as exc:
            code = int(exc.code) if isinstance(exc.code, int) else 1
    captured = capsys.readouterr()
    return code, json.loads(captured.out), captured.err


def _alias_codes(document: dict[str, Any]) -> list[str]:
    return [error["code"] for error in document["errors"]]


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


def test_forward_replay_check_alias_returns_suspects_and_e555(host: Example, capsys: pytest.CaptureFixture[str]) -> None:
    """The deprecated command still gives ``/specdev-review --with-replay`` a relational signal: E761, E763 and E555."""
    _edit_criterion(host)
    host.drop_entries(lambda entry: entry.source == "api-password-reset-confirm")
    fr_path = host.spec / FR_FILE
    document = json.loads(fr_path.read_text(encoding="utf-8"))
    dropped_id = "ac-password-reset-1"
    assert dropped_id in json.dumps(document)
    fr_path.write_text(json.dumps(document, indent=2).replace(f'"{dropped_id}"', '"ac-renamed-1"') + "\n", encoding="utf-8")
    _commit(host, "feature")
    code, out, err = _alias(host, capsys=capsys)
    codes = _alias_codes(out)
    assert code == 1
    assert {"E761", "E763", "E555"} <= set(codes)
    assert any(dropped_id in error["message"] for error in out["errors"] if error["code"] == "E555")
    assert DEPRECATION in err


def test_forward_replay_check_alias_step_limits_suspects_to_holder_step(host: Example, capsys: pytest.CaptureFixture[str]) -> None:
    """``--step 06`` keeps the suspects held by step 06 nodes (the slice of ``stale --step 06``) and the E555 of step 06's file only."""
    _edit_criterion(host)
    everything = _alias(host, capsys=capsys)[1]
    sliced = _alias(host, "--step", "06", capsys=capsys)[1]
    all_suspects = [error for error in everything["errors"] if error["code"] == "E763"]
    kept = [error for error in sliced["errors"] if error["code"] == "E763"]
    assert 0 < len(kept) < len(all_suspects)
    assert {error["node_id"] for error in kept} <= {error["node_id"] for error in all_suspects}
    graph = host.graph()
    assert {graph.by_id[error["node_id"]].step for error in kept} == {"06"}
    assert len({graph.by_id[error["node_id"]].step for error in all_suspects}) > 1


def test_alias_deprecation_line_goes_to_stderr_only(host: Example, capsys: pytest.CaptureFixture[str]) -> None:
    _code, document, err = _alias(host, capsys=capsys)
    assert DEPRECATION in err and "errors" in document


def _rename_criterion_and_commit(example: Example) -> None:
    """Rename ``ac-password-reset-1`` in the FR list and commit: step 04's file drops an id (E555, W598)."""
    fr_path = example.spec / FR_FILE
    fr_path.write_text(fr_path.read_text(encoding="utf-8").replace('"ac-password-reset-1"', '"ac-renamed-1"'), encoding="utf-8")
    _commit(example, "rename")


def _per_file_findings(document: dict[str, Any]) -> set[tuple[str, str | None]]:
    return {(error["code"], error.get("file")) for error in document["errors"] if error["code"] in {"E555", "W598", "W550"}}


def test_forward_replay_check_step_filters_the_id_regressions_by_their_file(host: Example, capsys: pytest.CaptureFixture[str]) -> None:
    """The id-regression findings name their file, so ``--step 04`` keeps them and ``--step 06`` drops them (they were dropped for every step)."""
    _rename_criterion_and_commit(host)
    everything = _per_file_findings(_alias(host, capsys=capsys)[1])
    assert {"E555", "W598"} <= {code for code, _file in everything}
    assert {file for _code, file in everything} == {f"spec/{FR_FILE}"}
    assert _per_file_findings(_alias(host, "--step", "04", capsys=capsys)[1]) == everything
    assert _per_file_findings(_alias(host, "--step", "06", capsys=capsys)[1]) == set()


def test_forward_replay_check_reads_the_base_through_a_symlinked_spec_root(host: Example, tmp_path: Path) -> None:
    """A spec root spelled through a symlink is the same folder: no W550 ``unable_to_read_base`` for every spec file."""
    from specdev_tools.validation.forward_replay_check import check_forward_replay

    _rename_criterion_and_commit(host)
    link = tmp_path / "link"
    link.symlink_to(host.host, target_is_directory=True)
    findings = check_forward_replay(str(ROOT), base_ref=BASE_BRANCH, git_root=str(host.host), spec_root=str(link / "spec"))
    assert "W550" not in {error.code for error in findings}
    assert "E555" in {error.code for error in findings}
