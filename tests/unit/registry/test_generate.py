"""Unit tests for the registry generator (specdev registry-generate).

Covers W3-T7: byte-determinism, golden-snapshot match, sentinel structure,
step coverage completeness, kind-inference rules, traceRef exclusion,
nested-array discovery, schema validation, and CLI required-flag enforcement.

All tests (except Test 12) run in-process via generate_registry() — no
subprocess forking.  Tests run against the toolkit's own schemas; no mocking.

Toolkit root from this file: Path(__file__).parents[3]
  → devspec_toolkit/tests/unit/registry/test_generate.py
  → parents[0] = devspec_toolkit/tests/unit/registry/
  → parents[1] = devspec_toolkit/tests/unit/
  → parents[2] = devspec_toolkit/tests/
  → parents[3] = devspec_toolkit/
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.registry.annotations import collect_annotations, lint_annotations
from specdev_tools.registry.generate import _serialize, generate_registry, run
from specdev_tools.registry.schema_checklist import CHECKLIST_FILE, ChecklistError, generate_checklist

# ---------------------------------------------------------------------------
# Toolkit root resolution
# ---------------------------------------------------------------------------

_TOOLKIT_ROOT = Path(__file__).parents[3]
"""Absolute path to the toolkit root (devspec_toolkit/)."""

_GOLDEN_PATH = _TOOLKIT_ROOT / "tests" / "fixtures" / "entry_key_registry_golden.json"
"""Golden snapshot for Test 2."""

_STEP_ORDER_PATH = _TOOLKIT_ROOT / "tools" / "step_order.json"
"""step_order.json for Test 4."""

_CHECKLIST_PATH = _TOOLKIT_ROOT / CHECKLIST_FILE
"""The generated schema-change checklist, committed."""

_KIND_ROLE_TABLE_PATH = _TOOLKIT_ROOT / "tests" / "fixtures" / "graph" / "kind_role_table.json"
"""Kind to step and role table of the spec graph (M1 fixture, extended with the M3 kinds)."""

_UNLISTED_KINDS = frozenset({"extension"})
"""Registered kinds the table leaves out: step 13 extension kinds are declared when they become first-class."""

_UNREGISTERED_KINDS = frozenset({"seed", "execution-record", "review-record"})
"""Table kinds with no registry entry: the seed is an external kind, the execution and review records arrive with a later milestone."""


def _run_generator() -> tuple[dict[str, Any], dict[str, Any]]:
    """Run generate_registry against toolkit's own schemas."""
    return generate_registry(str(_TOOLKIT_ROOT))


def _iter_all_arrays(entry: dict[str, Any]):
    """Yield every array-entry dict in a registry *entry*, at any nesting depth.

    The registry's ``arrayEntry.nested`` shape is recursive (DEVSPEC-125: step
    14 nests ``criterion`` three levels under ``milestones``), so invariants
    that must hold for *every* array — regardless of depth — walk with this
    helper rather than iterating a single ``nested`` level.
    """
    def _walk(node: dict[str, Any]):
        yield node
        for nested in node.get("nested", []):
            yield from _walk(nested)

    for arr in entry.get("arrays", []):
        yield from _walk(arr)


# ---------------------------------------------------------------------------
# Test 1: Byte-determinism
# ---------------------------------------------------------------------------


class TestByteDeterminism:
    """Running the generator twice with the same inputs must produce identical output."""

    def test_registry_doc_is_byte_identical_across_two_runs(self) -> None:
        """Serialised registry output is byte-identical across two independent calls."""
        reg1, _ext1 = _run_generator()
        reg2, _ext2 = _run_generator()
        assert _serialize(reg1) == _serialize(reg2), (
            "generate_registry() produced different byte output on two runs — "
            "sorting or ordering is non-deterministic."
        )

    def test_extraction_paths_doc_is_byte_identical_across_two_runs(self) -> None:
        """Serialised extraction_paths output is byte-identical across two independent calls."""
        _reg1, ext1 = _run_generator()
        _reg2, ext2 = _run_generator()
        assert _serialize(ext1) == _serialize(ext2), (
            "generate_registry() produced different extraction_paths byte output on two runs."
        )


# ---------------------------------------------------------------------------
# Test 2: Golden snapshot match
# ---------------------------------------------------------------------------


