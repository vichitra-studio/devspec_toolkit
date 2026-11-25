"""H-159-1 and H-159-2: the review loops remove a round's findings files first, and a finding's location is the node id.

The skill and agent tests read text under ``.claude``.
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


def test_a_round_reads_only_the_files_of_its_own_dispatch() -> None:
    """A stale file of an earlier round cannot be merged: every dispatch has its own folder, and a try its own name."""
    from specdev_tools.loop import store

    first, second = store.entry_path("run", 1, "r1", 1), store.entry_path("run", 2, "r1", 1)
    assert first != second and first.endswith("d1/r1.t1.json") and second.endswith("d2/r1.t1.json")
    assert store.entry_path("run", 1, "r1", 2).endswith("d1/r1.t2.json")


def test_a_stale_findings_file_is_not_merged_into_a_round(tmp_path: Path) -> None:
    """A file an earlier run or round left is on disk and holds a finding; the round's merge (``merge_round``) never reads it."""
    from unit.loop.test_loop_commands import FINDING, loop, review
    from unit.trace._lock_support import git_copy_of_example

    host = git_copy_of_example(tmp_path / "host")
    run_id = loop(host, "start", "--kind", "step", "04", "--review-only", "--readers", "1")["run_id"]
    action = loop(host, "next", run_id)
    expect = Path(action["entries"][0]["expect"])
    review(host, run_id, action, [FINDING])  # a complete file the round would take: the right round, scope and coverage
    stale = expect.read_text()
    expect.unlink()
    places = [
        expect.parent.parent / "d0" / expect.name,  # the folder of another dispatch
        expect.with_name(expect.name.replace(".t1.", ".t0.")),  # another try of this entry
        expect.with_name("r9.t1.json"),  # an entry this dispatch does not have
        host / ".specdev" / "findings" / "findings_04_1_r1.json",  # where the skills of 1.1.1 kept them
    ]
    for place in places:
        place.parent.mkdir(parents=True, exist_ok=True)
        place.write_text(stale)
    review(host, run_id, action)  # the reviewer of this round found nothing
    done = loop(host, "next", run_id)
    assert done["verdict"] == "CLEAN"
    assert json.loads(Path(done["summary"]).read_text())["findings"] == []
    assert all(place.is_file() for place in places)  # left alone, and not read


@_needs_claude
@pytest.mark.parametrize("skill", sorted(_SKILLS))
def test_no_loop_skill_handles_findings_files_itself(skill: str) -> None:
    text = _SKILLS[skill].read_text(encoding="utf-8")
    assert "rm -f .specdev/findings" not in text and "jq -s" not in text


@_needs_claude
def test_the_reviewer_agent_gives_the_node_id_form_of_location() -> None:
    text = _REVIEWER.read_text(encoding="utf-8")
    assert "fr-password-reset#statement" in text
    assert "functional_requirements/3" not in text


def test_the_findings_schema_describes_the_node_id_form() -> None:
    schema = json.loads(_FINDINGS_SCHEMA.read_text(encoding="utf-8"))
    description = schema["$defs"]["finding"]["properties"]["location"]["description"]
    assert description.startswith("Where the finding sits: the id of the node")
