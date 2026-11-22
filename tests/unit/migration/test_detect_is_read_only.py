"""``detect`` of every registered script leaves the documents and the files of the spec folder as they are (D1 of round 1).

The runner calls ``detect(context)`` and then ``apply(context)`` on the SAME ``DocumentSet``, and writes what ``apply`` left
changed.  A ``detect`` that edits a loaded document would therefore have its edit written and counted by no one.  The test runs
the whole 1.1.1 to 1.2.0 chain on a git copy of the mini host with every ``detect`` wrapped: at each script's turn (so on the
tree as the script finds it, after the earlier scripts) it checks that no loaded document changed and that no file of the spec
folder was written, created or deleted.  The one script of an older version (``p3_strip_status_ref``) is checked on the mini host as it is.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

from specdev_tools.migration import runner
from specdev_tools.migration.context import MigrationContext
from specdev_tools.migration.registry import PHASE_SHAPES, Script, discover_scripts
from specdev_tools.migration.report import STATUS_OK
from specdev_tools.migration.writer import DocumentSet

from ._support import make_host, make_script, make_toolkit

TARGET = "1.2.0"


def _digest(spec_root: str) -> dict[str, str]:
    return dict(runner.take_snapshot(spec_root).files)


def _checked(script: Script, seen: list[str], violations: list[str]) -> Script:
    """*script* with a ``detect`` that records what the original did to its context's documents and to the folder."""
    original = script.detect

    def detect(ctx: MigrationContext) -> int:
        files = _digest(ctx.spec_root)
        found = original(ctx)
        seen.append(script.id)
        changed = [document.rel for document in ctx.documents.changed()]
        if changed:
            violations.append(f"{script.id}: detect changed the loaded document(s) {changed}")
        if _digest(ctx.spec_root) != files:
            violations.append(f"{script.id}: detect wrote, created or deleted a file of the spec folder")
        return found

    return dataclasses.replace(script, detect=detect)


def test_detect_leaves_every_document_and_file_unchanged_for_every_script_of_the_chain(tmp_path: Path) -> None:
    host, toolkit = make_host(tmp_path), make_toolkit(tmp_path)
    seen: list[str] = []
    violations: list[str] = []
    registered = [script for script in discover_scripts() if script.version == TARGET]
    report = runner.run_migration(host / "spec", toolkit_root=toolkit, git_root=host, scripts=[_checked(s, seen, violations) for s in registered])
    assert report.status == STATUS_OK, report.errors
    assert not violations, violations
    assert sorted(set(seen)) == sorted(script.id for script in registered), "every registered script's detect ran under the check"
    assert len(registered) > 20


def test_detect_of_the_older_script_leaves_the_mini_host_unchanged(tmp_path: Path) -> None:
    host = make_host(tmp_path)
    older = [script for script in discover_scripts() if script.version != TARGET]
    assert older, "the registry holds a script of an older version"
    spec = str(host / "spec")
    for script in older:
        ctx = MigrationContext(spec, str(host), str(host), str(make_toolkit(tmp_path)), False, DocumentSet(spec), "1.0.0", TARGET)
        files = _digest(spec)
        script.detect(ctx)
        assert ctx.documents.changed() == [] and _digest(spec) == files, script.id


def test_the_check_would_catch_a_detect_that_edits_a_loaded_document(tmp_path: Path) -> None:
    """The wrapper itself: a ``detect`` that edits a document it loaded is reported (without the check the run passes)."""
    host, toolkit = make_host(tmp_path), make_toolkit(tmp_path)

    def detect(ctx: MigrationContext) -> int:
        ctx.documents.load("04_fr_list.json").data["edited_by_detect"] = True
        return 1

    seen: list[str] = []
    violations: list[str] = []
    bad = dataclasses.replace(make_script("p3_probe", PHASE_SHAPES), detect=detect)
    runner.run_migration(host / "spec", toolkit_root=toolkit, git_root=host, scripts=[_checked(bad, seen, violations)])
    assert violations and "04_fr_list.json" in violations[0]
