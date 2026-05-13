"""Unit tests for LLM response JSON schemas.

Asserts:
- Each schema loads as valid JSON Schema (draft 2020-12).
- Happy fixtures validate against their schema.
- INVALID fixture is rejected by pointer_response schema.
- Bundle schema validates happy, partial, and failure fixtures.
- No 'content' key is permitted in scoped_entries items (structural probe).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SCHEMAS_DIR = (
    Path(__file__).parents[3]
    / "tools" / "specdev_tools" / "llm" / "schemas"
)
FIXTURES_DIR = (
    Path(__file__).parents[3]
    / "tools" / "specdev_tools" / "llm" / "test_fixtures" / "llm_responses"
)

SCHEMA_FILES = [
    "pointer_response.schema.json",
    "edit_response.schema.json",
    "remediation_response.schema.json",
    "bundle_response.schema.json",
]

# Map schema file → happy fixture file
HAPPY_FIXTURE_MAP = {
    "pointer_response.schema.json": "pointer_response_happy.json",
    "edit_response.schema.json": "edit_response_happy.json",
    "remediation_response.schema.json": "remediation_response_happy.json",
    "bundle_response.schema.json": "bundle_response_happy.json",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_schema(filename: str) -> dict:
    path = SCHEMAS_DIR / filename
    assert path.exists(), f"Schema not found: {path}"
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _load_fixture(filename: str) -> dict:
    path = FIXTURES_DIR / filename
    assert path.exists(), f"Fixture not found: {path}"
    with path.open(encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Schema self-validity
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("schema_file", SCHEMA_FILES)
def test_schema_is_valid_json_schema_draft_2020_12(schema_file: str) -> None:
    schema = _load_schema(schema_file)
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        pytest.fail(f"{schema_file} is not valid JSON Schema draft 2020-12: {exc}")


# ---------------------------------------------------------------------------
# Happy fixtures validate
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("schema_file,fixture_file", list(HAPPY_FIXTURE_MAP.items()))
def test_happy_fixture_validates(schema_file: str, fixture_file: str) -> None:
    schema = _load_schema(schema_file)
    instance = _load_fixture(fixture_file)
    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors(instance))
    assert not errors, (
        f"Happy fixture {fixture_file} failed validation against {schema_file}:\n"
        + "\n".join(str(e) for e in errors)
    )


# ---------------------------------------------------------------------------
# INVALID fixture is rejected
# ---------------------------------------------------------------------------

def test_pointer_response_with_content_is_rejected() -> None:
    schema = _load_schema("pointer_response.schema.json")
    instance = _load_fixture("pointer_response_with_content_INVALID.json")
    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors(instance))
    assert errors, (
        "Expected pointer_response_with_content_INVALID.json to FAIL validation "
        "but it passed — schema is not blocking 'content' fields on pointer items."
    )


# ---------------------------------------------------------------------------
# Partial pointer response validates
# ---------------------------------------------------------------------------

def test_pointer_response_partial_validates() -> None:
    schema = _load_schema("pointer_response.schema.json")
    instance = _load_fixture("pointer_response_partial.json")
    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors(instance))
    assert not errors, (
        "pointer_response_partial.json failed validation:\n"
        + "\n".join(str(e) for e in errors)
    )


# ---------------------------------------------------------------------------
# Bundle schema validates all three envelope variants
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fixture_file", [
    "bundle_response_happy.json",
    "bundle_response_partial.json",
    "bundle_response_failure.json",
])
def test_bundle_fixtures_validate(fixture_file: str) -> None:
    schema = _load_schema("bundle_response.schema.json")
    instance = _load_fixture(fixture_file)
    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors(instance))
    assert not errors, (
        f"Bundle fixture {fixture_file} failed validation:\n"
        + "\n".join(str(e) for e in errors)
    )


# ---------------------------------------------------------------------------
# No 'content' field is permitted in scoped_entries items
# ---------------------------------------------------------------------------

def test_bundle_schema_rejects_content_in_scoped_entries() -> None:
    """Probe: a bundle with a scoped_entries item that has a 'content' field must fail."""
    schema = _load_schema("bundle_response.schema.json")
    # Build a minimal valid success bundle then inject content into scoped_entries
    instance = {
        "step": "04",
        "task": None,
        "bundle_version": "1",
        "context": {},
        "upstream_structure": {},
        "step_structure_summary": {},
        "scoped_entries": [
            {
                "file": "spec/04_fr_list.json",
                "id": "fr-example-001",
                "jq_path": ".functional_requirements[0]",
                "content": {"fr_id": "fr-example-001"}  # FORBIDDEN
            }
        ],
        "unresolved": [],
        "iterations": {"inner": 0},
        "partial": False,
        "ok": True,
    }
    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors(instance))
    assert errors, (
        "Expected bundle with scoped_entries[0].content to FAIL validation "
        "but it passed — schema is not blocking 'content' on scoped_entries items."
    )


def test_pointer_response_rejects_content_on_pointer_items() -> None:
    """Structural probe: pointer_response schema forbids content on pointer items."""
    schema = _load_schema("pointer_response.schema.json")
    # Try a pointer with extra field
    instance = {
        "pointers": [
            {
                "file": "spec/04_fr_list.json",
                "id": "fr-example-001",
                "content": {"data": "should be forbidden"}
            }
        ]
    }
    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors(instance))
    assert errors, (
        "Expected pointer with 'content' field to FAIL validation but it passed "
        "— pointer_response schema is not enforcing additionalProperties: false."
    )


# ---------------------------------------------------------------------------
# F2 — pointer item mutual exclusivity (id XOR jq_path)
# ---------------------------------------------------------------------------

def test_pointer_response_rejects_both_id_and_jq_path() -> None:
    """oneOf must reject a pointer that sets both id and jq_path simultaneously."""
    schema = _load_schema("pointer_response.schema.json")
    instance = {
        "pointers": [
            {"file": "spec/04.json", "id": "x", "jq_path": ".arr[0]"}
        ]
    }
    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors(instance))
    assert errors, (
        "Expected pointer with both 'id' and 'jq_path' to FAIL validation but it passed "
        "— schema must use oneOf (not anyOf) to enforce mutual exclusivity."
    )


# ---------------------------------------------------------------------------
# N4 — negative tests for edit and remediation schemas
# ---------------------------------------------------------------------------

def test_edit_response_rejects_unknown_field_on_edit_item() -> None:
    """additionalProperties: false must reject an edit item with an extra key."""
    schema = _load_schema("edit_response.schema.json")
    instance = {
        "edits": [
            {"file": "x", "jq_path": ".a", "value": 1, "leaked": True}
        ],
        "rationale": "test"
    }
    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors(instance))
    assert errors, (
        "Expected edit item with extra key 'leaked' to FAIL validation but it passed "
        "— edit_response schema must have additionalProperties: false on edit items."
    )


def test_remediation_response_rejects_non_specdev_command() -> None:
    """cmd pattern ^specdev must reject a command that does not start with 'specdev '."""
    schema = _load_schema("remediation_response.schema.json")
    instance = {
        "commands": [
            {"cmd": "rm -rf /", "expected_effect": "wipes everything"}
        ],
        "rationale": "test"
    }
    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors(instance))
    assert errors, (
        "Expected command 'rm -rf /' to FAIL validation but it passed "
        "— remediation_response schema must enforce pattern '^specdev ' on cmd field."
    )
