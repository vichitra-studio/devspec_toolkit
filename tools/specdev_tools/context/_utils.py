"""Shared utilities for the DevSpec Toolkit context package.

Consolidates helpers that were duplicated across structure.py, extractor.py,
and canon_extractor.py (NB-04, NB-05, NB-06).
"""
from __future__ import annotations

import json
import os
from typing import Any

from ..core.registry import SchemaRegistry


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


def find_step_schema_uri(step_id: str, registry: SchemaRegistry) -> str | None:
    """Search schema_registry for a URI that matches *step_id*.

    URIs follow patterns like ``vc:04-fr-list``, ``vc:02a-delivery-baseline``.
    """
    needle = f"vc:{step_id}-"
    for uri in registry.map.keys():
        if uri.startswith(needle):
            return uri
    return None


def merge_allof(schema: dict, registry: SchemaRegistry) -> dict:
    """Merge allOf branches with root-level properties into a single ``{properties, required}`` dict.

    Uses ``SchemaRegistry.to_referencing_registry()`` for ``$ref`` resolution
    per locked decision 4f — handles anchor-based ``$ref``s correctly.
    allOf branches with ``if``/``then`` (no ``properties`` at top-level) yield
    empty props and are safely skipped.

    Schemas may declare step-specific properties either at the root (alongside
    an ``allOf`` that $refs ``vc:core:step-base``) or inside an ``allOf`` branch.
    Both shapes are merged into a single property set.
    """
    ref_registry = registry.to_referencing_registry()
    merged_props: dict[str, Any] = dict(schema.get("properties", {}))
    merged_required: list[str] = list(schema.get("required", []))

    for branch in schema.get("allOf", []) or []:
        resolved = branch
        if isinstance(branch, dict) and "$ref" in branch:
            ref_uri = branch["$ref"]
            try:
                resolved = ref_registry.contents(ref_uri)
            except Exception:
                try:
                    resolved = registry.load(ref_uri)
                except Exception:
                    continue
        if not isinstance(resolved, dict):
            continue
        merged_props.update(resolved.get("properties", {}))
        merged_required.extend(resolved.get("required", []))

    return {"properties": merged_props, "required": merged_required}


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
