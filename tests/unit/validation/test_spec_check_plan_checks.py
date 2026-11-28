"""The ``frozen-plans`` check of ``spec-check``: PASS, SKIP and E827 findings on copies of the worked example."""
from __future__ import annotations

import json
from functools import partial
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from specdev_tools.lifecycle import anchor_store, frozen, plans
from specdev_tools.lifecycle.plan_records import Address, record_action
from specdev_tools.validation.open_items import check_open_items
from specdev_tools.validation.spec_check import _check_plan_records, run_spec_check_json
from unit.graph._synth import ROOT
from unit.lifecycle._record_support import ITEM, change_lock_hash, closed_row, plan_host, roots
from unit._ambiguity_support import unified_item
from unit.lifecycle._support import MILESTONE, PLAN, closed_record, edit_row, example_spec
from unit.verify._support import edit_doc


def _check(spec: Path) -> dict[str, Any]:
    _errors, context = run_spec_check_json(str(ROOT), str(spec))
    return context["checks"]["frozen-plans"]


def test_frozen_plans_passes_when_no_milestone_is_closed(tmp_path: Path) -> None:
    assert _check(example_spec(tmp_path))["status"] == "PASS"


def test_frozen_plans_skips_on_a_pre_migration_fixture(tmp_path: Path) -> None:
    spec = example_spec(tmp_path)
    anchor_store.write_row_state(spec, MILESTONE, "done", close={"signed_off_by": "legacy-migration", "source": "14.status"}, repo_root=str(ROOT))
    result = _check(spec)
    assert result["status"] == "SKIP" and "plan hash" in result["reason"]


def test_frozen_plans_reports_e827_on_a_migrated_fixture(tmp_path: Path) -> None:
    spec = example_spec(tmp_path)
    anchor_store.write_row_state(spec, MILESTONE, "done", close=closed_record(plan_hash=plans.plan_hash(spec / PLAN)), repo_root=str(ROOT))
    assert _check(spec)["status"] == "PASS"
    plan = spec / PLAN
    plan.write_text(plan.read_text(encoding="utf-8").replace("30 minutes", "31 minutes"), encoding="utf-8")
    result = _check(spec)
    assert result["status"] == "FAIL"
    (finding,) = result["findings"]
    assert (finding["code"], finding["owner"], finding["node_id"]) == ("E827", "step:16", MILESTONE)
    assert finding["file"] == "impl_context/ms_account_recovery_plan.json"


def _plan_records(spec: Path) -> dict[str, Any]:
    _errors, context = run_spec_check_json(str(ROOT), str(spec))
    return context["checks"]["plan-records"]


def test_plan_records_skips_without_lock_or_graph(tmp_path: Path) -> None:
    spec = example_spec(tmp_path)
    assert _plan_records(spec)["status"] == "PASS"
    (spec / "extras" / "trace.lock.json").unlink()
    result = _plan_records(spec)
    assert result["status"] == "SKIP" and "trace lock" in result["reason"]
    result = _check_plan_records(SimpleNamespace(check_graph=None))
    assert result["status"] == "SKIP" and "graph" in result["reason"]


