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
    "impl_plan": "09_impl_plan.json",
    "governance": "10_governance.json",
    "ci_gates": "12_ci_gates.json",
    "roadmap": "14_roadmap.json",
}
# Keys that are silently optional — coverage checks fire only when present.
_OPTIONAL_KEYS = {"charter", "apis", "fixtures", "impl_plan", "governance", "ci_gates"}

# Anchor artifact (`vc:16-anchor`) lives at a fixed path under spec_dir.
ANCHOR_FILENAME = "16_impl_context.json"


def _resolve_context_path(spec_dir: str, context_path: str) -> str:
    """Resolve a milestone_index[].context_path to an absolute filesystem path.

    The anchor schema allows two conventions:
      - `spec/impl_context/<plan>.json` (repo-root relative; the `spec/` segment
        mirrors spec_dir's basename).
      - `impl_context/<plan>.json` (spec_dir relative).

    This helper accepts either form by stripping a leading `spec/` segment when
    the spec_dir basename is `spec` and the path begins with `spec/`.
    """
    if os.path.isabs(context_path):
        return context_path
    spec_basename = os.path.basename(os.path.normpath(spec_dir))
    prefix = spec_basename + "/"
    if context_path.startswith(prefix):
        context_path = context_path[len(prefix):]
    return os.path.join(spec_dir, context_path)


def _load_milestone_plans_from_anchor(
    spec_dir: str,
) -> tuple[list[dict[str, Any]], list[SpecError]]:
    """Load each milestone plan the Trinity Anchor registers.

    Returns (milestone_plans, errors):
      - milestone_plans: list of parsed 16a plan dicts for each
        `plan.milestone_index[]` entry in `16_impl_context.json` whose
        `context_path` resolves to a readable JSON file.
      - errors: W570 when the anchor itself is absent or unreadable; W588
        (ANCHOR_MILESTONE_UNREADABLE) for each declared `context_path` that
        exists on disk but cannot be parsed as JSON.

    Responsibility split with ``step_16_anchor.py``:
      - Missing declared ``context_path`` files are surfaced by **W607
        ANCHOR_CONTEXT_PATH_MISSING** from the anchor validator (sole owner of
        the "declared but absent" signal). This function therefore silently
        skips missing files to avoid double-reporting.
      - Parse failures (file exists but is not valid JSON) are owned here:
        the anchor validator emits W588 for parse failures found via directory
        globbing; this function emits W588 for parse failures found via the
        anchor's explicit registry. Same code, different discovery path.

    Design: the anchor is the authoritative registry of which milestone plans
    exist. This function does not glob the `impl_context/` directory — it reads
    only what the anchor declares. Orphan plans on disk are outside this
    validator's scope (see step_16_anchor.py for cross-milestone drift).
    """
    errors: list[SpecError] = []
    anchor_path = os.path.join(spec_dir, ANCHOR_FILENAME)
    if not os.path.isfile(anchor_path):
        errors.append(make_error(
            "W570",
            f"GRACEFUL_SKIP missing_spec_file {ANCHOR_FILENAME} "
            f"(Trinity Anchor — required for milestone plan registry)",
        ))
        return [], errors
    try:
        with open(anchor_path, encoding="utf-8") as f:
            anchor_data = json.load(f)
    except (OSError, json.JSONDecodeError):
        errors.append(make_error(
            "W570",
            f"GRACEFUL_SKIP unreadable_spec_file {ANCHOR_FILENAME}",
        ))
        return [], errors

    if not isinstance(anchor_data, dict):
        return [], errors
    milestone_index = anchor_data.get("plan", {}).get("milestone_index", [])
    if not isinstance(milestone_index, list):
        return [], errors

    plans: list[dict[str, Any]] = []
    for entry in milestone_index:
        if not isinstance(entry, dict):
            continue
        context_path = entry.get("context_path")
        if not isinstance(context_path, str) or not context_path:
            continue
        resolved = _resolve_context_path(spec_dir, context_path)
        milestone_id = entry.get("milestone_id", "<unknown>")
        if not os.path.isfile(resolved):
            # Missing file is owned by W607 (emitted by step_16_anchor.py).
            # Silently skip here to avoid double-reporting the same condition.
            continue
        try:
            with open(resolved, encoding="utf-8") as f:
                plans.append(json.load(f))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(make_error(
                "W588",
                f"ANCHOR_MILESTONE_UNREADABLE {milestone_id}: "
                f"{context_path} is not valid JSON ({exc})",
            ))
            continue
    return plans, errors


