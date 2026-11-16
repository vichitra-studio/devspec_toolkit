from __future__ import annotations

from datetime import date
from typing import Any

from ...core.scope_helpers import as_list, dict_items
from ...core.errors import make_error, SpecError


def validate_step_09(instance: dict[str, Any], toolkit_root: str, spec_root: str | None = None) -> list[SpecError]:
    """Validate Step 09 (design milestones): unique ``milestone_id`` and ISO ``target_date`` values in date order.

    ``toolkit_root`` and ``spec_root`` are the dispatcher's common signature; no check reads another step.
    """
    errors: list[SpecError] = []
    milestones = as_list(instance.get("milestones"))
    dates: list[tuple[str, str]] = []
    for milestone in dict_items(milestones):
        milestone_id = milestone.get("milestone_id")
        target_date = milestone.get("target_date")
        if isinstance(target_date, str):
            try:
                date.fromisoformat(target_date)
                dates.append((target_date, milestone_id))
            except ValueError:
                errors.append(make_error("E520", f"Invalid target_date '{target_date}' in milestone '{milestone_id}'"))
    if dates != sorted(dates, key=lambda x: x[0]):
        errors.append(make_error("E520", "Milestone target_date values are not ordered"))
    return errors
