"""The shared definitions of `schema/core/collections.schema.json`."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

_COLLECTIONS = Path(__file__).parents[3] / "schema" / "core" / "collections.schema.json"


@pytest.mark.parametrize("value", [5, 1.5, "a", True, None, [1, "a"], {"k": 1}], ids=["integer", "float", "string", "boolean", "null", "array", "object"])
def test_any_json_accepts_each_json_type(value) -> None:
    any_json = json.loads(_COLLECTIONS.read_text(encoding="utf-8"))["$defs"]["anyJson"]
    assert [error.message for error in Draft202012Validator(any_json).iter_errors(value)] == []
