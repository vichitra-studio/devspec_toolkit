"""Migration planner for DevSpec Toolkit.

Orchestrates schema_differ output into a sequenced migration plan,
mapping each detected diff to a template and ordering steps according
to the pipeline DAG defined in step_order.json.
"""
from __future__ import annotations

import json
import logging
import re
import warnings
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..generation.schema_differ import (
    DiffType,
    FieldDiff,
    MigrationAction,
    MigrationDiff,
    ParadigmShift,
    StepDiff,
)
from ..core.changelog_parser import compare_versions, get_changes_between

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Constants — step-based template mapping
# -----------------------------------------------------------------------------

# Maps pipeline step number prefixes to step-based template filenames
# in prompts/migration/.  The DiffType is recorded in MigrationStep.action
# for the runner to know what kind of change to apply, but the *template*
# is determined by the step context.
_STEP_TO_TEMPLATE: Dict[str, str] = {
    "00": "template_charter.md",
    "01": "template_capabilities.md",
    "02": "template_system_sketch.md",
    "02a": "template_delivery_baseline.md",
    "03": "template_glossary.md",
    "04": "template_frs.md",
    "05": "template_interfaces.md",
    "06": "template_invariants.md",
    "07": "template_nfrs.md",
    "08": "template_fixtures.md",
    "09": "template_impl_plan.md",
    "10": "template_governance.md",
    "11": "template_redteam.md",
    "12": "template_ci_gates.md",
    "13": "template_extension_generator.md",
    "13a": "template_completeness_assessment.md",
    "14": "template_roadmap.md",
    "15": "template_scaffold.md",
    "16": "template_impl_context.md",
}


# -----------------------------------------------------------------------------
# Data Classes
# -----------------------------------------------------------------------------

@dataclass
class MigrationStep:
    """A single discrete migration action within a plan.

    Attributes:
        step_id: Pipeline step this action targets (e.g., "04_frs").
        action: Whether this can be auto-applied or needs AI assistance.
        template: Filename of the prompt template to use, or None if
            the action is fully auto-fixable and no template is required.
        context: Arbitrary context dict passed to the template renderer
            (field paths, expected types, suggestions, etc.).
        depends_on: List of step_ids that must be migrated before this one.
    """
    step_id: str
    action: MigrationAction
    template: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)


@dataclass
class MigrationPlan:
    """An ordered collection of migration steps with version metadata.

    Attributes:
        steps: Ordered list of migration steps to execute.
        source_version: The user's current toolkit version.
        target_version: The toolkit version being migrated to.
        created_at: ISO-8601 timestamp of plan creation.
    """
    steps: List[MigrationStep] = field(default_factory=list)
    source_version: str = ""
    target_version: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# -----------------------------------------------------------------------------
# Template Mapping
# -----------------------------------------------------------------------------

def map_diff_to_template(
    diff_type: DiffType,
    paradigm: Optional[ParadigmShift] = None,
    step_id: Optional[str] = None,
) -> Optional[str]:
    """Map a step context to a step-based template filename.

    Resolution priority:
    1. If ``step_id`` is provided, look up ``_STEP_TO_TEMPLATE`` by the
       extracted step number prefix.
    2. Fall back to ``None`` (no template) when the step has no mapping.

    Args:
        diff_type: The type of schema difference detected (retained for
            context in MigrationStep.action but no longer drives template
            selection).
        paradigm: An optional paradigm shift object (retained for backward
            compatibility; paradigm shifts use the relevant step template).
        step_id: Pipeline step identifier (e.g., ``"04_frs"``).

    Returns:
        Template filename string, or ``None`` when no template is mapped.
    """
    if step_id is not None:
        prefix = _extract_step_number(step_id)
        return _STEP_TO_TEMPLATE.get(prefix)

    return None


# -----------------------------------------------------------------------------
# Step Ordering
# -----------------------------------------------------------------------------

def _extract_step_number(step_id: str) -> str:
    """Extract the pipeline step number prefix from a step_id.

    Examples:
        "04_frs"  -> "04"
        "02a_glossary" -> "02a"
        "16c_review" -> "16c"
    """
    match = re.match(r"^(\d{2}[a-z]?)", step_id)
    return match.group(1) if match else step_id


def order_migration_steps(
    steps: List[MigrationStep],
    step_order_path: Path | str,
) -> List[MigrationStep]:
    """Sort migration steps according to the pipeline DAG.

    Reads ``step_order.json`` and uses its ``steps`` array to determine
    the correct execution order.  Steps whose step_id prefix does not
    appear in the DAG are placed at the end in their original order.

    Args:
        steps: Unordered list of migration steps.
        step_order_path: Path to ``tools/step_order.json``.

    Returns:
        A new list of MigrationStep objects sorted by pipeline order.
    """
    step_order_path = Path(step_order_path)
    with open(step_order_path, "r", encoding="utf-8") as f:
        dag = json.load(f)

    ordered_ids: List[str] = dag.get("steps", [])
    # Build a rank map: step number -> position index
    rank: Dict[str, int] = {sid: idx for idx, sid in enumerate(ordered_ids)}

    def sort_key(ms: MigrationStep) -> int:
        prefix = _extract_step_number(ms.step_id)
        return rank.get(prefix, len(ordered_ids))

    return sorted(steps, key=sort_key)


