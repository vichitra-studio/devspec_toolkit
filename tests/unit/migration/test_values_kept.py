"""Round-1 review of M10 (X1): a value of the host's spec is kept, and an odd text does not stop the run.

Every test runs the whole chain on a ``tmp_path`` git copy of the mini host with an edit of its own (the fixture is never
rewritten); the shapes are invented.
"""

from __future__ import annotations

import json

from specdev_tools.migration.minting import mint_id

from .test_convert_remove import items, migrate, read

JAPANESE = "日本語のリスク"
ARABIC = "؟؟؟"


def _by_text(rows: list[dict], field: str) -> dict[str, dict]:
    return {row[field]: row for row in rows}


# -- B2: two out_of_scope entries for one FR keep both reasons -------------------------------------------------------------


def test_two_out_of_scope_reasons_for_one_fr_are_both_kept(tmp_path):
    host, _toolkit, _report = migrate(tmp_path)
    fr = next(f for f in read(host, "04_fr_list.json")["functional_requirements"] if f["fr_id"] == "fr-waitlist-notify")
    assert fr["scope"] == "out"
    assert fr["scope_reason"] == "Waitlists are deferred; the desk phones members for now.; Waitlists are deferred to a later phase; no executable fixture exists to target."


def test_the_same_out_of_scope_reason_twice_is_written_once(tmp_path):
    same = "Waitlists wait for the next season."

    def reason(data: dict) -> None:
        data["out_of_scope"][0]["rationale"] = same

    host, _toolkit, _report = migrate(tmp_path, ("05_interface_contracts.json", reason), ("08_fixtures.json", reason))
    fr = next(f for f in read(host, "04_fr_list.json")["functional_requirements"] if f["fr_id"] == "fr-waitlist-notify")
    assert fr["scope_reason"] == same


# -- B1: a text without an ASCII letter or digit gets a numbered id ---------------------------------------------------------


def test_mint_id_falls_back_to_the_next_free_number():
    assert mint_id(JAPANESE, set(), prefix="risk-") == "risk-1"
    assert mint_id(ARABIC, {"risk-1"}, prefix="risk-") == "risk-2"
    assert mint_id("a plain risk", {"risk-1"}, prefix="risk-") == "risk-a-plain-risk"
    assert mint_id("???", set(), prefix=None) == "id-1"


def test_p2_id_mint_numbers_risks_written_in_other_scripts(tmp_path):
    def risks(data: dict) -> None:
        data["risks"] = [JAPANESE, ARABIC, *data["risks"][1:]]

    host, _toolkit, _report = migrate(tmp_path, ("00_charter.json", risks))
    ids = _by_text(read(host, "00_charter.json")["risks"], "text")
    assert (ids[JAPANESE]["risk_id"], ids[ARABIC]["risk_id"]) == ("risk-1", "risk-2")


def test_p4_exit_conditions_numbers_a_condition_written_in_another_script(tmp_path):
    def condition(data: dict) -> None:
        data["milestones"][0]["tasks"][0]["exit_conditions"] = [JAPANESE, ARABIC]

    host, _toolkit, _report = migrate(tmp_path, ("14_roadmap.json", condition))
    criteria = [c for m in read(host, "14_roadmap.json")["milestones"] for t in m["tasks"] for c in t["acceptance_criteria"]]
    made = _by_text(criteria, "text")
    assert (made[JAPANESE]["criterion_id"], made[ARABIC]["criterion_id"]) == ("tc-1", "tc-2")


def test_p4_step10_rules_numbers_a_review_rule_written_in_another_script(tmp_path):
    def requirement(data: dict) -> None:
        data["review_policy"]["verdict_requirements"] = [JAPANESE, ARABIC]

    host, _toolkit, _report = migrate(tmp_path, ("10_governance.json", requirement))
    rules = _by_text(read(host, "10_governance.json")["rules"], "text")
    assert (rules[JAPANESE]["rule_id"], rules[ARABIC]["rule_id"]) == ("rule-1", "rule-2")
    assert {i["about"] for i in items(host, "rule-reason")} >= {"rule-1", "rule-2"}


