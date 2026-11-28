"""A finding that names a command line names one that does what the finding says (review M5 R1, F1-2).

For each lock finding that tells the reader to run ``specdev attest ...`` or ``specdev attest --prune``, the test takes
the command lines out of the message, runs them on a git copy of the worked example, and checks the effect: the bare
``attest`` only shows, the one with ``--yes`` writes and clears the finding, ``--prune`` writes at once.
"""
from __future__ import annotations

import dataclasses
import re
import shlex
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.trace.lockfile import Lock, LockEntry, lock_path, read_lock, write_lock
from specdev_tools.validation.spec_check import run_spec_check_json

from unit.graph._synth import ROOT
from unit.trace._lock_support import git_copy_of_example, run_on_example

HOLDER = "api-password-reset-confirm"
CRITERION = "ac-password-reset-3"


@pytest.fixture
def host(tmp_path: Path) -> Path:
    return git_copy_of_example(tmp_path / "host")


def _findings(host: Path, code: str, node_id: str | None = None) -> list[dict[str, Any]]:
    _errors, context = run_spec_check_json(str(ROOT), str(host / "spec"), git_root=str(host))
    found = [finding for check in context["checks"].values() for finding in check.get("findings", []) if finding["code"] == code]
    return [finding for finding in found if node_id is None or finding.get("node_id") == node_id]


def _lock_text(host: Path) -> str:
    return Path(lock_path(str(host / "spec"))).read_text(encoding="utf-8")


def _commands(message: str) -> list[list[str]]:
    """The ``specdev`` command lines of *message* (its backticked parts), as argument lists without ``specdev``."""
    parts = [shlex.split(text) for text in re.findall(r"`([^`]+)`", message)]
    return [part[1:] for part in parts if part and part[0] == "specdev"]


def _rewrite_lock(host: Path, change: Any) -> None:
    write_lock(str(host / "spec"), Lock(tuple(change(read_lock(str(host / "spec")).entries))))


def _only_writing_command_writes(host: Path, message: str) -> None:
    """The message names two commands: the first only shows (the lock is unchanged), the second writes."""
    shows, writes = _commands(message)
    assert writes[-1] == "--yes" and shows == writes[:-1]
    before = _lock_text(host)
    code, out = run_on_example(host, *shows)
    assert code == 0 and "would write" in out, out
    assert _lock_text(host) == before
    code, out = run_on_example(host, *writes)
    assert code == 0 and "wrote" in out, out
    assert _lock_text(host) != before


def _edit_criterion(host: Path) -> None:
    code, out = run_on_example(host, "json", "patch", "--id", CRITERION, ".text", '"The text of the third criterion, edited."')
    assert code == 0, out


def test_e763_names_a_command_that_shows_and_one_that_writes(host: Path) -> None:
    _edit_criterion(host)
    (finding,) = _findings(host, "E763", HOLDER)
    _only_writing_command_writes(host, finding["message"])
    assert _findings(host, "E763", HOLDER) == []


def test_e761_names_a_command_that_shows_and_one_that_writes(host: Path) -> None:
    _rewrite_lock(host, lambda entries: [entry for entry in entries if entry.source != HOLDER])
    (finding, *_rest) = _findings(host, "E761", HOLDER)
    _only_writing_command_writes(host, finding["message"])
    assert _findings(host, "E761", HOLDER) == []


def test_e882_names_a_command_that_shows_and_one_that_writes(host: Path) -> None:
    _rewrite_lock(host, lambda entries: [dataclasses.replace(entry, baseline=True) if entry.source == HOLDER else entry for entry in entries])
    (finding, *_rest) = _findings(host, "E882", HOLDER)
    _only_writing_command_writes(host, finding["message"])
    assert _findings(host, "E882", HOLDER) == []


def _orphan(source: str, target: str = "fr-password-reset") -> LockEntry:
    return LockEntry(source, "derives_from", target, "sha256:" + "1" * 64, "sha256:" + "2" * 64)


def test_e762_names_a_command_that_writes_at_once(host: Path) -> None:
    _rewrite_lock(host, lambda entries: [*entries, _orphan("api-gone")])
    (finding,) = _findings(host, "E762")
    (command,) = _commands(finding["message"])
    assert command == ["attest", "--prune"]
    before = _lock_text(host)
    code, out = run_on_example(host, *command)
    assert code == 0 and "removed 1 orphan entry" in out, out
    assert _lock_text(host) != before and "api-gone" not in _lock_text(host)
    assert _findings(host, "E762") == []


def test_node_rename_refusal_names_a_prune_that_lets_the_rename_through(host: Path) -> None:
    _rewrite_lock(host, lambda entries: [*entries, _orphan("fr-password-recovery", "cap-account-recovery")])
    code, out = run_on_example(host, "node", "rename", "fr-password-reset", "fr-password-recovery")
    assert code == 1 and "attest --prune" in out, out
    (command,) = _commands(out)
    assert run_on_example(host, *command)[0] == 0
    code, out = run_on_example(host, "node", "rename", "fr-password-reset", "fr-password-recovery")
    assert code == 0, out


def test_a_dry_run_of_an_id_write_says_would_become_suspect_and_names_no_command(host: Path) -> None:
    """M5 R2 G1-6: nothing is written, so ``specdev stale`` shows nothing: the dry run does not send the reader there."""
    edit = ["json", "patch", "--id", CRITERION, ".text", '"A reset link stops working after one use."']
    code, dry = run_on_example(host, *edit, "--dry-run")
    assert code == 0 and "would become suspect: " in dry and "newly suspect" not in dry and "specdev stale" not in dry, dry
    assert "specdev stale" not in dry.split("would become suspect: ")[1]
    code, done = run_on_example(host, *edit)
    assert code == 0 and "newly suspect: " in done and "see `specdev stale`" in done and "would become" not in done, done
    count = re.search(r"newly suspect: (\d+ links) ", done)
    assert count is not None and f"would become suspect: {count.group(1)} " in dry
