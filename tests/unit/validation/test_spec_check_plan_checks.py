"""The ``frozen-plans`` check of ``spec-check``: PASS, SKIP and E827 findings on copies of the worked example."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from specdev_tools.lifecycle import anchor_store, plans
from specdev_tools.validation.spec_check import run_spec_check_json
from unit.graph._synth import ROOT
from unit.lifecycle._support import MILESTONE, PLAN, closed_record, example_spec


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
