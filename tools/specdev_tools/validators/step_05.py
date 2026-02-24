from __future__ import annotations

from typing import Any


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

