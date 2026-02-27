from __future__ import annotations

from typing import Any


def validate_step_12(instance: dict[str, Any], toolkit_root: str) -> list[str]:
    errors: list[str] = []
    job_ids = set()
    for i, job in enumerate(instance.get("jobs", [])):
        job_id = job.get("job_id")
        if job_id in job_ids:
            errors.append(f"Duplicate job_id '{job_id}' at index {i}")
        job_ids.add(job_id)
        for step in job.get("steps", []):
            if not step.get("id") or not step.get("command"):
                errors.append(f"Job '{job_id}' has step missing id/command")
    for job in instance.get("jobs", []):
        for req in job.get("requires", []):
            if req not in job_ids:
                errors.append(f"Job '{job.get('job_id')}' requires unknown job '{req}'")
    # DAG cycle detection
    graph: dict[str, list[str]] = {}
    for job in instance.get("jobs", []):
        jid = job.get("job_id", "")
        graph[jid] = list(job.get("requires", []))
    cycle = _has_cycle(graph)
    if cycle:
        errors.append(f"Circular dependency detected in job requires graph: {cycle}")
    return errors


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
