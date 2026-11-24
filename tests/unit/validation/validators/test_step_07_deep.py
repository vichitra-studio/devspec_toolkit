"""Tests for step_07 deep validation: NFR ID uniqueness, stage canonical values."""
import pytest

from specdev_tools.validation.validators.step_07 import validate_step_07

from ...graph._synth import unique_id_errors


def _render(errors):
    """Render SpecError list to strings for assertion convenience."""
    return [e.render() for e in errors]


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


    def test_validator_does_not_check_the_nfr_id_pattern(self, toolkit_root):
        instance = {"nfrs": [{"nfr_id": "nfr-latency", "stage": "prod"}]}
        assert validate_step_07(instance, toolkit_root) == []


class TestDuplicateId:
    def test_duplicate_nfr_id(self, toolkit_root):
        instance = {
            "nfrs": [
                {"nfr_id": "nfr-perf-01", "stage": "dev"},
                {"nfr_id": "nfr-perf-01", "stage": "prod"},
            ]
        }
        assert validate_step_07(instance, toolkit_root) == []
        errors = unique_id_errors({"07_nfrs.json": instance})
        assert [(e.code, e.owner, e.node_id) for e in errors] == [("E704", "step:07", "nfr-perf-01")]


class TestInvalidStage:
    def test_bad_stage(self, toolkit_root):
        instance = {
            "nfrs": [
                {"nfr_id": "nfr-01", "stage": "nonexistent"}
            ]
        }
        errors = validate_step_07(instance, toolkit_root)
        rendered = _render(errors)
        assert any("invalid stage" in e for e in rendered)