class TestGoldenSnapshotMatch:
    """Generated output must match the committed golden snapshot byte-for-byte."""

    def test_registry_matches_golden(self) -> None:
        """Registry doc matches tests/fixtures/entry_key_registry_golden.json exactly."""
        reg_doc, _ext = _run_generator()
        generated = _serialize(reg_doc)
        golden = _GOLDEN_PATH.read_text(encoding="utf-8")
        assert generated == golden, (
            "Generated registry does not match the golden snapshot.  "
            "If the schema legitimately changed, regenerate with:\n"
            "  source devspec_env/bin/activate && "
            "specdev registry-generate --repo-root ./devspec_toolkit\n"
            "  cp devspec_toolkit/tools/entry_key_registry.json "
            "devspec_toolkit/tests/fixtures/entry_key_registry_golden.json"
        )


# ---------------------------------------------------------------------------
# Test 3: Sentinels present
# ---------------------------------------------------------------------------


class TestSentinelsPresent:
    """_sentinels must list canonical_refs_used and canonical_proposals at top level only."""

    def test_sentinels_contains_canonical_refs_used(self) -> None:
        reg_doc, _ = _run_generator()
        assert "canonical_refs_used" in reg_doc["_sentinels"]

    def test_sentinels_contains_canonical_proposals(self) -> None:
        reg_doc, _ = _run_generator()
        assert "canonical_proposals" in reg_doc["_sentinels"]

    def test_sentinels_contains_out_of_scope(self) -> None:
        """out_of_scope must be present in _sentinels as a named sentinel value."""
        reg_doc, _ = _run_generator()
        assert "out_of_scope" in reg_doc["_sentinels"], (
            "'out_of_scope' sentinel is missing from _sentinels. "
            "This key is used as a hard sentinel to flag items intentionally "
            "excluded from extraction paths; it must be listed in _sentinels "
            "so consumers can distinguish it from real array paths."
        )

    def test_sentinels_not_in_per_file_array_paths(self) -> None:
        """Sentinel names must not appear as array_path values inside any registry entry."""
        reg_doc, _ = _run_generator()
        sentinels = set(reg_doc["_sentinels"])
        for basename, entry in reg_doc["registry"].items():
            # Every array at any depth (top-level or nested) must not name a sentinel.
            for arr in _iter_all_arrays(entry):
                arr_name = arr["array_path"].lstrip(".")
                assert arr_name not in sentinels, (
                    f"{basename}: sentinel '{arr_name}' must not appear as a "
                    "per-file array_path (at any nesting depth) — it belongs "
                    "only in _sentinels."
                )


# ---------------------------------------------------------------------------
# Test 4: Step coverage completeness
# ---------------------------------------------------------------------------


class TestStepCoverageCompleteness:
    """Every step in step_order.json must appear in exactly one of:
    registry (via its file's step), steps_without_entry_arrays, or
    steps_with_deferred_registration.
    """

    def test_all_steps_accounted_for(self) -> None:
        step_order_data = json.loads(_STEP_ORDER_PATH.read_text(encoding="utf-8"))
        all_steps: list[str] = step_order_data["steps"]

        reg_doc, _ = _run_generator()

        # Collect steps from each bucket
        registry_steps: set[str] = {
            entry["step"] for entry in reg_doc["registry"].values()
        }
        without_steps: set[str] = {
            item["step"] for item in reg_doc["steps_without_entry_arrays"]
        }
        deferred_steps: set[str] = {
            item["step"] for item in reg_doc["steps_with_deferred_registration"]
        }

        covered = registry_steps | without_steps | deferred_steps
        missing = [s for s in all_steps if s not in covered]

        assert not missing, (
            f"Steps not accounted for in registry, steps_without_entry_arrays, "
            f"or steps_with_deferred_registration: {missing}"
        )

    def test_no_step_is_double_counted(self) -> None:
        """No step should appear in more than one bucket."""
        reg_doc, _ = _run_generator()

        registry_steps: set[str] = {
            entry["step"] for entry in reg_doc["registry"].values()
        }
        without_steps: set[str] = {
            item["step"] for item in reg_doc["steps_without_entry_arrays"]
        }
        deferred_steps: set[str] = {
            item["step"] for item in reg_doc["steps_with_deferred_registration"]
        }

        reg_and_without = registry_steps & without_steps
        reg_and_deferred = registry_steps & deferred_steps
        without_and_deferred = without_steps & deferred_steps

        assert not reg_and_without, f"Steps in both registry and without-entry-arrays: {reg_and_without}"
        assert not reg_and_deferred, f"Steps in both registry and deferred: {reg_and_deferred}"
        assert not without_and_deferred, f"Steps in both without-entry-arrays and deferred: {without_and_deferred}"


