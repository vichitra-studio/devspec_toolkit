"""Guards for readers of retired 1.1.1 fields (M3 extends the field set and these cases)."""
import json
import shutil
from pathlib import Path
from typing import NamedTuple

import pytest

from specdev_tools.context.reviewer import _run_structural_pass
from specdev_tools.context.scope_resolver import _build_trace_graph
from specdev_tools.core.errors import render_errors
from specdev_tools.core.scope_helpers import is_parked
from specdev_tools.validation._legacy_shim import (
    LEGACY_CHARTER_CHAIN_FIELDS,
    LEGACY_COMPONENT_TRACE_FIELDS,
    LEGACY_CONNECTION_FIELDS,
    LEGACY_PARKED_SCOPES,
    LEGACY_TRACE_FIELDS,
    has_legacy_fields,
    is_parked_any_shape,
)
from specdev_tools.validation.cross_artifact_checks import check_step_02_integrity, check_step_04_integrity
from specdev_tools.validation.matrix import build_trace_matrix
from specdev_tools.validation.traceability_closure import check_traceability_closure

_CLOSURE_CODES = ("E560", "E535", "W564", "W568")

NEW_SHAPE = {
    "01_capabilities.json": {"capabilities": [
        {"capability_id": "cap-a", "verb": "pay", "scope": "in", "derives_from": ["seg-a"]}]},
    "02_system_sketch.json": {"$schema": "vc:02_system_sketch", "components": [
        {"component_id": "comp-a", "type": "service", "derives_from": ["cap-a"]}]},
    "04_fr_list.json": {"$schema": "vc:04_fr_list", "functional_requirements": [
        {"fr_id": "fr-a", "priority": "must-have", "scope": "in", "derives_from": ["cap-a"]}]},
    "05_interface_contracts.json": {"apis": [{"api_id": "api-a", "derives_from": ["fr-a"]}]},
}

LEGACY_SHAPE = {
    "00_charter.json": {"goals": [{"goal_id": "goal-a"}], "success_metrics": []},
    "01_capabilities.json": {"capabilities": [{"capability_id": "cap-a", "scope": "in", "trace": []}]},
    "02_system_sketch.json": {"$schema": "vc:02_system_sketch", "components": [{"component_id": "comp-a"}],
                              "connections": [{"from": "comp-a", "to": "comp-missing"}]},
    "04_fr_list.json": {"$schema": "vc:04_fr_list", "functional_requirements": [
        {"fr_id": "fr-a", "trace": [{"type": "capability", "id": "cap-missing"}]}]},
    "05_interface_contracts.json": {"apis": [
        {"api_id": "api-a", "trace": [{"type": "fr", "id": "fr-a"}]}]},
}


def _write_spec(tmp_path: Path, files: dict) -> str:
    spec_dir = tmp_path / "spec"
    spec_dir.mkdir()
    for name, data in files.items():
        (spec_dir / name).write_text(json.dumps(data), encoding="utf-8")
    return str(spec_dir)


def _closure_codes(spec_dir: str) -> set[str]:
    return {code for e in check_traceability_closure(spec_dir) for code in _CLOSURE_CODES if e.code == code}


_ALL_LEGACY_NAMES = (
    LEGACY_TRACE_FIELDS, LEGACY_CHARTER_CHAIN_FIELDS, LEGACY_CONNECTION_FIELDS, LEGACY_COMPONENT_TRACE_FIELDS,
)


def test_has_legacy_fields_true_for_1_1_1_shape():
    assert has_legacy_fields(LEGACY_SHAPE.values(), LEGACY_TRACE_FIELDS)
    assert has_legacy_fields([LEGACY_SHAPE["00_charter.json"]], LEGACY_CHARTER_CHAIN_FIELDS)
    assert has_legacy_fields([LEGACY_SHAPE["02_system_sketch.json"]["connections"]], LEGACY_CONNECTION_FIELDS)


