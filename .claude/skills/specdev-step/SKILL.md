---
name: specdev-step
description: >
  Author, extend, and review a single waterfall step. Dispatches specdev-impl in author mode
  to emit a fresh spec/NN_*.json from the step's prompt contract, or in author-extend mode to
  additively insert new operator-intent content into an EXISTING artifact, then runs the full
  review-fix loop via the /specdev-review protocol. Returns CONVERGED or HALT.
  When spec/NN_*.json exists and operator intent is propagation → `specdev stale`, then /specdev-review.
  When spec/NN_*.json exists and operator intent is to extend with NL-authored content →
  /specdev-step <NN> --extend "<intent>" (dispatches author-extend mode).
  NOT for step 16 trinity phases (→ /specdev-trinity). NOT for context-only or read-only
  questions about a step (→ /specdev-context).
  Sibling skills: specdev-context (orientation/read), specdev-review (review existing artifact),
  specdev-trinity (trinity phases 16a/16b/16c).
  Trigger on: "author step NN", "implement step NN", "/specdev-step NN",
  "/specdev-step NN --extend", "add content to step NN", or any request to produce or extend
  a spec artifact for a step.
---

# /specdev-step — Waterfall Step Author + Review

Author mode: emits a fresh artifact. Review mode: uses the same review-fix loop as
`/specdev-review`. This skill composes both.

---

## Arguments

```
/specdev-step <NN> [--extend "<intent>" [--seed <seed_path>]]
```

- `<NN>`: step number, e.g. `04`, `02a`, `16`. Must match a step in the toolkit pipeline.
- `--extend "<intent>"`: (optional) NL description of what to add to an EXISTING artifact.
  When supplied and the artifact already exists, dispatches author-extend mode instead of
  stopping. The subagent authors the full structured content from `intent` + prompt contract +
  upstream context — do NOT supply a pre-built content object.
- `--seed <seed_path>`: (optional, requires `--extend`) path to a seed/source doc the subagent
  reads as source material when authoring the new content.

---

## Protocol

### Step 1 — Author the artifact

**Migration worklist:** If `spec/extras/migration/worklist.json` exists, the host is in the middle of the
1.2.0 migration. Run `specdev align triage spec --step <NN>` first. Treat the `audience: agent` items as
input to this step's pass, ask the operator about each `audience: operator` item, and mark each item when
it is done: `specdev align triage spec --resolve <id> --note "<what was done>"`.

**Pre-dispatch existence check:** Before dispatching `specdev-impl`, probe for an existing artifact:
```bash
ls spec/<NN>_*.json 2>/dev/null
```
If a match is found, check whether `--extend` was supplied:

**If `--extend "<intent>"` was supplied** — the operator wants to add NL-authored content to the
existing artifact. Proceed to the **author-extend dispatch** below (do NOT print the stop message).

**If `--extend` was NOT supplied** — stop and print:
```
Artifact spec/<NN>_*.json already exists. /specdev-step only authors new artifacts.

Choose a path based on your intent:

  Sub-case A — Propagate an upstream change to this step:
    specdev stale --step <NN>
    then /specdev-review <NN>
    (Lists the links of this step that point at a node that changed above it. Read what
    changed, fix the step, then `specdev attest <node-id> --yes` for a link you checked;
    /specdev-review then validates the result.)

  Sub-case B — Insert known content directly (you already have the JSON):
    specdev json insert --step <NN> <collection-path> '<new-node-json>'   (a new node)
    specdev json patch --id <node-id> <field-path> '<value>'              (a field of a node)
    specdev json insert --id <node-id> <array-field> '<item>'             (an item of an array field)
    specdev json delete --id <node-id>                                    (a node)
    then /specdev-review <NN>
    (Surgically changes what you've already composed; /specdev-review then validates it.)

  Sub-case C — Add new content from a natural-language description:
    /specdev-step <NN> --extend "<what to add>" [--seed <seed_path>]
    (Dispatches author-extend mode; the subagent authors the structured content from your
    intent + the step prompt contract + upstream context, then inserts it and gates.)
```
If no existing artifact is found, proceed to the **author dispatch** below.

