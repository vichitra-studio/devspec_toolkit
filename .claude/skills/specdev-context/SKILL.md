---
name: specdev-context
description: >
  Load context for a pipeline step — for orientation, read-only inspection, and answering
  questions about spec files or pipeline steps. Use its primitives to safely read spec files;
  never read spec/ directly with the Read tool.
  NOT for authoring a new step artifact (→ /specdev-step). NOT for reviewing or fixing an
  existing artifact (→ /specdev-review). NOT for trinity phases or ms_*_plan.json work
  (→ /specdev-trinity). NOT when the task is to author, edit, or review a spec step.
  Sibling skills: specdev-step (author new step), specdev-review (review+fix), specdev-trinity
  (trinity phases).
  Trigger on: "what does step NN need", "look at step NN", "explain step NN",
  "/specdev-context NN", or any orientation/analysis/debugging question about a spec step.
---

# /specdev-context — Step Context Loader

Single entry point for all spec reads. Two flows: **Orientation** (load context for a step) and **Action** (apply surgical edits driven by a source of findings). Both compose existing CLI primitives. Subagents handle exploration; the main thread handles synthesis.

## Path variables

| Variable | Meaning |
|---|---|
| `$TOOLKIT_ROOT` | Toolkit submodule root (typically `./devspec_toolkit`) |
| `$SPEC_DIR` | Host spec directory (typically `./spec`) |
| `$GIT_ROOT` | Host repo root (typically `.`) |

All paths resolve from `$GIT_ROOT`. If running from `$TOOLKIT_ROOT`, paths break — `cd` to `$GIT_ROOT` first.

## Hard bans

| Banned |
|---|
| `Read` on any file under `$SPEC_DIR/` |
| `Read` on any file under `$TOOLKIT_ROOT/canon/kinds/` |
| `Read` on tool-output dump files (`*.txt`, `.specdev/`, `/tmp/`) |
| `cat` / `Bash` reads of spec or canon files, `git show <ref>:spec/...` among them (what changed between two git refs: `specdev diff <refA> <refB>`) |
| `Edit` on any existing file under `$SPEC_DIR/` (use `specdev json patch/insert/delete`) |
| `Write` on any file under `$SPEC_DIR/` (a brand-new step file is made with `specdev step create <NN> --from <draft>`; the draft is written outside `spec/`, at `.specdev/drafts/step_<NN>.json`) |
| Unfiltered `specdev json read <file>` — always pass a jq filter |
| `specdev json read` with a filter that traverses into a path whose shape you have not directly inspected this session — run `json structure` or `json keys` against the parent path first. Guessing field names produces "Cannot iterate over null" errors |
| `--spec-root` or `--git-root` on `specdev json` read/edit subcommands (`read`, `read-multi`, `keys`, `structure`, `schema`, `patch`, `insert`, `delete`) — the CLI silently strips them, but the canonical invocation omits them. Exceptions: `specdev json resolve-pointers` legitimately accepts `--git-root` (anchors relative file paths); the id forms `json patch|insert|delete --id <id>` and `json insert --step <NN>` take all three flags |
| Hardcoded "FRs live in step 04 / APIs in step 05" mappings — use `entry_key_registry` |
| `specdev context extract` (removed — hard-fails) |

Explicitly allowed: `Read` on `$TOOLKIT_ROOT/prompts/prompt_NN_*.md` and `$TOOLKIT_ROOT/docs/prompts/shared_expectations.md`.

## Surgical query rules

- Always pass a jq filter to `specdev json read`. Unfiltered reads of whole spec files are banned.
- **Shape-first**: before composing any new `json read` filter on a path you have not just inspected, run one of `specdev json structure <file>`, `specdev json keys <file> '<parent-path>'`, or `specdev json schema <file> <path>`. Each takes <1 second and prevents the dominant `json read` failure class. Do not trust priors about field names.
- Run `specdev <command> --help` when unsure about flags. Do not assume.
- **Flag scope**: `--spec-root` and `--git-root` apply to validation/governance commands (`spec-check`, `validate`, `governance-check`, `stale`, `coverage`, `trace`, `step ready`, etc.); `canon-accept` accepts `--git-root` only. Most `specdev json …` subcommands accept `--repo-root` only — the CLI silently strips the other two if passed. Exceptions: `specdev json resolve-pointers` legitimately accepts `--git-root` to anchor relative file paths; the id forms (`json patch|insert|delete --id`, `json insert --step`) take all three flags.

**Retry trap**: when a `json read` fails, do not retry with another guessed path — the failure means your assumption about the parent shape is wrong. Drop back to a shape probe (`json structure` / `json keys` / `json schema`) and rebuild the filter from real field names.

