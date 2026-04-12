"""Tests for R9 coverage threshold enforcement in matrix.py.

Covers _check_coverage_thresholds and _load_coverage_thresholds:
- Coverage above threshold passes (no W592/E592)
- Coverage below threshold in warn mode emits W592
- Coverage below threshold in error mode emits E592
- Missing step_order.json file → _MISSING_FILE sentinel → graceful skip
- step_order.json without coverage_thresholds key → None → defaults apply
- Zero fr_total produces no errors (avoids division by zero)
- _DEFAULT_COVERAGE_THRESHOLDS and _MISSING_FILE sentinel contracts
"""
import json
import os
import tempfile
import unittest
from pathlib import Path

from specdev_tools.validation.matrix import (
    _check_coverage_thresholds,
    _DEFAULT_COVERAGE_THRESHOLDS,
    _load_coverage_thresholds,
    _MISSING_FILE,
    build_trace_matrix,
)


class TestLoadCoverageThresholds(unittest.TestCase):
    """Tests for _load_coverage_thresholds helper."""

    def test_returns_thresholds_from_step_order(self):
        """Loads coverage_thresholds dict from tools/step_order.json."""
        with tempfile.TemporaryDirectory() as repo_root:
            tools_dir = os.path.join(repo_root, "tools")
            os.makedirs(tools_dir)
            step_order = {
                "steps": ["00"],
                "coverage_thresholds": {
                    "fr_coverage": 80,
                    "mode": "warn",
                },
            }
            with open(os.path.join(tools_dir, "step_order.json"), "w") as f:
                json.dump(step_order, f)

            result = _load_coverage_thresholds(repo_root)
            assert isinstance(result, dict)
            self.assertEqual(result["fr_coverage"], 80)
            self.assertEqual(result["mode"], "warn")

    def test_returns_missing_file_sentinel_when_file_absent(self):
        """Returns _MISSING_FILE sentinel when step_order.json does not exist."""
        with tempfile.TemporaryDirectory() as repo_root:
            result = _load_coverage_thresholds(repo_root)
            self.assertIs(result, _MISSING_FILE)

    def test_returns_none_when_key_absent(self):
        """Returns None when coverage_thresholds key is absent from step_order.json."""
        with tempfile.TemporaryDirectory() as repo_root:
            tools_dir = os.path.join(repo_root, "tools")
            os.makedirs(tools_dir)
            step_order = {"steps": ["00"]}
            with open(os.path.join(tools_dir, "step_order.json"), "w") as f:
                json.dump(step_order, f)

            result = _load_coverage_thresholds(repo_root)
            self.assertIsNone(result)

    def test_returns_missing_file_sentinel_on_invalid_json(self):
        """Returns _MISSING_FILE sentinel when step_order.json contains invalid JSON."""
        with tempfile.TemporaryDirectory() as repo_root:
            tools_dir = os.path.join(repo_root, "tools")
            os.makedirs(tools_dir)
            with open(os.path.join(tools_dir, "step_order.json"), "w") as f:
                f.write("{not valid json")

            result = _load_coverage_thresholds(repo_root)
            self.assertIs(result, _MISSING_FILE)


def _make_repo_with_thresholds(repo_root, fr_coverage=80, mode="warn"):
    """Helper: write a minimal step_order.json with coverage_thresholds."""
    tools_dir = os.path.join(repo_root, "tools")
    os.makedirs(tools_dir, exist_ok=True)
    step_order = {
        "steps": ["00"],
        "coverage_thresholds": {
            "fr_coverage": fr_coverage,
            "mode": mode,
        },
    }
    with open(os.path.join(tools_dir, "step_order.json"), "w") as f:
        json.dump(step_order, f)


