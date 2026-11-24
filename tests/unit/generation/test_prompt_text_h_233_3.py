"""Prompt 09 says `target_date` is a SHOULD, as the worked example and the validator allow (DEVSPEC-233, step 09)."""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PROMPT = REPO_ROOT / "prompts" / "prompt_09_impl_plan.md"
WORKED_EXAMPLE = REPO_ROOT / "tests" / "fixtures" / "graph_example" / "spec" / "09_impl_plan.json"


def test_prompt_09_target_date_is_a_should() -> None:
    text = PROMPT.read_text(encoding="utf-8")
    assert "MUST populate `target_date` on every milestone" not in text
    assert "SHOULD populate `target_date` on every milestone" in text
    assert "(not required by the schema; a date that is present is checked)" in text
    assert "no tool decides whether the plan does" in text


def test_worked_example_milestone_without_target_date_is_valid() -> None:
    milestones = json.loads(WORKED_EXAMPLE.read_text(encoding="utf-8"))["milestones"]
    assert any("target_date" not in milestone for milestone in milestones)
