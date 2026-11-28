"""Prompt 12 states that its three conditional MUSTs are authoring and review rules (DEVSPEC-233, ENF-061)."""
from __future__ import annotations

from pathlib import Path

_PROMPT_12 = Path(__file__).resolve().parents[3] / "prompts" / "prompt_12_ci_gates.md"
_COVERAGE_RULE = "MUST populate `coverage_thresholds` when any NFR in `spec/07_nfrs.json` specifies a coverage metric."
_UNCHECKED = "These three rules are authoring and review rules: no tool checks them."


def test_prompt_12_states_conditional_musts_are_unchecked() -> None:
    text = _PROMPT_12.read_text(encoding="utf-8")
    assert f"{_COVERAGE_RULE} {_UNCHECKED}" in text
