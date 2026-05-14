import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

from specdev_tools.validation.hallucination_lint import lint_hallucinations, _extract_path_from_string, _collect_path_value_pairs
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

    def test_linked_test_expectation_bash_c_wrapped_no_error(self):
        """Drift #2 (linked_test_expectation side): `bash -c "<cmd>"` wrap must
        unwrap before path extraction, so the inner test path is checked and no
        spurious E530 fires when the file exists."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            (root / "tests").mkdir(parents=True)
            (root / "tests" / "wrapped.test.js").write_text("// test", encoding="utf-8")
            cmd = 'bash -c "npx playwright test tests/wrapped.test.js"'
            (root / "spec" / "16a_plan.json").write_text(
                json.dumps({"linked_test_expectation": cmd}),
                encoding="utf-8",
            )
            errs = lint_hallucinations(str(root / "spec"), repo_root=str(root))
            self.assertFalse(
                any("LINKED_TEST_FILE_NOT_FOUND" in e for e in render_errors(errs)),
                "bash -c wrap must not break linked_test_expectation path extraction",
            )

    def test_linked_test_expectation_bash_c_wrapped_missing_fires(self):
        """`bash -c "..."` wrap unwraps, then existence check still fires E530
        when the inner path is missing — wrapping is not an escape from the check."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            cmd = 'bash -c "npx playwright test tests/does_not_exist.test.js"'
            (root / "spec" / "16a_plan.json").write_text(
                json.dumps({"linked_test_expectation": cmd}),
                encoding="utf-8",
            )
            errs = lint_hallucinations(str(root / "spec"), repo_root=str(root))
            self.assertTrue(
                any("LINKED_TEST_FILE_NOT_FOUND" in e for e in render_errors(errs)),
                "missing inner path under bash -c wrap must still fire E530",
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

    def test_bash_c_double_quoted_wrapper_unwrapped(self):
        """`bash -c "..."` wrap must not break path extraction. Drift #2 (linked_test_expectation side)."""
        result = _extract_path_from_string(
            'bash -c "npx playwright test tests/bootstrap.test.js"'
        )
        self.assertEqual(result, "tests/bootstrap.test.js")

    def test_bash_c_single_quoted_wrapper_unwrapped(self):
        result = _extract_path_from_string(
            "bash -c 'npx playwright test tests/bootstrap.test.js'"
        )
        self.assertEqual(result, "tests/bootstrap.test.js")

    def test_sh_c_wrapper_unwrapped(self):
        result = _extract_path_from_string(
            'sh -c "vitest run src/foo.test.js"'
        )
        self.assertEqual(result, "src/foo.test.js")

    def test_bash_c_with_compound_inner_returns_empty(self):
        """`bash -c "cd theme && npx ..."` unwraps to compound; returns '' (no single path)."""
        result = _extract_path_from_string(
            'bash -c "cd theme && npx playwright test foo.test.js"'
        )
        self.assertEqual(result, "")

    def test_bash_c_with_bare_path_inner(self):
        result = _extract_path_from_string('bash -c "tests/standalone.test.js"')
        self.assertEqual(result, "tests/standalone.test.js")

    def test_bash_c_malformed_quoting_falls_through(self):
        """Mismatched/missing quotes after `bash -c ` still extract the inner unquoted text."""
        result = _extract_path_from_string('bash -c "npx playwright test foo.test.js')
        # Inner kept as-is (leading quote retained); first path-like token wins.
        self.assertEqual(result, "foo.test.js")

    def test_no_shell_wrapper_unchanged(self):
        """Strings that do not start with `bash -c ` / `sh -c ` are unaffected."""
        self.assertEqual(_extract_path_from_string("src/real.py"), "src/real.py")


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


class CommandRefBypassAndProjectAllowlistTests(unittest.TestCase):
    """Drift #2 — ref-bypass on test_commands[].command and project-tier allowlist.

    Assertions filter on ``SpecError.code == "E530"`` (not substring matches on
    rendered text) so the rendered message format can evolve without breaking tests.
    """

    # --- helpers ---------------------------------------------------------

    def _write_step16(self, spec_dir: Path, command_entry: dict) -> None:
        # Nest under the real schema shape (plan.review_requirements.test_commands)
        # so the fixture mirrors a valid 16a artifact. hallucination-lint walks the
        # tree generically, so structural depth does not affect verb-prefix checks —
        # this nesting is for fixture fidelity, not lint behavior.
        (spec_dir / "16_impl_context.json").write_text(
            json.dumps({
                "plan": {
                    "review_requirements": {"test_commands": [command_entry]},
                },
            }),
            encoding="utf-8",
        )

    def _write_ci_gates(self, spec_dir: Path, commands: list[str]) -> None:
        (spec_dir / "12_ci_gates.json").write_text(
            json.dumps({
                "jobs": [{
                    "job_id": "job-1",
                    "steps": [
                        {"id": f"s-{i}", "command": cmd}
                        for i, cmd in enumerate(commands, start=1)
                    ],
                }]
            }),
            encoding="utf-8",
        )

    @staticmethod
    def _e530_for_prefix(errs, prefix: str) -> list:
        """Return E530 errors whose message names *prefix* as the offending verb."""
        # Message format: "INVENTED_ENUM_OR_ID {rel}:{p}={prefix} ..."
        return [e for e in errs if e.code == "E530" and f"={prefix} " in e.message + " "]

    # --- ref-bypass behavior --------------------------------------------

    def test_resolved_command_ref_bypasses_e530(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            self._write_step16(
                root / "spec",
                {"command": "jq -e '.foo'",
                 "command_ref": {"id": "cn:project:command:jq"}},
            )
            errs = lint_hallucinations(str(root / "spec"), repo_root=str(root))
            self.assertEqual(
                self._e530_for_prefix(errs, "jq"), [],
                f"resolved command_ref must bypass E530; got: {[e.message for e in errs]}",
            )

    def test_well_formed_but_unresolvable_cn_id_also_bypasses_by_design(self):
        """A `cn:` prefixed id that does NOT resolve to any canon entry still bypasses
        verb-validation here. canonical-integrity (E110) is responsible for catching
        the unresolvable id; hallucination-lint deliberately does not duplicate that
        check. This test pins that documented design choice — change it only if the
        contract between the two linters changes."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            self._write_step16(
                root / "spec",
                {"command": "jq -e '.foo'",
                 "command_ref": {"id": "cn:project:command:totally-invented-no-match"}},
            )
            errs = lint_hallucinations(str(root / "spec"), repo_root=str(root))
            self.assertEqual(
                self._e530_for_prefix(errs, "jq"), [],
                "Per design, well-formed cn: id bypasses E530 even when unresolvable; "
                "canonical-integrity owns ref-resolution (E110)."
            )

    def test_unresolved_command_ref_still_fires_e530(self):
        """Variants where the bypass condition is NOT met must still trigger E530."""
        for label, ref_value in (
            ("string-not-dict",     "cn:project:command:jq"),
            ("dict-missing-id",     {"label": "jq"}),
            ("id-without-cn-prefix", {"id": "project:command:jq"}),
            ("id-not-a-string",     {"id": 123}),
            ("ref-is-list",         ["cn:project:command:jq"]),
            ("ref-is-int",          42),
            ("ref-is-none",         None),
        ):
            with self.subTest(label=label):
                with tempfile.TemporaryDirectory() as td:
                    root = Path(td)
                    (root / "spec").mkdir()
                    self._write_step16(
                        root / "spec",
                        {"command": "jq -e '.foo'", "command_ref": ref_value},
                    )
                    errs = lint_hallucinations(str(root / "spec"), repo_root=str(root))
                    self.assertNotEqual(
                        self._e530_for_prefix(errs, "jq"), [],
                        f"{label}: ref must NOT bypass E530; got errors: {[e.message for e in errs]}",
                    )

    # --- project-tier allowlist -----------------------------------------

    def test_project_tier_allowlist_extends_toolkit_allowlist(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            project_canon = root / "spec" / "canon"
            project_canon.mkdir()
            (project_canon / "command_prefixes.json").write_text(
                json.dumps({"allowed_prefixes": ["yq"]}),
                encoding="utf-8",
            )
            self._write_ci_gates(root / "spec", ["yq eval '.x' file.yaml", "absentverb run"])
            errs = lint_hallucinations(
                str(root / "spec"),
                repo_root=str(root),
                project_canon_dir=str(project_canon),
            )
            self.assertEqual(
                self._e530_for_prefix(errs, "yq"), [],
                f"yq must be allowed via project allowlist; got: {[e.message for e in errs]}",
            )
            self.assertNotEqual(
                self._e530_for_prefix(errs, "absentverb"), [],
                f"absentverb must still fire E530; got: {[e.message for e in errs]}",
            )

    def test_missing_project_allowlist_file_is_no_op(self):
        """When no project allowlist file exists, only the toolkit defaults apply."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            project_canon = root / "spec" / "canon"
            project_canon.mkdir()  # exists, but no command_prefixes.json
            self._write_ci_gates(root / "spec", ["npm test", "absentverb run"])
            errs = lint_hallucinations(
                str(root / "spec"),
                repo_root=str(root),
                project_canon_dir=str(project_canon),
            )
            self.assertEqual(
                self._e530_for_prefix(errs, "npm"), [],
                "npm is in toolkit defaults; missing project file must not affect that.",
            )
            self.assertNotEqual(
                self._e530_for_prefix(errs, "absentverb"), [],
                "absentverb is in neither tier; must still fire E530.",
            )

    def test_malformed_project_allowlist_does_not_crash(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            project_canon = root / "spec" / "canon"
            project_canon.mkdir()
            cfg = project_canon / "command_prefixes.json"
            cfg.write_text("{not json", encoding="utf-8")
            self._write_ci_gates(root / "spec", ["npm test"])
            stderr_buf = io.StringIO()
            with redirect_stderr(stderr_buf):
                errs = lint_hallucinations(
                    str(root / "spec"),
                    repo_root=str(root),
                    project_canon_dir=str(project_canon),
                )
            self.assertEqual(
                self._e530_for_prefix(errs, "npm"), [],
                f"npm must remain allowed when project allowlist is malformed; got: {[e.message for e in errs]}",
            )
            stderr_text = stderr_buf.getvalue()
            self.assertIn(str(cfg), stderr_text,
                "loader must surface a stderr warning naming the malformed file")
            self.assertIn("JSONDecodeError", stderr_text,
                "loader must name the underlying error type for diagnosability")

    def test_non_list_allowed_prefixes_warns_and_skips(self):
        """`allowed_prefixes` set to a non-list value (e.g. dict) must be skipped
        with a stderr warning rather than silently producing no effect."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            project_canon = root / "spec" / "canon"
            project_canon.mkdir()
            cfg = project_canon / "command_prefixes.json"
            cfg.write_text(
                json.dumps({"allowed_prefixes": {"yq": True}}),
                encoding="utf-8",
            )
            self._write_ci_gates(root / "spec", ["npm test"])
            stderr_buf = io.StringIO()
            with redirect_stderr(stderr_buf):
                errs = lint_hallucinations(
                    str(root / "spec"),
                    repo_root=str(root),
                    project_canon_dir=str(project_canon),
                )
            self.assertEqual(self._e530_for_prefix(errs, "npm"), [])
            stderr_text = stderr_buf.getvalue()
            self.assertIn(str(cfg), stderr_text)
            self.assertIn("allowed_prefixes", stderr_text)

    def test_description_key_in_allowlist_is_not_treated_as_prefix(self):
        """Top-level keys other than `allowed_prefixes` (e.g. `_description`) must be
        ignored by the loader, not silently registered as a verb."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            project_canon = root / "spec" / "canon"
            project_canon.mkdir()
            (project_canon / "command_prefixes.json").write_text(
                json.dumps({
                    "_description": "absentverb",  # must NOT become an allowed prefix
                    "allowed_prefixes": ["yq"],
                }),
                encoding="utf-8",
            )
            self._write_ci_gates(root / "spec", ["absentverb run"])
            errs = lint_hallucinations(
                str(root / "spec"),
                repo_root=str(root),
                project_canon_dir=str(project_canon),
            )
            self.assertNotEqual(
                self._e530_for_prefix(errs, "absentverb"), [],
                "_description key must not become an allowed prefix.",
            )

    def test_project_allowlist_dedups_with_toolkit_defaults(self):
        """Listing a verb already present in toolkit defaults (e.g. `npm`) is a no-op,
        not a double-register or error."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            project_canon = root / "spec" / "canon"
            project_canon.mkdir()
            (project_canon / "command_prefixes.json").write_text(
                json.dumps({"allowed_prefixes": ["npm"]}),  # duplicate of toolkit default
                encoding="utf-8",
            )
            self._write_ci_gates(root / "spec", ["npm test"])
            errs = lint_hallucinations(
                str(root / "spec"),
                repo_root=str(root),
                project_canon_dir=str(project_canon),
            )
            self.assertEqual(
                self._e530_for_prefix(errs, "npm"), [],
                "duplicate registration must not produce E530.",
            )

    # --- bash -c documented behavior ------------------------------------

    def test_bash_dash_c_remains_legal_regression(self):
        """`bash -c "..."` is legal because `bash` is in the toolkit allowlist."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            self._write_ci_gates(root / "spec", ["bash -c \"jq -e '.'\""])
            errs = lint_hallucinations(str(root / "spec"), repo_root=str(root))
            self.assertEqual(
                [e for e in errs if e.code == "E530"], [],
                f"bash -c must remain legal; got: {[e.message for e in errs]}",
            )

    def test_bash_dash_c_does_not_recurse_into_inner_verb(self):
        """Pin the documented limitation: hallucination-lint inspects only the leading
        verb of the command string. It does NOT parse `bash -c "<inner>"` to validate
        the inner verb. This is why `bash -c` is described as "legal but discouraged"
        — it silently bypasses verb-prefix validation. Change this test only if the
        linter gains nested-command parsing."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            self._write_ci_gates(root / "spec", ["bash -c \"absentverb foo\""])
            errs = lint_hallucinations(str(root / "spec"), repo_root=str(root))
            self.assertEqual(
                self._e530_for_prefix(errs, "absentverb"), [],
                "linter intentionally does not recurse into bash -c; inner verbs are unchecked.",
            )

    # --- ref-bypass scope is generic (any node, not just test_commands) ---

    def test_command_ref_bypass_applies_to_ci_gates_step(self):
        """`_scan_node` is generic: a sibling `command_ref` on any node containing
        a `command` string bypasses E530, including Step 12 ci_gates steps. This
        pins the documented scope so a future scope-narrowing change is caught."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            (root / "spec" / "12_ci_gates.json").write_text(
                json.dumps({
                    "jobs": [{
                        "job_id": "job-1",
                        "steps": [{
                            "id": "s-1",
                            "command": "absentverb run",
                            "command_ref": {"id": "cn:project:command:absentverb"},
                        }],
                    }]
                }),
                encoding="utf-8",
            )
            errs = lint_hallucinations(str(root / "spec"), repo_root=str(root))
            self.assertEqual(
                self._e530_for_prefix(errs, "absentverb"), [],
                "ci_gates step with sibling command_ref must bypass E530 (same rule as test_commands).",
            )

    # --- project_canon_dir edge cases ---

    def test_project_canon_dir_empty_string_is_no_op(self):
        """Empty string `project_canon_dir` is treated as falsy — only toolkit defaults apply."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            self._write_ci_gates(root / "spec", ["npm test", "absentverb run"])
            errs = lint_hallucinations(
                str(root / "spec"), repo_root=str(root), project_canon_dir="",
            )
            self.assertEqual(self._e530_for_prefix(errs, "npm"), [])
            self.assertNotEqual(self._e530_for_prefix(errs, "absentverb"), [])

    def test_project_canon_dir_nonexistent_path_is_no_op(self):
        """`project_canon_dir` pointing at a missing directory must not crash."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            self._write_ci_gates(root / "spec", ["npm test", "absentverb run"])
            errs = lint_hallucinations(
                str(root / "spec"),
                repo_root=str(root),
                project_canon_dir=str(root / "does-not-exist"),
            )
            self.assertEqual(self._e530_for_prefix(errs, "npm"), [])
            self.assertNotEqual(self._e530_for_prefix(errs, "absentverb"), [])

    def test_project_allowlist_missing_allowed_prefixes_key_is_no_op(self):
        """A `command_prefixes.json` lacking the `allowed_prefixes` key falls back to
        defaults silently — `data.get('allowed_prefixes', [])` returns `[]`."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            project_canon = root / "spec" / "canon"
            project_canon.mkdir()
            (project_canon / "command_prefixes.json").write_text(
                json.dumps({"_description": "no allowed_prefixes key"}),
                encoding="utf-8",
            )
            self._write_ci_gates(root / "spec", ["npm test", "absentverb run"])
            errs = lint_hallucinations(
                str(root / "spec"),
                repo_root=str(root),
                project_canon_dir=str(project_canon),
            )
            self.assertEqual(self._e530_for_prefix(errs, "npm"), [])
            self.assertNotEqual(self._e530_for_prefix(errs, "absentverb"), [])


class StructuredFieldTests(unittest.TestCase):
    """Verify structured fields (subcode, file, jq_path, value) on E530 errors."""

    def test_existing_structure_path_not_found_has_structured_fields(self):
        """EXISTING_STRUCTURE_PATH_NOT_FOUND E530 must carry all four structured fields."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            spec = root / "spec"
            spec.mkdir()
            (spec / "15_scaffold.json").write_text(
                json.dumps({"existing_structures": ["theme/missing_dir/bootstrap.sh"]}),
                encoding="utf-8",
            )
            errs = lint_hallucinations(str(spec), repo_root=str(root))
            hits = [e for e in errs if e.code == "E530" and e.subcode == "EXISTING_STRUCTURE_PATH_NOT_FOUND"]
            self.assertTrue(hits, "Expected E530 EXISTING_STRUCTURE_PATH_NOT_FOUND")
            err = hits[0]
            self.assertEqual(err.subcode, "EXISTING_STRUCTURE_PATH_NOT_FOUND")
            self.assertIsNotNone(err.file, "file must be set")
            self.assertIsNotNone(err.jq_path, "jq_path must be set")
            self.assertTrue(err.jq_path.startswith("."), f"jq_path must start with '.', got {err.jq_path!r}")
            self.assertEqual(err.value, "theme/missing_dir/bootstrap.sh")

    def test_linked_test_file_not_found_has_structured_fields(self):
        """LINKED_TEST_FILE_NOT_FOUND E530 must carry all four structured fields."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            spec = root / "spec"
            spec.mkdir()
            (spec / "09_impl_plan.json").write_text(
                json.dumps({"linked_test_expectation": "tests/unit/completely_missing.py"}),
                encoding="utf-8",
            )
            errs = lint_hallucinations(str(spec), repo_root=str(root))
            hits = [e for e in errs if e.code == "E530" and e.subcode == "LINKED_TEST_FILE_NOT_FOUND"]
            self.assertTrue(hits, "Expected E530 LINKED_TEST_FILE_NOT_FOUND")
            err = hits[0]
            self.assertIsNotNone(err.file)
            self.assertTrue(err.jq_path.startswith("."), f"jq_path must start with '.', got {err.jq_path!r}")
            self.assertEqual(err.value, "tests/unit/completely_missing.py")

    def _lint(self, spec_data: dict, filename: str = "artifact.json") -> list:
        """Helper: write spec_data to a temp dir and run lint_hallucinations."""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            spec = root / "spec"
            spec.mkdir()
            (spec / filename).write_text(json.dumps(spec_data), encoding="utf-8")
            return lint_hallucinations(str(spec), repo_root=str(root))

    def _assert_e530(self, errs, subcode: str, *, file_contains: str = "", jq_path_contains: str = "", value: str = "") -> None:
        """Assert one E530 with the given subcode has all four structured fields set correctly."""
        hits = [e for e in errs if e.code == "E530" and e.subcode == subcode]
        self.assertTrue(hits, f"Expected E530 subcode={subcode} in {[e.render() for e in errs]}")
        err = hits[0]
        self.assertEqual(err.subcode, subcode)
        self.assertIsNotNone(err.file, "E530 file must be set")
        if file_contains:
            self.assertIn(file_contains, err.file)
        self.assertIsNotNone(err.jq_path, "E530 jq_path must be set")
        self.assertTrue(err.jq_path.startswith("."), f"jq_path must start with '.', got {err.jq_path!r}")
        if jq_path_contains:
            self.assertIn(jq_path_contains, err.jq_path)
        self.assertIsNotNone(err.value, "E530 value must be set")
        if value:
            self.assertEqual(err.value, value)

    def test_trace_type_invented_has_structured_fields(self):
        """INVENTED_ENUM_OR_ID on trace .type field must carry all four structured fields."""
        errs = self._lint({"trace": [{"type": "invented_trace_type", "id": "t-01"}]})
        self._assert_e530(errs, "INVENTED_ENUM_OR_ID", jq_path_contains="type", value="invented_trace_type")

    def test_stage_invented_has_structured_fields(self):
        """INVENTED_ENUM_OR_ID on .stage field must carry all four structured fields."""
        errs = self._lint({"stage": "hyperspace"})
        self._assert_e530(errs, "INVENTED_ENUM_OR_ID", jq_path_contains="stage", value="hyperspace")

    def test_stages_list_item_invented_has_structured_fields(self):
        """INVENTED_ENUM_OR_ID on .stages[i] list item must carry all four structured fields."""
        errs = self._lint({"stages": ["ci", "hyperspace_env"]})
        self._assert_e530(errs, "INVENTED_ENUM_OR_ID", jq_path_contains="stages", value="hyperspace_env")
        hits = [e for e in errs if e.code == "E530" and e.value == "hyperspace_env"]
        self.assertEqual(hits[0].jq_path, ".stages[1]", "list-item jq_path must include index")

    def test_unit_invented_has_structured_fields(self):
        """INVENTED_ENUM_OR_ID on .unit field must carry all four structured fields."""
        errs = self._lint({"unit": "furlongs_per_fortnight"})
        self._assert_e530(errs, "INVENTED_ENUM_OR_ID", jq_path_contains="unit", value="furlongs_per_fortnight")

    def test_units_list_item_invented_has_structured_fields(self):
        """INVENTED_ENUM_OR_ID on .units[i] list item must carry all four structured fields."""
        errs = self._lint({"units": ["ms", "furlongs_per_fortnight"]})
        self._assert_e530(errs, "INVENTED_ENUM_OR_ID", jq_path_contains="units", value="furlongs_per_fortnight")
        hits = [e for e in errs if e.code == "E530" and e.value == "furlongs_per_fortnight"]
        self.assertEqual(hits[0].jq_path, ".units[1]", "list-item jq_path must include index")

    def test_command_prefix_invented_has_structured_fields(self):
        """INVENTED_ENUM_OR_ID on .command field must carry all four structured fields."""
        errs = self._lint({"jobs": [{"steps": [{"command": "frobnicatecli run tests"}]}]})
        self._assert_e530(errs, "INVENTED_ENUM_OR_ID", jq_path_contains="command", value="frobnicatecli")

    def test_pr_rules_invented_has_structured_fields(self):
        """INVENTED_ENUM_OR_ID on .pr_rules[i] must carry all four structured fields."""
        errs = self._lint({"pr_rules": ["validate", "hyperspacecheck"]})
        self._assert_e530(errs, "INVENTED_ENUM_OR_ID", jq_path_contains="pr_rules", value="hyperspacecheck")

    def test_cross_ref_invented_id_has_structured_fields(self):
        """INVENTED_ENUM_OR_ID from the cross-ref loop must carry all four structured fields."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            spec = root / "spec"
            spec.mkdir()
            # a.json defines id="fr-real-001"; b.json references "fr-ghost-999" which is never defined
            (spec / "04_fr_list.json").write_text(
                json.dumps({"frs": [{"fr_id": "fr-real-001", "description": "d"}]}),
                encoding="utf-8",
            )
            (spec / "09_impl_plan.json").write_text(
                json.dumps({"tasks": [{"fr_refs": ["fr-ghost-999"]}]}),
                encoding="utf-8",
            )
            errs = lint_hallucinations(str(spec), repo_root=str(root))
            ghost = [e for e in errs if e.code == "E530" and e.subcode == "INVENTED_ENUM_OR_ID"
                     and e.value == "fr-ghost-999"]
            self.assertTrue(ghost, f"Expected E530 for fr-ghost-999 in {[e.render() for e in errs]}")
            err = ghost[0]
            self.assertIsNotNone(err.file)
            self.assertIsNotNone(err.jq_path)
            self.assertTrue(err.jq_path.startswith("."), f"jq_path must start with '.', got {err.jq_path!r}")
            self.assertEqual(err.value, "fr-ghost-999")

    def test_unresolved_nfr_ref_has_structured_fields(self):
        """UNRESOLVED_NFR_REF E530 must carry all four structured fields."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            spec = root / "spec"
            spec.mkdir()
            (spec / "07_nfrs.json").write_text(
                json.dumps({"nfrs": [{"nfr_id": "nfr-perf-001"}]}),
                encoding="utf-8",
            )
            (spec / "09_impl_plan.json").write_text(
                json.dumps({"tasks": [{"nfr_refs": ["nfr-ghost-999"]}]}),
                encoding="utf-8",
            )
            errs = lint_hallucinations(str(spec), repo_root=str(root))
            hits = [e for e in errs if e.code == "E530" and e.subcode == "UNRESOLVED_NFR_REF"]
            self.assertTrue(hits, f"Expected E530 UNRESOLVED_NFR_REF in {[e.render() for e in errs]}")
            err = hits[0]
            self.assertEqual(err.subcode, "UNRESOLVED_NFR_REF")
            self.assertIsNotNone(err.file)
            self.assertIsNotNone(err.jq_path)
            self.assertTrue(err.jq_path.startswith("."), f"jq_path must start with '.', got {err.jq_path!r}")
            self.assertEqual(err.value, "nfr-ghost-999")


class CollectPathValuePairsTests(unittest.TestCase):
    """Unit tests for _collect_path_value_pairs — jq_path precision."""

    def test_top_level_string_field(self):
        obj = {"linked_test_expectation": "tests/foo.py"}
        pairs = _collect_path_value_pairs(obj, "linked_test_expectation")
        assert pairs == [(".linked_test_expectation", "tests/foo.py")]

    def test_nested_field_produces_precise_path(self):
        obj = {"plan": {"steps": [{"linked_test_expectation": "tests/bar.py"}]}}
        pairs = _collect_path_value_pairs(obj, "linked_test_expectation")
        assert pairs == [(".plan.steps[0].linked_test_expectation", "tests/bar.py")]

    def test_multiple_occurrences_all_paths_distinct(self):
        obj = {
            "tasks": [
                {"linked_test_expectation": "tests/a.py"},
                {"linked_test_expectation": "tests/b.py"},
            ]
        }
        pairs = _collect_path_value_pairs(obj, "linked_test_expectation")
        assert (".tasks[0].linked_test_expectation", "tests/a.py") in pairs
        assert (".tasks[1].linked_test_expectation", "tests/b.py") in pairs
        assert len(pairs) == 2

    def test_list_value_produces_indexed_paths(self):
        obj = {"nfr_refs": ["nfr-perf-001", "nfr-sec-002"]}
        pairs = _collect_path_value_pairs(obj, "nfr_refs")
        assert pairs == [
            (".nfr_refs[0]", "nfr-perf-001"),
            (".nfr_refs[1]", "nfr-sec-002"),
        ]

    def test_linked_test_jq_path_appears_in_e530_error(self):
        """E530 jq_path must reflect the actual nested location, not a static '.key'."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            spec = root / "spec"
            spec.mkdir()
            (spec / "09_impl_plan.json").write_text(
                json.dumps({
                    "plan": {
                        "tasks": [
                            {"linked_test_expectation": "tests/unit/missing.py"}
                        ]
                    }
                }),
                encoding="utf-8",
            )
            errs = lint_hallucinations(str(spec), repo_root=str(root))
            e530 = [e for e in errs if e.code == "E530" and e.subcode == "LINKED_TEST_FILE_NOT_FOUND"]
            assert e530, "Expected an E530 LINKED_TEST_FILE_NOT_FOUND error"
            assert e530[0].jq_path == ".plan.tasks[0].linked_test_expectation", (
                f"Expected precise nested jq_path, got: {e530[0].jq_path!r}"
            )


if __name__ == "__main__":
    unittest.main()
