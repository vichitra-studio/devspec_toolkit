"""Render unit tests: plain and JSON (schema_version 2)."""
from __future__ import annotations

import json

from specdev_tools.analysis.upstream_backlog import (
    UNPLACED,
    Placement,
    Record,
    expand,
    group_key,
    render_json,
    render_plain,
    summarise,
)
from specdev_tools.core.ambiguity_items import AmbiguityItem, shape_of
from specdev_tools.graph.model import Graph, SpecShape

_GRAPH = Graph.from_nodes([], shape=SpecShape(step_ranks={"seed": -1, "04": 4, "05": 5}))
_POINTER = {"file": "spec/04_fr_list.json", "id": "fr-a"}


def _record(group: str = "04", step: str = "16b", placement: Placement | None = None, **raw) -> Record:
    raw.setdefault("id", "amb-y")
    item = AmbiguityItem("/s/impl_context/ms_x_plan.json", step, ".x", raw, shape_of(raw))
    return Record(item, "impl_context/ms_x_plan.json", placement or Placement((group,), ("04",), (_POINTER,)), group)


def _plain(records: list[Record]) -> str:
    return render_plain(records, summarise(records), _GRAPH)


def test_totals_line_counts_with_answer_and_needing_answer():
    records = [
        _record(id="a", about=["fr-a"], decision="Use thirty minutes."),
        _record(id="b", about=["fr-a"]),
        _record(id="c", about=["fr-a"]),
    ]
    assert _plain(records).splitlines()[-1] == "Totals: 3 items / 1 with answer / 2 needing answer."


def test_empty_report_is_the_totals_line_only():
    assert _plain([]) == "Totals: 0 items / 0 with answer / 0 needing answer."


def test_item_in_two_groups_counts_once_and_is_marked_also_in():
    placement = Placement(("04", "05"), ("04", "05"), ())
    records = expand(_record(placement=placement, about=["fr-a", "api-b"]))
    out = _plain(records)
    assert out.count("amb-y") == 2
    assert "(also in 04)" in out
    assert out.splitlines()[-1].startswith("Totals: 1 item /")


def test_groups_render_in_group_order_and_unplaced_last():
    records = [_record(UNPLACED, about=["x"], id="u"), _record("05", id="f", about=["y"]), _record("04", id="e", about=["z"])]
    records.sort(key=lambda r: group_key(r.group, _GRAPH))
    out = _plain(records)
    assert out.index("04 - ") < out.index("05 - ") < out.index(f"{UNPLACED} - ")


def test_plain_line_shows_artifact_item_description_about_and_answer_state():
    out = _plain([_record(about=["fr-a", "api-b"], description="first line\nsecond line")])
    assert "impl_context/ms_x_plan.json / amb-y - needs operator answer" in out
    assert "first line" in out and "second line" not in out
    assert "about: fr-a | api-b" in out


def test_plain_flags_a_legacy_item():
    assert "legacy" in _plain([_record(severity="low", status="tracking", impact=["spec/04_x.json"])])


def test_json_v2_record_keys_and_legacy_impact_key():
    unified = _record(id="u", about=["fr-a"], decision="yes")
    legacy = _record(id="l", severity="high", status="tracking", impact=["spec/04_fr_list.json:fr-a", {"file": "f", "id": "i"}])
    data = json.loads(render_json([unified, legacy], summarise([unified, legacy])))
    assert data["schema_version"] == "2"
    base = {"group", "also_in", "artifact", "step", "item_id", "about", "about_steps", "decision", "shape", "description", "impact"}
    u, l = data["records"]
    assert set(u) == base
    assert set(l) == base | {"severity", "status", "bucket", "matched_rule"}
    assert u["impact"] == [_POINTER]
    assert l["impact"] == ["spec/04_fr_list.json:fr-a", {"file": "f", "id": "i"}]
    assert (l["bucket"], l["shape"], u["shape"]) == ("step_04", "legacy", "unified")


def test_json_summary_counts_and_hidden_by_status():
    records = [_record(id="a", about=["x"], decision="d"), _record(UNPLACED, id="b", about=["y"])]
    summary = summarise(records, hidden_by_status=3, warnings=[{"code": "W613", "target": "t"}])
    data = json.loads(render_json(records, summary))
    assert data["summary"] == {"items": 2, "with_answer": 1, "needing_answer": 1, "unplaced_count": 1, "hidden_by_status_count": 3}
    assert data["warnings"] == [{"code": "W613", "target": "t"}]


def test_json_preserves_full_multiline_description():
    data = json.loads(render_json([_record(description="line1\nline2", about=["x"])], summarise([])))
    assert data["records"][0]["description"] == "line1\nline2"
