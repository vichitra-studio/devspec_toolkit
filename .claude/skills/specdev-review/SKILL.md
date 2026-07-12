---
name: specdev-review
description: >
  Run the structured review-fix loop on a spec scope. Dispatches specdev-scope (Haiku) for
  fan-out planning, then runs specdev-reviewer instances in parallel per round, merges findings,
  dispatches specdev-impl (fix mode) for repairs, and returns CONVERGED or HALT with findings path.
  NOT when spec/NN_*.json is absent (→ /specdev-step to author it first). NOT for
  ms_*_plan.json trinity reviews (→ /specdev-trinity). NOT for PR or audit scopes
  (→ /devspec_pr_audit). The artifact under review must already exist.
  Sibling skills: specdev-step (author missing step first), specdev-trinity (ms_* plan reviews),
  devspec_pr_audit (PR/branch audit scopes).
  Trigger on: "review step NN", "run review", "/specdev-review", review + any step reference,
  "check step", "audit scope", or after any spec authoring or editing task (artifact must exist).
---

# /specdev-review — Structured Review-Fix Loop

Main orchestrator for the review-fix loop. Three subagents handle all the work. This skill
stays thin: plan, dispatch in parallel, merge, dispatch fix, loop, surface verdict.

**Source spec:** K_agentification.md §3, §5.2, §5.2.1, §5.4, §5.6.

---

## Arguments

```
/specdev-review <scope> [--with-replay] [--with-backlog]
```

- `<scope>`: step number (e.g. `04`), step range (e.g. `04-07`), a file path, or `all`.
- `--with-replay`: wire `specdev forward-replay-check --json` output into a
  `cross_step_relational` reviewer. Surfaces `regression` and `drift` findings caused by
  upstream changes not yet propagated downstream.
- `--with-backlog`: wire `specdev upstream-backlog --json` output into a
  `cross_step_relational` reviewer. Surfaces `assumption` and `coverage` findings tied to
  unresolved upstream items.

When either flag is set, `specdev-scope` always adds at least one `cross_step_relational`
reviewer to the fan-out plan, alongside any per-step reviewers (K_agentification.md §5.2.1).
Per-step reviewers receive only their step's slice of the relational output to avoid
context bloat.

---

## Protocol

### Step 1 — Scope planning

Dispatch `specdev-scope` (Haiku agent) with:

```json
{
  "scope": "<scope-arg>",
  "change_set": "git_diff"
}
```

If `--with-replay` or `--with-backlog` is set, include the flag in the dispatch input so
specdev-scope includes a `cross_step_relational` reviewer.

Wait for the fan-out plan JSON:
```json
{
  "fan_out": [
    { "reviewer_id": "r1", "steps": [...], "scope_kind": "..." },
    ...
  ],
  "max_rounds": 5,
  "rationale": "..."
}
```

### Step 2 — Review-fix loop (max_rounds = 5)

**For each round from 1 to max_rounds:**

**2a. Dispatch reviewers in waves (wave loop).**

Per-round invariant: Each round dispatches ALL reviewers against the FULL current artifact state. Do NOT narrow review to only changed content. Do NOT reuse or resume reviewer agents from a prior round — every Agent call in every round is stateless-fresh. This is not an optimisation opportunity.

Resolve concurrency cap: `CONCURRENCY=${SPECDEV_REVIEW_CONCURRENCY:-6}`.

All clusters returned by specdev-scope (the `fan_out[]` list) must be reviewed before fix-dispatch.
Dispatch in waves: send the first ≤`CONCURRENCY` clusters as parallel Agent tool calls in a
single message; wait for ALL of them to return; then send the next wave of ≤`CONCURRENCY`
clusters; repeat until all clusters in `fan_out[]` have been dispatched and returned. Do NOT
dispatch clusters sequentially within a wave — all clusters in each wave are parallel.

