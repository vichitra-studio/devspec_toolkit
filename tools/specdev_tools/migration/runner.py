"""Migration runner for DevSpec Toolkit.

Executes migration plans produced by ``planner.py`` with backup/rollback
support.  Automatic fixes are applied in-place; AI-assisted steps generate
prompt files for manual review.
"""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..generation.schema_differ import (
    MigrationDiff,
    apply_auto_fixes,
    log_operation,
    validate_post_migration,
    validate_pre_migration,
)
from .planner import MigrationPlan, MigrationStep


# -----------------------------------------------------------------------------
# Data Classes
# -----------------------------------------------------------------------------

@dataclass
class MigrationTransaction:
    """Result of a migration plan execution.

    Attributes:
        backup_path: Path where pre-migration backups were stored,
            or None if ``dry_run`` was True.
        operations_completed: List of human-readable descriptions of
            successfully completed operations.
        operations_failed: List of human-readable descriptions of
            operations that failed.
        rolled_back: Whether a rollback was performed due to failure.
        dry_run: Whether this was a dry-run (no files modified).
    """
    backup_path: Optional[Path] = None
    operations_completed: List[str] = field(default_factory=list)
    operations_failed: List[str] = field(default_factory=list)
    rolled_back: bool = False
    dry_run: bool = False


@dataclass
class TransactionBoundary:
    """A group of migration steps that should be applied atomically.

    Steps targeting the same spec file are grouped together so they
    can be committed (or rolled back) as a single unit.

    Attributes:
        steps: The migration steps in this boundary.
        description: Human-readable summary of the grouped operations.
    """
    steps: List[MigrationStep] = field(default_factory=list)
    description: str = ""


# -----------------------------------------------------------------------------
# Backup / Restore
# -----------------------------------------------------------------------------

