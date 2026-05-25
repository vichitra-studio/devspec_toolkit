"""Tests for W554 HARDCODED_SEED_REFERENCE lint (check_hardcoded_seed_reference).

Verifies:
  - W554 fires on a prompt containing a literal seed_*.md filename.
  - W554 does NOT fire on the manifest-anchored bullet (seed_manifest.json).
  - W554 does NOT fire on a clean prompt with no seed references.
  - W554 fires for seed_*.md literals in nested prompt subdirectories (recursive glob).
"""
from __future__ import annotations

import os
import tempfile
import unittest

from specdev_tools.validation.seed_lint import check_hardcoded_seed_reference
from specdev_tools.core.errors import render_errors, PROMOTABLE_PAIRS


def _write_prompt(directory: str, filename: str, content: str) -> str:
    """Write a prompt file into *directory* and return its path."""
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


class TestW554HardcodedSeedReference(unittest.TestCase):
    """Unit tests for check_hardcoded_seed_reference()."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _codes(self, errors):
        return [e.split()[0] for e in render_errors(errors)]

    def _has_w554(self, errors):
        return "W554" in self._codes(errors)

    # ------------------------------------------------------------------
    # 1. W554 FIRES on a literal seed_*.md filename
    # ------------------------------------------------------------------

    def test_fires_on_seed_overview_md(self):
        """A prompt containing 'seed_overview.md' triggers W554."""
        with tempfile.TemporaryDirectory() as tmpdir:
            prompts_dir = os.path.join(tmpdir, "prompts")
            _write_prompt(
                prompts_dir,
                "prompt_00_charter.md",
                "## Seeds\nRead seed_overview.md before starting.\n",
            )
            errs = check_hardcoded_seed_reference(tmpdir)
            self.assertTrue(self._has_w554(errs), f"Expected W554 but got: {render_errors(errs)}")

    def test_fires_on_seed_tech_stack_md(self):
        """A prompt containing 'seed_tech_stack.md' triggers W554."""
        with tempfile.TemporaryDirectory() as tmpdir:
            prompts_dir = os.path.join(tmpdir, "prompts")
            _write_prompt(
                prompts_dir,
                "prompt_01_capabilities.md",
                "Include context from seed_tech_stack.md and seed_domain_model.md.\n",
            )
            errs = check_hardcoded_seed_reference(tmpdir)
            codes = self._codes(errs)
            self.assertIn("W554", codes, f"Expected W554 but got: {render_errors(errs)}")

    def test_multiple_occurrences_emit_multiple_findings(self):
        """Two lines with seed_*.md each produce a separate W554 finding."""
        with tempfile.TemporaryDirectory() as tmpdir:
            prompts_dir = os.path.join(tmpdir, "prompts")
            _write_prompt(
                prompts_dir,
                "prompt_02_system_sketch.md",
                "First: see seed_overview.md\nSecond: also seed_domain_model.md\n",
            )
            errs = check_hardcoded_seed_reference(tmpdir)
            w554_count = sum(1 for e in render_errors(errs) if e.startswith("W554"))
            self.assertEqual(w554_count, 2, f"Expected 2 W554 findings, got: {render_errors(errs)}")

    # ------------------------------------------------------------------
    # 2. W554 does NOT fire on seed_manifest.json (wrong suffix)
    # ------------------------------------------------------------------

    def test_no_fire_on_manifest_json_reference(self):
        """The manifest-anchored bullet 'seed_manifest.json' must NOT trigger W554."""
        with tempfile.TemporaryDirectory() as tmpdir:
            prompts_dir = os.path.join(tmpdir, "prompts")
            _write_prompt(
                prompts_dir,
                "prompt_00_charter.md",
                "## Input Context\n"
                "- **Seeds**: per spec/common/seed_manifest.json step_requirements[\"00\"]\n"
                "- All seeds listed for step \"00\" in `spec/common/seed_manifest.json` are present.\n",
            )
            errs = check_hardcoded_seed_reference(tmpdir)
            self.assertFalse(
                self._has_w554(errs),
                f"W554 should not fire on seed_manifest.json references. Got: {render_errors(errs)}",
            )

    # ------------------------------------------------------------------
    # 3. W554 does NOT fire on a clean prompt with no seed references
    # ------------------------------------------------------------------

    def test_no_fire_on_clean_prompt(self):
        """A prompt with no seed references at all does not trigger W554."""
        with tempfile.TemporaryDirectory() as tmpdir:
            prompts_dir = os.path.join(tmpdir, "prompts")
            _write_prompt(
                prompts_dir,
                "prompt_05_apis.md",
                "## API Contracts\nDefine all public API endpoints here.\n",
            )
            errs = check_hardcoded_seed_reference(tmpdir)
            self.assertFalse(
                self._has_w554(errs),
                f"Expected no W554 on clean prompt, got: {render_errors(errs)}",
            )

    # ------------------------------------------------------------------
    # 4. No prompts/ directory → no errors (graceful)
    # ------------------------------------------------------------------

    def test_no_prompts_dir_returns_empty(self):
        """When prompts/ doesn't exist, check returns no errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            errs = check_hardcoded_seed_reference(tmpdir)
            self.assertEqual(errs, [], f"Expected empty list, got: {errs}")

    # ------------------------------------------------------------------
    # 5. Recursive glob: seed_*.md in a nested subdirectory IS detected
    # ------------------------------------------------------------------

    def test_fires_on_nested_prompt_subdir(self):
        """A literal seed_*.md in prompts/migration/ subdir is detected (recursive glob)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nested_dir = os.path.join(tmpdir, "prompts", "migration")
            _write_prompt(
                nested_dir,
                "template_scaffold.md",
                "Legacy reference to seed_overview.md — must be removed.\n",
            )
            errs = check_hardcoded_seed_reference(tmpdir)
            self.assertTrue(
                self._has_w554(errs),
                f"Expected W554 from nested prompt, got: {render_errors(errs)}",
            )

    # ------------------------------------------------------------------
    # 6. W554 is warning-only (code starts with 'W')
    # ------------------------------------------------------------------

    def test_w554_is_warning_only(self):
        """W554 findings have warning severity (code starts with 'W')."""
        with tempfile.TemporaryDirectory() as tmpdir:
            prompts_dir = os.path.join(tmpdir, "prompts")
            _write_prompt(
                prompts_dir,
                "prompt_03_glossary.md",
                "Load seed_domain_model.md for terminology context.\n",
            )
            errs = check_hardcoded_seed_reference(tmpdir)
            self.assertTrue(errs, "Expected at least one finding")
            for e in errs:
                self.assertTrue(
                    e.code.startswith("W"),
                    f"Expected warning code, got: {e.code}",
                )

    def test_w554_is_non_promotable(self):
        """W554 must be absent from PROMOTABLE_PAIRS (no E-twin; promotion is inappropriate)."""
        self.assertNotIn("W554", PROMOTABLE_PAIRS, "W554 must be non-promotable (no E-twin)")


if __name__ == "__main__":
    unittest.main()
