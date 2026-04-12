"""Context extractor for the DevSpec Toolkit.

Implements ``extract_context(step_id, spec_dir, repo_root, entry_id=None) -> dict``.

Uses SchemaRegistry for schema access and scope_resolver for ID-based scoping.
Strips step-base boilerplate from output. Applies tiered extraction:
  - Traceable arrays: scoped to resolved_ids from scope_resolver
  - Non-traceable arrays: required-fields mode (schema required[] fields only)
  - Scalars/objects: always extracted fully
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any

from ..core.constants import resolve_extras_path
from ..core.registry import SchemaRegistry
from ..core.trace_types import normalize_trace_type, is_valid_trace_type
from .scope_resolver import resolve_scope
from ._utils import (
    load_json as _u_load_json,
    load_step_order as _u_load_step_order,
    find_spec_file as _u_find_spec_file,
    find_step_schema_uri as _u_find_step_schema_uri,
    merge_allof as _u_merge_allof,
    compute_required_inputs as _u_compute_required_inputs,
    get_boilerplate_keys as _u_get_boilerplate_keys,
)

# ---------------------------------------------------------------------------
# Step-base boilerplate keys — set at runtime in extract_context (§4g).
# ---------------------------------------------------------------------------
_BOILERPLATE_KEYS: frozenset[str] = frozenset()

# ---------------------------------------------------------------------------
# Tier-2 truncation threshold for non-traceable arrays.
# ---------------------------------------------------------------------------
_TIER2_THRESHOLD = 20

# ---------------------------------------------------------------------------
# Extraction-paths cache helpers (F-005).
# ---------------------------------------------------------------------------
_EXTRACTION_PATHS_FILENAME = "extraction_paths.json"


def _sha256_file(path: str) -> str:
    """Compute SHA-256 of a file and return ``sha256:<hex>``."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"


def _load_extraction_paths(spec_dir: str, repo_root: str) -> dict:
    """Load the extraction_paths.json cache file, returning {} on any error."""
    path = resolve_extras_path(spec_dir, repo_root, _EXTRACTION_PATHS_FILENAME)
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}


def _save_extraction_paths(spec_dir: str, repo_root: str, cache: dict) -> None:
    """Write the extraction_paths.json cache file, silently ignoring errors."""
    path = resolve_extras_path(spec_dir, repo_root, _EXTRACTION_PATHS_FILENAME)
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(cache, fh, indent=2)
    except OSError:
        pass


def _cache_is_fresh(cache: dict, step_id: str, schema_uri: str, registry: "SchemaRegistry") -> bool:
    """Return True if the cached entry for *step_id* is still valid.

    Staleness is detected by comparing the SHA-256 of the schema file
    against the hash stored in ``_meta.schema_hashes``.
    """
    if step_id not in cache:
        return False
    meta = cache.get("_meta", {})
    stored_hash = meta.get("schema_hashes", {}).get(schema_uri)
    if not stored_hash:
        return False
    schema_path = registry.resolve(schema_uri)
    if not schema_path or not os.path.isfile(schema_path):
        return False
    try:
        current_hash = _sha256_file(schema_path)
    except OSError:
        return False
    return current_hash == stored_hash