#### Author dispatch (new artifact)

**Readiness check:** before dispatching, run
```bash
specdev step ready <NN> --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
```
The step has no file yet, so the command checks its declared inputs (the `required_spec_inputs`
of `<NN>` in `tools/step_order.json`): each has a spec file and holds no pending replay (a suspect
link, or a coverage gap E740, E742 or E743 that the input step owns). Exit 0 prints
`step <NN>: ready`; go on. Exit 1 (E773) means an input has no spec file yet or has pending
replay, and the output names it (for example `step 04: no spec file yet` and `write step 04
first`, or, on a copy of the worked example with the files from step 08 on removed, `step 08: not
ready, 1 blocker`, `step 07: coverage gap E740: metric-reset-completion-rate`). The last line says
what to do first; when a link is suspect it can name a step above the inputs (for example `replay
step 01 first`), because the replay begins at the earliest suspect step. Print that output
and stop; do not dispatch.

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
4. Writes the whole artifact as a draft file outside `spec/` (`.specdev/drafts/step_<NN>.json`), then creates the step file with
   `specdev step create <NN> --from .specdev/drafts/step_<NN>.json --repo-root ./devspec_toolkit --spec-root ./spec --git-root .`
   (ids of sub-items may be left out; the command refuses a step that already has a file, E767).
   The agent never Writes into `spec/`.