# -----------------------------------------------------------------------------
# Plan Construction
# -----------------------------------------------------------------------------

def _migration_step_from_step_diff(
    step_diff: StepDiff,
    paradigm_shifts: List[ParadigmShift],
) -> MigrationStep:
    """Create a MigrationStep from a StepDiff (step-level diff).

    If the step diff is associated with a paradigm shift (matched by
    step_id prefix), the paradigm information is forwarded so the
    correct template is selected.
    """
    # Find a paradigm shift that relates to this step, if any.
    paradigm: Optional[ParadigmShift] = None
    for ps in paradigm_shifts:
        # Match by target_file name starting with the step prefix
        prefix = _extract_step_number(step_diff.step_id)
        if ps.target_file.name.startswith(prefix):
            paradigm = ps
            break

    diff_type = (
        DiffType.STEP_MISSING
        if step_diff.status == "missing"
        else DiffType.SCHEMA_REF_OUTDATED
    )

    template = map_diff_to_template(diff_type, paradigm=paradigm, step_id=step_diff.step_id)

    context: Dict[str, Any] = {
        "status": step_diff.status,
    }
    if step_diff.source_file:
        context["source_file"] = str(step_diff.source_file)
    if step_diff.target_file:
        context["target_file"] = str(step_diff.target_file)
    if step_diff.version_added:
        context["version_added"] = step_diff.version_added
    if paradigm is not None:
        context["paradigm_shift"] = paradigm.description

    return MigrationStep(
        step_id=step_diff.step_id,
        action=step_diff.action,
        template=template,
        context=context,
    )


def _migration_step_from_field_diff(
    step_id: str,
    field_diff: FieldDiff,
) -> MigrationStep:
    """Create a MigrationStep from a FieldDiff (field-level diff)."""
    template = map_diff_to_template(field_diff.diff_type, step_id=step_id)

    context: Dict[str, Any] = {
        "path": field_diff.path,
        "diff_type": field_diff.diff_type.value,
    }
    if field_diff.expected is not None:
        context["expected"] = field_diff.expected
    if field_diff.actual is not None:
        context["actual"] = field_diff.actual
    if field_diff.suggestion is not None:
        context["suggestion"] = field_diff.suggestion

    return MigrationStep(
        step_id=step_id,
        action=field_diff.action,
        template=template,
        context=context,
    )


def create_migration_plan(
    diff: MigrationDiff,
    templates_dir: Path | str | None = None,
) -> MigrationPlan:
    """Build an ordered migration plan from a MigrationDiff.

    Iterates over step-level and field-level diffs, creates a
    MigrationStep for each, assigns the appropriate prompt template,
    and orders the resulting steps according to the pipeline DAG.

    Args:
        diff: The complete migration diff produced by ``schema_differ``.
        templates_dir: Optional path to the templates directory.  When
            provided, only steps whose template file actually exists on
            disk are marked with a template; otherwise templates are
            assigned purely by name mapping.

    Returns:
        A fully ordered ``MigrationPlan`` ready for execution.
    """
    raw_steps: List[MigrationStep] = []

    # 1. Step-level diffs (missing steps, paradigm shifts, etc.)
    for step_diff in diff.steps:
        ms = _migration_step_from_step_diff(step_diff, diff.paradigm_shifts)

        # If step_diff has nested field_diffs, create per-field steps too.
        for fd in step_diff.field_diffs:
            raw_steps.append(_migration_step_from_field_diff(step_diff.step_id, fd))

        # Only include the step-level entry if it has actionable status.
        if step_diff.status in ("missing", "needs_update", "unknown"):
            raw_steps.append(ms)

    # 2. Determine step_order.json path — try common locations.
    step_order_candidates = [
        Path(__file__).resolve().parent.parent.parent / "step_order.json",  # tools/step_order.json
        Path(__file__).resolve().parent.parent.parent.parent / "tools" / "step_order.json",
    ]
    step_order_path: Optional[Path] = None
    for candidate in step_order_candidates:
        if candidate.exists():
            step_order_path = candidate
            break

    # 3. Order steps by pipeline DAG.
    if step_order_path is not None:
        ordered = order_migration_steps(raw_steps, step_order_path)
    else:
        warnings.warn(
            "step_order.json not found; migration steps will not be ordered by pipeline DAG",
            UserWarning,
            stacklevel=2,
        )
        ordered = raw_steps

    # 4. Resolve depends_on from DAG ordering.
    #    Each step depends on all earlier steps that share a different step_id.
    seen_step_ids: List[str] = []
    for ms in ordered:
        ms.depends_on = [sid for sid in seen_step_ids if sid != ms.step_id]
        if ms.step_id not in seen_step_ids:
            seen_step_ids.append(ms.step_id)

    # 5. If templates_dir supplied, validate template existence.
    if templates_dir is not None:
        templates_dir = Path(templates_dir)
        for ms in ordered:
            if ms.template and not (templates_dir / ms.template).exists():
                ms.context["template_missing"] = True

    return MigrationPlan(
        steps=ordered,
        source_version=diff.source_version or "",
        target_version=diff.target_version,
    )
