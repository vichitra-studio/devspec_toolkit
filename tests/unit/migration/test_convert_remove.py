"""Phase 3, the shape migration (WI-M10-05): ``p3_convert``, ``p3_remove``, ``p3_copies``, ``p3_host_canon``.

Every test runs the WHOLE registered chain through ``run_migration`` on a ``tmp_path`` git copy of the mini host with a temp
toolkit root that says 1.2.0 (ruling P1).  The module-scoped ``migrated`` run is the shared result; a test that needs another
1.1.1 shape edits its own copy first (the fixture folder is never rewritten).
"""

from __future__ import annotations

import copy
import json
import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

from specdev_tools.graph.build import build_graph
from specdev_tools.migration import runner
from specdev_tools.migration.context import MigrationContext
from specdev_tools.migration.maps import shape_map, shape_rows
from specdev_tools.migration.report import STATUS_OK
from specdev_tools.migration.scripts.v1_2_0.p3_remove import closed_plan_files, files_of_row, last_key, parents_at
from specdev_tools.migration.writer import DocumentSet
from specdev_tools.trace.computed_fields import check_stored_computed

from .test_runner_core import MINI_HOST, REAL_ROOT, git, make_host, make_toolkit, tree_digest

WORKLIST = "extras/migration/worklist.json"
CONVERT_TYPES_WITH_A_SOURCE = {"rename", "refs", "typed"}


def read(host: Path, rel: str):
    return json.loads((host / "spec" / rel).read_text(encoding="utf-8"))


def items(host: Path, kind: str | None = None) -> list[dict]:
    found = read(host, WORKLIST)["items"]
    return [i for i in found if kind is None or i["kind"] == kind]


