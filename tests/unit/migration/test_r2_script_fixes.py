"""Round-2 fixes of the migration scripts (M10 review round 2): each test runs the registered chain on a ``tmp_path`` copy of the mini host."""

from __future__ import annotations

import json
from pathlib import Path

from specdev_tools.migration import runner
from specdev_tools.migration.report import STATUS_OK

from .test_convert_remove import edit, items, migrate, read
from ._support import git, make_host, make_toolkit

RESERVATIONS = "ms-reservations"
ANCHOR = "16_impl_context.json"
PLAN = "impl_context/ms_reservations_plan.json"


def _rerun(host: Path, toolkit: Path):
    git(host, "add", "-A")
    if git(host, "status", "--porcelain"):
        git(host, "commit", "-q", "-m", "migration")
    return runner.run_migration(host / "spec", toolkit_root=toolkit, git_root=host)


# --- BD-1: p4_ambiguities counts the index over every entry of the array -----------------------------------------------


def test_a_rerun_over_an_array_with_converted_items_deletes_the_right_one(tmp_path):
    """A done milestone no anchor row names: run 1 skips the close; once the plan names its milestone the rerun freezes the plan's open items."""

    def done(data: dict) -> None:
        for milestone in data["milestones"]:
            if milestone["milestone_id"] == RESERVATIONS:
                milestone["status"] = "done"

    def no_row(data: dict) -> None:
        data["plan"]["milestone_index"][:] = [r for r in data["plan"]["milestone_index"] if r["milestone_id"] != RESERVATIONS]

    host, toolkit, _report = migrate(tmp_path, ("14_roadmap.json", done), (ANCHOR, no_row))
    assert items(host, "legacy-close-skipped")
    before = [i["id"] for i in read(host, PLAN)["plan"]["ambiguities"]]
    edit(host, PLAN, lambda data: data.update(milestone=RESERVATIONS))
    again = _rerun(host, toolkit)
    assert again.status == STATUS_OK, again.errors
    after = [i["id"] for i in read(host, PLAN)["plan"].get("ambiguities", [])]
    # the converted item stays where it was (before the fix the rerun deleted it); the legacy ones are removed and listed
    assert "amb-sms-retry" in before and after == ["amb-sms-retry"]
    assert {i["evidence"].split(" ")[0] for i in items(host, "legacy-open-item")} >= {"amb-sms-quota", "amb-fee-rounding-2"}


# --- BD-4: p3_remove strips the stored computed names from node objects only -------------------------------------------


def test_a_content_hash_inside_a_fixture_payload_stays_and_one_on_a_node_goes(tmp_path):
    def payload_and_node(data: dict) -> None:
        data["fixtures"][0]["input"]["content_hash"] = "sha256:9f2c"
        data["fixtures"][0]["expected"]["body"]["tools"][0]["chain_stamp"] = "2026-04-01"
        data["fixtures"][0]["content_hash"] = "sha256:stored-on-the-node"

    host, _toolkit, report = migrate(tmp_path, ("08_fixtures.json", payload_and_node))
    fixture = read(host, "08_fixtures.json")["fixtures"][0]
    assert fixture["input"]["content_hash"] == "sha256:9f2c"
    assert fixture["expected"]["body"]["tools"][0]["chain_stamp"] == "2026-04-01"
    assert "content_hash" not in fixture
    residue = "\n".join(next(s.residue for s in report.scripts if s.id == "p3_remove"))
    assert "stored computed names (content_hash, chain_stamp): 1 removed" in residue


# --- BD-6: a renamed kind whose new file already exists says what happens ----------------------------------------------


def test_a_kind_file_that_cannot_be_renamed_because_the_target_exists_says_so(tmp_path):
    from specdev_tools.migration.report import STATUS_OK as ok

    toolkit, host = make_toolkit(tmp_path), make_host(tmp_path)
    target = host / "spec" / "canon" / "kinds" / "invariant.json"
    target.write_text(json.dumps({"kind": "invariant", "entries": []}), encoding="utf-8")
    git(host, "add", "-A")
    git(host, "commit", "-q", "-m", "an invariant kind file already there")
    report = runner.run_migration(host / "spec", toolkit_root=toolkit, git_root=host)
    assert report.status != ok
    [error] = [e for e in report.errors if "p3_host_canon" in e.message]
    assert "canon/kinds/invariant.json exists, so it was not moved" in error.message and "merge its entries" in error.message
