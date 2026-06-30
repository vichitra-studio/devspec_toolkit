---
name: specdev-step
description: >
  Author and review a single waterfall step. Dispatches specdev-impl (author mode) to emit
  a fresh spec/NN_*.json artifact from the step's prompt contract, then runs the full
  review-fix loop via the /specdev-review protocol. Returns CONVERGED or HALT.
  NOT when spec/NN_*.json already exists (→ /specdev-review for fixes/propagation, or
  specdev json insert/patch for new content). NOT for step 16 trinity phases (→ /specdev-trinity).
  NOT for context-only or read-only questions about a step (→ /specdev-context).
  Sibling skills: specdev-context (orientation/read), specdev-review (review existing artifact),
  specdev-trinity (trinity phases 16a/16b/16c).
  Trigger on: "author step NN", "implement step NN", "/specdev-step NN",
  or any request to produce a new spec artifact for a step that does not yet exist.
---

# /specdev-step — Waterfall Step Author + Review

Author mode: emits a fresh artifact. Review mode: uses the same review-fix loop as
`/specdev-review`. This skill composes both.

**Source spec:** K_agentification.md §5.2.

---

## Arguments

```
/specdev-step <NN>
```

- `<NN>`: step number, e.g. `04`, `13a`, `16`. Must match a step in the toolkit pipeline.

---

## Protocol

### Step 1 — Author the artifact

**Pre-dispatch existence check:** Before dispatching `specdev-impl`, probe for an existing artifact:
```bash
ls spec/<NN>_*.json 2>/dev/null
```
If a match is found, stop — do NOT dispatch `specdev-impl`. Print:
```
Artifact spec/<NN>_*.json already exists. /specdev-step only authors new artifacts.

Choose a path based on your intent:

  Sub-case A — Propagate an upstream change to this step:
    /specdev-review step-<NN> --with-replay
    (Replays forward-validation; surfaces downstream breakage from the upstream edit.)

  Sub-case B — Insert or add new content to this step:
    specdev json insert spec/<NN>_*.json '<path>' '<new-content-json>'
    then /specdev-review step-<NN>
    (Surgically adds the new field; /specdev-review then validates it.
    Do NOT use /specdev-step — it would attempt to re-author the whole artifact.)
```
If no existing artifact is found, proceed to dispatch below.

Dispatch `specdev-impl` with `mode: "author"`:

```json
{
  "mode": "author",
  "step": "<NN>",
  "repo_root": "./devspec_toolkit",
  "spec_root": "./spec",
  "git_root": "."
}
```

The agent:
1. Reads `devspec_toolkit/docs/prompts/shared_expectations.md` first.
2. Reads `devspec_toolkit/prompts/prompt_<NN>_*.md`.
3. Probes upstream artifact shapes and reads needed upstream content via `specdev json read`.
4. Emits `spec/<NN>_*.json` via Write (new file only).
5. Runs the scoped gate:
   ```bash
   specdev spec-check spec \
     --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
   ```
6. Returns structured summary `{mode: "author", edits_applied: ..., gate_status: ..., errors_remaining: [...]}`.

After Agent returns:
1. Parse return JSON.
2. If `status != "blocker"`: check `gate_status`. If `gate_status: "errors"` and errors cannot
   be resolved within specdev-impl's budget, surface them to the user. Do not proceed to the
   review step if the artifact is structurally invalid.
3. If `status == "blocker"` (see `specdev-impl.md` § "Blocker emission protocol"):
   a. Validate shape: `questions[]` non-empty; each has `{id, question, header, options[2..4]}`.
      If malformed → HALT and surface to user (do NOT re-dispatch on a malformed payload).
      Malformed includes: `questions[]` empty, any entry missing required fields, artifact
      written AND `status: "blocker"` simultaneously (timing-constraint violation).
   b. Persist audit trail:
      ```bash
      mkdir -p .specdev/blockers/
      ```
      Write `.specdev/blockers/blocker_step-<NN>_author_<unix_ts>.json` with the full payload.
   c. Chunk questions into groups of ≤4. Call `AskUserQuestion` once per chunk, sequentially.
      Collect all answers keyed by `question.id`.
      If the user dismisses or does not answer an AskUserQuestion call (empty answer set
      returned), HALT immediately. Surface: "Blocker unresolved: user did not answer
      clarification questions. Re-invoke /specdev-step <NN> to retry." Write a HALT artifact
      noting `aborted_by_user` to `.specdev/blockers/blocker_step-<NN>_author_aborted_<unix_ts>.json`.
      Do not re-dispatch. Re-invoke the skill to retry from round 1.
   d. Build re-dispatch prompt:
      - Original dispatch input verbatim.
      - PLUS a `## User answers (from blocker bridge)` section listing each
        `{id, question, selected_label, selected_description, user_notes_if_any}`.
      - PLUS a `## Context from prior dispatch` section quoting the agent's `context` field.
   e. Increment `author_blocker_round` counter (per-dispatch-site, scoped to this author
      dispatch chain, independent of fix-phase counter; starts at 0 on first dispatch; cap = 2
      re-dispatches (counter values 0, 1, 2); does not persist across skill invocations).
   f. If `author_blocker_round > 2`: HALT, surface to user (persistent blocking — no auto-retry).
   g. Fresh Agent dispatch with the augmented prompt. Continue from step 1.
   Note: lossy re-dispatch — accepted cost; the re-dispatched agent re-reads all context
   from scratch; user answers are the ONLY persistence across the bridge.
   SendMessage-based clean resumption is deferred.

If the author step returns with `gate_status: "errors"` and the errors cannot be resolved
within specdev-impl's budget, surface them to the user. Do not proceed to the review step
if the artifact is structurally invalid.