# ---------------------------------------------------------------------------
# Test 5: No-arrays steps
# ---------------------------------------------------------------------------


class TestNoArraysSteps:
    """Every step in steps_without_entry_arrays has a non-empty rationale; step 16 registers its arrays."""

    def test_every_step_without_entry_arrays_has_a_rationale(self) -> None:
        reg_doc, _ = _run_generator()
        assert all(item["rationale"] for item in reg_doc["steps_without_entry_arrays"])

    def test_16_registers_its_ambiguity_arrays(self) -> None:
        reg_doc, _ = _run_generator()
        without_steps = {item["step"] for item in reg_doc["steps_without_entry_arrays"]}
        assert "16" not in without_steps
        paths = {a["array_path"] for a in reg_doc["registry"]["16_impl_context.json"]["arrays"]}
        # The anchor file holds what 16_anchor.schema.json declares; the plan schema's lists
        # belong to the plan files and are registered under their glob key.
        assert paths == {".plan.ambiguities", ".plan.milestone_index"}
        plan_paths = {a["array_path"] for a in reg_doc["registry"]["impl_context/ms_*_plan.json"]["arrays"]}
        assert plan_paths == {".plan.spec_alignment.checklist", ".plan.ambiguities", ".execution.emergent_ambiguities"}


# ---------------------------------------------------------------------------
# Test 6: Deferred registration
# ---------------------------------------------------------------------------


class TestDeferredRegistration:
    """Steps 16b and 16c are in steps_with_deferred_registration only; 16a is registered by annotation."""

    def test_deferred_steps_are_present(self) -> None:
        reg_doc, _ = _run_generator()
        deferred = {item["step"]: item for item in reg_doc["steps_with_deferred_registration"]}
        for step in ("16b", "16c"):
            assert step in deferred, f"Step '{step}' not found in steps_with_deferred_registration."
            assert deferred[step]["rationale"], f"Step '{step}' has empty rationale."

    def test_deferred_steps_not_in_without_entry_arrays(self) -> None:
        """Disjoint sets: 16a/16b/16c must not appear in steps_without_entry_arrays."""
        reg_doc, _ = _run_generator()
        without_steps_set = {item["step"] for item in reg_doc["steps_without_entry_arrays"]}
        for step in ("16a", "16b", "16c"):
            assert step not in without_steps_set, (
                f"Deferred step '{step}' found in steps_without_entry_arrays — "
                "deferred and without-entry-arrays must be disjoint."
            )

    def test_deferred_steps_not_in_registry(self) -> None:
        """Deferred steps must not appear as 'step' values inside the registry."""
        reg_doc, _ = _run_generator()
        registry_steps = {entry["step"] for entry in reg_doc["registry"].values()}
        for step in ("16b", "16c"):
            assert step not in registry_steps, (
                f"Deferred step '{step}' found as a 'step' value in registry — "
                "deferred steps should not have registry entries."
            )

    def test_plan_item_kind_is_registered_under_the_plan_file_glob(self) -> None:
        """The plan-item kind reaches the registry through its ``x-node`` ``files`` glob, as step 16a."""
        reg_doc, _ = _run_generator()
        entry = reg_doc["registry"]["impl_context/ms_*_plan.json"]
        assert entry["step"] == "16a"
        arr = next(a for a in entry["arrays"] if a["array_path"] == ".plan.spec_alignment.checklist")
        assert (arr["kind"], arr["id_field"], arr["role"]) == ("plan-item", "id", "plan")
        assert [lk["field"] for lk in arr["links"]] == ["realises", "replaces"]


# ---------------------------------------------------------------------------
# Registry cutover to the graph shape (WI-M3-18)
# ---------------------------------------------------------------------------


