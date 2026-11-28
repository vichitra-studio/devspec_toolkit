"""H-232-1: prompt 01 names no field the charter schema lacks and says which of its rules no tool checks."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

PROMPT = (Path(__file__).resolve().parents[3] / "prompts" / "prompt_01_capabilities.md").read_text(encoding="utf-8")


def test_prompt_01_names_no_charter_goals() -> None:
    assert re.search(r"charter[^\n]*\bgoals?\b", PROMPT, re.I) is None
    assert "glossary nouns" not in PROMPT


@pytest.mark.parametrize(
    "sentence",
    [
        "This is an authoring and review rule: the schema leaves `owner` optional and no tool checks it.",
        "no tool checks the `cap-` prefix or the name (authoring and review rule).",
    ],
)
def test_prompt_01_states_owner_and_prefix_are_unchecked(sentence: str) -> None:
    assert sentence in PROMPT


def test_prompt_01_checklist_owner_is_conditional() -> None:
    assert "- Include `owner` for each capability reflecting the accountable team for delivery." not in PROMPT
    assert "- Include `owner` for a capability that spans multiple components, naming the accountable team" in PROMPT
