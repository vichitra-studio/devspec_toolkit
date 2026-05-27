"""Unit tests for specdev_tools.validation.registry_check.

Tests cover:
- Happy path: all-correct fixture passes all checks.
- R001 MISSING_STEP_REGISTRATION: moved to toolkit unit test T-step-registry-coverage.
  E620 is retained in ERROR_CODES for backward compatibility but no longer emitted
  at host-runtime. See tests/unit/toolkit_invariants/test_step_registry_coverage.py.
- R002 PHANTOM_BASENAME: registered basename not in extraction_paths.json.
- R003 REGISTRY_DRIFT: id_field rename, array_path rename, missing array.
- R003 nested: nested array missing, nested id_field mismatch.
- R004 UNREGISTERED_ARRAY: host spec has id-bearing array absent from toolkit registry.
- spec-check wiring: registry-check SKIP when no registry file, PASS/WARN when present.
- --json envelope shape: matches the standard format_errors_json shape.
"""
from __future__ import annotations

import json
import os
import tempfile
from typing import Any

from specdev_tools.validation.registry_check import run_registry_check


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _write(directory: str, filename: str, content: Any) -> str:
    """Write JSON content to directory/filename and return the path."""
    path = os.path.join(directory, filename)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(content, fh, indent=2)
    return path


def _make_registry(entries: dict[str, Any], steps_without_entry_arrays: dict[str, str] | None = None) -> dict:
    result: dict = {
        "_format_version": "1",
        "registry": entries,
    }
    if steps_without_entry_arrays is not None:
        result["steps_without_entry_arrays"] = steps_without_entry_arrays
    return result


def _make_step_order(steps: list[str]) -> dict:
    return {"version": "1.0.0", "steps": steps}


def _make_extraction_paths(basenames: list[str], step: str = "04") -> dict:
    """Create extraction_paths.json with given basenames under a step key."""
    return {step: {bn: [".array"] for bn in basenames}}


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestRegistryCheckHappyPath:
    def test_all_correct_passes(self) -> None:
        """All three checks pass when registry, step_order, extraction_paths, and spec files align."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_root = os.path.join(tmpdir, "spec")
            repo_root = os.path.join(tmpdir, "toolkit")
            os.makedirs(spec_root)
            os.makedirs(os.path.join(repo_root, "tools"))

            # step_order.json with one step
            _write(repo_root, "tools/step_order.json", _make_step_order(["04"]))

            # extraction_paths.json with the registered basename
            _write(repo_root, "tools/extraction_paths.json",
                   _make_extraction_paths(["04_fr_list.json"], step="04"))

            # registry with step 04 registered
            registry = _make_registry({
                "04_fr_list.json": {
                    "step": "04",
                    "arrays": [{"array_path": ".functional_requirements", "id_field": "fr_id", "kind": "functional_requirement"}],
                }
            })
            _write(repo_root, "tools/entry_key_registry.json", registry)

            # spec file with matching structure
            spec_data = {
                "functional_requirements": [
                    {"fr_id": "fr-test", "name": "Test FR", "owner": "product"}
                ]
            }
            _write(spec_root, "04_fr_list.json", spec_data)

            errs = run_registry_check(spec_root=spec_root, repo_root=repo_root)
            assert errs == [], f"Expected no errors, got: {errs}"

    def test_no_registry_file_skips_all_checks(self) -> None:
        """When entry_key_registry.json doesn't exist, all checks are skipped (returns [])."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_root = os.path.join(tmpdir, "spec")
            repo_root = os.path.join(tmpdir, "toolkit")
            os.makedirs(spec_root)
            os.makedirs(os.path.join(repo_root, "tools"))
            _write(repo_root, "tools/step_order.json", _make_step_order(["04"]))
            # No entry_key_registry.json in repo_root/tools/
            errs = run_registry_check(spec_root=spec_root, repo_root=repo_root)
            assert errs == []


# ---------------------------------------------------------------------------
# R001 — Missing step registration (MOVED to toolkit unit tests)
# ---------------------------------------------------------------------------
# R001 / E620 REGISTRY_MISSING_STEP was removed from host-runtime registry-check
# after W6. The registry generator (W3) enforces step coverage as an internal
# contract. The full R001 invariant is now tested in:
#   tests/unit/toolkit_invariants/test_step_registry_coverage.py
#
# E620 is retained in ERROR_CODES for backward compatibility.
# Tests below verify R001 is NOT emitted at host-runtime (since W6).
# ---------------------------------------------------------------------------

