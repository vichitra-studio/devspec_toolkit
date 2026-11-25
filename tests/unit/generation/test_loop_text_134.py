"""H-134-1: the review-fix loop is held once. Since the agent harness it is held by `specdev loop`, and every skill
carries the same pump: the block that tells a session how to carry out the actions the tool prints.

These tests read skill text under ``.claude``.
"""
from __future__ import annotations

from pathlib import Path

import pytest

_SKILLS = Path(__file__).resolve().parents[3] / ".claude" / "skills"
_LOOP_SKILLS = ("specdev-review", "specdev-step", "specdev-pass", "specdev-trinity")
_STEP_SKILL = _SKILLS / "specdev-step" / "SKILL.md"

pytestmark = pytest.mark.skipif(not _STEP_SKILL.is_file(), reason=".claude is absent")


def _text(name: str) -> str:
    return (_SKILLS / name / "SKILL.md").read_text(encoding="utf-8")


def _pump(name: str) -> str:
    text = _text(name)
    start = text.index("## The pump")
    return text[start : text.index("\n## ", start + 1)].rstrip().rstrip("-").rstrip()


def test_the_pump_is_the_same_text_in_every_loop_skill() -> None:
    first = _pump(_LOOP_SKILLS[0])
    assert "specdev loop next <run-id>" in first and "Read and follow" in first
    for name in _LOOP_SKILLS[1:]:
        assert _pump(name) == first, name


@pytest.mark.parametrize("name", _LOOP_SKILLS)
def test_no_skill_merges_findings_or_counts_rounds_itself(name: str) -> None:
    text = _text(name)
    for gone in ("unique_by(", "jq -s", "max_rounds", "rm -f .specdev/findings", "`findings_closed`", "specdev-scope"):
        assert gone not in text, gone


def test_the_step_skill_starts_a_run_in_its_step_2() -> None:
    text = _text("specdev-step")
    start = text.index("### Step 2")
    section = text[start : text.index("\n## ", start)]
    assert "specdev loop start --kind step <NN> --author" in section
    assert 'specdev loop start --kind step <NN> --extend "<intent>"' in section
