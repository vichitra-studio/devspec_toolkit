from __future__ import annotations

import json
import os
from datetime import date
from typing import Any, Optional, Set


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

    # Cross-step capability reference validation
    capability_ids = _load_capability_ids(toolkit_root)
    if capability_ids is None:
        errors.append(
            "W590 CROSS_STEP_UPSTREAM_MISSING 01_capabilities.json not found; "
            "skipping capability reference validation"
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
                            f"E590 CROSS_STEP_ID_NOT_FOUND milestone "
                            f"'{milestone_id}' references unknown capability "
                            f"'{cap_ref}' (not in 01_capabilities.json)"
                        )

    return errors


def _load_capability_ids(toolkit_root: str) -> Optional[Set[str]]:
    """Load capability IDs from step 01 if available."""
    spec_dir = os.path.join(toolkit_root, "spec")
    if not os.path.isdir(spec_dir):
        return None

    for fn in os.listdir(spec_dir):
        if fn.startswith("01_") and fn.endswith(".json"):
            path = os.path.join(spec_dir, fn)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return {
                    cap.get("capability_id")
                    for cap in data.get("capabilities", [])
                    if isinstance(cap, dict) and cap.get("capability_id")
                }
            except (OSError, json.JSONDecodeError):
                pass
    return None
