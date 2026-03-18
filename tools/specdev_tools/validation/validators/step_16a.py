"""Step 16a (Plan phase) validator.

Validates the planning phase of the Trinity Loop: milestone checklists,
FR references, and dependency validation on top of the base step_16 checks.
"""
from __future__ import annotations

from typing import Any, Optional

from ...core.errors import make_error, SpecError
from .step_16 import validate_step_16


def validate_step_16a(data: dict[str, Any], toolkit_root: str, spec_path: Optional[str] = None) -> list[SpecError]:
    """Deep validation for Step 16a (Plan phase)."""
    errors = validate_step_16(data, toolkit_root, spec_path)

    plan = data.get("plan", {})
    if not isinstance(plan, dict):
        errors.append(make_error("E520", "Step 16a requires a 'plan' object"))
        return errors

    # Plan phase must have a status
    if not plan.get("status"):
        errors.append(make_error("E520", "Step 16a plan.status is required"))

    # Checklist items should have spec_ref with id for plan phase
    checklist = plan.get("spec_alignment", {}).get("checklist", [])
    seen_ids: set[str] = set()
    for i, item in enumerate(checklist):
        if not isinstance(item, dict):
            continue
        item_id = item.get("id")
        if item_id:
            if item_id in seen_ids:
                errors.append(make_error("E520", f"Step 16a: duplicate checklist id '{item_id}' at index {i}"))
            seen_ids.add(item_id)

        # Plan phase items should have spec_ref
        spec_ref = item.get("spec_ref")
        if not isinstance(spec_ref, dict) or not spec_ref.get("id"):
            if item.get("checklist_status") != "deferred":
                errors.append(
                    make_error("E590", f"Step 16a: checklist item '{item_id or i}' is active but missing spec_ref.id")
                )

    return errors
