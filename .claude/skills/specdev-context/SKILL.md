---
name: specdev-context
description: >
  Load context for a pipeline step. Required before any spec-related work: authoring,
  reviewing, analysing, debugging, or answering questions about spec files or pipeline steps.
  Never read files under spec/ directly with the Read tool — use this skill's primitives.
  Trigger on: any mention of a step number, "what does step NN need", "look at step NN",
  "work on step NN", "/specdev-context NN", or any task involving spec files, milestones,
  cross-step concepts, or backlog follow-up.
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

Literal `tools/` references in this skill (`$TOOLKIT_ROOT/tools/`, `$GIT_ROOT/tools/`) are the conventional toolkit + host layouts.

## Hard bans

| Banned |
|---|
| `Read` on any file under `$SPEC_DIR/` |
| `Read` on any file under `$TOOLKIT_ROOT/canon/kinds/` |
| `Read` on tool-output dump files (`*.txt`, `.specdev/`, `/tmp/`) |
| `cat` / `Bash` reads of spec or canon files |
| `Edit` on any existing file under `$SPEC_DIR/` (use `specdev json patch/insert/delete`) |
| `Write` on existing spec files (`Write` is allowed **only** for creating a brand-new step file that does not yet exist) |
| Unfiltered `specdev json read <file>` — always pass a jq filter |
| Hardcoded "FRs live in step 04 / APIs in step 05" mappings — use `entry_key_registry` |

