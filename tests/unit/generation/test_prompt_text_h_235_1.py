"""H-235-1: the step 16a prompt names W610 as a warning and the unchecked rules as review rules."""
from __future__ import annotations

from pathlib import Path

_TEXT = (Path(__file__).resolve().parents[3] / "prompts" / "prompt_16a_impl_planner.md").read_text(encoding="utf-8")


def test_prompt_16a_names_w610_for_the_id_prefix():
    assert "is reported as W610, a warning that does not fail the gate" in _TEXT


def test_prompt_16a_says_docs_touched_vs_target_patterns_is_a_review_rule():
    assert "Every doc path must appear in `plan.summary.target_file_patterns`. (review rule:" in _TEXT
    assert "not against `target_file_patterns`" in _TEXT


def test_prompt_16a_says_atomicity_is_a_review_rule():
    assert "These atomicity rules are review rules" in _TEXT
    assert "requires >2 file edits\n\n(These atomicity rules" in _TEXT
