"""``specdev align apply --auto`` writes only under ``spec/`` and never writes git (WI-M10-01c, DEVSPEC-248).

Every test runs the command as a SUBPROCESS (``python -m specdev_tools.cli align apply ...``) on a ``git clone`` of the
mini host (``tests/fixtures/migration/mini_host_1_1_1/``, a git copy has the ``.git`` a plain copy lacks) against a temp
toolkit root that says 1.2.0 (the live toolkit has no ``v1.2.0.yaml`` before the release commit, P1), with the scripts that
the toolkit registers when the test runs: the assertions are properties of the run, never the number or the names of
the scripts.  A ``git`` wrapper first on ``PATH`` logs the verb of every call the command and its libraries make.

The helpers at the top are shared with ``test_migration_dirty_tree.py`` and ``test_migration_dry_run_identical.py``.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pytest
import yaml

from unit.migration.test_align_apply_cli import VARIANT
from unit.migration.test_runner_core import git, make_host, make_toolkit, tree_digest

# Verbs that read only.  The runner's own list (``migration.context.READ_ONLY_GIT``) is the same set; it is repeated
# here on purpose, so a verb added to the product without a decision shows up as a red test.
READ_ONLY_VERBS = frozenset({"rev-parse", "status", "merge-base", "ls-files", "log", "show", "cat-file", "diff"})
SPEC = "spec"
STAMP = "specdev_version"
HOST_INSTALL_NAMES = (".claude", ".github", ".pre-commit-config.yaml", ".gitattributes", ".githooks")  # what `specdev update` installs
HOST_KINDS = ("1.1.1", "1.0.x")


# ---------------------------------------------------------------------------
# Hosts and the command (shared with the two sibling files)
# ---------------------------------------------------------------------------


def clone_host(tmp_path: Path, kind: str = "1.1.1") -> Path:
    """A ``git clone`` of the mini host in ``tmp_path/clone-<n>``: stamped 1.1.1, or ``1.0.x`` with ``status_ref`` keys.

    ``1.0.x`` is a 1.0.0-stamped host whose ``04_fr_list.json`` is the fixture variant that carries ``status_ref``, so
    the 1.1.0 script of the chain has work to do.
    """
    source_parent = tmp_path / f"source-{len(list(tmp_path.glob('source-*')))}"
    source_parent.mkdir()
    source = make_host(source_parent, version="1.0.0" if kind == "1.0.x" else "1.1.1", commit=kind != "1.0.x")
    if kind == "1.0.x":
        shutil.copy(VARIANT, source / SPEC / "04_fr_list.json")
        git(source, "add", "-A")
        git(source, "commit", "-q", "-m", "host at 1.0.0")
    clone = tmp_path / f"clone-{len(list(tmp_path.glob('clone-*')))}"
    git(tmp_path, "clone", "-q", str(source), str(clone))
    git(clone, "config", "user.email", "t@example.invalid")
    git(clone, "config", "user.name", "t")
    return clone


def commit_all(host: Path, message: str = "state") -> None:
    git(host, "add", "-A")
    git(host, "commit", "-q", "-m", message)


@dataclass
class Cli:
    """The command as a subprocess, with the logging ``git`` wrapper first on its ``PATH``.

    ``verbs`` is every git verb the command and what it calls ran, over all runs of this object; ``scratch`` is the
    ``TMPDIR`` of the command (the runner's scratch copy lives there and must be gone when it exits).
    """

    toolkit: Path
    bin_dir: Path
    log: Path
    scratch: Path
    runs: list[subprocess.CompletedProcess[str]] = field(default_factory=list)

    @property
    def verbs(self) -> set[str]:
        return {verb for argv in self._calls() for verb in [_verb(argv)] if verb}

    def _calls(self) -> list[list[str]]:
        return [line.split("\t") for line in self.log.read_text(encoding="utf-8").splitlines()] if self.log.exists() else []

    def apply(self, host: Path, *flags: str, spec: Path | None = None, git_root: Path | None = None) -> subprocess.CompletedProcess[str]:
        """``align apply <spec> --auto --repo-root <toolkit> --git-root <git_root> <flags>``; never raises on a non-zero exit."""
        env = dict(os.environ)
        env.update(PATH=f"{self.bin_dir}{os.pathsep}{env['PATH']}", GIT_LOG=str(self.log), TMPDIR=str(self.scratch))
        argv = [
            sys.executable, "-m", "specdev_tools.cli", "align", "apply", str(spec or host / SPEC), "--auto",
            "--repo-root", str(self.toolkit), "--git-root", str(git_root or host), *flags,
        ]
        done = subprocess.run(argv, capture_output=True, text=True, env=env, cwd=self.scratch.parent, check=False)
        self.runs.append(done)
        return done


def _verb(argv: list[str]) -> str | None:
    """The git subcommand of *argv*: the first word that is not an option or the value of ``-C`` / ``-c``."""
    skip = False
    for word in argv:
        if skip:
            skip = False
        elif word in ("-C", "-c"):
            skip = True
        elif not word.startswith("-"):
            return word
    return None


def make_cli(tmp_path: Path) -> Cli:
    """The command for a temp 1.2.0 toolkit root in ``tmp_path`` and a logging ``git`` wrapper (a shell script)."""
    real_git = shutil.which("git")
    assert real_git, "git is needed"
    bin_dir, scratch = tmp_path / "bin", tmp_path / "tmp" / "scratch"
    bin_dir.mkdir()
    scratch.mkdir(parents=True)
    wrapper = bin_dir / "git"
    wrapper.write_text(f"#!/bin/sh\n( IFS=\"$(printf '\\t')\"; printf '%s\\n' \"$*\" >> \"$GIT_LOG\" )\nexec {real_git} \"$@\"\n", encoding="utf-8")
    wrapper.chmod(wrapper.stat().st_mode | stat.S_IXUSR)
    return Cli(make_toolkit(tmp_path), bin_dir, tmp_path / "git-calls.log", scratch)


def stamp_of(host: Path) -> dict:
    return yaml.safe_load((host / SPEC / STAMP).read_text(encoding="utf-8"))


def json_of(done: subprocess.CompletedProcess[str]) -> dict:
    return json.loads(done.stdout)


# ---------------------------------------------------------------------------
# What a run must leave alone
# ---------------------------------------------------------------------------


def _digest_files(root: Path) -> dict[str, str]:
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob("*")) if p.is_file()}


def git_state(host: Path) -> dict[str, object]:
    """Everything a git write would change: HEAD, every ref, the index content, the stash, the config, the hooks."""
    return {
        "head": git(host, "rev-parse", "HEAD"),
        "refs": git(host, "for-each-ref"),
        "branches": git(host, "branch", "-a"),
        "index": hashlib.sha256(git(host, "ls-files", "-s").encode()).hexdigest(),
        "stash": git(host, "stash", "list"),
        "config": (host / ".git" / "config").read_bytes(),
        "hooks": _digest_files(host / ".git" / "hooks"),
    }


def outside_spec(host: Path) -> dict[str, str]:
    """The digest of every file of the work tree (outside ``.git``) that is not under ``spec/``."""
    return {rel: digest for rel, digest in tree_digest(host).items() if not rel.startswith(f"{SPEC}/")}


def changed_paths(host: Path) -> list[str]:
    """Paths ``git status`` shows as changed or new, one per file (untracked folders expanded)."""
    return sorted(line[3:] for line in git(host, "status", "--porcelain", "-uall").splitlines() if line)


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
