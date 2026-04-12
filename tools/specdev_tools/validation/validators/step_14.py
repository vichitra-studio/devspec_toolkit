from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from typing import Any

from ...core.constants import resolve_extras_path
from ...core.errors import make_error, SpecError
from ...core.loaders import KEBAB_ID_RE, load_sibling_artifact

KEBAB_RE = KEBAB_ID_RE


def validate_step_14(instance: dict[str, Any], toolkit_root: str, artifact_path: str | None = None) -> list[SpecError]:
    errors: list[SpecError] = []
    milestone_dates: list[tuple[str, str]] = []
    step09_ids, step09_error = _load_step09_milestone_ids(toolkit_root, artifact_path)
    step04_fr_ids = load_sibling_artifact(
        artifact_path or "", "04", "functional_requirements", "fr_id",
        fallback_root=toolkit_root,
    )
    step01_cap_ids = load_sibling_artifact(
        artifact_path or "", "01", "capabilities", "capability_id",
        fallback_root=toolkit_root,
    )
    has_source_milestones = False
    seen_milestones: set[str] = set()
    for i, milestone in enumerate(instance.get("milestones", [])):
        mid = milestone.get("milestone_id")
        if mid in seen_milestones:
            errors.append(make_error("E520", f"Duplicate milestone_id '{mid}' at index {i}"))
        seen_milestones.add(mid)
        target_date = milestone.get("target_date")
        if isinstance(target_date, str):
            try:
                date.fromisoformat(target_date)
                if isinstance(mid, str):
                    milestone_dates.append((target_date, mid))
            except ValueError:
                errors.append(make_error("E520", f"Invalid target_date '{target_date}' in milestone '{mid}'"))
        sources = milestone.get("source_milestones", [])
        if isinstance(sources, list) and any(isinstance(src, str) for src in sources):
            has_source_milestones = True
        if step09_ids:
            for src in sources:
                if isinstance(src, str) and src not in step09_ids:
                    errors.append(
                        make_error("E590", f"Milestone '{mid}' references unknown source_milestone '{src}' from Step 09")
                    )
        # fr_refs cross-ref validation
        if step04_fr_ids:
            for fr_id in milestone.get("fr_refs", []):
                if isinstance(fr_id, str) and fr_id not in step04_fr_ids:
                    errors.append(
                        make_error("E590", f"Milestone '{mid}' references unknown fr_ref '{fr_id}' not found in Step 04")
                    )
        # capability_refs cross-ref validation
        if step01_cap_ids:
            for cap_id in milestone.get("capability_refs", []):
                if isinstance(cap_id, str) and cap_id not in step01_cap_ids:
                    errors.append(
                        make_error("E590", f"Milestone '{mid}' references unknown capability_ref '{cap_id}' not found in Step 01")
                    )
        seen_tasks: set[str] = set()
        for task in milestone.get("tasks", []):
            tid = task.get("task_id")
            if tid in seen_tasks:
                errors.append(make_error("E520", f"Milestone '{mid}' duplicate task_id '{tid}'"))
            seen_tasks.add(tid)
        # Task dependency acyclicity check
        cycle_errors = _check_task_dependency_cycles(milestone.get("tasks", []), mid)
        errors.extend(cycle_errors)
    if milestone_dates != sorted(milestone_dates, key=lambda x: x[0]):
        errors.append(make_error("E520", "Milestone target_date values are not ordered"))
    if has_source_milestones and step09_error:
        errors.append(make_error("E590", step09_error))
    # tech_stack cross-ref validation
    step09_tech_names = _load_step09_tech_stack_names(toolkit_root, artifact_path)  # unique structure, kept local
    if step09_tech_names:
        roadmap_tech_names = _collect_tech_names(instance.get("tech_stack", {}))
        for name in roadmap_tech_names:
            if name not in step09_tech_names:
                errors.append(
                    make_error("E142", f"TECH_STACK_MISMATCH: roadmap uses tech '{name}' not present in Step 09 tech_stack")
                )
    # AUDIT-034: Step 02 → Step 14 tech stack consistency checks (W602, W605)
    step02_tech_names = _load_step02_tech_stack_names(toolkit_root, artifact_path)
    if step02_tech_names:
        roadmap_tech_names = _collect_tech_names(instance.get("tech_stack", {}))
        for name in roadmap_tech_names:
            if name not in step02_tech_names:
                errors.append(
                    make_error("W602", f"TECH_STACK_02_MISMATCH: roadmap uses tech '{name}' not found in Step 02 system_sketch tech_stack")
                )
        for name in step02_tech_names:
            if name not in roadmap_tech_names:
                errors.append(
                    make_error("W605", f"TECH_STACK_02_MISSING: Step 02 declares tech '{name}' but it is absent from roadmap tech_stack")
                )
    for dep in instance.get("dependencies", []):
        if not isinstance(dep, dict):
            errors.append(make_error("E520", f"Dependency entry must be an object: {dep!r}"))
            continue
        dep_id = dep.get("id")
        dep_type = dep.get("type")
        if isinstance(dep_id, str) and not KEBAB_RE.match(dep_id):
            errors.append(make_error("E530", f"Dependency has invalid id '{dep_id}'"))
        if dep_type == "external":
            if not dep.get("owner"):
                errors.append(make_error("E520", f"External dependency '{dep_id}' missing owner"))
            if not dep.get("note"):
                errors.append(make_error("E520", f"External dependency '{dep_id}' missing note"))
    # AUDIT-033: Trace matrix staleness check (W604)
    # If tools/trace_matrix.json is older than the roadmap artifact, warn that it should be regenerated.
    errors.extend(_check_trace_matrix_staleness(toolkit_root, artifact_path))
    return errors


