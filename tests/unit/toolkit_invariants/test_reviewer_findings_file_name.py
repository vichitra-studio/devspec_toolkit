"""No file writes a reviewer's file name with a second ``r``.

``specdev loop`` names every file an agent writes (``.specdev/runs/<run-id>/d<n>/<entry>.t<try>.json``), and the
ids of a round's reviewer entries begin with ``r``. A template that writes ``_r<reviewer_id>`` or ``_r<id>`` in a
file name would double that letter; no text under the folders of ``FOLDERS`` may hold that spelling.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
FOLDERS = ("prompts", "docs/agents", "docs/developers", "docs/prompts", "schema", ".claude/agents", ".claude/skills", "tools/specdev_tools")
OLD_SPELLING = re.compile(r"_r<(?:reviewer_id|id)>")


def _text_files() -> list[Path]:
    files: list[Path] = []
    for folder in FOLDERS:
        root = REPO_ROOT / folder
        if root.is_dir():
            files += [p for p in root.rglob("*") if p.suffix in {".md", ".json", ".py", ".yaml"} and p.is_file()]
    return files


def test_no_file_writes_the_reviewer_file_name_with_a_second_r() -> None:
    hits = [
        f"{path.relative_to(REPO_ROOT)}:{number}"
        for path in _text_files()
        for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1)
        if OLD_SPELLING.search(line)
    ]
    assert hits == []

