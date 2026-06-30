---
name: specdev-trinity
description: >
  Orchestrate trinity phases (16a plan, 16b code-write, 16c code-review) for a milestone batch
  via --phase plan|impl|review. Plan phase reviews ms_<batch_id>_plan.json then gates on user
  approval. Impl phase serially executes each group via specdev-trinity-impl + per-group review
  loop. Review phase runs milestone-wide reviewer + milestone_fix loop. Filesystem-derived state;
  no schema extensions.
  Trigger on: "trinity plan", "trinity impl", "trinity review", "/specdev-trinity",
  any /specdev-trinity invocation, "16a", "16b", "16c", "batch <id> plan|impl|review".
---

# /specdev-trinity — Trinity Phase Orchestrator

Runs the three phases of the Trinity loop: 16a plan review, 16b code-write implementation,
16c code-review. Select the phase with `--phase`. Default is `plan`.

**Source spec:** K_agentification.md §11.3, §11.3.1, §11.3.2, §11.5, §11.7, §11.8.

---

## Arguments

```
/specdev-trinity <batch_id> --phase plan|impl|review [--auto-advance] [--soft-warn-rounds N]
```

- `<batch_id>`: milestone batch identifier (maps to `spec/impl_context/ms_<batch_id>_plan.json`).
- `--phase`: default `plan`. Selects sub-protocol (see sections below).
- `--auto-advance`: `--phase impl` only; disables the pause-between-groups (E10). Default off
  (pause is the default per K2 §11.3.1).
- `--soft-warn-rounds N`: integer (default 5). Soft-warn threshold for both impl and review
  loops. Each loop iteration checks `round >= --soft-warn-rounds` and pauses for human gating
  (E9). Compared with `>=` so soft-warn fires at N and every subsequent round, preventing
  unbounded looping.

---

## --phase plan (default)

Runs the review-fix loop against a milestone batch plan artifact, then gates on human
approval. Plan-phase (16a) only.

**Source spec:** K_agentification.md §5.2, §5.5, §9.

### Step 1 — Locate the plan artifact

Verify that `spec/impl_context/ms_<batch_id>_plan.json` exists:
```bash
specdev json structure spec/impl_context/ms_<batch_id>_plan.json
```

If the file does not exist, return an error and stop.

### Step 2 — Review-fix loop

Run the review-fix loop on the plan artifact using the same protocol as `/specdev-review`:

1. Dispatch `specdev-scope` with:
   ```json
   {
     "scope": "ms-<batch_id>-plan",
     "change_set": "recent_commits"
   }
   ```

