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

    def _make_repo(self, tmp, steps, prompts):
        """Create a minimal repo structure for testing.

        Args:
            tmp: path to the temporary directory root
            steps: list of step IDs (e.g. ["00", "01", "02"])
            prompts: dict mapping filename -> content string
        Returns:
            tmp path (for use as repo_root)
        """
        tools_dir = os.path.join(tmp, "tools")
        os.makedirs(tools_dir, exist_ok=True)
        with open(os.path.join(tools_dir, "step_order.json"), "w") as f:
            json.dump({"steps": steps}, f)

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
                json.dump({"steps": ["00"]}, f)
            errors = check_extraction_intent(tmp)
            self.assertEqual(errors, [])

    def test_non_prompt_files_ignored(self):
        """Files not matching prompt_NN_*.md pattern are ignored."""
        with tempfile.TemporaryDirectory() as tmp:
            self._make_repo(
                tmp,
                steps=["00", "01"],
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

    def test_spec_prefixed_artifact_ref_parsed(self):
        """Entries like **spec/00_charter.json** are parsed the same as bare filename.

        Authors across the toolkit use both conventions — bare (`**00_charter.json**`)
        and spec-prefixed (`**spec/00_charter.json**`). Both must register as step
        references so upstream-dep coverage (E597) is accurate.
        """
        with tempfile.TemporaryDirectory() as tmp:
            self._make_repo(
                tmp,
                steps=["00", "01"],
                prompts={
                    "prompt_01_capabilities.md": (
                        "# Step 01 Capabilities\n\n"
                        "### Extraction Intent\n\n"
                        "- **spec/00_charter.json**: Extract the project name, "
                        "vision statement, and success criteria for system boundaries\n"
                    ),
                },
            )
            errors = check_extraction_intent(tmp)
            # spec-prefixed entry must count as a valid reference to step 00,
            # so neither E597 (missing upstream) nor E591 (empty section) fires.
            self.assertEqual(errors, [])

    def test_spec_impl_context_reference_maps_to_step_16a(self):
        """References to **spec/impl_context/<anything>.json** map to step 16a.

        The per-milestone plan filename varies (often a template placeholder), so
        the parser routes any `spec/impl_context/` entry to step 16a directly
        without attempting to extract a step number from the filename.
        """
        with tempfile.TemporaryDirectory() as tmp:
            self._make_repo(
                tmp,
                steps=["00", "01", "14", "16", "16a", "16b"],
                prompts={
                    "prompt_16b_impl_coder.md": (
                        "# Step 16b Coder\n\n"
                        "### Extraction Intent\n\n"
                        "- **spec/impl_context/{step_id}.json**: the milestone "
                        "context file 16a authored — read the checklist and write "
                        "execution results back into the same file\n"
                        "- **spec/16_impl_context.json**: Trinity Anchor — read "
                        "scope_in/scope_out to confirm code changes stay within "
                        "anchor-declared scope for this milestone cycle\n"
                    ),
                },
            )
            errors = check_extraction_intent(tmp)
            # Both "16" (from spec/16_impl_context.json) and "16a" (from
            # spec/impl_context/...) must register so upstream-dep coverage
            # is satisfied for 16b.
            e597 = [e for e in render_errors(errors) if e.startswith("E597")]
            missing_16 = [e for e in e597 if "'16'" in e]
            missing_16a = [e for e in e597 if "'16a'" in e]
            self.assertEqual(missing_16, [], f"'16' unexpectedly missing: {errors}")
            self.assertEqual(missing_16a, [], f"'16a' unexpectedly missing: {errors}")

    def test_step_metadata_required_spec_inputs_used_when_present(self):
        """When step_order declares step_metadata[step].required_spec_inputs, the
        validator treats THAT set (not derive_allowed_upstream) as the authoritative
        coverage requirement.

        Setup: steps = [00, 01, 02]. DAG-allowed upstream for step 02 is {00, 01}
        (both ancestors). But step_metadata[02].required_spec_inputs = [01] — only
        step 01 is actually consumed. A prompt declaring only step 01 must pass.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tools_dir = os.path.join(tmp, "tools")
            os.makedirs(tools_dir, exist_ok=True)
            step_order = {
                "steps": ["00", "01", "02"],
                "step_metadata": {
                    "02": {"required_spec_inputs": ["01"]},
                },
            }
            with open(os.path.join(tools_dir, "step_order.json"), "w") as f:
                json.dump(step_order, f)
            prompts_dir = os.path.join(tmp, "prompts")
            os.makedirs(prompts_dir, exist_ok=True)
            with open(os.path.join(prompts_dir, "prompt_02_system_sketch.md"), "w") as f:
                f.write(
                    "### Extraction Intent\n\n"
                    "- **01_capabilities.json**: Extract capability IDs and "
                    "descriptions used for system sketch component boundaries\n"
                )
            errors = check_extraction_intent(tmp)
            # Step 00 is a DAG ancestor but not a required_spec_input — must NOT fire E597
            self.assertEqual(errors, [])

    def test_step_metadata_empty_required_spec_inputs_respected(self):
        """An explicit `required_spec_inputs: []` means 'no upstream deps required'.

        The validator must respect this as a valid declaration (not fall back to
        derive_allowed_upstream). E.g., step 00 legitimately has no upstream.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tools_dir = os.path.join(tmp, "tools")
            os.makedirs(tools_dir, exist_ok=True)
            step_order = {
                "steps": ["00", "01"],
                "step_metadata": {
                    "01": {"required_spec_inputs": []},
                },
            }
            with open(os.path.join(tools_dir, "step_order.json"), "w") as f:
                json.dump(step_order, f)
            prompts_dir = os.path.join(tmp, "prompts")
            os.makedirs(prompts_dir, exist_ok=True)
            # Prompt declares step 00 — but required is []. Intent for 00 becomes
            # unrequired noise but should not trigger E597 (no gap). E598 also
            # should not fire (00 is a valid step).
            with open(os.path.join(prompts_dir, "prompt_01_capabilities.md"), "w") as f:
                f.write(
                    "### Extraction Intent\n\n"
                    "- **00_charter.json**: Extract the project scope and "
                    "success criteria used as contextual framing only\n"
                )
            errors = check_extraction_intent(tmp)
            e597 = [e for e in render_errors(errors) if e.startswith("E597")]
            self.assertEqual(e597, [])

    def test_impl_context_reference_credits_both_16a_and_16b(self):
        """A single `spec/impl_context/...` bullet covers BOTH 16a and 16b upstreams.

        Rationale: post-anchor-split, the milestone plan file is a shared Trinity
        artifact — 16a authors it, 16b writes execution evidence into it. Any
        caller (e.g., 16c) that references `spec/impl_context/...` is reading
        both contributions through a single path.
        """
        with tempfile.TemporaryDirectory() as tmp:
            self._make_repo(
                tmp,
                steps=["00", "14", "16", "16a", "16b", "16c"],
                prompts={
                    "prompt_16c_impl_reviewer.md": (
                        "# Step 16c Reviewer\n\n"
                        "### Extraction Intent\n\n"
                        "- **spec/impl_context/{step_id}.json**: the shared "
                        "milestone context carrying the 16a plan and 16b "
                        "execution evidence; read checklist, execution "
                        "results, and write review findings\n"
                        "- **spec/16_impl_context.json**: Trinity Anchor "
                        "scope and milestone_index for FR ownership context\n"
                        "- **spec/14_roadmap.json**: roadmap milestone "
                        "definitions used to verify coverage for this cycle\n"
                    ),
                },
            )
            # Declare required_spec_inputs for 16c that includes both 16a and 16b.
            step_order_path = os.path.join(tmp, "tools", "step_order.json")
            with open(step_order_path) as f:
                step_order = json.load(f)
            step_order["step_metadata"] = {
                "16c": {"required_spec_inputs": ["14", "16", "16a", "16b"]},
            }
            with open(step_order_path, "w") as f:
                json.dump(step_order, f)
            errors = check_extraction_intent(tmp)
            e597 = [e for e in render_errors(errors) if e.startswith("E597")]
            # impl_context reference should have satisfied both 16a and 16b
            self.assertEqual(
                e597, [],
                f"Expected impl_context reference to cover 16a and 16b. Got: {errors}",
            )

    def test_combined_errors_multiple_codes(self):
        """A single prompt can produce E597, W597, and E598 simultaneously."""
        with tempfile.TemporaryDirectory() as tmp:
            self._make_repo(
                tmp,
                steps=["00", "01", "02"],
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
