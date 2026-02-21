import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import os
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from specdev_tools.validate import _get_step_from_path, validate_dir, validate_file, _resolve_replay_base_ref


class ValidateB2IntegrationTests(unittest.TestCase):
    def test_get_step_from_path_supports_lettered_steps(self):
        self.assertEqual("13a", _get_step_from_path("13a_completeness_assessment.json"))
        self.assertEqual("16c", _get_step_from_path("tests/fixtures/step_16c/something.json"))

    def test_validate_dir_runs_b2_repo_level_checks(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            (root / "schema").mkdir()
            (root / "prompts").mkdir()
            (root / "tools").mkdir()
            (root / "canon").mkdir()

            (root / "spec" / "00_charter.json").write_text(json.dumps({"$schema": "x"}), encoding="utf-8")
            (root / "tools" / "step_order.json").write_text(
                json.dumps({"steps": ["00"], "allowed_upstream_dependencies": {"00": []}}),
                encoding="utf-8",
            )
            (root / "canon" / "manifest.json").write_text(
                json.dumps({"entries": [], "aliases": []}),
                encoding="utf-8",
            )
            (root / "prompts" / "prompt_00_charter.md").write_text("prompt", encoding="utf-8")

            with patch("specdev_tools.validate.validate_file", return_value=[]), \
                 patch("specdev_tools.validate.lint_spec_quality", return_value=[]) as p_quality, \
                 patch("specdev_tools.validate.lint_hallucinations", return_value=[]) as p_hall, \
                 patch("specdev_tools.validate.validate_canonical_integrity", return_value=[]) as p_integrity, \
                 patch("specdev_tools.validate.lint_canon_dir", return_value=[]) as p_canon, \
                 patch("specdev_tools.validate.lint_dependency_order", return_value=[]) as p_dep, \
                 patch("specdev_tools.validate.check_forward_replay", return_value=[]) as p_replay, \
                 patch("specdev_tools.validate.run_prompt_schema_sync", return_value=[]) as p_prompt:
                errs = validate_dir(str(root), str(root / "spec"))

            self.assertEqual([], errs)
            self.assertTrue(p_quality.called)
            self.assertTrue(p_hall.called)
            self.assertTrue(p_integrity.called)
            self.assertTrue(p_canon.called)
            self.assertTrue(p_dep.called)
            self.assertTrue(p_replay.called)
            self.assertTrue(p_prompt.called)

    def test_validate_file_returns_error_when_registry_bootstrap_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            missing_repo = root / "missing-repo-root"
            spec_file = root / "00_charter.json"
            spec_file.write_text(json.dumps({"$schema": "https://specdev.local/schema/00_charter.schema.json"}), encoding="utf-8")
            errs = validate_file(str(missing_repo), str(spec_file))
            self.assertTrue(errs)
            self.assertTrue(any("error during validation" in e for e in errs))

    def test_validate_dir_reports_missing_canon_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            (root / "tools").mkdir()
            (root / "prompts").mkdir()
            (root / "schema").mkdir()
            (root / "spec" / "00_charter.json").write_text(json.dumps({"$schema": "x"}), encoding="utf-8")
            with patch("specdev_tools.validate.validate_file", return_value=[]), \
                 patch("specdev_tools.validate.lint_spec_quality", return_value=[]), \
                 patch("specdev_tools.validate.lint_hallucinations", return_value=[]), \
                 patch("specdev_tools.validate.validate_canonical_integrity", return_value=[]), \
                 patch("specdev_tools.validate.lint_dependency_order", return_value=[]), \
                 patch("specdev_tools.validate.check_forward_replay", return_value=[]), \
                 patch("specdev_tools.validate.run_prompt_schema_sync", return_value=[]):
                errs = validate_dir(str(root), str(root / "spec"))
            self.assertTrue(any("missing" in e and "manifest.json" in e for e in errs))

    def test_validate_dir_handles_invalid_json_without_crash(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            (root / "tools").mkdir()
            (root / "prompts").mkdir()
            (root / "schema").mkdir()
            (root / "spec" / "bad.json").write_text("{bad", encoding="utf-8")
            (root / "tools" / "step_order.json").write_text(
                json.dumps({"steps": ["00"], "allowed_upstream_dependencies": {"00": []}}),
                encoding="utf-8",
            )
            errs = validate_dir(str(root), str(root / "spec"))
            self.assertTrue(any("invalid_json" in e for e in errs))

    def test_validate_dir_skips_forward_replay_when_policy_disabled(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            (root / "tools").mkdir()
            (root / "prompts").mkdir()
            (root / "schema").mkdir()
            (root / "canon").mkdir()
            (root / "spec" / "00_charter.json").write_text(json.dumps({"$schema": "x"}), encoding="utf-8")
            (root / "canon" / "manifest.json").write_text(
                json.dumps({"registry_version": "1.0.0", "entries": [], "aliases": []}),
                encoding="utf-8",
            )
            (root / "tools" / "step_order.json").write_text(
                json.dumps(
                    {
                        "steps": ["00"],
                        "policy": {"require_full_forward_replay_on_change": False},
                        "allowed_upstream_dependencies": {"00": []},
                    }
                ),
                encoding="utf-8",
            )
            with patch("specdev_tools.validate.validate_file", return_value=[]), \
                 patch("specdev_tools.validate.lint_spec_quality", return_value=[]), \
                 patch("specdev_tools.validate.lint_hallucinations", return_value=[]), \
                 patch("specdev_tools.validate.validate_canonical_integrity", return_value=[]), \
                 patch("specdev_tools.validate.lint_canon_dir", return_value=[]), \
                 patch("specdev_tools.validate.lint_dependency_order", return_value=[]), \
                 patch("specdev_tools.validate.check_forward_replay", return_value=[]) as p_replay, \
                 patch("specdev_tools.validate.run_prompt_schema_sync", return_value=[]):
                errs = validate_dir(str(root), str(root / "spec"))
            self.assertEqual([], errs)
            self.assertFalse(p_replay.called)

    def test_validate_dir_reports_invalid_step_order_instead_of_crashing(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            (root / "tools").mkdir()
            (root / "prompts").mkdir()
            (root / "schema").mkdir()
            (root / "canon").mkdir()
            (root / "spec" / "00_charter.json").write_text(json.dumps({"$schema": "x"}), encoding="utf-8")
            (root / "tools" / "step_order.json").write_text("{bad", encoding="utf-8")
            (root / "canon" / "manifest.json").write_text(
                json.dumps({"registry_version": "1.0.0", "entries": [], "aliases": []}),
                encoding="utf-8",
            )
            with patch("specdev_tools.validate.validate_file", return_value=[]), \
                 patch("specdev_tools.validate.lint_spec_quality", return_value=[]), \
                 patch("specdev_tools.validate.lint_hallucinations", return_value=[]), \
                 patch("specdev_tools.validate.validate_canonical_integrity", return_value=[]), \
                 patch("specdev_tools.validate.check_forward_replay", return_value=[]) as p_replay, \
                 patch("specdev_tools.validate.run_prompt_schema_sync", return_value=[]):
                errs = validate_dir(str(root), str(root / "spec"))
            self.assertTrue(any("invalid_step_order" in e for e in errs))
            self.assertFalse(p_replay.called)

    def test_validate_dir_uses_ignore_replay_mode_when_not_git_repo(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            (root / "tools").mkdir()
            (root / "prompts").mkdir()
            (root / "schema").mkdir()
            (root / "canon").mkdir()
            (root / "spec" / "00_charter.json").write_text(json.dumps({"$schema": "x"}), encoding="utf-8")
            (root / "tools" / "step_order.json").write_text(
                json.dumps({"steps": ["00"], "allowed_upstream_dependencies": {"00": []}}),
                encoding="utf-8",
            )
            (root / "canon" / "manifest.json").write_text(
                json.dumps({"registry_version": "1.0.0", "entries": [], "aliases": []}),
                encoding="utf-8",
            )
            with patch("specdev_tools.validate.validate_file", return_value=[]), \
                 patch("specdev_tools.validate.lint_spec_quality", return_value=[]), \
                 patch("specdev_tools.validate.lint_hallucinations", return_value=[]), \
                 patch("specdev_tools.validate.validate_canonical_integrity", return_value=[]), \
                 patch("specdev_tools.validate.lint_canon_dir", return_value=[]), \
                 patch("specdev_tools.validate.lint_dependency_order", return_value=[]), \
                 patch("specdev_tools.validate._is_git_repo", return_value=False), \
                 patch("specdev_tools.validate.check_forward_replay", return_value=[]) as p_replay, \
                 patch("specdev_tools.validate.run_prompt_schema_sync", return_value=[]):
                errs = validate_dir(str(root), str(root / "spec"))
            self.assertEqual([], errs)
            self.assertTrue(p_replay.called)
            self.assertEqual("ignore", p_replay.call_args.kwargs.get("diff_error_mode"))

    def test_validate_dir_uses_error_replay_mode_in_ci_without_git_repo(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            (root / "tools").mkdir()
            (root / "prompts").mkdir()
            (root / "schema").mkdir()
            (root / "canon").mkdir()
            (root / "spec" / "00_charter.json").write_text(json.dumps({"$schema": "x"}), encoding="utf-8")
            (root / "tools" / "step_order.json").write_text(
                json.dumps({"steps": ["00"], "allowed_upstream_dependencies": {"00": []}}),
                encoding="utf-8",
            )
            (root / "canon" / "manifest.json").write_text(
                json.dumps({"registry_version": "1.0.0", "entries": [], "aliases": []}),
                encoding="utf-8",
            )
            old_ci = os.environ.get("CI")
            os.environ["CI"] = "true"
            try:
                with patch("specdev_tools.validate.validate_file", return_value=[]), \
                     patch("specdev_tools.validate.lint_spec_quality", return_value=[]), \
                     patch("specdev_tools.validate.lint_hallucinations", return_value=[]), \
                     patch("specdev_tools.validate.validate_canonical_integrity", return_value=[]), \
                     patch("specdev_tools.validate.lint_canon_dir", return_value=[]), \
                     patch("specdev_tools.validate.lint_dependency_order", return_value=[]), \
                     patch("specdev_tools.validate._is_git_repo", return_value=False), \
                     patch("specdev_tools.validate.check_forward_replay", return_value=[]) as p_replay, \
                     patch("specdev_tools.validate.run_prompt_schema_sync", return_value=[]):
                    errs = validate_dir(str(root), str(root / "spec"))
            finally:
                if old_ci is None:
                    os.environ.pop("CI", None)
                else:
                    os.environ["CI"] = old_ci
            self.assertEqual([], errs)
            self.assertTrue(p_replay.called)
            self.assertEqual("error", p_replay.call_args.kwargs.get("diff_error_mode"))

    def test_validate_dir_passes_env_base_ref_to_replay(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            (root / "tools").mkdir()
            (root / "prompts").mkdir()
            (root / "schema").mkdir()
            (root / "canon").mkdir()
            (root / "spec" / "00_charter.json").write_text(json.dumps({"$schema": "x"}), encoding="utf-8")
            (root / "tools" / "step_order.json").write_text(
                json.dumps({"steps": ["00"], "allowed_upstream_dependencies": {"00": []}}),
                encoding="utf-8",
            )
            (root / "canon" / "manifest.json").write_text(
                json.dumps({"registry_version": "1.0.0", "entries": [], "aliases": []}),
                encoding="utf-8",
            )
            old_ref = os.environ.get("SPECDEV_REPLAY_BASE_REF")
            os.environ["SPECDEV_REPLAY_BASE_REF"] = "feature/base"
            try:
                with patch("specdev_tools.validate.validate_file", return_value=[]), \
                     patch("specdev_tools.validate.lint_spec_quality", return_value=[]), \
                     patch("specdev_tools.validate.lint_hallucinations", return_value=[]), \
                     patch("specdev_tools.validate.validate_canonical_integrity", return_value=[]), \
                     patch("specdev_tools.validate.lint_canon_dir", return_value=[]), \
                     patch("specdev_tools.validate.lint_dependency_order", return_value=[]), \
                     patch("specdev_tools.validate.check_forward_replay", return_value=[]) as p_replay, \
                     patch("specdev_tools.validate.run_prompt_schema_sync", return_value=[]):
                    errs = validate_dir(str(root), str(root / "spec"))
            finally:
                if old_ref is None:
                    os.environ.pop("SPECDEV_REPLAY_BASE_REF", None)
                else:
                    os.environ["SPECDEV_REPLAY_BASE_REF"] = old_ref
            self.assertEqual([], errs)
            self.assertTrue(p_replay.called)
            self.assertEqual("feature/base", p_replay.call_args.kwargs.get("base_ref"))

    def test_resolve_replay_base_ref_falls_back_to_current_branch(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with patch("specdev_tools.validate._git_ref_exists", return_value=False), \
                 patch("specdev_tools.validate._git_upstream_branch", return_value=None), \
                 patch("specdev_tools.validate._git_current_branch", return_value="feature/x"):
                self.assertEqual("feature/x", _resolve_replay_base_ref(root))

    def test_resolve_replay_base_ref_prefers_current_branch_over_defaults(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)

            def has_ref(_root, ref):
                return ref == "main"

            with patch("specdev_tools.validate._git_current_branch", return_value="feature/x"), \
                 patch("specdev_tools.validate._git_ref_exists", side_effect=has_ref), \
                 patch("specdev_tools.validate._git_upstream_branch", return_value=None):
                self.assertEqual("feature/x", _resolve_replay_base_ref(root))


if __name__ == "__main__":
    unittest.main()