Intra-round consistency rule: ALL waves of reviewer dispatch for this round MUST complete
before `specdev-impl` (fix mode, Step 2d) is dispatched. No fix dispatch between waves of the
same round.

This cap is per-wave (simultaneous clusters), NOT per-run (total). Large scopes may produce
more clusters than `CONCURRENCY`; they are covered across multiple waves, never truncated.

Note: the ≤`CONCURRENCY` wave limit is an LLM-compliance directive — the harness has no native
wave-dispatch primitive. This is the same enforcement level as `max_rounds = 5`.

Each reviewer receives its cluster slice from the fan-out plan:
```json
{
  "steps": [...],
  "scope_kind": "...",
  "reviewer_id": "r1",
  "round": <current_round>,
  "scope": "<scope-identifier>",
  "flags": {
    "with_replay": <bool>,
    "with_backlog": <bool>
  }
}
```

For `cross_step_relational` reviewers: pre-run the relational commands and pass their
output inline in the dispatch (do not have the reviewer re-run them):
```bash
specdev forward-replay-check --json \
  --repo-root ./devspec_toolkit --spec-root ./spec --git-root .

specdev upstream-backlog spec --json \
  --repo-root ./devspec_toolkit
```

Each reviewer writes its own file:
`.specdev/findings/findings_<scope>_<round>_r<reviewer_id>.json`

(Ensure the directory exists once per loop: `mkdir -p .specdev/findings`.)

**2b. Merge findings with the jq one-liner (K_agentification.md §5.4, paths per §11.7):**

```bash
jq -s '{round: .[0].round, scope: .[0].scope, generated_at: (now | floor), findings: (map(.findings) | add | unique_by({kind, location, signature}))}' \
  .specdev/findings/findings_<scope>_<round>_r*.json > .specdev/findings/findings_<scope>_<round>.json
```

This is the ONLY merge mechanism. Do not use `specdev findings emit/merge/dedup` — no such
CLI exists. The jq one-liner is skill-side; it keeps the main thread thin.

Dedup key is the tuple `(kind, location, signature)` as specified in K_agentification.md §5.4.

**2c. Check convergence:**

If `findings[]` in `.specdev/findings/findings_<scope>_<round>.json` is empty:
- Print: "CONVERGED at round <N>. No findings remain."
- Return.

**2d. Dispatch fix:**

If findings remain, dispatch `specdev-impl` with:
```json
{
  "mode": "fix",
  "findings_path": ".specdev/findings/findings_<scope>_<round>.json",
  "scope": "<scope>",
  "round": <current_round>
}
```

After Agent returns (blocker handling — canonical contract: `specdev-impl.md` § "Blocker emission protocol"):
1. Parse return JSON.
2. If `status != "blocker"`: check `gate_status`. If `gate_status: "errors"` and
   `errors_remaining` is non-empty, carry those forward as context for the next round.
3. If `status == "blocker"`:
   a. Validate shape: `questions[]` non-empty; each has `{id, question, header, options[2..4]}`.
      If malformed → HALT and surface to user (do NOT re-dispatch on a malformed payload).
      Malformed includes: `questions[]` empty, any entry missing required fields, edits
      written AND `status: "blocker"` simultaneously (timing-constraint violation).
   b. Persist audit trail:
      ```bash
      mkdir -p .specdev/blockers/
      ```
      Write `.specdev/blockers/blocker_<scope>_r<round>_<unix_ts>.json` with the full payload.
   c. Chunk questions into groups of ≤4. Call `AskUserQuestion` once per chunk, sequentially.
      Collect all answers keyed by `question.id`.
      If the user dismisses or does not answer an AskUserQuestion call (empty answer set
      returned), HALT immediately. Surface: "Blocker unresolved: user did not answer
      clarification questions. Re-invoke /specdev-review <scope> to retry." Write a HALT
      artifact noting `aborted_by_user` to `.specdev/blockers/blocker_<scope>_aborted_<unix_ts>.json`.
      Do not re-dispatch.
   d. Build re-dispatch prompt:
      - Original fix dispatch input verbatim.
      - PLUS a `## User answers (from blocker bridge)` section listing each
        `{id, question, selected_label, selected_description, user_notes_if_any}`.
      - PLUS a `## Context from prior dispatch` section quoting the agent's `context` field.
   e. Increment `blocker_round` counter (per-dispatch-site, scoped to a single subagent
      dispatch chain; starts at 0 on first dispatch; cap = 2 re-dispatches (counter values 0,
      1, 2); does not persist across skill invocations; resets to 0 at the start of each new
      outer review-fix round (R1/R2/.../R5)).
   f. If `blocker_round > 2`: HALT, surface to user (persistent blocking — no auto-retry).
   g. Fresh Agent dispatch with the augmented prompt. Continue from step 1.
   Note: lossy re-dispatch — accepted cost; the re-dispatched agent re-reads all context
   from scratch; user answers are the ONLY persistence across the bridge.
   SendMessage-based clean resumption is deferred.

