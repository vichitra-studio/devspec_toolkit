"""Loader unit tests: ``load_items`` reads every artifact and reports E520 for items it cannot report."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from specdev_tools.analysis.upstream_backlog import item_problem, load_items
from specdev_tools.core.ambiguity_items import AmbiguityItem, AmbiguityReadError, shape_of


def _write(root: Path, rel: str, doc: object) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc), encoding="utf-8")


def _item(raw: dict, step: str = "16b") -> AmbiguityItem:
    return AmbiguityItem("p.json", step, ".x", raw, shape_of(raw))


def test_anchor_items_are_read(tmp_path):
    _write(tmp_path, "16_impl_context.json", {"plan": {"ambiguities": [{"id": "amb-anchor", "about": ["fr-a"]}]}})
    items, errors = load_items(str(tmp_path))
    assert [(i.id, i.step) for i in items] == [("amb-anchor", "16")]
    assert errors == []


def test_step_files_plans_and_both_plan_arrays_are_read(tmp_path):
    _write(tmp_path, "04_fr_list.json", {"ambiguities": [{"id": "amb-04", "about": ["fr-a"]}]})
    _write(tmp_path, "impl_context/ms_a_plan.json", {
        "plan": {"ambiguities": [{"id": "amb-16a", "about": ["fr-a"]}]},
        "execution": {"emergent_ambiguities": [{"id": "amb-16b", "about": ["fr-a"]}]},
    })
    items, _ = load_items(str(tmp_path))
    assert [(i.id, i.step) for i in items] == [("amb-04", "04"), ("amb-16a", "16a"), ("amb-16b", "16b")]


def test_item_without_id_is_reported_and_skipped(tmp_path):
    _write(tmp_path, "impl_context/ms_a_plan.json", {"execution": {"emergent_ambiguities": [
        {"severity": "low", "impact": []}, {"id": "amb-ok", "about": ["fr-a"]},
    ]}})
    items, errors = load_items(str(tmp_path))
    assert [i.id for i in items] == ["amb-ok"]
    assert len(errors) == 1 and errors[0].startswith("E520 ") and "missing_id" in errors[0]


@pytest.mark.parametrize("raw", [
    {"id": "a", "severity": "LOW"},
    {"id": "a", "severity": "unknown"},
    {"id": "a"},
    {"id": "a", "severity": "blocking"},
])
def test_invalid_legacy_severity_on_the_execution_scale_is_a_problem(raw):
    assert "invalid_severity" in (item_problem(_item(raw)) or "")


@pytest.mark.parametrize("severity, step, ok", [
    ("blocking", "16a", True), ("high", "16a", False), ("high", "16b", True), ("non_blocking", "16b", False),
])
def test_legacy_severity_scale_depends_on_the_array(severity, step, ok):
    assert (item_problem(_item({"id": "a", "severity": severity}, step)) is None) is ok


def test_unified_item_has_no_severity_to_check():
    assert item_problem(_item({"id": "a", "about": ["fr-a"]})) is None


@pytest.mark.parametrize("doc", [{"id": "ms-x", "execution": None}, {"id": "ms-x", "execution": {"emergent_ambiguities": None}}])
def test_null_execution_or_array_yields_nothing(tmp_path, doc):
    _write(tmp_path, "impl_context/ms_a_plan.json", doc)
    assert load_items(str(tmp_path)) == ([], [])


def test_non_object_entry_raises_the_read_error(tmp_path):
    _write(tmp_path, "impl_context/ms_a_plan.json", {"execution": {"emergent_ambiguities": ["not-a-dict"]}})
    with pytest.raises(AmbiguityReadError):
        load_items(str(tmp_path))
