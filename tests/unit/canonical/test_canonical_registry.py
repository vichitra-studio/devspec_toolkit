import json
import tempfile
import unittest
from pathlib import Path

from specdev_tools.canonical.registry import CanonicalRegistry

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "canonical"


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
            self.assertEqual([], [e for e in errs if e.code.startswith("E")])

    def test_kind_mismatch(self):
        reg = CanonicalRegistry.from_manifest(
            {
                "entries": [{"id": "cn:core:unit:percent", "kind": "unit", "version": "1.0.0", "status": "active"}],
                "aliases": []
            }
        )
        errs = reg.validate_ref({"id": "cn:core:unit:percent", "kind": "metric", "version": "1.0.0"})
        self.assertTrue(any(e.code == "E120" for e in errs))

    def test_version_mismatch_fixture(self):
        manifest = json.loads((FIXTURE_DIR / "manifest_version_mismatch.json").read_text(encoding="utf-8"))
        reg = CanonicalRegistry.from_manifest(manifest)
        errs = reg.validate_ref({"id": "cn:core:metric:error-rate", "kind": "metric", "version": "^1.0.0"})
        self.assertTrue(any(e.code == "E130" for e in errs))

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
        self.assertTrue(any(e.code == "E140" for e in errs_amb))
        self.assertTrue(any(e.code == "W120" for e in errs_dep))

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
        self.assertTrue(any(e.code == "W110" for e in errs))
        self.assertTrue(any(e.code == "W130" for e in errs))

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
            self.assertTrue(any("invalid_aliases" in e.render() for e in reg.load_errors))

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
            self.assertTrue(any("invalid_kind_file" in e.render() for e in reg.load_errors))
            self.assertTrue(any("entries must be an array" in e.render() for e in reg.load_errors))


    def test_alias_lifecycle_stored(self):
        reg = CanonicalRegistry.from_manifest(
            {
                "entries": [
                    {"id": "cn:core:unit:ms", "kind": "unit", "version": "1.0.0", "status": "active"}
                ],
                "aliases": [
                    {
                        "kind": "unit",
                        "normalized": "millis",
                        "target_id": "cn:core:unit:ms",
                        "status": "deprecated",
                        "lifecycle": {
                            "deprecated_since": "2026-01-15",
                            "sunset_date": "2026-06-01",
                            "replaced_by": "cn:core:unit:ms",
                        },
                    }
                ],
            }
        )
        key = ("unit", "millis")
        self.assertIn(key, reg.alias_lifecycle)
        self.assertEqual(reg.alias_lifecycle[key]["replaced_by"], "cn:core:unit:ms")

    def test_sunset_expired_emits_E125(self):
        reg = CanonicalRegistry.from_manifest(
            {
                "entries": [
                    {"id": "cn:core:unit:ms", "kind": "unit", "version": "1.0.0", "status": "active"}
                ],
                "aliases": [
                    {
                        "kind": "unit",
                        "normalized": "millisec",
                        "target_id": "cn:core:unit:ms",
                        "status": "deprecated",
                        "lifecycle": {
                            "deprecated_since": "2025-06-01",
                            "sunset_date": "2025-12-31",
                            "replaced_by": "cn:core:unit:ms",
                        },
                    }
                ],
            }
        )
        errs = reg.validate_ref(
            {"id": "cn:core:unit:ms", "kind": "unit", "version": "1.0.0", "alias_used": "millisec"}
        )
        self.assertTrue(any(e.code == "E125" for e in errs), f"Expected E125 in {errs}")

    def test_deprecated_not_sunset_emits_W120_with_replaced_by(self):
        reg = CanonicalRegistry.from_manifest(
            {
                "entries": [
                    {"id": "cn:core:unit:ms", "kind": "unit", "version": "1.0.0", "status": "active"}
                ],
                "aliases": [
                    {
                        "kind": "unit",
                        "normalized": "millis",
                        "target_id": "cn:core:unit:ms",
                        "status": "deprecated",
                        "lifecycle": {
                            "deprecated_since": "2026-01-15",
                            "sunset_date": "2099-12-31",
                            "replaced_by": "cn:core:unit:ms",
                        },
                    }
                ],
            }
        )
        errs = reg.validate_ref(
            {"id": "cn:core:unit:ms", "kind": "unit", "version": "1.0.0", "alias_used": "millis"}
        )
        self.assertTrue(any(e.code == "W120" and "replaced_by" in e.message for e in errs), f"Expected W120 with replaced_by in {errs}")
        self.assertFalse(any(e.code == "E125" for e in errs), f"Did not expect E125 in {errs}")


    def test_registry_loader_includes_examples_directory(self):
        """Regression guard: canon/examples/ entries MUST be loaded into the registry.

        Auth entries (and other domain starter-kit entries) live in canon/examples/*.json.
        The loader must scan that directory and merge all entries so that canonical-lint
        and canonical-integrity can resolve IDs like cn:core:capability:authentication.
        Manifest/kinds entries take precedence over examples entries when IDs collide.
        """
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            canon_root = root / "canon"
            examples_dir = canon_root / "examples"
            examples_dir.mkdir(parents=True)

            example_ids = [
                "cn:core:capability:authentication",
                "cn:core:action:authenticate",
                "cn:core:entity:user",
            ]
            example_doc = {
                "registry_version": "1.0.0",
                "entries": [
                    {
                        "id": eid,
                        "kind": eid.split(":")[2],
                        "preferred_label": eid.split(":")[-1],
                        "version": "1.0.0",
                        "status": "active",
                        "lifecycle": {"introduced_at": "2026-02-21T00:00:00Z"},
                    }
                    for eid in example_ids
                ],
                "aliases": [],
            }
            (examples_dir / "auth_demo.json").write_text(
                __import__("json").dumps(example_doc), encoding="utf-8"
            )

            reg = CanonicalRegistry.load(str(root))

            for eid in example_ids:
                self.assertIsNotNone(
                    reg.get(eid),
                    msg=f"Entry {eid!r} from canon/examples/ must be resolvable in the registry",
                )

    def test_registry_loader_manifest_takes_precedence_over_examples(self):
        """Manifest entries override same-ID entries from canon/examples/."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            canon_root = root / "canon"
            examples_dir = canon_root / "examples"
            examples_dir.mkdir(parents=True)

            # examples version = "9.9.9", manifest version = "1.0.0"
            (examples_dir / "demo.json").write_text(
                __import__("json").dumps({
                    "registry_version": "1.0.0",
                    "entries": [
                        {
                            "id": "cn:core:unit:percent",
                            "kind": "unit",
                            "preferred_label": "percent",
                            "version": "9.9.9",
                            "status": "active",
                        }
                    ],
                    "aliases": [],
                }),
                encoding="utf-8",
            )
            (canon_root / "manifest.json").write_text(
                __import__("json").dumps({
                    "registry_version": "1.0.0",
                    "entries": [
                        {
                            "id": "cn:core:unit:percent",
                            "kind": "unit",
                            "preferred_label": "percent",
                            "version": "1.0.0",
                            "status": "active",
                        }
                    ],
                    "aliases": [],
                }),
                encoding="utf-8",
            )

            reg = CanonicalRegistry.load(str(root))
            entry = reg.get("cn:core:unit:percent")
            assert entry is not None, "cn:core:unit:percent must be resolvable"
            self.assertEqual("1.0.0", entry.version,
                             "Manifest entry (v1.0.0) must win over examples entry (v9.9.9)")


if __name__ == "__main__":
    unittest.main()
