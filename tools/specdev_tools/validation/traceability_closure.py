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

# Business rule: APIs and fixtures trace to FRs.
# Rationale: pairwise completeness checks (W564, W565) verify that each FR
# is covered by at least one API trace and at least one fixture target.
# The "fr" trace type links API/fixture -> FR.
_FR_TRACE_TYPE: str = "fr"

# Validate at definition time
for _label, _value in [
    ("_CHARTER_GOAL_TRACE_TYPE", _CHARTER_GOAL_TRACE_TYPE),
    ("_CAPABILITY_TRACE_TYPE", _CAPABILITY_TRACE_TYPE),
    ("_FR_TRACE_TYPE", _FR_TRACE_TYPE),
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
    "apis": "05_interface_contracts.json",
    "fixtures": "08_fixtures.json",
    "roadmap": "14_roadmap.json",
    "impl_planner": "16a_impl_planner.json",
}

def check_traceability_closure(spec_dir: str, repo_root: str | None = None) -> list[SpecError]:
    errors: list[SpecError] = []

    # Resolve spec_dir relative to repo_root if it's a relative path
    if repo_root and not os.path.isabs(spec_dir):
        spec_dir = os.path.join(repo_root, spec_dir)

    data: dict[str, Any] = {}
    # Keys that are silently optional — coverage checks fire only when present.
    _optional_keys = {"charter", "apis", "fixtures"}
    for key, filename in SPEC_FILES.items():
        # I5: fallback for impl_planner: try 16a first, then 16_impl_context.json
        if key == "impl_planner":
            primary_path = os.path.join(spec_dir, filename)
            fallback_path = os.path.join(spec_dir, "16_impl_context.json")
            if not os.path.isfile(primary_path) and os.path.isfile(fallback_path):
                filename = "16_impl_context.json"
        path = os.path.join(spec_dir, filename)
        if not os.path.isfile(path):
            if key in _optional_keys:
                continue  # Silently skip optional spec files
            errors.append(make_error("W570", f"GRACEFUL_SKIP missing_spec_file {filename}"))
            continue
        try:
            with open(path, encoding="utf-8") as f:
                data[key] = json.load(f)
        except (OSError, json.JSONDecodeError):
            if key in _optional_keys:
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
    milestone_fr_set: dict[str, set[str]] = {}
    milestone_task_fr_refs: dict[str, set[str]] = {}
    if "roadmap" in data:
        for ms in data["roadmap"].get("milestones", []):
            ms_id = ms.get("milestone_id")
            if ms_id:
                milestone_ids.add(ms_id)
                milestone_task_ids[ms_id] = [t.get("task_id") for t in ms.get("tasks", []) if t.get("task_id")]
                milestone_fr_set[ms_id] = set(ms.get("fr_refs", []))
                milestone_task_fr_refs[ms_id] = set(
                    fr for t in ms.get("tasks", [])
                    for fr in t.get("fr_refs", [])
                    if isinstance(fr, str)
                )
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

    # ---------------------------------------------------------------------------
    # Pairwise completeness checks (W564–W568)
    # ---------------------------------------------------------------------------

    # W564: FR→API coverage — each FR should be referenced by at least one API's trace.
    # NOTE: W564 checks ALL FRs, not just those with externally-observable behavior. The FR
    # schema (04_fr_list.json) has no field to classify observability (internal vs. external),
    # so all FRs are treated as externally observable for this check. If such a field is added
    # in the future (e.g. "observability": "external"|"internal"), this check should be updated
    # to filter to only externally-observable FRs before computing the coverage gap.
    if "frs" in data and "apis" in data:
        api_fr_refs: set[str] = set()
        for api in data["apis"].get("apis", []):
            for trace_ref in api.get("trace", []):
                if isinstance(trace_ref, dict) and normalize_trace_type(trace_ref.get("type") or "") == _FR_TRACE_TYPE and "id" in trace_ref:
                    api_fr_refs.add(trace_ref["id"])
        for fr_id in sorted(fr_ids - api_fr_refs):
            errors.append(make_error("W564", f"UNCOVERED_FR_API {fr_id}"))

    # W565: FR→fixture coverage — each FR should be referenced by at least one fixture's targets.
    if "frs" in data and "fixtures" in data:
        fixture_fr_refs: set[str] = set()
        for fixture in data["fixtures"].get("fixtures", []):
            for target in fixture.get("targets", []):
                # "type" field confirmed by 08_fixtures.schema.json targets[].type (via vc:core:collections#traceRef)
                if isinstance(target, dict) and normalize_trace_type(target.get("type") or "") == _FR_TRACE_TYPE and "id" in target:
                    fixture_fr_refs.add(target["id"])
        for fr_id in sorted(fr_ids - fixture_fr_refs):
            errors.append(make_error("W565", f"UNCOVERED_FR_FIXTURE {fr_id}"))

    # W566: FR→milestone coverage (same dimension as W561 but as a pairwise completeness code).
    # Fires only when both frs and roadmap are present; W561 fires earlier in the same conditions.
    # W566 provides a consistently-coded pairwise completeness signal for filtering and promotion.
    #
    # Design intent: W561 and W566 intentionally fire for the same FR IDs under the same guard
    # condition. W561 is the legacy informational signal (kept for backward compatibility).
    # W566 is the designated pairwise completeness code used for filtering and error promotion.
    # W561 is NOT in PROMOTABLE_PAIRS (see errors.py) to prevent double-promotion: without this
    # exclusion, SPECDEV_WARNINGS_AS_ERRORS=1 would emit both E561 and E566 for a single FR gap.
    if "frs" in data and "roadmap" in data:
        for fr_id in sorted(fr_ids - milestone_fr_refs):
            errors.append(make_error("W566", f"UNCOVERED_FR_MILESTONE {fr_id}"))

    # W567: Milestone decomposition completeness — milestones without any tasks.
    # TODO(batch-7): Also cross-check milestone.fr_refs against Step 09 deliverable IDs.
    # Per task 5-04 fix plan: load source_milestones from 09_impl_plan.json, collect
    # deliverable IDs, verify each appears in Step 14 tasks. Deferred: requires adding
    # "impl_plan" to SPEC_FILES and a new W-code for the Step 09 deliverable coverage gap.
    if "roadmap" in data:
        for ms_id, tasks in sorted(milestone_task_ids.items()):
            if not tasks:
                errors.append(make_error("W567", f"INCOMPLETE_MILESTONE_DECOMPOSITION {ms_id}"))

    # W567: also check that milestone fr_refs are covered by at least one task's fr_refs.
    # Guard with `if tasks` so this only fires when the milestone HAS tasks; a milestone
    # with no tasks is already covered by the empty-tasks W567 above and firing both would
    # double-count the same milestone in completeness-check ratio calculations.
    if "roadmap" in data:
        for ms_id, ms_fr in sorted(milestone_fr_set.items()):
            if not milestone_task_ids.get(ms_id):
                continue  # empty-tasks W567 already fired above
            task_fr = milestone_task_fr_refs.get(ms_id, set())
            for fr_ref in sorted(ms_fr - task_fr):
                errors.append(make_error("W567", f"INCOMPLETE_MILESTONE_DECOMPOSITION {ms_id}: fr_ref {fr_ref} not covered by any task fr_refs"))

    # W568: Capability coverage — each capability should be traced by at least one FR.
    # Mirrors the E560 capability_without_fr check but as a promotable warning.
    if "capabilities" in data and "frs" in data:
        for cap_id in sorted(capability_ids - fr_traced_caps):
            errors.append(make_error("W568", f"UNCOVERED_CAPABILITY {cap_id}"))

    return errors