def edit(host: Path, rel: str, change: Callable[[dict], None]) -> None:
    """Edit a file of the host copy and commit it (the migration refuses a dirty spec)."""
    path = host / "spec" / rel
    data = json.loads(path.read_text(encoding="utf-8"))
    change(data)
    path.write_text(json.dumps(data, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")
    git(host, "add", "-A")
    git(host, "commit", "-q", "-m", f"edit {rel}")


def migrate(tmp_path: Path, *edits: tuple[str, Callable[[dict], None]]):
    toolkit = make_toolkit(tmp_path)
    host = make_host(tmp_path)
    for rel, change in edits:
        edit(host, rel, change)
    report = runner.run_migration(host / "spec", toolkit_root=toolkit, git_root=host)
    assert report.status == STATUS_OK, report.errors
    return host, toolkit, report


@pytest.fixture(scope="module")
def migrated(tmp_path_factory):
    host, toolkit, report = migrate(tmp_path_factory.mktemp("p3"))
    return host, toolkit, report


def context(host: Path, toolkit: Path) -> MigrationContext:
    spec = str(host / "spec")
    return MigrationContext(spec, str(host), str(host), str(toolkit), True, DocumentSet(spec), "1.1.1", "1.2.0")


def rows_with_data(fixture_spec: Path, ctx: MigrationContext, rows: list[dict]) -> dict[str, int]:
    """``{row id: how many keys of the row the 1.1.1 host holds}`` (the row's own plan rule applied)."""
    closed = closed_plan_files(ctx)
    found: dict[str, int] = {}
    for row in rows:
        for rel in files_of_row(ctx, row, closed):
            data = json.loads((fixture_spec / rel).read_text(encoding="utf-8"))
            count = sum(last_key(row["path"]) in holder for holder in parents_at(data, row["path"]))
            if count:
                found[row["id"]] = found.get(row["id"], 0) + count
    return found


def test_no_removed_key_remains_after_p3(migrated):
    host, toolkit, _ = migrated
    ctx = context(host, toolkit)
    closed = closed_plan_files(ctx)
    assert closed == {"impl_context/ms_catalog_plan.json", "impl_context/ms_late_fees_plan.json"}
    leftover = []
    for row in [*shape_rows("p3_remove"), *shape_rows("p3_copies")]:
        for rel in files_of_row(ctx, row, closed):
            data = read(host, rel)
            leftover += [f"{row['id']} {rel}" for holder in parents_at(data, row["path"]) if last_key(row["path"]) in holder]
    assert leftover == []


def test_every_drop_row_is_applied(migrated):
    """Every drop-family row that the 1.1.1 mini host has data for names its removal in the run report (``residue``)."""
    host, toolkit, report = migrated
    ctx = context(host, toolkit)
    drop_rows = [*shape_rows("p3_remove"), *shape_rows("p3_copies")]
    present = rows_with_data(MINI_HOST / "spec", ctx, [r for r in drop_rows if r["id"] != "SC-13a-01"])
    assert len(present) > 40, "the mini host should exercise most drop rows"
    residue = "\n".join(report.to_json()["residue"])
    assert [row_id for row_id in present if f"{row_id}:" not in residue] == []


def test_every_rename_row_is_converted(migrated):
    host, toolkit, _ = migrated
    ctx = context(host, toolkit)
    closed = closed_plan_files(ctx)
    seen = 0
    for row in shape_rows("p3_convert"):
        spec = row["convert"]
        if spec["type"] not in CONVERT_TYPES_WITH_A_SOURCE:
            continue
        names = spec.get("fields") or [spec["field"]]
        for rel in files_of_row(ctx, row, closed):
            for holder in parents_at(read(host, rel), row["path"]):
                for name in names:
                    assert name not in holder, f"{row['id']}: {name}={holder[name]!r} was not converted"
        seen += 1
    assert seen >= 14
    sketch = read(host, "02_system_sketch.json")["connections"]
    assert sketch[0]["derives_from"] == ["desk-app"] and sketch[0]["connects_to"] == ["lending-service"]
    assert read(host, "12_ci_gates.json")["jobs"][1]["depends_on"] == ["gate-setup"]
    assert read(host, "15_scaffold.json")["interface_map"][0]["realises"] == ["api-catalog-search"]
    threat = read(host, "11_redteam.json")["threats"][0]
    assert threat["threatens"][0] == "api-checkout-create" and threat["mitigated_by"] == ["inv-no-double-checkout"]


def test_every_worklist_row_has_an_item(migrated):
    host, _, _ = migrated
    schedules = {i["about"] for i in items(host, "schedules")}
    assert schedules == {"milestone-catalog-basics", "milestone-reservations", "milestone-late-fees"}
    assert all(i["step"] == "09" and i["audience"] == "agent" and i["proposal"].startswith("schedule: fr-") for i in items(host, "schedules"))
    plan = read(host, "impl_context/ms_reservations_plan.json")
    wanted = {i["id"] for i in plan["plan"]["spec_alignment"]["checklist"] if "spec_ref" in i}
    assert wanted and wanted <= {i["about"] for i in items(host, "spec-ref-realises")}
    assert all("task criteria" in i["evidence"] for i in items(host, "spec-ref-realises"))
    closed_plan = read(host, "impl_context/ms_catalog_plan.json")
    assert any("spec_ref" in i for i in closed_plan["plan"]["spec_alignment"]["checklist"]), "a legacy-closed plan keeps spec_ref as history"
    assert not {i["about"] for i in items(host, "spec-ref-realises")} & {i["id"] for i in closed_plan["plan"]["spec_alignment"]["checklist"]}


def test_type_mismatch_in_old_ref_list_becomes_worklist_item(tmp_path):
    def mislabel(data: dict) -> None:
        entry = next(e for e in data["apis"][0]["trace"] if e["id"] == "fr-catalog-search")
        entry["type"] = "nfr"

    host, _, _ = migrate(tmp_path, ("05_interface_contracts.json", mislabel))
    api = read(host, "05_interface_contracts.json")["apis"][0]
    assert "fr-catalog-search" not in api.get("derives_from", []) and "trace" not in api
    found = [i for i in items(host, "trace-link") if i["about"] == "api-catalog-search" and "fr-catalog-search" in i["evidence"]]
    assert len(found) == 1 and "fixes nfr" in found[0]["evidence"] and "is a fr" in found[0]["evidence"]


def test_unknown_id_in_old_ref_list_becomes_worklist_item(tmp_path):
    def invent(data: dict) -> None:
        data["apis"][0]["trace"].append({"type": "fr", "id": "fr-never-written"})

    host, _, _ = migrate(tmp_path, ("05_interface_contracts.json", invent))
    assert any("fr-never-written" in i["evidence"] and "no node has this id" in i["evidence"] for i in items(host, "trace-link"))


def test_stored_computed_names_are_removed_everywhere(tmp_path):
    def stamp_fr(data: dict) -> None:
        data["functional_requirements"][0]["content_hash"] = "abc"

    def stamp_closed_plan(data: dict) -> None:
        data["plan"]["spec_alignment"]["checklist"][0]["chain_stamp"] = "def"

    host, toolkit, _ = migrate(tmp_path, ("04_fr_list.json", stamp_fr), ("impl_context/ms_catalog_plan.json", stamp_closed_plan))
    assert check_stored_computed(build_graph(str(host / "spec"), str(toolkit))) == []
    text = "".join(path.read_text(encoding="utf-8") for path in (host / "spec").rglob("*.json"))
    assert "content_hash" not in text and "chain_stamp" not in text
    closed = read(host, "impl_context/ms_catalog_plan.json")["plan"]["spec_alignment"]["checklist"][0]
    assert "milestone_ref" not in closed and "linked_test_expectation" in closed, "a closed plan loses the E768 names only"


def test_a_closed_plan_keeps_what_is_not_an_e768_name(migrated):
    host, _, _ = migrated
    closed = read(host, "impl_context/ms_catalog_plan.json")
    assert "execution_results" in closed["execution"] and "final_status" in closed["execution"]
    opened = read(host, "impl_context/ms_reservations_plan.json")
    assert "execution_results" not in opened["execution"]


def test_capability_goal_id_becomes_derives_from_to_metric(migrated, tmp_path):
    host, _, _ = migrated
    capability = read(host, "01_capabilities.json")["capabilities"][0]
    assert capability["derives_from"] == ["m-checkout-time"]
    assert not {"goal_id", "success_metric_refs", "trace"} & set(capability)

    def wrong_kind(data: dict) -> None:
        data["capabilities"][0]["goal_id"] = "fr-catalog-search"

    other, _, _ = migrate(tmp_path, ("01_capabilities.json", wrong_kind))
    assert read(other, "01_capabilities.json")["capabilities"][0]["derives_from"] == ["m-checkout-time"]
    assert any("fr-catalog-search" in i["evidence"] and "it is a fr" in i["evidence"] for i in items(other, "legacy-ref"))


def test_environment_host_keys_move_into_config(migrated):
    host, _, _ = migrated
    environments = read(host, "02a_delivery_baseline.json")["environments"]
    assert environments["dev"]["config"] == {"region": "eu-west-1", "log_level": "debug"}
    assert environments["prod"]["config"]["ghost_port"] == 2368
    assert environments["staging"]["config"]["lifecycle"] == "decommissioned-at-production-go-live"
    for environment in environments.values():
        assert set(environment) <= {"scope", "config", "derives_from", "lifecycle"}


def test_scope_defaults_and_reasons(migrated):
    host, _, _ = migrated
    capabilities = {c["capability_id"]: c for c in read(host, "01_capabilities.json")["capabilities"]}
    assert capabilities["cap-repair-queue"]["scope"] == "later" and "scope_reason" not in capabilities["cap-repair-queue"]
    assert any(i["about"] == "cap-repair-queue" for i in items(host, "scope-reason"))
    wont = next(f for f in read(host, "04_fr_list.json")["functional_requirements"] if f["fr_id"] == "fr-waitlist-notify")
    assert wont["scope"] == "out" and "priority" not in wont and wont["scope_reason"].startswith("Waitlists are deferred")
    assert all(g["scope"] == "in" for g in read(host, "02a_delivery_baseline.json")["ci_gates"])
    assert "out_of_scope" not in read(host, "05_interface_contracts.json") and "out_of_scope" not in read(host, "08_fixtures.json")


def test_fixture_targets_that_name_an_fr_become_items_with_the_criteria(migrated):
    host, _, _ = migrated
    fixture = next(f for f in read(host, "08_fixtures.json")["fixtures"] if f["fixture_id"] == "fix-checkout-conflict")
    assert fixture["verifies"] == ["api-checkout-create", "inv-no-double-checkout"]
    found = [i for i in items(host, "fixture-target") if i["about"] == "fix-checkout-conflict"]
    assert len(found) == 1 and "criteria of fr-checkout-tool" in found[0]["proposal"]


def test_a_connection_to_an_external_component_waits_for_the_third_party_pass(migrated):
    host, _, _ = migrated
    connection = next(c for c in read(host, "02_system_sketch.json")["connections"] if c["connection_id"] == "conn-lending-service-textline-sms")
    assert "connects_to" not in connection and "to" not in connection and connection["derives_from"] == ["lending-service"]
    found = [i for i in items(host, "connection-external") if i["about"] == "conn-lending-service-textline-sms"]
    assert len(found) == 1 and "to `textline-sms`" in found[0]["evidence"]


def test_retired_13a_and_trace_matrix_are_deleted(migrated):
    host, _, _ = migrated
    assert (MINI_HOST / "spec" / "13a_completeness_assessment.json").is_file() and (MINI_HOST / "spec" / "extras" / "trace_matrix.json").is_file()
    assert not (host / "spec" / "13a_completeness_assessment.json").exists()
    assert not (host / "spec" / "extras" / "trace_matrix.json").exists()
    assert (host / "spec" / "13_extension_manifest.json").is_file()


def test_host_canon_retired_kind_file_and_manifest_entry_removed(tmp_path):
    def add_retired_kind(host: Path) -> None:
        kind = {"$schema": "vc:canon:kind", "registry_version": "1.0.0", "kind": "completeness_dimension",
                "entries": [{"id": "cn:project:completeness_dimension:docs", "kind": "completeness_dimension", "preferred_label": "docs"}]}
        (host / "spec" / "canon" / "kinds" / "completeness_dimension.json").write_text(json.dumps(kind, indent=4) + "\n", encoding="utf-8")
        manifest = json.loads((host / "spec" / "canon" / "manifest.json").read_text(encoding="utf-8"))
        manifest["entries"].append(kind["entries"][0])
        (host / "spec" / "canon" / "manifest.json").write_text(json.dumps(manifest, indent=4) + "\n", encoding="utf-8")
        git(host, "add", "-A")
        git(host, "commit", "-q", "-m", "retired canon kind")

    toolkit = make_toolkit(tmp_path)
    host = make_host(tmp_path)
    add_retired_kind(host)
    report = runner.run_migration(host / "spec", toolkit_root=toolkit, git_root=host)
    assert report.status == STATUS_OK, report.errors
    assert not (host / "spec" / "canon" / "kinds" / "completeness_dimension.json").exists()
    assert all(e["kind"] != "completeness_dimension" for e in read(host, "canon/manifest.json")["entries"])
    assert (host / "spec" / "canon" / "kinds" / "interface.json").is_file(), "interface and dependency are kinds of the toolkit's canon: left alone"
    assert any("completeness_dimension" in line for line in report.to_json()["residue"])


def test_inv_kind_is_renamed_invariant(migrated):
    host, _, _ = migrated
    assert not (host / "spec" / "canon" / "kinds" / "inv.json").exists()
    renamed = read(host, "canon/kinds/invariant.json")
    assert renamed["kind"] == "invariant" and renamed["entries"][0]["id"] == "cn:project:invariant:no-double-checkout"
    manifest = [e for e in read(host, "canon/manifest.json")["entries"] if "no-double-checkout" in e["id"]]
    assert [(e["id"], e["kind"]) for e in manifest] == [("cn:project:invariant:no-double-checkout", "invariant")]


def test_the_retired_kinds_are_not_kinds_of_the_toolkit_canon():
    retired = shape_map()["host_canon"]["retired_kinds"]
    present = {json.loads(p.read_text(encoding="utf-8"))["kind"] for p in (REAL_ROOT / "canon" / "kinds").glob("*.json")}
    assert not set(retired) & present and "invariant" not in set(shape_map()["host_canon"]["renamed_kinds"])


def test_a_second_run_changes_no_byte(tmp_path):
    host, toolkit, _ = migrate(tmp_path)
    before = tree_digest(host / "spec")
    again = runner.run_migration(host / "spec", toolkit_root=toolkit, git_root=host)
    assert again.status == STATUS_OK and again.changed_files == []
    assert tree_digest(host / "spec") == before


def test_a_file_no_script_needs_to_change_is_byte_identical(migrated):
    """P17 per file: the indent-4 files these scripts do not touch come out as they went in."""
    host, _, report = migrated
    untouched = ["03_glossary.json", "13_extension_manifest.json", "canon/kinds/capability.json", "canon/kinds/term.json", "canon/kinds/interface.json"]
    for rel in untouched:
        assert rel not in report.changed_files, rel
        assert (host / "spec" / rel).read_bytes() == (MINI_HOST / "spec" / rel).read_bytes(), rel
    assert "08_fixtures.json" in report.changed_files
    assert (host / "spec" / "08_fixtures.json").read_text(encoding="utf-8").startswith('{\n  "$schema"'), "a file keeps its own indent (2)"


def test_the_14_milestone_status_stays_until_the_legacy_close(migrated):
    host, _, _ = migrated
    assert [m["status"] for m in read(host, "14_roadmap.json")["milestones"]] == ["done", "pending", "done"]


def test_no_schema_uri_or_file_rename_is_needed(migrated):
    """Every ``$schema`` and file name of the migrated mini host resolves at 1.2.0, so no script rewrites either (decision, WI-05 carried item)."""
    host, _, _ = migrated
    registry = json.loads((REAL_ROOT / "tools" / "schema_registry.json").read_text(encoding="utf-8"))
    steps = set(json.loads((REAL_ROOT / "tools" / "step_order.json").read_text(encoding="utf-8"))["steps"])
    for path in sorted((host / "spec").glob("[0-9][0-9]*.json")) + sorted((host / "spec" / "impl_context").glob("*.json")):
        assert json.loads(path.read_text(encoding="utf-8"))["$schema"] in registry, path.name
        if path.parent.name != "impl_context":
            assert path.name.split("_", 1)[0] in steps, path.name


def test_the_capture_still_validates_after_the_whole_chain(migrated):
    from specdev_tools.core.schema_validate import schema_violations

    host, _, _ = migrated
    assert schema_violations(str(REAL_ROOT), read(host, "extras/migration/capture.json")) == []
    assert read(host, "extras/migration/capture.json")["renames"]


def test_every_removed_value_a_later_script_reads_is_in_the_capture(migrated):
    """The rows that remove a value with `capture-then-remove` have data in the capture section they name (on the mini host)."""
    host, _, _ = migrated
    capture = read(host, "extras/migration/capture.json")
    for row in shape_rows("p3_remove"):
        if row["disposition"] == "capture-then-remove":
            section = capture[row["captured_in"].split(".")[0]]
            assert section, f"{row['id']}: the capture section {row['captured_in']} is empty on the mini host"
