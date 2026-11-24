"""Prompt 13 states the constraints that only the schema enforces and says which rules are review rules (DEVSPEC-233, step 13)."""
from __future__ import annotations

from pathlib import Path

PROMPT = Path(__file__).resolve().parents[3] / "prompts" / "prompt_13_extension_manifest.md"


def test_prompt_13_names_the_schema_only_constraints() -> None:
    text = PROMPT.read_text(encoding="utf-8")
    assert "holds at least 3 names" in text
    assert "(`required_schema_sections` has ≥3 entries: schema `minItems`)" in text
    assert "`([Vv]erif|[Tt]est|[Cc]heck|[Vv]alidat|[Aa]ssert)`" in text


def test_prompt_13_justification_is_a_review_rule() -> None:
    text = PROMPT.read_text(encoding="utf-8")
    sentence = "This is an authoring and review rule: the schema and E320 check only that the text is present."
    assert text.count(sentence) == 2
