"""Tests for the id-regression side of forward_replay_check.py: E555 for an id a changed file dropped, E550 for a diff that cannot be computed."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from specdev_tools.core.errors import render_errors
from specdev_tools.validation.forward_replay_check import check_forward_replay


# ---------------------------------------------------------------------------
# 1. E555 error code for SEMANTIC_COVERAGE_REGRESSION
# ---------------------------------------------------------------------------

class TestE555SemanticCoverageRegression(unittest.TestCase):
    """Verify that ID regressions use E555, not the old E550."""

    def test_id_regression_uses_e555(self):
        """When an ID is dropped, the error code must be E555."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "spec").mkdir()
            (root / "tools" / "step_order.json").write_text(
                json.dumps({"steps": ["00", "01"]}), encoding="utf-8"
            )
            (root / "spec" / "00_charter.json").write_text("{}", encoding="utf-8")
            (root / "spec" / "01_capabilities.json").write_text(
                '{"id": "kept-id"}', encoding="utf-8"
            )

            with patch(
                "specdev_tools.validation.forward_replay_check._changed_files",
                return_value=(
                    ["spec/00_charter.json", "spec/01_capabilities.json"],
                    None,
                ),
            ):
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value.returncode = 0
                    mock_run.return_value.stdout = '{"id": "dropped-id"}'
                    mock_run.return_value.stderr = ""
                    errs = check_forward_replay(str(root), base_ref="origin/main")

            regression_errs = [e for e in render_errors(errs) if "SEMANTIC_COVERAGE_REGRESSION" in e]
            self.assertTrue(len(regression_errs) > 0, "Expected at least one regression error")
            for err in regression_errs:
                self.assertTrue(
                    err.startswith("E555"),
                    f"Expected E555 prefix, got: {err}",
                )
                self.assertNotIn("E550", err)

    def test_id_regression_includes_dropped_ids(self):
        """The E555 message must list the specific dropped IDs."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "spec").mkdir()
            (root / "tools" / "step_order.json").write_text(
                json.dumps({"steps": ["04"]}), encoding="utf-8"
            )
            (root / "spec" / "04_frs.json").write_text(
                '{"id": "fr-remaining"}', encoding="utf-8"
            )

            with patch(
                "specdev_tools.validation.forward_replay_check._changed_files",
                return_value=(["spec/04_frs.json"], None),
            ):
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value.returncode = 0
                    mock_run.return_value.stdout = json.dumps({
                        "id": "fr-remaining",
                        "extra_ref": "fr-alpha",
                        "another_ref": "fr-beta",
                    })
                    mock_run.return_value.stderr = ""
                    errs = check_forward_replay(str(root), base_ref="origin/main")

            regression_errs = [e for e in render_errors(errs) if "E555" in e]
            self.assertTrue(len(regression_errs) > 0)
            combined = " ".join(regression_errs)
            self.assertIn("fr-alpha", combined)
            self.assertIn("fr-beta", combined)


# ---------------------------------------------------------------------------
# 2. E550 still reported for a failed diff of the base ref
# ---------------------------------------------------------------------------

class TestE550ForwardReplayMissing(unittest.TestCase):
    """Verify that E550 is still used for forward-replay structural errors."""

    def test_diff_failure_still_uses_e550(self):
        """Git diff failures should still produce E550."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "spec").mkdir()
            (root / "tools" / "step_order.json").write_text(
                json.dumps({"steps": ["00"]}), encoding="utf-8"
            )
            with patch(
                "specdev_tools.validation.forward_replay_check._changed_files",
                return_value=([], "fatal: bad revision"),
            ):
                errs = check_forward_replay(str(root), base_ref="origin/main")
            self.assertTrue(any(e.startswith("E550") for e in render_errors(errs)))

if __name__ == "__main__":
    unittest.main()
