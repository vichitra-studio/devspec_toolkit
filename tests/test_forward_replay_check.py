import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from specdev_tools.forward_replay_check import check_forward_replay


class ForwardReplayCheckTests(unittest.TestCase):
    def test_detects_missing_downstream_update(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "spec").mkdir()
            fixture_dir = (
                Path(__file__).resolve().parents[0]
                / "fixtures"
                / "dependency_order"
            )
            missing_changes = (
                fixture_dir / "replay_missing_changed_files.txt"
            ).read_text(encoding="utf-8").splitlines()
            (root / "tools" / "step_order.json").write_text(
                json.dumps({"steps": ["00", "01", "02"]}), encoding="utf-8"
            )
            (root / "spec" / "00_charter.json").write_text("{}", encoding="utf-8")
            (root / "spec" / "01_capabilities.json").write_text("{}", encoding="utf-8")
            (root / "spec" / "02_system_sketch.json").write_text("{}", encoding="utf-8")
            with patch("specdev_tools.forward_replay_check._changed_files", return_value=(missing_changes, None)):
                errs = check_forward_replay(str(root), base_ref="origin/main")
            self.assertTrue(any("E550" in e for e in errs))

    def test_git_diff_failure_is_reported(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "spec").mkdir()
            (root / "tools" / "step_order.json").write_text(
                json.dumps({"steps": ["00", "01"]}), encoding="utf-8"
            )
            with patch(
                "specdev_tools.forward_replay_check._changed_files",
                return_value=([], "fatal: bad revision"),
            ):
                errs = check_forward_replay(str(root), base_ref="origin/main")
            self.assertTrue(any("unable_to_compute_diff" in e for e in errs))

    def test_git_diff_failure_can_be_ignored(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "spec").mkdir()
            (root / "tools" / "step_order.json").write_text(
                json.dumps({"steps": ["00", "01"]}), encoding="utf-8"
            )
            with patch(
                "specdev_tools.forward_replay_check._changed_files",
                return_value=([], "fatal: bad revision"),
            ):
                errs = check_forward_replay(str(root), base_ref="origin/main", diff_error_mode="ignore")
            self.assertEqual([], errs)

    def test_invalid_diff_error_mode_is_reported(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "spec").mkdir()
            (root / "tools" / "step_order.json").write_text(
                json.dumps({"steps": ["00", "01"]}), encoding="utf-8"
            )
            with patch(
                "specdev_tools.forward_replay_check._changed_files",
                return_value=([], "fatal: bad revision"),
            ):
                errs = check_forward_replay(str(root), base_ref="origin/main", diff_error_mode="warn")
            self.assertTrue(any("invalid_diff_error_mode" in e for e in errs))

    def test_complete_replay_has_no_error(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "spec").mkdir()
            fixture_dir = (
                Path(__file__).resolve().parents[0]
                / "fixtures"
                / "dependency_order"
            )
            complete_changes = (
                fixture_dir / "replay_complete_changed_files.txt"
            ).read_text(encoding="utf-8").splitlines()
            (root / "tools" / "step_order.json").write_text(
                json.dumps({"steps": ["00", "01", "02"]}), encoding="utf-8"
            )
            (root / "spec" / "00_charter.json").write_text("{}", encoding="utf-8")
            (root / "spec" / "01_capabilities.json").write_text("{}", encoding="utf-8")
            (root / "spec" / "02_system_sketch.json").write_text("{}", encoding="utf-8")
            with patch(
                "specdev_tools.forward_replay_check._changed_files",
                return_value=(complete_changes, None),
            ):
                errs = check_forward_replay(str(root), base_ref="origin/main")
            self.assertFalse(any("E550" in e for e in errs))

    def test_unknown_changed_step_is_reported_without_crash(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "spec").mkdir()
            (root / "tools" / "step_order.json").write_text(
                json.dumps({"steps": ["00", "01"]}),
                encoding="utf-8",
            )
            with patch(
                "specdev_tools.forward_replay_check._changed_files",
                return_value=(["spec/99_future.json"], None),
            ):
                errs = check_forward_replay(str(root), base_ref="origin/main")
            self.assertTrue(any("unknown_step_in_diff=99" in e for e in errs))

    def test_not_git_repository_reason_is_compact(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "spec").mkdir()
            (root / "tools" / "step_order.json").write_text(
                json.dumps({"steps": ["00"]}), encoding="utf-8"
            )
            noisy = "warning: Not a git repository.\n" + ("usage: git diff\n" * 50)
            with patch(
                "specdev_tools.forward_replay_check._changed_files",
                return_value=([], "not-a-git-repository"),
            ):
                errs = check_forward_replay(str(root), base_ref="origin/main")
            self.assertTrue(any("reason=not-a-git-repository" in e for e in errs))


if __name__ == "__main__":
    unittest.main()
