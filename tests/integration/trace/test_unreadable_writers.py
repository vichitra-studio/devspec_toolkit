"""Every write that plans from the graph refuses while a spec file cannot be read (review M5 R1, F3-5).

A file that cannot be read gives no nodes, so a rename could not rewrite the links it holds and a delete could not list
them.  Each writer, dry run included, ends with E520 naming the file, exit 1, and nothing in the working tree changes.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from unit.graph._synth import git
from unit.trace._lock_support import git_copy_of_example, run_on_example

FR = "fr-password-reset"
API = "api-password-reset-confirm"
TERM = "term-reset-token"

WRITERS = {
    "patch": ["json", "patch", "--id", API, ".summary", '"x"'],
    "patch-dry-run": ["json", "patch", "--id", API, ".summary", '"x"', "--dry-run"],
    "insert-by-id": ["json", "insert", "--id", FR, ".tags", '"t"'],
    "insert-by-step": ["json", "insert", "--step", "05", ".endpoints", "{}"],
    "delete": ["json", "delete", "--id", API],
    "delete-dry-run": ["json", "delete", "--id", API, "--dry-run"],
    "step-create": ["step", "create", "15", "--from", "spec/15_scaffold.json"],
    "step-create-dry-run": ["step", "create", "15", "--from", "spec/15_scaffold.json", "--dry-run"],
    "rename": ["node", "rename", API, "api-password-reset-complete"],
    "rename-dry-run": ["node", "rename", API, "api-password-reset-complete", "--dry-run"],
    "rename-label": ["node", "rename", "--label", TERM, "Reset code"],
    "rename-label-dry-run": ["node", "rename", "--label", TERM, "Reset code", "--dry-run"],
    "attest-yes": ["attest", API, "--yes"],
    "attest-dry-run": ["attest", API, "--yes", "--dry-run"],
    "attest-prune": ["attest", "--prune"],
    "attest-prune-dry-run": ["attest", "--prune", "--dry-run"],
}


@pytest.mark.parametrize("argv", WRITERS.values(), ids=WRITERS.keys())
def test_a_write_refuses_while_a_spec_file_cannot_be_read(tmp_path: Path, argv: list[str]) -> None:
    host = git_copy_of_example(tmp_path / "host")
    shutil.rmtree(host / "spec" / "extras")  # a host with no lock yet: a refused write must not leave an empty folder behind (H1-4)
    broken = host / "spec" / "04_fr_list.json"
    broken.write_text("<<<<<<< ours\n" + broken.read_text(encoding="utf-8") + "=======\n>>>>>>> theirs\n", encoding="utf-8")
    git(host, "add", "-A")
    git(host, "commit", "-q", "-m", "conflict markers")
    before = sorted(os.listdir(host / "spec"))
    code, out = run_on_example(host, *argv)
    assert code == 1, out
    assert "E520" in out and "04_fr_list.json cannot be read" in out and "refused" in out, out
    assert git(host, "status", "--porcelain", "--ignored") == ""
    assert sorted(os.listdir(host / "spec")) == before and "extras" not in before
