from __future__ import annotations

from typing import Any

from ...core.errors import make_error, SpecError
from ...core.scope_helpers import dict_items


def validate_step_05(instance: dict[str, Any], toolkit_root: str, spec_root: str | None = None) -> list[SpecError]:
    """Deep validation for Step 05 (Interface Contracts).

    ``toolkit_root`` and ``spec_root`` are unused since the link checks left (the graph resolver
    owns them); they are kept for the uniform ``DEEP_VALIDATORS`` call shape.
    """
    errors: list[SpecError] = []
    apis = dict_items(instance.get("apis"))
    seen_method_route: set[tuple[str, str]] = set()
    for i, api in enumerate(apis):
        api_id = api.get("api_id")
        method = api.get("method")
        route = api.get("path") or api.get("route")  # schema uses 'path'; fallback for backward compat
        if isinstance(method, str) and isinstance(route, str) and method and route:
            key = (method, route)
            if key in seen_method_route:
                errors.append(make_error("E520", f"Duplicate API method/route '{method} {route}' at index {i}"))
            seen_method_route.add(key)
        # D25: Enum provenance check
        if _has_externally_sourced_enum(api) and not api.get("enum_provenance"):
            errors.append(
                make_error("E311", f"MISSING_ENUM_PROVENANCE api '{api_id or i}' declares a parameter enum "
                f"but no enum_provenance for reproducibility tracking")
            )

    return errors


def _has_externally_sourced_enum(api: dict[str, Any]) -> bool:
    """Return True when any declared parameter of *api* carries an ``enum``.

    Structure cannot tell an external value set (ISO 4217, IANA tags) from an
    internal one, so every parameter enum is asked for ``enum_provenance``.
    ``errors`` and ``error_codes`` never trigger E311.
    """
    params = api.get("parameters", [])
    if not isinstance(params, list):
        return False
    return any(isinstance(param, dict) and "enum" in param for param in params)
