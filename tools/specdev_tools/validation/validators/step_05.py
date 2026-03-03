from __future__ import annotations

import json
import os
from typing import Any, Optional, Set


def validate_step_05(instance: dict[str, Any], toolkit_root: str) -> list[str]:
    errors: list[str] = []
    seen_api_ids: set[str] = set()
    seen_method_route: set[tuple[str, str]] = set()
    for i, api in enumerate(instance.get("apis", [])):
        api_id = api.get("api_id")
        method = api.get("method")
        route = api.get("route") or api.get("path")  # schema uses 'route'; fallback for backward compat
        if api_id in seen_api_ids:
            errors.append(f"Duplicate api_id '{api_id}' at index {i}")
        seen_api_ids.add(api_id)
        if method and route:
            key = (method, route)
            if key in seen_method_route:
                errors.append(f"Duplicate API method/route '{method} {route}' at index {i}")
            seen_method_route.add(key)
        # D25: Enum provenance check
        if _has_enum_values(api) and not api.get("enum_provenance"):
            errors.append(
                f"E310 MISSING_ENUM_PROVENANCE api '{api_id or i}' has enum values "
                f"but no enum_provenance for reproducibility tracking"
            )

    # Cross-step FR reference validation
    fr_ids = _load_fr_ids(toolkit_root)
    if fr_ids is None:
        errors.append(
            "W590 CROSS_STEP_UPSTREAM_MISSING 04_fr_list.json not found; "
            "skipping FR reference validation"
        )
    else:
        for api in instance.get("apis", []):
            api_id = api.get("api_id", "<unknown>")
            fr_refs = _extract_fr_refs(api)
            for fr_ref in fr_refs:
                if fr_ref not in fr_ids:
                    errors.append(
                        f"E590 CROSS_STEP_ID_NOT_FOUND api '{api_id}' references "
                        f"unknown FR '{fr_ref}' (not in 04_fr_list.json)"
                    )

    return errors


def _has_enum_values(api: dict[str, Any]) -> bool:
    """Check if API has enum-like values in errors or parameters."""
    for field in ("errors", "error_codes"):
        val = api.get(field)
        if isinstance(val, list) and len(val) > 0:
            return True
        if isinstance(val, dict) and len(val) > 0:
            return True
    params = api.get("parameters", [])
    if isinstance(params, list):
        for param in params:
            if isinstance(param, dict) and "enum" in param:
                return True
    return False


def _extract_fr_refs(api: dict[str, Any]) -> list[str]:
    """Extract all FR references from an API contract.

    Collects FR IDs from the ``trace`` array — traceRef objects where
    ``id`` starts with ``fr-``.
    """
    refs: list[str] = []
    trace = api.get("trace", [])
    if isinstance(trace, list):
        for entry in trace:
            if isinstance(entry, dict):
                trace_id = entry.get("id")
                if isinstance(trace_id, str) and trace_id.startswith("fr-"):
                    refs.append(trace_id)
    return refs


def _load_fr_ids(toolkit_root: str) -> Optional[Set[str]]:
    """Load FR IDs from step 04 if available.

    Returns a set of fr_id strings, or None if the upstream file is not found.
    """
    spec_dir = os.path.join(toolkit_root, "spec")
    for fn in os.listdir(spec_dir) if os.path.isdir(spec_dir) else []:
        if fn.startswith("04_") and fn.endswith(".json"):
            path = os.path.join(spec_dir, fn)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return {
                    fr.get("fr_id")
                    for fr in data.get("functional_requirements", [])
                    if isinstance(fr, dict) and fr.get("fr_id")
                }
            except (OSError, json.JSONDecodeError):
                pass
    return None

