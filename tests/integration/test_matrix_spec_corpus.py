"""Integration test: build_trace_matrix() against the spec_corpus fixture directory.

W4-T3 — Standalone matrix test using the minimal spec_corpus fixture set.

Strategy
--------
Unlike ``test_matrix_registry_refactor.py`` (which requires the host repo),
this test runs against ``tests/fixtures/spec_corpus/`` — a self-contained
minimal corpus of spec files with one entity per relevant kind.

This allows the matrix golden-file test to run in standalone toolkit clones
(e.g. CI on the toolkit repo itself) without a host repo present.

Acceptance criteria
-------------------
- ``build_trace_matrix()`` returns a non-empty matrix (at least one row).
- Each row has the five required fields: fr_id, apis, fixtures, nfrs, threats.
- Coverage fr_total > 0.
- The registry-driven path is exercised (FR-CORPUS-001 → API-CORPUS-001 link
  is present, confirming registry-driven entity indexing, not legacy scan).

The corpus contains:
  - 04_fr_list.json       → FR-CORPUS-001 (kind: fr)
  - 05_interface_contracts.json → API-CORPUS-001 (kind: api, traces FR-CORPUS-001)
  - 07_nfrs.json          → NFR-CORPUS-001 (kind: nfr, traces API-CORPUS-001)
  - 08_fixtures.json      → FIX-CORPUS-001 (kind: fixture, targets API-CORPUS-001)
  - 11_redteam.json       → THR-CORPUS-001 (kind: threat, targets API-CORPUS-001)
"""
from __future__ import annotations

from pathlib import Path

from specdev_tools.validation.matrix import build_trace_matrix


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

TOOLKIT_ROOT = Path(__file__).resolve().parents[2]
SPEC_CORPUS_DIR = TOOLKIT_ROOT / "tests" / "fixtures" / "spec_corpus"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestMatrixSpecCorpus:
    """Matrix smoke-tests against the self-contained spec_corpus fixture set."""

    def test_spec_corpus_dir_exists(self):
        """Fixture directory exists and contains at least one spec file."""
        assert SPEC_CORPUS_DIR.is_dir(), (
            f"spec_corpus directory missing: {SPEC_CORPUS_DIR}. "
            "Create at least 04_fr_list.json and 05_interface_contracts.json."
        )
        json_files = list(SPEC_CORPUS_DIR.glob("*.json"))
        assert len(json_files) >= 2, (
            f"spec_corpus should contain at least 2 spec files; found {len(json_files)}: "
            f"{[f.name for f in json_files]}"
        )

    def test_matrix_non_empty(self):
        """build_trace_matrix() returns at least one matrix row from spec_corpus."""
        result = build_trace_matrix(str(TOOLKIT_ROOT), str(SPEC_CORPUS_DIR))

        assert "matrix" in result, "result must have a 'matrix' key"
        assert "coverage" in result, "result must have a 'coverage' key"

        matrix = result["matrix"]
        assert len(matrix) > 0, (
            "Matrix is empty — build_trace_matrix found no FRs in spec_corpus. "
            "Ensure 04_fr_list.json contains at least one entry with fr_id."
        )

    def test_coverage_fr_total_positive(self):
        """Coverage.fr_total is positive (registry-driven discovery found the corpus FR)."""
        result = build_trace_matrix(str(TOOLKIT_ROOT), str(SPEC_CORPUS_DIR))
        cov = result["coverage"]
        assert cov["fr_total"] > 0, (
            f"fr_total should be > 0; got {cov['fr_total']}. "
            "Check that 04_fr_list.json is well-formed and registry maps it to kind 'fr'."
        )

    def test_matrix_rows_have_required_fields(self):
        """Each matrix row has the five required fields: fr_id, apis, fixtures, nfrs, threats."""
        result = build_trace_matrix(str(TOOLKIT_ROOT), str(SPEC_CORPUS_DIR))
        for row in result.get("matrix", []):
            assert "fr_id" in row, f"row missing fr_id: {row}"
            assert "apis" in row, f"row missing apis: {row}"
            assert "fixtures" in row, f"row missing fixtures: {row}"
            assert "nfrs" in row, f"row missing nfrs: {row}"
            assert "threats" in row, f"row missing threats: {row}"

    def test_fr_corpus_001_links_to_api(self):
        """FR-CORPUS-001 links to API-CORPUS-001 via registry-driven entity indexing."""
        result = build_trace_matrix(str(TOOLKIT_ROOT), str(SPEC_CORPUS_DIR))
        fr_row = next(
            (r for r in result["matrix"] if r["fr_id"] == "FR-CORPUS-001"), None
        )
        assert fr_row is not None, (
            "FR-CORPUS-001 not found in matrix. "
            "Check that 04_fr_list.json has functional_requirements[0].fr_id='FR-CORPUS-001'."
        )
        assert "API-CORPUS-001" in fr_row["apis"], (
            f"FR-CORPUS-001 should link to API-CORPUS-001 via api.trace; "
            f"got apis={fr_row['apis']}. "
            "Check that 05_interface_contracts.json has trace=[{{type:fr, id:FR-CORPUS-001}}]."
        )

    def test_fr_corpus_001_links_to_fixture_and_nfr_and_threat(self):
        """FR-CORPUS-001 transitively links to fixture, NFR, and threat via API-CORPUS-001."""
        result = build_trace_matrix(str(TOOLKIT_ROOT), str(SPEC_CORPUS_DIR))
        fr_row = next(
            (r for r in result["matrix"] if r["fr_id"] == "FR-CORPUS-001"), None
        )
        assert fr_row is not None, "FR-CORPUS-001 not found in matrix"

        assert "FIX-CORPUS-001" in fr_row["fixtures"], (
            f"FR-CORPUS-001 should transitively link to FIX-CORPUS-001; "
            f"got fixtures={fr_row['fixtures']}"
        )
        assert "NFR-CORPUS-001" in fr_row["nfrs"], (
            f"FR-CORPUS-001 should transitively link to NFR-CORPUS-001; "
            f"got nfrs={fr_row['nfrs']}"
        )
        assert "THR-CORPUS-001" in fr_row["threats"], (
            f"FR-CORPUS-001 should transitively link to THR-CORPUS-001; "
            f"got threats={fr_row['threats']}"
        )

    def test_milestone_coverage_includes_corpus_fr(self):
        """milestone_coverage maps FR-CORPUS-001 to MS-CORPUS-001 (registry kind: milestone)."""
        result = build_trace_matrix(str(TOOLKIT_ROOT), str(SPEC_CORPUS_DIR))
        assert "milestone_coverage" in result, (
            "milestone_coverage key missing from build_trace_matrix result. "
            "Ensure 14_roadmap.json is present in spec_corpus/ and has a milestone "
            "with fr_refs=['FR-CORPUS-001']."
        )
        mc = result["milestone_coverage"]
        assert "FR-CORPUS-001" in mc, (
            f"FR-CORPUS-001 not found in milestone_coverage; got keys: {list(mc.keys())}. "
            "Check that 14_roadmap.json milestones[0].fr_refs includes 'FR-CORPUS-001'."
        )
        assert "MS-CORPUS-001" in mc["FR-CORPUS-001"], (
            f"MS-CORPUS-001 not found in milestone_coverage['FR-CORPUS-001']; "
            f"got: {mc['FR-CORPUS-001']}. "
            "Check that 14_roadmap.json milestones[0].milestone_id='MS-CORPUS-001'."
        )
