"""Tests for R9 CLI commands: env-check and dag-lint.

Validates that the two new commands registered in T28 are callable,
produce expected output, and respect the --repo-root flag.
"""

from __future__ import annotations

import io
import os
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Optional
from unittest.mock import patch

from specdev_tools import cli

REPO_ROOT = Path(__file__).resolve().parents[2]


class _CliMixin:
    """Shared helper to invoke CLI main() in-process with mocked venv check."""

    def _run_cli(self, argv: list[str], env_override: dict[str, str] | None = None) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        patchers = [
            patch("specdev_tools.cli.check_venv", return_value=None),
            patch.object(sys, "argv", ["specdev-tools", *argv]),
        ]
        if env_override is not None:
            merged = {**os.environ, **env_override}
            patchers.append(patch.dict(os.environ, merged, clear=True))
        with redirect_stdout(stdout), redirect_stderr(stderr):
            for p in patchers:
                p.start()
            try:
                cli.main()
                code = 0
            except SystemExit as exc:
                code = int(exc.code) if isinstance(exc.code, int) else 1
            finally:
                for p in reversed(patchers):
                    p.stop()
        return code, stdout.getvalue(), stderr.getvalue()


class TestEnvCheck(_CliMixin, unittest.TestCase):
    """Tests for the env-check diagnostic command."""

    def test_env_check_runs_without_error(self):
        """env-check exits 0 and prints the header/footer banners."""
        code, out, err = self._run_cli(["env-check", "--repo-root", str(REPO_ROOT)])
        self.assertEqual(code, 0, f"env-check failed with stderr: {err}")
        self.assertIn("SPECDEV Environment Check", out)
        self.assertIn("End Environment Check", out)

    def test_env_check_shows_promotable_pairs(self):
        """env-check reports the number of promotable W->E pairs."""
        code, out, _ = self._run_cli(["env-check", "--repo-root", str(REPO_ROOT)])
        self.assertEqual(code, 0)
        self.assertIn("Promotable pairs registered:", out)
        # The count must be a positive integer (there are known pairs in errors.py)
        for line in out.splitlines():
            if "Promotable pairs registered:" in line:
                count_str = line.split(":")[-1].strip()
                self.assertTrue(count_str.isdigit(), f"Expected digit, got: {count_str!r}")
                self.assertGreater(int(count_str), 0)
                break
        else:
            self.fail("'Promotable pairs registered:' line not found in output")

    def test_env_check_shows_specdev_vars_when_set(self):
        """env-check lists SPECDEV_* vars that are in the environment."""
        env = {
            "SPECDEV_WARNINGS_AS_ERRORS": "1",
            "SPECDEV_REPLAY_BASE_REF": "origin/develop",
        }
        code, out, _ = self._run_cli(
            ["env-check", "--repo-root", str(REPO_ROOT)],
            env_override=env,
        )
        self.assertEqual(code, 0)
        self.assertIn("SPECDEV_WARNINGS_AS_ERRORS=1", out)
        self.assertIn("SPECDEV_REPLAY_BASE_REF=origin/develop", out)
        self.assertIn("Active SPECDEV_* environment variables:", out)

    def test_env_check_shows_no_vars_message(self):
        """When no SPECDEV_* vars are set, env-check says so explicitly."""
        # Build an environment with all SPECDEV_* vars removed
        clean_env = {k: v for k, v in os.environ.items() if not k.startswith("SPECDEV_")}
        with patch.dict(os.environ, clean_env, clear=True):
            code, out, _ = self._run_cli(["env-check", "--repo-root", str(REPO_ROOT)])
        self.assertEqual(code, 0)
        self.assertIn("No SPECDEV_* environment variables set.", out)

    def test_env_check_promotion_all(self):
        """When SPECDEV_WARNINGS_AS_ERRORS=1, env-check reports ALL promotion."""
        env = {"SPECDEV_WARNINGS_AS_ERRORS": "1"}
        code, out, _ = self._run_cli(
            ["env-check", "--repo-root", str(REPO_ROOT)],
            env_override=env,
        )
        self.assertEqual(code, 0)
        self.assertIn("W→E Promotion: ALL", out)

    def test_env_check_promotion_selective(self):
        """When SPECDEV_PROMOTE_CODES is set, env-check reports SELECTIVE promotion."""
        # Make sure SPECDEV_WARNINGS_AS_ERRORS is off so selective path is taken
        clean_env = {k: v for k, v in os.environ.items() if k != "SPECDEV_WARNINGS_AS_ERRORS"}
        clean_env["SPECDEV_PROMOTE_CODES"] = "W550,W560"
        with patch.dict(os.environ, clean_env, clear=True):
            code, out, _ = self._run_cli(["env-check", "--repo-root", str(REPO_ROOT)])
        self.assertEqual(code, 0)
        self.assertIn("W→E Promotion: SELECTIVE", out)
        self.assertIn("2 codes", out)

    def test_env_check_promotion_off(self):
        """When no promotion env vars are set, env-check reports OFF."""
        clean_env = {
            k: v for k, v in os.environ.items()
            if k not in ("SPECDEV_WARNINGS_AS_ERRORS", "SPECDEV_PROMOTE_CODES")
        }
        with patch.dict(os.environ, clean_env, clear=True):
            code, out, _ = self._run_cli(["env-check", "--repo-root", str(REPO_ROOT)])
        self.assertEqual(code, 0)
        self.assertIn("W→E Promotion: OFF", out)

    def test_env_check_reports_spec_dir(self):
        """env-check prints spec dir path and its existence status."""
        code, out, _ = self._run_cli(["env-check", "--repo-root", str(REPO_ROOT)])
        self.assertEqual(code, 0)
        self.assertIn("Spec dir:", out)
        self.assertIn("Repo root:", out)
        # The real repo has a spec/ directory
        self.assertIn("exists", out)

    def test_env_check_reports_step_order(self):
        """env-check prints step_order.json path and its existence status."""
        code, out, _ = self._run_cli(["env-check", "--repo-root", str(REPO_ROOT)])
        self.assertEqual(code, 0)
        self.assertIn("Step order:", out)
        self.assertIn("exists", out)

    def test_env_check_respects_repo_root(self):
        """--repo-root changes the reported paths."""
        code, out, _ = self._run_cli(["env-check", "--repo-root", str(REPO_ROOT)])
        self.assertEqual(code, 0)
        self.assertIn(str(REPO_ROOT), out)


