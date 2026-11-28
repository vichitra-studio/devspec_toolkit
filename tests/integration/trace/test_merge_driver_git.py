"""The lock merge driver inside real git merges (WI-M5-07, exit criterion A1): installed, absent, and the repair."""
from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from specdev_tools.trace.lockfile import CONFLICT_MARKER, Lock, LockEntry, LockError, read_lock, serialise_lock, write_lock
from specdev_tools.trace.merge_driver import install_driver

from unit.graph._synth import GIT_IDENTITY, ROOT, git
from unit.trace._lock_support import DRIVER_COMMAND

LOCK_REL = "spec/extras/trace.lock.json"
GIT_ENV = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}


def _entry(source: str, target: str, digit: str) -> LockEntry:
    return LockEntry(source, "api_refs", target, f"sha256:{digit * 64}", f"sha256:{digit * 64}")


FIRST, SECOND = _entry("fr-1", "api-1", "1"), _entry("fr-2", "api-2", "2")
FIRST_ATTESTED, SECOND_ATTESTED = _entry("fr-1", "api-1", "a"), _entry("fr-2", "api-2", "b")
ADDED_BY_THEM, ADDED_BY_US = _entry("fr-3", "api-3", "3"), _entry("fr-4", "api-4", "4")
EXPECTED = Lock((FIRST_ATTESTED, SECOND_ATTESTED, ADDED_BY_THEM, ADDED_BY_US))


def _commit(repo: Path, lock: Lock, message: str) -> None:
    write_lock(str(repo / "spec"), lock)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)


def _try_merge(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *GIT_IDENTITY, *args], capture_output=True, text=True, env=GIT_ENV, check=False)


def _diverge(repo: Path, *, install: bool) -> Path:
    """*repo* on `main` and a branch `theirs`, both changed from one base: adjacent entries re-attested, one added each."""
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    if install:
        install_driver(str(repo), "spec", DRIVER_COMMAND)
    _commit(repo, Lock((FIRST, SECOND)), "base")
    git(repo, "checkout", "-q", "-b", "theirs")
    _commit(repo, Lock((FIRST_ATTESTED, SECOND, ADDED_BY_THEM)), "theirs attests the first link and adds one")
    git(repo, "checkout", "-q", "main")
    _commit(repo, Lock((FIRST, SECOND_ATTESTED, ADDED_BY_US)), "ours attests the second link and adds one")
    return repo


@pytest.fixture
def diverged(tmp_path: Path) -> Path:
    """The diverged repository with the merge driver installed."""
    return _diverge(tmp_path / "host", install=True)


@pytest.fixture
def diverged_never_installed(tmp_path: Path) -> Path:
    """The diverged repository of a clone that never installed the driver: no attribute line, no driver in git config."""
    return _diverge(tmp_path / "host", install=False)


def test_git_merge_with_installed_driver_leaves_no_markers(diverged: Path) -> None:
    done = _try_merge(diverged, "merge", "--no-edit", "theirs")
    assert done.returncode == 0, done.stdout + done.stderr
    text = (diverged / LOCK_REL).read_text(encoding="utf-8")
    assert CONFLICT_MARKER not in text
    assert text == serialise_lock(EXPECTED)
    assert read_lock(str(diverged / "spec")) == EXPECTED


def _printed_commands(message: str) -> list[str]:
    """The commands of the repair a message prints (the backticked parts), with ``specdev`` and the driver path filled in."""
    specdev = f"{shlex.quote(sys.executable)} -m specdev_tools.cli"
    commands = re.findall(r"`([^`]+)`", message)
    return [
        command.replace("<path to specdev>", specdev).replace("specdev ", f"{specdev} ", 1) + (f" --repo-root {ROOT}" if command.startswith("specdev ") else "")
        for command in commands
    ]


def test_without_driver_markers_loader_e760_and_repair_succeeds(diverged_never_installed: Path) -> None:
    """A clone that never installed the driver: the printed repair, run as printed, removes the markers and the unmerged state."""
    repo = diverged_never_installed
    assert not (repo / ".git" / "info" / "attributes").exists()
    done = _try_merge(repo, "merge", "--no-edit", "theirs")
    assert done.returncode != 0
    assert CONFLICT_MARKER in (repo / LOCK_REL).read_text(encoding="utf-8")
    with pytest.raises(LockError) as caught:
        read_lock(str(repo / "spec"))
    assert caught.value.error.code == "E760"
    message = caught.value.error.message
    assert message.count("lock install-driver") == 1 and "git checkout -m" in message and "git add" in message
    assert message.index("install-driver") < message.index("git checkout -m") < message.index("git add")

    commands = _printed_commands(message)
    assert len(commands) == 3
    for command in commands:
        ran = subprocess.run(command, shell=True, cwd=repo, capture_output=True, text=True, env=GIT_ENV, check=False)
        assert ran.returncode == 0, f"{command}\n{ran.stdout}{ran.stderr}"
    assert CONFLICT_MARKER not in (repo / LOCK_REL).read_text(encoding="utf-8")
    assert (repo / LOCK_REL).read_text(encoding="utf-8") == serialise_lock(EXPECTED)
    assert git(repo, "diff", "--name-only", "--diff-filter=U") == ""
    git(repo, "commit", "-q", "--no-edit")
    assert read_lock(str(repo / "spec")) == EXPECTED
