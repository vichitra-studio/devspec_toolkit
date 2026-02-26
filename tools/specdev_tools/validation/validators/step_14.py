from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any


KEBAB_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
FR_ID_RE = re.compile(r"^fr-[a-z0-9-]+$")
CAP_ID_RE = re.compile(r"^cap-[a-z0-9-]+$")


def validate_step_14(instance: dict[str, Any], toolkit_root: str, artifact_path: str | None = None) -> list[str]:
    errors: list[str] = []
    milestone_dates: list[tuple[str, str]] = []
    step09_ids, step09_error = _load_step09_milestone_ids(toolkit_root, artifact_path)
    step04_fr_ids = _load_step04_fr_ids(toolkit_root, artifact_path)
    step01_cap_ids = _load_step01_cap_ids(toolkit_root, artifact_path)
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
        # fr_refs cross-ref validation
        if step04_fr_ids:
            for fr_id in milestone.get("fr_refs", []):
                if isinstance(fr_id, str) and fr_id not in step04_fr_ids:
                    errors.append(
                        f"Milestone '{mid}' references unknown fr_ref '{fr_id}' not found in Step 04"
                    )
        # capability_refs cross-ref validation
        if step01_cap_ids:
            for cap_id in milestone.get("capability_refs", []):
                if isinstance(cap_id, str) and cap_id not in step01_cap_ids:
                    errors.append(
                        f"Milestone '{mid}' references unknown capability_ref '{cap_id}' not found in Step 01"
                    )
        seen_tasks: set[str] = set()
        for task in milestone.get("tasks", []):
            tid = task.get("task_id")
            if tid in seen_tasks:
                errors.append(f"Milestone '{mid}' duplicate task_id '{tid}'")
            seen_tasks.add(tid)
        # Task dependency acyclicity check
        cycle_errors = _check_task_dependency_cycles(milestone.get("tasks", []), mid)
        errors.extend(cycle_errors)
    if milestone_dates != sorted(milestone_dates, key=lambda x: x[0]):
        errors.append("Milestone target_date values are not ordered")
    if has_source_milestones and step09_error:
        errors.append(step09_error)
    # tech_stack cross-ref validation
    step09_tech_names = _load_step09_tech_stack_names(toolkit_root, artifact_path)
    if step09_tech_names:
        roadmap_tech_names = _collect_tech_names(instance.get("tech_stack", {}))
        for name in roadmap_tech_names:
            if name not in step09_tech_names:
                errors.append(
                    f"E142 TECH_STACK_MISMATCH: roadmap uses tech '{name}' not present in Step 09 tech_stack"
                )
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


def _check_task_dependency_cycles(tasks: list, milestone_id: Any) -> list[str]:
    """DFS cycle detection on task depends_on graph within a milestone."""
    task_ids = {task.get("task_id") for task in tasks if isinstance(task, dict) and task.get("task_id")}
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
    errors: list[str] = []

    def dfs(node: str) -> bool:
        visited.add(node)
        in_stack.add(node)
        for neighbor in adj.get(node, []):
            if neighbor not in visited:
                if dfs(neighbor):
                    return True
            elif neighbor in in_stack:
                errors.append(
                    f"E141 TASK_DEPENDENCY_CYCLE: circular dependency detected involving task '{neighbor}' "
                    f"in milestone '{milestone_id}'"
                )
                return True
        in_stack.discard(node)
        return False

    for tid in list(adj.keys()):
        if tid not in visited:
            dfs(tid)

    return errors


def _collect_tech_names(tech_stack: Any) -> set[str]:
    """Collect all technology names from a tech_stack object."""
    names: set[str] = set()
    if not isinstance(tech_stack, dict):
        return names
    for category in ("languages", "frameworks", "infrastructure", "tools"):
        for entry in tech_stack.get(category, []):
            if isinstance(entry, dict) and isinstance(entry.get("name"), str):
                names.add(entry["name"])
    return names


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


def _load_step09_tech_stack_names(toolkit_root: str, artifact_path: str | None) -> set[str]:
    """Load tech_stack names from Step 09 for cross-ref validation. Returns empty set if not found."""
    candidates: list[Path] = []
    if artifact_path:
        artifact_dir = Path(artifact_path).resolve().parent
        candidates.append(artifact_dir / "09_impl_plan.json")
    candidates.append(Path(toolkit_root).resolve() / "spec" / "09_impl_plan.json")
    for path in candidates:
        if not path.exists():
            continue
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError, ValueError, TypeError):
            return set()
        return _collect_tech_names(data.get("tech_stack", {}))
    return set()


def _load_step04_fr_ids(toolkit_root: str, artifact_path: str | None) -> set[str]:
    """Load FR IDs from Step 04 for fr_refs validation. Returns empty set if not found."""
    candidates: list[Path] = []
    if artifact_path:
        artifact_dir = Path(artifact_path).resolve().parent
        candidates.append(artifact_dir / "04_fr_list.json")
    candidates.append(Path(toolkit_root).resolve() / "spec" / "04_fr_list.json")
    for path in candidates:
        if not path.exists():
            continue
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError, ValueError, TypeError):
            return set()
        ids: set[str] = set()
        for fr in data.get("functional_requirements", []):
            if isinstance(fr, dict):
                fr_id = fr.get("fr_id") or fr.get("id")
                if isinstance(fr_id, str) and fr_id:
                    ids.add(fr_id)
        return ids
    return set()


def _load_step01_cap_ids(toolkit_root: str, artifact_path: str | None) -> set[str]:
    """Load capability IDs from Step 01 for capability_refs validation. Returns empty set if not found."""
    candidates: list[Path] = []
    if artifact_path:
        artifact_dir = Path(artifact_path).resolve().parent
        candidates.append(artifact_dir / "01_capabilities.json")
    candidates.append(Path(toolkit_root).resolve() / "spec" / "01_capabilities.json")
    for path in candidates:
        if not path.exists():
            continue
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError, ValueError, TypeError):
            return set()
        ids: set[str] = set()
        for cap in data.get("capabilities", []):
            if isinstance(cap, dict):
                cap_id = cap.get("capability_id") or cap.get("id")
                if isinstance(cap_id, str) and cap_id:
                    ids.add(cap_id)
        return ids
    return set()