def test_has_legacy_fields_false_for_new_shape():
    for names in _ALL_LEGACY_NAMES:
        assert not has_legacy_fields(NEW_SHAPE.values(), names)


class _Spec(NamedTuple):
    """A spec folder under test: its root, its ``spec`` directory and the files written into it."""

    root: Path
    spec_dir: str
    files: dict


def _silent_closure(spec):
    assert _closure_codes(spec.spec_dir) == set()


def _silent_matrix_integrity(spec):
    assert "integrity_errors" not in build_trace_matrix(str(spec.root), spec.spec_dir)


def _silent_matrix_fr_to_api(spec):
    matrix = build_trace_matrix(str(spec.root), spec.spec_dir)
    assert all(row["apis"] == [] for row in matrix["matrix"])


def _silent_step_02_integrity(spec):
    arts = {f"spec/{name}": data for name, data in spec.files.items()}
    capability_ids = {c["capability_id"] for c in spec.files["01_capabilities.json"]["capabilities"]}
    assert check_step_02_integrity(arts, capability_ids=capability_ids) == []


def _silent_step_04_integrity(spec):
    arts = {f"spec/{name}": data for name, data in spec.files.items()}
    capability_ids = {c["capability_id"] for c in spec.files["01_capabilities.json"]["capabilities"]}
    assert check_step_04_integrity(arts, set(), capability_ids) == []


def _silent_scope_resolver(spec):
    _, adjacency = _build_trace_graph(spec.spec_dir)
    assert not any(adjacency[fr["fr_id"]] for fr in spec.files["04_fr_list.json"]["functional_requirements"])


def _silent_reviewer(spec):
    review = _run_structural_pass(
        spec.files["05_interface_contracts.json"], "", [("", spec.files["04_fr_list.json"])]
    )
    assert review.upstream_coverage["covered"] == []


SILENT_READERS = {
    "closure": _silent_closure,
    "matrix_integrity": _silent_matrix_integrity,
    "matrix_fr_to_api": _silent_matrix_fr_to_api,
    "step_02_integrity": _silent_step_02_integrity,
    "step_04_integrity": _silent_step_04_integrity,
    "scope_resolver": _silent_scope_resolver,
    "reviewer": _silent_reviewer,
}


@pytest.mark.parametrize("reader", sorted(SILENT_READERS))
def test_guarded_reader_silent_on_new_shape(tmp_path, reader):
    spec_dir = _write_spec(tmp_path, NEW_SHAPE)
    SILENT_READERS[reader](_Spec(tmp_path, spec_dir, NEW_SHAPE))


@pytest.mark.parametrize("reader", sorted(SILENT_READERS))
def test_guarded_reader_silent_on_graph_example(reader):
    example = Path(__file__).parents[2] / "fixtures" / "graph_example"
    spec_dir = example / "spec"
    files = {
        name: json.loads((spec_dir / name).read_text(encoding="utf-8"))
        for name in NEW_SHAPE
    }
    SILENT_READERS[reader](_Spec(example, str(spec_dir), files))


def test_guarded_readers_unchanged_on_legacy_shape(tmp_path):
    spec_dir = _write_spec(tmp_path, LEGACY_SHAPE)
    arts = {f"spec/{name}": data for name, data in LEGACY_SHAPE.items()}

    assert {"E560", "W568"} <= _closure_codes(spec_dir)
    matrix = build_trace_matrix(str(tmp_path), spec_dir)
    assert matrix["matrix"][0]["apis"] == ["api-a"]
    assert any("not found" in line for line in render_errors(check_step_02_integrity(arts, capability_ids=set())))
    assert any("unknown capability" in line for line in render_errors(check_step_04_integrity(arts, set(), {"cap-a"})))
    _, adjacency = _build_trace_graph(spec_dir)
    assert "cap-missing" in adjacency["fr-a"]
    review = _run_structural_pass(LEGACY_SHAPE["05_interface_contracts.json"], "", [("", {"fr_id": "fr-a"})])
    assert review.upstream_coverage["covered"] == ["fr-a"]


