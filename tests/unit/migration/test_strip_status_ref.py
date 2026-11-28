"""``p3_strip_status_ref`` (v1_1_0, DEVSPEC-249): the first real script under the migration contract.

The 1.0.x shapes are built in ``tmp_path`` from the mini host's variant (live ``status_ref`` objects in step 04) and
from small step 14 and plan-file documents; the live ``status_ref`` shape is the one the variant's README names.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from specdev_tools.migration import runner
from specdev_tools.migration.context import MigrationContext
from specdev_tools.migration.registry import chain_for, discover_scripts
from specdev_tools.migration.report import STATUS_OK
from specdev_tools.migration.scripts.v1_1_0 import p3_strip_status_ref as script
from specdev_tools.migration.writer import DocumentSet

from ._support import MINI_HOST, git, make_host, make_toolkit, tree_digest

VARIANT = MINI_HOST / "variants" / "status_ref_1_0_x" / "04_fr_list.json"
STATUS = {"id": "cn:core:status:active", "kind": "status", "version": "1.0.0"}
KEEP = {"id": "cn:project:capability:browse-catalog", "kind": "capability", "version": "1.0.0"}


def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=4) + "\n", encoding="utf-8")


def _context(spec: Path) -> MigrationContext:
    return MigrationContext(str(spec), str(spec.parent), str(spec.parent), "unused", False, DocumentSet(str(spec)), "1.0.0", "1.2.0")


@pytest.fixture
def old_host(tmp_path):
    """The mini host stamped 1.0.0, with the 1.0.x step 04, a step 14 and a plan file that carry ``status_ref`` at depth."""
    host = make_host(tmp_path, version="1.0.0", commit=False)
    spec = host / "spec"
    shutil.copy(VARIANT, spec / "04_fr_list.json")
    _write(spec / "14_roadmap.json", {
        "milestones": [{
            "milestone_id": "ms-a", "status": "pending", "status_ref": STATUS,
            "tasks": [{"task_id": "t-1", "status": "done", "status_ref": STATUS, "extra": [{"deep": {"status_ref": STATUS}}]}],
        }],
        "canonical_refs_used": [KEEP, STATUS, {"id": "cn:project:status:blocked", "kind": "status", "version": "1.0.0"}],
    })
    _write(spec / "impl_context" / "ms_a_plan.json", {
        "milestone": "ms-a",
        "items": [{"id": "i-1", "status": "done", "status_ref": STATUS}],
        "canonical_refs_used": [STATUS],
    })
    _write(spec / "extras" / "notes.json", {"status_ref": "not a step file: left alone"})
    git(host, "add", "-A")
    git(host, "commit", "-q", "-m", "host 1.0.0")
    return host


def test_removes_status_ref_keys_at_every_depth(old_host, tmp_path):
    toolkit = make_toolkit(tmp_path)
    spec = old_host / "spec"
    before_notes = (spec / "extras" / "notes.json").read_bytes()
    fr_before = json.loads((spec / "04_fr_list.json").read_text(encoding="utf-8"))
    # step 04: 2 keys + 1 status id; step 14: 3 keys + 2 status ids; the plan: 1 key + 1 status id; extras is not read
    assert script.detect(_context(spec)) == 10
    report = runner.run_migration(spec, toolkit_root=toolkit, git_root=old_host, scripts=[s for s in discover_scripts() if s.id == script.SCRIPT.id])
    assert report.status == STATUS_OK, report.render()
    assert report.edits_by_script == {"p3_strip_status_ref": 10}
    for rel in ("04_fr_list.json", "14_roadmap.json", "impl_context/ms_a_plan.json"):
        text = (spec / rel).read_text(encoding="utf-8")
        assert "status_ref" not in text and "cn:core:status" not in text and ":status:" not in text, rel
    roadmap = json.loads((spec / "14_roadmap.json").read_text(encoding="utf-8"))
    assert roadmap["canonical_refs_used"] == [KEEP]
    assert roadmap["milestones"][0]["tasks"][0]["status"] == "done"
    fr_after = json.loads((spec / "04_fr_list.json").read_text(encoding="utf-8"))
    for old, new in zip(fr_before["functional_requirements"], fr_after["functional_requirements"]):
        assert {k: v for k, v in old.items() if k != "status_ref"} == new
    assert [r for r in fr_after["canonical_refs_used"]] == [r for r in fr_before["canonical_refs_used"] if r["kind"] != "status"]
    assert (spec / "extras" / "notes.json").read_bytes() == before_notes


def test_lines_the_script_did_not_touch_keep_their_bytes(old_host, tmp_path):
    spec = old_host / "spec"
    before = (spec / "04_fr_list.json").read_text(encoding="utf-8").splitlines()
    runner.run_migration(spec, toolkit_root=make_toolkit(tmp_path), git_root=old_host, scripts=[s for s in discover_scripts() if s.id == script.SCRIPT.id])
    after = (spec / "04_fr_list.json").read_text(encoding="utf-8").splitlines()
    assert len(after) < len(before)
    original = {line.rstrip(",") for line in before}
    assert all(line.rstrip(",") in original for line in after)  # only removals (and the comma of a new last item)
    assert (spec / "04_fr_list.json").read_text(encoding="utf-8").endswith("\n")


def test_rerun_makes_zero_edits(old_host, tmp_path):
    toolkit = make_toolkit(tmp_path)
    spec = old_host / "spec"
    only = [s for s in discover_scripts() if s.id == script.SCRIPT.id]
    assert runner.run_migration(spec, toolkit_root=toolkit, git_root=old_host, scripts=only).status == STATUS_OK
    done = tree_digest(old_host)
    assert script.detect(_context(spec)) == 0
    again = runner.run_migration(spec, toolkit_root=toolkit, git_root=old_host, allow_dirty=True, scripts=only)
    assert again.status == STATUS_OK and again.total_edits == 0
    assert tree_digest(old_host) == done


def test_a_tree_without_status_ref_has_nothing_to_detect(tmp_path):
    host = make_host(tmp_path)
    assert script.detect(_context(host / "spec")) == 0


def test_only_a_host_below_1_1_0_runs_it():
    scripts = discover_scripts()
    assert script.SCRIPT.id in [s.id for s in chain_for(scripts, "1.0.0", "1.2.0")]
    assert script.SCRIPT.id in [s.id for s in chain_for(scripts, "1.0.5", "1.2.0")]
    assert script.SCRIPT.id not in [s.id for s in chain_for(scripts, "1.1.0", "1.2.0")]
    assert script.SCRIPT.id not in [s.id for s in chain_for(scripts, "1.1.1", "1.2.0")]
    first = chain_for(scripts, "1.0.0", "1.2.0")[0]
    assert first.id == script.SCRIPT.id  # before every script of 1.2.0
