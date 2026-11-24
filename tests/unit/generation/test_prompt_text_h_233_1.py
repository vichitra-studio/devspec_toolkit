"""Prompt 06 says what the schema requires and what no tool checks of an invariant (DEVSPEC-233, step 06)."""
from __future__ import annotations

from pathlib import Path

PROMPT = Path(__file__).resolve().parents[3] / "prompts" / "prompt_06_invariants.md"


def _text() -> str:
    return PROMPT.read_text(encoding="utf-8")


def test_prompt_06_says_severity_is_required() -> None:
    text = _text()
    assert "`severity` is required by the schema (E520 when missing)" in text
    assert "`severity` is required and must be set deliberately" in text


def test_prompt_06_names_policy_ref() -> None:
    text = _text()
    assert "`policy_ref` is required on every rule" in text
    assert "`canonical-integrity` reports one that does not resolve (E110)" in text


def test_prompt_06_states_text_language_is_not_flagged() -> None:
    assert "A rule with `language` `text` is valid and no tool flags it" in _text()


def test_prompt_06_states_w615_covers_only_rules_with_risk_category_ref() -> None:
    assert "Only a rule that carries it is checked for red-team coverage (W615 at step 11)" in _text()


def test_prompt_06_states_sample_maintenance_is_unchecked() -> None:
    assert "Nothing checks that the sample changed in the same PR" in _text()
