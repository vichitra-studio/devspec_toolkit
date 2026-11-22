# specdev update

`specdev update <spec_dir> [options]`

Syncs a project to the current toolkit version and installs the toolkit's files into the host. This is the primary command to run after bumping the `devspec_toolkit` submodule, and the command `init` runs to install everything a host gets. What it installs, piece by piece, is in [host_setup.md](../host_setup.md).

## What it does

First the host install (below), then the version logic:

| Situation | Action |
|---|---|
| `spec/specdev_version` already matches toolkit version | Prints "Already at toolkit vX.Y.Z. Nothing to do." and exits 0 |
| Versions differ, no migration needed | Refreshes deps via `uv pip install`, re-stamps `spec/specdev_version`, exits 0 |
| Versions differ, a migration is needed | Refreshes deps via `uv pip install`, leaves the stamp as it is, prints the commands of the migration in the order they run, exits 1 (status `needs_migration`) |
| The stamp says `migration_status: in_progress` | Re-stamps nothing, prints that a migration is in progress and names `align triage` and `align validate`; exit 0 when the stamp's version equals the toolkit's, 1 when it differs (status `migration_in_progress`) |

The host install runs in every row, so a host that needs a migration is installed too (`--no-install` skips it). With `--install-only` only the install runs: no version check, no stamp.

A migration is needed when **any one** of three things holds: a migration script is registered for a version above the host's (`align apply --auto` would run it); the changelog entries between the host's version and the toolkit's hold a `script` or `kind: mechanical`; or the toolkit's changelog lists its releases and the host's version is not one of them. Beyond that, only structural schema changes (`steps_missing`, `steps_needs_update`, `steps_needs_rename`, `paradigm_shifts`) are reported as a reason to run the `align` flow. User-extension steps (`steps_unknown`, `steps_extension`) never block a re-stamp, and a spec with no `specdev_version` is re-stamped as before.

On a host that needs a migration, the text printed is the seven commands of the 1.1.1 to 1.2.0 migration, each with its purpose: `update --no-install --dry-run` (check again, writing nothing), `align apply --auto --dry-run` (review), `align apply --auto` (run it; it writes under `spec/` only, git is the undo), `git add spec && git commit --no-verify` (commit it; the old hooks still name retired commands), `update --adopt` (install the host files for the new version), `align triage` (the pass) and `align validate` (finish: clears `migration_status` when `spec-check --merge` is clean). The procedure is in [Migrating a 1.1.1 host to 1.2.0](../workflows/workflow_migrate_1_2_0.md).

## Usage

```bash
# Submodule deployment (standard), from the host root
specdev update spec --repo-root ./devspec_toolkit --git-root .

# Dry-run — preview without writing or starting any command
specdev update spec --repo-root ./devspec_toolkit --git-root . --dry-run

# Install or refresh the host files only (what `init` runs)
specdev update spec --repo-root ./devspec_toolkit --git-root . --install-only

# Version check and stamp only
specdev update spec --repo-root ./devspec_toolkit --no-install

# Take over what is only reported as drift / replace stale skill and agent links
specdev update spec --repo-root ./devspec_toolkit --git-root . --adopt --force-claude

# JSON output (for CI / scripting): the envelope has a `host_install` key
specdev update spec --repo-root ./devspec_toolkit --git-root . --json
```

## Options

| Flag | Default | Description |
|---|---|---|
| `spec_dir` | (required) | Path to the project's `spec/` directory |
| `--repo-root` | `.` | Toolkit root (contains `tools/pyproject.toml`) |
| `--git-root` | the git top folder of `spec_dir` | The host root to install into. Without a git repository around `spec_dir` and without this flag every piece is refused (W931) |
| `--install-only` | off | Install the host files; skip the version check and the stamp. Exclusive with `--no-install` (usage error, exit 2) |
| `--no-install` | off | Install nothing; check and stamp the version only. `--adopt` or `--force-claude` with it is accepted and does nothing |
| `--adopt` | off | Rewrite what `update` only reports as drift: hand-written toolkit hooks in `.pre-commit-config.yaml` (replaced by one marked block) and an edited `tools/run_specdev.sh` or `tools/ensure_venv.py`. A workflow of the installer's name that lacks the managed header is never touched |
| `--force-claude` | off | Replace a stale link in `.claude/skills/` or `.claude/agents/`; never a real file or folder |
| `--dry-run` | off | Report what would be done; do not write any files or start any command |
| `--json` | off | Emit structured JSON output |

