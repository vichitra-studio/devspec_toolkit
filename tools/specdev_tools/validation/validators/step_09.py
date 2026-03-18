from __future__ import annotations

from datetime import date
from typing import Any

from ...core.errors import make_error, SpecError
from ...core.loaders import load_upstream_ids
from ...validation.linter_utils import check_no_duplicates


def validate_step_09(instance: dict[str, Any], toolkit_root: str) -> list[SpecError]:
    errors: list[SpecError] = []
    check_no_duplicates(instance.get("milestones", []), "milestone_id", "milestone_id", errors)
    dates: list[tuple[str, str]] = []
    for milestone in instance.get("milestones", []):
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

    # Cross-step capability reference validation
    capability_ids = load_upstream_ids(toolkit_root, "01", "capabilities", "capability_id")
    if capability_ids is None:
        errors.append(
            make_error("W590", "CROSS_STEP_UPSTREAM_MISSING 01_capabilities.json not found; "
            "skipping capability reference validation")
        )
    else:
        for milestone in instance.get("milestones", []):
            milestone_id = milestone.get("milestone_id", "<unknown>")
            # Check deliverables traceRef objects with type "capability"
            for ref_obj in milestone.get("deliverables", []):
                if isinstance(ref_obj, dict) and ref_obj.get("type") == "capability":
                    cap_ref = ref_obj.get("id")
                    if isinstance(cap_ref, str) and cap_ref not in capability_ids:
                        errors.append(
                            make_error("E590", f"CROSS_STEP_ID_NOT_FOUND milestone "
                            f"'{milestone_id}' references unknown capability "
                            f"'{cap_ref}' (not in 01_capabilities.json)")
                        )

    return errors
