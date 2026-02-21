from __future__ import annotations

from typing import Any


def validate_step_13(instance: dict[str, Any], toolkit_root: str) -> list[str]:
    errors: list[str] = []
    seen_ids: set[str] = set()
    for i, ext in enumerate(instance.get("extensions", [])):
        ext_id = ext.get("extension_id")
        if ext_id in seen_ids:
            errors.append(f"Duplicate extension_id '{ext_id}' at index {i}")
        seen_ids.add(ext_id)
        if not ext.get("required_schema_sections"):
            errors.append(f"Extension '{ext_id}' missing required_schema_sections")
    return errors
