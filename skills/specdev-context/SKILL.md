---
name: specdev-context
description: >
  Load context for a pipeline step. Required before any spec-related work: authoring,
  reviewing, analysing, debugging, or answering questions about spec/*.json or pipeline steps.
  NEVER read spec/*.json files directly with the Read tool — use this skill instead.
  Trigger on: any mention of a step number, "what does step NN need", "look at step NN",
  "work on step NN", "/specdev-context NN", or any task involving spec files or pipeline steps.
---

# /specdev-context — Step Context Loader

**Never read `spec/*.json` files directly.** This skill is the single entry point for all
spec reads. For any work involving a pipeline step — authoring, reviewing, fixing, debugging,
or answering questions — load context here first.

For re-reads during a review-refine cycle, re-run with `--scope <entry-id>` to get a fresh
scoped view of the modified entry. Do not inspect fields directly.

## Input

```
/specdev-context <NN> [--scope <entry-id>] [--full]
```

- `<NN>`: Step ID (e.g. `04`, `02a`, `16b`)
- `--scope <entry-id>`: Restrict to IDs reachable from this entry via the trace graph.
  Use during review-refine cycles to reload a specific entry after editing it.
  The same `<entry-id>` value is used as `--entry` in Steps 2 and 3.
- `--full`: Bypass scope filtering — include all spec objects for this step.

## Prerequisites

Run from the host repo root. The toolkit must be at `./devspec_toolkit/`.
Replace `<spec_dir>` with the actual spec directory path (typically `spec/` for a product repo,
or `devspec_toolkit/spec/` when working on the toolkit itself).

```
./tools/run_specdev.sh <subcommand> --repo-root ./devspec_toolkit
```

**Seed freshness (steps 00–02a only)**: If authoring or reviewing a step that reads seed
documents (00–02a), verify seeds are current before loading context:

```bash
./tools/run_specdev.sh context freshness \
  <spec_dir> --repo-root ./devspec_toolkit
```

A `"stale": true` result on any seed means upstream content has changed since the spec was
last written. Stale seeds produce misleading context — re-index the affected seed before
proceeding. Steps 05 and above have no seed dependency; skip this check.

## Execution

Run each command in sequence. Stop and report if any command exits non-zero.

### Step 1 — Structure

```bash
./tools/run_specdev.sh context structure \
  <spec_dir> --step <NN> --repo-root ./devspec_toolkit
```

### Step 2 — Scope (only if --scope provided)

```bash
./tools/run_specdev.sh context scope \
  <spec_dir> --entry <entry-id> --repo-root ./devspec_toolkit
```

If the output contains a `scope_warning`, surface it and run Step 3 with `--full` instead
of `--entry`. Skip entirely when `--scope` is not provided.

### Step 3 — Extract

```bash
./tools/run_specdev.sh context extract \
  <spec_dir> --step <NN> [--entry <entry-id>] [--full] \
  --repo-root ./devspec_toolkit
```

### Step 4 — Canon

```bash
./tools/run_specdev.sh context canon \
  --step <NN> --repo-root ./devspec_toolkit
```

For **submodule / product-repo** deployments where `spec/canon/` holds project-specific
terms (e.g. after running `canon-accept`), add `--spec-root` so project-tier entries are
merged alongside toolkit-core entries:

```bash
./tools/run_specdev.sh context canon \
  --step <NN> --repo-root ./devspec_toolkit --spec-root ./spec
```

Full definitions are in `devspec_toolkit/canon/kinds/<kind>.json`. Do not read them
unless a specific term lookup is requested.

### Step 5 — Prompt contract

Read the file matching:

```
devspec_toolkit/prompts/prompt_<NN>_*.md
```

## Output

After all steps complete, output only one of:

```
Context loaded for step <NN>.                       # no --scope or --full
Context loaded for step <NN> [scope: <entry-id>].   # --scope used
Context loaded for step <NN> [scope: full].         # --full used
```

All loaded data is in working context. Do not echo command outputs unless the user
asks for something specific.

## Reading the step's own output artifact

These commands are for **post-authoring verification only** — checking specific fields of
the artifact a step just produced. They do NOT load upstream context.

**For upstream context (what a step needs as inputs), always run the 5-step execution above —
never substitute `json read` for `/specdev-context`.**

```bash
# Read a single targeted field or expression — supports streaming filters
./tools/run_specdev.sh json read <file> '<jq-filter>'

# Examples:
./tools/run_specdev.sh json read spec/03_glossary.json '.terms | length'
./tools/run_specdev.sh json read spec/03_glossary.json '.terms[2]'
./tools/run_specdev.sh json read spec/03_glossary.json '.terms[] | select(.domain == "analytics")'

# Read multiple fields in one pass — returns a keyed JSON object
# RESTRICTION: each filter must return a single value; streaming filters (.arr[]) are rejected here
./tools/run_specdev.sh json read-multi <file> '<filter1>' '<filter2>' ...
./tools/run_specdev.sh json read-multi spec/03_glossary.json '.id' '.version' '.terms | length'

# Tree overview — structure only, no field content
./tools/run_specdev.sh json structure <file>
```

Use `json read` for streaming filters (`.arr[] | select(...)`). Use `json read-multi` when
spot-checking several independent single-value fields after writing an artifact.

## Snapshot and diff

Save a checkpoint of a step artifact and diff it against the current state — without requiring
a git commit. Useful during iterative authoring or review cycles.

```bash
# Save current state as a workspace snapshot
./tools/run_specdev.sh context snapshot <spec_dir> --step <NN> --repo-root ./devspec_toolkit

# Diff current artifact against the saved snapshot
./tools/run_specdev.sh context diff <spec_dir> --step <NN> --repo-root ./devspec_toolkit
```

Snapshots are stored in `.specdev/snapshots/` at the git root. Add `.specdev/` to `.gitignore`
if you do not want snapshots committed.

## Writing and editing artifacts

Check whether `<spec_dir>/<NN>_*.json` exists before touching it.

**File does not exist — full write**

Write the complete JSON in one operation. The schema validator requires a complete document.

**File exists — targeted edits only**

| Situation | Command |
|-----------|---------|
| Replace a value | `Edit` tool |
| Append to an array or merge into an object | `./tools/run_specdev.sh json insert <file> <jq-path> <value>` |
| Update by entry ID | `./tools/run_specdev.sh json patch <file> <jq-path> <value>` |
| Delete a field or entry | `./tools/run_specdev.sh json delete <file> <jq-path>` |

Prefer `Edit` for simple replacements. Use `./tools/run_specdev.sh json` when the edit requires
array manipulation or targeting an entry by ID within a nested array.

## Error handling

- **Command exits non-zero**: show stderr and stop.
- **Step not found / schema not found**: check `--repo-root ./devspec_toolkit`; confirm
  the step ID exists in `devspec_toolkit/tools/step_order.json`.
- **No spec file for an upstream step**: note missing steps and proceed with available context.
- **`scope_warning` in scope output**: surface the warning, fall back to `--full` extraction.
