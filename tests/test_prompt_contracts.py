import re
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from specdev_tools.core.registry import SchemaRegistry
from specdev_tools.validation.validate import _registry_for


class PromptContractsTests(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(__file__).resolve().parents[1]
        self.prompt_dir = Path(__file__).resolve().parents[1] / "prompts"

    def test_output_contract_examples_include_b4_fields(self):
        for path in sorted(self.prompt_dir.glob("prompt_*.md")):
            text = path.read_text(encoding="utf-8")
            if "# Output Contract" not in text or "## B4 Metadata Contract" not in text:
                continue
            section = text.split("# Output Contract", 1)[1].split("## B4 Metadata Contract", 1)[0]
            blocks = re.findall(r"```json\s*(.*?)\s*```", section, flags=re.DOTALL)
            self.assertTrue(blocks, msg=path.name)
            parsed = []
            for idx, block in enumerate(blocks):
                try:
                    parsed.append(json.loads(block))
                except json.JSONDecodeError as exc:
                    self.fail(f"{path.name} output-contract block {idx} invalid JSON: {exc}")
            output_payload = parsed[-1]
            self.assertIsInstance(output_payload, dict, msg=path.name)
            self.assertIn("seed_refs", output_payload, msg=path.name)
            self.assertIn("generation_quality", output_payload, msg=path.name)
            self.assertIn("canonical_refs_used", output_payload, msg=path.name)
            self.assertIn("canonical_proposals", output_payload, msg=path.name)
            self.assertIn("canonical_conflicts", output_payload, msg=path.name)

    def test_output_contract_examples_validate_against_step_schemas(self):
        registry = SchemaRegistry(str(self.repo_root))
        jsonschema_registry = _registry_for(registry)
        step_to_schema: dict[str, str] = {}
        for uri in registry.store:
            match = re.search(r"/schema/(\d{2}[a-z]?)_.*\.schema\.json$", uri)
            if match:
                step_to_schema[match.group(1)] = uri

        for path in sorted(self.prompt_dir.glob("prompt_*.md")):
            name_match = re.match(r"prompt_(\d{2}[a-z]?)_", path.name)
            if not name_match:
                continue
            step = name_match.group(1)
            schema_uri = step_to_schema.get(step)
            if step in {"16a", "16b", "16c"}:
                schema_uri = step_to_schema.get("16")
            if not schema_uri:
                continue

            text = path.read_text(encoding="utf-8")
            if "# Output Contract" not in text or "## B4 Metadata Contract" not in text:
                continue
            section = text.split("# Output Contract", 1)[1].split("## B4 Metadata Contract", 1)[0]
            blocks = re.findall(r"```json\s*(.*?)\s*```", section, flags=re.DOTALL)
            self.assertTrue(blocks, msg=f"{path.name} missing output-contract JSON block")

            payload = json.loads(blocks[-1])
            self.assertIsInstance(payload, dict, msg=f"{path.name} output payload must be object")
            payload_no_schema = dict(payload)
            payload_no_schema.pop("$schema", None)

            schema = registry.load(schema_uri)
            validator = Draft202012Validator(
                schema,
                registry=jsonschema_registry,
                format_checker=Draft202012Validator.FORMAT_CHECKER,
            )
            errors = sorted(validator.iter_errors(payload_no_schema), key=lambda e: list(e.path))
            self.assertEqual(
                [],
                errors,
                msg=(
                    f"{path.name} output-contract example fails schema validation: "
                    f"{errors[0].json_path if errors else '$'}: {errors[0].message if errors else ''}"
                ),
            )

    def test_no_legacy_completeness_threshold_phrasing_remains(self):
        legacy_patterns = (
            r"completeness\s*<\s*0\.9",
            r"private completeness score",
            r"If < 0\.5",
        )
        for path in sorted(self.prompt_dir.glob("prompt_*.md")):
            text = path.read_text(encoding="utf-8")
            for pattern in legacy_patterns:
                self.assertIsNone(re.search(pattern, text), msg=f"{path.name} matched {pattern}")

    def test_output_rules_require_disk_first_artifact_write(self):
        disk_first_patterns = (
            r"write the final json artifact directly to disk",
            r"write/?update.*artifact file",
        )
        for path in sorted(self.prompt_dir.glob("prompt_*.md")):
            text = path.read_text(encoding="utf-8")
            if "# Output Rules" not in text and "## Output Rules" not in text:
                continue
            section = re.split(r"^#+\s*Output Rules\s*$", text, flags=re.MULTILINE)
            if len(section) < 2:
                continue
            output_rules = section[1].split("# Schema Reference", 1)[0]
            self.assertTrue(
                any(re.search(pattern, output_rules, flags=re.IGNORECASE) for pattern in disk_first_patterns),
                msg=f"{path.name} missing disk-first output guidance",
            )

    def test_output_rules_do_not_require_inline_json_chat_output(self):
        forbidden_patterns = (
            r"NO\s+prose\s+before\s+or\s+after\s+the\s+JSON",
            r"return\s+only\s+valid\s+json",
            r"output\s+only\s+json",
            r"return\s+fenced\s+json",
        )
        for path in sorted(self.prompt_dir.glob("prompt_*.md")):
            text = path.read_text(encoding="utf-8")
            if "# Output Rules" not in text and "## Output Rules" not in text:
                continue
            section = re.split(r"^#+\s*Output Rules\s*$", text, flags=re.MULTILINE)
            if len(section) < 2:
                continue
            output_rules = section[1].split("# Schema Reference", 1)[0]
            for pattern in forbidden_patterns:
                self.assertIsNone(
                    re.search(pattern, output_rules, flags=re.IGNORECASE),
                    msg=f"{path.name} matched forbidden inline-output pattern: {pattern}",
                )

    def test_all_prompts_include_hardening_protocol_block(self):
        required_lines = (
            "## Hardening Protocol",
            "- fail-closed preflight: verify required fields, allowed enums, referenced IDs, and command/tool existence before emitting JSON.",
            "- No-Invention Rules: do not invent IDs, enums, commands, files, metrics, stages, or canonical mappings that are not grounded in provided inputs.",
            "- Completeness Closure: run a final closure pass to confirm required sections, trace/canonical closure, and seed coverage are complete.",
            "- blocker report: if required inputs are missing, conflicting, or ambiguous after clarification, stop and return a blocker report instead of speculative output.",
        )
        for path in sorted(self.prompt_dir.glob("prompt_*.md")):
            text = path.read_text(encoding="utf-8")
            for line in required_lines:
                self.assertIn(line, text, msg=f"{path.name} missing hardening line: {line}")

    def test_trinity_output_examples_include_non_empty_canonical_refs(self):
        for file_name in (
            "prompt_16a_impl_planner.md",
            "prompt_16b_impl_coder.md",
            "prompt_16c_impl_reviewer.md",
        ):
            path = self.prompt_dir / file_name
            text = path.read_text(encoding="utf-8")
            section = text.split("# Output Contract", 1)[1].split("## B4 Metadata Contract", 1)[0]
            blocks = re.findall(r"```json\s*(.*?)\s*```", section, flags=re.DOTALL)
            self.assertTrue(blocks, msg=f"{file_name} missing output-contract JSON block")
            payload = json.loads(blocks[-1])
            refs = payload.get("canonical_refs_used")
            self.assertIsInstance(refs, list, msg=f"{file_name} canonical_refs_used must be an array")
            self.assertGreater(len(refs), 0, msg=f"{file_name} canonical_refs_used must be non-empty")
            self.assertIn("id", refs[0], msg=f"{file_name} canonical ref must include id")
            self.assertIn("kind", refs[0], msg=f"{file_name} canonical ref must include kind")

    def test_trinity_update_logic_examples_preserve_canonical_refs_used(self):
        for file_name in ("prompt_16b_impl_coder.md", "prompt_16c_impl_reviewer.md"):
            path = self.prompt_dir / file_name
            text = path.read_text(encoding="utf-8")
            section = text.split("# Output Contract (Update Logic)", 1)[1].split("## B4 Metadata Contract", 1)[0]
            blocks = re.findall(r"```json\s*(.*?)\s*```", section, flags=re.DOTALL)
            self.assertGreaterEqual(len(blocks), 2, msg=f"{file_name} requires input/output JSON examples")
            input_payload = json.loads(blocks[0])
            output_payload = json.loads(blocks[-1])
            self.assertIn("canonical_refs_used", input_payload, msg=f"{file_name} input must include canonical_refs_used")
            self.assertIn("canonical_refs_used", output_payload, msg=f"{file_name} output must include canonical_refs_used")
            self.assertEqual(
                input_payload["canonical_refs_used"],
                output_payload["canonical_refs_used"],
                msg=f"{file_name} output must carry-forward canonical_refs_used from input example",
            )
            self.assertGreater(
                len(output_payload["canonical_refs_used"]),
                0,
                msg=f"{file_name} output canonical_refs_used must remain non-empty",
            )


if __name__ == "__main__":
    unittest.main()
