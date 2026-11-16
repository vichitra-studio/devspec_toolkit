"""Guards for readers of retired 1.1.1 fields (M3 extends the field set and these cases)."""
import ast
import io
import json
import re
import shutil
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import NamedTuple
from unittest import mock

import pytest

from specdev_tools import cli
from specdev_tools.validation.forward_replay_check import _prune_removed_paths, check_forward_replay
from specdev_tools.validation.validators.step_14 import validate_step_14

from specdev_tools.analysis.upstream_backlog import run as run_upstream_backlog
from specdev_tools.context.reviewer import _compute_verdict, _run_structural_pass
from specdev_tools.context.scope_resolver import _build_trace_graph, resolve_scope
from specdev_tools.core.errors import render_errors
from specdev_tools.core.scope_helpers import is_parked
from specdev_tools.validation._legacy_shim import (
    LEGACY_CAPABILITY_GOAL_FIELDS,
    LEGACY_CAPABILITY_METRIC_FIELDS,
    LEGACY_CHARTER_GOAL_FIELDS,
    LEGACY_COMPONENT_TRACE_FIELDS,
    LEGACY_PARKED_SCOPES,
    LEGACY_TRACE_FIELDS,
    has_legacy_fields,
    is_parked_any_shape,
    out_of_scope_fr_ids,
    fr_api_reader_on,
    fr_fixture_reader_on,
    fr_milestone_reader_on,
    reader_on,
    records_of,
    removed_paths,
)
from specdev_tools.validation.seed_lint import lint_seeds
from specdev_tools.validation.validate import validate_file
from specdev_tools.validation.cross_artifact_checks import check_step_02_integrity, check_step_04_integrity
from specdev_tools.validation.matrix import build_trace_matrix
from specdev_tools.validation.traceability_closure import check_traceability_closure, uncomputed_dimensions
from specdev_tools.validation.validators.step_11 import _load_parked_fr_ids

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
    LEGACY_TRACE_FIELDS, LEGACY_CHARTER_GOAL_FIELDS, LEGACY_CAPABILITY_GOAL_FIELDS,
    LEGACY_CAPABILITY_METRIC_FIELDS, LEGACY_COMPONENT_TRACE_FIELDS,
)


def test_records_of_a_1_1_1_shape_carry_the_legacy_fields():
    assert has_legacy_fields(records_of(LEGACY_SHAPE["05_interface_contracts.json"]), LEGACY_TRACE_FIELDS)
    assert has_legacy_fields(records_of(LEGACY_SHAPE["00_charter.json"]), LEGACY_CHARTER_GOAL_FIELDS)
    assert has_legacy_fields(records_of(LEGACY_SHAPE["01_capabilities.json"]), LEGACY_CAPABILITY_GOAL_FIELDS)
    assert has_legacy_fields(records_of(_CAPABILITIES_1_1_1), LEGACY_CAPABILITY_METRIC_FIELDS)
    assert has_legacy_fields([{"component_id": "comp-a", "trace": []}], LEGACY_COMPONENT_TRACE_FIELDS)
    assert has_legacy_fields([{"component_id": "comp-a", "trace_refs": []}], LEGACY_COMPONENT_TRACE_FIELDS)


def test_records_of_a_new_shape_carry_no_legacy_field():
    for names in _ALL_LEGACY_NAMES:
        assert not any(has_legacy_fields(records_of(artifact), names) for artifact in NEW_SHAPE.values())


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
    assert all("apis" not in row for row in matrix["matrix"])
    assert "fr_with_api" not in matrix["coverage"]
    assert matrix["not_computed"][:2] == ["fr_with_api", "apis"]


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

    assert {"E560", "W568"} <= _closure_codes(spec_dir), "traceability_closure reader (E560/W568)"
    matrix = build_trace_matrix(str(tmp_path), spec_dir)
    assert matrix["matrix"][0]["apis"] == ["api-a"], "matrix reader"
    assert any(
        "not found" in line for line in render_errors(check_step_02_integrity(arts, capability_ids=set()))
    ), "check_step_02_integrity reader"
    assert any(
        "unknown capability" in line for line in render_errors(check_step_04_integrity(arts, set(), {"cap-a"}))
    ), "check_step_04_integrity reader"
    _, adjacency = _build_trace_graph(spec_dir)
    assert "cap-missing" in adjacency["fr-a"], "scope_resolver _build_trace_graph reader"
    review = _run_structural_pass(LEGACY_SHAPE["05_interface_contracts.json"], "", [("", {"fr_id": "fr-a"})])
    assert review.upstream_coverage["covered"] == ["fr-a"], "reviewer _run_structural_pass reader"


_CHARTER_METRIC = {"metric_id": "metric-a"}
_CHARTER_1_1_1 = {"goals": [{"goal_id": "goal-a"}], "success_metrics": [_CHARTER_METRIC]}
_CHARTER_1_2_0 = {"goals": [{"id": "goal-a"}], "success_metrics": [_CHARTER_METRIC]}
_CAPABILITIES_1_1_1 = {"capabilities": [{"capability_id": "cap-a", "scope": "in", "trace": [], "success_metric_refs": []}]}
_CAPABILITIES_1_1_1_TRACE_ONLY = {"capabilities": [{"capability_id": "cap-a", "scope": "in", "trace": []}]}
_CAPABILITIES_1_2_0 = {"capabilities": [{"capability_id": "cap-a", "scope": "in", "derives_from": ["goal-a"]}]}