class TestCheckCoverageThresholds(unittest.TestCase):
    """Tests for _check_coverage_thresholds enforcement logic."""

    # ------------------------------------------------------------------
    # 1. Coverage above threshold passes (no W592/E592)
    # ------------------------------------------------------------------
    def test_above_threshold_no_errors(self):
        """100% coverage with 80% threshold produces no diagnostics."""
        with tempfile.TemporaryDirectory() as repo_root:
            _make_repo_with_thresholds(repo_root, fr_coverage=80, mode="warn")
            coverage = {"fr_total": 10, "fr_with_api": 10}
            errors = _check_coverage_thresholds(coverage, repo_root)
            self.assertEqual(errors, [])

    def test_exactly_at_threshold_no_errors(self):
        """Coverage exactly at threshold (80%) produces no diagnostics."""
        with tempfile.TemporaryDirectory() as repo_root:
            _make_repo_with_thresholds(repo_root, fr_coverage=80, mode="warn")
            coverage = {"fr_total": 10, "fr_with_api": 8}
            errors = _check_coverage_thresholds(coverage, repo_root)
            self.assertEqual(errors, [])

    def test_above_threshold_error_mode_no_errors(self):
        """100% coverage in error mode also produces no diagnostics."""
        with tempfile.TemporaryDirectory() as repo_root:
            _make_repo_with_thresholds(repo_root, fr_coverage=80, mode="error")
            coverage = {"fr_total": 5, "fr_with_api": 5}
            errors = _check_coverage_thresholds(coverage, repo_root)
            self.assertEqual(errors, [])

    # ------------------------------------------------------------------
    # 2. Coverage below threshold in warn mode emits W592
    # ------------------------------------------------------------------
    def test_below_threshold_warn_mode_emits_w592(self):
        """50% coverage with 80% threshold in warn mode produces W592."""
        with tempfile.TemporaryDirectory() as repo_root:
            _make_repo_with_thresholds(repo_root, fr_coverage=80, mode="warn")
            coverage = {"fr_total": 10, "fr_with_api": 5}
            errors = _check_coverage_thresholds(coverage, repo_root)
            self.assertEqual(len(errors), 1)
            self.assertIn("W592", errors[0].render())
            self.assertIn("COVERAGE_THRESHOLD_WARN", errors[0].render())
            self.assertIn("fr_coverage", errors[0].render())
            self.assertIn("50.0%", errors[0].render())
            self.assertIn("80%", errors[0].render())

    def test_below_threshold_warn_mode_zero_coverage(self):
        """0% coverage in warn mode still produces W592."""
        with tempfile.TemporaryDirectory() as repo_root:
            _make_repo_with_thresholds(repo_root, fr_coverage=80, mode="warn")
            coverage = {"fr_total": 5, "fr_with_api": 0}
            errors = _check_coverage_thresholds(coverage, repo_root)
            self.assertEqual(len(errors), 1)
            self.assertIn("W592", errors[0].render())
            self.assertIn("0.0%", errors[0].render())

    # ------------------------------------------------------------------
    # 3. Coverage below threshold in error mode emits E592
    # ------------------------------------------------------------------
    def test_below_threshold_error_mode_emits_e592(self):
        """50% coverage with 80% threshold in error mode produces E592."""
        with tempfile.TemporaryDirectory() as repo_root:
            _make_repo_with_thresholds(repo_root, fr_coverage=80, mode="error")
            coverage = {"fr_total": 10, "fr_with_api": 5}
            errors = _check_coverage_thresholds(coverage, repo_root)
            self.assertEqual(len(errors), 1)
            self.assertIn("E592", errors[0].render())
            self.assertIn("COVERAGE_THRESHOLD_BREACH", errors[0].render())
            self.assertIn("fr_coverage", errors[0].render())

    def test_below_threshold_error_mode_just_under(self):
        """79.9% coverage with 80% threshold in error mode produces E592."""
        with tempfile.TemporaryDirectory() as repo_root:
            # 799 out of 1000 = 79.9%
            _make_repo_with_thresholds(repo_root, fr_coverage=80, mode="error")
            coverage = {"fr_total": 1000, "fr_with_api": 799}
            errors = _check_coverage_thresholds(coverage, repo_root)
            self.assertEqual(len(errors), 1)
            self.assertIn("E592", errors[0].render())

    # ------------------------------------------------------------------
    # 4. Missing config: file absent → skip; key absent → defaults apply
    # ------------------------------------------------------------------
    def test_missing_step_order_file_no_errors(self):
        """No step_order.json means no config, so no errors."""
        with tempfile.TemporaryDirectory() as repo_root:
            coverage = {"fr_total": 10, "fr_with_api": 0}
            errors = _check_coverage_thresholds(coverage, repo_root)
            self.assertEqual(errors, [])

    def test_missing_coverage_thresholds_key_uses_defaults(self):
        """step_order.json without coverage_thresholds key applies defaults (80%, warn)."""
        with tempfile.TemporaryDirectory() as repo_root:
            tools_dir = os.path.join(repo_root, "tools")
            os.makedirs(tools_dir)
            with open(os.path.join(tools_dir, "step_order.json"), "w") as f:
                json.dump({"steps": ["00"]}, f)
            coverage = {"fr_total": 10, "fr_with_api": 0}
            errors = _check_coverage_thresholds(coverage, repo_root)
            self.assertEqual(len(errors), 1)
            self.assertIn("W592", errors[0].render())
            self.assertIn("COVERAGE_THRESHOLD_WARN", errors[0].render())
            self.assertIn("0.0%", errors[0].render())
            self.assertIn("80%", errors[0].render())

    def test_default_mode_is_warn(self):
        """When mode is absent from config, defaults to warn (W592, not E592)."""
        with tempfile.TemporaryDirectory() as repo_root:
            tools_dir = os.path.join(repo_root, "tools")
            os.makedirs(tools_dir)
            step_order = {
                "steps": ["00"],
                "coverage_thresholds": {
                    "fr_coverage": 80,
                    # mode intentionally omitted
                },
            }
            with open(os.path.join(tools_dir, "step_order.json"), "w") as f:
                json.dump(step_order, f)
            coverage = {"fr_total": 10, "fr_with_api": 5}
            errors = _check_coverage_thresholds(coverage, repo_root)
            self.assertEqual(len(errors), 1)
            self.assertIn("W592", errors[0].render())
            self.assertNotIn("E592", errors[0].render())

    # ------------------------------------------------------------------
    # 5. Zero fr_total produces no errors (avoids division by zero)
    # ------------------------------------------------------------------
    def test_zero_fr_total_no_errors(self):
        """fr_total=0 short-circuits with no errors (no division by zero)."""
        with tempfile.TemporaryDirectory() as repo_root:
            _make_repo_with_thresholds(repo_root, fr_coverage=80, mode="error")
            coverage = {"fr_total": 0, "fr_with_api": 0}
            errors = _check_coverage_thresholds(coverage, repo_root)
            self.assertEqual(errors, [])

    def test_zero_fr_total_with_warn_mode(self):
        """fr_total=0 in warn mode also produces no errors."""
        with tempfile.TemporaryDirectory() as repo_root:
            _make_repo_with_thresholds(repo_root, fr_coverage=80, mode="warn")
            coverage = {"fr_total": 0, "fr_with_api": 0}
            errors = _check_coverage_thresholds(coverage, repo_root)
            self.assertEqual(errors, [])

    def test_missing_fr_total_key_defaults_to_zero(self):
        """Coverage dict missing fr_total key defaults to 0, no errors."""
        with tempfile.TemporaryDirectory() as repo_root:
            _make_repo_with_thresholds(repo_root, fr_coverage=80, mode="error")
            coverage = {}
            errors = _check_coverage_thresholds(coverage, repo_root)
            self.assertEqual(errors, [])


