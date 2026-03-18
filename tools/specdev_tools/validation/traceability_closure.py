from __future__ import annotations
import json
import os
import warnings
from typing import Any

from ..core.errors import SpecError, make_error
from ..core.trace_types import is_valid_trace_type, normalize_trace_type

# ---------------------------------------------------------------------------
# Business-rule trace-type constants for traceability closure chains
# ---------------------------------------------------------------------------

# Business rule: capabilities trace back to charter goals.
# Rationale: the charter (Step 00) defines high-level goals. Capabilities
# (Step 01) prove each goal is decomposed into at least one user-facing
# capability.  The "charter-goal" trace type links capability -> goal.
# NOTE: "charter-goal" was added to canon as cn:core:trace_type:charter-goal.
_CHARTER_GOAL_TRACE_TYPE: str = "charter-goal"

# Business rule: FRs trace back to capabilities.
# Rationale: each FR (Step 04) must reference at least one capability
# (Step 01) to show the functional requirement is grounded in a user-facing
# capability.  The "capability" trace type links FR -> capability.
_CAPABILITY_TRACE_TYPE: str = "capability"

# Validate at definition time
for _label, _value in [
    ("_CHARTER_GOAL_TRACE_TYPE", _CHARTER_GOAL_TRACE_TYPE),
    ("_CAPABILITY_TRACE_TYPE", _CAPABILITY_TRACE_TYPE),
]:
    if not is_valid_trace_type(_value):
        warnings.warn(
            f"traceability_closure: {_label} '{_value}' is not a valid canon trace type",
            stacklevel=1,
        )

SPEC_FILES = {
    "charter": "00_charter.json",
    "capabilities": "01_capabilities.json",
    "frs": "04_fr_list.json",
    "roadmap": "14_roadmap.json",
    "impl_planner": "16a_impl_planner.json",
}


def check_traceability_closure(spec_dir: str, repo_root: str | None = None) -> list[SpecError]:
    errors: list[SpecError] = []

    # Resolve spec_dir relative to repo_root if it's a relative path
    if repo_root and not os.path.isabs(spec_dir):
        spec_dir = os.path.join(repo_root, spec_dir)

    data: dict[str, Any] = {}
    for key, filename in SPEC_FILES.items():
        # I5: fallback for impl_planner: try 16a first, then 16_impl_context.json
        if key == "impl_planner":
            primary_path = os.path.join(spec_dir, filename)
            fallback_path = os.path.join(spec_dir, "16_impl_context.json")
            if not os.path.isfile(primary_path) and os.path.isfile(fallback_path):
                filename = "16_impl_context.json"
        path = os.path.join(spec_dir, filename)
        if not os.path.isfile(path):
            if key == "charter":
                continue  # Charter is optional for backwards compat
            errors.append(make_error("W570", f"GRACEFUL_SKIP missing_spec_file {filename}"))
            continue
        try:
            with open(path, encoding="utf-8") as f:
                data[key] = json.load(f)
        except (OSError, json.JSONDecodeError):
            if key == "charter":
                continue
            errors.append(make_error("W570", f"GRACEFUL_SKIP unreadable_spec_file {filename}"))
            continue

    capability_ids: set[str] = set()
    if "capabilities" in data:
        capability_ids = {c.get("capability_id") for c in data["capabilities"].get("capabilities", []) if c.get("capability_id")}

    # Charter → Capabilities chain
    if "charter" in data and "capabilities" in data:
        charter_goals = data["charter"]
        goal_ids: set[str] = set()
        for goal in charter_goals.get("goals", []):
            if isinstance(goal, dict) and goal.get("goal_id"):
                goal_ids.add(goal["goal_id"])

        if goal_ids:
            cap_traced_goals: set[str] = set()
            for cap in data["capabilities"].get("capabilities", []):
                for trace_ref in cap.get("trace", []):
                    if isinstance(trace_ref, dict) and normalize_trace_type(trace_ref.get("type") or "") == _CHARTER_GOAL_TRACE_TYPE and "id" in trace_ref:
                        cap_traced_goals.add(trace_ref["id"])

            for goal_id in sorted(goal_ids - cap_traced_goals):
                errors.append(make_error("E560", f"TRACEABILITY_GAP charter_goal_without_capability {goal_id}"))

    fr_traced_caps: set[str] = set()
    fr_ids: set[str] = set()
    if "frs" in data:
        for fr in data["frs"].get("functional_requirements", []):
            if "fr_id" in fr:
                fr_ids.add(fr["fr_id"])
            for cap_ref in fr.get("trace", []):
                if isinstance(cap_ref, dict) and normalize_trace_type(cap_ref.get("type") or "") == _CAPABILITY_TRACE_TYPE and "id" in cap_ref:
                    fr_traced_caps.add(cap_ref["id"])

    milestone_fr_refs: set[str] = set()
    milestone_ids: set[str] = set()
    milestone_task_ids: dict[str, list[str]] = {}
    if "roadmap" in data:
        for ms in data["roadmap"].get("milestones", []):
            ms_id = ms.get("milestone_id")
            if ms_id:
                milestone_ids.add(ms_id)
                milestone_task_ids[ms_id] = [t.get("task_id") for t in ms.get("tasks", []) if t.get("task_id")]
            for fr_ref in ms.get("fr_refs", []):
                milestone_fr_refs.add(fr_ref)

    checklist_milestone_refs: set[str] = set()
    checklist_task_refs: set[str] = set()
    if "impl_planner" in data:
        impl_data = data["impl_planner"]
        checklist = impl_data.get("plan", {}).get("spec_alignment", {}).get("checklist", [])
        for item in checklist:
            spec_ref = item.get("spec_ref", {})
            if isinstance(spec_ref, dict) and "id" in spec_ref:
                checklist_task_refs.add(spec_ref["id"])

        for ms_id, tasks in milestone_task_ids.items():
            if any(t_id in checklist_task_refs for t_id in tasks):
                checklist_milestone_refs.add(ms_id)

    if "capabilities" in data and "frs" in data:
        for cap_id in sorted(capability_ids - fr_traced_caps):
            errors.append(make_error("E560", f"TRACEABILITY_GAP capability_without_fr {cap_id}"))

    if "frs" in data and "roadmap" in data:
        for fr_id in sorted(fr_ids - milestone_fr_refs):
            errors.append(make_error("W561", f"UNCOVERED_FR {fr_id}"))

    if "roadmap" in data and "impl_planner" in data:
        for ms_id in sorted(milestone_ids - checklist_milestone_refs):
            errors.append(make_error("W562", f"ORPHAN_MILESTONE {ms_id}"))

        # Task-level traceability: each task should be referenced by at least one checklist item
        for ms_id, tasks in milestone_task_ids.items():
            for task_id in tasks:
                if task_id not in checklist_task_refs:
                    errors.append(make_error("W563", f"CHECKLIST_ROADMAP_MISMATCH {task_id} (milestone: {ms_id})"))

    return errors