Increment round counter and continue.

### Step 3 — HALT on max_rounds

If round 5 completes with findings remaining:

Write the HALT artifact:
```
.specdev/findings/findings_<scope>_5_<unix_timestamp>.json
```

This is a timestamped copy of the round-5 merged findings file. It is the audit trail.
Do not promote it to a canonical name. The timestamped file IS the record.

Print:
```
HALT: max_rounds=5 reached with unresolved findings.
Findings path: .specdev/findings/findings_<scope>_5_<unix_timestamp>.json
Finding count: <N> (<P0_count> P0, <P1_count> P1, <P2_count> P2)
Human action required: proceed-with-gaps | replay | hand-edit then re-invoke /specdev-review <scope>
```

Do not silently accept partial convergence. HALT is a first-class verdict.

---

## HALT resume

After the human hand-edits and re-invokes `/specdev-review <scope>`, always start fresh
at round 1. Prior findings files are NOT consulted — the reviewer sees the artifact's
current state and emits fresh findings. This keeps the loop deterministic and avoids
state drift across runs (K_agentification.md §5.6).

Prior blocker audit files under `.specdev/blockers/` are also NOT consulted on resume —
the fresh-state invariant applies to both findings and blocker artifacts (K_agentification.md
§5.6). They exist for human inspection of past blocker rounds only. If a prior blocker is
still relevant, the re-dispatched specdev-impl will re-emit it and AskUserQuestion will fire
again.

---

## Flag-stripping reminder

When running specdev commands from this skill:
- `specdev json` read/shape/edit subcommands: pass `--repo-root` only.
- Exception: `specdev json resolve-pointers` accepts `--git-root` (anchors relative paths).
- `spec-check`, `forward-replay-check`, `governance-check`:
  pass all three flags `--repo-root ./devspec_toolkit --spec-root ./spec --git-root .`
- `upstream-backlog`: pass `--repo-root` only (does not accept `--spec-root` or `--git-root`).
- `canon-accept`: pass `--git-root`, NOT `--spec-root`.

Never read `spec/*.json` directly. All spec reads go through `specdev json read` with a filter.

---

## What this skill does NOT do

- Does not author new spec artifacts. That is `/specdev-step`'s job (author mode).
- Does not manage trinity-plan human gating. That is `/specdev-trinity --phase plan`'s job.
- Does not handle 16b/16c code-write or code-review. Plan-phase and spec-phase only
  (see K_agentification.md §9 — 16b/16c are covered by K2 (WIP/toolkit_proposals/K_agentification.md §11+)).
- Does not commit changes. User authorizes commits separately.
- Does not use `specdev findings emit/merge/dedup`. No such CLI exists (K §5.4).
- Does not run reviewers sequentially in a single round. Parallel dispatch is required.
- Does not skip AskUserQuestion on a blocker payload. Blocker questions must be presented
  to the user via the harness before re-dispatching.
