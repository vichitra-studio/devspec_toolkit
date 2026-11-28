"""File-level forward replay is gone (WI-M6c-02): an id dropped from a spec file raises no removal finding.

The deleted node is caught where it is used: every holder of a link to it has a broken link (see
``unit/graph/test_resolve.py::test_deleted_node_surfaces_as_broken_link``).
"""
from __future__ import annotations

import shutil
from pathlib import Path

from specdev_tools.validation.spec_check import run_spec_check_json
from specdev_tools.validation.validate import validate_dir

from unit.graph._synth import ROOT, git
from unit.trace._lock_support import EXAMPLE_HOST

REMOVED_CODES = {"E550", "E555", "W550", "W598"}
FR_FILE = "04_fr_list.json"
DROPPED_ID = "ac-password-reset-1"


def _host_with_a_dropped_id(tmp_path: Path) -> Path:
    """The worked example committed on ``main``, then ``feature`` with the id ``DROPPED_ID`` removed from the FR list."""
    host = tmp_path / "host"
    shutil.copytree(EXAMPLE_HOST, host)
    git(host, "init", "-q", "-b", "main")
    git(host, "add", "-A")
    git(host, "commit", "-q", "-m", "base")
    git(host, "checkout", "-q", "-b", "feature")
    path = host / "spec" / FR_FILE
    text = path.read_text(encoding="utf-8")
    assert f'"{DROPPED_ID}"' in text
    path.write_text(text.replace(f'"{DROPPED_ID}"', '"ac-renamed-1"'), encoding="utf-8")
    git(host, "add", "-A")
    git(host, "commit", "-q", "-m", "drop an id")
    return host


def test_dropped_id_raises_no_removal_error(tmp_path: Path) -> None:
    host = _host_with_a_dropped_id(tmp_path)
    spec = str(host / "spec")
    errors, _context = run_spec_check_json(str(ROOT), spec, git_root=str(host), spec_root=spec)
    assert REMOVED_CODES.isdisjoint(e.code for e in errors)
    failures = validate_dir(str(ROOT), spec, git_root=str(host), spec_root=spec)
    assert REMOVED_CODES.isdisjoint(e.code for e in failures)
