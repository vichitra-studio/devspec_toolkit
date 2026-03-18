import unittest
from pathlib import Path
import json

from specdev_tools.canonical.lint import lint_manifest
from specdev_tools.canonical.lint import lint_canon_dir
from specdev_tools.core.registry import SchemaRegistry

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "canonical"


class CanonicalLintTests(unittest.TestCase):
    def test_alias_collision(self):
        manifest = json.loads((FIXTURE_DIR / "manifest_alias_conflict.json").read_text(encoding="utf-8"))
        errs = lint_manifest(manifest)
        self.assertTrue(any(e.code == "E410" for e in errs))

    def test_deprecated_requires_timestamp(self):
        manifest = json.loads((FIXTURE_DIR / "manifest_invalid_deprecated.json").read_text(encoding="utf-8"))
        errs = lint_manifest(manifest)
        self.assertTrue(any(e.code == "E420" for e in errs))

    def test_missing_manifest_reports_unresolved_input(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            errs = lint_canon_dir(td, require_manifest_schema_registration=False)
            self.assertTrue(any(e.code == "E520" for e in errs))

    def test_malformed_manifest_shapes_report_unresolved_input(self):
        errs = lint_manifest({"entries": [None], "aliases": [None]})
        self.assertTrue(any(e.code == "E520" for e in errs))

    def test_invalid_manifest_json_reports_unresolved_input(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            canon = Path(td) / "canon"
            canon.mkdir()
            (canon / "manifest.json").write_text("{bad", encoding="utf-8")
            errs = lint_canon_dir(td, require_manifest_schema_registration=False)
            self.assertTrue(any("invalid_manifest" in e.render() for e in errs))

    def test_manifest_root_must_be_object(self):
        errs = lint_manifest([])
        self.assertTrue(any("manifest root must be an object" in e.render() for e in errs))

    def test_lint_canon_dir_accepts_modular_registry_without_manifest(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            canon = Path(td) / "canon"
            (canon / "kinds").mkdir(parents=True)
            (canon / "aliases.json").write_text(
                json.dumps(
                    {
                        "registry_version": "1.0.0",
                        "aliases": [
                            {
                                "kind": "stage",
                                "normalized": "continuous integration",
                                "target_id": "cn:core:stage:ci",
                                "status": "active",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (canon / "kinds" / "stage.json").write_text(
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
            errs = lint_canon_dir(td, require_manifest_schema_registration=False)
            self.assertEqual([], errs)

    def test_lint_canon_dir_reports_malformed_aliases_without_manifest(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            canon = Path(td) / "canon"
            canon.mkdir(parents=True)
            (canon / "aliases.json").write_text("{bad", encoding="utf-8")

            errs = lint_canon_dir(td, require_manifest_schema_registration=False)
            self.assertTrue(any("invalid_aliases" in e.render() for e in errs))

    def test_lint_manifest_requires_alias_target_id(self):
        errs = lint_manifest(
            {
                "registry_version": "1.0.0",
                "entries": [],
                "aliases": [{"kind": "term", "normalized": "jwt", "status": "active"}],
            }
        )
        self.assertTrue(any("missing target_id" in e.render() for e in errs))

    def test_lint_manifest_handles_non_string_entry_id_without_crash(self):
        errs = lint_manifest(
            {
                "registry_version": "1.0.0",
                "entries": [
                    {
                        "id": {"bad": 1},
                        "kind": "term",
                        "preferred_label": "jwt",
                        "definition": "token",
                        "version": "1.0.0",
                        "status": "active",
                        "lifecycle": {"introduced_at": "2026-01-01T00:00:00Z"},
                    }
                ],
                "aliases": [],
            }
        )
        self.assertTrue(any("manifest.entries[0] missing id" in e.render() for e in errs))

    def test_lint_manifest_handles_non_string_entry_kind_without_crash(self):
        errs = lint_manifest(
            {
                "registry_version": "1.0.0",
                "entries": [
                    {
                        "id": "cn:core:term:jwt",
                        "kind": {"bad": 1},
                        "aliases": ["JWT"],
                        "preferred_label": "jwt",
                        "definition": "token",
                        "version": "1.0.0",
                        "status": "active",
                        "lifecycle": {"introduced_at": "2026-01-01T00:00:00Z"},
                    }
                ],
                "aliases": [],
            }
        )
        self.assertTrue(any("manifest.entries[0] missing kind" in e.render() for e in errs))

    def test_lint_canon_dir_reports_manifest_modular_drift(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            canon = Path(td) / "canon"
            (canon / "kinds").mkdir(parents=True)
            (canon / "manifest.json").write_text(
                json.dumps(
                    {
                        "registry_version": "1.0.0",
                        "entries": [
                            {
                                "id": "cn:core:stage:ci",
                                "kind": "stage",
                                "preferred_label": "ci",
                                "definition": "Old definition.",
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
            (canon / "kinds" / "stage.json").write_text(
                json.dumps(
                    {
                        "registry_version": "1.0.0",
                        "kind": "stage",
                        "entries": [
                            {
                                "id": "cn:core:stage:ci",
                                "kind": "stage",
                                "preferred_label": "ci",
                                "definition": "New definition.",
                                "version": "1.0.0",
                                "status": "active",
                                "lifecycle": {"introduced_at": "2026-02-21T00:00:00Z"},
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            errs = lint_canon_dir(td, require_manifest_schema_registration=False)
            self.assertTrue(any("canonical_manifest_modular_mismatch" in e.render() for e in errs))

    def test_schema_registry_includes_canon_modular_schemas(self):
        repo_root = Path(__file__).resolve().parents[3]
        registry = SchemaRegistry(str(repo_root))
        aliases_uri = "https://specdev.local/schema/canon/aliases/1"
        kind_uri = "https://specdev.local/schema/canon/kind/1"

        self.assertEqual("canon/aliases.schema.json", registry.map.get(aliases_uri))
        self.assertEqual("canon/kind.schema.json", registry.map.get(kind_uri))
        self.assertIsNotNone(registry.resolve(aliases_uri))
        self.assertIsNotNone(registry.resolve(kind_uri))

    def test_lint_canon_dir_validates_modular_files_against_registered_schema(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "canon" / "kinds").mkdir(parents=True)
            (root / "schema" / "core").mkdir(parents=True)
            (root / "tools").mkdir(parents=True)

            (root / "schema" / "core" / "canon.schema.json").write_text(
                json.dumps(
                    {
                        "$schema": "https://json-schema.org/draft/2020-12/schema",
                        "$id": "https://specdev.local/schema/core/canon/1",
                        "$defs": {
                            "semver": {"type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$"},
                            "alias": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "kind": {"type": "string"},
                                    "normalized": {"type": "string"},
                                    "target_id": {"type": "string"},
                                    "status": {"type": "string"},
                                },
                                "required": ["kind", "normalized", "target_id", "status"],
                            },
                            "entry": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "id": {"type": "string"},
                                    "kind": {"type": "string"},
                                    "preferred_label": {"type": "string"},
                                    "definition": {"type": "string"},
                                    "version": {"type": "string"},
                                    "status": {"type": "string"},
                                    "owners": {"type": "array", "items": {"type": "string"}},
                                    "aliases": {"type": "array", "items": {"type": "string"}},
                                    "lifecycle": {"type": "object", "properties": {"introduced_at": {"type": "string"}}, "required": ["introduced_at"]},
                                },
                                "required": ["id", "kind", "preferred_label", "definition", "version", "status", "owners", "lifecycle"],
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )
            (root / "canon" / "aliases.schema.json").write_text(
                (Path(__file__).resolve().parents[3] / "canon" / "aliases.schema.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (root / "canon" / "kind.schema.json").write_text(
                (Path(__file__).resolve().parents[3] / "canon" / "kind.schema.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (root / "tools" / "schema_registry.json").write_text(
                json.dumps(
                    {
                        "https://specdev.local/schema/core/canon/1": "schema/core/canon.schema.json",
                        "https://specdev.local/schema/canon/aliases/1": "canon/aliases.schema.json",
                        "https://specdev.local/schema/canon/kind/1": "canon/kind.schema.json",
                    }
                ),
                encoding="utf-8",
            )

            (root / "canon" / "kinds" / "stage.json").write_text(
                json.dumps(
                    {
                        "registry_version": "1.0.0",
                        "kind": "stage",
                        "entries": [
                            {
                                "id": "cn:core:stage:ci",
                                "kind": "stage",
                                "preferred_label": "ci",
                                "definition": "CI stage",
                                "version": "1.0.0",
                                "status": "active",
                                "owners": ["spec-platform"],
                                "aliases": ["continuous integration"],
                                "lifecycle": {"introduced_at": "2026-02-21T00:00:00Z"},
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (root / "canon" / "aliases.json").write_text(
                json.dumps(
                    {
                        "registry_version": "1.0.0",
                        "aliases": [
                            {
                                "kind": "stage",
                                "normalized": "continuous integration",
                                "target_id": "cn:core:stage:ci",
                                "status": "active",
                                "extra": "not-allowed"
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            errs = lint_canon_dir(str(root), require_manifest_schema_registration=False)
            self.assertTrue(any("schema_invalid" in e.render() for e in errs))

    def test_lint_canon_dir_validates_manifest_against_registered_schema(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "canon").mkdir(parents=True)
            (root / "schema" / "core").mkdir(parents=True)
            (root / "tools").mkdir(parents=True)

            (root / "schema" / "core" / "canon.schema.json").write_text(
                (Path(__file__).resolve().parents[3] / "schema" / "core" / "canon.schema.json").read_text(
                    encoding="utf-8"
                ),
                encoding="utf-8",
            )
            (root / "tools" / "schema_registry.json").write_text(
                json.dumps(
                    {
                        "https://specdev.local/schema/core/canon/1": "schema/core/canon.schema.json",
                    }
                ),
                encoding="utf-8",
            )
            (root / "canon" / "manifest.json").write_text(
                json.dumps(
                    {
                        "registry_version": "1.0.0",
                        "entries": [
                            {
                                "id": "cn:core:term:jwt",
                                "kind": "term",
                                "preferred_label": "jwt",
                                "definition": "token",
                                "version": "1.0.0",
                                "status": "nonsense",
                                "owners": ["spec-platform"],
                                "lifecycle": {"introduced_at": "2026-02-21T00:00:00Z"},
                            }
                        ],
                        "aliases": [],
                    }
                ),
                encoding="utf-8",
            )

            errs = lint_canon_dir(str(root), require_manifest_schema_registration=False)
            self.assertTrue(any("schema_invalid" in e.render() and "manifest.json" in e.render() for e in errs))

    def test_lint_canon_dir_can_require_manifest_schema_registration(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "canon").mkdir(parents=True)
            (root / "tools").mkdir(parents=True)
            (root / "tools" / "schema_registry.json").write_text(
                json.dumps(
                    {
                        "https://specdev.local/schema/canon/aliases/1": "canon/aliases.schema.json",
                        "https://specdev.local/schema/canon/kind/1": "canon/kind.schema.json",
                    }
                ),
                encoding="utf-8",
            )
            (root / "canon" / "manifest.json").write_text(
                json.dumps(
                    {
                        "registry_version": "1.0.0",
                        "entries": [
                            {
                                "id": "cn:core:term:jwt",
                                "kind": "term",
                                "preferred_label": "jwt",
                                "definition": "token",
                                "version": "1.0.0",
                                "status": "active",
                                "owners": ["spec-platform"],
                                "lifecycle": {"introduced_at": "2026-02-21T00:00:00Z"},
                            }
                        ],
                        "aliases": [],
                    }
                ),
                encoding="utf-8",
            )

            errs = lint_canon_dir(str(root), require_manifest_schema_registration=True)
            self.assertTrue(any("schema_uri_not_registered" in e.render() for e in errs))

    def test_lint_canon_dir_fails_when_strict_and_schema_registry_missing(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "canon").mkdir(parents=True)
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

            errs = lint_canon_dir(str(root), require_manifest_schema_registration=True)
            self.assertTrue(any("missing_schema_registry" in e.render() for e in errs))


if __name__ == "__main__":
    unittest.main()