def test_a_rerun_after_a_numbered_id_mints_nothing(tmp_path):
    from specdev_tools.migration import runner

    from ._support import git, tree_digest

    def edits(data: dict) -> None:
        data["risks"] = [JAPANESE, *data["risks"][1:]]

    host, toolkit, _report = migrate(tmp_path, ("00_charter.json", edits))
    git(host, "add", "-A")
    git(host, "commit", "-q", "--no-verify", "-m", "migrated")
    before = tree_digest(host)
    runner.run_migration(host / "spec", toolkit_root=toolkit, git_root=host)
    assert tree_digest(host) == before


# -- B3: the reason a whole open plan was deferred is kept ------------------------------------------------------------------

DEFERRED_REASON = "The vendor contract waits on legal review for the whole milestone."


def _defer(data: dict) -> None:
    data["plan"]["status"] = "deferred"
    data["plan"]["deferred_reason"] = DEFERRED_REASON


def test_the_deferral_of_an_open_plan_is_captured_and_listed(tmp_path):
    host, _toolkit, _report = migrate(tmp_path, ("impl_context/ms_reservations_plan.json", _defer))
    held = next(p for p in read(host, "extras/migration/capture.json")["milestone_status"]["plans"] if p["file"].endswith("ms_reservations_plan.json"))
    assert held["legacy_plan_status"] == "deferred" and held["legacy_plan_deferred_reason"] == DEFERRED_REASON
    assert "deferred_reason" not in read(host, "impl_context/ms_reservations_plan.json")["plan"]
    [item] = [i for i in items(host, "plan-item-disposition") if i["id"].endswith("plan-deferred")]
    assert (item["audience"], item["blocking"], item["about"]) == ("operator", False, "ms-reservations")
    assert DEFERRED_REASON.rstrip(".") in item["evidence"]
    assert 'specdev milestone defer ms-reservations --reason "' in item["proposal"]


def test_a_closed_plan_keeps_its_deferred_reason_and_lists_nothing(tmp_path):
    host, _toolkit, _report = migrate(tmp_path, ("impl_context/ms_catalog_plan.json", _defer))
    assert read(host, "impl_context/ms_catalog_plan.json")["plan"]["deferred_reason"] == DEFERRED_REASON
    assert not [i for i in items(host, "plan-item-disposition") if i["id"].endswith("plan-deferred")]


def test_an_active_open_plan_lists_no_plan_deferral(tmp_path):
    host, _toolkit, _report = migrate(tmp_path)
    assert not [i for i in items(host, "plan-item-disposition") if i["id"].endswith("plan-deferred")]
    assert all("legacy_plan_deferred_reason" not in p for p in read(host, "extras/migration/capture.json")["milestone_status"]["plans"])


# -- A-2: a renamed duplicate open item is recorded in the capture ----------------------------------------------------------


def test_a_renamed_duplicate_open_item_is_recorded_in_the_capture(tmp_path):
    host, _toolkit, report = migrate(tmp_path)
    rows = [r for r in read(host, "extras/migration/capture.json")["renames"] if r["kind"] == "ambiguity-item"]
    printed = [line for s in report.scripts if s.id == "p4_ambiguities" for line in s.residue if line.startswith("duplicate id renamed")]
    assert len(rows) == len(printed) == 2
    assert {(r["old"], r["new"]) for r in rows} == {("amb-sms-retry", "amb-sms-retry-2"), ("amb-fee-rounding", "amb-fee-rounding-2")}
    assert {r["file"] for r in rows} == {"impl_context/ms_reservations_plan.json"}


# -- B5 (ruling P28): the note of a converted trace entry is not carried, and the old file shows it ---------------------------


def test_the_note_of_a_converted_trace_entry_is_read_with_triage_legacy(tmp_path):
    from .test_align_triage_validate import specdev

    host, toolkit, _report = migrate(tmp_path)
    note = "A checkout of a tool on loan is refused"
    assert note not in "".join(p.read_text(encoding="utf-8") for p in (host / "spec").rglob("*.json") if p.name != "capture.json")
    code, out, err = specdev("triage", str(host / "spec"), "--legacy", "06", "--repo-root", str(toolkit), "--git-root", str(host))
    assert code == 0, err
    assert note in out
