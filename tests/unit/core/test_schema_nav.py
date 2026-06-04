"""Unit tests for schema_nav.effective_schema.

Each test targets one behavioural invariant documented in the plan (§2 WS3,
§3.2, §5 "Unit (schema_nav / discovery)").
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from specdev_tools.core.json_utils import json_schema_discovery
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


def test_own_property_wins_collision_with_allof_branch():
    """When own and allOf define the same key, the branch (later) wins.

    merge_allof / _get_all_properties both use .update() (branch-wins semantics).
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
    merge_allof / _get_all_properties callers)."""
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
