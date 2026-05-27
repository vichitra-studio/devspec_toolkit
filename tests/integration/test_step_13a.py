"""Integration tests for Step 13a (Completeness Assessment) validator.

Tests cover:
- Valid minimal document passes validation
- Missing dimensions field fires E520
- Ratio below threshold fires W592
- Ratio inconsistency fires E520
- Completeness check output maps to 13a dimensions (data-flow verification)
"""

import json
import os
import tempfile
import unittest
from pathlib import Path

from specdev_tools.validation.validators.step_13a import validate_step_13a
from specdev_tools.validation.traceability_closure import check_traceability_closure


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _render(errors):
    return [e.render() if hasattr(e, "render") else str(e) for e in errors]


def _codes(errors):
    return [e.code if hasattr(e, "code") else "" for e in errors]


def _write_json(directory: str, filename: str, data: dict) -> None:
    with open(os.path.join(directory, filename), "w", encoding="utf-8") as f:
        json.dump(data, f)


def _make_valid_dimensions():
    """Return a dimensions dict with all 4 dimensions fully covered."""
    dim = {
        "covered_count": 1,
        "total_count": 1,
        "ratio": 1.0,
        "uncovered_ids": [],
    }
    return {
        "fr_api_coverage": dict(dim),
        "fr_fixture_coverage": dict(dim),
        "fr_milestone_coverage": dict(dim),
        "capability_fr_coverage": dict(dim),
    }


