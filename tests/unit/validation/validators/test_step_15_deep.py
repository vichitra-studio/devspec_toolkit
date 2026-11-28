"""Deep tests for step 15 (scaffold): the row shape (``row_id``, ``realises``, ``path``) and the validator.

Schema-layer tests run the shipped schema through jsonschema; validator-layer tests call ``validate_step_15``.
No mocking: shipped schema, shipped fixtures.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from specdev_tools.core.registry import SchemaRegistry
from specdev_tools.validation.validators.step_15 import validate_step_15

from ...graph._synth import unique_id_errors

TOOLKIT_ROOT = Path(__file__).resolve().parents[4]
FIXTURES_DIR = TOOLKIT_ROOT / "tests" / "fixtures" / "step_15"

# The design's example row (DOC L1809-1811).
DOC_EXAMPLE_ROW: dict[str, Any] = {
    "row_id": "scaffold-password-reset-confirm",
    "realises": ["api-password-reset-confirm"],
    "path": "src/routes/password-resets/confirm.ts",
}


@pytest.fixture(scope="module")
def schema_validator() -> Draft202012Validator:
    registry = SchemaRegistry(str(TOOLKIT_ROOT))
    return Draft202012Validator(registry.store["vc:15-scaffold"], registry=registry.to_referencing_registry())


@pytest.fixture
def instance() -> dict[str, Any]:
    """The shipped minimal valid scaffold with one row added."""
    base = json.loads((FIXTURES_DIR / "valid_minimal.json").read_text())
    base["interface_map"] = [copy.deepcopy(DOC_EXAMPLE_ROW)]
    return base


def _messages(validator: Draft202012Validator, doc: dict[str, Any]) -> list[str]:
    return [e.message for e in validator.iter_errors(doc)]


def test_doc_example_row_validates(schema_validator, instance) -> None:
    assert _messages(schema_validator, instance) == []
    assert validate_step_15(instance, str(TOOLKIT_ROOT)) == []


def test_old_interface_ref_row_rejected(schema_validator, instance) -> None:
    instance["interface_map"] = [{"interface_ref": "api-password-reset-confirm", "path": "src/a.ts", "method": "POST"}]
    messages = _messages(schema_validator, instance)
    assert any("'row_id' is a required property" in m for m in messages)
    assert any("Additional properties" in m and "interface_ref" in m and "method" in m for m in messages)


def test_row_without_realises_rejected(schema_validator, instance) -> None:
    del instance["interface_map"][0]["realises"]
    assert any("'realises' is a required property" in m for m in _messages(schema_validator, instance))


def test_row_with_empty_realises_rejected(schema_validator, instance) -> None:
    instance["interface_map"][0]["realises"] = []
    assert _messages(schema_validator, instance)


def test_row_without_row_id_rejected(schema_validator, instance) -> None:
    del instance["interface_map"][0]["row_id"]
    assert any("'row_id' is a required property" in m for m in _messages(schema_validator, instance))


@pytest.mark.parametrize("field", ["trace", "links"])
def test_removed_top_level_field_rejected(schema_validator, instance, field: str) -> None:
    instance[field] = []
    assert _messages(schema_validator, instance)


def test_two_rows_may_realise_the_same_api(schema_validator, instance) -> None:
    second = {**DOC_EXAMPLE_ROW, "row_id": "scaffold-password-reset-confirm-test", "path": "tests/confirm.test.ts"}
    instance["interface_map"].append(second)
    assert _messages(schema_validator, instance) == []
    assert validate_step_15(instance, str(TOOLKIT_ROOT)) == []


def test_duplicate_row_id_is_e704(instance) -> None:
    instance["interface_map"].append({**DOC_EXAMPLE_ROW, "realises": ["api-other"], "path": "src/other.ts"})
    assert validate_step_15(instance, str(TOOLKIT_ROOT)) == []
    errors = unique_id_errors({"15_scaffold.json": instance})
    assert [(e.code, e.owner, e.node_id) for e in errors] == [("E704", "step:15", DOC_EXAMPLE_ROW["row_id"])]


def test_green_without_validators_is_e520(instance) -> None:
    instance.update(build_status="green", validators=[])
    assert [e.code for e in validate_step_15(instance, str(TOOLKIT_ROOT))] == ["E520"]


def test_unknown_build_status_is_e530(instance) -> None:
    instance["build_status"] = "blue"
    assert [e.code for e in validate_step_15(instance, str(TOOLKIT_ROOT))] == ["E530"]


@pytest.mark.parametrize(
    "field, value",
    [
        ("interface_map", "rows"),
        ("interface_map", [1, None, ["x"]]),
        ("project_skeleton", ["python"]),
        ("validators", {"a": 1}),
        ("build_status", ["green"]),
        ("build_status", {"x": 1}),
    ],
)
def test_wrong_typed_value_does_not_raise(instance, field: str, value: Any) -> None:
    instance[field] = value
    validate_step_15(instance, str(TOOLKIT_ROOT))


def test_row_id_of_wrong_type_does_not_raise(instance) -> None:
    instance["interface_map"] = [{"row_id": ["a"]}, {"row_id": ["a"]}, {"row_id": 3}]
    assert validate_step_15(instance, str(TOOLKIT_ROOT)) == []


@pytest.mark.parametrize("name", ["valid_minimal.json", "valid_full.json"])
def test_shipped_valid_fixtures_pass(schema_validator, name: str) -> None:
    doc = json.loads((FIXTURES_DIR / name).read_text())
    assert _messages(schema_validator, doc) == []
    assert validate_step_15(doc, str(TOOLKIT_ROOT)) == []
