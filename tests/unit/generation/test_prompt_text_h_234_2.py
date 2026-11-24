"""H-234-2: prompt 15 says what `step ready 15` reads and which of its rules no tool checks."""
from __future__ import annotations

from pathlib import Path

PROMPT = (Path(__file__).resolve().parents[3] / "prompts" / "prompt_15_scaffold.md").read_text(encoding="utf-8")
REVIEW_RULE = "(review rule: `project_skeleton` cannot express it and no tool checks it)"


def test_prompt_15_self_audit_names_what_step_ready_checks() -> None:
    sentence = "(read as context; `specdev step ready 15` does not check this file, it checks step 05)"
    assert PROMPT.count(sentence) == 2


def test_prompt_15_says_validators_are_not_run() -> None:
    assert "No tool runs the strings in `validators`" in PROMPT


def test_prompt_15_says_skeleton_extras_are_review_rules() -> None:
    assert PROMPT.count(REVIEW_RULE) == 2
    assert "`framework` and `modules` are optional in the schema and no tool checks them" in PROMPT
    assert "specifies language, framework, and core modules" not in PROMPT