def _registered_kinds(registry: dict[str, Any]) -> dict[str, set[tuple[str, str | None, bool]]]:
    """Map each registered kind to the ``(step, role, coarse)`` triples it is registered with."""
    found: dict[str, set[tuple[str, str | None, bool]]] = {}
    for entry in registry.values():
        for array in _iter_all_arrays(entry):
            found.setdefault(array["kind"], set()).add((entry["step"], array.get("role"), array.get("coarse", False)))
    return found


class TestRegistryCutover:
    """The registry the annotated schemas produce, against the kind table and the generator's lists."""

    def test_registry_lint_passes_on_every_real_schema(self) -> None:
        decls = collect_annotations(str(_TOOLKIT_ROOT))
        assert not decls.empty
        assert lint_annotations(decls) == []

    def test_kind_table_equals_registry(self) -> None:
        table = json.loads(_KIND_ROLE_TABLE_PATH.read_text(encoding="utf-8"))["kinds"]
        registered = _registered_kinds(_run_generator()[0]["registry"])
        assert set(registered) - set(table) == _UNLISTED_KINDS
        unregistered = {k for k in table if k not in registered}
        assert unregistered == _UNREGISTERED_KINDS | {k for k, row in table.items() if row["role"] == "content"}
        for kind, triples in registered.items():
            if kind in _UNLISTED_KINDS:
                continue
            row = table[kind]
            steps = {step for step, _, _ in triples}
            assert steps <= {row["step"]} or row["step"] == "any", (kind, steps)
            assert {role for _, role, _ in triples} == {row["role"]}, kind
            assert {coarse for _, _, coarse in triples} == {row.get("coarse", False)}, kind

    def test_steps_without_entry_arrays_loses_10_15_16(self) -> None:
        reg_doc, _ = _run_generator()
        without = {item["step"] for item in reg_doc["steps_without_entry_arrays"]}
        assert without == set()

    def test_steps_with_deferred_registration_loses_16a(self) -> None:
        reg_doc, _ = _run_generator()
        assert [item["step"] for item in reg_doc["steps_with_deferred_registration"]] == ["16b", "16c"]
        assert "16a" in {entry["step"] for entry in reg_doc["registry"].values()}

    def test_registry_generate_writes_schema_change_checklist_byte_identically(self, tmp_path: Path) -> None:
        paths = {name: str(tmp_path / name) for name in ("reg.json", "paths.json", "checklist.md")}
        run(str(_TOOLKIT_ROOT), paths["reg.json"], paths["paths.json"], checklist_out=paths["checklist.md"])
        written = Path(paths["checklist.md"]).read_bytes()
        assert written == _CHECKLIST_PATH.read_bytes()
        assert written == generate_checklist(_TOOLKIT_ROOT).encode("utf-8")

    def test_a_rows_file_that_cannot_be_used_writes_no_output_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def unusable(_repo_root: Path) -> str:
            raise ChecklistError("tools/schema_changes.json: rows[0]: id: duplicate")

        monkeypatch.setattr("specdev_tools.registry.generate.generate_checklist", unusable)
        paths = {name: str(tmp_path / name) for name in ("reg.json", "paths.json", "order.json", "checklist.md")}
        with pytest.raises(ChecklistError):
            run(str(_TOOLKIT_ROOT), paths["reg.json"], paths["paths.json"],
                step_order_out=paths["order.json"], checklist_out=paths["checklist.md"])
        assert list(tmp_path.iterdir()) == []


# ---------------------------------------------------------------------------
# Test 7: Kind inference Rule A — *_id suffix
# ---------------------------------------------------------------------------


