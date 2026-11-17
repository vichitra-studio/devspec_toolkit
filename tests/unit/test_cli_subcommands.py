"""Tests for R9 CLI commands: env-check and dag-lint.

Validates that the two new commands registered in T28 are callable,
produce expected output, and respect the --repo-root flag.
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from unittest.mock import patch

from specdev_tools import cli
from specdev_tools.core.toolkit_root import detect_toolkit_root
from specdev_tools.trace.lockfile import Lock, LockEntry, serialise_lock

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
        code, _, err = self._run_cli(["dag-lint", "--repo-root", str(REPO_ROOT)])
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
        code, _, err = self._run_cli(["dag-lint", "--repo-root", "/tmp/nonexistent_dag_test"])
        self.assertEqual(code, 1)
        self.assertIn("E520", err)

    def test_dag_lint_detects_missing_step_order(self):
        """dag-lint reports E520 when step_order.json is absent."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            # Empty directory — no tools/step_order.json
            code, _, err = self._run_cli(["dag-lint", "--repo-root", tmpdir])
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
            code, _, err = self._run_cli(["dag-lint", "--repo-root", tmpdir])
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
            code, _, err = self._run_cli(["dag-lint", "--repo-root", tmpdir])
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
            code, _, err = self._run_cli(["dag-lint", "--repo-root", tmpdir])
            self.assertEqual(code, 1)
            self.assertIn("E599", err)
            self.assertIn("DAG_CONSUMER_INCONSISTENCY", err)


class TestExtractionIntentCheck(_CliMixin, unittest.TestCase):
    """Tests for the extraction-intent-check command."""

    def test_extraction_intent_check_registered_and_callable(self):
        """extraction-intent-check runs without crashing on the real repo."""
        code, _, err = self._run_cli(["extraction-intent-check", "--repo-root", str(REPO_ROOT)])
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
            code, _, _ = self._run_cli(["extraction-intent-check", "--repo-root", tmpdir])
            self.assertEqual(code, 0)


EXAMPLE_SPEC = REPO_ROOT / "tests" / "fixtures" / "graph_example" / "spec"
_EXAMPLE_ID = "ac-password-reset-3"
_ROOT_FLAGS = ["--repo-root", str(REPO_ROOT), "--spec-root", str(EXAMPLE_SPEC)]


