---
name: specdev-trinity
description: >
  Orchestrate the trinity loop of one milestone (16a plan, 16b code-write, 16c code-review) via
  --phase plan|impl|review. Each phase is a `specdev loop` run that this skill pumps: the plan phase
  authors ms_<batch_id>_plan.json when it is missing and reviews it, gates on user approval and starts
  the milestone; the impl phase executes and reviews each plan item in order; the review phase runs the
  milestone-wide review, records it (specdev review record), asks the person for sign-off and closes
  the milestone. A person decides sign-off, defer and manual verification; the skill never answers
  those prompts and writes no spec file by hand.
  Trigger on: "trinity plan", "trinity impl", "trinity review", "/specdev-trinity",
  any /specdev-trinity invocation, "16a", "16b", "16c", "batch <id> plan|impl|review".
---

# /specdev-trinity — Trinity Phase Orchestrator

Runs the three phases of the trinity loop for one milestone: 16a plan, 16b code-write, 16c
code-review. Select the phase with `--phase`; the default is `plan`. The step contracts are
`prompts/prompt_16a_impl_planner.md`, `prompt_16b_impl_coder.md` and `prompt_16c_impl_reviewer.md`.
The packs are the spec source of the three roles, and each agent renders its own from its brief:
`specdev trace --recipe 16a <task-id>` (the plan author), `specdev trace --recipe 16b <plan-item-id>`
(`specdev-trinity-impl`), `specdev trace --recipe 16c <milestone-id>` (`specdev-trinity-reviewer`).

The loop of every phase is kept by `specdev loop`: it hands out the briefs, checks every file an agent writes,
and decides each next action. This skill does a phase's preflight, pumps its run (section "The pump"), and
does the hand-off.

---

## Arguments

```
/specdev-trinity <batch_id> --phase plan|impl|review [--auto-advance] [--soft-warn-rounds N]
```

- `<batch_id>`: the plan file stem (`spec/impl_context/ms_<batch_id>_plan.json`): letters, digits, `_`, `-`.
- `--phase`: default `plan`. Selects the sub-protocol (see sections below).
- `--auto-advance`: `--phase impl` only; disables the pause between groups. Default off.
- `--soft-warn-rounds N`: integer (default 5). The rounds a code run may use before it asks the person
  whether to continue; it is passed to the run as `--cap N`. A plan run ends at 5 rounds.

---

## The milestone id

Every lifecycle command takes the roadmap milestone id (`ms-...`), never the batch id. Once the
plan file exists, run `specdev milestone-state --batch-id <batch_id> --repo-root ./devspec_toolkit --spec-root ./spec --git-root .`
and read the `milestone` key ONCE: that value is `<ms-id>` wherever this skill says so. The output's
`milestone_id` echoes the batch id and is not a milestone id (a batch id given to a milestone
command is E803).

If `milestone` is `null`, the plan has no `milestone` key (it was written before 1.2.0): stop. Tell
the operator what the toolkit prints for it, "E803 no plan names milestone <ms-id>: add it with
`specdev json patch <plan file> '.milestone' '"<milestone-id>"'` (the plan has no `milestone` key)", and that
on a host not yet migrated to 1.2.0 the migration writes the key (`specdev align apply spec --auto`, a person
confirms it); the operator runs one of the two or not; do nothing else with that plan.

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
   `specdev step ready 16a` and a plan run that authors it (`specdev step create 16a <batch_id> --from <draft>`).
2. Plan review and approval, then `specdev milestone start <ms-id>`.
3. Per plan item: a `code-group` run (`specdev-trinity-impl`: `specdev plan record`, `specdev verify run`; then its review).
4. The milestone-wide review: a `code-milestone` run.
5. `specdev verify run --milestone <ms-id> --stage ci`, `specdev verify attest` (a person decides),
   `specdev review record <ms-id> --verdict verified --findings-file <file>`, `specdev status --milestone <ms-id>`.
6. `specdev milestone sign-off <ms-id>` (a person decides), `specdev milestone close <ms-id> --check`,
   `specdev milestone close <ms-id>`.

---

