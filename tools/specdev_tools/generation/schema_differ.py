"""Schema differ for DevSpec Toolkit migration system.

Compares user spec files against toolkit schemas to identify migration gaps.
At ~1300 LOC this is the largest module in the toolkit; a future refactor
could split it into core diff logic, report formatters, and apply/backup
helpers (see AUDIT-020).

See: docs/developers/workflows/migration_system_spec.md
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..core.changelog_parser import (
    ChangelogEntry,
    VersionChangelog,
    compare_versions,
    get_changes_between,
    get_toolkit_version,
    list_versions,
    load_version,
)


# -----------------------------------------------------------------------------
# Enums
# -----------------------------------------------------------------------------

class DiffType(Enum):
    """Type of difference detected between user spec and toolkit schema."""
    MISSING_REQUIRED = "missing_required"      # Required field not present
    EXTRA_FIELD = "extra_field"                # Field exists in user but not schema
    TYPE_MISMATCH = "type_mismatch"            # Field type doesn't match schema
    RENAME_CANDIDATE = "rename_candidate"       # Field may have been renamed
    SCHEMA_REF_OUTDATED = "schema_ref"         # $schema reference is outdated
    STEP_MISSING = "step_missing"              # Step exists in toolkit but not user
    STEP_UNKNOWN = "step_unknown"              # Step exists in user but not toolkit


class MigrationAction(Enum):
    """Action required to resolve a difference."""
    AUTO = "auto"                  # Can be auto-applied (renames, $schema updates)
    AI_ASSISTED = "ai_assisted"    # Requires AI prompt generation
    MERGE = "merge"                # Step consolidation
    ARCHIVE = "archive"            # Move to archive folder


# -----------------------------------------------------------------------------
# Data Classes
# -----------------------------------------------------------------------------

@dataclass
class FieldDiff:
    """Represents a difference in a single field."""
    path: str                           # JSONPath-like path (e.g., "milestones[].user_story")
    diff_type: DiffType
    expected: Optional[str] = None      # What schema expects
    actual: Optional[str] = None        # What user has
    action: MigrationAction = MigrationAction.AUTO
    auto_fixable: bool = False
    suggestion: Optional[str] = None    # Suggested fix or migration hint


@dataclass
class StepDiff:
    """Represents differences in a step (spec file)."""
    step_id: str                        # e.g., "00_charter"
    status: str                         # "ok", "missing", "unknown", "needs_update"
    source_file: Optional[Path] = None  # User's file path
    target_file: Optional[Path] = None  # Expected toolkit schema path
    field_diffs: List[FieldDiff] = field(default_factory=list)
    action: MigrationAction = MigrationAction.AUTO
    version_added: Optional[str] = None      # Version when step was added (for context)
    paradigm_shift_from: Optional[str] = None  # Source file if this is a paradigm shift


@dataclass
class ParadigmShift:
    """Represents a paradigm shift (e.g., prose→JSON conversion)."""
    description: str
    source_file: Path
    target_file: Path
    detected: bool = False              # Whether source exists and target missing
    prompt_template: Optional[str] = None


@dataclass
class MigrationDiff:
    """Complete migration diff between user project and toolkit."""
    source_version: Optional[str]       # User's current toolkit version
    target_version: str                 # Toolkit's current version
    steps: List[StepDiff] = field(default_factory=list)
    paradigm_shifts: List[ParadigmShift] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    version_delta: Optional[str] = None  # e.g., "1 MINOR update (breaking)"


# -----------------------------------------------------------------------------
# Version Delta Calculation
# -----------------------------------------------------------------------------

def calculate_version_delta(
    source_version: Optional[str],
    target_version: str,
    changelog_dir: Optional[Path] = None,
) -> Optional[str]:
    """Calculate version delta description.
    
    Args:
        source_version: User's current version (may be None)
        target_version: Toolkit's current version
        changelog_dir: Path to changelog/ dir for breaking flag check
        
    Returns:
        Delta string like "1 MINOR update (breaking)" or None if same version
    """
    if not source_version or source_version == target_version:
        return None
    
    # Parse versions
    def parse_semver(v: str) -> tuple:
        parts = v.replace("-", ".").split(".")
        return (
            int(parts[0]) if len(parts) > 0 and parts[0].isdigit() else 0,
            int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0,
            int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0,
        )
    
    src = parse_semver(source_version)
    tgt = parse_semver(target_version)
    
    # Determine delta type and count
    major_delta = tgt[0] - src[0]
    minor_delta = tgt[1] - src[1]
    patch_delta = tgt[2] - src[2]
    
    if major_delta > 0:
        delta_type = "MAJOR"
        delta_count = major_delta
    elif minor_delta > 0:
        delta_type = "MINOR"
        delta_count = minor_delta
    elif patch_delta > 0:
        delta_type = "PATCH"
        delta_count = patch_delta
    else:
        # Downgrade or same
        return None
    
    # Check for breaking flag in target version changelog
    breaking = False
    if changelog_dir and changelog_dir.exists():
        try:
            changelog = load_version(changelog_dir, target_version)
            breaking = changelog.breaking
        except (FileNotFoundError, ValueError):
            # If no changelog, assume MAJOR = breaking
            breaking = major_delta > 0
    else:
        breaking = major_delta > 0
    
    # Format delta string
    update_word = "update" if delta_count == 1 else "updates"
    if breaking:
        return f"{delta_count} {delta_type} {update_word} (breaking)"
    return f"{delta_count} {delta_type} {update_word}"


# -----------------------------------------------------------------------------
# Step Inventory Functions
# -----------------------------------------------------------------------------

def inventory_user_steps(spec_dir: Path) -> Dict[str, Path]:
    """List user spec files with step IDs.
    
    Args:
        spec_dir: Path to user's spec/ directory
        
    Returns:
        Dict mapping step_id (e.g., "00_charter") to file path
    """
    steps: Dict[str, Path] = {}
    
    if not spec_dir.exists():
        return steps
    
    # Match pattern: NN_stepname.json or NNx_stepname.json
    pattern = re.compile(r"^(\d{2}[a-z]?_\w+)\.json$")
    
    for f in spec_dir.iterdir():
        if f.is_file() and f.suffix == ".json":
            match = pattern.match(f.name)
            if match:
                step_id = match.group(1)
                steps[step_id] = f
    
    return steps


def inventory_toolkit_schemas(schema_dir: Path) -> Dict[str, Path]:
    """List toolkit schemas with step IDs.
    
    Args:
        schema_dir: Path to toolkit's schema/ directory
        
    Returns:
        Dict mapping step_id (e.g., "00_charter") to schema file path
    """
    schemas: Dict[str, Path] = {}
    
    if not schema_dir.exists():
        return schemas
    
    # Match pattern: NN_stepname.schema.json or NNx_stepname.schema.json
    pattern = re.compile(r"^(\d{2}[a-z]?_\w+)\.schema\.json$")
    
    for f in schema_dir.iterdir():
        if f.is_file() and f.suffix == ".json":
            match = pattern.match(f.name)
            if match:
                step_id = match.group(1)
                schemas[step_id] = f
    
    return schemas


def get_user_version(spec_dir: Path) -> Optional[str]:
    """Get user's toolkit version from spec/specdev_version.
    
    Args:
        spec_dir: Path to user's spec/ directory
        
    Returns:
        Version string or None if not found
    """
    version_file = spec_dir / "specdev_version"
    if not version_file.exists():
        return None
    
    try:
        import yaml
        with open(version_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data.get("toolkit_version") if data else None
    except Exception:
        return None


# -----------------------------------------------------------------------------
# Step Comparison
# -----------------------------------------------------------------------------

def compare_step_inventories(
    user_steps: Dict[str, Path],
    toolkit_schemas: Dict[str, Path],
    changes: Optional[List[ChangelogEntry]] = None,
) -> List[StepDiff]:
    """Compare user steps against toolkit schemas.
    
    Args:
        user_steps: Dict from inventory_user_steps
        toolkit_schemas: Dict from inventory_toolkit_schemas
        changes: Optional list of changelog entries for rename detection
        
    Returns:
        List of StepDiff objects
    """
    diffs: List[StepDiff] = []
    
    # Build rename map from changes if available
    rename_map: Dict[str, str] = {}  # old_id -> new_id
    if changes:
        for change in changes:
            if change.type == "rename_step" and change.from_id and change.to_id:
                rename_map[change.from_id] = change.to_id
    
    # Check each toolkit schema
    for step_id, schema_path in sorted(toolkit_schemas.items()):
        if step_id in user_steps:
            # User has this step - check for field differences later
            diffs.append(StepDiff(
                step_id=step_id,
                status="ok",
                source_file=user_steps[step_id],
                target_file=schema_path,
                action=MigrationAction.AUTO,
            ))
        else:
            # Step missing - check if it was renamed from something user has
            old_id = None
            for old, new in rename_map.items():
                if new == step_id and old in user_steps:
                    old_id = old
                    break
            
            if old_id:
                # User has old version that needs rename
                diffs.append(StepDiff(
                    step_id=step_id,
                    status="needs_rename",
                    source_file=user_steps[old_id],
                    target_file=schema_path,
                    action=MigrationAction.AUTO,
                    field_diffs=[FieldDiff(
                        path="$filename",
                        diff_type=DiffType.RENAME_CANDIDATE,
                        expected=f"{step_id}.json",
                        actual=user_steps[old_id].name,
                        auto_fixable=True,
                        suggestion=f"Rename {user_steps[old_id].name} to {step_id}.json",
                    )],
                ))
            else:
                # Step is genuinely missing
                diffs.append(StepDiff(
                    step_id=step_id,
                    status="missing",
                    source_file=None,
                    target_file=schema_path,
                    action=MigrationAction.AI_ASSISTED,
                ))
    
    # Check for unknown user steps (not in toolkit)
    toolkit_ids = set(toolkit_schemas.keys())
    
    for step_id, user_path in sorted(user_steps.items()):
        if step_id not in toolkit_ids:
            # Check if this is an old name that should be renamed
            if step_id in rename_map:
                continue  # Already handled above
            
            # Check if it's a project-specific extension (e.g., ext_01_database.json).
            # Per docs/developers/extension_schemas.md, extensions use ext_NN_<topic>.json
            # naming. This branch catches user-created specs with a numeric step prefix
            # (e.g., 02b_custom) that have no corresponding toolkit schema.
            # Note: Some extensions like 13a_completeness_assessment ARE in toolkit_ids
            # and are handled in the first loop above.
            if re.match(r"^\d{2}[a-z]_", step_id):
                diffs.append(StepDiff(
                    step_id=step_id,
                    status="extension",
                    source_file=user_path,
                    target_file=None,
                    action=MigrationAction.ARCHIVE,
                ))
            else:
                # Unknown step
                diffs.append(StepDiff(
                    step_id=step_id,
                    status="unknown",
                    source_file=user_path,
                    target_file=None,
                    action=MigrationAction.ARCHIVE,
                ))
    
    return diffs


# -----------------------------------------------------------------------------
# Field-Level Diff
# -----------------------------------------------------------------------------

def diff_step_fields(user_file: Path, schema_path: Path) -> List[FieldDiff]:
    """Compare fields in user spec against schema.
    
    Args:
        user_file: Path to user's spec JSON file
        schema_path: Path to toolkit schema
        
    Returns:
        List of FieldDiff objects for differences found
    """
    diffs: List[FieldDiff] = []
    
    try:
        with open(user_file, "r", encoding="utf-8") as f:
            user_data = json.load(f)
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        diffs.append(FieldDiff(
            path="$",
            diff_type=DiffType.TYPE_MISMATCH,
            expected="valid JSON",
            actual=str(e),
            auto_fixable=False,
        ))
        return diffs
    
    # Check $schema reference
    user_schema_ref = user_data.get("$schema", "")
    expected_schema_ref = schema.get("$id", "")
    if user_schema_ref and expected_schema_ref:
        if user_schema_ref != expected_schema_ref:
            diffs.append(FieldDiff(
                path="$schema",
                diff_type=DiffType.SCHEMA_REF_OUTDATED,
                expected=expected_schema_ref,
                actual=user_schema_ref,
                action=MigrationAction.AUTO,
                auto_fixable=True,
                suggestion=f"Update $schema to {expected_schema_ref}",
            ))
    
    # Check required fields
    required = schema.get("required", [])
    properties = schema.get("properties", {})
    
    for field_name in required:
        if field_name not in user_data:
            field_info = properties.get(field_name, {})
            field_type = field_info.get("type", "unknown")
            
            diffs.append(FieldDiff(
                path=field_name,
                diff_type=DiffType.MISSING_REQUIRED,
                expected=f"{field_type} (required)",
                actual="missing",
                action=MigrationAction.AI_ASSISTED,
                auto_fixable=False,
                suggestion=f"Add required field '{field_name}'",
            ))
    
    # Check for extra fields if additionalProperties is false
    if schema.get("additionalProperties") is False:
        allowed_fields = set(properties.keys()) | {"$schema"}
        for field_name in user_data.keys():
            if field_name not in allowed_fields:
                diffs.append(FieldDiff(
                    path=field_name,
                    diff_type=DiffType.EXTRA_FIELD,
                    expected="not allowed",
                    actual=f"present ({type(user_data[field_name]).__name__})",
                    action=MigrationAction.ARCHIVE,
                    auto_fixable=False,
                    suggestion=f"Move '{field_name}' to _migration_notes or remove",
                ))
    
    return diffs


# -----------------------------------------------------------------------------
# Paradigm Shift Detection
# -----------------------------------------------------------------------------

def detect_paradigm_shifts(
    spec_dir: Path,
    project_root: Path,
    changelog: Optional[VersionChangelog] = None,
) -> List[ParadigmShift]:
    """Detect paradigm shifts (e.g., prose→JSON conversion needs).
    
    Args:
        spec_dir: Path to user's spec/ directory
        project_root: Path to user's project root
        changelog: Optional changelog for paradigm shift definitions
        
    Returns:
        List of ParadigmShift objects
    """
    shifts: List[ParadigmShift] = []
    
    # Check for common paradigm shifts
    paradigm_checks = [
        # (source_file, target_file, description, prompt_template)
        (
            project_root / "roadmap.md",
            spec_dir / "14_roadmap.json",
            "Prose roadmap converted to structured JSON",
            "template_prose_to_json.md",
        ),
        (
            project_root / "docs" / "roadmap.md",
            spec_dir / "14_roadmap.json",
            "Prose roadmap converted to structured JSON",
            "template_prose_to_json.md",
        ),
    ]
    
    # Add changelog-defined paradigm shifts
    if changelog:
        for change in changelog.changes:
            if change.type == "paradigm_shift" and change.detection:
                source_exists = change.detection.get("file_exists", "")
                target_missing = change.detection.get("file_missing", "")
                if source_exists and target_missing:
                    source_path = project_root / source_exists
                    target_path = project_root / target_missing
                    prompt = None
                    if change.migration:
                        prompt = change.migration.prompt
                    paradigm_checks.append((
                        source_path,
                        target_path,
                        change.description or "Paradigm shift",
                        prompt or "",
                    ))
    
    for source, target, description, prompt in paradigm_checks:
        if source.exists() and not target.exists():
            shifts.append(ParadigmShift(
                description=description,
                source_file=source,
                target_file=target,
                detected=True,
                prompt_template=prompt,
            ))
    
    return shifts


# -----------------------------------------------------------------------------
# Main Entry Point
# -----------------------------------------------------------------------------

def diff_spec_directory(
    spec_dir: Path,
    toolkit_root: Path,
    changelog_dir: Optional[Path] = None,
) -> MigrationDiff:
    """Compute complete migration diff between user specs and toolkit.
    
    Args:
        spec_dir: Path to user's spec/ directory
        toolkit_root: Path to devspec_toolkit root
        changelog_dir: Optional path to changelog/ (defaults to toolkit_root/changelog)
        
    Returns:
        MigrationDiff with all differences
    """
    if changelog_dir is None:
        changelog_dir = toolkit_root / "changelog"
    
    schema_dir = toolkit_root / "schema"
    
    # Get versions
    user_version = get_user_version(spec_dir)
    toolkit_version = get_toolkit_version(toolkit_root)
    
    # Load changelog for migration hints
    changelog = None
    all_changes = []
    
    if toolkit_version and changelog_dir.exists():
        try:
            # 1. Load specific target version changelog (for Paradigm Shifts & direct hints)
            changelog = load_version(changelog_dir, toolkit_version)
            
            # 2. Load ALL changes between source and target (for Multi-Version Renames)
            if user_version:
                 all_changes = get_changes_between(changelog_dir, user_version, toolkit_version)
            else:
                # Bootstrap or unknown source: Just use target version changes?
                # Actually, for bootstrap we might want everything, but robustly
                # we usually just care about the target state. 
                # For now, let's include the target version's changes at minimum.
                all_changes = changelog.changes
                
        except (FileNotFoundError, ValueError):
            pass
    
    # Inventory steps
    user_steps = inventory_user_steps(spec_dir)
    toolkit_schemas = inventory_toolkit_schemas(schema_dir)
    
    # Compare step inventories (Pass ALL changes for robust rename detection)
    step_diffs = compare_step_inventories(user_steps, toolkit_schemas, all_changes)
    
    # Diff fields for existing steps
    for diff in step_diffs:
        if diff.status == "ok" and diff.source_file and diff.target_file:
            field_diffs = diff_step_fields(diff.source_file, diff.target_file)
            if field_diffs:
                diff.field_diffs = field_diffs
                diff.status = "needs_update"
    
    # Detect paradigm shifts
    project_root = spec_dir.parent
    paradigm_shifts = detect_paradigm_shifts(spec_dir, project_root, changelog)
    
    # Link paradigm shifts to corresponding missing steps
    paradigm_map = {}  # target file stem -> source file name
    for shift in paradigm_shifts:
        # Extract step id from target file (e.g., "14_roadmap.json" -> "14_roadmap")
        target_stem = shift.target_file.stem
        paradigm_map[target_stem] = shift.source_file.name
    
    # Update missing steps with paradigm shift hints
    for step_diff in step_diffs:
        if step_diff.status == "missing" and step_diff.step_id in paradigm_map:
            step_diff.paradigm_shift_from = paradigm_map[step_diff.step_id]
    
    # Build summary
    ok_count = sum(1 for d in step_diffs if d.status == "ok")
    missing_count = sum(1 for d in step_diffs if d.status == "missing")
    needs_update_count = sum(1 for d in step_diffs if d.status == "needs_update")
    needs_rename_count = sum(1 for d in step_diffs if d.status == "needs_rename")
    unknown_count = sum(1 for d in step_diffs if d.status == "unknown")
    extension_count = sum(1 for d in step_diffs if d.status == "extension")
    
    summary = {
        "user_version": user_version,
        "toolkit_version": toolkit_version,
        "steps_ok": ok_count,
        "steps_missing": missing_count,
        "steps_needs_update": needs_update_count,
        "steps_needs_rename": needs_rename_count,
        "steps_unknown": unknown_count,
        "steps_extension": extension_count,
        "paradigm_shifts": len(paradigm_shifts),
        "total_toolkit_steps": len(toolkit_schemas),
        "total_user_steps": len(user_steps),
    }
    
    # Calculate version delta
    version_delta = calculate_version_delta(
        user_version,
        toolkit_version or "unknown",
        changelog_dir,
    )
    
    return MigrationDiff(
        source_version=user_version,
        target_version=toolkit_version or "unknown",
        steps=step_diffs,
        paradigm_shifts=paradigm_shifts,
        summary=summary,
        version_delta=version_delta,
    )


# -----------------------------------------------------------------------------
# Output Formatting
# -----------------------------------------------------------------------------

def format_status_report(diff: MigrationDiff) -> str:
    """Format migration status as human-readable text.
    
    Args:
        diff: MigrationDiff from diff_spec_directory
        
    Returns:
        Formatted status string
    """
    lines = [
        "",
        "🔍 Toolkit Migration Status",
        "━" * 27,
        f"Current toolkit version: {diff.target_version}",
    ]
    
    if diff.source_version:
        lines.append(f"Your project version:    {diff.source_version} (from spec/specdev_version)")
    else:
        lines.append("Your project version:    Not detected (no spec/specdev_version)")
    
    lines.append("")
    
    s = diff.summary
    if diff.source_version == diff.target_version:
        lines.append("✅ Project is aligned with toolkit version")
    elif diff.source_version:
        lines.append("Version Delta:")
        delta_str = diff.version_delta or "update required"
        lines.append(f"  {diff.source_version} → {diff.target_version}: {delta_str}")
        lines.append("")
        lines.append("⚠️  Migration recommended")
        
        if s["steps_missing"]:
            lines.append(f"   - {s['steps_missing']} new steps to generate")
        if s["steps_needs_rename"]:
            lines.append(f"   - {s['steps_needs_rename']} steps to rename")
        if s["steps_needs_update"]:
            lines.append(f"   - {s['steps_needs_update']} steps need field updates")
        if s["paradigm_shifts"]:
            lines.append(f"   - {s['paradigm_shifts']} paradigm shifts detected")
    else:
        lines.append("⚠️  No version tracking detected")
        lines.append("   This may be a bootstrap case (empty → current)")
    
    lines.append("")
    lines.append("Run `specdev align diff <spec_dir>` for detailed analysis.")
    
    return "\n".join(lines)


def format_diff_report(diff: MigrationDiff) -> str:
    """Format migration diff as human-readable text.
    
    Args:
        diff: MigrationDiff from diff_spec_directory
        
    Returns:
        Formatted diff string
    """
    lines = [
        "",
        "📊 Migration Diff Report",
        "━" * 24,
        "",
        f"Step Inventory ({diff.summary.get('total_toolkit_steps', 0)} steps in current toolkit):",
    ]
    
    # Status icons
    icons = {
        "ok": "✅",
        "missing": "❌",
        "needs_update": "⚠️ ",
        "needs_rename": "🔄",
        "unknown": "❓",
        "extension": "📦",
    }
    
    status_labels = {
        "ok": "OK",
        "missing": "MISSING",
        "needs_update": "NEEDS UPDATE",
        "needs_rename": "NEEDS RENAME",
        "unknown": "UNKNOWN",
        "extension": "EXTENSION",
    }
    
    for step in diff.steps:
        icon = icons.get(step.status, "  ")
        label = status_labels.get(step.status, step.status.upper())
        file_name = f"{step.step_id}.json"
        padding = "." * (35 - len(file_name))
        
        # Add context hints for missing steps
        context_hint = ""
        if step.status == "missing" and step.paradigm_shift_from:
            context_hint = f" (paradigm shift from {step.paradigm_shift_from})"
        
        lines.append(f"  {icon} {file_name} {padding} {label}{context_hint}")
        
        # Show field diffs for steps needing updates
        if step.field_diffs:
            for fd in step.field_diffs[:3]:  # Limit to first 3
                lines.append(f"      └─ {fd.path}: {fd.diff_type.value}")
            if len(step.field_diffs) > 3:
                lines.append(f"      └─ ... and {len(step.field_diffs) - 3} more")
    
    # Paradigm shifts
    if diff.paradigm_shifts:
        lines.extend(["", "Paradigm Shifts Detected:"])
        for shift in diff.paradigm_shifts:
            lines.append(f"  📝 {shift.source_file.name} exists but {shift.target_file.name} missing")
            lines.append(f"     → Requires AI-assisted conversion")
    
    # Summary
    s = diff.summary
    lines.extend([
        "",
        "Summary:",
        f"  ✅ {s.get('steps_ok', 0)} steps OK",
    ])
    
    if s.get("steps_needs_rename"):
        lines.append(f"  🔄 {s['steps_needs_rename']} steps need rename")
    if s.get("steps_needs_update"):
        lines.append(f"  ⚠️  {s['steps_needs_update']} steps need field updates")
    if s.get("steps_missing"):
        lines.append(f"  ❌ {s['steps_missing']} steps missing (need generation)")
    if s.get("paradigm_shifts"):
        lines.append(f"  📝 {s['paradigm_shifts']} paradigm shifts detected")
    if s.get("steps_extension"):
        lines.append(f"  📦 {s['steps_extension']} project extensions")
    if s.get("steps_unknown"):
        lines.append(f"  ❓ {s['steps_unknown']} unknown steps")
    
    return "\n".join(lines)


def format_plan_report(diff: MigrationDiff) -> str:
    """Format migration plan with ordered actions.
    
    Args:
        diff: MigrationDiff from diff_spec_directory
        
    Returns:
        Formatted plan string
    """
    lines = [
        "",
        "📋 Migration Plan",
        "━" * 30,
        "",
    ]
    
    # Group actions
    mechanical_ops = []
    semantic_ops = []
    
    # 1. Mechanical (Auto) - Renames
    for step in diff.steps:
        if step.status == "needs_rename" and step.action == MigrationAction.AUTO:
            field_diff = next((fd for fd in step.field_diffs if fd.diff_type == DiffType.RENAME_CANDIDATE), None)
            new_name = field_diff.expected if field_diff else f"{step.step_id}.json"
            src_name = step.source_file.name if step.source_file else step.step_id
            mechanical_ops.append(f"Rename {src_name} → {new_name}")

    # 2. Mechanical (Auto) - Metadata
    for step in diff.steps:
        for fd in step.field_diffs:
            if fd.diff_type == DiffType.SCHEMA_REF_OUTDATED and fd.action == MigrationAction.AUTO:
                src_name = step.source_file.name if step.source_file else step.step_id
                mechanical_ops.append(f"Update $schema in {src_name}")

    # 3. Semantic (AI) - Paradigm Shifts
    for shift in diff.paradigm_shifts:
        if shift.detected:
            semantic_ops.append(f"Convert {shift.source_file.name} → {shift.target_file.name} (AI-Assisted)")

    # 4. Semantic (AI) - Missing Steps
    for step in diff.steps:
        if step.status == "missing" and step.action == MigrationAction.AI_ASSISTED:
            semantic_ops.append(f"Generate {step.step_id}.json (AI-Assisted)")
            
    # 5. Semantic (AI) - Fields
    for step in diff.steps:
         for fd in step.field_diffs:
             if fd.action == MigrationAction.AI_ASSISTED:
                 semantic_ops.append(f"Add field '{fd.path}' to {step.step_id}.json (AI-Assisted)")
             if fd.action == MigrationAction.ARCHIVE:
                 semantic_ops.append(f"Archive field '{fd.path}' in {step.step_id}.json")

    # Output Mechanical
    if mechanical_ops:
        lines.append("🤖 Phase 1: Mechanical Fixes (Run `apply --auto`)")
        for i, op in enumerate(mechanical_ops, 1):
            lines.append(f"  {i}. {op}")
        lines.append("")
    else:
        lines.append("🤖 Phase 1: Mechanical Fixes")
        lines.append("  (None required)")
        lines.append("")

    # Output Semantic
    if semantic_ops:
        lines.append("🧠 Phase 2: Semantic Migrations (Run `prompts`)")
        for i, op in enumerate(semantic_ops, 1):
            lines.append(f"  {i}. {op}")
    else:
        lines.append("🧠 Phase 2: Semantic Migrations")
        lines.append("  (None required)")

    return "\n".join(lines)


# -----------------------------------------------------------------------------
# Pre-Migration Validation (Phase 5)
# -----------------------------------------------------------------------------

@dataclass
class ValidationResult:
    """Result of pre-migration validation."""
    can_proceed: bool
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


def validate_pre_migration(spec_dir: Path, toolkit_root: Path) -> ValidationResult:
    """Validate environment before migration.
    
    Checks per spec:
    - Git repo exists: Warn, skip Git backup
    - Working tree clean: Warn, prompt to continue
    - spec/ exists: Abort
    - Toolkit version detectable: Abort
    """
    warnings = []
    errors = []
    
    # Check spec/ exists
    if not spec_dir.exists():
        errors.append(f"No spec/ directory found: {spec_dir}")
    
    # Check toolkit version is detectable
    toolkit_version = get_toolkit_version(toolkit_root)
    if not toolkit_version:
        errors.append("Cannot determine toolkit version from pyproject.toml")
    
    # Check Git repo and working tree
    git_dir = spec_dir.parent / ".git"
    if not git_dir.exists():
        warnings.append("Not a Git repo - Git backup will be skipped")
    else:
        import subprocess
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=spec_dir.parent,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.stdout.strip():
                warnings.append("Git working tree has uncommitted changes")
        except Exception:
            warnings.append("Could not check Git status")
    
    return ValidationResult(
        can_proceed=len(errors) == 0,
        warnings=warnings,
        errors=errors,
    )


def log_operation(spec_dir: Path, operation: str, status: str) -> None:
    """Log operation to spec/migration_log.
    
    Args:
        spec_dir: Path to spec/ directory
        operation: Description of operation
        status: Status (e.g., "success", "failed")
    """
    from datetime import datetime
    
    log_file = spec_dir / "migration_log"
    timestamp = datetime.now().isoformat()
    
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"{timestamp} | {status} | {operation}\n")


# -----------------------------------------------------------------------------
# Backup System (Phase 5)
# -----------------------------------------------------------------------------

@dataclass
class BackupResult:
    """Result of backup operation."""
    git_branch: Optional[str]
    backup_dir: Path
    timestamp: str


def create_backup(spec_dir: Path, target_version: str) -> BackupResult:
    """Create hybrid backup: folder copy (always) + Git branch (if in repo).
    
    Args:
        spec_dir: Path to user's spec/ directory
        target_version: Version being migrated to
        
    Returns:
        BackupResult with backup location info
    """
    import shutil
    from datetime import datetime
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Folder copy (always)
    backup_dir = spec_dir / "migration_backups" / f"pre_v{target_version}_{timestamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    for item in spec_dir.iterdir():
        if item.name == "migration_backups":
            continue  # Don't copy backup folder itself
        if item.is_dir():
            shutil.copytree(item, backup_dir / item.name)
        else:
            shutil.copy2(item, backup_dir / item.name)
    
    # Git branch (if in repo) - create branch at current commit
    git_branch = None
    git_dir = spec_dir.parent / ".git"
    if git_dir.exists():
        import subprocess
        branch_name = f"backup/pre-migration-v{target_version}"
        try:
            # First ensure we have a commit to branch from
            subprocess.run(
                ["git", "add", str(spec_dir)],
                cwd=spec_dir.parent,
                capture_output=True,
                check=False,
                timeout=10,
            )
            subprocess.run(
                ["git", "commit", "-m", f"Pre-migration snapshot for v{target_version}"],
                cwd=spec_dir.parent,
                capture_output=True,
                check=False,
                timeout=10,
            )
            # Create branch at current HEAD
            subprocess.run(
                ["git", "branch", "-f", branch_name],
                cwd=spec_dir.parent,
                capture_output=True,
                check=False,
                timeout=10,
            )
            git_branch = branch_name
        except Exception:
            pass  # Git backup is optional
    
    return BackupResult(
        git_branch=git_branch,
        backup_dir=backup_dir,
        timestamp=timestamp,
    )


def list_backups(spec_dir: Path) -> List[BackupResult]:
    """List available backups for rollback.
    
    Args:
        spec_dir: Path to user's spec/ directory
        
    Returns:
        List of BackupResult objects
    """
    backups = []
    backup_root = spec_dir / "migration_backups"
    
    if backup_root.exists():
        for backup_dir in sorted(backup_root.iterdir(), reverse=True):
            if backup_dir.is_dir() and backup_dir.name.startswith("pre_v"):
                # Parse version and timestamp from name
                parts = backup_dir.name.split("_", 2)  # pre, vX.Y.Z, timestamp
                timestamp = parts[2] if len(parts) > 2 else ""
                backups.append(BackupResult(
                    git_branch=None,
                    backup_dir=backup_dir,
                    timestamp=timestamp,
                ))
    
    return backups


def restore_backup(spec_dir: Path, backup: BackupResult) -> None:
    """Restore from a backup.
    
    Args:
        spec_dir: Path to user's spec/ directory
        backup: BackupResult to restore from
    """
    import shutil
    
    # Atomic Restore Strategy:
    # 1. Restore backup to spec/.restore_tmp
    # 2. Rename spec -> spec.trash
    # 3. Rename spec/.restore_tmp -> spec
    # 4. Cleanup spec.trash
    
    restore_tmp = spec_dir.parent / ".restore_tmp"
    if restore_tmp.exists():
        shutil.rmtree(restore_tmp)
    restore_tmp.mkdir()
    
    # Copy from backup to temp location
    for item in backup.backup_dir.iterdir():
        if item.is_dir():
            shutil.copytree(item, restore_tmp / item.name)
        else:
            shutil.copy2(item, restore_tmp / item.name)
            
    # Perform the swap
    trash_dir = spec_dir.parent / "spec.trash"
    if trash_dir.exists():
       shutil.rmtree(trash_dir)
       
    spec_dir.rename(trash_dir)
    restore_tmp.rename(spec_dir)
    
    # Cleanup trash
    shutil.rmtree(trash_dir)


# -----------------------------------------------------------------------------
# Auto-Apply Fixes (Phase 5)
# -----------------------------------------------------------------------------

@dataclass
class ApplyResult:
    """Result of applying auto fixes."""
    operations: List[str]
    backup: Optional[BackupResult]
    success: bool
    error: Optional[str] = None


def apply_auto_fixes(
    diff: MigrationDiff,
    spec_dir: Path,
    toolkit_root: Path,
    dry_run: bool = False,
) -> ApplyResult:
    """Apply mechanical/auto-fixable changes.
    
    Args:
        diff: MigrationDiff with identified changes
        spec_dir: Path to user's spec/ directory
        toolkit_root: Path to toolkit root
        dry_run: If True, only report what would be done
        
    Returns:
        ApplyResult with operations performed
    """
    operations = []
    backup = None
    
    # Count auto-fixes needed
    auto_fixes = []
    for step in diff.steps:
        if step.status == "needs_rename":
            auto_fixes.append(("rename", step))
        for fd in step.field_diffs:
            if fd.auto_fixable:
                auto_fixes.append(("field", step, fd))
    
    if not auto_fixes:
        return ApplyResult(
            operations=["No auto-fixable changes found."],
            backup=None,
            success=True,
        )
    
    # Create backup (unless dry run)
    if not dry_run:
        backup = create_backup(spec_dir, diff.target_version)
        operations.append(f"Creating backup...")
        operations.append(f"      Git branch: {backup.git_branch or 'N/A'}")
        operations.append(f"      Folder: {backup.backup_dir.name}/")
        operations.append(f"      ✅ Backup complete")
        log_operation(spec_dir, f"Created backup: {backup.backup_dir.name}", "success")
    else:
        operations.append("[DRY RUN] Would create backup")
    
    # Apply fixes with error handling
    for fix in auto_fixes:
        try:
            if fix[0] == "rename":
                step = fix[1]
                old_path = step.source_file
                new_name = f"{step.step_id}.json"
                new_path = spec_dir / new_name
                
                if dry_run:
                    operations.append(f"[DRY RUN] Would rename {old_path.name} → {new_name}")
                else:
                    if new_path.exists():
                        operations.append(f"⚠️ Skipped rename {old_path.name} → {new_name} (target exists)")
                        log_operation(spec_dir, f"Skipped rename {old_path.name} (conflict)", "skipped")
                    else:
                        old_path.rename(new_path)
                        operations.append(f"Renaming {old_path.name} → {new_name}...")
                        operations.append(f"      ✅ File renamed")
                        log_operation(spec_dir, f"Renamed {old_path.name} → {new_name}", "success")
            
            elif fix[0] == "field":
                step, fd = fix[1], fix[2]
                if fd.diff_type == DiffType.SCHEMA_REF_OUTDATED:
                    file_path = step.source_file
                    if dry_run:
                        operations.append(f"[DRY RUN] Would update $schema in {file_path.name}")
                    else:
                        try:
                            with open(file_path, "r", encoding="utf-8") as f:
                                data = json.load(f)
                            data["$schema"] = fd.expected
                            with open(file_path, "w", encoding="utf-8") as f:
                                json.dump(data, f, indent=2)
                            operations.append(f"Updating $schema in {file_path.name}...")
                            operations.append(f"      ✅ Schema reference updated")
                            log_operation(spec_dir, f"Updated $schema in {file_path.name}", "success")
                        except json.JSONDecodeError as e:
                            operations.append(f"⚠️ Skipped {file_path.name}: JSON parse error at line {e.lineno}")
                            log_operation(spec_dir, f"Failed {file_path.name}: {e}", "error")
        except Exception as e:
            operations.append(f"⚠️ Error: {e}")
            log_operation(spec_dir, f"Error during fix: {e}", "error")
    
    # Update specdev_version with in-progress marker
    if not dry_run:
        version_file = spec_dir / "specdev_version"
        try:
            import yaml
            version_data = {"toolkit_version": diff.target_version, "migration_status": "in_progress"}
            if version_file.exists():
                with open(version_file, "r", encoding="utf-8") as f:
                    existing = yaml.safe_load(f) or {}
                existing["migration_status"] = "in_progress"
                existing["target_version"] = diff.target_version
                version_data = existing
            with open(version_file, "w", encoding="utf-8") as f:
                yaml.dump(version_data, f, default_flow_style=False)
            operations.append(f"Updating spec/specdev_version...")
            operations.append(f"      ✅ In-progress marker added")
            log_operation(spec_dir, "Updated specdev_version with in-progress marker", "success")
        except Exception as e:
            operations.append(f"⚠️ Could not update specdev_version: {e}")
    else:
        operations.append("[DRY RUN] Would update spec/specdev_version")
    
    # Log completion
    if not dry_run:
        log_operation(spec_dir, "Migration apply --auto completed", "success")
    
    return ApplyResult(
        operations=operations,
        backup=backup,
        success=True,
    )


def format_apply_report(result: ApplyResult) -> str:
    """Format apply result as human-readable text."""
    lines = [
        "",
        "🔧 Applying Mechanical Fixes",
        "━" * 28,
        "",
    ]
    
    # Count main operations (not indented detail lines)
    main_ops = [op for op in result.operations if not op.startswith("      ")]
    op_num = 0
    
    for op in result.operations:
        if op.startswith("      "):
            # Detail line - no numbering
            lines.append(op)
        else:
            # Main operation - add numbering
            op_num += 1
            lines.append(f"[{op_num}/{len(main_ops)}] {op}")
    
    lines.append("")
    if result.success:
        lines.append(f"✅ Mechanical fixes complete ({len(main_ops)}/{len(main_ops)})")
        lines.append("")
        lines.append("Remaining work requires AI assistance.")
        lines.append("Run `specdev align prompts` to generate migration prompts.")
    else:
        lines.append(f"❌ Failed: {result.error}")
    
    return "\n".join(lines)


# -----------------------------------------------------------------------------
# Post-Migration Validation (Phase 9)
# -----------------------------------------------------------------------------

def validate_post_migration(
    spec_dir: Path, 
    toolkit_root: Path,
    toolkit_version: str
) -> ValidationResult:
    """Validate migrated specs and trace integrity.
    
    Args:
        spec_dir: Path to user's spec/ directory
        toolkit_root: Path to toolkit root
        toolkit_version: The target toolkit version
        
    Returns:
        ValidationResult with status and messages
    """
    from ..validation.validate import validate_dir
    warnings = []
    errors = []
    
    # 1. Schema Validation
    schema_failures = validate_dir(str(toolkit_root), str(spec_dir), git_root=str(spec_dir.parent), spec_root=str(spec_dir))
    if schema_failures:
        for fail in schema_failures:
            errors.append(f"Schema Validation Failed: {fail}")

    # 2. Trace Integrity
    from ..validation.matrix import validate_trace_integrity
    from ..core.errors import render_errors as _render_errors
    trace_errors = validate_trace_integrity(str(toolkit_root), str(spec_dir))
    if trace_errors:
        errors.extend(_render_errors(trace_errors))
    
    # 3. Migration Notes Check
    notes_file = spec_dir / "_migration_notes.md"
    if notes_file.exists():
        warnings.append(f"_migration_notes.md exists. Please review manually for unmapped data.")
    
    # Check checks for in-file _migration_notes objects
    for f in spec_dir.iterdir():
        if f.suffix == ".json":
            try:
                with open(f, "r", encoding="utf-8") as file:
                    data = json.load(file)
                if "_migration_notes" in data:
                    warnings.append(f"{f.name} contains '_migration_notes'. Review required.")
            except Exception:
                pass

    if errors:
        return ValidationResult(can_proceed=False, warnings=warnings, errors=errors)
    
    # 4. Update Version File on Success
    version_file = spec_dir / "specdev_version"
    try:
        import yaml
        version_data = {
            "toolkit_version": toolkit_version,
            "created_at": _get_timestamp(),
            "last_migration": _get_timestamp(),
            "migration_history": []
        }
        
        if version_file.exists():
             with open(version_file, "r", encoding="utf-8") as f:
                existing = yaml.safe_load(f) or {}
                
                # Preserve created_at, or set if missing (bootstrap)
                version_data["created_at"] = existing.get("created_at", _get_timestamp())
                
                version_data["migration_history"] = existing.get("migration_history", [])
                
                # Add this migration to history
                if existing.get("toolkit_version") != toolkit_version:
                     history_entry = {
                         "from": existing.get("toolkit_version", "unknown"),
                         "to": toolkit_version,
                         "date": _get_timestamp(),
                         "notes": f"Migrated to v{toolkit_version}"
                     }
                     version_data["migration_history"].append(history_entry)
        
        with open(version_file, "w", encoding="utf-8") as f:
            yaml.dump(version_data, f, default_flow_style=False)
            
    except Exception as e:
        warnings.append(f"Could not update specdev_version: {e}")

    return ValidationResult(can_proceed=True, warnings=warnings, errors=errors)

def _get_timestamp():
    from datetime import datetime
    return datetime.utcnow().isoformat() + "Z"