### Step 2 — Review-fix loop

After the author step completes with a clean gate, run the review-fix loop inline using
the same protocol as `/specdev-review`:

1. Dispatch `specdev-scope` with `{ "scope": "step-<NN>", "change_set": "git_diff" }`.
2. For each round up to max_rounds=5:
   a. Dispatch all planned `specdev-reviewer` instances in parallel (single message,
      multiple Agent tool calls).
   b. Merge with the jq one-liner (paths per K_agentification.md §11.7;
      ensure directory exists once: `mkdir -p .specdev/findings`):
      ```bash
      jq -s '{round: .[0].round, scope: .[0].scope, generated_at: (now | floor), findings: (map(.findings) | add | unique_by({kind, location, signature}))}' \
        .specdev/findings/findings_step-<NN>_<round>_r*.json > .specdev/findings/findings_step-<NN>_<round>.json
      ```
   c. If `findings[]` is empty: CONVERGED.
   d. Else dispatch `specdev-impl` with `mode: "fix"` and the merged findings path.
      After Agent returns (blocker handling — see `specdev-impl.md` § "Blocker emission protocol"):
      1. Parse return JSON.
      2. If `status != "blocker"`: check `gate_status` and `errors_remaining`; carry forward.
      3. If `status == "blocker"`:
         a. Validate shape: `questions[]` non-empty; each has `{id, question, header, options[2..4]}`.
            If malformed → HALT and surface to user.
            Malformed includes: `questions[]` empty, any entry missing required fields,
            edits applied AND `status: "blocker"` simultaneously (timing-constraint violation —
            blocker window is closed after the first edit).
         b. Persist: `mkdir -p .specdev/blockers/` then write
            `.specdev/blockers/blocker_step-<NN>_fix_r<round>_<unix_ts>.json`.
         c. Chunk questions ≤4. Call `AskUserQuestion` once per chunk, sequentially.
            Collect answers keyed by `question.id`.
            If the user dismisses or does not answer an AskUserQuestion call (empty answer set
            returned), HALT immediately. Surface: "Blocker unresolved: user did not answer
            clarification questions. Re-invoke /specdev-step <NN> to retry." Write a HALT
            artifact noting `aborted_by_user` to `.specdev/blockers/blocker_step-<NN>_fix_aborted_<unix_ts>.json`.
            Do not re-dispatch.
         d. Build re-dispatch prompt: original fix dispatch input verbatim
            + `## User answers (from blocker bridge)` section listing each
              `{id, question, selected_label, selected_description, user_notes_if_any}`
            + `## Context from prior dispatch` section (agent's `context` field).
         e. Increment `fix_blocker_round` counter (per-dispatch-site, scoped to this fix
            dispatch chain, independent of author-phase counter; starts at 0 on first dispatch;
            cap = 2 re-dispatches (counter values 0, 1, 2); does not persist across skill
            invocations; resets to 0 at the start of each new outer review-fix round (R1/R2/.../R5)).
         f. If `fix_blocker_round > 2`: HALT, surface to user.
         g. Fresh Agent dispatch with augmented prompt. Continue from step 1.
         Note: lossy re-dispatch — accepted cost; SendMessage-based resumption deferred.
   e. Increment round and continue.
3. If round 5 completes with findings remaining: HALT.

   Write the HALT artifact:
   ```
   .specdev/findings/findings_step-<NN>_5_<unix_timestamp>.json
   ```
   This is a timestamped copy of the round-5 merged findings file. It is the audit trail.
   Do not promote it to a canonical name. The timestamped file IS the record.

   Print:
   ```
   HALT: max_rounds=5 reached with unresolved findings.
   Findings path: .specdev/findings/findings_step-<NN>_5_<unix_timestamp>.json
   Finding count: <N> (<P0_count> P0, <P1_count> P1, <P2_count> P2)
   Human action required: proceed-with-gaps | replay | hand-edit then re-invoke /specdev-step <NN>
   ```

   Do not silently accept partial convergence. HALT is a first-class verdict.

The scope identifier for this step is `step-<NN>` (e.g. `step-04`, `step-13a`).

---

## Hand-off

After the review loop completes, report the final verdict:

```
/specdev-step <NN> complete.
Author gate: <clean | errors>
Review verdict: CONVERGED at round <N> | HALT at round 5
Artifact: spec/<NN>_*.json
Findings path (on HALT): .specdev/findings/findings_step-<NN>_5_<unix_timestamp>.json
```

---

## Flag discipline

Three-flag protocol for all validation/governance commands:
```
--repo-root ./devspec_toolkit --spec-root ./spec --git-root .
```

`specdev json` read/shape/edit subcommands: pass `--repo-root` only.
Exception: `specdev json resolve-pointers` accepts `--git-root`.
`canon-accept`: pass `--git-root`, NOT `--spec-root`.

Never read `spec/*.json` directly.

---

## What this skill does NOT do

- Does not review existing artifacts without authoring. Use `/specdev-review` for that.
- Does not manage trinity-plan gating. Use `/specdev-trinity --phase plan` for that.
- Does not handle 16b/16c. Plan-phase and Discovery-phase steps only
  (see K_agentification.md §9).
- Does not commit changes. User authorizes commits separately.
- Does not run reviewers sequentially within a round. Parallel dispatch is required.
- Does not skip AskUserQuestion on a blocker payload. Blocker questions must be presented
  to the user via the harness before re-dispatching.
- Does not author a step when `spec/<NN>_*.json` already exists (Step 1 pre-dispatch check
  short-circuits before any Agent dispatch). For upstream propagation, use
  `/specdev-review step-<NN> --with-replay`. For new content insertion, use
  `specdev json insert/patch` then `/specdev-review step-<NN>`.