class TestDagLint(_CliMixin, unittest.TestCase):
    """Tests for the dag-lint command."""

    def test_dag_lint_registered_and_callable(self):
        """dag-lint runs without crashing on the real repo."""
        code, out, err = self._run_cli(["dag-lint", "--repo-root", str(REPO_ROOT)])
        # It may exit 0 (OK) or 1 (errors found) — but it should not crash
        self.assertIn(code, (0, 1), f"Unexpected exit code {code}; stderr: {err}")

    def test_dag_lint_produces_output(self):
        """dag-lint produces either OK or error diagnostics."""
        code, out, err = self._run_cli(["dag-lint", "--repo-root", str(REPO_ROOT)])
        # When no errors: stdout contains "OK"; when errors: stderr has content
        if code == 0:
            self.assertIn("OK", out)
        else:
            self.assertTrue(len(err) > 0, "dag-lint failed but produced no stderr")

    def test_dag_lint_respects_repo_root(self):
        """dag-lint uses --repo-root to locate step_order.json."""
        # Point at a nonexistent directory — should get E520 about missing step_order.json
        code, out, err = self._run_cli(["dag-lint", "--repo-root", "/tmp/nonexistent_dag_test"])
        self.assertEqual(code, 1)
        self.assertIn("E520", err)

    def test_dag_lint_detects_missing_step_order(self):
        """dag-lint reports E520 when step_order.json is absent."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            # Empty directory — no tools/step_order.json
            code, out, err = self._run_cli(["dag-lint", "--repo-root", tmpdir])
            self.assertEqual(code, 1)
            self.assertIn("E520", err)
            self.assertIn("not found", err)

    def test_dag_lint_detects_dead_end_producer(self):
        """dag-lint reports E596 for a non-terminal step with zero consumers."""
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            tools_dir = os.path.join(tmpdir, "tools")
            os.makedirs(tools_dir)
            step_order = {
                "steps": ["00", "01"],
                "downstream_consumers": {"00": ["01"], "01": []},
            }
            with open(os.path.join(tools_dir, "step_order.json"), "w") as f:
                json.dump(step_order, f)
            code, out, err = self._run_cli(["dag-lint", "--repo-root", tmpdir])
            self.assertEqual(code, 1)
            self.assertIn("E596", err)
            self.assertIn("DAG_DEAD_END_PRODUCER", err)
            self.assertIn("'01'", err)

    def test_dag_lint_detects_circular_dependency(self):
        """dag-lint reports E599 when a consumer appears before its producer in steps ordering.

        Under derive_allowed_upstream, cycles are structurally impossible.
        Consumer ordering violations (consumer before producer in steps) are
        detected as E599 DAG_CONSUMER_INCONSISTENCY.
        """
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            tools_dir = os.path.join(tmpdir, "tools")
            os.makedirs(tools_dir)
            step_order = {
                "steps": ["00", "01", "02"],
                "downstream_consumers": {
                    # 02 claims 01 is its consumer, but 01 appears before 02 -> E599
                    "00": ["01", "02"], "01": ["02"], "02": ["01"],
                },
            }
            with open(os.path.join(tools_dir, "step_order.json"), "w") as f:
                json.dump(step_order, f)
            code, out, err = self._run_cli(["dag-lint", "--repo-root", tmpdir])
            self.assertEqual(code, 1)
            self.assertIn("E599", err)
            self.assertIn("DAG_CONSUMER_INCONSISTENCY", err)

    def test_dag_lint_detects_consumer_inconsistency(self):
        """dag-lint reports E599 when a declared consumer comes before the producer in steps."""
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            tools_dir = os.path.join(tmpdir, "tools")
            os.makedirs(tools_dir)
            step_order = {
                "steps": ["00", "01", "16c"],
                "downstream_consumers": {
                    # 16c claims 00 is its consumer, but 00 appears before 16c -> E599
                    "00": ["01", "16c"],
                    "01": ["16c"],
                    "16c": ["00"],
                },
            }
            with open(os.path.join(tools_dir, "step_order.json"), "w") as f:
                json.dump(step_order, f)
            code, out, err = self._run_cli(["dag-lint", "--repo-root", tmpdir])
            self.assertEqual(code, 1)
            self.assertIn("E599", err)
            self.assertIn("DAG_CONSUMER_INCONSISTENCY", err)


class TestExtractionIntentCheck(_CliMixin, unittest.TestCase):
    """Tests for the extraction-intent-check command."""

    def test_extraction_intent_check_registered_and_callable(self):
        """extraction-intent-check runs without crashing on the real repo."""
        code, out, err = self._run_cli(["extraction-intent-check", "--repo-root", str(REPO_ROOT)])
        # It may exit 0 (OK) or 1 (errors found) — but it should not crash
        self.assertIn(code, (0, 1), f"Unexpected exit code {code}; stderr: {err}")

    def test_extraction_intent_check_produces_output(self):
        """extraction-intent-check produces either OK or error diagnostics."""
        code, out, err = self._run_cli(["extraction-intent-check", "--repo-root", str(REPO_ROOT)])
        if code == 0:
            self.assertIn("OK", out)
        else:
            self.assertTrue(len(err) > 0, "extraction-intent-check failed but produced no stderr")

    def test_extraction_intent_check_respects_repo_root(self):
        """extraction-intent-check uses --repo-root to locate step_order.json."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            # Empty directory — no step_order.json → should exit 0 (graceful skip)
            code, out, err = self._run_cli(["extraction-intent-check", "--repo-root", tmpdir])
            self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
