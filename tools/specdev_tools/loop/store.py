"""The run folder of ``specdev loop``: ``<git root>/.specdev/runs/<run-id>/``.

All state of a run is here. ``run.json`` holds the machine's state (:class:`RunState`) and
what the machine does not need to decide but the tool needs to remember (``meta``): the
scope, the roots, the text of every finding, the questions asked. Files are written under a
temporary name and renamed, so a reader never sees half a file.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import asdict
from typing import Any

from specdev_tools.loop.machine import Dispatch, Entry, Finding, RunState

RUNS_DIR = os.path.join(".specdev", "runs")
TMP_SUFFIX = ".tmp"


def runs_root(git_root: str) -> str:
    return os.path.join(git_root, RUNS_DIR)


def slug(text: str) -> str:
    """A scope as a file-name part: the findings schema allows no ``/`` in ``scope``."""
    return re.sub(r"[^a-z0-9_-]+", "-", text.lower()).strip("-") or "scope"


def new_run_id(kind: str, scope_label: str, now: float | None = None) -> str:
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(now if now is not None else time.time()))
    return f"{kind}-{slug(scope_label)}-{stamp}"


def write_json(path: str, document: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + TMP_SUFFIX
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(document, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, path)


def write_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + TMP_SUFFIX
    with open(tmp, "w", encoding="utf-8") as handle:
        handle.write(text)
    os.replace(tmp, path)


def read_json(path: str) -> Any:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _state_from(d: dict[str, Any]) -> RunState:
    d = dict(d)
    findings = {k: Finding(**v) for k, v in d.pop("findings", {}).items()}
    dispatch = d.pop("dispatch", None)
    s = RunState(**d)
    s.findings = findings
    if dispatch is not None:
        entries = [Entry(**e) for e in dispatch.pop("entries", [])]
        s.dispatch = Dispatch(entries=entries, **dispatch)
    return s


def save(run_dir: str, state: RunState, meta: dict[str, Any]) -> None:
    write_json(os.path.join(run_dir, "run.json"), {"state": asdict(state), "meta": meta})


def load(run_dir: str) -> tuple[RunState, dict[str, Any]]:
    document = read_json(os.path.join(run_dir, "run.json"))
    return _state_from(document["state"]), document["meta"]


def list_runs(git_root: str) -> list[str]:
    """The run ids that have a ``run.json``, oldest first (the id ends with its timestamp)."""
    root = runs_root(git_root)
    if not os.path.isdir(root):
        return []
    found = [r for r in os.listdir(root) if os.path.isfile(os.path.join(root, r, "run.json"))]
    return sorted(found, key=lambda r: (r.rsplit("-", 1)[-1], r))


def dispatch_dir(run_dir: str, number: int) -> str:
    return os.path.join(run_dir, f"d{number}")


def entry_path(run_dir: str, number: int, entry_id: str, attempt: int) -> str:
    return os.path.join(dispatch_dir(run_dir, number), f"{entry_id}.t{attempt}.json")
