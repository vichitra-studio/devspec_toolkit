from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any


KEBAB_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def validate_step_14(instance: dict[str, Any], toolkit_root: str, artifact_path: str | None = None) -> list[str]:
    errors: list[str] = []
    milestone_dates: list[tuple[str, str]] = []
    step09_ids, step09_error = _load_step09_milestone_ids(toolkit_root, artifact_path)
    has_source_milestones = False
    seen_milestones: set[str] = set()
    for i, milestone in enumerate(instance.get("milestones", [])):
        mid = milestone.get("milestone_id")
        if mid in seen_milestones:
            errors.append(f"Duplicate milestone_id '{mid}' at index {i}")
        seen_milestones.add(mid)
        target_date = milestone.get("target_date")
        if isinstance(target_date, str):
            try:
                date.fromisoformat(target_date)
                if isinstance(mid, str):
                    milestone_dates.append((target_date, mid))
            except ValueError:
                errors.append(f"Invalid target_date '{target_date}' in milestone '{mid}'")
        sources = milestone.get("source_milestones", [])
        if isinstance(sources, list) and any(isinstance(src, str) for src in sources):
            has_source_milestones = True
        if step09_ids:
            for src in sources:
                if isinstance(src, str) and src not in step09_ids:
                    errors.append(
                        f"Milestone '{mid}' references unknown source_milestone '{src}' from Step 09"
                    )
        seen_tasks: set[str] = set()
        for task in milestone.get("tasks", []):
            tid = task.get("task_id")
            if tid in seen_tasks:
                errors.append(f"Milestone '{mid}' duplicate task_id '{tid}'")
            seen_tasks.add(tid)
    if milestone_dates != sorted(milestone_dates, key=lambda x: x[0]):
        errors.append("Milestone target_date values are not ordered")
    if has_source_milestones and step09_error:
        errors.append(step09_error)
    for dep in instance.get("dependencies", []):
        if not isinstance(dep, dict):
            errors.append(f"Dependency entry must be an object: {dep!r}")
            continue
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


def _load_step09_milestone_ids(toolkit_root: str, artifact_path: str | None) -> tuple[set[str], str | None]:
    candidates: list[Path] = []
    if artifact_path:
        artifact_dir = Path(artifact_path).resolve().parent
        candidates.append(artifact_dir / "09_impl_plan.json")
    candidates.append(Path(toolkit_root).resolve() / "spec" / "09_impl_plan.json")
    last_candidate: Path | None = None
    for path in candidates:
        last_candidate = path
        if not path.exists():
            continue
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError, ValueError, TypeError):
            return set(), f"Unable to load Step 09 artifact for source_milestone integrity: {path}"
        ids: set[str] = set()
        for milestone in data.get("milestones", []):
            if not isinstance(milestone, dict):
                continue
            value = milestone.get("milestone_id")
            if not isinstance(value, str):
                value = milestone.get("id")
            if isinstance(value, str) and value:
                ids.add(value)
        if not ids:
            return set(), f"Step 09 artifact has no milestone ids for source_milestone integrity: {path}"
        return ids, None
    expected = str(last_candidate) if last_candidate is not None else "<unknown>"
    return set(), f"Missing Step 09 artifact required for source_milestone integrity: {expected}"
