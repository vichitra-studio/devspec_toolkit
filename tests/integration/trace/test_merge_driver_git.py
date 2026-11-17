"""The lock merge driver inside real git merges (WI-M5-07, exit criterion A1): installed, absent, and the repair."""
from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from specdev_tools.trace.lockfile import CONFLICT_MARKER, Lock, LockEntry, LockError, read_lock, serialise_lock, write_lock
from specdev_tools.trace.merge_driver import DRIVER_NAME, install_driver

from unit.graph._synth import GIT_IDENTITY, git

LOCK_REL = "spec/extras/trace.lock.json"
DRIVER_COMMAND = f"{shlex.quote(sys.executable)} -m specdev_tools.cli lock merge"
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


@pytest.fixture
def diverged(tmp_path: Path) -> Path:
    """A repository on `main` and a branch `theirs`, both changed from one base: adjacent entries re-attested, one added each."""
    repo = tmp_path / "host"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    install_driver(str(repo), "spec", DRIVER_COMMAND)
    _commit(repo, Lock((FIRST, SECOND)), "base")
    git(repo, "checkout", "-q", "-b", "theirs")
    _commit(repo, Lock((FIRST_ATTESTED, SECOND, ADDED_BY_THEM)), "theirs attests the first link and adds one")
    git(repo, "checkout", "-q", "main")
    _commit(repo, Lock((FIRST, SECOND_ATTESTED, ADDED_BY_US)), "ours attests the second link and adds one")
    return repo


def test_git_merge_with_installed_driver_leaves_no_markers(diverged: Path) -> None:
    done = _try_merge(diverged, "merge", "--no-edit", "theirs")
    assert done.returncode == 0, done.stdout + done.stderr
    text = (diverged / LOCK_REL).read_text(encoding="utf-8")
    assert CONFLICT_MARKER not in text
    assert text == serialise_lock(EXPECTED)
    assert read_lock(str(diverged / "spec")) == EXPECTED


def test_without_driver_markers_loader_e760_and_repair_succeeds(diverged: Path) -> None:
    git(diverged, "config", "--remove-section", f"merge.{DRIVER_NAME}")
    done = _try_merge(diverged, "merge", "--no-edit", "theirs")
    assert done.returncode != 0
    assert CONFLICT_MARKER in (diverged / LOCK_REL).read_text(encoding="utf-8")
    with pytest.raises(LockError) as caught:
        read_lock(str(diverged / "spec"))
    assert caught.value.error.code == "E760"
    repair = caught.value.error.message
    assert f"git config merge.{DRIVER_NAME}.driver" in repair and "git checkout -m" in repair and "git add" in repair

    git(diverged, "config", f"merge.{DRIVER_NAME}.driver", f"{DRIVER_COMMAND} %O %A %B %P")
    git(diverged, "checkout", "-m", "--", LOCK_REL)
    git(diverged, "add", LOCK_REL)
    assert (diverged / LOCK_REL).read_text(encoding="utf-8") == serialise_lock(EXPECTED)
    assert git(diverged, "diff", "--name-only", "--diff-filter=U") == ""
    git(diverged, "commit", "-q", "--no-edit")
    assert read_lock(str(diverged / "spec")) == EXPECTED
