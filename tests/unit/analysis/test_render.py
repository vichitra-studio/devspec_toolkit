"""Render unit tests — plain and JSON."""
from __future__ import annotations

import json

from specdev_tools.analysis.upstream_backlog import (
    _record_sort_key,
    render_json,
    render_plain,
)


def _rec(**kw):
    base = {
        "milestone_id": "ms-x",
        "ambiguity_id": "amb-y",
        "severity": "medium",
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


def _sample_records():
    return sorted([
        _rec(ambiguity_id="a-step09", bucket="step_09", severity="high",
             impact=["spec/09_impl_plan.json:task-foo"], matched_rule=1,
             matched_impact_entry="spec/09_impl_plan.json:task-foo"),
        _rec(ambiguity_id="a-plan", bucket="plan_level", severity="medium",
             impact=["plan.summary"], matched_rule=3,
             matched_impact_entry="plan.summary"),
        _rec(ambiguity_id="a-tool", bucket="toolkit", severity="low",
             impact=["E307 foo"], matched_rule=2,
             matched_impact_entry="E307 foo"),
        _rec(ambiguity_id="a-un", bucket="unclassified", severity="low",
             impact=["SCREAMING_TOKEN"]),
    ], key=_record_sort_key)


def test_plain_bucket_order():
    out = render_plain(
        _sample_records(), status_filter="open",
        total_records=4, open_count=4, resolved_count=0,
        milestones_scanned=1, unclassified_w613_count=1,
    )
    idx_step = out.index("Step 09")
    idx_plan = out.index("Plan-level")
    idx_tool = out.index("Toolkit")
    idx_un = out.index("Unclassified")
    assert idx_step < idx_plan < idx_tool < idx_un


def test_plain_unset_status_rendered():
    r = _rec(status="tracking", status_unset=True, bucket="plan_level",
             impact=["plan.x"])
    out = render_plain([r], status_filter="open", total_records=1,
                       open_count=1, resolved_count=0, milestones_scanned=1,
                       unclassified_w613_count=0)
    assert "(unset status → tracking)" in out


def test_plain_w613_header_when_unclassified():
    r = _rec(ambiguity_id="a-un", bucket="unclassified")
    out = render_plain([r], status_filter="open", total_records=1,
                       open_count=1, resolved_count=0, milestones_scanned=1,
                       unclassified_w613_count=1)
    assert "[1 x W613 — see stderr]" in out


def test_plain_origin_tag_plan_renders_16a():
    r = _rec(bucket="plan_level", impact=["plan.x"], origin="plan")
    out = render_plain([r], status_filter="open", total_records=1,
                       open_count=1, resolved_count=0, milestones_scanned=1,
                       unclassified_w613_count=0)
    assert "[16a]" in out


def test_plain_origin_tag_execution_renders_16b_plus():
    r = _rec(bucket="plan_level", impact=["plan.x"], origin="execution")
    out = render_plain([r], status_filter="open", total_records=1,
                       open_count=1, resolved_count=0, milestones_scanned=1,
                       unclassified_w613_count=0)
    assert "[16b+]" in out


def test_plain_totals_line():
    out = render_plain([], status_filter="open", total_records=0,
                       open_count=0, resolved_count=0, milestones_scanned=0,
                       unclassified_w613_count=0)
    assert out.startswith("Totals:")


def test_json_schema_version_and_shape():
    records = _sample_records()
    out = render_json(
        records, total_records=len(records), open_count=len(records),
        resolved_count=0, milestones_scanned=1, unclassified_count=1,
        warnings=[{"code": "W613", "target": "ms-x:a-un"}],
    )
    data = json.loads(out)
    assert data["schema_version"] == "1"
    assert set(data) == {"schema_version", "summary", "records", "warnings"}
    assert data["summary"]["unclassified_count"] == 1
    assert data["warnings"][0]["code"] == "W613"


def test_json_sort_order_buckets():
    records = _sample_records()
    out = json.loads(render_json(
        records, total_records=4, open_count=4, resolved_count=0,
        milestones_scanned=1, unclassified_count=1, warnings=[],
    ))
    buckets = [r["bucket"] for r in out["records"]]
    assert buckets == ["step_09", "plan_level", "toolkit", "unclassified"]


def test_letter_suffix_sort_order():
    recs = [
        _rec(ambiguity_id="a13a", bucket="step_13a", severity="low"),
        _rec(ambiguity_id="a14", bucket="step_14", severity="low"),
        _rec(ambiguity_id="a13", bucket="step_13", severity="low"),
    ]
    sorted_recs = sorted(recs, key=_record_sort_key)
    assert [r["bucket"] for r in sorted_recs] == [
        "step_13", "step_13a", "step_14"
    ]


def test_plain_description_multiline_truncates_to_first_line():
    r = _rec(bucket="plan_level", impact=["plan.x"],
             description="first line\nsecond line\nthird")
    out = render_plain([r], status_filter="open", total_records=1,
                       open_count=1, resolved_count=0, milestones_scanned=1,
                       unclassified_w613_count=0)
    assert "first line" in out
    assert "second line" not in out
    assert "third" not in out


def test_json_preserves_full_multiline_description():
    r = _rec(bucket="plan_level", description="line1\nline2")
    out = json.loads(render_json(
        [r], total_records=1, open_count=1, resolved_count=0,
        milestones_scanned=1, unclassified_count=0, warnings=[],
    ))
    assert out["records"][0]["description"] == "line1\nline2"


def test_plain_wrap_continuation_prefixed_with_pipe():
    from specdev_tools.analysis.upstream_backlog import _wrap_impact
    # Entries crafted to force a wrap at ~80 chars with indent=11.
    impact = ["a" * 30, "b" * 30, "c" * 30]
    lines = _wrap_impact(impact, indent=11, width=80)
    assert len(lines) >= 2
    assert lines[0].lstrip().startswith("impact: ")
    # First entry on first line; second entry on same line; third wraps.
    for cont in lines[1:]:
        assert cont.lstrip().startswith("| "), f"expected '| ' prefix: {cont!r}"


def test_plain_wrap_single_entry_no_continuation():
    from specdev_tools.analysis.upstream_backlog import _wrap_impact
    lines = _wrap_impact(["short"], indent=11)
    assert lines == ["           impact: short"]


def test_plain_wrap_filters_non_string_entries():
    from specdev_tools.analysis.upstream_backlog import _wrap_impact
    assert _wrap_impact([{"x": 1}, 42, None], indent=11) == []


def test_json_preserves_non_string_impact_entries():
    r = _rec(bucket="unclassified", impact=["plain", 42, {"x": 1}])
    out = json.loads(render_json(
        [r], total_records=1, open_count=1, resolved_count=0,
        milestones_scanned=1, unclassified_count=1, warnings=[],
    ))
    assert out["records"][0]["impact"] == ["plain", 42, {"x": 1}]


def test_json_hidden_by_status_count_defaults_to_zero():
    out = json.loads(render_json(
        [], total_records=0, open_count=0, resolved_count=0,
        milestones_scanned=0, unclassified_count=0, warnings=[],
    ))
    assert out["summary"]["hidden_by_status_count"] == 0


def test_json_hidden_by_status_count_passthrough():
    out = json.loads(render_json(
        [], total_records=0, open_count=0, resolved_count=0,
        milestones_scanned=0, unclassified_count=0, warnings=[],
        hidden_by_status_count=71,
    ))
    assert out["summary"]["hidden_by_status_count"] == 71


def test_json_record_origin_defaults_to_execution_without_origin_key():
    r = _rec(bucket="unclassified")
    out = json.loads(render_json(
        [r], total_records=1, open_count=1, resolved_count=0,
        milestones_scanned=1, unclassified_count=1, warnings=[],
    ))
    assert out["records"][0]["origin"] == "execution"


def test_json_record_origin_plan_passthrough():
    r = _rec(bucket="unclassified", origin="plan", severity="blocking")
    out = json.loads(render_json(
        [r], total_records=1, open_count=1, resolved_count=0,
        milestones_scanned=1, unclassified_count=1, warnings=[],
    ))
    assert out["records"][0]["origin"] == "plan"
