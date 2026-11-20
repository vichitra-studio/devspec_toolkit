"""``--git-root`` absent means the host root derived from the spec folder, for every command that reads seed texts (M5 round 2, G1-1).

Before the fix the default was the current folder, so from any other folder the clean worked example showed 13 suspect
links (every seed text read as missing) and ``attest --yes`` stamped ``missing:<seed>`` hashes into the lock.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from specdev_tools.trace.lockfile import lock_path
from specdev_tools.validation.spec_check import run_spec_check_json

from unit.graph._synth import ROOT, git, run_cli
from unit.trace._lock_support import EXAMPLE_HOST
from unit.trace.test_suspects import Example

FR = "fr-password-reset-request"
STEPS = ("00", "01", "02", "02a", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12", "13", "14", "15", "16a")


@pytest.fixture
def host(tmp_path: Path) -> Example:
    root = tmp_path / "work" / "host"
    shutil.copytree(EXAMPLE_HOST, root)
    git(root, "init", "-q", "-b", "main")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "one")
    return Example(root)


# Every M5 command that reads seed texts (and the two that read git history), in a form that writes nothing.
READING_COMMANDS = {
    "stale": ["stale"],
    "stale-json": ["stale", "--json"],
    "attest-step-preview": ["attest", "--step", "00"],
    "attest-node-preview": ["attest", "asm-member-controls-email"],
    "attest-dry-run": ["attest", "--step", "00", "--yes", "--dry-run"],
    "coverage": ["coverage"],
    "step-ready": ["step", "ready", "05"],
    "json-patch-dry-run": ["json", "patch", "--id", FR, ".statement", '"A member can ask for a reset link."', "--dry-run"],
    "json-insert-dry-run": ["json", "insert", "--id", FR, ".acceptance_criteria", '{"criterion_id": "ac-password-reset-request-3", "scope": "in", "text": "Given x, when y, then z."}', "--dry-run"],
    "node-rename-dry-run": ["node", "rename", FR, "fr-password-reset-ask", "--dry-run"],
    "step-create-dry-run": ["step", "create", "15", "--from", "draft_15.json", "--dry-run"],
    "diff": ["diff", "HEAD", "HEAD"],
    "trace-since": ["trace", "PWRESET_CONFIRM_EXPIRED_01", "--recipe", "16b", "--since", "HEAD"],
}


def _run(args: list[str], example: Example, *, git_root: bool) -> tuple[int, str]:
    flags = ["--repo-root", str(ROOT), "--spec-root", str(example.spec)]
    return run_cli(*args, *flags, *(["--git-root", str(example.host)] if git_root else []))


@pytest.mark.parametrize("name", sorted(READING_COMMANDS))
def test_every_reading_command_gives_the_same_output_from_another_folder(
    name: str, host: Example, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shutil.move(host.spec / "15_scaffold.json", host.host / "draft_15.json")
    host.edit_seed()
    other = tmp_path / "elsewhere"
    other.mkdir()
    monkeypatch.chdir(other)
    args = READING_COMMANDS[name]
    given = _run(args, host, git_root=True)
    derived = _run(args, host, git_root=False)
    assert derived == given
    assert "missing:" not in derived[1]
    if name in ("stale", "step-ready"):
        assert "no pending replay" not in derived[1] and "step 05: ready" not in derived[1]


def test_attest_yes_from_another_folder_leaves_spec_check_clean(host: Example, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    host.edit_seed()
    other = tmp_path / "elsewhere"
    other.mkdir()
    monkeypatch.chdir(other)
    for step in STEPS:
        _run(["attest", "--step", step, "--yes"], host, git_root=False)
    code, out = _run(["stale"], host, git_root=True)
    assert code == 0, out
    assert "missing:" not in Path(lock_path(str(host.spec))).read_text(encoding="utf-8")
    monkeypatch.chdir(host.host)
    errors, _context = run_spec_check_json(str(ROOT), str(host.spec), git_root=str(host.host))
    assert [e.message for e in errors if e.code == "E763"] == []


@pytest.mark.parametrize("command", ["spec-check", "validate-all"])
def test_spec_check_and_validate_all_derive_the_host_root_from_the_spec_folder(
    command: str, host: Example, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """H1-1: without ``--git-root`` both read the seed texts under the folder that holds the spec folder, not the toolkit root or the current folder (64 false E763 before the fix)."""
    other = tmp_path / "elsewhere"
    other.mkdir()
    monkeypatch.chdir(other)
    flags = ["--repo-root", str(ROOT), "--spec-root", str(host.spec)]
    given = run_cli(command, str(host.spec), *flags, "--git-root", str(host.host))
    derived = run_cli(command, str(host.spec), *flags)
    assert "E763" not in given[1]
    assert "E763" not in derived[1]
    assert derived == given