2. For each round up to max_rounds=5:

   **2a. Dispatch all planned `specdev-reviewer` instances in parallel** (single message,
   multiple Agent tool calls). Dispatch ONE `specdev-reviewer` instance per `fan_out[]` entry
   from `specdev-scope`; this example shows the r1 slot (plan artifacts typically produce 1–2
   reviewers from fan-out). Pass the plan artifact path and scope per reviewer:
   ```json
   {
     "steps": ["ms-<batch_id>-plan"],
     "scope_kind": "plan_artifact",
     "reviewer_id": "<reviewer_id from fan_out[]>",
     "round": <current_round>,
     "scope": "ms-<batch_id>-plan",
     "flags": { "with_replay": false, "with_backlog": false },
     "artifact_path": "spec/impl_context/ms_<batch_id>_plan.json"
   }
   ```

   Each reviewer writes to:
   `.specdev/findings/findings_ms-<batch_id>-plan_<round>_r<reviewer_id>.json`

   (Ensure directory exists once: `mkdir -p .specdev/findings`.)

   **2b. Merge with the jq one-liner** (K_agentification.md §5.4, paths per §11.7):
   ```bash
   jq -s '{round: .[0].round, scope: .[0].scope, generated_at: (now | floor), findings: (map(.findings) | add | unique_by({kind, location, signature}))}' \
     .specdev/findings/findings_ms-<batch_id>-plan_<round>_r*.json > .specdev/findings/findings_ms-<batch_id>-plan_<round>.json
   ```

   **2c. Check convergence:**
   If `findings[]` is empty: CONVERGED. Proceed to Step 3.

   **2d. Dispatch fix:**
   Dispatch `specdev-impl` with `mode: "fix"` and the merged findings path.

   After Agent returns (blocker handling — canonical contract: `specdev-impl.md` § "Blocker emission protocol"):
   1. Parse return JSON.
   2. If `status != "blocker"`: check `gate_status` and `errors_remaining`; carry forward.
   3. If `status == "blocker"`:
      a. Validate shape: `questions[]` non-empty; each has `{id, question, header, options[2..4]}`.
         If malformed → HALT and surface to user (do NOT re-dispatch on a malformed payload).
         Malformed includes: `questions[]` empty, any entry missing required fields, edits
         written AND `status: "blocker"` simultaneously (timing-constraint violation).
      b. Persist: `mkdir -p .specdev/blockers/` then write
         `.specdev/blockers/blocker_ms-<batch_id>-plan_r<round>_<unix_ts>.json`.
      c. Chunk questions ≤4. Call `AskUserQuestion` once per chunk, sequentially.
         Collect answers keyed by `question.id`.
         If the user dismisses or does not answer an AskUserQuestion call (empty answer set
         returned), HALT immediately. Surface: "Blocker unresolved: user did not answer
         clarification questions. Re-invoke /specdev-trinity <batch_id> --phase plan to retry."
         Write a HALT artifact noting `aborted_by_user` to
         `.specdev/blockers/blocker_ms-<batch_id>-plan_aborted_<unix_ts>.json`.
         Do not re-dispatch.
      d. Build re-dispatch prompt: original fix dispatch input verbatim
         + `## User answers (from blocker bridge)` section listing each
           `{id, question, selected_label, selected_description, user_notes_if_any}`
         + `## Context from prior dispatch` section (agent's `context` field).
      e. Increment `blocker_round` counter (per-dispatch-site, scoped to a single subagent
         dispatch chain; starts at 0 on first dispatch; cap = 2 re-dispatches (counter values
         0, 1, 2); does not persist across skill invocations; resets to 0 at the start of each
         new outer review-fix round (R1/R2/.../R5)).
      f. If `blocker_round > 2`: HALT, surface to user (persistent blocking — no auto-retry).
      g. Fresh Agent dispatch with augmented prompt. Continue from step 1.
      Note: lossy re-dispatch — accepted cost; user answers are the ONLY persistence across
      the bridge. SendMessage-based clean resumption is deferred.
      Note: the Step 3 human gate (proceed/replay/abort) fires AFTER the entire review-fix
      loop exits, regardless of whether blockers occurred mid-loop. The blocker AskUserQuestion
      and the human gate AskUserQuestion are independent mechanisms.

   Increment round and continue.

3. If round 5 completes with findings remaining: HALT.

   Write the HALT artifact:
   `.specdev/findings/findings_ms-<batch_id>-plan_5_<unix_timestamp>.json`

   This is a timestamped copy of the round-5 merged findings file. It is the audit trail. Do not promote it to a canonical name. The timestamped file IS the record.

   Print:
   ```
   HALT: max_rounds=5 reached with unresolved findings.
   Findings path: .specdev/findings/findings_ms-<batch_id>-plan_5_<unix_timestamp>.json
   Finding count: <N> (<P0_count> P0, <P1_count> P1, <P2_count> P2)
   Human action required: proceed-with-gaps | replay | hand-edit then re-invoke /specdev-trinity <batch_id> --phase plan
   ```

   Do not silently accept partial convergence. HALT is a first-class verdict.

   Set verdict = "HALT (N unresolved findings)". Proceed to Step 3 regardless (HALT is a valid verdict to gate on).

### Step 3 — Human gate (K_agentification.md §5.5)

After the loop returns a verdict (CONVERGED or HALT), present an `AskUserQuestion` with
three options:

```
Plan phase review complete.
Verdict: <CONVERGED at round N | HALT at round 5 with N findings remaining>
[On HALT: Findings path: .specdev/findings/findings_ms-<batch_id>-plan_5_<unix_timestamp>.json]

How would you like to proceed?
A) Proceed — accept the plan and continue to downstream phases.
B) Replay — re-run the review-fix loop from round 1 (fresh state, no prior findings).
C) Abort — stop here; plan requires substantial rework before proceeding.
```

**On Proceed:** Return the verdict. Downstream 16b/16c are handled by
`/specdev-trinity --phase impl` and `/specdev-trinity --phase review`. This skill's job is complete.

**On Replay:** Re-run the loop from Step 2 (round 1, fresh state). Prior findings files
are NOT consulted — the reviewer sees the artifact's current state (K_agentification.md §5.6).

**On Abort:** Return. The user will rework the plan artifact manually before re-invoking.

---

## --phase impl

**Semantics deviation from K1 (deliberate):** K1 §3 sets `max_rounds=5` as a hard cap with
HALT as a first-class verdict. K2 `--phase impl` replaces this with **no hard cap,
soft-warn-at-N (default 5)** with explicit user gating to continue. Spec-phase agents
(`/specdev-review`, `/specdev-step`) continue to enforce K1's hard cap; only the code-phase
trinity uses soft-warn semantics. Rationale: `ms_phase2_newsletter_send` showed real code-phase
groups legitimately needing >5 rounds (K2 §11.3.1).

**Source spec:** K_agentification.md §11.3.1.

### Pre-flight

1. Dispatch `specdev-scope` with `{ "mode": "milestone_state", "batch_id": "<batch_id>" }`.
2. Parse `groups[]` and `derived_phase_position` from the output.
3. Identify unresolved groups: groups in state `{pending}` (and `executing` if observed).
   Groups in `{code_converged, blocked, verified, deferred}` are skipped.
4. Compute `milestone_start_ref` once before the first group dispatch:
   ```bash
   milestone_start_ref=$(git rev-parse HEAD)
   ```
   This ref is injected into every reviewer dispatch for supplemental git diff context.
   Git diff is typically empty in the normal uncommitted-work flow; `actions[].target` is
   the primary code-discovery path (see reviewer steps 5 and 5b).

### Per-group serial loop (in plan order)

For each unresolved group (serial — not parallel; inter-group file-overlap dependencies make
serial ordering safe per K2 §11.3.1):

**1. Execute**

Dispatch `specdev-trinity-impl` with:
```json
{
  "mode": "execute",
  "plan_path": "spec/impl_context/ms_<batch_id>_plan.json",
  "group_id": "<group_id>",
  "batch_id": "<batch_id>"
}
```
This applies the group's `implementation.actions[]` to host source code.

**2. Inner review-fix loop (no hard cap; soft-warn at `--soft-warn-rounds`, default 5)**

```
round = 1
repeat:
  mkdir -p .specdev/findings

  Dispatch specdev-trinity-reviewer with:
  {
    "milestone_id": "ms_<batch_id>",
    "batch_id": "<batch_id>",
    "group_id": "<group_id>",
    "scope_kind": "code_phase_group",
    "scope": "<group_id>",
    "round": <round>,
    "reviewer_id": "r1",
    "plan_path": "spec/impl_context/ms_<batch_id>_plan.json",
    "milestone_start_ref": "<milestone_start_ref>"
  }
  → writes .specdev/findings/findings_<group_id>_<round>_r1.json

  (Single reviewer per round for code_phase_group — no multi-reviewer fan-out at code phase.
   The per-reviewer file IS the merged file; copy to the canonical merged name:)
  cp .specdev/findings/findings_<group_id>_<round>_r1.json \
     .specdev/findings/findings_<group_id>_<round>.json

  If findings == [] → CONVERGED for this group; record round count; exit loop

  If round >= --soft-warn-rounds:
    Write HALT artifact:
      cp .specdev/findings/findings_<group_id>_<round>.json \
         .specdev/findings/findings_<group_id>_<round>_<unix_timestamp>.json
      (Timestamped copy is the audit trail. Do not promote it to a canonical name.)

    Print:
      HALT: --soft-warn-rounds (default 5) reached for group <group_id>.
      Findings path: .specdev/findings/findings_<group_id>_<round>_<unix_timestamp>.json
      Finding count: <N> (<P0_count> P0, <P1_count> P1, <P2_count> P2)
      Human action required: Continue N more rounds | Halt + hand-edit | Abort milestone
    AskUserQuestion → {Continue N more rounds | Halt + hand-edit | Abort milestone}
    On Continue: increment N target; continue loop
    On Halt: exit loop; record HALT-at-round-<round>; mark group not-converged
    On Abort: exit skill entirely

  Do not silently accept partial convergence. HALT is a first-class verdict.

  Dispatch specdev-trinity-impl with:
  {
    "mode": "fix",
    "findings_path": ".specdev/findings/findings_<group_id>_<round>.json",
    "group_id": "<group_id>",
    "batch_id": "<batch_id>"
  }
  round += 1
```

**3. After group converges or HALTs**

- Do NOT flip `implementation.status` — it stays `pending` throughout impl + review phases per
  E11 / §11.5. Operator flips to `verified` after deploy + live verification.
- Do NOT write to `plan.trinity_execution` — not a schema field this session per session decision.
- Convergence marker is the empty-findings file itself (written by `specdev-trinity-reviewer`).

**4. Pause for user inspection** (default; `--auto-advance` disables per E10).

### After all groups processed

Dispatch `specdev-scope` with `{ "mode": "milestone_state", "batch_id": "<batch_id>" }`.
Verify `derived_phase_position == impl_complete`.

Print: "ready for --phase review"

EXIT — does NOT auto-fire `--phase review`. User must manually invoke
`/specdev-trinity <batch_id> --phase review`. No AskUserQuestion at the phase boundary by
design (AskUserQuestion is reserved for HALT gating).

---

## --phase review

Milestone-wide convergence sweep. Re-runnable: always fresh round 1
(K §5.6 fresh-resume invariant carries forward). New empty-findings file written each
successful run; prior files stay as audit trail.

**Source spec:** K_agentification.md §11.3.2.

### Pre-flight

1. Dispatch `specdev-scope` with `{ "mode": "milestone_state", "batch_id": "<batch_id>" }`.
2. Check `derived_phase_position`.
3. Refuse if `derived_phase_position` is not in `{impl_complete, review_pending, review_complete}`.
   (Refuse if any non-deferred group is in `pending` state — impl must complete first.)

   Print refusal:
   ```
   REFUSED: --phase review requires impl_complete or later phase position.
   Current state: <derived_phase_position>
   Pending groups: <list of group_ids with state=pending>
   Action: Run /specdev-trinity <batch_id> --phase impl to completion first.
   ```
   Exit.
4. Compute `milestone_start_ref` once before the first review round:
   ```bash
   milestone_start_ref=$(git rev-parse HEAD)
   ```
   This ref is injected into every reviewer dispatch for supplemental git diff context.
   Git diff is typically empty in the normal uncommitted-work flow; `actions[].target` is
   the primary code-discovery path (see reviewer steps 5 and 5b).

### Milestone-wide loop (no hard cap; soft-warn at `--soft-warn-rounds`, default 5)

```
round = 1
repeat:
  mkdir -p .specdev/findings

  Dispatch specdev-trinity-reviewer with:
  {
    "milestone_id": "ms_<batch_id>",
    "batch_id": "<batch_id>",
    "scope_kind": "code_phase_milestone",
    "scope": "<batch_id>",
    "round": <round>,
    "reviewer_id": "r1",
    "plan_path": "spec/impl_context/ms_<batch_id>_plan.json",
    "milestone_start_ref": "<milestone_start_ref>"
  }
  → writes .specdev/findings/findings_<batch_id>_review_<round>_r1.json

  (Single reviewer per round per code_phase_milestone; per-reviewer file IS the merged file:)
  cp .specdev/findings/findings_<batch_id>_review_<round>_r1.json \
     .specdev/findings/findings_<batch_id>_review_<round>.json

  If findings == [] → CONVERGED; exit loop
    Convergence marker = .specdev/findings/findings_<batch_id>_review_<round>.json
    (the empty-findings file itself is the convergence signal)

  If round >= --soft-warn-rounds:
    Write HALT artifact:
      cp .specdev/findings/findings_<batch_id>_review_<round>.json \
         .specdev/findings/findings_<batch_id>_review_<round>_<unix_timestamp>.json
      (Timestamped copy is the audit trail.)

    Print:
      HALT: --soft-warn-rounds (default 5) reached for milestone <batch_id>.
      Findings path: .specdev/findings/findings_<batch_id>_review_<round>_<unix_timestamp>.json
      Finding count: <N> (<P0_count> P0, <P1_count> P1, <P2_count> P2)
      Human action required: Continue N more rounds | Halt + hand-edit | Abort review
    AskUserQuestion → {Continue N more rounds | Halt + hand-edit | Abort review}
    On Continue: increment N target; continue loop
    On Halt: exit loop; record HALT-at-round-<round>
    On Abort: exit skill entirely

  Do not silently accept partial convergence. HALT is a first-class verdict.

  Dispatch specdev-trinity-impl with:
  {
    "mode": "milestone_fix",
    "findings_path": ".specdev/findings/findings_<batch_id>_review_<round>.json",
    "batch_id": "<batch_id>",
    "plan_path": "spec/impl_context/ms_<batch_id>_plan.json"
  }
  → operates on union of target_file_patterns across milestone
  round += 1
```

### After convergence

**On CONVERGED:** perform evidence synthesis and write the `review` block automatically
(no gate before the verdict write). Then present the operator gate for anchor/roadmap sync.

#### Step C1 — Read checklist evidence

```bash
specdev json read spec/impl_context/ms_<batch_id>_plan.json '.plan.spec_alignment.checklist[]'
```

Data source is `actions[].evidence` in the plan artifact — NOT the convergence findings file
(which carries no schema data, only the empty-findings signal).

#### Step C2 — Derive `review` fields

**`fixture_status`** — `implemented_interfaces: []`, `test_results: []`, plus:
- `ci_status: "green"` — derived from ANCHORED evidence signals in `actions[].evidence.content`
  across all FR-linked checklist items. NOT a loose substring match.

  **Anchored-match rule (AC7 invariant):**
  1. Failure signals (any present in any FR-linked action ⇒ `ci_status: "red"`; HALT):
     `FAIL`, `FAILED`, `ERROR`, non-zero-exit indicator.
  2. Anchored success signal (required per FR-linked item; absence ⇒ HALT):
     - `^(pytest|tests?|ci|suite)\b.*\bPASS(ED)?\b` — test-runner context + PASS/PASSED
     - OR `\b[1-9]\d*\s+pass(ed)?\b` — explicit "N passed" counter (N ≥ 1; "0 passed" is not a success)
     - OR `\bexit\s+0\b` — explicit exit-code token
  3. Decoy evidence that must NOT satisfy the check: `"BYPASSED"` (no anchored signal),
     `"PASSED 0 of 3 suites"` (0 tests actually passed), `"compile PASS / tests FAIL"`
     (failure signal present). These are the exact AC7 regression cases.

  HALT with a clear error naming the evidence gap if any FR-linked item lacks an anchored
  success signal, shows a failure signal, or is ambiguous — do NOT fabricate green.

  **Status-deviation note (RB-WI8-A2):** In the agentified trinity flow,
  `implementation.status` remains `pending` (§11.5 — operator flips to `verified` after
  deploy + live verification). Therefore prompt_16c §4b criterion 2
  (`status == "verified"`) CANNOT be met literally for agentified runs. `satisfied: true`
  and `ci_status: "green"` are derived from ANCHORED evidence signals in
  `actions[].evidence.content`, NOT from `implementation.status`. A future reader must NOT
  "fix" this back to a literal status check — `status: "pending"` is correct and deliberate
  in the agentified flow.

**`semantic_review.fr_coverage`** — one entry per distinct FR referenced in the checklist.
  Two-branch filter (apply in order; HALT only if neither yields ≥1 entry):
  - **PRIMARY:** `spec_ref.type == "fr"` → `fr_id = spec_ref.id`.
    Real plans use `type="fr"` with kebab IDs (confirmed against fixtures); this is the
    normal path.
  - **DEFENSIVE:** `spec_ref.type == "doc" AND spec_ref.id == "vc:04-fr-list"` →
    contribute an entry ONLY when a resolvable kebab fr_id is derivable from the item's
    context (e.g., `description`, `milestone_ref`). If none is derivable, SKIP the item —
    do NOT fabricate an fr_id. Schema requires `^[a-z0-9]+(?:-[a-z0-9]+)*$`; a
    non-kebab or fabricated id is invalid and will fail spec-check.

  Per entry: `fr_id`, `satisfied: true` iff an anchored success signal is present (same
  rule as ci_status above), `evidence_summary` ≥20 chars from `actions[].evidence.content`,
  `checklist_ids` from matched items.

**`semantic_review.hallucinated_features`**: `[]` — empty asserts no untraced behavior.

**`review.ratings`**: default all five scores to 3; adjust upward on strong PASS evidence.

**`review.findings`**: `[]` (convergence = empty).

**`review.verdict`**: `"verified"` (per D-VERDICT; do NOT use `code_review_complete` or
  any invented value).

Write the complete `review` object atomically:
```bash
specdev json patch spec/impl_context/ms_<batch_id>_plan.json '.review' '<review-json>'
```
Confirm with spec-check after write:
```bash
specdev spec-check spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
```

**On HALT (review non-convergence or evidence failure):** write non-empty `review.findings`
(the HALT round's findings, or the named evidence gap) before exit:
```bash
specdev json patch spec/impl_context/ms_<batch_id>_plan.json '.review.findings' '<findings-json>'
```
Do NOT write `review.verdict`. Do NOT update anchor or roadmap files. Exit with HALT verdict.

#### Step C3 — Operator gate (anchor/roadmap sync)

After the `review.verdict` write, present AskUserQuestion:
```
Review converged. Update anchor and roadmap to done? (Y/N)
```
- On **Y**: patch three files:
  - `spec/16_impl_context.json` → `plan.milestone_index[<this milestone>].status = "done"`
  - `spec/14_roadmap.json` → corresponding milestone `status = "done"`
  - `spec/09_impl_plan.json` → corresponding milestone `status = "done"`
- On **N**: leave as-is.

This gate is deliberate and distinct from the "no AskUserQuestion at phase boundary" note in
--phase impl (which applies only to the impl→review phase transition). This AskUserQuestion
appears within --phase review post-convergence and is a required operator checkpoint.

- Do NOT write to `plan.trinity_review` — not a schema field this session.
- Convergence marker is the empty-findings file at
  `.specdev/findings/findings_<batch_id>_review_<round>.json`.
- `implementation.status` stays `pending` (operator phase pending — §11.5). Operator flips
  to `verified` after deploy + live verification.
- EXIT — return CONVERGED or HALT verdict.

### Re-runnability

`--phase review` is re-runnable: always fresh round 1 (K §5.6 fresh-resume invariant).
New empty-findings file written each successful run; prior files stay as audit trail.

---

## Flag discipline

Three-flag protocol for all validation/governance commands:
```
--repo-root ./devspec_toolkit --spec-root ./spec --git-root .
```

`specdev json` read/shape/edit subcommands: pass `--repo-root` only.
Exception: `specdev json resolve-pointers` accepts `--git-root`.
`canon-accept`: pass `--git-root`, NOT `--spec-root`.

Never read `spec/*.json` directly. Use `specdev json read` with a filter.

---

## What this skill does NOT do

- Does not author the plan artifact from scratch. The plan must already exist at
  `spec/impl_context/ms_<batch_id>_plan.json` before invoking any phase.
- Does not commit changes. User authorizes commits separately.
- Does not accept `--with-replay` or `--with-backlog` flags for `--phase plan` (plan artifacts
  are not subject to forward-replay in the same sense as spec steps).
- Does not silently accept partial convergence. HALT is a first-class verdict that gates on
  human decision.
- Does not auto-advance between phases. After `--phase impl` exits, the user manually invokes
  `/specdev-trinity <batch_id> --phase review`.
- Does not write to `plan.trinity_execution` or `plan.trinity_review` — these are proposed
  schema extensions (K2 §13 Day 1) that have NOT landed in this session. Convergence state is
  encoded entirely by the filesystem under `.specdev/findings/`.
- Does not flip `implementation.status` to `verified`. That is operator-driven (§11.5).
- Does not run impl group reviewers in parallel within a round. Code-phase groups are serial
  (E1: inter-group file-overlap dependencies; K2 §11.3.1).
- Does not skip AskUserQuestion on a blocker payload (--phase plan only; --phase impl and
  --phase review are outside alpha scope). Blocker questions must be presented to the user via
  the harness before re-dispatching.
