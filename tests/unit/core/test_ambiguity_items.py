"""Tests for the shared ambiguity-item reader (WI-M6a-05)."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from specdev_tools.core.ambiguity_items import (
    LOCATIONS,
    PLAN_FILE_GLOB,
    PLAN_FILE_RE,
    PLAN_ITEM_STEPS,
    AmbiguityItem,
    AmbiguityReadError,
    about_targets,
    iter_ambiguity_items,
    is_open,
    shape_of,
)

from .._ambiguity_support import unified_item
from ..graph._synth import write_json

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKLOG_FIXTURES = REPO_ROOT / "tests" / "fixtures" / "analysis" / "upstream_backlog"
EXAMPLE_SPEC = REPO_ROOT / "tests" / "fixtures" / "graph_example" / "spec"
REGISTRY_FILE = REPO_ROOT / "tools" / "entry_key_registry.json"
KIND = "ambiguity-item"
PLAN_KEY = "impl_context/ms_*_plan.json"


def _registry_locations() -> set[tuple[str, str, bool]]:
    """(step, array path, in a plan file) of every ``ambiguity-item`` array of the registry."""
    registry = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))["registry"]
    found = set()
    for file_key, entry in registry.items():
        for array in entry["arrays"]:
            if array["kind"] != KIND:
                continue
            if file_key == PLAN_KEY:
                step = "16a" if array["array_path"] == ".plan.ambiguities" else "16b"
                found.add((step, array["array_path"], True))
            else:
                found.add((file_key.split("_", 1)[0], array["array_path"], False))
    return found


def _item_for_every_location(spec: Path) -> None:
    for step in sorted({loc.step for loc in LOCATIONS if not loc.in_plan_file and loc.step != "16"}):
        write_json(spec, f"{step}_x.json", {"ambiguities": [unified_item(f"amb-{step}")]})
    write_json(spec, "16_impl_context.json", {"plan": {"ambiguities": [unified_item("amb-anchor")]}})
    write_json(
        spec, "impl_context/ms_a_plan.json",
        {"plan": {"ambiguities": [unified_item("amb-16a")]}, "execution": {"emergent_ambiguities": [unified_item("amb-16b")]}},
    )


def test_registry_locations_equal_the_reader_list() -> None:
    assert {(loc.step, loc.array_path, loc.in_plan_file) for loc in LOCATIONS} == _registry_locations()
    assert len(LOCATIONS) == 20


def test_item_in_each_registry_location_is_read(tmp_path: Path) -> None:
    _item_for_every_location(tmp_path)
    items = list(iter_ambiguity_items(str(tmp_path)))
    assert {(i.step, i.location) for i in items} == {(loc.step, loc.array_path) for loc in LOCATIONS}
    assert len(items) == 20
    assert all(i.shape == "unified" and is_open(i) for i in items)


def test_anchor_items_are_read(tmp_path: Path) -> None:
    write_json(tmp_path, "16_impl_context.json", {"plan": {"ambiguities": [unified_item("amb-anchor")]}})
    (item,) = iter_ambiguity_items(str(tmp_path))
    assert (item.step, item.id, item.location) == ("16", "amb-anchor", ".plan.ambiguities")
    assert item.artifact_path.endswith("16_impl_context.json")


def test_legacy_fixture_with_six_ambiguities_reads_as_legacy_shape(tmp_path: Path) -> None:
    fixture = json.loads((BACKLOG_FIXTURES / "plan_with_six_ambiguities.json").read_text(encoding="utf-8"))
    write_json(tmp_path, "impl_context/ms_six_plan.json", fixture)
    items = list(iter_ambiguity_items(str(tmp_path)))
    assert len(items) == 6
    assert {i.shape for i in items} == {"legacy"}
    assert {i.step for i in items} == {"16b"}


def test_dual_origin_fixture_reads_both_plan_arrays(tmp_path: Path) -> None:
    fixture = json.loads((BACKLOG_FIXTURES / "plan_with_dual_origin_ambiguities.json").read_text(encoding="utf-8"))
    write_json(tmp_path, "impl_context/ms_dual_plan.json", fixture)
    items = list(iter_ambiguity_items(str(tmp_path)))
    assert [(i.step, i.id) for i in items] == [
        ("16a", "amb-16a-open-blocking"),
        ("16a", "amb-16a-resolved-non-blocking"),
        ("16b", "amb-16b-open-high"),
        ("16b", "amb-16c-resolved-critical"),
    ]


def test_resolved_legacy_items_are_not_open(tmp_path: Path) -> None:
    fixture = json.loads((BACKLOG_FIXTURES / "plan_with_dual_origin_ambiguities.json").read_text(encoding="utf-8"))
    write_json(tmp_path, "impl_context/ms_dual_plan.json", fixture)
    open_ids = [i.id for i in iter_ambiguity_items(str(tmp_path)) if is_open(i)]
    assert open_ids == ["amb-16a-open-blocking", "amb-16b-open-high"]


def test_unified_item_without_status_is_open() -> None:
    raw = unified_item("amb-x")
    assert "status" not in raw
    item = AmbiguityItem("spec/05_x.json", "05", ".ambiguities", raw, shape_of(raw))
    assert item.shape == "unified" and is_open(item)


def test_unified_item_stays_open_whatever_a_stray_status_says() -> None:
    raw = unified_item("amb-x", status="resolved")
    assert is_open(AmbiguityItem("spec/05_x.json", "05", ".ambiguities", raw, shape_of(raw)))


@pytest.mark.parametrize(
    ("raw", "shape"),
    [
        (unified_item("a"), "unified"),
        (unified_item("a", severity="low"), "legacy"),
        ({"id": "a", "description": "d", "impact": ["x"]}, "legacy"),
    ],
)
def test_shape_of(raw: dict, shape: str) -> None:
    assert shape_of(raw) == shape


def _about(raw: dict) -> tuple:
    return about_targets(AmbiguityItem("spec/05_x.json", "05", ".ambiguities", raw, shape_of(raw)))


def test_about_targets_returns_the_about_ids() -> None:
    assert _about(unified_item("a", about=["fr-login", "seed-accounts"])) == ("fr-login", "seed-accounts")


def test_about_targets_returns_the_silent_form_for_a_missing_kind() -> None:
    targets = _about(unified_item("a", about=["cap-auth", "cap-other"], missing_kind="fr"))
    assert targets == (("silent", "fr", "cap-auth"),)


def test_about_targets_of_a_legacy_item_is_empty() -> None:
    assert _about({"id": "a", "description": "d", "severity": "low", "impact": ["x"]}) == ()


def test_example_spec_has_no_items_and_is_read_without_error() -> None:
    assert list(iter_ambiguity_items(str(EXAMPLE_SPEC))) == []


def test_spec_folder_without_any_ambiguity_item_yields_nothing(tmp_path: Path) -> None:
    write_json(tmp_path, "05_x.json", {"id": "x"})
    write_json(tmp_path, "impl_context/ms_a_plan.json", {"plan": {}, "execution": {}})
    assert list(iter_ambiguity_items(str(tmp_path))) == []
    assert list(iter_ambiguity_items(str(tmp_path / "missing"))) == []


def test_files_outside_the_locations_are_not_read(tmp_path: Path) -> None:
    doc = {"ambiguities": [unified_item("amb-x")]}
    write_json(tmp_path, "16a_x.json", doc)
    write_json(tmp_path, "extras/05_x.json", doc)
    write_json(tmp_path, "impl_context/notes.json", doc)
    write_json(tmp_path, "impl_context/nested/ms_a_plan.json", doc)
    assert list(iter_ambiguity_items(str(tmp_path))) == []


@pytest.mark.parametrize(
    "doc",
    [{"ambiguities": "text"}, {"ambiguities": ["not-an-object"]}],
)
def test_malformed_array_raises(tmp_path: Path, doc: dict) -> None:
    write_json(tmp_path, "05_x.json", doc)
    with pytest.raises(AmbiguityReadError):
        list(iter_ambiguity_items(str(tmp_path)))


def test_unreadable_json_raises_with_the_path(tmp_path: Path) -> None:
    (tmp_path / "05_x.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(AmbiguityReadError) as err:
        list(iter_ambiguity_items(str(tmp_path)))
    assert err.value.path.endswith("05_x.json")


requires_unprivileged = pytest.mark.skipif(os.geteuid() == 0, reason="root can read a file of mode 000")


@requires_unprivileged
def test_a_file_that_cannot_be_opened_is_a_read_error_naming_the_reason(tmp_path: Path) -> None:
    path = tmp_path / "04_fr_list.json"
    write_json(tmp_path, "04_fr_list.json", {"ambiguities": []})
    path.chmod(0)
    try:
        with pytest.raises(AmbiguityReadError) as caught:
            list(iter_ambiguity_items(str(tmp_path)))
    finally:
        path.chmod(0o644)
    assert caught.value.path == str(path) and "Permission denied" in caught.value.reason


def test_a_folder_named_like_a_step_file_is_a_read_error(tmp_path: Path) -> None:
    (tmp_path / "04_x.json").mkdir()
    with pytest.raises(AmbiguityReadError) as caught:
        list(iter_ambiguity_items(str(tmp_path)))
    assert caught.value.path == str(tmp_path / "04_x.json") and "directory" in caught.value.reason.lower()


def test_a_plan_file_that_is_a_folder_is_a_read_error(tmp_path: Path) -> None:
    (tmp_path / "impl_context" / "ms_a_plan.json").mkdir(parents=True)
    with pytest.raises(AmbiguityReadError):
        list(iter_ambiguity_items(str(tmp_path)))


def test_the_item_gives_description_decision_and_about_ids_as_typed_values(tmp_path: Path) -> None:
    write_json(tmp_path, "05_x.json", {"ambiguities": [
        unified_item("amb-a", decision="  use the seed  ", about=["fr-a", 7, "fr-b"]),
        {"id": "amb-b", "about": "fr-a", "decision": "   ", "description": 5},
        {"id": "amb-c", "severity": "low", "impact": []},
    ]})
    first, second, legacy = iter_ambiguity_items(str(tmp_path))
    assert (first.description, first.decision, first.about_ids) == ("what is unclear", "  use the seed  ", ("fr-a", "fr-b"))
    assert (second.description, second.decision, second.about_ids) == ("", None, ())
    assert (legacy.decision, legacy.about_ids) == (None, ())


def test_the_plan_constants_are_derived_from_one_another() -> None:
    assert PLAN_FILE_GLOB == "ms_*_plan.json"
    assert all(PLAN_FILE_RE.match(name) for name in ("ms_a_plan.json", "ms_1-b_plan.json"))
    assert not any(PLAN_FILE_RE.match(name) for name in ("ms_a_plan.json.bak", "x_ms_a_plan.json", "ms_a_plan.jsonx", "notes.json"))
    assert PLAN_ITEM_STEPS == {loc.step for loc in LOCATIONS if loc.in_plan_file} == {"16a", "16b"}
