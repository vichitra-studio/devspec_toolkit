"""Shared utilities for the DevSpec Toolkit context package.

Consolidates helpers that were duplicated across structure.py, extractor.py,
and canon_extractor.py (NB-04, NB-05, NB-06).
"""
from __future__ import annotations

import json
import os
from typing import Any

from ..core.registry import SchemaRegistry
from ..core.schema_nav import effective_schema as _schema_nav_effective_schema


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def load_step_order(repo_root: str) -> dict:
    """Load tools/step_order.json from *repo_root*."""
    path = os.path.join(os.path.abspath(repo_root), "tools", "step_order.json")
    if not os.path.exists(path):
        path = os.path.join(os.path.abspath(repo_root), "step_order.json")
    return load_json(path)


def find_spec_file(step_id: str, spec_dir: str) -> str | None:
    """Find the spec JSON file for *step_id* inside *spec_dir*.

    Convention: files are named ``{step_id}_{name}.json``.
    """
    spec_dir_abs = os.path.abspath(spec_dir)
    if not os.path.isdir(spec_dir_abs):
        return None
    prefix = f"{step_id}_"
    for fname in os.listdir(spec_dir_abs):
        if fname.startswith(prefix) and fname.endswith(".json"):
            return os.path.join(spec_dir_abs, fname)
    return None


# ---------------------------------------------------------------------------
# Fail-loud hardening: explicit disambiguation table for multi-schema steps.
#
# Context: some steps have more than one schema URI registered under the same
# step prefix (e.g. step 16 has both vc:16-impl-context and vc:16-anchor).
# The old code silently returned the first dict-order match, which happened to
# be correct only because schema_registry.json listed vc:16-impl-context first.
#
# This table makes the resolution ORDER-INDEPENDENT and FAIL-LOUD:
#   - If exactly 1 URI matches → return it (unchanged behavior, no table needed).
#   - If >1 URIs match and the step is in this table → return the mapped primary
#     (order-independent, deterministic).
#   - If >1 URIs match and the step is NOT in this table → raise ValueError
#     (fail-loud: a future multi-schema step without a table entry is caught).
#
# IMPORTANT: this is fail-loud hardening + explicit disambiguation.
# It is NOT "resolution by $id" (the bigger refactor where callers say which
# variant they want is deliberately out of scope here).
#
# To add a new multi-schema step: add its step_id → primary URI mapping below.
# The primary URI must be the one that represents the canonical spec artifact.
_MULTI_SCHEMA_STEP_PRIMARY: dict[str, str] = {
    "16": "vc:16-impl-context",  # 16_anchor.schema.json is an internal anchor, not a spec
}


def find_step_schema_uri(step_id: str, registry: SchemaRegistry) -> str | None:
    """Search schema_registry for a URI that matches *step_id*.

    URIs follow patterns like ``vc:04-fr-list``, ``vc:02a-delivery-baseline``.

    Fail-loud on unhandled ambiguity: if >1 URI matches and the step has no
    entry in ``_MULTI_SCHEMA_STEP_PRIMARY``, raises ``ValueError`` naming the
    step, the ambiguous URIs, and the fix instruction.  This makes the selector
    ORDER-INDEPENDENT and FAIL-LOUD rather than silently dict-order-dependent.
    """
    needle = f"vc:{step_id}-"
    matches = [uri for uri in registry.map.keys() if uri.startswith(needle)]

    if not matches:
        return None

    if len(matches) == 1:
        return matches[0]

    # >1 match: consult the explicit disambiguation table.
    primary = _MULTI_SCHEMA_STEP_PRIMARY.get(step_id)
    if primary is not None and primary in matches:
        return primary

    # Stale table: primary mapped but not among current matches, or step not in table.
    if primary is not None:
        raise ValueError(
            f"find_step_schema_uri: step '{step_id}' has a _MULTI_SCHEMA_STEP_PRIMARY "
            f"entry ('{primary}') but that URI is not among the current matches "
            f"{sorted(matches)!r}. The disambiguation table may be stale — "
            f"update _MULTI_SCHEMA_STEP_PRIMARY in tools/specdev_tools/context/_utils.py."
        )
    raise ValueError(
        f"find_step_schema_uri: step '{step_id}' matched multiple schema URIs "
        f"{sorted(matches)!r} and has no entry in _MULTI_SCHEMA_STEP_PRIMARY. "
        f"Add an explicit primary URI for this step to "
        f"_MULTI_SCHEMA_STEP_PRIMARY in tools/specdev_tools/context/_utils.py."
    )


