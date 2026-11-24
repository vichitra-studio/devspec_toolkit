"""The dispatched trinity agents are told to use the dispatch's absolute paths, and the two that write check the worktree (DEVSPEC-138)."""
from __future__ import annotations

from pathlib import Path

import pytest

AGENTS = Path(__file__).resolve().parents[3] / ".claude" / "agents"
SECTION = "## Worktree dispatch"
TOPLEVEL_CHECK = "git rev-parse --show-toplevel"
WRITING_AGENTS = ["specdev-trinity-impl.md", "specdev-trinity-reviewer.md"]


def _text(name: str) -> str:
    return (AGENTS / name).read_text(encoding="utf-8")


@pytest.mark.parametrize("name", [*WRITING_AGENTS, "specdev-scope.md"])
def test_each_dispatched_agent_has_the_worktree_section(name: str) -> None:
    assert _text(name).count(SECTION) == 1


@pytest.mark.parametrize("name", WRITING_AGENTS)
def test_a_writing_agent_checks_the_toplevel_before_it_writes(name: str) -> None:
    text = _text(name)
    assert TOPLEVEL_CHECK in text
    assert "worktree mismatch" in text


def test_the_scope_agent_writes_nothing_so_it_has_no_toplevel_check() -> None:
    assert TOPLEVEL_CHECK not in _text("specdev-scope.md")