def _check_trace_matrix_staleness(toolkit_root: str, artifact_path: str | None) -> list[SpecError]:
    """Check whether trace_matrix.json is stale relative to the roadmap artifact.

    Emits W604 TRACE_MATRIX_STALE if trace_matrix.json is older than 14_roadmap.json,
    or if trace_matrix.json is missing.

    Looks in ``<spec_dir>/extras/`` first (host-repo location), then falls
    back to ``<toolkit_root>/tools/`` for backwards compatibility.

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
        # Locate trace_matrix.json via shared resolution (extras/ → tools/ fallback)
        spec_dir = str(roadmap_path.parent)
        matrix_path = Path(resolve_extras_path(spec_dir, toolkit_root, "trace_matrix.json"))
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
    """Load milestone IDs from Step 09 for cross-ref validation.

    Not migrated to shared ``load_upstream_ids()`` (AUDIT-017) because:
    1. Returns a ``(ids, error_msg)`` tuple (not ``set | None``).
    2. Falls back across two ID fields: ``milestone_id`` then ``id``.
    3. Uses sibling-then-fallback path resolution with detailed error messages.
    """
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
    """Load tech_stack names from Step 09 for cross-ref validation.

    Not migrated to shared ``load_upstream_ids()`` (AUDIT-017) because it extracts
    names from a nested ``tech_stack.{category}[].name`` structure, not a flat
    ``array[].id_field`` pattern.  Returns empty set if not found.
    """
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


def _load_step02_tech_stack_names(toolkit_root: str, artifact_path: str | None) -> set[str]:
    """Load tech_stack names from Step 02 system sketch for cross-ref validation."""
    candidates: list[Path] = []
    if artifact_path:
        artifact_dir = Path(artifact_path).resolve().parent
        candidates.append(artifact_dir / "02_system_sketch.json")
    candidates.append(Path(toolkit_root).resolve() / "spec" / "02_system_sketch.json")
    for path in candidates:
        if not path.exists():
            continue
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError, ValueError, TypeError):
            continue
        return _collect_tech_names(data.get("tech_stack", {}))
    return set()