@pytest.mark.parametrize(("charter", "capabilities", "reports"), [
    (_CHARTER_1_1_1, _CAPABILITIES_1_1_1, True),
    (_CHARTER_1_2_0, _CAPABILITIES_1_2_0, False),
    (_CHARTER_1_1_1, _CAPABILITIES_1_2_0, False),
    (_CHARTER_1_2_0, _CAPABILITIES_1_1_1_TRACE_ONLY, False),
], ids=["both-1.1.1", "both-1.2.0", "charter-only-1.1.1", "capabilities-only-1.1.1"])
def test_e560_goal_half_runs_only_when_both_sides_carry_the_1_1_1_fields(tmp_path, charter, capabilities, reports):
    spec_dir = _write_spec(tmp_path, {"00_charter.json": charter, "01_capabilities.json": capabilities})
    goal_findings = [e for e in render_errors(check_traceability_closure(spec_dir)) if "charter_goal_without_capability" in e]
    assert bool(goal_findings) is reports


def test_e560_metric_half_reports_for_1_1_1_capabilities_with_trace_and_no_metric_refs(tmp_path):
    """A 1.1.1 capability carries `trace`; `success_metric_refs` is optional, so the charter metrics still need a capability."""
    charter = {"goals": [{"goal_id": "goal-a"}], "success_metrics": [{"metric_id": "metric-a"}, {"metric_id": "metric-b"}]}
    spec_dir = _write_spec(tmp_path, {"00_charter.json": charter, "01_capabilities.json": _CAPABILITIES_1_1_1_TRACE_ONLY})
    rendered = render_errors(check_traceability_closure(spec_dir))
    assert [e for e in rendered if "charter_success_metric_without_capability" in e and ("metric-a" in e or "metric-b" in e)]
    assert len([e for e in rendered if "charter_success_metric_without_capability" in e]) == 2


def test_reader_on_is_the_one_rule_of_the_guards():
    assert reader_on([], {"trace"}) is True
    assert reader_on([], {"trace"}, when_empty=False) is False
    assert reader_on([{"id": 1}], {"trace"}) is False
    assert reader_on([{"trace": []}], {"trace"}) is True
    assert reader_on(iter([{"trace": []}]), {"trace"}) is True  # any iterable of records


def test_has_legacy_fields_reads_keys_of_records_and_does_not_descend():
    assert has_legacy_fields([{"trace": []}], {"trace"})
    assert not has_legacy_fields([{"input": {"trace": [1]}, "expected": [{"targets": 1}]}], {"trace", "targets"})
    assert not has_legacy_fields([7, "trace", None, ["trace"]], {"trace"})


def test_records_of_is_the_file_and_the_objects_of_its_top_level_arrays():
    artifact = {"a": [{"x": 1}, 5, [{"y": 2}]], "b": {"c": [{"z": 3}]}, "d": "s"}
    assert records_of(artifact) == [artifact, {"x": 1}]
    assert records_of([1]) == records_of(None) == records_of("x") == []


def test_the_three_shared_decisions_use_the_one_empty_rule():
    for decide in (fr_api_reader_on, fr_milestone_reader_on, fr_fixture_reader_on):
        assert decide([]) is True
        assert decide([{"x": 1}]) is False
    assert fr_api_reader_on([{"trace": []}]) and fr_milestone_reader_on([{"fr_refs": []}])
    assert fr_fixture_reader_on([{"targets": []}]) and fr_fixture_reader_on([{"x": 1}], [{"out_of_scope": []}])
    assert not fr_fixture_reader_on([{"x": 1}], [{"fixtures": []}])


@pytest.mark.parametrize(("node", "expected"), [
    ({"scope": "later"}, True),
    ({"scope": "out"}, True),
    ({"scope": "in"}, False),
    ({"priority": "wont-have"}, False),
    ({"capability_id": "cap-a"}, False),
    ({"scope": ["in"]}, False),
    ({"scope": {}}, False),
    ({"scope": 7, "priority": ["wont-have"]}, False),
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
    ({"scope": ["future"]}, False),
    ({"scope": {}}, False),
    ({"scope": 7, "priority": ["wont-have"]}, False),
    ({"priority": ["wont-have"]}, False),
])
def test_is_parked_any_shape_contract(node, expected):
    assert is_parked_any_shape(node) is expected


def test_legacy_parked_scopes_is_the_1_1_1_value():
    assert LEGACY_PARKED_SCOPES == frozenset({"future"})
    assert not is_parked({"scope": "future"})  # the shared helper stays new-shape only


def test_legacy_shape_fixtures_keep_priority_wont_have_and_stay_green(tmp_path):
    # A legacy FR parked by `priority: wont-have` stays out of every FR denominator of the readers
    # that can meet a 1.1.1 file: closure, matrix, the step-11 sibling loader and the CLI.
    files = {
        "04_fr_list.json": {"$schema": "vc:04_fr_list", "functional_requirements": [
            {"fr_id": "fr-a", "priority": "must-have", "trace": []},
            {"fr_id": "fr-legacy-export", "priority": "wont-have", "trace": []}]},
        "14_roadmap.json": {"milestones": [{"milestone_id": "m1", "fr_refs": [], "tasks": []}]},
    }
    spec_dir = _write_spec(tmp_path, files)
    messages = [e.message for e in check_traceability_closure(spec_dir)]
    assert any("UNCOVERED_FR_MILESTONE fr-a" in m for m in messages)
    assert not any("fr-legacy-export" in m for m in messages)
    assert build_trace_matrix(str(tmp_path), spec_dir)["coverage"]["fr_total"] == 1
    artifact = str(Path(spec_dir) / "11_adversarial.json")
    assert _load_parked_fr_ids(str(tmp_path), artifact) == {"fr-legacy-export"}


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


