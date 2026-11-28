"""The traceability closure is gone (WI-M6c-15): no module, no check line, no command, no code.

The questions its two commands answered are answered by ``specdev coverage`` (link counts and the ids not linked) and
by the role rules of ``specdev spec-check`` (E740 to E745).
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from specdev_tools.validation.spec_check import run_spec_check_json

from unit.graph._synth import ROOT, run_cli
from unit.trace._lock_support import EXAMPLE_HOST

CLOSURE_CODES = {
    "E535", "E536", "E560", "E562", "E563", "E564", "E565", "E568", "E569", "E575", "E576",
    "W562", "W563", "W564", "W565", "W568", "W569", "W575", "W576",
}
RETIRED_COMMANDS = {"completeness-check": "specdev coverage", "traceability-check": "specdev spec-check"}


@pytest.fixture
def host(tmp_path: Path) -> Path:
    copy = tmp_path / "host"
    shutil.copytree(EXAMPLE_HOST, copy)
    return copy


def test_spec_check_on_new_shape_corpus_reports_no_closure_codes(host: Path) -> None:
    _errors, report = run_spec_check_json(str(ROOT), str(host / "spec"), git_root=str(host))
    codes = {finding["code"] for check in report["checks"].values() for finding in check.get("findings", [])}
    assert not codes & CLOSURE_CODES
    assert not set(report["checks"]) & {"traceability-closure", "completeness-check"}


def test_retired_closure_commands_are_absent_from_help() -> None:
    code, help_text = run_cli("--help")
    assert code == 0
    for command, pointer in RETIRED_COMMANDS.items():
        assert command not in help_text
        code, out = run_cli(command, "spec", "--repo-root", str(ROOT))
        assert code == 2
        assert f"{command} was removed in 1.2.0" in out and pointer in out


def test_the_closure_module_and_the_registered_commands_are_gone() -> None:
    assert not (ROOT / "tools" / "specdev_tools" / "validation" / "traceability_closure.py").exists()
    registry = (ROOT / "tools" / "cli_commands.json").read_text(encoding="utf-8")
    assert not [command for command in RETIRED_COMMANDS if f'"{command}"' in registry]