def check_traceability_closure(spec_dir: str, repo_root: str | None = None) -> list[SpecError]:
    errors: list[SpecError] = []

    # Resolve spec_dir relative to repo_root if it's a relative path
    if repo_root and not os.path.isabs(spec_dir):
        spec_dir = os.path.join(repo_root, spec_dir)

    data: dict[str, Any] = {}
    for key, filename in SPEC_FILES.items():
        path = os.path.join(spec_dir, filename)
        if not os.path.isfile(path):
            if key in _OPTIONAL_KEYS:
                continue  # Silently skip optional spec files
            errors.append(make_error("W570", f"GRACEFUL_SKIP missing_spec_file {filename}"))
            continue
        try:
            with open(path, encoding="utf-8") as f:
                data[key] = json.load(f)
        except (OSError, json.JSONDecodeError):
            if key in _OPTIONAL_KEYS:
                continue
            errors.append(make_error("W570", f"GRACEFUL_SKIP unreadable_spec_file {filename}"))
            continue

    # Load the Trinity Anchor (`vc:16-anchor`) and each milestone plan it
    # declares via `plan.milestone_index[].context_path`. Merged checklist and
    # execution data surface under the legacy `impl_planner` / `code_execution`
    # keys so the downstream coverage checks read from a single source.
    milestone_plans, registry_errors = _load_milestone_plans_from_anchor(spec_dir)
    errors.extend(registry_errors)
    if milestone_plans:
        data["impl_planner"] = {
            "plan": {
                "spec_alignment": {
                    "checklist": [
                        item
                        for plan in milestone_plans
                        for item in plan.get("plan", {}).get("spec_alignment", {}).get("checklist", [])
                        if isinstance(item, dict)
                    ]
                }
            }
        }
        execution_results: list[dict[str, Any]] = []
        # Resolve `satisfied_checklist_ids` → roadmap task_ids per-plan so that
        # duplicate checklist IDs across milestones cannot cross-contaminate.
        # The mapping is `checklist_item.id` → `checklist_item.spec_ref.id`,
        # matching the convention W562/W563 already enforce (spec_ref.id on a
        # checklist item is the roadmap task it verifies).
        satisfied_task_ids: set[str] = set()
        for plan in milestone_plans:
            results = plan.get("execution", {}).get("execution_results", [])
            if isinstance(results, list):
                execution_results.extend(r for r in results if isinstance(r, dict))
            local_checklist_to_task: dict[str, str] = {}
            for item in plan.get("plan", {}).get("spec_alignment", {}).get("checklist", []):
                if not isinstance(item, dict):
                    continue
                checklist_id = item.get("id")
                spec_ref = item.get("spec_ref")
                if (
                    isinstance(checklist_id, str) and checklist_id
                    and isinstance(spec_ref, dict)
                ):
                    spec_ref_id = spec_ref.get("id")
                    if isinstance(spec_ref_id, str) and spec_ref_id:
                        local_checklist_to_task[checklist_id] = spec_ref_id
            satisfied = (
                plan.get("execution", {})
                .get("critical_evidence", {})
                .get("satisfied_checklist_ids", [])
            )
            if isinstance(satisfied, list):
                for sat_id in satisfied:
                    if isinstance(sat_id, str):
                        resolved = local_checklist_to_task.get(sat_id)
                        if resolved:
                            satisfied_task_ids.add(resolved)
        if execution_results or satisfied_task_ids:
            data["code_execution"] = {
                "execution": {
                    "execution_results": execution_results,
                    "satisfied_task_ids": sorted(satisfied_task_ids),
                }
            }

    capability_ids: set[str] = set()
    # Capabilities marked scope:"out" (permanently excluded, the capability-level
    # analog of FR-level priority:"wont-have") or scope:"future" (acknowledged but
    # deferred to a later release -- the capability-level analog of task/milestone
    # "deferred") are both parked by design and exempted from W568 below: neither
    # is expected to have an FR trace yet.
    capability_parked_ids: set[str] = set()
    if "capabilities" in data:
        capability_ids = {c.get("capability_id") for c in data["capabilities"].get("capabilities", []) if c.get("capability_id")}
        capability_parked_ids = {
            c.get("capability_id")
            for c in data["capabilities"].get("capabilities", [])
            if c.get("capability_id") and c.get("scope") in ("out", "future")
        }

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

        # Task 7-01 (AUDIT-022): success_metrics traceability
        # Each charter success_metric must be referenced by at least one capability's success_metric_refs
        metric_ids: set[str] = set()
        for metric in charter_goals.get("success_metrics", []):
            if isinstance(metric, dict) and metric.get("metric_id"):
                metric_ids.add(metric["metric_id"])

        if metric_ids:
            cap_traced_metrics: set[str] = set()
            for cap in data["capabilities"].get("capabilities", []):
                for metric_ref in cap.get("success_metric_refs", []):
                    if isinstance(metric_ref, str) and metric_ref:
                        cap_traced_metrics.add(metric_ref)
            for metric_id in sorted(metric_ids - cap_traced_metrics):
                errors.append(make_error("E560", f"TRACEABILITY_GAP charter_success_metric_without_capability {metric_id}"))

    fr_traced_caps: set[str] = set()
    fr_ids: set[str] = set()
    if "frs" in data:
        for fr in data["frs"].get("functional_requirements", []):
            # Capability traces are always collected — a `wont-have` FR still
            # anchors its capability so W568 UNCOVERED_CAPABILITY does not fire.
            for cap_ref in fr.get("trace", []):
                if isinstance(cap_ref, dict) and normalize_trace_type(cap_ref.get("type") or "") == _CAPABILITY_TRACE_TYPE and "id" in cap_ref:
                    fr_traced_caps.add(cap_ref["id"])
            # Exclude `wont-have` FRs from downstream coverage checks — they
            # are explicitly out-of-scope (parked for a later phase) and have
            # no APIs, fixtures, or milestones by design. Including them
            # produces false-positive W561/W564/W565/W566 warnings.
            if fr.get("priority") == "wont-have":
                continue
            if "fr_id" in fr:
                fr_ids.add(fr["fr_id"])

    # Compute FR IDs exempted by Step 05 out_of_scope[] from W564 (API coverage),
    # W561, and W566 (milestone coverage). An FR listed in Step 05 out_of_scope[]
    # with a non-empty rationale is acknowledged as having no HTTP API surface;
    # the same exemption extends to milestone coverage because infra/ops FRs with
    # no API surface may also legitimately lack milestone placement (DEVSPEC-2).
    step05_oos_fr_ids: set[str] = set()
    if "apis" in data:
        step05_oos_fr_ids = {
            entry["fr_id"]
            for entry in data["apis"].get("out_of_scope", [])
            if isinstance(entry, dict) and entry.get("fr_id") and entry.get("rationale")
        }

    # Compute FR IDs exempted by Step 08 out_of_scope[] from W565 (fixture coverage).
    # Deliberately separate from step05_oos_fr_ids (DEVSPEC-122): "no API surface"
    # (Step 05) and "no fixture" (Step 08) are independent scoping decisions — an
    # FR with no API can still need a fixture (e.g. a background job), and an FR
    # with an API can legitimately have no fixture yet. Reusing step05_oos_fr_ids
    # here would silently suppress legitimate W565 warnings.
    step08_oos_fr_ids: set[str] = set()
    if "fixtures" in data:
        step08_oos_fr_ids = {
            entry["fr_id"]
            for entry in data["fixtures"].get("out_of_scope", [])
            if isinstance(entry, dict) and entry.get("fr_id") and entry.get("rationale")
        }

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
        for fr_id in sorted(fr_ids - milestone_fr_refs - step05_oos_fr_ids):
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

    # W564 / E535: FR→API coverage and out_of_scope[] contradiction check.
    # step05_oos_fr_ids (computed above) carries the Step 05 out_of_scope[] exemption.
    if "frs" in data and "apis" in data:
        api_fr_refs: set[str] = set()
        for api in data["apis"].get("apis", []):
            for trace_ref in api.get("trace", []):
                if isinstance(trace_ref, dict) and normalize_trace_type(trace_ref.get("type") or "") == _FR_TRACE_TYPE and "id" in trace_ref:
                    api_fr_refs.add(trace_ref["id"])
        # E535: FR declared in out_of_scope[] ("no API surface") but also referenced by
        # an API's trace[] — the two claims contradict. out_of_scope[] suppresses W564,
        # so without this check the trace reference would be silently masked.
        for fr_id in sorted(step05_oos_fr_ids & api_fr_refs):
            errors.append(make_error("E535", f"CONTRADICTORY_OUT_OF_SCOPE_FR {fr_id} appears in out_of_scope[] but is also referenced by an API trace"))
        for fr_id in sorted(fr_ids - api_fr_refs - step05_oos_fr_ids):
            errors.append(make_error("W564", f"UNCOVERED_FR_API {fr_id}"))

    # W565 / E536: FR→fixture coverage and out_of_scope[] contradiction check.
    # step08_oos_fr_ids (computed above) carries the Step 08 out_of_scope[] exemption.
    if "frs" in data and "fixtures" in data:
        fixture_fr_refs: set[str] = set()
        for fixture in data["fixtures"].get("fixtures", []):
            for target in fixture.get("targets", []):
                # "type" field confirmed by 08_fixtures.schema.json targets[].type (via vc:core:collections#traceRef)
                if isinstance(target, dict) and normalize_trace_type(target.get("type") or "") == _FR_TRACE_TYPE and "id" in target:
                    fixture_fr_refs.add(target["id"])
        # E536: FR declared in out_of_scope[] ("no fixture needed") but also referenced by
        # a fixture's targets[] — the two claims contradict. out_of_scope[] suppresses W565,
        # so without this check the target reference would be silently masked.
        for fr_id in sorted(step08_oos_fr_ids & fixture_fr_refs):
            errors.append(make_error("E536", f"CONTRADICTORY_OUT_OF_SCOPE_FR_FIXTURE {fr_id} appears in out_of_scope[] but is also referenced by a fixture target"))
        for fr_id in sorted(fr_ids - fixture_fr_refs - step08_oos_fr_ids):
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
        for fr_id in sorted(fr_ids - milestone_fr_refs - step05_oos_fr_ids):
            errors.append(make_error("W566", f"UNCOVERED_FR_MILESTONE {fr_id}"))

    # W567: Milestone decomposition completeness — milestones without any tasks.
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
    # scope:"out" capabilities are exempt (permanently excluded, no FR expected).
    if "capabilities" in data and "frs" in data:
        for cap_id in sorted(capability_ids - fr_traced_caps - capability_parked_ids):
            errors.append(make_error("W568", f"UNCOVERED_CAPABILITY {cap_id}"))

    # W575: Step 09 deliverable → Step 14 task pairwise completeness.
    # For each Step 09 milestone deliverable (traceRef with an 'id' field), verify that the
    # deliverable ID is referenced by at least one Step 14 task via the task's fr_refs, or
    # is referenced in any Step 14 milestone's deliverables list.
    # Guard: only fires when both impl_plan and roadmap are present.
    if "impl_plan" in data and "roadmap" in data:
        # Collect all artifact IDs referenced in Step 14 tasks (fr_refs) and deliverables
        step14_task_fr_ids: set[str] = set()
        step14_deliverable_ids: set[str] = set()
        for ms in data["roadmap"].get("milestones", []):
            for task in ms.get("tasks", []):
                for fr_id in task.get("fr_refs", []):
                    if isinstance(fr_id, str):
                        step14_task_fr_ids.add(fr_id)
            for deliverable in ms.get("deliverables", []):
                if isinstance(deliverable, dict) and "id" in deliverable:
                    step14_deliverable_ids.add(deliverable["id"])
        step14_covered_ids = step14_task_fr_ids | step14_deliverable_ids
        for ms09 in data["impl_plan"].get("milestones", []):
            ms09_id = ms09.get("milestone_id") or ms09.get("id", "<unknown>")
            for deliverable in ms09.get("deliverables", []):
                if not isinstance(deliverable, dict):
                    continue
                deliverable_id = deliverable.get("id")
                if not isinstance(deliverable_id, str) or not deliverable_id:
                    continue
                if deliverable_id not in step14_covered_ids:
                    errors.append(make_error(
                        "W575",
                        f"IMPL_PLAN_DELIVERABLE_UNCOVERED {deliverable_id} "
                        f"(Step 09 milestone: {ms09_id}) not referenced in any Step 14 task fr_refs or deliverables"
                    ))

    # W576: Step 14 task → Step 16b execution pairwise completeness.
    # For each Step 14 task with status != "done", verify that at least one Step 16b
    # execution entry references that task_id.
    # Guard: only fires when execution data was loaded from any milestone plan (the
    # `code_execution` key is synthesized from spec/impl_context/<milestone>_plan.json
    # files; post-Trinity-Anchor split there is no longer a separate 16b_code.json
    # artifact — the same milestone-plan file accumulates plan/execution/review).
    if "code_execution" in data and "roadmap" in data:
        # Executed task coverage is sourced from `satisfied_task_ids`, resolved
        # per-plan in `_load_milestone_plans_from_anchor` from each plan's
        # `critical_evidence.satisfied_checklist_ids` → `checklist[*].spec_ref.id`.
        # The 16_impl_context schema forbids a `task_id` field on execution_results
        # items (additionalProperties: false), so the mapping through the
        # checklist is the only schema-compliant closure path.
        executed_task_ids: set[str] = set(
            data["code_execution"].get("execution", {}).get("satisfied_task_ids", [])
        )
        # Defense-in-depth: a task whose own status hasn't been updated to
        # deferred/wont_do yet, but whose every covering checklist item has
        # already been marked deferred/wont_do, is transitionally paused too --
        # mirrors the coverage-counting logic in step_16.py's E304 check.
        checklist_item_statuses: dict[str, list[str]] = {}
        for item in data.get("impl_planner", {}).get("plan", {}).get("spec_alignment", {}).get("checklist", []):
            if not isinstance(item, dict):
                continue
            spec_ref = item.get("spec_ref")
            if not isinstance(spec_ref, dict):
                continue
            spec_ref_id = spec_ref.get("id")
            if not isinstance(spec_ref_id, str) or not spec_ref_id:
                continue
            checklist_item_statuses.setdefault(spec_ref_id, []).append(
                item.get("checklist_status", "active")
            )
        # Check each non-done, non-deferred, non-wont_do task
        for ms in data["roadmap"].get("milestones", []):
            for task in ms.get("tasks", []):
                if not isinstance(task, dict):
                    continue
                task_id = task.get("task_id")
                task_status = task.get("status", "pending")
                if not isinstance(task_id, str) or not task_id:
                    continue
                if task_status in ("done", "deferred", "wont_do"):
                    continue
                covering_statuses = checklist_item_statuses.get(task_id)
                if covering_statuses and all(s in ("deferred", "wont_do") for s in covering_statuses):
                    continue
                if task_id not in executed_task_ids:
                    errors.append(make_error(
                        "W576",
                        f"TASK_EXECUTION_MISSING {task_id} has no corresponding Step 16b execution entry"
                    ))

    # Task 7-07 (AUDIT-077): governance-to-CI cross-validation
    # For each pr_rule in Step 10, verify a corresponding CI job step command references it.
    if "governance" in data and "ci_gates" in data:
        pr_rules = data["governance"].get("pr_rules", [])
        ci_jobs = data["ci_gates"].get("jobs", [])
        # Collect all step commands from all CI jobs
        ci_commands: list[str] = []
        for job in ci_jobs:
            if not isinstance(job, dict):
                continue
            for step in job.get("steps", []):
                if not isinstance(step, dict):
                    continue
                cmd = step.get("command", "")
                if isinstance(cmd, str) and cmd:
                    ci_commands.append(cmd)
        for rule in pr_rules:
            if not isinstance(rule, str):
                continue
            if not any(rule in cmd for cmd in ci_commands):
                errors.append(make_error("W569", f"GOVERNANCE_PR_RULE_UNCOVERED {rule} has no corresponding CI job step enforcing it"))

    return errors
