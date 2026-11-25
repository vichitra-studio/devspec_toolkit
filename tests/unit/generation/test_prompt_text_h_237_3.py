"""The shared expectations and the step prompts say what the checks do (DEVSPEC-237)."""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
PROMPTS = sorted((ROOT / "prompts").glob("prompt_[0-9][0-9]*_*.md"))
SHARED = ROOT / "docs" / "prompts" / "shared_expectations.md"
UNUSED_NODE_LINE = "- [ ] Every upstream node this step must cover is used by a node of this step"
STEP_PROMPTS_WITH_THE_LINE = [p for p in PROMPTS if "prompt_16" not in p.name]


def _shared() -> str:
    return SHARED.read_text(encoding="utf-8")


@pytest.mark.parametrize("path", [*PROMPTS, SHARED], ids=lambda p: p.name)
def test_no_prompt_says_upstream_ids_are_consumed(path: Path) -> None:
    assert "has been consumed" not in path.read_text(encoding="utf-8")


@pytest.mark.parametrize("path", STEP_PROMPTS_WITH_THE_LINE, ids=lambda p: p.name)
def test_every_step_prompt_has_the_unused_node_line(path: Path) -> None:
    assert UNUSED_NODE_LINE in path.read_text(encoding="utf-8")


def test_shared_expectations_closure_runs_before_emitting() -> None:
    text = _shared()
    assert "run Coverage Closure BEFORE emitting the artifact (8.2)" in text
    assert "Coverage Closure AFTER emitting" not in text


def test_shared_expectations_says_an_agent_records_its_gap_questions() -> None:
    """An agent in a run of `specdev loop` asks nobody: a gap is an open item (the agent file's section is named)."""
    text = _shared()
    assert "it asks nobody: each gap is recorded as an open item of the artifact" in text
    assert 'section "What nothing settles"' in text
    assert "## What nothing settles" in (ROOT / ".claude" / "agents" / "specdev-impl.md").read_text(encoding="utf-8")


def test_shared_expectations_output_contract_is_not_a_restatement() -> None:
    text = _shared()
    assert "tests/integration/test_prompt_output_examples.py" in text
    assert "a worked example that a test validates against the schema" in text


def test_shared_expectations_deprecated_canon_is_a_warning() -> None:
    assert "reports a use of a deprecated entry as W110, a warning that has no error form" in _shared()
