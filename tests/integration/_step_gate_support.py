"""Builders for the step gate tests: a git copy of the worked example with the deltas of ``tests/fixtures/step_gate`` on top.

A delta is a JSON file with ``ops`` (see ``tests/fixtures/step_gate/README.md``).  The copy, the git repository and the
command runner are the ones M5 ships (``tests/unit/trace/_lock_support.py``); nothing of the example is copied into the
fixtures folder.
"""
from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from specdev_tools.graph.build import build_graph
from specdev_tools.trace.lockfile import write_lock

from unit.graph._synth import git
from unit.trace._lock_support import ROOT, git_copy_of_example, lock_for, run_on_example

DELTAS = ROOT / "tests" / "fixtures" / "step_gate" / "deltas"


class DeltaError(Exception):
    """A delta names an op, a file or a path the host copy does not have."""


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, document: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def _array_at(document: Any, keys: list[str], *, create: bool) -> list[Any]:
    """The array at the object path *keys* of *document*; with *create*, the last key is made an empty array when absent."""
    node = document
    for key in keys[:-1]:
        node = node[key]
    if keys[-1] not in node and create:
        node[keys[-1]] = []
    array = node[keys[-1]]
    if not isinstance(array, list):
        raise DeltaError(f"{'.'.join(keys)} is not an array")
    return array


def _apply_op(host: Path, op: dict[str, Any]) -> None:
    target = host / op["file"]
    if op["op"] == "write":
        _write(target, op["value"])
    elif op["op"] == "append":
        if not target.is_file():
            raise DeltaError(f"{op['file']}: no such file in the host copy")
        document = _read(target)
        _array_at(document, op["path"], create=op.get("create", False)).append(op["value"])
        _write(target, document)
    else:
        raise DeltaError(f"unknown op '{op['op']}'")


def apply_delta(host: Path, name: str) -> None:
    """Apply the delta ``tests/fixtures/step_gate/deltas/<name>.json`` to the host copy *host*.

    Raises ``DeltaError`` for an unknown op, a missing file or a path that is not an array.
    """
    for op in _read(DELTAS / f"{name}.json")["ops"]:
        _apply_op(host, op)


def commit_all(host: Path, message: str) -> None:
    """Commit the working tree of *host* (a baseline for the step gate's merge-base comparison)."""
    git(host, "add", "-A")
    git(host, "commit", "-q", "-m", message)


def step_gate_host(
    destination: Path, deltas: Iterable[str] = (), *, attested: bool = True, commit: bool = False
) -> Path:
    """The worked example copied to *destination* as a git repository, with *deltas* applied; returns the host folder.

    With *attested* the trace lock accepts every link as the deltas leave it, so a new link raises no E761; pass
    ``False`` for a test about a link with no lock entry.  The deltas and the lock are left uncommitted, so the copy's
    one commit is the clean baseline; with *commit* they are committed too.
    """
    host = git_copy_of_example(destination)
    for name in deltas:
        apply_delta(host, name)
    if attested:
        write_lock(str(host / "spec"), lock_for(build_graph(str(host / "spec"), str(ROOT)), host))
    if commit:
        commit_all(host, "deltas: " + ", ".join(deltas))
    return host


def run_spec_check(host: Path, *flags: str) -> tuple[int, str]:
    """Run ``specdev spec-check`` on the spec folder of *host* with the three root flags: ``(exit code, output)``."""
    return run_on_example(host, "spec-check", str(host / "spec"), *flags)
