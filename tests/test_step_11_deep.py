"""Tests for step_11 deep validation: threat_id uniqueness, target cross-ref, mitigations."""
import json
import os
import pytest
from specdev_tools.validation.validators.step_11 import validate_step_11


@pytest.fixture
def toolkit_root(tmp_path):
    spec_dir = tmp_path / "spec"
    spec_dir.mkdir()
    return str(tmp_path)


class TestValidMinimal:
    def test_empty_threats(self, toolkit_root):
        errors = validate_step_11({"threats": []}, toolkit_root)
        assert errors == []

    def test_valid_threat(self, toolkit_root):
        instance = {
            "threats": [{
                "threat_id": "threat-01",
                "target_ids": [{"type": "api", "id": "api-login"}],
                "mitigations": [{"type": "fr", "description": "Rate limiting"}],
            }]
        }
        errors = validate_step_11(instance, toolkit_root)
        # May have cross-ref errors if step files don't exist, but no structural errors
        structural = [e for e in errors if "Duplicate" in e or "invalid target type" in e or "invalid mitigation type" in e]
        assert structural == []


class TestDuplicateThreatId:
    def test_duplicate(self, toolkit_root):
        instance = {
            "threats": [
                {"threat_id": "threat-01", "target_ids": [{"type": "api", "id": "a"}], "mitigations": [{"type": "fr", "description": "x"}]},
                {"threat_id": "threat-01", "target_ids": [{"type": "api", "id": "b"}], "mitigations": [{"type": "fr", "description": "y"}]},
            ]
        }
        errors = validate_step_11(instance, toolkit_root)
        assert any("Duplicate" in e and "threat-01" in e for e in errors)


class TestInvalidTargetType:
    def test_bad_target_type(self, toolkit_root):
        instance = {
            "threats": [{
                "threat_id": "threat-01",
                "target_ids": [{"type": "database", "id": "db-main"}],
                "mitigations": [{"type": "fr", "description": "x"}],
            }]
        }
        errors = validate_step_11(instance, toolkit_root)
        assert any("invalid target type" in e for e in errors)


class TestNoTargets:
    def test_missing_target_ids(self, toolkit_root):
        instance = {
            "threats": [{
                "threat_id": "threat-01",
                "target_ids": [],
                "mitigations": [{"type": "fr", "description": "x"}],
            }]
        }
        errors = validate_step_11(instance, toolkit_root)
        assert any("no target_ids" in e for e in errors)


class TestInvalidMitigationType:
    def test_bad_mitigation_type(self, toolkit_root):
        instance = {
            "threats": [{
                "threat_id": "threat-01",
                "target_ids": [{"type": "api", "id": "api-x"}],
                "mitigations": [{"type": "unknown-type", "description": "x"}],
            }]
        }
        errors = validate_step_11(instance, toolkit_root)
        assert any("invalid mitigation type" in e for e in errors)


class TestNoMitigations:
    def test_empty_mitigations(self, toolkit_root):
        instance = {
            "threats": [{
                "threat_id": "threat-01",
                "target_ids": [{"type": "api", "id": "api-x"}],
                "mitigations": [],
            }]
        }
        errors = validate_step_11(instance, toolkit_root)
        assert any("no mitigations" in e for e in errors)


class TestMitigationMissingFields:
    def test_no_description_or_ref(self, toolkit_root):
        instance = {
            "threats": [{
                "threat_id": "threat-01",
                "target_ids": [{"type": "api", "id": "api-x"}],
                "mitigations": [{"type": "fr"}],
            }]
        }
        errors = validate_step_11(instance, toolkit_root)
        assert any("without description or ref" in e for e in errors)


class TestComponentCrossRef:
    def test_unknown_component(self, toolkit_root):
        """When step 02 exists, unknown component IDs should be flagged."""
        spec_dir = os.path.join(toolkit_root, "spec")
        sketch = {"components": [{"component_id": "comp-auth"}]}
        with open(os.path.join(spec_dir, "02_system_sketch.json"), "w") as f:
            json.dump(sketch, f)

        instance = {
            "threats": [{
                "threat_id": "threat-01",
                "target_ids": [{"type": "component", "id": "comp-nonexistent"}],
                "mitigations": [{"type": "fr", "description": "x"}],
            }]
        }
        errors = validate_step_11(instance, toolkit_root)
        assert any("comp-nonexistent" in e and "unknown component" in e for e in errors)

    def test_known_component(self, toolkit_root):
        spec_dir = os.path.join(toolkit_root, "spec")
        sketch = {"components": [{"component_id": "comp-auth"}]}
        with open(os.path.join(spec_dir, "02_system_sketch.json"), "w") as f:
            json.dump(sketch, f)

        instance = {
            "threats": [{
                "threat_id": "threat-01",
                "target_ids": [{"type": "component", "id": "comp-auth"}],
                "mitigations": [{"type": "fr", "description": "x"}],
            }]
        }
        errors = validate_step_11(instance, toolkit_root)
        assert not any("unknown component" in e for e in errors)


class TestNonObjectMitigation:
    def test_string_mitigation(self, toolkit_root):
        instance = {
            "threats": [{
                "threat_id": "threat-01",
                "target_ids": [{"type": "api", "id": "api-x"}],
                "mitigations": ["just a string"],
            }]
        }
        errors = validate_step_11(instance, toolkit_root)
        assert any("non-object mitigation" in e for e in errors)
