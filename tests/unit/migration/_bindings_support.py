"""Support for the legacy binding tests (WI-M10-17): a migrated copy of the mini host, in-process CLI calls and small edits of its files."""

from __future__ import annotations

import io
import json
import shlex
import shutil
import sys
from collections.abc import Callable
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any
from unittest.mock import patch

from specdev_tools import cli
from specdev_tools.migration.proposers import MigratedTree, context_of, load_tree

from .test_convert_remove import edit as _edit_and_commit
from .test_runner_core import MINI_HOST, REAL_ROOT, git

OVERLAY = MINI_HOST.parent / "legacy_bindings" / "ci"
CAPTURE = "extras/migration/capture.json"
FIXTURES = "08_fixtures.json"
RECORDS = Path("spec") / "extras" / "verification"


def specdev(*argv: str) -> tuple[int, str, str]:
    """Run ``specdev <argv>`` in process; return (exit code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    code = 0
    with patch("specdev_tools.cli.check_venv", return_value=None), patch.object(sys, "argv", ["specdev", *argv]), redirect_stdout(out), redirect_stderr(err):
        try:
            cli.main()
        except SystemExit as exit_:
            code = exit_.code if isinstance(exit_.code, int) else (0 if exit_.code is None else 1)
    return code, out.getvalue(), err.getvalue()


def align(host: Path, action: str, *argv: str, stdin_tty: bool = False) -> tuple[int, str, str]:
    """``specdev align <action> <host>/spec`` against the live toolkit and *host* as the git root; stdin is no terminal unless *stdin_tty*."""
    with patch("sys.stdin.isatty", return_value=stdin_tty):
        return specdev("align", action, str(host / "spec"), "--repo-root", str(REAL_ROOT), "--git-root", str(host), *argv)


def run_line(host: Path, line: str) -> tuple[int, str, str]:
    """Run a ``specdev ...`` line a proposal printed, adding the root flags of *host* when the line has none."""
    words = shlex.split(line)
    assert words[0] == "specdev", line
    roots = [] if "--repo-root" in words else ["--repo-root", str(REAL_ROOT), "--spec-root", str(host / "spec"), "--git-root", str(host)]
    return specdev(*words[1:], *roots)


def fresh(migrated_host: Path, tmp_path: Path, *, overlay: bool = False) -> Path:
    """A copy of the migrated host in *tmp_path* (with its git history), committed; *overlay* adds the invented CI workflow and its test file."""
    host = tmp_path / "copy"
    tmp_path.mkdir(parents=True, exist_ok=True)
    shutil.copytree(migrated_host, host)
    if overlay:
        shutil.copytree(OVERLAY, host, dirs_exist_ok=True)
    git(host, "add", "-A")
    if git(host, "status", "--porcelain").strip():
        git(host, "commit", "-q", "-m", "migrated")
    return host


def edit_json(host: Path, rel: str, change: Callable[[Any], None]) -> None:
    """Edit ``spec/<rel>`` of *host* and commit it."""
    _edit_and_commit(host, rel, change)


def edit_capture(host: Path, item: str, **fields: Any) -> None:
    """Set ``legacy_*`` fields of the capture's plan item *item* (a ``None`` value removes the field)."""

    def change(data: dict) -> None:
        entry = next(row for row in data["plan_items"] if row["item"] == item)
        for name, value in fields.items():
            entry.pop(name, None) if value is None else entry.__setitem__(name, value)

    edit_json(host, CAPTURE, change)


def fixture_of(host: Path, fixture_id: str) -> dict:
    """The fixture *fixture_id* of ``spec/08_fixtures.json`` of *host*."""
    data = json.loads((host / "spec" / FIXTURES).read_text(encoding="utf-8"))
    return next(entry for entry in data["fixtures"] if entry["fixture_id"] == fixture_id)


def records(host: Path) -> dict[str, bytes]:
    """``{file name: bytes}`` of the verification records of *host*."""
    folder = host / RECORDS
    return {path.name: path.read_bytes() for path in sorted(folder.glob("*.json"))} if folder.is_dir() else {}


def tree_of(host: Path) -> MigratedTree:
    """The tree a proposer reads for *host* (against the live toolkit)."""
    return load_tree(context_of(host / "spec", REAL_ROOT, host))
