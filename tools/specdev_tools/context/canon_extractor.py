"""Canon vocabulary extractor for the DevSpec Toolkit context package.

Implements ``extract_canon(step_id, repo_root, spec_root=None) -> dict``.

Schema-driven kind discovery: walks the step's output schema to find _ref
fields, maps them to canon kinds via INFERENCE_RULES, then loads the relevant
canon/kinds/{kind}.json files.
"""
from __future__ import annotations

import json
import os
from typing import Any

from ..core.registry import SchemaRegistry
from ..core.constants import INFERENCE_RULES
from ._utils import (
    load_json as _u_load_json,
    find_step_schema_uri as _u_find_step_schema_uri,
    merge_allof as _u_merge_allof,
)


# ---------------------------------------------------------------------------
# Build a lookup: _ref field name -> canon kind, from INFERENCE_RULES.
# ---------------------------------------------------------------------------
_REF_TO_KIND: dict[str, str] = {
    rule[1]: rule[2] for rule in INFERENCE_RULES
}


def _load_json(path: str) -> Any:
    return _u_load_json(path)


def _find_step_schema_uri(step_id: str, registry: SchemaRegistry) -> str | None:
    """Search schema_registry for a URI that matches *step_id*."""
    return _u_find_step_schema_uri(step_id, registry)


def _merge_allof(schema: dict, registry: SchemaRegistry) -> dict:
    """Merge allOf branches into a single properties+required dict."""
    return _u_merge_allof(schema, registry)


_CANONICAL_REF_ANCHOR = "#canonicalRef"


def _is_canonical_ref_field(field_schema: dict[str, Any]) -> bool:
    """Return True if *field_schema* references the canonicalRef definition.

    Canonical _ref fields have ``$ref`` pointing to the canonicalRef anchor
    in vc:core:collections (e.g. ``"vc:core:collections#canonicalRef"``).
    Also detects the FC pattern: ``allOf: [{$ref: canonicalRef}, ...]``.
    Non-canonical _ref fields (fixture_ref, interface_ref in step 15, etc.)
    use ``vc:core:atoms#kebabId`` or other targets and must be excluded.
    """
    ref_target = field_schema.get("$ref", "")
    if ref_target.endswith(_CANONICAL_REF_ANCHOR):
        return True
    # FC pattern: allOf containing a $ref to canonicalRef
    all_of = field_schema.get("allOf")
    if isinstance(all_of, list):
        return any(
            isinstance(item, dict) and item.get("$ref", "").endswith(_CANONICAL_REF_ANCHOR)
            for item in all_of
        )
    return False



def _collect_ref_fields_split(
    schema: dict[str, Any],
) -> tuple[set[str], set[str]]:
    """Like _collect_ref_fields but splits into required vs optional.

    Walks properties recursively.  A *_ref field is "required" if it
    appears in a ``required`` array at the same level (or any ancestor
    that is itself required).

    Returns (required_fields, optional_fields).
    """
    required: set[str] = set()
    optional: set[str] = set()

    def _walk(obj: dict[str, Any]) -> None:
        props = obj.get("properties", {})
        req_keys = set(obj.get("required", []))
        for field_name, field_schema in props.items():
            if field_name.endswith("_ref") and _is_canonical_ref_field(field_schema):
                if field_name in req_keys:
                    required.add(field_name)
                else:
                    optional.add(field_name)
            # Recurse into array items
            if isinstance(field_schema, dict) and field_schema.get("type") == "array":
                items = field_schema.get("items", {})
                if isinstance(items, dict):
                    _walk(items)
            # Recurse into object
            elif isinstance(field_schema, dict) and field_schema.get("type") == "object":
                _walk(field_schema)

    _walk(schema)
    return required, optional


def _load_kind_entries(kind: str, repo_root: str) -> list[dict[str, Any]]:
    """Load entries from ``canon/kinds/{kind}.json``.

    The file has the structure:
      {"kind": "...", "entries": [...]}

    Each entry has ``id``, ``preferred_label``, ``definition``, ``aliases``.
    """
    kind_path = os.path.join(repo_root, "canon", "kinds", f"{kind}.json")
    if not os.path.isfile(kind_path):
        return []
    try:
        data = _load_json(kind_path)
    except (OSError, json.JSONDecodeError):
        return []

    raw_entries: list[Any]
    if isinstance(data, list):
        raw_entries = data
    elif isinstance(data, dict):
        raw_entries = data.get("entries", [])
    else:
        return []

    result: list[dict[str, Any]] = []
    for entry in raw_entries:
        if not isinstance(entry, dict):
            continue
        result.append({
            "id": entry.get("id", ""),
            "preferred_label": entry.get("preferred_label", ""),
            "definition": entry.get("definition", ""),
            "aliases": entry.get("aliases", []),
        })
    return result


