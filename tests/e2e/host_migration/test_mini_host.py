"""The harness on the invented 1.1.1 host ``mini_host_1_1_1`` (never skipped).

One mechanical stage is run per session on a git copy (the module fixture ``stage``); the tests assert on its report, and each
claim a check makes is also asserted here from the copy itself (git, files), so a harness that always said "ok" fails.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from integration._mini_host_pass import run_scripted_pass

from .harness import (
    MUST_CLEAR,
    Cli,
    HarnessRefusal,
    Report,
    check_end_state,
    compare_expect,
    git,
    git_state,
    main,
    make_git_copy,
    refuse,
    run_mechanical_stage,
    tree_digest,
)

REAL_ROOT = Path(__file__).resolve().parents[3]
MINI_HOST = REAL_ROOT / "tests" / "fixtures" / "migration" / "mini_host_1_1_1"
VARIANTS = MINI_HOST / "variants"
EXPECT = Path(__file__).with_name("mini_host.expect.json")
SCRIPTS = REAL_ROOT / "tools" / "specdev_tools" / "migration" / "scripts" / "v1_2_0"


def mini_copy(destination: Path, variant: str | None = None) -> Path:
    """A git copy of the mini host; *variant* names a file of ``variants/`` whose edits are made and committed first."""
    host = make_git_copy(MINI_HOST, destination / "host")
    if variant:
        for edit in json.loads((VARIANTS / f"{variant}.json").read_text(encoding="utf-8"))["edits"]:
            path = host / edit["file"]
            document = json.loads(path.read_text(encoding="utf-8"))
            target = document
            for key in edit["path"][:-1]:
                target = target[key]
            target[edit["path"][-1]] = edit["value"]
            path.write_text(json.dumps(document, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")
        for args in (("add", "-A"), ("commit", "-q", "--no-verify", "-m", f"variant {variant}")):
            subprocess.run(["git", "-C", str(host), *args], check=True, capture_output=True)
    return host


@pytest.fixture(scope="module")
def stage(tmp_path_factory, toolkit_1_2_0):
    """``(report, copy, tree digest after the stage)``: the mechanical stage on a copy of the mini host, run once."""
    copy = mini_copy(tmp_path_factory.mktemp("mini"))
    report = run_mechanical_stage(copy, toolkit_1_2_0, "mini")
    return report, copy, tree_digest(copy)


def check_named(report: Report, fragment: str):
    found = [check for check in report.checks if fragment in check.name]
    assert found, f"no check names {fragment!r}: {[c.name for c in report.checks]}"
    return found


def test_the_mechanical_stage_on_the_mini_host_writes_only_under_spec(stage):
    report, copy, _digest = stage
    assert report.ok, report.render()
    assert all(check.ok is not None or check.criterion == "3" for check in report.checks)
    assert all(check.ok for check in check_named(report, "no path outside spec/ changed"))
    paths = [line[3:] for line in git(copy, "status", "--porcelain=v1", "-uall").splitlines()]
    assert paths and all(path.startswith("spec/") for path in paths)
    assert git(copy, "rev-list", "--count", "HEAD").strip() == "1"  # the stage commits nothing
    assert report.metrics["files_deleted"] == 3 and report.metrics["renames"] == 5


def test_the_second_run_makes_no_edit(stage, toolkit_1_2_0):
    report, copy, digest = stage
    assert all(check.ok for check in check_named(report, "a second run changes 0 files"))
    again = Cli(copy, toolkit_1_2_0).align("apply", "--auto", "--json")
    assert again.code == 0, again.err
    assert sum(again.json()["edits_by_script"].values()) == 0
    assert tree_digest(copy) == digest


def test_head_refs_stash_and_status_are_unchanged_by_a_dry_run(tmp_path, toolkit_1_2_0):
    copy = mini_copy(tmp_path)
    before_state, before_tree = git_state(copy), tree_digest(copy)
    dry = Cli(copy, toolkit_1_2_0).align("apply", "--auto", "--dry-run", "--json")
    assert dry.code == 0 and dry.json()["status"] == "ok" and dry.json()["dry_run"] is True
    assert sum(dry.json()["edits_by_script"].values()) > 0  # it found work and wrote none of it
    assert git_state(copy) == before_state and tree_digest(copy) == before_tree
    assert before_state["status"] == ""


def committed_migration(tmp_path: Path, copy: Path) -> tuple[Path, str]:
    """A copy of the migrated *copy* (its .git too) with the migration committed; returns it and the first commit (the merge base)."""
    other = tmp_path / "committed"
    shutil.copytree(copy, other)
    base = git(other, "rev-list", "--max-parents=0", "HEAD").strip()
    for args in (("add", "-A"), ("commit", "-q", "--no-verify", "-m", "Migrate the spec to toolkit v1.2.0")):
        subprocess.run(["git", "-C", str(other), *args], check=True, capture_output=True)
    return other, base


def test_the_end_state_fails_on_the_mechanical_state_and_changes_nothing(stage, tmp_path, toolkit_1_2_0):
    """The judgement pass has not been made: the end stage says so, line by line, and ``align validate`` refuses and writes nothing."""
    _report, copy, _digest = stage
    other, base = committed_migration(tmp_path, copy)
    before = tree_digest(other)
    report = check_end_state(other, toolkit_1_2_0, "mini", base_ref=base)
    assert not report.ok
    failed = {check.name for check in report.failures}
    assert {"spec-check --merge is clean", "align validate exits 0", "align validate removed the worklist and the capture"} <= failed
    assert report.metrics["errors_merge"] > 0
    assert all(check.ok for check in check_named(report, "no depends_on or dependencies"))  # the mechanical stage did clear criterion 12
    assert tree_digest(other) == before  # validate refused: nothing changed
    # criterion 11 is a release-time condition: a note by default, a failure with --release-ready; the binding pass is not part of the migration PR
    assert report.metrics["fixtures_without_proof"] > 0 and all(check.ok is None for check in check_named(report, "no proof error for a legacy fixture"))
    strict = check_end_state(other, toolkit_1_2_0, "mini", base_ref=base, release_ready=True)
    assert {check.name for check in strict.failures} >= {"the release gate reports no proof error for a legacy fixture"}
    assert main(["--host-copy", str(other), "--toolkit", str(toolkit_1_2_0), "--kind", "mini", "--stage", "end", "--base-ref", base]) == 1


def test_the_harness_exits_non_zero_when_a_check_fails(tmp_path, toolkit_1_2_0, capsys):
    copy = mini_copy(tmp_path)
    expect = tmp_path / "wrong.json"
    expect.write_text('{"renames": 99, "worklist_items": {"min": 1}}', encoding="utf-8")
    code = main(["--host-copy", str(copy), "--toolkit", str(toolkit_1_2_0), "--kind", "mini", "--expect", str(expect)])
    out = capsys.readouterr().out
    assert code == 1
    assert "[FAIL] exp  expect.renames" in out and "[ ok ] exp  expect.worklist_items" in out
    assert out.rstrip().endswith("FAILED")


def test_the_harness_refuses_the_toolkit_root_and_a_dirty_spec(tmp_path, toolkit_1_2_0, capsys):
    argv = ["--toolkit", str(toolkit_1_2_0), "--kind", "mini"]
    assert main(["--host-copy", str(toolkit_1_2_0), *argv]) == 2
    assert "toolkit root" in capsys.readouterr().err
    assert main(["--host-copy", str(REAL_ROOT), *argv]) == 2  # the live checkout is never a host copy
    plain = tmp_path / "plain"
    shutil.copytree(MINI_HOST, plain)
    assert main(["--host-copy", str(plain), *argv]) == 2
    assert "not the top of a git work tree" in capsys.readouterr().err
    copy = mini_copy(tmp_path)
    (copy / "spec" / "04_fr_list.json").write_text("{}\n", encoding="utf-8")
    before = tree_digest(copy)
    assert main(["--host-copy", str(copy), *argv]) == 2
    assert "uncommitted changes" in capsys.readouterr().err
    with pytest.raises(HarnessRefusal):
        refuse(copy, toolkit_1_2_0)
    assert tree_digest(copy) == before  # a refusal runs nothing
    assert main(["--host-copy", str(copy), "--toolkit", str(tmp_path), "--kind", "mini"]) == 2  # not a toolkit either


def test_expect_file_metrics_are_compared_by_name(stage):
    report = stage[0]
    probe = Report("mechanical", "mini", "x", metrics=dict(report.metrics))
    compare_expect(probe, {"renames": 5, "worklist_items": {"min": 1, "max": 10**6}, "errors_after.E768": 0, "errors_after.E999": 0})
    assert [check.ok for check in probe.checks] == [True, True, True, True]
    bad = Report("mechanical", "mini", "x", metrics=dict(report.metrics))
    compare_expect(bad, {"renames": 4, "worklist_items": {"max": 1}, "no_such_metric": 1, "kind": "w"})
    assert [(check.name, check.ok) for check in bad.checks] == [("expect.renames", False), ("expect.worklist_items", False), ("expect.no_such_metric", False), ("expect.kind", False)]
    assert "wanted 4" in bad.checks[0].detail and "no metric of that name" in bad.checks[2].detail


def test_the_committed_expect_of_the_mini_host_is_reproduced(stage):
    report = Report("mechanical", "mini", "x", metrics=dict(stage[0].metrics))
    compare_expect(report, json.loads(EXPECT.read_text(encoding="utf-8")))
    assert report.checks and report.ok, report.render()


def test_every_code_the_stage_must_clear_names_a_script_that_exists_and_the_first_three_name_it():
    for code, script in MUST_CLEAR.items():
        assert (SCRIPTS / f"{script}.py").is_file(), (code, script)
    for code in ("E768", "E704", "E761"):
        assert code in (SCRIPTS / f"{MUST_CLEAR[code]}.py").read_text(encoding="utf-8"), code


@pytest.mark.parametrize(
    ("variant", "kind", "wanted"),
    [
        ("criterion_text_names_removed_field", None, None),
        ("sentence_dependencies", "external-dependency", 2),
    ],
)
def test_the_real_host_shapes_the_first_mini_host_lacked_pass_the_mechanical_stage(tmp_path, toolkit_1_2_0, variant, kind, wanted):
    """Both shapes failed the first real run (E881) before their fixes: a criterion text naming ``exit_conditions``; sentence dependencies."""
    copy = mini_copy(tmp_path, variant)
    report = run_mechanical_stage(copy, toolkit_1_2_0, "mini")
    assert report.ok, report.render()
    if kind:
        assert report.metrics.get(f"worklist_kind.{kind}", 0) >= wanted


def clean_host(destination: Path) -> tuple[Path, str]:
    """A tiny host the judgement pass has left clean: a base commit stamped 1.1.1, then a branch with the 1.2.0 stamp in progress and an empty worklist."""
    host = destination / "clean"
    (host / "spec" / "extras" / "migration").mkdir(parents=True)
    stamp = host / "spec" / "specdev_version"
    stamp.write_text("created_at: '2026-03-02T09:00:00.000000Z'\nlast_migration: null\nmigration_history: []\ntoolkit_version: 1.1.1\n", encoding="utf-8")
    steps = (("init", "-q", "-b", "main"), ("config", "user.email", "harness@example.invalid"), ("config", "user.name", "harness"), ("add", "-A"), ("commit", "-q", "--no-verify", "-m", "base"), ("checkout", "-q", "-b", "migration"))
    for args in steps:
        subprocess.run(["git", "-C", str(host), *args], check=True, capture_output=True)
    stamp.write_text("created_at: '2026-03-02T09:00:00.000000Z'\nlast_migration: null\nmigration_history: []\nmigration_status: in_progress\ntoolkit_version: 1.2.0\n", encoding="utf-8")
    (host / "spec" / "extras" / "migration" / "worklist.json").write_text('{"$schema": "vc:infra:migration-worklist", "items": []}\n', encoding="utf-8")
    (host / "spec" / "extras" / "migration" / "capture.json").write_text('{"$schema": "vc:infra:migration-capture"}\n', encoding="utf-8")
    for args in (("add", "-A"), ("commit", "-q", "--no-verify", "-m", "Migrate the spec to toolkit v1.2.0")):
        subprocess.run(["git", "-C", str(host), *args], check=True, capture_output=True)
    return host, "main"


def test_the_end_state_checks_pass_on_a_host_the_pass_left_clean(tmp_path, toolkit_1_2_0):
    """Every line of the end stage passes, ``align validate`` writes what it writes (the worklist and capture go, the stamp is finished), and it is idempotent."""
    host, base = clean_host(tmp_path)
    report = check_end_state(host, toolkit_1_2_0, "mini", base_ref=base, release_ready=True)
    assert report.ok, report.render()
    assert {check.criterion for check in report.checks} >= {"3", "5", "6", "11", "12"}
    assert not (host / "spec" / "extras" / "migration" / "worklist.json").exists()
    assert "migration_status" not in (host / "spec" / "specdev_version").read_text(encoding="utf-8")
    assert main(["--host-copy", str(host), "--toolkit", str(toolkit_1_2_0), "--kind", "w", "--stage", "end", "--base-ref", base]) == 2  # spec/ is dirty now: refused, not run


def test_the_end_state_checklist_passes_on_the_scripted_pass_of_the_mini_host(stage, tmp_path, toolkit_1_2_0):
    """The migrated mini host, its judgement pass made by the scripted answers of M10-15b, passes every line of the end stage."""
    other, base = committed_migration(tmp_path, stage[1])
    run_scripted_pass(other, toolkit_1_2_0)
    report = check_end_state(other, toolkit_1_2_0, "mini", base_ref=base)
    assert report.ok, report.render()
    assert not (other / "spec" / "extras" / "migration" / "worklist.json").exists()