5. Runs the scoped gate:
   ```bash
   specdev spec-check spec --step <NN> \
     --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
   ```
   Clean (`RESULT: CLEAR`) means no error owned by step `<NN>` and none new in an earlier
   step. Upstream debt and findings that wait on later steps are shown, not blocking.
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
      - PLUS, for each answer whose question has an `owner` other than `this-step` (a step id or
        `seed`), the instruction: record the answer as an open item with
        `specdev json insert --step <NN> .ambiguities '<item>'` (`description` is the question,
        `about` is the question's `about` ids, `decision` is the chosen label), and proceed
        without applying it to this step. `about` must name nodes the schema allows there
        (`specdev node candidates --kind ambiguity-item --field about` lists them); a node of the
        same step is refused (E767). Answers the step owns are applied as today.
      Each question carries `owner` and `about`; show both to the user with the question.
      The item is deleted with `specdev json delete --id <item-id>` once its decision is applied;
      `specdev upstream-backlog spec --repo-root ./devspec_toolkit` lists the open items by the step
      of their `about` nodes, for the pass that applies them.
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

#### Author-extend dispatch (extend existing artifact)

When `--extend "<intent>"` was supplied and the artifact already exists, dispatch
`specdev-impl` with `mode: "author-extend"`:

```json
{
  "mode": "author-extend",
  "target": "spec/<NN>_*.json",
  "intent": "<the --extend intent string verbatim>",
  "seed_path": "<value of --seed if supplied, else omit field>"
}
```

Pass `target` and `intent`. Pass `seed_path` only if `--seed` was supplied. Do NOT pass
`insert_pointer` — the subagent derives the correct jq-path from the prompt contract.
Do NOT build a content payload — the subagent does the authoring from `intent`.

The agent:
1. Reads `devspec_toolkit/docs/prompts/shared_expectations.md` first.
2. Probes the existing artifact structure via `specdev json structure` / `json keys`.
3. Reads `devspec_toolkit/prompts/prompt_<NN>_*.md`.
4. Authors the new structured content object from `intent` + optional `seed_path` + contract + upstream.
5. Applies via `specdev json insert --step <NN> <collection-path>` for a new node, and
   `specdev json patch|insert|delete --id <node-id>` for an existing one — NEVER Write.
6. Runs the scoped gate:
   ```bash
   specdev spec-check spec --step <NN> \
     --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
   ```
7. Returns structured summary `{mode: "author-extend", edits_applied: ..., gate_status: ..., errors_remaining: [...], pending_replay: ["<step>", ...]}`.

After Agent returns:
1. Parse return JSON.
2. If `status != "blocker"`: check `gate_status`. If `gate_status: "errors"` and errors cannot
   be resolved within specdev-impl's budget, surface them to the user. Do not proceed to the
   review step if the artifact is structurally invalid.
3. If `status == "blocker"` (see `specdev-impl.md` § "Blocker emission protocol"):
   a. Validate shape: `questions[]` non-empty; each has `{id, question, header, options[2..4]}`.
      If malformed → HALT and surface to user (do NOT re-dispatch on a malformed payload).
      Malformed includes: `questions[]` empty, any entry missing required fields, edits applied
      AND `status: "blocker"` simultaneously (timing-constraint violation).
   b. Persist audit trail:
      ```bash
      mkdir -p .specdev/blockers/
      ```
      Write `.specdev/blockers/blocker_step-<NN>_author-extend_<unix_ts>.json` with the full payload.
   c. Chunk questions into groups of ≤4. Call `AskUserQuestion` once per chunk, sequentially.
      Collect all answers keyed by `question.id`.
      If the user dismisses or does not answer an AskUserQuestion call (empty answer set returned),
      HALT immediately. Surface: "Blocker unresolved: user did not answer clarification questions.
      Re-invoke /specdev-step <NN> --extend ... to retry." Write a HALT artifact noting
      `aborted_by_user` to `.specdev/blockers/blocker_step-<NN>_author-extend_aborted_<unix_ts>.json`.
      Do not re-dispatch.
   d. Build re-dispatch prompt:
      - Original dispatch input verbatim.
      - PLUS a `## User answers (from blocker bridge)` section listing each
        `{id, question, selected_label, selected_description, user_notes_if_any}`.
      - PLUS a `## Context from prior dispatch` section quoting the agent's `context` field.
      - PLUS the `owner` / `about` instruction of the author dispatch above (step d): an answer
        owned by another step or by a seed is recorded as an open item in `.ambiguities`, not applied.
   e. Increment `author_extend_blocker_round` counter (per-dispatch-site, scoped to this
      author-extend dispatch chain, independent of author-phase and fix-phase counters;
      starts at 0 on first dispatch; cap = 2 re-dispatches (counter values 0, 1, 2); does not
      persist across skill invocations).
   f. If `author_extend_blocker_round > 2`: HALT, surface to user (persistent blocking — no auto-retry).
   g. Fresh Agent dispatch with the augmented prompt. Continue from step 1.
   Note: lossy re-dispatch — accepted cost; user answers are the ONLY persistence across the bridge.
4. On clean gate: surface the `pending_replay` list (step ids) from the return JSON to the user. It names
   the steps that `specdev stale` lists after the extend (links that point at a node the extend
   changed, and coverage gaps of later steps). The operator re-reads those steps, fixes them, and
   clears a link they checked with `specdev attest <node-id> --yes` (read the shown old and new
   text first; never edit the lock file by hand).

### Step 2 — Review-fix loop

After the author step completes with a clean gate, run the review-fix loop inline using
the same protocol as `/specdev-review`:

1. Dispatch `specdev-scope` with `{ "scope": "<NN>", "change_set": "git_diff" }`.
2. For each round up to max_rounds=5:
   a. Dispatch all planned `specdev-reviewer` instances in parallel (single message,
      multiple Agent tool calls).
   b. Merge with the jq one-liner (ensure directory exists once: `mkdir -p .specdev/findings`):
      ```bash
      jq -s '{"$schema": "vc:infra:findings", round: .[0].round, scope: .[0].scope, generated_at: (now | floor), findings: (map(.findings) | add | unique_by({kind, location, signature}))}' \
        .specdev/findings/findings_<NN>_<round>_r*.json > .specdev/findings/findings_<NN>_<round>.json
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
            + `## Context from prior dispatch` section (agent's `context` field)
            + the `owner` / `about` instruction of the author dispatch above (step d): an answer
              owned by another step or by a seed is recorded as an open item in `.ambiguities`,
              not applied. An open item whose decision a fix applies is deleted with
              `specdev json delete --id <item-id>`.
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
   .specdev/findings/findings_<NN>_5_<unix_timestamp>.json
   ```
   This is a timestamped copy of the round-5 merged findings file. It is the audit trail.
   Do not promote it to a canonical name. The timestamped file IS the record.

   Print:
   ```
   HALT: max_rounds=5 reached with unresolved findings.
   Findings path: .specdev/findings/findings_<NN>_5_<unix_timestamp>.json
   Finding count: <N> (<P0_count> P0, <P1_count> P1, <P2_count> P2)
   Human action required: proceed-with-gaps | replay | hand-edit then re-invoke /specdev-step <NN>
   ```

   Do not silently accept partial convergence. HALT is a first-class verdict.

The review scope for this step is `<NN>` (e.g. `04`, `02a`), as `/specdev-review` takes it; the findings files are named from it (`findings_<NN>_<round>.json`).

---

## Hand-off

After the review loop completes, run the step gate once more and read `step_gate` from its JSON:
```bash
specdev spec-check spec --step <NN> --json \
  --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
```
`step_gate.result` is `clear` or `blocked`. `blocking` holds the errors owned by step `<NN>` and the
new errors of earlier steps; only these block the step. `upstream_debt` (errors of earlier steps
that were there before), `pending` (a map from a later step to the findings that clear when that
step runs) and `waiting` (errors below a node that an open item is about) are shown and do not
block. List each finding by its node id.

Then report the final verdict:

```
/specdev-step <NN> complete.
Author gate: <clean | errors>
Review verdict: CONVERGED at round <N> | HALT at round 5
Artifact: spec/<NN>_*.json
Blocking (own, new upstream): <node ids, or none>
Pending (not blocking): upstream debt <node ids>; later steps <step: node ids>; waiting <node ids, with the open item ids>
Findings path (on HALT): .specdev/findings/findings_<NN>_5_<unix_timestamp>.json
```

---

## Flag discipline

Three-flag protocol for all validation/governance commands:
```
--repo-root ./devspec_toolkit --spec-root ./spec --git-root .
```

`specdev json` read/shape subcommands (`read`, `structure`, `keys`, ...) and `json patch|insert|delete`
on a file path: pass `--repo-root` only.
Exceptions: `specdev json resolve-pointers` accepts `--git-root`. The id forms, `json patch|insert|delete --id`
and `json insert --step`, take all three flags, as do `step create`, `step ready`, `stale`, `attest`,
`node status` and `node rename`.
`canon-accept`: pass `--git-root`, NOT `--spec-root`.

Never read `spec/*.json` directly. Never edit the lock file by hand: `specdev attest` writes it, and
only after you have read the old and new text it shows. `specdev node status <id> <lifecycle>` marks a
node `deprecated` (or `active` again); `not_applicable` is only for a step-14 node of a closed milestone
and is refused elsewhere (E705). `specdev node rename <old> <new>` renames a node and keeps the old id
as an alias. Deleting a node is `specdev json delete --id`.

---

## What this skill does NOT do

- Does not review existing artifacts without authoring. Use `/specdev-review` for that.
- Does not manage trinity-plan gating. Use `/specdev-trinity --phase plan` for that.
- Does not handle 16a/16b/16c. Discovery-phase steps only: a milestone's plan is created by
  `/specdev-trinity --phase plan` with `specdev step create 16a <batch> --from <draft>`, and the code
  phase writes only through `specdev plan record` and `specdev review record` (trinity phases belong to
  `/specdev-trinity`).
- Does not commit changes. User authorizes commits separately.
- Does not run reviewers sequentially within a round. Parallel dispatch is required.
- Does not skip AskUserQuestion on a blocker payload. Blocker questions must be presented
  to the user via the harness before re-dispatching.
- Does not author a fresh artifact when `spec/<NN>_*.json` already exists (Step 1
  pre-dispatch check short-circuits). For upstream propagation read `specdev stale --step <NN>`,
  then `/specdev-review <NN>`. For NL-intent-driven new content use
  `/specdev-step <NN> --extend "<intent>"` (author-extend mode). For direct JSON changes
  of already-composed content use `specdev json insert|patch|delete` (`--id` or `--step` forms),
  then `/specdev-review <NN>`.