## The two static indices

| Index | Path | Answers |
|---|---|---|
| `step_order.json` | `$TOOLKIT_ROOT/tools/step_order.json` | "Which steps are downstream of step N? Which upstream files feed step N?" |
| `entry_key_registry.json` | `$TOOLKIT_ROOT/tools/entry_key_registry.json` | "Which file/array/id_field holds entities of kind K? Registry is keyed by filename: `{<file>: {step, arrays: [{array_path, id_field, kind}]}}`. Each array entry may also carry an optional `nested: [{array_path, id_field, kind}]` array for sub-array entries (the registry file says which kinds carry one). To find the file for a kind, scan entries." |

**Composition rule**: when walking from a kind to its owning file, or from a step to its downstream files — compose these two indices. Never hardcode the mappings they encode.

Links between entities are not in an index file; ask the graph:
- "If I change node X, what depends on it? What does it derive from?" — `specdev trace --down <id>` / `specdev trace --up <id>` (lineage and impact).
- "How are the FRs covered?" — `specdev coverage --by fr` (per FR, the nodes that link it and whether each link is current or suspect).
- "What is still to be re-read after an upstream change?" — `specdev stale`.

**Cross-index walks:**
- kind → owning file/step: `entry_key_registry.json` → walk `step_order.json` `downstream_consumers` for downstream blast radius.
- cross-step link → both endpoint ids → `entry_key_registry.json` for each id's kind/file/step → downstream impact via `step_order.json`.
- entry's step → `step_order.json` `step_metadata.required_spec_inputs` → upstream files it was derived from.

**Update cadence:**
- `step_order.json` — regenerated by `specdev registry-generate --repo-root <toolkit>`: `step_metadata.required_spec_inputs` and `downstream_consumers` are derived from the `x-link` declarations of the schemas and from `declared_edges`; only the keys `version`, `steps`, `policy` and `declared_edges` are kept by hand in the file (edit those, then regenerate). `downstream_consumers` and `step_metadata.required_spec_inputs` must stay inverse-consistent (E543 STEP_METADATA_INCONSISTENT).
- `entry_key_registry.json` — regenerated by `specdev registry-generate --repo-root <toolkit>` after any schema change. The five generator-owned files (`tools/entry_key_registry.json`, `tools/extraction_paths.json`, `tools/step_order.json`, `tools/cli_commands.json`, `docs/developers/schema-change-checklist.md`) must not be hand-edited; CI enforces byte-exact equality. `tests/fixtures/entry_key_registry_golden.json` is a copy of the registry that a test compares byte for byte.

## Subagent delegation

For tasks requiring more than 5 reads to compose an answer — cross-step concept reviews, milestone audits, backlog impact amplification — spawn a subagent. Give it the task; it runs the reads internally and returns a structured report: `findings` (list of `{file, id, observation}`), `recommendations` (list of actionable items), and any explicit deliverables the caller requested. The orchestrator's context stays focused on decisions.

For single-step tasks (load context, patch one entry, verify), do the reads inline.

## Orientation flow

Invoked on a step, optionally with a scope hint (entry-id, milestone-id, fr-prefix, concept keyword). Skip Step 3 if no scope hint was provided.

### Step 1 — Orient

```bash
specdev context structure $SPEC_DIR --step <NN> --repo-root $TOOLKIT_ROOT
```

Returns a structural skeleton: required upstream files, per-file array counts, canon kinds used.

### Step 2 — Know shape (mandatory before any new `json read` filter)

```bash
specdev json structure $SPEC_DIR/<NN>_*.json
specdev json keys      $SPEC_DIR/<NN>_*.json '<parent-jq-path>'
specdev json schema    $SPEC_DIR/<NN>_*.json '<jq-path>' --repo-root $TOOLKIT_ROOT
```

Pick whichever probe matches the question — `structure` for the whole skeleton, `keys` for "what fields exist at this path", `schema` for typed constraints. Skipping Step 2 is the root cause of the most common `json read` failure ("Cannot iterate over null") — see the **Retry trap** note under Surgical query rules.

### Step 3 — Scope resolution (only if a scope hint was provided)

Compose primitives based on the hint:

- **Entry id**: scan the registry for the kind, then read the matching entry:
  ```bash
  specdev json read $TOOLKIT_ROOT/tools/entry_key_registry.json \
    '.registry | to_entries[] | .key as $f | .value | .arrays[] | select(.kind == "<K>") | . + {file: $f}'
  # then:
  specdev json read $SPEC_DIR/<file> '.<array>[] | select(.<id_field> == "<entry-id>")'
  ```
