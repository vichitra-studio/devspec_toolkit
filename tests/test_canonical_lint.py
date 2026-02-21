import unittest
from pathlib import Path
import sys
import json

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from specdev_tools.canonical_lint import lint_manifest
from specdev_tools.canonical_lint import lint_canon_dir

FIXTURE_DIR = Path(__file__).resolve().parents[0] / "fixtures" / "canonical"


class CanonicalLintTests(unittest.TestCase):
    def test_alias_collision(self):
        manifest = json.loads((FIXTURE_DIR / "manifest_alias_conflict.json").read_text(encoding="utf-8"))
        errs = lint_manifest(manifest)
        self.assertTrue(any("E410" in e for e in errs))

    def test_deprecated_requires_timestamp(self):
        manifest = json.loads((FIXTURE_DIR / "manifest_invalid_deprecated.json").read_text(encoding="utf-8"))
        errs = lint_manifest(manifest)
        self.assertTrue(any("E420" in e for e in errs))

    def test_missing_manifest_reports_unresolved_input(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            errs = lint_canon_dir(td)
            self.assertTrue(any("E520" in e for e in errs))

    def test_malformed_manifest_shapes_report_unresolved_input(self):
        errs = lint_manifest({"entries": [None], "aliases": [None]})
        self.assertTrue(any("E520" in e for e in errs))

    def test_invalid_manifest_json_reports_unresolved_input(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            canon = Path(td) / "canon"
            canon.mkdir()
            (canon / "manifest.json").write_text("{bad", encoding="utf-8")
            errs = lint_canon_dir(td)
            self.assertTrue(any("invalid_manifest" in e for e in errs))

    def test_manifest_root_must_be_object(self):
        errs = lint_manifest([])
        self.assertTrue(any("manifest root must be an object" in e for e in errs))


if __name__ == "__main__":
    unittest.main()
