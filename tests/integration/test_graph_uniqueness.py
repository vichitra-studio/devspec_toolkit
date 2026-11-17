"""Id uniqueness end to end (WI-M4-03): the repros of DEVSPEC-232 on the worked example, run through ``spec-check``.

Each case copies the worked example (``tests/fixtures/graph_example/spec``), changes one document, and reads the
``graph`` check of ``specdev spec-check``.
"""
from __future__ import annotations

import copy
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.validation.spec_check import run_spec_check_json
from specdev_tools.validation.validate import validate_file
from unit.graph._synth import ROOT, copy_example, graph_check, load_doc, run_specdev, write_json

_FR = "04_fr_list.json"
_ROADMAP = "14_roadmap.json"
_CHARTER = "00_charter.json"
_CAPABILITIES = "01_capabilities.json"
_DUPLICATED = "ac-password-reset-1"


@pytest.fixture
def spec(tmp_path: Path) -> Path:
    return copy_example(tmp_path / "spec")


def _edit(spec: Path, rel: str, change: Callable[[dict[str, Any]], None]) -> None:
    document = load_doc(spec, rel)
    change(document)
    write_json(spec, rel, document)


def _e704(spec: Path) -> list[dict[str, Any]]:
    return [finding for finding in graph_check(spec)["findings"] if finding["code"] == "E704"]


def _first_task(document: dict[str, Any]) -> dict[str, Any]:
    return document["milestones"][0]["tasks"][0]


def _assert_spec_check_fails(spec: Path) -> None:
    result = run_specdev("spec-check", str(spec), "--repo-root", str(ROOT))
    assert result.returncode != 0, result.stderr


def test_worked_example_has_no_duplicate(spec: Path) -> None:
    assert graph_check(spec)["findings"] == []


def test_duplicate_across_steps(spec: Path) -> None:
    """An 04 criterion id re-minted in step 14 with other text: E704 owned by step 14."""
    _edit(spec, _ROADMAP, lambda doc: _first_task(doc)["acceptance_criteria"].append(
        {"criterion_id": _DUPLICATED, "text": "A different statement under a re-used id."}))
    (finding,) = _e704(spec)
    assert (finding["owner"], finding["node_id"], finding["file"]) == ("step:14", _DUPLICATED, _ROADMAP)
    assert _FR in finding["message"] and _ROADMAP in finding["message"]
    _assert_spec_check_fails(spec)


def test_duplicate_nested_in_one_fr(spec: Path) -> None:
    def repeat(document: dict[str, Any]) -> None:
        criteria = document["functional_requirements"][0]["acceptance_criteria"]
        criteria.append({**criteria[0], "text": "The same id with new text."})

    _edit(spec, _FR, repeat)
    (finding,) = _e704(spec)
    assert (finding["owner"], finding["node_id"]) == ("step:04", _DUPLICATED)
    assert finding["jq_path"] == ".functional_requirements[0].acceptance_criteria[3]"
    _assert_spec_check_fails(spec)


def test_whole_criterion_object_duplicated(spec: Path) -> None:
    def copy_whole(document: dict[str, Any]) -> None:
        criteria = document["functional_requirements"][0]["acceptance_criteria"]
        criteria.append(copy.deepcopy(criteria[0]))

    _edit(spec, _FR, copy_whole)
    (finding,) = _e704(spec)
    assert (finding["owner"], finding["node_id"]) == ("step:04", _DUPLICATED)
    _assert_spec_check_fails(spec)


def test_task_criterion_id_repeated_in_second_task(spec: Path) -> None:
    def second_task(document: dict[str, Any]) -> None:
        first = _first_task(document)
        repeated = copy.deepcopy(first["acceptance_criteria"][0])
        document["milestones"][0]["tasks"].append(
            {"task_id": "task-second", "description": "A second task.", "acceptance_criteria": [repeated]})

    _edit(spec, _ROADMAP, second_task)
    (finding,) = _e704(spec)
    assert (finding["owner"], finding["node_id"]) == ("step:14", "tc-confirm-expired-token")
    _assert_spec_check_fails(spec)


def test_capability_and_step00_ids_covered(spec: Path) -> None:
    """No per-step validator checked capability ids or step 00 ids; the graph check does."""
    _edit(spec, _CAPABILITIES, lambda doc: doc["capabilities"].append(copy.deepcopy(doc["capabilities"][0])))
    _edit(spec, _CHARTER, lambda doc: doc["scope_items"].append(copy.deepcopy(doc["scope_items"][0])))
    found = {(finding["node_id"], finding["owner"]) for finding in _e704(spec)}
    assert found == {("cap-account-recovery", "step:01"), ("scope-password-reset", "step:00")}


