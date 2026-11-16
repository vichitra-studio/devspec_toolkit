from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Any

from ...core.constants import resolve_extras_path
from ...core.errors import make_error, SpecError
from ...core.scope_helpers import dict_items
from ...validation._legacy_shim import LEGACY_ROADMAP_MATRIX_FIELDS, has_legacy_fields, records_of


def validate_step_14(instance: dict[str, Any], toolkit_root: str, artifact_path: str | None = None) -> list[SpecError]:
    """Deep checks of a step 14 artifact: valid and ordered milestone dates.

    Duplicate milestone and task ids (E704) and a task ``depends_on`` cycle (E703) are the graph's checks, run by
    ``spec-check``. Reads only values of the expected type; a malformed ``milestones`` or milestone is skipped and
    left to the schema's own error. Never raises on wrong-typed input. Also warns W604 when the trace matrix is stale, on a roadmap
    that still carries the 1.1.1 ``fr_refs`` or ``source_milestones``.
    """
    errors: list[SpecError] = []
    milestone_dates: list[tuple[str, str]] = []
    for milestone in dict_items(instance.get("milestones")):
        errors.extend(_date_errors(milestone, milestone_dates))
    if milestone_dates != sorted(milestone_dates, key=lambda x: x[0]):
        errors.append(make_error("E520", "Milestone target_date values are not ordered"))
    # AUDIT-033: Trace matrix staleness check (W604)
    # If spec/extras/trace_matrix.json is older than the roadmap artifact, warn that it should be regenerated.
    # The matrix is built from the 1.1.1 `fr_refs` / `source_milestones` (M6c deletes the guard).
    if has_legacy_fields(records_of(instance), LEGACY_ROADMAP_MATRIX_FIELDS):
        errors.extend(_check_trace_matrix_staleness(artifact_path))
    return errors


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