class TestKindInferenceIdSuffix:
    """Arrays whose id_field ends in _id derive kind by stripping _id and snake→kebab."""

    def test_04_fr_list_functional_requirements_kind(self) -> None:
        """04_fr_list.json → .functional_requirements: fr_id → kind: fr"""
        reg_doc, _ = _run_generator()
        entry = reg_doc["registry"]["04_fr_list.json"]
        arr = next(a for a in entry["arrays"] if a["array_path"] == ".functional_requirements")
        assert arr["id_field"] == "fr_id"
        assert arr["kind"] == "fr"

    def test_11_redteam_threats_kind(self) -> None:
        """11_redteam.json → .threats: threat_id → kind: threat"""
        reg_doc, _ = _run_generator()
        entry = reg_doc["registry"]["11_redteam.json"]
        arr = next(a for a in entry["arrays"] if a["array_path"] == ".threats")
        assert arr["id_field"] == "threat_id"
        assert arr["kind"] == "threat"

    def test_01_capabilities_kind(self) -> None:
        """01_capabilities.json → .capabilities: capability_id → kind: capability"""
        reg_doc, _ = _run_generator()
        entry = reg_doc["registry"]["01_capabilities.json"]
        arr = next(a for a in entry["arrays"] if a["array_path"] == ".capabilities")
        assert arr["id_field"] == "capability_id"
        assert arr["kind"] == "capability"

    def test_07_nfrs_kind(self) -> None:
        """07_nfrs.json → .nfrs: nfr_id → kind: nfr"""
        reg_doc, _ = _run_generator()
        entry = reg_doc["registry"]["07_nfrs.json"]
        arr = next(a for a in entry["arrays"] if a["array_path"] == ".nfrs")
        assert arr["id_field"] == "nfr_id"
        assert arr["kind"] == "nfr"


# ---------------------------------------------------------------------------
# Test 8: Kind inference Rule A — bare id arrays
# ---------------------------------------------------------------------------


class TestKindInferenceBareId:
    """Arrays where id_field == 'id' derive kind via singularize(array_name) + snake→kebab."""

    def test_11_redteam_edge_cases_kind(self) -> None:
        """11_redteam.json → .edge_cases: id → singularize('edge_cases') = 'edge_case' → kebab 'edge-case'"""
        reg_doc, _ = _run_generator()
        entry = reg_doc["registry"]["11_redteam.json"]
        arr = next(a for a in entry["arrays"] if a["array_path"] == ".edge_cases")
        assert arr["id_field"] == "id"
        assert arr["kind"] == "edge-case", (
            f"Expected 'edge-case' (singularize edge_cases + snake→kebab), got '{arr['kind']}'"
        )

    def test_14_roadmap_has_no_dependencies_array_and_declares_graph_kinds(self) -> None:
        """14_roadmap.json: the top-level ``dependencies`` array is gone; the nodes are declared by ``x-node``."""
        reg_doc, _ = _run_generator()
        entry = reg_doc["registry"]["14_roadmap.json"]
        assert ".dependencies" not in {a["array_path"] for a in entry["arrays"]}
        milestones = next(a for a in entry["arrays"] if a["array_path"] == ".milestones")
        assert milestones["kind"] == "roadmap-milestone"
        tasks = next(n for n in milestones["nested"] if n["array_path"] == ".tasks")
        criteria = next(n for n in tasks["nested"] if n["array_path"] == ".acceptance_criteria")
        assert (tasks["kind"], criteria["kind"], criteria["id_field"]) == ("task", "task-criterion", "criterion_id")

    def test_11_redteam_threats_uses_id_suffix_not_bare_id(self) -> None:
        """Confirm .threats uses threat_id (not bare id), validating Rule A priority."""
        reg_doc, _ = _run_generator()
        entry = reg_doc["registry"]["11_redteam.json"]
        arr = next(a for a in entry["arrays"] if a["array_path"] == ".threats")
        # id_field must be threat_id (suffix-_id wins over bare 'id')
        assert arr["id_field"] == "threat_id"
        assert arr["kind"] == "threat"


# ---------------------------------------------------------------------------
# Test 9: traceRef exclusion (Rule B)
# ---------------------------------------------------------------------------


