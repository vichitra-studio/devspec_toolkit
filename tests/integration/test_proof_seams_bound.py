"""The proof implementations of the context seams are the ones every path that runs graph checks uses.

Each test runs one path in a FRESH process (nothing imported before) on a copy of the worked example built so that a seam
changes what the path reports: the example's fixture ``fix-password-reset-expired-token`` is bound only at stage ``dev``
and the environment ``dev`` is out of scope, so ``retired_bindings`` takes the fixture out of play and ``ac-password-reset-3``
loses its verifier (E743); a spare fixture is named by a binding record, so ``record_users`` keeps it from E742 while a bare
one is reported.  With a seam left at its default the numbers differ, so a path that reports them used the bound seam.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from unit.graph._synth import ROOT, run_specdev
from unit.proof._support import add_fixture, binding_item, commit_all, edit_doc, host_with

RETIRED_PROBE = ("E743", "ac-password-reset-3")
USED_THROUGH_RECORD = "fix-spare"
UNUSED = "fix-bare"
UNUSED_FINDING = ("E742", UNUSED)
ROOT_FLAGS = ("--repo-root", str(ROOT))


@pytest.fixture(scope="module")
def host(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The example with its dev environment out of scope (so the example's dev binding is retired) and two spare fixtures, one named by a binding record."""
    host = host_with(tmp_path_factory.mktemp("seams"), binding_item("ver-spare", verifier=USED_THROUGH_RECORD, proves=("ac-password-reset-1",)), keep_example_binding=True)
    add_fixture(host, fixture_id=USED_THROUGH_RECORD, verifies=["ac-password-reset-1"])
    add_fixture(host, fixture_id=UNUSED, verifies=["ac-password-reset-2"])
    edit_doc(host, "02a_delivery_baseline.json", lambda doc: doc["environments"]["dev"].update(scope="out", scope_reason="the dev environment is not shipped"))
    commit_all(host)
    return host


def _findings(document: Any) -> set[tuple[str, str]]:
    """Every ``(code, node)`` pair found anywhere in *document* (the shapes of ``spec-check``, ``stale`` and ``coverage`` differ)."""
    found: set[tuple[str, str]] = set()
    if isinstance(document, dict):
        node = document.get("node_id") or document.get("node")
        if isinstance(document.get("code"), str) and isinstance(node, str):
            found.add((document["code"], node))
        for value in document.values():
            found |= _findings(value)
    elif isinstance(document, list):
        for value in document:
            found |= _findings(value)
    return found


def _in_fresh_process(code: str, *args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(ROOT / "tools") + os.pathsep + os.environ.get("PYTHONPATH", "")}
    return subprocess.run([sys.executable, "-c", code, *args], capture_output=True, text=True, env=env)


def _flags(host: Path) -> list[str]:
    return [*ROOT_FLAGS, "--spec-root", str(host / "spec"), "--git-root", str(host)]


def _assert_seams_used(found: set[tuple[str, str]]) -> None:
    assert RETIRED_PROBE in found, "retired_bindings was not the proof implementation: the fixture of ac-password-reset-3 is still in play"
    assert UNUSED_FINDING in found
    assert ("E742", USED_THROUGH_RECORD) not in found, "record_users was not the proof implementation: a binding record names fix-spare"


@pytest.mark.parametrize("command", [["stale"], ["coverage"], ["spec-check", "spec", "--step", "14"], ["spec-check", "spec"]], ids=["stale", "coverage", "step-gate", "spec-check"])
def test_a_command_in_a_fresh_process_uses_the_bound_seams(command: list[str], host: Path) -> None:
    done = run_specdev(*command, "--json", *_flags(host))
    assert done.stdout, done.stderr
    _assert_seams_used(_findings(json.loads(done.stdout)))


def test_step_ready_in_a_fresh_process_uses_the_bound_retired_bindings_seam(host: Path) -> None:
    """``step ready 14`` reads the role gaps of the steps before it: with the dev fixture retired, step 08 holds the E743 of ac-password-reset-3."""
    done = run_specdev("step", "ready", "14", *_flags(host))
    assert "step 08: coverage gap E743: " in done.stdout and "ac-password-reset-3" in done.stdout


def test_the_check_runner_called_in_process_uses_the_bound_seams(host: Path) -> None:
    """A caller that never builds the parser (a gate in a library) gets the seams from ``validation.spec_check`` alone."""
    code = (
        "import json, sys\n"
        "from specdev_tools.validation.spec_check import run_spec_check_json\n"
        "_errors, report = run_spec_check_json(sys.argv[1], sys.argv[2], git_root=sys.argv[3], spec_root=sys.argv[2])\n"
        "print(json.dumps(report))\n"
    )
    done = _in_fresh_process(code, str(ROOT), str(host / "spec"), str(host))
    assert done.returncode == 0, done.stderr
    _assert_seams_used(_findings(json.loads(done.stdout)))

