import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from specdev_tools.hallucination_lint import lint_hallucinations


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
            self.assertTrue(any("preprod" in e for e in errs))
            self.assertTrue(any("unknown-type" in e for e in errs))

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
            self.assertTrue(any("inventcmd" in e for e in errs))
            self.assertTrue(any("job-x" in e for e in errs))

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
            self.assertFalse(any("obj-2" in e and "INVENTED" in e for e in errs))

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
            self.assertTrue(any("nonsense-unit" in e for e in errs))

    def test_invalid_json_is_reported_not_raised(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            (root / "spec" / "bad.json").write_text("{bad", encoding="utf-8")
            errs = lint_hallucinations(str(root / "spec"), repo_root=str(root))
            self.assertTrue(any("invalid_json" in e for e in errs))

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
                    self.assertFalse(any("command=" in e for e in errs))

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
            self.assertFalse(any("command=npm" in e for e in errs))


if __name__ == "__main__":
    unittest.main()
