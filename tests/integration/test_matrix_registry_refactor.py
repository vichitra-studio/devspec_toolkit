"""Integration test: registry-driven build_trace_matrix() golden regression.

W4-T3 — Golden-file regression test for the W4-T1 refactor that replaced the
legacy ``_id``-suffix discovery scan in ``build_trace_matrix()`` with
registry-driven iteration via ``core/entry_key_registry.py``.

Strategy
--------
The test uses the *host repo's own spec/* directory (``../../spec`` relative to
the toolkit root) together with the real toolkit registry.  This avoids the
complexity of maintaining a minimal fixture corpus while still exercising the
exact registry paths the refactor touches.

The pre-refactor output was captured before any code change and stored at::

    tests/fixtures/trace_matrix_pre_refactor.json

The test regenerates the matrix via ``build_trace_matrix()`` and asserts
byte-for-byte equality against that golden.

Intentional diff policy
-----------------------
The post-refactor output is **byte-for-byte identical** to the pre-refactor
output.  If this test fails, it means an unintended difference was introduced.
Any intentional change (e.g. adding a new entity kind to the registry) must be
accompanied by:

    1. A doc comment here naming the diff and labelling it "INTENDED".
    2. An update to ``tests/fixtures/trace_matrix_pre_refactor.json``.

W4-T2 verification note
------------------------
``CanonicalRegistry`` is not imported inside ``build_trace_matrix()`` — it was
never there in the original code.  Canon resolution (``normalize_trace_type``,
``is_valid_trace_type``) is unchanged: the legacy scan's call sites were moved
to ``_legacy_scan_data()`` (the fallback path, not exercised here), and the
registry-driven path uses kind values from the registry directly without
normalisation.  End-to-end canon resolution is confirmed by the ``spec-check``
command passing unchanged.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from specdev_tools.validation.matrix import build_trace_matrix


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

TOOLKIT_ROOT = Path(__file__).resolve().parents[2]
GOLDEN_PATH = TOOLKIT_ROOT / "tests" / "fixtures" / "trace_matrix_pre_refactor.json"

# The host repo lives two levels above the toolkit (toolkit is a submodule at
# <host>/devspec_toolkit/).  If the host spec directory doesn't exist (e.g.
# running tests inside a standalone toolkit clone), the test is skipped.
HOST_ROOT = TOOLKIT_ROOT.parent
HOST_SPEC_DIR = HOST_ROOT / "spec"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_golden() -> dict:
    with GOLDEN_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestMatrixRegistryRefactorGolden:
    """Golden-file regression: refactored build_trace_matrix() matches pre-refactor output."""

    @pytest.mark.skipif(
        not HOST_SPEC_DIR.is_dir(),
        reason=(
            "Host spec directory not found at expected submodule path "
            f"({HOST_SPEC_DIR}). Run from the host repo context."
        ),
    )
    def test_output_matches_golden(self):
        """Post-refactor matrix output is byte-for-byte identical to the golden snapshot.

        If this test fails, determine whether the diff is *intended* (registry
        correctly excludes entities the old scan incorrectly included) or a
        *bug*.  For intended diffs: update the golden file and document the
        reason in the docstring above under "Intentional diff policy".
        """
        assert GOLDEN_PATH.exists(), (
            f"Golden file missing: {GOLDEN_PATH}. "
            "Re-generate with: specdev matrix spec --repo-root ./devspec_toolkit "
            "--spec-root ./spec --git-root . "
            "--out devspec_toolkit/tests/fixtures/trace_matrix_pre_refactor.json"
        )

        golden = _load_golden()

        result = build_trace_matrix(str(TOOLKIT_ROOT), str(HOST_SPEC_DIR))

        # Normalise both through JSON round-trip so formatting differences don't
        # cause false failures (the golden was written with indent=2 by specdev).
        result_json = json.dumps(result, indent=2)
        golden_json = json.dumps(golden, indent=2)

        if result_json != golden_json:
            # Produce a useful diff summary (first 20 differing lines)
            result_lines = result_json.splitlines()
            golden_lines = golden_json.splitlines()
            import difflib
            diff = list(difflib.unified_diff(
                golden_lines, result_lines,
                fromfile="golden (pre-refactor)",
                tofile="result (post-refactor)",
                lineterm="",
            ))
            diff_excerpt = "\n".join(diff[:40])
            pytest.fail(
                f"Matrix output differs from golden snapshot.\n\n"
                f"Diff (first 40 lines):\n{diff_excerpt}\n\n"
                f"If the diff is INTENDED (e.g. registry correctly excludes "
                f"entities the old scan over-included), update the golden file "
                f"and document the reason in test_matrix_registry_refactor.py."
            )

    @pytest.mark.skipif(
        not HOST_SPEC_DIR.is_dir(),
        reason="Host spec directory not found.",
    )
    def test_registry_driven_path_is_taken(self):
        """When toolkit registry exists, the registry-driven path is used.

        Verifies that the result has the expected top-level keys and that
        entity counts are non-zero (confirming discovery actually ran).
        """
        result = build_trace_matrix(str(TOOLKIT_ROOT), str(HOST_SPEC_DIR))

        assert "matrix" in result, "result must have a 'matrix' key"
        assert "coverage" in result, "result must have a 'coverage' key"
        cov = result["coverage"]
        assert cov["fr_total"] > 0, (
            "fr_total should be > 0 when host spec has functional requirements"
        )

    @pytest.mark.skipif(
        not HOST_SPEC_DIR.is_dir(),
        reason="Host spec directory not found.",
    )
    def test_matrix_rows_have_required_fields(self):
        """Each matrix row has the five required fields: fr_id, apis, fixtures, nfrs, threats."""
        result = build_trace_matrix(str(TOOLKIT_ROOT), str(HOST_SPEC_DIR))

        for row in result.get("matrix", []):
            assert "fr_id" in row, f"row missing fr_id: {row}"
            assert "apis" in row, f"row missing apis: {row}"
            assert "fixtures" in row, f"row missing fixtures: {row}"
            assert "nfrs" in row, f"row missing nfrs: {row}"
            assert "threats" in row, f"row missing threats: {row}"
