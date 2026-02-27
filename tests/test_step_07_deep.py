"""Tests for step_07 deep validation: NFR ID uniqueness, stage canonical values, FR traceability."""
import json
import os

import pytest

from specdev_tools.validation.validators.step_07 import validate_step_07


@pytest.fixture
def toolkit_root(tmp_path):
    """Create minimal toolkit layout."""
    spec_dir = tmp_path / "spec"
    spec_dir.mkdir()
    canon_dir = tmp_path / "canon"
    canon_dir.mkdir()
    return str(tmp_path)


class TestValidMinimal:
    def test_empty_nfrs(self, toolkit_root):
        instance = {"nfrs": []}
        errors = validate_step_07(instance, toolkit_root)
        assert errors == []

    def test_valid_single_nfr(self, toolkit_root):
        instance = {
            "nfrs": [
                {"nfr_id": "nfr-perf-01", "stage": "prod"}
            ]
        }
        errors = validate_step_07(instance, toolkit_root)
        assert errors == []


class TestDuplicateId:
    def test_duplicate_nfr_id(self, toolkit_root):
        instance = {
            "nfrs": [
                {"nfr_id": "nfr-perf-01", "stage": "dev"},
                {"nfr_id": "nfr-perf-01", "stage": "prod"},
            ]
        }
        errors = validate_step_07(instance, toolkit_root)
        assert any("Duplicate" in e and "nfr-perf-01" in e for e in errors)


class TestInvalidStage:
    def test_bad_stage(self, toolkit_root):
        instance = {
            "nfrs": [
                {"nfr_id": "nfr-01", "stage": "nonexistent"}
            ]
        }
        errors = validate_step_07(instance, toolkit_root)
        assert any("invalid stage" in e for e in errors)


class TestFrRefConvention:
    def test_non_fr_prefix(self, toolkit_root):
        instance = {
            "nfrs": [
                {"nfr_id": "nfr-01", "stage": "dev", "fr_refs": ["bad-ref"]}
            ]
        }
        errors = validate_step_07(instance, toolkit_root)
        assert any("fr-*" in e for e in errors)

    def test_valid_fr_ref(self, toolkit_root):
        instance = {
            "nfrs": [
                {"nfr_id": "nfr-01", "stage": "dev", "fr_refs": ["fr-login"]}
            ]
        }
        errors = validate_step_07(instance, toolkit_root)
        # Should not flag fr-login as convention error
        assert not any("fr-*" in e for e in errors)


class TestCrossStepFrTraceability:
    def test_unknown_fr_ref(self, toolkit_root):
        """When step 04 exists, unknown FR refs should be flagged."""
        spec_dir = os.path.join(toolkit_root, "spec")
        fr_data = {
            "functional_requirements": [
                {"fr_id": "fr-login"},
                {"fr_id": "fr-logout"},
            ]
        }
        with open(os.path.join(spec_dir, "04_fr_list.json"), "w") as f:
            json.dump(fr_data, f)

        instance = {
            "nfrs": [
                {"nfr_id": "nfr-01", "stage": "dev", "fr_refs": ["fr-login", "fr-nonexistent"]}
            ]
        }
        errors = validate_step_07(instance, toolkit_root)
        assert any("fr-nonexistent" in e for e in errors)
        assert not any("fr-login" in e and "unknown" in e for e in errors)
