"""schema_nav — canonical schema-property merge helper.

SoC guarantee: this module has **no** imports from the registry, file-system, or
any other toolkit subsystem.  Ref-resolution is always injected by the caller.

``$defs`` inside allOf branches are NOT merged — ``$defs`` are expected at the
JSON Schema document root and local refs are resolved against the raw document
by the discovery layer before schema_nav is called.
"""

from __future__ import annotations

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

    Merge order — own-first, branch-wins on collision (property set is the
    UNION of all sources):

    .. code-block:: text

        props    = dict(node.get("properties", {}))   # own first
        required = list(node.get("required", []))
        for b in allOf:
            e = effective_schema(b, resolve_ref, include_conditionals=...)
            props    |= e["properties"]               # branch-wins collision
            required += e["required"]                 # list-concat, no dedup
        if include_conditionals:                      # OFF by default
            for b in oneOf / anyOf:
                e = effective_schema(b, ...)
                props |= e["properties"]              # props only — NOT required
            for b in then / else:
                e = effective_schema(b, ...)
                props |= e["properties"]              # props only — NOT required
            # "if" is a predicate, never a property source — excluded

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
        (but never into ``required``).  Defaults to ``False`` so that existing
        ``merge_allof`` / ``_get_all_properties`` callers experience zero
        behavior change.
    :param _seen: **Internal — do not pass.**  A frozenset of ``$ref`` strings
        already resolved on the current recursion path.  Used as a cycle guard:
        if a ``$ref`` string is encountered that is already in ``_seen``, the
        branch is returned as an empty schema (``{"properties": {}, "required":
        []}``) rather than recursing infinitely.  Copy-on-recurse semantics (via
        frozenset union) ensure sibling branches do NOT share visited state, so
        a ``$ref`` legitimately reused across two sibling branches resolves
        correctly in both.
    """
    # --- Step 1: resolve $ref ---
    # If the node is a bare $ref, resolve it and use the resolved dict as the
    # base.  Any own keys alongside $ref are retained by the resolved result
    # (JSON Schema 2020-12 allows sibling keywords, but the toolkit's own
    # schemas use bare $ref objects, so the resolved dict IS the full node).
    if "$ref" in node:
        ref: str = node["$ref"]
        if ref in _seen:
            # Cycle guard: this $ref has already been resolved on the current
            # recursion path.  Return an empty schema to break the cycle
            # gracefully rather than crashing with RecursionError.
            return {"properties": {}, "required": []}
        resolved = resolve_ref(node)
        if not isinstance(resolved, dict):
            # Guard: resolver signalled it cannot resolve this $ref by returning
            # a non-dict (e.g. None).  Return an empty schema so the caller sees
            # a harmless empty branch rather than crashing.  See resolve_ref
            # contract in the docstring — returning the input node is incorrect.
            return {"properties": {}, "required": []}
        node = resolved
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
    for branch in node.get("allOf", []) or []:
        if not isinstance(branch, dict):
            continue
        e = effective_schema(branch, resolve_ref, include_conditionals=include_conditionals, _seen=_seen)
        props.update(e["properties"])       # branch-wins on collision
        required.extend(e["required"])      # list-concat, no dedup

    # --- Step 5: optionally union conditional branches (props only) ---
    if include_conditionals:
        # oneOf / anyOf — mutually exclusive branches; union props, NOT required
        for keyword in ("oneOf", "anyOf"):
            for branch in node.get(keyword, []) or []:
                if not isinstance(branch, dict):
                    continue
                e = effective_schema(branch, resolve_ref, include_conditionals=include_conditionals, _seen=_seen)
                props.update(e["properties"])

        # then / else — conditional gated branches; union props, NOT required
        for keyword in ("then", "else"):
            branch = node.get(keyword)
            if isinstance(branch, dict):
                e = effective_schema(branch, resolve_ref, include_conditionals=include_conditionals, _seen=_seen)
                props.update(e["properties"])

        # "if" is a predicate (discriminator), never a property source — excluded.

    # --- Step 6: write merged properties + required into result ---
    # Always set both keys even when empty so callers can do e["properties"]
    # and e["required"] without KeyError.
    base["properties"] = props
    base["required"] = required

    return base
