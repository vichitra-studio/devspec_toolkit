import json
import tempfile
import unittest
from pathlib import Path

from specdev_tools.generation.prompt_schema_sync import run_prompt_schema_sync
from specdev_tools.core.errors import render_errors


class PromptSchemaSyncTests(unittest.TestCase):
    def test_repo_prompt_schema_sync_is_clean(self):
        repo_root = Path(__file__).resolve().parents[3]
        errs = run_prompt_schema_sync(str(repo_root))
        self.assertEqual([], errs, msg=f"Repo prompt/schema drift detected: {errs}")

    def test_detects_missing_required(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "schema").mkdir()
            (root / "prompts").mkdir()
            (root / "schema" / "00_charter.schema.json").write_text(
                json.dumps({"required": ["id", "owner"]}),
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
            self.assertTrue(any("missing required" in e for e in render_errors(errs)))
            self.assertTrue(any(":2 " in e or ":3 " in e for e in render_errors(errs)))

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
            self.assertTrue(any("invalid_schema" in e for e in render_errors(errs)))

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
                                "$ref": "vc:core:collections#/$defs/dependencyList"
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
                    "{\"type\":\"object\",\"properties\":{\"dependencies\":{\"$ref\":\"vc:core:collections#stringArray\"}},\"required\":[]}\n"
                    "```\n"
                ),
                encoding="utf-8",
            )
            errs = run_prompt_schema_sync(str(root))
            self.assertTrue(any("property_drift field='dependencies'" in e for e in render_errors(errs)))

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
                                "$ref": "vc:core:collections#/$defs/dependencyList"
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
            self.assertTrue(any("property_drift field='dependencies'" in e for e in render_errors(errs)))

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
                                "items": {"$ref": "vc:core:collections#traceRef"},
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
                    "{\"type\":\"object\",\"properties\":{\"trace\":{\"$ref\":\"vc:core:collections#traceRef\"}},\"required\":[]}\n"
                    "```\n"
                ),
                encoding="utf-8",
            )
            errs = run_prompt_schema_sync(str(root))
            self.assertTrue(any("property_drift field='trace'" in e for e in render_errors(errs)))

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
                            "canonical_refs_used": {
                                "$ref": "vc:core:collections#/$defs/canonicalRefArray"
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
            self.assertTrue(any("missing property field='canonical_refs_used'" in e for e in render_errors(errs)))

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
                                            "$ref": "vc:core:collections#/$defs/canonicalRef"
                                        },
                                        "unit_ref": {
                                            "$ref": "vc:core:collections#/$defs/canonicalRef"
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
                    "{\"type\":\"object\",\"properties\":{\"nfrs\":{\"type\":\"array\",\"items\":{\"type\":\"object\",\"properties\":{\"metric_ref\":{\"$ref\":\"vc:core:collections#/$defs/canonicalRef\"},\"unit_ref\":{\"$ref\":\"vc:core:collections#/$defs/canonicalRef\"}},\"required\":[]}}},\"required\":[]}\n"
                    "```\n"
                ),
                encoding="utf-8",
            )
            errs = run_prompt_schema_sync(str(root))
            self.assertTrue(any("missing_required_canonical_refs" in e for e in render_errors(errs)))

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
                            "canonical_refs_used": {
                                "$ref": "vc:core:collections#/$defs/canonicalRefArray"
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
                    "- Include `canonical_refs_used` in the output artifact.\n"
                ),
                encoding="utf-8",
            )
            errs = run_prompt_schema_sync(str(root))
            self.assertTrue(any("missing property field='canonical_refs_used'" in e for e in render_errors(errs)))

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
            self.assertTrue(any("output_contract_schema_error" in e for e in render_errors(errs)))

    def test_detects_output_contract_schema_uri_mismatch(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "schema").mkdir()
            (root / "prompts").mkdir()
            (root / "tools").mkdir()
            schema_uri = "vc:00-charter"
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
                    "{\"$schema\":\"vc:wrong\",\"id\":\"charter\"}\n"
                    "```\n\n"
                    "## Metadata Contract\n"
                ),
                encoding="utf-8",
            )
            errs = run_prompt_schema_sync(str(root))
            self.assertTrue(any("output_contract_schema_uri_mismatch" in e for e in render_errors(errs)))

    def test_detects_invalid_latest_output_contract_block(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "schema").mkdir()
            (root / "prompts").mkdir()
            (root / "tools").mkdir()
            schema_uri = "vc:00-charter"
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
                    "{\"$schema\":\"vc:00-charter\",\"id\":\"charter\"}\n"
                    "```\n"
                    "```json\n"
                    "{\"$schema\":\"vc:00-charter\",\"id\":\n"
                    "```\n\n"
                    "## Metadata Contract\n"
                ),
                encoding="utf-8",
            )
            errs = run_prompt_schema_sync(str(root))
            self.assertTrue(any("invalid output contract JSON block" in e for e in render_errors(errs)))

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
            self.assertTrue(any("output_contract_schema_error" in e for e in render_errors(errs)))

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
            self.assertTrue(any("E520 UNRESOLVED_INPUT" in e for e in render_errors(errs)))
            self.assertTrue(any("schema_registry_bootstrap_failed" in e for e in render_errors(errs)))

    def test_accepts_schema_reference_without_embedded_schema_block(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "schema").mkdir()
            (root / "prompts").mkdir()
            schema_uri = "vc:00-charter"
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
                    "- Schema URI: vc:00-charter\n"
                    "- Schema File: schema/00_charter.schema.json\n"
                    "- Schema Registry: tools/schema_registry.json\n\n"
                    "# Output Contract\n"
                    "```json\n"
                    "{\"$schema\":\"vc:00-charter\",\"id\":\"charter\"}\n"
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
            schema_uri = "vc:00-charter"
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
                    "- Schema URI: vc:wrong\n"
                    "- Schema File: schema/00_charter.schema.json\n"
                    "- Schema Registry: tools/schema_registry.json\n\n"
                    "# Output Contract\n"
                    "```json\n"
                    "{\"$schema\":\"vc:00-charter\",\"id\":\"charter\"}\n"
                    "```\n\n"
                    "## Metadata Contract\n"
                ),
                encoding="utf-8",
            )
            errs = run_prompt_schema_sync(str(root))
            self.assertTrue(any("schema_uri_mismatch" in e for e in render_errors(errs)))

    def test_step_from_prompt_name_returns_substep_id(self):
        """_step_from_prompt_name should return '16a', not '16'."""
        from specdev_tools.generation.prompt_schema_sync import _step_from_prompt_name
        self.assertEqual(_step_from_prompt_name("prompt_16a_impl_planner.md"), "16a")
        self.assertEqual(_step_from_prompt_name("prompt_16b_impl_coder.md"), "16b")
        self.assertEqual(_step_from_prompt_name("prompt_16c_impl_reviewer.md"), "16c")
        self.assertEqual(_step_from_prompt_name("prompt_04_functional_requirements.md"), "04")
        self.assertIsNone(_step_from_prompt_name("not_a_prompt.md"))

    def test_substep_drift_16a_emitting_anchor_milestone_index_triggers_w580(self):
        """W580: a 16a prompt that accidentally emits the anchor-only field
        `milestone_index` should fire SUBSTEP_DRIFT, catching the mistake before
        the anchor/milestone contract drifts silently.
        """
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "schema").mkdir()
            (root / "prompts").mkdir()
            (root / "schema" / "16_impl_context.schema.json").write_text(
                json.dumps({
                    "type": "object",
                    "properties": {
                        "plan": {"type": "object"},
                        "milestone_index": {"type": "array"},
                    },
                    "required": [],
                }),
                encoding="utf-8",
            )
            (root / "prompts" / "prompt_16a_impl_planner.md").write_text(
                (
                    "# Output Contract\n"
                    "```json\n"
                    "{\"plan\": {\"status\": \"active\"}, "
                    "\"milestone_index\": [{\"milestone_id\": \"ms-x\"}]}\n"
                    "```\n"
                ),
                encoding="utf-8",
            )
            errs = run_prompt_schema_sync(str(root))
            w580 = [e for e in render_errors(errs) if "W580" in e]
            self.assertTrue(
                any("milestone_index" in e and "16anchor" in e for e in w580),
                f"Expected W580 citing 'milestone_index' as a 16anchor-domain "
                f"key leaking into 16a. Got: {w580}",
            )

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
            w580_errs = [e for e in render_errors(errs) if "W580" in e]
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
            w580_errs = [e for e in render_errors(errs) if "W580" in e]
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
            w580_errs = [e for e in render_errors(errs) if "W580" in e]
            self.assertEqual(
                w580_errs, [],
                f"Upstream keys should not trigger W580. Got: {w580_errs}"
            )

    def test_prompt_step_override_files_exist(self):
        """Every filename key in _PROMPT_STEP_OVERRIDE must refer to a real prompt on disk.

        The override maps prompts that would resolve to the wrong schema via the
        default filename-prefix rule. If someone renames the underlying prompt
        file without updating the override, the mapping silently stops applying
        and the validator picks the wrong schema, producing a false E310
        PROMPT_SCHEMA_DRIFT on the next run. This test pins the reality check
        so the drift is caught at commit time.
        """
        from specdev_tools.generation.prompt_schema_sync import _PROMPT_STEP_OVERRIDE
        repo_root = Path(__file__).resolve().parents[3]
        prompts_dir = repo_root / "prompts"
        missing = [
            name for name in _PROMPT_STEP_OVERRIDE
            if not (prompts_dir / name).is_file()
        ]
        self.assertEqual(
            missing, [],
            f"_PROMPT_STEP_OVERRIDE references prompts that do not exist: {missing}. "
            f"Either rename the prompt back, or update the override dict.",
        )

    def test_anchor_prompt_validates_against_vc_16_anchor_schema(self):
        """Regression test: prompt_16_impl_context.md must validate against vc:16-anchor,
        not vc:16-impl-context, after the anchor/milestone-plan schema split.

        This is the load-bearing contract of _PROMPT_STEP_OVERRIDE. A rename of
        the prompt file (or removal of the override entry) would silently route
        the anchor prompt's Output Contract through the milestone-plan schema
        and produce either a false pass or a false E310 drift signal.
        """
        from specdev_tools.generation.prompt_schema_sync import _PROMPT_STEP_OVERRIDE
        self.assertEqual(
            _PROMPT_STEP_OVERRIDE.get("prompt_16_impl_context.md"),
            "16anchor",
            "prompt_16_impl_context.md must map to '16anchor' step key so its "
            "Output Contract is validated against schema/16_anchor.schema.json",
        )
        # And the repo-level sync must be clean — this is the end-to-end proof
        # that the override is working.
        repo_root = Path(__file__).resolve().parents[3]
        errs = run_prompt_schema_sync(str(repo_root))
        e310 = [e for e in render_errors(errs) if "E310" in e and "prompt_16_impl_context" in e]
        self.assertEqual(
            e310, [],
            f"prompt_16_impl_context.md must not fire E310 PROMPT_SCHEMA_DRIFT. Got: {e310}",
        )


if __name__ == "__main__":
    unittest.main()
