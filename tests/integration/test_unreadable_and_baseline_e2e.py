"""M6a review round 1, fixer 2: unreadable spec files and the reasons of an unavailable baseline, run end to end.

Each test starts from a git copy of the worked example (``tests/integration/_step_gate_support.py``) and runs the CLI
in this process.
"""
from __future__ import annotations

import json
import os
import shutil
import stat
from pathlib import Path
from typing import Any

import pytest

from integration._step_gate_support import run_split, start_branch, step_gate_host
from unit.graph._synth import git
from unit.trace._lock_support import ROOT

STEP_FILE = "spec/04_fr_list.json"
NFR_FILE = "spec/07_nfrs.json"
requires_unprivileged = pytest.mark.skipif(os.geteuid() == 0, reason="root can read a file of mode 000")


def _flags(host: Path) -> list[str]:
    return ["--repo-root", str(ROOT), "--spec-root", str(host / "spec"), "--git-root", str(host)]


def _spec_check(capsys: pytest.CaptureFixture[str], host: Path, *flags: str) -> tuple[int, str, str]:
    return run_split(capsys, "spec-check", str(host / "spec"), *_flags(host), *flags)


def _backlog(capsys: pytest.CaptureFixture[str], host: Path) -> tuple[int, str, str]:
    return run_split(capsys, "upstream-backlog", str(host / "spec"), "--repo-root", str(ROOT))


def _unreadable_step_file(host: Path, how: str) -> Path:
    path = host / STEP_FILE
    if how == "mode000":
        path.chmod(0)
    else:
        path.unlink()
        path.mkdir()
    return path


def _restore(path: Path, how: str) -> None:
    if how == "mode000":
        path.chmod(stat.S_IRWXU)


HOWS = [pytest.param("mode000", marks=requires_unprivileged), "directory"]


def _unreadable_findings(output: str) -> list[dict[str, Any]]:
    return [f for f in json.loads(output)["checks"]["open-items"]["findings"] if f["code"] == "E520"]


@pytest.mark.parametrize("how", HOWS)
def test_plain_spec_check_reports_one_e520_for_an_unreadable_step_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], how: str
) -> None:
    host = step_gate_host(tmp_path / "h")
    path = _unreadable_step_file(host, how)
    try:
        code, out, err = _spec_check(capsys, host, "--json")
    finally:
        _restore(path, how)
    found = _unreadable_findings(out)
    assert code == 1 and "Traceback" not in err
    assert [(f["file"], f["owner"]) for f in found] == [("04_fr_list.json", "step:04")]


@pytest.mark.parametrize("how", HOWS)
def test_step_gate_goes_on_with_an_unreadable_step_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], how: str
) -> None:
    host = step_gate_host(tmp_path / "h")
    path = _unreadable_step_file(host, how)
    try:
        code, out, err = _spec_check(capsys, host, "--step", "05")
    finally:
        _restore(path, how)
    assert code == 1 and "fatal error" not in err and "RESULT: BLOCKED" in out
    assert sum("cannot read" in line and "04_fr_list.json" in line for line in out.splitlines()) == 1


@pytest.mark.parametrize("how", HOWS)
def test_step_gate_says_on_stderr_which_step_file_it_could_not_read(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], how: str
) -> None:
    """A file without permission and a folder named like the file get the same note."""
    host = step_gate_host(tmp_path / "h")
    path = _unreadable_step_file(host, how)
    try:
        _code, _out, err = _spec_check(capsys, host, "--step", "05")
    finally:
        _restore(path, how)
    assert _lines_with(err, "could not read") == ["specdev spec-check: could not read 04_fr_list.json; the answer may be incomplete"]


