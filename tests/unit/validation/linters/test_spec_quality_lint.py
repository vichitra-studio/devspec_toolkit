import json
import tempfile
import unittest
from pathlib import Path

from specdev_tools.validation.spec_quality_lint import lint_spec_quality
from specdev_tools.core.errors import render_errors


class SpecQualityLintTests(unittest.TestCase):
    def test_detects_placeholder_and_missing_fields(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            (root / "spec" / "00_charter.json").write_text(
                json.dumps(
                    {
                        "id": "charter",
                        "owner": "system",
                        "created_at": "2026-01-01T00:00:00Z",


                        "canonical_refs_used": [],
                        "canonical_proposals": [],
                        "canonical_conflicts": [],
                        "terms": [],
                        "notes": "TODO",
                    }
                ),
                encoding="utf-8",
            )
            errs = lint_spec_quality(str(root / "spec"))
            self.assertTrue(any("E510" in e for e in render_errors(errs)))
            self.assertTrue(any("empty critical array" in e for e in render_errors(errs)))

    def test_invalid_json_is_reported_not_raised(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            (root / "spec" / "bad.json").write_text("{bad", encoding="utf-8")
            errs = lint_spec_quality(str(root / "spec"))
            self.assertTrue(any("invalid_json" in e for e in render_errors(errs)))

    def test_non_step_json_is_not_forced_to_step_top_level_keys(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec" / "common").mkdir(parents=True)
            (root / "spec" / "common" / "seed_manifest.json").write_text(
                json.dumps({"global_seed_order": ["seed_overview"]}),
                encoding="utf-8",
            )
            errs = lint_spec_quality(str(root / "spec"))
            self.assertFalse(any("seed_manifest.json missing top-level" in e for e in render_errors(errs)))

    def test_detects_missing_metadata_top_level_fields(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            (root / "spec" / "01_capabilities.json").write_text(
                json.dumps(
                    {
                        "id": "capabilities-test",
                        "owner": "system",
                        "created_at": "2026-01-01T00:00:00Z",

                        "capabilities": [{"capability_id": "cap-one"}],
                    }
                ),
                encoding="utf-8",
            )
            errs = lint_spec_quality(str(root / "spec"))
            self.assertTrue(any("missing top-level 'canonical_refs_used'" in e for e in render_errors(errs)))
            self.assertFalse(any("missing top-level 'generation_quality'" in e for e in render_errors(errs)))
            self.assertFalse(any("missing top-level 'canonical_proposals'" in e for e in render_errors(errs)))
            self.assertFalse(any("missing top-level 'canonical_conflicts'" in e for e in render_errors(errs)))

    def test_schema_uri_drives_step_detection_for_nonstandard_filename(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            (root / "spec" / "artifact.json").write_text(
                json.dumps(
                    {
                        "$schema": "vc:01-capabilities",
                        "id": "capabilities-test",
                        "owner": "system",
                        "created_at": "2026-01-01T00:00:00Z",

                        "capabilities": [{"capability_id": "cap-one"}],
                    }
                ),
                encoding="utf-8",
            )
            errs = lint_spec_quality(str(root / "spec"))
            self.assertTrue(any("artifact.json missing top-level 'canonical_refs_used'" in e for e in render_errors(errs)))
            self.assertFalse(any("artifact.json missing top-level 'generation_quality'" in e for e in render_errors(errs)))

    def test_detects_assumption_vague_quantifier(self):
        from specdev_tools.validation.spec_quality_lint import _check_assumptions
        errs = _check_assumptions("test.json", {"assumptions": ["Some things are fast"]}, set())
        self.assertTrue(any("W571 ASSUMPTION_VAGUE_QUANTIFIER" in e and "ref=Some" in e for e in render_errors(errs)))
        self.assertTrue(any("W571 ASSUMPTION_VAGUE_QUANTIFIER" in e and "ref=fast" in e for e in render_errors(errs)))

    def test_detects_assumption_placeholder(self):
        from specdev_tools.validation.spec_quality_lint import _check_assumptions
        errs = _check_assumptions("test.json", {"assumptions": ["This is TBD"]}, set())
        self.assertTrue(any("E512 ASSUMPTION_HAS_PLACEHOLDER" in e for e in render_errors(errs)))

    def test_detects_assumption_unbound_id(self):
        from specdev_tools.validation.spec_quality_lint import _check_assumptions
        errs = _check_assumptions("test.json", {"assumptions": ["fr-auth-login works"]}, set(["fr-other"]))
        self.assertTrue(any("W573 ASSUMPTION_UNBOUND_ID" in e and "ref=fr-auth-login" in e for e in render_errors(errs)))

    def test_detects_assumption_count_high(self):
        from specdev_tools.validation.spec_quality_lint import _check_assumptions
        errs = _check_assumptions("test.json", {"assumptions": ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11"]}, set())
        self.assertTrue(any("W572 ASSUMPTION_COUNT_HIGH" in e for e in render_errors(errs)))



if __name__ == "__main__":
    unittest.main()