def test_plan_records_reports_w825_and_w826(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Ada Lovelace")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "ada@example.invalid")
    host = plan_host(tmp_path)
    spec, repo, git = roots(host)
    record_action(spec, repo, git, Address(ITEM, "a01"), "done")
    assert _plan_records(host / "spec")["status"] == "PASS"

    change_lock_hash(host)
    stale = _plan_records(host / "spec")
    (finding,) = stale["findings"]
    assert (stale["status"], finding["code"], finding["node_id"], finding["owner"]) == ("WARN", "W825", "rec-0001", "step:16")

    edit_doc(host, "14_roadmap.json", lambda doc: doc["milestones"][0]["tasks"][0].update(disposition={"value": "deferred", "reason": "Blocked on the mail vendor sandbox."}))
    excluded = _plan_records(host / "spec")
    assert sorted(item["code"] for item in excluded["findings"]) == ["W825", "W826"]
    only = next(item for item in excluded["findings"] if item["code"] == "W826")
    assert only["node_id"] == ITEM and "deferred or wont_do" in only["message"]


def test_plan_records_reports_neither_for_a_closed_milestone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Ada Lovelace")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "ada@example.invalid")
    host = plan_host(tmp_path)
    spec, repo, git = roots(host)
    record_action(spec, repo, git, Address(ITEM, "a01"), "done")
    change_lock_hash(host)
    edit_doc(host, "14_roadmap.json", lambda doc: doc["milestones"][0]["tasks"][0].update(disposition={"value": "wont_do", "reason": "Cancelled with the feature."}))
    closed_row(host)
    assert _plan_records(host / "spec")["status"] == "PASS"


def _open_items(spec: Path) -> dict[str, Any]:
    _errors, context = run_spec_check_json(str(ROOT), str(spec))
    return context["checks"]["open-items"]


def test_an_open_item_in_the_plan_of_a_closed_milestone_is_silent_at_the_step_gate(tmp_path: Path) -> None:
    spec = example_spec(tmp_path)
    plan = spec / PLAN
    item = {"id": "amb-token-store", "description": "Is the token store per user?", "about": ["tc-confirm-expired-token"]}
    document = json.loads(plan.read_text(encoding="utf-8"))
    document["execution"] = {"emergent_ambiguities": [item]}
    plan.write_text(json.dumps(document, indent=2), encoding="utf-8")
    live = _open_items(spec)
    assert live["status"] == "WARN" and [finding["code"] for finding in live["findings"]] == ["W630"]

    anchor_store.write_row_state(spec, MILESTONE, "done", close=closed_record(plan_hash=plans.plan_hash(plan)), repo_root=str(ROOT))
    assert _open_items(spec)["findings"] == []
    # the merge gate through the library, with the provider the step gate passes: a legacy item, W633
    legacy = check_open_items(str(spec), gate="merge", frozen=partial(frozen.is_frozen_path, str(spec)))
    assert [error.code for error in legacy] == ["W633"]


def _second_paused_task() -> dict[str, Any]:
    return {
        "task_id": "task-second", "description": "A second task, deferred.", "disposition": {"value": "deferred", "reason": "Waiting for the vendor sandbox."},
        "acceptance_criteria": [{"criterion_id": "tc-second", "text": "The second task's work is done and its verifier shows it.", "verified_by": ["fix-password-reset-reused-token"]}],
    }


def test_plan_records_is_silent_for_an_item_that_realises_a_paused_and_a_live_criterion(tmp_path: Path) -> None:
    host = plan_host(tmp_path)
    edit_doc(host, "14_roadmap.json", lambda doc: doc["milestones"][0]["tasks"].append(_second_paused_task()))
    edit_doc(host, PLAN, lambda doc: doc["plan"]["spec_alignment"]["checklist"][0]["realises"].append("tc-second"))
    result = _plan_records(host / "spec")
    assert [finding["code"] for finding in result["findings"]] == [] and result["status"] == "PASS"
    # the live criterion paused as well: the item realises only paused criteria, W826
    edit_doc(host, "14_roadmap.json", lambda doc: doc["milestones"][0]["tasks"][0].update(disposition={"value": "wont_do", "reason": "Cancelled with the feature."}))
    result = _plan_records(host / "spec")
    assert [(finding["code"], finding["node_id"]) for finding in result["findings"]] == [("W826", ITEM)]


def test_the_latest_record_of_an_action_decides_w825(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Ada Lovelace")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "ada@example.invalid")
    host = plan_host(tmp_path)
    spec, repo, git = roots(host)
    record_action(spec, repo, git, Address(ITEM, "a01"), "done")
    change_lock_hash(host)
    assert [finding["code"] for finding in _plan_records(host / "spec")["findings"]] == ["W825"]
    record_action(spec, repo, git, Address(ITEM, "a01"), "done")  # the second record carries the hash of now
    assert _plan_records(host / "spec")["status"] == "PASS"


def _plan_with_open_item(spec: Path) -> None:
    plan = spec / PLAN
    document = json.loads(plan.read_text(encoding="utf-8"))
    document["plan"]["ambiguities"] = [unified_item("amb-token-length", about=["tc-confirm-expired-token"])]
    plan.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def test_an_anchor_row_with_an_unknown_status_does_not_stop_spec_check_at_one_line(tmp_path: Path) -> None:
    spec = example_spec(tmp_path)
    _plan_with_open_item(spec)
    edit_row(spec, lambda row: row.update(status="bogus"))
    _errors, context = run_spec_check_json(str(ROOT), str(spec))
    checks = context["checks"]
    assert len(checks) > 5  # the whole report, not the one line of the E801
    assert [finding["code"] for finding in checks["frozen-plans"]["findings"]] == ["E801"]
    assert [error.code for error in _errors].count("E801") == 1
    assert [finding["code"] for finding in checks["open-items"]["findings"]] == ["W630"]


def test_an_open_item_of_a_closed_plan_is_silent_and_of_an_open_one_is_listed(tmp_path: Path) -> None:
    spec = example_spec(tmp_path)
    _plan_with_open_item(spec)
    _errors, context = run_spec_check_json(str(ROOT), str(spec))
    assert [finding["code"] for finding in context["checks"]["open-items"]["findings"]] == ["W630"]
    anchor_store.write_row_state(spec, MILESTONE, "done", close=closed_record(plan_hash=plans.plan_hash(spec / PLAN)), repo_root=str(ROOT))
    _errors, context = run_spec_check_json(str(ROOT), str(spec))
    assert context["checks"]["open-items"]["findings"] == []
