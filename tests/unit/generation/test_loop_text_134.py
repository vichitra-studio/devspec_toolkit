"""H-134-1: `/specdev-step` runs its review-fix loop by invoking `/specdev-review`, which holds the loop once.

These tests read skill text under ``.claude``; they pass once the orchestrator has applied the edit
listed in the H builder report (CLAUDE-EDITS of B8).
"""
from __future__ import annotations

from pathlib import Path

import pytest

_SKILLS = Path(__file__).resolve().parents[3] / ".claude" / "skills"
_STEP_SKILL = _SKILLS / "specdev-step" / "SKILL.md"
_REVIEW_SKILL = _SKILLS / "specdev-review" / "SKILL.md"
_MERGE_EXPRESSION = "unique_by({kind, location, signature})"

pytestmark = pytest.mark.skipif(not _STEP_SKILL.is_file(), reason=".claude is absent")


def _step_2_section() -> str:
    text = _STEP_SKILL.read_text(encoding="utf-8")
    start = text.index("### Step 2")
    return text[start : text.index("\n## ", start)]


def test_the_step_skill_invokes_specdev_review_in_its_step_2() -> None:
    assert "`specdev-review`" in _step_2_section()


def test_the_merge_of_the_findings_files_is_written_once() -> None:
    assert _MERGE_EXPRESSION not in _STEP_SKILL.read_text(encoding="utf-8")
    assert _MERGE_EXPRESSION in _REVIEW_SKILL.read_text(encoding="utf-8")


def test_step_2_keeps_the_rule_about_findings_closed_and_open() -> None:
    section = _step_2_section()
    assert "`findings_closed`" in section and "`findings_open`" in section
