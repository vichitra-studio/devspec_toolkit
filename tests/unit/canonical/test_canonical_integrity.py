import json
import tempfile
import unittest
from pathlib import Path

from specdev_tools.canonical.integrity import validate_canonical_integrity, validate_canonical_integrity_file


class CanonicalIntegrityTests(unittest.TestCase):
    def test_missing_spec_dir_is_reported(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            errs = validate_canonical_integrity(str(root), str(root / "spec"), require_manifest_schema_registration=False)
            self.assertTrue(any("missing_spec_dir" in e.render() for e in errs))

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
            errs = validate_canonical_integrity(str(root), str(root / "spec"), require_manifest_schema_registration=False)
            self.assertTrue(any(e.code == "E110" for e in errs))

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
            errs = validate_canonical_integrity(str(root), str(root / "spec"), require_manifest_schema_registration=False)
            self.assertTrue(any("invalid_json" in e.render() for e in errs))

    def test_malformed_modular_canon_file_is_reported_not_traceback(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "canon").mkdir()
            (root / "spec").mkdir()
            (root / "canon" / "aliases.json").write_text("{bad", encoding="utf-8")
            (root / "spec" / "07_nfrs.json").write_text(json.dumps({"metric": "error rate"}), encoding="utf-8")
            errs = validate_canonical_integrity(str(root), str(root / "spec"), require_manifest_schema_registration=False)
            self.assertTrue(any("invalid_aliases" in e.render() for e in errs))

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
            errs = validate_canonical_integrity(str(root), str(root / "spec"), require_manifest_schema_registration=False)
            self.assertTrue(any("invalid_kind_file" in e.render() for e in errs))
            self.assertTrue(any("entries must be an array" in e.render() for e in errs))

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
            errs = validate_canonical_integrity(str(root), str(root / "spec"), require_manifest_schema_registration=False)
            self.assertTrue(any("manifest.aliases[0] missing target_id" in e.render() for e in errs))

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
            errs = validate_canonical_integrity(str(root), str(root / "spec"), require_manifest_schema_registration=False)
            self.assertTrue(any("missing introduced_at" in e.render() for e in errs))

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
                        "$schema": "vc:does-not-exist",
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
            errs = validate_canonical_integrity(str(root), str(root / "spec"), require_manifest_schema_registration=False)
            self.assertTrue(any("schema_not_found" in e.render() for e in errs))
            self.assertFalse(any("unresolved_canonical_semantic" in e.render() for e in errs))

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
                        "vc:test": "schema/test.schema.json",
                        "vc:shared": "schema/shared.schema.json",
                    }
                ),
                encoding="utf-8",
            )
            (root / "schema" / "test.schema.json").write_text(
                json.dumps(
                    {
                        "$schema": "https://json-schema.org/draft/2020-12/schema",
                        "$id": "vc:test",
                        "type": "object",
                        "properties": {
                            "obj": {"$ref": "vc:shared#/$defs/object"},
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
                        "$id": "vc:shared",
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
                        "$schema": "vc:test",
                        "obj": {"status": "active"},
                        "canonical_refs_used": [],
                        "canonical_proposals": [],
                        "canonical_conflicts": [],
                    }
                ),
                encoding="utf-8",
            )
            errs = validate_canonical_integrity(str(root), str(root / "spec"), require_manifest_schema_registration=False)
            self.assertFalse(any("unresolved_canonical_semantic" in e.render() for e in errs))

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
                        "vc:03-glossary": "schema/03_glossary.schema.json",
                        "vc:core:atoms": "schema/atoms.schema.json",
                        "vc:core:collections": "schema/collections.schema.json",
                    }
                ),
                encoding="utf-8",
            )
            (root / "schema").mkdir()
            repo_root = Path(__file__).resolve().parents[3]
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
                        "$schema": "vc:03-glossary",
                        "id": "glossary-auth",
                        "owner": "api",
                        "created_at": "2026-01-01T00:00:00Z",
                        "terms": [
                            {
                                "term_id": "term-jwt",
                                "term": "JWT",
                                "definition": "JSON Web Token used to carry signed authentication claims.",
                            }
                        ],
                        "canonical_refs_used": [],
                        "canonical_proposals": [],
                        "canonical_conflicts": [],
                    }
                ),
                encoding="utf-8",
            )

            strict = validate_canonical_integrity_file(str(root), str(sample), require_manifest_schema_registration=False)
            self.assertTrue(any("unresolved_canonical_semantic" in e.render() for e in strict))

            non_strict = validate_canonical_integrity_file(
                str(root),
                str(sample),
                enforce_unresolved_semantics=False,
            )
            self.assertFalse(any("unresolved_canonical_semantic" in e.render() for e in non_strict))

    def test_string_typed_ref_sibling_does_not_trigger_e210(self):
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
                json.dumps({"vc:test": "schema/test.schema.json"}),
                encoding="utf-8",
            )
            (root / "schema" / "test.schema.json").write_text(
                json.dumps(
                    {
                        "$schema": "https://json-schema.org/draft/2020-12/schema",
                        "$id": "vc:test",
                        "type": "object",
                        "properties": {
                            "evidence": {"type": "string", "minLength": 20},
                            "evidence_ref": {"type": "string"},
                            "canonical_refs_used": {"type": "array"},
                            "canonical_proposals": {"type": "array"},
                            "canonical_conflicts": {"type": "array"},
                        },
                        "required": [
                            "evidence",
                            "evidence_ref",
                            "canonical_refs_used",
                            "canonical_proposals",
                            "canonical_conflicts",
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (root / "spec").mkdir()
            (root / "spec" / "sample.json").write_text(
                json.dumps(
                    {
                        "$schema": "vc:test",
                        "evidence": "command output captured here >=20 chars",
                        "evidence_ref": "https://example/log",
                        "canonical_refs_used": [],
                        "canonical_proposals": [],
                        "canonical_conflicts": [],
                    }
                ),
                encoding="utf-8",
            )
            errs = validate_canonical_integrity(str(root), str(root / "spec"), require_manifest_schema_registration=False)
            self.assertFalse(any("schema_not_found" in e.render() or "schema_uri_not_registered" in e.render() for e in errs))
            self.assertFalse(any("unresolved_canonical_semantic" in e.render() for e in errs))
            self.assertFalse(any("kind=evidence" in e.render() for e in errs))

    def test_canonical_ref_typed_sibling_still_flags_e210_when_unresolved(self):
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
                        "vc:test": "schema/test.schema.json",
                        "vc:core:atoms": "schema/atoms.schema.json",
                        "vc:core:collections": "schema/collections.schema.json",
                    }
                ),
                encoding="utf-8",
            )
            repo_root = Path(__file__).resolve().parents[3]
            (root / "schema" / "atoms.schema.json").write_text(
                (repo_root / "schema" / "core" / "atoms.schema.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (root / "schema" / "collections.schema.json").write_text(
                (repo_root / "schema" / "core" / "collections.schema.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (root / "schema" / "test.schema.json").write_text(
                json.dumps(
                    {
                        "$schema": "https://json-schema.org/draft/2020-12/schema",
                        "$id": "vc:test",
                        "type": "object",
                        "properties": {
                            "status": {"type": "string"},
                            "status_ref": {
                                "allOf": [
                                    {"$ref": "vc:core:collections#canonicalRef"},
                                    {"properties": {"kind": {"const": "status"}}},
                                ]
                            },
                            "canonical_refs_used": {"type": "array"},
                            "canonical_proposals": {"type": "array"},
                            "canonical_conflicts": {"type": "array"},
                        },
                        "required": [
                            "status",
                            "canonical_refs_used",
                            "canonical_proposals",
                            "canonical_conflicts",
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (root / "spec").mkdir()
            (root / "spec" / "sample.json").write_text(
                json.dumps(
                    {
                        "$schema": "vc:test",
                        "status": "passed",
                        "canonical_refs_used": [],
                        "canonical_proposals": [],
                        "canonical_conflicts": [],
                    }
                ),
                encoding="utf-8",
            )
            errs = validate_canonical_integrity(str(root), str(root / "spec"), require_manifest_schema_registration=False)
            self.assertFalse(any("schema_not_found" in e.render() or "schema_uri_not_registered" in e.render() for e in errs))
            self.assertTrue(
                any(
                    "unresolved_canonical_semantic" in e.render()
                    and "field=status" in e.render()
                    and "kind=status" in e.render()
                    for e in errs
                ),
                f"Expected E210 unresolved_canonical_semantic for status/status_ref, got: {[e.render() for e in errs]}",
            )

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
            self.assertTrue(any("schema_uri_not_registered" in e.render() for e in strict))

            relaxed = validate_canonical_integrity(
                str(root),
                str(root / "spec"),
                require_manifest_schema_registration=False,
            )
            self.assertFalse(any("schema_uri_not_registered" in e.render() for e in relaxed))


    def test_partial_drift_emits_E211_with_artifact_paths(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "canon").mkdir()
            (root / "spec").mkdir()
            (root / "canon" / "manifest.json").write_text(
                json.dumps(
                    {
                        "registry_version": "1.0.0",
                        "entries": [
                            {"id": "cn:core:unit:ms", "kind": "unit", "version": "1.0.0", "status": "active", "lifecycle": {"introduced_at": "2026-01-01T00:00:00Z"}},
                            {"id": "cn:core:unit:seconds", "kind": "unit", "version": "1.0.0", "status": "active", "lifecycle": {"introduced_at": "2026-01-01T00:00:00Z"}},
                        ],
                        "aliases": [],
                    }
                ),
                encoding="utf-8",
            )
            (root / "spec" / "a.json").write_text(
                json.dumps({"unit": "latency", "unit_ref": {"id": "cn:core:unit:ms", "kind": "unit"}}),
                encoding="utf-8",
            )
            (root / "spec" / "b.json").write_text(
                json.dumps({"unit": "latency", "unit_ref": {"id": "cn:core:unit:seconds", "kind": "unit"}}),
                encoding="utf-8",
            )
            errs = validate_canonical_integrity(str(root), str(root / "spec"), require_manifest_schema_registration=False)
            e211_errs = [e for e in errs if e.code == "E211"]
            self.assertTrue(e211_errs, f"Expected E211 in {errs}")
            # Check artifact paths are included
            combined = " ".join(e.render() for e in e211_errs)
            self.assertIn("a.json", combined)
            self.assertIn("b.json", combined)

    def test_single_cid_no_E211(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "canon").mkdir()
            (root / "spec").mkdir()
            (root / "canon" / "manifest.json").write_text(
                json.dumps(
                    {
                        "registry_version": "1.0.0",
                        "entries": [
                            {"id": "cn:core:unit:ms", "kind": "unit", "version": "1.0.0", "status": "active", "lifecycle": {"introduced_at": "2026-01-01T00:00:00Z"}},
                        ],
                        "aliases": [],
                    }
                ),
                encoding="utf-8",
            )
            (root / "spec" / "a.json").write_text(
                json.dumps({"unit": "latency", "unit_ref": {"id": "cn:core:unit:ms", "kind": "unit"}}),
                encoding="utf-8",
            )
            (root / "spec" / "b.json").write_text(
                json.dumps({"unit": "latency", "unit_ref": {"id": "cn:core:unit:ms", "kind": "unit"}}),
                encoding="utf-8",
            )
            errs = validate_canonical_integrity(str(root), str(root / "spec"), require_manifest_schema_registration=False)
            self.assertFalse(any(e.code == "E211" for e in errs), f"Did not expect E211 in {errs}")


class Step10CanonicalRefsFixtureTests(unittest.TestCase):
    """Regression: step-10 governance canonical refs (id_pattern_ref, policy_ref,
    command_ref) must resolve against the core canon without E110/E120."""

    def test_valid_with_canonical_refs_fixture(self):
        toolkit_root = Path(__file__).resolve().parents[3]
        fixture = toolkit_root / "tests" / "fixtures" / "step_10" / "valid_with_canonical_refs.json"
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            # Use the real toolkit canon so cn:core:policy:spec-first etc. resolve.
            canon_src = toolkit_root / "canon"
            import shutil
            shutil.copytree(canon_src, root / "canon")
            (root / "spec").mkdir()
            (root / "spec" / "10_governance.json").write_text(
                fixture.read_text(encoding="utf-8"), encoding="utf-8"
            )
            errs = validate_canonical_integrity(
                str(root), str(root / "spec"), require_manifest_schema_registration=False
            )
            offending = [e for e in errs if e.code in ("E110", "E120")]
            self.assertFalse(
                offending,
                f"Expected no E110/E120 for step-10 canonical refs, got: {[e.render() for e in offending]}",
            )


class Step10CanonicalRefsNegativeTests(unittest.TestCase):
    """Regression: a step-10 canonical ref whose kind does not match the canon
    entry's kind must raise E120 CANONICAL_KIND_MISMATCH."""

    def _run(self, fixture_name: str):
        toolkit_root = Path(__file__).resolve().parents[3]
        fixture = toolkit_root / "tests" / "fixtures" / "step_10" / fixture_name
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            import shutil
            shutil.copytree(toolkit_root / "canon", root / "canon")
            (root / "spec").mkdir()
            (root / "spec" / "10_governance.json").write_text(
                fixture.read_text(encoding="utf-8"), encoding="utf-8"
            )
            return validate_canonical_integrity(
                str(root), str(root / "spec"), require_manifest_schema_registration=False
            )

    def test_policy_ref_wrong_kind_raises_e120(self):
        errs = self._run("invalid_policy_ref_wrong_kind.json")
        e120 = [e for e in errs if e.code == "E120"]
        self.assertEqual(len(e120), 1, f"Expected one E120, got: {[e.render() for e in errs]}")
        self.assertIn("cn:core:policy:spec-first", e120[0].render())

    def test_command_ref_wrong_kind_raises_e120(self):
        errs = self._run("invalid_command_ref_wrong_kind.json")
        e120 = [e for e in errs if e.code == "E120"]
        self.assertEqual(len(e120), 1, f"Expected one E120, got: {[e.render() for e in errs]}")
        self.assertIn("cn:core:command:governance-check", e120[0].render())

    def test_id_pattern_ref_wrong_kind_raises_e120(self):
        errs = self._run("invalid_id_pattern_ref_wrong_kind.json")
        e120 = [e for e in errs if e.code == "E120"]
        self.assertEqual(len(e120), 1, f"Expected one E120, got: {[e.render() for e in errs]}")
        self.assertIn("cn:core:id_pattern:conventional-commit", e120[0].render())


class StructuredFieldTests(unittest.TestCase):
    """DEVSPEC-8: E110/E210/E211 errors carry subcode, file, jq_path, value."""

    def _make_root(self, td: str) -> Path:
        root = Path(td)
        (root / "canon").mkdir()
        (root / "spec").mkdir()
        return root

    def _write_manifest(self, root: Path, entries: list) -> None:
        (root / "canon" / "manifest.json").write_text(
            json.dumps({"registry_version": "1.0.0", "entries": entries, "aliases": []}),
            encoding="utf-8",
        )

    def test_e110_carries_structured_fields(self):
        """E110 from _validate_document_integrity has subcode/file/jq_path/value."""
        with tempfile.TemporaryDirectory() as td:
            root = self._make_root(td)
            self._write_manifest(root, [])
            (root / "spec" / "07_nfrs.json").write_text(
                json.dumps({
                    "metric_ref": {"id": "cn:core:metric:unknown-metric", "kind": "metric"},
                    "canonical_refs_used": [],
                    "canonical_proposals": [],
                    "canonical_conflicts": [],
                }),
                encoding="utf-8",
            )
            errs = validate_canonical_integrity(
                str(root), str(root / "spec"), require_manifest_schema_registration=False
            )
            e110 = [e for e in errs if e.code == "E110"]
            self.assertTrue(e110, f"Expected E110, got: {[e.render() for e in errs]}")
            err = e110[0]
            self.assertEqual(err.subcode, "UNKNOWN_CANONICAL_ID")
            self.assertIsNotNone(err.file)
            self.assertIn("07_nfrs.json", err.file)
            self.assertIsNotNone(err.jq_path)
            self.assertTrue(err.jq_path.startswith("."), f"jq_path must start with '.', got: {err.jq_path!r}")
            self.assertIn("metric_ref", err.jq_path)
            self.assertEqual(err.value, "cn:core:metric:unknown-metric")

    def test_e120_carries_structured_fields(self):
        """E120 from _validate_document_integrity has subcode/file/jq_path/value."""
        with tempfile.TemporaryDirectory() as td:
            root = self._make_root(td)
            self._write_manifest(root, [
                {
                    "id": "cn:core:unit:ms",
                    "kind": "unit",
                    "version": "1.0.0",
                    "status": "active",
                    "lifecycle": {"introduced_at": "2026-01-01T00:00:00Z"},
                }
            ])
            (root / "spec" / "07_nfrs.json").write_text(
                json.dumps({
                    "latency_ref": {"id": "cn:core:unit:ms", "kind": "metric"},
                    "canonical_refs_used": [],
                    "canonical_proposals": [],
                    "canonical_conflicts": [],
                }),
                encoding="utf-8",
            )
            errs = validate_canonical_integrity(
                str(root), str(root / "spec"), require_manifest_schema_registration=False
            )
            e120 = [e for e in errs if e.code == "E120"]
            self.assertTrue(e120, f"Expected E120, got: {[e.render() for e in errs]}")
            err = e120[0]
            self.assertEqual(err.subcode, "CANONICAL_KIND_MISMATCH")
            self.assertIsNotNone(err.file)
            self.assertIn("07_nfrs.json", err.file)
            self.assertIsNotNone(err.jq_path)
            self.assertTrue(err.jq_path.startswith("."))
            self.assertEqual(err.value, "cn:core:unit:ms")

    def test_e210_canonical_refs_used_missing_carries_structured_fields(self):
        """E210 from refs-used mismatch (missing) has subcode/file/jq_path/value."""
        with tempfile.TemporaryDirectory() as td:
            root = self._make_root(td)
            self._write_manifest(root, [
                {
                    "id": "cn:core:unit:ms",
                    "kind": "unit",
                    "version": "1.0.0",
                    "status": "active",
                    "lifecycle": {"introduced_at": "2026-01-01T00:00:00Z"},
                }
            ])
            # latency_ref uses cn:core:unit:ms but canonical_refs_used is empty
            (root / "spec" / "07_nfrs.json").write_text(
                json.dumps({
                    "latency_ref": {"id": "cn:core:unit:ms", "kind": "unit"},
                    "canonical_refs_used": [],
                    "canonical_proposals": [],
                    "canonical_conflicts": [],
                }),
                encoding="utf-8",
            )
            errs = validate_canonical_integrity(
                str(root), str(root / "spec"), require_manifest_schema_registration=False
            )
            e210 = [e for e in errs if e.code == "E210" and e.subcode == "CROSS_ARTIFACT_DRIFT"]
            self.assertTrue(e210, f"Expected E210 CROSS_ARTIFACT_DRIFT, got: {[e.render() for e in errs]}")
            missing_err = next(
                (e for e in e210 if "canonical_refs_used_missing" in e.message), None
            )
            self.assertIsNotNone(missing_err, "Expected canonical_refs_used_missing E210")
            self.assertEqual(missing_err.subcode, "CROSS_ARTIFACT_DRIFT")
            self.assertIn("07_nfrs.json", missing_err.file)
            self.assertEqual(missing_err.jq_path, ".canonical_refs_used")
            self.assertIn("cn:core:unit:ms", missing_err.value)

    def test_e210_canonical_refs_used_extra_carries_structured_fields(self):
        """E210 from refs-used mismatch (extra) has subcode/file/jq_path/value."""
        with tempfile.TemporaryDirectory() as td:
            root = self._make_root(td)
            self._write_manifest(root, [
                {
                    "id": "cn:core:unit:ms",
                    "kind": "unit",
                    "version": "1.0.0",
                    "status": "active",
                    "lifecycle": {"introduced_at": "2026-01-01T00:00:00Z"},
                }
            ])
            # canonical_refs_used lists cn:core:unit:ms but no *_ref field uses it
            (root / "spec" / "07_nfrs.json").write_text(
                json.dumps({
                    "description": "no refs used in body",
                    "canonical_refs_used": [{"id": "cn:core:unit:ms", "kind": "unit"}],
                    "canonical_proposals": [],
                    "canonical_conflicts": [],
                }),
                encoding="utf-8",
            )
            errs = validate_canonical_integrity(
                str(root), str(root / "spec"), require_manifest_schema_registration=False
            )
            e210 = [e for e in errs if e.code == "E210" and e.subcode == "CROSS_ARTIFACT_DRIFT"]
            self.assertTrue(e210, f"Expected E210 CROSS_ARTIFACT_DRIFT, got: {[e.render() for e in errs]}")
            extra_err = next(
                (e for e in e210 if "canonical_refs_used_extra" in e.message), None
            )
            self.assertIsNotNone(extra_err, "Expected canonical_refs_used_extra E210")
            self.assertEqual(extra_err.subcode, "CROSS_ARTIFACT_DRIFT")
            self.assertIn("07_nfrs.json", extra_err.file)
            self.assertEqual(extra_err.jq_path, ".canonical_refs_used")
            self.assertIn("cn:core:unit:ms", extra_err.value)

    def test_e211_carries_subcode_and_value_but_no_file(self):
        """E211 PARTIAL_DRIFT has subcode and value; file is intentionally omitted (cross-file)."""
        with tempfile.TemporaryDirectory() as td:
            root = self._make_root(td)
            self._write_manifest(root, [
                {
                    "id": "cn:core:unit:ms",
                    "kind": "unit",
                    "version": "1.0.0",
                    "status": "active",
                    "lifecycle": {"introduced_at": "2026-01-01T00:00:00Z"},
                },
                {
                    "id": "cn:core:unit:seconds",
                    "kind": "unit",
                    "version": "1.0.0",
                    "status": "active",
                    "lifecycle": {"introduced_at": "2026-01-01T00:00:00Z"},
                },
            ])
            (root / "spec" / "a.json").write_text(
                json.dumps({
                    "latency": "p99",
                    "latency_ref": {"id": "cn:core:unit:ms", "kind": "unit"},
                    "canonical_refs_used": [{"id": "cn:core:unit:ms", "kind": "unit"}],
                    "canonical_proposals": [],
                    "canonical_conflicts": [],
                }),
                encoding="utf-8",
            )
            (root / "spec" / "b.json").write_text(
                json.dumps({
                    "latency": "p99",
                    "latency_ref": {"id": "cn:core:unit:seconds", "kind": "unit"},
                    "canonical_refs_used": [{"id": "cn:core:unit:seconds", "kind": "unit"}],
                    "canonical_proposals": [],
                    "canonical_conflicts": [],
                }),
                encoding="utf-8",
            )
            errs = validate_canonical_integrity(
                str(root), str(root / "spec"), require_manifest_schema_registration=False
            )
            e211 = [e for e in errs if e.code == "E211"]
            self.assertTrue(e211, f"Expected E211, got: {[e.render() for e in errs]}")
            err = e211[0]
            self.assertEqual(err.subcode, "PARTIAL_DRIFT")
            self.assertIsNotNone(err.value)
            self.assertIsInstance(err.value, str)
            # file and jq_path are intentionally None — E211 spans multiple files
            # and multiple fields; no single authoritative path exists.
            self.assertIsNone(err.file, f"E211 file should be None (cross-file), got: {err.file!r}")
            self.assertIsNone(err.jq_path, f"E211 jq_path should be None (cross-file), got: {err.jq_path!r}")


if __name__ == "__main__":
    unittest.main()