def _create_backup(spec_dir: Path) -> Path:
    """Create a timestamped backup of the spec directory.

    Copies all JSON spec files from ``spec_dir`` into a backup
    subdirectory at ``spec_dir/migration_backups/<timestamp>/``.

    Args:
        spec_dir: Path to the user's spec directory.

    Returns:
        Path to the created backup directory.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = spec_dir / "migration_backups" / timestamp
    backup_dir.mkdir(parents=True, exist_ok=True)

    for f in spec_dir.iterdir():
        if f.is_file() and f.suffix == ".json":
            shutil.copy2(f, backup_dir / f.name)

    return backup_dir


def _restore_backup(spec_dir: Path, backup_path: Path) -> None:
    """Restore spec files from a backup directory.

    Overwrites current spec JSON files with their backed-up versions.

    Args:
        spec_dir: Path to the user's spec directory.
        backup_path: Path to the backup directory created by
            ``_create_backup``.
    """
    for f in backup_path.iterdir():
        if f.is_file() and f.suffix == ".json":
            shutil.copy2(f, spec_dir / f.name)


# -----------------------------------------------------------------------------
# Single Step Execution
# -----------------------------------------------------------------------------

def execute_single_step(
    step: MigrationStep,
    spec_dir: Path,
    toolkit_root: Path,
) -> Tuple[bool, str]:
    """Execute a single migration step.

    For ``AUTO`` actions, applies fixes directly to the spec files
    using ``apply_auto_fixes``.  For ``AI_ASSISTED`` actions, generates
    a prompt file under ``spec_dir/prompts/migration/`` and returns
    a message indicating manual intervention is needed.

    Args:
        step: The migration step to execute.
        spec_dir: Path to the user's spec directory.
        toolkit_root: Path to the devspec_toolkit root.

    Returns:
        Tuple of (success: bool, message: str) describing the outcome.
    """
    from ..generation.schema_differ import MigrationAction

    step_desc = f"[{step.step_id}] {step.action.value}"

    try:
        if step.action == MigrationAction.AUTO:
            # Apply automatic fix — reconstruct a MigrationDiff from step context
            raw_diff = step.context.get("migration_diff") if isinstance(step.context, dict) else None
            if isinstance(raw_diff, dict) and not isinstance(raw_diff, MigrationDiff):
                diff = MigrationDiff(
                    source_version=raw_diff.get("source_version"),
                    target_version=raw_diff.get("target_version", "unknown"),
                    steps=[],
                )
            elif isinstance(raw_diff, MigrationDiff):
                diff = raw_diff
            else:
                diff = MigrationDiff(
                    source_version=step.context.get("source_version") if isinstance(step.context, dict) else None,
                    target_version=step.context.get("target_version", "unknown") if isinstance(step.context, dict) else "unknown",
                )
            result = apply_auto_fixes(
                diff=diff,
                spec_dir=spec_dir,
                toolkit_root=toolkit_root,
            )
            message = (
                f"{step_desc}: auto-fix applied "
                f"({result.fixed_count} fix(es), {result.skipped_count} skipped)"
            )
            log_operation(spec_dir, f"auto_fix:{step.step_id}", "success")
            return (True, message)

        elif step.action == MigrationAction.AI_ASSISTED:
            # Generate prompt file for manual/AI intervention
            prompts_dir = spec_dir / "prompts" / "migration"
            prompts_dir.mkdir(parents=True, exist_ok=True)

            prompt_filename = f"migrate_{step.step_id}.md"
            prompt_path = prompts_dir / prompt_filename

            prompt_content = _render_prompt(step, toolkit_root)
            prompt_path.write_text(prompt_content, encoding="utf-8")

            message = (
                f"{step_desc}: prompt generated at {prompt_path}. "
                "Manual or AI-assisted intervention required."
            )
            log_operation(spec_dir, f"prompt_gen:{step.step_id}", "pending")
            return (True, message)

        else:
            # MERGE / ARCHIVE — log but mark as needing manual review
            message = (
                f"{step_desc}: action '{step.action.value}' requires manual review."
            )
            log_operation(spec_dir, f"{step.action.value}:{step.step_id}", "pending")
            return (True, message)

    except Exception as exc:
        message = f"{step_desc}: FAILED — {exc}"
        log_operation(spec_dir, f"error:{step.step_id}", "failed")
        return (False, message)


def _render_prompt(step: MigrationStep, toolkit_root: Path) -> str:
    """Render a migration prompt file for an AI-assisted step.

    If a template file exists at ``toolkit_root/prompts/migration/<template>``,
    its contents are used as the base.  Otherwise a minimal prompt is
    generated from the step context.

    Args:
        step: The migration step to render a prompt for.
        toolkit_root: Path to the devspec_toolkit root.

    Returns:
        Rendered prompt content as a string.
    """
    lines: List[str] = [
        f"# Migration Prompt: {step.step_id}",
        "",
        f"**Action**: {step.action.value}",
        "",
    ]

    # Try to load template
    if step.template:
        template_path = toolkit_root / "prompts" / "migration" / step.template
        if template_path.exists():
            lines.append("## Template")
            lines.append("")
            lines.append(template_path.read_text(encoding="utf-8"))
            lines.append("")

    # Include context
    lines.append("## Context")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(step.context, indent=2, default=str))
    lines.append("```")
    lines.append("")

    # Include depends_on if any
    if step.depends_on:
        lines.append("## Dependencies")
        lines.append("")
        for dep in step.depends_on:
            lines.append(f"- {dep}")
        lines.append("")

    return "\n".join(lines)


# -----------------------------------------------------------------------------
# Transaction Boundaries
# -----------------------------------------------------------------------------

def group_transaction_boundaries(plan: MigrationPlan) -> List[TransactionBoundary]:
    """Group migration steps by step_id for atomic transactions.

    Steps targeting the same pipeline step (e.g., multiple field fixes
    within ``04_frs``) are grouped into a single ``TransactionBoundary``
    so they can be applied and committed (or rolled back) atomically.

    Args:
        plan: The migration plan to partition.

    Returns:
        Ordered list of transaction boundaries.
    """
    groups: Dict[str, List[MigrationStep]] = {}
    order: List[str] = []

    for step in plan.steps:
        if step.step_id not in groups:
            groups[step.step_id] = []
            order.append(step.step_id)
        groups[step.step_id].append(step)

    boundaries: List[TransactionBoundary] = []
    for step_id in order:
        group_steps = groups[step_id]
        actions = {s.action.value for s in group_steps}
        desc = f"Migrate {step_id} ({len(group_steps)} operation(s), actions: {', '.join(sorted(actions))})"
        boundaries.append(TransactionBoundary(steps=group_steps, description=desc))

    return boundaries


# -----------------------------------------------------------------------------
# Plan Execution
# -----------------------------------------------------------------------------

def execute_plan(
    plan: MigrationPlan,
    spec_dir: Path,
    toolkit_root: Path,
    dry_run: bool = False,
) -> MigrationTransaction:
    """Execute a full migration plan with backup and rollback support.

    Creates a backup of the current spec files before applying any
    changes.  If any step fails, all changes are rolled back from the
    backup and the transaction is marked as rolled back.

    In ``dry_run`` mode no files are modified; the plan is walked and
    each step is reported without side effects.

    Args:
        plan: The migration plan to execute.
        spec_dir: Path to the user's spec directory.
        toolkit_root: Path to the devspec_toolkit root.
        dry_run: If True, simulate execution without modifying files.

    Returns:
        A ``MigrationTransaction`` summarising the outcome.
    """
    tx = MigrationTransaction(dry_run=dry_run)

    if not plan.steps:
        tx.operations_completed.append("No migration steps to execute.")
        return tx

    # Pre-migration validation
    pre_result = validate_pre_migration(spec_dir, toolkit_root)
    if not pre_result.valid:
        tx.operations_failed.append(
            f"Pre-migration validation failed: {'; '.join(pre_result.errors)}"
        )
        return tx

    # Create backup (unless dry run)
    if not dry_run:
        tx.backup_path = _create_backup(spec_dir)
        log_operation(spec_dir, "backup_created", str(tx.backup_path))

    # Execute steps grouped by transaction boundaries
    boundaries = group_transaction_boundaries(plan)
    for boundary in boundaries:
        if dry_run:
            for step in boundary.steps:
                desc = (
                    f"[DRY RUN] [{step.step_id}] {step.action.value}"
                    f"{f' (template: {step.template})' if step.template else ''}"
                )
                tx.operations_completed.append(desc)
            continue

        # Per-boundary file backup for granular rollback
        boundary_files: dict[str, str] = {}
        for step in boundary.steps:
            spec_file = spec_dir / f"{step.step_id}.json"
            if spec_file.exists():
                boundary_files[step.step_id] = spec_file.read_text(encoding="utf-8")

        boundary_failed = False
        for step in boundary.steps:
            success, message = execute_single_step(step, spec_dir, toolkit_root)

            if success:
                tx.operations_completed.append(message)
            else:
                tx.operations_failed.append(message)
                boundary_failed = True
                break

        if boundary_failed:
            # Rollback this boundary's files
            for step_id, content in boundary_files.items():
                (spec_dir / f"{step_id}.json").write_text(content, encoding="utf-8")
            tx.operations_failed.append(
                f"Boundary '{boundary.description}' rolled back"
            )
            # Full rollback from backup
            if tx.backup_path is not None:
                _restore_backup(spec_dir, tx.backup_path)
                tx.rolled_back = True
                log_operation(spec_dir, "rollback", str(tx.backup_path))
                tx.operations_failed.append(
                    f"Rolled back to backup at {tx.backup_path}"
                )
            break

    # Post-migration validation (only if not dry run and not rolled back)
    if not dry_run and not tx.rolled_back:
        post_result = validate_post_migration(spec_dir, toolkit_root)
        if not post_result.valid:
            warnings = "; ".join(post_result.errors)
            tx.operations_completed.append(
                f"Post-migration validation warnings: {warnings}"
            )

    return tx
