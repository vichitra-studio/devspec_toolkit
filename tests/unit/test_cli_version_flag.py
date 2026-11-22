"""``specdev --version`` prints the toolkit's version; ``--version`` after a subcommand belongs to that subcommand."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from specdev_tools.core.changelog_parser import get_toolkit_version

ROOT = Path(__file__).parents[2]


def _specdev(*argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-m", "specdev_tools.cli", *argv], capture_output=True, text=True, cwd=ROOT)


def test_the_global_flag_prints_the_toolkit_version() -> None:
    done = _specdev("--version")
    assert done.returncode == 0 and done.stdout.strip() == f"specdev {get_toolkit_version(ROOT)}"


def test_changelog_version_shows_that_version_and_not_the_toolkit_version_line() -> None:
    done = _specdev("changelog", "--version", "1.1.0", "--repo-root", str(ROOT))
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() != f"specdev {get_toolkit_version(ROOT)}"
    assert "1.1.0" in done.stdout and len(done.stdout.splitlines()) > 3
