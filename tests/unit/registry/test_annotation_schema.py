"""Tests for the graph annotation language schema (vc:core:graph)."""
from __future__ import annotations

from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from specdev_tools.core.registry import SchemaRegistry

_ROOT = Path(__file__).resolve().parents[3]
_URI = "vc:core:graph"

# The 20 link field names of the design's verb table.
_DOC_VERBS = {
    "derives_from", "refines", "realises", "mitigated_by", "assumes", "constrains",
    "provided_by", "relies_on", "connects_to", "verifies", "verified_by", "threatens",
    "schedules", "justified_by", "depends_on", "part_of", "replaces", "removes", "about", "expects",
}


@pytest.fixture(scope="module")
def registry() -> SchemaRegistry:
    return SchemaRegistry(str(_ROOT))


def _validator(registry: SchemaRegistry, anchor: str) -> Draft202012Validator:
    return Draft202012Validator(
        {"$ref": f"{_URI}#{anchor}"}, registry=registry.to_referencing_registry()
    )


def _ok(registry: SchemaRegistry, anchor: str, instance) -> bool:
    return _validator(registry, anchor).is_valid(instance)


def test_graph_schema_registered_and_valid(registry: SchemaRegistry) -> None:
    assert registry.uri_exists(_URI)
    schema = registry.load(_URI)
    assert schema["$id"] == _URI
    Draft202012Validator.check_schema(schema)
    for name, node in schema["$defs"].items():
        assert node["$anchor"] == name


NODE_OK = [
    {"kind": "fr", "id": "fr_id", "role": "obligation-system",
     "contract": ["statement", "priority"]},
    {"kind": "criterion", "id": "criterion_id", "role": "verifier", "contract": ["text"]},
    {"kind": "scope-item", "map_keyed": True, "role": "obligation-system",
     "contract": ["text"], "coarse": True, "step": "00"},
    {"kind": "plan-item", "id": "item_id", "role": "plan", "contract": ["a"],
     "files": ["impl_context/ms_*_plan.json"], "step": "16"},
    {"kind": "seed", "id": "seed_id", "top_of_graph": True},
]

NODE_BAD = [
    {"kind": "fr", "id": "x", "map_keyed": True, "role": "plan", "contract": ["a"]},
    {"kind": "fr", "role": "plan", "contract": ["a"]},
    {"kind": "seed", "id": "x", "role": "plan", "top_of_graph": True},
    {"kind": "fr", "id": "x", "role": "seed", "contract": ["a"]},
    {"kind": "fr", "id": "x", "role": "plan", "contract": ["a"], "bogus": 1},
    {"kind": "fr", "id": "x", "role": "plan"},
    {"kind": "FR", "id": "x", "role": "plan", "contract": ["a"]},
    {"kind": "fr", "id": "x", "top_of_graph": True},
    {"id": "x", "role": "plan", "contract": ["a"]},
]


@pytest.mark.parametrize("instance", NODE_OK)
def test_xnode_accepts(registry, instance) -> None:
    assert _ok(registry, "xNode", instance)


@pytest.mark.parametrize("instance", NODE_BAD)
def test_xnode_rejects(registry, instance) -> None:
    assert not _ok(registry, "xNode", instance)


@pytest.mark.parametrize("instance", [
    {"kinds": ["capability"], "required": True, "built": True},
    {"kinds": ["need", "seed"], "required": False, "same_step_kinds": ["need"]},
    {"kinds": "*", "required": False},
])
def test_xlink_accepts(registry, instance) -> None:
    assert _ok(registry, "xLink", instance)


@pytest.mark.parametrize("instance", [
    {"kinds": [], "required": True},
    {"kinds": ["a", "*"], "required": True},
    {"kinds": ["a"], "required": True, "bogus": 1},
    {"kinds": ["a"]},
    {"kinds": "fr", "required": True},
])
def test_xlink_rejects(registry, instance) -> None:
    assert not _ok(registry, "xLink", instance)


def test_link_verb_set_matches_design(registry) -> None:
    verbs = registry.load(_URI)["$defs"]["linkVerb"]["enum"]
    assert len(verbs) == 20 and set(verbs) == _DOC_VERBS
    assert _ok(registry, "linkVerb", "about")
    assert not _ok(registry, "linkVerb", "trace")


def test_node_id_accepts_both_forms(registry) -> None:
    assert _ok(registry, "nodeId", "fr-user-login")
    assert _ok(registry, "nodeId", "NFR_LATENCY")
    assert not _ok(registry, "nodeId", "Mixed-Case_x")


def test_lifecycle_enum(registry) -> None:
    for v in ("active", "deprecated", "not_applicable"):
        assert _ok(registry, "lifecycle", v)
    assert not _ok(registry, "lifecycle", "retired")


def _item_validator(registry: SchemaRegistry) -> Draft202012Validator:
    item = {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "lifecycle": {"$ref": f"{_URI}#lifecycle"},
            "scope": {"$ref": f"{_URI}#scope"},
            "scope_reason": {"$ref": f"{_URI}#scopeReason"},
        },
        "allOf": [{"$ref": f"{_URI}#scopeReasonRule"}],
        "additionalProperties": False,
    }
    return Draft202012Validator(item, registry=registry.to_referencing_registry())


def test_scope_reason_rule(registry) -> None:
    v = _item_validator(registry)
    assert v.is_valid({"id": "a", "scope": "in"})
    assert v.is_valid({"id": "a"})
    assert v.is_valid({"id": "a", "scope": "out", "scope_reason": "not needed"})
    assert v.is_valid({"id": "a", "scope": "later", "scope_reason": "v2"})
    for scope in ("later", "out"):
        errs = [e.message for e in v.iter_errors({"id": "a", "scope": scope})]
        assert any("'scope_reason' is a required property" in m for m in errs)
    assert not v.is_valid({"id": "a", "scope": "out", "scope_reason": ""})
    assert not v.is_valid({"id": "a", "scope": "maybe"})
    assert not v.is_valid({"id": "a", "unknown": 1})
