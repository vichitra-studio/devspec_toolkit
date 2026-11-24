"""H-235-3: prompt 16b says what no tool checks (test commands, vagueness, the `amb-new-` prefix)."""
from __future__ import annotations

from pathlib import Path

_TEXT = (Path(__file__).resolve().parents[3] / "prompts" / "prompt_16b_impl_coder.md").read_text(encoding="utf-8")


def test_prompt_16b_says_test_commands_are_not_run_by_a_tool():
    assert "No tool runs `test_commands` for you (an authoring rule)" in _TEXT
    assert "every action is recorded done (E812)" in _TEXT
    assert "`specdev verify run` (E811)" in _TEXT


def test_prompt_16b_says_amb_new_is_a_convention():
    assert "The `amb-new-` prefix is a naming convention that no tool checks" in _TEXT


def test_prompt_16b_says_vagueness_is_judgement():
    assert "Whether an item is vague is your judgement: no tool detects it." in _TEXT
