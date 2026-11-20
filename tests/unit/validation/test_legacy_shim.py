"""Guards for readers of retired 1.1.1 fields (M3 extends the field set and these cases)."""
import ast
import json
import re
import shutil
from pathlib import Path
from typing import NamedTuple

import pytest

from specdev_tools.analysis.upstream_backlog import run as run_upstream_backlog
from specdev_tools.context.reviewer import _compute_verdict, _run_structural_pass
from specdev_tools.context.scope_resolver import resolve_scope
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
from specdev_tools.validation.validate import validate_file
from specdev_tools.validation.validators.step_11 import _load_parked_fr_ids

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


def _silent_reviewer(spec):
    review = _run_structural_pass(
        spec.files["05_interface_contracts.json"], "", [("", spec.files["04_fr_list.json"])]
    )
    assert review.upstream_coverage["covered"] == []


SILENT_READERS = {
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
    review = _run_structural_pass(LEGACY_SHAPE["05_interface_contracts.json"], "", [("", {"fr_id": "fr-a"})])
    assert review.upstream_coverage["covered"] == ["fr-a"], "reviewer _run_structural_pass reader"


_CAPABILITIES_1_1_1 = {"capabilities": [{"capability_id": "cap-a", "scope": "in", "trace": [], "success_metric_refs": []}]}


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
    assert fr_fixture_reader_on([{"targets": []}]) and not fr_fixture_reader_on([{"x": 1}])


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


# --- a copy of the worked example to run the guarded readers on -----------------------------------

EXAMPLE_SPEC = Path(__file__).parents[2] / "fixtures" / "graph_example" / "spec"
TOOLKIT_ROOT = Path(__file__).parents[3]


def _example_copy(tmp_path: Path, extra: dict | None = None) -> str:
    spec_dir = tmp_path / "spec"
    spec_dir.mkdir(parents=True)
    for path in EXAMPLE_SPEC.glob("*.json"):
        shutil.copy(path, spec_dir / path.name)
    for name, data in (extra or {}).items():
        (spec_dir / name).write_text(json.dumps(data), encoding="utf-8")
    return str(spec_dir)


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
    # A legacy FR parked by `priority: wont-have` stays out of the step-11 sibling loader.
    files = {
        "04_fr_list.json": {"$schema": "vc:04_fr_list", "functional_requirements": [
            {"fr_id": "fr-a", "priority": "must-have", "trace": []},
            {"fr_id": "fr-legacy-export", "priority": "wont-have", "trace": []}]},
        "14_roadmap.json": {"milestones": [{"milestone_id": "m1", "fr_refs": [], "tasks": []}]},
    }
    spec_dir = _write_spec(tmp_path, files)
    artifact = str(Path(spec_dir) / "11_adversarial.json")
    assert _load_parked_fr_ids(str(tmp_path), artifact) == {"fr-legacy-export"}


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


def test_removed_paths_lists_shim_removals_of_one_step(tmp_path):
    def row(seq: int, step: str, path: str, change: str, shim: bool) -> dict:
        return {"id": f"SC-{step}-{seq:02d}", "step": step, "path": path, "change": change, "shim": shim,
                "replaced_by": None, "owner": "M3", "design": [], "tickets": []}

    rows = [
        row(1, "05", "out_of_scope", "remove", True),
        row(2, "05", "apis[].trace", "remove", False),
        row(3, "05", "apis[].scope", "change", True),
        row(1, "16_anchor", "plan.x", "remove", True),
        row(1, "16_impl_context", "plan.y", "remove", True),
        row(1, "13a", "z", "remove", True),
        {"id": "SC-05-09", "step": "05", "path": "not_well_formed", "change": "remove", "shim": True},
    ]
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "schema_changes.json").write_text(json.dumps({"rows": rows}), encoding="utf-8")
    assert removed_paths("05", tmp_path) == ["out_of_scope"]
    assert removed_paths("16", tmp_path) == ["plan.x", "plan.y"]
    assert removed_paths("13", tmp_path) == []
    assert removed_paths("01", tmp_path / "absent") == []


@pytest.mark.parametrize("content", ['{"rows": null}', '{"rows": 5}', "[]", "null", "{", "\xff\xfe"])
def test_removed_paths_of_a_rows_file_that_cannot_be_used_is_empty(content, tmp_path):
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "schema_changes.json").write_bytes(content.encode("latin-1"))
    assert removed_paths("05", tmp_path) == []