# --- readers of steps 06-16 on a new-shape spec (WI-M3-17a) -------------------------------------

_ISO = "2025-01-01T00:00:00Z"


def _doc(schema: str, doc_id: str, **body) -> dict:
    return {"$schema": f"vc:{schema}", "id": doc_id, "owner": "api", "created_at": _ISO, **body,
            "canonical_refs_used": []}


# New-shape documents of steps 06-16, modelled on the valid fixtures under tests/fixtures/step_06..16.
NEW_SHAPE_06_16 = {
    "06_invariants.json": _doc("06-invariants", "invariants", rules=[{
        "inv_id": "invariant-token-single-use", "description": "A reset token redeems once.", "language": "cel",
        "expression": "token.uses <= 1", "constrains": ["fr-password-reset"], "severity": "error"}]),
    "07_nfrs.json": _doc("07-nfrs", "nfrs", nfrs=[{
        "nfr_id": "nfr-latency-p95", "category": "latency", "metric": "p95", "target": 200, "unit": "ms",
        "measurement_method": "PromQL", "stage": "prod", "owner": "api", "constrains": ["fr-password-reset"]}]),
    "08_fixtures.json": _doc("08-fixtures", "fixtures", fixtures=[{
        "fixture_id": "fixture-reset-ok", "description": "Reset succeeds", "verifies": ["api-password-reset-confirm"],
        "mode": "contract", "input": {}, "expected": {"status": 200}}]),
    "09_impl_plan.json": _doc("09-impl-plan", "impl-plan", milestones=[{
        "milestone_id": "milestone-reset", "name": "Reset", "target_date": "2025-11-15", "risks": [], "spikes": [],
        "schedules": ["fr-password-reset"]}]),
    "10_governance.json": _doc("10-governance", "governance", versioning="semver", rules=[{
        "rule_id": "rule-spec-check", "text": "Every pull request passes the spec merge check.",
        "derives_from": ["fr-password-reset"], "cli_command": "spec-check"}]),
    "11_redteam.json": _doc("11-redteam", "redteam", edge_cases=[], threats=[{
        "threat_id": "threat-token-guess", "description": "Guessing a reset token", "vector": "guess",
        "category": "authn", "severity": "high", "threatens": ["api-password-reset-confirm"],
        "mitigated_by": ["invariant-token-single-use"]}]),
    "12_ci_gates.json": _doc("12-ci-gates", "ci", jobs=[{
        "job_id": "test", "name": "Test", "steps": [{"name": "t", "command": "npm test"}],
        "verifies": ["nfr-latency-p95"]}]),
    "14_roadmap.json": _doc("14-roadmap", "roadmap", milestones=[{
        "milestone_id": "m1", "name": "Core", "target_date": "2025-02-01", "risk_status": "low",
        "user_story": "As a member, I reset my password.", "risks": [], "spikes": [], "tasks": [{
            "task_id": "t1", "description": "Build reset", "acceptance_criteria": [{
                "criterion_id": "c1", "text": "Reset works.", "refines": ["ac-password-reset-1"]}]}]}]),
    "15_scaffold.json": _doc("15-scaffold", "scaffold", project_skeleton={"language": "python"},
                             validators=["spec-validate"], build_status="green", interface_map=[{
                                 "row_id": "scaffold-confirm", "realises": ["api-password-reset-confirm"],
                                 "path": "src/confirm.py"}]),
    "16_impl_context.json": _doc("16-anchor", "anchor", artifact_role="anchor", plan={
        "summary": {"functional_summary": "Reset.", "scope_in": ["reset"], "scope_out": []},
        "ambiguities": [], "drift": {"checks": []},
        "milestone_index": [{"anchor_id": "anchor-m1", "about": ["m1"], "status": "in_progress",
                             "checklist_id_prefix": "M1", "summary": "m1"}]}),
}


def _graph_spec(root: Path, extra: dict | None = None) -> str:
    """A new-shape spec: the graph example (00-05) plus the inline 06-16 documents."""
    spec_dir = _example_copy(root, {**NEW_SHAPE_06_16, **(extra or {})})
    return spec_dir


def _run_cli(argv: list[str]) -> tuple[int, str]:
    out, err = io.StringIO(), io.StringIO()
    with mock.patch("specdev_tools.cli.check_venv", return_value=None), \
            mock.patch.object(sys, "argv", ["specdev-tools", *argv]), \
            redirect_stdout(out), redirect_stderr(err):
        try:
            cli.main()
            code = 0
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else 1
    return code, out.getvalue()


def test_matrix_silent_on_new_shape_06_16(tmp_path):
    result = build_trace_matrix(str(TOOLKIT_ROOT), _graph_spec(tmp_path))
    assert "integrity_errors" not in result
    assert "milestone_coverage" not in result
    assert "invariant_threat_coverage" not in result
    assert result["not_computed"] == [
        "fr_with_api", "apis", "fr_with_fixture", "fixtures", "fr_with_nfr", "nfrs", "fr_with_threat", "threats",
        "milestone_coverage", "invariant_threat_coverage",
    ]
    assert all(set(row) == {"fr_id"} for row in result["matrix"])
    assert set(result["coverage"]) == {"fr_total", "fr_total_fixture", "scaffolds_found"}