class TestR001MissingStepRegistration:
    def test_r001_no_longer_fires_e620_at_host_runtime(self) -> None:
        """R001 moved to toolkit unit tests — unregistered step does NOT fire E620 at host-runtime.

        After W6, E620 is NOT emitted by run_registry_check(). The generator
        enforces step coverage internally. See T-step-registry-coverage.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_root = os.path.join(tmpdir, "spec")
            repo_root = os.path.join(tmpdir, "toolkit")
            os.makedirs(spec_root)
            os.makedirs(os.path.join(repo_root, "tools"))

            _write(repo_root, "tools/step_order.json", _make_step_order(["04", "05"]))
            _write(repo_root, "tools/extraction_paths.json",
                   _make_extraction_paths(["04_fr_list.json"], step="04"))

            # Registry only covers step 04 (step 05 is "unregistered")
            registry = _make_registry({
                "04_fr_list.json": {
                    "step": "04",
                    "arrays": [{"array_path": ".functional_requirements", "id_field": "fr_id", "kind": "fr"}],
                }
            })
            _write(repo_root, "tools/entry_key_registry.json", registry)
            _write(spec_root, "04_fr_list.json", {"functional_requirements": [{"fr_id": "fr-x"}]})

            errs = run_registry_check(spec_root=spec_root, repo_root=repo_root)
            codes = [e.code for e in errs]
            # R001 moved to toolkit unit tests — E620 must NOT fire at host-runtime
            assert "E620" not in codes, (
                f"E620 unexpectedly fired at host-runtime (R001 was moved to toolkit "
                f"unit tests after W6). Got errors: {errs}"
            )

    def test_opted_out_step_does_not_fire(self) -> None:
        """Step in steps_without_entry_arrays → no E620 (unchanged; R001 not emitted)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_root = os.path.join(tmpdir, "spec")
            repo_root = os.path.join(tmpdir, "toolkit")
            os.makedirs(spec_root)
            os.makedirs(os.path.join(repo_root, "tools"))

            _write(repo_root, "tools/step_order.json", _make_step_order(["16a"]))
            _write(repo_root, "tools/extraction_paths.json", {"_meta": {}})

            # Registry with 16a opted out
            registry = _make_registry(
                {},
                steps_without_entry_arrays={"16a": "No dedicated spec file."}
            )
            _write(repo_root, "tools/entry_key_registry.json", registry)

            errs = run_registry_check(spec_root=spec_root, repo_root=repo_root)
            codes = [e.code for e in errs]
            assert "E620" not in codes

    def test_step_with_basename_in_registry_does_not_fire(self) -> None:
        """Step with a registered basename → no E620 (unchanged; R001 not emitted)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_root = os.path.join(tmpdir, "spec")
            repo_root = os.path.join(tmpdir, "toolkit")
            os.makedirs(spec_root)
            os.makedirs(os.path.join(repo_root, "tools"))

            _write(repo_root, "tools/step_order.json", _make_step_order(["03"]))
            _write(repo_root, "tools/extraction_paths.json",
                   _make_extraction_paths(["03_glossary.json"], step="03"))

            registry = _make_registry({
                "03_glossary.json": {
                    "step": "03",
                    "arrays": [{"array_path": ".terms", "id_field": "term_id", "kind": "term"}],
                }
            })
            _write(repo_root, "tools/entry_key_registry.json", registry)
            _write(spec_root, "03_glossary.json", {"terms": [{"term_id": "t-1"}]})

            errs = run_registry_check(spec_root=spec_root, repo_root=repo_root)
            codes = [e.code for e in errs]
            assert "E620" not in codes


# ---------------------------------------------------------------------------
# R002 — Phantom basename
# ---------------------------------------------------------------------------

class TestR002PhantomBasename:
    def test_phantom_basename_fires_E621(self) -> None:
        """Registered basename not in extraction_paths.json → E621."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_root = os.path.join(tmpdir, "spec")
            repo_root = os.path.join(tmpdir, "toolkit")
            os.makedirs(spec_root)
            os.makedirs(os.path.join(repo_root, "tools"))

            _write(repo_root, "tools/step_order.json", _make_step_order([]))
            # extraction_paths has no entries (only _meta)
            _write(repo_root, "tools/extraction_paths.json", {"_meta": {}})

            registry = _make_registry({
                "04_phantom_file.json": {
                    "step": "04",
                    "arrays": [{"array_path": ".items", "id_field": "item_id", "kind": "item"}],
                }
            })
            _write(repo_root, "tools/entry_key_registry.json", registry)

            errs = run_registry_check(spec_root=spec_root, repo_root=repo_root)
            codes = [e.code for e in errs]
            assert "E621" in codes, f"Expected E621, got: {errs}"

    def test_known_basename_does_not_fire(self) -> None:
        """Basename present in extraction_paths.json → no E621."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_root = os.path.join(tmpdir, "spec")
            repo_root = os.path.join(tmpdir, "toolkit")
            os.makedirs(spec_root)
            os.makedirs(os.path.join(repo_root, "tools"))

            _write(repo_root, "tools/step_order.json", _make_step_order(["04"]))
            _write(repo_root, "tools/extraction_paths.json",
                   _make_extraction_paths(["04_fr_list.json"], step="04"))

            registry = _make_registry({
                "04_fr_list.json": {
                    "step": "04",
                    "arrays": [{"array_path": ".functional_requirements", "id_field": "fr_id", "kind": "fr"}],
                }
            })
            _write(repo_root, "tools/entry_key_registry.json", registry)
            _write(spec_root, "04_fr_list.json", {"functional_requirements": [{"fr_id": "fr-x"}]})

            errs = run_registry_check(spec_root=spec_root, repo_root=repo_root)
            codes = [e.code for e in errs]
            assert "E621" not in codes

    def test_sentinel_entries_do_not_fire(self) -> None:
        """canonical_refs_used / canonical_proposals (sentinel) entries are ignored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_root = os.path.join(tmpdir, "spec")
            repo_root = os.path.join(tmpdir, "toolkit")
            os.makedirs(spec_root)
            os.makedirs(os.path.join(repo_root, "tools"))

            _write(repo_root, "tools/step_order.json", _make_step_order([]))
            _write(repo_root, "tools/extraction_paths.json", {"_meta": {}})

            registry = _make_registry({
                "canonical_refs_used": {"_special": True},
                "canonical_proposals": {"_special": True},
            })
            _write(repo_root, "tools/entry_key_registry.json", registry)

            errs = run_registry_check(spec_root=spec_root, repo_root=repo_root)
            codes = [e.code for e in errs]
            assert "E621" not in codes


