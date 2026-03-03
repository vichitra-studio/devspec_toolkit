import json
import tempfile
import unittest
from pathlib import Path

from specdev_tools.generation.prompt_schema_sync import run_prompt_schema_sync


class PromptSchemaSyncTests(unittest.TestCase):
    def test_repo_prompt_schema_sync_is_clean(self):
        repo_root = Path(__file__).resolve().parents[1]
        errs = run_prompt_schema_sync(str(repo_root))
        self.assertEqual([], errs, msg=f"Repo prompt/schema drift detected: {errs}")

    def test_detects_missing_required(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "schema").mkdir()
            (root / "prompts").mkdir()
            (root / "schema" / "00_charter.schema.json").write_text(
                json.dumps({"required": ["id", "seed_refs"]}),
                encoding="utf-8",
            )
            (root / "prompts" / "prompt_00_project_charter.md").write_text(
                (
                    "## Embedded Schema\n"
                    "```json\n"
                    "{\"type\":\"object\",\"properties\":{\"id\":{\"type\":\"string\"}},\"required\": [\"id\"]}\n"
                    "```\n"
                    "## Output Contract\n"
                    "```json\n"
                    "{\"id\":\"charter\"}\n"
                    "```"
                ),
                encoding="utf-8",
            )
            errs = run_prompt_schema_sync(str(root))
            self.assertTrue(any("missing required" in e for e in errs))
            self.assertTrue(any(":2 " in e or ":3 " in e for e in errs))

    def test_invalid_schema_json_is_reported(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "schema").mkdir()
            (root / "prompts").mkdir()
            (root / "schema" / "00_charter.schema.json").write_text("{bad", encoding="utf-8")
            (root / "prompts" / "prompt_00_project_charter.md").write_text(
                "## Embedded Schema\n```json\n{\"type\":\"object\",\"properties\":{},\"required\":[]}\n```",
                encoding="utf-8",
            )
            errs = run_prompt_schema_sync(str(root))
            self.assertTrue(any("invalid_schema" in e for e in errs))

    def test_detects_drift_sensitive_property_shape_mismatch(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "schema").mkdir()
            (root / "prompts").mkdir()
            (root / "schema" / "09_impl_plan.schema.json").write_text(
                json.dumps(
                    {
                        "type": "object",
                        "properties": {
                            "dependencies": {
                                "$ref": "https://specdev.local/schema/core/collections/1#/$defs/dependencyList"
                            }
                        },
                        "required": [],
                    }
                ),
                encoding="utf-8",
            )
            (root / "prompts" / "prompt_09_impl_plan.md").write_text(
                (
                    "## Embedded Schema\n"
                    "```json\n"
                    "{\"type\":\"object\",\"properties\":{\"dependencies\":{\"$ref\":\"https://specdev.local/schema/core/collections/1#stringArray\"}},\"required\":[]}\n"
                    "```\n"
                ),
                encoding="utf-8",
            )
            errs = run_prompt_schema_sync(str(root))
            self.assertTrue(any("property_drift field='dependencies'" in e for e in errs))

    def test_detects_dependency_drift_when_prompt_uses_inline_shape(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "schema").mkdir()
            (root / "prompts").mkdir()
            (root / "schema" / "09_impl_plan.schema.json").write_text(
                json.dumps(
                    {
                        "type": "object",
                        "properties": {
                            "dependencies": {
                                "$ref": "https://specdev.local/schema/core/collections/1#/$defs/dependencyList"
                            }
                        },
                        "required": [],
                    }
                ),
                encoding="utf-8",
            )
            (root / "prompts" / "prompt_09_impl_plan.md").write_text(
                (
                    "## Embedded Schema\n"
                    "```json\n"
                    "{\"type\":\"object\",\"properties\":{\"dependencies\":{\"type\":\"integer\"}},\"required\":[]}\n"
                    "```\n"
                ),
                encoding="utf-8",
            )
            errs = run_prompt_schema_sync(str(root))
            self.assertTrue(any("property_drift field='dependencies'" in e for e in errs))

    def test_detects_trace_property_drift(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "schema").mkdir()
            (root / "prompts").mkdir()
            (root / "schema" / "11_redteam.schema.json").write_text(
                json.dumps(
                    {
                        "type": "object",
                        "properties": {
                            "trace": {
                                "type": "array",
                                "items": {"$ref": "https://specdev.local/schema/core/collections/1#traceRef"},
                            }
                        },
                        "required": [],
                    }
                ),
                encoding="utf-8",
            )
            (root / "prompts" / "prompt_11_redteam.md").write_text(
                (
                    "## Embedded Schema\n"
                    "```json\n"
                    "{\"type\":\"object\",\"properties\":{\"trace\":{\"$ref\":\"https://specdev.local/schema/core/collections/1#traceRef\"}},\"required\":[]}\n"
                    "```\n"
                ),
                encoding="utf-8",
            )
            errs = run_prompt_schema_sync(str(root))
            self.assertTrue(any("property_drift field='trace'" in e for e in errs))

    def test_detects_missing_metadata_property_when_not_declared_anywhere(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "schema").mkdir()
            (root / "prompts").mkdir()
            (root / "schema" / "00_charter.schema.json").write_text(
                json.dumps(
                    {
                        "type": "object",
                        "properties": {
                            "generation_quality": {
                                "$ref": "https://specdev.local/schema/core/collections/1#/$defs/generationQuality"
                            }
                        },
                        "required": [],
                    }
                ),
                encoding="utf-8",
            )
            (root / "prompts" / "prompt_00_project_charter.md").write_text(
                (
                    "## Embedded Schema\n"
                    "```json\n"
                    "{\"type\":\"object\",\"properties\":{},\"required\":[]}\n"
                    "```\n"
                ),
                encoding="utf-8",
            )
            errs = run_prompt_schema_sync(str(root))
            self.assertTrue(any("missing property field='generation_quality'" in e for e in errs))

    def test_detects_missing_required_nested_canonical_refs(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "schema").mkdir()
            (root / "prompts").mkdir()
            (root / "schema" / "07_nfrs.schema.json").write_text(
                json.dumps(
                    {
                        "type": "object",
                        "properties": {
                            "nfrs": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "metric_ref": {
                                            "$ref": "https://specdev.local/schema/core/collections/1#/$defs/canonicalRef"
                                        },
                                        "unit_ref": {
                                            "$ref": "https://specdev.local/schema/core/collections/1#/$defs/canonicalRef"
                                        },
                                    },
                                    "required": ["metric_ref", "unit_ref"],
                                },
                            }
                        },
                        "required": [],
                    }
                ),
                encoding="utf-8",
            )
            (root / "prompts" / "prompt_07_nfrs.md").write_text(
                (
                    "## Embedded Schema\n"
                    "```json\n"
                    "{\"type\":\"object\",\"properties\":{\"nfrs\":{\"type\":\"array\",\"items\":{\"type\":\"object\",\"properties\":{\"metric_ref\":{\"$ref\":\"https://specdev.local/schema/core/collections/1#/$defs/canonicalRef\"},\"unit_ref\":{\"$ref\":\"https://specdev.local/schema/core/collections/1#/$defs/canonicalRef\"}},\"required\":[]}}},\"required\":[]}\n"
                    "```\n"
                ),
                encoding="utf-8",
            )
            errs = run_prompt_schema_sync(str(root))
            self.assertTrue(any("missing_required_canonical_refs" in e for e in errs))

    def test_metadata_text_mention_does_not_bypass_missing_property_check(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "schema").mkdir()
            (root / "prompts").mkdir()
            (root / "schema" / "00_charter.schema.json").write_text(
                json.dumps(
                    {
                        "type": "object",
                        "properties": {
                            "generation_quality": {
                                "$ref": "https://specdev.local/schema/core/collections/1#/$defs/generationQuality"
                            }
                        },
                        "required": [],
                    }
                ),
                encoding="utf-8",
            )
            (root / "prompts" / "prompt_00_project_charter.md").write_text(
                (
                    "## Embedded Schema\n"
                    "```json\n"
                    "{\"type\":\"object\",\"properties\":{},\"required\":[]}\n"
                    "```\n\n"
                    "## Metadata Contract\n"
                    "- Include `generation_quality` in the output artifact.\n"
                ),
                encoding="utf-8",
            )
            errs = run_prompt_schema_sync(str(root))
            self.assertTrue(any("missing property field='generation_quality'" in e for e in errs))

    def test_detects_output_contract_schema_violation(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "schema").mkdir()
            (root / "prompts").mkdir()
            (root / "schema" / "00_charter.schema.json").write_text(
                json.dumps(
                    {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string", "pattern": "^[a-z0-9-]+$"},
                        },
                        "required": ["id"],
                    }
                ),
                encoding="utf-8",
            )
            (root / "prompts" / "prompt_00_project_charter.md").write_text(
                (
                    "## Embedded Schema\n"
                    "```json\n"
                    "{\"type\":\"object\",\"properties\":{\"id\":{\"type\":\"string\",\"pattern\":\"^[a-z0-9-]+$\"}},\"required\":[\"id\"]}\n"
                    "```\n\n"
                    "# Output Contract\n"
                    "```json\n"
                    "{\"id\":\"INVALID_ID\"}\n"
                    "```\n\n"
                    "## Metadata Contract\n"
                ),
                encoding="utf-8",
            )
            errs = run_prompt_schema_sync(str(root))
            self.assertTrue(any("output_contract_schema_error" in e for e in errs))

    def test_detects_output_contract_schema_uri_mismatch(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "schema").mkdir()
            (root / "prompts").mkdir()
            (root / "tools").mkdir()
            schema_uri = "https://specdev.local/schema/00_charter.schema.json"
            (root / "tools" / "schema_registry.json").write_text(
                json.dumps({schema_uri: "schema/00_charter.schema.json"}),
                encoding="utf-8",
            )
            (root / "schema" / "00_charter.schema.json").write_text(
                json.dumps(
                    {
                        "$schema": "https://json-schema.org/draft/2020-12/schema",
                        "$id": schema_uri,
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                        },
                        "required": ["id"],
                    }
                ),
                encoding="utf-8",
            )
            (root / "prompts" / "prompt_00_project_charter.md").write_text(
                (
                    "## Embedded Schema\n"
                    "```json\n"
                    "{\"type\":\"object\",\"properties\":{\"id\":{\"type\":\"string\"}},\"required\":[\"id\"]}\n"
                    "```\n\n"
                    "# Output Contract\n"
                    "```json\n"
                    "{\"$schema\":\"https://specdev.local/schema/wrong.schema.json\",\"id\":\"charter\"}\n"
                    "```\n\n"
                    "## Metadata Contract\n"
                ),
                encoding="utf-8",
            )
            errs = run_prompt_schema_sync(str(root))
            self.assertTrue(any("output_contract_schema_uri_mismatch" in e for e in errs))

    def test_detects_invalid_latest_output_contract_block(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "schema").mkdir()
            (root / "prompts").mkdir()
            (root / "tools").mkdir()
            schema_uri = "https://specdev.local/schema/00_charter.schema.json"
            (root / "tools" / "schema_registry.json").write_text(
                json.dumps({schema_uri: "schema/00_charter.schema.json"}),
                encoding="utf-8",
            )
            (root / "schema" / "00_charter.schema.json").write_text(
                json.dumps(
                    {
                        "$schema": "https://json-schema.org/draft/2020-12/schema",
                        "$id": schema_uri,
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                        },
                        "required": ["id"],
                    }
                ),
                encoding="utf-8",
            )
            (root / "prompts" / "prompt_00_project_charter.md").write_text(
                (
                    "## Embedded Schema\n"
                    "```json\n"
                    "{\"type\":\"object\",\"properties\":{\"id\":{\"type\":\"string\"}},\"required\":[\"id\"]}\n"
                    "```\n\n"
                    "# Output Contract\n"
                    "```json\n"
                    "{\"$schema\":\"https://specdev.local/schema/00_charter.schema.json\",\"id\":\"charter\"}\n"
                    "```\n"
                    "```json\n"
                    "{\"$schema\":\"https://specdev.local/schema/00_charter.schema.json\",\"id\":\n"
                    "```\n\n"
                    "## Metadata Contract\n"
                ),
                encoding="utf-8",
            )
            errs = run_prompt_schema_sync(str(root))
            self.assertTrue(any("invalid output contract JSON block" in e for e in errs))

    def test_validates_output_contract_for_16a_using_step_16_schema(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "schema").mkdir()
            (root / "prompts").mkdir()
            (root / "schema" / "16_impl_context.schema.json").write_text(
                json.dumps(
                    {
                        "type": "object",
                        "properties": {
                            "plan": {
                                "type": "object",
                                "properties": {"status": {"type": "string"}},
                                "required": ["status"],
                            }
                        },
                        "required": ["plan"],
                    }
                ),
                encoding="utf-8",
            )
            (root / "prompts" / "prompt_16a_impl_planner.md").write_text(
                (
                    "## Embedded Schema\n"
                    "```json\n"
                    "{\"type\":\"object\",\"properties\":{\"plan\":{\"type\":\"object\",\"properties\":{\"status\":{\"type\":\"string\"}},\"required\":[\"status\"]}},\"required\":[\"plan\"]}\n"
                    "```\n\n"
                    "# Output Contract\n"
                    "```json\n"
                    "{\"plan\":{}}\n"
                    "```\n\n"
                    "## Metadata Contract\n"
                ),
                encoding="utf-8",
            )
            errs = run_prompt_schema_sync(str(root))
            self.assertTrue(any("output_contract_schema_error" in e for e in errs))

    def test_prompt_sync_handles_malformed_registry_map_shape_without_crash(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "schema").mkdir()
            (root / "prompts").mkdir()
            (root / "tools" / "schema_registry.json").write_text("[]", encoding="utf-8")
            (root / "schema" / "00_charter.schema.json").write_text(
                json.dumps(
                    {
                        "type": "object",
                        "properties": {"id": {"type": "string"}},
                        "required": ["id"],
                    }
                ),
                encoding="utf-8",
            )
            (root / "prompts" / "prompt_00_project_charter.md").write_text(
                (
                    "## Embedded Schema\n"
                    "```json\n"
                    "{\"type\":\"object\",\"properties\":{\"id\":{\"type\":\"string\"}},\"required\":[\"id\"]}\n"
                    "```\n\n"
                    "# Output Contract\n"
                    "```json\n"
                    "{\"id\":\"charter\"}\n"
                    "```\n\n"
                    "## Metadata Contract\n"
                ),
                encoding="utf-8",
            )
            errs = run_prompt_schema_sync(str(root))
            self.assertIsInstance(errs, list)
            self.assertTrue(any("E520 UNRESOLVED_INPUT" in e for e in errs))
            self.assertTrue(any("schema_registry_bootstrap_failed" in e for e in errs))

    def test_accepts_schema_reference_without_embedded_schema_block(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "schema").mkdir()
            (root / "prompts").mkdir()
            schema_uri = "https://specdev.local/schema/00_charter.schema.json"
            (root / "tools" / "schema_registry.json").write_text(
                json.dumps({schema_uri: "schema/00_charter.schema.json"}),
                encoding="utf-8",
            )
            (root / "schema" / "00_charter.schema.json").write_text(
                json.dumps(
                    {
                        "$schema": "https://json-schema.org/draft/2020-12/schema",
                        "$id": schema_uri,
                        "type": "object",
                        "properties": {"id": {"type": "string"}},
                        "required": ["id"],
                    }
                ),
                encoding="utf-8",
            )
            (root / "prompts" / "prompt_00_project_charter.md").write_text(
                (
                    "# Schema Reference\n"
                    "- Schema URI: https://specdev.local/schema/00_charter.schema.json\n"
                    "- Schema File: schema/00_charter.schema.json\n"
                    "- Schema Registry: tools/schema_registry.json\n\n"
                    "# Output Contract\n"
                    "```json\n"
                    "{\"$schema\":\"https://specdev.local/schema/00_charter.schema.json\",\"id\":\"charter\"}\n"
                    "```\n\n"
                    "## Metadata Contract\n"
                ),
                encoding="utf-8",
            )
            errs = run_prompt_schema_sync(str(root))
            self.assertEqual([], errs, msg=f"unexpected errors: {errs}")

    def test_detects_schema_reference_uri_mismatch_without_embedded_schema(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "schema").mkdir()
            (root / "prompts").mkdir()
            schema_uri = "https://specdev.local/schema/00_charter.schema.json"
            (root / "tools" / "schema_registry.json").write_text(
                json.dumps({schema_uri: "schema/00_charter.schema.json"}),
                encoding="utf-8",
            )
            (root / "schema" / "00_charter.schema.json").write_text(
                json.dumps(
                    {
                        "$schema": "https://json-schema.org/draft/2020-12/schema",
                        "$id": schema_uri,
                        "type": "object",
                        "properties": {"id": {"type": "string"}},
                        "required": ["id"],
                    }
                ),
                encoding="utf-8",
            )
            (root / "prompts" / "prompt_00_project_charter.md").write_text(
                (
                    "# Schema Reference\n"
                    "- Schema URI: https://specdev.local/schema/wrong.schema.json\n"
                    "- Schema File: schema/00_charter.schema.json\n"
                    "- Schema Registry: tools/schema_registry.json\n\n"
                    "# Output Contract\n"
                    "```json\n"
                    "{\"$schema\":\"https://specdev.local/schema/00_charter.schema.json\",\"id\":\"charter\"}\n"
                    "```\n\n"
                    "## Metadata Contract\n"
                ),
                encoding="utf-8",
            )
            errs = run_prompt_schema_sync(str(root))
            self.assertTrue(any("schema_uri_mismatch" in e for e in errs))

    def test_step_from_prompt_name_returns_substep_id(self):
        """_step_from_prompt_name should return '16a', not '16'."""
        from specdev_tools.generation.prompt_schema_sync import _step_from_prompt_name
        self.assertEqual(_step_from_prompt_name("prompt_16a_impl_planner.md"), "16a")
        self.assertEqual(_step_from_prompt_name("prompt_16b_impl_coder.md"), "16b")
        self.assertEqual(_step_from_prompt_name("prompt_16c_impl_reviewer.md"), "16c")
        self.assertEqual(_step_from_prompt_name("prompt_04_functional_requirements.md"), "04")
        self.assertIsNone(_step_from_prompt_name("not_a_prompt.md"))

    def test_substep_drift_detection_w580(self):
        """W580: sub-step prompt with keys from another sub-step's domain triggers warning."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "schema").mkdir()
            (root / "prompts").mkdir()
            # Create Step 16 schema (base schema used for all sub-steps)
            (root / "schema" / "16_impl_context.schema.json").write_text(
                json.dumps(
                    {
                        "type": "object",
                        "properties": {
                            "plan": {"type": "object"},
                            "execution": {"type": "object"},
                            "review": {"type": "object"},
                        },
                        "required": [],
                    }
                ),
                encoding="utf-8",
            )
            # Create a 16a prompt whose output contract contains "review" (a 16c key)
            (root / "prompts" / "prompt_16a_impl_planner.md").write_text(
                (
                    "# Output Contract\n"
                    "```json\n"
                    "{\"plan\": {\"status\": \"active\"}, \"review\": {\"verdict\": \"pending\"}}\n"
                    "```\n"
                ),
                encoding="utf-8",
            )
            errs = run_prompt_schema_sync(str(root))
            w580_errs = [e for e in errs if "W580" in e]
            self.assertTrue(
                len(w580_errs) > 0,
                f"Expected W580 SUBSTEP_DRIFT warning. Got: {errs}"
            )
            self.assertTrue(
                any("review" in e for e in w580_errs),
                f"Expected W580 to mention 'review' as foreign key. Got: {w580_errs}"
            )

    def test_substep_no_drift_when_keys_match_domain(self):
        """No W580 when sub-step output contract only contains its own domain keys."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "schema").mkdir()
            (root / "prompts").mkdir()
            (root / "schema" / "16_impl_context.schema.json").write_text(
                json.dumps(
                    {
                        "type": "object",
                        "properties": {
                            "plan": {"type": "object"},
                        },
                        "required": [],
                    }
                ),
                encoding="utf-8",
            )
            # 16a prompt with only 16a domain keys
            (root / "prompts" / "prompt_16a_impl_planner.md").write_text(
                (
                    "# Output Contract\n"
                    "```json\n"
                    "{\"plan\": {\"status\": \"active\"}}\n"
                    "```\n"
                ),
                encoding="utf-8",
            )
            errs = run_prompt_schema_sync(str(root))
            w580_errs = [e for e in errs if "W580" in e]
            self.assertEqual(
                w580_errs, [],
                f"Did not expect W580 errors. Got: {w580_errs}"
            )


    def test_substep_upstream_keys_no_drift(self):
        """No W580 when sub-step output contract contains upstream domain keys."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "schema").mkdir()
            (root / "prompts").mkdir()
            (root / "schema" / "16_impl_context.schema.json").write_text(
                json.dumps(
                    {
                        "type": "object",
                        "properties": {
                            "plan": {"type": "object"},
                            "execution": {"type": "object"},
                            "review": {"type": "object"},
                        },
                        "required": [],
                    }
                ),
                encoding="utf-8",
            )
            # 16b prompt with "plan" (upstream from 16a) — should be allowed
            (root / "prompts" / "prompt_16b_impl_coder.md").write_text(
                (
                    "# Output Contract\n"
                    "```json\n"
                    '{"plan": {"status": "active"}, "execution": {"files": []}}\n'
                    "```\n"
                ),
                encoding="utf-8",
            )
            errs = run_prompt_schema_sync(str(root))
            w580_errs = [e for e in errs if "W580" in e]
            self.assertEqual(
                w580_errs, [],
                f"Upstream keys should not trigger W580. Got: {w580_errs}"
            )


if __name__ == "__main__":
    unittest.main()
