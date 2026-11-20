"""A closed milestone's frozen links in the graph check and in the id-keyed write paths (M7 WI-09, the historical set).

A closed criterion's ``verified_by`` or ``refines`` target may be deleted: the graph check raises no E700 for it, and an
id-keyed write is judged by the findings it adds, so the link that already dangles never blocks one.  A write that would
put a NEW dangling link into a closed criterion is refused: the write paths resolve without the historical set.
"""
from __future__ import annotations

import json
from pathlib import Path

from specdev_tools.graph.build import build_graph
from specdev_tools.graph.check import run_graph_check
from specdev_tools.trace import id_writes, rename
from specdev_tools.trace.lockfile import read_lock

from unit.graph._synth import ROOT, run_cli
from unit.proof._closed import FIXTURES, MILESTONE, closed_example, set_status
from unit.verify._support import edit_doc

FROZEN_HOLDER = "tc-confirm-reused-token"
FIXTURE = "fix-password-reset-reused-token"
FR = "fr-password-reset"
FR_REQUEST = "fr-password-reset-request"


def _delete_fixture(host: Path) -> None:
    edit_doc(host, FIXTURES, lambda doc: doc["fixtures"].__setitem__(slice(None), [f for f in doc["fixtures"] if f["fixture_id"] != FIXTURE]))


def _e700(graph) -> set[str | None]:
    return {error.node_id for error in id_writes._finding_keys(graph).values() if error.code == "E700"}


def _check_e700(host: Path) -> set[str | None]:
    spec = str(host / "spec")
    graph = build_graph(spec, str(ROOT))
    return {error.node_id for error in run_graph_check(spec, str(ROOT), graph=graph, lock=read_lock(spec)) if error.code == "E700"}


def _flags(host: Path) -> list[str]:
    return ["--repo-root", str(ROOT), "--spec-root", str(host / "spec"), "--git-root", str(host)]


def test_check_ignores_a_deleted_target_of_a_closed_criterion(tmp_path: Path) -> None:
    host = closed_example(tmp_path)
    _delete_fixture(host)
    assert FROZEN_HOLDER not in _check_e700(host)


def test_writing_a_dangling_verified_by_into_a_closed_criterion_by_id_is_refused(tmp_path: Path) -> None:
    host = closed_example(tmp_path)
    status, out = run_cli("json", "patch", "--id", FROZEN_HOLDER, ".verified_by", json.dumps(["fix-does-not-exist"]), *_flags(host))
    assert status == 1 and "E767" in out and "E700" in out and "fix-does-not-exist" in out
    assert FROZEN_HOLDER not in _check_e700(host)


def test_an_id_keyed_write_of_an_unrelated_node_succeeds_after_that_deletion(tmp_path: Path) -> None:
    host = closed_example(tmp_path)
    _delete_fixture(host)
    status, out = run_cli("json", "patch", "--id", FR, ".statement", json.dumps("The system shall let a member set a new password."), *_flags(host), "--json")
    assert status == 0, out
    assert "E700" not in out


def test_a_live_criterion_with_a_missing_verified_by_target_is_still_e700_in_the_check_and_both_write_paths(tmp_path: Path) -> None:
    host = closed_example(tmp_path)
    set_status(host, MILESTONE, "open")
    _delete_fixture(host)
    graph = build_graph(str(host / "spec"), str(ROOT))
    assert FROZEN_HOLDER in _check_e700(host)
    assert FROZEN_HOLDER in _e700(graph)
    assert FROZEN_HOLDER in {code_node for code, code_node in rename._finding_keys(graph) if code == "E700"}


def test_deleting_the_target_of_a_closed_criterion_by_id_is_not_refused_for_its_frozen_link(tmp_path: Path) -> None:
    host = closed_example(tmp_path)
    status, out = run_cli("json", "delete", "--id", FIXTURE, *_flags(host), "--json")
    assert status == 0 and json.loads(out)["written"], out
    assert "E700" not in out
