"""Rows and plans as a 1.1.1 project left them read through the lifecycle readers without error."""
from __future__ import annotations

from pathlib import Path

from specdev_tools.core.plan_files import find_plan
from specdev_tools.lifecycle import anchor_store, frozen, plans

SPEC = Path(__file__).parents[2] / "fixtures" / "m8_legacy_rows" / "spec"


def test_legacy_rows_read_through_read_row_find_plan_and_plan_hash() -> None:
    pending = anchor_store.read_row(SPEC, "ms-pending")
    done = anchor_store.read_row(SPEC, "ms-done")
    assert pending is not None and pending.status == "pending"
    assert done is not None and done.status == "done" and anchor_store.is_legacy_close(done.close)
    assert find_plan(SPEC, "ms-pending") == SPEC / "impl_context" / "ms_pending_plan.json"
    legacy_plan = find_plan(SPEC, "ms-done")
    assert legacy_plan is not None
    assert plans.plan_hash(legacy_plan).startswith("sha256:")
    assert find_plan(SPEC, "ms-unkeyed") is None
    assert plans.plan_hash(SPEC / "impl_context" / "ms_unkeyed_plan.json").startswith("sha256:")


def test_a_legacy_close_without_a_hash_is_frozen_and_never_drifts() -> None:
    assert frozen.is_frozen(SPEC, "ms-done") and not frozen.is_frozen(SPEC, "ms-pending")
    assert frozen.frozen_plan_drift(SPEC, "ms-done") is None
