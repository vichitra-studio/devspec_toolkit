import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from specdev_tools.prompt_schema_sync import run_prompt_schema_sync


class PromptSchemaSyncTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
