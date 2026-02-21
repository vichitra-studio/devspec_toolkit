import unittest
import tempfile
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from specdev_tools.canonical_integrity import validate_canonical_integrity


class CanonicalIntegrityDriftTests(unittest.TestCase):
    def test_cross_artifact_drift_detected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "canon").mkdir()
            (root / "spec").mkdir()
            (root / "canon" / "manifest.json").write_text(
                json.dumps(
                    {
                        "registry_version": "1.0.0",
                        "entries": [
                            {
                                "id": "cn:core:metric:error-rate",
                                "kind": "metric",
                                "version": "1.0.0",
                                "status": "active",
                                "lifecycle": {"introduced_at": "2026-02-21T00:00:00Z"},
                            },
                            {
                                "id": "cn:core:metric:failure-rate",
                                "kind": "metric",
                                "version": "1.0.0",
                                "status": "active",
                                "lifecycle": {"introduced_at": "2026-02-21T00:00:00Z"},
                            },
                        ],
                        "aliases": [],
                    }
                ),
                encoding="utf-8",
            )
            (root / "spec" / "07_nfrs.json").write_text(
                json.dumps({"metric": "error rate", "metric_ref": {"id": "cn:core:metric:error-rate", "kind": "metric"}}),
                encoding="utf-8",
            )
            (root / "spec" / "14_roadmap.json").write_text(
                json.dumps({"metric": "error rate", "metric_ref": {"id": "cn:core:metric:failure-rate", "kind": "metric"}}),
                encoding="utf-8",
            )
            errs = validate_canonical_integrity(str(root), str(root / "spec"))
            self.assertTrue(any("E210" in e for e in errs))

    def test_generic_ref_value_pair_drift_detected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "canon").mkdir()
            (root / "spec").mkdir()
            (root / "canon" / "manifest.json").write_text(
                json.dumps(
                    {
                        "registry_version": "1.0.0",
                        "entries": [
                            {
                                "id": "cn:core:capability:user-auth",
                                "kind": "capability",
                                "version": "1.0.0",
                                "status": "active",
                                "lifecycle": {"introduced_at": "2026-02-21T00:00:00Z"},
                            },
                            {
                                "id": "cn:core:capability:identity-auth",
                                "kind": "capability",
                                "version": "1.0.0",
                                "status": "active",
                                "lifecycle": {"introduced_at": "2026-02-21T00:00:00Z"},
                            },
                        ],
                        "aliases": [],
                    }
                ),
                encoding="utf-8",
            )
            (root / "spec" / "01_capabilities.json").write_text(
                json.dumps(
                    {
                        "capability": "authentication",
                        "capability_ref": {"id": "cn:core:capability:user-auth", "kind": "capability"},
                    }
                ),
                encoding="utf-8",
            )
            (root / "spec" / "04_fr_list.json").write_text(
                json.dumps(
                    {
                        "capability": "authentication",
                        "capability_ref": {"id": "cn:core:capability:identity-auth", "kind": "capability"},
                    }
                ),
                encoding="utf-8",
            )
            errs = validate_canonical_integrity(str(root), str(root / "spec"))
            self.assertTrue(any("E210" in e for e in errs))

    def test_missing_canonical_refs_used_entry_is_detected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "canon").mkdir()
            (root / "spec").mkdir()
            (root / "canon" / "manifest.json").write_text(
                json.dumps(
                    {
                        "registry_version": "1.0.0",
                        "entries": [
                            {
                                "id": "cn:core:metric:error-rate",
                                "kind": "metric",
                                "version": "1.0.0",
                                "status": "active",
                                "lifecycle": {"introduced_at": "2026-02-21T00:00:00Z"},
                            }
                        ],
                        "aliases": [],
                    }
                ),
                encoding="utf-8",
            )
            (root / "spec" / "07_nfrs.json").write_text(
                json.dumps(
                    {
                        "metric": "error rate",
                        "metric_ref": {"id": "cn:core:metric:error-rate", "kind": "metric"},
                        "canonical_refs_used": [],
                    }
                ),
                encoding="utf-8",
            )
            errs = validate_canonical_integrity(str(root), str(root / "spec"))
            self.assertTrue(any("canonical_refs_used_missing" in e for e in errs))

    def test_extra_canonical_refs_used_entry_is_detected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "canon").mkdir()
            (root / "spec").mkdir()
            (root / "canon" / "manifest.json").write_text(
                json.dumps(
                    {
                        "registry_version": "1.0.0",
                        "entries": [
                            {
                                "id": "cn:core:metric:error-rate",
                                "kind": "metric",
                                "version": "1.0.0",
                                "status": "active",
                                "lifecycle": {"introduced_at": "2026-02-21T00:00:00Z"},
                            }
                        ],
                        "aliases": [],
                    }
                ),
                encoding="utf-8",
            )
            (root / "spec" / "07_nfrs.json").write_text(
                json.dumps(
                    {
                        "metric": "error rate",
                        "metric_ref": {"id": "cn:core:metric:error-rate", "kind": "metric"},
                        "canonical_refs_used": [
                            {"id": "cn:core:metric:error-rate", "kind": "metric"},
                            {"id": "cn:core:metric:extra-metric", "kind": "metric"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            errs = validate_canonical_integrity(str(root), str(root / "spec"))
            self.assertTrue(any("canonical_refs_used_extra" in e for e in errs))


if __name__ == "__main__":
    unittest.main()
