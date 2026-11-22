"""``spec-check --step`` while a host migrates (WI-M10-10): the baseline is "which steps are passed", not the merge-base.

Each host is a git copy of the worked example: the base commit carries a 1.1.1 stamp, the working tree a 1.2.0 stamp (the
migration under way) and, where a case needs them, the migration baseline marker on the trace-lock links held by one step.
The case that sets the stamps equal is the control: the same errors, the merge-base rule.
"""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from integration._step_gate_support import apply_delta, attest, commit_all, run_split, step_gate_host
from specdev_tools.graph.build import build_graph
from specdev_tools.trace.lockfile import Lock, read_lock, write_lock
from unit.graph._synth import ROOT

BROKEN = "broken_link_in_step_04"
BROKEN_CODE, BROKEN_NODE = "E700", "fr-broken-link"
MARKED_STEP = "04"


def _stamp(host: Path, version: str) -> None:
    (host / "spec" / "specdev_version").write_text(f"toolkit_version: {version}\n", encoding="utf-8")


def _mark_baseline(host: Path, step: str) -> None:
    """Put the migration baseline marker on every lock entry held by a node of *step*."""
    spec = str(host / "spec")
    graph = build_graph(spec, str(ROOT))
    lock = read_lock(spec)
    write_lock(spec, Lock(tuple(
        replace(entry, baseline=True) if (holder := graph.by_id.get(entry.source)) and holder.step == step else entry
        for entry in lock.entries
    )))


def _migrating_host(tmp_path: Path, *, base_has_error: bool, marked: bool, working_stamp: str = "1.2.0") -> Path:
    """A host whose base commit is stamped 1.1.1 (with the broken link of step 04 when *base_has_error*) and whose working tree is stamped *working_stamp*."""
    host = step_gate_host(tmp_path / "host", [BROKEN] if base_has_error else [], commit=base_has_error)
    _stamp(host, "1.1.1")
    commit_all(host, "stamp 1.1.1")
    if not base_has_error:
        apply_delta(host, BROKEN)
        attest(host)
    _stamp(host, working_stamp)
    if marked:
        _mark_baseline(host, MARKED_STEP)
    return host


def _gate(capsys: pytest.CaptureFixture[str], host: Path) -> dict[str, Any]:
    roots = ["--repo-root", str(ROOT), "--spec-root", str(host / "spec"), "--git-root", str(host)]
    _code, out, _err = run_split(capsys, "spec-check", str(host / "spec"), *roots, "--step", "05", "--json")
    return json.loads(out)["step_gate"]


def _found(findings: list[dict[str, Any]]) -> bool:
    return any(finding["code"] == BROKEN_CODE and finding.get("node_id") == BROKEN_NODE for finding in findings)


def test_breaking_a_passed_step_blocks_the_next_step_with_new_upstream_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    gate = _gate(capsys, _migrating_host(tmp_path, base_has_error=True, marked=False))
    assert _found(gate["blocking"]) and not _found(gate["upstream_debt"])


def test_an_error_of_a_step_with_markers_is_debt_not_block(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    gate = _gate(capsys, _migrating_host(tmp_path, base_has_error=False, marked=True))
    assert _found(gate["upstream_debt"]) and not _found(gate["blocking"])


def test_removing_the_version_difference_restores_the_merge_base_rule(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    with_error_at_base = _gate(capsys, _migrating_host(tmp_path / "a", base_has_error=True, marked=False, working_stamp="1.1.1"))
    new_since_base = _gate(capsys, _migrating_host(tmp_path / "b", base_has_error=False, marked=True, working_stamp="1.1.1"))
    assert _found(with_error_at_base["upstream_debt"]) and not _found(with_error_at_base["blocking"])
    assert _found(new_since_base["blocking"]) and not _found(new_since_base["upstream_debt"])


def test_a_step_with_no_markers_and_an_error_blocks_downstream(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    host = _migrating_host(tmp_path, base_has_error=False, marked=False)
    _mark_baseline(host, "05")
    gate = _gate(capsys, host)
    assert _found(gate["blocking"])
