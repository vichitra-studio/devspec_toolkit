from __future__ import annotations

from datetime import date
from typing import Any


def validate_step_09(instance: dict[str, Any], toolkit_root: str) -> list[str]:
    errors: list[str] = []
    seen_milestones: set[str] = set()
    dates: list[tuple[str, str]] = []
    for i, milestone in enumerate(instance.get("milestones", [])):
        milestone_id = milestone.get("milestone_id")
        if milestone_id in seen_milestones:
            errors.append(f"Duplicate milestone_id '{milestone_id}' at index {i}")
        seen_milestones.add(milestone_id)
        target_date = milestone.get("target_date")
        if isinstance(target_date, str):
            try:
                date.fromisoformat(target_date)
                dates.append((target_date, milestone_id))
            except ValueError:
                errors.append(f"Invalid target_date '{target_date}' in milestone '{milestone_id}'")
    if dates != sorted(dates, key=lambda x: x[0]):
        errors.append("Milestone target_date values are not ordered")
    return errors
