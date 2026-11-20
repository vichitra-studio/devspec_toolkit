"""``spec-check`` on the worked example with the graph checks real: the owners of their findings (WI-M6b-02 part; the other tests of the file are written in wave 4)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from integration._step_gate_support import run_split
from unit.trace._lock_support import ROOT, git_copy_of_example

STEP_14_FILE = "14_roadmap.json"
DANGLING_AT_14 = ("err-password-reset-confirm-token-expired", "nfr-latency-reset-email", "threat-reset-token-replay", "ec-token-at-expiry-second")
DANGLING_AT_12 = ("dev", "staging", "prod", "secret-mailrelay-api-key", "secret-reset-token-signing-key")


def _gate(capsys: pytest.CaptureFixture[str], host: Path, step: str) -> dict[str, Any]:
    flags = ["--repo-root", str(ROOT), "--spec-root", str(host / "spec"), "--git-root", str(host)]
    _code, out, _err = run_split(capsys, "spec-check", str(host / "spec"), *flags, "--step", step, "--json")
    return json.loads(out)["step_gate"]


def _e740(findings: list[dict[str, Any]]) -> set[str]:
    return {finding["node_id"] for finding in findings if finding["code"] == "E740"}


def test_half_authored_example_shows_pending_owners(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """With step 14 not authored, the nodes that only a step-14 node can use are pending under owner 14, those a job uses under 12; nothing blocks step 11."""
    complete = git_copy_of_example(tmp_path / "complete")
    complete_gate = _gate(capsys, complete, "11")
    half = git_copy_of_example(tmp_path / "half")
    (half / "spec" / STEP_14_FILE).unlink()
    half_gate = _gate(capsys, half, "11")

    assert _e740(half_gate["blocking"]) == set()
    assert set(DANGLING_AT_14) <= _e740(half_gate["pending"]["14"])
    assert set(DANGLING_AT_12) <= _e740(half_gate["pending"]["12"])
    assert _e740(half_gate["pending"]["14"]) == _e740(complete_gate["pending"]["14"])
    assert _e740(half_gate["pending"]["12"]) == _e740(complete_gate["pending"]["12"])
