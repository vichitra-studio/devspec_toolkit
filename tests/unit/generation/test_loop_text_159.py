"""H-159-1 and H-159-2: the review loops remove a round's findings files first, and a finding's location is the node id.

The skill and agent tests read text under ``.claude``; they pass once the orchestrator has applied the edits listed in
the H builder report (CLAUDE-EDITS of B7).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_CLAUDE = _ROOT / ".claude"
_SKILLS = {name: _CLAUDE / "skills" / name / "SKILL.md" for name in ("specdev-review", "specdev-trinity")}
_REVIEWER = _CLAUDE / "agents" / "specdev-reviewer.md"
_FINDINGS_SCHEMA = _ROOT / "schema" / "infra" / "findings.schema.json"

_needs_claude = pytest.mark.skipif(not _CLAUDE.is_dir(), reason=".claude is absent")


@_needs_claude
@pytest.mark.parametrize("skill", sorted(_SKILLS))
def test_the_loop_skill_removes_the_findings_of_the_round_before_it_merges(skill: str) -> None:
    text = _SKILLS[skill].read_text(encoding="utf-8")
    removal = text.find("rm -f .specdev/findings/findings_")
    assert removal != -1, "no `rm -f .specdev/findings/findings_` line"
    assert removal < text.find("jq -s '"), "the removal comes after the merge"


@_needs_claude
def test_the_reviewer_agent_gives_the_node_id_form_of_location() -> None:
    text = _REVIEWER.read_text(encoding="utf-8")
    assert "fr-password-reset#description" in text
    assert "functional_requirements/3" not in text


def test_the_findings_schema_describes_the_node_id_form() -> None:
    schema = json.loads(_FINDINGS_SCHEMA.read_text(encoding="utf-8"))
    description = schema["$defs"]["finding"]["properties"]["location"]["description"]
    assert description.startswith("Where the finding sits: the id of the node")
