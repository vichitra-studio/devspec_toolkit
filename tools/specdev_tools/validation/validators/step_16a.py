"""Step 16a (Plan phase) validator.

Validates the planning phase of the Trinity Loop: milestone checklists,
FR references, and dependency validation on top of the base step_16 checks.
"""
from __future__ import annotations

from typing import Any, Optional

from ...core.errors import make_error, SpecError
from .step_16 import validate_step_16


def validate_step_16a(data: dict[str, Any], toolkit_root: str, spec_path: Optional[str] = None, spec_root: Optional[str] = None, nfrs_data: Optional[dict[str, Any]] = None) -> list[SpecError]:
    """Deep validation for Step 16a (Plan phase)."""
    errors = validate_step_16(data, toolkit_root, spec_path, spec_root, nfrs_data)

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

    # W584: review→plan feedback loop.  Under the post-split model (16a/16b/16c
    # all share one ``spec/impl_context/{milestone_id}.json`` artifact that
    # grows as phases execute), a ``review`` section populated by 16c lives on
    # the same ``data`` dict as the 16a plan.  When chain-up validation reaches
    # ``validate_step_16a`` for a 16c-phase artifact, any remediation_task
    # surfaced by the reviewer must be represented as a checklist item in the
    # plan — otherwise the planner has accepted a review without incorporating
    # the remediation work.  No sibling file lookup is needed; the pre-split
    # ``16c_review.json`` path resolution was phantom and silently disabled
    # this check in every real Trinity run.
    review = data.get("review")
    if isinstance(review, dict):
        for finding in review.get("findings", []):
            if not isinstance(finding, dict):
                continue
            rem = finding.get("remediation_task")
            if not isinstance(rem, dict):
                continue
            task_id = rem.get("task_id", "<unknown>")
            linked_ids = rem.get("checklist_ids") or []
            unknown = [cid for cid in linked_ids if cid not in seen_ids]
            if unknown:
                errors.append(make_error(
                    "W584",
                    f"REMEDIATION_TASK_LINK_UNKNOWN: review remediation task '{task_id}' "
                    f"references unknown checklist ids: {', '.join(str(c) for c in unknown)}",
                ))

    return errors