class TestSentinelsAndDefaults(unittest.TestCase):
    """Tests for _MISSING_FILE sentinel and _DEFAULT_COVERAGE_THRESHOLDS constants."""

    def test_missing_file_sentinel_is_not_none(self):
        """_MISSING_FILE is a unique sentinel distinct from None."""
        self.assertIsNotNone(_MISSING_FILE)
        self.assertIsNot(_MISSING_FILE, None)

    def test_default_coverage_thresholds_values(self):
        """_DEFAULT_COVERAGE_THRESHOLDS equals {'fr_coverage': 80, 'mode': 'warn'}."""
        self.assertEqual(
            _DEFAULT_COVERAGE_THRESHOLDS,
            {"fr_coverage": 80, "mode": "warn"},
        )


class TestMilestoneCoverageInMatrixOutput(unittest.TestCase):
    """Tests that build_trace_matrix returns milestone_coverage when Step 14 data is present."""

    def _write_spec_file(self, spec_dir, filename, data):
        path = os.path.join(spec_dir, filename)
        with open(path, "w") as f:
            json.dump(data, f)
        return path

    def test_milestone_coverage_key_present_when_step14_has_fr_refs(self):
        """milestone_coverage key exists in result when Step 14 artifact with fr_refs is present."""
        with tempfile.TemporaryDirectory() as repo_root:
            spec_dir = os.path.join(repo_root, "spec")
            os.makedirs(spec_dir)

            # Minimal Step 14 artifact with milestone-level fr_refs
            roadmap = {
                "$schema": "https://example.com/schema/14-roadmap.json",
                "milestones": [
                    {
                        "milestone_id": "ms-v1",
                        "fr_refs": ["fr-login", "fr-auth"],
                        "tasks": [],
                    }
                ],
            }
            self._write_spec_file(spec_dir, "14_roadmap.json", roadmap)

            result = build_trace_matrix(repo_root, spec_dir)
            self.assertIn("milestone_coverage", result)

    def test_milestone_coverage_maps_frs_to_milestone_ids(self):
        """FR IDs map to the correct milestone IDs in milestone_coverage."""
        with tempfile.TemporaryDirectory() as repo_root:
            spec_dir = os.path.join(repo_root, "spec")
            os.makedirs(spec_dir)

            roadmap = {
                "$schema": "https://example.com/schema/14-roadmap.json",
                "milestones": [
                    {
                        "milestone_id": "ms-v1",
                        "fr_refs": ["fr-login", "fr-auth"],
                        "tasks": [],
                    },
                    {
                        "milestone_id": "ms-v2",
                        "fr_refs": ["fr-auth"],
                        "tasks": [],
                    },
                ],
            }
            self._write_spec_file(spec_dir, "14_roadmap.json", roadmap)

            result = build_trace_matrix(repo_root, spec_dir)
            mc = result.get("milestone_coverage", {})
            self.assertEqual(mc.get("fr-login"), ["ms-v1"])
            self.assertEqual(sorted(mc.get("fr-auth", [])), ["ms-v1", "ms-v2"])

    def test_milestone_coverage_includes_task_level_fr_refs(self):
        """FR refs at task level within milestones are also included in milestone_coverage."""
        with tempfile.TemporaryDirectory() as repo_root:
            spec_dir = os.path.join(repo_root, "spec")
            os.makedirs(spec_dir)

            roadmap = {
                "$schema": "https://example.com/schema/14_roadmap.json",
                "milestones": [
                    {
                        "milestone_id": "ms-v1",
                        "fr_refs": [],
                        "tasks": [
                            {"task_id": "t-1", "fr_refs": ["fr-login"]},
                            {"task_id": "t-2", "fr_refs": ["fr-signup"]},
                        ],
                    }
                ],
            }
            self._write_spec_file(spec_dir, "14_roadmap.json", roadmap)

            result = build_trace_matrix(repo_root, spec_dir)
            mc = result.get("milestone_coverage", {})
            self.assertEqual(mc.get("fr-login"), ["ms-v1"])
            self.assertEqual(mc.get("fr-signup"), ["ms-v1"])

    def test_milestone_coverage_absent_when_no_step14(self):
        """milestone_coverage key is absent when no Step 14 artifact is present."""
        with tempfile.TemporaryDirectory() as repo_root:
            spec_dir = os.path.join(repo_root, "spec")
            os.makedirs(spec_dir)

            result = build_trace_matrix(repo_root, spec_dir)
            self.assertNotIn("milestone_coverage", result)

    def test_milestone_coverage_sorted_milestone_ids(self):
        """Milestone IDs in milestone_coverage values are sorted."""
        with tempfile.TemporaryDirectory() as repo_root:
            spec_dir = os.path.join(repo_root, "spec")
            os.makedirs(spec_dir)

            roadmap = {
                "$schema": "https://example.com/schema/14-roadmap.json",
                "milestones": [
                    {"milestone_id": "ms-z", "fr_refs": ["fr-x"], "tasks": []},
                    {"milestone_id": "ms-a", "fr_refs": ["fr-x"], "tasks": []},
                    {"milestone_id": "ms-m", "fr_refs": ["fr-x"], "tasks": []},
                ],
            }
            self._write_spec_file(spec_dir, "14_roadmap.json", roadmap)

            result = build_trace_matrix(repo_root, spec_dir)
            mc = result.get("milestone_coverage", {})
            self.assertEqual(mc.get("fr-x"), ["ms-a", "ms-m", "ms-z"])


