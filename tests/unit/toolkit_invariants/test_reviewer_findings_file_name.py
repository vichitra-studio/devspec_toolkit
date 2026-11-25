"""The per-reviewer findings file has one spelling: findings_<scope>_<round>_<reviewer_id>.json, ids r1, r2, ...

The dispatch sends ``"reviewer_id": "r1"``; a template that writes ``_r<reviewer_id>`` yields ``_rr1.json``,
which the skills' ``cp ..._r1.json`` and ``_r*.json`` lines then miss.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
FOLDERS = ("prompts", "docs/agents", "docs/developers", "docs/prompts", "schema", ".claude/agents", ".claude/skills", "tools/specdev_tools", "docs/architecture", "scripts", "changelog")
OLD_SPELLING = re.compile(r"_r<(?:reviewer_id|id)>")


_SUFFIXES = {".md", ".json", ".py", ".yaml"}


def _tracked_files() -> list[Path] | None:
    """The files git tracks under FOLDERS, or ``None`` when git fails or REPO_ROOT is not a checkout."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z", "--", *FOLDERS], cwd=REPO_ROOT, capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return [REPO_ROOT / name for name in result.stdout.split("\0") if name]


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


def test_the_scope_agent_states_the_reviewer_id_form() -> None:
    scope = REPO_ROOT / ".claude" / "agents" / "specdev-scope.md"
    assert scope.is_file(), f"{scope} is absent"
    assert "written `r<N>` (`r1`, `r2`, ...)" in scope.read_text(encoding="utf-8")


def test_text_files_are_the_files_git_tracks() -> None:
    tracked = _tracked_files()
    if tracked is None:
        pytest.skip("not a git checkout")
    scanned = _text_files()
    assert scanned, "the scan found no file"
    assert set(scanned) <= set(tracked)
    assert all(p.suffix in _SUFFIXES for p in scanned)