class TestGraphCommands(_CliMixin, unittest.TestCase):
    """The graph commands ``node``, ``trace`` and ``diff`` (WI-M4-11)."""

    def _example_copy(self) -> Path:
        import shutil
        import tempfile

        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        return Path(shutil.copytree(EXAMPLE_SPEC, tmp / "spec"))

    def test_node_trace_diff_accept_three_root_flags(self):
        """The three-flag default of CLAUDE.md never gives "unrecognized arguments" on a graph command."""
        flags = ["--repo-root", "tk", "--spec-root", "sp", "--git-root", "host"]
        parsed = cli.build_parser()
        for argv in (["trace", "an-id", *flags], ["diff", "v1", "v2", *flags]):
            with self.subTest(command=argv[0]):
                args = parsed.parse_args(argv)
                self.assertEqual((args.repo_root, args.spec_root, args.git_root), ("tk", "sp", "host"))
        code, out, err = self._run_cli(["node", _EXAMPLE_ID, *_ROOT_FLAGS, "--git-root", str(REPO_ROOT)])
        self.assertEqual(code, 0, err)
        self.assertIn(_EXAMPLE_ID, out)
        code, _, err = self._run_cli(["trace", _EXAMPLE_ID, *_ROOT_FLAGS, "--git-root", str(REPO_ROOT)])
        self.assertEqual(code, 0, err)

    def test_node_status_subcommand_dispatch(self):
        spec = self._example_copy()
        flags = ["--repo-root", str(REPO_ROOT), "--spec-root", str(spec)]
        code, out, err = self._run_cli(["node", "status", _EXAMPLE_ID, "deprecated", *flags])
        self.assertEqual(code, 0, err)
        self.assertEqual(out.strip(), f"{_EXAMPLE_ID}: active -> deprecated (04_fr_list.json)")
        self.assertIn('"lifecycle": "deprecated"', (spec / "04_fr_list.json").read_text(encoding="utf-8"))
        code, out, err = self._run_cli(["node", "status", _EXAMPLE_ID, "active", *flags])
        self.assertEqual(code, 0, err)
        self.assertNotIn('"lifecycle"', (spec / "04_fr_list.json").read_text(encoding="utf-8"))
        code, _, err = self._run_cli(["node", "status", "ac-no-such-node", "active", *flags])
        self.assertEqual(code, 1)
        self.assertTrue(err.startswith("E705"), err)

    def test_node_explicit_repo_root_after_id(self):
        """``node <id> --repo-root X --json`` works without the auto-detect of the default ``.``."""
        code, out, err = self._run_cli(["node", _EXAMPLE_ID, *_ROOT_FLAGS, "--json"])
        self.assertEqual(code, 0, err)
        self.assertEqual([node["id"] for node in json.loads(out)["nodes"]], [_EXAMPLE_ID])

    def test_node_show_disambiguates(self):
        """An id that is also a subcommand name is read through ``node show``; the bare form is the subcommand."""
        for word in ("status", "candidates"):
            with self.subTest(word=word):
                code, _, err = self._run_cli(["node", "show", word, *_ROOT_FLAGS])
                self.assertEqual(code, 1)
                self.assertTrue(err.startswith("E706") and f"'{word}'" in err, err)
                code, _, _ = self._run_cli(["node", word, *_ROOT_FLAGS])
                self.assertEqual(code, 2)

    def test_json_flag_shapes(self):
        spec = self._example_copy()
        flags = ["--repo-root", str(REPO_ROOT), "--spec-root", str(spec), "--json"]
        shapes = {
            ("node", _EXAMPLE_ID): {"nodes", "errors"},
            ("node", "candidates", "--kind", "api", "--field", "derives_from"): {"kind", "field", "total", "candidates"},
            ("node", "status", _EXAMPLE_ID, "deprecated"): {"node_id", "old", "new", "file", "jq_path"},
            ("trace", _EXAMPLE_ID): {"entry", "up", "down"},
            ("trace", "PWRESET_CONFIRM_EXPIRED_01", "--recipe", "16b"): {"role", "start", "sections", "counts", "ambiguity_report", "dependency_report"},
        }
        for argv, keys in shapes.items():
            with self.subTest(argv=argv):
                code, out, err = self._run_cli([*argv, *flags])
                self.assertEqual(code, 0, err)
                self.assertEqual(set(json.loads(out)), keys)

    def test_json_flag_prints_a_finding_as_the_standard_envelope(self):
        code, out, _ = self._run_cli(["trace", "no-such-id", *_ROOT_FLAGS, "--json"])
        self.assertEqual(code, 1)
        document = json.loads(out)
        self.assertEqual((document["command"], document["status"], document["errors"][0]["code"]), ("trace", "FAIL", "E706"))

    def test_trace_recipe_flags_are_checked(self):
        for argv in (["--recipe", "16b", "--up"], ["--expand"], ["--since", "v1"]):
            with self.subTest(argv=argv):
                code, _, err = self._run_cli(["trace", _EXAMPLE_ID, *argv, *_ROOT_FLAGS])
                self.assertEqual(code, 2)
                self.assertIn("specdev trace: error:", err)

    def test_candidates_needs_exactly_one_of_kind_and_for(self):
        for argv in (["--field", "derives_from"], ["--kind", "api", "--for", _EXAMPLE_ID, "--field", "derives_from"]):
            with self.subTest(argv=argv):
                code, _, _ = self._run_cli(["node", "candidates", *argv, *_ROOT_FLAGS])
                self.assertEqual(code, 2)

    def test_detect_toolkit_root_finds_the_submodule_only_for_the_default(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / "devspec_toolkit" / "tools" / "specdev_tools" / "__init__.py"
            marker.parent.mkdir(parents=True)
            marker.touch()
            self.assertEqual(detect_toolkit_root(".", cwd=tmp), str(Path(tmp) / "devspec_toolkit"))
            self.assertEqual(detect_toolkit_root("elsewhere", cwd=tmp), "elsewhere")
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(detect_toolkit_root(".", cwd=tmp), ".")


class TestTraceCommands(_CliMixin, unittest.TestCase):
    """The trace commands (``stale``), registered by ``trace.commands.add_trace_parsers`` (WI-M5-05)."""

    def test_stale_accepts_the_three_root_flags_and_its_own(self):
        flags = ["--repo-root", "tk", "--spec-root", "sp", "--git-root", "host"]
        args = cli.build_parser().parse_args(["stale", "--step", "06", "--diff", "--json", *flags])
        self.assertEqual((args.repo_root, args.spec_root, args.git_root), ("tk", "sp", "host"))
        self.assertEqual((args.step, args.diff, args.json_output), ("06", True, True))
        defaults = cli.build_parser().parse_args(["stale"])
        self.assertEqual((defaults.step, defaults.diff, defaults.json_output), (None, False, False))

    def test_stale_dispatches_to_its_handler(self):
        code, out, err = self._run_cli(["stale", *_ROOT_FLAGS, "--git-root", str(EXAMPLE_SPEC.parent)])
        self.assertEqual(code, 0, err)
        self.assertEqual(out.strip(), "stale: no pending replay")

    def test_stale_json_flag_shape(self):
        code, out, err = self._run_cli(["stale", *_ROOT_FLAGS, "--git-root", str(EXAMPLE_SPEC.parent), "--json"])
        self.assertEqual(code, 0, err)
        self.assertEqual(set(json.loads(out)), {"steps", "totals"})

    def test_stale_on_a_missing_spec_folder_is_e520(self):
        code, _, err = self._run_cli(["stale", "--repo-root", str(REPO_ROOT), "--spec-root", str(REPO_ROOT / "no-such-spec")])
        self.assertEqual(code, 1)
        self.assertTrue(err.startswith("E520"), err)

    def test_attest_accepts_the_three_root_flags_and_its_own(self):
        flags = ["--repo-root", "tk", "--spec-root", "sp", "--git-root", "host"]
        args = cli.build_parser().parse_args(["attest", "a-node", "--field", "f", "--target", "t", "--yes", "--dry-run", "--json", *flags])
        self.assertEqual((args.repo_root, args.spec_root, args.git_root), ("tk", "sp", "host"))
        self.assertEqual((args.node_id, args.field, args.target, args.yes, args.dry_run, args.json_output), ("a-node", "f", "t", True, True, True))
        self.assertEqual((args.step, args.prune), (None, False))
        by_step = cli.build_parser().parse_args(["attest", "--step", "06"])
        self.assertEqual((by_step.node_id, by_step.step, by_step.yes, by_step.dry_run), (None, "06", False, False))
        self.assertTrue(cli.build_parser().parse_args(["attest", "--prune"]).prune)

    def test_attest_dispatches_to_its_handler(self):
        code, out, err = self._run_cli(["attest", _EXAMPLE_ID, *_ROOT_FLAGS, "--git-root", str(EXAMPLE_SPEC.parent)])
        self.assertEqual(code, 0, err)
        self.assertEqual(out.strip(), "attest: nothing to attest")

    def test_attest_needs_a_node_a_step_or_prune(self):
        code, _, err = self._run_cli(["attest", *_ROOT_FLAGS])
        self.assertEqual(code, 2)
        self.assertIn("one of the arguments", err)

    def test_attest_on_a_missing_spec_folder_is_e520(self):
        code, _, err = self._run_cli(["attest", "--prune", "--repo-root", str(REPO_ROOT), "--spec-root", str(REPO_ROOT / "no-such-spec")])
        self.assertEqual(code, 1)
        self.assertTrue(err.startswith("E520"), err)


class TestLockCommand(_CliMixin, unittest.TestCase):
    """``specdev lock merge`` and ``lock install-driver``, registered by ``trace.commands.add_trace_parsers`` (WI-M5-07)."""

    def _lock_text(self, *digits: str) -> str:
        entries = [LockEntry(f"fr-{d}", "api_refs", f"api-{d}", f"sha256:{d * 64}", f"sha256:{d * 64}") for d in digits]
        return serialise_lock(Lock(tuple(entries)))

    def test_merge_takes_the_four_positionals(self):
        args = cli.build_parser().parse_args(["lock", "merge", "o", "a", "b", "spec/extras/trace.lock.json"])
        self.assertEqual((args.base, args.ours, args.theirs, args.pathname), ("o", "a", "b", "spec/extras/trace.lock.json"))

    def test_install_driver_takes_the_root_flags_and_a_required_driver_command(self):
        args = cli.build_parser().parse_args(["lock", "install-driver", "--driver-command", "x lock merge", "--git-root", "h", "--spec-root", "s", "--repo-root", "t", "--json"])
        self.assertEqual((args.driver_command, args.git_root, args.spec_root, args.json_output), ("x lock merge", "h", "s", True))
        code, _, err = self._run_cli(["lock", "install-driver"])
        self.assertEqual(code, 2, err)

    def test_lock_without_a_subcommand_is_a_usage_error(self):
        code, _, _ = self._run_cli(["lock"])
        self.assertEqual(code, 2)

    def test_merge_dispatches_and_writes_the_result_over_ours(self):
        with tempfile.TemporaryDirectory() as tmp:
            files = {name: Path(tmp) / name for name in ("base", "ours", "theirs")}
            for name, text in (("base", self._lock_text("1")), ("ours", self._lock_text("1", "2")), ("theirs", self._lock_text("1", "3"))):
                files[name].write_text(text, encoding="utf-8")
            code, out, err = self._run_cli(["lock", "merge", str(files["base"]), str(files["ours"]), str(files["theirs"]), "p"])
            self.assertEqual((code, out, err), (0, "", ""))
            self.assertEqual(files["ours"].read_text(encoding="utf-8"), self._lock_text("1", "2", "3"))

    def test_merge_of_a_malformed_version_exits_1_with_e760_and_leaves_ours(self):
        with tempfile.TemporaryDirectory() as tmp:
            base, ours, theirs = (Path(tmp) / name for name in ("base", "ours", "theirs"))
            for path, text in ((base, self._lock_text("1")), (ours, self._lock_text("2")), (theirs, "<<<<<<< x\n")):
                path.write_text(text, encoding="utf-8")
            code, out, err = self._run_cli(["lock", "merge", str(base), str(ours), str(theirs), "p"])
            self.assertEqual(code, 1)
            self.assertTrue(err.startswith("E760"), err)
            self.assertEqual(ours.read_text(encoding="utf-8"), self._lock_text("2"))


if __name__ == "__main__":
    unittest.main()
