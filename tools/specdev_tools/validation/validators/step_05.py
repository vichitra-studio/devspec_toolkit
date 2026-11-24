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
                f"and relies on a third party but has no enum_provenance")
            )

    return errors


def _has_externally_sourced_enum(api: dict[str, Any]) -> bool:
    """Return True when *api* relies on a third party and a parameter of it carries an ``enum``.

    An enum of an API that relies on a third party is read as taken from it; an API
    that relies on none has first-party value sets. ``errors`` and ``error_codes``
    never trigger E311.
    """
    relies_on = api.get("relies_on")
    if not isinstance(relies_on, list) or not relies_on:
        return False
    params = api.get("parameters", [])
    if not isinstance(params, list):
        return False
    return any(isinstance(param, dict) and "enum" in param for param in params)
