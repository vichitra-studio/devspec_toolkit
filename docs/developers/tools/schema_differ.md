# Schema Differ Library Reference

## Overview
The `schema_differ` module is the core engine behind the migration system. It compares a user's `spec/` directory against the toolkit's `schema/` definitions and `changelog/` rules to compute a precise migration delta.

## Usage

```python
from specdev_tools.generation.schema_differ import (
    diff_spec_directory,
    format_diff_report
)

# 1. Compute Diff
diff = diff_spec_directory(user_spec_dir, toolkit_root)

# 2. Print Report
print(format_diff_report(diff))
```

The module only reads and reports (`align status | diff | plan | prompts`). It no longer applies anything: `specdev align apply --auto` runs the migration runner (`specdev_tools.migration.runner.run_migration`), which works on a scratch copy of the spec folder, never commits and keeps no backup folder (git is the backup). `list_backups` and `restore_backup` remain only for the `spec/migration_backups/` folders that earlier toolkits wrote (`align rollback`).

The functions that applied a migration and a validation pass of the old flow (`validate_pre_migration`, `create_backup`, `apply_auto_fixes`, `format_apply_report`, `validate_post_migration` and its `ValidationResult`) are gone: the mechanical migration is the runner's, and finishing it is `specdev align validate`, which runs `spec-check --merge`.

## The stamp: `stamp_specdev_version`

```python
stamp_specdev_version(spec_dir, toolkit_version, is_migration=False, *,
                      migration_status=KEEP_STATUS, history_notes=None, now=None)
```

The one writer of `spec/specdev_version`. `specdev update` (a plain re-stamp), the migration runner (the start of a migration) and `specdev align validate` (its end) all call it. It reads the file first and keeps every key it holds, whether it knows the key or not; only the keys named here change. `is_migration=True` sets `last_migration` and appends a `migration_history` entry (`from`, `to`, `date`, `notes`) when the recorded version differs from `toolkit_version`; a re-run at the same version appends none. `migration_status` is left alone for `KEEP_STATUS`, set to a string (`in_progress`, by the runner) or removed for `None` (`align validate`). `history_notes` is the `notes` of the entry (default `Migrated to v<version>`); `now` is the clock of the dates. It returns `None` on success or an error message.

## Data Structures

### MigrationDiff
The top-level object representing the gap between two states.

```python
@dataclass
class MigrationDiff:
    source_version: Optional[str]  # e.g. "0.1.0" or None (bootstrap)
    target_version: str            # e.g. "0.2.0"
    steps: List[StepDiff]          # Per-step analysis
    paradigm_shifts: List[dict]    # Detected shifts (e.g. roadmap.md)
    summary: dict                  # Counters (missing, renames, etc)
```

### StepDiff
Analysis of a single step.

```python
@dataclass
class StepDiff:
    step_id: str                   # e.g. "15_scaffold"
    status: str                    # "ok", "missing", "rename", "schema_mismatch"
    source_file: Optional[str]     # e.g. "spec/13_scaffold.json"
    target_file: Optional[str]     # e.g. "spec/15_scaffold.json"
    field_diffs: List[FieldDiff]   # Detailed field-level diffs
    action: MigrationAction        # Recommended action
```

### FieldDiff
Granular difference for a specific field within a step.

```python
@dataclass
class FieldDiff:
    path: str                      # JSON path e.g. "milestones[0].user_story"
    diff_type: DiffType            # Enum: MISSING_REQUIRED, TYPE_MISMATCH, etc.
    expected: Optional[str]        # Expected schema type/value
    actual: Optional[str]          # Actual value/type
    action: MigrationAction        # AUTO, AI_ASSISTED, etc.
```

## Enum Definitions

### DiffType
- `MISSING_REQUIRED`: A field required by schema is missing.
- `EXTRA_FIELD`: A field exists in data but not in schema (requires `additionalProperties: false`).
- `TYPE_MISMATCH`: Field has wrong type (e.g. string vs int).
- `RENAME_CANDIDATE`: Field likely renamed.
- `SCHEMA_REF_OUTDATED`: `$schema` URL points to old version.
- `STEP_MISSING`: Entire step file is missing.
- `STEP_UNKNOWN`: File exists but doesn't map to any known step.

### MigrationAction
- `AUTO`: Safe to apply mechanically (e.g. rename file, update `$schema`).
- `AI_ASSISTED`: Requires semantic understanding (e.g. inferring missing data).
- `MERGE`: Requires combining multiple files.
- `ARCHIVE`: File should be moved to archive (deprecated).

## Core Logic

### `diff_spec_directory`
1.  **Inventory**: Scans `spec/` for JSON files and `docs/` for prose candidates.
2.  **Version Check**: Reads `spec/specdev_version`.
3.  **Changelog Lookup**: Loads `changelog/` to find explicit rename rules.
4.  **Schema Validation**: Validates each existing file against target schema.
5.  **Gap Analysis**: correlated inventory with requirements to find missing steps.
