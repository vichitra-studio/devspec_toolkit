"""The id migration (WI-M10-04): ``p2_id_mint``, ``p2_id_collisions``, ``p2_plan_milestone_key``, ``p2_anchor_rows``, ``p2_action_ids``.

Every test runs the scripts through ``run_migration`` on a ``tmp_path`` git copy of the mini host (``mini_host_1_1_1``) with
a temp toolkit root that says 1.2.0 (ruling P1).  ``p1_capture`` runs first, as it does in a real run.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable
from pathlib import Path

import pytest

from specdev_tools.migration import runner
from specdev_tools.migration.maps import legacy_ref_fields
from specdev_tools.migration.registry import script_from_module
from specdev_tools.migration.report import STATUS_OK
from specdev_tools.migration.scripts.v1_2_0 import (
    p1_capture,
    p2_action_ids,
    p2_anchor_rows,
    p2_id_collisions,
    p2_id_mint,
    p2_plan_milestone_key,
)
from specdev_tools.migration.spec_reads import capture_renames
from specdev_tools.validation.spec_check import run_spec_check_json

from ._support import REAL_ROOT, git, make_host, make_toolkit, tree_digest

ID_SCRIPTS = [script_from_module(m, "1.2.0") for m in (p1_capture, p2_id_collisions, p2_id_mint, p2_plan_milestone_key, p2_anchor_rows, p2_action_ids)]
CATALOG = "impl_context/ms_catalog_plan.json"
LATE_FEES = "impl_context/ms_late_fees_plan.json"
RESERVATIONS = "impl_context/ms_reservations_plan.json"


def _json(host: Path, rel: str):
    return json.loads((host / "spec" / rel).read_text(encoding="utf-8"))


def _commit_edit(host: Path, rel: str, edit: Callable[[dict], None]) -> None:
    path = host / "spec" / rel
    data = json.loads(path.read_text(encoding="utf-8"))
    edit(data)
    path.write_text(json.dumps(data, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")
    git(host, "add", "-A")
    git(host, "commit", "-q", "-m", f"edit {rel}")


@pytest.fixture
def toolkit(tmp_path) -> Path:
    return make_toolkit(tmp_path)


@pytest.fixture
def host(tmp_path) -> Path:
    return make_host(tmp_path)


def _migrate(host: Path, toolkit: Path, scripts=None):
    report = runner.run_migration(host / "spec", toolkit_root=toolkit, git_root=host, scripts=scripts or ID_SCRIPTS)
    assert report.status == STATUS_OK, report.errors
    return report


@pytest.fixture
def migrated(host, toolkit) -> Path:
    _migrate(host, toolkit)
    return host


def _items(host: Path, kind: str):
    return [item for item in read_items_from(host) if item["kind"] == kind]


def read_items_from(host: Path) -> list[dict]:
    return _json(host, "extras/migration/worklist.json")["items"]


def _all_strings(value):
    if isinstance(value, dict):
        for held in value.values():
            yield from _all_strings(held)
    elif isinstance(value, list):
        for held in value:
            yield from _all_strings(held)
    elif isinstance(value, str):
        yield value


def test_mint_slug_is_readable_and_stable(host, toolkit):
    _migrate(host, toolkit)
    charter = _json(host, "00_charter.json")
    assert [r["risk_id"] for r in charter["risks"]] == [
        "risk-volunteer-availability-at-the-cafe-lantern",
        "risk-the-hosting-plan-may-not-allow-a-second",
    ]
    assert [e["error_id"] for e in _json(host, "05_interface_contracts.json")["apis"][0]["errors"]] == ["err-query-too-short"]
    assert [s["secret_id"] for s in _json(host, "02a_delivery_baseline.json")["secrets"]] == ["secret-database-url", "secret-textline-api-key"]
    assert [g["gate_id"] for g in _json(host, "02a_delivery_baseline.json")["ci_gates"]] == ["lint", "unit-tests", "schema-validate"]
    assert [r["rule_id"] for r in _json(host, "10_governance.json")["rules"]][:2] == ["rule-validate-all", "rule-matrix"]
    digest = tree_digest(host / "spec")
    runner.run_migration(host / "spec", toolkit_root=toolkit, git_root=host, scripts=ID_SCRIPTS, allow_dirty=True)
    assert tree_digest(host / "spec") == digest


def test_mint_slug_suffixes_on_collision(host, toolkit):
    def twice(charter):
        charter["risks"] = ["Late fees confuse members", "Late  fees confuse members"]

    _commit_edit(host, "00_charter.json", twice)
    _migrate(host, toolkit)
    assert [r["risk_id"] for r in _json(host, "00_charter.json")["risks"]] == ["risk-late-fees-confuse-members", "risk-late-fees-confuse-members-2"]


def test_plan_item_uppercase_ids_are_kept(migrated):
    for rel in (CATALOG, LATE_FEES, RESERVATIONS):
        ids = [item["id"] for item in _json(migrated, rel)["plan"]["spec_alignment"]["checklist"]]
        assert ids and all(i == i.upper() and "_" in i for i in ids)
    assert "RESERVE_ENDPOINT_01" in [i["id"] for i in _json(migrated, RESERVATIONS)["plan"]["spec_alignment"]["checklist"]]


def test_stakeholder_gets_id_from_role_and_each_need_its_own(migrated):
    stakeholders = _json(migrated, "00_charter.json")["stakeholders"]
    assert [s["stakeholder_id"] for s in stakeholders] == ["sh-volunteer-librarian", "sh-neighbourhood-member"]
    needs = [n for s in stakeholders for n in s["needs"]]
    assert len(needs) == 3 and all(set(n) == {"need_id", "text"} for n in needs)
    assert len({n["need_id"] for n in needs}) == 3
    assert needs[0] == {"need_id": "need-check-a-tool-out-in-under-a-minute", "text": "Check a tool out in under a minute"}


def test_collision_keeps_lower_step_and_renames_later_definition(migrated):
    fr = _json(migrated, "04_fr_list.json")["functional_requirements"]
    assert {"ac-catalog-search-1", "ac-reserve-tool-1"} <= {c["criterion_id"] for f in fr for c in f["acceptance_criteria"]}
    roadmap = _json(migrated, "14_roadmap.json")
    ids = [c["criterion_id"] for m in roadmap["milestones"] for t in m["tasks"] for c in t.get("acceptance_criteria", [])]
    assert "tc-catalog-search-1" in ids and "tc-reserve-tool-1" in ids
    assert "ac-catalog-search-1" not in ids and "ac-reserve-tool-1" not in ids


def test_milestone_collision_renames_the_09_copy(migrated):
    assert "milestone-late-fees" in [m["milestone_id"] for m in _json(migrated, "09_impl_plan.json")["milestones"]]
    assert "ms-late-fees" not in [m["milestone_id"] for m in _json(migrated, "09_impl_plan.json")["milestones"]]
    assert "ms-late-fees" in [m["milestone_id"] for m in _json(migrated, "14_roadmap.json")["milestones"]]


def test_capture_records_the_renames_of_phase_2_once(host, toolkit):
    """P20: the capture keeps the old id -> new id of every rename, in the run that renamed; a second run adds nothing."""
    _migrate(host, toolkit)
    renames = _json(host, "extras/migration/capture.json")["renames"]
    assert {(r["old"], r["new"], r["kind"]) for r in renames} == {
        ("ms-late-fees", "milestone-late-fees", "design-milestone"),
        ("ac-catalog-search-1", "tc-catalog-search-1", "task-criterion"),
        ("ac-reserve-tool-1", "tc-reserve-tool-1", "task-criterion"),
    }
    assert all(r["file"] for r in renames)
    before = tree_digest(host / "spec")
    _migrate(host, toolkit)
    assert tree_digest(host / "spec") == before


def test_capture_renames_reader_maps_old_ids_per_kind(host, toolkit):
    from specdev_tools.migration.context import MigrationContext
    from specdev_tools.migration.writer import DocumentSet

    _migrate(host, toolkit)
    ctx = MigrationContext(str(host / "spec"), str(host), str(host), str(toolkit), True, DocumentSet(str(host / "spec")), "1.1.1", "1.2.0")
    assert capture_renames(ctx)["design-milestone"] == {"ms-late-fees": "milestone-late-fees"}


def test_typed_reference_moves_with_its_definition(migrated):
    """14 ``source_milestones`` fixes the kind (a 09 milestone): it follows the renamed 09 copy; the fields that name the 14 milestone stay."""
    late = next(m for m in _json(migrated, "14_roadmap.json")["milestones"] if m["milestone_id"] == "ms-late-fees")
    assert late["source_milestones"] == ["milestone-late-fees"]
    assert [i["milestone_ref"] for i in _json(migrated, LATE_FEES)["plan"]["spec_alignment"]["checklist"] if "milestone_ref" in i] == ["ms-late-fees"] * 2
    anchor_about = [row["about"] for row in _json(migrated, "16_impl_context.json")["plan"]["milestone_index"]]
    assert ["ms-late-fees"] in anchor_about


def test_untyped_prose_citation_is_not_rewritten_and_gives_one_worklist_item(migrated):
    item = next(i for i in _json(migrated, CATALOG)["plan"]["spec_alignment"]["checklist"] if i["id"] == "CATALOG_SEARCH_01")
    assert "`ac-catalog-search-1`" in item["description"]
    found = [i for i in _items(migrated, "collided-id-citation") if i["about"] == "CATALOG_SEARCH_01"]
    assert len(found) == 1
    assert "criterion at 04_fr_list.json" in found[0]["evidence"] and "task-criterion at 14_roadmap.json" in found[0]["evidence"]
    assert "tc-catalog-search-1" in found[0]["evidence"]
    # the plan is closed and frozen: the person is told to leave the text, not to edit a frozen plan
    assert "closed and frozen: leave the text as it is and resolve the item" in found[0]["proposal"]


def test_ambiguity_item_duplicates_are_left_for_p4(migrated):
    errors, _ = run_spec_check_json(str(REAL_ROOT), str(migrated / "spec"), git_root=str(migrated), spec_root=str(migrated / "spec"))
    dups = sorted(e.message.split("'")[1] for e in errors if e.code == "E704")
    assert dups == ["amb-fee-rounding", "amb-pickup-hours", "amb-sms-retry"]
    promoted = _items(migrated, "duplicate-promoted-item")
    assert [i["about"] for i in promoted] == ["amb-fee-rounding"]
    assert promoted[0]["audience"] == "operator" and promoted[0]["blocking"] is True
    # the run renames the plan's copy, so both are deleted by id; the item no longer says `--id` refuses the id
    assert "`amb-fee-rounding-2`" in promoted[0]["proposal"] and "specdev json delete --id amb-fee-rounding`" in promoted[0]["proposal"]
    assert "refuses it" not in promoted[0]["proposal"]


def test_renamed_collision_writes_no_alias(migrated):
    for path in (migrated / "spec").glob("*.json"):
        assert "aliases" not in path.read_text(encoding="utf-8")


def test_no_anchor_row_reuses_a_14_milestone_id(migrated):
    milestones = {m["milestone_id"] for m in _json(migrated, "14_roadmap.json")["milestones"]}
    rows = _json(migrated, "16_impl_context.json")["plan"]["milestone_index"]
    assert len(rows) == 3
    for row in rows:
        assert row["anchor_id"] not in milestones and "milestone_id" not in row
        assert row["anchor_id"] == "anchor-" + row["about"][0] and row["about"][0] in milestones
        assert {"status", "summary", "checklist_id_prefix"} <= set(row)


def test_plan_milestone_key_is_set_when_batch_stem_differs(migrated):
    assert _json(migrated, CATALOG)["milestone"] == "ms-catalog-basics"  # file ms_catalog_plan.json
    assert _json(migrated, LATE_FEES)["milestone"] == "ms-late-fees"
    assert _json(migrated, RESERVATIONS)["milestone"] == "ms-reservations"


def test_no_plan_file_is_renamed(host, toolkit):
    before = sorted(p.name for p in (host / "spec" / "impl_context").iterdir())
    _migrate(host, toolkit)
    assert sorted(p.name for p in (host / "spec" / "impl_context").iterdir()) == before


def test_every_plan_action_gets_an_id(migrated):
    items = _json(migrated, RESERVATIONS)["plan"]["spec_alignment"]["checklist"]
    actions = [a for i in items for a in i["implementation"]["actions"]]
    assert actions and all(a["id"].startswith("a") for a in actions)
    for item in items:
        ids = [a["id"] for a in item["implementation"]["actions"]]
        assert len(ids) == len(set(ids))


def test_legacy_closed_plans_get_no_action_ids(migrated):
    """P13: the plan closed by verdict and the plan closed by the 14 status alone get the milestone key and nothing else."""
    for rel in (CATALOG, LATE_FEES):
        actions = [a for i in _json(migrated, rel)["plan"]["spec_alignment"]["checklist"] for a in i.get("implementation", {}).get("actions", [])]
        assert actions and not any("id" in a for a in actions)


def test_second_run_mints_no_action_id(host, toolkit):
    _migrate(host, toolkit)
    digest = tree_digest(host / "spec")
    again = runner.run_migration(host / "spec", toolkit_root=toolkit, git_root=host, scripts=ID_SCRIPTS, allow_dirty=True)
    assert tree_digest(host / "spec") == digest
    p2 = [s for s in again.scripts if s.id.startswith("p2_")]
    assert len(p2) == 5 and all(s.detected == 0 and s.edits == 0 for s in p2)


def test_registry_drift_e622_is_gone_after_p2(host, toolkit):
    def codes(path: Path) -> Counter:
        errors, _ = run_spec_check_json(str(REAL_ROOT), str(path / "spec"), git_root=str(path), spec_root=str(path / "spec"))
        return Counter(e.code for e in errors)

    assert codes(host)["E622"] == 5
    _migrate(host, toolkit)
    assert codes(host)["E622"] == 0


def test_the_collision_map_names_every_field_of_the_host_facts():
    fields = legacy_ref_fields()["fields"]
    assert {"00", "01", "02", "03", "04", "05", "06", "07", "08", "09", "11", "14", "15", "plan", "invariants"} <= set(fields)
    assert fields["09"]["refs"]["depends_on"] == "design-milestone"
    assert fields["14"]["refs"]["depends_on"] == {"task": "task", "roadmap-milestone": "roadmap-milestone"}
