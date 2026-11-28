"""schema_nav — canonical schema-property merge helper.

SoC guarantee: this module has **no** imports from the registry, file-system, or
any other toolkit subsystem.  Ref-resolution is always injected by the caller.

``$defs`` inside allOf branches are NOT merged — ``$defs`` are expected at the
JSON Schema document root and local refs are resolved against the raw document
by the discovery layer before schema_nav is called.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any


# Composition keywords consumed during merge.  All are stripped from the
# returned dict so that re-calling effective_schema on its own output is
# idempotent (the json_schema_discovery path-walker does exactly this).
_CONSUMED_KEYWORDS = frozenset({"allOf", "oneOf", "anyOf", "if", "then", "else"})


def effective_schema(
    node: dict,
    resolve_ref: Callable[[dict], dict | None],
    *,
    include_conditionals: bool = False,
    _seen: frozenset[str] = frozenset(),
) -> dict:
    """Resolve ``$ref`` + merge ``allOf`` (+ optionally union ``oneOf``/``anyOf``/
    ``then``/``else`` branch properties) into a single navigable node.

    Merge order — own-first, ``allOf`` branch wins on collision; a conditional
    branch only ADDS a property (property set is the UNION of all sources):

    .. code-block:: text

        props    = dict(node.get("properties", {}))   # own first
        required = list(node.get("required", []))
        for b in allOf:
            props    |= unconditional properties of b # branch-wins collision
            required += required of b                 # list-concat, no dedup
        if include_conditionals:                      # OFF by default
            for b in oneOf / anyOf / then / else (of the node and of its allOf branches):
                conditional |= properties of b        # props only — NOT required
            for name in conditional:
                props.setdefault(name, ...)           # never replaces a declaration
            # "if" is a predicate, never a property source — excluded

    A conditional branch that restates a property the node (or one of its
    ``allOf`` branches) declares narrows it for some documents only (``then:
    {properties: {errors: {items: ...}}}``): the declaration is the one
    returned, so its type, description and items stay navigable.  A bound that
    only such a branch states is not in the result.

    Returns a node-shaped dict that:

    * preserves ``type``, ``items``, ``description``, ``additionalProperties``,
      ``enum`` (and any other non-composition key) from the (ref-resolved) node;
    * sets ``properties`` (always — may be ``{}``) to the merged map;
    * sets ``required`` (always — may be ``[]``) to the merged list;
    * strips all composition keywords (``allOf``, ``oneOf``, ``anyOf``, ``if``,
      ``then``, ``else``) so the result is idempotent under re-application.

    :param node: A JSON-Schema node dict.
    :param resolve_ref: ``resolve_ref(node) -> dict`` — called when ``node``
        contains a ``"$ref"`` key.  The helper knows nothing about registries or
        files; resolution semantics are entirely the caller's responsibility.
        If the callback cannot resolve a ``$ref`` it **MUST** return a non-dict
        (e.g. ``None``) so the branch is treated as empty (returning
        ``{"properties": {}, "required": []}``).  Returning the input node
        itself is INCORRECT — it would be re-processed as a resolved schema,
        causing infinite recursion or silent data corruption.
    :param include_conditionals: When ``True``, properties from ``oneOf``,
        ``anyOf``, ``then``, and ``else`` branches are unioned into ``props``
        (but never into ``required``).  Defaults to ``False``.  ``merge_allof``
        calls it twice and adds the conditional-only
        properties under the allOf-only ones.
    :param _seen: **Internal — do not pass.**  A frozenset of ``$ref`` strings
        already resolved on the current recursion path.  Used as a cycle guard:
        if a ``$ref`` string is encountered that is already in ``_seen``, the
        branch is returned as an empty schema (``{"properties": {}, "required":
        []}``) rather than recursing infinitely.  Copy-on-recurse semantics (via
        frozenset union) ensure sibling branches do NOT share visited state, so
        a ``$ref`` legitimately reused across two sibling branches resolves
        correctly in both.
    """
    base, conditional = _split_effective(node, resolve_ref, include_conditionals, _seen)
    for name, schema in conditional.items():
        base["properties"].setdefault(name, schema)
    return base


def _split_effective(
    node: dict, resolve_ref: Callable[[dict], dict | None], include_conditionals: bool, _seen: frozenset[str],
) -> tuple[dict, dict[str, Any]]:
    """The node of ``effective_schema`` with its unconditional properties only, and the properties its conditional branches state.

    The second value is empty unless *include_conditionals*; among conditional branches the later one wins, and inside
    one branch its own declaration wins over a branch nested in it.
    """
    # --- Step 1: resolve $ref ---
    # JSON Schema 2020-12: keywords beside ``$ref`` apply together with the
    # target.  After the ref resolves to dict R, the effective node is R
    # overlaid by the node's own keywords other than ``$ref``: a sibling value
    # wins on collision; ``properties`` are unioned (sibling wins per key);
    # ``required`` is the order-preserving union.  Composition keywords beside
    # ``$ref`` (allOf/oneOf/anyOf/if/then/else) are NOT overlaid; the resolved
    # dict's own composition keywords are the ones merged.
    if "$ref" in node:
        ref: str = node["$ref"]
        if ref in _seen:
            # Cycle guard: this $ref has already been resolved on the current
            # recursion path.  Return an empty schema to break the cycle
            # gracefully rather than crashing with RecursionError.
            return {"properties": {}, "required": []}, {}
        resolved = resolve_ref(node)
        if not isinstance(resolved, dict):
            # Guard: resolver signalled it cannot resolve this $ref by returning
            # a non-dict (e.g. None).  Return an empty schema so the caller sees
            # a harmless empty branch rather than crashing.  See resolve_ref
            # contract in the docstring — returning the input node is incorrect.
            return {"properties": {}, "required": []}, {}
        merged: dict[str, Any] = dict(resolved)
        for key, value in node.items():
            if key == "$ref" or key in _CONSUMED_KEYWORDS:
                continue
            if key == "properties" and isinstance(value, dict):
                base_props = merged.get("properties")
                merged["properties"] = {
                    **(base_props if isinstance(base_props, dict) else {}),
                    **value,
                }
            elif key == "required" and isinstance(value, list):
                base_req = merged.get("required")
                union = list(base_req) if isinstance(base_req, list) else []
                union.extend(r for r in value if r not in union)
                merged["required"] = union
            else:
                merged[key] = value
        node = merged
        _seen = _seen | {ref}

    # --- Step 2: build the base result ---
    # Start with all non-composition keys from the (possibly ref-resolved) node,
    # then overlay the merged properties/required.  Stripping composition
    # keywords here is what makes the output idempotent under re-application.
    base: dict[str, Any] = {
        k: v for k, v in node.items() if k not in _CONSUMED_KEYWORDS
    }

    # --- Step 3: initialise own properties + required ---
    props: dict[str, Any] = dict(node.get("properties", {}))
    required: list[str] = list(node.get("required", []))

    # --- Step 4: merge allOf branches (always) ---
    conditional: dict[str, Any] = {}
    for branch in node.get("allOf", []) or []:
        if not isinstance(branch, dict):
            continue
        e, nested = _split_effective(branch, resolve_ref, include_conditionals, _seen)
        props.update(e["properties"])       # branch-wins on collision
        required.extend(e["required"])      # list-concat, no dedup
        conditional.update(nested)

    # --- Step 5: optionally collect conditional branches (props only) ---
    if include_conditionals:
        # oneOf / anyOf are mutually exclusive branches, then / else are gated ones: their properties
        # are collected apart (NOT required) and only added by ``effective_schema``.
        branches: list[Any] = [b for keyword in ("oneOf", "anyOf") for b in node.get(keyword, []) or []]
        branches.extend(node.get(keyword) for keyword in ("then", "else"))
        for branch in branches:
            if not isinstance(branch, dict):
                continue
            e, nested = _split_effective(branch, resolve_ref, include_conditionals, _seen)
            conditional.update({**nested, **e["properties"]})

        # "if" is a predicate (discriminator), never a property source — excluded.

    # --- Step 6: write merged properties + required into result ---
    # Always set both keys even when empty so callers can do e["properties"]
    # and e["required"] without KeyError.
    base["properties"] = props
    base["required"] = required

    return base, conditional


def child_schema(effective: dict, step: str | int, *, additional: bool = False) -> dict | None:
    """The schema of the member *step* of a value described by the already effective node *effective* (see ``effective_schema``).

    An index gives ``items``; a key gives its ``properties`` entry, else the entry of the first ``patternProperties``
    pattern that matches it (a pattern that is not a valid regular expression matches nothing) and, with *additional*,
    else a schema ``additionalProperties``.  ``None`` when there is none or it is not an object schema.
    """
    found: Any
    if isinstance(step, int):
        found = effective.get("items")
    else:
        found = effective.get("properties", {}).get(step)
        if found is None:
            found = next((sub for pattern, sub in effective.get("patternProperties", {}).items() if _matches(pattern, step)), None)
        if found is None and additional:
            found = effective.get("additionalProperties")
    return found if isinstance(found, dict) else None


def _matches(pattern: str, text: str) -> bool:
    try:
        return re.search(pattern, text) is not None
    except re.error:
        return False
