"""The link a lock finding is about travels in ``SpecError.target`` (OPEN-2 of M6a), on a copy of the worked example."""
from __future__ import annotations

import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from specdev_tools.core.errors import SpecError
from specdev_tools.graph.build import build_graph
from specdev_tools.graph.check import run_graph_check
from specdev_tools.graph.contract import item_at
from specdev_tools.graph.gitview import read_seed_texts
from specdev_tools.trace.lockfile import Lock, LockEntry, read_lock, write_lock
from specdev_tools.trace.suspects import check_lock

from ..trace._lock_support import EXAMPLE_HOST
from ._synth import ROOT

CRITERION = "ac-password-reset-3"
HASH = "sha256:" + "5" * 64


@pytest.fixture
def host(tmp_path: Path) -> Path:
    copy = tmp_path / "host"
    shutil.copytree(EXAMPLE_HOST, copy)
    return copy


def _edit_criterion(host: Path) -> None:
    node = build_graph(str(host / "spec"), str(ROOT)).by_id[CRITERION]
    path = host / "spec" / node.file
    document = json.loads(path.read_text(encoding="utf-8"))
    item = item_at(document, node.jq_path)
    assert item is not None
    item["text"] = item["text"] + " Also reject a token issued for another account."  # type: ignore[index]
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def _targets(errors: list[SpecError], code: str) -> set[tuple[str | None, str | None]]:
    return {(error.node_id, error.target) for error in errors if error.code == code}


def test_suspect_findings_carry_the_link_target(host: Path) -> None:
    spec = host / "spec"
    marked = ("api-password-reset-confirm", "derives_from", "fr-password-reset")
    entries = [
        replace(entry, baseline=entry.key == marked) for entry in read_lock(str(spec)).entries
        if entry.source != "fr-password-reset"
    ]
    write_lock(str(spec), Lock((*entries, LockEntry("scope-password-reset", "derives_from", "need-ghost", HASH, HASH))))
    _edit_criterion(host)
    graph = build_graph(str(spec), str(ROOT))
    lock = read_lock(str(spec))
    found = [*run_graph_check(str(spec), str(ROOT), graph=graph, lock=lock), *check_lock(graph, lock, read_seed_texts(graph, str(host)))]
    assert _targets(found, "E761") == {("fr-password-reset", "derives_from->cap-account-recovery")}
    assert _targets(found, "E762") == {("scope-password-reset", "derives_from->need-ghost")}
    assert _targets(found, "E882") == {("api-password-reset-confirm", "derives_from->fr-password-reset")}
    assert ("tc-confirm-expired-token", f"refines->{CRITERION}") in _targets(found, "E763")
    assert all(error.target for error in found if error.code in {"E761", "E762", "E763", "E882"})