| Explicitly allowed |
|---|
| `Read` on `$TOOLKIT_ROOT/prompts/prompt_NN_*.md` (step's authoring contract) |
| `Read` on `$TOOLKIT_ROOT/prompts/shared_expectations.md` (operating rules — required before any prompt execution) |

## Surgical query rules

- Always pass a jq filter to `specdev json read`. Unfiltered reads of whole spec files are banned.
- Use `specdev json structure <file>` and `specdev json schema <file> <path>` to learn a file's shape before composing queries. Do not trust priors about field names.
- Run `specdev <command> --help` when unsure about flags. Do not assume.

## The three static indices

| Index | Path | Answers |
|---|---|---|
| `step_order.json` | `$TOOLKIT_ROOT/tools/step_order.json` | "Which steps are downstream of step N? Which upstream files feed step N?" |
| `trace_matrix.json` | `$GIT_ROOT/tools/trace_matrix.json` | "If I change entity E, which other entities are linked? (link kinds defined in `$TOOLKIT_ROOT/canon/kinds/trace_type.json`)" |
| `entry_key_registry.json` | `$TOOLKIT_ROOT/tools/entry_key_registry.json` | "Which file/array/id_field holds entities of kind K? Which step is that file in?" |

**Composition rule**: when walking from a kind to its owning file, from an entity to its dependents, or from a step to its downstream files — compose these three indices. Never hardcode the mappings they encode.

`step_order` is mostly consumed indirectly via `specdev context structure` (Orientation Step 1). Read it directly only for `downstream_consumers` lookups in impact amplification.

## Subagent delegation

For tasks requiring many reads to compose an answer — cross-step concept reviews, milestone audits, backlog impact amplification — spawn a subagent. Give it the task; it runs the reads internally and returns a synthesis. The orchestrator's context stays focused on decisions.

For single-step tasks (load context, patch one entry, verify), do the reads inline.

## Orientation flow

Invoked on a step, optionally with a scope hint (entry-id, milestone-id, fr-prefix, concept keyword). Skip Step 3 if no scope hint was provided.

### Step 1 — Orient

```bash
specdev context structure $SPEC_DIR --step <NN> --repo-root $TOOLKIT_ROOT
```

Returns a structural skeleton: required upstream files, per-file array counts, canon kinds used.

### Step 2 — Know shape

```bash
specdev json structure $SPEC_DIR/<NN>_*.json
specdev json schema $SPEC_DIR/<NN>_*.json '<jq-path>' --repo-root $TOOLKIT_ROOT
```

Discover the file's actual shape before querying. `json structure` returns a tree; `json schema` returns the schema definition for a path.

### Step 3 — Scope resolution (only if a scope hint was provided)

Compose primitives based on the hint:

- **Entry id**: look up `kind` → `(file, array, id_field)` in `$TOOLKIT_ROOT/tools/entry_key_registry.json`, then `specdev json read $SPEC_DIR/<file> '.<array>[] | select(.<id_field> == "<entry-id>")'`.
- **Milestone id**: `specdev json read $SPEC_DIR/14_roadmap.json '.milestones[] | select(.milestone_id == "<id>")'`; then the per-milestone plan at `$SPEC_DIR/impl_context/ms_*_plan.json`; then the trace matrix slice for the milestone's FRs.
- **Concept keyword / FR prefix**: query `$GIT_ROOT/tools/trace_matrix.json` for entities matching the prefix; drill into specific entries via `json read`.

### Step 4 — Canon

```bash
specdev context canon --step <NN> --repo-root $TOOLKIT_ROOT --spec-root $SPEC_DIR
```

### Step 5 — Prompt contract

Read `$TOOLKIT_ROOT/prompts/shared_expectations.md` (operating rules; required before any prompt execution) **and** `$TOOLKIT_ROOT/prompts/prompt_<NN>_*.md` (the step's authoring contract). Both are explicitly read-allowed (see Hard bans table).

## Action flow

Run when the task is to apply edits driven by a source of findings.

### Step 1 — Acquire findings

| Source | Command |
|---|---|
| Backlog | `specdev upstream-backlog $SPEC_DIR --repo-root $TOOLKIT_ROOT --json` |
| Edit intent | Caller supplies findings |
| Spec-check errors | `specdev spec-check $SPEC_DIR --repo-root $TOOLKIT_ROOT --spec-root $SPEC_DIR --git-root $GIT_ROOT --json` |

Each finding has minimally `{id, severity, description, impact[]}`. The `impact[]` is a list of pointer-shaped `(file, id)` targets.

### Step 2 — Validate pointers

`specdev json resolve-pointers` reads a JSON array of `{file, id}` (or `{file, jq_path}`) objects from stdin; returns hits/misses with `nearest[]` hints.

```bash
specdev upstream-backlog $SPEC_DIR --repo-root $TOOLKIT_ROOT --json \
  | jq '[.records[]?.impact[]?
         | if type == "string" and test(":") then split(":") | {file: .[0], id: .[1]}
           elif type == "object" then {file, id}
           else empty end]' \
  | specdev json resolve-pointers --repo-root $TOOLKIT_ROOT --git-root $GIT_ROOT
```

The shape guard (`if type ==`) keeps the pipeline robust to either string (`"file:id"`) or object (`{file, id}`) impact entries. Surface unresolved pointers to the caller; do not silently drop.

### Step 3 — Amplify impact (optional)

When a finding's `impact[]` may be incomplete (typical for newly-recorded `emergent_ambiguities`), walk the three indices to compute the full blast radius before patching:

1. For each entity in the impact set, query `$GIT_ROOT/tools/trace_matrix.json` for all linked entities. The set of link kinds is defined in `$TOOLKIT_ROOT/canon/kinds/trace_type.json` — do not hardcode the kind list in your query.
2. For each linked entity, look up its owning file via `$TOOLKIT_ROOT/tools/entry_key_registry.json` (kind → file/step).
3. Union all `(file, id)` pairs into the amplified impact set.
4. Optionally query `$TOOLKIT_ROOT/tools/step_order.json` `.downstream_consumers["<step>"]` for step-level blast radius.

### Step 4 — Surgical edit

```bash
specdev json patch <file> '<jq-path>' '<value>' \
  --against-schema-field <step>.<field> --repo-root $TOOLKIT_ROOT
```

Use `insert` for array append, `delete` for removal. Always pass `--against-schema-field` for schema-validated writes. Preview with `--dry-run` for non-trivial edits.

### Step 5 — Verify

```bash
specdev spec-check $SPEC_DIR --repo-root $TOOLKIT_ROOT --spec-root $SPEC_DIR --git-root $GIT_ROOT --json
specdev forward-replay-check --repo-root $TOOLKIT_ROOT --spec-root $SPEC_DIR --git-root $GIT_ROOT --json
```

If both green: done. If errors surface, fix the lowest-numbered failing entry first, re-validate. One fix per cycle.

## Writing primitives

| Situation | Command |
|---|---|
| New step file (does not yet exist) | `Write` tool for initial creation only; then `spec-check` to validate |
| Replace a scalar | `specdev json patch <file> '<jq-path>' '<value>' --against-schema-field <step>.<field>` |
| Append to array / merge into object | `specdev json insert <file> '<jq-path>' '<value>' --against-schema-field <step>.<field>` |
| Delete a field or entry | `specdev json delete <file> '<jq-path>'` |
| Preview before write | All three accept `--dry-run` |

## Cross-tier canon drift

When `spec-check` reports the same canonical id resolving differently in `$TOOLKIT_ROOT/canon/manifest.json` vs `$SPEC_DIR/canon/manifest.json`, query both, decide which is authoritative, and surface to caller for human resolution. Do not silently align one side.

## Upstream drift recording

When a checklist assertion would diverge from the cited spec entry, log it as `plan.ambiguities[]` (16a) or `execution.emergent_ambiguities[]` (16b+). The `impact[]` of each new entry MUST be computed via the Action flow's amplification procedure (Step 3 above).

Verify routing:

```bash
specdev upstream-backlog $SPEC_DIR --repo-root $TOOLKIT_ROOT
```

Entries landing in `Unclassified` mean `impact[]` lacks a step-routable path.

## Permission allow-list

**Auto-invocable** (no human confirmation):
`context structure`, `context canon`, `json read`, `json read-multi`, `json keys`, `json structure`, `json schema`, `json resolve-pointers`, `json patch`, `json insert`, `json delete`, `spec-check --json`, `forward-replay-check --json`, `upstream-backlog --json`, `matrix`, `guide`, `registry-check`. Other read-only diagnostics (`align status`, `env-check`, `prompt-context`, `ai-help`) are auto-invocable by default.

**Human required**:
`canon-accept`, `align apply`, `git commit`, `git push`.

## Error handling

- **Command exits non-zero**: surface stderr to the caller and stop.
- **`json resolve-pointers` reports misses**: surface the miss set with `nearest[]` hints. Do not silently drop.
- **`spec-check` fails after a patch**: fix the lowest-numbered failing entry first, re-validate. One fix per cycle.
- **`forward-replay-check` reports invalidation**: feed affected entries into another Action flow iteration.
- **Error code lookup**: `specdev guide <error-code>` for the canonical remediation playbook.
