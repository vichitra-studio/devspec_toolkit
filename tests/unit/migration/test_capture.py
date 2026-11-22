"""The capture-first worklist (WI-M10-03): ``p1_capture``, ``capture.json`` and the worklist API.

Every test runs the script through ``run_migration`` on a ``tmp_path`` git copy of the mini host (``mini_host_1_1_1``)
with a temp toolkit root that says 1.2.0 (ruling P1).  A second script, written in the test, stands for the later
phases: it removes content the capture must have kept.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from specdev_tools.core.schema_validate import validate_data_against_schema
from specdev_tools.migration import runner, writer, worklist
from specdev_tools.migration.context import MigrationContext
from specdev_tools.migration.registry import PHASE_SHAPES, Script, ScriptResult, ScriptSpec, script_from_module
from specdev_tools.migration.report import STATUS_OK
from specdev_tools.migration.scripts.v1_2_0 import p1_capture
from specdev_tools.migration.worklist import WorklistError, add_items, make_item, missing_items, read_items
from specdev_tools.validation.spec_check import run_spec_check_json

from .test_runner_core import MINI_HOST, REAL_ROOT, git, make_host, make_toolkit, tree_digest

CAPTURE = "spec/extras/migration/capture.json"
WORKLIST = "spec/extras/migration/worklist.json"
ROADMAP = "14_roadmap.json"
P1 = script_from_module(p1_capture, "1.2.0")


@pytest.fixture
def toolkit(tmp_path) -> Path:
    return make_toolkit(tmp_path)


@pytest.fixture
def host(tmp_path) -> Path:
    return make_host(tmp_path)


def _spec_json(host: Path, rel: str):
    return json.loads((host / "spec" / rel).read_text(encoding="utf-8"))


def _capture(host: Path) -> dict:
    return json.loads((host / CAPTURE).read_text(encoding="utf-8"))


def _fixture_json(rel: str):
    return json.loads((MINI_HOST / "spec" / rel).read_text(encoding="utf-8"))


def _shapes_script(edit) -> Script:
    """A phase-3 script that applies *edit(data_by_name)* to the loaded documents once (what P3 to P4 do to the tree)."""

    def detect(ctx) -> int:
        return 1 if "tech_stack" in ctx.documents.load(ROADMAP).data else 0

    def apply(ctx) -> ScriptResult:
        edit(ctx)
        return ScriptResult(edits=1)

    return Script(ScriptSpec("p3_remove", PHASE_SHAPES, touches=("*",)), "1.2.0", detect, apply, lambda before, after: [])


def _remove_old_fields(ctx) -> None:
    """Delete from the roadmap what the capture holds: the tech stack, task statuses and exit conditions."""
    roadmap = ctx.documents.load(ROADMAP).data
    del roadmap["tech_stack"]
    for milestone in roadmap["milestones"]:
        milestone["status"] = "removed"
        for task in milestone["tasks"]:
            task.pop("exit_conditions", None)
            task.pop("fr_refs", None)


def _context(host: Path, toolkit: Path) -> MigrationContext:
    return MigrationContext(str(host / "spec"), str(host), str(host), str(toolkit), False, writer.DocumentSet(str(host / "spec")), "1.1.1", "1.2.0")


def _run(host: Path, toolkit: Path, scripts, **kwargs):
    return runner.run_migration(host / "spec", toolkit_root=toolkit, git_root=host, scripts=scripts, **kwargs)


# ---------------------------------------------------------------------------
# The capture holds every row of the table
# ---------------------------------------------------------------------------


def _by(rows: list[dict], key: str, value: str = "legacy_status") -> dict:
    return {row[key]: row.get(value) for row in rows}


def test_capture_holds_every_row_of_the_table(host, toolkit):
    assert _run(host, toolkit, [P1]).status == STATUS_OK
    capture = _capture(host)
    status = capture["milestone_status"]
    tasks = {row["task"]: row for row in capture["task_status"]}
    plan_item_ids = {
        (f"impl_context/{name}", item["id"])
        for name in ("ms_catalog_plan.json", "ms_reservations_plan.json", "ms_late_fees_plan.json")
        for item in _fixture_json(f"impl_context/{name}")["plan"]["spec_alignment"]["checklist"]
        if "linked_test_expectation" in item
    }
    rows = {
        "milestone status, step 14": (_by(status["roadmap"], "milestone"), {"ms-catalog-basics": "done", "ms-reservations": "pending", "ms-late-fees": "done"}),
        "milestone status reason, step 14": (status["roadmap"][2]["legacy_milestone_status_reason"], "Closed by the desk lead after the two-day fee check"),
        "milestone status, step 09": (_by(status["impl_plan"], "milestone"), {"milestone-catalog-basics": "done", "milestone-reservations": "pending", "ms-late-fees": "pending"}),
        "milestone status, anchor": (_by(status["anchor"], "milestone"), {"ms-catalog-basics": "done", "ms-reservations": "in_progress", "ms-late-fees": "pending"}),
        "plan review verdicts": (_by(status["plans"], "file", "review_verdict"), {"impl_context/ms_catalog_plan.json": "verified", "impl_context/ms_late_fees_plan.json": None, "impl_context/ms_reservations_plan.json": None}),
        "plan.status": (set(_by(status["plans"], "file", "legacy_plan_status").values()), {"active"}),
        "task status": (_by(capture["task_status"], "task"), {"task-catalog-schema": "done", "task-catalog-search-endpoint": "done", "task-catalog-import": "pending", "task-reserve-endpoint": "pending", "task-checkout-return-flow": "done", "task-reserve-sms": "in_progress", "task-fee-calculator": "done", "task-fee-endpoint": "deferred"}),
        "task status reason": (tasks["task-fee-endpoint"]["legacy_status_reason"], "The desk will read fees off the loan screen first"),
        "task fr_refs and invariant_refs": ((tasks["task-checkout-return-flow"]["legacy_fr_refs"], tasks["task-checkout-return-flow"]["legacy_invariant_refs"]), (["fr-checkout-tool", "fr-return-tool"], ["inv-no-double-checkout"])),
        "tech_stack of 02, 09, 14": ([row["step"] for row in capture["third_party"]["tech_stacks"]], ["02", "09", "14"]),
        "tech_stack content": (capture["third_party"]["tech_stacks"][0]["legacy_tech_stack"], _fixture_json("02_system_sketch.json")["tech_stack"]),
        "02 external components": ([row["legacy_component"]["type"] for row in capture["third_party"]["external_components"]], ["external"]),
        "step 10 keys": (set(capture["governance"]), {"legacy_pr_rules", "legacy_review_policy", "legacy_reviewers", "legacy_spec_first_policy", "legacy_policy_ref"}),
        "step 10 pr_rules": (capture["governance"]["legacy_pr_rules"], ["validate-all", "matrix", "governance-check", "fixtures-lint", "test", "lint"]),
        "14 exit_conditions": (_by(capture["task_exit_conditions"], "task", "legacy_exit_conditions"), {"task-catalog-schema": ["The migration runs on a fresh database without errors"], "task-catalog-search-endpoint": ["GET /tools answers 200 with a page of tools"], "task-reserve-endpoint": ["POST /reservations answers 201 and 409 as specified"]}),
        "14 assumptions": (_by(capture["task_assumptions"], "task", "legacy_assumptions"), {"task-catalog-schema": ["PostgreSQL is available on the hosting plan"], "task-reserve-endpoint": ["Members always have a text-capable phone"]}),
        "16a security": (capture["plan_security"], [{"file": "impl_context/ms_catalog_plan.json", "legacy_spec_mutations": _fixture_json("impl_context/ms_catalog_plan.json")["plan"]["security"]["spec_mutations"], "legacy_new_fixtures": ["fix-search-empty-text"]}]),
        "plan items with linked_test_expectation": ({(row["file"], row["item"]) for row in capture["plan_items"] if "legacy_linked_test_expectation" in row}, plan_item_ids),
        "plan item fixture_ref": (_by(capture["plan_items"], "item", "legacy_fixture_ref")["RESERVE_ENDPOINT_01"], "fix-reserve-happy"),
        "plan item deferred_reason and wont_do_reason": (
            {row["item"]: (row.get("legacy_checklist_status"), row.get("legacy_deferred_reason") or row.get("legacy_wont_do_reason")) for row in capture["plan_items"] if "legacy_checklist_status" in row}["RESERVE_WAITLIST_01"],
            ("wont_do", "Waitlists are out of scope for this release; the desk phones members."),
        ),
        "linked_test_expectation as a list": (_by(capture["plan_items"], "item", "legacy_linked_test_expectation")["CATALOG_SEARCH_01"][0], "npm test -- catalog-search"),
        "09 depends_on": (_by(capture["milestone_ordering"]["pairs"], "milestone", "legacy_depends_on"), {"milestone-reservations": ["milestone-catalog-basics"], "ms-late-fees": ["milestone-reservations"]}),
        "typed dependencies of 09 and 14": ([(row["step"], row["legacy_dependency"]["type"]) for row in capture["milestone_ordering"]["typed_dependencies"]], [("09", "external"), ("14", "milestone"), ("14", "external")]),
        "dependency_ref of 09 and 14": ([row["step"] for row in capture["milestone_ordering"]["dependency_refs"]], ["09", "14"]),
        "milestone deliverables of 09 and 14": ([(row["step"], row["milestone"]) for row in capture["milestone_links"] if "legacy_deliverables" in row], [("09", "milestone-catalog-basics"), ("09", "milestone-reservations"), ("09", "ms-late-fees"), ("14", "ms-catalog-basics"), ("14", "ms-reservations"), ("14", "ms-late-fees")]),
        "14 source_milestones, fr_refs, capability_refs": ({key for row in capture["milestone_links"] if row["step"] == "14" for key in row}, {"step", "milestone", "legacy_source_milestones", "legacy_deliverables", "legacy_fr_refs", "legacy_capability_refs"}),
        "anchor fr_refs and context_path": ([(row["legacy_context_path"], row["legacy_fr_refs"]) for row in capture["milestone_links"] if row["step"] == "16"][0], ("spec/impl_context/ms_catalog_plan.json", ["fr-catalog-search"])),
        "open ambiguities (resolved ones are not copied)": (
            [(item["file"], item["step"], item["legacy_item"]["id"]) for item in capture["ambiguities"]],
            [
                ("16_impl_context.json", "16", "amb-fee-rounding"),
                ("16_impl_context.json", "16", "amb-card-renewal"),
                ("impl_context/ms_late_fees_plan.json", "16b", "amb-pickup-hours"),
                ("impl_context/ms_reservations_plan.json", "16a", "amb-fee-rounding"),
                ("impl_context/ms_reservations_plan.json", "16a", "amb-sms-retry"),
                ("impl_context/ms_reservations_plan.json", "16a", "amb-sms-quota"),
                ("impl_context/ms_reservations_plan.json", "16b", "amb-sms-retry"),
                ("impl_context/ms_reservations_plan.json", "16b", "amb-pickup-hours"),
            ],
        ),
        "impact[] of an open item": (capture["ambiguities"][1]["legacy_item"]["impact"], ["fr-reserve-tool", "api-reserve-create"]),
        "02a environments": (
            {row["environment"]: set(row["legacy_environment"]) for row in capture["environment_host_keys"]},
            {"dev": {"region", "log_level"}, "ci": {"runner"}, "staging": {"region", "lifecycle"}, "prod": {"region", "log_level", "ghost_port"}},
        ),
    }
    for name, (actual, expected) in rows.items():
        assert actual == expected, name


def test_capture_holds_the_legacy_command_ref_of_step_10(tmp_path, toolkit):
    host = make_host(tmp_path / "x")
    governance = host / "spec" / "10_governance.json"
    data = json.loads(governance.read_text(encoding="utf-8"))
    data["command_ref"] = {"id": "cn:project:command:specdev-check", "kind": "command", "version": "1.0.0"}
    governance.write_text(json.dumps(data, indent=4), encoding="utf-8")
    git(host, "commit", "-aqm", "command_ref")
    assert _run(host, toolkit, [P1]).status == STATUS_OK
    assert _capture(host)["governance"]["legacy_command_ref"] == data["command_ref"]


def test_capture_leaves_out_what_is_recoverable_or_deleted_later(host, toolkit):
    _run(host, toolkit, [P1])
    text = (host / CAPTURE).read_text(encoding="utf-8")
    capture = json.loads(text)
    resolved = {"amb-pickup-cutoff", "amb-late-pickup"}
    assert not resolved & {item["legacy_item"]["id"] for item in capture["ambiguities"]}
    assert all("trace" not in row["legacy_component"] for row in capture["third_party"]["external_components"])
    assert '"links"' not in text


# ---------------------------------------------------------------------------
# The header
# ---------------------------------------------------------------------------


def test_capture_header_names_source_commit_and_show_form(host, toolkit):
    commit = git(host, "rev-parse", "HEAD").strip()
    assert _run(host, toolkit, [P1]).status == STATUS_OK
    source = _capture(host)["source"]
    assert source["commit"] == commit
    assert source["spec_dir"] == "spec"
    assert source["show_form"] == f"git show {commit}:spec/<file>"
    old = git(host, "show", f"{commit}:spec/{ROADMAP}")
    assert source["file_hashes"][ROADMAP] == hashlib.sha256(old.encode("utf-8")).hexdigest()
    assert not [rel for rel in source["file_hashes"] if rel.startswith("extras/migration/")]
    assert source["file_hashes"]["extras/trace_matrix.json"]


def test_capture_holds_no_clock_value_and_no_absolute_path(host, toolkit, tmp_path):
    _run(host, toolkit, [P1])
    text = (host / CAPTURE).read_text(encoding="utf-8") + (host / WORKLIST).read_text(encoding="utf-8")
    assert str(tmp_path) not in text and "specdev-migrate-" not in text
    assert not re.search(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[.\d]*Z", text.replace("2026-", "X"))


# ---------------------------------------------------------------------------
# One time, byte for byte
# ---------------------------------------------------------------------------


def test_rerun_after_p3_leaves_capture_byte_identical(host, toolkit):
    scripts = [P1, _shapes_script(_remove_old_fields)]
    assert _run(host, toolkit, scripts).status == STATUS_OK
    first = (host / CAPTURE).read_bytes()
    assert "tech_stack" not in _spec_json(host, ROADMAP)
    again = _run(host, toolkit, scripts)
    assert again.status == STATUS_OK, again.render()
    assert [s.detected for s in again.scripts] == [0, 0]
    assert (host / CAPTURE).read_bytes() == first
    assert _capture(host)["third_party"]["tech_stacks"][2]["step"] == "14"


def test_rerun_after_apply_and_commit_leaves_capture_byte_identical(host, toolkit):
    scripts = [P1, _shapes_script(_remove_old_fields)]
    assert _run(host, toolkit, scripts).status == STATUS_OK
    first = (host / CAPTURE).read_bytes()
    git(host, "add", "-A")
    git(host, "commit", "-qm", "mechanical migration")
    head = git(host, "rev-parse", "HEAD")
    again = _run(host, toolkit, scripts)
    assert again.status == STATUS_OK, again.render()
    assert (host / CAPTURE).read_bytes() == first
    assert _capture(host)["source"]["commit"] != head.strip()
    assert git(host, "status", "--porcelain").strip() == ""


def test_capture_survives_a_run_that_starts_again_on_a_migrated_tree_with_no_old_values(host, toolkit):
    """The detect rule reads the file, not the tree: a stripped tree is never captured a second time as empty data."""
    scripts = [P1, _shapes_script(_remove_old_fields)]
    _run(host, toolkit, scripts)
    ctx = _context(host, toolkit)
    assert p1_capture.detect(ctx) == 0
    assert [row["step"] for row in p1_capture.build_capture(ctx)["third_party"]["tech_stacks"]] == ["02", "09"]


def test_two_copies_of_one_host_give_the_same_bytes(tmp_path, toolkit):
    first = make_host(tmp_path / "a")
    second = tmp_path / "b"
    shutil.copytree(first, second)
    for host in (first, second):
        assert _run(host, toolkit, [P1]).status == STATUS_OK
    for rel in (CAPTURE, WORKLIST):
        assert (first / rel).read_bytes() == (second / rel).read_bytes()


# ---------------------------------------------------------------------------
# Order and reach
# ---------------------------------------------------------------------------


def test_capture_is_written_before_any_other_file(host, toolkit, monkeypatch):
    written: list[str] = []

    def spy(real):
        def replace(path: str, text: str) -> None:
            written.append(path)
            real(path, text)

        return replace

    monkeypatch.setattr(writer, "replace_file_atomically", spy(writer.replace_file_atomically))
    assert _run(host, toolkit, [_shapes_script(_remove_old_fields), P1]).status == STATUS_OK
    tails = [re.sub(r"^.*?/spec/", "", path) for path in written]
    assert tails[0] == "extras/migration/capture.json"
    assert tails.index(ROADMAP) > tails.index("extras/migration/capture.json")
    assert tails[:2] == ["extras/migration/capture.json", "extras/migration/worklist.json"]
    capture = _capture(host)
    assert capture["third_party"]["tech_stacks"][2]["step"] == "14"
    assert capture["task_exit_conditions"] and capture["milestone_status"]["roadmap"][0]["legacy_status"] == "done"


def test_p1_changes_only_its_two_files(host, toolkit):
    before = tree_digest(host)
    report = _run(host, toolkit, [P1])
    assert report.status == STATUS_OK and report.scripts[0].edits == 2
    assert p1_capture.detect(_context(host, toolkit)) == 0
    after = tree_digest(host)
    changed = {rel for rel in set(before) | set(after) if before.get(rel) != after.get(rel)}
    assert changed == {"spec/extras/migration/capture.json", "spec/extras/migration/worklist.json", "spec/specdev_version"}


def test_p1_does_not_replace_a_worklist_that_exists(host, toolkit):
    target = host / "spec" / "extras" / "migration"
    target.mkdir(parents=True)
    kept = json.dumps({"$schema": worklist.WORKLIST_SCHEMA, "items": [make_item("04", "x", "fr-a", audience="agent", blocking=False).to_json()]}, indent=4) + "\n"
    (target / "worklist.json").write_text(kept, encoding="utf-8")
    git(host, "add", "-A")
    git(host, "commit", "-qm", "worklist")
    report = _run(host, toolkit, [P1])
    assert report.status == STATUS_OK and report.scripts[0].edits == 1
    assert (target / "worklist.json").read_text(encoding="utf-8") == kept


# ---------------------------------------------------------------------------
# The files are not read as spec, and they match their schemas
# ---------------------------------------------------------------------------


def _findings(host: Path) -> list[str]:
    errors, _context = run_spec_check_json(str(REAL_ROOT), str(host / "spec"), git_root=str(host), spec_root=str(host / "spec"))
    return sorted(error.render() for error in errors)


def test_extras_migration_files_are_not_read_as_spec(host, toolkit):
    before = _findings(host)
    assert before
    stamp = (host / "spec" / "specdev_version").read_text(encoding="utf-8")
    assert _run(host, toolkit, [P1], allow_dirty=True).status == STATUS_OK
    (host / "spec" / "specdev_version").write_text(stamp, encoding="utf-8")
    ctx = _context(host, toolkit)
    add_items(ctx, [make_item("14", "status-conflict", "ms-late-fees", audience="operator", blocking=True, evidence="14 done, anchor pending", proposal="close it")])
    ctx.documents.write()
    assert [item.id for item in read_items(ctx)] == ["wl-14-status-conflict-ms-late-fees"]
    assert _findings(host) == before


def _violations(data: dict) -> list[str]:
    return [message for _path, message in validate_data_against_schema(str(REAL_ROOT), data)]


def test_capture_and_worklist_match_their_schemas(host, toolkit):
    _run(host, toolkit, [P1])
    assert _violations(_capture(host)) == []
    assert _violations(json.loads((host / WORKLIST).read_text(encoding="utf-8"))) == []


def test_the_two_schemas_are_well_formed_and_registered():
    registry = json.loads((REAL_ROOT / "tools" / "schema_registry.json").read_text(encoding="utf-8"))
    for uri, name in (("vc:infra:migration-capture", "migration_capture"), ("vc:infra:migration-worklist", "migration_worklist")):
        assert registry[uri] == f"schema/infra/{name}.schema.json"
        schema = json.loads((REAL_ROOT / registry[uri]).read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        assert schema["$id"] == uri


def test_schemas_refuse_a_malformed_document(host, toolkit):
    _run(host, toolkit, [P1])
    capture = _capture(host)
    capture["task_status"][0]["status"] = "done"
    assert _violations(capture)
    item = make_item("04", "x", "fr-a", audience="agent", blocking=False).to_json()
    assert _violations({"$schema": worklist.WORKLIST_SCHEMA, "items": [{**item, "audience": "robot"}]})
    assert _violations({"$schema": worklist.WORKLIST_SCHEMA, "items": [{**item, "blocking": "no"}]})


def _removed_field_names() -> set[str]:
    rows = json.loads((REAL_ROOT / "tools" / "schema_changes.json").read_text(encoding="utf-8"))["rows"]
    names = {row["path"].replace("{}", "").replace("[]", "").split(".")[-1] for row in rows if row["change"] == "remove"}
    return {name for name in names if re.fullmatch(r"[a-z][a-z_0-9]*", name)}


def _bare_keys(node, path: str = "") -> list[str]:
    """The keys of *node* outside any ``legacy_`` subtree (the captured values; a file path in ``file_hashes`` is data too)."""
    found: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "file_hashes" or key.startswith("legacy_"):
                continue
            found.append(key)
            found.extend(_bare_keys(value))
    elif isinstance(node, list):
        for entry in node:
            found.extend(_bare_keys(entry))
    return found


def test_capture_holds_no_removed_key_outside_legacy_names(host, toolkit):
    _run(host, toolkit, [P1])
    removed = _removed_field_names()
    assert {"tech_stack", "exit_conditions", "environments", "fr_refs", "pr_rules"} <= removed
    clashes = sorted(set(_bare_keys(_capture(host))) & removed)
    assert clashes == []


# ---------------------------------------------------------------------------
# The worklist API
# ---------------------------------------------------------------------------


@pytest.fixture
def ctx(host, toolkit) -> MigrationContext:
    return _context(host, toolkit)


def _item(about: str = "ms-late-fees", **kwargs):
    return make_item("14", "status-conflict", about, audience=kwargs.pop("audience", "operator"), blocking=True, **kwargs)


def test_item_id_is_built_from_step_kind_about_and_key():
    assert worklist.item_id("14", "status-conflict", "ms-late-fees") == "wl-14-status-conflict-ms-late-fees"
    assert worklist.item_id("02a", "scope-reason", "spec/02a_delivery_baseline.json", "Env: Prod") == "wl-02a-scope-reason-spec-02a-delivery-baseline-json-env-prod"
    long = worklist.item_id("04", "k", "x" * 200)
    assert len(long) < 90 and long == worklist.item_id("04", "k", "x" * 200) and long != worklist.item_id("04", "k", "x" * 199 + "y")


def test_make_item_refuses_a_bad_audience_and_an_empty_about():
    with pytest.raises(WorklistError, match="audience"):
        make_item("04", "k", "fr-a", audience="robot", blocking=False)
    with pytest.raises(WorklistError, match="about"):
        make_item("04", "k", "", audience="agent", blocking=False)


def test_add_items_is_idempotent_and_creates_the_file(host, ctx):
    assert read_items(ctx) == []
    assert not (host / WORKLIST).exists()
    items = [_item("ms-late-fees", evidence="e", proposal="p"), _item("ms-reservations")]
    assert [i.id for i in missing_items(ctx, items)] == ["wl-14-status-conflict-ms-late-fees", "wl-14-status-conflict-ms-reservations"]
    assert add_items(ctx, items) == 2
    ctx.documents.write()
    assert missing_items(ctx, items) == [] and add_items(ctx, items) == 0
    fresh = _context(host, Path(ctx.toolkit_root))
    assert read_items(fresh) == items and add_items(fresh, items) == 0
    assert not fresh.documents.changed()


def test_a_closed_item_is_not_reopened_by_a_second_add(host, ctx):
    item = _item("ms-late-fees", evidence="e", proposal="p")
    add_items(ctx, [item])
    ctx.documents.write()
    path = host / WORKLIST
    data = json.loads(path.read_text(encoding="utf-8"))
    data["items"][0].update(resolved=True, note="closed by the desk lead")
    path.write_text(json.dumps(data, indent=4) + "\n", encoding="utf-8")
    fresh = _context(host, Path(ctx.toolkit_root))
    assert missing_items(fresh, [item]) == [] and add_items(fresh, [item, _item("ms-reservations")]) == 1
    fresh.documents.write()
    kept = json.loads(path.read_text(encoding="utf-8"))["items"]
    assert [(i["about"], i["resolved"], i["note"]) for i in kept] == [("ms-late-fees", True, "closed by the desk lead"), ("ms-reservations", False, "")]


def test_items_are_kept_in_step_kind_id_order_whatever_the_order_added(host, ctx):
    items = [make_item("16", "b", "x", audience="agent", blocking=False), make_item("04", "z", "x", audience="agent", blocking=False), make_item("04", "a", "y", audience="agent", blocking=False), make_item("02a", "a", "x", audience="agent", blocking=False)]
    add_items(ctx, items[:2])
    add_items(ctx, items[2:])
    assert [i.id for i in read_items(ctx)] == ["wl-02a-a-x", "wl-04-a-y", "wl-04-z-x", "wl-16-b-x"]


def test_two_cases_with_one_id_are_refused_unless_keyed(ctx):
    with pytest.raises(WorklistError, match="two cases"):
        missing_items(ctx, [make_item("04", "k", "A_b", audience="agent", blocking=False), make_item("04", "k", "a-b", audience="agent", blocking=False)])
    keyed = [make_item("04", "k", "fr-a", audience="agent", blocking=False, key=str(n)) for n in (1, 2)]
    assert len(missing_items(ctx, keyed)) == 2


def test_a_file_that_is_not_a_worklist_is_refused(host, ctx):
    path = host / WORKLIST
    path.parent.mkdir(parents=True)
    path.write_text('{"items": 3}\n', encoding="utf-8")
    with pytest.raises(WorklistError, match="no list of items"):
        read_items(ctx)
    path.write_text('{"items": [{"id": "wl-x"}]}\n', encoding="utf-8")
    with pytest.raises(WorklistError, match="fields of a worklist item"):
        read_items(_context(host, Path(ctx.toolkit_root)))
