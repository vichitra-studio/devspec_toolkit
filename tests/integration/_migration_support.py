"""Support for the migration tests that run ``specdev align`` as a subprocess on a git clone of the mini host: the hosts, the command with its git log, and what a run must leave alone."""

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

import yaml

from unit.migration._support import VARIANT, git, make_host, make_toolkit, tree_digest

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
