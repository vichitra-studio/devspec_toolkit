"""Prompt 11 says which of its rules are warnings or review rules that no tool enforces (DEVSPEC-233)."""
from __future__ import annotations

from pathlib import Path

PROMPT_11 = Path(__file__).resolve().parents[3] / "prompts" / "prompt_11_redteam.md"


def _text() -> str:
    return PROMPT_11.read_text(encoding="utf-8")


def test_prompt_11_says_w583_is_a_warning() -> None:
    text = _text()
    assert "W583 is a warning: it has no error form and does not fail `spec-check`" in text
    assert "It covers APIs only." in text


def test_prompt_11_says_trust_boundary_and_edge_case_count_are_review_rules() -> None:
    text = _text()
    assert "(review rule: no tool checks components; W583 covers APIs only)" in text
    assert "(review rule: the schema requires neither `edge_cases` nor a count)" in text


def test_prompt_11_says_w615_covers_only_rules_with_risk_category_ref() -> None:
    text = _text()
    assert "W615 is a warning and checks only a rule that carries a `risk_category_ref`" in text
    assert "a rule without one is not checked" in text
