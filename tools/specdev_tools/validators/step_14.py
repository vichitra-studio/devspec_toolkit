from __future__ import annotations

import re
from typing import Any


KEBAB_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def validate_step_14(instance: dict[str, Any], toolkit_root: str) -> list[str]:
    errors: list[str] = []
    seen_milestones: set[str] = set()
    for i, milestone in enumerate(instance.get("milestones", [])):
        mid = milestone.get("milestone_id")
        if mid in seen_milestones:
            errors.append(f"Duplicate milestone_id '{mid}' at index {i}")
        seen_milestones.add(mid)
        seen_tasks: set[str] = set()
        for task in milestone.get("tasks", []):
            tid = task.get("task_id")
            if tid in seen_tasks:
                errors.append(f"Milestone '{mid}' duplicate task_id '{tid}'")
            seen_tasks.add(tid)
    for dep in instance.get("dependencies", []):
        dep_id = dep.get("id")
        dep_type = dep.get("type")
        if isinstance(dep_id, str) and not KEBAB_RE.match(dep_id):
            errors.append(f"Dependency has invalid id '{dep_id}'")
        if dep_type == "external":
            if not dep.get("owner"):
                errors.append(f"External dependency '{dep_id}' missing owner")
            if not dep.get("note"):
                errors.append(f"External dependency '{dep_id}' missing note")
    return errors
