# Spec → Implementation Workflow (Steps 13–16c)

Phase II turns validated specs into a running system while keeping runtime behavior traceable back to the artifacts.

All commands in this guide assume you run them from repo root with the toolkit available at [./devspec_toolkit/](../../../).

## AI Assist Flow
Where prompts apply in this phase (e.g., Scaffold updates, Trinity Plan/Review, Drift), use the two‑phase flow:
- Phase A — Clarify: ask targeted questions based on the prompt’s “Self‑Audit Gate”.
- Phase B — Emit: write the step artifact as a draft file, then create the step with `specdev step create` (an existing step is edited with `specdev json patch|insert|delete --id`); never write a file under `spec/` by hand.
Clarify responses should be short, bulleted questions grouped by topic (no JSON, no code fences), prioritizing gating items; pause emission until those answers are provided.

## Step Progression
Step 13a (the completeness assessment) was removed in 1.2.0. Before step 14, run `specdev step ready 14` and `specdev coverage`: the blockers `step ready 14` lists belong to the steps below 14 and are fixed first; `specdev coverage` and `specdev stale` also list gaps that step 14 owns (the E740 of the nodes a task criterion uses, E742), and `spec-check` reports E566, E744 and E745; none of these is a blocker, and the task criteria of step 14 clear them (run on a copy of the worked example with steps 14 to 16 removed: 11 blockers at steps 07, 08 and 12, and 13 more gaps, E740 and E742, owned by step 14).

| Step | Purpose | Key Activities |
|------|---------|----------------|
| 13 — Extensions | Define domain-specific schemas | Identify missing domains (AI, DB) and generate `spec/13_extension_manifest.json`. |
| 14 — Roadmap | Sequence the work (Core + Extensions) | Merge Step 09 baseline + Step 13 extensions into a tactical JIT execution plan. |
| 15 — Scaffold | Generate compile-clean skeleton | Implement manually or via framework CLI. |
| 16a — Plan (Trinity) | Detailed Task & Sec/Ops Planning | Plan items that realise task criteria, with their actions, docs impact and drift checks, in `spec/impl_context/ms_<batch>_plan.json` (`specdev step create 16a <batch> --from <draft>`). |
| 16b — Build (Trinity) | Implement & Config | Write code, configs and docs; record each carried-out action with `specdev plan record` and prove a verifier action with `specdev verify run`. |
| 16c — Review (Trinity) | Audit & Gate | Verify code, security and ops; record the verdict with `specdev review record`; a person signs the milestone off and `specdev milestone close` runs the close gate. |

## Step 16 Artifact Layout
Step 16 uses **two levels** of artifacts:
1. **Trinity Anchor**: `spec/16_impl_context.json` (one file) — a root summary for the active cycle.
2. **Milestone Plans**: `spec/impl_context/ms_<batch>_plan.json` — one plan file per milestone, written by 16a (`step create 16a`), with the execution records of 16b (`plan record`) and the review of 16c (`review record`) in it. The plan names its milestone in its `milestone` key.

