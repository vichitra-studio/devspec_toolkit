"""Tests for the schema path walker (``specdev_tools.registry.schema_paths``)."""
from __future__ import annotations

import pytest

from specdev_tools.registry.schema_paths import (
    PathInfo,
    SchemaPathError,
    flatten_schema,
    index_by_id,
)


def test_walker_keeps_properties_named_description() -> None:
    schema = {
        "$id": "vc:test:step",
        "type": "object",
        "properties": {
            "description": {"type": "string", "description": "a property, not a keyword"},
            "items": {
                "type": "array",
                "items": {"type": "object", "properties": {"description": {"type": "string"}}},
            },
        },
    }

    paths = flatten_schema(schema, index_by_id([schema]))

    assert paths == {
        "description": PathInfo("string", None),
        "items": PathInfo("array", None),
        "items[]": PathInfo("object", None),
        "items[].description": PathInfo("string", None),
    }


def test_walker_expands_core_refs_with_cycle_guard() -> None:
    core = {
        "$id": "vc:core:node",
        "$defs": {
            "node": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "child": {"$ref": "vc:core:node#node"},
                },
            },
            "ident": {"type": "string"},
        },
    }
    step = {
        "$id": "vc:test:step",
        "allOf": [
            {
                "type": "object",
                "properties": {
                    "root": {"$ref": "vc:core:node#node"},
                    "label": {"$ref": "#/$defs/local"},
                    "key": {"$ref": "vc:core:node#ident"},
                },
            }
        ],
        "$defs": {"local": {"type": "string"}},
    }

    paths = flatten_schema(step, index_by_id([core, step]))

    assert paths["root"] == PathInfo("object", "vc:core:node#node")
    assert paths["root.name"] == PathInfo("string", None)
    assert paths["root.child"] == PathInfo("object", "vc:core:node#node")
    assert "root.child.name" not in paths
    assert paths["label"] == PathInfo("string", "#/$defs/local")
    assert paths["key"] == PathInfo("string", "vc:core:node#ident")


def test_walker_records_maps_and_combinator_branches() -> None:
    schema = {
        "$id": "vc:test:step",
        "properties": {
            "env": {"type": "object", "additionalProperties": {"type": "string"}},
            "mode": {"type": ["string", "null"]},
        },
        "if": {"properties": {"a": {"type": "string"}}},
        "then": {"properties": {"b": {"type": "string"}}},
    }

    paths = flatten_schema(schema, index_by_id([schema]))

    assert paths["env{}"] == PathInfo("string", None)
    assert paths["mode"] == PathInfo("null|string", None)
    assert {"a", "b"} <= paths.keys()


def test_walker_include_defs_walks_unreferenced_definitions() -> None:
    core = {"$id": "vc:core:x", "$defs": {"thing": {"type": "object", "properties": {"n": {"type": "string"}}}}}

    paths = flatten_schema(core, index_by_id([core]), include_defs=True)

    assert paths["$defs.thing.n"] == PathInfo("string", None)


def test_walker_rejects_unresolvable_ref() -> None:
    schema = {"$id": "vc:test:step", "properties": {"x": {"$ref": "vc:core:missing#nope"}}}

    with pytest.raises(SchemaPathError):
        flatten_schema(schema, index_by_id([schema]))


def test_walker_records_enum_values() -> None:
    core = {"$id": "vc:core:x", "$defs": {"kind": {"type": "string", "enum": ["b", "a"]}}}
    step = {
        "$id": "vc:test:step",
        "properties": {
            "own": {"type": "string", "enum": ["x", "y"]},
            "via_ref": {"$ref": "vc:core:x#kind"},
            "plain": {"type": "string"},
        },
    }

    paths = flatten_schema(step, index_by_id([core, step]))

    assert paths["own"].enum == ("x", "y")
    assert paths["via_ref"].enum == ("b", "a")
    assert paths["plain"].enum is None
