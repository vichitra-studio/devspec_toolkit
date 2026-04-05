from __future__ import annotations

import re
from typing import Any, Optional, Set

from ...core.errors import make_error, SpecError
from ...core.loaders import load_upstream_ids
from ...validation.linter_utils import check_no_duplicates


# Pattern to match FR and NFR IDs in string values
_FR_ID_RE = re.compile(r"^fr-[a-z0-9]+(?:-[a-z0-9]+)*$")
_NFR_ID_RE = re.compile(r"^nfr-[a-z0-9]+(?:-[a-z0-9]+)*$")


def validate_step_12(instance: dict[str, Any], toolkit_root: str, spec_root: str | None = None) -> list[SpecError]:
    errors: list[SpecError] = []
    check_no_duplicates(instance.get("jobs", []), "job_id", "job_id", errors)
    job_ids = {j["job_id"] for j in instance.get("jobs", []) if isinstance(j, dict) and isinstance(j.get("job_id"), str)}
    for job in instance.get("jobs", []):
        job_id = job.get("job_id")
        for step in job.get("steps", []):
            if not step.get("id") or not step.get("command"):
                errors.append(make_error("E520", f"Job '{job_id}' has step missing id/command"))
    for job in instance.get("jobs", []):
        for req in job.get("requires", []):
            if req not in job_ids:
                errors.append(make_error("E590", f"Job '{job.get('job_id')}' requires unknown job '{req}'"))
    # DAG cycle detection
    graph: dict[str, list[str]] = {}
    for job in instance.get("jobs", []):
        jid = job.get("job_id", "")
        graph[jid] = list(job.get("requires", []))
    cycle = _has_cycle(graph)
    if cycle:
        errors.append(make_error("E141", f"Circular dependency detected in job requires graph: {cycle}"))

    # Cross-step FR/NFR reference validation
    fr_ids = load_upstream_ids(toolkit_root, "04", "functional_requirements", "fr_id", spec_root=spec_root)
    nfr_ids = load_upstream_ids(toolkit_root, "07", "nfrs", "nfr_id", spec_root=spec_root)

    upstream_map: dict[str, tuple[set[str] | None, str, str]] = {
        "fr-": (fr_ids, "04_fr_list.json", "FR"),
        "nfr-": (nfr_ids, "07_nfrs.json", "NFR"),
    }

    # Emit W590 once per missing upstream file
    warned_missing: set[str] = set()
    for prefix, (id_set, filename, type_label) in upstream_map.items():
        if id_set is None and filename not in warned_missing:
            errors.append(
                make_error("W590", f"CROSS_STEP_UPSTREAM_MISSING {filename} not found; "
                f"skipping {type_label} reference validation")
            )
            warned_missing.add(filename)

    # Collect and validate spec references from trace and jobs
    # 1. Top-level trace references
    for trace_entry in instance.get("trace", []):
        if not isinstance(trace_entry, dict):
            continue
        trace_id = trace_entry.get("id", "")
        if isinstance(trace_id, str):
            _check_ref(trace_id, "trace", upstream_map, errors)

    # 2. Deep-scan jobs for string values matching fr-* or nfr-* patterns
    for job in instance.get("jobs", []):
        job_id = job.get("job_id", "<unknown>")
        refs = _collect_refs_from_value(job)
        for ref in refs:
            for prefix, (id_set, filename, _type_label) in upstream_map.items():
                if ref.startswith(prefix):
                    if id_set is not None and ref not in id_set:
                        errors.append(
                            make_error("E590", f"CROSS_STEP_ID_NOT_FOUND job '{job_id}' "
                            f"references unknown {_type_label} '{ref}' "
                            f"(not in {filename})")
                        )
                    break

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




def _check_ref(
    ref: str,
    source_label: str,
    upstream_map: dict[str, tuple[set[str] | None, str, str]],
    errors: list[SpecError],
) -> None:
    """Check a single reference string against the upstream ID sets."""
    for prefix, (id_set, filename, type_label) in upstream_map.items():
        if ref.startswith(prefix):
            if id_set is not None and ref not in id_set:
                errors.append(
                    make_error("E590", f"CROSS_STEP_ID_NOT_FOUND {source_label} "
                    f"references unknown {type_label} '{ref}' "
                    f"(not in {filename})")
                )
            break


def _collect_refs_from_value(value: Any) -> set[str]:
    """Recursively collect all string values matching fr-* or nfr-* patterns from a data structure."""
    refs: set[str] = set()
    if isinstance(value, str):
        if _FR_ID_RE.match(value) or _NFR_ID_RE.match(value):
            refs.add(value)
    elif isinstance(value, dict):
        for v in value.values():
            refs.update(_collect_refs_from_value(v))
    elif isinstance(value, list):
        for item in value:
            refs.update(_collect_refs_from_value(item))
    return refs
