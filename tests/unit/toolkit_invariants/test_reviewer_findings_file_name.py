"""The per-reviewer findings file has one spelling: findings_<scope>_<round>_<reviewer_id>.json, ids r1, r2, ...

The dispatch sends ``"reviewer_id": "r1"``; a template that writes ``_r<reviewer_id>`` yields ``_rr1.json``,
which the skills' ``cp ..._r1.json`` and ``_r*.json`` lines then miss.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
FOLDERS = ("prompts", "docs/agents", "docs/developers", "docs/prompts", "schema", ".claude/agents", ".claude/skills", "tools/specdev_tools", "docs/architecture", "scripts", "changelog")
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


def test_the_scope_agent_states_the_reviewer_id_form() -> None:
    scope = REPO_ROOT / ".claude" / "agents" / "specdev-scope.md"
    assert scope.is_file(), f"{scope} is absent"
    assert "written `r<N>` (`r1`, `r2`, ...)" in scope.read_text(encoding="utf-8")
