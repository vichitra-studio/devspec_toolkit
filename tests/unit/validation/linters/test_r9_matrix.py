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

from specdev_tools.validation.matrix import (
    _check_coverage_thresholds,
    _DEFAULT_COVERAGE_THRESHOLDS,
    _load_coverage_thresholds,
    _MISSING_FILE,
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
            self.assertIsNotNone(result)
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


if __name__ == "__main__":
    unittest.main()
