"""``specdev milestone close``: the one write, what it leaves alone, and every way the gate refuses it."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.core.errors import FindingError
from specdev_tools.core.schema_validate import validate_data_against_schema
from specdev_tools.graph.build import build_graph
from specdev_tools.lifecycle import anchor_store, frozen
from specdev_tools.lifecycle.executed import lock_if_present
from specdev_tools.validation.graph_checks import run_graph_checks
from specdev_tools.validation.graph_checks.context import GraphCheckContext
from specdev_tools.validation.graph_checks.prose_ids import check_prose_ids
from specdev_tools.lifecycle.milestone import close_milestone
from specdev_tools.lifecycle.plan_records import Address, record_action
from unit.graph._synth import ROOT
from unit.lifecycle._milestone_support import cli_run, providers_of, ready_host, set_row
from unit.lifecycle._record_support import ALPHA, ITEM, author, plan_host, roots
from unit.lifecycle._support import ANCHOR, MILESTONE, PLAN
from unit.proof._support import REUSED_BINDING, run

pytestmark = pytest.mark.usefixtures("author")


def _close(host: Path, *, check: bool = False, given: str = MILESTONE) -> Any:
    spec, repo, git = roots(host)
    return close_milestone(spec, repo, git, given, providers_of(host), check_only=check)


def test_close_writes_status_and_the_close_record(tmp_path: Path) -> None:
    host = ready_host(tmp_path, signed=True)
    result = _close(host)
    assert result.closed and result.report.passed
    row = anchor_store.read_row(host / "spec", MILESTONE)
    assert row is not None and row.status == "done" and row.deferral_reason is None
    close = dict(row.close or {})
    assert close.pop("closed_at")
    assert close == {"signed_off_by": "ada@example.invalid", "signoff": "so-ms-account-recovery-0001", "tree": result.tree, "plan_hash": close["plan_hash"], "migrations": []}
    assert result.tree == result.signoff_tree
    assert validate_data_against_schema(str(ROOT), json.loads((host / "spec" / ANCHOR).read_text(encoding="utf-8"))) == []


def test_close_leaves_the_plan_bytes_unchanged(tmp_path: Path) -> None:
    host = ready_host(tmp_path, signed=True)
    before = (host / "spec" / PLAN).read_bytes()
    _close(host)
    assert (host / "spec" / PLAN).read_bytes() == before
    assert frozen.frozen_plan_drift(host / "spec", MILESTONE) is None and frozen.is_frozen(host / "spec", MILESTONE)
    spec, repo, git = roots(host)
    with pytest.raises(FindingError) as caught:
        record_action(spec, repo, git, Address(ITEM, "a01"), "done")
    assert caught.value.error.code == "E820"
    assert frozen.check_frozen_plans(spec).errors == ()


def test_second_close_is_e801(tmp_path: Path) -> None:
    host = ready_host(tmp_path, signed=True)
    _close(host)
    before = (host / "spec" / ANCHOR).read_bytes()
    with pytest.raises(FindingError) as caught:
        _close(host)
    assert caught.value.error.code == "E801"
    assert (host / "spec" / ANCHOR).read_bytes() == before


def test_check_flag_writes_nothing(tmp_path: Path) -> None:
    host = ready_host(tmp_path, signed=True)
    before = (host / "spec" / ANCHOR).read_bytes()
    result = _close(host, check=True)
    assert result.report.passed and not result.closed and result.record is None
    assert (host / "spec" / ANCHOR).read_bytes() == before
    code, out, _ = cli_run(host, "milestone", "close", MILESTONE, "--check")
    assert code == 0 and "nothing written" in out


def test_failed_close_lists_errors_by_owner_and_writes_nothing(tmp_path: Path) -> None:
    host = ready_host(tmp_path)
    before = (host / "spec" / ANCHOR).read_bytes()
    result = _close(host)
    assert not result.closed and [error.code for error in result.report.errors] == ["E814"]
    assert (host / "spec" / ANCHOR).read_bytes() == before
    code, out, err = cli_run(host, "milestone", "close", MILESTONE)
    assert code == 1 and out == "" and "cannot be closed: 1 error(s)" in err and "close-gate (1):" in err and "E814" in err
    code, out, _ = cli_run(host, "milestone", "close", MILESTONE, "--json")
    assert code == 1 and json.loads(out)["errors"][0]["code"] == "E814"


def test_close_before_the_work_is_done_reports_every_gate_code_at_once(tmp_path: Path) -> None:
    host = plan_host(tmp_path)
    codes = [error.code for error in _close(host).report.errors]
    assert codes == ["E810", "E811", "E811", "E812", "E813", "E746", "E814"]


def test_close_refuses_a_milestone_that_is_not_in_progress_and_a_batch_id(tmp_path: Path) -> None:
    host = ready_host(tmp_path, signed=True)
    set_row(host, "pending")
    with pytest.raises(FindingError) as caught:
        _close(host)
    assert caught.value.error.code == "E801"
    code, _, err = cli_run(host, "milestone", "close", "account_recovery")
    assert code == 1 and "batch id" in err and "milestone-state --batch-id account_recovery" in err


def test_close_prints_the_two_trees_and_says_when_they_differ(tmp_path: Path) -> None:
    host = ready_host(tmp_path, signed=True)
    (host / "src" / "hello.txt").write_text("changed after the sign-off\n", encoding="utf-8")
    run(host, [REUSED_BINDING, ALPHA])
    code, out, _ = cli_run(host, "milestone", "close", MILESTONE)
    assert code == 0 and "the tree of the sign-off is not the tree the milestone is closed at" in out


def test_after_close_the_graph_and_prose_checks_report_nothing_for_the_anchor_row(tmp_path: Path) -> None:
    host = ready_host(tmp_path, signed=True)
    _close(host)
    spec = str(host / "spec")
    graph = build_graph(spec, str(ROOT))
    context = GraphCheckContext.from_graph(graph, lock_if_present(spec), str(ROOT), git_root=str(host), spec_root=spec)
    findings = [*check_prose_ids(context, "merge"), *run_graph_checks(context, "merge")]
    assert [f for f in findings if f.node_id == "anchor-ms-account-recovery" or "so-ms-account-recovery" in f.message] == []
