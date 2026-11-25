"""H-169-1 and H-169-2: a question an open item already asks is not asked again; a decision kept only in a commit message is no record.

These tests read agent text under ``.claude``.
"""
from __future__ import annotations

from pathlib import Path

import pytest

_AGENTS = Path(__file__).resolve().parents[3] / ".claude" / "agents"
_IMPL = _AGENTS / "specdev-impl.md"
_REVIEWER = _AGENTS / "specdev-reviewer.md"

pytestmark = pytest.mark.skipif(not _IMPL.is_file(), reason=".claude is absent")


def _does_not_trigger_blocker_list() -> str:
    text = _IMPL.read_text(encoding="utf-8")
    start = text.index("**Does NOT trigger blocker:**")
    return text[start : text.index("\n\n", start)]


def test_the_fix_agent_reads_the_open_items_before_it_asks() -> None:
    assert "specdev upstream-backlog spec --repo-root ./devspec_toolkit" in _does_not_trigger_blocker_list()


def test_the_reviewer_says_a_commit_message_is_no_record() -> None:
    text = " ".join(_REVIEWER.read_text(encoding="utf-8").split())
    assert "A commit message, a dispatch brief and a chat reply are not records." in text
    assert "raise the finding as usual" in text
