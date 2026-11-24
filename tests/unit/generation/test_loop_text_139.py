"""The review loop has a scope kind for a file of `spec/common/` that is not a step file (DEVSPEC-139)."""
from __future__ import annotations

from pathlib import Path

import pytest

AGENTS = Path(__file__).resolve().parents[3] / ".claude" / "agents"
KIND = "manifest_artifact"


def _text(name: str) -> str:
    return (AGENTS / name).read_text(encoding="utf-8")


@pytest.mark.parametrize("name", ["specdev-scope.md", "specdev-reviewer.md"])
def test_the_agent_names_the_manifest_artifact_kind(name: str) -> None:
    assert KIND in _text(name)


def test_the_reviewer_lists_the_kind_among_the_scope_kinds() -> None:
    line = next(line for line in _text("specdev-reviewer.md").splitlines() if line.startswith("- `scope_kind`: one of"))
    assert KIND in line