## --phase plan (default)

Authors the plan when it is missing, runs the review-fix loop against it, then gates on human
approval and starts the milestone. Plan-phase (16a) only.

### Step 1 — Locate the plan, or prepare its authoring

```bash
specdev json structure spec/impl_context/ms_<batch_id>_plan.json
```

If the file exists, read `<ms-id>` (section "The milestone id") and go to Step 2. If it does not, `<ms-id>` is
the roadmap milestone the operator named, and:

1. When `spec/16_impl_context.json` has no row for the milestone, add it as
   `prompts/prompt_16_impl_context.md` says (`specdev step create 16` for a missing anchor file;
   `specdev json insert --step 16 .plan.milestone_index '<row>'` for one more row). The row comes first: the
   plan's author stops without it.
2. Run `specdev step ready 16a --repo-root ./devspec_toolkit --spec-root ./spec --git-root .`.
   Exit 1 (E773) means a step upstream of the plan has no file, has suspect links or has coverage
   gaps (the output names which: for example `step 14 (11 blockers); fix the coverage gaps of step 14
   first`): show the output and stop; the step it names is authored or replayed first
   (`/specdev-step <NN>`, `/specdev-review <NN>`, `/specdev-pass --replay`).
3. Go to Step 2 with `--author --batch <batch_id>`. The author (`specdev-impl`, from its brief) renders the 16a
   pack of each task of the milestone, follows `prompts/prompt_16a_impl_planner.md`, writes the plan as a draft
   outside `spec/` and creates the file with
   `specdev step create 16a <batch_id> --from .specdev/drafts/plan_<batch_id>.json`. Never write a file under
   `spec/` yourself. A milestone has one plan file: a second `step create 16a` for it is E767.

**Re-plan.** A 16a re-plan edits the existing plan by id (`prompt_16a` Output Rules). Afterwards run
`specdev attest <item-id> --yes` for each new item and each item whose `realises` changed (E761 names a
missing lock entry), and `specdev plan record --prune <ms-id>` only when `specdev spec-check` reports a
record (E700 on a `rec-NNNN`) whose item is gone. `--prune` also removes a record whose action is gone
from an item that still exists; nothing reports that one (no E700), so prune after deleting an action
that had a record. An upstream edit after approval makes links on
the plan's chain suspect: `specdev status --milestone <ms-id>` and `specdev milestone start` (E800) list
them and the close gate blocks on them (E763); the step authors replay what `specdev stale` lists, and
then the plan's links are attested again.

### Step 2 — The plan run

```bash
specdev loop start --kind plan <ms-id> [--author --batch <batch_id>] --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
```

It prints `{"run_id": ..., "resumed": ...}`; on `"type": "error"` print the message and stop. Pump the run
(section "The pump"). The tool runs `specdev spec-check spec --step 16a` itself and takes the plan's own errors as
findings. An author or fixer asks nothing: what the spec does not settle it records as an open item of the plan
(`.plan.ambiguities`), and the report lists it.

### Step 3 — Human gate

After the run's `done` (any verdict but `HALT(agent_failed)`, which stops here with its report), present an
`AskUserQuestion` with three options:

```
Plan phase review complete.
Verdict: <CONVERGED | HALT(cap) with N findings open | HALT(operator)>
Report: <the done action's report>

How would you like to proceed?
A) Proceed — accept the plan and continue to downstream phases.
B) Replay — run the review-fix loop again on the plan as it is now.
C) Abort — stop here; plan requires substantial rework before proceeding.
```

**On Proceed:** run `specdev milestone start <ms-id> --repo-root ./devspec_toolkit --spec-root ./spec --git-root .`
(pending or deferred becomes `in_progress`; a milestone already in progress is left as it is, exit 0). If it
refuses with E800 (no anchor row for the milestone, the milestone is done, or suspect links on its chain),
show the message and the owner-tagged lines under it and stop: the replay it names clears it, then start
again. On success return the verdict. Downstream 16b/16c are handled by `/specdev-trinity --phase impl` and
`/specdev-trinity --phase review`.

