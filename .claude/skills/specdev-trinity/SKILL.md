---
name: specdev-trinity
description: >
  Orchestrate the trinity loop of one milestone (16a plan, 16b code-write, 16c code-review) via
  --phase plan|impl|review. Plan phase creates ms_<batch_id>_plan.json when it is missing
  (specdev step create 16a), reviews it, gates on user approval and starts the milestone. Impl
  phase executes each plan item serially via specdev-trinity-impl with a per-item review loop.
  Review phase runs the milestone-wide reviewer + milestone_fix loop, records the review
  (specdev review record), asks the person for sign-off and closes the milestone. A person
  decides sign-off, defer and manual verification; the skill never answers those prompts and
  writes no spec file by hand.
  Trigger on: "trinity plan", "trinity impl", "trinity review", "/specdev-trinity",
  any /specdev-trinity invocation, "16a", "16b", "16c", "batch <id> plan|impl|review".
---

# /specdev-trinity — Trinity Phase Orchestrator

Runs the three phases of the trinity loop for one milestone: 16a plan, 16b code-write, 16c
code-review. Select the phase with `--phase`; the default is `plan`. The step contracts are
`prompts/prompt_16a_impl_planner.md`, `prompt_16b_impl_coder.md` and `prompt_16c_impl_reviewer.md`
(read `docs/prompts/shared_expectations.md` before them). The packs are the spec source of the
three roles: the session renders the 16a packs when it authors the plan
(`specdev trace --recipe 16a <task-id>`); `specdev-trinity-impl` and `specdev-trinity-reviewer`
render their own (`specdev trace --recipe 16b <plan-item-id>`, `specdev trace --recipe 16c <milestone-id>`).

---

## Arguments

```
/specdev-trinity <batch_id> --phase plan|impl|review [--auto-advance] [--soft-warn-rounds N]
```

- `<batch_id>`: the plan file stem (`spec/impl_context/ms_<batch_id>_plan.json`): letters, digits, `_`, `-`.
- `--phase`: default `plan`. Selects the sub-protocol (see sections below).
- `--auto-advance`: `--phase impl` only; disables the pause between groups. Default off.
- `--soft-warn-rounds N`: integer (default 5). Soft-warn threshold for the impl and review
  loops: each iteration checks `round >= --soft-warn-rounds` and pauses for human gating, at N
  and every round after it.

---

## The milestone id

Every lifecycle command takes the roadmap milestone id (`ms-...`), never the batch id. Once the
plan file exists, dispatch `specdev-scope` with `{ "mode": "milestone_state", "batch_id": "<batch_id>" }`
(it runs `specdev milestone-state --batch-id <batch_id>` and returns its JSON) and read the
`milestone` key ONCE: that value is `<ms-id>` wherever this skill says so. The output's
`milestone_id` echoes the batch id and is not a milestone id (a batch id given to a milestone
command is E803).

If `milestone` is `null`, the plan has no `milestone` key (it was written before 1.2.0): stop. Tell
the operator what the toolkit prints for it, "E803 no plan names milestone <ms-id>: add it with
`specdev json patch <plan file> '.milestone' '"<milestone-id>"'` (the plan has no `milestone` key)", and that
the migration which writes the key may not be in this toolkit version yet (`specdev align` does not write it);
the operator runs that command or not; do nothing else with that plan.

## Who decides what

The skill runs the loop, `specdev milestone start`, `specdev verify run`, `specdev review record`
and `specdev milestone close`. A **person** decides:

- **sign-off** (`specdev milestone sign-off <ms-id>`) and **defer**
  (`specdev milestone defer <ms-id> --reason "<at most 300 characters>"`);
- whether a **manual-verification action** was carried out (it is then recorded with
  `specdev plan record <ITEM>/<action-id> --outcome done --note "operator confirmed"`), and whether a
  **manual fixture** or a **rule enforced by review** was attested (`specdev verify attest <node-id>...`;
  not `specdev attest`, which re-accepts links);
- **release**, the cut (`specdev release --tag <name>`): not a step of a milestone's loop; the person
  runs it and the skill never does.

Before each of them except the release: show `specdev status --milestone <ms-id>` first, ask the person
in the conversation, and run the command only on an explicit yes. When the host has installed ask rules, Claude Code also
asks before the command runs; that prompt is the person's and the skill never answers it. The skill
never runs one of these commands on its own judgement.

## The life of a milestone, in order

1. `specdev milestone-state --batch-id <batch_id>` (the id), then, when the plan is missing,
   `specdev step ready 16a` and `specdev step create 16a <batch_id> --from <draft>`.