@pytest.mark.parametrize(("node", "expected"), [
    ({"scope": "later"}, True),
    ({"scope": "out"}, True),
    ({"scope": "in"}, False),
    ({"priority": "wont-have"}, True),
    ({"capability_id": "cap-a"}, False),
])
def test_is_parked_contract(node, expected):
    assert is_parked(node) is expected


# --- per-reader guards: a legacy file of a later step never switches a 00-05 reader on -----------

EXAMPLE_SPEC = Path(__file__).parents[2] / "fixtures" / "graph_example" / "spec"
TOOLKIT_ROOT = Path(__file__).parents[3]
LEGACY_LATER_FILES = {
    "09_impl_plan.json": {"tasks": [{"id": "x", "trace": [{"type": "fr", "id": "fr-x"}]}]},
    "14_roadmap.json": {"milestones": [{"milestone_id": "m1", "trace": [{"type": "fr", "id": "x"}]}], "trace": []},
}


def _example_copy(tmp_path: Path, extra: dict | None = None) -> str:
    spec_dir = tmp_path / "spec"
    spec_dir.mkdir(parents=True)
    for path in EXAMPLE_SPEC.glob("*.json"):
        shutil.copy(path, spec_dir / path.name)
    for name, data in (extra or {}).items():
        (spec_dir / name).write_text(json.dumps(data), encoding="utf-8")
    return str(spec_dir)


@pytest.mark.parametrize("name", sorted(LEGACY_LATER_FILES))
def test_legacy_later_file_does_not_switch_on_00_05_readers(tmp_path, name):
    plain = _example_copy(tmp_path / "plain")
    mixed = _example_copy(tmp_path / "mixed", {name: LEGACY_LATER_FILES[name]})

    assert _closure_codes(mixed) == _closure_codes(plain) == set()
    plain_matrix = build_trace_matrix(str(TOOLKIT_ROOT), plain)
    mixed_matrix = build_trace_matrix(str(TOOLKIT_ROOT), mixed)
    assert mixed_matrix["coverage"] == plain_matrix["coverage"]
    # The only integrity line is the added file's own dangling reference. The old tree also
    # reported a W592 fr_coverage warning here, in the plain and in the mixed spec.
    assert "integrity_errors" not in plain_matrix
    assert len(mixed_matrix["integrity_errors"]) == 1
    assert mixed_matrix["integrity_errors"][0].startswith("E590 ")


def test_matrix_reports_no_fr_to_api_threshold_on_new_shape():
    result = build_trace_matrix(str(TOOLKIT_ROOT), str(EXAMPLE_SPEC))
    assert result["coverage"]["fr_total"] > 0
    assert not any("fr_coverage" in line for line in result.get("integrity_errors", []))


def _threshold_repo(tmp_path: Path, mode: str) -> str:
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "step_order.json").write_text(
        json.dumps({"coverage_thresholds": {"fr_coverage": 80, "mode": mode}}), encoding="utf-8")
    return str(tmp_path)


def test_matrix_threshold_unchanged_on_legacy_shape(tmp_path):
    files = {
        "04_fr_list.json": {"$schema": "vc:04_fr_list", "functional_requirements": [
            {"fr_id": "fr-a", "trace": []}, {"fr_id": "fr-b", "trace": []}]},
        "05_interface_contracts.json": {"apis": [{"api_id": "api-a", "trace": [{"type": "fr", "id": "fr-a"}]}]},
    }
    root = tmp_path / "repo"
    root.mkdir()
    spec_dir = _write_spec(root, files)
    result = build_trace_matrix(_threshold_repo(root, "error"), spec_dir)
    assert any("E592" in line and "fr_coverage=50.0%" in line for line in result["integrity_errors"])


