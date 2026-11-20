"""Every consumer that walks the spec folder meets ``spec/common/host_declarations.json`` and ignores it.

The file has a ``$schema`` and no step.  Each test runs one consumer on a git copy of the worked example before and
after the file is added and expects the same answer (the file adds nothing and breaks nothing).
"""
from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

import pytest

from integration._step_gate_support import run_split
from specdev_tools.canonical.autofix import canonical_autofix
from specdev_tools.canonical.integrity import validate_canonical_integrity
from specdev_tools.core.config import reset_config
from specdev_tools.core.host_declarations import HOST_DECLARATIONS_FILE
from specdev_tools.core.loaders import iter_spec_artifacts, read_json_object
from specdev_tools.graph.build import build_graph
from specdev_tools.graph.ownership import step_for_file, stamp_file_owner
from specdev_tools.validation.fixtures_lint import _load_fixtures, lint_fixtures
from specdev_tools.validation.governance import load_governance
from specdev_tools.validation.linter_utils import iter_json
from specdev_tools.validation.spec_check import run_spec_check as run_plain_spec_check
from specdev_tools.validation.spec_quality_lint import lint_spec_quality
from specdev_tools.validation.touched_steps import steps_for_paths
from specdev_tools.validation.validate import validate_dir, validate_file
from unit.trace._lock_support import ROOT, git_copy_of_example

T = TypeVar("T")

FIXTURE_FILE = ROOT / "tests" / "fixtures" / "host_declarations" / "spec" / HOST_DECLARATIONS_FILE
GOLDEN = ROOT / "tests" / "fixtures" / "step_gate" / "spec_check_summary.golden"
STEP_ORDER = json.loads((ROOT / "tools" / "step_order.json").read_text(encoding="utf-8"))["steps"]


@pytest.fixture
def host(tmp_path: Path) -> Path:
    """A git copy of the worked example, with no declarations file."""
    return git_copy_of_example(tmp_path / "host")


def _add_declarations(host: Path) -> Path:
    target = host / "spec" / HOST_DECLARATIONS_FILE
    shutil.copyfile(FIXTURE_FILE, target)
    return target


def _same_before_and_after(host: Path, probe: Callable[[Path], T]) -> tuple[T, T]:
    """``probe(spec folder)`` before and after the declarations file is added to *host*."""
    spec = host / "spec"
    before = probe(spec)
    reset_config()
    _add_declarations(host)
    return before, probe(spec)


def test_spec_check_passes_with_the_file_present(host: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The summary of ``spec-check`` on the example with the file added is the pinned golden: no new check, no new finding."""
    _add_declarations(host)
    spec = str(host / "spec")
    run_plain_spec_check(str(ROOT), spec, git_root=str(host), spec_root=spec, project_canon_dir=f"{spec}/canon")
    assert capsys.readouterr().err == GOLDEN.read_text(encoding="utf-8")


def test_the_walk_of_spec_artifacts_reaches_the_file(host: Path) -> None:
    """The file lies where ``iter_spec_artifacts`` looks (``spec/common``), so the other tests exercise it."""
    target = _add_declarations(host)
    assert str(target) in set(iter_spec_artifacts(str(host / "spec")))


def test_integrity_and_autofix_ignore_the_file(host: Path) -> None:
    def probe(spec: Path) -> tuple[Any, Any]:
        canon = f"{spec}/canon"
        return (
            validate_canonical_integrity(str(ROOT), str(spec), project_canon_dir=canon),
            canonical_autofix(str(ROOT), str(spec), write=False, project_canon_dir=canon),
        )

    before, after = _same_before_and_after(host, probe)
    assert after == before


def test_linter_walk_ignores_the_file(host: Path) -> None:
    def probe(spec: Path) -> tuple[list[str], Any]:
        return sorted(iter_json(str(spec))), lint_spec_quality(str(spec))

    (files_before, findings_before), (files_after, findings_after) = _same_before_and_after(host, probe)
    assert findings_after == findings_before
    assert len(files_after) == len(files_before) + 1


def test_validate_dir_ignores_the_file(host: Path) -> None:
    def probe(spec: Path) -> list[Any]:
        return validate_dir(str(ROOT), str(spec), f"{spec}/canon", git_root=str(host), spec_root=str(spec))

    before, after = _same_before_and_after(host, probe)
    assert after == before
    assert not [error for error in after if "host_declarations" in str(error)]


def test_governance_load_ignores_the_file(host: Path) -> None:
    before, after = _same_before_and_after(host, lambda spec: load_governance(str(spec)))
    assert after == before
    assert after is not None and after.get("$schema") != "vc:host-declarations"


def test_fixtures_lint_ignores_the_file(host: Path) -> None:
    """The example's fixtures file carries the registry id, which the reader skips, so a 1.1.1-style fixtures file (a ``$schema`` ending ``/08_fixtures.schema.json``) is added to give the reader something to find."""
    fixture = {"fixture_id": "fx-one", "input": {}, "expected": {"status": 200}}
    legacy = {"$schema": "https://example.invalid/schema/08_fixtures.schema.json", "fixtures": [fixture]}
    (host / "spec" / "08_legacy.json").write_text(json.dumps(legacy), encoding="utf-8")

    def probe(spec: Path) -> tuple[list[Any], list[Any]]:
        return _load_fixtures(str(spec)), lint_fixtures(str(spec))

    before, after = _same_before_and_after(host, probe)
    assert after == before
    assert after[0] == [fixture]


def test_touched_steps_maps_the_file_to_no_step(host: Path) -> None:
    spec = host / "spec"
    _add_declarations(host)
    manifest = read_json_object(spec / "common" / "seed_manifest.json") or {}
    touched = steps_for_paths(
        [f"spec/{HOST_DECLARATIONS_FILE}"],
        str(spec),
        manifest,
        lambda: build_graph(str(spec), str(ROOT)),
        step_order=STEP_ORDER,
        git_root=str(host),
    )
    assert (touched.steps, touched.outside_root, touched.seed_edited) == ((), (), False)


def test_schema_validation_check_stamps_no_owner_on_the_file(host: Path) -> None:
    """The file passes ``validate_file``; a broken copy is reported by the schema and the finding keeps no step owner."""
    target = _add_declarations(host)

    def findings(path: Path) -> list[Any]:
        return validate_file(
            str(ROOT), str(path), include_quality_lint=False, include_canonical_integrity=False,
            git_root=str(host), spec_root=str(host / "spec"), include_id_slice=False,
        )

    assert step_for_file(str(target), read_json_object(target)) is None
    assert findings(target) == []
    document = json.loads(target.read_text(encoding="utf-8"))
    target.write_text(json.dumps({**document, "unknown_key": 1}), encoding="utf-8")
    broken = findings(target)
    assert broken
    assert all(error.owner is None for error in stamp_file_owner(broken, step_for_file(str(target), read_json_object(target))))


def test_cli_validate_names_no_finding_for_the_file(host: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """``spec-check --json`` on the example with the file added reports no finding about it."""
    _add_declarations(host)
    flags = ["--repo-root", str(ROOT), "--spec-root", str(host / "spec"), "--git-root", str(host)]
    _code, out, _err = run_split(capsys, "spec-check", str(host / "spec"), *flags, "--json")
    assert "host_declarations" not in out
