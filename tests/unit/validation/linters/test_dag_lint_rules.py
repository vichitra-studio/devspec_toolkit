"""Tests for the DAG completeness validator (dag_lint.py).

Covers error codes E520 (file I/O), E585 (circular deps), E596 (dead-end
producer), E599 (consumer inconsistency), W596 (undeclared upstream ref),
the 16c terminal exemption, and the _INTENT_ENTRY_RE regex.

Note: E597, E598, and W597 are now exclusively in extraction_intent_check.py.
"""

import json
import os
import tempfile
import unittest

from specdev_tools.validation.dag_lint import _INTENT_ENTRY_RE, lint_dag
from specdev_tools.core.errors import render_errors


class TestDagLint(unittest.TestCase):
    """Unit tests for lint_dag()."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_repo(self, tmp, steps=None, consumers=None):
        """Build a minimal repo layout with tools/step_order.json."""
        tools_dir = os.path.join(tmp, "tools")
        os.makedirs(tools_dir, exist_ok=True)
        data = {
            "steps": steps or ["00", "01", "02"],
            "downstream_consumers": consumers or {
                "00": ["01", "02"],
                "01": ["02"],
                "02": [],
            },
        }
        with open(os.path.join(tools_dir, "step_order.json"), "w") as f:
            json.dump(data, f)
        return tmp

    def _make_prompt(self, tmp, step, filename_suffix, content):
        """Write a prompt file into the prompts/ directory."""
        prompts_dir = os.path.join(tmp, "prompts")
        os.makedirs(prompts_dir, exist_ok=True)
        prompt_path = os.path.join(prompts_dir, f"prompt_{step}_{filename_suffix}.md")
        with open(prompt_path, "w") as f:
            f.write(content)
        return prompt_path

    def _error_codes(self, errors):
        """Extract just the error code prefix (e.g. 'E596') from each error."""
        return [e.split()[0] for e in render_errors(errors)]

    # ------------------------------------------------------------------
    # 1. Clean DAG passes (no errors)
    # ------------------------------------------------------------------

    def test_clean_dag_no_errors(self):
        """A consistent 3-step DAG with matching deps/consumers produces no errors."""
        with tempfile.TemporaryDirectory() as tmp:
            self._make_repo(tmp)
            errors = lint_dag(tmp)
            # Step "02" has no consumers but it IS the last step in this DAG.
            # However, "02" is not in _TERMINAL_STEPS so it would emit E596.
            # To get a truly clean DAG, mark 02 as having consumers or use 16c.
            # Let's re-build with a terminal step that IS exempt.
            pass

        # Clean DAG: all non-terminal steps have consumers
        with tempfile.TemporaryDirectory() as tmp:
            self._make_repo(
                tmp,
                steps=["00", "01", "16c"],
                consumers={"00": ["01", "16c"], "01": ["16c"], "16c": []},
            )
            errors = lint_dag(tmp)
            self.assertEqual(errors, [])

    def test_clean_dag_all_nonterminal_have_consumers(self):
        """When every non-terminal step has at least one consumer, no E596."""
        with tempfile.TemporaryDirectory() as tmp:
            self._make_repo(
                tmp,
                steps=["00", "01", "02"],
                consumers={"00": ["01", "02"], "01": ["02"], "02": ["01"]},
            )
            errors = lint_dag(tmp)
            e596_errors = [e for e in render_errors(errors) if "E596 DAG_DEAD_END_PRODUCER" in e]
            self.assertEqual(e596_errors, [])

    # ------------------------------------------------------------------
    # 2. Dead-end producer (E596)
    # ------------------------------------------------------------------

    def test_dead_end_producer_emits_e596(self):
        """A non-terminal step with zero downstream consumers triggers E596."""
        with tempfile.TemporaryDirectory() as tmp:
            self._make_repo(
                tmp,
                steps=["00", "01", "02"],
                consumers={"00": ["01"], "01": [], "02": []},
            )
            errors = lint_dag(tmp)
            codes = self._error_codes(errors)
            self.assertIn("E596", codes)
            # Specifically steps 01 and 02 should be flagged
            dead_end_errors = [
                e for e in render_errors(errors)
                if "E596 DAG_DEAD_END_PRODUCER" in e and "zero downstream" in e
            ]
            flagged_steps = {e.split("'")[1] for e in dead_end_errors}
            self.assertIn("01", flagged_steps)
            self.assertIn("02", flagged_steps)

    def test_single_dead_end_among_healthy_steps(self):
        """Only the dead-end step triggers E596, not the healthy ones."""
        with tempfile.TemporaryDirectory() as tmp:
            # Step 01 has consumers, step 02 does not
            self._make_repo(
                tmp,
                steps=["00", "01", "02"],
                consumers={"00": ["01"], "01": ["02"], "02": []},
            )
            errors = lint_dag(tmp)
            dead_end_errors = [
                e for e in render_errors(errors)
                if "E596 DAG_DEAD_END_PRODUCER" in e and "zero downstream" in e
            ]
            # Only step 02 is a dead-end
            self.assertEqual(len(dead_end_errors), 1)
            self.assertIn("'02'", dead_end_errors[0])

    # ------------------------------------------------------------------
    # 3. Terminal step 16c is exempt from E596
    # ------------------------------------------------------------------

    def test_terminal_step_16c_exempt_from_e596(self):
        """Step 16c with zero consumers does NOT trigger E596."""
        with tempfile.TemporaryDirectory() as tmp:
            self._make_repo(
                tmp,
                steps=["00", "01", "16c"],
                consumers={"00": ["01", "16c"], "01": ["16c"], "16c": []},
            )
            errors = lint_dag(tmp)
            e596_dead = [
                e for e in render_errors(errors)
                if "E596 DAG_DEAD_END_PRODUCER" in e and "zero downstream" in e
            ]
            self.assertEqual(e596_dead, [])

    def test_16c_exempt_but_other_dead_ends_flagged(self):
        """16c is exempt, but another dead-end step is still caught."""
        with tempfile.TemporaryDirectory() as tmp:
            self._make_repo(
                tmp,
                steps=["00", "01", "02", "16c"],
                consumers={"00": ["01", "02"], "01": ["16c"], "02": [], "16c": []},
            )
            errors = lint_dag(tmp)
            dead_end_errors = [
                e for e in render_errors(errors)
                if "E596 DAG_DEAD_END_PRODUCER" in e and "zero downstream" in e
            ]
            flagged_steps = {e.split("'")[1] for e in dead_end_errors}
            self.assertIn("02", flagged_steps)
            self.assertNotIn("16c", flagged_steps)

    # ------------------------------------------------------------------
    # 4. Consumer inconsistency (E599)
    # ------------------------------------------------------------------

    def test_consumer_inconsistency_emits_e599(self):
        """Step X lists Y as consumer but Y appears BEFORE X in steps ordering -> E599.

        Under derive_allowed_upstream (strict_waterfall), allowed upstreams are
        derived from positional order. E599 fires when a declared consumer does
        not come after its producer in the steps list.
        """
        with tempfile.TemporaryDirectory() as tmp:
            self._make_repo(
                tmp,
                steps=["00", "01", "02"],
                # 02 claims 01 is its consumer, but 01 appears BEFORE 02 -> E599
                consumers={"00": ["01", "02"], "01": ["02"], "02": ["01"]},
            )
            errors = lint_dag(tmp)
            e599_errors = [e for e in render_errors(errors) if "E599" in e]
            self.assertTrue(len(e599_errors) >= 1)
            # The error should mention step '02' listing '01' as consumer
            self.assertTrue(
                any("'02'" in e and "'01'" in e for e in e599_errors)
            )

    def test_consumer_references_nonexistent_step_emits_e599(self):
        """Downstream consumer referencing a step not in the steps list -> E599."""
        with tempfile.TemporaryDirectory() as tmp:
            self._make_repo(
                tmp,
                steps=["00", "01"],
                consumers={"00": ["01", "99"], "01": []},
            )
            errors = lint_dag(tmp)
            e599_errors = [e for e in render_errors(errors) if "E599" in e]
            self.assertTrue(len(e599_errors) >= 1)
            self.assertTrue(any("'99'" in e and "not a recognized step" in e for e in e599_errors))

    def test_no_e599_when_consistent(self):
        """Fully consistent deps/consumers produce no E599."""
        with tempfile.TemporaryDirectory() as tmp:
            self._make_repo(
                tmp,
                steps=["00", "01", "16c"],
                consumers={"00": ["01", "16c"], "01": ["16c"], "16c": []},
            )
            errors = lint_dag(tmp)
            e599_errors = [e for e in render_errors(errors) if "E599" in e]
            self.assertEqual(e599_errors, [])

    # ------------------------------------------------------------------
    # 5. Circular dependency detection (E585 DAG_CIRCULAR_DEPENDENCY)
    # ------------------------------------------------------------------

    def test_circular_dependency_detected(self):
        """A consumer ordering violation (consumer before producer) triggers E599.

        Under derive_allowed_upstream, allowed upstreams are strictly positional,
        making true DAG cycles impossible. Consumer ordering violations — where a
        declared consumer appears before its producer in the steps list — are
        detected via E599 instead.
        """
        with tempfile.TemporaryDirectory() as tmp:
            self._make_repo(
                tmp,
                steps=["00", "01", "02"],
                # 02 lists 00 as consumer, but 00 appears before 02 -> E599
                consumers={"00": ["01", "02"], "01": ["02"], "02": ["00"]},
            )
            errors = lint_dag(tmp)
            # Should detect the ordering violation as E599
            ordering_errors = [e for e in render_errors(errors) if "E599" in e]
            self.assertTrue(len(ordering_errors) >= 1)

    def test_no_circular_dependency_in_linear_chain(self):
        """A simple linear chain (00->01->02) has no cycles."""
        with tempfile.TemporaryDirectory() as tmp:
            self._make_repo(
                tmp,
                steps=["00", "01", "16c"],
                consumers={"00": ["01"], "01": ["16c"], "16c": []},
            )
            errors = lint_dag(tmp)
            circular_errors = [e for e in render_errors(errors) if "DAG_CIRCULAR_DEPENDENCY" in e]
            self.assertEqual(circular_errors, [])

    # ------------------------------------------------------------------
    # 6. W596: Prompt references artifact not in computed allowed upstream steps
    # ------------------------------------------------------------------

    def test_undeclared_upstream_ref_emits_w596(self):
        """Extraction intent references a FUTURE step (after current) -> W596.

        Under derive_allowed_upstream, any prior step is a valid upstream.
        W596 fires when a prompt references a step that comes AFTER the current
        step in the pipeline (a forward reference, which is not a valid upstream).
        """
        with tempfile.TemporaryDirectory() as tmp:
            self._make_repo(
                tmp,
                steps=["00", "01", "02"],
                consumers={"00": ["01"], "01": ["02"], "02": []},
            )
            # Prompt for step 01 references step 02, which comes AFTER 01
            self._make_prompt(tmp, "01", "capabilities", (
                "# Prompt for Step 01\n\n"
                "### Extraction Intent\n\n"
                "- **00_charter.json**: Extract the project scope and constraints to scope capability discovery\n"
                "- **02_system_sketch.json**: Extract system architecture details to inform capability definitions\n"
            ))
            errors = lint_dag(tmp)
            w596_errors = [e for e in render_errors(errors) if "W596" in e]
            self.assertTrue(len(w596_errors) >= 1)
            self.assertTrue(any("'02'" in e for e in w596_errors))

    def test_trinity_substeps_shared_artifact_no_w596(self):
        """Intra-Trinity cross-references via spec/impl_context/ do NOT trigger W596.

        16a/16b/16c share a single milestone plan file — the parser credits an
        ``impl_context`` bullet to both 16a and 16b so coverage works for 16c.
        When that bullet appears in a 16b prompt, the 16b self-credit would fire
        a spurious W596 under the strict DAG-ancestor rule. The W596 check
        tolerates intra-Trinity cross-refs because they describe reads from the
        shared artifact, not DAG violations.
        """
        with tempfile.TemporaryDirectory() as tmp:
            self._make_repo(
                tmp,
                steps=["00", "16", "16a", "16b", "16c"],
                consumers={"00": ["16"], "16": ["16a"], "16a": ["16b"], "16b": ["16c"], "16c": []},
            )
            self._make_prompt(tmp, "16b", "impl_coder", (
                "# Prompt for Step 16b\n\n"
                "### Extraction Intent\n\n"
                "- **spec/impl_context/{step_id}.json**: the shared milestone "
                "context 16a authored and this step writes execution results into\n"
                "- **spec/16_impl_context.json**: Trinity Anchor scope and "
                "milestone_index for this cycle\n"
            ))
            errors = lint_dag(tmp)
            w596_errors = [e for e in render_errors(errors) if "W596" in e]
            self.assertEqual(
                w596_errors, [],
                f"Intra-Trinity impl_context references must not trigger W596. Got: {w596_errors}",
            )


    # ------------------------------------------------------------------
    # 7. Edge cases: missing step_order.json, parse error (E520)
    # ------------------------------------------------------------------

    def test_missing_step_order_json(self):
        """If step_order.json does not exist, returns E520 error."""
        with tempfile.TemporaryDirectory() as tmp:
            errors = lint_dag(tmp)
            self.assertEqual(len(errors), 1)
            self.assertIn("E520", render_errors(errors)[0])
            self.assertIn("not found", render_errors(errors)[0])

    def test_malformed_step_order_json(self):
        """If step_order.json is invalid JSON, returns E520 parse error."""
        with tempfile.TemporaryDirectory() as tmp:
            tools_dir = os.path.join(tmp, "tools")
            os.makedirs(tools_dir, exist_ok=True)
            with open(os.path.join(tools_dir, "step_order.json"), "w") as f:
                f.write("{broken json!!!")
            errors = lint_dag(tmp)
            self.assertEqual(len(errors), 1)
            self.assertIn("E520", render_errors(errors)[0])
            self.assertIn("parse error", render_errors(errors)[0])

    # ------------------------------------------------------------------
    # 8. No prompts directory -> extraction intent checks skipped
    # ------------------------------------------------------------------

    def test_no_prompts_dir_skips_extraction_checks(self):
        """Without a prompts/ directory, no W596 is emitted."""
        with tempfile.TemporaryDirectory() as tmp:
            self._make_repo(
                tmp,
                steps=["00", "01", "16c"],
                consumers={"00": ["01", "16c"], "01": ["16c"], "16c": []},
            )
            # Explicitly ensure no prompts dir
            prompts_dir = os.path.join(tmp, "prompts")
            self.assertFalse(os.path.isdir(prompts_dir))
            errors = lint_dag(tmp)
            extraction_errors = [
                e for e in render_errors(errors) if "W596" in e
            ]
            self.assertEqual(extraction_errors, [])


    # ------------------------------------------------------------------
    # 9. Multiple errors can co-exist
    # ------------------------------------------------------------------

    def test_multiple_error_types_coexist(self):
        """A badly constructed DAG can emit E596 and E599 simultaneously."""
        with tempfile.TemporaryDirectory() as tmp:
            self._make_repo(
                tmp,
                steps=["00", "01", "02"],
                # 02 claims 01 is consumer (but 01 appears before 02) -> E599
                # 01 has no consumers -> E596
                # 02 has no consumers -> E596 (but 02 lists 01 as consumer, which is invalid)
                consumers={"00": ["01", "02"], "01": [], "02": ["01"]},
            )
            errors = lint_dag(tmp)
            codes = set(self._error_codes(errors))
            # Should have dead-end (E596) and consumer ordering inconsistency (E599)
            self.assertIn("E596", codes)
            self.assertIn("E599", codes)


    def test_curated_consumers_subset_is_valid(self):
        """Allowed upstream deps NOT in provider's downstream_consumers should NOT emit E599.

        downstream_consumers is a curated provider-side subset — the inverse
        the inverse of computed upstream deps is intentionally NOT enforced.
        """
        with tempfile.TemporaryDirectory() as tmp:
            # Step 02 lists both 00 and 01 as upstream deps, but 00 only
            # declares 01 as its downstream consumer (omitting 02).
            # This must NOT produce an E599 — the provider curates its list.
            self._make_repo(
                tmp,
                steps=["00", "01", "02", "16c"],
                consumers={
                    "00": ["01"],     # Intentionally omits "02"
                    "01": ["02"],
                    "02": ["16c"],
                    "16c": [],
                },
            )
            errors = lint_dag(tmp)
            e599_errors = [e for e in render_errors(errors) if "E599" in e]
            self.assertEqual(
                e599_errors, [],
                f"Curated subset should not trigger E599, got: {e599_errors}"
            )


class TestIntentEntryRegex(unittest.TestCase):
    """Unit tests for the _INTENT_ENTRY_RE regex pattern.

    Verifies that the broadened regex correctly matches extraction intent
    entries with various parenthetical annotations like (optional),
    (if present), (when available), etc.
    """

    def test_basic_entry_matches(self):
        """Standard extraction intent entry without parenthetical matches."""
        line = "- **04_fr_list.json**: Extract all FR identifiers and acceptance criteria for traceability"
        m = _INTENT_ENTRY_RE.match(line)
        assert m is not None
        self.assertEqual(m.group(1), "04_fr_list.json")
        self.assertIn("Extract all FR identifiers", m.group(2))

    def test_entry_with_optional_parenthetical(self):
        """Entry with (optional) annotation after the artifact name matches."""
        line = "- **03_glossary.json** (optional): Extract domain terms and definitions for consistency checking"
        m = _INTENT_ENTRY_RE.match(line)
        assert m is not None
        self.assertEqual(m.group(1), "03_glossary.json")
        self.assertIn("Extract domain terms", m.group(2))

    def test_entry_with_if_present_parenthetical(self):
        """Entry with (if present) annotation matches."""
        line = "- **02a_delivery_baseline.json** (if present): Extract delivery constraints and timeline boundaries for planning"
        m = _INTENT_ENTRY_RE.match(line)
        assert m is not None
        self.assertEqual(m.group(1), "02a_delivery_baseline.json")
        self.assertIn("Extract delivery constraints", m.group(2))

    def test_entry_with_when_available_parenthetical(self):
        """Entry with (when available) annotation matches."""
        line = "- **08_fixtures.json** (when available): Extract fixture definitions and their target mappings for validation"
        m = _INTENT_ENTRY_RE.match(line)
        assert m is not None
        self.assertEqual(m.group(1), "08_fixtures.json")
        self.assertIn("Extract fixture definitions", m.group(2))

    def test_seed_doc_ref_matches(self):
        """Seed document reference with docs/seed/ prefix matches."""
        line = "- **docs/seed/seed_overview.md**: Extract high-level product vision and target audience for capability alignment"
        m = _INTENT_ENTRY_RE.match(line)
        assert m is not None
        self.assertEqual(m.group(1), "seed_overview.md")

    def test_seed_doc_without_prefix_matches(self):
        """Bare seed_*.md reference matches."""
        line = "- **seed_tech_stack.md**: Extract technology choices and platform constraints for architecture decisions"
        m = _INTENT_ENTRY_RE.match(line)
        assert m is not None
        self.assertEqual(m.group(1), "seed_tech_stack.md")

    def test_step_with_letter_suffix_matches(self):
        """Step numbers with letter suffixes like 02a, 13a, 16b match."""
        line = "- **13a_completeness_assessment.json**: Extract completeness scores and gap analysis for roadmap planning"
        m = _INTENT_ENTRY_RE.match(line)
        assert m is not None
        self.assertEqual(m.group(1), "13a_completeness_assessment.json")

    def test_non_intent_line_does_not_match(self):
        """A regular markdown bullet without bold artifact name does not match."""
        line = "- This is just a regular bullet point about something"
        m = _INTENT_ENTRY_RE.match(line)
        self.assertIsNone(m)

    def test_indented_entry_matches(self):
        """Entry with leading whitespace still matches."""
        line = "  - **00_charter.json**: Extract the project scope boundaries and constraints to inform decisions"
        m = _INTENT_ENTRY_RE.match(line)
        assert m is not None
        self.assertEqual(m.group(1), "00_charter.json")


if __name__ == "__main__":
    unittest.main()
