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
    return errors
