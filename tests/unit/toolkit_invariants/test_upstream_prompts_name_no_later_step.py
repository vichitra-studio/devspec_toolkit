"""H-253-1: prompt 03 and prompt 02a state nothing about the steps after them."""
from __future__ import annotations

from pathlib import Path

PROMPTS = Path(__file__).resolve().parents[3] / "prompts"
OLD_SENTENCES = {
    "prompt_03_glossary.md": "Every domain noun introduced in steps 04-16c MUST have a corresponding `term_id`",
    "prompt_02a_delivery_baseline.md": "that map directly to Step 12 output",
}


def test_prompt_03_and_02a_state_nothing_about_later_steps() -> None:
    for name, sentence in OLD_SENTENCES.items():
        text = (PROMPTS / name).read_text(encoding="utf-8")
        assert sentence not in text, name
    assert "downstream steps MUST NOT introduce terms" not in (PROMPTS / "prompt_03_glossary.md").read_text(encoding="utf-8")
