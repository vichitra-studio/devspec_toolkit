import json
import tempfile
import unittest
from pathlib import Path

from specdev_tools.validation.hallucination_lint import lint_hallucinations, _extract_path_from_string
from specdev_tools.validation.spec_check import run_spec_check
from specdev_tools.core.errors import render_errors


class HallucinationLintTests(unittest.TestCase):
    def test_detects_invalid_stage_and_trace_type(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            (root / "spec" / "07_nfrs.json").write_text(
                json.dumps(
                    {
                        "stage": "preprod",
                        "trace": [{"type": "unknown-type", "id": "x"}]
                    }
                ),
                encoding="utf-8",
            )
            errs = lint_hallucinations(str(root / "spec"))
            self.assertTrue(any("preprod" in e for e in render_errors(errs)))
            self.assertTrue(any("unknown-type" in e for e in render_errors(errs)))

    def test_detects_invalid_command_and_unknown_ref(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            (root / "spec" / "12_ci_gates.json").write_text(
                json.dumps(
                    {
                        "jobs": [
                            {
                                "job_id": "job-1",
                                "steps": [{"id": "s-1", "command": "inventcmd run"}],
                                "requires": ["job-x"],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            errs = lint_hallucinations(str(root / "spec"))
            self.assertTrue(any("inventcmd" in e for e in render_errors(errs)))
            self.assertTrue(any("job-x" in e for e in render_errors(errs)))

    def test_reference_context_tokenization(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            (root / "spec" / "x.json").write_text(
                json.dumps(
                    {
                        "id": "obj-1",
                        "note": "targetscope",
                        "meta": {"id": "obj-2"},
                        "trace": [{"type": "doc", "id": "obj-2"}],
                    }
                ),
                encoding="utf-8",
            )
            errs = lint_hallucinations(str(root / "spec"))
            self.assertFalse(any("obj-2" in e and "INVENTED" in e for e in render_errors(errs)))

    def test_detects_unknown_unit_without_canon_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            (root / "spec" / "07_nfrs.json").write_text(
                json.dumps(
                    {
                        "nfrs": [
                            {
                                "nfr_id": "n1",
                                "unit": "nonsense-unit",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            errs = lint_hallucinations(str(root / "spec"))
            self.assertTrue(any("nonsense-unit" in e for e in render_errors(errs)))

    def test_invalid_json_is_reported_not_raised(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            (root / "spec" / "bad.json").write_text("{bad", encoding="utf-8")
            errs = lint_hallucinations(str(root / "spec"), repo_root=str(root))
            self.assertTrue(any("invalid_json" in e for e in render_errors(errs)))

    def test_common_js_command_prefixes_are_allowed(self):
        for command in ("pnpm test", "yarn test", "npx vitest run", "ruff check .", "poetry run pytest"):
            with self.subTest(command=command):
                with tempfile.TemporaryDirectory() as td:
                    root = Path(td)
                    (root / "spec").mkdir()
                    (root / "tools").mkdir()
                    (root / "tools" / "command_prefixes.json").write_text(
                        json.dumps(
                            {
                                "allowed_prefixes": [
                                    "pnpm",
                                    "yarn",
                                    "npx",
                                    "ruff",
                                    "poetry",
                                ]
                            }
                        ),
                        encoding="utf-8",
                    )
                    (root / "spec" / "12_ci_gates.json").write_text(
                        json.dumps(
                            {
                                "jobs": [
                                    {
                                        "job_id": "job-1",
                                        "steps": [{"id": "s-1", "command": command}],
                                    }
                                ]
                            }
                        ),
                        encoding="utf-8",
                    )
                    errs = lint_hallucinations(str(root / "spec"), repo_root=str(root))
                    self.assertFalse(any("command=" in e for e in render_errors(errs)))

    def test_default_command_prefixes_work_without_config_file(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            (root / "spec" / "12_ci_gates.json").write_text(
                json.dumps(
                    {
                        "jobs": [
                            {
                                "job_id": "job-1",
                                "steps": [{"id": "s-1", "command": "npm test"}],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            errs = lint_hallucinations(str(root / "spec"), repo_root=str(root))
            self.assertFalse(any("command=npm" in e for e in render_errors(errs)))

    def test_canonical_load_errors_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            (root / "canon").mkdir()
            (root / "canon" / "aliases.json").write_text("{bad", encoding="utf-8")
            (root / "spec" / "07_nfrs.json").write_text(
                json.dumps({"nfrs": [{"nfr_id": "n1", "unit": "ms"}]}),
                encoding="utf-8",
            )
            errs = lint_hallucinations(str(root / "spec"), repo_root=str(root))
            self.assertTrue(any("invalid_aliases" in e for e in render_errors(errs)))

    def test_canonical_preflight_errors_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            (root / "canon").mkdir()
            (root / "canon" / "aliases.json").write_text(
                json.dumps(
                    {
                        "registry_version": "1.0.0",
                        "aliases": [{"kind": "term", "normalized": "jwt", "status": "active"}],
                    }
                ),
                encoding="utf-8",
            )
            (root / "spec" / "07_nfrs.json").write_text(
                json.dumps({"nfrs": [{"nfr_id": "n1", "unit": "ms"}]}),
                encoding="utf-8",
            )
            errs = lint_hallucinations(str(root / "spec"), repo_root=str(root))
            self.assertTrue(any("missing target_id" in e for e in render_errors(errs)))

    def test_missing_canon_dir_is_reported_when_required(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            (root / "spec" / "07_nfrs.json").write_text(
                json.dumps({"nfrs": [{"nfr_id": "n1", "unit": "ms"}]}),
                encoding="utf-8",
            )
            errs = lint_hallucinations(
                str(root / "spec"),
                repo_root=str(root),
                canon_dir="does_not_exist",
                require_canon_dir=True,
            )
            self.assertTrue(any("missing_canon_dir" in e for e in render_errors(errs)))

    def test_can_require_manifest_schema_registration(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "canon").mkdir()
            (root / "spec").mkdir()
            (root / "tools" / "schema_registry.json").write_text(json.dumps({}), encoding="utf-8")
            (root / "canon" / "manifest.json").write_text(
                json.dumps({"registry_version": "1.0.0", "entries": [], "aliases": []}),
                encoding="utf-8",
            )
            (root / "spec" / "07_nfrs.json").write_text(
                json.dumps({"nfrs": [{"nfr_id": "n1", "unit": "ms"}]}),
                encoding="utf-8",
            )
            strict = lint_hallucinations(
                str(root / "spec"),
                repo_root=str(root),
                require_manifest_schema_registration=True,
            )
            self.assertTrue(any("schema_uri_not_registered" in e for e in render_errors(strict)))

            relaxed = lint_hallucinations(
                str(root / "spec"),
                repo_root=str(root),
                require_manifest_schema_registration=False,
            )
            self.assertFalse(any("schema_uri_not_registered" in e.render() for e in relaxed))


    def test_existing_structures_missing_path(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            (root / "spec" / "13_impl.json").write_text(
                json.dumps({"existing_structures": ["src/does_not_exist.py"]}),
                encoding="utf-8",
            )
            errs = lint_hallucinations(str(root / "spec"), repo_root=str(root))
            self.assertTrue(any("EXISTING_STRUCTURE_PATH_NOT_FOUND" in e for e in render_errors(errs)))

    def test_existing_structures_real_path(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            (root / "src").mkdir()
            (root / "src" / "real_file.py").write_text("# exists", encoding="utf-8")
            (root / "spec" / "13_impl.json").write_text(
                json.dumps({"existing_structures": ["src/real_file.py"]}),
                encoding="utf-8",
            )
            errs = lint_hallucinations(str(root / "spec"), repo_root=str(root))
            self.assertFalse(any("EXISTING_STRUCTURE_PATH_NOT_FOUND" in e for e in render_errors(errs)))

    def test_existing_structures_object_path_missing(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            (root / "spec" / "13_impl.json").write_text(
                json.dumps({"existing_structures": [{"signature": "foo", "source_file": "src/does_not_exist.py"}]}),
                encoding="utf-8",
            )
            errs = lint_hallucinations(str(root / "spec"), repo_root=str(root))
            self.assertTrue(any("EXISTING_STRUCTURE_PATH_NOT_FOUND" in e for e in render_errors(errs)))

    def test_existing_structures_object_path_real(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            (root / "src").mkdir()
            (root / "src" / "real_file.py").write_text("# exists", encoding="utf-8")
            (root / "spec" / "13_impl.json").write_text(
                json.dumps({"existing_structures": [{"signature": "foo", "source_file": "src/real_file.py"}]}),
                encoding="utf-8",
            )
            errs = lint_hallucinations(str(root / "spec"), repo_root=str(root))
            self.assertFalse(any("EXISTING_STRUCTURE_PATH_NOT_FOUND" in e for e in render_errors(errs)))

    def test_linked_test_expectation_missing_file(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            (root / "spec" / "13_impl.json").write_text(
                json.dumps({"linked_test_expectation": "tests/missing_test.py"}),
                encoding="utf-8",
            )
            errs = lint_hallucinations(str(root / "spec"), repo_root=str(root))
            self.assertTrue(any("LINKED_TEST_FILE_NOT_FOUND" in e for e in render_errors(errs)))

    # ------------------------------------------------------------------
    # Submodule path resolution: git_root vs repo_root (Bug 1 & Bug 2)
    # ------------------------------------------------------------------

    def test_existing_structures_git_root_resolves_host_file(self):
        """Bug 1A regression: file at git_root (host repo) must not fire E530
        even when repo_root is a subdirectory (toolkit submodule)."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            toolkit = root / "devspec_toolkit"
            toolkit.mkdir()
            spec = toolkit / "spec"
            spec.mkdir()
            # File exists at host root, not under toolkit submodule
            (root / "theme").mkdir()
            (root / "theme" / "bootstrap.sh").write_text("#!/bin/bash", encoding="utf-8")
            (spec / "16a_plan.json").write_text(
                json.dumps({"existing_structures": ["theme/bootstrap.sh"]}),
                encoding="utf-8",
            )
            errs = lint_hallucinations(
                str(spec), repo_root=str(toolkit), git_root=str(root)
            )
            self.assertFalse(
                any("EXISTING_STRUCTURE_PATH_NOT_FOUND" in e for e in render_errors(errs)),
                "file at git_root must not trigger E530 in submodule deployment",
            )

    def test_existing_structures_emdash_composite_no_error(self):
        """Bug 1B regression: existing_structures with em-dash description suffix
        must extract the path portion and not fire E530 when the file exists."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            (root / "theme").mkdir()
            (root / "theme" / "bootstrap.sh").write_text("#!/bin/bash", encoding="utf-8")
            value = "theme/bootstrap.sh \u2014 main bootstrap orchestration script"
            (root / "spec" / "16a_plan.json").write_text(
                json.dumps({"existing_structures": [value]}),
                encoding="utf-8",
            )
            errs = lint_hallucinations(str(root / "spec"), repo_root=str(root))
            self.assertFalse(
                any("EXISTING_STRUCTURE_PATH_NOT_FOUND" in e for e in render_errors(errs)),
                "em-dash composite must extract path before existence check",
            )

    def test_existing_structures_emdash_composite_missing(self):
        """Em-dash composite: if the extracted path doesn't exist, E530 must still fire."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            value = "theme/does_not_exist.sh \u2014 some description"
            (root / "spec" / "16a_plan.json").write_text(
                json.dumps({"existing_structures": [value]}),
                encoding="utf-8",
            )
            errs = lint_hallucinations(str(root / "spec"), repo_root=str(root))
            self.assertTrue(
                any("EXISTING_STRUCTURE_PATH_NOT_FOUND" in e for e in render_errors(errs)),
                "missing path in em-dash composite must still fire E530",
            )

    def test_linked_test_expectation_playwright_command_no_error(self):
        """Bug 2 regression: playwright command with --grep flag must extract the
        test file path and not fire E530 when the file exists."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            (root / "tests").mkdir(parents=True)
            (root / "tests" / "bootstrap.test.js").write_text("// test", encoding="utf-8")
            cmd = "npx playwright test tests/bootstrap.test.js --grep 'publish post success'"
            (root / "spec" / "16a_plan.json").write_text(
                json.dumps({"linked_test_expectation": cmd}),
                encoding="utf-8",
            )
            errs = lint_hallucinations(str(root / "spec"), repo_root=str(root))
            self.assertFalse(
                any("LINKED_TEST_FILE_NOT_FOUND" in e for e in render_errors(errs)),
                "playwright command must extract test file path before existence check",
            )

    def test_linked_test_expectation_playwright_command_missing(self):
        """Playwright command: if the extracted test file doesn't exist, E530 fires."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            cmd = "npx playwright test tests/missing.test.js --grep 'some test'"
            (root / "spec" / "16a_plan.json").write_text(
                json.dumps({"linked_test_expectation": cmd}),
                encoding="utf-8",
            )
            errs = lint_hallucinations(str(root / "spec"), repo_root=str(root))
            self.assertTrue(
                any("LINKED_TEST_FILE_NOT_FOUND" in e for e in render_errors(errs)),
                "missing test file in playwright command must fire E530",
            )

    def test_linked_test_expectation_compound_command_no_error(self):
        """Compound shell commands (&&) must not fire E530 — there is no single
        authoritative test-file path to validate in a compound command."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            cmd = "npx gulp zip && npx gscan theme/dist/vc-collective.zip"
            (root / "spec" / "16a_plan.json").write_text(
                json.dumps({"linked_test_expectation": cmd}),
                encoding="utf-8",
            )
            errs = lint_hallucinations(str(root / "spec"), repo_root=str(root))
            self.assertFalse(
                any("LINKED_TEST_FILE_NOT_FOUND" in e for e in render_errors(errs)),
                "compound && command must not fire E530 (no single test file to validate)",
            )

    def test_existing_structures_emdash_composite_with_git_root(self):
        """Combined Bug 1A+1B: em-dash composite string AND git_root != repo_root.
        File exists at git_root; path must be extracted from composite before
        the existence check resolves against git_root."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            toolkit = root / "devspec_toolkit"
            toolkit.mkdir()
            spec = toolkit / "spec"
            spec.mkdir()
            (root / "theme").mkdir()
            (root / "theme" / "bootstrap.sh").write_text("#!/bin/bash", encoding="utf-8")
            value = "theme/bootstrap.sh \u2014 main bootstrap orchestration script"
            (spec / "16a_plan.json").write_text(
                json.dumps({"existing_structures": [value]}),
                encoding="utf-8",
            )
            errs = lint_hallucinations(
                str(spec), repo_root=str(toolkit), git_root=str(root)
            )
            self.assertFalse(
                any("EXISTING_STRUCTURE_PATH_NOT_FOUND" in e for e in render_errors(errs)),
                "em-dash composite at git_root must not fire E530 in submodule deployment",
            )

    def test_linked_test_expectation_git_root_resolves_host_file(self):
        """Bug 2A regression: test file at git_root must not fire E530 in
        submodule deployment where repo_root is the toolkit subdirectory."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            toolkit = root / "devspec_toolkit"
            toolkit.mkdir()
            spec = toolkit / "spec"
            spec.mkdir()
            (root / "tests").mkdir()
            (root / "tests" / "bootstrap.test.js").write_text("// test", encoding="utf-8")
            cmd = "npx playwright test tests/bootstrap.test.js --grep 'x'"
            (spec / "16a_plan.json").write_text(
                json.dumps({"linked_test_expectation": cmd}),
                encoding="utf-8",
            )
            errs = lint_hallucinations(
                str(spec), repo_root=str(toolkit), git_root=str(root)
            )
            self.assertFalse(
                any("LINKED_TEST_FILE_NOT_FOUND" in e for e in render_errors(errs)),
                "test file at git_root must not trigger E530 in submodule deployment",
            )

    def test_nfr_refs_unresolved(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            (root / "spec" / "07_nfrs.json").write_text(
                json.dumps({"nfrs": [{"nfr_id": "nfr-perf", "unit": "ms"}]}),
                encoding="utf-8",
            )
            (root / "spec" / "13_impl.json").write_text(
                json.dumps({"nfr_refs": ["nfr-perf", "nfr-invented"]}),
                encoding="utf-8",
            )
            errs = lint_hallucinations(str(root / "spec"), repo_root=str(root))
            self.assertTrue(any("UNRESOLVED_NFR_REF" in e and "nfr-invented" in e for e in render_errors(errs)))
            self.assertFalse(any("UNRESOLVED_NFR_REF" in e and "nfr-perf" in e for e in render_errors(errs)))

    def test_nfr_refs_skipped_when_07_absent(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            (root / "spec" / "13_impl.json").write_text(
                json.dumps({"nfr_refs": ["nfr-anything"]}),
                encoding="utf-8",
            )
            errs = lint_hallucinations(str(root / "spec"), repo_root=str(root))
            self.assertFalse(any("UNRESOLVED_NFR_REF" in e for e in render_errors(errs)))


class ExtractPathFromStringTests(unittest.TestCase):
    """Unit tests for _extract_path_from_string covering all four branches."""

    def test_emdash_composite_returns_path_prefix(self):
        result = _extract_path_from_string("theme/bootstrap.sh \u2014 main orchestration script")
        self.assertEqual(result, "theme/bootstrap.sh")

    def test_emdash_composite_strips_whitespace(self):
        result = _extract_path_from_string("  src/foo.py  \u2014 description")
        self.assertEqual(result, "src/foo.py")

    def test_compound_and_returns_empty(self):
        result = _extract_path_from_string("npx gulp zip && npx gscan theme/dist/vc.zip")
        self.assertEqual(result, "")

    def test_compound_or_returns_empty(self):
        result = _extract_path_from_string("cmd1 || theme/fallback.sh")
        self.assertEqual(result, "")

    def test_compound_semicolon_returns_empty(self):
        result = _extract_path_from_string("cmd1 ; theme/fallback.sh")
        self.assertEqual(result, "")

    def test_single_command_extracts_file_token(self):
        result = _extract_path_from_string(
            "npx playwright test tests/bootstrap.test.js --grep 'publish post'"
        )
        self.assertEqual(result, "tests/bootstrap.test.js")

    def test_bare_path_returned(self):
        self.assertEqual(_extract_path_from_string("src/real_file.py"), "src/real_file.py")

    def test_no_path_token_returns_empty(self):
        self.assertEqual(_extract_path_from_string("npm audit --audit-level=high"), "")

    def test_empty_string_returns_empty(self):
        self.assertEqual(_extract_path_from_string(""), "")

    def test_flag_only_tokens_skipped(self):
        self.assertEqual(_extract_path_from_string("--verbose --dry-run"), "")

    def test_quoted_token_skipped_finds_next(self):
        result = _extract_path_from_string("cmd 'some/quoted' tests/real.test.js")
        self.assertEqual(result, "tests/real.test.js")

    def test_emdash_no_surrounding_spaces(self):
        """Em-dash without surrounding spaces must still split correctly."""
        result = _extract_path_from_string("theme/bootstrap.sh\u2014description text")
        self.assertEqual(result, "theme/bootstrap.sh")

    def test_long_option_value_not_treated_as_path(self):
        """--prefix <dir> argument value must not be returned as the path."""
        result = _extract_path_from_string("npx --prefix theme/subdir playwright test")
        self.assertEqual(result, "")

    def test_long_option_value_skipped_finds_subsequent_path(self):
        """When a long option is followed by a value and then a real path,
        the real path must be returned, not the option value."""
        result = _extract_path_from_string(
            "npx --prefix theme/subdir playwright test tests/bootstrap.test.js"
        )
        self.assertEqual(result, "tests/bootstrap.test.js")


class SpecCheckGitRootForwardingTests(unittest.TestCase):
    """Integration test: run_spec_check must forward git_root to lint_hallucinations.

    Uses the real toolkit root as repo_root (schemas and canon exist there) and
    a tempdir for spec artifacts and host-repo files.  This lets canonical-lint
    pass cleanly so hallucination-lint actually runs.

    If git_root=git_root is ever removed from spec_check._run_checks, the
    positive test will regress to a false-positive E530.
    """

    # Real toolkit root — schemas, canon, schema_registry.json all live here.
    _TOOLKIT_ROOT: str = str(Path(__file__).parent.parent.parent.parent.parent)

    def test_existing_structures_at_git_root_no_e530_via_spec_check(self):
        """run_spec_check must not fire E530 for a file that exists at git_root
        (host repo root) when repo_root is the toolkit directory."""
        with tempfile.TemporaryDirectory() as td:
            host = Path(td)
            spec = host / "spec"
            spec.mkdir()
            (host / "theme").mkdir()
            (host / "theme" / "bootstrap.sh").write_text("#!/bin/bash", encoding="utf-8")
            (spec / "16a_plan.json").write_text(
                json.dumps({"existing_structures": ["theme/bootstrap.sh"]}),
                encoding="utf-8",
            )
            errs = run_spec_check(
                repo_root=self._TOOLKIT_ROOT,
                spec_dir=str(spec),
                git_root=str(host),
            )
            e530 = [e for e in render_errors(errs) if "EXISTING_STRUCTURE_PATH_NOT_FOUND" in e]
            self.assertEqual(
                e530, [],
                "spec_check must forward git_root; host-repo file must not trigger E530",
            )

    def test_existing_structures_at_git_root_fires_e530_without_git_root(self):
        """Regression guard: without git_root, the same host-repo file is not
        found under toolkit root and triggers E530 (proving the forward matters)."""
        with tempfile.TemporaryDirectory() as td:
            host = Path(td)
            spec = host / "spec"
            spec.mkdir()
            (host / "theme").mkdir()
            (host / "theme" / "bootstrap.sh").write_text("#!/bin/bash", encoding="utf-8")
            (spec / "16a_plan.json").write_text(
                json.dumps({"existing_structures": ["theme/bootstrap.sh"]}),
                encoding="utf-8",
            )
            errs = run_spec_check(
                repo_root=self._TOOLKIT_ROOT,
                spec_dir=str(spec),
                git_root=None,
            )
            e530 = [e for e in render_errors(errs) if "EXISTING_STRUCTURE_PATH_NOT_FOUND" in e]
            self.assertGreater(
                len(e530), 0,
                "without git_root, host-repo file must trigger E530 (file not under toolkit root)",
            )


if __name__ == "__main__":
    unittest.main()
