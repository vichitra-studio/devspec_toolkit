"""The review loop takes a file of `spec/common/` that is not a step file as a scope (DEVSPEC-139).

The tool part (a read-only run on `spec/common/seed_manifest.json`) is tested in ``tests/unit/loop/test_loop_kinds.py``.
"""
from __future__ import annotations

from pathlib import Path

CLAUDE = Path(__file__).resolve().parents[3] / ".claude"


def test_the_reviewer_agent_says_how_a_spec_common_file_is_reviewed() -> None:
    text = (CLAUDE / "agents" / "specdev-reviewer.md").read_text(encoding="utf-8")
    line = next(line for line in text.splitlines() if "`specdev seed-lint spec <roots>`" in line)
    assert "`spec/common/`" in line and "`specdev spec-check spec <roots>`" in line


def test_the_review_skill_names_the_scope() -> None:
    text = " ".join((CLAUDE / "skills" / "specdev-review" / "SKILL.md").read_text(encoding="utf-8").split())
    assert "the name of a file of `spec/common/` (`seed_manifest.json`)" in text
    assert "A `spec/common/` file is reviewed with `--review-only`" in text
