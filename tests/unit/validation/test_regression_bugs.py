"""Regression tests for specific bugs found during the tool audit.

Created by FIX-049 (Batch 5).
"""
from __future__ import annotations

import re

import pytest

from specdev_tools.core.errors import ERROR_CODES, PROMOTABLE_PAIRS, SpecError, make_error


# ---------------------------------------------------------------------------
# Bug 1: E320 must be in ERROR_CODES registry
# ---------------------------------------------------------------------------

class TestErrorCodeRegistry:
    """Verify that specific error codes exist in the registry."""

    def test_e320_exists(self):
        assert "E320" in ERROR_CODES
        assert ERROR_CODES["E320"] == "STEP13_EXTENSION_ERROR"

    def test_all_e_codes_start_with_e(self):
        for code in ERROR_CODES:
            assert code[0] in ("E", "W"), f"Unexpected prefix in {code}"

    def test_all_w_codes_have_numeric_suffix(self):
        for code in ERROR_CODES:
            assert re.match(r"^[EW]\d{3}$", code), f"Malformed code: {code}"


# ---------------------------------------------------------------------------
# Bug 2: hallucination_lint _load_nfr_ids uses nfr_id not id
# ---------------------------------------------------------------------------

class TestHallucinationLintNfrIds:
    """Verify _load_nfr_ids uses nfr_id field, not generic id."""

    def test_load_nfr_ids_uses_nfr_id(self, tmp_path):
        import json
        spec_dir = tmp_path
        nfr_file = spec_dir / "07_nfrs.json"
        nfr_file.write_text(json.dumps({
            "nfrs": [
                {"nfr_id": "nfr-perf", "id": "wrong-id"},
                {"nfr_id": "nfr-sec"},
            ]
        }))
        from specdev_tools.validation.hallucination_lint import _load_nfr_ids
        result = _load_nfr_ids(str(spec_dir))
        assert result is not None
        assert "nfr-perf" in result
        assert "nfr-sec" in result
        # Should NOT use the generic "id" field
        assert "wrong-id" not in result

    def test_load_nfr_ids_missing_file(self, tmp_path):
        from specdev_tools.validation.hallucination_lint import _load_nfr_ids
        result = _load_nfr_ids(str(tmp_path))
        assert result is None


# ---------------------------------------------------------------------------
# Bug 4: validate_file applies W->E promotion
# ---------------------------------------------------------------------------

