from __future__ import annotations

from typing import Any


def validate_step_05(instance: dict[str, Any], toolkit_root: str) -> list[str]:
    errors: list[str] = []
    seen_api_ids: set[str] = set()
    seen_method_path: set[tuple[str, str]] = set()
    for i, api in enumerate(instance.get("apis", [])):
        api_id = api.get("api_id")
        method = api.get("method")
        path = api.get("path")
        if api_id in seen_api_ids:
            errors.append(f"Duplicate api_id '{api_id}' at index {i}")
        seen_api_ids.add(api_id)
        if method and path:
            key = (method, path)
            if key in seen_method_path:
                errors.append(f"Duplicate API method/path '{method} {path}' at index {i}")
            seen_method_path.add(key)
    return errors