2. Plan review and approval, then `specdev milestone start <ms-id>`.
3. Per plan item: `specdev-trinity-impl` (`specdev plan record`, `specdev verify run`) and a review loop.
4. The milestone-wide review loop.
5. `specdev verify run --milestone <ms-id> --stage ci`, `specdev verify attest` (a person decides),
   `specdev review record <ms-id> --verdict verified --findings-file <file>`, `specdev status --milestone <ms-id>`.
6. `specdev milestone sign-off <ms-id>` (a person decides), `specdev milestone close <ms-id> --check`,
   `specdev milestone close <ms-id>`.

---

## --phase plan (default)

Creates the plan when it is missing, runs the review-fix loop against it, then gates on human
approval and starts the milestone. Plan-phase (16a) only.

### Step 1 — Locate or create the plan

```bash
specdev json structure spec/impl_context/ms_<batch_id>_plan.json
```

If the file exists, read `<ms-id>` (section "The milestone id") and go to Step 2. If it does not:

1. Run `specdev step ready 16a --repo-root ./devspec_toolkit --spec-root ./spec --git-root .`.
   Exit 1 (E773) means a step upstream of the plan has no file, has suspect links or has coverage
   gaps (the output names which: for example `step 14 (11 blockers); fix the coverage gaps of step 14
   first`): show the output and stop; the step it names is authored or replayed first
   (`/specdev-step <NN>`, `/specdev-review <NN>`).
2. Render the 16a pack of each task of the milestone (`specdev trace <ms-id> --down --kinds task --json`
   lists the tasks of the roadmap milestone the operator named; `specdev trace --recipe 16a <task-id>`
   renders one) and follow `prompts/prompt_16a_impl_planner.md`: write the plan as a draft outside
   `spec/` (`.specdev/drafts/plan_<batch_id>.json`) and create the file with
   `specdev step create 16a <batch_id> --from .specdev/drafts/plan_<batch_id>.json` (`--dry-run`
   prints the report and writes nothing). Never write a file under `spec/` yourself. A milestone
   has one plan file: a second `step create 16a` for it is E767.
3. When `spec/16_impl_context.json` has no row for the milestone, add it as
   `prompts/prompt_16_impl_context.md` says (`specdev step create 16` for a missing anchor file;
   `specdev json insert --step 16 .plan.milestone_index '<row>'` for one more row).
4. `specdev spec-check spec --step 16a` must report `RESULT: CLEAR`. Then read `<ms-id>` and go on.

**Re-plan.** A 16a re-plan edits the existing plan by id (`prompt_16a` Output Rules). Afterwards run
`specdev attest <item-id> --yes` for each new item and each item whose `realises` changed (E761 names a
missing lock entry), and `specdev plan record --prune <ms-id>` only when `specdev spec-check` reports a
record (E700 on a `rec-NNNN`) whose item is gone. `--prune` also removes a record whose action is gone
from an item that still exists; nothing reports that one (no E700), so prune after deleting an action
that had a record. An upstream edit after approval makes links on
the plan's chain suspect: `specdev status --milestone <ms-id>` and `specdev milestone start` (E800) list
them and the close gate blocks on them (E763); the step authors replay what `specdev stale` lists, and
then the plan's links are attested again.

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
     "flags": { "with_backlog": false },
     "artifact_path": "spec/impl_context/ms_<batch_id>_plan.json"
   }
   ```

   Each reviewer writes to:
   `.specdev/findings/findings_ms-<batch_id>-plan_<round>_r<reviewer_id>.json`

   (Ensure directory exists once: `mkdir -p .specdev/findings`.)

   **2b. Merge with the jq one-liner** (the merged file keeps `"$schema": "vc:infra:findings"`; without it
   `specdev validate` gives E520 and `review record` refuses the file):
   ```bash
   jq -s '{"$schema": "vc:infra:findings", round: .[0].round, scope: .[0].scope, generated_at: (now | floor), findings: (map(.findings) | add | unique_by({kind, location, signature}))}' \
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
      Note: re-dispatch is lossy; user answers are the ONLY persistence across the bridge.
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

### Step 3 — Human gate

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

**On Proceed:** run `specdev milestone start <ms-id> --repo-root ./devspec_toolkit --spec-root ./spec --git-root .`
(pending or deferred becomes `in_progress`; a milestone already in progress is left as it is, exit 0). If it
refuses with E800 (no anchor row for the milestone, the milestone is done, or suspect links on its chain),
show the message and the owner-tagged lines under it and stop: the replay it names clears it, then start
again. On success return the verdict. Downstream 16b/16c are handled by `/specdev-trinity --phase impl` and
`/specdev-trinity --phase review`.

