"""H-233-2: prompt 07 says `measurement_method` is required and that a concrete query is a SHOULD."""
from __future__ import annotations

from pathlib import Path

_TEXT = (Path(__file__).resolve().parents[3] / "prompts" / "prompt_07_nfrs.md").read_text(encoding="utf-8")


def test_prompt_07_measurement_method_is_a_should():
    assert "MUST include `measurement_method` that specifies a concrete query" not in _TEXT
    assert "MUST include `measurement_method` (required by the schema); it SHOULD specify a concrete query, tool, or dashboard URL" in _TEXT
