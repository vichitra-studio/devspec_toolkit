from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Any

from ...core.constants import resolve_extras_path
from ...core.errors import make_error, SpecError


def validate_step_14(instance: dict[str, Any], toolkit_root: str, artifact_path: str | None = None) -> list[SpecError]:
    """Deep checks of a step 14 artifact: unique milestone and task ids, valid and ordered dates, acyclic task ``depends_on``.

    Reads only values of the expected type; a malformed ``milestones``, milestone, ``tasks`` or task is skipped and
    left to the schema's own error. Never raises on wrong-typed input. Also warns W604 when the trace matrix is stale.
    """
    errors: list[SpecError] = []
    milestone_dates: list[tuple[str, str]] = []
    seen_milestones: set[str] = set()
    for i, milestone in enumerate(_dicts(instance.get("milestones"))):
        mid = milestone.get("milestone_id")
        if isinstance(mid, str):
            if mid in seen_milestones:
                errors.append(make_error("E520", f"Duplicate milestone_id '{mid}' at index {i}"))
            seen_milestones.add(mid)
        errors.extend(_date_errors(milestone, milestone_dates))
        tasks = _dicts(milestone.get("tasks"))
        errors.extend(_duplicate_task_errors(tasks, mid))
        errors.extend(_check_task_dependency_cycles(tasks, mid))
    if milestone_dates != sorted(milestone_dates, key=lambda x: x[0]):
        errors.append(make_error("E520", "Milestone target_date values are not ordered"))
    # AUDIT-033: Trace matrix staleness check (W604)
    # If spec/extras/trace_matrix.json is older than the roadmap artifact, warn that it should be regenerated.
    errors.extend(_check_trace_matrix_staleness(artifact_path))
    return errors


def _dicts(value: Any) -> list[dict[str, Any]]:
    """The object entries of *value*; empty when *value* is not a list."""
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


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


def _duplicate_task_errors(tasks: list[dict[str, Any]], milestone_id: Any) -> list[SpecError]:
    """E520 for every task id that repeats within one milestone."""
    errors: list[SpecError] = []
    seen: set[str] = set()
    for task in tasks:
        tid = task.get("task_id")
        if not isinstance(tid, str):
            continue
        if tid in seen:
            errors.append(make_error("E520", f"Milestone '{milestone_id}' duplicate task_id '{tid}'"))
        seen.add(tid)
    return errors


def _check_trace_matrix_staleness(artifact_path: str | None) -> list[SpecError]:
    """Check whether trace_matrix.json is stale relative to the roadmap artifact.

    Emits W604 TRACE_MATRIX_STALE if trace_matrix.json is older than 14_roadmap.json,
    or if trace_matrix.json is missing.

    Looks in ``<spec_dir>/extras/trace_matrix.json`` (canonical location).

    Guard conditions (skip silently):
    - artifact_path is None or not named "14_roadmap.json" — only meaningful for the real artifact
    - artifact_path is inside a "tests" directory — skip for test fixtures
    - toolkit_root cannot be resolved
    """
    errors: list[SpecError] = []
    try:
        # Only check when validating the canonical 14_roadmap.json artifact, not test fixtures
        if not artifact_path:
            return errors
        roadmap_path = Path(artifact_path).resolve()
        if roadmap_path.name != "14_roadmap.json":
            return errors
        # Skip for paths inside a tests directory (test fixtures)
        if "tests" in roadmap_path.parts:
            return errors
        if not roadmap_path.exists():
            return errors
        # Locate trace_matrix.json via shared resolution (canonical: spec/extras/)
        spec_dir = str(roadmap_path.parent)
        matrix_path = Path(resolve_extras_path(spec_dir, "trace_matrix.json"))
        if not matrix_path.exists():
            errors.append(make_error(
                "W604",
                "TRACE_MATRIX_STALE trace_matrix.json does not exist; "
                "run 'specdev matrix spec' to generate it"
            ))
            return errors
        matrix_mtime = os.path.getmtime(str(matrix_path))
        roadmap_mtime = os.path.getmtime(str(roadmap_path))
        if matrix_mtime < roadmap_mtime:
            errors.append(make_error(
                "W604",
                "TRACE_MATRIX_STALE trace_matrix.json is older than 14_roadmap.json; "
                "run 'specdev matrix spec' to regenerate it"
            ))
    except (OSError, ValueError, TypeError):
        # Graceful skip on any path or mtime error
        pass
    return errors


def _check_task_dependency_cycles(tasks: list, milestone_id: Any) -> list[SpecError]:
    """DFS cycle detection on task depends_on graph within a milestone."""
    task_ids = {task["task_id"] for task in tasks if isinstance(task, dict) and isinstance(task.get("task_id"), str)}
    adj: dict[str, list[str]] = {}
    for task in tasks:
        if not isinstance(task, dict):
            continue
        tid = task.get("task_id")
        if not isinstance(tid, str):
            continue
        deps = task.get("depends_on", [])
        if isinstance(deps, list):
            adj[tid] = [d for d in deps if isinstance(d, str) and d in task_ids]
        else:
            adj[tid] = []

    visited: set[str] = set()
    in_stack: set[str] = set()
    errors: list[SpecError] = []

    def dfs(node: str) -> bool:
        visited.add(node)
        in_stack.add(node)
        for neighbor in adj.get(node, []):
            if neighbor not in visited:
                if dfs(neighbor):
                    return True
            elif neighbor in in_stack:
                errors.append(
                    make_error("E141", f"TASK_DEPENDENCY_CYCLE: circular dependency detected involving task '{neighbor}' "
                    f"in milestone '{milestone_id}'")
                )
                return True
        in_stack.discard(node)
        return False

    for tid in list(adj.keys()):
        if tid not in visited:
            dfs(tid)

    return errors
