"""The ``frozen-plans`` check of ``spec-check``: PASS, SKIP and E827 findings on copies of the worked example."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from specdev_tools.lifecycle import anchor_store, plans
from specdev_tools.lifecycle.plan_records import Address, record_action
from specdev_tools.validation.spec_check import _check_plan_records, run_spec_check_json
from unit.graph._synth import ROOT
from unit.lifecycle._record_support import ITEM, change_lock_hash, close_milestone, plan_host, roots
from unit.lifecycle._support import MILESTONE, PLAN, closed_record, example_spec
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
    close_milestone(host)
    assert _plan_records(host / "spec")["status"] == "PASS"