def test_matrix_threshold_reported_when_there_is_no_05_file(tmp_path):
    """No API artifact at all: FR-to-API coverage is 0 by definition, as on main."""
    files = {"04_fr_list.json": {"$schema": "vc:04_fr_list", "functional_requirements": [
        {"fr_id": "fr-a", "derives_from": ["cap-a"]}]}}
    root = tmp_path / "repo"
    root.mkdir()
    spec_dir = _write_spec(root, files)
    result = build_trace_matrix(_threshold_repo(root, "warn"), spec_dir)
    assert any("W592" in line and "fr_coverage=0.0%" in line for line in result["integrity_errors"])


def test_matrix_threshold_silent_when_apis_exist_and_none_carries_trace(tmp_path):
    files = {
        "04_fr_list.json": {"$schema": "vc:04_fr_list", "functional_requirements": [
            {"fr_id": "fr-a", "derives_from": ["cap-a"]}]},
        "05_interface_contracts.json": {"apis": [{"api_id": "api-a", "derives_from": ["fr-a"]}]},
    }
    root = tmp_path / "repo"
    root.mkdir()
    spec_dir = _write_spec(root, files)
    result = build_trace_matrix(_threshold_repo(root, "warn"), spec_dir)
    assert not any("fr_coverage" in line for line in result.get("integrity_errors", []))


def test_new_shape_scope_later_fr_is_parked_in_matrix_and_closure(tmp_path):
    files = {
        "04_fr_list.json": {"$schema": "vc:04_fr_list", "functional_requirements": [
            {"fr_id": "fr-a", "priority": "must-have", "scope": "in", "derives_from": ["cap-a"]},
            {"fr_id": "fr-later", "priority": "must-have", "scope": "later", "derives_from": ["cap-a"]}]},
        "14_roadmap.json": {"milestones": [{"milestone_id": "m1", "fr_refs": [], "tasks": []}]},
    }
    spec_dir = _write_spec(tmp_path, files)
    messages = [e.message for e in check_traceability_closure(spec_dir)]
    assert any("UNCOVERED_FR_MILESTONE fr-a" in m for m in messages)
    assert not any("fr-later" in m for m in messages)
    assert build_trace_matrix(str(tmp_path), spec_dir)["coverage"]["fr_total"] == 1


# --- one spelling of "parked" for the readers that can meet either shape ------------------------

@pytest.mark.parametrize(("node", "expected"), [
    ({"scope": "later"}, True),
    ({"scope": "out"}, True),
    ({"scope": "future"}, True),
    ({"scope": "in"}, False),
    ({"priority": "wont-have"}, True),
    ({"capability_id": "cap-a"}, False),
])
def test_is_parked_any_shape_contract(node, expected):
    assert is_parked_any_shape(node) is expected


def test_legacy_parked_scopes_is_the_1_1_1_value():
    assert LEGACY_PARKED_SCOPES == frozenset({"future"})
    assert not is_parked({"scope": "future"})  # the shared helper stays new-shape only


def _w568_ids(tmp_path: Path, capabilities: list[dict]) -> set[str]:
    """W568 messages of a spec whose FR file is legacy (switches the reader on)."""
    spec_dir = _write_spec(tmp_path, {
        "01_capabilities.json": {"capabilities": capabilities},
        "04_fr_list.json": LEGACY_SHAPE["04_fr_list.json"],
    })
    return {e.message for e in check_traceability_closure(spec_dir) if e.code == "W568"}


@pytest.mark.parametrize("scope", ["later", "out", "future"])
def test_w568_exempts_parked_capability_of_either_shape(tmp_path, scope):
    # legacy FR file + a capability file already in the new shape (scope later) or the old one
    messages = _w568_ids(tmp_path, [{"capability_id": "cap-parked", "scope": scope}])
    assert not any("cap-parked" in m for m in messages), messages


def test_w568_still_reports_an_uncovered_in_scope_capability(tmp_path):
    messages = _w568_ids(tmp_path, [{"capability_id": "cap-live", "scope": "in"}])
    assert any("cap-live" in m for m in messages), messages
