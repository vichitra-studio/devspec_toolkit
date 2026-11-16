from __future__ import annotations

from typing import Any

from ...core.scope_helpers import dict_items, str_items
from ...core.errors import make_error, SpecError
from ...validation.linter_utils import check_no_duplicates


def validate_step_12(instance: dict[str, Any], toolkit_root: str, spec_root: str | None = None) -> list[SpecError]:
    """Deep checks of a step 12 artifact: unique job ids, steps with a command, known and acyclic ``depends_on``.

    Reads only values of the expected type, so a malformed ``jobs``, job, step or ``depends_on`` is skipped here and
    left to the schema's own error. Never raises on wrong-typed input.
    """
    errors: list[SpecError] = []
    jobs = dict_items(instance.get("jobs"))
    check_no_duplicates(jobs, "job_id", "job_id", errors)
    job_ids = {j["job_id"] for j in jobs if isinstance(j.get("job_id"), str)}
    for job in jobs:
        errors.extend(_step_errors(job))
        errors.extend(_unknown_dependency_errors(job, job_ids))
    cycle = _has_cycle({j["job_id"]: str_items(j.get("depends_on")) for j in jobs if isinstance(j.get("job_id"), str)})
    if cycle:
        errors.append(make_error("E141", f"Circular dependency detected in job depends_on graph: {cycle}"))
    return errors


def _step_errors(job: dict[str, Any]) -> list[SpecError]:
    """E520 for every step of *job* that has no command."""
    steps = job.get("steps")
    if not isinstance(steps, list):
        return []
    return [
        make_error("E520", f"Job '{job.get('job_id')}' has step missing command")
        for step in steps
        if isinstance(step, dict) and not step.get("command")
    ]


def _unknown_dependency_errors(job: dict[str, Any], job_ids: set[str]) -> list[SpecError]:
    """E590 for every ``depends_on`` entry of *job* that names no job of this spec."""
    return [
        make_error("E590", f"Job '{job.get('job_id')}' depends_on unknown job '{dep}'")
        for dep in str_items(job.get("depends_on"))
        if dep not in job_ids
    ]


def _has_cycle(graph: dict[str, list[str]]) -> list[str] | None:
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {n: WHITE for n in graph}
    path: list[str] = []

    def dfs(node: str) -> list[str] | None:
        color[node] = GRAY
        path.append(node)
        for dep in graph.get(node, []):
            if dep not in color:
                continue
            if color[dep] == GRAY:
                idx = path.index(dep)
                return path[idx:]
            if color[dep] == WHITE:
                result = dfs(dep)
                if result is not None:
                    return result
        path.pop()
        color[node] = BLACK
        return None

    for node in graph:
        if color[node] == WHITE:
            result = dfs(node)
            if result is not None:
                return result
    return None
