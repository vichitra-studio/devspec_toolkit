"""H-170-1 and H-133-1: the fix agent reads each fix back and returns a record per finding.

These tests read agent and skill text under ``.claude``; they pass once the orchestrator has applied
the edits listed in the H builder report (CLAUDE-EDITS of B6).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

_CLAUDE = Path(__file__).resolve().parents[3] / ".claude"
_IMPL = _CLAUDE / "agents" / "specdev-impl.md"
_SKILLS = {name: _CLAUDE / "skills" / name / "SKILL.md" for name in ("specdev-review", "specdev-trinity")}

pytestmark = pytest.mark.skipif(not _IMPL.is_file(), reason=".claude is absent")


def _fix_return_blocks() -> list[dict]:
    """Every fenced JSON example of the impl agent whose ``mode`` is ``fix`` and that parses."""
    blocks = re.findall(r"```json\n(.*?)\n```", _IMPL.read_text(encoding="utf-8"), flags=re.DOTALL)
    parsed = []
    for block in blocks:
        try:
            doc = json.loads(block)
        except json.JSONDecodeError:
            continue
        if isinstance(doc, dict) and doc.get("mode") == "fix" and "edits_applied" in doc:
            parsed.append(doc)
    return parsed


def test_the_fix_return_block_parses_and_holds_the_finding_lists():
    clean = [doc for doc in _fix_return_blocks() if doc.get("gate_status") == "clean"]
    assert clean, "no fix return example with gate_status clean"
    assert "findings_closed" in clean[0] and "findings_open" in clean[0]
    record = clean[0]["findings_closed"][0]
    assert {"signature", "location", "node", "field", "value", "edits", "parts"} <= set(record)


def test_the_fix_procedure_reads_each_fix_back_and_checks_the_sibling_fields():
    text = _IMPL.read_text(encoding="utf-8")
    assert "4b. Read each fix back" in text
    assert "4c. After the batch, read the other fields of each node you edited" in text


@pytest.mark.parametrize("skill", sorted(_SKILLS))
def test_the_loop_skills_print_the_closed_by_edits_line_and_check_one_write(skill):
    text = _SKILLS[skill].read_text(encoding="utf-8")
    assert "findings closed by" in text
    assert "`findings_closed`" in text and "`findings_open`" in text
    assert "specdev node show" in text or "`/specdev-review` does" in text
