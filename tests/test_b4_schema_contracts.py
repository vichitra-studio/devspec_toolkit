import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

from jsonschema import Draft202012Validator

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from specdev_tools.canonical_autofix import canonical_autofix
from specdev_tools.registry import SchemaRegistry
from specdev_tools.validate import _registry_for, validate_file


class B4SchemaContractsTests(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(__file__).resolve().parents[1]
        self.schema_root = self.repo_root / "schema"

    def test_all_step_schemas_include_b4_top_level_fields(self):
        for path in sorted(self.schema_root.glob("[0-9][0-9]*.schema.json")):
            with path.open("r", encoding="utf-8") as f:
                schema = json.load(f)
            props = schema.get("properties", {})
            self.assertIn("generation_quality", props, msg=path.name)
            self.assertIn("canonical_refs_used", props, msg=path.name)
            self.assertIn("canonical_proposals", props, msg=path.name)
            self.assertIn("canonical_conflicts", props, msg=path.name)

    def test_step_schemas_do_not_use_unregistered_collections_schema_uri(self):
        old_uri = "https://specdev.local/schema/core/collections.schema.json#/"
        for path in sorted(self.schema_root.glob("[0-9][0-9]*.schema.json")):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn(old_uri, text, msg=path.name)

    def test_all_step_schemas_have_at_least_one_canonical_ref_slot(self):
        for path in sorted(self.schema_root.glob("[0-9][0-9]*.schema.json")):
            with path.open("r", encoding="utf-8") as f:
                schema = json.load(f)
            self.assertGreater(_count_canonical_ref_slots(schema), 0, msg=path.name)

    def test_b4_expected_canonical_ref_kinds_exist_per_step(self):
        expected_by_step = {
            "00": {"role", "unit"},
            "01": {"capability", "action", "entity", "role"},
            "02": {"entity", "interface", "event"},
            "02a": {"environment", "policy", "command"},
            "03": {"term", "acronym", "unit"},
            "04": {"capability", "action", "entity", "status"},
            "05": {"interface", "event", "entity", "policy"},
            "06": {"policy", "risk_category", "status"},
            "07": {"metric", "unit", "stage", "environment"},
            "08": {"tag"},
            "09": {"status", "environment", "tech_stack", "dependency"},
            "10": {"policy", "command", "id_pattern"},
            "11": {"risk_category", "policy"},
            "12": {"command", "environment", "role"},
            "13": {"tag", "policy", "id_pattern", "governance_label"},
            "13a": {"risk_category", "tag", "completeness_dimension"},
            "14": {"status", "environment", "metric", "tech_stack", "dependency"},
            "15": {"interface", "command"},
            "16": {"status", "command", "policy", "risk_category"},
        }
        for step, expected_kinds in expected_by_step.items():
            candidates = sorted(self.schema_root.glob(f"{step}_*.schema.json"))
            self.assertTrue(candidates, msg=f"Missing schema for step {step}")
            with candidates[0].open("r", encoding="utf-8") as f:
                schema = json.load(f)
            present = _collect_canonical_ref_kinds(schema)
            missing = sorted(expected_kinds - present)
            self.assertEqual([], missing, msg=f"{candidates[0].name} missing canonical kinds {missing}")

    def test_d022_targeted_schemas_reuse_shared_environment_stage_and_dependency_anchors(self):
        expected_refs = {
            "02a_delivery_baseline.schema.json": {
                "#/$defs/environmentName",
                "#/$defs/environmentConfig",
            },
            "07_nfrs.schema.json": {
                "#/$defs/stageName",
            },
            "09_impl_plan.schema.json": {
                "#/$defs/techStack",
                "#/$defs/dependencyList",
            },
            "14_roadmap.schema.json": {
                "#/$defs/techStack",
                "#/$defs/dependencyObjectList",
            },
            "16_impl_context.schema.json": {
                "#/$defs/environmentName",
            },
        }
        for file_name, refs in expected_refs.items():
            text = (self.schema_root / file_name).read_text(encoding="utf-8")
            for ref in refs:
                self.assertIn(ref, text, msg=f"{file_name} missing shared anchor ref {ref}")

    def test_step_07_requires_metric_unit_and_environment_refs_per_nfr_item(self):
        schema = json.loads((self.schema_root / "07_nfrs.schema.json").read_text(encoding="utf-8"))
        nfr_item = schema["properties"]["nfrs"]["items"]
        required = set(nfr_item.get("required", []))
        self.assertTrue({"metric_ref", "unit_ref", "environment_ref"}.issubset(required))

    def test_canonical_manifest_covers_all_schema_ref_kinds(self):
        manifest = json.loads((self.repo_root / "canon" / "manifest.json").read_text(encoding="utf-8"))
        manifest_kinds = {entry.get("kind") for entry in manifest.get("entries", []) if isinstance(entry, dict)}
        ref_kinds: set[str] = set()
        for path in sorted(self.schema_root.glob("[0-9][0-9]*.schema.json")):
            with path.open("r", encoding="utf-8") as f:
                schema = json.load(f)
            ref_kinds.update(_collect_canonical_ref_kinds(schema))
        missing = sorted(kind for kind in ref_kinds if kind not in manifest_kinds)
        self.assertEqual([], missing, msg=f"Missing canonical bootstrap kinds: {missing}")

    def test_dependency_item_requires_owner_and_note_when_external(self):
        registry = SchemaRegistry(str(self.repo_root))
        core = registry.load("https://specdev.local/schema/core/collections/1")
        dep_item = core["$defs"]["dependencyItem"]
        validator = Draft202012Validator(dep_item, registry=_registry_for(registry))
        errors = list(validator.iter_errors({"type": "external", "id": "dep-a"}))
        self.assertTrue(errors)

    def test_02a_environment_config_rejects_unbounded_nested_values(self):
        registry = SchemaRegistry(str(self.repo_root))
        schema = registry.load("https://specdev.local/schema/02a_delivery_baseline.schema.json")
        validator = Draft202012Validator(schema, registry=_registry_for(registry))
        payload = {
            "id": "delivery-baseline",
            "owner": "api",
            "created_at": "2026-01-01T00:00:00Z",
            "seed_refs": [{"seed_id": "seed-overview"}],
            "environments": {
                "dev": {"nested": {"a": 1}},
                "ci": {"runner": "gha"},
                "staging": {"url": "https://staging.example.com"},
                "prod": {"url": "https://example.com"},
            },
            "ci_gates": ["validate-all"],
            "generation_quality": {"preflight_passed": True},
            "canonical_refs_used": [],
            "canonical_proposals": [],
            "canonical_conflicts": [],
        }
        errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.path))
        self.assertTrue(errors, msg="Nested free-form environment payload unexpectedly passed")

    def test_validate_file_runtime_error_is_not_misclassified_as_ref_resolution(self):
        sample = self.repo_root / "spec" / "05_interface_contracts.json"
        with patch("specdev_tools.validate.Draft202012Validator.iter_errors", side_effect=RuntimeError("boom")):
            errs = validate_file(str(self.repo_root), str(sample))
        self.assertTrue(errs)
        self.assertTrue(any("E521 VALIDATOR_RUNTIME" in e for e in errs))
        self.assertTrue(any("schema_validation_runtime_error" in e for e in errs))
        self.assertFalse(any("schema_reference_resolution_failed" in e for e in errs))

    def test_validate_file_reports_unresolved_ref_deterministically(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "schema").mkdir()
            (root / "spec").mkdir()

            registry_map = {
                "https://specdev.local/schema/test.schema.json": "schema/test.schema.json",
            }
            (root / "tools" / "schema_registry.json").write_text(
                json.dumps(registry_map),
                encoding="utf-8",
            )
            (root / "schema" / "test.schema.json").write_text(
                json.dumps(
                    {
                        "$schema": "https://json-schema.org/draft/2020-12/schema",
                        "$id": "https://specdev.local/schema/test.schema.json",
                        "type": "object",
                        "properties": {
                            "x": {"$ref": "https://specdev.local/schema/missing.schema.json#/$defs/value"}
                        },
                    }
                ),
                encoding="utf-8",
            )
            sample = root / "spec" / "sample.json"
            sample.write_text(
                json.dumps({"$schema": "https://specdev.local/schema/test.schema.json", "x": 1}),
                encoding="utf-8",
            )
            errs = validate_file(str(root), str(sample))
            self.assertTrue(errs)
            self.assertTrue(any("E520 UNRESOLVED_INPUT" in e for e in errs))
            self.assertTrue(any("schema_reference_resolution_failed" in e for e in errs))

    def test_step_14_valid_fixture_still_validates_after_shared_anchor_rollout(self):
        fixture = self.repo_root / "tests" / "fixtures" / "step_14" / "valid_roadmap.json"
        errs = validate_file(str(self.repo_root), str(fixture))
        self.assertEqual([], errs, msg=f"Unexpected validation errors: {errs}")

    def test_step_14_rejects_string_dependencies(self):
        registry = SchemaRegistry(str(self.repo_root))
        schema = registry.load("https://specdev.local/schema/14_roadmap.schema.json")
        validator = Draft202012Validator(schema, registry=_registry_for(registry))

        with (self.repo_root / "tests" / "fixtures" / "step_14" / "valid_roadmap.json").open(
            "r", encoding="utf-8"
        ) as f:
            payload = json.load(f)
        payload.pop("$schema", None)
        payload["dependencies"] = ["dep-one"]

        errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.path))
        self.assertTrue(errors, msg="String dependency payload unexpectedly passed")

    def test_validate_file_enforces_b4_top_level_fields_for_step_artifacts(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "schema").mkdir()
            (root / "spec").mkdir()

            registry_map = {
                "https://specdev.local/schema/01_capabilities.schema.json": "schema/01_capabilities.schema.json",
                "https://specdev.local/schema/core/atoms/1": "schema/atoms.schema.json",
                "https://specdev.local/schema/core/collections/1": "schema/collections.schema.json",
            }
            (root / "tools" / "schema_registry.json").write_text(json.dumps(registry_map), encoding="utf-8")
            (root / "schema" / "01_capabilities.schema.json").write_text(
                (self.schema_root / "01_capabilities.schema.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (root / "schema" / "atoms.schema.json").write_text(
                (self.schema_root / "core" / "atoms.schema.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (root / "schema" / "collections.schema.json").write_text(
                (self.schema_root / "core" / "collections.schema.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            sample = root / "spec" / "01_capabilities.json"
            sample.write_text(
                json.dumps(
                    {
                        "$schema": "https://specdev.local/schema/01_capabilities.schema.json",
                        "id": "caps",
                        "owner": "api",
                        "created_at": "2026-01-01T00:00:00Z",
                        "seed_refs": [{"seed_id": "seed-overview"}],
                        "capabilities": [
                            {
                                "capability_id": "cap-a",
                                "verb": "do",
                                "description": "valid description",
                                "scope": "in",
                                "owner": "api",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            errs = validate_file(str(root), str(sample))
            self.assertTrue(any("missing top-level 'generation_quality'" in e for e in errs))
            self.assertTrue(any("missing top-level 'canonical_refs_used'" in e for e in errs))
            self.assertTrue(any("missing top-level 'canonical_proposals'" in e for e in errs))
            self.assertTrue(any("missing top-level 'canonical_conflicts'" in e for e in errs))

    def test_validate_file_enforces_b4_even_with_nonstandard_filename(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "schema").mkdir()
            (root / "spec").mkdir()

            registry_map = {
                "https://specdev.local/schema/01_capabilities.schema.json": "schema/01_capabilities.schema.json",
                "https://specdev.local/schema/core/atoms/1": "schema/atoms.schema.json",
                "https://specdev.local/schema/core/collections/1": "schema/collections.schema.json",
            }
            (root / "tools" / "schema_registry.json").write_text(json.dumps(registry_map), encoding="utf-8")
            (root / "schema" / "01_capabilities.schema.json").write_text(
                (self.schema_root / "01_capabilities.schema.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (root / "schema" / "atoms.schema.json").write_text(
                (self.schema_root / "core" / "atoms.schema.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (root / "schema" / "collections.schema.json").write_text(
                (self.schema_root / "core" / "collections.schema.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            sample = root / "spec" / "artifact.json"
            sample.write_text(
                json.dumps(
                    {
                        "$schema": "https://specdev.local/schema/01_capabilities.schema.json",
                        "id": "caps",
                        "owner": "api",
                        "created_at": "2026-01-01T00:00:00Z",
                        "seed_refs": [{"seed_id": "seed-overview"}],
                        "capabilities": [
                            {
                                "capability_id": "cap-a",
                                "verb": "do",
                                "description": "valid description",
                                "scope": "in",
                                "owner": "api",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            errs = validate_file(str(root), str(sample))
            self.assertTrue(any("missing top-level 'generation_quality'" in e for e in errs))
            self.assertTrue(any("missing top-level 'canonical_refs_used'" in e for e in errs))

    def test_validate_file_enforces_canonical_refs_used_closure(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "schema").mkdir()
            (root / "spec").mkdir()
            (root / "canon").mkdir()

            registry_map = {
                "https://specdev.local/schema/07_nfrs.schema.json": "schema/07_nfrs.schema.json",
                "https://specdev.local/schema/core/atoms/1": "schema/atoms.schema.json",
                "https://specdev.local/schema/core/collections/1": "schema/collections.schema.json",
            }
            (root / "tools" / "schema_registry.json").write_text(json.dumps(registry_map), encoding="utf-8")
            (root / "schema" / "07_nfrs.schema.json").write_text(
                (self.schema_root / "07_nfrs.schema.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (root / "schema" / "atoms.schema.json").write_text(
                (self.schema_root / "core" / "atoms.schema.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (root / "schema" / "collections.schema.json").write_text(
                (self.schema_root / "core" / "collections.schema.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
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
                                "id": "cn:core:unit:ms",
                                "kind": "unit",
                                "version": "1.0.0",
                                "status": "active",
                                "lifecycle": {"introduced_at": "2026-02-21T00:00:00Z"},
                            },
                            {
                                "id": "cn:core:environment:prod",
                                "kind": "environment",
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

            sample = root / "spec" / "07_nfrs.json"
            sample.write_text(
                json.dumps(
                    {
                        "$schema": "https://specdev.local/schema/07_nfrs.schema.json",
                        "id": "nfrs-test",
                        "owner": "api",
                        "created_at": "2026-01-01T00:00:00Z",
                        "seed_refs": [{"seed_id": "seed-overview"}],
                        "nfrs": [
                            {
                                "nfr_id": "nfr-latency-p95",
                                "category": "latency",
                                "metric": "p95 latency",
                                "target": 100,
                                "unit": "ms",
                                "stage": "prod",
                                "metric_ref": {"id": "cn:core:metric:error-rate", "kind": "metric"},
                                "unit_ref": {"id": "cn:core:unit:ms", "kind": "unit"},
                                "environment_ref": {"id": "cn:core:environment:prod", "kind": "environment"},
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
            errs = validate_file(str(root), str(sample))
            self.assertTrue(any("canonical_refs_used_missing" in e for e in errs))

    def test_step_09_allows_string_dependencies_without_oneof_overlap(self):
        registry = SchemaRegistry(str(self.repo_root))
        schema = registry.load("https://specdev.local/schema/09_impl_plan.schema.json")
        validator = Draft202012Validator(schema, registry=_registry_for(registry))

        with (self.repo_root / "tests" / "fixtures" / "step_09" / "valid_complete.json").open(
            "r", encoding="utf-8"
        ) as f:
            payload = json.load(f)
        payload.pop("$schema", None)
        payload["dependencies"] = ["dep-one"]

        errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.path))
        self.assertEqual([], errors, msg=f"Unexpected errors for string dependencies: {errors}")

    def test_step_16_plan_requires_explicit_status(self):
        registry = SchemaRegistry(str(self.repo_root))
        schema = registry.load("https://specdev.local/schema/16_impl_context.schema.json")
        validator = Draft202012Validator(schema, registry=_registry_for(registry))
        payload = {
            "id": "step-api-core",
            "owner": "api",
            "created_at": "2026-01-01T00:00:00Z",
            "seed_refs": [{"seed_id": "seed-overview"}],
            "plan": {
                "summary": {
                    "functional_summary": "Implement auth core",
                    "scope_in": ["Login"],
                    "scope_out": [],
                    "target_file_patterns": ["src/auth/routes.py"],
                },
                "review_requirements": {"test_commands": ["pytest tests/auth"]},
            },
        }
        errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.path))
        self.assertTrue(any(list(e.path) == ["plan"] and "'status' is a required property" in e.message for e in errors))

    def test_canonical_autofix_does_not_add_schema_invalid_unit_ref_from_units(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "schema").mkdir()
            (root / "spec").mkdir()
            (root / "canon").mkdir()

            registry_map = {
                "https://specdev.local/schema/03_glossary.schema.json": "schema/03_glossary.schema.json",
                "https://specdev.local/schema/core/atoms/1": "schema/atoms.schema.json",
                "https://specdev.local/schema/core/collections/1": "schema/collections.schema.json",
            }
            (root / "tools" / "schema_registry.json").write_text(json.dumps(registry_map), encoding="utf-8")
            (root / "schema" / "03_glossary.schema.json").write_text(
                (self.schema_root / "03_glossary.schema.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (root / "schema" / "atoms.schema.json").write_text(
                (self.schema_root / "core" / "atoms.schema.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (root / "schema" / "collections.schema.json").write_text(
                (self.schema_root / "core" / "collections.schema.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (root / "canon" / "manifest.json").write_text(
                (self.repo_root / "canon" / "manifest.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )

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
                                "units": "ms",
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

            pre = validate_file(str(root), str(sample))
            self.assertEqual([], pre, msg=f"Unexpected pre-autofix errors: {pre}")

            changes = canonical_autofix(str(root), str(root / "spec"), write=True)
            self.assertIn(str(sample), changes)

            payload = json.loads(sample.read_text(encoding="utf-8"))
            self.assertIn("term_ref", payload["terms"][0])
            self.assertNotIn("unit_ref", payload["terms"][0])
            declared_ids = {item["id"] for item in payload["canonical_refs_used"]}
            self.assertIn("cn:core:term:jwt", declared_ids)

            post = validate_file(str(root), str(sample))
            self.assertFalse(any("Additional properties are not allowed ('unit_ref' was unexpected)" in e for e in post))
            self.assertFalse(any("canonical_refs_used_missing" in e for e in post))

    def test_canonical_autofix_avoids_invalid_nfr_risk_category_ref_and_closes_refs_used(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "schema").mkdir()
            (root / "spec").mkdir()
            (root / "canon").mkdir()

            registry_map = {
                "https://specdev.local/schema/07_nfrs.schema.json": "schema/07_nfrs.schema.json",
                "https://specdev.local/schema/core/atoms/1": "schema/atoms.schema.json",
                "https://specdev.local/schema/core/collections/1": "schema/collections.schema.json",
            }
            (root / "tools" / "schema_registry.json").write_text(json.dumps(registry_map), encoding="utf-8")
            (root / "schema" / "07_nfrs.schema.json").write_text(
                (self.schema_root / "07_nfrs.schema.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (root / "schema" / "atoms.schema.json").write_text(
                (self.schema_root / "core" / "atoms.schema.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (root / "schema" / "collections.schema.json").write_text(
                (self.schema_root / "core" / "collections.schema.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (root / "canon" / "manifest.json").write_text(
                (self.repo_root / "canon" / "manifest.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )

            sample = root / "spec" / "07_nfrs.json"
            sample.write_text(
                json.dumps(
                    {
                        "$schema": "https://specdev.local/schema/07_nfrs.schema.json",
                        "id": "nfr-auth",
                        "owner": "api",
                        "created_at": "2026-01-01T00:00:00Z",
                        "seed_refs": [{"seed_id": "seed-overview"}],
                        "nfrs": [
                            {
                                "nfr_id": "nfr-auth-latency",
                                "category": "privacy",
                                "metric": "error_rate",
                                "target": 0.1,
                                "unit": "ms",
                                "stage": "prod",
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

            pre = validate_file(str(root), str(sample))
            self.assertTrue(
                any("'metric_ref' is a required property" in e for e in pre),
                msg=f"Expected missing required canonical refs before autofix, got: {pre}",
            )

            changes = canonical_autofix(str(root), str(root / "spec"), write=True)
            self.assertIn(str(sample), changes)

            payload = json.loads(sample.read_text(encoding="utf-8"))
            self.assertIn("metric_ref", payload["nfrs"][0])
            self.assertIn("unit_ref", payload["nfrs"][0])
            self.assertIn("stage_ref", payload["nfrs"][0])
            self.assertIn("environment_ref", payload["nfrs"][0])
            self.assertNotIn("risk_category_ref", payload["nfrs"][0])
            declared_ids = {item["id"] for item in payload["canonical_refs_used"]}
            self.assertIn("cn:core:metric:error-rate", declared_ids)
            self.assertIn("cn:core:unit:ms", declared_ids)
            self.assertIn("cn:core:stage:prod", declared_ids)
            self.assertIn("cn:core:environment:prod", declared_ids)

            post = validate_file(str(root), str(sample))
            self.assertFalse(any("risk_category_ref' was unexpected" in e for e in post))
            self.assertFalse(any("canonical_refs_used_missing" in e for e in post))

    def test_canonical_autofix_infers_risk_category_ref_where_schema_allows(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "schema").mkdir()
            (root / "spec").mkdir()
            (root / "canon").mkdir()

            registry_map = {
                "https://specdev.local/schema/11_redteam.schema.json": "schema/11_redteam.schema.json",
                "https://specdev.local/schema/core/atoms/1": "schema/atoms.schema.json",
                "https://specdev.local/schema/core/collections/1": "schema/collections.schema.json",
            }
            (root / "tools" / "schema_registry.json").write_text(json.dumps(registry_map), encoding="utf-8")
            (root / "schema" / "11_redteam.schema.json").write_text(
                (self.schema_root / "11_redteam.schema.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (root / "schema" / "atoms.schema.json").write_text(
                (self.schema_root / "core" / "atoms.schema.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (root / "schema" / "collections.schema.json").write_text(
                (self.schema_root / "core" / "collections.schema.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (root / "canon" / "manifest.json").write_text(
                (self.repo_root / "canon" / "manifest.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )

            sample = root / "spec" / "11_redteam.json"
            sample.write_text(
                json.dumps(
                    {
                        "$schema": "https://specdev.local/schema/11_redteam.schema.json",
                        "id": "redteam-auth",
                        "owner": "api",
                        "created_at": "2026-01-01T00:00:00Z",
                        "seed_refs": [{"seed_id": "seed-overview"}],
                        "threats": [
                            {
                                "threat_id": "threat-authz-bypass",
                                "description": "Unauthorized access through missing authorization check.",
                                "vector": "parameter tampering",
                                "target_ids": [{"type": "api", "id": "api-auth"}],
                                "category": "authz",
                                "mitigations": [{"type": "fr", "id": "fr-authz-enforced"}],
                                "severity": "high",
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

            pre = validate_file(str(root), str(sample))
            self.assertEqual([], pre, msg=f"Unexpected pre-autofix errors: {pre}")

            canonical_autofix(str(root), str(root / "spec"), write=True)
            payload = json.loads(sample.read_text(encoding="utf-8"))
            self.assertEqual(
                {"id": "cn:core:risk_category:authz", "kind": "risk_category"},
                payload["threats"][0].get("risk_category_ref"),
            )
            declared_ids = {item["id"] for item in payload["canonical_refs_used"]}
            self.assertIn("cn:core:risk_category:authz", declared_ids)

            post = validate_file(str(root), str(sample))
            self.assertFalse(any("canonical_refs_used_missing" in e for e in post))

    def test_canonical_autofix_skips_mutation_when_schema_unresolved(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "spec").mkdir()
            (root / "canon").mkdir()
            (root / "tools" / "schema_registry.json").write_text("{}", encoding="utf-8")
            (root / "canon" / "manifest.json").write_text(
                (self.repo_root / "canon" / "manifest.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )

            sample = root / "spec" / "artifact.json"
            initial_payload = {
                "$schema": "https://specdev.local/schema/unknown.schema.json",
                "stage": "prod",
                "canonical_refs_used": [],
            }
            sample.write_text(json.dumps(initial_payload, indent=2), encoding="utf-8")

            changes = canonical_autofix(str(root), str(root / "spec"), write=True)
            self.assertIn(str(sample), changes)
            self.assertTrue(any("E520 UNRESOLVED_INPUT" in entry for entry in changes[str(sample)]))
            self.assertTrue(any("schema_not_found" in entry for entry in changes[str(sample)]))

            payload = json.loads(sample.read_text(encoding="utf-8"))
            self.assertEqual(initial_payload, payload)

    def test_canonical_autofix_requires_schema_uri_and_does_not_mutate(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "spec").mkdir()
            (root / "canon").mkdir()
            (root / "tools" / "schema_registry.json").write_text("{}", encoding="utf-8")
            (root / "canon" / "manifest.json").write_text(
                (self.repo_root / "canon" / "manifest.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )

            sample = root / "spec" / "artifact.json"
            initial_payload = {
                "stage": "prod",
                "canonical_refs_used": [],
            }
            sample.write_text(json.dumps(initial_payload, indent=2), encoding="utf-8")

            changes = canonical_autofix(str(root), str(root / "spec"), write=True)
            self.assertIn(str(sample), changes)
            self.assertTrue(any("E520 UNRESOLVED_INPUT" in entry for entry in changes[str(sample)]))
            self.assertTrue(any("missing_schema_uri" in entry for entry in changes[str(sample)]))

            payload = json.loads(sample.read_text(encoding="utf-8"))
            self.assertEqual(initial_payload, payload)


def _count_canonical_ref_slots(obj) -> int:
    count = 0
    if isinstance(obj, dict):
        props = obj.get("properties")
        if isinstance(props, dict):
            for key, value in props.items():
                if (
                    key.endswith("_ref")
                    and isinstance(value, dict)
                    and "canonicalRef" in value.get("$ref", "")
                ):
                    count += 1
        for value in obj.values():
            count += _count_canonical_ref_slots(value)
    elif isinstance(obj, list):
        for value in obj:
            count += _count_canonical_ref_slots(value)
    return count


def _collect_canonical_ref_kinds(obj) -> set[str]:
    kinds: set[str] = set()
    if isinstance(obj, dict):
        props = obj.get("properties")
        if isinstance(props, dict):
            for key, value in props.items():
                if (
                    key.endswith("_ref")
                    and isinstance(value, dict)
                    and "canonicalRef" in value.get("$ref", "")
                ):
                    kinds.add(key[:-4])
                kinds.update(_collect_canonical_ref_kinds(value))
        else:
            for value in obj.values():
                kinds.update(_collect_canonical_ref_kinds(value))
    elif isinstance(obj, list):
        for value in obj:
            kinds.update(_collect_canonical_ref_kinds(value))
    return kinds


if __name__ == "__main__":
    unittest.main()