class TestTraceRefExclusion:
    """traceRef arrays are cross-step foreign-key refs and must not appear in registry."""

    def test_no_kind_equals_trace_anywhere(self) -> None:
        """No entry in the registry (top-level or nested) should have kind == 'trace'."""
        reg_doc, _ = _run_generator()
        for basename, entry in reg_doc["registry"].items():
            # No array at any depth may carry kind='trace' (traceRef leak).
            for arr in _iter_all_arrays(entry):
                assert arr.get("kind") != "trace", (
                    f"{basename}: array {arr['array_path']} has kind='trace', "
                    "which indicates a traceRef array leaked into the registry."
                )

    def test_traceref_files_have_no_trace_array_path(self) -> None:
        """Files that have .trace[] (a traceRef array) must not include it in their registry entry."""
        # These files use traceRef and should NOT have a .trace array_path in registry
        files_with_trace_arrays = [
            "02a_delivery_baseline.json",
            "09_impl_plan.json",
            "10_governance.json",
            "11_redteam.json",
            "12_ci_gates.json",
            "14_roadmap.json",
            "15_scaffold.json",
        ]
        reg_doc, _ = _run_generator()
        for basename in files_with_trace_arrays:
            if basename not in reg_doc["registry"]:
                continue  # step has no registry entry (steps_without or deferred)
            entry = reg_doc["registry"][basename]
            array_paths = [a["array_path"] for a in entry.get("arrays", [])]
            assert ".trace" not in array_paths, (
                f"{basename}: .trace should be excluded from registry (it is a traceRef array), "
                f"but it appears in array_paths: {array_paths}"
            )

    def test_14_roadmap_milestones_nested_has_no_deliverables(self) -> None:
        """14_roadmap.json .milestones[] nested must NOT include deliverables (traceRefs)."""
        reg_doc, _ = _run_generator()
        entry = reg_doc["registry"].get("14_roadmap.json")
        assert entry is not None, "14_roadmap.json not in registry"
        milestones_arr = next(
            a for a in entry["arrays"] if a["array_path"] == ".milestones"
        )
        nested_paths = [n["array_path"] for n in milestones_arr.get("nested", [])]
        assert ".deliverables" not in nested_paths, (
            "14_roadmap.json: .milestones[].deliverables is a traceRef array and must be "
            f"excluded from nested discovery. Found nested: {nested_paths}"
        )


# ---------------------------------------------------------------------------
# Test 10: Nested-array discovery
# ---------------------------------------------------------------------------


class TestNestedArrayDiscovery:
    """Nested arrays inside top-level entries must be discovered and registered."""

    def test_14_roadmap_milestones_has_nested_tasks(self) -> None:
        """14_roadmap.json → .milestones nested must contain .tasks with kind 'task'."""
        reg_doc, _ = _run_generator()
        entry = reg_doc["registry"]["14_roadmap.json"]
        milestones_arr = next(a for a in entry["arrays"] if a["array_path"] == ".milestones")
        assert "nested" in milestones_arr, ".milestones must have a 'nested' key"
        nested_by_path = {n["array_path"]: n for n in milestones_arr["nested"]}
        assert ".tasks" in nested_by_path, (
            f".milestones nested must include .tasks; found: {list(nested_by_path.keys())}"
        )
        tasks_nested = nested_by_path[".tasks"]
        assert tasks_nested["id_field"] == "task_id"
        assert tasks_nested["kind"] == "task"

    def test_04_fr_list_functional_requirements_has_nested_acceptance_criteria(self) -> None:
        """04_fr_list.json → .functional_requirements nested must contain .acceptance_criteria."""
        reg_doc, _ = _run_generator()
        entry = reg_doc["registry"]["04_fr_list.json"]
        fr_arr = next(
            a for a in entry["arrays"] if a["array_path"] == ".functional_requirements"
        )
        assert "nested" in fr_arr, ".functional_requirements must have a 'nested' key"
        nested_by_path = {n["array_path"]: n for n in fr_arr["nested"]}
        assert ".acceptance_criteria" in nested_by_path, (
            f".functional_requirements nested must include .acceptance_criteria; "
            f"found: {list(nested_by_path.keys())}"
        )
        crit_nested = nested_by_path[".acceptance_criteria"]
        assert crit_nested["id_field"] == "criterion_id"
        assert crit_nested["kind"] == "criterion"


# ---------------------------------------------------------------------------
# Test 11: Schema validation
# ---------------------------------------------------------------------------


class TestSchemaValidation:
    """Generated output must validate against entry_key_registry.schema.json."""

    def test_registry_doc_validates_against_schema(self) -> None:
        """Run generator and validate the result with jsonschema."""
        import jsonschema  # noqa: PLC0415

        schema_path = _TOOLKIT_ROOT / "schema" / "entry_key_registry.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))

        reg_doc, _ = _run_generator()

        # jsonschema.validate raises jsonschema.ValidationError on failure
        try:
            jsonschema.validate(instance=reg_doc, schema=schema)
        except jsonschema.ValidationError as exc:
            pytest.fail(
                f"Generated registry doc failed JSON Schema validation:\n{exc.message}"
            )