**On Replay:** go to Step 2 again (a new run; it reads the plan's current state).

**On Abort:** Return. The user will rework the plan artifact manually before re-invoking.

---

## --phase impl

A plan run ends at five rounds. A code run has **no hard cap: it asks at N rounds (default 5)** whether to
continue, because real code-phase groups can legitimately need more rounds.

### Pre-flight

1. Run `specdev milestone-state --batch-id <batch_id> --repo-root ./devspec_toolkit --spec-root ./spec --git-root .`. Read
   `<ms-id>` (`milestone`), `groups[]` and `derived_phase_position` from the output.
2. Run `specdev status --milestone <ms-id>`: its first line must be `milestone <ms-id>: in_progress`.
   Otherwise print `REFUSED: milestone <ms-id> is <status>; approve the plan with /specdev-trinity <batch_id>
   --phase plan (that starts the milestone)` and exit; when `status` itself refuses with E800 (the anchor row
   is missing; exit 1) show that message and stop, it names the row to add; for `done` print instead `REFUSED: milestone
   <ms-id> is done: it is closed and is not started again` (`milestone start` of a done milestone is E800).
3. Identify unresolved groups: groups in state `pending`. Groups in `{code_converged, blocked, deferred,
   wont_do}` are skipped; list each `blocked` group with its `blocking_amb_ids` (open items of the plan about a
   node of the item's chain) for the operator.
4. Compute `milestone_start_ref` once, before the first group: `milestone_start_ref=$(git rev-parse HEAD)`. Every
   run of this phase gets it as `--base-ref`, and the reviewers get it in their briefs for `git diff`.

### Per-group serial loop (in plan order)

For each unresolved group, one at a time (groups share files, so they are never run in parallel):

```bash
specdev loop start --kind code-group <ms-id>/<group_id> --execute --base-ref <milestone_start_ref> --cap <soft-warn-rounds> --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
```

Pump the run (section "The pump"). The run begins with one execute dispatch: `specdev-trinity-impl` applies the
group's `implementation.actions[]` to host source code and records each carried-out action with
`specdev plan record` (an action that names a verifier is proven by `specdev verify run`, not recorded). It writes
no spec file. When an earlier run of the group already executed it, the tool skips the execute dispatch. Then the
review-fix loop of the group runs, one reviewer per round (`specdev-trinity-reviewer`).

The questions a group run can ask (the pump's `ask`):

- A manual-verification action the executor could not record (its outcome's `awaiting_confirmation`). Show
  `specdev status --milestone <ms-id>` first. Ask the person whether each was carried out; on an explicit yes run the
  command the option carries, `specdev plan record <group_id>/<action-id> --outcome done --note "operator confirmed"`;
  on no it stays unrecorded and the item stays not executed.
- The cap is reached with findings open: `Continue 2 more rounds`, `Continue 5 more rounds` or `Stop`.
- Two fixes failed for a finding: two options, `Try once more` (the person's guidance goes in the notes) and `Leave as is`.
  For a P0 finding of a code run, and for every gate or link finding, the second option is `Stop the run` instead of `Leave as is`.

After the run's `done`:

| Verdict | Then |
|---|---|
| `CONVERGED` | The tool wrote the empty findings file `specdev milestone-state` reads (`.specdev/findings/findings_<group_id>_<N>.json`): the group is `code_converged`. Nothing is written to the plan or the anchor row here |
| `HALT(blocked)` | An open item of the plan holds the group (`open_items` of the action lists the ids). List them: they block the item until the operator answers them upstream and deletes each with `specdev json delete --id <amb-id>`; never edit them away otherwise. The group stays `pending`; go on with the next group |
| `HALT(operator)` | The person stopped at the cap or at a finding: the group is not converged; the findings left are in the done action's `final`. Hand-edit and run the phase again, or abort. Go on with the next group |
| `HALT(agent_failed)` | An agent refused (the report holds the refusal: E820 closed milestone, E821 unknown item or action) or wrote no usable file twice. Show the report and stop the phase |

Then **pause for user inspection** (default; `--auto-advance` disables it). The executor's outcome also names
`recorded` and `skipped_at_deploy` (actions marked `at_deploy`: nothing to do here; a deploy job records them with
`plan record --at-deploy`); the report lists both.

### After all groups processed

Run `specdev milestone-state --batch-id <batch_id>` again. When `derived_phase_position == impl_complete`, print:
"ready for --phase review". Otherwise list the groups that are still `pending` or `blocked`, each with its reason.

EXIT — does NOT auto-fire `--phase review`. User must manually invoke
`/specdev-trinity <batch_id> --phase review`.

---

## --phase review

Milestone-wide review run, then the close sequence. Re-runnable: each time is a new run. A new
empty-findings file is written by each run that converges; prior files stay as audit trail.

### Pre-flight

1. Run `specdev milestone-state --batch-id <batch_id> --repo-root ./devspec_toolkit --spec-root ./spec --git-root .`; read `<ms-id>`
   (`milestone`) and `derived_phase_position`.
2. Run `specdev status --milestone <ms-id>`: its first line must be `milestone <ms-id>: in_progress`.
3. Refuse if `derived_phase_position` is not in `{impl_complete, review_pending, review_complete}` or the status
   is not `in_progress`. (An active group in `pending` state means impl must complete first; `closed` means the
   milestone is already closed; `operator_pending` means the review converged and an open item of the plan
   still blocks a group.)

   Print refusal (every position but `operator_pending`):
   ```
   REFUSED: --phase review requires the phase position impl_complete, review_pending or review_complete.
   Current state: <derived_phase_position>
   Pending groups: <list of group_ids with state=pending>
   Action: Run /specdev-trinity <batch_id> --phase impl to completion first.
   ```
   Print refusal (`operator_pending`):
   ```
   REFUSED: an open item of the plan blocks a group; the review cannot close the milestone.
   Current state: operator_pending
   Blocked groups: <group_id: blocking_amb_ids, for each group whose blocking_amb_ids is not empty>
   Action: answer each open item in the step that owns its node, delete the item
   (specdev json delete --id <amb-id>), then run /specdev-trinity <batch_id> --phase review again.
   ```
   Exit.
4. Compute `milestone_start_ref` once: `milestone_start_ref=$(git rev-parse HEAD)`.

### The milestone run

```bash
specdev loop start --kind code-milestone <ms-id> --base-ref <milestone_start_ref> --cap <soft-warn-rounds> --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
```

Pump the run (section "The pump"). One `specdev-trinity-reviewer` reads the milestone's code each round (the files
of the plan's `target_file_patterns` and `milestone_supporting_files`) and runs
`specdev verify run --milestone <ms-id> --stage ci --no-record`; `specdev-trinity-impl` fixes what it finds. The
run asks the cap question and the two-fixes question as a group run does.

| Verdict | Then |
|---|---|
| `CONVERGED` | The tool wrote `.specdev/findings/findings_<batch_id>_review_<N>.json` with an empty `findings` list (`milestone-state` shows `review_complete`). Go to "After convergence" with the done action's `final` as `<final>` |
| `HALT(blocked)` | The plan holds an open item (`open_items` lists the ids): no review is recorded over an open item. Print them and the action of the `operator_pending` refusal above, and stop |
| `HALT(operator)` with findings left | `specdev review record <ms-id> --verdict needs_work --findings-file <final>`; no sign-off, no close |
| `HALT(operator)` with nothing left, `HALT(agent_failed)` | Nothing is recorded. Show the report and stop |

### After convergence

The converged file is the run's `final.json` (`<final>`): it carries
`"$schema": "vc:infra:findings"`, `scope` the milestone id and an empty `findings` list. The tree must not
change between (1) and (6): a code edit after (1) sends the loop back to (1), because the evidence of
`verify run` is tied to the code tree (a changed tree is E811 `STALE_TREE`). The code tree counts every
untracked file that git does not ignore (the spec folder and the seed documents are left out), so after (1)
nothing is written into the repository outside the spec folder before `specdev milestone close` (a findings file written under `.specdev/` after `verify run` moved the tree on
a host that does not ignore `.specdev/`: `status` then listed both bindings `STALE_TREE`); the
run writes its files before its `done`, so they are there first.

0. The milestone's code must be committed (the close gate reads tracked files: E746). The skill never
   commits: if `git status` shows the milestone's files uncommitted, ask the operator to commit them now.
1. `specdev verify run --milestone <ms-id> --stage ci` runs the dev and ci bindings of the milestone and
   writes their evidence on the final tree. A `FAIL` line (exit 1) is not a findings file: send it back to the
   milestone-wide review loop (a new milestone run: the reviewer's `specdev verify run --milestone <ms-id> --stage ci --no-record`
   spot-check turns it into a finding, and the fixer takes that), then start again from (1).
2. `specdev status --milestone <ms-id>`. Each line under "manual share" that reads
   "not attested; `specdev verify attest <node>`" is a manual fixture or a rule enforced by review: ask
   the person whether it was carried out and, for each yes, run `specdev verify attest <node-id>...`.
3. `specdev review record <ms-id> --verdict verified --findings-file <final>`.
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
| not converged (the operator stops at the cap) | `specdev review record <ms-id> --verdict needs_work --findings-file <final>`; no sign-off, no close | `review` block `needs_work` (the next `review record` replaces it), the run folder under `.specdev/runs/` and the findings files under `.specdev/findings/`, anchor row `in_progress` |
| close refused | print the errors by owner and stop; see the next section | the sign-off record stays; the anchor row stays `in_progress` |
| re-plan (16a again) | the "Re-plan" rule of the plan phase, then 16b and 16c again | the old `review` block until the next `review record` replaces it |

`--phase review` is re-runnable: each time is a new run.

## The pump

`<roots>` is `--repo-root ./devspec_toolkit --spec-root ./spec --git-root .` on every `specdev loop` and `specdev pass` command.
The tool keeps the loop: it decides every next action, checks every file an agent writes, runs the step gate and
`specdev stale`, and writes the report. This session only carries out the action it prints.

1. Call `specdev loop next <run-id> <roots>`. It prints one JSON action. Do what its `type` says:
   - `dispatch`: start one subagent per entry of `entries`, all in one message. The subagent type is the entry's
     `agent`; the prompt is exactly `Read and follow <the entry's brief>`. Add nothing to the prompt. When all have
     returned, go to 1.
   - `wait`: files are missing, or arrived and failed the tool's checks (`refused` gives the reason for each). If a subagent of this session is still running, wait for it, then go to 1. If none is
     running (all returned, or this is a new session), call `specdev loop next <run-id> --redispatch <roots>` and treat
     its action as in 1.
   - `ask`: put every question of `questions` to the operator with AskUserQuestion, as given (question text, option
     labels and descriptions), at most 4 questions per call. If a chosen option carries a `command`, run it now. Write
     one JSON object `{"<question id>": {"label": "<chosen label>", "notes": "<the operator's notes or free text>"}}`
     with every answer to `answers_path`, call `specdev loop next <run-id> --answers <answers_path> <roots>`, and
     treat its action as in 1. If the operator dismisses a question, stop here and print
     `Stopped at a question; run the same command again to go on.` The run is kept.
   - `done`: print the file at `report` and the line `<verdict>: <report path>`. Go on with the hand-off below.
   - `error`: print `message` and stop. Do not work around it.
2. If the operator asks to stop, call `specdev loop next <run-id> --stop <roots>` and print its report.
3. Between `loop start` and `done` this session reads no spec file, findings file or brief, edits no spec, code or
   findings file, runs no gate, and gives an agent nothing but the brief path. Every agent is a fresh subagent: never
   continue an earlier one.

---

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
`verify` (`run`, `bind`, `attest`), `step`, `trace`, `attest`, `stale`, `spec-check`, `milestone-state` and `loop`.

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
- Does not accept partial convergence silently. A HALT is a verdict a person decides on.
- Does not auto-advance between phases. After `--phase impl` exits, the user manually invokes
  `/specdev-trinity <batch_id> --phase review`.
- Does not run two groups at once. Code-phase groups are serial (they share files).
