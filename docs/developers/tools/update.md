# specdev update

`specdev update <spec_dir> [options]`

Syncs a project to the current toolkit version and installs the toolkit's files into the host. This is the primary command to run after bumping the `devspec_toolkit` submodule, and the command `init` runs to install everything a host gets. What it installs, piece by piece, is in [host_setup.md](../host_setup.md).

## What it does

First the host install (below), then the version logic:

| Situation | Action |
|---|---|
| `spec/specdev_version` already matches toolkit version | Prints "Already at vX.Y.Z. Nothing to do." and exits 0 |
| Versions differ, no schema changes | Refreshes deps via `uv pip install`, re-stamps `spec/specdev_version`, exits 0 |
| Versions differ, schema changes required | Refreshes deps via `uv pip install`, prints `specdev align` instructions, exits 1 |

The host install runs in all three rows, so a host that needs a migration is installed too (`--no-install` skips it). With `--install-only` only the install runs: no version check, no stamp.

The split between **re-stamp** and **migrate** follows this rule: only structural schema changes (`steps_missing`, `steps_needs_update`, `steps_needs_rename`, `paradigm_shifts`) require migration. User-extension steps (`steps_unknown`, `steps_extension`) never block a re-stamp.

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

Per piece, what is written and where, what is per clone and not committed, and what `drift` means for it: [host_setup.md](../host_setup.md). Short form: the merge driver (the clone's git config and `.git/info/attributes`) and the ask rules (`.claude/settings.local.json`) are per clone, so run `update` once in every clone; everything else is a file to commit, and it belongs to the code tree, so commit it before `specdev verify run`.

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
specdev update spec --repo-root ./devspec_toolkit --git-root .
```

## See also

- [`specdev align`](./align.md) — full migration CLI
- [Migration workflow](../workflows/workflow_align.md) — step-by-step walkthrough
- [Error codes](../error-codes.md) — E608 details