_LEGACY_LINK_FILES = {
    "04_fr_list.json": {"$schema": "vc:04_fr_list", "functional_requirements": [{"fr_id": "fr-a"}]},
    "05_interface_contracts.json": {"apis": [{"api_id": "api-a", "trace": [{"type": "fr", "id": "fr-a"}]}]},
    "07_nfrs.json": {"nfrs": [{"nfr_id": "nfr-a", "trace": [{"type": "fr", "id": "fr-a"}]}]},
    "08_fixtures.json": {"fixtures": [{"fixture_id": "fx-a", "targets": [{"type": "api", "id": "api-a"}]}]},
    "11_redteam.json": {"threats": [{"threat_id": "th-a", "target_ids": [{"type": "api", "id": "api-a"}],
                                     "mitigations": [{"type": "inv", "id": "inv-a"}]}]},
    "14_roadmap.json": {"$schema": "vc:14-roadmap", "milestones": [{"milestone_id": "m1", "fr_refs": ["fr-a"]}]},
}


def test_matrix_computes_every_link_on_legacy_06_16(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    result = build_trace_matrix(str(root), _write_spec(root, _LEGACY_LINK_FILES))
    assert "not_computed" not in result
    assert result["matrix"][0] == {"fr_id": "fr-a", "apis": ["api-a"], "fixtures": ["fx-a"], "nfrs": ["nfr-a"],
                                   "threats": ["th-a"]}
    assert result["milestone_coverage"] == {"fr-a": ["m1"]}
    assert result["invariant_threat_coverage"] == {"inv-a": ["th-a"]}


# (file, entry list, entry field the reader needs) -> the values omitted and named when the reader is skipped
_KEY_BY_READER = {
    ("07_nfrs.json", "nfrs", "trace"): ["fr_with_nfr", "nfrs"],
    ("08_fixtures.json", "fixtures", "targets"): ["fr_with_fixture", "fixtures"],
    ("11_redteam.json", "threats", "target_ids"): ["fr_with_threat", "threats"],
    ("11_redteam.json", "threats", "mitigations"): ["invariant_threat_coverage"],
    ("14_roadmap.json", "milestones", "fr_refs"): ["milestone_coverage"],
}


@pytest.mark.parametrize("reader", list(_KEY_BY_READER), ids=lambda r: r[2])
def test_matrix_names_only_the_value_whose_reader_was_skipped(tmp_path, reader):
    file_name, array, field = reader
    files = json.loads(json.dumps(_LEGACY_LINK_FILES))
    for entry in files[file_name][array]:
        entry.pop(field, None)
    root = tmp_path / "repo"
    root.mkdir()
    result = build_trace_matrix(str(root), _write_spec(root, files))
    assert result["not_computed"] == _KEY_BY_READER[reader]
    row = result["matrix"][0]
    for name in _KEY_BY_READER[reader]:
        assert name not in row and name not in result["coverage"] and name not in result
    assert "apis" in row and row["apis"] == ["api-a"]


@pytest.mark.parametrize("field", ["trace", "targets", "target_ids", "mitigations", "fr_refs", "milestones"])
def test_matrix_does_not_raise_on_wrong_typed_link_fields(tmp_path, field):
    files = {
        "04_fr_list.json": {"$schema": "vc:04_fr_list", "functional_requirements": [{"fr_id": "fr-a"}]},
        "05_interface_contracts.json": {"apis": [{"api_id": "api-a", "trace": "x" if field == "trace" else []}]},
        "07_nfrs.json": {"nfrs": [{"nfr_id": "nfr-a", "trace": 7 if field == "trace" else []}]},
        "08_fixtures.json": {"fixtures": [{"fixture_id": "fx-a", "targets": "x" if field == "targets" else []}]},
        "11_redteam.json": {"threats": [{"threat_id": "th-a", "target_ids": 3 if field == "target_ids" else [],
                                         "mitigations": "m" if field == "mitigations" else []}]},
        "14_roadmap.json": {"$schema": "vc:14-roadmap", "milestones": "m" if field == "milestones" else [
            {"milestone_id": "m1", "fr_refs": 5 if field == "fr_refs" else [], "tasks": "t"}]},
    }
    root = tmp_path / "repo"
    root.mkdir()
    assert build_trace_matrix(str(root), _write_spec(root, files))["matrix"][0]["fr_id"] == "fr-a"


def test_closure_silent_on_new_shape_06_16(tmp_path):
    spec_dir = _graph_spec(tmp_path)
    assert check_traceability_closure(spec_dir) == []


_LEGACY_CLOSURE_FILES = {
    "00_charter.json": {"goals": [], "success_metrics": []},
    "01_capabilities.json": {"capabilities": [{"capability_id": "cap-a", "scope": "in"}]},
    "04_fr_list.json": {"functional_requirements": [{"fr_id": "fr-a", "trace": []}, {"fr_id": "fr-b", "trace": []}]},
    "05_interface_contracts.json": {"apis": [{"api_id": "api-a", "trace": []}]},
    "08_fixtures.json": {"fixtures": [{"fixture_id": "fx-a", "targets": []}]},
    "09_impl_plan.json": {"milestones": [{"milestone_id": "m09", "deliverables": [{"type": "fr", "id": "dl-a"}]}]},
    "10_governance.json": {"pr_rules": ["rule-a"]},
    "12_ci_gates.json": {"jobs": [{"job_id": "j", "steps": [{"command": "make"}]}]},
    "14_roadmap.json": {"milestones": [
        {"milestone_id": "m1", "fr_refs": ["fr-b"], "tasks": [{"task_id": "t1", "fr_refs": []}]}, {"milestone_id": "m2"}]},
}


def test_closure_reports_every_reader_on_legacy_06_16(tmp_path):
    codes = {e.code for e in check_traceability_closure(_write_spec(tmp_path, _LEGACY_CLOSURE_FILES))}
    assert {"W561", "W564", "W565", "W566", "W567", "W568", "W569", "W575"} <= codes


def _plan_spec(root: Path, checklist_item: dict) -> str:
    """A roadmap with one task, an anchor that registers one milestone plan, and that plan."""
    files = {
        "14_roadmap.json": {"milestones": [{"milestone_id": "m1", "tasks": [{"task_id": "t1"}]}]},
        "16_impl_context.json": {"plan": {"milestone_index": [
            {"milestone_id": "m1", "context_path": "impl_context/ms_a_plan.json"}]}},
    }
    spec_dir = _write_spec(root, files)
    plans = Path(spec_dir) / "impl_context"
    plans.mkdir()
    plan = {"plan": {"spec_alignment": {"checklist": [checklist_item]}},
            "execution": {"execution_results": [{"id": "r1"}]}}
    (plans / "ms_a_plan.json").write_text(json.dumps(plan), encoding="utf-8")
    return spec_dir


def test_closure_plan_readers_skip_a_plan_item_without_spec_ref(tmp_path):
    codes = {e.code for e in check_traceability_closure(_plan_spec(tmp_path, {"id": "cl-1", "realises": ["c1"]}))}
    assert not codes & {"W562", "W563", "W576"}


def test_closure_plan_readers_report_a_plan_item_with_spec_ref(tmp_path):
    item = {"id": "cl-1", "spec_ref": {"type": "task", "id": "other"}}
    codes = {e.code for e in check_traceability_closure(_plan_spec(tmp_path, item))}
    assert {"W562", "W563", "W576"} <= codes


@pytest.mark.parametrize("roadmap", [
    {"milestones": "m1"},
    {"milestones": ["m1", 7, {"milestone_id": "m2", "tasks": "t", "fr_refs": 5}]},
    {"milestones": [{"milestone_id": "m1", "fr_refs": [["x"]], "tasks": [7, {"task_id": "t", "fr_refs": "x"}]}]},
])
def test_closure_does_not_raise_on_a_wrong_typed_roadmap(tmp_path, roadmap):
    files = {
        "04_fr_list.json": {"functional_requirements": ["fr-a", {"fr_id": "fr-b", "trace": 7}]},
        "05_interface_contracts.json": {"apis": [7, {"api_id": "api-a", "trace": "x"}], "out_of_scope": 3},
        "08_fixtures.json": {"fixtures": [{"fixture_id": "fx", "targets": 1}]},
        "09_impl_plan.json": {"milestones": [{"milestone_id": "m", "deliverables": 4}, 5]},
        "14_roadmap.json": roadmap,
    }
    check_traceability_closure(_write_spec(tmp_path, files))


def test_closure_reads_nothing_of_a_graph_shape_roadmap_beside_legacy_fixtures(tmp_path):
    spec_dir = _graph_spec(tmp_path / "plain")
    legacy_08 = {"08_fixtures.json": {"fixtures": [{"fixture_id": "fx-a", "targets": []}]}}
    codes = {e.code for e in check_traceability_closure(_graph_spec(tmp_path / "mixed", legacy_08))}
    assert check_traceability_closure(spec_dir) == []
    assert codes == {"W565"}


def test_uncomputed_dimensions_lists_the_skipped_readers(tmp_path):
    assert uncomputed_dimensions(_graph_spec(tmp_path / "new")) == [
        "fr_api_coverage", "fr_fixture_coverage", "fr_milestone_coverage", "capability_fr_coverage"]
    assert uncomputed_dimensions(_write_spec(tmp_path, _LEGACY_CLOSURE_FILES)) == []
    assert uncomputed_dimensions(str(tmp_path / "absent")) == []


def test_completeness_check_follows_guards(tmp_path):
    code, out = _run_cli(["completeness-check", _graph_spec(tmp_path / "new"), "--repo-root", str(TOOLKIT_ROOT),
                          "--json"])
    payload = json.loads(out)
    skipped = ["fr_api_coverage", "fr_fixture_coverage", "fr_milestone_coverage", "capability_fr_coverage"]
    assert code == 0
    assert payload["not_computed"] == skipped
    vacuous = {"covered_count": 0, "total_count": 0, "ratio": 1.0, "uncovered_ids": []}
    assert all(payload["coverage"][name] == vacuous for name in skipped)
    assert payload["coverage"]["milestone_decomp_completeness"]["total_count"] == 1
    _, text = _run_cli(["completeness-check", _graph_spec(tmp_path / "text"), "--repo-root", str(TOOLKIT_ROOT)])
    assert text.count("[SKIP]") == len(skipped)
    assert "[SKIP] FR → API coverage: not computed on this spec shape" in text
    assert "[OK] Milestone decomp completeness: 100.0%" in text


def test_completeness_check_reports_every_dimension_on_legacy_shape(tmp_path):
    _, out = _run_cli(["completeness-check", _write_spec(tmp_path, _LEGACY_CLOSURE_FILES), "--repo-root",
                       str(TOOLKIT_ROOT), "--json"])
    payload = json.loads(out)
    assert payload["not_computed"] == []
    assert payload["coverage"]["fr_api_coverage"]["uncovered_ids"] == ["fr-a", "fr-b"]
    assert payload["coverage"]["fr_fixture_coverage"]["uncovered_ids"] == ["fr-a", "fr-b"]
    assert payload["coverage"]["fr_milestone_coverage"]["uncovered_ids"] == ["fr-a"]


def test_step_14_w604_skipped_on_new_shape(tmp_path):
    roadmap = tmp_path / "spec" / "14_roadmap.json"
    roadmap.parent.mkdir()
    new_shape = NEW_SHAPE_06_16["14_roadmap.json"]
    legacy = {**new_shape, "milestones": [{**new_shape["milestones"][0], "fr_refs": ["fr-a"]}]}
    roadmap.write_text(json.dumps(new_shape), encoding="utf-8")

    def codes(instance):
        return [e.code for e in validate_step_14(instance, str(TOOLKIT_ROOT), str(roadmap))]

    assert codes(new_shape) == []
    assert codes(legacy) == ["W604"]


def _forward_replay_repo(root: Path, *, shim: bool) -> None:
    (root / "tools").mkdir(parents=True)
    (root / "spec").mkdir()
    (root / "tools" / "step_order.json").write_text(json.dumps({"steps": ["00", "01"]}), encoding="utf-8")
    row = {"id": "SC-01-90", "step": "01", "path": "capabilities[].trace", "change": "remove", "shim": shim}
    (root / "tools" / "schema_changes.json").write_text(json.dumps({"rows": [row]}), encoding="utf-8")
    (root / "spec" / "00_charter.json").write_text("{}", encoding="utf-8")
    (root / "spec" / "01_capabilities.json").write_text(
        json.dumps({"capabilities": [{"capability_id": "cap-a"}]}), encoding="utf-8")


_BASE_01 = {"capabilities": [{"capability_id": "cap-a", "trace": [{"type": "charter-goal", "id": "goal-gone"}]}]}


def _forward_replay_codes(root: Path) -> list[str]:
    changed = (["spec/00_charter.json", "spec/01_capabilities.json"], None)

    def git_show(cmd, **_):
        base = _BASE_01 if cmd[-1].endswith("01_capabilities.json") else {}
        return mock.Mock(returncode=0, stdout=json.dumps(base), stderr="")

    with mock.patch("specdev_tools.validation.forward_replay_check._changed_files", return_value=changed), \
            mock.patch("subprocess.run", side_effect=git_show):
        return [e.code for e in check_forward_replay(str(root), base_ref="origin/main")]


def test_forward_replay_prunes_removed_paths_before_dropped_id_diff(tmp_path):
    _forward_replay_repo(tmp_path / "flagged", shim=True)
    _forward_replay_repo(tmp_path / "unflagged", shim=False)
    assert not {"E555", "W598"} & set(_forward_replay_codes(tmp_path / "flagged"))
    assert {"E555", "W598"} <= set(_forward_replay_codes(tmp_path / "unflagged"))


def test_removed_paths_lists_shim_removals_of_one_step(tmp_path):
    rows = [
        {"id": "a", "step": "05", "path": "out_of_scope", "change": "remove", "shim": True},
        {"id": "b", "step": "05", "path": "apis[].trace", "change": "remove", "shim": False},
        {"id": "c", "step": "05", "path": "apis[].scope", "change": "change", "shim": True},
        {"id": "d", "step": "16_anchor", "path": "plan.x", "change": "remove", "shim": True},
        {"id": "e", "step": "16_impl_context", "path": "plan.y", "change": "remove", "shim": True},
        {"id": "f", "step": "13a", "path": "z", "change": "remove", "shim": True},
    ]
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "schema_changes.json").write_text(json.dumps({"rows": rows}), encoding="utf-8")
    assert removed_paths("05", tmp_path) == ["out_of_scope"]
    assert removed_paths("16", tmp_path) == ["plan.x", "plan.y"]
    assert removed_paths("13", tmp_path) == []
    assert removed_paths("01", tmp_path / "absent") == []


