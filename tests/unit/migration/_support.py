"""Support shared by the migration tests: the live toolkit root, the mini host, a fake toolkit root, a git helper, a host copy.

Not a ``test_*`` module, so a test, a support module or a scripted pass imports from here and never from another test file.
``REAL_ROOT`` is the live checkout: it says the released version (1.2.0), has the real changelog, and serves every test that
needs "a toolkit root that says 1.2.0".  ``make_toolkit`` builds the one FAKE root (a chosen version and chosen changelog
entries, nothing else) for the tests that need a root whose content differs from the live one.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import yaml

from specdev_tools import cli
from specdev_tools.migration import runner
from specdev_tools.migration.context import MigrationContext
from specdev_tools.migration.registry import Script, ScriptResult, ScriptSpec
from specdev_tools.migration.report import STATUS_OK
from specdev_tools.migration.writer import DocumentSet

REAL_ROOT = Path(__file__).resolve().parents[3]
MINI_HOST = REAL_ROOT / "tests" / "fixtures" / "migration" / "mini_host_1_1_1"
VARIANT = MINI_HOST / "variants" / "status_ref_1_0_x" / "04_fr_list.json"
"""The mini host's ``04_fr_list.json`` of a 1.0.x host: it carries ``status_ref`` keys."""


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


WORKLIST = "extras/migration/worklist.json"


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


def context(host: Path, toolkit: Path) -> MigrationContext:
    spec = str(host / "spec")
    return MigrationContext(spec, str(host), str(host), str(toolkit), True, DocumentSet(spec), "1.1.1", "1.2.0")


def specdev(*argv: str) -> tuple[int, str, str]:
    """Run ``specdev align ...`` in process; return (exit code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    code = 0
    with (
        patch("specdev_tools.cli.check_venv", return_value=None),
        patch.object(sys, "argv", ["specdev", "align", *argv]),
        redirect_stdout(out),
        redirect_stderr(err),
    ):
        try:
            cli.main()
        except SystemExit as exit_:
            code = exit_.code if isinstance(exit_.code, int) else (0 if exit_.code is None else 1)
    return code, out.getvalue(), err.getvalue()
