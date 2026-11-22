"""What the host-installer test files share: a scratch git host with a spec folder, and the install context of a piece run on it.

``test_host_install_core.py`` builds a different host (a toolkit checkout beside it) and keeps its own.
"""
from __future__ import annotations

import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from specdev_tools import host_install as hi

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def host(tmp_path: Path) -> Path:
    """An empty git repository holding an empty ``spec`` folder."""
    root = tmp_path / "host"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / "spec").mkdir()
    return root


def make_ctx(host: Path, **overrides: object) -> hi.InstallContext:
    """The install context of *host*: toolkit folder ``devspec_toolkit``, venv ``devspec_env``, toolkit 1.2.3, a real run; *overrides* name the fields to change."""
    base = hi.InstallContext(
        spec_dir=host / "spec",
        spec_rel="spec",
        git_root=host,
        toolkit_root=host / "devspec_toolkit",
        templates_dir=REPO / "templates",
        toolkit_version="1.2.3",
        venv_prefix=host / "devspec_env",
        venv_name="devspec_env",
        dry_run=False,
        adopt=False,
        force_claude=False,
    )
    return replace(base, **overrides)
