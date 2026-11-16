"""Host probe of the spec graph (WI-M4-12): build the graph of a migrated host and time the ``graph`` check.

Two tests run only when a host is provided.  Each host is named by one environment variable holding the path of the
host's spec folder (not its repository root):

* ``SPECDEV_HOST_PROBE_W``: the spec folder of host W,
* ``SPECDEV_HOST_PROBE_P``: the spec folder of host P.

The path is read only: nothing is copied into it and nothing is written under it.  The probe asserts that the graph
builds and the check runs, and prints the node count, the finding count and the wall time (design R-12: timing is
recorded, not gated).  It asserts no finding count: no host is migrated yet.  A variable set to a path that is not a
folder fails with a message naming the variable.
"""
from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path
from typing import NamedTuple

import pytest

from specdev_tools.graph.build import build_graph
from specdev_tools.graph.check import run_graph_check
from unit.graph._synth import ROOT, copy_example

HOST_W = "SPECDEV_HOST_PROBE_W"
HOST_P = "SPECDEV_HOST_PROBE_P"


class ProbeResult(NamedTuple):
    """What one probe measured."""

    nodes: int
    findings: int
    seconds: float


def probe_folder(variable: str) -> Path:
    """The spec folder named by environment variable *variable*.

    Skips the test when the variable is unset or empty; fails with a message naming the variable when its value is
    not an existing folder.
    """
    value = os.environ.get(variable)
    if not value:
        pytest.skip(f"{variable} is not set: no migrated host to probe")
    folder = Path(value)
    if not folder.is_dir():
        pytest.fail(f"{variable}={value!r} is not a folder: set it to the spec folder of a migrated host")
    return folder


def probe(folder: Path) -> ProbeResult:
    """Build the graph of *folder* and run the ``graph`` check on it; read-only."""
    started = time.perf_counter()
    graph = build_graph(str(folder), str(ROOT))
    findings = run_graph_check(str(folder), str(ROOT), graph=graph)
    return ProbeResult(len(graph.nodes), len(findings), time.perf_counter() - started)


def run_host_probe(variable: str) -> ProbeResult:
    """Probe the host named by *variable*, print the node count and the wall time, and return the result."""
    result = probe(probe_folder(variable))
    print(f"host probe {variable}: {result.nodes} nodes, {result.findings} findings, {result.seconds:.2f} s")
    return result


def test_host_probe_graph_w() -> None:
    assert run_host_probe(HOST_W).nodes > 0


def test_host_probe_graph_p() -> None:
    assert run_host_probe(HOST_P).nodes > 0


# --- the harness itself: one test per branch, on a copy of the worked example ---------------------


def _digest(folder: Path) -> dict[str, str]:
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.rglob("*")) if p.is_file()}


@pytest.mark.parametrize("variable", [HOST_W, HOST_P])
def test_probe_is_skipped_when_the_variable_is_unset(monkeypatch: pytest.MonkeyPatch, variable: str) -> None:
    monkeypatch.delenv(variable, raising=False)
    with pytest.raises(pytest.skip.Exception, match=variable):
        run_host_probe(variable)


@pytest.mark.parametrize("variable", [HOST_W, HOST_P])
def test_probe_runs_on_a_provided_folder_and_prints_nodes_and_time(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path, variable: str
) -> None:
    spec = copy_example(tmp_path / "spec")
    before = _digest(spec)
    monkeypatch.setenv(variable, str(spec))
    result = run_host_probe(variable)
    assert result.nodes == len(build_graph(str(spec), str(ROOT)).nodes) > 0
    assert result.findings == 0 and result.seconds >= 0
    printed = capsys.readouterr().out
    assert f"{result.nodes} nodes" in printed and " s" in printed
    assert _digest(spec) == before


@pytest.mark.parametrize("variable", [HOST_W, HOST_P])
def test_probe_of_a_missing_folder_fails_with_a_clear_message(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, variable: str
) -> None:
    monkeypatch.setenv(variable, str(tmp_path / "no-such-host"))
    with pytest.raises(pytest.fail.Exception, match=rf"{variable}=.*is not a folder"):
        run_host_probe(variable)
