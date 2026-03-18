import unittest
import tempfile
import json
from pathlib import Path

from specdev_tools.canonical.integrity import validate_canonical_integrity


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
            errs = validate_canonical_integrity(str(root), str(root / "spec"), require_manifest_schema_registration=False)
            self.assertTrue(any(e.code == "E211" for e in errs))

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
            errs = validate_canonical_integrity(str(root), str(root / "spec"), require_manifest_schema_registration=False)
            self.assertTrue(any(e.code == "E211" for e in errs))

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
            errs = validate_canonical_integrity(str(root), str(root / "spec"), require_manifest_schema_registration=False)
            self.assertTrue(any("canonical_refs_used_missing" in e.render() for e in errs))

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
            errs = validate_canonical_integrity(str(root), str(root / "spec"), require_manifest_schema_registration=False)
            self.assertTrue(any("canonical_refs_used_extra" in e.render() for e in errs))

    def test_unresolved_semantic_without_proposal_is_detected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "canon").mkdir()
            (root / "spec").mkdir()
            (root / "canon" / "manifest.json").write_text(
                json.dumps(
                    {
                        "registry_version": "1.0.0",
                        "entries": [],
                        "aliases": [],
                    }
                ),
                encoding="utf-8",
            )
            (root / "spec" / "03_glossary.json").write_text(
                json.dumps(
                    {
                        "terms": [
                            {
                                "term": "json web token"
                            }
                        ],
                        "canonical_proposals": [],
                        "canonical_conflicts": [],
                    }
                ),
                encoding="utf-8",
            )
            errs = validate_canonical_integrity(str(root), str(root / "spec"), require_manifest_schema_registration=False)
            self.assertTrue(any("unresolved_canonical_semantic" in e.render() for e in errs))

    def test_unresolved_semantic_is_allowed_when_proposed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "canon").mkdir()
            (root / "spec").mkdir()
            (root / "canon" / "manifest.json").write_text(
                json.dumps(
                    {
                        "registry_version": "1.0.0",
                        "entries": [],
                        "aliases": [],
                    }
                ),
                encoding="utf-8",
            )
            (root / "spec" / "03_glossary.json").write_text(
                json.dumps(
                    {
                        "terms": [
                            {
                                "term": "json web token"
                            }
                        ],
                        "canonical_proposals": [
                            {
                                "temp_id": "jwt-term",
                                "kind": "term",
                                "proposed_label": "json web token",
                                "definition": "JWT term proposal",
                                "source_field": "terms[0].term"
                            }
                        ],
                        "canonical_conflicts": [],
                    }
                ),
                encoding="utf-8",
            )
            errs = validate_canonical_integrity(str(root), str(root / "spec"), require_manifest_schema_registration=False)
            self.assertFalse(any("unresolved_canonical_semantic" in e.render() for e in errs))

    def test_nfr_category_without_risk_category_ref_does_not_trigger_unresolved(self):
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
                                "id": "cn:core:metric:p95",
                                "kind": "metric",
                                "version": "1.0.0",
                                "status": "active",
                                "lifecycle": {"introduced_at": "2026-02-21T00:00:00Z"},
                            },
                            {
                                "id": "cn:core:unit:ms",
                                "kind": "unit",
                                "version": "1.0.0",
                                "status": "active",
                                "lifecycle": {"introduced_at": "2026-02-21T00:00:00Z"},
                            },
                            {
                                "id": "cn:core:stage:ci",
                                "kind": "stage",
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
                json.dumps(
                    {
                        "nfrs": [
                            {
                                "nfr_id": "nfr-perf-latency",
                                "category": "latency",
                                "metric": "p95",
                                "target": 200,
                                "unit": "ms",
                                "measurement_method": "load test",
                                "stage": "ci",
                                "owner": "platform",
                                "trace": [],
                                "metric_ref": {"id": "cn:core:metric:p95", "kind": "metric"},
                                "unit_ref": {"id": "cn:core:unit:ms", "kind": "unit"},
                                "stage_ref": {"id": "cn:core:stage:ci", "kind": "stage"},
                            }
                        ],
                        "canonical_refs_used": [
                            {"id": "cn:core:metric:p95", "kind": "metric"},
                            {"id": "cn:core:unit:ms", "kind": "unit"},
                            {"id": "cn:core:stage:ci", "kind": "stage"},
                        ],
                        "canonical_proposals": [],
                        "canonical_conflicts": [],
                    }
                ),
                encoding="utf-8",
            )
            errs = validate_canonical_integrity(str(root), str(root / "spec"), require_manifest_schema_registration=False)
            self.assertFalse(any("field=nfrs[0].category" in e.render() for e in errs))


if __name__ == "__main__":
    unittest.main()