def test_shipped_removed_paths_hold_the_legacy_read_fields():
    assert "out_of_scope" in removed_paths("05")
    assert any(path.endswith("trace") for path in removed_paths("06"))


def test_out_of_scope_fr_ids_needs_a_rationale_and_never_raises():
    assert out_of_scope_fr_ids({"out_of_scope": [
        {"fr_id": "fr-a", "rationale": "no api"}, {"fr_id": "fr-b"}, {"fr_id": 7, "rationale": "x"}, "fr-c"]}) == {"fr-a"}
    assert out_of_scope_fr_ids({"out_of_scope": "fr-a"}) == set()
    assert out_of_scope_fr_ids({}) == set()


@pytest.mark.parametrize(("doc", "paths", "expected"), [
    ({"a": 1, "trace": [1]}, ["trace"], {"a": 1}),
    ({"items": [{"trace": 1, "k": 2}, {"k": 3}]}, ["items[].trace"], {"items": [{"k": 2}, {"k": 3}]}),
    ({"env": {"x": {"cfg": 1, "keep": 2}}}, ["env{}.cfg"], {"env": {"x": {"keep": 2}}}),
    ({"a": {"b": {"c": 1, "d": 2}}}, ["a.b.c"], {"a": {"b": {"d": 2}}}),
    ({"items": [1, 2]}, ["items[]"], {"items": [1, 2]}),
    ({"items": "text", "m": [1]}, ["items[].trace", "m{}.x", "missing.deep", "$defs.t", "**.lifecycle"],
     {"items": "text", "m": [1]}),
    ([1, 2], ["trace"], [1, 2]),
])
def test_prune_removed_paths(doc, paths, expected):
    assert _prune_removed_paths(doc, paths) == expected