**On Replay:** Re-run the loop from Step 2 (round 1, fresh state). Prior findings files
are NOT consulted — the reviewer sees the artifact's current state.

**On Abort:** Return. The user will rework the plan artifact manually before re-invoking.

---

## --phase impl

The spec-phase loops (`/specdev-review`, `/specdev-step`) have a hard cap of five rounds. The code-phase
loops have **no hard cap: soft-warn at N (default 5)** with explicit user gating to continue, because
real code-phase groups can legitimately need more rounds.

### Pre-flight

1. Dispatch `specdev-scope` with `{ "mode": "milestone_state", "batch_id": "<batch_id>" }`. Read
   `<ms-id>` (`milestone`), `groups[]` and `derived_phase_position` from the output.
2. Run `specdev status --milestone <ms-id>`: its first line must be `milestone <ms-id>: in_progress`.
   Otherwise print `REFUSED: milestone <ms-id> is <status>; approve the plan with /specdev-trinity <batch_id>
   --phase plan (that starts the milestone)` and exit; when `status` itself refuses with E800 (the anchor row
   is missing; exit 1) show that message and stop, it names the row to add; for `done` print instead `REFUSED: milestone
   <ms-id> is done: it is closed and is not started again` (`milestone start` of a done milestone is E800).
3. Identify unresolved groups: groups in state `pending`. Groups in `{code_converged, blocked, deferred,
   wont_do}` are skipped; list each `blocked` group with its `blocking_amb_ids` (open items of the plan about a
   node of the item's chain) for the operator.
4. Compute `milestone_start_ref` once before the first group dispatch:
   ```bash
   milestone_start_ref=$(git rev-parse HEAD)
   ```
   This ref is injected into every reviewer dispatch for supplemental git diff context.
   Git diff is typically empty in the normal uncommitted-work flow; `actions[].target` is
   the primary code-discovery path (see reviewer steps 5 and 5b).

### Per-group serial loop (in plan order)

For each unresolved group (serial — not parallel; inter-group file-overlap dependencies make
serial ordering is safe):

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
The agent applies the group's `implementation.actions[]` to host source code and records each carried-out
action with `specdev plan record` (an action that names a verifier is proven by `specdev verify run`,
not recorded). It writes no spec file. Its return carries `recorded`, `awaiting_confirmation`,
`skipped_at_deploy`, `gate_status`, `errors_remaining` and `ambiguities_raised`:

- `awaiting_confirmation` lists manual-verification actions the agent could not record. Ask the person whether
  each was carried out (show `specdev status --milestone <ms-id>` first); on an explicit yes run
  `specdev plan record <group_id>/<action-id> --outcome done --note "operator confirmed"`; on no leave it
  unrecorded and say the item stays not executed.
- `skipped_at_deploy` lists actions marked `at_deploy`: nothing to do here (they hold nothing up; a deploy job
  records them with `plan record --at-deploy`).
- `errors_remaining` holding a refusal (E820 closed milestone, E821 unknown item or action): show it and stop.
- `ambiguities_raised` are open items `{id, description, about}` the agent already wrote into the plan. List them
  at the pause. They block the item until the operator answers them upstream and deletes each with
  `specdev json delete --id <amb-id>`; never edit them away otherwise.

**2. Inner review-fix loop (no hard cap; soft-warn at `--soft-warn-rounds`, default 5)**

```
round = 1
repeat:
  mkdir -p .specdev/findings

  Dispatch specdev-trinity-reviewer with:
  {
    "milestone_id": "<ms-id>",
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

- The convergence marker is the empty-findings file itself (written by `specdev-trinity-reviewer`);
  `specdev milestone-state` shows the group as `code_converged`. Nothing is written to the plan or the
  anchor row here.

**4. Pause for user inspection** (default; `--auto-advance` disables it).

### After all groups processed

Dispatch `specdev-scope` with `{ "mode": "milestone_state", "batch_id": "<batch_id>" }`.
Verify `derived_phase_position == impl_complete`.

Print: "ready for --phase review"

EXIT — does NOT auto-fire `--phase review`. User must manually invoke
`/specdev-trinity <batch_id> --phase review`. No AskUserQuestion at the phase boundary by
design (AskUserQuestion is reserved for HALT gating).

---

## --phase review

Milestone-wide convergence sweep, then the close sequence. Re-runnable: always fresh round 1. A new
empty-findings file is written each successful run; prior files stay as audit trail.

### Pre-flight

1. Dispatch `specdev-scope` with `{ "mode": "milestone_state", "batch_id": "<batch_id>" }`; read `<ms-id>`
   (`milestone`) and `derived_phase_position`.
2. Run `specdev status --milestone <ms-id>`: its first line must be `milestone <ms-id>: in_progress`.
3. Refuse if `derived_phase_position` is not in `{impl_complete, review_pending, review_complete}` or the status
   is not `in_progress`. (An active group in `pending` state means impl must complete first; `closed` means the
   milestone is already closed.)

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
    "milestone_id": "<ms-id>",
    "batch_id": "<batch_id>",
    "scope_kind": "code_phase_milestone",
    "scope": "<ms-id>",
    "round": <round>,
    "reviewer_id": "r1",
    "plan_path": "spec/impl_context/ms_<batch_id>_plan.json",
    "milestone_start_ref": "<milestone_start_ref>"
  }
  → writes .specdev/findings/findings_<ms-id>_<round>_r1.json  (its `scope` is the milestone id)

  (Single reviewer per round per code_phase_milestone; the per-reviewer file IS the merged file. Copy it to
   the name `specdev milestone-state` reads for the milestone-wide review:)
  cp .specdev/findings/findings_<ms-id>_<round>_r1.json \
     .specdev/findings/findings_<batch_id>_review_<round>.json

  If findings == [] → CONVERGED; exit loop
    Convergence marker = .specdev/findings/findings_<batch_id>_review_<round>.json
    (the empty-findings file of the newest round is the convergence signal; `milestone-state` shows `review_complete`)

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
    "milestone_id": "<ms-id>",
    "batch_id": "<batch_id>",
    "plan_path": "spec/impl_context/ms_<batch_id>_plan.json"
  }
  → operates on union of target_file_patterns across milestone
  round += 1
```

### After convergence

The converged file is `.specdev/findings/findings_<batch_id>_review_<round>.json` of the last round: it carries
`"$schema": "vc:infra:findings"`, `scope` the milestone id and an empty `findings` list. The tree must not
change between (1) and (6): a code edit after (1) sends the loop back to (1), because the evidence of
`verify run` is tied to the code tree (a changed tree is E811 `STALE_TREE`). The code tree counts every
untracked file that git does not ignore (the spec folder and the seed documents are left out), so after (1)
nothing is written into the repository outside the spec folder before `specdev milestone close` (a findings file written under `.specdev/` after `verify run` moved the tree on
a host that does not ignore `.specdev/`: `status` then listed both bindings `STALE_TREE`); write the
findings file first, as the loop above does.

0. The milestone's code must be committed (the close gate reads tracked files: E746). The skill never
   commits: if `git status` shows the milestone's files uncommitted, ask the operator to commit them now.
1. `specdev verify run --milestone <ms-id> --stage ci` runs the dev and ci bindings of the milestone and
   writes their evidence on the final tree. A `FAIL` line (exit 1) is not a findings file: send it back to the
   milestone-wide review loop (the reviewer's `specdev verify run --milestone <ms-id> --stage ci --no-record`
   spot-check turns it into a finding, and `milestone_fix` takes that), then start again from (1).
2. `specdev status --milestone <ms-id>`. Each line under "manual share" that reads
   "not attested; `specdev verify attest <node>`" is a manual fixture or a rule enforced by review: ask
   the person whether it was carried out and, for each yes, run `specdev verify attest <node-id>...`.
3. `specdev review record <ms-id> --verdict verified --findings-file .specdev/findings/findings_<batch_id>_review_<round>.json`.
4. `specdev status --milestone <ms-id>` again: its close-gate dry run lists what is still owed; only
   E814 (no sign-off) should remain.
5. Ask the person for the sign-off (the status of (4) is what they decide on). On an explicit yes run
   `specdev milestone sign-off <ms-id>`. If the code changed after a sign-off, show the status again (it
   prints each sign-off with its tree next to the code tree now) and ask whether it still stands.
6. `specdev milestone close <ms-id> --check` prints `the close gate passes; nothing written` or the
   errors that are still owed; then `specdev milestone close <ms-id>`. Afterwards `milestone-state` shows
   `derived_phase_position: closed` and `plan record` on this milestone is E820 (the plan is frozen).

| Outcome | Commands | Left on disk |
|---|---|---|
| converged | (1) to (6) | `review` block `verified`, evidence and attestation records, sign-off record, anchor row `done` with its close record, frozen plan |
| not converged (the operator halts at the soft-warn gate) | `specdev review record <ms-id> --verdict needs_work --findings-file <the timestamped halt copy>`; no sign-off, no close | `review` block `needs_work` (the next `review record` replaces it), the findings files under `.specdev/findings/`, anchor row `in_progress` |
| close refused | print the errors by owner and stop; see the next section | the sign-off record stays; the anchor row stays `in_progress` |
| re-plan (16a again) | the "Re-plan" rule of the plan phase, then 16b and 16c again | the old `review` block until the next `review record` replaces it |

`--phase review` is re-runnable: always fresh round 1.

## When a command refuses

Show the message as printed (and the owner-tagged lines under it), say what it means and run what clears it; a
refusal is never answered by writing a spec file.

| Code | It means | What clears it |
|---|---|---|
| E800 (`milestone start`) | no anchor row for the id, the milestone is done, or suspect links on its chain | add the row with the `specdev json insert --step 16 .plan.milestone_index '<row>'` the message prints (a real prefix and summary in place of its placeholders; plan phase, Step 1; the milestone must be in the roadmap); a done milestone stays done; for suspect links the step authors replay what `specdev stale` lists, then start again |
| E803 | a batch id was given, or no plan names the milestone | use the `milestone` value of `milestone-state`; a plan with no `milestone` key stops the skill |
| E810 | a task criterion has no plan item that realises it | a 16a re-plan adds the item, then 16b and 16c again |
| E811 | a criterion is unproven (`NO_EVIDENCE`, `STALE_TREE`, `STALE_HASH`, or the verifier has no binding) | `specdev verify run <binding> --stage dev` as printed, or step (1); a missing binding is `specdev verify bind <verifier-id> --command CMD --guard REGEX`, an author's decision: ask |
| E812 | a plan item is not executed | `--phase impl` for the item (`specdev plan record`) |
| E813 | no review is recorded, or its verdict is not `verified` | the review loop, then `specdev review record <ms-id> --verdict verified ...` |
| E814 | no sign-off record | ask the person for the sign-off |
| E746 | a scaffold row names a file that is not tracked | ask the operator to commit the file |
| E632 | an open item is still in the plan | the operator answers it upstream and deletes it: `specdev json delete --id <amb-id>` |
| E763 | a suspect link on the milestone's chain | the step authors replay what `specdev stale` lists, then `specdev attest <node-id> --yes`; then again from (1) (the attest changes hashes) |
| E820 | the plan is frozen (the milestone is closed) | nothing; no record can be written |
| E821 | the address names no item or action | the message lists the item's actions: use one of those ids; an item with no action at all is a planner's gap: the message names the `specdev json insert --id <item> .implementation.actions '<action>'` that adds one (a 16a re-plan), then record it |
| E822 | the action names a verifier | its proof is `specdev verify run <binding>`, not a record |
| E823 | the findings file is invalid | `specdev validate <file> --repo-root ./devspec_toolkit`, fix the file (`"$schema": "vc:infra:findings"`), record again |
| E767 | a second plan file for the milestone | edit the plan by id (`specdev json patch\|insert\|delete --id`) |

---

## Flag discipline

Three-flag protocol for every command this skill runs except the two below:
```
--repo-root ./devspec_toolkit --spec-root ./spec --git-root .
```
That covers `milestone` (`start`, `defer`, `sign-off`, `close`), `plan record`, `review record`, `status`,
`verify` (`run`, `bind`, `attest`), `step`, `trace`, `attest`, `stale`, `spec-check` and `milestone-state`.

`specdev json` read/shape/edit subcommands and `specdev validate`: pass `--repo-root` only.

Never read `spec/*.json` directly. Use `specdev json read` with a filter or a pack.

---

## What this skill does NOT do

- Does not write a file under `spec/` by hand: a new plan is `specdev step create 16a`, records are
  `specdev plan record`, the `review` block is `specdev review record`, a milestone's status is
  `specdev milestone start|defer|close`.
- Does not decide sign-off, defer, a manual action or a manual attestation, and never answers the prompt of
  one (section "Who decides what").
- Does not commit changes. The operator authorizes commits separately.
- Does not run `step ready` for the code phase (16b, 16c): the gate that opens it is `milestone start` and
  the gate that ends it is the close gate.
- Does not silently accept partial convergence. HALT is a first-class verdict that gates on
  human decision.
- Does not auto-advance between phases. After `--phase impl` exits, the user manually invokes
  `/specdev-trinity <batch_id> --phase review`.
- Does not run impl group reviewers in parallel within a round. Code-phase groups are serial
  (inter-group file-overlap dependencies).
- Does not skip AskUserQuestion on a blocker payload (`--phase plan` only). Blocker questions must be
  presented to the user via the harness before re-dispatching.
