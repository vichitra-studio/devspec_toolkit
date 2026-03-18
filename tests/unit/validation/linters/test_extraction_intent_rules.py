"""Tests for the extraction intent validator (check_extraction_intent).

Covers all error/warning codes:
    E591 — extraction intent section present but empty (no entries parsed)
    E597 — allowed upstream dependency missing from extraction intent
    W597 — vague intent text (<10 words or contains "relevant"/"as needed")
    E598 — intent references a step not in the steps array
    (no error) — valid extraction intent passes; prompt without section skipped
"""

import json
import os
import tempfile
import unittest

from specdev_tools.validation.extraction_intent_check import check_extraction_intent
from specdev_tools.core.errors import render_errors


class TestExtractionIntentCheck(unittest.TestCase):
    """Unit tests for check_extraction_intent."""

    def _make_repo(self, tmp, steps, deps, prompts):
        """Create a minimal repo structure for testing.

        Args:
            tmp: path to the temporary directory root
            steps: list of step IDs (e.g. ["00", "01", "02"])
            deps: dict mapping step ID -> list of upstream step IDs
            prompts: dict mapping filename -> content string
        Returns:
            tmp path (for use as repo_root)
        """
        tools_dir = os.path.join(tmp, "tools")
        os.makedirs(tools_dir, exist_ok=True)
        with open(os.path.join(tools_dir, "step_order.json"), "w") as f:
            json.dump({"steps": steps, "allowed_upstream_dependencies": deps}, f)

        prompts_dir = os.path.join(tmp, "prompts")
        os.makedirs(prompts_dir, exist_ok=True)
        for name, content in prompts.items():
            with open(os.path.join(prompts_dir, name), "w") as f:
                f.write(content)

        return tmp

    # ------------------------------------------------------------------
    # 1. Valid extraction intent -- no errors
    # ------------------------------------------------------------------
    def test_valid_extraction_intent_no_errors(self):
        """A prompt with complete, specific extraction intent entries produces no errors."""
        with tempfile.TemporaryDirectory() as tmp:
            self._make_repo(
                tmp,
                steps=["00", "01", "02"],
                deps={"02": ["00", "01"]},
                prompts={
                    "prompt_02_system_sketch.md": (
                        "# Step 02 System Sketch\n\n"
                        "### Extraction Intent\n\n"
                        "- **00_charter.json**: Extract the project name, "
                        "vision statement, and success criteria for system boundaries\n"
                        "- **01_capabilities.json**: Extract capability IDs and "
                        "their descriptions to map system components accurately\n"
                    ),
                },
            )
            errors = check_extraction_intent(tmp)
            self.assertEqual(errors, [])

    # ------------------------------------------------------------------
    # 2. Missing upstream coverage -- E597
    # ------------------------------------------------------------------
    def test_missing_upstream_coverage_emits_e597(self):
        """If an allowed upstream dep has no extraction intent entry, emit E597."""
        with tempfile.TemporaryDirectory() as tmp:
            self._make_repo(
                tmp,
                steps=["00", "01", "02"],
                deps={"02": ["00", "01"]},
                prompts={
                    "prompt_02_system_sketch.md": (
                        "# Step 02 System Sketch\n\n"
                        "### Extraction Intent\n\n"
                        "- **00_charter.json**: Extract the project name, "
                        "vision statement, and success criteria for system boundaries\n"
                        # Missing entry for step 01
                    ),
                },
            )
            errors = check_extraction_intent(tmp)
            e597 = [e for e in render_errors(errors) if e.startswith("E597")]
            self.assertEqual(len(e597), 1)
            self.assertIn("'01'", e597[0])
            self.assertIn("prompt_02", e597[0])

    def test_multiple_missing_upstream_emits_multiple_e597(self):
        """Each missing upstream dependency produces its own E597."""
        with tempfile.TemporaryDirectory() as tmp:
            self._make_repo(
                tmp,
                steps=["00", "01", "02", "03"],
                deps={"03": ["00", "01", "02"]},
                prompts={
                    "prompt_03_glossary.md": (
                        "# Step 03 Glossary\n\n"
                        "### Extraction Intent\n\n"
                        "- **00_charter.json**: Extract the project name, "
                        "vision statement, and success criteria for system boundaries\n"
                        # Missing entries for 01 and 02
                    ),
                },
            )
            errors = check_extraction_intent(tmp)
            e597 = [e for e in render_errors(errors) if e.startswith("E597")]
            self.assertEqual(len(e597), 2)

    # ------------------------------------------------------------------
    # 3. Vague intent -- W597
    # ------------------------------------------------------------------
    def test_vague_intent_short_text_emits_w597(self):
        """Intent text with fewer than 10 words triggers W597."""
        with tempfile.TemporaryDirectory() as tmp:
            self._make_repo(
                tmp,
                steps=["00", "01"],
                deps={"01": ["00"]},
                prompts={
                    "prompt_01_capabilities.md": (
                        "# Step 01 Capabilities\n\n"
                        "### Extraction Intent\n\n"
                        "- **00_charter.json**: Extract goals\n"
                    ),
                },
            )
            errors = check_extraction_intent(tmp)
            w597 = [e for e in render_errors(errors) if e.startswith("W597")]
            self.assertEqual(len(w597), 1)
            self.assertIn("vague", w597[0].lower())

    def test_vague_intent_relevant_keyword_emits_w597(self):
        """Intent text containing the word 'relevant' triggers W597."""
        with tempfile.TemporaryDirectory() as tmp:
            self._make_repo(
                tmp,
                steps=["00", "01"],
                deps={"01": ["00"]},
                prompts={
                    "prompt_01_capabilities.md": (
                        "# Step 01 Capabilities\n\n"
                        "### Extraction Intent\n\n"
                        "- **00_charter.json**: Extract all relevant fields from "
                        "the charter document and use them for building capability list\n"
                    ),
                },
            )
            errors = check_extraction_intent(tmp)
            w597 = [e for e in render_errors(errors) if e.startswith("W597")]
            self.assertEqual(len(w597), 1)

    def test_vague_intent_as_needed_keyword_emits_w597(self):
        """Intent text containing 'as needed' triggers W597."""
        with tempfile.TemporaryDirectory() as tmp:
            self._make_repo(
                tmp,
                steps=["00", "01"],
                deps={"01": ["00"]},
                prompts={
                    "prompt_01_capabilities.md": (
                        "# Step 01 Capabilities\n\n"
                        "### Extraction Intent\n\n"
                        "- **00_charter.json**: Extract project goals and scope "
                        "boundaries as needed from the charter document for mapping\n"
                    ),
                },
            )
            errors = check_extraction_intent(tmp)
            w597 = [e for e in render_errors(errors) if e.startswith("W597")]
            self.assertEqual(len(w597), 1)

    # ------------------------------------------------------------------
    # 4. Invalid artifact reference -- E598
    # ------------------------------------------------------------------
    def test_invalid_artifact_ref_emits_e598(self):
        """Intent referencing a step not in the steps array triggers E598."""
        with tempfile.TemporaryDirectory() as tmp:
            self._make_repo(
                tmp,
                steps=["00", "01"],
                deps={"01": ["00"]},
                prompts={
                    "prompt_01_capabilities.md": (
                        "# Step 01 Capabilities\n\n"
                        "### Extraction Intent\n\n"
                        "- **00_charter.json**: Extract the project name, "
                        "vision statement, and success criteria for system boundaries\n"
                        "- **99_nonexistent.json**: Extract something from "
                        "a step that does not exist in the pipeline at all\n"
                    ),
                },
            )
            errors = check_extraction_intent(tmp)
            e598 = [e for e in render_errors(errors) if e.startswith("E598")]
            self.assertEqual(len(e598), 1)
            self.assertIn("'99'", e598[0])

    # ------------------------------------------------------------------
    # 5. Prompt without extraction intent section -- graceful skip
    # ------------------------------------------------------------------
    def test_no_extraction_intent_section_skipped(self):
        """A prompt without ### Extraction Intent is silently skipped."""
        with tempfile.TemporaryDirectory() as tmp:
            self._make_repo(
                tmp,
                steps=["00", "01"],
                deps={"01": ["00"]},
                prompts={
                    "prompt_01_capabilities.md": (
                        "# Step 01 Capabilities\n\n"
                        "Some instructions without extraction intent.\n"
                    ),
                },
            )
            errors = check_extraction_intent(tmp)
            self.assertEqual(errors, [])

    # ------------------------------------------------------------------
    # 6. Empty extraction intent section -- E591
    # ------------------------------------------------------------------
    def test_empty_extraction_intent_emits_e591(self):
        """Section header present but no entries parsed triggers E591."""
        with tempfile.TemporaryDirectory() as tmp:
            self._make_repo(
                tmp,
                steps=["00", "01"],
                deps={"01": ["00"]},
                prompts={
                    "prompt_01_capabilities.md": (
                        "# Step 01 Capabilities\n\n"
                        "### Extraction Intent\n\n"
                        "No bullet entries here, just plain text.\n"
                    ),
                },
            )
            errors = check_extraction_intent(tmp)
            e591 = [e for e in render_errors(errors) if e.startswith("E591")]
            self.assertEqual(len(e591), 1)
            self.assertIn("prompt_01", e591[0])

    def test_empty_extraction_intent_only_header(self):
        """Section header with nothing following also triggers E591."""
        with tempfile.TemporaryDirectory() as tmp:
            self._make_repo(
                tmp,
                steps=["00", "01"],
                deps={"01": ["00"]},
                prompts={
                    "prompt_01_capabilities.md": (
                        "# Step 01 Capabilities\n\n"
                        "### Extraction Intent\n"
                    ),
                },
            )
            errors = check_extraction_intent(tmp)
            e591 = [e for e in render_errors(errors) if e.startswith("E591")]
            self.assertEqual(len(e591), 1)

    # ------------------------------------------------------------------
    # Edge cases
    # ------------------------------------------------------------------
    def test_seed_doc_refs_not_counted_as_step_entries(self):
        """Seed doc references (docs/seed/...) are skipped; they don't satisfy dep coverage."""
        with tempfile.TemporaryDirectory() as tmp:
            self._make_repo(
                tmp,
                steps=["00", "01"],
                deps={"01": ["00"]},
                prompts={
                    "prompt_01_capabilities.md": (
                        "# Step 01 Capabilities\n\n"
                        "### Extraction Intent\n\n"
                        "- **docs/seed/seed_overview.md**: Scope boundaries "
                        "from the seed overview document used for initial framing\n"
                    ),
                },
            )
            errors = check_extraction_intent(tmp)
            # Seed ref IS a valid entry — section is populated (just not
            # with spec deps), so E591 should NOT fire.
            e591 = [e for e in render_errors(errors) if e.startswith("E591")]
            self.assertEqual(len(e591), 0)

    def test_step_with_no_deps_and_valid_intent_no_errors(self):
        """Step 00 has no upstream deps; valid intent entries produce no E597."""
        with tempfile.TemporaryDirectory() as tmp:
            self._make_repo(
                tmp,
                steps=["00", "01"],
                deps={"00": [], "01": ["00"]},
                prompts={
                    "prompt_00_charter.md": (
                        "# Step 00 Charter\n\n"
                        "### Extraction Intent\n\n"
                        "This step has no upstream dependencies.\n"
                    ),
                },
            )
            errors = check_extraction_intent(tmp)
            # No deps to check, but section is present with no entries -> E591
            e591 = [e for e in render_errors(errors) if e.startswith("E591")]
            self.assertEqual(len(e591), 1)
            # No E597 though (no deps to be missing)
            e597 = [e for e in render_errors(errors) if e.startswith("E597")]
            self.assertEqual(len(e597), 0)

    def test_missing_step_order_json_returns_empty(self):
        """When step_order.json is absent, check returns empty list."""
        with tempfile.TemporaryDirectory() as tmp:
            prompts_dir = os.path.join(tmp, "prompts")
            os.makedirs(prompts_dir, exist_ok=True)
            with open(os.path.join(prompts_dir, "prompt_01_capabilities.md"), "w") as f:
                f.write("### Extraction Intent\n\n- **00_charter.json**: stuff\n")
            errors = check_extraction_intent(tmp)
            self.assertEqual(errors, [])

    def test_missing_prompts_dir_returns_empty(self):
        """When prompts directory does not exist, check returns empty list."""
        with tempfile.TemporaryDirectory() as tmp:
            tools_dir = os.path.join(tmp, "tools")
            os.makedirs(tools_dir, exist_ok=True)
            with open(os.path.join(tools_dir, "step_order.json"), "w") as f:
                json.dump({"steps": ["00"], "allowed_upstream_dependencies": {}}, f)
            errors = check_extraction_intent(tmp)
            self.assertEqual(errors, [])

    def test_non_prompt_files_ignored(self):
        """Files not matching prompt_NN_*.md pattern are ignored."""
        with tempfile.TemporaryDirectory() as tmp:
            self._make_repo(
                tmp,
                steps=["00", "01"],
                deps={"01": ["00"]},
                prompts={
                    "README.md": "### Extraction Intent\n\nSome text.\n",
                    "notes_01_capabilities.md": "### Extraction Intent\n\nSome text.\n",
                },
            )
            errors = check_extraction_intent(tmp)
            self.assertEqual(errors, [])

    def test_optional_parenthetical_in_entry(self):
        """Entries with optional parentheticals like '(if present)' are parsed correctly."""
        with tempfile.TemporaryDirectory() as tmp:
            self._make_repo(
                tmp,
                steps=["00", "01", "02", "02a", "03"],
                deps={"03": ["00", "01", "02", "02a"]},
                prompts={
                    "prompt_03_glossary.md": (
                        "# Step 03 Glossary\n\n"
                        "### Extraction Intent\n\n"
                        "- **00_charter.json**: Extract the project name, "
                        "vision, and success criteria for establishing glossary scope\n"
                        "- **01_capabilities.json**: Extract capability names "
                        "and descriptions to identify domain terms needing definition\n"
                        "- **02_system_sketch.json** (if present): Extract "
                        "component names and interface labels for technical term coverage\n"
                        "- **02a_supplemental.json** (optional): Extract any "
                        "supplemental context that adds domain terminology not in core\n"
                    ),
                },
            )
            errors = check_extraction_intent(tmp)
            self.assertEqual(errors, [])

    def test_extraction_intent_section_stops_at_next_heading(self):
        """Parser stops at the next heading after ### Extraction Intent."""
        with tempfile.TemporaryDirectory() as tmp:
            self._make_repo(
                tmp,
                steps=["00", "01"],
                deps={"01": ["00"]},
                prompts={
                    "prompt_01_capabilities.md": (
                        "# Step 01 Capabilities\n\n"
                        "### Extraction Intent\n\n"
                        "- **00_charter.json**: Extract the project name, "
                        "vision statement, and success criteria for system boundaries\n"
                        "\n"
                        "### Output Contract\n\n"
                        "- **99_fake.json**: This should not be parsed because "
                        "it is under a different heading section entirely\n"
                    ),
                },
            )
            errors = check_extraction_intent(tmp)
            # Only 00 should be parsed; 99 is under a different heading
            e598 = [e for e in render_errors(errors) if e.startswith("E598")]
            self.assertEqual(len(e598), 0)
            self.assertEqual(errors, [])

    def test_custom_prompts_dir_parameter(self):
        """The prompts_dir parameter overrides the default prompts path."""
        with tempfile.TemporaryDirectory() as tmp:
            # Create step_order.json in the repo root
            tools_dir = os.path.join(tmp, "tools")
            os.makedirs(tools_dir, exist_ok=True)
            with open(os.path.join(tools_dir, "step_order.json"), "w") as f:
                json.dump(
                    {
                        "steps": ["00", "01"],
                        "allowed_upstream_dependencies": {"01": ["00"]},
                    },
                    f,
                )

            # Create prompt in a custom location
            custom_prompts = os.path.join(tmp, "custom_prompts")
            os.makedirs(custom_prompts, exist_ok=True)
            with open(
                os.path.join(custom_prompts, "prompt_01_capabilities.md"), "w"
            ) as f:
                f.write(
                    "### Extraction Intent\n\n"
                    "- **00_charter.json**: Extract the project name, "
                    "vision statement, and success criteria for system boundaries\n"
                )

            errors = check_extraction_intent(tmp, prompts_dir=custom_prompts)
            self.assertEqual(errors, [])

    def test_combined_errors_multiple_codes(self):
        """A single prompt can produce E597, W597, and E598 simultaneously."""
        with tempfile.TemporaryDirectory() as tmp:
            self._make_repo(
                tmp,
                steps=["00", "01", "02"],
                deps={"02": ["00", "01"]},
                prompts={
                    "prompt_02_system_sketch.md": (
                        "# Step 02 System Sketch\n\n"
                        "### Extraction Intent\n\n"
                        "- **00_charter.json**: Short\n"
                        "- **77_nonexistent.json**: Extract data from this "
                        "step that does not exist in the pipeline for mapping\n"
                        # Missing entry for 01 -> E597
                        # 00 intent is too short -> W597
                        # 77 not in steps -> E598
                    ),
                },
            )
            errors = check_extraction_intent(tmp)
            codes = {e.split()[0] for e in render_errors(errors)}
            self.assertIn("E597", codes, "Missing upstream dep should trigger E597")
            self.assertIn("W597", codes, "Short intent should trigger W597")
            self.assertIn("E598", codes, "Invalid step ref should trigger E598")


if __name__ == "__main__":
    unittest.main()
