# Workflow: System Alignment & Migration

> **Audience**: Developers maintaining a DevSpec project  
> **Tooling**: `specdev update` and the `specdev align` CLI  
> **Goal**: Keep your project specs synchronized with the evolving DevSpec Toolkit

The DevSpec Toolkit evolves rapidly. New versions bring stricter schemas, improved prompts and new steps. The alignment workflow is the process for upgrading your project's `spec/` to the toolkit version you run. For a 1.1.1 host moving to 1.2.0 the full procedure, with the commands as they print, is **[Migrating a 1.1.1 host to 1.2.0](./workflow_migrate_1_2_0.md)**; this page is the general shape.

---

## Overview

A migration has two stages:

1.  **The mechanical stage**, `specdev align apply --auto`: scripts of the release, run in phases on a scratch copy of `spec/`, rewrite what has one right answer (ids, link fields, removed fields, the trace lock, the close of finished milestones) and write the list of decisions they could not take. A dry run shows the diff first. The command writes under `spec/` only, commits nothing and makes no backup branch or folder: git is the undo.
2.  **The judgement pass**, by a person or an agent whose work a person reviews: `specdev align triage` lists the decisions, `specdev align propose` offers candidates for some of them, the edits are made with the id-keyed commands (`specdev json patch --id`), links are accepted with `specdev attest`, and `specdev spec-check spec --step NN` says when a step is clear. `specdev align validate` finishes it.

---

## Prerequisites

1.  **A git work tree with a committed `spec/`**: the run is refused (`E880`) on a folder that is not a git work tree and on uncommitted changes in `spec/` unless you pass `--allow-dirty`. Work on a branch off the default branch: the final check measures the branch against it.
2.  **The target toolkit**: update the submodule to the version you migrate to.
    ```bash
    git submodule update --remote devspec_toolkit
    ```
3.  **Virtual Env**: `devspec_env` active.
    ```bash
    source devspec_env/bin/activate
    ```

---

## The Alignment Cycle

### 1. Ask whether a migration is needed
```bash
specdev update spec --repo-root ./devspec_toolkit --git-root . --no-install --dry-run
```
*   Same version: `Already at toolkit vX.Y.Z. Nothing to do.`
*   A version that needs no data migration: the spec would be re-stamped (`would_update`).
*   A version that needs one: `update` does not re-stamp. It exits 1 and prints the commands to run, in order (see below).

### 2. Mechanical stage
```bash
specdev align apply spec --auto --dry-run --repo-root ./devspec_toolkit --git-root .
specdev align apply spec --auto --repo-root ./devspec_toolkit --git-root .
```
The second command prints one line per script, the totals, and `review: git diff --stat spec` / `undo:   git checkout -- spec && git clean -fd spec  (the second removes the files the run created)`. It stamps `spec/specdev_version` with the new `toolkit_version` and `migration_status: in_progress`, with a `migration_history` entry. A rerun changes no byte.

### 3. Commit it
```bash
git add spec && git commit --no-verify -m "Migrate the spec to toolkit vX.Y.Z"
specdev update spec --repo-root ./devspec_toolkit --git-root . --adopt
```
`--no-verify` because the host's old hooks may still name commands the new version retired. `update --adopt` installs the host files of the new version (hooks, merge driver, workflows, wrappers, ask rules); with the stamp in progress it re-stamps nothing.

### 4. The judgement pass
```bash
specdev align triage spec --repo-root ./devspec_toolkit --git-root .
specdev align propose spec --kind refines --repo-root ./devspec_toolkit --git-root .
```
Work the steps in waterfall order. For each step, read what is asked (`align triage --step NN`), open the step's template by hand (`prompts/migration/template_<name>.md`), make the edits, close the items (`align triage --resolve <id> --note "..."`), accept the links (`specdev attest <node> --yes`) and gate the step (`specdev spec-check spec --step NN`). `specdev align prompts` renders prompts only for structural schema differences, which on a 1.1.1 host for 1.2.0 is one file that no longer exists, so it is not part of this pass. The guide has the details.

### 5. Validate
```bash
specdev align validate spec --repo-root ./devspec_toolkit --git-root . --base-ref <default-branch>
```
It runs `spec-check --merge`; when that has no error it deletes the migration's own files (`spec/extras/migration/`), clears `migration_status` and refreshes `last_migration`. With errors it prints them and changes nothing.

---

## Undoing a migration

Before you commit: `git checkout -- spec && git clean -fd spec` (the run creates files: the capture, the worklist, the lock and, on a host with a canon kind `inv`, `canon/kinds/invariant.json`; a rerun after `checkout` alone stops with `E881`). After the migration commit: revert that commit. The migration of 1.2.0 makes no backup branch and no backup folder; `specdev align rollback` only restores a backup folder that an earlier toolkit made (under `spec/migration_backups/`).

---

## Troubleshooting

### `E880` on `align apply`
The run was refused before it wrote anything: not a git work tree, no or an unusable `toolkit_version` stamp, a version the migration cannot start from, or uncommitted changes. `specdev guide E880`.

### `E881` on `align apply`
A script broke a rule of the runner; nothing was written. `specdev guide E881`.

### `E882` after the migration
A link the migration wrote has not been accepted yet. `specdev attest <node> --yes`, node by node. `specdev guide E882`.

### `E700` to `E704` while editing
A link names an id no node has, a node of the wrong kind or step, forms a cycle, or two nodes define one id. `specdev guide E700` (and the next four codes).

### `align validate` says the migration has not been run
The spec is stamped with a version below the toolkit's. Run `align apply --auto` first.

---

## FAQ

**Q: Can I skip versions (e.g., 1.0.0 to 1.2.0)?**
A: Yes, from 1.0.0 on. The runner chains the scripts of every release between the host's version and the toolkit's, in order, and refuses (`E880`) a host older than 1.0.0 or at a version the toolkit's changelog does not list.

**Q: What happens to data that no longer has a field?**
A: The scripts copy what a later script or the pass still needs into `spec/extras/migration/capture.json` before they remove it, with the commit it came from; the rest is in git. A decision a script cannot take is a worklist item, never a guess. `align triage --legacy NN` prints a step's files as they were.

**Q: Do I need to be in a git repo?**
A: Yes for `align apply`, `propose`, `triage`, `bind-legacy` and `validate`: the migration is reviewed with `git diff` and undone with `git checkout`.
