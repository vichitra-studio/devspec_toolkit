"""Deep tests for step 13 extension generator: validator-layer + schema-layer.

Validator-layer tests call validate_step_13() directly.
Schema-layer tests load the shipped schema via the registry and run jsonschema.validate.
No mocking. All tests use real shipped schemas and fixtures.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from specdev_tools.core.registry import SchemaRegistry
from specdev_tools.validation.validators.step_13 import validate_step_13

TOOLKIT_ROOT = Path(__file__).resolve().parents[4]
FIXTURES_DIR = TOOLKIT_ROOT / "tests" / "fixtures" / "step_13"


def _render(errors):
    return [e.render() for e in errors]


@pytest.fixture
def schema_validator():
    """Build a Draft202012 validator against the shipped step 13 schema."""
    registry = SchemaRegistry(str(TOOLKIT_ROOT))
    ref_registry = registry.to_referencing_registry()
    schema = registry.store["vc:13-extension-generator"]
    return Draft202012Validator(schema, registry=ref_registry)


@pytest.fixture
def base_extension():
    """Minimal valid extension dict for validator-layer tests."""
    return {
        "extension_id": "ext-01-test",
        "justification": "Test justification text.",
        "required_schema_sections": ["tables"],
        "governance_label_ref": {"id": "cn:core:governance_label:mandatory", "kind": "governance_label"},
    }


@pytest.fixture
def valid_instance():
    """Load the shipped valid_manifest.json fixture."""
    return json.loads((FIXTURES_DIR / "valid_manifest.json").read_text())


@pytest.fixture
def none_required_instance():
    """Load the shipped valid_none_required.json fixture."""
    return json.loads((FIXTURES_DIR / "valid_none_required.json").read_text())


# ---------------------------------------------------------------------------
# Validator-layer tests (call validate_step_13 directly)
# ---------------------------------------------------------------------------

class TestValidatorJustification:
    def test_missing_justification_raises_e320(self, base_extension):
        del base_extension["justification"]
        instance = {"extensions": [base_extension]}
        errors = validate_step_13(instance, str(TOOLKIT_ROOT))
        rendered = _render(errors)
        assert any("E320" in e and "justification" in e for e in rendered)


class TestValidatorCrossStep:
    def test_governance_label_not_in_step_10_raises_e590(self, base_extension):
        """When spec_root points at fixture dir with 10_governance.json, unknown label → E590."""
        base_extension["governance_label_ref"] = {
            "id": "cn:core:governance_label:nonexistent",
            "kind": "governance_label",
        }
        instance = {"extensions": [base_extension]}
        errors = validate_step_13(instance, str(TOOLKIT_ROOT), spec_root=str(FIXTURES_DIR))
        rendered = _render(errors)
        assert any("E590" in e and "nonexistent" in e for e in rendered)

    def test_governance_label_in_step_10_passes(self, base_extension):
        """When spec_root points at fixture dir, known label → no E590."""
        instance = {"extensions": [base_extension]}
        errors = validate_step_13(instance, str(TOOLKIT_ROOT), spec_root=str(FIXTURES_DIR))
        rendered = _render(errors)
        assert not any("E590" in e for e in rendered)

    def test_no_step_10_file_raises_w590(self, base_extension, tmp_path):
        """When spec_root points at a dir with no 10_*.json and extensions exist → W590."""
        instance = {"extensions": [base_extension]}
        errors = validate_step_13(instance, str(TOOLKIT_ROOT), spec_root=str(tmp_path))
        rendered = _render(errors)
        assert any("W590" in e for e in rendered)


# ---------------------------------------------------------------------------
# Schema-layer tests (jsonschema.validate against shipped schema)
# ---------------------------------------------------------------------------

class TestSchemaDesignGuidelines:
    def test_missing_keyword_fails_pattern(self, schema_validator):
        """schema_design_guidelines without verification keyword → pattern violation."""
        instance = json.loads((FIXTURES_DIR / "valid_manifest.json").read_text())
        instance["extensions"][0]["schema_design_guidelines"] = (
            "Reuse vc:core:atoms for IDs. Follow standard naming conventions for all fields."
        )
        errors = list(schema_validator.iter_errors(instance))
        pattern_errors = [e for e in errors if "pattern" in e.message.lower() or e.validator == "pattern"]
        assert len(pattern_errors) > 0

    def test_keyword_present_passes(self, schema_validator, valid_instance):
        """schema_design_guidelines with verification keyword → passes."""
        errors = list(schema_validator.iter_errors(valid_instance))
        pattern_errors = [e for e in errors if e.validator == "pattern"]
        assert len(pattern_errors) == 0


class TestSchemaVerificationRulesRejected:
    def test_verification_rules_fails_additional_properties(self, schema_validator, valid_instance):
        """Writing verification_rules should fail additionalProperties: false on items."""
        valid_instance["extensions"][0]["verification_rules"] = ["some rule"]
        errors = list(schema_validator.iter_errors(valid_instance))
        rejected = [e for e in errors if "additional" in e.message.lower() and "verification_rules" in e.message]
        assert len(rejected) > 0


class TestSchemaExtensionDecision:
    def test_none_required_empty_passes(self, schema_validator, none_required_instance):
        errors = list(schema_validator.iter_errors(none_required_instance))
        assert errors == []

    def test_missing_extension_decision_fails(self, schema_validator):
        instance = json.loads((FIXTURES_DIR / "invalid_empty_no_decision.json").read_text())
        errors = list(schema_validator.iter_errors(instance))
        assert len(errors) > 0
        assert any("extension_decision" in e.message for e in errors)

    def test_none_required_with_extensions_fails(self, schema_validator):
        instance = json.loads((FIXTURES_DIR / "invalid_status_mismatch_2.json").read_text())
        errors = list(schema_validator.iter_errors(instance))
        max_items_errors = [e for e in errors if e.validator == "maxItems"]
        assert len(max_items_errors) > 0, f"Expected maxItems error, got: {[e.validator for e in errors]}"

    def test_extensions_required_empty_fails(self, schema_validator):
        instance = json.loads((FIXTURES_DIR / "invalid_status_mismatch.json").read_text())
        errors = list(schema_validator.iter_errors(instance))
        min_items_errors = [e for e in errors if e.validator == "minItems"]
        assert len(min_items_errors) > 0, f"Expected minItems error, got: {[e.validator for e in errors]}"

    def test_extensions_required_populated_passes(self, schema_validator, valid_instance):
        errors = list(schema_validator.iter_errors(valid_instance))
        assert errors == []


class TestSchemaGovernanceLabelRef:
    def test_missing_governance_label_ref_fails(self, schema_validator, valid_instance):
        del valid_instance["extensions"][0]["governance_label_ref"]
        errors = list(schema_validator.iter_errors(valid_instance))
        required_errors = [e for e in errors if e.validator == "required" and "governance_label_ref" in e.message]
        assert len(required_errors) > 0


# ---------------------------------------------------------------------------
# D7 — Additional coverage: validator E520, E320 pattern, schema constraints
# ---------------------------------------------------------------------------

class TestValidatorSectionErrors:
    def test_missing_required_schema_sections_raises_e520(self, base_extension):
        """Extension with no required_schema_sections → E520."""
        del base_extension["required_schema_sections"]
        instance = {"extensions": [base_extension]}
        errors = validate_step_13(instance, str(TOOLKIT_ROOT))
        rendered = _render(errors)
        assert any("E520" in e for e in rendered)

    def test_invalid_section_name_raises_e320(self, base_extension):
        """Section name that fails identifier pattern → E320."""
        base_extension["required_schema_sections"] = ["!!!invalid"]
        instance = {"extensions": [base_extension]}
        errors = validate_step_13(instance, str(TOOLKIT_ROOT))
        rendered = _render(errors)
        assert any("E320" in e and "not a valid identifier" in e for e in rendered)


class TestValidatorDuplicateExtensionId:
    def test_duplicate_extension_id_raises_error(self, base_extension):
        """Two extensions with the same extension_id → duplicate error."""
        base_extension["extension_id"] = "ext-01-dup"
        instance = {"extensions": [base_extension, base_extension.copy()]}
        errors = validate_step_13(instance, str(TOOLKIT_ROOT))
        rendered = _render(errors)
        assert any("E520" in e and "ext-01-dup" in e for e in rendered)


class TestValidatorNoW590WhenEmpty:
    def test_empty_extensions_skips_cross_step(self, tmp_path):
        """When extensions is empty, no W590 even if 10_*.json is missing."""
        instance = {"extensions": []}
        errors = validate_step_13(instance, str(TOOLKIT_ROOT), spec_root=str(tmp_path))
        rendered = _render(errors)
        assert not any("W590" in e for e in rendered)


class TestSchemaRationaleMinLength:
    def test_short_rationale_fails(self, schema_validator, valid_instance):
        """extension_decision.rationale shorter than 40 chars → minLength violation."""
        valid_instance["extension_decision"]["rationale"] = "Too short."
        errors = list(schema_validator.iter_errors(valid_instance))
        min_len_errors = [e for e in errors if e.validator == "minLength"]
        assert len(min_len_errors) > 0


class TestSchemaExtensionIdPattern:
    def test_malformed_extension_id_fails(self, schema_validator, valid_instance):
        """extension_id not matching ^ext-[0-9]{2}-[a-z0-9-]+$ → pattern violation."""
        valid_instance["extensions"][0]["extension_id"] = "bad-id-format"
        errors = list(schema_validator.iter_errors(valid_instance))
        pattern_errors = [e for e in errors if e.validator == "pattern"]
        assert len(pattern_errors) > 0


class TestSchemaDesignGuidelinesMinLength:
    def test_short_guidelines_fails(self, schema_validator, valid_instance):
        """schema_design_guidelines shorter than 40 chars → minLength violation."""
        valid_instance["extensions"][0]["schema_design_guidelines"] = "Check it."
        errors = list(schema_validator.iter_errors(valid_instance))
        min_len_errors = [e for e in errors if e.validator == "minLength"]
        assert len(min_len_errors) > 0


# ---------------------------------------------------------------------------
# F5 — Schema coverage gaps: constraints that lacked dedicated tests
# ---------------------------------------------------------------------------

class TestSchemaGovernanceLabelRefKind:
    def test_wrong_kind_fails(self, schema_validator, valid_instance):
        """governance_label_ref.kind != 'governance_label' → const violation."""
        valid_instance["extensions"][0]["governance_label_ref"]["kind"] = "tag"
        errors = list(schema_validator.iter_errors(valid_instance))
        const_errors = [e for e in errors if e.validator == "const"]
        assert len(const_errors) > 0, f"Expected const error, got: {[e.validator for e in errors]}"


class TestSchemaRequiredItemProperties:
    """Schema requires 7 properties on each extension item."""

    @pytest.mark.parametrize("field", [
        "extension_id", "title", "area_of_concern", "justification",
        "required_schema_sections", "schema_design_guidelines",
    ])
    def test_missing_required_field_fails(self, schema_validator, valid_instance, field):
        """Removing any required extension field → required violation."""
        del valid_instance["extensions"][0][field]
        errors = list(schema_validator.iter_errors(valid_instance))
        required_errors = [e for e in errors if e.validator == "required" and field in e.message]
        assert len(required_errors) > 0, f"Expected required error for '{field}', got: {[e.message for e in errors]}"


class TestSchemaExtensionDecisionStatusEnum:
    def test_invalid_status_fails(self, schema_validator, valid_instance):
        """extension_decision.status not in enum → enum violation."""
        valid_instance["extension_decision"]["status"] = "maybe"
        errors = list(schema_validator.iter_errors(valid_instance))
        enum_errors = [e for e in errors if e.validator == "enum"]
        assert len(enum_errors) > 0, f"Expected enum error, got: {[e.validator for e in errors]}"


class TestSchemaRequiredSectionsMinItems:
    def test_empty_sections_fails(self, schema_validator, valid_instance):
        """required_schema_sections: [] → minItems violation."""
        valid_instance["extensions"][0]["required_schema_sections"] = []
        errors = list(schema_validator.iter_errors(valid_instance))
        min_items_errors = [e for e in errors if e.validator == "minItems"]
        assert len(min_items_errors) > 0, f"Expected minItems error, got: {[e.validator for e in errors]}"


class TestSchemaAdditionalPropertiesArbitrary:
    def test_arbitrary_key_rejected(self, schema_validator, valid_instance):
        """Arbitrary unknown key on extension item → additionalProperties violation."""
        valid_instance["extensions"][0]["foo_bar_baz"] = "should be rejected"
        errors = list(schema_validator.iter_errors(valid_instance))
        additional_errors = [e for e in errors if "additional" in e.message.lower()]
        assert len(additional_errors) > 0, f"Expected additionalProperties error, got: {[e.message for e in errors]}"


# ---------------------------------------------------------------------------
# F6 — Fixture-based test: use orphaned invalid_missing_ref.json
# ---------------------------------------------------------------------------

class TestValidatorFixtureMissingRef:
    def test_invalid_missing_ref_fixture_raises_e590(self):
        """Shipped invalid_missing_ref.json fixture triggers E590 for nonexistent label."""
        instance = json.loads((FIXTURES_DIR / "invalid_missing_ref.json").read_text())
        errors = validate_step_13(instance, str(TOOLKIT_ROOT), spec_root=str(FIXTURES_DIR))
        rendered = _render(errors)
        assert any("E590" in e and "nonexistent" in e for e in rendered)
