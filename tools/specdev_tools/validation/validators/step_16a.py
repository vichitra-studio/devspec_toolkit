"""Step 16a (Plan phase) validator.

Validates the planning phase of the Trinity Loop: milestone checklists and
review-to-plan remediation links on top of the base step_16 checks.
"""
from __future__ import annotations

from typing import Any, Optional

from ...core.errors import make_error, SpecError
from ...core.scope_helpers import dict_items, str_items
from .step_16 import _checklist_of, validate_step_16


def validate_step_16a(data: dict[str, Any], toolkit_root: str, spec_path: Optional[str] = None, spec_root: Optional[str] = None) -> list[SpecError]:
    """Deep validation for Step 16a (Plan phase)."""
    errors = validate_step_16(data, toolkit_root, spec_path, spec_root)

    plan = data.get("plan", {})
    if not isinstance(plan, dict):
        errors.append(make_error("E520", "Step 16a requires a 'plan' object"))
        return errors

    seen_ids: set[str] = set()
    for i, item in enumerate(_checklist_of(plan)):
        item_id = item.get("id")
        if isinstance(item_id, str) and item_id:
            if item_id in seen_ids:
                errors.append(make_error("E520", f"Step 16a: duplicate checklist id '{item_id}' at index {i}"))
            seen_ids.add(item_id)

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
        for finding in dict_items(review.get("findings")):
            rem = finding.get("remediation_task")
            if not isinstance(rem, dict):
                continue
            task_id = rem.get("task_id", "<unknown>")
            linked_ids = rem.get("checklist_ids")
            unknown = [cid for cid in str_items(linked_ids) if cid not in seen_ids]
            if unknown:
                errors.append(make_error(
                    "W584",
                    f"REMEDIATION_TASK_LINK_UNKNOWN: review remediation task '{task_id}' "
                    f"references unknown checklist ids: {', '.join(str(c) for c in unknown)}",
                ))

    return errors
