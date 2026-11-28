"""``specdev align apply --auto`` writes only under ``spec/`` and never writes git (WI-M10-01c, DEVSPEC-248).

Every test runs the command as a SUBPROCESS (``python -m specdev_tools.cli align apply ...``) on a ``git clone`` of the
mini host (``tests/fixtures/migration/mini_host_1_1_1/``, a git copy has the ``.git`` a plain copy lacks) against a temp
toolkit root that says 1.2.0 (the live toolkit has no ``v1.2.0.yaml`` before the release commit, P1), with the scripts that
the toolkit registers when the test runs: the assertions are properties of the run, never the number or the names of
the scripts.  A ``git`` wrapper first on ``PATH`` logs the verb of every call the command and its libraries make.

The helpers at the top are shared with ``test_migration_dirty_tree.py`` and ``test_migration_dry_run_identical.py``.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
from pathlib import Path

import pytest
import yaml

from integration._migration_support import _digest_files, changed_paths, Cli, clone_host, commit_all, git_state, HOST_INSTALL_NAMES, HOST_KINDS, json_of, make_cli, outside_spec, READ_ONLY_VERBS, SPEC, STAMP, stamp_of
from unit.migration._support import git, tree_digest

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.fixture
def cli(tmp_path) -> Cli:
    return make_cli(tmp_path)


@pytest.fixture(params=HOST_KINDS)
def host(request, tmp_path) -> Path:
    return clone_host(tmp_path, request.param)


def test_apply_changes_no_ref_commit_or_branch(cli, host):
    before = git_state(host)
    done = cli.apply(host)
    assert done.returncode == 0, done.stderr
    assert git_state(host) == before
    assert "backup/" not in git(host, "branch", "-a") and "backup/" not in git(host, "for-each-ref")
    assert not (host / SPEC / "migration_backups").exists()
    assert changed_paths(host), "the run changed nothing: the test would prove nothing"


def test_changed_paths_are_inside_the_allowed_write_set(cli, host):
    outside, toolkit = outside_spec(host), _digest_files(cli.toolkit)
    installed = {name for name in HOST_INSTALL_NAMES if (host / name).exists()}
    done = cli.apply(host)
    assert done.returncode == 0, done.stderr
    paths = changed_paths(host)
    assert paths and all(path.startswith(f"{SPEC}/") for path in paths), paths
    assert not [path for path in paths if path.endswith(".tmp") or "/.specdev-migrate-" in path]
    assert outside_spec(host) == outside
    assert {name for name in HOST_INSTALL_NAMES if (host / name).exists()} == installed
    assert _digest_files(cli.toolkit) == toolkit
    assert not list(cli.scratch.iterdir()), "the runner left its scratch copy behind"


def test_dry_run_changes_no_path(cli, host):
    tree, state = tree_digest(host), git_state(host)
    done = cli.apply(host, "--dry-run")
    assert done.returncode == 0, done.stderr
    assert "dry run, nothing written" in done.stdout
    assert tree_digest(host) == tree
    assert git_state(host) == state
    assert changed_paths(host) == []
    assert not list(cli.scratch.iterdir())


@pytest.mark.parametrize("flags", [(), ("--dry-run",)], ids=["real run", "dry run"])
def test_every_git_call_is_read_only(cli, host, flags):
    done = cli.apply(host, *flags)
    assert done.returncode == 0, done.stderr
    assert cli.verbs, "the git wrapper saw no call: the log is not wired"
    assert cli.verbs <= READ_ONLY_VERBS, sorted(cli.verbs - READ_ONLY_VERBS)


def test_second_run_makes_zero_edits(cli, host):
    first = cli.apply(host)
    assert first.returncode == 0, first.stderr
    after_first, paths = tree_digest(host), changed_paths(host)
    diff = git(host, "diff")
    second = cli.apply(host)
    assert second.returncode == 0, second.stderr
    assert tree_digest(host) == after_first
    assert changed_paths(host) == paths and git(host, "diff") == diff
    counted = json_of(cli.apply(host, "--json"))
    assert counted["status"] == "ok" and set(counted["edits_by_script"].values()) == {0}
    assert len(stamp_of(host)["migration_history"]) == 1


def test_partial_run_then_rerun_equals_full_run(cli, tmp_path):
    """A run that died before the stamp leaves the files of the scripts that ran and the old version; a rerun finishes it.

    The command has no ``--only`` (P16): the rerun IS the partial run.  The interruption is made by putting the committed
    stamp back after a full run; the rerun resumes (the capture file is there) and ends where that full run ended.
    """
    host = clone_host(tmp_path, "1.0.x")
    assert cli.apply(host).returncode == 0
    full_stamp = stamp_of(host)
    full = {rel: digest for rel, digest in tree_digest(host).items() if rel != f"{SPEC}/{STAMP}"}
    git(host, "checkout", "-q", "--", f"{SPEC}/{STAMP}")
    assert stamp_of(host)["toolkit_version"] == "1.0.0"
    resumed = cli.apply(host)
    assert resumed.returncode == 0, resumed.stderr
    assert {rel: digest for rel, digest in tree_digest(host).items() if rel != f"{SPEC}/{STAMP}"} == full
    stamp = stamp_of(host)
    assert stamp["toolkit_version"] == "1.2.0" and len(stamp["migration_history"]) == 1
    volatile = ("created_at", "last_migration", "migration_history")
    assert {k: v for k, v in stamp.items() if k not in volatile} == {k: v for k, v in full_stamp.items() if k not in volatile}


def test_git_root_differs_from_spec_parent(cli, tmp_path):
    outer = clone_host(tmp_path)
    nested = outer / "packages" / "app"
    nested.mkdir(parents=True)
    shutil.move(str(outer / SPEC), str(nested / SPEC))
    commit_all(outer, "move the spec down")
    before, outside = git_state(outer), outside_spec(outer)
    done = cli.apply(outer, spec=nested / SPEC, git_root=outer)
    assert done.returncode == 0, done.stderr
    paths = changed_paths(outer)
    assert paths and all(path.startswith("packages/app/spec/") for path in paths), paths
    assert git_state(outer) == before
    assert {k: v for k, v in outside_spec(outer).items() if not k.startswith("packages/app/spec/")} == {
        k: v for k, v in outside.items() if not k.startswith("packages/app/spec/")
    }
    assert "git diff --stat packages/app/spec" in done.stdout
    assert re.search(r"^migration 1\.\d\.\d -> 1\.2\.0$", done.stdout, re.M)
