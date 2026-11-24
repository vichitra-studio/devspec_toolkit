"""H-234-3: prompt 16 says which anchor coverage rules no tool checks and that a misfiled anchor is W609."""
from __future__ import annotations

from pathlib import Path

PROMPT = (Path(__file__).resolve().parents[3] / "prompts" / "prompt_16_impl_context.md").read_text(encoding="utf-8")


def test_prompt_16_states_unchecked_coverage_rules() -> None:
    assert "No tool reports a roadmap milestone that has no row (review rule)." in PROMPT
    assert "no tool compares the anchor's two lists with each other (review rule)" in PROMPT


def test_prompt_16_names_w609_for_a_misfiled_anchor() -> None:
    assert "reports an anchor found there as W609, a warning that does not fail the gate" in PROMPT
