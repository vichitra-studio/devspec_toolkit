---
name: specdev-context
description: >
  Load context for a pipeline step. Required before any spec-related work: authoring,
  reviewing, analysing, debugging, or answering questions about spec/*.json or pipeline steps.
  NEVER read spec/*.json files directly with the Read tool — use this skill instead.
  Trigger on: any mention of a step number, "what does step NN need", "look at step NN",
  "work on step NN", "/specdev-context NN", or any task involving spec files or pipeline steps.
  Also the canonical LLM-agent entry point for the specdev llm offload pipeline; see the Invocation modes section below.
---

# /specdev-context — Step Context Loader

**Never read `spec/*.json` files directly, and never read tool output dump files.** This skill
is the single entry point for all spec reads. For any work involving a pipeline step —
authoring, reviewing, fixing, debugging, or answering questions — load context here first.
For targeted follow-up queries after context is loaded, use `json read` on the source artifact,
not on saved terminal output. See **Prohibited patterns** below.

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

## Prohibited patterns

The following are **hard bans** — never do these regardless of context:

| Banned action | Why | Use instead |
|---|---|---|
| `Read` on `spec/*.json` | Bypasses pipeline, no query filtering | `context extract` + `json read` |
| `Read` on tool output dump files (`*.txt`, `.specdev/`, temp paths) | Reads stale, unfiltered blobs | `json read <source-file> '<jq-filter>'` on the actual artifact |
| `cat` / `Bash` reads of spec or canon files | Same as above | `json read` |
| `Read` on `devspec_toolkit/canon/kinds/*.json` | Canon is loaded via `context canon` | `context canon` output |
| Re-running `context extract` to re-read already-loaded context | Wastes tokens | Use `json read` for targeted follow-up queries |

**If a command output is truncated** (saved to a file because it exceeded terminal limits):
- Do **not** `Read` the saved dump file.
- Instead run targeted `json read` queries directly on the upstream source artifact:
  ```bash
  # Example: extract output was large — query what you need directly
  ./tools/run_specdev.sh json read spec/01_capabilities.json '.capabilities[] | {capability_id, scope, name}'
  ./tools/run_specdev.sh json read spec/00_charter.json '.in_scope'
  ```
- Only call `context extract --full` again if the specific field you need is not accessible via `json read`.

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

## Upstream drift

When a checklist assertion would diverge from the cited spec entry — or when the same canonical id resolves to different text in different source files — do not silently encode the code-side value. Log it as a `plan.ambiguities[]` entry (16a) or `execution.emergent_ambiguities[]` (16b+) and let the upstream-revision cycle reconcile it. Schema and field requirements live in `prompt_16a_impl_planner.md` and the step-16 schema.

Before minting a new entry, check sibling plans in `spec/impl_context/` — reuse the id or cross-reference if the drift is already logged.

Each entry's `impact[]` must include the upstream spec file path (e.g. `spec/04_fr_list.json:<id>`) so `upstream-backlog` can route it. For duplicate-id drift, include every definition site.

After authoring, verify routing:

```bash
./tools/run_specdev.sh upstream-backlog <spec_dir> \
  --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
```

Any entry from this plan landing in `Unclassified` means `impact[]` lacks a step-routable path.

## Error handling

- **Command exits non-zero**: show stderr and stop.
- **Step not found / schema not found**: check `--repo-root ./devspec_toolkit`; confirm
  the step ID exists in `devspec_toolkit/tools/step_order.json`.
- **No spec file for an upstream step**: note missing steps and proceed with available context.
- **`scope_warning` in scope output**: surface the warning, fall back to `--full` extraction.

---

## Invocation modes

> **Shell note for recipes below:** all `specdev` commands assume the venv is already active (via `source dev_env/bin/activate` or the host wrapper `./tools/run_specdev.sh`). The `source dev_env/bin/activate &&` prefix shown in earlier sections of this skill is equivalent.

`/specdev-context` serves two distinct use cases. Choose based on the caller:

| Mode | Caller | Invocation | Effect |
|---|---|---|---|
| Interactive drill-down | Human in Claude Code session | `/specdev-context <NN>` | Loads step context, prompts for action |
| LLM-agent entry point | Automated agent pipeline | `/specdev-context <NN> [--scope <entry-id>] [--full]` | Loads step context into working memory; agent next invokes `specdev json` or `specdev llm bundle` (Wave A). `edit`/`remediate` pending Wave C. |

When acting as an LLM agent downstream of this skill, the canonical next steps are:

1. **`specdev json read '<file>' '<jq>'`** — targeted read of a specific field (Wave A, shipping)
2. **`specdev json read '<pointer-response.json>' '.pointers' | specdev json resolve-pointers --spec-root ./spec --git-root .`** — expand pointer response into concrete values; note `resolve-pointers` reads a raw JSON array from stdin, so extract `.pointers` from the schema envelope first (Wave A, shipping)
3. **`specdev llm bundle --step <NN> --spec-root ./spec --repo-root ./devspec_toolkit --git-root .`** — assemble orientation bundle for a step (Wave A, shipping)
4. **`specdev llm edit`** — apply LLM edits from pointer response <!-- amended-in-wave-c --> <!-- TODO: remove marker and document flags when Wave C (specdev-llm-offload story) ships -->
5. **`specdev llm remediate`** — LLM-assisted remediation of spec-check errors <!-- amended-in-wave-c --> <!-- TODO: remove marker and document flags when Wave C (specdev-llm-offload story) ships -->

---

## Model-selection guidance

Match the model to the task's reasoning demand and token budget. These mappings are derived from §16.1 of the LLM offload protocol (`docs/agents/llm_protocol.md`), restructured for skill audience. For the authoritative task-role table see §16.1 directly.

| Task | Recommended model | Rationale |
|---|---|---|
| Inner loop (per-entry edits, pointer resolution) | `haiku-4-5` | Low latency, cheap; each call processes one entry |
| Outer loop (step-level bundle composition) | `haiku-4-5` | Aggregation is structural; heavy reasoning not required |
| Widen pass (cross-step ambiguity triage) | `sonnet-4-6` | Needs broader context window and reasoning depth |
| Manual investigation (interactive, human-in-loop) | `sonnet-4-6` | Human review session; cost less critical |
| Remediation from spec-check errors | `sonnet-4-6` | Error diagnosis benefits from stronger reasoning |

**Override rule:** If a step has >50 entries or references >3 upstream artifacts, escalate to `sonnet-4-6` for outer loop regardless of the table above.

---

## Composition recipes

Three end-to-end playbooks. Steps marked `<!-- amended-in-wave-c -->` depend on Wave C primitives that have not yet shipped; substitute a manual equivalent until then.

### Recipe A — Backlog → spec entries flow

Use when: an upstream-backlog item needs to be turned into a new spec entry.

```
1. /specdev-context <NN>                           # load step context
2. specdev json read spec/<NN>_*.json '<jq>'       # read relevant existing entries
3. specdev json read '<pointer-response.json>' '.pointers' | specdev json resolve-pointers --spec-root ./spec --git-root .
4. specdev json insert spec/<NN>_*.json '<array-path>' '<new-entry-json>'
5. source dev_env/bin/activate && specdev spec-check spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
```

### Recipe B — Edit with replay check

Use when: an LLM suggests an edit to an existing entry and you need to validate it doesn't break downstream.

```
1. /specdev-context <NN>
2. specdev json patch spec/<NN>_*.json '<jq-path>' '<new-value>'
3. source dev_env/bin/activate && specdev spec-check spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
4. # If errors: see Manual replay playbook below
```

<!-- amended-in-wave-c -->
<!-- TODO: replace step 2 with `specdev llm edit` (check flags at ship time) when Wave C (specdev-llm-offload story) ships -->

### Recipe C — Investigate then fix

Use when: spec-check reports an error and you need an LLM to suggest the fix.

```
1. source dev_env/bin/activate && specdev spec-check spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root . 2>&1 | tee /tmp/spec_errors.txt
2. /specdev-context <NN>   # load context for the failing step
3. # Review error output + step context, apply manual fix via specdev json patch/insert/delete
4. source dev_env/bin/activate && specdev spec-check spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
```

<!-- amended-in-wave-c -->
<!-- TODO: replace step 3 with `specdev llm remediate` (check flags at ship time) when Wave C (specdev-llm-offload story) ships -->

---

## Manual replay playbook

Use when: a spec-check run fails after an upstream edit and you need to replay forward from the changed step.

**When this matters:** Forward-replay silently no-ops if `--git-root` is omitted (known issue, see bug seq #4 in project `23ed365c-beef-4a93-9050-37ac382eacb3`). Always pass `--git-root .` when running spec-check from the host repo root.

### Drill-down recipe

1. Identify the first failing step from `specdev spec-check` output (lowest step number with errors).
2. Run `/specdev-context <NN>` for that step to load its schema, canon context, and upstream structure.
3. Apply the fix using `specdev json patch|insert|delete` (never direct file edits).
4. Re-run `specdev spec-check spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root .` — repeat from step 1 if new errors appear in later steps.

### Reasoning

- **Fix upstream first:** downstream failures are almost always symptoms of an upstream root cause; fixing downstream directly creates a forward-replay violation.
- **Use `specdev json` ops, not direct edits:** direct file edits skip schema awareness and can silently introduce structural errors.
- **Replay is forward-only:** you cannot patch step N by editing step N+1; the waterfall must flow forward.
- **`--git-root` is mandatory:** omitting it disables forward-replay diff tracking (see bug seq #4).
- **One fix per spec-check cycle:** fix the earliest error, validate, then proceed — batching fixes masks cascading root causes.

### Worked examples

**Example 1 — E110 in step 04 after glossary edit:**
```bash
# spec-check shows: E110 UNKNOWN_CANONICAL_ID cn:project:term:session-token (spec/04_fr_list.json)
# Root cause: term was renamed in spec/03_glossary.json but not updated in 04

/specdev-context 04                    # check what 04 expects from 03
# Locate the index of the stale canonical ref
specdev json read spec/04_fr_list.json '.functional_requirements | to_entries[] | select(.value.id == "fr-session-auth") | .key'
# Patch by index (substitute the index returned above for N and M)
specdev json patch spec/04_fr_list.json '.functional_requirements[N].canonical_refs_used[M].id' '"cn:project:term:auth-session"'
source dev_env/bin/activate && specdev spec-check spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
```

**Example 2 — E530 invented verb in step 12:**
```bash
# spec-check shows: E530 INVENTED_ENUM_OR_ID frobulate (spec/12_ci_gates.json)
# Fix: replace invented verb with an allowlisted one, or register command_ref

# Locate the job and step indices
specdev json read spec/12_ci_gates.json '.jobs | to_entries[] | select(.value.job_id == "lint-job") | .key'
specdev json read spec/12_ci_gates.json '.jobs[J].steps | to_entries[] | select(.value.id == "step-lint") | .key'
# Patch by index (substitute J and S from the reads above)
specdev json patch spec/12_ci_gates.json '.jobs[J].steps[S].command' '"pytest tests/integration/ -v"'
source dev_env/bin/activate && specdev spec-check spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
```

**Example 3 — E530 missing test file in step 16 impl_context:**
```bash
# spec-check shows: E530 LINKED_TEST_FILE_NOT_FOUND tests/integration/test_session_flow.py
# Fix: either create the file or update the linked_test_expectation to an existing path
# linked_test_expectation lives at plan.spec_alignment.checklist[N].linked_test_expectation

# Locate the checklist index with the stale path
specdev json read spec/impl_context/ms_phase1_plan.json '.plan.spec_alignment.checklist | to_entries[] | select(.value.linked_test_expectation | test("test_session_flow")) | .key'
# Patch by index (substitute N from the read above)
specdev json patch spec/impl_context/ms_phase1_plan.json '.plan.spec_alignment.checklist[N].linked_test_expectation' '"tests/integration/test_auth_flow.py"'
source dev_env/bin/activate && specdev spec-check spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
```

---

## Permission allow-list for LLM agents

When operating in agent mode, these are the only `specdev` commands that should be invoked automatically (without human confirmation):

| Command | Safe to auto-invoke | Notes |
|---|---|---|
| `specdev llm bundle` | Yes | Orientation assembly; ships Wave A |
| `specdev llm edit` | Yes (pending) | <!-- amended-in-wave-c --> <!-- TODO: document correct flags when Wave C (specdev-llm-offload story) ships; do not assume --model flag exists --> |
| `specdev llm remediate` | Yes (pending) | <!-- amended-in-wave-c --> <!-- TODO: document correct flags when Wave C (specdev-llm-offload story) ships; do not assume --model flag exists --> |
| `specdev json patch` | Yes | Targeted JSON edit; schema-validated before write |
| `specdev json insert` | Yes | Targeted JSON insert; schema-validated before write |
| `specdev json delete` | Yes | Targeted JSON delete |
| `specdev spec-check --json` | Yes | Read-only validation; `--json` for machine-parseable output |
| `specdev json resolve-pointers` | Yes | Read-only pointer expansion (pipe `.pointers` array, not full envelope) |
| `specdev json read` | Yes | Read-only |
| `specdev json read-multi` | Yes | Read-only |
| `specdev context snapshot` | Yes | Read-only workspace state snapshot |
| `specdev context diff` | Yes | Read-only workspace state diff |
| `specdev canon-accept` | **No** — human required | Writes to canon registry; irreversible without git revert |
| `specdev align apply` | **No** — human required | Bulk mechanical migration; review plan first |
| `git commit` | **No** — human required | Never auto-commit spec changes |
| `git push` | **No** — human required | Never auto-push |