class TestEntityDedup(unittest.TestCase):
    """Tests for F20: entity dedup during build_trace_matrix entity collection."""

    _TOOLKIT_ROOT = str(Path(__file__).resolve().parents[4])

    def _write_spec_file(self, spec_dir, filename, data):
        path = os.path.join(spec_dir, filename)
        with open(path, "w") as f:
            json.dump(data, f)
        return path

    def test_duplicate_fr_dedup(self):
        """FR appearing in both functional_requirements and out_of_scope is counted once."""
        with tempfile.TemporaryDirectory() as td:
            spec_dir = os.path.join(td, "spec")
            os.makedirs(spec_dir)

            fr_obj = {
                "fr_id": "fr-login",
                "statement": "User can log in",
                "acceptance_criteria": ["Given valid creds, login succeeds"],
                "priority": "must-have",
            }
            self._write_spec_file(spec_dir, "04_fr_list.json", {
                "$schema": "vc:step:04",
                "functional_requirements": [fr_obj],
            })
            self._write_spec_file(spec_dir, "05_interface_contracts.json", {
                "$schema": "vc:step:05",
                "out_of_scope": [fr_obj],
            })

            result = build_trace_matrix(self._TOOLKIT_ROOT, spec_dir)
            self.assertEqual(result["coverage"]["fr_total"], 1)
            # No duplicate rows in the matrix
            fr_ids_in_matrix = [row["fr_id"] for row in result.get("matrix", [])]
            self.assertEqual(len(fr_ids_in_matrix), len(set(fr_ids_in_matrix)))

    def test_aliased_trace_type_dedup(self):
        """FR appearing in both functional_requirements and a reference array in another file is counted once."""
        with tempfile.TemporaryDirectory() as td:
            spec_dir = os.path.join(td, "spec")
            os.makedirs(spec_dir)

            fr_obj = {
                "fr_id": "fr-login",
                "statement": "User can log in",
                "acceptance_criteria": ["Given valid creds, login succeeds"],
                "priority": "must-have",
            }
            # Canonical FR definition
            self._write_spec_file(spec_dir, "04_fr_list.json", {
                "$schema": "vc:step:04",
                "functional_requirements": [fr_obj],
            })
            # Same fr_id referenced in a different step's array (realistic:
            # Step 07 NFRs can carry fr_id on linked_requirements objects)
            self._write_spec_file(spec_dir, "07_nfrs.json", {
                "$schema": "vc:step:07",
                "nfrs": [],
                "linked_requirements": [{"fr_id": "fr-login", "rationale": "perf target"}],
            })

            result = build_trace_matrix(self._TOOLKIT_ROOT, spec_dir)
            # fr-login should be counted once, not twice
            self.assertEqual(result["coverage"]["fr_total"], 1)
            fr_ids = [row["fr_id"] for row in result.get("matrix", [])]
            self.assertEqual(fr_ids, ["fr-login"])

    def test_no_false_dedup(self):
        """Two genuinely different FRs both appear in the matrix."""
        with tempfile.TemporaryDirectory() as td:
            spec_dir = os.path.join(td, "spec")
            os.makedirs(spec_dir)

            self._write_spec_file(spec_dir, "04_fr_list.json", {
                "$schema": "vc:step:04",
                "functional_requirements": [
                    {
                        "fr_id": "fr-login",
                        "statement": "User can log in",
                        "acceptance_criteria": ["Given valid creds, login succeeds"],
                        "priority": "must-have",
                    },
                    {
                        "fr_id": "fr-logout",
                        "statement": "User can log out",
                        "acceptance_criteria": ["Session is terminated"],
                        "priority": "must-have",
                    },
                ],
            })

            result = build_trace_matrix(self._TOOLKIT_ROOT, spec_dir)
            self.assertEqual(result["coverage"]["fr_total"], 2)
            fr_ids_in_matrix = [row["fr_id"] for row in result.get("matrix", [])]
            self.assertIn("fr-login", fr_ids_in_matrix)
            self.assertIn("fr-logout", fr_ids_in_matrix)


if __name__ == "__main__":
    unittest.main()
