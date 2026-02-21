import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from specdev_tools.spec_quality_lint import lint_spec_quality


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
                        "seed_refs": [],
                        "generation_quality": {"completeness": 1, "correctness": 1, "consistency": 1},
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
            self.assertTrue(any("E510" in e for e in errs))
            self.assertTrue(any("empty critical array" in e for e in errs))

    def test_invalid_json_is_reported_not_raised(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            (root / "spec" / "bad.json").write_text("{bad", encoding="utf-8")
            errs = lint_spec_quality(str(root / "spec"))
            self.assertTrue(any("invalid_json" in e for e in errs))

    def test_non_step_json_is_not_forced_to_step_top_level_keys(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec" / "common").mkdir(parents=True)
            (root / "spec" / "common" / "seed_manifest.json").write_text(
                json.dumps({"global_seed_order": ["seed_overview"]}),
                encoding="utf-8",
            )
            errs = lint_spec_quality(str(root / "spec"))
            self.assertFalse(any("seed_manifest.json missing top-level" in e for e in errs))

    def test_detects_missing_b4_top_level_fields(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            (root / "spec" / "01_capabilities.json").write_text(
                json.dumps(
                    {
                        "id": "capabilities-test",
                        "owner": "system",
                        "created_at": "2026-01-01T00:00:00Z",
                        "seed_refs": [],
                        "capabilities": [{"capability_id": "cap-one"}],
                    }
                ),
                encoding="utf-8",
            )
            errs = lint_spec_quality(str(root / "spec"))
            self.assertTrue(any("missing top-level 'generation_quality'" in e for e in errs))
            self.assertTrue(any("missing top-level 'canonical_refs_used'" in e for e in errs))
            self.assertTrue(any("missing top-level 'canonical_proposals'" in e for e in errs))
            self.assertTrue(any("missing top-level 'canonical_conflicts'" in e for e in errs))

    def test_schema_uri_drives_step_detection_for_nonstandard_filename(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            (root / "spec" / "artifact.json").write_text(
                json.dumps(
                    {
                        "$schema": "https://specdev.local/schema/01_capabilities.schema.json",
                        "id": "capabilities-test",
                        "owner": "system",
                        "created_at": "2026-01-01T00:00:00Z",
                        "seed_refs": [],
                        "capabilities": [{"capability_id": "cap-one"}],
                    }
                ),
                encoding="utf-8",
            )
            errs = lint_spec_quality(str(root / "spec"))
            self.assertTrue(any("artifact.json missing top-level 'generation_quality'" in e for e in errs))


if __name__ == "__main__":
    unittest.main()