- **Milestone id**: `specdev json read $SPEC_DIR/14_roadmap.json '.milestones[] | select(.milestone_id == "<id>")'`; then the per-milestone plan at `$SPEC_DIR/impl_context/ms_*_plan.json`; then `specdev trace --down <milestone-id>` for what the milestone schedules.
- **Concept keyword / FR prefix**: find the node ids with `specdev json read $SPEC_DIR/04_fr_list.json '.functional_requirements[] | select(.fr_id | startswith("<prefix>")) | .fr_id'` (run `json structure` on the file first), then `specdev trace --down <id>` for what depends on each and `specdev coverage --by fr` for the FR view; drill into specific entries via `json read`.

### Step 4 — Canon

```bash
specdev context canon --step <NN> --repo-root $TOOLKIT_ROOT --spec-root $SPEC_DIR
```

### Step 5 — Prompt contract

Read `$TOOLKIT_ROOT/docs/prompts/shared_expectations.md` (required before any prompt execution) **and** `$TOOLKIT_ROOT/prompts/prompt_<NN>_*.md` (step's authoring contract).

## Action flow

Run when the task is to apply edits driven by a source of findings.

### Step 1 — Acquire findings

| Source | Command |
|---|---|
| Backlog | `specdev upstream-backlog $SPEC_DIR --repo-root $TOOLKIT_ROOT --json` |
| Edit intent | Caller supplies findings |
| Spec-check errors | `specdev spec-check $SPEC_DIR --repo-root $TOOLKIT_ROOT --spec-root $SPEC_DIR --git-root $GIT_ROOT --json` |

Each finding has minimally `{id, severity, description, impact[]}`; a backlog record names its item `item_id`, and has `severity` only when the item is of the 1.1.1 shape. The `impact[]` is a list of pointer-shaped `(file, id)` targets. If the source produced zero actionable findings (empty `records[]` for backlog, empty `findings[]` for spec-check, no items supplied for edit intent), stop and report "no findings" — do not proceed to Step 2.

### Step 2 — Validate pointers

`specdev json resolve-pointers` reads a JSON array of `{file, id}` (or `{file, jq_path}`) objects from stdin; returns hits/misses with `nearest[]` hints; an id defined more than once in the file is returned with `"ambiguous": true` and every definition under `locations`.

```bash
specdev upstream-backlog $SPEC_DIR --repo-root $TOOLKIT_ROOT --json \
  | jq '[.records[]?.impact[]?
         | if type == "string" and test(":") then split(":") | {file: .[0], id: .[1]}
           elif type == "object" then {file, id}
           else empty end]' \
  | specdev json resolve-pointers --repo-root $TOOLKIT_ROOT --git-root $GIT_ROOT
```

The shape guard (`if type ==`) keeps the pipeline robust to either string (`"file:id"`) or object (`{file, id}`) impact entries. Surface unresolved pointers to the caller; do not silently drop.

A 1.2.0 item has `impact: []`; its pointers are the node or seed ids in `about`. The jq above does not read them: locate each with `specdev node show <id> --json` (its `file` and `jq_path`), or list them with `specdev trace --down <id>`. An `about` id that names no node is listed under `unplaced`; surface it to the caller.

### Step 3 — Amplify impact (optional)

When a finding's `impact[]` may be incomplete (typical for newly-recorded `emergent_ambiguities`), walk the graph to compute the full blast radius before patching:

1. For each entity in the impact set, run `specdev trace --down <id> --repo-root $TOOLKIT_ROOT --spec-root $SPEC_DIR --git-root $GIT_ROOT` (add `--json` to read it) for all entities that depend on it.
2. For each dependent entity, its owning file and step are in the trace output; for a kind you have not seen, look up its file via `$TOOLKIT_ROOT/tools/entry_key_registry.json` (kind → file/step).
3. Union all `(file, id)` pairs into the amplified impact set.
4. Optionally query `$TOOLKIT_ROOT/tools/step_order.json` `.downstream_consumers["<step>"]` for step-level blast radius.

### Step 4 — Surgical edit

```bash
specdev json patch <file> '<jq-path>' '<value>' --repo-root $TOOLKIT_ROOT
```

Use `insert` for array append, `delete` for removal. `json patch`/`insert` validate every write against the file's own `$schema` automatically — there is no flag, and `json delete` is not validated. A write is refused if it introduces a new schema violation (a didactic error naming the failing constraint or value), the file has no `$schema`, the edit would modify `$schema` itself, or the schema cannot be resolved or loaded (validation fails closed on any error). Validation is **differential** — it blocks only violations the edit *introduces*, so fixing one field while another is still invalid is allowed. A consequence: flipping a conditionally-gated field before its required siblings exist is refused — e.g. setting an implementation `status` to `verified` before its `actions[]` carry `evidence`; supply those siblings (within the same object) in the same or a prior patch, or rewrite the whole object. Preview with `--dry-run` for non-trivial edits. When `impact[]` contains multiple `(file, id)` pairs (distinct from the within-object case above), apply patches one at a time; do not batch multiple patches into a single call. Run spec-check between patches.

### Step 5 — Verify

```bash
specdev spec-check $SPEC_DIR --repo-root $TOOLKIT_ROOT --spec-root $SPEC_DIR --git-root $GIT_ROOT --json
specdev stale --repo-root $TOOLKIT_ROOT --spec-root $SPEC_DIR --git-root $GIT_ROOT --json
```

The gate of an edit is the gate of the step it was made in: for each step `<NN>` you edited, `specdev spec-check $SPEC_DIR --step <NN> --repo-root $TOOLKIT_ROOT --spec-root $SPEC_DIR --git-root $GIT_ROOT` must end `RESULT: CLEAR`. The whole-repo run above also lists errors that other steps own; those are not yours to fix here. When every edited step is clear and `stale` lists nothing pending (`"steps": []`): done. If errors of an edited step surface, fix the lowest-numbered failing entry first, re-validate. One fix per cycle.

## Writing primitives

| Situation | Command |
|---|---|
| New step file (does not yet exist) | Write the draft at `.specdev/drafts/step_<NN>.json`, then `specdev step create <NN> --from .specdev/drafts/step_<NN>.json` (human go-ahead); then `spec-check --step <NN>` to validate |
| Replace a scalar | `specdev json patch <file> '<jq-path>' '<value>'`, or by node id: `specdev json patch --id <id> <field-path> '<value>'` |
| Append to array / merge into object | `specdev json insert <file> '<jq-path>' '<value>'`, or `specdev json insert --id <id> <array-field> '<item>'`; a new node: `specdev json insert --step <NN> <collection-path> '<item>'` |
| Delete a field or entry | `specdev json delete <file> '<jq-path>'`, or `specdev json delete --id <id>` |
| Preview before write | All three accept `--dry-run` |

The id forms take all three flags and show the links the edit leaves suspect and the lock entries it writes; the lock is written by the commands, never by hand.

## Cross-tier canon drift

When `spec-check` reports the same canonical id resolving differently in `$TOOLKIT_ROOT/canon/manifest.json` vs `$SPEC_DIR/canon/manifest.json`, query both, decide which is authoritative, and surface to caller for human resolution. Do not silently align one side.

## Upstream drift recording

When a checklist assertion would diverge from the cited spec entry, log it as `plan.ambiguities[]` (16a) or `execution.emergent_ambiguities[]` (16b+). The `impact[]` of each new entry MUST be computed via the Action flow's amplification procedure (Step 3 above).

Verify routing:

```bash
specdev upstream-backlog $SPEC_DIR --repo-root $TOOLKIT_ROOT
```

Entries under `unplaced` (W613) have an `about` id that names no node, or are 1.1.1 items whose `impact[]` names no step.

## Permission allow-list

**Auto-invocable** (no human confirmation):
`context structure`, `context canon`, `node show`, `node candidates`, `trace`, `diff`, `stale`, `coverage`, `step ready`, `json read`, `json read-multi`, `json keys`, `json structure`, `json schema`, `json resolve-pointers`, `json patch`, `json insert`, `json delete`, `spec-check --json`, `upstream-backlog --json`, `guide`, `registry-check`, `registry-generate`. Other read-only diagnostics (`align status`, `env-check`, `prompt-context`, `ai-help`) are auto-invocable by default. During a migration, `align triage` (it lists the worklist, and `--resolve` marks one item done) and `align propose` (it writes proposals into the worklist, nothing else) are auto-invocable too.

**Human required**:
`canon-accept`, `align apply`, `align validate`, `align bind-legacy`, `attest`, `node status`, `node rename`, `step create`, `git commit`, `git push`. (`attest` writes the lock, `node status` and `node rename` write spec files, `step create` writes a new step file; run `attest` only after reading the shown old and new text.)

## Error handling

- **Command exits non-zero**: surface stderr to the caller and stop.
- **`json resolve-pointers` reports misses**: surface the miss set with `nearest[]` hints. Do not silently drop.
- **`spec-check` fails after a patch**: fix the lowest-numbered failing entry first, re-validate. One fix per cycle.
- **`stale` lists suspect links after a patch**: read each suspect link (`specdev stale --diff` shows the old and new text), feed affected entries into another Action flow iteration. Cap at 3 iterations — if suspect links persist, surface to caller for human review; clearing them is `specdev attest` (human go-ahead).
- **Error code lookup**: `specdev guide <error-code>` for the canonical remediation playbook.
