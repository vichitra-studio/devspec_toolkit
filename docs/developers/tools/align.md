# specdev align - Toolkit Alignment CLI

## Synopsis
`specdev align <subcommand> [options]`

## Overview
The `align` tool is the implementation of the [Alignment Workflow](../workflows/workflow_align.md). It manages the process of synchronizing a user's `spec/` directory with the current version of the DevSpec Toolkit.

## Subcommands

### status
Check alignment between project and toolkit versions.

```bash
specdev align status --repo-root ./devspec_toolkit
```

**Output**:
- Toolkit Version (from `tools/pyproject.toml`)
- Project Version (from `spec/specdev_version`)
- Version Delta (Major/Minor/Patch)
- Brief recommendation ("Migration recommended", "Aligned", etc.)

### diff
Compute and display migration delta.

```bash
specdev align diff --repo-root ./devspec_toolkit
```

**Output**:
- Detailed list of missing steps
- Renamed steps
- Schema drifts (missing fields, extra fields, type mismatches)
- Paradigm shifts (e.g., `roadmap.md` → `14_roadmap.json`)

### plan
Generate step-by-step migration plan.

```bash
specdev align plan --repo-root ./devspec_toolkit
```

**Output**:
- Ordered list of operations
- Classification of operations (Mechanical vs Semantic)

### apply
Apply migration changes.

```bash
specdev align apply --auto --repo-root ./devspec_toolkit
```

**Options**:
- `--auto`: Apply only mechanical fixes (file renames, schema updates, header updates).
- `--dry-run`: Show what would be changed without modifying files.

**Safety**:
- Automatically creates a hybrid backup (Git branch + local folder) before running.
- Updates `spec/specdev_version` to reflect partial/in-progress migration.

### prompts
Generate AI prompts for semantic migrations.

```bash
specdev align prompts --output migration_prompts/ --mode upgrade
```

**Options**:
- `--output DIR`: Directory to write generated prompt files (default: local dir).
- `--mode`: `upgrade` (default) or `bootstrap`.

**Behavior**:
- Reads the Diff.
- For each semantic gap, identifies the correct template from `devspec_toolkit/migration_prompts/`.
- Fills the template with source data (if available), target schema, and diff context.
- Writes a ready-to-use prompt file.

### validate
Validate migrated specs against schemas.

```bash
specdev align validate --repo-root ./devspec_toolkit
```

**Checks**:
- Conformance to all schemas.
- Trace integrity (all referenced IDs exist).
- Presence of `_migration_notes` (warns if manual review needed).

### rollback
Restore from backup.

```bash
specdev align rollback
```

**Behavior**:
- Lists available backups (Git branches and `spec/migration_backups/` folders).
- Interactively asks user to select a backup.
- Restores the selected state.

## Examples

**Full Migration Flow**:
```bash
specdev align status
specdev align diff
specdev align apply --auto
specdev align prompts --output prompts_v0.2.0/
# ... manual AI work ...
specdev align validate
```

**Bootstrapping**:
```bash
specdev align status # "No version found"
specdev align prompts --mode bootstrap --output devspec_prompts/
# ... run prompts ...
specdev align validate
```
