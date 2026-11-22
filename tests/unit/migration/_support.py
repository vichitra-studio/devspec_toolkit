"""Support shared by the migration tests: the live toolkit root, the mini host, a fake toolkit root, a git helper, a host copy.

Not a ``test_*`` module, so a test, a support module or a scripted pass imports from here and never from another test file.
``REAL_ROOT`` is the live checkout: it says the released version (1.2.0), has the real changelog, and serves every test that
needs "a toolkit root that says 1.2.0".  ``make_toolkit`` builds the one FAKE root (a chosen version and chosen changelog
entries, nothing else) for the tests that need a root whose content differs from the live one.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from pathlib import Path

import yaml

from specdev_tools.migration.registry import Script, ScriptResult, ScriptSpec

REAL_ROOT = Path(__file__).resolve().parents[3]
MINI_HOST = REAL_ROOT / "tests" / "fixtures" / "migration" / "mini_host_1_1_1"


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