# --- readers of WI-M3-17b: scope resolver, reviewer, upstream backlog, seed lint -----------------

def test_scope_resolver_no_crash_on_new_shape(tmp_path):
    spec_dir = _graph_spec(tmp_path)
    id_to_file, adjacency = _build_trace_graph(spec_dir)
    assert "fr-password-reset" in id_to_file
    assert not any(adjacency.values())
    scope = resolve_scope("fr-password-reset", spec_dir, str(TOOLKIT_ROOT))
    assert not scope.get("errors")


@pytest.mark.parametrize("value", ["fr-a", 7, {"id": "fr-a"}, [7, None, ["fr-a"]]])
@pytest.mark.parametrize("field", ["trace", "targets", "fr_refs", "source_milestones"])
def test_scope_resolver_does_not_raise_on_wrong_typed_links(tmp_path, field, value):
    spec_dir = _write_spec(tmp_path, {"04_fr_list.json": {"functional_requirements": [
        {"fr_id": "fr-x", field: value}]}})
    _, adjacency = _build_trace_graph(spec_dir)
    assert not adjacency.get("fr-x")


def test_scope_resolver_builds_every_legacy_edge(tmp_path):
    spec_dir = _write_spec(tmp_path, {"14_roadmap.json": {"milestones": [{
        "milestone_id": "m1", "fr_refs": ["fr-a"], "source_milestones": ["m0"],
        "trace": [{"type": "fr", "id": "fr-b"}], "targets": [{"type": "api", "id": "api-c"}]}]}})
    _, adjacency = _build_trace_graph(spec_dir)
    assert adjacency["m1"] == {"fr-a", "m0", "fr-b", "api-c"}


