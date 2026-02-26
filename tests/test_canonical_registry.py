import json
import tempfile
import unittest
from pathlib import Path

from specdev_tools.canonical.registry import CanonicalRegistry

FIXTURE_DIR = Path(__file__).resolve().parents[0] / "fixtures" / "canonical"


class CanonicalRegistryTests(unittest.TestCase):
    def test_load_and_validate_ref(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "canon").mkdir(parents=True)
            manifest = {
                "registry_version": "1.0.0",
                "entries": [
                    {
                        "id": "cn:core:metric:error-rate",
                        "kind": "metric",
                        "version": "1.2.0",
                        "status": "active",
                        "aliases": ["failure rate"],
                        "lifecycle": {"introduced_at": "2026-02-21T00:00:00Z"},
                    }
                ],
                "aliases": []
            }
            (root / "canon" / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            reg = CanonicalRegistry.load(str(root))
            self.assertEqual(reg.resolve_alias("metric", "failure rate"), "cn:core:metric:error-rate")
            errs = reg.validate_ref({"id": "cn:core:metric:error-rate", "kind": "metric", "version": "^1.0.0"})
            self.assertEqual([], [e for e in errs if e.startswith("E")])

    def test_kind_mismatch(self):
        reg = CanonicalRegistry.from_manifest(
            {
                "entries": [{"id": "cn:core:unit:percent", "kind": "unit", "version": "1.0.0", "status": "active"}],
                "aliases": []
            }
        )
        errs = reg.validate_ref({"id": "cn:core:unit:percent", "kind": "metric", "version": "1.0.0"})
        self.assertTrue(any("E120" in e for e in errs))

    def test_version_mismatch_fixture(self):
        manifest = json.loads((FIXTURE_DIR / "manifest_version_mismatch.json").read_text(encoding="utf-8"))
        reg = CanonicalRegistry.from_manifest(manifest)
        errs = reg.validate_ref({"id": "cn:core:metric:error-rate", "kind": "metric", "version": "^1.0.0"})
        self.assertTrue(any("E130" in e for e in errs))

    def test_ambiguous_alias_and_deprecated_alias(self):
        reg = CanonicalRegistry.from_manifest(
            {
                "entries": [
                    {
                        "id": "cn:core:metric:p95-latency",
                        "kind": "metric",
                        "version": "1.0.0",
                        "status": "active",
                        "lifecycle": {"introduced_at": "2026-02-21T00:00:00Z"},
                    },
                    {
                        "id": "cn:core:metric:p99-latency",
                        "kind": "metric",
                        "version": "1.0.0",
                        "status": "active",
                        "lifecycle": {"introduced_at": "2026-02-21T00:00:00Z"},
                    },
                ],
                "aliases": [
                    {"kind": "metric", "normalized": "latency", "target_id": "cn:core:metric:p95-latency", "status": "active"},
                    {"kind": "metric", "normalized": "latency", "target_id": "cn:core:metric:p99-latency", "status": "active"},
                    {"kind": "metric", "normalized": "old-latency", "target_id": "cn:core:metric:p95-latency", "status": "deprecated", "deprecated_since": "2026-02-21T00:00:00Z"},
                ],
            }
        )
        errs_amb = reg.validate_ref(
            {"id": "cn:core:metric:p95-latency", "kind": "metric", "version": "1.0.0", "alias_used": "latency"}
        )
        errs_dep = reg.validate_ref(
            {"id": "cn:core:metric:p95-latency", "kind": "metric", "version": "1.0.0", "alias_used": "old-latency"}
        )
        self.assertTrue(any("E140" in e for e in errs_amb))
        self.assertTrue(any("W120" in e for e in errs_dep))

    def test_warning_emissions_for_deprecated_entry_and_missing_version(self):
        reg = CanonicalRegistry.from_manifest(
            {
                "entries": [
                    {
                        "id": "cn:core:metric:error-rate",
                        "kind": "metric",
                        "version": "1.0.0",
                        "status": "deprecated",
                        "lifecycle": {
                            "introduced_at": "2026-02-21T00:00:00Z",
                            "deprecated_since": "2026-02-21T00:00:00Z",
                        },
                    }
                ],
                "aliases": [],
            }
        )
        errs = reg.validate_ref({"id": "cn:core:metric:error-rate", "kind": "metric"})
        self.assertTrue(any("W110" in e for e in errs))
        self.assertTrue(any("W130" in e for e in errs))

    def test_preferred_label_is_resolvable_alias(self):
        reg = CanonicalRegistry.from_manifest(
            {
                "entries": [
                    {
                        "id": "cn:core:role:reviewer",
                        "kind": "role",
                        "preferred_label": "reviewer",
                        "version": "1.0.0",
                        "status": "active",
                        "lifecycle": {"introduced_at": "2026-02-21T00:00:00Z"},
                    }
                ],
                "aliases": [],
            }
        )
        self.assertEqual("cn:core:role:reviewer", reg.resolve_alias("role", "reviewer"))

    def test_alias_normalization_treats_hyphen_and_underscore_equivalently(self):
        reg = CanonicalRegistry.from_manifest(
            {
                "entries": [
                    {
                        "id": "cn:core:policy:spec-first",
                        "kind": "policy",
                        "preferred_label": "spec_first",
                        "version": "1.0.0",
                        "status": "active",
                        "lifecycle": {"introduced_at": "2026-02-21T00:00:00Z"},
                    }
                ],
                "aliases": [],
            }
        )
        self.assertEqual("cn:core:policy:spec-first", reg.resolve_alias("policy", "spec_first"))
        self.assertEqual("cn:core:policy:spec-first", reg.resolve_alias("policy", "spec-first"))
        self.assertEqual("cn:core:policy:spec-first", reg.resolve_alias("policy", "spec first"))

    def test_load_ignores_malformed_manifest_alias(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "canon").mkdir(parents=True)
            manifest = {
                "registry_version": "1.0.0",
                "entries": [],
                "aliases": [{"kind": "unit"}],
            }
            (root / "canon" / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            reg = CanonicalRegistry.load(str(root))
            self.assertEqual({}, reg.entries)

    def test_load_supports_modular_registry_without_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            canon_root = root / "canon"
            (canon_root / "kinds").mkdir(parents=True)
            (canon_root / "kinds" / "unit.json").write_text(
                json.dumps(
                    {
                        "registry_version": "1.0.0",
                        "kind": "unit",
                        "entries": [
                            {
                                "id": "cn:core:unit:ms",
                                "kind": "unit",
                                "preferred_label": "milliseconds",
                                "version": "1.0.0",
                                "status": "active",
                                "aliases": ["ms"],
                                "lifecycle": {"introduced_at": "2026-02-21T00:00:00Z"},
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (canon_root / "aliases.json").write_text(
                json.dumps(
                    {
                        "registry_version": "1.0.0",
                        "aliases": [
                            {
                                "kind": "unit",
                                "normalized": "milliseconds",
                                "target_id": "cn:core:unit:ms",
                                "status": "active",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            reg = CanonicalRegistry.load(str(root))
            self.assertEqual("cn:core:unit:ms", reg.resolve_alias("unit", "milliseconds"))
            self.assertIsNotNone(reg.get("cn:core:unit:ms"))

    def test_load_merges_modular_entries_with_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            canon_root = root / "canon"
            (canon_root / "kinds").mkdir(parents=True)
            (canon_root / "manifest.json").write_text(
                json.dumps(
                    {
                        "registry_version": "1.0.0",
                        "entries": [],
                        "aliases": [],
                    }
                ),
                encoding="utf-8",
            )
            (canon_root / "kinds" / "stage.json").write_text(
                json.dumps(
                    {
                        "registry_version": "1.0.0",
                        "kind": "stage",
                        "entries": [
                            {
                                "id": "cn:core:stage:ci",
                                "kind": "stage",
                                "preferred_label": "ci",
                                "version": "1.0.0",
                                "status": "active",
                                "aliases": ["continuous integration"],
                                "lifecycle": {"introduced_at": "2026-02-21T00:00:00Z"},
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            reg = CanonicalRegistry.load(str(root))
            self.assertIsNotNone(reg.get("cn:core:stage:ci"))
            self.assertEqual("cn:core:stage:ci", reg.resolve_alias("stage", "continuous integration"))

    def test_load_reports_malformed_modular_registry_file_without_raising(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            canon_root = root / "canon"
            canon_root.mkdir(parents=True)
            (canon_root / "aliases.json").write_text("{bad", encoding="utf-8")

            reg = CanonicalRegistry.load(str(root))
            self.assertEqual({}, reg.entries)
            self.assertTrue(any("invalid_aliases" in e for e in reg.load_errors))

    def test_load_reports_structurally_invalid_kind_file_without_raising(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            canon_root = root / "canon"
            kinds_root = canon_root / "kinds"
            kinds_root.mkdir(parents=True)
            (kinds_root / "term.json").write_text(
                json.dumps(
                    {
                        "kind": "term",
                        "registry_version": "1.0.0",
                        "entries": {"id": "cn:core:term:jwt", "preferred_label": "jwt"},
                    }
                ),
                encoding="utf-8",
            )

            reg = CanonicalRegistry.load(str(root))
            self.assertEqual({}, reg.entries)
            self.assertTrue(any("invalid_kind_file" in e for e in reg.load_errors))
            self.assertTrue(any("entries must be an array" in e for e in reg.load_errors))


if __name__ == "__main__":
    unittest.main()
