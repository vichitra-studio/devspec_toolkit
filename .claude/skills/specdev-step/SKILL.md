---
name: specdev-step
description: >
  Author, extend, and review a single waterfall step. Starts a `specdev loop` run that first has
  specdev-impl author a fresh spec/NN_*.json from the step's prompt contract (or, with --extend, add
  content for an operator intent to an EXISTING artifact), then runs the review-fix loop on it;
  this skill pumps that run. Returns CONVERGED or HALT.
  When spec/NN_*.json exists and operator intent is propagation → `specdev stale`, then /specdev-review.
  When spec/NN_*.json exists and operator intent is to extend with NL-authored content →
  /specdev-step <NN> --extend "<intent>".
  NOT for several steps top down or a feature through all steps (→ /specdev-pass).
  NOT for step 16 trinity phases (→ /specdev-trinity). NOT for context-only or read-only questions
  about a step (→ /specdev-context).
  Sibling skills: specdev-context (orientation/read), specdev-review (review existing artifact),
  specdev-pass (several steps), specdev-trinity (trinity phases 16a/16b/16c).
  Trigger on: "author step NN", "implement step NN", "/specdev-step NN",
  "/specdev-step NN --extend", "add content to step NN", or any request to produce or extend
  a spec artifact for a step.
---

# /specdev-step: author or extend one step, then review it

```
/specdev-step <NN> [--extend "<intent>" [--seed <seed_path>]]
```

- `<NN>`: a step of `00` to `15` (`04`, `02a`).
- `--extend "<intent>"`: what to add to an EXISTING artifact, in plain words. The author agent writes the structured
  content from the intent, the step's prompt contract and the upstream nodes. Do not supply a content object.
- `--seed <seed_path>`: with `--extend`, the seed document the intent comes from.

A feature that touches several steps is `/specdev-pass --extend "<intent>" [--seed <seed_path>]`: it walks every step
once, top down.

## Protocol

### Step 1: preflight

**Unfinished run:** Run `specdev loop status --repo-root ./devspec_toolkit --spec-root ./spec --git-root .`. If it
lists a run of step `<NN>` whose `verdict` is `null`, that run is continued: go to Step 2 with the same arguments
(`loop start` prints its id).

**Migration worklist:** If `spec/extras/migration/worklist.json` exists, the host is in the middle of the
1.2.0 migration. Run `specdev align triage spec --step <NN>` first. Treat the `audience: agent` items as
input to this step's pass, ask the operator about each `audience: operator` item, and mark each item when
it is done: `specdev align triage spec --resolve <id> --note "<what was done>"`.

**Pre-dispatch existence check:** `ls spec/<NN>_*.json 2>/dev/null`.

- No file: run `specdev step ready <NN> --repo-root ./devspec_toolkit --spec-root ./spec --git-root .`. Exit 0 prints
  `step <NN>: ready`: go to Step 2 with `--author`. Exit 1 (E773) means an input step has no spec file yet or has
  pending replay; the last line of the output says what to do first. Print the output and stop.
- A file, and `--extend` was given: go to Step 2 with `--extend`.
- A file, and no `--extend`: stop and print:

```
Artifact spec/<NN>_*.json already exists. /specdev-step authors a new artifact or extends one.

  Propagate an upstream change to this step:   specdev stale --step <NN>, then /specdev-review <NN>
                                               (the review takes each suspect link of the step as a finding)
  Insert content you already have as JSON:     specdev json insert --step <NN> <collection-path> '<node-json>'
                                               specdev json patch --id <node-id> <field-path> '<value>'
                                               specdev json delete --id <node-id>
                                               then /specdev-review <NN>
  Add content from a description:              /specdev-step <NN> --extend "<what to add>" [--seed <seed_path>]
```

### Step 2: the run

```bash
specdev loop start --kind step <NN> --author --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
specdev loop start --kind step <NN> --extend "<intent>" [--seed <seed_path>] --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
```

One of the two. It prints `{"run_id": ..., "resumed": ...}`. If it prints `"type": "error"`, print the message and
stop. The run begins with one author dispatch (`specdev-impl`, from its brief), then the step gate, then the same
review-fix loop `/specdev-review` runs; with `--extend` only what the author changed is reviewed. An author asks no
question: what the contract and the upstream nodes do not settle it records as an open item in the artifact, and the
report lists those items.

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
     A folder that has been quiet for a while does not show that the agents are done: go by a subagent that
     returned and by the action the tool prints, never by watching the files.
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

## Hand-off

Print the report; it ends with the step gate's result (`clear` or `blocked`) and the open items the run recorded.

| Verdict | Then |
|---|---|
| `CONVERGED` | Run `specdev stale <roots>`. If it lists steps below `<NN>`, or the report lists handoffs or open items, print: `Next: /specdev-pass --replay` (it takes the handoffs and the suspect links, asks the open items in one batch, and applies the answers) |
| `HALT(cap)` | Five rounds were used and findings are open. Print: `Hand-edit, or go on with /specdev-review <NN> --worklist <the done action's final>` |
| `HALT(agent_failed)` | The author refused (the report gives its reason: a missing prerequisite, an artifact that exists), or an agent wrote no usable file twice. Print the report and stop |
| `HALT(operator)` | The operator stopped the run |

## Flag discipline

`--repo-root ./devspec_toolkit --spec-root ./spec --git-root .` on `loop`, `pass`, `spec-check`, `step ready`, `stale`,
`attest` and the id forms of `json` (`json patch|insert|delete --id`, `json insert --step`). `specdev json`
read and shape subcommands take `--repo-root` only. `canon-accept` takes `--git-root`, not `--spec-root`.

Never read `spec/*.json` directly, and never edit the lock file by hand: `specdev attest` writes it.

## What this skill does NOT do

- It does not review an existing artifact without authoring or extending: that is `/specdev-review`.
- It does not handle 16a, 16b or 16c: a milestone's plan is created by `/specdev-trinity --phase plan` with
  `specdev step create 16a <batch> --from <draft>`, and its code belongs to `/specdev-trinity` too.
- It does not commit.