def test_shipped_removed_paths_hold_the_legacy_read_fields():
    assert "out_of_scope" in removed_paths("05")
    assert any(path.endswith("trace") for path in removed_paths("06"))


def test_out_of_scope_fr_ids_needs_a_rationale_and_never_raises():
    assert out_of_scope_fr_ids({"out_of_scope": [
        {"fr_id": "fr-a", "rationale": "no api"}, {"fr_id": "fr-b"}, {"fr_id": 7, "rationale": "x"}, "fr-c"]}) == {"fr-a"}
    assert out_of_scope_fr_ids({"out_of_scope": "fr-a"}) == set()
    assert out_of_scope_fr_ids({}) == set()


# --- readers of WI-M3-17b: scope resolver, reviewer, upstream backlog, seed lint -----------------

def test_scope_resolver_no_crash_on_new_shape(tmp_path):
    spec_dir = _graph_spec(tmp_path)
    scope = resolve_scope("fr-password-reset", spec_dir, str(TOOLKIT_ROOT))
    assert not scope.get("errors")
    assert scope["resolved_ids"]["fr"] == ["fr-password-reset"]


@pytest.mark.parametrize("value", ["fr-a", 7, {"id": "fr-a"}, [7, None, ["fr-a"]]])
@pytest.mark.parametrize("field", ["trace", "targets", "fr_refs", "source_milestones"])
def test_scope_resolver_does_not_raise_on_wrong_typed_links(tmp_path, field, value):
    spec_dir = _write_spec(tmp_path, {"04_fr_list.json": {"functional_requirements": [
        {"fr_id": "fr-x", field: value}]}})
    scope = resolve_scope("fr-x", spec_dir, str(TOOLKIT_ROOT))
    assert scope["resolved_ids"].get("fr") == ["fr-x"]


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


def test_upstream_backlog_lists_pd3_items_and_places_unresolved_about_in_unplaced(tmp_path):
    plan = {"plan": {"ambiguities": [{"id": "amb-1", "description": "Timeout unstated.", "about": ["fr-a"]}]},
            "execution": {"emergent_ambiguities": [{"id": "amb-2", "description": "Retry unstated.", "about": ["fr-a"]}]}}
    plans = tmp_path / "spec" / "impl_context"
    plans.mkdir(parents=True)
    (plans / "ms_a_plan.json").write_text(json.dumps(plan), encoding="utf-8")
    stdout, stderr_lines, exit_code = run_upstream_backlog(str(tmp_path / "spec"), repo_root=str(TOOLKIT_ROOT))
    assert exit_code == 0
    assert "amb-1" in stdout and "amb-2" in stdout
    assert [line.split()[2] for line in stderr_lines if line.startswith("W613")] == [
        "impl_context/ms_a_plan.json:amb-1", "impl_context/ms_a_plan.json:amb-2"]
    assert not any(line.startswith("E520") for line in stderr_lines)


def test_inline_m8_guards_run_on_the_legacy_item_and_skip_the_new_one():
    impl_context = TOOLKIT_ROOT / "tests" / "fixtures" / "step_16" / "impl_context"

    def codes(name):
        return {e.code for e in validate_file(str(TOOLKIT_ROOT), str(impl_context / name))}

    assert {"E301"} <= codes("legacy_verified_missing_evidence.json")
    assert {"E305"} <= codes("legacy_planned_unexecuted.json")
    assert not codes("valid_full.json") & {"E301", "E305", "E307"}


# --- the guard sites ------------------------------------------------------------------------------

TOOLS_PACKAGE = TOOLKIT_ROOT / "tools" / "specdev_tools"
SHIM_FILE = "validation/_legacy_shim.py"

# Every function that calls `has_legacy_fields(` or `reader_on(` (or a shared decision), with the shim-table row it belongs to. M6c deletes the module by
# following this list; a new guard site must be added here.
GUARD_SITES = {
    ("context/reviewer.py", "_run_structural_pass"): "context/reviewer.py",
}

# Every module that imports the shim (guard sites and the other shim functions).
SHIM_CONSUMERS = {
    "context/reviewer.py": "context/reviewer.py",
    "validation/validators/step_11.py": "is_parked_any_shape",
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


