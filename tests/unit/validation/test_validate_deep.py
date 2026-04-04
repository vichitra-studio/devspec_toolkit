"""Tests for R9/T26 dynamic W->E promotion logic in validate_dir.

The promotion logic uses PROMOTABLE_PAIRS from errors.py to dynamically
promote warning codes to error codes based on environment variables:
  - SPECDEV_WARNINGS_AS_ERRORS=1  -> promote ALL PROMOTABLE_PAIRS
  - SPECDEV_PROMOTE_CODES=W571,...  -> promote only specified W-codes
  - Neither env var               -> no promotion; deduplicate W/E pairs
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from unittest.mock import patch

from specdev_tools.core.errors import PROMOTABLE_PAIRS, SpecError, make_error
from specdev_tools.validation.validate import validate_dir


def _make_minimal_repo(root: Path) -> Path:
    """Create the minimal directory layout that validate_dir needs."""
    for d in ("spec", "tools", "prompts", "schema", "canon"):
        (root / d).mkdir(exist_ok=True)
    (root / "spec" / "00_charter.json").write_text(
        json.dumps({"$schema": "x"}), encoding="utf-8"
    )
    (root / "tools" / "step_order.json").write_text(
        json.dumps({"steps": ["00"]}),
        encoding="utf-8",
    )
    (root / "canon" / "manifest.json").write_text(
        json.dumps({"registry_version": "1.0.0", "entries": [], "aliases": []}),
        encoding="utf-8",
    )
    (root / "prompts" / "prompt_00_charter.md").write_text("prompt", encoding="utf-8")
    return root


def _run_validate_dir_with_injected_failures(
    root: Path, injected_failures: list[SpecError], env_overrides: dict[str, str] | None = None
) -> list[SpecError]:
    """Run validate_dir with all sub-validators mocked, injecting specific failures.

    The sub-validators are fully mocked out so we only test the promotion
    logic at the end of validate_dir. The injected_failures list is returned
    by lint_spec_quality so they appear in the failures list before promotion.
    """
    env = env_overrides or {}
    # Clean up promotion-related env vars unless explicitly overridden
    clean_env = {
        "SPECDEV_WARNINGS_AS_ERRORS": "",
        "SPECDEV_PROMOTE_CODES": "",
    }
    clean_env.update(env)

    with patch.dict(os.environ, clean_env), \
         patch("specdev_tools.validation.validate.validate_file", return_value=[]), \
         patch("specdev_tools.validation.validate.lint_spec_quality", return_value=injected_failures), \
         patch("specdev_tools.validation.validate.lint_hallucinations", return_value=[]), \
         patch("specdev_tools.validation.validate.validate_canonical_integrity", return_value=[]), \
         patch("specdev_tools.validation.validate.lint_canon_dirs", return_value=[]), \
         patch("specdev_tools.validation.validate.lint_dependency_order", return_value=[]), \
         patch("specdev_tools.validation.validate.check_forward_replay", return_value=[]), \
         patch("specdev_tools.validation.traceability_closure.check_traceability_closure", return_value=[]), \
         patch("specdev_tools.validation.validate.check_extraction_intent", return_value=[]), \
         patch("specdev_tools.validation.validate.run_prompt_schema_sync", return_value=[]):
        return validate_dir(str(root), str(root / "spec"))


class TestR9PromotionWarningsAsErrors(unittest.TestCase):
    """SPECDEV_WARNINGS_AS_ERRORS=1 promotes ALL W-codes in PROMOTABLE_PAIRS."""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = _make_minimal_repo(Path(self._td.name))

    def tearDown(self):
        self._td.cleanup()

    def test_promote_all_single_w_code(self):
        """A single W571 failure is promoted to E571."""
        failures = [make_error("W571", "ASSUMPTION_VAGUE_QUANTIFIER spec/04.json ref=some")]
        result = _run_validate_dir_with_injected_failures(
            self.root, failures, {"SPECDEV_WARNINGS_AS_ERRORS": "1"}
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].code, "E571")

    def test_promote_all_multiple_distinct_w_codes(self):
        """Multiple distinct W-codes are all promoted."""
        failures = [
            make_error("W571", "ASSUMPTION_VAGUE_QUANTIFIER spec/04.json ref=some"),
            make_error("W593", "VAGUE_LANGUAGE_FREE_TEXT spec/05.json ref=many"),
            make_error("W580", "SUBSTEP_DRIFT spec/09.json ref=milestone-1"),
        ]
        result = _run_validate_dir_with_injected_failures(
            self.root, failures, {"SPECDEV_WARNINGS_AS_ERRORS": "1"}
        )
        self.assertEqual(len(result), 3)
        for err in result:
            self.assertFalse(err.code.startswith("W"), f"W-code not promoted: {err.code}")
            self.assertTrue(err.code.startswith("E"), f"Expected E-code: {err.code}")

    def test_promote_all_covers_every_promotable_pair(self):
        """Every W-code in PROMOTABLE_PAIRS is promoted to its E-code."""
        failures = [
            make_error(w_code, f"TEST_LABEL spec/test.json ref=x") for w_code in PROMOTABLE_PAIRS
        ]
        result = _run_validate_dir_with_injected_failures(
            self.root, failures, {"SPECDEV_WARNINGS_AS_ERRORS": "1"}
        )
        self.assertEqual(len(result), len(PROMOTABLE_PAIRS))
        result_codes = {err.code for err in result}
        expected_codes = set(PROMOTABLE_PAIRS.values())
        self.assertEqual(result_codes, expected_codes)

    def test_promote_all_true_string(self):
        """SPECDEV_WARNINGS_AS_ERRORS=true (lowercase) also works."""
        failures = [make_error("W571", "ASSUMPTION_VAGUE_QUANTIFIER spec/04.json ref=some")]
        result = _run_validate_dir_with_injected_failures(
            self.root, failures, {"SPECDEV_WARNINGS_AS_ERRORS": "true"}
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].code, "E571")

    def test_promote_all_yes_string(self):
        """SPECDEV_WARNINGS_AS_ERRORS=yes also works."""
        failures = [make_error("W571", "ASSUMPTION_VAGUE_QUANTIFIER spec/04.json ref=some")]
        result = _run_validate_dir_with_injected_failures(
            self.root, failures, {"SPECDEV_WARNINGS_AS_ERRORS": "yes"}
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].code, "E571")

    def test_promote_all_does_not_promote_non_promotable_codes(self):
        """W-codes NOT in PROMOTABLE_PAIRS are left untouched."""
        failures = [make_error("W110", "DEPRECATED_CANONICAL_USED spec/01.json ref=old-id")]
        result = _run_validate_dir_with_injected_failures(
            self.root, failures, {"SPECDEV_WARNINGS_AS_ERRORS": "1"}
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].code, "W110")

    def test_promote_all_leaves_existing_e_codes_untouched(self):
        """E-codes already present are not double-promoted or corrupted."""
        failures = [
            make_error("E571", "ASSUMPTION_VAGUE_QUANTIFIER spec/04.json ref=existing-error"),
            make_error("W571", "ASSUMPTION_VAGUE_QUANTIFIER spec/04.json ref=warn-to-promote"),
        ]
        result = _run_validate_dir_with_injected_failures(
            self.root, failures, {"SPECDEV_WARNINGS_AS_ERRORS": "1"}
        )
        # Both should be E571 now; dedup removes exact duplicates
        for err in result:
            self.assertEqual(err.code, "E571")


class TestR9PromotionSelectiveCodes(unittest.TestCase):
    """SPECDEV_PROMOTE_CODES selectively promotes only specified W-codes."""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = _make_minimal_repo(Path(self._td.name))

    def tearDown(self):
        self._td.cleanup()

    def test_promote_single_code(self):
        """SPECDEV_PROMOTE_CODES=W571 promotes only W571->E571."""
        failures = [
            make_error("W571", "ASSUMPTION_VAGUE_QUANTIFIER spec/04.json ref=some"),
            make_error("W593", "VAGUE_LANGUAGE_FREE_TEXT spec/05.json ref=many"),
        ]
        result = _run_validate_dir_with_injected_failures(
            self.root, failures, {"SPECDEV_PROMOTE_CODES": "W571"}
        )
        self.assertEqual(len(result), 2)
        codes = [err.code for err in result]
        self.assertIn("E571", codes)
        self.assertIn("W593", codes)

    def test_promote_multiple_codes(self):
        """SPECDEV_PROMOTE_CODES=W571,W593 promotes both."""
        failures = [
            make_error("W571", "ASSUMPTION_VAGUE_QUANTIFIER spec/04.json ref=some"),
            make_error("W593", "VAGUE_LANGUAGE_FREE_TEXT spec/05.json ref=many"),
            make_error("W580", "SUBSTEP_DRIFT spec/09.json ref=milestone-1"),
        ]
        result = _run_validate_dir_with_injected_failures(
            self.root, failures, {"SPECDEV_PROMOTE_CODES": "W571,W593"}
        )
        self.assertEqual(len(result), 3)
        codes = [err.code for err in result]
        self.assertIn("E571", codes)
        self.assertIn("E593", codes)
        self.assertIn("W580", codes)

    def test_promote_codes_with_spaces(self):
        """Whitespace in SPECDEV_PROMOTE_CODES is handled gracefully."""
        failures = [
            make_error("W571", "ASSUMPTION_VAGUE_QUANTIFIER spec/04.json ref=some"),
            make_error("W593", "VAGUE_LANGUAGE_FREE_TEXT spec/05.json ref=many"),
        ]
        result = _run_validate_dir_with_injected_failures(
            self.root, failures, {"SPECDEV_PROMOTE_CODES": " W571 , W593 "}
        )
        codes = [err.code for err in result]
        self.assertIn("E571", codes)
        self.assertIn("E593", codes)

    def test_invalid_code_is_ignored(self):
        """An unrecognized code in SPECDEV_PROMOTE_CODES is silently ignored."""
        failures = [
            make_error("W571", "ASSUMPTION_VAGUE_QUANTIFIER spec/04.json ref=some"),
        ]
        result = _run_validate_dir_with_injected_failures(
            self.root, failures, {"SPECDEV_PROMOTE_CODES": "W999,W571"}
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].code, "E571")

    def test_non_promotable_code_is_ignored(self):
        """A W-code that exists but is NOT in PROMOTABLE_PAIRS is ignored."""
        failures = [
            make_error("W110", "DEPRECATED_CANONICAL_USED spec/01.json ref=old-id"),
        ]
        result = _run_validate_dir_with_injected_failures(
            self.root, failures, {"SPECDEV_PROMOTE_CODES": "W110"}
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].code, "W110")

    def test_empty_promote_codes_no_promotion(self):
        """SPECDEV_PROMOTE_CODES="" (empty) means no selective promotion."""
        failures = [make_error("W571", "ASSUMPTION_VAGUE_QUANTIFIER spec/04.json ref=some")]
        result = _run_validate_dir_with_injected_failures(
            self.root, failures, {"SPECDEV_PROMOTE_CODES": ""}
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].code, "W571")


class TestR9PromotionNoEnvVar(unittest.TestCase):
    """With no promotion env vars, W-codes stay as warnings but W/E duplicates are deduped."""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = _make_minimal_repo(Path(self._td.name))

    def tearDown(self):
        self._td.cleanup()

    def test_no_env_var_w_codes_remain(self):
        """Without env vars, W-codes are not promoted."""
        failures = [
            make_error("W571", "ASSUMPTION_VAGUE_QUANTIFIER spec/04.json ref=some"),
            make_error("W593", "VAGUE_LANGUAGE_FREE_TEXT spec/05.json ref=many"),
        ]
        result = _run_validate_dir_with_injected_failures(self.root, failures)
        self.assertEqual(len(result), 2)
        for err in result:
            self.assertTrue(err.code.startswith("W"), f"Expected W-code: {err.code}")

    def test_no_env_var_dedup_w_when_e_exists(self):
        """When both W571 and E571 exist for the same message, W571 is dropped."""
        msg_body = "ASSUMPTION_VAGUE_QUANTIFIER spec/04.json ref=some"
        failures = [
            make_error("E571", msg_body),
            make_error("W571", msg_body),
        ]
        result = _run_validate_dir_with_injected_failures(self.root, failures)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].code, "E571")

    def test_no_env_var_keeps_w_when_no_matching_e(self):
        """W-codes without a matching E-code counterpart are preserved."""
        failures = [
            make_error("W571", "ASSUMPTION_VAGUE_QUANTIFIER spec/04.json ref=some"),
            make_error("E593", "VAGUE_LANGUAGE_FREE_TEXT spec/05.json ref=different-message"),
        ]
        result = _run_validate_dir_with_injected_failures(self.root, failures)
        # Both should remain since the messages differ
        self.assertEqual(len(result), 2)
        codes = [err.code for err in result]
        self.assertIn("W571", codes)
        self.assertIn("E593", codes)

    def test_no_env_var_dedup_multiple_pairs(self):
        """Multiple W/E duplicate pairs are all deduped correctly."""
        failures = [
            make_error("E571", "ASSUMPTION_VAGUE_QUANTIFIER spec/04.json ref=x"),
            make_error("W571", "ASSUMPTION_VAGUE_QUANTIFIER spec/04.json ref=x"),
            make_error("E580", "SUBSTEP_DRIFT spec/09.json ref=y"),
            make_error("W580", "SUBSTEP_DRIFT spec/09.json ref=y"),
        ]
        result = _run_validate_dir_with_injected_failures(self.root, failures)
        self.assertEqual(len(result), 2)
        codes = [err.code for err in result]
        self.assertIn("E571", codes)
        self.assertIn("E580", codes)
        self.assertNotIn("W571", codes)
        self.assertNotIn("W580", codes)

    def test_exact_duplicate_failures_are_deduped(self):
        """Exact duplicate SpecErrors (same code, same message) are deduped."""
        failures = [
            make_error("W571", "ASSUMPTION_VAGUE_QUANTIFIER spec/04.json ref=some"),
            make_error("W571", "ASSUMPTION_VAGUE_QUANTIFIER spec/04.json ref=some"),
        ]
        result = _run_validate_dir_with_injected_failures(self.root, failures)
        self.assertEqual(len(result), 1)


class TestR9PromotionPrecedence(unittest.TestCase):
    """When both env vars are set, SPECDEV_WARNINGS_AS_ERRORS takes precedence."""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = _make_minimal_repo(Path(self._td.name))

    def tearDown(self):
        self._td.cleanup()

    def test_warnings_as_errors_takes_precedence_over_promote_codes(self):
        """With both set, SPECDEV_WARNINGS_AS_ERRORS=1 wins and promotes all."""
        failures = [
            make_error("W571", "ASSUMPTION_VAGUE_QUANTIFIER spec/04.json ref=some"),
            make_error("W593", "VAGUE_LANGUAGE_FREE_TEXT spec/05.json ref=many"),
            make_error("W580", "SUBSTEP_DRIFT spec/09.json ref=milestone-1"),
        ]
        result = _run_validate_dir_with_injected_failures(
            self.root,
            failures,
            {
                "SPECDEV_WARNINGS_AS_ERRORS": "1",
                "SPECDEV_PROMOTE_CODES": "W571",
            },
        )
        # All three should be promoted, not just W571
        self.assertEqual(len(result), 3)
        for err in result:
            self.assertTrue(err.code.startswith("E"), f"Expected E-code: {err.code}")

    def test_promote_codes_alone_does_not_promote_all(self):
        """Without WARNINGS_AS_ERRORS, PROMOTE_CODES only promotes the listed ones."""
        failures = [
            make_error("W571", "ASSUMPTION_VAGUE_QUANTIFIER spec/04.json ref=some"),
            make_error("W593", "VAGUE_LANGUAGE_FREE_TEXT spec/05.json ref=many"),
            make_error("W580", "SUBSTEP_DRIFT spec/09.json ref=milestone-1"),
        ]
        result = _run_validate_dir_with_injected_failures(
            self.root,
            failures,
            {"SPECDEV_PROMOTE_CODES": "W571"},
        )
        codes = [err.code for err in result]
        self.assertIn("E571", codes)
        self.assertIn("W593", codes)
        self.assertIn("W580", codes)


class TestR9PromotablePairsIntegrity(unittest.TestCase):
    """Sanity checks on the PROMOTABLE_PAIRS data structure."""

    def test_promotable_pairs_count(self):
        """PROMOTABLE_PAIRS has the expected entries (W561 excluded to prevent double-promotion with W566)."""
        self.assertEqual(len(PROMOTABLE_PAIRS), 26)

    def test_all_w_codes_map_to_e_codes(self):
        """Every key is a W-code and every value is the corresponding E-code."""
        for w_code, e_code in PROMOTABLE_PAIRS.items():
            self.assertTrue(w_code.startswith("W"), f"Key should be W-code: {w_code}")
            self.assertTrue(e_code.startswith("E"), f"Value should be E-code: {e_code}")
            # The numeric part should match
            self.assertEqual(w_code[1:], e_code[1:], f"Numeric mismatch: {w_code} -> {e_code}")

    def test_all_codes_exist_in_error_codes(self):
        """Every code in PROMOTABLE_PAIRS is registered in ERROR_CODES."""
        from specdev_tools.core.errors import ERROR_CODES
        for w_code, e_code in PROMOTABLE_PAIRS.items():
            self.assertIn(w_code, ERROR_CODES, f"W-code {w_code} not in ERROR_CODES")
            self.assertIn(e_code, ERROR_CODES, f"E-code {e_code} not in ERROR_CODES")


class TestR9ExtractionIntentPipelineIntegration(unittest.TestCase):
    """Verify extraction_intent_check is wired into validate_dir pipeline."""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = _make_minimal_repo(Path(self._td.name))

    def tearDown(self):
        self._td.cleanup()

    def test_extraction_intent_errors_surface_through_validate_dir(self):
        """E597/W597 from extraction_intent_check appear in validate_dir output."""
        intent_errors = [
            make_error("E597", "EXTRACTION_INTENT_UPSTREAM_GAP step=05 missing_upstream=04"),
            make_error("W597", "EXTRACTION_INTENT_VAGUE step=06 text='relevant stuff'"),
        ]
        with patch.dict(os.environ, {"SPECDEV_WARNINGS_AS_ERRORS": "", "SPECDEV_PROMOTE_CODES": ""}), \
             patch("specdev_tools.validation.validate.validate_file", return_value=[]), \
             patch("specdev_tools.validation.validate.lint_spec_quality", return_value=[]), \
             patch("specdev_tools.validation.validate.lint_hallucinations", return_value=[]), \
             patch("specdev_tools.validation.validate.validate_canonical_integrity", return_value=[]), \
             patch("specdev_tools.validation.validate.lint_canon_dirs", return_value=[]), \
             patch("specdev_tools.validation.validate.lint_dependency_order", return_value=[]), \
             patch("specdev_tools.validation.validate.check_forward_replay", return_value=[]), \
                 patch("specdev_tools.validation.validate.check_extraction_intent", return_value=intent_errors):
            result = validate_dir(str(self.root), str(self.root / "spec"))
        codes = [err.code for err in result]
        self.assertIn("E597", codes)
        self.assertIn("W597", codes)

    def test_extraction_intent_called_with_repo_root(self):
        """check_extraction_intent is called with the correct repo_root."""
        with patch.dict(os.environ, {"SPECDEV_WARNINGS_AS_ERRORS": "", "SPECDEV_PROMOTE_CODES": ""}), \
             patch("specdev_tools.validation.validate.validate_file", return_value=[]), \
             patch("specdev_tools.validation.validate.lint_spec_quality", return_value=[]), \
             patch("specdev_tools.validation.validate.lint_hallucinations", return_value=[]), \
             patch("specdev_tools.validation.validate.validate_canonical_integrity", return_value=[]), \
             patch("specdev_tools.validation.validate.lint_canon_dirs", return_value=[]), \
             patch("specdev_tools.validation.validate.lint_dependency_order", return_value=[]), \
             patch("specdev_tools.validation.validate.check_forward_replay", return_value=[]), \
                 patch("specdev_tools.validation.validate.check_extraction_intent", return_value=[]) as mock_intent:
            validate_dir(str(self.root), str(self.root / "spec"))
        mock_intent.assert_called_once_with(str(self.root))

    def test_extraction_intent_skipped_without_prompts_dir(self):
        """check_extraction_intent is NOT called when prompts/ doesn't exist."""
        import shutil
        shutil.rmtree(self.root / "prompts")
        with patch.dict(os.environ, {"SPECDEV_WARNINGS_AS_ERRORS": "", "SPECDEV_PROMOTE_CODES": ""}), \
             patch("specdev_tools.validation.validate.validate_file", return_value=[]), \
             patch("specdev_tools.validation.validate.lint_spec_quality", return_value=[]), \
             patch("specdev_tools.validation.validate.lint_hallucinations", return_value=[]), \
             patch("specdev_tools.validation.validate.validate_canonical_integrity", return_value=[]), \
             patch("specdev_tools.validation.validate.lint_canon_dirs", return_value=[]), \
             patch("specdev_tools.validation.validate.lint_dependency_order", return_value=[]), \
             patch("specdev_tools.validation.validate.check_forward_replay", return_value=[]), \
                 patch("specdev_tools.validation.validate.check_extraction_intent", return_value=[]) as mock_intent:
            validate_dir(str(self.root), str(self.root / "spec"))
        mock_intent.assert_not_called()

    def test_extraction_intent_errors_promotable(self):
        """W597 from extraction_intent_check is promoted with SPECDEV_WARNINGS_AS_ERRORS=1."""
        intent_errors = [
            make_error("W597", "EXTRACTION_INTENT_VAGUE step=06 text='relevant stuff'"),
        ]
        with patch.dict(os.environ, {"SPECDEV_WARNINGS_AS_ERRORS": "1", "SPECDEV_PROMOTE_CODES": ""}), \
             patch("specdev_tools.validation.validate.validate_file", return_value=[]), \
             patch("specdev_tools.validation.validate.lint_spec_quality", return_value=[]), \
             patch("specdev_tools.validation.validate.lint_hallucinations", return_value=[]), \
             patch("specdev_tools.validation.validate.validate_canonical_integrity", return_value=[]), \
             patch("specdev_tools.validation.validate.lint_canon_dirs", return_value=[]), \
             patch("specdev_tools.validation.validate.lint_dependency_order", return_value=[]), \
             patch("specdev_tools.validation.validate.check_forward_replay", return_value=[]), \
                 patch("specdev_tools.validation.validate.check_extraction_intent", return_value=intent_errors):
            result = validate_dir(str(self.root), str(self.root / "spec"))
        codes = [err.code for err in result]
        self.assertIn("E597", codes)
        self.assertNotIn("W597", codes)


if __name__ == "__main__":
    unittest.main()