def test_waiting_is_off_when_an_artifact_of_open_items_cannot_be_read(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Items read before the unreadable file would explain the errors below them; the run must not trust a list that stops half way."""
    host = step_gate_host(tmp_path / "h", ["open_items", "broken_links_below_open_items"])
    code, out, _err = _spec_check(capsys, host, "--step", "05", "--json")
    assert code == 0 and len(json.loads(out)["step_gate"]["waiting"]) == 2

    (host / NFR_FILE).unlink()
    (host / NFR_FILE).mkdir()
    code, out, _err = _spec_check(capsys, host, "--step", "05", "--json")

    gate = json.loads(out)["step_gate"]
    assert code == 1 and gate["waiting"] == []
    assert [f["code"] for f in gate["blocking"] if f["code"] == "E700"] == ["E700", "E700"]


@pytest.mark.parametrize("how", HOWS)
def test_upstream_backlog_prints_one_e520_and_exits_2_for_an_unreadable_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], how: str
) -> None:
    host = step_gate_host(tmp_path / "h")
    path = _unreadable_step_file(host, how)
    try:
        code, out, err = _backlog(capsys, host)
    finally:
        _restore(path, how)
    lines = err.strip().splitlines()
    assert code == 2 and out == ""
    assert len(lines) == 1 and lines[0].startswith("E520 UNRESOLVED_INPUT ") and "04_fr_list.json" in lines[0]


# --- the baseline: its failures and its reasons -------------------------------------------------------------------

def test_a_baseline_the_checks_cannot_read_is_unavailable_with_its_reason(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``07_nfrs.json`` is ``[]`` at the merge-base and restored on the branch: no traceback, ``base: unavailable``."""
    host = step_gate_host(tmp_path / "h")
    good = (host / NFR_FILE).read_text(encoding="utf-8")
    (host / NFR_FILE).write_text("[]\n", encoding="utf-8")
    git(host, "commit", "-q", "-am", "damage the nfrs")
    start_branch(host)
    (host / NFR_FILE).write_text(good, encoding="utf-8")
    git(host, "commit", "-q", "-am", "restore the nfrs")
    code, out, err = _spec_check(capsys, host, "--step", "05")
    assert code == 0 and "Traceback" not in err
    assert "base: unavailable" in out
    assert "note: the checks could not run on the baseline tree: " in err


def test_a_branch_that_adds_the_spec_folder_says_so(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A host's first adoption branch: the base commit holds no spec folder, one plain note, no exception text."""
    host = step_gate_host(tmp_path / "h")
    first = git(host, "rev-parse", "HEAD")
    git(host, "rm", "-rq", "spec")
    git(host, "commit", "-q", "-m", "no spec yet")
    base = git(host, "rev-parse", "HEAD")
    start_branch(host)
    git(host, "checkout", "-q", first, "--", "spec")
    git(host, "commit", "-q", "-m", "adopt the spec")
    code, out, err = _spec_check(capsys, host, "--step", "05")
    assert code in (0, 1) and "Traceback" not in err
    assert "base: unavailable" in out
    assert _lines_with(err, "note:") == [
        f"note: the spec folder is not in the base commit {base[:12]}: every error of an earlier step counts as new"
    ]


def _lines_with(text: str, word: str) -> list[str]:
    return [line for line in text.splitlines() if word in line]


def test_unknown_base_ref_says_so(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    host = step_gate_host(tmp_path / "h")
    _code, out, err = _spec_check(capsys, host, "--step", "05", "--base-ref", "nope")
    assert "base: unavailable" in out
    assert _lines_with(err, "note:") == ["note: nope does not name a commit"]


def test_no_base_ref_found_says_so(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    host = step_gate_host(tmp_path / "h")
    git(host, "branch", "-m", "odd")
    _code, out, err = _spec_check(capsys, host, "--step", "05")
    assert "base: unavailable" in out
    assert _lines_with(err, "note:") == ["note: no base ref found (origin/main, origin/master, main, master); pass --base-ref"]


def test_a_repository_without_a_commit_says_so(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    host = step_gate_host(tmp_path / "h")
    git(host, "update-ref", "-d", "refs/heads/main")
    _code, out, err = _spec_check(capsys, host, "--step", "05")
    assert "base: unavailable" in out
    assert _lines_with(err, "note:") == ["note: no commit yet"]


def test_a_folder_that_is_not_a_repository_says_so(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    host = step_gate_host(tmp_path / "h")
    for entry in (host / ".git").iterdir():
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()
    (host / ".git").rmdir()
    _code, out, err = _spec_check(capsys, host, "--step", "05")
    assert "base: unavailable" in out
    assert _lines_with(err, "note:") == ["note: not a git repository"]


def test_a_shallow_clone_without_common_history_says_so(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = step_gate_host(tmp_path / "src")
    start_branch(source, "side")
    (source / "spec" / "extras" / "side.txt").write_text("side\n", encoding="utf-8")
    git(source, "add", "-A")
    git(source, "commit", "-q", "-m", "side")
    git(source, "checkout", "-q", "main")
    (source / "spec" / "extras" / "main.txt").write_text("main\n", encoding="utf-8")
    git(source, "add", "-A")
    git(source, "commit", "-q", "-m", "main moves on")
    clone = tmp_path / "clone"
    git(tmp_path, "clone", "-q", "--depth", "1", "--no-single-branch", "--branch", "side", f"file://{source}", str(clone))
    _code, out, err = _spec_check(capsys, clone, "--step", "05", "--base-ref", "origin/main")
    assert "base: unavailable" in out
    assert _lines_with(err, "note:") == ["note: no common history with origin/main (a shallow clone?)"]


def test_the_head_note_says_only_uncommitted_changes_count(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    host = step_gate_host(tmp_path / "h")
    start_branch(host)
    _code, _out, err = _spec_check(capsys, host, "--step", "05")
    assert _lines_with(err, "note:") == ["note: the baseline is HEAD itself: only uncommitted changes count as new"]