`update` takes no `--spec-root`.

## Host install

`update` runs seven pieces in this order and prints one line for each, `pre-commit`, `merge-driver`, `workflows`, `wrappers`, `claude-links`, `ask-rules` and `gitignore`:

```
Host install:
  pre-commit: created (written with the toolkit hooks between markers)
  merge-driver: created (merge driver 'specdev-trace-lock' set in the clone's git config)
  workflows: created (written from the template)
  wrappers: created (tools/run_specdev.sh: created; tools/ensure_venv.py: created)
  claude-links: created (17 linked)
  ask-rules: created (10 ask rule(s) added to .claude/settings.local.json)
  gitignore: created ('.specdev/' added to .gitignore)
```

The status of a piece is `created`, `refreshed` (it rewrote what it owns), `current` (nothing to write), `drift` (the host has something at that place that is not what the piece would write: it is reported with W930 and left as it is until `--adopt` or `--force-claude` says otherwise), `refused` (W931: the piece could not run, the others went on) or `would_install` (`--dry-run`). A second run prints `current (up to date)` for every piece and changes no byte. The warnings never change the exit code and are never promoted; W932 (a retired command in the host's own workflow or hook file) and W935 (no `setup_command` declared) are printed beside them and never rewrite anything.

Per piece, what is written and where, what is per clone and not committed, and what `drift` means for it: [host_setup.md](../host_setup.md). Short form: the merge driver (the clone's git config and `.git/info/attributes`) and the ask rules (`.claude/settings.local.json`) are per clone, so run `update` once in every clone; everything else is a file to commit, and it belongs to the code tree, so commit it before `specdev verify run`. A host that tracks `.claude/settings.local.json` sees the file as modified after `update` has added the ask rules (the line the installer adds to `.git/info/exclude` has no effect on a tracked file): commit the change or restore the file, as you decide.

## Dependency refresh

When versions differ, `specdev update` runs `uv pip install -e <toolkit_tools_dir>` before computing the diff. This ensures that any new dependencies added in the newer toolkit version are available.

**uv not installed**: The command prints installation instructions and proceeds with the re-stamp using the existing editable install. New dependencies may be missing until uv is installed and setup is re-run.

**Wrong Python version** (< 3.13): The command prints instructions to re-run `setup_devspec_env.sh` and proceeds without refreshing. See [setup_devspec_env.sh](../../../scripts/setup_devspec_env.sh) for details.

## Relationship to `specdev align`

`specdev update` is the **user-facing entry point**; `specdev align` is the **migration engine**. The two operations are intentionally separate:

- `specdev update` — always the first command to run after a toolkit bump
- `specdev align apply --auto` → the judgement pass (`align triage`, `align propose`) → `align validate` — run only when `specdev update` says a migration is needed. `align apply --auto` stamps the new version with `migration_status: in_progress` and a migration-history entry; `align validate` clears the status once `spec-check --merge` is clean. Do **not** finish a migration by re-running `specdev update`: on a spec in progress it re-stamps nothing.

`specdev update` reads the migration scripts and the changelog to determine whether a migration is needed, but it never runs the migration itself. This keeps the fast no-change path instant and avoids triggering unnecessary spec edits on non-breaking bumps.

## E608 remediation

When `spec-check` reports **E608 TOOLKIT_VERSION_MISMATCH**, run:

```bash
specdev update spec --repo-root ./devspec_toolkit --git-root .
```

## See also

- [`specdev align`](./align.md) — full migration CLI
- [Migration workflow](../workflows/workflow_align.md) — step-by-step walkthrough
- [Error codes](../error-codes.md) — E608 details
