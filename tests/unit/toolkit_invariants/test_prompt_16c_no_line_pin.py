"""H-252-2: a finding of a 16c review is written into a durable plan, so the prompt asks for no line number."""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
PROMPT = REPO_ROOT / "prompts" / "prompt_16c_impl_reviewer.md"
REVIEWER_AGENT = REPO_ROOT / ".claude" / "agents" / "specdev-trinity-reviewer.md"


def test_prompt_16c_does_not_demand_file_line() -> None:
    assert "file:line" not in PROMPT.read_text(encoding="utf-8")


@pytest.mark.skipif(not REVIEWER_AGENT.is_file(), reason=".claude is absent")
def test_trinity_reviewer_agent_does_not_demand_file_line() -> None:
    """The trinity reviewer agent file asks for no line number either."""
    assert "file:line" not in REVIEWER_AGENT.read_text(encoding="utf-8")
