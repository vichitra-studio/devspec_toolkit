"""H-199-2: the reviewer agent text defines ``regression``, ``origin`` and the tie-breaks between overlapping kinds.

The text lives in a ``.claude/`` file that the orchestrator edits; the test waits for that edit.
"""
from __future__ import annotations

from pathlib import Path

import pytest

AGENT = Path(__file__).resolve().parents[3] / ".claude" / "agents" / "specdev-reviewer.md"


@pytest.mark.skipif(not AGENT.exists(), reason=".claude/agents/specdev-reviewer.md is absent")
def test_reviewer_defines_regression_origin_and_tie_breaks() -> None:
    text = AGENT.read_text(encoding="utf-8")
    for needle in ("E763", "origin", "Tie-breaks"):
        assert needle in text, needle
