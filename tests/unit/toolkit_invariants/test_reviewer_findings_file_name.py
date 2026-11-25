"""No file writes a reviewer's file name with a second ``r``.

``specdev loop`` names every file an agent writes (``.specdev/runs/<run-id>/d<n>/<entry>.t<try>.json``), and the
ids of a round's reviewer entries begin with ``r``. A template that writes ``_r<reviewer_id>`` or ``_r<id>`` in a
file name would double that letter; no text under the folders of ``FOLDERS`` may hold that spelling.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
FOLDERS = ("prompts", "docs/agents", "docs/developers", "docs/prompts", "schema", ".claude/agents", ".claude/skills", "tools/specdev_tools", "docs/architecture", "scripts", "changelog")
OLD_SPELLING = re.compile(r"_r<(?:reviewer_id|id)>")


_SUFFIXES = {".md", ".json", ".py", ".yaml"}


def _tracked_files() -> list[Path] | None:
    """The files git tracks under FOLDERS, or ``None`` when git fails, REPO_ROOT is not a checkout or git lists none.

    Git lists none when the toolkit is an untracked folder inside another work tree: the scan then walks the folders.
    """
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z", "--", *FOLDERS], cwd=REPO_ROOT, capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return [REPO_ROOT / name for name in result.stdout.split("\0") if name] or None


def _text_files() -> list[Path]:
    """The text files of FOLDERS that git tracks (an untracked draft is no part of the scan); a walk off a checkout."""
    tracked = _tracked_files()
    if tracked is not None:
        return [p for p in tracked if p.suffix in _SUFFIXES and p.is_file()]
    files: list[Path] = []
    for folder in FOLDERS:
        root = REPO_ROOT / folder
        if root.is_dir():
            files += [p for p in root.rglob("*") if p.suffix in _SUFFIXES and p.is_file()]
    return files


def test_no_file_writes_the_reviewer_file_name_with_a_second_r() -> None:
    hits = [
        f"{path.relative_to(REPO_ROOT)}:{number}"
        for path in _text_files()
        for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1)
        if OLD_SPELLING.search(line)
    ]
    assert hits == []


def test_the_scan_reads_only_the_files_git_tracks(monkeypatch: pytest.MonkeyPatch) -> None:
    """An untracked draft under FOLDERS is no part of the scan: the scan is the tracked list, filtered by suffix."""
    tracked = [REPO_ROOT / ".claude" / "agents" / "specdev-reviewer.md", REPO_ROOT / "prompts" / "a_picture.png"]
    monkeypatch.setattr(sys.modules[__name__], "_tracked_files", lambda: tracked)
    assert _text_files() == [tracked[0]]


def test_the_scan_walks_the_folders_when_git_lists_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys.modules[__name__], "_tracked_files", lambda: None)
    scanned = _text_files()
    assert REPO_ROOT / ".claude" / "agents" / "specdev-reviewer.md" in scanned
    assert all(p.suffix in _SUFFIXES for p in scanned)