def test_reuse_after_delete_ok(spec: Path) -> None:
    """A deleted node is in no file: its id is free to mint again in another step."""
    freed = "ac-password-reset-request-2"

    def delete_criterion(document: dict[str, Any]) -> None:
        criteria = document["functional_requirements"][1]["acceptance_criteria"]
        document["functional_requirements"][1]["acceptance_criteria"] = [c for c in criteria if c["criterion_id"] != freed]

    _edit(spec, _FR, delete_criterion)
    _edit(spec, _ROADMAP, lambda doc: _first_task(doc)["acceptance_criteria"].append(
        {"criterion_id": freed, "text": "Minted again after the delete."}))
    assert _e704(spec) == []


def test_lifecycle_does_not_exempt(spec: Path) -> None:
    """A deprecated node and a not_applicable node still collide with the id they repeat."""
    def repeat_with_lifecycle(document: dict[str, Any]) -> None:
        criteria = document["functional_requirements"][0]["acceptance_criteria"]
        criteria.append({**criteria[0], "lifecycle": "deprecated"})
        criteria.append({**criteria[0], "lifecycle": "not_applicable"})

    _edit(spec, _FR, repeat_with_lifecycle)
    findings = _e704(spec)
    assert [finding["jq_path"] for finding in findings] == [
        ".functional_requirements[0].acceptance_criteria[3]", ".functional_requirements[0].acceptance_criteria[4]"]


def test_spec_check_emits_one_e704_per_duplicate(spec: Path) -> None:
    """One repeated id is one E704 in the combined findings: the one-file id check does not run under spec-check."""
    _edit(spec, _FR, lambda doc: doc["functional_requirements"].append(copy.deepcopy(doc["functional_requirements"][1])))
    errors, context = run_spec_check_json(str(ROOT), str(spec))
    repeated = [error for error in errors if error.code == "E704" and error.node_id == "fr-password-reset-request"]
    assert len(repeated) == 1
    assert [f for f in context["checks"]["schema-validation"]["findings"] if f["code"] == "E704"] == []


def test_validate_reports_a_duplicate_inside_one_file(spec: Path) -> None:
    """Single-file ``validate`` keeps within-file duplicate detection; ``include_id_slice=False`` turns it off."""
    _edit(spec, _FR, lambda doc: doc["functional_requirements"].append(copy.deepcopy(doc["functional_requirements"][0])))
    errors = validate_file(str(ROOT), str(spec / _FR))
    found = [e for e in errors if e.code == "E704"]
    assert {e.owner for e in found} == {"step:04"}
    assert {e.node_id for e in found} == {
        "fr-password-reset", "ac-password-reset-1", "ac-password-reset-2", "ac-password-reset-3"}
    assert not [e for e in validate_file(str(ROOT), str(spec / _FR), include_id_slice=False) if e.code == "E704"]


def test_validate_does_not_report_a_duplicate_across_files(spec: Path) -> None:
    _edit(spec, _ROADMAP, lambda doc: _first_task(doc)["acceptance_criteria"].append(
        {"criterion_id": _DUPLICATED, "text": "Repeats an id of step 04."}))
    assert not [e for e in validate_file(str(ROOT), str(spec / _ROADMAP)) if e.code == "E704"]


def test_validate_reports_a_duplicate_in_a_plan_file(spec: Path) -> None:
    plan_rel = "impl_context/ms_account_recovery_plan.json"
    plan = load_doc(spec, plan_rel)
    checklist = plan["plan"]["spec_alignment"]["checklist"]
    checklist.append(copy.deepcopy(checklist[0]))
    write_json(spec, plan_rel, plan)
    errors = [e for e in validate_file(str(ROOT), str(spec / plan_rel)) if e.code == "E704"]
    assert [(e.owner, e.node_id) for e in errors] == [("step:16a", checklist[0]["id"])]


def test_validate_reports_a_duplicate_in_the_seed_manifest(spec: Path) -> None:
    manifest_rel = "common/seed_manifest.json"
    manifest = load_doc(spec, manifest_rel)
    manifest["seeds"].append(copy.deepcopy(manifest["seeds"][0]))
    write_json(spec, manifest_rel, manifest)
    errors = [e for e in validate_file(str(ROOT), str(spec / manifest_rel)) if e.code == "E704"]
    assert [e.node_id for e in errors] == [manifest["seeds"][0]["seed_id"]]
