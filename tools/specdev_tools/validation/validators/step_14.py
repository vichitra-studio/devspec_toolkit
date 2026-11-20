from __future__ import annotations

from datetime import date
from typing import Any

from ...core.errors import make_error, SpecError
from ...core.scope_helpers import dict_items


def validate_step_14(instance: dict[str, Any]) -> list[SpecError]:
    """Deep checks of a step 14 artifact: valid and ordered milestone dates.

    Duplicate milestone and task ids (E704) and a task ``depends_on`` cycle (E703) are the graph's checks, run by
    ``spec-check``. Reads only values of the expected type; a malformed ``milestones`` or milestone is skipped and
    left to the schema's own error. Never raises on wrong-typed input.
    """
    errors: list[SpecError] = []
    milestone_dates: list[tuple[str, str]] = []
    for milestone in dict_items(instance.get("milestones")):
        errors.extend(_date_errors(milestone, milestone_dates))
    if milestone_dates != sorted(milestone_dates, key=lambda x: x[0]):
        errors.append(make_error("E520", "Milestone target_date values are not ordered"))
    return errors


def _date_errors(milestone: dict[str, Any], milestone_dates: list[tuple[str, str]]) -> list[SpecError]:
    """E520 for an unparseable ``target_date``; a valid one is appended to *milestone_dates* with its milestone id."""
    target_date = milestone.get("target_date")
    mid = milestone.get("milestone_id")
    if not isinstance(target_date, str):
        return []
    try:
        date.fromisoformat(target_date)
    except ValueError:
        return [make_error("E520", f"Invalid target_date '{target_date}' in milestone '{mid}'")]
    if isinstance(mid, str):
        milestone_dates.append((target_date, mid))
    return []
