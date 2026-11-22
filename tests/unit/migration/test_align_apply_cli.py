"""``specdev align apply --auto`` runs the migration runner (WI-M10-01b): the command, not only the function.

Each test copies the mini host into ``tmp_path`` (a git work tree) and runs ``cli.main`` with the argv of a real call
against a temp toolkit root (``_support.make_toolkit``).
Scripts are the test-only ones of ``_support.make_script`` or the real ``p3_strip_status_ref``.
"""

from __future__ import annotations

import io
import json
import shutil
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from specdev_tools import cli
from specdev_tools.migration import runner
from specdev_tools.migration.registry import PHASE_IDS, discover_scripts
from specdev_tools.migration.report import STATUS_NOOP, STATUS_OK, MigrationReport, ScriptReport

from ._support import MINI_HOST, VARIANT, git, make_host, make_script, make_toolkit, tree_digest

MARK = "extras/migrated-by-p2_mark"


def align(argv: list[str], scripts) -> tuple[int, str, str]:
    """Run ``specdev align apply ...`` in process with *scripts* as the registry; return (exit code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    code = 0
    with (
        patch("specdev_tools.cli.check_venv", return_value=None),
        patch.object(sys, "argv", ["specdev", "align", "apply", *argv]),
        patch.object(runner, "discover_scripts", return_value=list(scripts)),
        redirect_stdout(out),
        redirect_stderr(err),
    ):
        try:
            cli.main()
        except SystemExit as exit_:
            code = exit_.code if isinstance(exit_.code, int) else (0 if exit_.code is None else 1)
    return code, out.getvalue(), err.getvalue()


def mark_script():
    return make_script("p2_mark", PHASE_IDS, touches=("extras",))


def args(host: Path, toolkit: Path, *more: str) -> list[str]:
    return [str(host / "spec"), "--auto", "--repo-root", str(toolkit), *more]


def real_script(script_id: str):
    return [s for s in discover_scripts() if s.id == script_id]


@pytest.fixture
def toolkit(tmp_path):
    return make_toolkit(tmp_path)


@pytest.fixture
def host(tmp_path):
    return make_host(tmp_path)


def test_dry_run_prints_the_diff_and_writes_nothing(host, toolkit):
    before = tree_digest(host)
    code, out, err = align(args(host, toolkit, "--dry-run"), [mark_script()])
    assert code == 0, err
    assert "migration 1.1.1 -> 1.2.0 (dry run, nothing written)" in out
    assert "p2 p2_mark: 1 edit(s)" in out
    assert "+++ b/extras/migrated-by-p2_mark" in out and "+++ b/specdev_version" in out
    assert tree_digest(host) == before
    assert git(host, "status", "--porcelain") == ""


def test_real_run_writes_stamps_and_prints_review_and_undo(host, toolkit):
    code, out, err = align(args(host, toolkit), [mark_script()])
    assert code == 0, err
    assert "migration 1.1.1 -> 1.2.0" in out and "dry run" not in out
    assert "review: git diff --stat spec" in out and "undo:   git checkout -- spec && git clean -fd spec" in out
    assert 'commit: git add spec && git commit --no-verify -m "Migrate the spec to toolkit v1.2.0"' in out and "your old hooks still name commands" in out
    assert out.rstrip().splitlines()[-1].startswith("next:   specdev align triage spec")
    assert (host / "spec" / MARK).is_file()
    stamp = yaml.safe_load((host / "spec" / "specdev_version").read_text(encoding="utf-8"))
    assert stamp["toolkit_version"] == "1.2.0" and stamp["migration_status"] == "in_progress"
    assert len(stamp["migration_history"]) == 1
    changed = git(host, "status", "--porcelain", "-uall").split("\n")
    assert sorted(line[3:] for line in changed if line) == ["spec/extras/migrated-by-p2_mark", "spec/specdev_version"]
    assert not (host / "spec" / "migration_backups").exists()
    assert git(host, "branch", "--list").strip().count("\n") == 0 and "backup/" not in git(host, "branch", "--list", "-a")
    assert len(git(host, "log", "--oneline").splitlines()) == 1


def test_real_run_with_the_real_script_strips_status_ref_of_a_1_0_x_host(tmp_path, toolkit):
    host = make_host(tmp_path, version="1.0.0", commit=False)
    shutil.copy(VARIANT, host / "spec" / "04_fr_list.json")
    git(host, "add", "-A")
    git(host, "commit", "-q", "-m", "host at 1.0.0")
    assert "status_ref" in (host / "spec" / "04_fr_list.json").read_text(encoding="utf-8")
    code, out, err = align(args(host, toolkit), real_script("p3_strip_status_ref"))
    assert code == 0, err
    assert "p3 p3_strip_status_ref: 3 edit(s)" in out
    text = (host / "spec" / "04_fr_list.json").read_text(encoding="utf-8")
    assert "status_ref" not in text and "cn:core:status:active" not in text
    stamp = yaml.safe_load((host / "spec" / "specdev_version").read_text(encoding="utf-8"))
    assert stamp["toolkit_version"] == "1.2.0" and stamp["migration_history"][-1]["from"] == "1.0.0"
    diff = git(host, "diff", "--stat", "spec")
    assert "04_fr_list.json" in diff and "specdev_version" in diff
    assert git(host, "status", "--porcelain", "-uall").count("\n") == 2


def test_dirty_spec_is_refused_with_e880_unless_allow_dirty_and_a_dry_run_is_allowed(host, toolkit):
    (host / "spec" / "00_charter.json").write_text((host / "spec" / "00_charter.json").read_text(encoding="utf-8") + "\n", encoding="utf-8")
    dirty = tree_digest(host)
    code, out, err = align(args(host, toolkit), [mark_script()])
    assert code == 1 and "E880" in err and "uncommitted changes" in err and "--allow-dirty" in err
    assert tree_digest(host) == dirty
    code, out, err = align(args(host, toolkit, "--dry-run"), [mark_script()])
    assert code == 0 and "dry run" in out and tree_digest(host) == dirty
    code, out, err = align(args(host, toolkit, "--allow-dirty"), [mark_script()])
    assert code == 0, err
    assert (host / "spec" / MARK).is_file()


def test_git_root_differs_from_the_spec_parent(tmp_path, toolkit):
    outer = make_host(tmp_path)
    nested = outer / "packages" / "app"
    nested.mkdir(parents=True)
    shutil.move(str(outer / "spec"), str(nested / "spec"))
    git(outer, "add", "-A")
    git(outer, "commit", "-q", "-m", "move")
    spec = nested / "spec"
    argv = [str(spec), "--auto", "--repo-root", str(toolkit), "--git-root", str(outer)]
    code, out, err = align(argv, [mark_script()])
    assert code == 0, err
    assert (spec / MARK).is_file()
    assert "review: git diff --stat packages/app/spec" in out
    # the dirty check looks at the spec folder inside the given work tree
    fresh = make_host(tmp_path / "fresh")
    nested2 = fresh / "packages" / "app"
    nested2.mkdir(parents=True)
    shutil.move(str(fresh / "spec"), str(nested2 / "spec"))
    git(fresh, "add", "-A")
    git(fresh, "commit", "-q", "-m", "move")
    (nested2 / "spec" / "00_charter.json").write_text("{}\n", encoding="utf-8")
    code, out, err = align([str(nested2 / "spec"), "--auto", "--repo-root", str(toolkit), "--git-root", str(fresh)], [mark_script()])
    assert code == 1 and "E880" in err and "uncommitted changes" in err


def test_a_spec_outside_git_is_refused_with_e880(tmp_path, toolkit):
    host = tmp_path / "plain"
    shutil.copytree(MINI_HOST, host)
    code, out, err = align(args(host, toolkit), [mark_script()])
    assert code == 1 and "E880" in err and "not a git work tree" in err
    assert not (host / "spec" / MARK).exists()


def test_json_output_has_the_documented_keys(host, toolkit):
    code, out, err = align(args(host, toolkit, "--json"), [mark_script()])
    assert code == 0, err
    payload = json.loads(out)
    assert list(payload) == ["status", "dry_run", "edits_by_script", "worklist_items", "residue", "errors"]
    assert payload["status"] == "ok" and payload["dry_run"] is False
    assert payload["edits_by_script"] == {"p2_mark": 1} and payload["errors"] == []


def test_json_output_of_a_refusal_carries_the_code_and_exits_nonzero(tmp_path, toolkit):
    host = tmp_path / "plain"
    shutil.copytree(MINI_HOST, host)
    code, out, err = align(args(host, toolkit, "--json", "--dry-run"), [mark_script()])
    payload = json.loads(out)
    assert code == 1 and payload["status"] == "refused" and payload["dry_run"] is True
    assert payload["errors"][0]["code"] == "E880"


def test_a_failed_invariant_is_e881_exit_nonzero_and_writes_nothing(host, toolkit):
    def damage(ctx):
        (Path(ctx.spec_root) / "00_charter.json").unlink()

    bad = make_script("p2_mark", PHASE_IDS, touches=("extras",), edit=damage)
    before = tree_digest(host)
    code, out, err = align(args(host, toolkit), [bad])
    assert code == 1 and "E881" in err and "nothing was written" in err
    assert tree_digest(host) == before


def test_yes_is_accepted_and_changes_nothing(host, toolkit):
    code, out, err = align(args(host, toolkit, "--yes", "-y"), [mark_script()])
    assert code == 0, err


def test_without_auto_the_old_refusal_stays(host, toolkit):
    code, out, err = align([str(host / "spec"), "--repo-root", str(toolkit)], [mark_script()])
    assert code == 1 and "Use --auto" in err
    assert not (host / "spec" / MARK).exists()


def test_a_host_at_the_toolkit_version_is_a_noop_that_does_not_stamp(tmp_path):
    """P19: until the version commit the live toolkit is 1.1.1 and a 1.1.1 host is already current: nothing is stamped."""
    toolkit = make_toolkit(tmp_path, version="1.1.1", listed=("1.0.0", "1.1.0", "1.1.1"))
    host = make_host(tmp_path)
    before = tree_digest(host)
    code, out, err = align(args(host, toolkit), [])
    assert code == 0, err
    assert out.strip() == "migration 1.1.1 -> 1.1.1\nthe spec is already at toolkit version 1.1.1; nothing to do"
    assert tree_digest(host) == before


def test_the_list_of_changes_no_script_makes_is_printed_only_when_the_run_changed_something():
    notes = ["change_schema: a step file changed shape"]
    ran = MigrationReport(STATUS_OK, False, "1.1.1", "1.2.0", scripts=[ScriptReport("p1_a", 1, 1, 1)], not_run=notes, changed_files=["spec/a.json"])
    assert "not run by the runner (do these by hand):" in ran.render() and "  - change_schema: a step file changed shape" in ran.render()
    assert "align prompts" not in ran.render()
    nothing = MigrationReport(STATUS_NOOP, False, "1.2.0", "1.2.0", scripts=[ScriptReport("p1_a", 1, 0, 0)], not_run=notes)
    assert "not run by the runner" not in nothing.render() and "change_schema" not in nothing.render()
    dry = MigrationReport(STATUS_OK, True, "1.1.1", "1.2.0", scripts=[ScriptReport("p1_a", 1, 1, 1)], not_run=notes, changed_files=["spec/a.json"])
    assert "not run by the runner" in dry.render()