def merge_allof(schema: dict, registry: SchemaRegistry) -> dict:
    """Merge allOf branches with root-level properties into a single ``{properties, required}`` dict.

    Uses ``SchemaRegistry.to_referencing_registry()`` for ``$ref`` resolution
    per locked decision 4f — handles anchor-based ``$ref``s correctly.
    allOf branches with ``if``/``then`` (no ``properties`` at top-level) yield
    empty props and are safely skipped.

    Schemas may declare step-specific properties either at the root (alongside
    an ``allOf`` that $refs ``vc:core:step-base``) or inside an ``allOf`` branch.
    Both shapes are merged into a single property set.

    Thin adapter over ``schema_nav.effective_schema`` (conditionals OFF — same
    allOf-only, own-first behavior as before; oneOf/anyOf/if-then-else latent gap
    is intentionally unchanged per §6 deferred scope).
    """
    ref_registry = registry.to_referencing_registry()

    def _resolve_ref(node: dict):
        """Dual-fallback $ref resolver.

        1. Try ``ref_registry.contents(uri)`` — handles $anchor/fragment refs.
        2. On exception, try ``registry.load(uri)`` — handles whole-schema URIs.
        3. On exception, return None (non-dict) so effective_schema skips branch.

        MUST return None (non-dict) on failure — never raise.  effective_schema
        has no try/except; a raise would change today's branch-skip error semantics.
        """
        ref_uri = node.get("$ref")
        if not ref_uri:
            return None
        try:
            return ref_registry.contents(ref_uri)
        except Exception:
            pass
        try:
            return registry.load(ref_uri)
        except Exception:
            pass
        return None

    e = _schema_nav_effective_schema(schema, _resolve_ref, include_conditionals=False)
    return {"properties": e["properties"], "required": e["required"]}


def compute_required_inputs(
    step_id: str, downstream_consumers: dict[str, list[str]]
) -> list[str]:
    """Return upstream step IDs that *step_id* requires as input.

    Inverts downstream_consumers: step N requires step S if step N
    appears in downstream_consumers[S].
    """
    return [
        src for src, consumers in downstream_consumers.items()
        if step_id in consumers
    ]


# Module-level cache for boilerplate keys.
_boilerplate_keys_cache: frozenset[str] | None = None

_BOILERPLATE_KEYS_FALLBACK: frozenset[str] = frozenset([
    "$schema",
    "id",
    "owner",
    "created_at",
    "canonical_refs_used",
    "canonical_proposals",
    "canonical_conflicts",
    "_migration_notes",
])


def get_boilerplate_keys(registry: SchemaRegistry | None = None) -> frozenset[str]:
    """Return the set of step-base boilerplate keys.

    Loads from vc:core:step-base via SchemaRegistry on first call and caches
    the result. Falls back to a hardcoded set if the registry is unavailable.
    Self-maintaining: new step-base fields defined in the schema are auto-included on each call.
    """
    global _boilerplate_keys_cache
    if _boilerplate_keys_cache is not None:
        return _boilerplate_keys_cache
    if registry is not None:
        try:
            step_base = registry.load("vc:core:step-base")
            props = step_base.get("properties", {})
            if props:
                _boilerplate_keys_cache = frozenset(props.keys())
                return _boilerplate_keys_cache
        except Exception:
            pass
    # Don't cache the fallback — allow future calls with a registry to populate the cache.
    return _BOILERPLATE_KEYS_FALLBACK
