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

    def _make_repo(self, tmp, steps=None, deps=None, consumers=None):
        """Build a minimal repo layout with tools/step_order.json."""
        tools_dir = os.path.join(tmp, "tools")
        os.makedirs(tools_dir, exist_ok=True)
        data = {
            "steps": steps or ["00", "01", "02"],
            "allowed_upstream_dependencies": deps or {
                "00": [],
                "01": ["00"],
                "02": ["00", "01"],
            },
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
                deps={"00": [], "01": ["00"], "16c": ["00", "01"]},
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
                deps={"00": [], "01": ["00"], "02": ["00", "01"]},
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
                deps={"00": [], "01": ["00"], "02": ["01"]},
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
                deps={"00": [], "01": ["00"], "02": ["01"]},
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
                deps={"00": [], "01": ["00"], "16c": ["00", "01"]},
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
                deps={"00": [], "01": ["00"], "02": ["00"], "16c": ["01"]},
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
        """Step X lists Y as consumer but Y does not list X as upstream dep -> E599."""
        with tempfile.TemporaryDirectory() as tmp:
            self._make_repo(
                tmp,
                steps=["00", "01", "02"],
                deps={"00": [], "01": ["00"], "02": ["01"]},
                # 00 claims 02 is a consumer, but 02's deps only include 01
                consumers={"00": ["01", "02"], "01": ["02"], "02": []},
            )
            errors = lint_dag(tmp)
            e599_errors = [e for e in render_errors(errors) if "E599" in e]
            self.assertTrue(len(e599_errors) >= 1)
            # The error should mention step '00' listing '02' as consumer
            self.assertTrue(
                any("'00'" in e and "'02'" in e for e in e599_errors)
            )

    def test_consumer_references_nonexistent_step_emits_e599(self):
        """Downstream consumer referencing a step not in the steps list -> E599."""
        with tempfile.TemporaryDirectory() as tmp:
            self._make_repo(
                tmp,
                steps=["00", "01"],
                deps={"00": [], "01": ["00"]},
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
                deps={"00": [], "01": ["00"], "16c": ["00", "01"]},
                consumers={"00": ["01", "16c"], "01": ["16c"], "16c": []},
            )
            errors = lint_dag(tmp)
            e599_errors = [e for e in render_errors(errors) if "E599" in e]
            self.assertEqual(e599_errors, [])

    # ------------------------------------------------------------------
    # 5. Circular dependency detection (E585 DAG_CIRCULAR_DEPENDENCY)
    # ------------------------------------------------------------------

    def test_circular_dependency_detected(self):
        """A cycle in allowed_upstream_dependencies triggers E585 DAG_CIRCULAR_DEPENDENCY."""
        with tempfile.TemporaryDirectory() as tmp:
            self._make_repo(
                tmp,
                steps=["00", "01", "02"],
                deps={"00": ["02"], "01": ["00"], "02": ["01"]},
                # Consumers irrelevant here; just make non-empty to avoid E596 dead-end noise
                consumers={"00": ["01"], "01": ["02"], "02": ["00"]},
            )
            errors = lint_dag(tmp)
            circular_errors = [e for e in render_errors(errors) if "DAG_CIRCULAR_DEPENDENCY" in e]
            self.assertTrue(len(circular_errors) >= 1)

    def test_no_circular_dependency_in_linear_chain(self):
        """A simple linear chain (00->01->02) has no cycles."""
        with tempfile.TemporaryDirectory() as tmp:
            self._make_repo(
                tmp,
                steps=["00", "01", "16c"],
                deps={"00": [], "01": ["00"], "16c": ["01"]},
                consumers={"00": ["01"], "01": ["16c"], "16c": []},
            )
            errors = lint_dag(tmp)
            circular_errors = [e for e in render_errors(errors) if "DAG_CIRCULAR_DEPENDENCY" in e]
            self.assertEqual(circular_errors, [])

    # ------------------------------------------------------------------
    # 6. W596: Prompt references artifact not in allowed_upstream_dependencies
    # ------------------------------------------------------------------

    def test_undeclared_upstream_ref_emits_w596(self):
        """Extraction intent references a valid step that is NOT in the step's upstream deps -> W596."""
        with tempfile.TemporaryDirectory() as tmp:
            # Step 02 only depends on 01, but its prompt also references 00
            self._make_repo(
                tmp,
                steps=["00", "01", "02"],
                deps={"00": [], "01": ["00"], "02": ["01"]},
                consumers={"00": ["01"], "01": ["02"], "02": []},
            )
            self._make_prompt(tmp, "02", "system_sketch", (
                "# Prompt for Step 02\n\n"
                "### Extraction Intent\n\n"
                "- **00_charter.json**: Extract the project scope boundaries and constraints to inform architecture decisions\n"
                "- **01_capabilities.json**: Extract all capability identifiers and their descriptions for cross-referencing\n"
            ))
            errors = lint_dag(tmp)
            w596_errors = [e for e in render_errors(errors) if "W596" in e]
            self.assertTrue(len(w596_errors) >= 1)
            self.assertTrue(any("'00'" in e for e in w596_errors))


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
                deps={"00": [], "01": ["00"], "16c": ["00", "01"]},
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
                deps={"00": [], "01": ["00"], "02": []},
                # 00 claims 02 is consumer (but 02 has no upstream deps) -> E599
                # 01 has no consumers -> E596
                # 02 has no consumers -> E596
                consumers={"00": ["01", "02"], "01": [], "02": []},
            )
            errors = lint_dag(tmp)
            codes = set(self._error_codes(errors))
            # Should have dead-end (E596) and consumer inconsistency (E599)
            self.assertIn("E596", codes)
            self.assertIn("E599", codes)


    def test_curated_consumers_subset_is_valid(self):
        """Allowed upstream deps NOT in provider's downstream_consumers should NOT emit E599.

        downstream_consumers is a curated provider-side subset — the inverse
        of allowed_upstream_dependencies is intentionally NOT enforced.
        """
        with tempfile.TemporaryDirectory() as tmp:
            # Step 02 lists both 00 and 01 as upstream deps, but 00 only
            # declares 01 as its downstream consumer (omitting 02).
            # This must NOT produce an E599 — the provider curates its list.
            self._make_repo(
                tmp,
                steps=["00", "01", "02", "16c"],
                deps={"00": [], "01": ["00"], "02": ["00", "01"], "16c": ["02"]},
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
        line = "- **04_functional_requirements.json**: Extract all FR identifiers and acceptance criteria for traceability"
        m = _INTENT_ENTRY_RE.match(line)
        assert m is not None
        self.assertEqual(m.group(1), "04_functional_requirements.json")
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