# ---------------------------------------------------------------------------
# Test 12: Required-flag enforcement (CLI level)
# ---------------------------------------------------------------------------


class TestRequiredFlagEnforcement:
    """Invoking 'specdev registry-generate' without --repo-root must fail."""

    def test_no_args_exits_nonzero(self) -> None:
        """specdev registry-generate with no args exits with non-zero status."""
        result = subprocess.run(
            [sys.executable, "-m", "specdev_tools.cli", "registry-generate"],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0, (
            f"Expected non-zero exit when --repo-root is missing, got 0. "
            f"stderr: {result.stderr!r}"
        )

    def test_no_args_stderr_mentions_repo_root(self) -> None:
        """stderr must indicate that --repo-root is missing."""
        result = subprocess.run(
            [sys.executable, "-m", "specdev_tools.cli", "registry-generate"],
            capture_output=True,
            text=True,
        )
        assert "repo-root" in result.stderr or "repo_root" in result.stderr, (
            f"Expected stderr to mention '--repo-root' missing, got: {result.stderr!r}"
        )


# ---------------------------------------------------------------------------
# Test 13: _schema_file_for_step — fail-loud hardening
# ---------------------------------------------------------------------------


class TestSchemaFileForStepHardening:
    """_schema_file_for_step fail-loud hardening: ValueError on unhandled ambiguity.

    These tests verify the three behaviour invariants introduced by the
    fail-loud / order-independent refactor:

    1. Step 16 returns the impl_context schema (not anchor) — same result as
       before, now proven independent of SCHEMA_SKIP rather than dict order.
    2. Any step with exactly 0 or 1 schema after the skip-filter passes through
       unchanged (no regression for current steps).
    3. A synthetic directory with two non-skipped same-step schemas triggers
       the new ValueError, naming the step and the remaining files.
    """

    def test_step_16_returns_impl_context_schema(self) -> None:
        """_schema_file_for_step('16', schema_dir) returns 16_impl_context.schema.json.

        16_anchor.schema.json is in SCHEMA_SKIP, so exactly 1 file remains.
        This is the primary correctness invariant.
        """
        from specdev_tools.registry.generate import _schema_file_for_step

        schema_dir = str(_TOOLKIT_ROOT / "schema")
        result = _schema_file_for_step("16", schema_dir)
        assert result is not None, "_schema_file_for_step('16', ...) returned None"
        assert result.endswith("16_impl_context.schema.json"), (
            f"Expected 16_impl_context.schema.json, got {result!r}"
        )

    def test_single_match_returned_directly(self) -> None:
        """Steps with exactly one schema file after SCHEMA_SKIP return that file."""
        from specdev_tools.registry.generate import _schema_file_for_step

        schema_dir = str(_TOOLKIT_ROOT / "schema")
        # Step 04 has exactly one schema file; no skip-filter entry.
        result = _schema_file_for_step("04", schema_dir)
        assert result is not None
        assert "04_" in result

    def test_ambiguity_raises_value_error(self, tmp_path: Path) -> None:
        """Two non-skipped same-step schemas → ValueError naming step + files + fix hint.

        Constructs a synthetic schema dir with two files matching step '99'
        that are NOT in SCHEMA_SKIP, then asserts the new raise fires.
        """
        from specdev_tools.registry.generate import _schema_file_for_step

        # Create two fake step-99 schema files in a temp dir
        (tmp_path / "99_alpha.schema.json").write_text("{}", encoding="utf-8")
        (tmp_path / "99_beta.schema.json").write_text("{}", encoding="utf-8")

        with pytest.raises(ValueError) as exc_info:
            _schema_file_for_step("99", str(tmp_path))

        msg = str(exc_info.value)
        assert "99" in msg, f"ValueError should name the step; got: {msg!r}"
        assert "99_alpha.schema.json" in msg, f"ValueError should list file; got: {msg!r}"
        assert "99_beta.schema.json" in msg, f"ValueError should list file; got: {msg!r}"
        assert "SCHEMA_SKIP" in msg, f"ValueError should mention SCHEMA_SKIP; got: {msg!r}"