def test_reviewer_skips_reverse_trace_without_trace():
    upstream = [("", NEW_SHAPE["04_fr_list.json"]), ("", NEW_SHAPE["01_capabilities.json"])]
    review = _run_structural_pass(NEW_SHAPE["05_interface_contracts.json"], "", upstream)
    assert review.upstream_coverage == {"covered": [], "dropped": []}
    assert review.reverse_trace == {"unjustified": [], "scope_creep": []}
    assert _compute_verdict(review, []) == "PASS"


def test_reviewer_counts_trace_when_the_artifact_carries_it():
    artifact = {"apis": [{"api_id": "api-a", "trace": [{"type": "fr", "id": "fr-a"}, {"type": "fr", "id": "fr-z"}]}]}
    review = _run_structural_pass(artifact, "", [("", {"fr_id": "fr-a"}), ("", {"fr_id": "fr-b"})])
    assert review.upstream_coverage == {"covered": ["fr-a"], "dropped": ["fr-b"]}
    assert review.reverse_trace["unjustified"] == ["fr-z"]


def test_upstream_backlog_accepts_pd3_item_without_w613(tmp_path):
    plan = {"plan": {"ambiguities": [{"id": "amb-1", "description": "Timeout unstated.", "about": ["fr-a"]}]},
            "execution": {"emergent_ambiguities": [{"id": "amb-2", "description": "Retry unstated.", "about": ["fr-a"]}]}}
    plans = tmp_path / "spec" / "impl_context"
    plans.mkdir(parents=True)
    (plans / "ms_a_plan.json").write_text(json.dumps(plan), encoding="utf-8")
    stdout, stderr_lines, exit_code = run_upstream_backlog(str(tmp_path / "spec"))
    assert exit_code == 0
    assert "amb-1" in stdout and "amb-2" in stdout
    assert not any(line.startswith(("W613", "E520")) for line in stderr_lines)


def test_seed_lint_w140_w551_on_new_shape_fixtures(tmp_path):
    example = TOOLKIT_ROOT / "tests" / "fixtures" / "graph_example"
    project = tmp_path / "project"
    shutil.copytree(example, project)
    for name, doc in NEW_SHAPE_06_16.items():
        (project / "spec" / name).write_text(json.dumps(doc), encoding="utf-8")
    codes = {e.code for e in lint_seeds(str(TOOLKIT_ROOT), str(project / "spec"), project_root=str(project))}
    assert not codes & {"W140", "W551"}


def test_inline_m8_guards_run_on_the_legacy_item_and_skip_the_new_one():
    impl_context = TOOLKIT_ROOT / "tests" / "fixtures" / "step_16" / "impl_context"

    def codes(name):
        return {e.code for e in validate_file(str(TOOLKIT_ROOT), str(impl_context / name))}

    assert {"E301"} <= codes("legacy_verified_missing_evidence.json")
    assert {"E305"} <= codes("legacy_planned_unexecuted.json")
    assert not codes("valid_full.json") & {"E301", "E305", "E307"}


