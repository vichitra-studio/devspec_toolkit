import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from specdev_tools import cli


class CliB3Tests(unittest.TestCase):
    def _run_cli(self, argv: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("specdev_tools.cli.check_venv", return_value=None), \
             patch.object(sys, "argv", ["specdev-tools", *argv]), \
             redirect_stdout(stdout), \
             redirect_stderr(stderr):
            try:
                cli.main()
                code = 0
            except SystemExit as exc:
                code = int(exc.code) if isinstance(exc.code, int) else 1
        return code, stdout.getvalue(), stderr.getvalue()

    def test_help_lists_b3_subcommands(self):
        code, out, _ = self._run_cli(["--help"])
        self.assertEqual(0, code)
        for name in (
            "prompt-sync",
            "canonical-lint",
            "canonical-integrity",
            "canonical-autofix",
            "spec-quality-lint",
            "hallucination-lint",
            "dependency-order-lint",
            "forward-replay-check",
        ):
            self.assertIn(name, out)

    def test_prompt_sync_fails_when_default_spec_dir_missing(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td)
            with patch("specdev_tools.prompt_schema_sync.run_prompt_schema_sync", return_value=[]):
                code, _, err = self._run_cli(["prompt-sync", "--repo-root", str(repo_root)])
            self.assertEqual(1, code)
            self.assertIn("missing_spec_dir", err)

    def test_prompt_sync_dispatches_when_spec_dir_exists(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td)
            spec_dir = repo_root / "spec"
            spec_dir.mkdir()
            with patch("specdev_tools.prompt_schema_sync.run_prompt_schema_sync", return_value=[]) as run_sync:
                code, out, err = self._run_cli(["prompt-sync", str(spec_dir), "--repo-root", str(repo_root)])
            self.assertEqual(0, code, msg=err)
            self.assertIn("OK", out)
            run_sync.assert_called_once_with(os.path.abspath(str(repo_root)))

    def test_prompt_sync_rejects_non_repo_spec_dir(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td)
            (repo_root / "spec").mkdir()
            other_dir = repo_root / "other"
            other_dir.mkdir()
            with patch("specdev_tools.prompt_schema_sync.run_prompt_schema_sync", return_value=[]):
                code, _, err = self._run_cli(["prompt-sync", str(other_dir), "--repo-root", str(repo_root)])
            self.assertEqual(1, code)
            self.assertIn("prompt_sync_spec_dir_must_equal_repo_spec", err)

    def test_prompt_sync_uses_repo_root_spec_when_spec_dir_omitted(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td)
            (repo_root / "spec").mkdir()
            with patch("specdev_tools.prompt_schema_sync.run_prompt_schema_sync", return_value=[]) as run_sync:
                code, out, err = self._run_cli(["prompt-sync", "--repo-root", str(repo_root)])
            self.assertEqual(0, code, msg=err)
            self.assertIn("OK", out)
            run_sync.assert_called_once_with(os.path.abspath(str(repo_root)))

    def test_canonical_autofix_rejects_conflicting_flags(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td)
            spec_dir = repo_root / "spec"
            spec_dir.mkdir()
            code, _, err = self._run_cli(
                ["canonical-autofix", str(spec_dir), "--repo-root", str(repo_root), "--write", "--dry-run"]
            )
            self.assertEqual(2, code)
            self.assertIn("not allowed with argument", err)

    def test_new_b3_command_dispatch_paths(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td)
            spec_dir = repo_root / "spec"
            canon_dir = repo_root / "canon"
            spec_dir.mkdir()
            canon_dir.mkdir()

            with patch("specdev_tools.canonical_lint.lint_canon_dir", return_value=[]) as p_canon_lint:
                code, out, err = self._run_cli(["canonical-lint", str(canon_dir), "--repo-root", str(repo_root)])
                self.assertEqual(0, code, msg=err)
                self.assertIn("OK", out)
                p_canon_lint.assert_called_once_with(
                    os.path.abspath(str(repo_root)),
                    canon_dir=os.path.abspath(str(canon_dir)),
                )

            with patch("specdev_tools.canonical_integrity.validate_canonical_integrity", return_value=[]) as p_integrity:
                code, out, err = self._run_cli(["canonical-integrity", str(spec_dir), "--repo-root", str(repo_root)])
                self.assertEqual(0, code, msg=err)
                self.assertIn("OK", out)
                p_integrity.assert_called_once_with(
                    os.path.abspath(str(repo_root)),
                    os.path.abspath(str(spec_dir)),
                    canon_dir="canon",
                )

            with patch("specdev_tools.canonical_autofix.canonical_autofix", return_value={}) as p_autofix:
                code, out, err = self._run_cli(["canonical-autofix", str(spec_dir), "--repo-root", str(repo_root)])
                self.assertEqual(0, code, msg=err)
                self.assertIn("OK (no changes)", out)
                p_autofix.assert_called_once_with(
                    os.path.abspath(str(repo_root)),
                    os.path.abspath(str(spec_dir)),
                    write=False,
                    canon_dir="canon",
                )

            with patch("specdev_tools.spec_quality_lint.lint_spec_quality", return_value=[]) as p_quality:
                code, out, err = self._run_cli(["spec-quality-lint", str(spec_dir), "--repo-root", str(repo_root)])
                self.assertEqual(0, code, msg=err)
                self.assertIn("OK", out)
                p_quality.assert_called_once_with(os.path.abspath(str(spec_dir)))

            with patch("specdev_tools.hallucination_lint.lint_hallucinations", return_value=[]) as p_hall:
                code, out, err = self._run_cli(["hallucination-lint", str(spec_dir), "--repo-root", str(repo_root)])
                self.assertEqual(0, code, msg=err)
                self.assertIn("OK", out)
                p_hall.assert_called_once_with(
                    os.path.abspath(str(spec_dir)),
                    repo_root=os.path.abspath(str(repo_root)),
                    canon_dir="canon",
                )

            with patch("specdev_tools.dependency_order_lint.lint_dependency_order", return_value=[]) as p_dep:
                code, out, err = self._run_cli(["dependency-order-lint", "--repo-root", str(repo_root)])
                self.assertEqual(0, code, msg=err)
                self.assertIn("OK", out)
                p_dep.assert_called_once_with(os.path.abspath(str(repo_root)))

            with patch("specdev_tools.validate._resolve_replay_base_ref", return_value="feature/x") as p_base, \
                 patch("specdev_tools.forward_replay_check.check_forward_replay", return_value=[]) as p_replay:
                code, out, err = self._run_cli(["forward-replay-check", "--repo-root", str(repo_root)])
                self.assertEqual(0, code, msg=err)
                self.assertIn("OK", out)
                p_base.assert_called_once_with(os.path.abspath(str(repo_root)))
                p_replay.assert_called_once_with(
                    os.path.abspath(str(repo_root)),
                    base_ref="feature/x",
                    diff_error_mode="error",
                )


if __name__ == "__main__":
    unittest.main()