class TestValidateFilePromotion:
    """Verify that validate_file applies W->E promotion."""

    def test_apply_we_promotion_with_warnings_as_errors(self, monkeypatch):
        from specdev_tools.core.config import reset_config
        from specdev_tools.validation.validate import _apply_we_promotion

        monkeypatch.setenv("SPECDEV_WARNINGS_AS_ERRORS", "1")
        reset_config()
        try:
            # W572 is a stable promotable pair (W572 -> E572). W590 is NOT used
            # here: it was deliberately removed from PROMOTABLE_PAIRS because
            # CROSS_STEP_UPSTREAM_MISSING has no semantically-correct E-counterpart.
            failures = [make_error("W572", "ASSUMPTION_COUNT_HIGH some message")]
            result = _apply_we_promotion(failures)
            assert any(e.code == "E572" for e in result)
            assert not any(e.code == "W572" for e in result)
        finally:
            monkeypatch.delenv("SPECDEV_WARNINGS_AS_ERRORS", raising=False)
            reset_config()

    def test_apply_we_promotion_selective(self, monkeypatch):
        from specdev_tools.core.config import reset_config
        from specdev_tools.validation.validate import _apply_we_promotion

        monkeypatch.setenv("SPECDEV_PROMOTE_CODES", "W571")
        monkeypatch.delenv("SPECDEV_WARNINGS_AS_ERRORS", raising=False)
        reset_config()
        try:
            failures = [
                make_error("W571", "ASSUMPTION_VAGUE_QUANTIFIER some message"),
                make_error("W590", "CROSS_STEP_UPSTREAM_MISSING other message"),
            ]
            result = _apply_we_promotion(failures)
            # W571 should be promoted to E571
            assert any(e.code == "E571" for e in result)
            # W590 should NOT be promoted (not in promote list)
            assert any(e.code == "W590" for e in result)
        finally:
            monkeypatch.delenv("SPECDEV_PROMOTE_CODES", raising=False)
            reset_config()

    def test_apply_we_promotion_no_env(self, monkeypatch):
        from specdev_tools.core.config import reset_config
        from specdev_tools.validation.validate import _apply_we_promotion

        monkeypatch.delenv("SPECDEV_WARNINGS_AS_ERRORS", raising=False)
        monkeypatch.delenv("SPECDEV_PROMOTE_CODES", raising=False)
        reset_config()
        try:
            failures = [make_error("W590", "CROSS_STEP_UPSTREAM_MISSING message")]
            result = _apply_we_promotion(failures)
            assert len(result) == 1
            assert result[0].code == "W590"
            assert result[0].message == "CROSS_STEP_UPSTREAM_MISSING message"
        finally:
            reset_config()

    def test_warn_ignored_promote_codes_non_promotable(self, monkeypatch, capsys):
        """A valid-but-non-promotable code in SPECDEV_PROMOTE_CODES warns to stderr."""
        from specdev_tools.core.config import reset_config
        from specdev_tools.validation.validate import _warn_ignored_promote_codes

        # W590 is a valid warning code that is intentionally non-promotable.
        monkeypatch.setenv("SPECDEV_PROMOTE_CODES", "W590")
        monkeypatch.delenv("SPECDEV_WARNINGS_AS_ERRORS", raising=False)
        reset_config()
        try:
            _warn_ignored_promote_codes()
            err = capsys.readouterr().err
            assert "W590" in err
            assert "not a promotable code" in err
        finally:
            monkeypatch.delenv("SPECDEV_PROMOTE_CODES", raising=False)
            reset_config()

    def test_warn_ignored_promote_codes_unrecognised(self, monkeypatch, capsys):
        """An unrecognised code in SPECDEV_PROMOTE_CODES warns to stderr."""
        from specdev_tools.core.config import reset_config
        from specdev_tools.validation.validate import _warn_ignored_promote_codes

        monkeypatch.setenv("SPECDEV_PROMOTE_CODES", "WXXX")
        monkeypatch.delenv("SPECDEV_WARNINGS_AS_ERRORS", raising=False)
        reset_config()
        try:
            _warn_ignored_promote_codes()
            err = capsys.readouterr().err
            assert "WXXX" in err
            assert "unrecognised" in err
        finally:
            monkeypatch.delenv("SPECDEV_PROMOTE_CODES", raising=False)
            reset_config()

    def test_warn_ignored_promote_codes_silent_when_promotable(self, monkeypatch, capsys):
        """A promotable code in SPECDEV_PROMOTE_CODES produces no warning."""
        from specdev_tools.core.config import reset_config
        from specdev_tools.validation.validate import _warn_ignored_promote_codes

        monkeypatch.setenv("SPECDEV_PROMOTE_CODES", "W571")
        monkeypatch.delenv("SPECDEV_WARNINGS_AS_ERRORS", raising=False)
        reset_config()
        try:
            _warn_ignored_promote_codes()
            assert capsys.readouterr().err == ""
        finally:
            monkeypatch.delenv("SPECDEV_PROMOTE_CODES", raising=False)
            reset_config()

    def test_warn_ignored_promote_codes_silent_when_warnings_as_errors(self, monkeypatch, capsys):
        """When SPECDEV_WARNINGS_AS_ERRORS=1, promote_codes is ignored wholesale,
        so a per-code 'ignored' warning would mislead and must be suppressed."""
        from specdev_tools.core.config import reset_config
        from specdev_tools.validation.validate import _warn_ignored_promote_codes

        monkeypatch.setenv("SPECDEV_PROMOTE_CODES", "W590")
        monkeypatch.setenv("SPECDEV_WARNINGS_AS_ERRORS", "1")
        reset_config()
        try:
            _warn_ignored_promote_codes()
            assert capsys.readouterr().err == ""
        finally:
            monkeypatch.delenv("SPECDEV_PROMOTE_CODES", raising=False)
            monkeypatch.delenv("SPECDEV_WARNINGS_AS_ERRORS", raising=False)
            reset_config()

    def test_warn_ignored_promote_codes_mixed_list(self, monkeypatch, capsys):
        """With a mixed list, only the non-promotable code warns; the promotable
        one is silent."""
        from specdev_tools.core.config import reset_config
        from specdev_tools.validation.validate import _warn_ignored_promote_codes

        monkeypatch.setenv("SPECDEV_PROMOTE_CODES", "W571,W590")
        monkeypatch.delenv("SPECDEV_WARNINGS_AS_ERRORS", raising=False)
        reset_config()
        try:
            _warn_ignored_promote_codes()
            err = capsys.readouterr().err
            assert "W590" in err
            assert "W571" not in err
        finally:
            monkeypatch.delenv("SPECDEV_PROMOTE_CODES", raising=False)
            reset_config()

    def test_promotable_pairs_consistency(self):
        """Every W-code in PROMOTABLE_PAIRS must exist in ERROR_CODES."""
        for w_code, e_code in PROMOTABLE_PAIRS.items():
            assert w_code in ERROR_CODES, f"{w_code} not in ERROR_CODES"
            assert e_code in ERROR_CODES, f"{e_code} not in ERROR_CODES"

    def test_partial_promotion_drops_non_promoted_w_with_matching_e(self, monkeypatch):
        """M1: In partial-promotion mode, non-promoted W-codes with matching
        E-code counterparts already present should be dropped (deduped).

        Scenario: SPECDEV_PROMOTE_CODES=W571 (only W571 promoted).
        Input has both W572 and E572 with the same message/path.
        W572 is NOT in the promote list, but its E-code counterpart E572
        is already present — W572 should be dropped as redundant.
        """
        from specdev_tools.core.config import reset_config
        from specdev_tools.validation.validate import _apply_we_promotion

        monkeypatch.setenv("SPECDEV_PROMOTE_CODES", "W571")
        monkeypatch.delenv("SPECDEV_WARNINGS_AS_ERRORS", raising=False)
        reset_config()
        try:
            msg = "some assumption count message"
            failures = [
                make_error("W572", msg),
                make_error("E572", msg),
                make_error("W571", "vague quantifier message"),
            ]
            result = _apply_we_promotion(failures)
            # W572 should be dropped because E572 with same message exists
            assert not any(e.code == "W572" for e in result), (
                "W572 should be dropped when matching E572 is present"
            )
            # E572 should survive
            assert any(e.code == "E572" for e in result)
            # W571 should be promoted to E571
            assert any(e.code == "E571" for e in result)
            assert not any(e.code == "W571" for e in result)
        finally:
            monkeypatch.delenv("SPECDEV_PROMOTE_CODES", raising=False)
            reset_config()
