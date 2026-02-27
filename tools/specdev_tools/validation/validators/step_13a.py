from __future__ import annotations

import re
from typing import Any

ELEMENT_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def validate_step_13a(instance: dict[str, Any], toolkit_root: str) -> list[str]:
    errors: list[str] = []
    for item in instance.get("missing_elements", []):
        element_id = item.get("element_id")
        if isinstance(element_id, str) and not ELEMENT_ID_PATTERN.match(element_id):
            errors.append(f"Element has element_id '{element_id}' that does not follow kebab-case convention")
        score = item.get("impact_score")
        if isinstance(score, (int, float)) and not (0 <= score <= 100):
            errors.append(f"Invalid impact_score for '{element_id}': {score}")
    summary = instance.get("summary", {})
    if isinstance(summary, dict):
        completeness = summary.get("completeness")
        if isinstance(completeness, (int, float)) and not (0 <= completeness <= 100):
            errors.append(f"Invalid summary.completeness: {completeness}")
        if isinstance(completeness, (int, float)) and completeness < 100:
            missing = instance.get("missing_elements", [])
            if not missing:
                errors.append(f"summary.completeness is {completeness} (< 100) but missing_elements is empty")
    return errors
