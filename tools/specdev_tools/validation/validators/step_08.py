from __future__ import annotations

from typing import Any


def validate_step_08(instance: dict[str, Any], toolkit_root: str) -> list[str]:
    errors: list[str] = []
    seen_ids: set[str] = set()
    for i, fixture in enumerate(instance.get("fixtures", [])):
        fixture_id = fixture.get("fixture_id")
        if fixture_id in seen_ids:
            errors.append(f"Duplicate fixture_id '{fixture_id}' at index {i}")
        seen_ids.add(fixture_id)
        if not fixture.get("targets"):
            errors.append(f"Fixture '{fixture_id}' missing targets")
    return errors
