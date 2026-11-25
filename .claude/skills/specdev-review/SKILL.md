---
name: specdev-review
description: >
  Run the review-fix loop on a spec scope that already exists. The loop is kept by `specdev loop`
  (start, next): it hands out reviewer and fixer briefs, checks every finding, runs the step gate and
  the suspect links, and ends CONVERGED or HALT with a report. This skill only pumps it.
  NOT when spec/NN_*.json is absent (→ /specdev-step to author it first). NOT for
  ms_*_plan.json trinity reviews (→ /specdev-trinity). NOT for several steps top down, a new feature
  or a replay (→ /specdev-pass). NOT for PR or audit scopes (→ /devspec_pr_audit).
  Sibling skills: specdev-step (author or extend one step), specdev-pass (several steps),
  specdev-trinity (ms_* plan reviews), devspec_pr_audit (PR/branch audit scopes).
  Trigger on: "review step NN", "run review", "/specdev-review", review + any step reference,
  "check step", "audit scope", or after any spec authoring or editing task (artifact must exist).
---

# /specdev-review: review and fix a spec scope

```
/specdev-review <scope> [--review-only] [--worklist FILE] [--about NODE]
```

- `<scope>`: a step (`04`), a range (`04-07`), a list (`04,06`), `all`, or the name of a file of `spec/common/`
  (`seed_manifest.json`). A `spec/common/` file is reviewed with `--review-only`: a person edits seed files.
- `--review-only`: one round, nothing is edited; the verdict is `CLEAN` or `FINDINGS`. Upstream reconciliation
  (confirming or refuting what earlier steps reported) is not a review output: the report holds findings, each with a
  quote, and nothing else.
- `--worklist FILE`: begin by fixing the findings of FILE: the `final.json` or `handoffs.json` of an earlier run, or
  any findings file (`vc:infra:findings`).
- `--about NODE`: read only NODE and the nodes that link to it. What may be fixed is still the whole scope.

A review of several steps that should also fix what it finds above each step is `/specdev-pass <range>`: it surveys
first and changes each step once.

## Start

```bash
specdev loop start --kind step <scope> [--review-only] [--worklist FILE] [--about NODE] --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
```

It prints `{"run_id": ..., "resumed": ...}`: a new run, or the unfinished run of this scope (`resumed: true`; say so
in one line). If it prints `"type": "error"`, print the message and stop: it names the step that has no artifact
(`/specdev-step <NN>` authors it) or the unfinished run that was started another way and the command that ends it.

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

## Hand-off

| Verdict | Then |
|---|---|
| `CONVERGED` | Every node was read in its current content, and no finding, gate error or suspect link of the scope is open. Run `specdev stale <roots>`; if it lists steps below the scope, or the report lists handoffs, print: `Next: /specdev-pass --replay` |
| `CLEAN`, `FINDINGS` | A review-only run. For `FINDINGS` print: `To fix them: /specdev-review <scope> --worklist <the done action's final>` |
| `HALT(cap)` | Five rounds were used and findings are open; the report lists them. Print: `Hand-edit, or go on with /specdev-review <scope> --worklist <final>` |
| `HALT(agent_failed)` | An agent wrote no usable file twice, or refused; the report says which. Print the report and stop |
| `HALT(operator)` | The operator stopped the run |

This skill does not commit. It never edits a spec file itself: fixes are made by `specdev-impl` from its brief.
