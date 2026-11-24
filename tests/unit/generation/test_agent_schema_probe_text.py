"""H-211-2: the fix agent and the reviewer read `specdev json schema` for the pointers they write or judge.

Reads text under ``.claude``; passes once the orchestrator has applied the edits listed in the H builder report
(CLAUDE-EDITS of B7).
"""
from __future__ import annotations

from pathlib import Path

import pytest

_AGENTS = Path(__file__).resolve().parents[3] / ".claude" / "agents"
_PROBE = "specdev json schema <file> '<pointer>' --repo-root ./devspec_toolkit"

pytestmark = pytest.mark.skipif(not _AGENTS.is_dir(), reason=".claude/agents is absent")


def test_the_impl_translation_rules_start_with_the_schema_probe() -> None:
    text = (_AGENTS / "specdev-impl.md").read_text(encoding="utf-8")
    section = text.split("## Finding-to-edit translation rules", 1)[1]
    assert _PROBE in section.split("\n| Finding kind", 1)[0]


def test_the_reviewer_procedure_probes_the_pointer_of_a_bug_or_hallucination() -> None:
    text = (_AGENTS / "specdev-reviewer.md").read_text(encoding="utf-8")
    procedure = text.split("## Operating procedure", 1)[1]
    step = procedure.split("3b.", 1)[1].split("\n4.", 1)[0]
    assert _PROBE in step and "evidence[]" in step


def test_the_fix_agent_reads_the_open_items_before_it_asks_or_inserts_one() -> None:
    """H-169-1: a question an open item already asks is not asked again."""
    text = (_AGENTS / "specdev-impl.md").read_text(encoding="utf-8")
    blocker_list = text.split("**Does NOT trigger blocker:**", 1)[1].split("\n- Findings whose `suggested_fix` is concrete.", 1)[0]
    assert "specdev upstream-backlog spec --repo-root ./devspec_toolkit" in blocker_list
    assert "unless an open item already asks the same question" in text