def test_legacy_shape_suites_unchanged():
    corpus = TOOLKIT_ROOT / "tests" / "fixtures" / "spec_corpus"
    assert uncomputed_dimensions(str(corpus)) == []
    assert [e.code for e in check_traceability_closure(str(corpus))] == ["W570", "W570", "W565"]
    result = build_trace_matrix(str(TOOLKIT_ROOT), str(corpus))
    assert "not_computed" not in result
    assert result["coverage"]["fr_with_api"] == 1
    assert result["matrix"][0]["apis"] == ["API-CORPUS-001"]
    assert result["milestone_coverage"] == {"FR-CORPUS-001": ["MS-CORPUS-001"]}


# --- the guard sites ------------------------------------------------------------------------------

TOOLS_PACKAGE = TOOLKIT_ROOT / "tools" / "specdev_tools"
SHIM_FILE = "validation/_legacy_shim.py"

# Every function that calls `has_legacy_fields(` or `reader_on(` (or a shared decision), with the shim-table row it belongs to. M6c deletes the module by
# following this list; a new guard site must be added here.
GUARD_SITES = {
    ("context/reviewer.py", "_run_structural_pass"): "context/reviewer.py",
    ("context/scope_resolver.py", "_collect_entity_ids_and_traces"): "context/scope_resolver.py",
    ("validation/cross_artifact_checks.py", "check_step_02_integrity"): "step-02 capability coverage (M2)",
    ("validation/matrix.py", "build_trace_matrix"): "validation/matrix.py",
    ("validation/traceability_closure.py", "_api_reader_on"): "validation/traceability_closure.py",
    ("validation/traceability_closure.py", "_fixture_reader_on"): "validation/traceability_closure.py",
    ("validation/traceability_closure.py", "_milestone_reader_on"): "validation/traceability_closure.py",
    ("validation/traceability_closure.py", "_capability_reader_on"): "validation/traceability_closure.py",
    ("validation/traceability_closure.py", "check_traceability_closure"): "validation/traceability_closure.py",
    ("validation/validators/step_14.py", "validate_step_14"): "validators/step_14.py W604",
}

# Every module that imports the shim (guard sites and the other shim functions).
SHIM_CONSUMERS = {
    "cli.py": "completeness-check",
    "context/reviewer.py": "context/reviewer.py",
    "context/scope_resolver.py": "context/scope_resolver.py",
    "validation/cross_artifact_checks.py": "step-02 capability coverage (M2)",
    "validation/forward_replay_check.py": "removed_paths",
    "validation/matrix.py": "validation/matrix.py",
    "validation/traceability_closure.py": "validation/traceability_closure.py",
    "validation/validators/step_11.py": "is_parked_any_shape",
    "validation/validators/step_14.py": "validators/step_14.py W604",
}

# Files whose inline guards M8 rewrites. They never call the shim and the table above never names them.
M8_INLINE_FILES = {"context/milestone_state.py", "validation/validators/step_16.py",
                   "validation/validators/step_16_anchor.py"}


def _tool_sources() -> dict[str, str]:
    return {
        str(path.relative_to(TOOLS_PACKAGE)): path.read_text(encoding="utf-8")
        for path in sorted(TOOLS_PACKAGE.rglob("*.py"))
    }


_GUARD_CALLS = ("has_legacy_fields", "reader_on", "fr_api_reader_on", "fr_fixture_reader_on", "fr_milestone_reader_on")


def _guard_calls(source: str) -> set[str]:
    """The names of the functions (innermost def) that call ``has_legacy_fields``, ``reader_on`` or a shared decision."""
    found: set[str] = set()

    def visit(node: ast.AST, enclosing: str | None) -> None:
        for child in ast.iter_child_nodes(node):
            name = child.name if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) else enclosing
            if isinstance(child, ast.Call) and getattr(child.func, "id", getattr(child.func, "attr", "")) in _GUARD_CALLS:
                found.add(enclosing or "<module>")
            visit(child, name)

    visit(ast.parse(source), None)
    return found


def test_every_guard_site_is_in_the_table():
    sites = {
        (name, function)
        for name, source in _tool_sources().items()
        if name != SHIM_FILE
        for function in _guard_calls(source)
    }
    assert sites == set(GUARD_SITES)


def test_every_shim_consumer_is_in_the_table():
    importers = {
        name for name, source in _tool_sources().items()
        if name != SHIM_FILE and re.search(r"_legacy_shim\b", source)
    }
    assert importers == set(SHIM_CONSUMERS)


def test_no_m8_rewrites_site_calls_the_module():
    tagged = {name for name, source in _tool_sources().items() if re.search(r"#\s*M8 rewrites", source)}
    assert M8_INLINE_FILES <= tagged
    for name in tagged & set(_tool_sources()):
        source = _tool_sources()[name]
        assert "_legacy_shim" not in source and "has_legacy_fields" not in source, name
    assert not M8_INLINE_FILES & ({file for file, _ in GUARD_SITES} | set(SHIM_CONSUMERS))


def test_step_04_integrity_skips_a_non_dict_fr_trace_entry():
    arts = {"spec/04_fr_list.json": {"$schema": "vc:04_fr_list", "functional_requirements": [
        {"fr_id": "fr-a", "trace": ["cap-a", 7, None, {"type": "capability", "id": "cap-missing"}]}]}}
    errors = render_errors(check_step_04_integrity(arts, set(), {"cap-a"}))
    assert len(errors) == 1 and "cap-missing" in errors[0]
