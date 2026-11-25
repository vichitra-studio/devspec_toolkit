"""H-280-2 and H-281-1: the reviewer has one finding class for a node whose text disagrees with the node it points at.

Reads ``.claude/agents/specdev-reviewer.md``.
"""
from __future__ import annotations

from pathlib import Path

import pytest

_REVIEWER = Path(__file__).resolve().parents[3] / ".claude" / "agents" / "specdev-reviewer.md"


@pytest.mark.skipif(not _REVIEWER.is_file(), reason=".claude is absent")
def test_reviewer_names_disagreement_for_refines_verifies_and_shared_outcome():
    text = " ".join(_REVIEWER.read_text(encoding="utf-8").split())
    assert "`disagreement:`" in text
    assert "each node it `refines`" in text
    assert "each node it `verifies`" in text
    assert "an API error and an invariant that govern the same outcome" in text
