"""Phase 5, the legacy close and the triage rows (WI-M10-08): ``p5_legacy_close``, ``p5_triage``, and the closed rule reading the capture (ruling P23).

Each test runs the registered chain up to phase 5 through ``run_migration`` on a ``tmp_path`` git copy of the mini host with a temp toolkit root
that says 1.2.0 (ruling P1), so nothing here depends on whether a later phase (the lock baseline) is registered.  The module-scoped ``migrated`` run is
the shared result; a test that needs another 1.1.1 shape edits its own copy first (the fixture folder is never rewritten).
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path

import pytest

from specdev_tools.graph.build import build_graph
from specdev_tools.graph.names import ROW_DONE
from specdev_tools.lifecycle import anchor_store, frozen, plans
from specdev_tools.lifecycle.close_gate import verify_close_record
from specdev_tools.migration import registry, runner
from specdev_tools.migration.registry import PHASE_CAPTURE, PHASE_CLOSE, PHASE_CONTENT
from specdev_tools.migration.report import STATUS_OK
from specdev_tools.migration.scripts.v1_2_0 import p5_legacy_close, p5_triage
from specdev_tools.migration.spec_reads import (
    SOURCE_ANCHOR,
    SOURCE_ROADMAP,
    SOURCE_VERDICT,
    closed_milestones,
    closed_plan_files,
    closed_sources,
)
from specdev_tools.release.gate import _unsigned
from specdev_tools.validation.graph_checks.context import GraphCheckContext

from .test_convert_remove import context, edit, items, read
from ._support import REAL_ROOT, make_host, make_toolkit, tree_digest

CATALOG, RESERVATIONS, LATE_FEES = "ms-catalog-basics", "ms-reservations", "ms-late-fees"
PLAN_OF = {CATALOG: "impl_context/ms_catalog_plan.json", RESERVATIONS: "impl_context/ms_reservations_plan.json", LATE_FEES: "impl_context/ms_late_fees_plan.json"}
ANCHOR = "16_impl_context.json"


def migrate_to(tmp_path: Path, *edits: tuple[str, Callable[[dict], None]], last: int = PHASE_CLOSE):
    """The mini host copy migrated by the scripts of the phases up to *last* (the host, its temp toolkit and the report)."""
    toolkit = make_toolkit(tmp_path)
    host = make_host(tmp_path)
    for rel, change in edits:
        edit(host, rel, change)
    chain = [script for script in registry.discover_scripts() if script.spec.phase <= last]
    report = runner.run_migration(host / "spec", toolkit_root=toolkit, git_root=host, scripts=chain)
    assert report.status == STATUS_OK, report.errors
    return host, toolkit, report


@pytest.fixture(scope="module")
def migrated(tmp_path_factory):
    return migrate_to(tmp_path_factory.mktemp("p5"))


@pytest.fixture(scope="module")
def before_close(tmp_path_factory):
    """The same copy migrated by phases 1 to 4 only."""
    return migrate_to(tmp_path_factory.mktemp("p4"), last=PHASE_CONTENT)


def row_of(host: Path, milestone: str) -> anchor_store.AnchorRow:
    row = anchor_store.read_row(host / "spec", milestone)
    assert row is not None, milestone
    return row


def set_roadmap_status(milestone: str, status: str) -> Callable[[dict], None]:
    def change(data: dict) -> None:
        next(m for m in data["milestones"] if m["milestone_id"] == milestone)["status"] = status

    return change


def set_anchor_status(milestone: str, status: str) -> Callable[[dict], None]:
    def change(data: dict) -> None:
        next(r for r in data["plan"]["milestone_index"] if r["milestone_id"] == milestone)["status"] = status

    return change


def set_verdict(verdict: str) -> Callable[[dict], None]:
    def change(data: dict) -> None:
        data.setdefault("review", {})["verdict"] = verdict

    return change


def closed_ids(host: Path) -> set[str]:
    return {m for m, state in anchor_store.read_statuses(host / "spec").items() if state.status == ROW_DONE}


# ---------------------------------------------------------------------------
# The close
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("edits", "source"),
    [
        ((("14_roadmap.json", set_roadmap_status(RESERVATIONS, "done")),), SOURCE_ROADMAP),
        ((("16_impl_context.json", set_anchor_status(RESERVATIONS, "done")),), SOURCE_ANCHOR),
        (((PLAN_OF[RESERVATIONS], set_verdict("verified")),), SOURCE_VERDICT),
    ],
    ids=["roadmap-status", "anchor-status", "plan-verdict"],
)
def test_each_source_alone_closes_the_milestone(tmp_path, edits, source):
    host, _toolkit, _report = migrate_to(tmp_path, *edits)
    row = row_of(host, RESERVATIONS)
    assert row.status == ROW_DONE and row.close["signed_off_by"] == "legacy-migration" and row.close["source"] == source
    assert closed_ids(host) == {CATALOG, RESERVATIONS, LATE_FEES}


def test_disagreeing_sources_add_a_status_conflict_item(migrated, tmp_path):
    host, _toolkit, _report = migrated
    [conflict] = items(host, "status-conflict")
    assert conflict["about"] == LATE_FEES and conflict["step"] == "14" and conflict["audience"] == "operator" and conflict["blocking"] is True
    for said in ("14 says done", "anchor says pending", "09 ms-late-fees says pending", "closed by 14.status"):
        assert said in conflict["evidence"], said
    assert closed_ids(host) >= {LATE_FEES}, "a conflict closes the milestone all the same; the item asks the operator to confirm"
    # A verdict that is there and is not `verified` disagrees with a `done` status as well.
    other, _t, _r = migrate_to(tmp_path, (PLAN_OF[CATALOG], set_verdict("changes_requested")))
    assert {i["about"] for i in items(other, "status-conflict")} == {CATALOG, LATE_FEES}


def test_open_milestone_is_untouched(migrated, before_close):
    host, _toolkit, _report = migrated
    row = row_of(host, RESERVATIONS)
    assert row.status == "in_progress" and row.close is None
    assert all(i["about"] != RESERVATIONS for i in items(host, "status-conflict") + items(host, "legacy-close-skipped"))
    before_host, _t, _r = before_close
    assert (host / "spec" / PLAN_OF[RESERVATIONS]).read_bytes() == (before_host / "spec" / PLAN_OF[RESERVATIONS]).read_bytes()
    assert frozen.is_frozen(host / "spec", RESERVATIONS) is False


def test_close_record_names_source_and_sets_plan_hash(migrated):
    host, _toolkit, _report = migrated
    spec = host / "spec"
    sources = {CATALOG: f"{SOURCE_ROADMAP}, {SOURCE_ANCHOR}, {SOURCE_VERDICT}", LATE_FEES: SOURCE_ROADMAP}
    for milestone, source in sources.items():
        row = row_of(host, milestone)
        assert row.status == ROW_DONE
        assert row.close == {
            "signed_off_by": "legacy-migration",
            "source": source,
            "signoff": None,
            "plan_hash": plans.plan_hash(plans.require_plan(spec, milestone)),
        }
        assert verify_close_record(row) == []
    assert [e for e in _unsigned(GraphCheckContext.from_graph(build_graph(str(spec), str(REAL_ROOT)), None, None, spec_root=str(spec)))] == []


def test_frozen_plan_drift_is_quiet_after_close(migrated, before_close):
    host, _toolkit, _report = migrated
    spec = str(host / "spec")
    report = frozen.check_frozen_plans(spec)
    assert report.errors == () and (report.closed, report.compared) == (2, 2)
    assert [frozen.frozen_plan_drift(spec, m) for m in (CATALOG, LATE_FEES)] == [None, None]
    # The plans are the ones phase 4 left: the close phase writes no plan file.
    before_host, _t, _r = before_close
    for rel in PLAN_OF.values():
        assert (host / "spec" / rel).read_bytes() == (before_host / "spec" / rel).read_bytes(), rel


def test_plan_edit_after_close_is_recorded_as_close_migration(tmp_path):
    host, _toolkit, _report = migrate_to(tmp_path)
    spec = str(host / "spec")
    plan = host / "spec" / PLAN_OF[CATALOG]
    data = json.loads(plan.read_text(encoding="utf-8"))
    data["owner"] = "engineering"
    plan.write_text(json.dumps(data, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")
    assert "changed" in (frozen.frozen_plan_drift(spec, CATALOG) or ""), "an unrecorded edit of a closed plan is E827"
    anchor_store.append_close_migration(spec, CATALOG, plans.plan_hash(plan), "owner set by a worklist resolution", repo_root=str(REAL_ROOT))
    assert frozen.frozen_plan_drift(spec, CATALOG) is None and frozen.check_frozen_plans(spec).errors == ()
    assert row_of(host, CATALOG).close["migrations"] == [{"hash_after": plans.plan_hash(plan), "note": "owner set by a worklist resolution"}]


# ---------------------------------------------------------------------------
# Open items
# ---------------------------------------------------------------------------


def test_anchor_ambiguities_become_blocking_triage_items(migrated, tmp_path):
    host, _toolkit, _report = migrated
    found = items(host, "anchor-open-item")
    assert {i["about"] for i in found} == {"amb-fee-rounding", "amb-card-renewal"}
    assert all(i["blocking"] is True and i["audience"] == "operator" and i["step"] == "16" for i in found)
    # A resolved anchor item is not listed.
    resolved = lambda d: d["plan"]["ambiguities"][1].update(status="resolved")  # noqa: E731
    other, _t, _r = migrate_to(tmp_path, (ANCHOR, resolved))
    assert {i["about"] for i in items(other, "anchor-open-item")} == {"amb-fee-rounding"}


def test_frozen_plan_items_become_informational_items(migrated):
    host, _toolkit, report = migrated
    listed = items(host, "legacy-open-item")
    assert listed and all(i["blocking"] is False for i in listed)
    assert {i["about"] for i in listed} == {LATE_FEES} and all(i["id"].endswith("amb-pickup-hours") for i in listed), "only the closed plan's not-resolved items; the open plan keeps its own"
    residue = next(s.residue for s in report.scripts if s.id == "p5_triage")
    assert f"open items in frozen plans: {len(listed)} (listed by p4_ambiguities as legacy-open-item)" in residue


def test_decisions_seed_item_and_trinity_seed_item(migrated, tmp_path):
    host, _toolkit, _report = migrated
    [decisions] = items(host, "decisions-seed")
    assert decisions["about"] == "seed-decision-clarifications" and decisions["blocking"] is True and decisions["step"] == "00"
    assert items(host, "seed-trinity-route") == [], "the mini host routes no seed to a trinity step"
    add_route = lambda d: d["step_requirements"].update({"16a": ["seed-volunteer-roster"]})  # noqa: E731
    other, _t, _r = migrate_to(tmp_path, ("common/seed_manifest.json", add_route))
    [trinity] = items(other, "seed-trinity-route")
    assert trinity["about"] == "16a" and "seed-volunteer-roster" in trinity["evidence"] and trinity["blocking"] is False


def test_pending_tasks_in_closed_milestones_listed(migrated, tmp_path):
    host, _toolkit, _report = migrated
    [pending] = items(host, "pending-task")
    assert pending["about"] == "task-catalog-import" and pending["blocking"] is False and pending["audience"] == "operator"
    assert "Waiting for the volunteers" in pending["evidence"]
    # task-fee-endpoint is `deferred` (not listed), tasks of the open milestone are not listed.
    make_in_progress = lambda d: next(t for m in d["milestones"] if m["milestone_id"] == LATE_FEES for t in m["tasks"] if t["task_id"] == "task-fee-endpoint").update(status="in_progress")  # noqa: E731
    other, _t, _r = migrate_to(tmp_path, ("14_roadmap.json", make_in_progress))
    assert {i["about"] for i in items(other, "pending-task")} == {"task-catalog-import", "task-fee-endpoint"}


def test_triage_has_no_signer_item(migrated):
    host, _toolkit, _report = migrated
    for item in read(host, "extras/migration/worklist.json")["items"]:
        assert "signer" not in json.dumps(item).lower(), item["id"]


# ---------------------------------------------------------------------------
# Host rows
# ---------------------------------------------------------------------------


def test_p_staging_environment_item(migrated, tmp_path):
    host, _toolkit, _report = migrated
    [staging] = items(host, "staging-environment")
    assert staging["about"] == "staging" and staging["step"] == "02a" and staging["blocking"] is False and "scope: out" in staging["proposal"]
    run_in_staging = lambda d: next(j for j in d["jobs"] if j["job_id"] == "gate-lint").update(environment_ref={"id": "cn:core:environment:staging", "kind": "environment", "version": "1.0.0"})  # noqa: E731
    other, _t, _r = migrate_to(tmp_path, ("12_ci_gates.json", run_in_staging))
    assert items(other, "staging-environment") == [], "a job that runs in staging is the staging job"


def test_seed_route_cleanup_items(migrated):
    host, _toolkit, _report = migrated
    found = {(i["step"], i["about"]): i for i in items(host, "seed-route-cleanup")}
    assert set(found) == {("00", "seed-volunteer-roster"), ("00", "seed-lending-overview"), ("02", "seed-hosting-plan"), ("02a", "seed-hosting-plan")}
    assert found[("00", "seed-volunteer-roster")]["evidence"].startswith("E747: ") and found[("02", "seed-hosting-plan")]["evidence"].startswith("E748: ")
    assert all(i["blocking"] is False and i["audience"] == "operator" for i in found.values())
    assert all(i["about"] != "seed-decision-clarifications" for i in found.values()), "the decisions seed has its own item"


# ---------------------------------------------------------------------------
# P23: the closed rule reads the capture; the 14 status leaves
# ---------------------------------------------------------------------------


def legacy_rule(ctx) -> set[str]:
    """The closed rule as it read the live tree before P23: 14 ``done``, the anchor ``done`` or a legacy close, a plan verdict ``verified``."""
    from specdev_tools.migration.spec_reads import anchor_rows, plan_milestones, row_milestone, step_data

    closed = {m["milestone_id"] for m in step_data(ctx, "14")["milestones"] if m.get("status") == ROW_DONE}
    closed |= {row_milestone(r) for r in anchor_rows(ctx) if r.get("status") == ROW_DONE or anchor_store.is_legacy_close(r.get("close"))}
    closed |= {m for rel, m in plan_milestones(ctx).items() if (ctx.documents.load(rel).data.get("review") or {}).get("verdict") == "verified"}
    return closed


def test_closed_set_is_the_same_from_the_capture_and_from_the_live_tree(tmp_path, migrated, before_close):
    """Before the close the live tree and the capture give one set; after it (the 14 status gone) the capture still gives it."""
    host, toolkit, _report = migrate_to(tmp_path, last=PHASE_CAPTURE)
    ctx = context(host, toolkit)
    assert closed_milestones(ctx) == legacy_rule(ctx) == {CATALOG, LATE_FEES}
    assert closed_sources(ctx) == {CATALOG: [SOURCE_ROADMAP, SOURCE_ANCHOR, SOURCE_VERDICT], LATE_FEES: [SOURCE_ROADMAP]}
    for done_host, done_toolkit, _r in (before_close, migrated):
        done = context(done_host, done_toolkit)
        assert closed_milestones(done) == {CATALOG, LATE_FEES}
        assert closed_plan_files(done) == {PLAN_OF[CATALOG], PLAN_OF[LATE_FEES]}


def test_a_milestone_that_cannot_be_closed_is_listed_not_guessed(tmp_path):
    def no_row(data: dict) -> None:
        data["plan"]["milestone_index"][:] = [r for r in data["plan"]["milestone_index"] if r["milestone_id"] != LATE_FEES]

    host, _toolkit, _report = migrate_to(tmp_path, (ANCHOR, no_row))
    [skipped] = items(host, "legacy-close-skipped")
    assert skipped["about"] == LATE_FEES and skipped["blocking"] is True and "no anchor row is about ms-late-fees" in skipped["evidence"]
    assert row_of(host, CATALOG).status == ROW_DONE and anchor_store.read_row(host / "spec", LATE_FEES) is None


# ---------------------------------------------------------------------------
# The chain: idempotence and the registry
# ---------------------------------------------------------------------------


def test_a_second_run_changes_no_byte(tmp_path):
    host, toolkit, _report = migrate_to(tmp_path)
    before = tree_digest(host / "spec")
    chain = [s for s in registry.discover_scripts() if s.spec.phase <= PHASE_CLOSE]
    again = runner.run_migration(host / "spec", toolkit_root=toolkit, git_root=host, allow_dirty=True, scripts=chain)
    assert again.status in (STATUS_OK, "noop") and tree_digest(host / "spec") == before
    ctx = context(host, toolkit)
    assert p5_legacy_close.detect(ctx) == 0 and p5_triage.detect(ctx) == 0


def test_a_resolved_item_stays_resolved_on_a_rerun(tmp_path):
    host, toolkit, _report = migrate_to(tmp_path)
    path = host / "spec" / "extras" / "migration" / "worklist.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    target = next(i for i in data["items"] if i["kind"] == "pending-task")
    target.update(resolved=True, note="deferred by the desk lead")
    path.write_text(json.dumps(data, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")
    ctx = context(host, toolkit)
    assert p5_triage.detect(ctx) == 0 and p5_legacy_close.detect(ctx) == 0


def test_the_scripts_are_discovered_with_their_ids():
    found = {script.spec.id: script for script in registry.discover_scripts()}
    for module in (p5_legacy_close, p5_triage):
        assert found[module.SCRIPT.id].spec.phase == PHASE_CLOSE and os.path.basename(module.__file__) == f"{module.SCRIPT.id}.py"
