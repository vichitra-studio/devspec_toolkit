# specdev update

`specdev update <spec_dir> [options]`

Syncs a project to the current toolkit version. This is the primary command to run after bumping the `devspec_toolkit` submodule.

## What it does

| Situation | Action |
|---|---|
| `spec/specdev_version` already matches toolkit version | Prints "Already at vX.Y.Z" and exits 0 |
| Versions differ, no schema changes | Refreshes deps via `uv pip install`, re-stamps `spec/specdev_version`, exits 0 |
| Versions differ, schema changes required | Refreshes deps via `uv pip install`, prints `specdev align` instructions, exits 1 |

The split between **re-stamp** and **migrate** follows this rule: only structural schema changes (`steps_missing`, `steps_needs_update`, `steps_needs_rename`, `paradigm_shifts`) require migration. User-extension steps (`steps_unknown`, `steps_extension`) never block a re-stamp.

## Usage

```bash
# Submodule deployment (standard)
specdev update spec --repo-root ./devspec_toolkit

# Dry-run — preview without writing
specdev update spec --repo-root ./devspec_toolkit --dry-run

# JSON output (for CI / scripting)
specdev update spec --repo-root ./devspec_toolkit --json
```

## Options

| Flag | Default | Description |
|---|---|---|
| `spec_dir` | (required) | Path to the project's `spec/` directory |
| `--repo-root` | `.` | Toolkit root (contains `tools/pyproject.toml`) |
| `--dry-run` | off | Report what would be done; do not write any files |
| `--json` | off | Emit structured JSON output |

## Dependency refresh

When versions differ, `specdev update` runs `uv pip install -e <toolkit_tools_dir>` before computing the diff. This ensures that any new dependencies added in the newer toolkit version are available.

**uv not installed**: The command prints installation instructions and proceeds with the re-stamp using the existing editable install. New dependencies may be missing until uv is installed and setup is re-run.

**Wrong Python version** (< 3.13): The command prints instructions to re-run `setup_devspec_env.sh` and proceeds without refreshing. See [setup_devspec_env.sh](../../../scripts/setup_devspec_env.sh) for details.

## Relationship to `specdev align`

`specdev update` is the **user-facing entry point**; `specdev align` is the **migration engine**. The two operations are intentionally separate:

- `specdev update` — always the first command to run after a toolkit bump
- `specdev align apply --auto` → (optionally) `align prompts` → `align validate` — run only when `specdev update` reports schema changes. `align validate` is the finalizer: it runs full post-migration validation and stamps `spec/specdev_version` with a migration-history entry. Do **not** finalize a migration by re-running `specdev update` — that only re-stamps after a weaker structural check and drops the audit trail.

`specdev update` calls `specdev align`-style logic internally to determine whether migration is needed, but it never runs the actual migration itself. This keeps the fast no-change path instant and avoids triggering unnecessary spec edits on non-breaking bumps.

## E608 remediation

When `spec-check` reports **E608 TOOLKIT_VERSION_MISMATCH**, run:

```bash
specdev update spec --repo-root ./devspec_toolkit
```

## See also

- [`specdev align`](./align.md) — full migration CLI
- [Migration workflow](../workflows/workflow_align.md) — step-by-step walkthrough
- [Error codes](../error-codes.md) — E608 details
