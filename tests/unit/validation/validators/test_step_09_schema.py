"""Schema-level tests for step 09 impl_plan fixtures.

Covers:
  - invalid_status_ref_on_milestone.json: schema must REJECT a milestone with an
    unexpected `status_ref` property (additionalProperties: false violation).
  - valid_minimal.json: schema must ACCEPT the minimal positive fixture (zero
    errors) under the post-DEVSPEC-38 step_09 schema, including the milestones
    minItems:1 constraint.
"""
from __future__ import annotations

import json
import pathlib

from specdev_tools.core.schema_validate import validate_data_against_schema

_TOOLKIT_ROOT = str(pathlib.Path(__file__).resolve().parents[4])
_FIXTURES_DIR = pathlib.Path(_TOOLKIT_ROOT) / "tests" / "fixtures" / "step_09"


class TestStep09MilestoneAdditionalProperties:
    """additionalProperties: false on milestone items rejects unknown properties."""

    def test_invalid_status_ref_on_milestone_is_rejected(self) -> None:
        """invalid_status_ref_on_milestone.json must fail schema validation.

        The fixture contains a `status_ref` object inside milestones[0].
        The milestone schema declares additionalProperties: false, so this
        property is not allowed.  Exactly one schema error is expected, and it
        must mention 'status_ref'.
        """
        doc = json.loads((_FIXTURES_DIR / "invalid_status_ref_on_milestone.json").read_text())
        errors = validate_data_against_schema(_TOOLKIT_ROOT, doc)

        assert len(errors) > 0, (
            "Expected schema validation to reject invalid_status_ref_on_milestone.json "
            "but got no errors — the fixture was incorrectly accepted."
        )

        error_messages = " ".join(msg for _, msg in errors)
        assert "status_ref" in error_messages, (
            f"Expected 'status_ref' in validation error message; got: {error_messages!r}"
        )

    def test_invalid_status_ref_error_is_additional_properties(self) -> None:
        """The rejection must be an 'Additional properties are not allowed' error.

        This confirms the error comes from additionalProperties: false on the
        milestone item schema, not from some other constraint.
        """
        doc = json.loads((_FIXTURES_DIR / "invalid_status_ref_on_milestone.json").read_text())
        errors = validate_data_against_schema(_TOOLKIT_ROOT, doc)

        assert len(errors) == 1, (
            f"Expected exactly 1 schema error; got {len(errors)}: {errors!r}"
        )

        _, message = errors[0]
        assert "Additional properties are not allowed" in message, (
            f"Expected 'Additional properties are not allowed' in error message; got: {message!r}"
        )
        assert "status_ref" in message, (
            f"Expected 'status_ref' to be named in the error message; got: {message!r}"
        )


class TestStep09ValidMinimal:
    """The minimal positive fixture must validate cleanly under the step_09 schema."""

    def test_valid_minimal_has_zero_schema_errors(self) -> None:
        """valid_minimal.json must produce ZERO schema errors.

        Positive conformance for the minimal step_09 impl_plan fixture. The
        pre-DEVSPEC-38 fixture had milestones:[] which silently violated the
        schema's minItems:1 (never exercised by any test); this guards the
        corrected fixture (one real milestone) against regression and confirms
        the minimal shape remains schema-valid.
        """
        doc = json.loads((_FIXTURES_DIR / "valid_minimal.json").read_text())
        errors = validate_data_against_schema(_TOOLKIT_ROOT, doc)

        assert errors == [], (
            f"valid_minimal.json must validate cleanly under the step_09 schema; "
            f"got {len(errors)} error(s): {errors!r}"
        )
