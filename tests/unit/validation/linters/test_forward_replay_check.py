import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from specdev_tools.validation.forward_replay_check import check_forward_replay
from specdev_tools.core.errors import make_error, render_errors


class ForwardReplayCheckTests(unittest.TestCase):
    def test_detects_missing_downstream_update(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "spec").mkdir()
            fixture_dir = (
                Path(__file__).resolve().parents[3]
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
            with patch("specdev_tools.validation.forward_replay_check._changed_files", return_value=(missing_changes, None)):
                errs = check_forward_replay(str(root), base_ref="origin/main")
            self.assertTrue(any("E550" in e for e in render_errors(errs)))

    def test_git_diff_failure_is_reported(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "spec").mkdir()
            (root / "tools" / "step_order.json").write_text(
                json.dumps({"steps": ["00", "01"]}), encoding="utf-8"
            )
            with patch(
                "specdev_tools.validation.forward_replay_check._changed_files",
                return_value=([], "fatal: bad revision"),
            ):
                errs = check_forward_replay(str(root), base_ref="origin/main")
            self.assertTrue(any("unable_to_compute_diff" in e for e in render_errors(errs)))

    def test_git_diff_failure_can_be_ignored(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "spec").mkdir()
            (root / "tools" / "step_order.json").write_text(
                json.dumps({"steps": ["00", "01"]}), encoding="utf-8"
            )
            with patch(
                "specdev_tools.validation.forward_replay_check._changed_files",
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
                "specdev_tools.validation.forward_replay_check._changed_files",
                return_value=([], "fatal: bad revision"),
            ):
                errs = check_forward_replay(str(root), base_ref="origin/main", diff_error_mode="warn")
            self.assertTrue(any("invalid_diff_error_mode" in e for e in render_errors(errs)))

    def test_complete_replay_has_no_error(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "spec").mkdir()
            fixture_dir = (
                Path(__file__).resolve().parents[3]
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
                "specdev_tools.validation.forward_replay_check._changed_files",
                return_value=(complete_changes, None),
            ):
                errs = check_forward_replay(str(root), base_ref="origin/main")
            self.assertFalse(any("E550" in e for e in render_errors(errs)))

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
                "specdev_tools.validation.forward_replay_check._changed_files",
                return_value=(["spec/99_future.json"], None),
            ):
                errs = check_forward_replay(str(root), base_ref="origin/main")
            self.assertTrue(any("unknown_step_in_diff=99" in e for e in render_errors(errs)))

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
                "specdev_tools.validation.forward_replay_check._changed_files",
                return_value=([], "not-a-git-repository"),
            ):
                errs = check_forward_replay(str(root), base_ref="origin/main")
            self.assertTrue(any("reason=not-a-git-repository" in e for e in render_errors(errs)))

    def test_semantic_coverage_regression_detected_when_id_dropped(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "spec").mkdir()
            (root / "tools" / "step_order.json").write_text(json.dumps({"steps": ["00", "01"]}), encoding="utf-8")
            (root / "spec" / "00_charter.json").write_text('{}', encoding="utf-8")
            (root / "spec" / "01_capabilities.json").write_text('{"id": "foo-123"}', encoding="utf-8")
            
            with patch("specdev_tools.validation.forward_replay_check._changed_files", return_value=(["spec/00_charter.json", "spec/01_capabilities.json"], None)):
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value.returncode = 0
                    mock_run.return_value.stdout = '{"id": "dropped-id"}'
                    errs = check_forward_replay(str(root), base_ref="origin/main")
                    
            self.assertTrue(any("SEMANTIC_COVERAGE_REGRESSION" in e and "dropped-id" in e for e in render_errors(errs)))

    def test_no_regression_when_ids_preserved_across_replay(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "spec").mkdir()
            (root / "tools" / "step_order.json").write_text(json.dumps({"steps": ["00", "01"]}), encoding="utf-8")
            (root / "spec" / "00_charter.json").write_text('{"id": "kept-id"}', encoding="utf-8")
            (root / "spec" / "01_capabilities.json").write_text('{"id": "kept-id", "new_id": "added-id"}', encoding="utf-8")

            with patch("specdev_tools.validation.forward_replay_check._changed_files", return_value=(["spec/00_charter.json", "spec/01_capabilities.json"], None)):
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value.returncode = 0
                    mock_run.return_value.stdout = '{"id": "kept-id"}'
                    errs = check_forward_replay(str(root), base_ref="origin/main")
                    
            self.assertFalse(any("SEMANTIC_COVERAGE" in e for e in render_errors(errs)))

    def test_graceful_failure_when_git_show_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "spec").mkdir()
            (root / "tools" / "step_order.json").write_text(json.dumps({"steps": ["00", "01"]}), encoding="utf-8")
            (root / "spec" / "00_charter.json").write_text('{}', encoding="utf-8")
            (root / "spec" / "01_capabilities.json").write_text('{}', encoding="utf-8")
            
            with patch("specdev_tools.validation.forward_replay_check._changed_files", return_value=(["spec/00_charter.json", "spec/01_capabilities.json"], None)):
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value.returncode = 128
                    mock_run.return_value.stdout = ''
                    mock_run.return_value.stderr = 'fatal: bad revision'
                    errs = check_forward_replay(str(root), base_ref="origin/main")
                    
            self.assertTrue(any("W550 SEMANTIC_COVERAGE_SKIP" in e for e in render_errors(errs)))

    def test_status_only_change_is_exempted(self):
        """T1: A change to only milestones[].status in an exempted step should not trigger E550."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "spec").mkdir()
            step_order = {
                "steps": ["09", "10"],
                "policy": {
                    "status_write_exemptions": {
                        "09": ["milestones[].status"]
                    }
                }
            }
            (root / "tools" / "step_order.json").write_text(json.dumps(step_order), encoding="utf-8")
            new_spec = {"milestones": [{"milestone_id": "m1", "status": "done", "name": "Alpha"}]}
            (root / "spec" / "09_impl_plan.json").write_text(json.dumps(new_spec), encoding="utf-8")
            (root / "spec" / "10_governance.json").write_text("{}", encoding="utf-8")
            old_spec = {"milestones": [{"milestone_id": "m1", "status": "pending", "name": "Alpha"}]}

            def mock_run(cmd, **kwargs):
                class Result:
                    returncode = 0
                    stdout = json.dumps(old_spec)
                    stderr = ""
                return Result()

            with patch("specdev_tools.validation.forward_replay_check._changed_files",
                       return_value=(["spec/09_impl_plan.json"], None)):
                with patch("subprocess.run", side_effect=mock_run):
                    errs = check_forward_replay(str(root), base_ref="origin/main")
            self.assertFalse(any("E550" in e for e in render_errors(errs)))

    def test_status_plus_other_change_is_not_exempted(self):
        """T2: A change that also modifies non-exempt fields should still trigger E550."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "spec").mkdir()
            step_order = {
                "steps": ["09", "10"],
                "policy": {
                    "status_write_exemptions": {
                        "09": ["milestones[].status"]
                    }
                }
            }
            (root / "tools" / "step_order.json").write_text(json.dumps(step_order), encoding="utf-8")
            new_spec = {"milestones": [{"milestone_id": "m1", "status": "done", "name": "Beta"}]}
            (root / "spec" / "09_impl_plan.json").write_text(json.dumps(new_spec), encoding="utf-8")
            (root / "spec" / "10_governance.json").write_text("{}", encoding="utf-8")
            old_spec = {"milestones": [{"milestone_id": "m1", "status": "pending", "name": "Alpha"}]}

            def mock_run(cmd, **kwargs):
                class Result:
                    returncode = 0
                    stdout = json.dumps(old_spec)
                    stderr = ""
                return Result()

            with patch("specdev_tools.validation.forward_replay_check._changed_files",
                       return_value=(["spec/09_impl_plan.json"], None)):
                with patch("subprocess.run", side_effect=mock_run):
                    errs = check_forward_replay(str(root), base_ref="origin/main")
            self.assertTrue(any("E550" in e for e in render_errors(errs)))

    def test_no_exemptions_configured_preserves_behavior(self):
        """T3: Without status_write_exemptions, original E550 behavior is preserved."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "spec").mkdir()
            (root / "tools" / "step_order.json").write_text(
                json.dumps({"steps": ["09", "10"]}), encoding="utf-8"
            )
            (root / "spec" / "09_impl_plan.json").write_text("{}", encoding="utf-8")
            (root / "spec" / "10_governance.json").write_text("{}", encoding="utf-8")
            with patch("specdev_tools.validation.forward_replay_check._changed_files",
                       return_value=(["spec/09_impl_plan.json"], None)):
                errs = check_forward_replay(str(root), base_ref="origin/main")
            self.assertTrue(any("E550" in e for e in render_errors(errs)))

    def test_exempted_step_with_git_show_failure_not_exempted(self):
        """T4: If git show fails, conservative fallback means the step is NOT exempted."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "spec").mkdir()
            step_order = {
                "steps": ["09", "10"],
                "policy": {
                    "status_write_exemptions": {
                        "09": ["milestones[].status"]
                    }
                }
            }
            (root / "tools" / "step_order.json").write_text(json.dumps(step_order), encoding="utf-8")
            new_spec = {"milestones": [{"milestone_id": "m1", "status": "done", "name": "Alpha"}]}
            (root / "spec" / "09_impl_plan.json").write_text(json.dumps(new_spec), encoding="utf-8")
            (root / "spec" / "10_governance.json").write_text("{}", encoding="utf-8")

            def mock_run(cmd, **kwargs):
                class Result:
                    returncode = 128
                    stdout = ""
                    stderr = "fatal: bad revision"
                return Result()

            with patch("specdev_tools.validation.forward_replay_check._changed_files",
                       return_value=(["spec/09_impl_plan.json"], None)):
                with patch("subprocess.run", side_effect=mock_run):
                    errs = check_forward_replay(str(root), base_ref="origin/main")
            self.assertTrue(any("E550" in e for e in render_errors(errs)))

    def test_id_stability_removal_warning_on_dropped_id(self):
        """W598 ID_STABILITY_REMOVAL fires for each ID removed between base and current."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "spec").mkdir()
            (root / "tools" / "step_order.json").write_text(
                json.dumps({"steps": ["04"]}), encoding="utf-8"
            )
            # Current version of 04 is missing fr-removed that was in the base
            (root / "spec" / "04_frs.json").write_text(
                '{"id": "fr-kept"}', encoding="utf-8"
            )

            with patch(
                "specdev_tools.validation.forward_replay_check._changed_files",
                return_value=(["spec/04_frs.json"], None),
            ):
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value.returncode = 0
                    mock_run.return_value.stdout = '{"id": "fr-kept", "extra_ref": "fr-removed"}'
                    mock_run.return_value.stderr = ""
                    errs = check_forward_replay(str(root), base_ref="origin/main")

            rendered = render_errors(errs)
            stability_warnings = [e for e in rendered if "W598" in e and "ID_STABILITY_REMOVAL" in e]
            self.assertTrue(
                len(stability_warnings) > 0,
                f"Expected W598 ID_STABILITY_REMOVAL warning, got: {rendered}",
            )
            self.assertTrue(
                any("fr-removed" in e for e in stability_warnings),
                f"W598 should name the removed ID, got: {stability_warnings}",
            )

    def test_id_stability_no_warning_when_ids_preserved(self):
        """W598 does not fire when no IDs are removed between base and current."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "spec").mkdir()
            (root / "tools" / "step_order.json").write_text(
                json.dumps({"steps": ["04"]}), encoding="utf-8"
            )
            (root / "spec" / "04_frs.json").write_text(
                '{"id": "fr-kept", "extra_ref": "fr-new"}', encoding="utf-8"
            )

            with patch(
                "specdev_tools.validation.forward_replay_check._changed_files",
                return_value=(["spec/04_frs.json"], None),
            ):
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value.returncode = 0
                    mock_run.return_value.stdout = '{"id": "fr-kept"}'
                    mock_run.return_value.stderr = ""
                    errs = check_forward_replay(str(root), base_ref="origin/main")

            rendered = render_errors(errs)
            stability_warnings = [e for e in rendered if "W598" in e]
            self.assertEqual(
                stability_warnings, [],
                f"Expected no W598 when no IDs removed, got: {stability_warnings}",
            )

    def test_traceability_gaps_surfaced_as_warnings(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "spec").mkdir()
            (root / "tools" / "step_order.json").write_text(json.dumps({"steps": ["00"]}), encoding="utf-8")
            
            with patch("specdev_tools.validation.forward_replay_check._changed_files", return_value=([], None)):
                with patch("specdev_tools.validation.forward_replay_check.check_traceability_closure", return_value=[make_error("E560", "TRACEABILITY_GAP fake gap")]):
                    errs = check_forward_replay(str(root), base_ref="origin/main")
                    
            self.assertTrue(any("W560 TRACEABILITY_GAP fake gap" in e for e in render_errors(errs)))
            self.assertFalse(any("E560" in e for e in render_errors(errs)))



if __name__ == "__main__":
    unittest.main()
