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


def _what_nothing_settles() -> str:
    text = _IMPL.read_text(encoding="utf-8")
    start = text.index("## What nothing settles")
    return text[start : text.index("\n## ", start + 1)]


def test_the_fix_agent_reads_the_open_items_before_it_records_one_and_asks_nobody() -> None:
    section = _what_nothing_settles()
    look, record = section.index("specdev upstream-backlog spec --repo-root ./devspec_toolkit"), section.index("specdev json insert --step <NN> .ambiguities")
    assert look < record, "the look for an existing open item comes before the insert"
    assert "You ask nobody" in section and '"status": "blocker"' not in _IMPL.read_text(encoding="utf-8")


def test_the_reviewer_says_a_commit_message_is_no_record() -> None:
    text = " ".join(_REVIEWER.read_text(encoding="utf-8").split())
    assert "A commit message, a dispatch brief and a chat reply are not records." in text
    assert "raise the finding as usual" in text
