import re
import json
import unittest
from pathlib import Path
import sys

from jsonschema import Draft202012Validator

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from specdev_tools.registry import SchemaRegistry
from specdev_tools.validate import _registry_for


class PromptB4ContractsTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
