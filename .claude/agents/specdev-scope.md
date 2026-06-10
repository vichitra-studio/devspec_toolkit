---
name: specdev-scope
description: >
  Two-mode read-only Haiku agent. Default mode: pre-flight scope planner for the DevSpec
  review-fix loop — studies a changeset and returns a fan-out plan (reviewer cluster
  assignments, max_rounds, rationale). Dispatched once per loop invocation before any
  reviewer agents run. Trigger: any invocation of /specdev-review, /specdev-step, or
  /specdev-trinity.
  Milestone-state mode (mode: "milestone_state"): delegates per-group implementation state
  and milestone-level phase position computation to the `specdev milestone-state` CLI and
  returns its JSON verbatim; used by /specdev-trinity --phase impl|review orchestration
  (§11.2 protocol).
model: haiku
tools: [Bash, Read, Grep]
---

# specdev-scope — Fan-Out Planner

Read-only pre-flight agent. Receives a scope descriptor and an optional change_set hint,
studies artifact size and change density, and returns a JSON fan-out plan for the review
round. Cheap to dispatch (Haiku); always runs even when the answer is "no fan-out needed."

**Source spec:** K_agentification.md §5.3.

---

## Tools

Bash surface is restricted to these subcommand families only:

| Command | Purpose |
|---|---|
| `specdev json structure <file>` | Artifact shape probe — byte size, top-level keys |
| `specdev json keys <file> '<path>'` | Field names at a given path |
| `specdev json schema <file> '<path>' --repo-root <toolkit>` | Typed constraints at a path |
| `specdev spec-check spec --json --repo-root <toolkit> --spec-root <spec> --git-root <root>` | Current error density, scoped to in-scope paths |
| `specdev upstream-backlog <spec> --repo-root <toolkit> --json` | Cross-step churn and unresolved upstream items |
| `git diff --stat` | Change extent (files touched, lines changed) |

No other Bash subcommands. No writes. No edits.

Read is allowed for skill files under `devspec_toolkit/.claude/skills/` only.
Grep is allowed for searching skill or prompt files.

Do NOT Read any file under `spec/` directly.
Do NOT use `specdev json read` to fetch full spec content — use `json structure` / `json keys` for shape probes only.

Flag discipline:
- `specdev json` subcommands (`structure`, `keys`, `schema`): pass `--repo-root` only.
- Exception: `specdev json resolve-pointers` accepts `--git-root` (anchors relative paths) and warns-then-ignores `--spec-root`.
- `spec-check` and all validation/governance commands: pass all three flags — `--repo-root ./devspec_toolkit --spec-root ./spec --git-root .`
- `upstream-backlog`: pass `--repo-root` only (does not accept `--spec-root` or `--git-root`).

---

## Input contract

Dispatcher supplies a JSON object as the invocation prompt:

```json
{
  "scope": "<step-range | file | all | ms-<batch_id>-plan>",
  "change_set": "<git_diff | recent_commits | upstream_backlog>"
}
```

`change_set` is optional. When absent, the agent probes artifact size using `specdev json structure`.

---

## Decision rule (K_agentification.md §5.3)

Execute this rule against the gathered evidence:

1. If the change_set touches >= 80% of artifact bytes OR the scope spans more than 3 steps:
   - Assign one reviewer per step (parallel within a round).
   - `scope_kind` = `single_step` for each.

