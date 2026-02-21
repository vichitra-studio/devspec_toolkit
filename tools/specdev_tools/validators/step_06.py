from __future__ import annotations

from typing import Any


def validate_step_06(instance: dict[str, Any], toolkit_root: str) -> list[str]:
    errors: list[str] = []
    seen_ids: set[str] = set()
    for i, rule in enumerate(instance.get("rules", [])):
        inv_id = rule.get("inv_id")
        if inv_id in seen_ids:
            errors.append(f"Duplicate inv_id '{inv_id}' at index {i}")
        seen_ids.add(inv_id)
        if not rule.get("trace"):
            errors.append(f"Invariant '{inv_id}' missing trace")
    return errors
