import json
import tempfile
import unittest
from pathlib import Path

from specdev_tools.validation.hallucination_lint import lint_hallucinations
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
            self.assertFalse(any("schema_uri_not_registered" in e for e in relaxed))


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


if __name__ == "__main__":
    unittest.main()
