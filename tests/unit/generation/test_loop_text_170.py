"""H-170-1 and H-133-1: the fix agent reads each fix back and returns a record per finding.

These tests read agent and skill text under ``.claude``.
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


def _outcome_examples() -> list[dict]:
    """Every fenced JSON example of the impl agent that parses and holds ``outcomes``."""
    blocks = re.findall(r"```json\n(.*?)\n```", _IMPL.read_text(encoding="utf-8"), flags=re.DOTALL)
    parsed = []
    for block in blocks:
        try:
            doc = json.loads(block)
        except json.JSONDecodeError:
            continue
        if isinstance(doc, dict) and "outcomes" in doc:
            parsed.append(doc)
    return parsed


def test_the_outcome_example_parses_and_passes_the_tools_intake():
    """The record per finding is the outcome file; `fix_checks` reads the same fields the example gives."""
    from specdev_tools.loop.briefs import FIX_SHAPE

    examples = _outcome_examples()
    assert examples, "no outcome example in the impl agent"
    allowed = set(FIX_SHAPE["outcomes"][0])
    for entry in examples[0]["outcomes"]:
        assert set(entry) <= allowed, set(entry) - allowed
        assert entry["outcome"] in FIX_SHAPE["outcomes"][0]["outcome"].split(" | ")
    assert {e["outcome"] for e in examples[0]["outcomes"]} >= {"fixed", "accepted", "declined"}


def test_the_fix_procedure_reads_each_fix_back_and_checks_the_sibling_fields():
    text = _IMPL.read_text(encoding="utf-8")
    assert "4. Read each fix back before you call it fixed" in text
    assert "5. Read the other fields of each node you edited" in text
    assert "A write that was refused is not a fix" in text


def test_the_tool_not_the_skill_checks_what_a_fixer_claims():
    """H-133-1: a claimed fix that changed nothing is no fix (tested on a run in tests/unit/loop); no skill re-checks it."""
    for skill in _SKILLS.values():
        text = skill.read_text(encoding="utf-8")
        assert "checks every file an agent writes" in " ".join(text.split())
        assert "`findings_closed`" not in text


def test_a_round_reports_its_progress(tmp_path: Path) -> None:
    """H-133-1: the report of a run gives each round's findings by severity, and every finding with its status and attempts."""
    from unit.loop.test_loop_commands import FINDING, KEY, loop, review
    from unit.trace._lock_support import git_copy_of_example

    host = git_copy_of_example(tmp_path / "host")
    run_id = loop(host, "start", "--kind", "step", "04", "--readers", "1", "--cap", "1")["run_id"]
    note = dict(FINDING, kind="gap", severity="P2")
    review(host, run_id, loop(host, "next", run_id), [FINDING, note])
    done = loop(host, "next", run_id)
    summary = json.loads(Path(done["summary"]).read_text())
    assert [(r["round"], r["P0"], r["P1"], r["P2"], r["rejected"]) for r in summary["rounds"]] == [(1, 0, 1, 1, 0)]
    assert [(f["key"], f["status"], f["attempts"]) for f in summary["findings"] if f["key"] == KEY] == [(KEY, "open", 0)]
    report = Path(done["report"]).read_text()
    assert "| Round | P0 | P1 | P2 | Refused | Reviewers | Nodes read |" in report
    assert re.search(r"^\| 1 \| 0 \| 1 \| 1 \| 0 \| 1 \| \d+ \|$", report, flags=re.MULTILINE), report
    assert f"- {KEY} (open): {FINDING['message']}" in report
