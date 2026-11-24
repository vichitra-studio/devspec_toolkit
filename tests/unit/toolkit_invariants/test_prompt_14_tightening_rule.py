"""H-280-1: prompt 14 states one rule on tightening: a bar that no upstream node states is an open item, not a refinement."""
from __future__ import annotations

from pathlib import Path

_TEXT = (Path(__file__).resolve().parents[3] / "prompts" / "prompt_14_roadmap.md").read_text(encoding="utf-8")


def test_prompt_14_does_not_call_a_stricter_bar_ok():
    for line in _TEXT.splitlines():
        if line.startswith(("- **Stricter threshold**", "- **Added edge case**")):
            assert not line.endswith("— OK."), line
            assert "= refinement:" not in line, line


def test_prompt_14_sends_a_bar_no_upstream_node_states_to_an_open_item():
    assert "**Stricter threshold** = invention, not a refinement" in _TEXT
    assert "**Added edge case** = refinement only when an upstream node states it" in _TEXT
    assert "The threshold or case it checks is one that an upstream node states" in _TEXT
