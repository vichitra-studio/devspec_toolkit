"""The migration runner core (WI-M10-01a): script order, preflight, invariants, the scratch copy, the stamp.

The scripts here are test-only (``Script`` values built in the test); a toolkit root with the version 1.2.0 is built in
``tmp_path`` because the real toolkit says 1.1.1 until the release commit (ruling P1).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from specdev_tools.migration import runner
from specdev_tools.migration.context import GitReadError, read_git
from specdev_tools.migration.registry import (
    PHASE_BASELINE,
    PHASE_CAPTURE,
    PHASE_CLOSE,
    PHASE_CONTENT,
    PHASE_IDS,
    Problem,
    RegistryError,
    Script,
    ScriptResult,
    ScriptSpec,
    chain_for,
    discover_scripts,
    order_scripts,
)
from specdev_tools.migration.report import STATUS_FAILED, STATUS_NOOP, STATUS_OK, STATUS_REFUSED
from specdev_tools.lifecycle import plans

REAL_ROOT = Path(__file__).resolve().parents[3]
MINI_HOST = REAL_ROOT / "tests" / "fixtures" / "migration" / "mini_host_1_1_1"
FR_FILE = "04_fr_list.json"


# ---------------------------------------------------------------------------
# Support
# ---------------------------------------------------------------------------


def make_toolkit(tmp_path: Path, version: str = "1.2.0", listed: tuple[str, ...] = ("1.0.0", "1.1.0", "1.1.1", "1.2.0")) -> Path:
    """A toolkit root that says *version*: a pyproject, a changelog folder and the two registries the graph reads."""
    root = tmp_path / "toolkit"
    (root / "tools").mkdir(parents=True)
    (root / "changelog").mkdir()
    (root / "tools" / "pyproject.toml").write_text(f'[project]\nname = "specdev-tools"\nversion = "{version}"\n', encoding="utf-8")
    for name in ("entry_key_registry.json", "step_order.json"):
        shutil.copy(REAL_ROOT / "tools" / name, root / "tools" / name)
    for listed_version in listed:
        (root / "changelog" / f"v{listed_version}.yaml").write_text(f"version: {listed_version}\nbreaking: false\nchanges: []\n", encoding="utf-8")
    return root


def git(cwd: Path, *args: str) -> str:
    done = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True)
    return done.stdout


def make_host(tmp_path: Path, *, version: str = "1.1.1", commit: bool = True) -> Path:
    """A git work tree holding a copy of the mini host (without its README), stamped *version*."""
    host = tmp_path / "host"
    shutil.copytree(MINI_HOST, host)
    (host / "README.md").unlink()
    stamp = host / "spec" / "specdev_version"
    data = yaml.safe_load(stamp.read_text(encoding="utf-8"))
    data["toolkit_version"] = version
    stamp.write_text(yaml.dump(data, default_flow_style=False), encoding="utf-8")
    git(host, "init", "-q")
    git(host, "config", "user.email", "t@example.invalid")
    git(host, "config", "user.name", "t")
    if commit:
        git(host, "add", "-A")
        git(host, "commit", "-q", "-m", "host")
    return host


def tree_digest(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file() and ".git" not in path.relative_to(root).parts
    }


def make_script(
    script_id: str,
    phase: int,
    *,
    requires: tuple[str, ...] = (),
    touches: tuple[str, ...] = ("*",),
    edit=None,
    log: list[str] | None = None,
    version: str = "1.2.0",
    verify=None,
    result: ScriptResult | None = None,
) -> Script:
    """A script that runs *edit(ctx)* once: ``detect`` is 1 until the edit has been made (it looks for the mark)."""
    mark = f"migrated-by-{script_id}"

    def detect(ctx) -> int:
        return 0 if os.path.exists(os.path.join(ctx.spec_root, "extras", mark)) else 1

    def apply(ctx) -> ScriptResult:
        if log is not None:
            log.append(script_id)
        if edit is not None:
            edit(ctx)
        os.makedirs(os.path.join(ctx.spec_root, "extras"), exist_ok=True)
        with open(os.path.join(ctx.spec_root, "extras", mark), "w", encoding="utf-8") as handle:
            handle.write("done\n")
        return result or ScriptResult(edits=1)

    return Script(ScriptSpec(script_id, phase, requires, touches), version, detect, apply, verify or (lambda before, after: []))


def run(host: Path, toolkit: Path, scripts, **kwargs):
    return runner.run_migration(host / "spec", toolkit_root=toolkit, git_root=host, scripts=scripts, **kwargs)


def stamp_of(host: Path) -> dict:
    return yaml.safe_load((host / "spec" / "specdev_version").read_text(encoding="utf-8"))


@pytest.fixture
def toolkit(tmp_path) -> Path:
    return make_toolkit(tmp_path)


@pytest.fixture
def host(tmp_path) -> Path:
    return make_host(tmp_path)


# ---------------------------------------------------------------------------
# Order of the scripts
# ---------------------------------------------------------------------------


def test_scripts_run_in_requires_order(host, toolkit):
    log: list[str] = []
    scripts = [
        make_script("p3_shapes", PHASE_IDS + 1, requires=("p2_ids",), log=log),
        make_script("p2_ids_b", PHASE_IDS, requires=("p2_ids",), log=log),
        make_script("p2_ids", PHASE_IDS, log=log),
        make_script("p1_capture", PHASE_CAPTURE, log=log),
        make_script("p4_content", PHASE_CONTENT, log=log),
    ]
    report = run(host, toolkit, scripts)
    assert report.status == STATUS_OK, report.render()
    assert log == ["p1_capture", "p2_ids", "p2_ids_b", "p3_shapes", "p4_content"]
    assert [script.id for script in report.scripts] == log
    assert order_scripts(reversed(scripts)) == order_scripts(scripts)


def test_requires_cycle_is_rejected(host, toolkit):
    a = make_script("p2_a", PHASE_IDS, requires=("p2_b",))
    b = make_script("p2_b", PHASE_IDS, requires=("p2_a",))
    with pytest.raises(RegistryError, match="cycle"):
        order_scripts([a, b])
    before = tree_digest(host)
    report = run(host, toolkit, [a, b])
    assert report.status == STATUS_FAILED and report.errors[0].code == "E881" and "cycle" in report.errors[0].message
    assert tree_digest(host) == before


def test_registry_rejects_unknown_requirement_duplicate_id_and_later_phase():
    with pytest.raises(RegistryError, match="not registered"):
        order_scripts([make_script("p2_a", PHASE_IDS, requires=("p9_missing",))])
    with pytest.raises(RegistryError, match="twice"):
        order_scripts([make_script("p2_a", PHASE_IDS), make_script("p2_a", PHASE_IDS)])
    with pytest.raises(RegistryError, match="later phase"):
        order_scripts([make_script("p2_a", PHASE_IDS, requires=("p4_b",)), make_script("p4_b", PHASE_CONTENT)])
    with pytest.raises(RegistryError, match="phase 9"):
        order_scripts([make_script("p9_a", 9)])


def test_chain_takes_the_versions_above_the_host_up_to_the_target():
    old = make_script("p1_old", PHASE_CAPTURE, version="1.1.0")
    new = make_script("p1_new", PHASE_CAPTURE, version="1.2.0")
    later = make_script("p1_later", PHASE_CAPTURE, version="1.3.0")
    assert [s.id for s in chain_for([later, new, old], "1.0.0", "1.2.0")] == ["p1_old", "p1_new"]
    assert [s.id for s in chain_for([later, new, old], "1.1.1", "1.2.0")] == ["p1_new"]
    assert order_scripts([new, old])[0] is old


def test_discovery_finds_the_modules_of_the_scripts_package():
    assert all(isinstance(script, Script) for script in discover_scripts())


# ---------------------------------------------------------------------------
# Preflight (E880)
# ---------------------------------------------------------------------------


def test_preflight_refuses_non_git_host(tmp_path, toolkit):
    host = make_host(tmp_path / "x")
    shutil.rmtree(host / ".git")
    report = run(host, toolkit, [make_script("p1_a", PHASE_CAPTURE)])
    assert report.status == STATUS_REFUSED
    assert [e.code for e in report.errors] == ["E880"] and "git work tree" in report.errors[0].message


@pytest.mark.parametrize(
    ("version", "text"),
    [("0.9.0", "older than 1.0.0"), ("1.3.0", "newer than this toolkit"), ("1.1.5", "not a version listed"), ("1.1.1-dev", "not a version listed")],
)
def test_preflight_refuses_unlisted_and_newer_versions(tmp_path, toolkit, version, text):
    host = make_host(tmp_path / "x", version=version)
    before = tree_digest(host)
    report = run(host, toolkit, [make_script("p1_a", PHASE_CAPTURE)])
    assert report.status == STATUS_REFUSED
    assert report.errors[0].code == "E880" and text in report.errors[0].message
    assert tree_digest(host) == before


def test_preflight_refuses_a_missing_stamp_and_an_unreadable_toolkit_version(tmp_path, toolkit):
    host = make_host(tmp_path / "x")
    (toolkit / "tools" / "pyproject.toml").write_text("[project]\nname = 'x'\n", encoding="utf-8")
    assert "toolkit version cannot be read" in run(host, toolkit, []).errors[0].message
    (toolkit / "tools" / "pyproject.toml").write_text('[project]\nversion = "1.2.0"\n', encoding="utf-8")
    (host / "spec" / "specdev_version").unlink()
    report = run(host, toolkit, [])
    assert report.status == STATUS_REFUSED and "records no toolkit_version" in report.errors[0].message


def test_dirty_spec_is_refused_unless_allowed(host, toolkit):
    (host / "spec" / FR_FILE).write_text((host / "spec" / FR_FILE).read_text(encoding="utf-8") + "\n", encoding="utf-8")
    script = make_script("p1_a", PHASE_CAPTURE)
    refused = run(host, toolkit, [script])
    assert refused.status == STATUS_REFUSED and "uncommitted" in refused.errors[0].message
    assert run(host, toolkit, [script], allow_dirty=True).status == STATUS_OK


def test_resume_marker_skips_clean_tree_check(host, toolkit):
    script = make_script("p1_a", PHASE_CAPTURE)
    (host / "spec" / "extras" / "migration").mkdir(parents=True)
    (host / "spec" / "extras" / "migration" / "capture.json").write_text("{}\n", encoding="utf-8")
    report = run(host, toolkit, [script])
    assert report.status == STATUS_OK, report.render()
    assert report.scripts[0].edits == 1
    # the in_progress status is a marker too
    other = make_host(host.parent / "y")
    (other / "spec" / "specdev_version").write_text(
        yaml.dump({"toolkit_version": "1.1.1", "migration_status": "in_progress", "migration_history": []}), encoding="utf-8"
    )
    assert run(other, toolkit, [script]).status == STATUS_OK


def test_host_at_target_without_capture_is_noop(tmp_path, toolkit):
    host = make_host(tmp_path / "x", version="1.2.0")
    before = tree_digest(host)
    report = run(host, toolkit, [make_script("p1_a", PHASE_CAPTURE)])
    assert report.status == STATUS_NOOP and "already at toolkit version 1.2.0" in report.render()
    assert tree_digest(host) == before


def test_host_at_the_real_toolkit_version_is_noop(host):
    report = runner.run_migration(host / "spec", toolkit_root=REAL_ROOT, git_root=host)
    assert report.status == STATUS_NOOP


# ---------------------------------------------------------------------------
# The empty runner, the stamp, the dry run
# ---------------------------------------------------------------------------


def test_the_empty_runner_changes_nothing_on_the_mini_host(host, toolkit):
    before = tree_digest(host)
    report = run(host, toolkit, [])
    assert report.status == STATUS_NOOP and "no migration script is registered" in report.render()
    assert tree_digest(host) == before and git(host, "status", "--porcelain") == ""


def test_a_real_run_installs_the_edits_and_stamps_once(host, toolkit):
    def edit(ctx):
        document = ctx.documents.load(FR_FILE)
        document.data["migrated"] = True

    report = run(host, toolkit, [make_script("p4_content", PHASE_CONTENT, edit=edit, touches=("04", "extras"))])
    assert report.status == STATUS_OK, report.render()
    assert json.loads((host / "spec" / FR_FILE).read_text(encoding="utf-8"))["migrated"] is True
    stamp = stamp_of(host)
    assert stamp["toolkit_version"] == "1.2.0" and stamp["migration_status"] == "in_progress"
    assert [(h["from"], h["to"]) for h in stamp["migration_history"]] == [("1.1.1", "1.2.0")]
    assert "p4_content" in stamp["migration_history"][0]["notes"]
    changed = git(host, "status", "--porcelain").split("\n")
    assert all(line[3:].startswith("spec/") for line in changed if line)
    assert git(host, "log", "--oneline").count("\n") == 1  # no commit was made
    assert f"git checkout -- spec" in report.render()


def test_stamp_writes_one_history_entry_on_resume(host, toolkit):
    first = make_script("p1_a", PHASE_CAPTURE)
    assert run(host, toolkit, [first]).status == STATUS_OK
    entries = stamp_of(host)["migration_history"]
    # a rerun on the uncommitted result is a resume (in_progress): nothing to do, no second entry, no byte changes
    before = tree_digest(host)
    again = run(host, toolkit, [first])
    assert again.status == STATUS_OK and again.total_edits == 0
    assert stamp_of(host)["migration_history"] == entries and len(entries) == 1
    assert tree_digest(host) == before
    # a failure before the stamp leaves the old version and a capture file; the rerun adds the one entry
    other = make_host(host.parent / "z")
    (other / "spec" / "extras" / "migration").mkdir(parents=True)
    (other / "spec" / "extras" / "migration" / "capture.json").write_text("{}\n", encoding="utf-8")
    bad = make_script("p2_bad", PHASE_IDS, verify=lambda b, a: [Problem("no")])
    assert run(other, toolkit, [first, bad]).status == STATUS_FAILED
    assert stamp_of(other)["toolkit_version"] == "1.1.1" and stamp_of(other)["migration_history"] == []
    assert run(other, toolkit, [first]).status == STATUS_OK
    assert len(stamp_of(other)["migration_history"]) == 1


def test_stamp_keeps_the_other_keys_of_the_file(host, toolkit):
    created = stamp_of(host)["created_at"]
    run(host, toolkit, [make_script("p1_a", PHASE_CAPTURE)])
    stamp = stamp_of(host)
    assert stamp["created_at"] == created and stamp["last_migration"]


def test_dry_run_changes_no_path_and_prints_the_same_diff_twice(host, toolkit):
    def edit(ctx):
        ctx.documents.load(FR_FILE).data["migrated"] = True

    scripts = [make_script("p4_content", PHASE_CONTENT, edit=edit, touches=("04", "extras"))]
    before = tree_digest(host)
    first = run(host, toolkit, scripts, dry_run=True)
    second = run(host, toolkit, scripts, dry_run=True)
    assert first.status == STATUS_OK and first.dry_run
    assert tree_digest(host) == before and git(host, "status", "--porcelain") == ""
    assert first.diff and first.diff == second.diff and first.render() == second.render()
    assert '+    "migrated": true' in first.diff and "+++ b/specdev_version" in first.diff
    assert "<timestamp>" in first.diff and "20" not in "".join(l for l in first.diff.splitlines() if l.startswith("+last_migration"))
    assert first.changed_files == sorted(first.changed_files) and FR_FILE in first.changed_files


def test_dry_run_on_a_dirty_tree_is_allowed(host, toolkit):
    (host / "spec" / FR_FILE).write_text((host / "spec" / FR_FILE).read_text(encoding="utf-8") + "\n", encoding="utf-8")
    assert run(host, toolkit, [make_script("p1_a", PHASE_CAPTURE)], dry_run=True).status == STATUS_OK


def test_report_json_has_the_documented_keys(host, toolkit):
    report = run(host, toolkit, [make_script("p1_a", PHASE_CAPTURE, result=ScriptResult(edits=3, worklist_items=2, residue=("left",)))])
    assert report.to_json() == {
        "status": "ok", "dry_run": False, "edits_by_script": {"p1_a": 3}, "worklist_items": 2, "residue": ["left"], "errors": [],
    }
    (host / "spec" / "00_charter.json").write_text("{}\n", encoding="utf-8")
    refused = run(make_host(host.parent / "again"), toolkit, [make_script("p1_a", PHASE_CAPTURE)]).to_json()
    assert refused["status"] == "ok"
    dirty = make_host(host.parent / "dirty")
    (dirty / "spec" / "00_charter.json").write_text("{}\n", encoding="utf-8")
    refused = run(dirty, toolkit, [make_script("p1_a", PHASE_CAPTURE)]).to_json()
    assert refused["status"] == "refused" and refused["errors"][0]["code"] == "E880"


def test_changelog_entries_the_runner_does_not_run_are_listed(host, toolkit):
    (toolkit / "changelog" / "v1.2.0.yaml").write_text(
        "version: 1.2.0\nbreaking: true\nchanges:\n  - type: add_constraint\n    description: a rule a person applies\n    migration:\n      action: ai_assisted\n",
        encoding="utf-8",
    )
    report = run(host, toolkit, [make_script("p1_a", PHASE_CAPTURE)], dry_run=True)
    assert report.not_run == ["add_constraint: a rule a person applies"] and "not run by the runner" in report.render()


# ---------------------------------------------------------------------------
# Failure: nothing is written
# ---------------------------------------------------------------------------


def test_failed_verify_aborts_with_no_writes(host, toolkit):
    def edit(ctx):
        ctx.documents.load(FR_FILE).data["migrated"] = True

    good = make_script("p2_good", PHASE_IDS, edit=edit)
    bad = make_script("p3_bad", PHASE_IDS + 1, requires=("p2_good",), verify=lambda b, a: [Problem("the tree is wrong")])
    before = tree_digest(host)
    report = run(host, toolkit, [good, bad])
    assert report.status == STATUS_FAILED
    assert report.errors[0].code == "E881" and "p3_bad" in report.errors[0].message and "the tree is wrong" in report.errors[0].message
    assert "nothing was written" in report.errors[0].message
    assert tree_digest(host) == before


def test_a_script_that_raises_fails_the_run_with_no_writes(host, toolkit):
    def edit(ctx):
        raise RuntimeError("boom")

    before = tree_digest(host)
    report = run(host, toolkit, [make_script("p2_a", PHASE_IDS, edit=edit)])
    assert report.status == STATUS_FAILED and "RuntimeError: boom" in report.errors[0].message
    assert tree_digest(host) == before


def test_a_file_outside_touches_fails(host, toolkit):
    def edit(ctx):
        ctx.documents.load(FR_FILE).data["x"] = 1

    report = run(host, toolkit, [make_script("p2_a", PHASE_IDS, edit=edit, touches=("00",))])
    assert report.status == STATUS_FAILED and "04_fr_list.json, which is outside its touches" in report.errors[0].message


def test_a_definition_id_lost_fails_unless_recorded(host, toolkit):
    def drop(ctx):
        ctx.documents.load(FR_FILE).data["functional_requirements"][0]["acceptance_criteria"].pop(0)

    dropped = "ac-catalog-search-1"
    bad = run(host, toolkit, [make_script("p2_a", PHASE_IDS, edit=drop, touches=("04", "extras"))], dry_run=True)
    assert bad.status == STATUS_FAILED and f"definition id {dropped} was lost" in bad.errors[0].message
    recorded = run(host, toolkit, [make_script("p2_a", PHASE_IDS, edit=drop, touches=("04", "extras"), result=ScriptResult(edits=1, deleted_ids=(dropped,)))], dry_run=True)
    assert recorded.status == STATUS_OK, recorded.render()


def test_a_renamed_id_must_be_recorded_and_present(host, toolkit):
    def rename(ctx):
        entry = ctx.documents.load(FR_FILE).data["functional_requirements"][0]
        entry["acceptance_criteria"][0]["criterion_id"] = "ac-catalog-search-1-renamed"

    old = "ac-catalog-search-1"
    unrecorded = run(host, toolkit, [make_script("p2_a", PHASE_IDS, edit=rename, touches=("04", "extras"))], dry_run=True)
    assert unrecorded.status == STATUS_FAILED
    ok = run(host, toolkit, [make_script("p2_a", PHASE_IDS, edit=rename, touches=("04", "extras"), result=ScriptResult(edits=1, renames=((old, old + "-renamed"),)))], dry_run=True)
    assert ok.status == STATUS_OK, ok.render()


def test_a_script_that_is_not_idempotent_fails(host, toolkit):
    def detect(ctx):
        return 1

    script = Script(ScriptSpec("p2_a", PHASE_IDS, touches=("*",)), "1.2.0", detect, lambda ctx: ScriptResult(edits=1), lambda b, a: [])
    report = run(host, toolkit, [script])
    assert report.status == STATUS_FAILED and "not idempotent" in report.errors[0].message


def test_a_script_writing_outside_the_spec_folder_fails(host, toolkit):
    def edit(ctx):
        with open(os.path.join(ctx.host_root, "docs", "seed", "seed_hosting_plan.md"), "a", encoding="utf-8") as handle:
            handle.write("changed\n")

    before = tree_digest(host)
    report = run(host, toolkit, [make_script("p2_a", PHASE_IDS, edit=edit)])
    assert report.status == STATUS_FAILED and "outside the spec folder" in report.errors[0].message
    assert tree_digest(host) == before

    def create(ctx):
        with open(os.path.join(ctx.host_root, "stray.txt"), "w", encoding="utf-8") as handle:
            handle.write("x")

    assert run(host, toolkit, [make_script("p2_b", PHASE_IDS, edit=create)]).status == STATUS_FAILED
    assert not (host / "stray.txt").exists()


def test_a_closed_plan_may_not_change_after_the_legacy_close(host, toolkit):
    spec = host / "spec"
    plan = spec / "impl_context" / "ms_catalog_plan.json"
    data = json.loads(plan.read_text(encoding="utf-8"))
    data["milestone"] = "ms-catalog"
    plan.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    def edit_plan(ctx):
        ctx.documents.load("impl_context/ms_catalog_plan.json").data["touched"] = True

    late = make_script("p6_late", PHASE_BASELINE, edit=edit_plan, touches=("16", "extras"))
    failed = run(host, toolkit, [late], allow_dirty=True)
    assert failed.status == STATUS_FAILED and "changed the plan impl_context/ms_catalog_plan.json after the legacy close" in failed.errors[0].message
    early = make_script("p4_early", PHASE_CONTENT, edit=edit_plan, touches=("16", "extras"))
    outcome = run(host, toolkit, [early], allow_dirty=True, dry_run=True)
    assert outcome.status == STATUS_OK, outcome.render()


def test_frozen_plan_drift_quiet_after_run(host, toolkit):
    """A closed milestone whose stored hash matches stays quiet; a script that moves the plan hash is E881."""
    spec = host / "spec"
    plan_path = spec / "impl_context" / "ms_catalog_plan.json"
    data = json.loads(plan_path.read_text(encoding="utf-8"))
    data["milestone"] = "ms-catalog"
    plan_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    anchor_path = spec / "16_impl_context.json"
    anchor = json.loads(anchor_path.read_text(encoding="utf-8"))
    anchor.setdefault("plan", {})["milestone_index"] = [
        {"about": ["ms-catalog"], "status": "done", "close": {"plan_hash": plans.plan_hash(plan_path)}}
    ]
    anchor_path.write_text(json.dumps(anchor, indent=2) + "\n", encoding="utf-8")

    def unrelated(ctx):
        ctx.documents.load(FR_FILE).data["x"] = 1

    quiet = run(host, toolkit, [make_script("p2_a", PHASE_IDS, edit=unrelated, touches=("04", "extras"))], allow_dirty=True, dry_run=True)
    assert quiet.status == STATUS_OK, quiet.render()

    def move_plan(ctx):
        ctx.documents.load("impl_context/ms_catalog_plan.json").data["touched"] = True

    drift = run(host, toolkit, [make_script("p4_a", PHASE_CONTENT, edit=move_plan, touches=("16", "extras"))], allow_dirty=True, dry_run=True)
    assert drift.status == STATUS_FAILED and "no longer has the hash of its close record" in drift.errors[0].message


# ---------------------------------------------------------------------------
# What the runner may call and write
# ---------------------------------------------------------------------------


def test_the_runner_makes_read_only_git_calls_only(host):
    assert read_git(str(host), "rev-parse", "--is-inside-work-tree").strip() == "true"
    for write in ("add", "commit", "branch", "checkout", "stash", "reset", "rm", "mv", "restore", "tag"):
        with pytest.raises(GitReadError, match="read-only"):
            read_git(str(host), write, "x")


def test_git_is_called_through_read_git_only():
    package = REAL_ROOT / "tools" / "specdev_tools" / "migration"
    callers = sorted(
        path.name for path in package.rglob("*.py") if "subprocess" in path.read_text(encoding="utf-8")
    )
    assert callers == ["context.py"]
