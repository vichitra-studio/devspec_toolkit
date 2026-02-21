from __future__ import annotations

from typing import Any


def validate_step_13a(instance: dict[str, Any], toolkit_root: str) -> list[str]:
    errors: list[str] = []
    for item in instance.get("missing_elements", []):
        score = item.get("impact_score")
        if isinstance(score, (int, float)) and not (0 <= score <= 100):
            errors.append(f"Invalid impact_score for '{item.get('element_id')}': {score}")
    summary = instance.get("summary", {})
    if isinstance(summary, dict):
        completeness = summary.get("completeness")
        if isinstance(completeness, (int, float)) and not (0 <= completeness <= 100):
            errors.append(f"Invalid summary.completeness: {completeness}")
    return errors
