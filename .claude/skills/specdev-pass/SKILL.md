---
name: specdev-pass
description: >
  Take the spec through several steps, top down, once, without a person in between: author a spec
  from its seeds, add a feature or a new seed through every step, review one feature across the
  steps that hold it, or replay what earlier runs left (handoffs, open findings, suspect links,
  answered open items). `specdev pass` names each next run; this skill pumps the runs. The operator
  is asked once, in one batch, between the two walks. Returns COMPLETE or INCOMPLETE with a report.
  NOT for one step (→ /specdev-step, /specdev-review). NOT for milestone plans or code (→ /specdev-trinity).
  Sibling skills: specdev-step, specdev-review, specdev-trinity, specdev-context.
  Trigger on: "/specdev-pass", "author the spec", "run steps NN to MM", "add this feature to the spec",
  "new seed", "review this feature across the spec", "replay", "take the handoffs", "propagate upstream changes".
---

# /specdev-pass: several steps, top down, once

```
/specdev-pass <NN-MM | all>                               author what is missing in the range, review and fix the rest
/specdev-pass --extend "<intent>" [--seed PATH] [--from NN]   a new feature or seed: every step from NN (default 00) to 15
/specdev-pass --review --about <node-id>                   one feature: the steps that hold the node or a node that links to it
/specdev-pass --replay                                     what earlier runs left: handoffs, open findings, suspect links, answered open items
```

A seed is written or edited by a person before the pass (`docs/developers/workflows/workflow_feature_extension.md`).

How a pass goes, all decided by `specdev pass next`:

1. **Survey** (not for `--extend`, and not when no step has an artifact yet): one read-only run over the existing
   steps. Every finding is known before the first edit, so a step is changed once, with everything found about it.
2. **Walk**: one run per step that has work, top down. A run fixes the findings about its step, takes the step's
   suspect links, and authors or extends where the entry says so. It asks nothing; what no source settles becomes an
   open item.
3. **One batch of questions**: the open items, and what two fixes could not close.
4. **Second walk**: applies the answers, and takes what the first walk handed upward. It is the last.

## Preflight

On macOS, for a pass of more than three steps, print the output of `pmset -g batt` and say: `A pass can run for a long
time. caffeinate -s keeps the machine awake only on AC power, and a closed lid puts it to sleep unless an external
display is attached: keep it on AC power with the lid open.`

```bash
specdev pass start <entry as typed> --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
```

It prints `{"pass_id": ..., "resumed": ...}`: a new pass, or the unfinished pass with the same entry. If it prints
`"type": "error"`, print the message and stop.

## The pass pump

`<roots>` is the three root flags of the command above: `--repo-root ./devspec_toolkit --spec-root ./spec --git-root .`.

1. Call `specdev pass next <pass-id> <roots>`. It prints one JSON action:
   - `run`: a run was created (or is unfinished). Print one line, `step <step>, walk <walk>: <run_id>`, then pump
     that run with **The pump** below until its `done`. Print only its `<verdict>: <report path>` line, not the
     report. Then go to 1, whatever the verdict.
   - `ask`: the batch. Put every question to the operator with AskUserQuestion, as given, at most 4 per call. A
     question with `"free_text": true` takes the operator's own answer as its notes. Write
     `{"<question id>": {"label": "<chosen label>", "notes": "<notes or free text>"}}` with every answer to
     `answers_path`, call `specdev pass next <pass-id> --answers <answers_path> <roots>` and treat its action as in 1.
     The tool writes each decision into its open item. If the operator dismisses a question, stop and print
     `Stopped at the batch; run the same command again to go on.`
   - `done`: print the file at `report` and the line `<verdict>: <report path>`.
   - `error`: print `message` and stop.
2. If a run ended `HALT(agent_failed)` or `HALT(operator)`, the pass ends with that verdict. After the cause is
   removed, `specdev pass next <pass-id> --retry <roots>` starts that step's run anew and the pass goes on.
3. If the operator asks to stop: `specdev pass next <pass-id> --stop <roots>`.

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

| Verdict | Then |
|---|---|
| `COMPLETE` | Every step of the pass has its artifact, and no finding, open item, gate error or suspect link of those steps is left. The report lists what lies outside the pass (a step above or below it). Print the report |
| `INCOMPLETE` | The report lists what is left, by step. Print it and: `Go on with: /specdev-pass --replay` |
| `HALT(agent_failed)`, `HALT(operator)` | Print the report of the run that ended it, and the `--retry` command of step 2 above |

This skill does not commit, and edits no spec file itself.
