import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from specdev_tools.canonical_integrity import validate_canonical_integrity, validate_canonical_integrity_file


class CanonicalIntegrityTests(unittest.TestCase):
    def test_missing_spec_dir_is_reported(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            errs = validate_canonical_integrity(str(root), str(root / "spec"))
            self.assertTrue(any("missing_spec_dir" in e for e in errs))

    def test_unknown_id_detected(self):
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
                        "metric_ref": {"id": "cn:core:metric:err-rate", "kind": "metric"}
                    }
                ),
                encoding="utf-8",
            )
            errs = validate_canonical_integrity(str(root), str(root / "spec"))
            self.assertTrue(any("E110" in e for e in errs))

    def test_invalid_json_is_reported_not_raised(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "canon").mkdir()
            (root / "canon" / "manifest.json").write_text(
                json.dumps({"registry_version": "1.0.0", "entries": [], "aliases": []}),
                encoding="utf-8",
            )
            (root / "spec").mkdir()
            (root / "spec" / "bad.json").write_text("{bad", encoding="utf-8")
            errs = validate_canonical_integrity(str(root), str(root / "spec"))
            self.assertTrue(any("invalid_json" in e for e in errs))

    def test_malformed_modular_canon_file_is_reported_not_traceback(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "canon").mkdir()
            (root / "spec").mkdir()
            (root / "canon" / "aliases.json").write_text("{bad", encoding="utf-8")
            (root / "spec" / "07_nfrs.json").write_text(json.dumps({"metric": "error rate"}), encoding="utf-8")
            errs = validate_canonical_integrity(str(root), str(root / "spec"))
            self.assertTrue(any("invalid_aliases" in e for e in errs))

    def test_structurally_invalid_kind_file_is_reported(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "canon").mkdir()
            (root / "canon" / "kinds").mkdir()
            (root / "spec").mkdir()
            (root / "canon" / "kinds" / "term.json").write_text(
                json.dumps(
                    {
                        "kind": "term",
                        "registry_version": "1.0.0",
                        "entries": {"id": "cn:core:term:jwt", "preferred_label": "jwt"},
                    }
                ),
                encoding="utf-8",
            )
            (root / "spec" / "03_glossary.json").write_text(
                json.dumps({"terms": [], "canonical_proposals": [], "canonical_conflicts": []}),
                encoding="utf-8",
            )
            errs = validate_canonical_integrity(str(root), str(root / "spec"))
            self.assertTrue(any("invalid_kind_file" in e for e in errs))
            self.assertTrue(any("entries must be an array" in e for e in errs))

    def test_invalid_alias_required_fields_are_reported(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "canon").mkdir()
            (root / "spec").mkdir()
            (root / "canon" / "aliases.json").write_text(
                json.dumps(
                    {
                        "registry_version": "1.0.0",
                        "aliases": [{"kind": "term", "normalized": "jwt"}],
                    }
                ),
                encoding="utf-8",
            )
            (root / "spec" / "artifact.json").write_text(
                json.dumps({"canonical_refs_used": [], "canonical_proposals": [], "canonical_conflicts": []}),
                encoding="utf-8",
            )
            errs = validate_canonical_integrity(str(root), str(root / "spec"))
            self.assertTrue(any("manifest.aliases[0] missing target_id" in e for e in errs))

    def test_missing_entry_lifecycle_is_reported(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "canon").mkdir()
            (root / "canon" / "kinds").mkdir()
            (root / "spec").mkdir()
            (root / "canon" / "kinds" / "term.json").write_text(
                json.dumps(
                    {
                        "kind": "term",
                        "registry_version": "1.0.0",
                        "entries": [
                            {
                                "id": "cn:core:term:jwt",
                                "kind": "term",
                                "preferred_label": "jwt",
                                "definition": "token",
                                "version": "1.0.0",
                                "status": "active",
                                "owners": ["team"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (root / "spec" / "artifact.json").write_text(
                json.dumps({"canonical_refs_used": [], "canonical_proposals": [], "canonical_conflicts": []}),
                encoding="utf-8",
            )
            errs = validate_canonical_integrity(str(root), str(root / "spec"))
            self.assertTrue(any("missing introduced_at" in e for e in errs))

    def test_unknown_schema_uri_is_reported(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "canon").mkdir()
            (root / "canon" / "manifest.json").write_text(
                json.dumps({"registry_version": "1.0.0", "entries": [], "aliases": []}),
                encoding="utf-8",
            )
            (root / "tools").mkdir()
            (root / "tools" / "schema_registry.json").write_text(json.dumps({}), encoding="utf-8")
            (root / "spec").mkdir()
            (root / "spec" / "11_redteam.json").write_text(
                json.dumps(
                    {
                        "$schema": "https://specdev.local/schema/does-not-exist/1",
                        "threats": [
                            {
                                "threat_id": "t1",
                                "description": "d",
                                "vector": "v",
                                "severity": "low",
                                "category": "authn",
                                "target_ids": [],
                                "mitigations": [],
                            }
                        ],
                        "edge_cases": [],
                        "negative_tests": [],
                        "traceability": [],
                        "canonical_refs_used": [],
                        "canonical_proposals": [],
                        "canonical_conflicts": [],
                    }
                ),
                encoding="utf-8",
            )
            errs = validate_canonical_integrity(str(root), str(root / "spec"))
            self.assertTrue(any("schema_not_found" in e for e in errs))
            self.assertFalse(any("unresolved_canonical_semantic" in e for e in errs))

    def test_external_schema_ref_does_not_trigger_false_unresolved_semantics(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "canon").mkdir()
            (root / "canon" / "manifest.json").write_text(
                json.dumps({"registry_version": "1.0.0", "entries": [], "aliases": []}),
                encoding="utf-8",
            )
            (root / "tools").mkdir()
            (root / "schema").mkdir()
            (root / "tools" / "schema_registry.json").write_text(
                json.dumps(
                    {
                        "https://specdev.local/schema/test/1": "schema/test.schema.json",
                        "https://specdev.local/schema/shared/1": "schema/shared.schema.json",
                    }
                ),
                encoding="utf-8",
            )
            (root / "schema" / "test.schema.json").write_text(
                json.dumps(
                    {
                        "$schema": "https://json-schema.org/draft/2020-12/schema",
                        "$id": "https://specdev.local/schema/test/1",
                        "type": "object",
                        "properties": {
                            "obj": {"$ref": "https://specdev.local/schema/shared/1#/$defs/object"},
                            "canonical_refs_used": {"type": "array"},
                            "canonical_proposals": {"type": "array"},
                            "canonical_conflicts": {"type": "array"},
                        },
                        "required": ["obj", "canonical_refs_used", "canonical_proposals", "canonical_conflicts"],
                    }
                ),
                encoding="utf-8",
            )
            (root / "schema" / "shared.schema.json").write_text(
                json.dumps(
                    {
                        "$schema": "https://json-schema.org/draft/2020-12/schema",
                        "$id": "https://specdev.local/schema/shared/1",
                        "$defs": {
                            "object": {
                                "type": "object",
                                "properties": {"status": {"type": "string"}},
                                "required": ["status"],
                                "additionalProperties": False,
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            (root / "spec").mkdir()
            (root / "spec" / "sample.json").write_text(
                json.dumps(
                    {
                        "$schema": "https://specdev.local/schema/test/1",
                        "obj": {"status": "active"},
                        "canonical_refs_used": [],
                        "canonical_proposals": [],
                        "canonical_conflicts": [],
                    }
                ),
                encoding="utf-8",
            )
            errs = validate_canonical_integrity(str(root), str(root / "spec"))
            self.assertFalse(any("unresolved_canonical_semantic" in e for e in errs))

    def test_file_mode_can_skip_unresolved_semantic_enforcement(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "canon").mkdir()
            (root / "canon" / "manifest.json").write_text(
                json.dumps({"registry_version": "1.0.0", "entries": [], "aliases": []}),
                encoding="utf-8",
            )
            (root / "tools").mkdir()
            (root / "tools" / "schema_registry.json").write_text(
                json.dumps(
                    {
                        "https://specdev.local/schema/03_glossary.schema.json": "schema/03_glossary.schema.json",
                        "https://specdev.local/schema/core/atoms/1": "schema/atoms.schema.json",
                        "https://specdev.local/schema/core/collections/1": "schema/collections.schema.json",
                    }
                ),
                encoding="utf-8",
            )
            (root / "schema").mkdir()
            repo_root = Path(__file__).resolve().parents[1]
            (root / "schema" / "03_glossary.schema.json").write_text(
                (repo_root / "schema" / "03_glossary.schema.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (root / "schema" / "atoms.schema.json").write_text(
                (repo_root / "schema" / "core" / "atoms.schema.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (root / "schema" / "collections.schema.json").write_text(
                (repo_root / "schema" / "core" / "collections.schema.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (root / "spec").mkdir()
            sample = root / "spec" / "03_glossary.json"
            sample.write_text(
                json.dumps(
                    {
                        "$schema": "https://specdev.local/schema/03_glossary.schema.json",
                        "id": "glossary-auth",
                        "owner": "api",
                        "created_at": "2026-01-01T00:00:00Z",
                        "seed_refs": [{"seed_id": "seed-overview"}],
                        "terms": [
                            {
                                "term_id": "term-jwt",
                                "term": "JWT",
                                "definition": "JSON Web Token used to carry signed authentication claims.",
                            }
                        ],
                        "generation_quality": {"preflight_passed": True},
                        "canonical_refs_used": [],
                        "canonical_proposals": [],
                        "canonical_conflicts": [],
                    }
                ),
                encoding="utf-8",
            )

            strict = validate_canonical_integrity_file(str(root), str(sample))
            self.assertTrue(any("unresolved_canonical_semantic" in e for e in strict))

            non_strict = validate_canonical_integrity_file(
                str(root),
                str(sample),
                enforce_unresolved_semantics=False,
            )
            self.assertFalse(any("unresolved_canonical_semantic" in e for e in non_strict))

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
            (root / "spec" / "artifact.json").write_text(json.dumps({}), encoding="utf-8")

            strict = validate_canonical_integrity(
                str(root),
                str(root / "spec"),
                require_manifest_schema_registration=True,
            )
            self.assertTrue(any("schema_uri_not_registered" in e for e in strict))

            relaxed = validate_canonical_integrity(
                str(root),
                str(root / "spec"),
                require_manifest_schema_registration=False,
            )
            self.assertFalse(any("schema_uri_not_registered" in e for e in relaxed))


if __name__ == "__main__":
    unittest.main()
