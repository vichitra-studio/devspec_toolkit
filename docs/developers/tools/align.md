# specdev align - Toolkit Alignment CLI

## Synopsis
`specdev align <action> <spec_dir> [options]`

## Overview
`align` moves a host's `spec/` directory from the toolkit version it was written for to the version of the toolkit you run. For a 1.1.1 host moving to 1.2.0 it is a two-stage migration: a mechanical stage that rewrites the spec in one command (`apply --auto`), and a judgement pass that a person does with a list of decisions (`triage`, `propose`, `bind-legacy`) and finishes with `validate`. The step-by-step guide is [Migrating a 1.1.1 host to 1.2.0](../workflows/workflow_migrate_1_2_0.md); the older read-only actions are described under [Older actions](#older-actions).

Flags every action accepts: `--repo-root` (the toolkit), `--git-root` (the host's git work tree; default: the folder that holds `spec_dir`) and `--json`. `align` takes no `--spec-root`: the positional `spec_dir` is the spec folder. A git work tree is needed by `apply`, `propose`, `triage`, `bind-legacy` and `validate`.

## The migration

### apply
The mechanical stage.

```bash
specdev align apply spec --auto --dry-run --repo-root ./devspec_toolkit --git-root .
specdev align apply spec --auto --repo-root ./devspec_toolkit --git-root .
```

Runs the migration scripts of the release, in phases, on a scratch copy of `spec/`; when every script passed, it installs the changed files into `spec/`. The scripts capture what they remove, mint ids, convert the legacy reference fields into link fields, remove the fields the release dropped, close the milestones that 1.1.1 called done, write the trace lock with `baseline` markers, and list the decisions they cannot take in `spec/extras/migration/worklist.json`. The runner stamps `spec/specdev_version` with the new version and `migration_status: in_progress`.

**Options**:
- `--auto`: required for the mechanical stage.
- `--dry-run`: print the diff of every file the run would change, the edits and worklist items per script, and the totals; nothing is written. Allowed on a dirty `spec/`.
- `--allow-dirty`: do not refuse a `spec/` with uncommitted changes. A run that resumes (the stamp says `in_progress`) needs it for no reason: it is allowed.
- `--json`: the report as a document (`status`, `dry_run`, `edits_by_script`, `worklist_items`, `residue`, `errors`).
- `--yes`: accepted and ignored; `apply` never asks.

**What it does not do**: it writes under `spec/` only; it makes no commit, no branch and no backup; it never rewrites a host file outside `spec/` (a retired command in your hooks or workflows is reported as a worklist item and as `W932`, and you edit it). The review is `git diff --stat spec`; the undo is `git checkout -- spec && git clean -fd spec` (the run creates files, and a rerun after `checkout` alone stops with `E881`).

**Idempotent**: a second run says `nothing to do` for every script and changes no byte.

**Refusals**: `E880` (not a git work tree; no or an unusable version stamp; a spec older than 1.0.0, newer than the toolkit or at a version the changelog does not list; uncommitted changes in `spec/` without `--allow-dirty`) and `E881` (a script raised, broke an invariant, was not idempotent, wrote outside `spec/`, or a closed plan no longer matches its close hash). Both leave the host as it was. On a spec already at the toolkit's version it prints that there is nothing to do and stamps nothing.

### triage
The list of decisions the scripts left.

```bash
specdev align triage spec --repo-root ./devspec_toolkit --git-root . [--step NN] [--audience operator|agent] [--json]
specdev align triage spec --resolve <item id> --note "<what was decided>" --repo-root ./devspec_toolkit --git-root .
specdev align triage spec --legacy NN --repo-root ./devspec_toolkit --git-root .
```

Lists the open items of `spec/extras/migration/worklist.json`: `operator` items (a person decides) before `agent` items (an agent proposes, a person confirms), blocking ones first, then by step and kind. Each shows its id, step, kind, the node or file it is about, the evidence and, where there is one, a proposal. `--resolve` closes an item with a note and changes only the worklist. `--legacy NN` prints the files of step NN as they were before the migration (`git show <commit>:<path>`, with the commit the capture names; a deleted file is shown too) and writes nothing. Exit 0 whatever is open.

### propose
Proposals for the judgement pass.

```bash
specdev align propose spec --kind refines|prose-ids|bindings [--dry-run] --repo-root ./devspec_toolkit --git-root .
```

- `refines`: for each task criterion of step 14, the node it most likely refines, with a class (`auto-eligible`, `needs-judgement`, `none`) and a text-similarity score. A score is a candidate, not a decision.
- `prose-ids`: for the text of each node that names an id, which ids resolve to a node and could become links.
- `bindings`: for each legacy fixture, the command the 1.1.1 plans and CI workflows recorded for it, as a `specdev verify bind` line, with a class (`certain`, `needs-judgement`, `manual`).

Each proposal becomes a worklist item; a rerun adds none twice. `--dry-run` prints the proposals and adds nothing. Proposals are never applied by this command. A folder that has not been through `apply --auto` (no `extras/migration/capture.json`) is refused in one line.

### bind-legacy
The legacy binding pass: fixtures need a binding or an attestation before the first release.

```bash
specdev align bind-legacy spec [--yes] --repo-root ./devspec_toolkit --git-root .
specdev align bind-legacy spec --summary --repo-root ./devspec_toolkit --git-root .
```

Prints the `specdev verify bind` line of each `certain` group, writes the lines (through the writer of `verify bind`) after a prompt or with `--yes`, and closes the worklist items it settled. A line `verify bind` refuses (`E330` to `E334`, `E767`) is printed as refused, with the same text. `--summary` prints the counts only, ending with the number of fixtures still without a binding or attestation, which must be 0 before the first release. A binding it writes proves nothing until `specdev verify run --stage <its stage>` has run it and the guard matched the real output.

### validate
Finishes the migration.

```bash
specdev align validate spec --repo-root ./devspec_toolkit --git-root . [--base-ref REF] [--keep-worklist]
```

In order: the stamp must record the toolkit's own version (a spec stamped below it has not been migrated: refused); `spec-check --merge` against `--base-ref` (default: the merge base with the default branch; `E900` when there is none) must report no error, and when it does the command prints them and changes nothing. Then, only then, it deletes `capture.json` and `worklist.json` when no worklist item is open (items still open are counted as information and do not refuse; `--keep-worklist` keeps the files in any case), clears `migration_status` and refreshes `last_migration`. A second run changes nothing. Merge mode is the gate; the per-step gate of the pass is `specdev spec-check spec --step NN`.

## Older actions

`status`, `diff`, `plan`, `prompts` and `rollback` come from the toolkit's earlier migration system. They still run, and on a 1.1.1 host they say almost nothing about this release; do not use them to plan it.

- `status`: the host's version, the toolkit's, the delta, a recommendation. On a 1.1.1 host it prints that a migration is recommended and nothing more.
- `diff` and `plan`: compare the top level of each step schema (its own `required`, `properties` and `additionalProperties`) between the two versions. The 1.2.0 changes are nested, so every step reads `OK`.
- `prompts [--output DIR] [--mode upgrade|bootstrap]`: renders one prompt for each structural difference, choosing the template of the step from `prompts/migration/`. On a 1.1.1 host for 1.2.0 the only difference is the removed step 13a file, whose prompt is made from the charter template. The per-step templates are therefore opened by hand: `prompts/migration/template_<name>.md` (the table is in the guide). Each template says what the step's nodes look like in 1.2.0, the kinds of worklist item of that step with the command that answers each, and how an item is closed.
- `rollback [--backup-dir NAME] [--yes]`: restores `spec/` from a backup folder under `spec/migration_backups/` that an earlier toolkit made. The 1.2.0 migration makes no backup (git is the undo), so on a host that has none it prints `No backups found in spec/migration_backups/`.

## Examples

See [Migrating a 1.1.1 host to 1.2.0](../workflows/workflow_migrate_1_2_0.md) for the whole procedure, and the [Alignment Workflow Guide](../workflows/workflow_align.md) for the version-to-version flow in general.