def _make_valid_instance(dimensions=None):
    """Return a minimal valid 13a instance dict (without $schema, for direct validator calls)."""
    return {
        "id": "completeness-v1",
        "owner": "product",
        "created_at": "2025-01-01T00:00:00Z",
        "canonical_refs_used": [],
        "dimensions": dimensions if dimensions is not None else _make_valid_dimensions(),
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestStep13aIntegration(unittest.TestCase):

    def setUp(self):
        self.toolkit_root = str(Path(__file__).resolve().parents[2])

    # ------------------------------------------------------------------
    # Test 1: valid minimal document passes with no errors
    # ------------------------------------------------------------------

    def test_valid_minimal_13a_passes_validation(self):
        """A well-formed 13a document with all 4 dimensions at 100% should produce no errors."""
        with tempfile.TemporaryDirectory() as tmp:
            spec_dir = os.path.join(tmp, "spec")
            os.makedirs(spec_dir)
            # Provide upstream files so cross-step ID validation passes
            _write_json(spec_dir, "01_capabilities.json", {
                "capabilities": [{"capability_id": "cap-auth"}]
            })
            _write_json(spec_dir, "04_fr_list.json", {
                "functional_requirements": [{"fr_id": "fr-login"}]
            })
            _write_json(spec_dir, "05_interface_contracts.json", {
                "apis": [{"api_id": "api-auth"}]
            })

            instance = _make_valid_instance()
            errors = validate_step_13a(instance, tmp)
            non_warnings = [e for e in errors if hasattr(e, "code") and not e.code.startswith("W")]
            self.assertEqual(
                non_warnings, [],
                f"Valid minimal 13a should pass with no errors. Got: {_render(errors)}"
            )

    # ------------------------------------------------------------------
    # Test 2: missing dimensions field fires E520
    # ------------------------------------------------------------------

    def test_missing_dimensions_fires_error(self):
        """A 13a document without a 'dimensions' field should fire E520."""
        with tempfile.TemporaryDirectory() as tmp:
            spec_dir = os.path.join(tmp, "spec")
            os.makedirs(spec_dir)

            instance = {
                "id": "completeness-v1",
                "owner": "product",
                "created_at": "2025-01-01T00:00:00Z",
                "canonical_refs_used": [],
                # 'dimensions' intentionally omitted
            }
            errors = validate_step_13a(instance, tmp)
            codes = _codes(errors)
            self.assertIn(
                "E520", codes,
                f"Missing 'dimensions' should fire E520. Got: {_render(errors)}"
            )

    # ------------------------------------------------------------------
    # Test 3: ratio below threshold fires W592
    # ------------------------------------------------------------------

    def test_ratio_below_threshold_fires_w592(self):
        """A dimension with ratio=0.5 should fire W592 (coverage below threshold)."""
        with tempfile.TemporaryDirectory() as tmp:
            spec_dir = os.path.join(tmp, "spec")
            os.makedirs(spec_dir)
            _write_json(spec_dir, "04_fr_list.json", {
                "functional_requirements": [
                    {"fr_id": "fr-login"},
                    {"fr_id": "fr-logout"},
                ]
            })
            _write_json(spec_dir, "05_interface_contracts.json", {
                "apis": [{"api_id": "api-auth"}]
            })

            dimensions = _make_valid_dimensions()
            # fr_api_coverage: 1 of 2 FRs covered — ratio 0.5
            dimensions["fr_api_coverage"] = {
                "covered_count": 1,
                "total_count": 2,
                "ratio": 0.5,
                "uncovered_ids": ["fr-logout"],
            }
            instance = _make_valid_instance(dimensions=dimensions)
            errors = validate_step_13a(instance, tmp)
            codes = _codes(errors)
            self.assertIn(
                "W592", codes,
                f"ratio=0.5 should fire W592. Got: {_render(errors)}"
            )

    # ------------------------------------------------------------------
    # Test 4: ratio inconsistency fires E520
    # ------------------------------------------------------------------

    def test_ratio_inconsistency_fires_error(self):
        """A dimension with ratio=1.0 but covered_count=0 and total_count=5 should fire E520."""
        with tempfile.TemporaryDirectory() as tmp:
            spec_dir = os.path.join(tmp, "spec")
            os.makedirs(spec_dir)

            dimensions = _make_valid_dimensions()
            # Ratio claims 1.0 but 0/5 = 0.0 — clear inconsistency
            dimensions["fr_api_coverage"] = {
                "covered_count": 0,
                "total_count": 5,
                "ratio": 1.0,
                "uncovered_ids": ["fr-a", "fr-b", "fr-c", "fr-d", "fr-e"],
            }
            instance = _make_valid_instance(dimensions=dimensions)
            errors = validate_step_13a(instance, tmp)
            codes = _codes(errors)
            self.assertIn(
                "E520", codes,
                f"Ratio inconsistency (ratio=1.0 but 0/5=0.0) should fire E520. Got: {_render(errors)}"
            )
            # Verify the message mentions ratio inconsistency
            rendered = " ".join(_render(errors))
            self.assertIn(
                "RATIO_INCONSISTENCY", rendered,
                f"Error message should mention RATIO_INCONSISTENCY. Got: {rendered}"
            )

    # ------------------------------------------------------------------
    # Test 5: completeness-check output maps to 13a dimensions
    # ------------------------------------------------------------------

    def test_completeness_check_output_maps_to_13a_dimensions(self):
        """Verifies that check_traceability_closure output can derive 13a dimension values.

        Writes minimal spec files (1 FR covered by 1 API), calls check_traceability_closure,
        asserts no W564 (UNCOVERED_FR_API) fires, then constructs a 13a dimensions dict
        reflecting 100% FR→API coverage and validates it passes.
        """
        with tempfile.TemporaryDirectory() as tmp:
            spec_dir = os.path.join(tmp, "spec")
            os.makedirs(spec_dir)

            # Minimal 04_fr_list.json with 1 FR
            _write_json(spec_dir, "04_fr_list.json", {
                "functional_requirements": [
                    {
                        "fr_id": "fr-login",
                        "trace": [{"type": "capability", "id": "cap-auth"}],
                    }
                ]
            })

            # Minimal 01_capabilities.json with 1 capability
            _write_json(spec_dir, "01_capabilities.json", {
                "capabilities": [
                    {
                        "capability_id": "cap-auth",
                        "trace": [],
                    }
                ]
            })

            # 05_interface_contracts.json: 1 API tracing back to fr-login
            _write_json(spec_dir, "05_interface_contracts.json", {
                "apis": [
                    {
                        "api_id": "api-auth",
                        "trace": [{"type": "fr", "id": "fr-login"}],
                    }
                ]
            })

            # Run traceability closure check
            tc_errors = check_traceability_closure(spec_dir)
            tc_codes = [e.code if hasattr(e, "code") else "" for e in tc_errors]

            # W564 = UNCOVERED_FR_API: should NOT fire since fr-login has api-auth
            self.assertNotIn(
                "W564", tc_codes,
                f"W564 should not fire when FR is covered by API. Got: {[_render([e]) for e in tc_errors if hasattr(e, 'code') and e.code == 'W564']}"
            )

            # Derive dimension values: 1 FR, 1 covered → ratio=1.0
            fr_api_dimension = {
                "covered_count": 1,
                "total_count": 1,
                "ratio": 1.0,
                "uncovered_ids": [],
            }

            # Construct 13a dimensions reflecting the completeness check result
            dimensions = {
                "fr_api_coverage": fr_api_dimension,
                "fr_fixture_coverage": {
                    "covered_count": 1,
                    "total_count": 1,
                    "ratio": 1.0,
                    "uncovered_ids": [],
                },
                "fr_milestone_coverage": {
                    "covered_count": 1,
                    "total_count": 1,
                    "ratio": 1.0,
                    "uncovered_ids": [],
                },
                "capability_fr_coverage": {
                    "covered_count": 1,
                    "total_count": 1,
                    "ratio": 1.0,
                    "uncovered_ids": [],
                },
            }

            instance = _make_valid_instance(dimensions=dimensions)
            errors = validate_step_13a(instance, tmp)
            non_errors = [e for e in errors if hasattr(e, "code") and not e.code.startswith("W")]
            self.assertEqual(
                non_errors, [],
                f"13a derived from completeness-check data should validate cleanly. Got: {_render(errors)}"
            )


    # ------------------------------------------------------------------
    # Test 6: DIMENSION_INCONSISTENCY when covered_count > total_count
    # ------------------------------------------------------------------

    def test_dimension_inconsistency_covered_exceeds_total_fires_error(self):
        """covered_count > total_count fires E520 DIMENSION_INCONSISTENCY."""
        with tempfile.TemporaryDirectory() as tmp:
            spec_dir = os.path.join(tmp, "spec")
            os.makedirs(spec_dir)
            dimensions = _make_valid_dimensions()
            dimensions["fr_api_coverage"] = {
                "covered_count": 5,   # exceeds total
                "total_count": 3,
                "ratio": 1.0,
                "uncovered_ids": [],
            }
            instance = _make_valid_instance(dimensions=dimensions)
            errors = validate_step_13a(instance, tmp)
            codes = _codes(errors)
            self.assertIn("E520", codes,
                f"covered_count > total_count should fire E520. Got: {_render(errors)}")
            rendered = " ".join(_render(errors))
            self.assertIn("DIMENSION_INCONSISTENCY", rendered,
                f"Error should mention DIMENSION_INCONSISTENCY. Got: {rendered}")

    # ------------------------------------------------------------------
    # Test 7: Missing individual required dimension fires E520
    # ------------------------------------------------------------------

    def test_missing_individual_required_dimension_fires_error(self):
        """Each missing required dimension key fires a separate E520 MISSING_DIMENSION."""
        with tempfile.TemporaryDirectory() as tmp:
            spec_dir = os.path.join(tmp, "spec")
            os.makedirs(spec_dir)
            # Only provide 3 of 4 required dimensions
            dims = _make_valid_dimensions()
            del dims["capability_fr_coverage"]
            instance = _make_valid_instance(dimensions=dims)
            errors = validate_step_13a(instance, tmp)
            codes = _codes(errors)
            self.assertIn("E520", codes,
                f"Missing capability_fr_coverage should fire E520. Got: {_render(errors)}")
            rendered = " ".join(_render(errors))
            self.assertIn("MISSING_DIMENSION", rendered,
                f"Error should mention MISSING_DIMENSION. Got: {rendered}")
            self.assertIn("capability_fr_coverage", rendered,
                f"Error should mention the missing dimension name. Got: {rendered}")

    # ------------------------------------------------------------------
    # Test 8: E590 for hallucinated FR ID in uncovered_ids
    # ------------------------------------------------------------------

    def test_e590_fires_for_hallucinated_fr_id_in_uncovered_ids(self):
        """A fr-* ID in uncovered_ids that does not exist in 04_fr_list.json fires E590."""
        with tempfile.TemporaryDirectory() as tmp:
            spec_dir = os.path.join(tmp, "spec")
            os.makedirs(spec_dir)
            # Only fr-login exists; fr-hallucinated does not
            _write_json(spec_dir, "04_fr_list.json", {
                "functional_requirements": [{"fr_id": "fr-login"}]
            })
            _write_json(spec_dir, "01_capabilities.json", {
                "capabilities": [{"capability_id": "cap-auth"}]
            })
            _write_json(spec_dir, "05_interface_contracts.json", {
                "apis": [{"api_id": "api-auth"}]
            })
            dimensions = _make_valid_dimensions()
            dimensions["fr_api_coverage"] = {
                "covered_count": 0,
                "total_count": 1,
                "ratio": 0.0,
                "uncovered_ids": ["fr-hallucinated"],  # does not exist in spec
            }
            instance = _make_valid_instance(dimensions=dimensions)
            errors = validate_step_13a(instance, tmp)
            codes = _codes(errors)
            self.assertIn("E590", codes,
                f"Hallucinated fr-hallucinated should fire E590. Got: {_render(errors)}")
            rendered = " ".join(_render(errors))
            self.assertIn("fr-hallucinated", rendered,
                f"E590 message should mention the bad ID. Got: {rendered}")

    # ------------------------------------------------------------------
    # Test 9: W590 for missing upstream file
    # ------------------------------------------------------------------

    def test_w590_fires_when_fr_list_upstream_file_absent(self):
        """When 04_fr_list.json is absent, W590 fires for the missing upstream file."""
        with tempfile.TemporaryDirectory() as tmp:
            spec_dir = os.path.join(tmp, "spec")
            os.makedirs(spec_dir)
            # Provide 01 and 05 but NOT 04
            _write_json(spec_dir, "01_capabilities.json", {
                "capabilities": [{"capability_id": "cap-auth"}]
            })
            _write_json(spec_dir, "05_interface_contracts.json", {
                "apis": [{"api_id": "api-auth"}]
            })
            # Put an fr- ID in uncovered_ids to trigger the validation path
            dimensions = _make_valid_dimensions()
            dimensions["fr_api_coverage"] = {
                "covered_count": 0,
                "total_count": 1,
                "ratio": 0.0,
                "uncovered_ids": ["fr-login"],
            }
            instance = _make_valid_instance(dimensions=dimensions)
            errors = validate_step_13a(instance, tmp)
            codes = _codes(errors)
            self.assertIn("W590", codes,
                f"Missing 04_fr_list.json should fire W590. Got: {_render(errors)}")
            rendered = " ".join(_render(errors))
            self.assertIn("04_fr_list.json", rendered,
                f"W590 message should mention the missing file. Got: {rendered}")

    # ------------------------------------------------------------------
    # Test 10: cap-* IDs cross-validated against 01_capabilities.json
    # ------------------------------------------------------------------

    def test_e590_fires_for_cap_prefixed_capability_id_not_in_spec(self):
        """cap-* IDs in capability_fr_coverage.uncovered_ids are validated against 01_capabilities.json."""
        with tempfile.TemporaryDirectory() as tmp:
            spec_dir = os.path.join(tmp, "spec")
            os.makedirs(spec_dir)
            # cap-real exists; cap-ghost does not
            _write_json(spec_dir, "01_capabilities.json", {
                "capabilities": [{"capability_id": "cap-real"}]
            })
            _write_json(spec_dir, "04_fr_list.json", {
                "functional_requirements": [{"fr_id": "fr-login"}]
            })
            _write_json(spec_dir, "05_interface_contracts.json", {
                "apis": [{"api_id": "api-auth"}]
            })
            dimensions = _make_valid_dimensions()
            dimensions["capability_fr_coverage"] = {
                "covered_count": 0,
                "total_count": 1,
                "ratio": 0.0,
                "uncovered_ids": ["cap-ghost"],  # does not exist in spec
            }
            instance = _make_valid_instance(dimensions=dimensions)
            errors = validate_step_13a(instance, tmp)
            codes = _codes(errors)
            self.assertIn("E590", codes,
                f"Hallucinated cap-ghost should fire E590. Got: {_render(errors)}")
            rendered = " ".join(_render(errors))
            self.assertIn("cap-ghost", rendered,
                f"E590 message should mention the bad ID. Got: {rendered}")


if __name__ == "__main__":
    unittest.main()