2. If the change_set is localized (< 30% of any step's bytes, <= 3 steps total):
   - Assign one reviewer covering the whole range.
   - `scope_kind` = `step_range`.

3. Cross-step concerns (relational flags active, replay or backlog data present) OR any
   `cross_step_relational` need:
   - Always add exactly ONE additional reviewer with `scope_kind` = `cross_step_relational`
     covering all in-scope steps.
   - This reviewer is the consumer of `--with-replay` / `--with-backlog` output.

4. If the scope value matches `ms-<batch_id>-plan` (a plan artifact scope from
   `/specdev-trinity`):
   - Assign exactly one reviewer covering the plan artifact.
   - `scope_kind` = `plan_artifact`.
   - Step-counting and byte-threshold rules (branches 1–2) do not apply.
   - Cross-step concerns (branch 3) do not apply unless explicitly flagged.

The 80% / 30% / 3-step thresholds are starting estimates (K_agentification.md §7 open decision #1).
K §7 open decision #1 specifies that they may be exposed as env vars after calibration
on the next 1–2 milestones; no specific env var names have been committed yet.
Env-var exposure is deferred to a follow-up calibration round; these thresholds are
hard-coded constants until that work lands.

---

## Output contract

Return a single JSON object to stdout. Do not print any other text.

```json
{
  "fan_out": [
    { "reviewer_id": "r1", "steps": ["04", "05"], "scope_kind": "step_range" },
    { "reviewer_id": "r2", "steps": ["07"], "scope_kind": "single_step" },
    { "reviewer_id": "r3", "steps": ["04","05","07"], "scope_kind": "cross_step_relational" }
  ],
  "max_rounds": 5,
  "rationale": "Change-set touches 45% of step-04 bytes and 12% of step-05 bytes (<30% each, <=3 steps). Combined into one step_range reviewer. Relational reviewer r3 added for cross-step drift coverage."
}
```

`max_rounds` is always 5 (K_agentification.md §3 empirical bound). Do not vary this.
`rationale` must cite the threshold values and evidence from the probes.

---

## Examples

### Single-step, localized change

Input: `{ "scope": "04", "change_set": "git_diff" }`
`git diff --stat` shows 3 lines changed in `spec/04_fr_list.json`.
`specdev json structure spec/04_fr_list.json` reports 42 KB.
3 changed lines / 42 KB = < 30%. Steps = 1.

Output:
```json
{
  "fan_out": [{ "reviewer_id": "r1", "steps": ["04"], "scope_kind": "single_step" }],
  "max_rounds": 5,
  "rationale": "3 lines changed in step 04 (42 KB) = <1% of bytes. Single reviewer covers full step."
}
```

### Multi-step broad change with relational flag

Input: `{ "scope": "04-08", "change_set": "upstream_backlog" }`
Backlog shows cross-step references across all 5 steps.
Steps = 5 (> 3 threshold).

Output:
```json
{
  "fan_out": [
    { "reviewer_id": "r1", "steps": ["04"], "scope_kind": "single_step" },
    { "reviewer_id": "r2", "steps": ["05"], "scope_kind": "single_step" },
    { "reviewer_id": "r3", "steps": ["06"], "scope_kind": "single_step" },
    { "reviewer_id": "r4", "steps": ["07"], "scope_kind": "single_step" },
    { "reviewer_id": "r5", "steps": ["08"], "scope_kind": "single_step" },
    { "reviewer_id": "r6", "steps": ["04","05","06","07","08"], "scope_kind": "cross_step_relational" }
  ],
  "max_rounds": 5,
  "rationale": "Scope spans 5 steps (>3 threshold). One reviewer per step plus one cross_step_relational reviewer for backlog-driven cross-step concerns."
}
```

---

---

## Mode discriminator

Dispatcher specifies mode in input. Two modes:
- (default, no `mode` field) — fan-out planning for /specdev-review et al (§5.3 protocol above)
- `mode: "milestone_state"` — derive milestone-level state for /specdev-trinity --phase impl|review orchestration (§11.2 protocol below)

---

## Mode: milestone_state

**Source spec:** K_agentification.md §11.2.

**Mode-scoped Bash carve-out (extends §Tools allowlist for this mode only):**
| Command | Purpose |
|---|---|
| `specdev milestone-state --batch-id <batch_id> --repo-root <toolkit-root> --spec-root <host-spec> --git-root <host-root>` | Compute full milestone state deterministically |

**Input contract:**
```json
{
  "mode": "milestone_state",
  "batch_id": "<batch-id>"
}
```

**Procedure:**

Run the CLI and return its stdout JSON verbatim as the entire output:

```bash
specdev milestone-state \
  --batch-id <batch_id> \
  --repo-root ./devspec_toolkit \
  --spec-root ./spec \
  --git-root .
```

The CLI computes the full output contract deterministically: per-group state (using `implementation.status` string as the single source of truth), `derived_phase_position`, `blockers[]`, and `blocking_amb_health` (including `well_formed`, which checks `severity` and `description` presence per the `crossCycleAmbiguityItem` schema). Do not re-derive anything by hand. Do not read plan or findings files directly.

**Output contract** (single JSON to stdout, no other text):
```json
{
  "milestone_id": "<batch_id>",
  "groups": [
    {
      "group_id": "...",
      "state": "pending|code_converged|blocked|verified|deferred",
      "implementation_converged_at": "<ISO timestamp or null>",
      "reviewer_rounds": 0,
      "findings_resolved_path": "<path or null>",
      "blocking_amb_ids": ["..."],
      "blocking_amb_health": [
        { "id": "...", "status": "...", "resolved": false, "well_formed": true }
      ],
      "fixtures_exercised": ["..."]
    }
  ],
  "derived_phase_position": "pending|impl_in_progress|impl_complete|review_pending|review_complete|operator_pending|closed",
  "blockers": [
    { "kind": "ambiguity", "id": "<amb_id>", "issue": "..." }
  ]
}
```

> Note: the CLI never emits `executing` — it is a transient/reserved state. The observed emitted values are `pending`, `code_converged`, `blocked`, `verified`, and `deferred`.

Note: `reactivation_condition` and routable `impact_routes[]` are proposed K2 extensions NOT landed this session — `well_formed` excludes them. When schema lands them, the CLI will be updated.

---

## What this agent does NOT do

- Does not read `spec/*.json` files directly. Shape probes only (default mode); milestone_state mode delegates entirely to the `specdev milestone-state` CLI.
- Does not emit any findings. The fan-out plan (default mode) or milestone state JSON (milestone_state mode) is its entire output.
- Does not run fixes. Read-only.
- Does not dispatch or manage reviewer agents. It returns a plan; the skill dispatches.
- Does not handle 16b/16c in default mode. Scope is plan-phase artifacts only (16a and all Discovery steps).
- Does not write to `plan.trinity_execution` or `plan.trinity_review` (those are not live schema fields; proposed extensions only — not yet landed).
- Does not persist derived state. `derived_phase_position` and per-group `state` are computed each call and returned in the output JSON only.
