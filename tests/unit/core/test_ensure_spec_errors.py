"""Tests for ensure_spec_errors and render_errors in core.errors.

Batch 0A of P7 Phase 0.
"""
from __future__ import annotations

import pytest

from specdev_tools.core.errors import (
    SpecError,
    ensure_spec_errors,
    render_errors,
)


# ---------------------------------------------------------------------------
# render_errors
# ---------------------------------------------------------------------------

class TestRenderErrors:
    """Tests for render_errors helper."""

    def test_empty_list(self):
        assert render_errors([]) == []

    def test_renders_code_and_message(self):
        errs = [SpecError(code="E520", message="something broke")]
        assert render_errors(errs) == ["E520 something broke"]

    def test_renders_with_path(self):
        errs = [SpecError(code="E590", message="id not found", path="spec/04.json")]
        assert render_errors(errs) == ["E590 spec/04.json id not found"]

    def test_multiple(self):
        errs = [
            SpecError(code="E520", message="a"),
            SpecError(code="W571", message="b"),
        ]
        result = render_errors(errs)
        assert len(result) == 2
        assert result[0] == "E520 a"
        assert result[1] == "W571 b"


# ---------------------------------------------------------------------------
# ensure_spec_errors — all 4 parsing paths
# ---------------------------------------------------------------------------

class TestEnsureSpecErrors:
    """Tests for ensure_spec_errors covering all parsing heuristics."""

    # Path 1: SpecError passthrough
    def test_spec_error_passthrough(self):
        original = SpecError(code="E520", message="already structured", path="foo.json")
        result = ensure_spec_errors([original])
        assert len(result) == 1
        assert result[0] is original

    # Path 2: Three-part string (code + mnemonic/path + rest)
    def test_three_part_string(self):
        s = "E520 UNRESOLVED_INPUT spec/04.json missing field"
        result = ensure_spec_errors([s])
        assert len(result) == 1
        assert result[0].code == "E520"
        assert result[0].message == "UNRESOLVED_INPUT spec/04.json missing field"

    def test_three_part_warning(self):
        s = "W571 ASSUMPTION_VAGUE_QUANTIFIER some vague text"
        result = ensure_spec_errors([s])
        assert len(result) == 1
        assert result[0].code == "W571"
        assert result[0].message == "ASSUMPTION_VAGUE_QUANTIFIER some vague text"

    # Path 3: Two-part string (code + message only)
    def test_two_part_string(self):
        s = "E590 cross-step id not found"
        result = ensure_spec_errors([s])
        assert len(result) == 1
        assert result[0].code == "E590"
        assert result[0].message == "cross-step id not found"

    def test_two_part_code_only_with_space(self):
        s = "W570 "
        result = ensure_spec_errors([s])
        assert len(result) == 1
        assert result[0].code == "W570"
        assert result[0].message == ""

    # Path 4: Fallback (no code prefix)
    def test_fallback_no_code(self):
        s = "Missing targets for fixture fix-login"
        result = ensure_spec_errors([s])
        assert len(result) == 1
        assert result[0].code == "E521"
        assert result[0].message == s

    def test_fallback_numeric_start(self):
        s = "123 not an error code"
        result = ensure_spec_errors([s])
        assert len(result) == 1
        assert result[0].code == "E521"

    # Edge cases
    def test_empty_list(self):
        assert ensure_spec_errors([]) == []

    def test_mixed_list(self):
        items: list[str | SpecError] = [
            SpecError(code="E520", message="structured"),
            "E590 CROSS_STEP_ID_NOT_FOUND some ref",
            "W571 vague quantifier",
            "plain text error",
        ]
        result = ensure_spec_errors(items)
        assert len(result) == 4
        assert result[0].code == "E520"
        assert result[0].message == "structured"
        assert result[1].code == "E590"
        assert result[1].message == "CROSS_STEP_ID_NOT_FOUND some ref"
        assert result[2].code == "W571"
        assert result[2].message == "vague quantifier"
        assert result[3].code == "E521"
        assert result[3].message == "plain text error"

    def test_path_in_three_part_string_not_set_on_spec_error(self):
        """Three-part parse puts everything into message, not path field."""
        s = "E520 spec/04.json missing"
        result = ensure_spec_errors([s])
        assert result[0].path is None
        assert "spec/04.json" in result[0].message

    def test_empty_string_fallback(self):
        """Empty string should fall through to fallback with E521."""
        result = ensure_spec_errors([""])
        assert len(result) == 1
        assert result[0].code == "E521"
        assert result[0].message == ""

    def test_whitespace_only_string_fallback(self):
        """Whitespace-only string should fall through to fallback with E521."""
        result = ensure_spec_errors(["   "])
        assert len(result) == 1
        assert result[0].code == "E521"
        assert result[0].message == "   "
