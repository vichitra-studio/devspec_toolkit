from __future__ import annotations

from typing import Any

from ...core.scope_helpers import dict_items
from ...core.errors import make_error, SpecError


def validate_step_12(instance: dict[str, Any], toolkit_root: str, spec_root: str | None = None) -> list[SpecError]:
    """Deep checks of a step 12 artifact: every job step has a command.

    Whether a ``depends_on`` job exists (E700), whether the jobs form a cycle (E703) and whether a ``job_id``
    repeats (E704) are the graph's checks, run by ``spec-check``. Reads only values of the expected type, so a
    malformed ``jobs``, job or step is skipped here and left to the schema's own error. Never raises on wrong-typed
    input.
    """
    errors: list[SpecError] = []
    for job in dict_items(instance.get("jobs")):
        errors.extend(_step_errors(job))
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