# ---------------------------------------------------------------------------
# R003 — Drift detection
# ---------------------------------------------------------------------------

class TestR003Drift:
    def _minimal_registry_with(self, array_path: str, id_field: str) -> dict:
        return _make_registry({
            "04_fr_list.json": {
                "step": "04",
                "arrays": [{"array_path": array_path, "id_field": id_field, "kind": "fr"}],
            }
        })

    def test_array_path_rename_fires_E622(self) -> None:
        """Registered array_path doesn't exist in file → E622."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_root = os.path.join(tmpdir, "spec")
            repo_root = os.path.join(tmpdir, "toolkit")
            os.makedirs(spec_root)
            os.makedirs(os.path.join(repo_root, "tools"))

            _write(repo_root, "tools/step_order.json", _make_step_order(["04"]))
            _write(repo_root, "tools/extraction_paths.json",
                   _make_extraction_paths(["04_fr_list.json"], step="04"))

            # Registry says ".functional_requirements" but file has ".frs"
            _write(repo_root, "tools/entry_key_registry.json",
                   self._minimal_registry_with(".functional_requirements", "fr_id"))
            _write(spec_root, "04_fr_list.json", {"frs": [{"fr_id": "fr-x"}]})

            errs = run_registry_check(spec_root=spec_root, repo_root=repo_root)
            codes = [e.code for e in errs]
            assert "E622" in codes, f"Expected E622 for array_path rename, got: {errs}"

    def test_id_field_rename_fires_E622(self) -> None:
        """Array exists but first entry lacks registered id_field → E622."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_root = os.path.join(tmpdir, "spec")
            repo_root = os.path.join(tmpdir, "toolkit")
            os.makedirs(spec_root)
            os.makedirs(os.path.join(repo_root, "tools"))

            _write(repo_root, "tools/step_order.json", _make_step_order(["04"]))
            _write(repo_root, "tools/extraction_paths.json",
                   _make_extraction_paths(["04_fr_list.json"], step="04"))

            # Registry says "fr_id" but file uses "requirement_id"
            _write(repo_root, "tools/entry_key_registry.json",
                   self._minimal_registry_with(".functional_requirements", "fr_id"))
            _write(spec_root, "04_fr_list.json", {
                "functional_requirements": [{"requirement_id": "req-1", "name": "Test"}]
            })

            errs = run_registry_check(spec_root=spec_root, repo_root=repo_root)
            codes = [e.code for e in errs]
            assert "E622" in codes, f"Expected E622 for id_field rename, got: {errs}"
            msgs = " ".join(e.message for e in errs)
            assert "fr_id" in msgs

    def test_missing_array_fires_E622(self) -> None:
        """Spec file exists but the registered array key is missing → E622."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_root = os.path.join(tmpdir, "spec")
            repo_root = os.path.join(tmpdir, "toolkit")
            os.makedirs(spec_root)
            os.makedirs(os.path.join(repo_root, "tools"))

            _write(repo_root, "tools/step_order.json", _make_step_order(["04"]))
            _write(repo_root, "tools/extraction_paths.json",
                   _make_extraction_paths(["04_fr_list.json"], step="04"))

            _write(repo_root, "tools/entry_key_registry.json",
                   self._minimal_registry_with(".functional_requirements", "fr_id"))
            # File has no 'functional_requirements' at all
            _write(spec_root, "04_fr_list.json", {"title": "FRs"})

            errs = run_registry_check(spec_root=spec_root, repo_root=repo_root)
            codes = [e.code for e in errs]
            assert "E622" in codes, f"Expected E622 for missing array, got: {errs}"

    def test_empty_array_no_error(self) -> None:
        """An empty array cannot drift — no entries to check id_field against."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_root = os.path.join(tmpdir, "spec")
            repo_root = os.path.join(tmpdir, "toolkit")
            os.makedirs(spec_root)
            os.makedirs(os.path.join(repo_root, "tools"))

            _write(repo_root, "tools/step_order.json", _make_step_order(["04"]))
            _write(repo_root, "tools/extraction_paths.json",
                   _make_extraction_paths(["04_fr_list.json"], step="04"))

            _write(repo_root, "tools/entry_key_registry.json",
                   self._minimal_registry_with(".functional_requirements", "fr_id"))
            _write(spec_root, "04_fr_list.json", {"functional_requirements": []})

            errs = run_registry_check(spec_root=spec_root, repo_root=repo_root)
            codes = [e.code for e in errs]
            assert "E622" not in codes

    def test_no_spec_file_skips_drift(self) -> None:
        """If the spec file doesn't exist yet (future step), R003 is skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_root = os.path.join(tmpdir, "spec")
            repo_root = os.path.join(tmpdir, "toolkit")
            os.makedirs(spec_root)
            os.makedirs(os.path.join(repo_root, "tools"))

            _write(repo_root, "tools/step_order.json", _make_step_order(["04"]))
            _write(repo_root, "tools/extraction_paths.json",
                   _make_extraction_paths(["04_fr_list.json"], step="04"))

            _write(repo_root, "tools/entry_key_registry.json",
                   self._minimal_registry_with(".functional_requirements", "fr_id"))
            # No 04_fr_list.json in spec_root

            errs = run_registry_check(spec_root=spec_root, repo_root=repo_root)
            codes = [e.code for e in errs]
            assert "E622" not in codes

    def test_nested_array_missing_fires_E622(self) -> None:
        """Nested array_path missing under first parent → E622."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_root = os.path.join(tmpdir, "spec")
            repo_root = os.path.join(tmpdir, "toolkit")
            os.makedirs(spec_root)
            os.makedirs(os.path.join(repo_root, "tools"))

            _write(repo_root, "tools/step_order.json", _make_step_order(["14"]))
            _write(repo_root, "tools/extraction_paths.json",
                   _make_extraction_paths(["14_roadmap.json"], step="14"))

            registry = _make_registry({
                "14_roadmap.json": {
                    "step": "14",
                    "arrays": [{
                        "array_path": ".milestones",
                        "id_field": "milestone_id",
                        "kind": "milestone",
                        "nested": [{"array_path": ".tasks", "id_field": "task_id", "kind": "task"}],
                    }],
                }
            })
            _write(repo_root, "tools/entry_key_registry.json", registry)
            # Parent entry exists but has no 'tasks' key
            _write(spec_root, "14_roadmap.json", {
                "milestones": [{"milestone_id": "ms-1", "name": "M1"}]
            })

            errs = run_registry_check(spec_root=spec_root, repo_root=repo_root)
            codes = [e.code for e in errs]
            assert "E622" in codes, f"Expected E622 for missing nested array, got: {errs}"

    def test_nested_id_field_mismatch_fires_E622(self) -> None:
        """Nested array exists but first entry lacks registered nested id_field → E622."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_root = os.path.join(tmpdir, "spec")
            repo_root = os.path.join(tmpdir, "toolkit")
            os.makedirs(spec_root)
            os.makedirs(os.path.join(repo_root, "tools"))

            _write(repo_root, "tools/step_order.json", _make_step_order(["14"]))
            _write(repo_root, "tools/extraction_paths.json",
                   _make_extraction_paths(["14_roadmap.json"], step="14"))

            registry = _make_registry({
                "14_roadmap.json": {
                    "step": "14",
                    "arrays": [{
                        "array_path": ".milestones",
                        "id_field": "milestone_id",
                        "kind": "milestone",
                        "nested": [{"array_path": ".tasks", "id_field": "task_id", "kind": "task"}],
                    }],
                }
            })
            _write(repo_root, "tools/entry_key_registry.json", registry)
            # tasks array exists but uses "id" not "task_id"
            _write(spec_root, "14_roadmap.json", {
                "milestones": [
                    {
                        "milestone_id": "ms-1",
                        "name": "M1",
                        "tasks": [{"id": "task-x", "description": "Do something"}]
                    }
                ]
            })

            errs = run_registry_check(spec_root=spec_root, repo_root=repo_root)
            codes = [e.code for e in errs]
            assert "E622" in codes, f"Expected E622 for nested id_field mismatch, got: {errs}"


# ---------------------------------------------------------------------------
# G2 / G3 / G4 — additional drift and library-API contract tests
# ---------------------------------------------------------------------------


class TestG2DriftMissingSpecFile:
    def test_drift_missing_spec_file_is_silently_skipped(self) -> None:
        """G2: registry references a basename whose file is absent on disk.

        Current behaviour (registry_check.py:194–196): the drift check
        ``continue``s when the spec file does not exist (e.g. a future step
        whose artifact hasn't been generated yet). This test pins that
        behaviour so future refactors that change it must update the test
        deliberately.

        Fixture is constructed so R001 (coverage) and R002 (phantom basename)
        cannot fire — only R003 is exercised, and it must NOT emit E622.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_root = os.path.join(tmpdir, "spec")
            repo_root = os.path.join(tmpdir, "toolkit")
            os.makedirs(spec_root)
            os.makedirs(os.path.join(repo_root, "tools"))

            # 99 is in step_order AND registered → R001 satisfied.
            _write(repo_root, "tools/step_order.json", _make_step_order(["99"]))
            # Basename declared in extraction_paths → R002 satisfied.
            _write(repo_root, "tools/extraction_paths.json",
                   _make_extraction_paths(["99_phantom.json"], step="99"))

            registry = _make_registry({
                "99_phantom.json": {
                    "step": "99",
                    "arrays": [{"array_path": ".items", "id_field": "item_id", "kind": "item"}],
                }
            })
            _write(repo_root, "tools/entry_key_registry.json", registry)
            # Deliberately DO NOT create 99_phantom.json — drift must be skipped.

            errs = run_registry_check(spec_root=spec_root, repo_root=repo_root)
            codes = [e.code for e in errs]
            assert "E622" not in codes, (
                f"Expected no E622 (missing-spec-file is silently skipped), got: {errs}"
            )


class TestG3DriftArrayPathNotAList:
    def test_drift_array_path_is_object_fires_E622(self) -> None:
        """G3: array_path exists but is an object, not an array → E622.

        Pins the "exists but is not an array" branch at registry_check.py:222.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_root = os.path.join(tmpdir, "spec")
            repo_root = os.path.join(tmpdir, "toolkit")
            os.makedirs(spec_root)
            os.makedirs(os.path.join(repo_root, "tools"))

            _write(repo_root, "tools/step_order.json", _make_step_order(["04"]))
            _write(repo_root, "tools/extraction_paths.json",
                   _make_extraction_paths(["04_fr_list.json"], step="04"))

            registry = _make_registry({
                "04_fr_list.json": {
                    "step": "04",
                    "arrays": [{"array_path": ".functional_requirements", "id_field": "fr_id", "kind": "fr"}],
                }
            })
            _write(repo_root, "tools/entry_key_registry.json", registry)
            # functional_requirements is an OBJECT, not a list.
            _write(spec_root, "04_fr_list.json", {"functional_requirements": {}})

            errs = run_registry_check(spec_root=spec_root, repo_root=repo_root)
            codes = [e.code for e in errs]
            assert "E622" in codes, f"Expected E622 for non-array array_path, got: {errs}"
            # Message must clearly identify the type mismatch.
            msgs = " ".join(e.message for e in errs)
            assert "not an array" in msgs
            assert "dict" in msgs


class TestG4ResolvePointersRequiresSpecRoot:
    def test_resolve_pointers_raises_TypeError_when_repo_root_omitted(self) -> None:
        """G4: library API contract — ``resolve_pointers`` requires ``repo_root``.

        Pins the post-Task-1 fix: the previous ``spec_root=""`` default
        propagated empty strings into the loader, raising a confusing
        ``FileNotFoundError`` at runtime. Now ``repo_root`` is a keyword-only
        required parameter, so omitting it raises ``TypeError`` at call time.
        (Renamed from spec_root → repo_root in W3-T4.)
        """
        from specdev_tools.core.json_utils import resolve_pointers

        ptr = {"file": "some_spec.json", "id": "fr-x"}
        try:
            resolve_pointers([ptr])  # type: ignore[call-arg]
        except TypeError as exc:
            assert "repo_root" in str(exc), (
                f"TypeError should mention 'repo_root', got: {exc!r}"
            )
        else:
            raise AssertionError(
                "resolve_pointers([...]) without repo_root must raise TypeError"
            )


# ---------------------------------------------------------------------------
# --json envelope shape
# ---------------------------------------------------------------------------

class TestJsonEnvelopeShape:
    def test_json_output_matches_spec_error_format(self) -> None:
        """Errors returned by run_registry_check are SpecError objects with code/message.

        Uses R002 / E621 (phantom basename) to trigger an error — R001 / E620
        was moved to toolkit unit tests after W6 and no longer fires at host-runtime.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_root = os.path.join(tmpdir, "spec")
            repo_root = os.path.join(tmpdir, "toolkit")
            os.makedirs(spec_root)
            os.makedirs(os.path.join(repo_root, "tools"))

            _write(repo_root, "tools/step_order.json", _make_step_order([]))
            # extraction_paths has no entries — basename will be phantom
            _write(repo_root, "tools/extraction_paths.json", {"_meta": {}})
            # Registry references a basename not in extraction_paths → E621
            registry = _make_registry({
                "05_interface_contracts.json": {
                    "step": "05",
                    "arrays": [{"array_path": ".apis", "id_field": "api_id", "kind": "api"}],
                }
            })
            _write(repo_root, "tools/entry_key_registry.json", registry)

            errs = run_registry_check(spec_root=spec_root, repo_root=repo_root)
            # Should fire E621 for phantom basename
            assert any(e.code == "E621" for e in errs), (
                f"Expected E621 (phantom basename), got: {[e.code for e in errs]}"
            )
            # All errors have message strings
            for err in errs:
                assert isinstance(err.message, str) and len(err.message) > 0

    def test_format_errors_json_produces_valid_envelope(self) -> None:
        """format_errors_json produces a JSON-serialisable envelope with required keys."""
        from specdev_tools.core.json_output import format_errors_json
        from specdev_tools.core.errors import ensure_spec_errors

        with tempfile.TemporaryDirectory() as tmpdir:
            spec_root = os.path.join(tmpdir, "spec")
            repo_root = os.path.join(tmpdir, "toolkit")
            os.makedirs(spec_root)
            os.makedirs(os.path.join(repo_root, "tools"))

            _write(repo_root, "tools/step_order.json", _make_step_order(["05"]))
            _write(repo_root, "tools/extraction_paths.json", {"_meta": {}})
            _write(repo_root, "tools/entry_key_registry.json", _make_registry({}))

            errs = run_registry_check(spec_root=spec_root, repo_root=repo_root)
            spec_errs = ensure_spec_errors(errs)
            envelope_str = format_errors_json(spec_errs, context={"command": "registry-check"})
            envelope = json.loads(envelope_str)

            assert "status" in envelope
            assert "error_count" in envelope
            assert "warning_count" in envelope
            assert "errors" in envelope
            assert envelope["status"] in ("PASS", "WARN", "FAIL")
            for err_obj in envelope["errors"]:
                assert "code" in err_obj
                assert "message" in err_obj
                assert "severity" in err_obj


# ---------------------------------------------------------------------------
# spec-check wiring
# ---------------------------------------------------------------------------

class TestSpecCheckWiring:
    def test_registry_check_skip_when_no_registry(self) -> None:
        """spec-check reports registry-check as SKIP when entry_key_registry.json is absent."""
        from specdev_tools.validation.spec_check import _run_checks

        with tempfile.TemporaryDirectory() as tmpdir:
            # Minimal spec_dir — no registry file
            spec_dir = tmpdir
            repo_root = os.path.join(tmpdir, "toolkit")
            os.makedirs(os.path.join(repo_root, "tools"))
            _write(repo_root, "tools/step_order.json", _make_step_order([]))

            checks = _run_checks(repo_root=repo_root, spec_dir=spec_dir)
            rc = checks.get("registry-check", {})
            assert rc.get("status") == "SKIP", f"Expected SKIP, got: {rc}"

    def test_registry_check_in_checks_output_when_registry_present(self) -> None:
        """spec-check includes registry-check with PASS when registry is clean."""
        from specdev_tools.validation.spec_check import _run_checks

        with tempfile.TemporaryDirectory() as tmpdir:
            spec_dir = tmpdir
            repo_root = os.path.join(tmpdir, "toolkit")
            os.makedirs(os.path.join(repo_root, "tools"))
            _write(repo_root, "tools/step_order.json", _make_step_order([]))
            _write(repo_root, "tools/extraction_paths.json", {"_meta": {}})
            # Write registry to toolkit-side tools/ directory
            _write(repo_root, "tools/entry_key_registry.json", _make_registry(
                {},
                steps_without_entry_arrays={}
            ))

            checks = _run_checks(repo_root=repo_root, spec_dir=spec_dir)
            rc = checks.get("registry-check", {})
            assert rc.get("status") in ("PASS", "WARN"), f"Expected PASS/WARN, got: {rc}"

    def test_registry_check_fail_propagates_to_spec_check(self) -> None:
        """When registry-check fires E621 (phantom basename), spec-check includes it.

        Previously this test asserted E620. After W6, R001 was moved to toolkit
        unit tests and E620 no longer fires at host-runtime. This test now uses
        E621 (phantom basename) to verify the propagation path is intact.
        """
        from specdev_tools.validation.spec_check import run_spec_check

        import io
        import sys

        with tempfile.TemporaryDirectory() as tmpdir:
            spec_dir = tmpdir
            repo_root = os.path.join(tmpdir, "toolkit")
            os.makedirs(os.path.join(repo_root, "tools"))
            _write(repo_root, "tools/step_order.json", _make_step_order(["04"]))
            # extraction_paths has no entries → registered basename becomes phantom
            _write(repo_root, "tools/extraction_paths.json", {"_meta": {}})
            # Registry references a basename not in extraction_paths → E621
            registry = _make_registry({
                "04_fr_list.json": {
                    "step": "04",
                    "arrays": [{"array_path": ".functional_requirements", "id_field": "fr_id", "kind": "fr"}],
                }
            })
            _write(repo_root, "tools/entry_key_registry.json", registry)

            # Suppress stderr output from _print_summary
            captured = io.StringIO()
            orig_stderr = sys.stderr
            sys.stderr = captured
            try:
                errs = run_spec_check(repo_root=repo_root, spec_dir=spec_dir)
            finally:
                sys.stderr = orig_stderr

            codes = [e.code for e in errs]
            assert "E621" in codes, (
                f"Expected E621 (phantom basename) in combined spec-check errors, got: {codes}"
            )

    def test_run_spec_check_json_skip_check_has_no_findings(self) -> None:
        """DEVSPEC-10: SKIP checks in run_spec_check_json must NOT have a findings key."""
        from specdev_tools.validation.spec_check import run_spec_check_json

        import io
        import sys

        with tempfile.TemporaryDirectory() as tmpdir:
            spec_dir = tmpdir
            repo_root = os.path.join(tmpdir, "toolkit")
            os.makedirs(os.path.join(repo_root, "tools"))
            _write(repo_root, "tools/step_order.json", _make_step_order([]))
            # No registry → registry-check will be SKIP

            captured = io.StringIO()
            sys.stderr = captured
            try:
                _, ctx = run_spec_check_json(repo_root=repo_root, spec_dir=spec_dir)
            finally:
                sys.stderr = sys.__stderr__

            checks = ctx["checks"]
            skip_checks = {name: info for name, info in checks.items() if info.get("status") == "SKIP"}
            assert skip_checks, f"Expected at least one SKIP check, got: {list(checks.keys())}"
            for name, info in skip_checks.items():
                assert "findings" not in info, (
                    f"SKIP check '{name}' must not have findings key, got: {info}"
                )

    def test_run_spec_check_json_non_skip_check_has_findings(self) -> None:
        """DEVSPEC-10: non-SKIP checks in run_spec_check_json must have a findings key (even when empty)."""
        from specdev_tools.validation.spec_check import run_spec_check_json

        import io
        import sys

        with tempfile.TemporaryDirectory() as tmpdir:
            spec_dir = tmpdir
            repo_root = os.path.join(tmpdir, "toolkit")
            os.makedirs(os.path.join(repo_root, "tools"))
            _write(repo_root, "tools/step_order.json", _make_step_order([]))
            _write(repo_root, "tools/extraction_paths.json", {"_meta": {}})
            # Write a clean registry so registry-check runs (not SKIP) and passes
            _write(spec_dir, "entry_key_registry.json", _make_registry(
                {},
                steps_without_entry_arrays={}
            ))

            captured = io.StringIO()
            sys.stderr = captured
            try:
                _, ctx = run_spec_check_json(repo_root=repo_root, spec_dir=spec_dir)
            finally:
                sys.stderr = sys.__stderr__

            checks = ctx["checks"]
            non_skip = {name: info for name, info in checks.items() if info.get("status") != "SKIP"}
            assert non_skip, f"Expected at least one non-SKIP check, got: {list(checks.keys())}"
            for name, info in non_skip.items():
                assert "findings" in info, (
                    f"Non-SKIP check '{name}' must have findings key, got: {info}"
                )
                assert isinstance(info["findings"], list), (
                    f"findings must be a list for check '{name}', got: {type(info['findings'])}"
                )

    def test_run_spec_check_json_findings_contain_error_to_dict_shape(self) -> None:
        """DEVSPEC-10: non-empty findings in run_spec_check_json have code/message/severity keys.

        Uses R002 / E621 (phantom basename) to trigger a finding — R001 / E620
        was moved to toolkit unit tests after W6 and no longer fires at host-runtime.
        """
        from specdev_tools.validation.spec_check import run_spec_check_json

        import io
        import sys

        with tempfile.TemporaryDirectory() as tmpdir:
            spec_dir = tmpdir
            repo_root = os.path.join(tmpdir, "toolkit")
            os.makedirs(os.path.join(repo_root, "tools"))
            _write(repo_root, "tools/step_order.json", _make_step_order(["04"]))
            # extraction_paths has no entries → registered basename becomes phantom
            _write(repo_root, "tools/extraction_paths.json", {"_meta": {}})
            # Registry references a basename not in extraction_paths → E621
            registry = _make_registry({
                "04_fr_list.json": {
                    "step": "04",
                    "arrays": [{"array_path": ".functional_requirements", "id_field": "fr_id", "kind": "fr"}],
                }
            })
            _write(repo_root, "tools/entry_key_registry.json", registry)

            captured = io.StringIO()
            sys.stderr = captured
            try:
                _, ctx = run_spec_check_json(repo_root=repo_root, spec_dir=spec_dir)
            finally:
                sys.stderr = sys.__stderr__

            checks = ctx["checks"]
            # Find the registry-check which should have an E621 finding
            rc = checks.get("registry-check", {})
            assert rc.get("status") != "SKIP", f"registry-check should not be SKIP, got: {rc}"
            assert "findings" in rc, f"registry-check must have findings, got: {rc}"
            findings = rc["findings"]
            assert len(findings) >= 1, (
                f"Expected E621 (phantom basename) finding, got: {findings}"
            )
            finding = findings[0]
            assert "code" in finding, f"finding must have 'code' key, got: {finding}"
            assert "message" in finding, f"finding must have 'message' key, got: {finding}"
            assert "severity" in finding, f"finding must have 'severity' key, got: {finding}"
            assert finding["severity"] == "error", (
                f"E621 must have severity=error, got: {finding['severity']}"
            )


# ---------------------------------------------------------------------------
# R004 — Unregistered arrays (W614)
# ---------------------------------------------------------------------------


def _make_registry_with_sentinels(entries: dict[str, Any], sentinels: list[str] | None = None) -> dict:
    """Create a registry doc with _sentinels field."""
    result = _make_registry(entries)
    result["_sentinels"] = sentinels if sentinels is not None else ["canonical_refs_used", "canonical_proposals"]
    return result


class TestR004UnregisteredArrays:
    """R004 / W614 UNREGISTERED_ARRAY: host spec has id-bearing array absent from registry."""

    def test_unregistered_array_fires_W614(self) -> None:
        """Array with *_id items not in registry emits W614."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_root = os.path.join(tmpdir, "spec")
            repo_root = os.path.join(tmpdir, "toolkit")
            os.makedirs(spec_root)
            os.makedirs(os.path.join(repo_root, "tools"))

            # Registry has no arrays for the spec file (empty arrays list)
            registry = _make_registry_with_sentinels({
                "04_fr_list.json": {
                    "step": "04",
                    "arrays": [],
                }
            })
            _write(repo_root, "tools/entry_key_registry.json", registry)
            # Spec file has an id-bearing array that isn't registered
            _write(spec_root, "04_fr_list.json", {
                "functional_requirements": [{"fr_id": "fr-x", "title": "Login"}],
            })

            errs = run_registry_check(spec_root=spec_root, repo_root=repo_root)
            codes = [e.code for e in errs]
            assert "W614" in codes, f"Expected W614, got: {errs}"
            w614 = [e for e in errs if e.code == "W614"][0]
            assert "04_fr_list.json:.functional_requirements" in w614.message

    def test_registered_array_does_not_fire_W614(self) -> None:
        """Array whose (basename, array_path) is in registry → no W614."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_root = os.path.join(tmpdir, "spec")
            repo_root = os.path.join(tmpdir, "toolkit")
            os.makedirs(spec_root)
            os.makedirs(os.path.join(repo_root, "tools"))

            registry = _make_registry_with_sentinels({
                "04_fr_list.json": {
                    "step": "04",
                    "arrays": [{"array_path": ".functional_requirements", "id_field": "fr_id", "kind": "fr"}],
                }
            })
            _write(repo_root, "tools/entry_key_registry.json", registry)
            _write(spec_root, "04_fr_list.json", {
                "functional_requirements": [{"fr_id": "fr-x", "title": "Login"}],
            })

            errs = run_registry_check(spec_root=spec_root, repo_root=repo_root)
            codes = [e.code for e in errs]
            assert "W614" not in codes, f"Unexpected W614: {errs}"

    def test_sentinel_arrays_excluded_from_W614(self) -> None:
        """Sentinel arrays (canonical_refs_used, canonical_proposals) → no W614."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_root = os.path.join(tmpdir, "spec")
            repo_root = os.path.join(tmpdir, "toolkit")
            os.makedirs(spec_root)
            os.makedirs(os.path.join(repo_root, "tools"))

            registry = _make_registry_with_sentinels({})
            _write(repo_root, "tools/entry_key_registry.json", registry)
            # Spec file has sentinel arrays with id-like fields
            _write(spec_root, "04_fr_list.json", {
                "canonical_refs_used": [{"id": "cap-x"}],
                "canonical_proposals": [{"id": "term-y"}],
            })

            errs = run_registry_check(spec_root=spec_root, repo_root=repo_root)
            codes = [e.code for e in errs]
            assert "W614" not in codes, f"Sentinel arrays should not trigger W614: {errs}"

    def test_trace_array_excluded_from_W614(self) -> None:
        """TraceRef array (.trace with bare 'id') → no W614."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_root = os.path.join(tmpdir, "spec")
            repo_root = os.path.join(tmpdir, "toolkit")
            os.makedirs(spec_root)
            os.makedirs(os.path.join(repo_root, "tools"))

            registry = _make_registry_with_sentinels({})
            _write(repo_root, "tools/entry_key_registry.json", registry)
            # Spec file has a .trace array with bare 'id' field (traceRef pattern)
            _write(spec_root, "02a_delivery_baseline.json", {
                "trace": [{"id": "charter-v1", "type": "charter-goal", "note": "..."}],
            })

            errs = run_registry_check(spec_root=spec_root, repo_root=repo_root)
            codes = [e.code for e in errs]
            assert "W614" not in codes, f"TraceRef .trace array should not trigger W614: {errs}"

    def test_array_without_id_field_excluded_from_W614(self) -> None:
        """Array whose first item has no *_id or 'id' field → no W614."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_root = os.path.join(tmpdir, "spec")
            repo_root = os.path.join(tmpdir, "toolkit")
            os.makedirs(spec_root)
            os.makedirs(os.path.join(repo_root, "tools"))

            registry = _make_registry_with_sentinels({})
            _write(repo_root, "tools/entry_key_registry.json", registry)
            # Spec file has an array whose items have no id-like field
            _write(spec_root, "00_charter.json", {
                "tags": [{"name": "mvp", "color": "blue"}],
            })

            errs = run_registry_check(spec_root=spec_root, repo_root=repo_root)
            codes = [e.code for e in errs]
            assert "W614" not in codes, f"Array without id field should not trigger W614: {errs}"

    def test_W614_severity_is_warning_not_error(self) -> None:
        """W614 is a warning (W-prefix), not an error (E-prefix)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_root = os.path.join(tmpdir, "spec")
            repo_root = os.path.join(tmpdir, "toolkit")
            os.makedirs(spec_root)
            os.makedirs(os.path.join(repo_root, "tools"))

            registry = _make_registry_with_sentinels({
                "04_fr_list.json": {
                    "step": "04",
                    "arrays": [],
                }
            })
            _write(repo_root, "tools/entry_key_registry.json", registry)
            _write(spec_root, "04_fr_list.json", {
                "functional_requirements": [{"fr_id": "fr-x"}],
            })

            errs = run_registry_check(spec_root=spec_root, repo_root=repo_root)
            w614_errs = [e for e in errs if e.code == "W614"]
            assert w614_errs, "Expected at least one W614"
            for err in w614_errs:
                # W-prefix codes are warnings
                assert err.code.startswith("W"), (
                    f"W614 should have W-prefix, got code: {err.code}"
                )

    def test_unknown_file_does_not_fire_W614(self) -> None:
        """Spec file with no registry entry and no id-bearing arrays → no W614."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_root = os.path.join(tmpdir, "spec")
            repo_root = os.path.join(tmpdir, "toolkit")
            os.makedirs(spec_root)
            os.makedirs(os.path.join(repo_root, "tools"))

            # Registry with no entries
            registry = _make_registry_with_sentinels({})
            _write(repo_root, "tools/entry_key_registry.json", registry)
            # Spec file has no id-bearing arrays
            _write(spec_root, "10_governance.json", {
                "governance": {"process": "iterative"},
                "owner": "product",
            })

            errs = run_registry_check(spec_root=spec_root, repo_root=repo_root)
            codes = [e.code for e in errs]
            assert "W614" not in codes, f"Non-id-bearing arrays should not trigger W614: {errs}"
