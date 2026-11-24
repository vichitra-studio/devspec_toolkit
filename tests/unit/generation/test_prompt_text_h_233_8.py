"""Prompt 08 says what `fixtures-lint` checks of a contract fixture and what nothing checks (DEVSPEC-233, step 08)."""
from __future__ import annotations

from pathlib import Path

PROMPT = Path(__file__).resolve().parents[3] / "prompts" / "prompt_08_fixtures.md"


def _text() -> str:
    return PROMPT.read_text(encoding="utf-8")


def test_prompt_08_contract_body_is_a_should() -> None:
    text = _text()
    assert "`expected` MUST have `status`, `body`" not in text
    assert "and SHOULD have `body`" in text
    assert "`fixtures-lint` does not require `body`" in text


def test_prompt_08_says_sample_is_not_scanned() -> None:
    assert "the spec scanners skip `spec/samples/`, so E510 never reads this file" in _text()


def test_prompt_08_says_same_pr_rule_is_unchecked() -> None:
    assert "Nothing checks that the sample changed in the same PR" in _text()
