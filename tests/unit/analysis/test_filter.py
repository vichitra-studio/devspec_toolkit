"""Filter unit tests — pure."""
from __future__ import annotations

from specdev_tools.analysis.upstream_backlog import (
    SEVERITY_ORDER,
    _severity_rank,
    filter_records,
)


def _rec(**kw):
    base = {
        "milestone_id": "ms-x",
        "ambiguity_id": "amb-y",
        "severity": "low",
        "status": "tracking",
        "status_unset": False,
        "description": "",
        "impact": [],
        "bucket": "unclassified",
        "matched_rule": 4,
        "matched_impact_entry": None,
    }
    base.update(kw)
    return base


def test_severity_ordering_monotonic():
    assert SEVERITY_ORDER["low"] < SEVERITY_ORDER["medium"]
    assert SEVERITY_ORDER["medium"] < SEVERITY_ORDER["high"]
    assert SEVERITY_ORDER["high"] < SEVERITY_ORDER["critical"]


def test_severity_min_medium_drops_low():
    records = [
        _rec(ambiguity_id="a1", severity="low"),
        _rec(ambiguity_id="a2", severity="medium"),
        _rec(ambiguity_id="a3", severity="high"),
        _rec(ambiguity_id="a4", severity="critical"),
    ]
    out = filter_records(records, "medium", "all")
    assert {r["ambiguity_id"] for r in out} == {"a2", "a3", "a4"}


def test_status_open_excludes_only_resolved():
    records = [
        _rec(ambiguity_id="a1", status="tracking"),
        _rec(ambiguity_id="a2", status="deferred"),
        _rec(ambiguity_id="a3", status="resolved"),
        _rec(ambiguity_id="a4", status="blocked"),  # 4th atom value
    ]
    out = filter_records(records, "low", "open")
    assert {r["ambiguity_id"] for r in out} == {"a1", "a2", "a4"}


def test_status_resolved_keeps_only_resolved():
    records = [
        _rec(ambiguity_id="a1", status="tracking"),
        _rec(ambiguity_id="a2", status="resolved"),
        _rec(ambiguity_id="a3", status="blocked"),
    ]
    out = filter_records(records, "low", "resolved")
    assert {r["ambiguity_id"] for r in out} == {"a2"}


def test_status_all_is_noop():
    records = [
        _rec(ambiguity_id="a1", status="tracking"),
        _rec(ambiguity_id="a2", status="resolved"),
    ]
    out = filter_records(records, "low", "all")
    assert len(out) == 2


def test_null_status_coerced_survives_open():
    r = _rec(ambiguity_id="a1", status="tracking", status_unset=True)
    assert filter_records([r], "low", "open") == [r]


def test_blocked_excluded_under_resolved_filter():
    r = _rec(ambiguity_id="a1", status="blocked")
    assert filter_records([r], "low", "resolved") == []


# ---------------------------------------------------------------------------
# DEVSPEC-123: plan.ambiguities[] (origin="plan") uses a binary
# blocking/non_blocking severity scale, mapped onto the shared rank.
# ---------------------------------------------------------------------------

def test_severity_rank_defaults_to_execution_scale_without_origin():
    r = _rec(severity="high")
    assert _severity_rank(r) == SEVERITY_ORDER["high"]


def test_severity_rank_plan_blocking_maps_to_critical():
    r = _rec(origin="plan", severity="blocking")
    assert _severity_rank(r) == SEVERITY_ORDER["critical"]


def test_severity_rank_plan_non_blocking_maps_to_low():
    r = _rec(origin="plan", severity="non_blocking")
    assert _severity_rank(r) == SEVERITY_ORDER["low"]


def test_severity_filter_high_keeps_plan_blocking_drops_plan_non_blocking():
    records = [
        _rec(ambiguity_id="a1", origin="plan", severity="blocking"),
        _rec(ambiguity_id="a2", origin="plan", severity="non_blocking"),
    ]
    out = filter_records(records, "high", "all")
    assert {r["ambiguity_id"] for r in out} == {"a1"}
