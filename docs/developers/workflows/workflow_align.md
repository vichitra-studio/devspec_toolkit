# Workflow: System Alignment & Migration

> **Audience**: Developers maintaining a DevSpec project  
> **Tooling**: `specdev align` CLI  
> **Goal**: Keep your project specs synchronized with the evolving DevSpec Toolkit

The DevSpec Toolkit evolves rapidly. New versions bring stricter schemas, improved prompts, and entirely new steps. The **Alignment Workflow** is the systematic process for upgrading your project to match the current toolkit version with zero data loss.

---

## Overview

Unlike traditional code migrations that might just patch syntax, DevSpec migration often involves **semantic upgrades**. For example, converting a prose document into a structured JSON file or adding entirely new required fields like "User Stories" to a roadmap.

The `specdev align` tool manages this complexity by:
1.  **Detecting** the exact gap between your project and the toolkit.
2.  **Planning** the necessary changes (renames, additions, transforms).
3.  **Automating** mechanical fixes (file renames, schema updates).
4.  **Assisting** with semantic changes via AI prompt generation.

---

## Prerequisites

Before starting an alignment or migration:

1.  **Clean Git State**: Ensure you have no uncommitted changes.
    ```bash
    git status
    # Should say "nothing to commit, working tree clean"
    ```
2.  **Latest Toolkit**: Update the submodule to the target version.
    ```bash
    git submodule update --remote devspec_toolkit
    ```
3.  **Virtual Env**: `devspec_env` active (run `source devspec_env/bin/activate` from the toolkit root).
    ```bash
    source devspec_env/bin/activate
    ```

---

## The Alignment Cycle

### 1. Check Status
First, determine if migration is actually needed.

```bash
specdev align status
```
**Output Scenarios**:
*   **"Aligned"**: Your `spec/specdev_version` matches the toolkit. No action needed.
*   **"Migration Required"**: Versions differ. Proceed to step 2.
*   **"Bootstrap"**: No version file found. Toolkit treats this as migrating from "empty" to "current".

### 2. Review the Gap (Diff)
See exactly what will change before touching anything.

```bash
specdev align diff
```
This reports:
*   **Missing Steps**: New files you need to create.
*   **Renames**: Steps that have been renumbered (e.g., `13_old` → `15_new`).
*   **Schema Drifts**: Fields that are now missing, extra, or have type mismatches.
*   **Paradigm Shifts**: Prose files (like `roadmap.md`) that need conversion to JSON.

### 3. Generate a Plan
Get a step-by-step checklist of operations.

```bash
specdev align plan
```
This separates changes into:
*   **Mechanical**: Safe to auto-apply (renames, schema headers).
*   **Semantic**: Requires AI assistance or manual input.

### 4. Apply Mechanical Fixes
Run the auto-fixer to handle the boring stuff.

```bash
specdev align apply --auto
```
> **Safety**: This automatically creates a hybrid backup (Git branch + local folder) before modifying any files.

**What this does**:
*   Renames files (e.g., `13_scaffold.json` → `15_scaffold.json`).
*   Updates `$schema` URLs in JSON files.
*   Adds an in-progress marker to `spec/specdev_version` (`migration_status: in_progress` + `target_version`), leaving `toolkit_version` at the **old** value.

> `apply --auto` does **not** finalize the version. It only marks the migration as in-progress; `toolkit_version` is advanced — and a `migration_history` entry recorded — solely by `align validate` (step 7), once the full migration is verified. The in-progress marker is cleared at that point.

### 5. Generate AI Prompts
For complex changes (like converting prose to JSON or inferring new fields), generate tailored AI prompts.

```bash
specdev align prompts --output migration_prompts/
```

This creates file-specific prompts (e.g., `migration_prompts/prompt_migrate_14_roadmap.md`) pre-filled with:
*   Your **original source data**.
*   The **target schema**.
*   Specific **transformation rules**.

### 6. Execute Semantic Migrations (Human + AI)
Iterate through the generated prompts:
1.  Open `migration_prompts/prompt_X.md`.
2.  Copy content to your AI assistant.
3.  Paste the AI's JSON output into the target spec file.
4.  Repeat for all generated prompts.

### 7. Validate
Confirm that your project is fully aligned and validity is restored.

```bash
specdev align validate
```
This checks:
*   Schema compliance for all files.
*   Trace integrity (links between steps).
*   Presence of `_migration_notes` (if any data couldn't be mapped).

If successful, it updates `spec/specdev_version` to the new toolkit version.

---

## Rollback

If something goes wrong (e.g., data corruption, completely broken specs), you can restore to the pre-migration state.

```bash
specdev align rollback
```

You will be presented with a list of available backups:
1.  **Git Backups**: Restores the `backup/pre-migration-vX.Y.Z` branch.
2.  **Folder Backups**: Restores from `spec/migration_backups/`.

---

## Troubleshooting

### "Schemaless file detected"
**Cause**: A JSON file exists but lacks the `$schema` key.
**Fix**: Add the `$schema` key manually or run `align apply --auto` if the file name matches a known step.

### "Paradigm Shift detected but source file missing"
**Cause**: The toolkit expects to migrate `roadmap.md` to `14_roadmap.json`, but can't find `roadmap.md`.
**Fix**: If you don't have the source file, you can skip this by manually creating an empty valid JSON file for the target step.

### "Trace integrity failed"
**Cause**: Migration renamed a step (e.g., `FR-01` in step 04), but downstream files still reference the old name.
**Fix**: Run `specdev align prompts` again—it generates specific "fix reference" prompts for broken links.

---

## FAQ

**Q: Can I skip versions (e.g., v0.1 to v0.5)?**
A: Yes. The `align` tool compares your current state directly to the target state. It does not run a chain of sequential scripts. It calculates the net difference and plans accordingly.

**Q: What happens to data that doesn't fit the new schema?**
A: We follow a **Lossless Migration** philosophy. Any data that cannot be mapped to a valid field is moved to a special `_migration_notes` object within the JSON file, or a sidecar `_migration_notes.md` file. It is never silently deleted.

**Q: Do I need to be in a Git repo?**
A: It is highly recommended, but `align apply` works without Git by using folder-based backups in `spec/migration_backups/`.