def _update_cache_entry(
    cache: dict,
    step_id: str,
    schema_uri: str,
    schema_path: str,
    field_map: dict[str, list[str]],
) -> None:
    """Update the cache for *step_id* with newly discovered field paths."""
    import datetime
    meta = cache.setdefault("_meta", {})
    hashes = meta.setdefault("schema_hashes", {})
    try:
        hashes[schema_uri] = _sha256_file(schema_path)
    except OSError:
        pass
    meta["generated_at"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cache[step_id] = field_map


def _load_json(path: str) -> dict:
    return _u_load_json(path)


def _load_step_order(repo_root: str) -> dict:
    """Load tools/step_order.json from *repo_root*."""
    return _u_load_step_order(repo_root)


def _find_spec_file(step_id: str, spec_dir: str) -> str | None:
    """Find the spec JSON file for *step_id* inside *spec_dir*."""
    return _u_find_spec_file(step_id, spec_dir)


def _find_step_schema_uri(step_id: str, registry: SchemaRegistry) -> str | None:
    """Search schema_registry for a URI that matches *step_id*.

    URIs follow patterns like ``vc:04-fr-list``, ``vc:02a-delivery-baseline``.
    """
    return _u_find_step_schema_uri(step_id, registry)


def _merge_allof(schema: dict, registry: SchemaRegistry) -> dict:
    """Merge allOf branches into a single properties+required dict."""
    return _u_merge_allof(schema, registry)


def _strip_to_required(item: dict, required_fields: list[str]) -> dict:
    """Strip optional fields from an item, keeping only required fields."""
    if not required_fields:
        return item  # no schema info, keep all
    return {k: v for k, v in item.items() if k in required_fields}


def _is_traceable_array(prop_schema: dict) -> tuple[bool, str | None]:
    """Determine if an array property contains traceable entities.

    Returns (is_traceable, id_field_name).
    An array is traceable if its items have an ``*_id`` field whose prefix
    corresponds to a valid trace type.
    """
    if prop_schema.get("type") != "array":
        return False, None
    items_schema = prop_schema.get("items", {})
    item_props = items_schema.get("properties", {})
    for field_name in item_props:
        if field_name.endswith("_id"):
            prefix = field_name[:-3]  # strip trailing "_id"
            if is_valid_trace_type(prefix) or is_valid_trace_type(
                normalize_trace_type(prefix)
            ):
                return True, field_name
    return False, None


def _get_all_resolved_ids(resolved_ids: dict[str, list[str]]) -> set[str]:
    """Flatten the resolved_ids dict into a flat set of all IDs."""
    flat: set[str] = set()
    for ids in resolved_ids.values():
        flat.update(ids)
    return flat


def _compute_required_inputs(
    step_id: str, downstream_consumers: dict[str, list[str]]
) -> list[str]:
    """Return list of upstream step IDs that *step_id* requires as input."""
    return _u_compute_required_inputs(step_id, downstream_consumers)


def extract_context(
    step_id: str,
    spec_dir: str,
    repo_root: str,
    entry_id: str | None = None,
    full: bool = False,
) -> dict[str, Any]:
    """Extract a focused context package for a pipeline step.

    Parameters
    ----------
    step_id:
        Pipeline step to prepare context for (e.g. ``"04"``, ``"16a"``).
    spec_dir:
        Directory containing spec JSON files.
    repo_root:
        Path to the devspec_toolkit repo root.
    entry_id:
        Optional scope anchor (e.g. ``"milestone-02"``). When provided,
        traceable arrays are filtered to reachable IDs only.
    full:
        If True, skip scoping and return all items from all arrays.

    Returns
    -------
    dict with keys: step, scope, context, token_estimate, vs_full_read_estimate
    """
    repo_root_abs = os.path.abspath(repo_root)
    spec_dir_abs = os.path.abspath(spec_dir)

    # ------------------------------------------------------------------
    # 1. Resolve scope (BFS over trace graph).
    # ------------------------------------------------------------------
    scope_label: str
    resolved_id_set: set[str] = set()

    if entry_id and not full:
        scope_result = resolve_scope(entry_id, spec_dir_abs, repo_root_abs)
        resolved_id_set = _get_all_resolved_ids(scope_result.get("resolved_ids", {}))
        scope_label = entry_id
    else:
        scope_label = "all"

    # ------------------------------------------------------------------
    # 2. Determine upstream spec files needed for this step.
    # ------------------------------------------------------------------
    try:
        step_order = _load_step_order(repo_root_abs)
    except (OSError, json.JSONDecodeError):
        step_order = {}

    downstream_consumers: dict[str, list[str]] = step_order.get(
        "downstream_consumers", {}
    )
    upstream_step_ids = _compute_required_inputs(step_id, downstream_consumers)

    # ------------------------------------------------------------------
    # 3. Initialise SchemaRegistry.
    # ------------------------------------------------------------------
    try:
        registry = SchemaRegistry(repo_root_abs)
    except Exception:
        registry = None  # type: ignore[assignment]

    global _BOILERPLATE_KEYS
    _BOILERPLATE_KEYS = _u_get_boilerplate_keys(registry)

    # ------------------------------------------------------------------
    # 4. Collect context from each upstream spec file.
    # ------------------------------------------------------------------
    context: dict[str, Any] = {}
    upstream_files: list[str] = []

    extraction_cache = _load_extraction_paths(spec_dir_abs, repo_root_abs)
    cache_updated = False

    for src_step in upstream_step_ids:
        spec_path = _find_spec_file(src_step, spec_dir_abs)
        if not spec_path or not os.path.isfile(spec_path):
            continue
        upstream_files.append(spec_path)

        try:
            data = _load_json(spec_path)
        except (OSError, json.JSONDecodeError):
            continue

        # Load step schema to understand property types.
        merged_schema: dict[str, Any] = {}
        uri: str | None = None
        if registry is not None:
            try:
                uri = _find_step_schema_uri(src_step, registry)
                if uri:
                    raw_schema = registry.load(uri)
                    merged_schema = _merge_allof(raw_schema, registry)
            except Exception:
                pass

        schema_props = merged_schema.get("properties", {})

        # Check extraction_paths.json cache for this src_step.
        cached_fields: dict[str, list[str]] | None = None
        if registry is not None and uri:
            if _cache_is_fresh(extraction_cache, src_step, uri, registry):
                cached_fields = extraction_cache.get(src_step)

        # Walk each top-level key of the spec data.
        keys_to_process = list(data.keys())
        if cached_fields is not None:
            # Use cache to restrict which keys to process.
            allowed: set[str] = set()
            for paths in cached_fields.values():
                for p in paths:
                    # Extract the top-level key from jq paths like ".goals" or ".capabilities[]"
                    key_match = p.lstrip(".").split("[")[0].split("|")[0].strip()
                    if key_match:
                        allowed.add(key_match)
            if allowed:
                keys_to_process = [k for k in keys_to_process if k in allowed or k in _BOILERPLATE_KEYS]

        keys_before = set(context.keys())
        for key in keys_to_process:
            value = data[key]
            if key in _BOILERPLATE_KEYS:
                continue

            if isinstance(value, list):
                prop_schema = schema_props.get(key, {})
                is_traceable, id_field = _is_traceable_array(prop_schema)

                if is_traceable and id_field and resolved_id_set and not full:
                    # Traceable: filter to resolved_ids.
                    filtered = [
                        item
                        for item in value
                        if isinstance(item, dict)
                        and item.get(id_field) in resolved_id_set
                    ]
                    # Strip boilerplate keys from each item.
                    filtered = [
                        {k: v for k, v in item.items() if k not in _BOILERPLATE_KEYS}
                        for item in filtered
                    ]
                    context[key] = filtered
                elif not is_traceable and not full:
                    # Non-traceable: required-fields mode (Tier 1).
                    item_schema = prop_schema.get("items", {})
                    item_required = item_schema.get("required", [])
                    stripped = [
                        _strip_to_required(
                            {k: v for k, v in item.items() if k not in _BOILERPLATE_KEYS},
                            item_required,
                        )
                        for item in value
                        if isinstance(item, dict)
                    ]
                    # Tier 2: truncate if item count exceeds threshold.
                    if len(stripped) > _TIER2_THRESHOLD:
                        total = len(stripped)
                        stripped = stripped[:_TIER2_THRESHOLD]
                        stripped.insert(0, {
                            "_context_note": (
                                f"truncated to {_TIER2_THRESHOLD} of {total} items; "
                                "use --full to see all"
                            )
                        })
                    context[key] = stripped
                else:
                    # full=True or scope_label=="all" with no resolved_ids: keep all.
                    context[key] = [
                        {k: v for k, v in item.items() if k not in _BOILERPLATE_KEYS}
                        if isinstance(item, dict)
                        else item
                        for item in value
                    ]

            else:
                # Scalar or object: always include fully.
                context[key] = value

        if registry is not None and uri and cached_fields is None:
            # Cache miss: record payload keys for future use.
            schema_path = registry.resolve(uri)
            if schema_path:
                new_keys = set(context.keys()) - keys_before
                discovered: dict[str, list[str]] = {}
                for key in new_keys:
                    discovered[os.path.basename(spec_path)] = discovered.get(
                        os.path.basename(spec_path), []
                    ) + [f".{key}"]
                _update_cache_entry(extraction_cache, src_step, uri, schema_path, discovered)
                cache_updated = True

    if cache_updated:
        _save_extraction_paths(spec_dir_abs, repo_root_abs, extraction_cache)

    # ------------------------------------------------------------------
    # 5. Token estimates.
    # ------------------------------------------------------------------
    context_json = json.dumps(context)
    token_estimate = len(context_json) // 4

    vs_full_read_estimate: int = 0
    for fpath in upstream_files:
        try:
            vs_full_read_estimate += os.path.getsize(fpath)
        except OSError:
            pass
    vs_full_read_estimate = vs_full_read_estimate // 4

    return {
        "step": step_id,
        "scope": scope_label,
        "context": context,
        "token_estimate": token_estimate,
        "vs_full_read_estimate": vs_full_read_estimate,
    }