## The Life of a Milestone
One milestone runs through the commands below, in this order; the `/specdev-trinity` skill (`.claude/skills/specdev-trinity/SKILL.md`) and the prompts 16 to 16c say the same. The commands are in [the reference](../reference.md#the-life-of-a-milestone-milestone-plan-record-review-record-verify-attest-status); the refusals are in [error-codes.md](../error-codes.md#milestone-lifecycle-80x--81x--82x--83x). Nobody writes a milestone's status, a record or a plan by hand.

1. **Find the milestone id.** `specdev milestone-state --batch-id <batch>` prints it under `milestone` (the key `milestone_id` echoes the batch id and is not a milestone id). A plan with no `milestone` key stops here with E803.
2. **Plan (16a).** `specdev step ready 16a`; when the milestone has no plan, write a draft and run `specdev step create 16a <batch> --from <draft>`; review the plan; the person approves it.
3. **Start.** `specdev milestone start <ms-id>` moves the milestone from `pending` or `deferred` to `in_progress`.
4. **Build (16b).** Per plan item: write the code; `specdev plan record <ITEM>/<action-id> --outcome done` for each action that was carried out, and `specdev verify run <binding>` for an action that names a verifier (a record for it is E822); review the item. Open items go into the plan by `specdev json patch|insert`.
5. **Review (16c).** The milestone-wide reviewer writes a findings file. **The code is committed before `specdev verify run --milestone <ms-id> --stage ci`**: the close gate reads tracked files (E746), and a commit after the run makes the evidence `STALE_TREE` (E811). Then the skill runs `specdev review record <ms-id> --verdict verified --findings-file <converged file>` (the reviewer writes findings only; in a manual run you run it).
6. **Sign-off and close.** Show `specdev status --milestone <ms-id>`; the person signs the milestone off (`specdev milestone sign-off <ms-id>`); then the skill runs `specdev milestone close <ms-id> --check` and `specdev milestone close <ms-id>` (in a manual run you do), which sets the row `done`, writes the close record and freezes the plan.

**A person decides** sign-off, defer (`specdev milestone defer <ms-id> --reason "..."`) and manual verification, that is, whether a manual-verification action was carried out (the skill then records it with `specdev plan record`), the attestation of a manual fixture or of a rule enforced by review (`specdev verify attest <node-id>...`) and of an `at_deploy` action a person carried out. An agent shows `specdev status` first, asks, and never answers the host's ask prompt itself; specdev records who ran the command (from git) and checks nothing about who that is.

`specdev attest` re-accepts links in the trace lock; `specdev verify attest` writes an attestation record. The milestone-wide run (`specdev loop start --kind code-milestone <ms-id>`) ends with `final.json` in its run folder, the findings it did not close; the skill passes that file to `specdev review record --findings-file`, and the run writes a copy to `.specdev/findings/findings_<batch>_review_<n>.json`, which `milestone-state` reads. A 1.1.1 plan (no `milestone` key, with the removed fields) is read through `specdev status` only and is not driven through the loop until `specdev align apply --auto` has rewritten it (it adds the `milestone` key, the action ids and, in a plan of a milestone still open, removes the old progress fields: see [Migrating a 1.1.1 host to 1.2.0](./workflow_migrate_1_2_0.md)).

## Why Two Planning Steps?
Confusion often arises between **Step 09 (Implementation Plan)** and **Step 14 (Roadmap)**.

| Feature | Step 09 (Impl Plan) | Step 14 (Roadmap) |
| :--- | :--- | :--- |
| **Phase** | Discovery (Planning) | Execution (JIT) |
| **Goal** | **Unlock Downstream Specs** | **Drive Daily Coding** |
| **Key Output** | Design milestones: named groups of the requirements, APIs, invariants, NFRs and components one delivery slice schedules | Atomic User Stories, Tasks with acceptance criteria |
| **Why?** | You need to know which upstream nodes ship together before you can write the *Roadmap* (Step 14) that turns each slice into tasks. | You need to know the *Extensions* (Step 13) before you can sequence the actual work. |

**Rule of Thumb**: Step 09 is the "Architect's Baseline". Step 14 is the "Project Manager's Schedule".

## Command Cadence
- Generate scaffolds manually or using framework tools, ensuring alignment with `15_scaffold.json`.
- **Verify**: Use `python devspec_toolkit/tests/integration/test_step_15.py <path_to_scaffold>` to run `specdev validate` on it (schema compliance and the `build_status` rules).
- Run the [core validation commands](../reference.md#core-validation-commands) to track fixture progress and trace coverage as implementation evolves.

## CI Integration
- **validate** — schema + fixture lint
- **test** — executes fixture suite and custom tests
- **redteam** — runs adversarial inputs and adds regressions to fixtures
- **deploy** — deploys via the plan in Step 09/16
- **drift-audit** — compares runtime data to spec assertions as defined in `16_impl_context.json` (Step 16a)

Ensure the host's own workflows reflect these jobs and reference the spec IDs they enforce. `specdev update` installs one workflow, `.github/workflows/specdev-merge-check.yml` (the merge gate and `release prep`); the deploy jobs are the host's own, built from the snippets described in [host_setup.md](../host_setup.md).


## Outputs
- Current artifacts under `spec/13*` through `spec/16*`
- Implemented scaffold or runtime referencing Step 05 contracts
- Updated monitoring bindings and drift schedules guaranteeing the spec remains the single source of truth
