"""Unit tests for schema_nav.effective_schema.

Each test targets one behavioural invariant documented in the plan (§2 WS3,
§3.2, §5 "Unit (schema_nav / discovery)").
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from specdev_tools.core.json_utils import _CONSTRAINT_KEYWORDS, json_schema_discovery
from specdev_tools.core.schema_nav import effective_schema

# ---------------------------------------------------------------------------
# Fixtures / constants for CLI-level regression tests (§10)
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_IMPL_CONTEXT_FIXTURE = str(
    _REPO_ROOT / "tests" / "fixtures" / "step_16" / "impl_context" / "valid_full.json"
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def noop_resolver(node: dict) -> dict:
    """A no-op resolver that returns the node unchanged (no $ref resolution)."""
    return node


def make_stub_resolver(mapping: dict[str, dict]):
    """Return a resolver that looks up ``node["$ref"]`` in *mapping*.

    If the ref is not found, returns the node unchanged (safe fallback).
    """
    def _resolve(node: dict[str, Any]) -> dict:
        ref = node.get("$ref")
        return mapping.get(ref, node) if ref is not None else node
    return _resolve


# ---------------------------------------------------------------------------
# 1. Own-first union — the P2 regression (P2: overwrite bug)
# ---------------------------------------------------------------------------

def test_own_properties_survive_allof_merge():
    """A node with own properties + an allOf branch returns the UNION.

    This is the direct regression test for the P2 overwrite bug: the old
    _effective_schema code did ``base['properties'] = merged_props`` (overwrite),
    discarding the node's own properties.  The correct behaviour is a UNION
    with own-first seed.
    """
    node = {
        "properties": {"own_field": {"type": "string"}},
        "allOf": [
            {"properties": {"branch_field": {"type": "integer"}}},
        ],
    }
    result = effective_schema(node, noop_resolver)
    assert "own_field" in result["properties"], "own property must survive"
    assert "branch_field" in result["properties"], "allOf branch property must be merged"


def test_allof_branch_wins_collision_with_own_property():
    """When own and allOf define the same key, the branch (later) wins.

    merge_allof uses .update() (branch-wins semantics).
    Our helper must match.
    """
    node = {
        "properties": {"shared": {"type": "string", "description": "own"}},
        "allOf": [
            {"properties": {"shared": {"type": "string", "description": "branch"}}},
        ],
    }
    result = effective_schema(node, noop_resolver)
    # Branch-wins (update overwrites)
    assert result["properties"]["shared"]["description"] == "branch"


# ---------------------------------------------------------------------------
# 2. Required accumulation across allOf branches
# ---------------------------------------------------------------------------

def test_required_accumulated_across_branches():
    """required from own + all allOf branches is concatenated (list-concat, no dedup)."""
    node = {
        "properties": {"a": {}, "b": {}, "c": {}},
        "required": ["a"],
        "allOf": [
            {"properties": {"b": {}}, "required": ["b"]},
            {"properties": {"c": {}}, "required": ["c"]},
        ],
    }
    result = effective_schema(node, noop_resolver)
    # Plan: required += e.required  (list-concat, preserves order, no dedup)
    assert result["required"] == ["a", "b", "c"]


def test_required_duplicates_preserved():
    """List-concat semantics: duplicate required entries are NOT deduped."""
    node = {
        "required": ["x"],
        "allOf": [
            {"required": ["x"]},   # duplicate
        ],
    }
    result = effective_schema(node, noop_resolver)
    assert result["required"] == ["x", "x"]


# ---------------------------------------------------------------------------
# 3. Nested allOf (recursion)
# ---------------------------------------------------------------------------

def test_nested_allof_merged_recursively():
    """An allOf branch that itself has allOf is merged recursively."""
    node = {
        "properties": {"root_field": {}},
        "allOf": [
            {
                "properties": {"mid_field": {}},
                "allOf": [
                    {"properties": {"deep_field": {}}, "required": ["deep_field"]},
                ],
            },
        ],
    }
    result = effective_schema(node, noop_resolver)
    assert "root_field" in result["properties"]
    assert "mid_field" in result["properties"]
    assert "deep_field" in result["properties"]
    assert "deep_field" in result["required"]


# ---------------------------------------------------------------------------
# 4. include_conditionals=False (default): oneOf/anyOf/then/else NOT surfaced
# ---------------------------------------------------------------------------

def test_conditionals_not_surfaced_when_flag_off():
    """With include_conditionals=False (default), properties in oneOf/anyOf/then/else
    are NOT merged into the output (the latent-gap behaviour preserved for
    merge_allof callers)."""
    node = {
        "properties": {"base_field": {}},
        "oneOf": [
            {"properties": {"oneof_field": {}}},
        ],
        "anyOf": [
            {"properties": {"anyof_field": {}}},
        ],
        "if": {"properties": {"predicate_field": {}}},
        "then": {"properties": {"then_field": {}}},
        "else": {"properties": {"else_field": {}}},
    }
    result = effective_schema(node, noop_resolver)  # include_conditionals=False by default
    assert "base_field" in result["properties"]
    assert "oneof_field" not in result["properties"]
    assert "anyof_field" not in result["properties"]
    assert "predicate_field" not in result["properties"]
    assert "then_field" not in result["properties"]
    assert "else_field" not in result["properties"]


# ---------------------------------------------------------------------------
# 5. include_conditionals=True: oneOf/anyOf/then/else props ARE surfaced
# ---------------------------------------------------------------------------

def test_conditionals_surfaced_when_flag_on():
    """With include_conditionals=True, properties from oneOf/anyOf/then/else
    are unioned into props."""
    node = {
        "properties": {"base_field": {}},
        "oneOf": [
            {"properties": {"oneof_field": {}}},
        ],
        "anyOf": [
            {"properties": {"anyof_field": {}}},
        ],
        "then": {"properties": {"then_field": {}}},
        "else": {"properties": {"else_field": {}}},
    }
    result = effective_schema(node, noop_resolver, include_conditionals=True)
    assert "base_field" in result["properties"]
    assert "oneof_field" in result["properties"]
    assert "anyof_field" in result["properties"]
    assert "then_field" in result["properties"]
    assert "else_field" in result["properties"]


def test_conditional_fields_not_added_to_required():
    """Properties from oneOf/anyOf/then/else are unioned into props ONLY —
    their fields must NOT appear in required (mutually exclusive / conditional)."""
    node = {
        "oneOf": [
            {"properties": {"option_a": {}}, "required": ["option_a"]},
            {"properties": {"option_b": {}}, "required": ["option_b"]},
        ],
        "then": {"properties": {"then_field": {}}, "required": ["then_field"]},
    }
    result = effective_schema(node, noop_resolver, include_conditionals=True)
    # Props are merged
    assert "option_a" in result["properties"]
    assert "option_b" in result["properties"]
    assert "then_field" in result["properties"]
    # But required from those branches is NOT included
    assert "option_a" not in result["required"]
    assert "option_b" not in result["required"]
    assert "then_field" not in result["required"]


def test_if_predicate_never_surfaced_even_with_conditionals():
    """The 'if' clause is a predicate, never a property source.
    Its properties must NOT appear even with include_conditionals=True."""
    node = {
        "if": {"properties": {"discriminator_field": {"const": "magic"}}},
        "then": {"properties": {"then_only": {}}},
    }
    result = effective_schema(node, noop_resolver, include_conditionals=True)
    assert "discriminator_field" not in result["properties"], (
        "'if' clause must be excluded — it is a predicate, not a property source"
    )
    assert "then_only" in result["properties"]


# ---------------------------------------------------------------------------
# 6. $ref resolution via injected callback
# ---------------------------------------------------------------------------

def test_ref_resolved_via_injected_callback():
    """$ref is resolved by the injected callback, not by any internal mechanism."""
    fake_ref_target = {
        "properties": {"from_ref": {"type": "string"}},
        "required": ["from_ref"],
    }
    stub = make_stub_resolver({"vc:some-schema": fake_ref_target})

    node = {"$ref": "vc:some-schema"}
    result = effective_schema(node, stub)
    assert "from_ref" in result["properties"]
    assert "from_ref" in result["required"]


def test_ref_resolver_is_called():
    """Verify the resolver callback is actually invoked (not silently skipped)."""
    calls = []

    def counting_resolver(node: dict) -> dict:
        calls.append(node)
        return {"properties": {"resolved_prop": {}}, "required": []}

    node = {"$ref": "vc:anything"}
    effective_schema(node, counting_resolver)
    assert len(calls) == 1, "resolver must be called exactly once for a bare $ref node"
    assert calls[0] == node


def test_allof_branch_with_ref_resolved_recursively():
    """An allOf branch that is a bare $ref is resolved via recursion."""
    ref_target = {
        "properties": {"from_allof_ref": {}},
        "required": ["from_allof_ref"],
    }
    stub = make_stub_resolver({"vc:target": ref_target})

    node = {
        "properties": {"own": {}},
        "allOf": [
            {"$ref": "vc:target"},
        ],
    }
    result = effective_schema(node, stub)
    assert "own" in result["properties"]
    assert "from_allof_ref" in result["properties"]
    assert "from_allof_ref" in result["required"]


# ---------------------------------------------------------------------------
# 7. Preservation of non-composition schema keywords
# ---------------------------------------------------------------------------

def test_preserves_type_items_enum_description_additionalproperties():
    """type, items, description, additionalProperties, enum from the (ref-resolved)
    node are carried through into the result."""
    node = {
        "type": "object",
        "description": "a test schema",
        "additionalProperties": False,
        "enum": ["a", "b"],
        "items": {"type": "string"},
        "properties": {"x": {}},
        "allOf": [
            {"properties": {"y": {}}},
        ],
    }
    result = effective_schema(node, noop_resolver)
    assert result["type"] == "object"
    assert result["description"] == "a test schema"
    assert result["additionalProperties"] is False
    assert result["enum"] == ["a", "b"]
    assert result["items"] == {"type": "string"}


def test_composition_keywords_stripped_from_output():
    """allOf, oneOf, anyOf, if, then, else are NOT present in the returned dict
    (ensures idempotency under re-application)."""
    node = {
        "properties": {"a": {}},
        "allOf": [{"properties": {"b": {}}}],
        "oneOf": [{"properties": {"c": {}}}],
        "anyOf": [{"properties": {"d": {}}}],
        "if": {"properties": {"e": {}}},
        "then": {"properties": {"f": {}}},
        "else": {"properties": {"g": {}}},
    }
    result = effective_schema(node, noop_resolver, include_conditionals=True)
    for keyword in ("allOf", "oneOf", "anyOf", "if", "then", "else"):
        assert keyword not in result, f"composition keyword '{keyword}' must be stripped"


def test_idempotent_under_reapplication():
    """Calling effective_schema on its own output produces the same result.

    This is the json_schema_discovery re-call invariant: the path walker calls
    effective_schema on each step's output as it descends.  A non-idempotent
    implementation would accumulate duplicate required entries on each re-call.
    """
    node = {
        "properties": {"a": {}},
        "required": ["a"],
        "allOf": [
            {"properties": {"b": {}}, "required": ["b"]},
        ],
    }
    first = effective_schema(node, noop_resolver)
    second = effective_schema(first, noop_resolver)
    assert first["properties"] == second["properties"]
    assert first["required"] == second["required"]


# ---------------------------------------------------------------------------
# 8. Always-set properties and required (no KeyError for callers)
# ---------------------------------------------------------------------------

def test_always_returns_properties_and_required_keys():
    """Even for an empty / minimal node, properties and required are always present."""
    result = effective_schema({}, noop_resolver)
    assert "properties" in result
    assert "required" in result
    assert result["properties"] == {}
    assert result["required"] == []


def test_node_with_only_type_returns_empty_props_and_required():
    """A schema that is just {type: string} returns empty props/required."""
    result = effective_schema({"type": "string"}, noop_resolver)
    assert result["type"] == "string"
    assert result["properties"] == {}
    assert result["required"] == []


# ---------------------------------------------------------------------------
# 9. Additional plan-§5-named cases
# ---------------------------------------------------------------------------

def test_empty_allof_returns_only_own_properties():
    """An empty allOf list (``allOf: []``) contributes nothing — only own properties."""
    node = {
        "properties": {"own": {"type": "string"}},
        "required": ["own"],
        "allOf": [],
    }
    result = effective_schema(node, noop_resolver)
    assert list(result["properties"].keys()) == ["own"]
    assert result["required"] == ["own"]


def test_ref_with_sibling_allof_merges_resolved_allof():
    """A top-level node with both ``$ref`` and sibling ``allOf`` uses the RESOLVED
    dict's allOf for merging — the original node's sibling allOf is discarded.

    Pins the sibling-discard behavior: after $ref resolution, ``node`` becomes
    the resolved dict, so any allOf on the *original* node is replaced by the
    allOf (if any) from the resolved dict.
    """
    resolved_target = {
        "properties": {"from_ref": {"type": "string"}},
        "allOf": [
            {"properties": {"from_ref_allof": {"type": "integer"}}},
        ],
    }
    stub = make_stub_resolver({"vc:target": resolved_target})

    # Original node has $ref + sibling allOf.  After resolution, node becomes
    # resolved_target; its allOf (not the original sibling allOf) is merged.
    original_sibling_allof_prop = {"properties": {"from_sibling_allof": {}}}
    node = {
        "$ref": "vc:target",
        "allOf": [original_sibling_allof_prop],  # sibling — discarded after resolution
    }
    result = effective_schema(node, stub)
    assert "from_ref" in result["properties"], "resolved $ref props must appear"
    assert "from_ref_allof" in result["properties"], "resolved dict's allOf must be merged"
    assert "from_sibling_allof" not in result["properties"], (
        "original sibling allOf must be discarded after $ref resolution"
    )


def test_non_dict_resolver_return_yields_empty_schema():
    """A resolver that returns None (cannot resolve the $ref) produces an empty
    schema — no crash, no original-node passthrough."""
    def none_resolver(_node: dict[str, Any]) -> None:  # type: ignore[return]
        return None  # signals: cannot resolve

    node = {"$ref": "vc:unknown", "description": "should be discarded"}
    result = effective_schema(node, none_resolver)  # type: ignore[arg-type]
    assert result == {"properties": {}, "required": []}, (
        "non-dict resolver return must yield empty schema, not the original node"
    )


def test_include_conditionals_propagates_through_then_oneOf():
    """Deeply nested conditional: a ``then`` branch containing a ``oneOf`` with
    properties surfaces those nested properties when include_conditionals=True.

    Proves include_conditionals propagates through recursion depth > 1.
    """
    node = {
        "properties": {"top": {}},
        "then": {
            "properties": {"then_own": {}},
            "oneOf": [
                {"properties": {"nested_oneof_a": {}}},
                {"properties": {"nested_oneof_b": {}}},
            ],
        },
    }
    result = effective_schema(node, noop_resolver, include_conditionals=True)
    assert "top" in result["properties"]
    assert "then_own" in result["properties"]
    assert "nested_oneof_a" in result["properties"], (
        "nested oneOf inside then must surface with include_conditionals=True"
    )
    assert "nested_oneof_b" in result["properties"]


# ---------------------------------------------------------------------------
# 10. CLI-level regression tests — json_schema_discovery on a real step-16
#     impl_context plan fixture  (§5 "Unit (schema_nav / discovery)", F3)
# ---------------------------------------------------------------------------
#
# These tests exercise the complete json_schema_discovery path (the same code
# path invoked by `specdev json schema`) rather than the bare effective_schema
# primitive.  Two invariants are guarded:
#
#   F3-P2  The overwrite-bug regression: '.plan' must expose plan's own
#          properties (docs, spec_alignment, etc.) that live exclusively in
#          plan's own `properties` dict, not in any allOf branch.  If the old
#          overwrite bug returned, allOf-branch props would clobber the own
#          props and these fields would disappear.
#
#   F3-cond The conditional-branch guard: '.plan.docs' is a pure oneOf with NO
#           own properties.  Its two branches contribute disjoint fields:
#           'reason' (not_applicable branch) and 'required_updates' (planned
#           branch).  Both must appear in the resolved allowed_properties
#           simultaneously, which is only possible when include_conditionals=True
#           propagates through the path walk.


def _schema_info(path_selector: str) -> dict:
    """Return the parsed json_schema_discovery result for *path_selector* on the
    step-16 impl_context valid_full fixture."""
    raw = json_schema_discovery(
        _IMPL_CONTEXT_FIXTURE,
        path_selector,
        repo_root=str(_REPO_ROOT),
    )
    assert raw is not None, f"json_schema_discovery returned None for path '{path_selector}'"
    return json.loads(raw)


def test_plan_path_exposes_own_only_properties():
    """'.plan' resolves and exposes properties that live ONLY in plan's own
    `properties` dict (not in any allOf branch).

    This is the F3-P2 regression guard.  The fields 'docs', 'spec_alignment',
    'ambiguities', 'solution', and 'context' are declared only in plan's own
    properties — NOT in any allOf/then/else branch.  If the old overwrite bug
    were reintroduced, allOf-branch props would clobber the own props dict and
    these fields would vanish from allowed_properties.
    """
    info = _schema_info(".plan")
    allowed = info.get("allowed_properties") or []
    for own_only_key in ("docs", "spec_alignment", "ambiguities", "solution", "context"):
        assert own_only_key in allowed, (
            f"plan's own property '{own_only_key}' missing from allowed_properties={allowed!r}; "
            "the P2 overwrite bug may have been reintroduced"
        )


def test_plan_docs_path_returns_nonempty_allowed_properties():
    """'.plan.docs' navigates successfully AND returns a non-empty allowed_properties.

    'docs' is a pure oneOf field (no own properties), so allowed_properties is
    populated only when include_conditionals=True propagates through the path walk.
    If include_conditionals is False (or not propagated), the oneOf branches are
    opaque and allowed_properties would be None or empty — this test catches that.
    """
    info = _schema_info(".plan.docs")
    assert "error" not in info, (
        f"'.plan.docs' navigation failed: {info.get('error')}"
    )
    allowed = info.get("allowed_properties")
    assert allowed is not None, (
        "'.plan.docs' allowed_properties is None; include_conditionals=True may not be propagating"
    )
    assert len(allowed) > 0, (
        f"'.plan.docs' allowed_properties is empty={allowed!r}; "
        "include_conditionals=True may not be propagating through the path walk"
    )


def test_plan_docs_surfaces_cross_branch_union_fields():
    """'.plan.docs' exposes fields from BOTH oneOf branches simultaneously.

    This is the F3-conditional guard.  plan.docs has no own properties; its
    schema is entirely defined by two oneOf branches:
      - not_applicable branch: contributes 'reason'
      - planned branch:        contributes 'required_updates'

    Both 'reason' and 'required_updates' appearing together in allowed_properties
    proves that include_conditionals=True propagated correctly through the
    path walker.  With include_conditionals=False the oneOf branches are opaque
    and allowed_properties would be empty or absent.
    """
    info = _schema_info(".plan.docs")
    allowed = info.get("allowed_properties") or []
    assert "reason" in allowed, (
        f"'reason' (not_applicable branch) missing from .plan.docs allowed_properties={allowed!r}; "
        "conditional branch surfacing (include_conditionals=True) may be broken"
    )
    assert "required_updates" in allowed, (
        f"'required_updates' (planned branch) missing from .plan.docs allowed_properties={allowed!r}; "
        "conditional branch surfacing (include_conditionals=True) may be broken"
    )


# ---------------------------------------------------------------------------
# 11. Cycle guard — $ref cycles must not cause RecursionError
# ---------------------------------------------------------------------------

def test_cycle_allof_ref_returns_gracefully():
    """A cyclic allOf $ref chain (A -> B -> A) returns without RecursionError.

    Schema A has allOf with a $ref to B; schema B has allOf with a $ref back to A.
    effective_schema must terminate and return the properties it reached before
    the cycle, not crash with RecursionError.
    """
    schema_a = {
        "properties": {"a_field": {"type": "string"}},
        "allOf": [{"$ref": "schema:B"}],
    }
    schema_b = {
        "properties": {"b_field": {"type": "string"}},
        "allOf": [{"$ref": "schema:A"}],
    }
    mapping = {"schema:A": schema_a, "schema:B": schema_b}
    stub = make_stub_resolver(mapping)

    # Must not raise RecursionError
    result = effective_schema(schema_a, stub)
    # Properties reachable before cycle must appear
    assert "a_field" in result["properties"], "own a_field must be present"
    assert "b_field" in result["properties"], "b_field from B must be merged before cycle breaks"


def test_cycle_through_conditional_branch_returns_gracefully():
    """A cyclic chain through a conditional branch (A.oneOf -> B, B.then -> A)
    returns without RecursionError when include_conditionals=True.
    """
    schema_a = {
        "properties": {"a_field": {"type": "string"}},
        "oneOf": [{"$ref": "schema:B"}],
    }
    schema_b = {
        "properties": {"b_field": {"type": "string"}},
        "then": {"$ref": "schema:A"},
    }
    mapping = {"schema:A": schema_a, "schema:B": schema_b}
    stub = make_stub_resolver(mapping)

    # Must not raise RecursionError
    result = effective_schema(schema_a, stub, include_conditionals=True)
    assert "a_field" in result["properties"], "own a_field must be present"
    assert "b_field" in result["properties"], "b_field from B must be merged before cycle breaks"


def test_sibling_reuse_of_same_ref_is_not_a_cycle():
    """A node whose allOf has TWO branches both $ref-ing the same target T is NOT
    a cycle — copy-on-recurse (frozenset) semantics must allow T to resolve in
    both siblings independently.

    This proves the visited-set is path-local: the first sibling's resolution of
    T must NOT poison the second sibling's attempted resolution of T.
    """
    schema_t = {
        "properties": {"t_field": {"type": "string"}},
        "required": ["t_field"],
    }
    mapping = {"schema:T": schema_t}
    stub = make_stub_resolver(mapping)

    node = {
        "properties": {"own": {}},
        "allOf": [
            {"$ref": "schema:T"},  # sibling 1
            {"$ref": "schema:T"},  # sibling 2 — same ref, NOT a cycle
        ],
    }
    result = effective_schema(node, stub)
    assert "own" in result["properties"], "own property must appear"
    assert "t_field" in result["properties"], "T's property must resolve (not blocked as cycle)"
    # required is list-concat; both siblings contribute "t_field"
    assert result["required"].count("t_field") == 2, (
        "both sibling $ref branches must resolve T and contribute t_field to required"
    )


def test_bogus_path_returns_navigate_failure():
    """A clearly-bogus path returns the navigate-failure sentinel — NOT a crash.

    Negative guard: confirms the error-path is exercised and the error message
    contains 'Could not navigate'.
    """
    info = _schema_info(".bogus_top_level.nonexistent_child")
    assert "error" in info, (
        f"Expected navigate-failure for bogus path, got: {info!r}"
    )
    assert "Could not navigate" in info["error"], (
        f"Error message format unexpected: {info['error']!r}"
    )


# ---------------------------------------------------------------------------
# WI-M1-01: keywords beside $ref survive (JSON Schema 2020-12 sibling overlay)
# ---------------------------------------------------------------------------

def test_ref_sibling_x_node_and_x_link_survive():
    stub = make_stub_resolver({"vc:t": {"type": "string", "description": "target"}})
    node = {"$ref": "vc:t", "x-node": {"kind": "k"}, "x-link": {"to": "z"}}
    result = effective_schema(node, stub)
    assert result["x-node"] == {"kind": "k"}
    assert result["x-link"] == {"to": "z"}
    assert result["type"] == "string"


def test_ref_sibling_description_and_items_win():
    stub = make_stub_resolver(
        {"vc:t": {"description": "target", "items": {"type": "string"}, "minItems": 0}}
    )
    node = {"$ref": "vc:t", "description": "own", "items": {"type": "integer"}, "minItems": 1}
    result = effective_schema(node, stub)
    assert result["description"] == "own"
    assert result["items"] == {"type": "integer"}
    assert result["minItems"] == 1


def test_ref_sibling_properties_union_and_required_union_ordered():
    stub = make_stub_resolver(
        {"vc:t": {"properties": {"a": {"x": 1}, "b": {"x": 1}}, "required": ["b", "a"]}}
    )
    node = {
        "$ref": "vc:t",
        "properties": {"b": {"x": 2}, "c": {"x": 2}},
        "required": ["a", "c"],
    }
    result = effective_schema(node, stub)
    assert result["properties"] == {"a": {"x": 1}, "b": {"x": 2}, "c": {"x": 2}}
    assert result["required"] == ["b", "a", "c"]


def test_ref_sibling_overlay_is_idempotent():
    stub = make_stub_resolver({"vc:t": {"properties": {"a": {}}, "required": ["a"]}})
    node = {"$ref": "vc:t", "description": "own", "x-node": {"k": 1}}
    once = effective_schema(node, stub)
    assert effective_schema(once, stub) == once


def test_ref_sibling_cycle_guard_and_unresolved_unchanged():
    stub = make_stub_resolver({"vc:loop": {"properties": {"n": {"$ref": "vc:loop"}}}})
    node = {"$ref": "vc:loop", "description": "own"}
    result = effective_schema(node, stub)
    assert result["description"] == "own"
    assert "n" in result["properties"]
    assert effective_schema({"$ref": "vc:x", "description": "d"}, lambda n: None) == {
        "properties": {},
        "required": [],
    }


def test_schema_ref_sibling_census():
    """A ``$ref`` node in schema/**/*.json carries no sibling beyond annotations and array bounds.

    Allowed siblings: ``description``, ``default``, ``items``, ``minItems``, ``maxItems``. Any
    other keyword beside a ``$ref`` (``type``, ``enum``, ``properties``, ...) is ignored or
    contradicted by some validators, so a schema must not rely on it.
    """
    from collections import Counter

    counts: Counter = Counter()

    def walk(n: Any) -> None:
        if isinstance(n, dict):
            if "$ref" in n and len(n) > 1:
                counts[tuple(sorted(k for k in n if k != "$ref"))] += 1
            for v in n.values():
                walk(v)
        elif isinstance(n, list):
            for v in n:
                walk(v)

    for f in sorted((_REPO_ROOT / "schema").rglob("*.json")):
        walk(json.loads(f.read_text(encoding="utf-8")))

    allowed = {"description", "default", "items", "minItems", "maxItems"}
    offenders = {siblings: n for siblings, n in counts.items() if not set(siblings) <= allowed}
    assert offenders == {}


# ---------------------------------------------------------------------------
# child_schema: the schema of one member of an already effective node
# ---------------------------------------------------------------------------

import pytest  # noqa: E402

from specdev_tools.core.schema_nav import child_schema  # noqa: E402

_NODE: dict[str, Any] = {
    "properties": {"name": {"type": "string"}, "tags": {"type": "array", "items": {"type": "string", "enum": ["a"]}}, "flag": True},
    "patternProperties": {"^x-": {"type": "integer"}, "(": {"type": "boolean"}},
    "additionalProperties": {"type": "number"},
    "items": {"type": "object"},
}


@pytest.mark.parametrize(
    ("step", "additional", "expected"),
    [
        ("name", False, {"type": "string"}),
        (0, False, {"type": "object"}),
        ("x-extra", False, {"type": "integer"}),
        ("other", False, None),
        ("other", True, {"type": "number"}),
        ("flag", True, None),
    ],
)
def test_child_schema_reads_property_index_pattern_and_additional(step: str | int, additional: bool, expected: dict[str, Any] | None) -> None:
    """A property wins over a pattern, an index reads ``items``, a pattern matches by search, ``additionalProperties`` only on request, and a boolean schema is no schema."""
    assert child_schema(_NODE, step, additional=additional) == expected


def test_child_schema_treats_a_pattern_that_is_not_a_regular_expression_as_matching_nothing() -> None:
    assert child_schema({"patternProperties": {"(": {"type": "boolean"}}}, "(") is None
    assert child_schema({}, "anything", additional=True) is None


# ---------------------------------------------------------------------------
# 11. json schema prints the constraint keywords of the node (DEVSPEC-211)
# ---------------------------------------------------------------------------

_EXAMPLE_SPEC = _REPO_ROOT / "tests" / "fixtures" / "graph_example" / "spec"


def _example_info(file_name: str, path_selector: str) -> dict:
    raw = json_schema_discovery(str(_EXAMPLE_SPEC / file_name), path_selector, repo_root=str(_REPO_ROOT))
    assert raw is not None
    return json.loads(raw)


def test_probe_prints_min_and_max_items():
    info = _example_info("02_system_sketch.json", ".components[].responsibilities")
    assert (info["minItems"], info["maxItems"]) == (3, 6)


def test_probe_prints_min_length():
    assert _example_info("00_charter.json", ".problem_statement")["minLength"] == 20


def test_probe_prints_every_constraint_keyword_of_the_node(tmp_path):
    values: dict[str, Any] = {
        "minItems": 1, "maxItems": 2, "uniqueItems": True, "minLength": 1, "maxLength": 9, "pattern": "^a",
        "format": "date", "minimum": 0, "maximum": 5, "exclusiveMinimum": -1, "exclusiveMaximum": 6,
        "additionalProperties": False, "const": "x",
    }
    assert set(values) == set(_CONSTRAINT_KEYWORDS)
    schema_dir = tmp_path / "schema"
    schema_dir.mkdir()
    (schema_dir / "t.schema.json").write_text(json.dumps({
        "$id": "vc:test:constraints",
        "type": "object",
        "properties": {
            "field": {"type": "array", "items": {"type": "string", "minLength": 2}, **values},
        },
    }), encoding="utf-8")
    document = tmp_path / "doc.json"
    document.write_text(json.dumps({"$schema": "vc:test:constraints", "field": []}), encoding="utf-8")
    raw = json_schema_discovery(str(document), ".field", repo_root=str(tmp_path))
    info = json.loads(raw)
    assert {keyword: info[keyword] for keyword in _CONSTRAINT_KEYWORDS} == values
    assert info["items_constraints"] == {"minLength": 2}