def extract_canon(step_id: str, repo_root: str, spec_root: str | None = None) -> dict[str, Any]:
    """Extract canon vocabulary needed for a pipeline step.

    Parameters
    ----------
    step_id:
        Pipeline step identifier (e.g. ``"04"``, ``"05"``).
    repo_root:
        Path to the devspec_toolkit repo root (toolkit-tier canon).
    spec_root:
        Optional path to the host project's spec directory. When provided,
        project-tier entries from ``{spec_root}/canon/kinds/{kind}.json`` are
        merged after toolkit entries, so project-specific terms are visible
        alongside core vocabulary.

    Returns
    -------
    dict with keys: step, canon_kinds, total_entries, token_estimate
    """
    repo_root_abs = os.path.abspath(repo_root)

    # ------------------------------------------------------------------
    # 1. Load the step schema and collect _ref fields.
    # ------------------------------------------------------------------
    ref_fields: set[str] = set()
    required_ref_fields: set[str] = set()
    optional_ref_fields: set[str] = set()
    try:
        registry = SchemaRegistry(repo_root_abs)
        uri = _find_step_schema_uri(step_id, registry)
        if uri:
            raw_schema = registry.load(uri)
            merged = _merge_allof(raw_schema, registry)
            required_ref_fields, optional_ref_fields = _collect_ref_fields_split(merged)
            ref_fields = required_ref_fields | optional_ref_fields
    except Exception:
        pass

    # ------------------------------------------------------------------
    # 2. Map _ref fields to canon kinds (deduplicated, preserving order).
    # ------------------------------------------------------------------
    kinds_needed: list[str] = []
    seen_kinds: set[str] = set()
    for ref_field in sorted(ref_fields):
        kind = _REF_TO_KIND.get(ref_field)
        if kind and kind not in seen_kinds:
            kinds_needed.append(kind)
            seen_kinds.add(kind)

    # ------------------------------------------------------------------
    # 3. Load entries for each kind — toolkit tier first, then project tier.
    # ------------------------------------------------------------------
    # Resolve project canon directory: {spec_root}/canon/ when spec_root given.
    project_canon_root: str | None = None
    if spec_root:
        candidate = os.path.join(os.path.abspath(spec_root), "canon")
        if os.path.isdir(candidate):
            project_canon_root = candidate

    canon_kinds: dict[str, list[dict[str, Any]]] = {}
    total_entries = 0
    for kind in kinds_needed:
        # Toolkit-tier entries (e.g. devspec_toolkit/canon/kinds/term.json)
        entries = _load_kind_entries(kind, repo_root_abs)
        # Project-tier entries merged in (e.g. spec/canon/kinds/term.json)
        if project_canon_root:
            project_root_for_kind = os.path.dirname(project_canon_root)  # parent of canon/
            project_entries = _load_kind_entries(kind, project_root_for_kind)
            # Deduplicate by id — toolkit entries take precedence; project entries whose id
            # already exists in the toolkit tier are skipped. In practice this is a no-op
            # because toolkit IDs are cn:core:* and project IDs are cn:project:*.
            toolkit_ids = {e["id"] for e in entries}
            entries = entries + [e for e in project_entries if e["id"] not in toolkit_ids]
        canon_kinds[kind] = entries
        total_entries += len(entries)

    # ------------------------------------------------------------------
    # 4. Token estimate.
    # ------------------------------------------------------------------
    token_estimate = len(json.dumps(canon_kinds)) // 4

    # ------------------------------------------------------------------
    # 5. Required vs optional kind split.
    # ------------------------------------------------------------------
    req_kinds: list[str] = []
    opt_kinds: list[str] = []
    req_seen: set[str] = set()
    opt_seen: set[str] = set()
    for rf in sorted(required_ref_fields):
        k = _REF_TO_KIND.get(rf)
        if k and k not in req_seen:
            req_kinds.append(k)
            req_seen.add(k)
    for rf in sorted(optional_ref_fields):
        k = _REF_TO_KIND.get(rf)
        if k and k not in opt_seen and k not in req_seen:
            opt_kinds.append(k)
            opt_seen.add(k)

    return {
        "step": step_id,
        "canon_kinds": canon_kinds,
        "canon_kinds_required": req_kinds,
        "canon_kinds_optional": opt_kinds,
        "total_entries": total_entries,
        "token_estimate": token_estimate,
    }
