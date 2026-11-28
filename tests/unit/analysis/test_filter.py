"""Filter unit tests: ``--severity`` and ``--status`` apply to legacy items only."""
from __future__ import annotations

import pytest

from specdev_tools.analysis.upstream_backlog import SEVERITY_ORDER, Record, Placement, filter_records, severity_rank
from specdev_tools.core.ambiguity_items import AmbiguityItem, shape_of

_PLACED = Placement(("04",), (), ())


def _rec(step: str = "16b", **raw) -> Record:
    raw.setdefault("id", "amb-y")
    return Record(AmbiguityItem("p.json", step, ".x", raw, shape_of(raw)), "p.json", _PLACED, "04")


def _ids(records: list[Record]) -> set[str]:
    return {r.item_id for r in records}


def test_severity_ordering_monotonic():
    assert SEVERITY_ORDER["low"] < SEVERITY_ORDER["medium"] < SEVERITY_ORDER["high"] < SEVERITY_ORDER["critical"]


def test_severity_min_medium_drops_low():
    records = [_rec(id=f"a-{s}", severity=s) for s in SEVERITY_ORDER]
    assert _ids(filter_records(records, "medium", "all")) == {"a-medium", "a-high", "a-critical"}


@pytest.mark.parametrize("status, kept", [
    ("open", {"a-tracking", "a-deferred", "a-blocked"}),
    ("resolved", {"a-resolved"}),
    ("all", {"a-tracking", "a-deferred", "a-blocked", "a-resolved"}),
])
def test_status_filter_on_legacy_items(status, kept):
    records = [_rec(id=f"a-{s}", severity="low", status=s) for s in ("tracking", "deferred", "blocked", "resolved")]
    assert _ids(filter_records(records, "low", status)) == kept


def test_severity_and_status_filters_apply_to_legacy_items_only():
    unified = _rec(id="u", about=["fr-a"])
    legacy_resolved = _rec(id="l", severity="low", status="resolved")
    out = filter_records([unified, legacy_resolved], "critical", "open")
    assert out == [unified]
    assert filter_records([unified], "critical", "resolved") == [unified]


def test_plan_scale_maps_onto_the_shared_rank():
    assert severity_rank(_rec("16a", severity="blocking")) == SEVERITY_ORDER["critical"]
    assert severity_rank(_rec("16a", severity="non_blocking")) == SEVERITY_ORDER["low"]
    assert severity_rank(_rec("16b", severity="high")) == SEVERITY_ORDER["high"]


def test_severity_filter_high_keeps_plan_blocking_drops_plan_non_blocking():
    records = [_rec("16a", id="a1", severity="blocking"), _rec("16a", id="a2", severity="non_blocking")]
    assert _ids(filter_records(records, "high", "all")) == {"a1"}


def test_unified_item_ranks_critical_and_survives_every_threshold():
    record = _rec(about=["fr-a"])
    assert severity_rank(record) == SEVERITY_ORDER["critical"]
    for threshold in SEVERITY_ORDER:
        assert filter_records([record], threshold, "all") == [record]
