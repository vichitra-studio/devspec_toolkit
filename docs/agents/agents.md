# Agent Operations Contract

This document defines how automated agents should work with the AI Spec Driven Development Toolkit. Follow it verbatim to avoid hallucinations and maintain deterministic outputs.

## 1. Locating Agent Guidance
- Prefer machine-readable metadata in [docs/agents/manifest.json](manifest.json).
- If the manifest is missing, fall back to this file ([docs/agents/agents.md](agents.md)).
- A root-level pointer ([README.md](../../README.md)) also links here; use it to discover agent docs when scanning the repository top-down.

## 2. Repository Expectations
- The toolkit is checked out at repo root as [./devspec_toolkit/](../../); adjust if your checkout differs.
- Live spec artifacts reside in the host repository under `spec/` (sibling to the toolkit submodule).
- Mandatory seed manifest lives at `spec/common/seed_manifest.json` and defines seed order + step requirements.
- Prompts required to generate artifacts live under [./devspec_toolkit/prompts/](../../prompts/) (adjust the path if you store the toolkit elsewhere).
- Schemas are referenced from [./devspec_toolkit/schema/](../../schema/) and resolved using [./devspec_toolkit/tools/schema_registry.json](../../tools/schema_registry.json).
- Validation commands are executed via `./tools/run_specdev.sh ... --repo-root <toolkit-path>` (venv enforced). Avoid calling internal modules directly.

## 3. Operating Protocol (Two‑Phase)
This toolkit uses a two‑phase interaction to maximize completeness without hard‑coding schemas.

1. **Read Inputs**
   - Load the relevant human guide: `spec/NN_name.guide.md`.
   - Load the deterministic prompt: [./devspec_toolkit/prompts/prompt_NN_name.md](../../prompts/).
   - In prompts, use the sections: `Operating Flow`, `Self‑Audit Gate`, and `Coverage Closure`. Every prompt also has a `Negative Constraints` section; follow it.
2. **Prepare Context**
   - Read `spec/common/seed_manifest.json` first and ingest required seeds in order.
   - For every step, ingest the seeds listed in `step_requirements[NN]` (resolved to paths via `seeds[]`, in `global_seed_order` order — read order only, not inclusion) before any other context. A seed is routed to each step that distils a part of it: a node of that step lists the seed in `derives_from` (beside the upstream node where the field is required and also names upstream nodes: see the seed rules of `docs/prompts/shared_expectations.md`), and `spec-check` reports a route that no node of its step uses, and any route to step 13 or a trinity step, as E748. A step with empty or absent `step_requirements[NN]` ingests no seeds; there is no fallback to `global_seed_order`.
   - Build a private ledger per step (e.g., FR ledger, API ledger) as described in `Operating Flow` (do not output it).
3. **Phase A — Clarify**
   - Apply the `Self‑Audit Gate`. If the private completeness score is < 0.9 or any gating item is missing:
     - In an interactive session, output only a short, bulleted list of targeted gap questions (no code fences, no JSON). An agent dispatched by a skill (`specdev-impl`) returns a `status: "blocker"` JSON with `questions[]` instead (the shape of "Blocker emission protocol" in `.claude/agents/specdev-impl.md`); the skill asks the person and re-dispatches.
     - Group questions by field/impact (e.g., “Success Metrics”, “Security”, “Schemas”).
     - Stop and wait for human answers.
4. **Phase B — Emit**
   - Once answers resolve gating items, run the same prompt to generate the artifact.
   - An answer that another step or a seed owns is not applied in this step: record it as an open item (`specdev json insert --step <NN> .ambiguities '<item>'`; shared_expectations section 11, item 5).
   - Write the JSON artifact to disk and validate against the referenced step schema; do not return fenced JSON as primary output. A step that does not exist yet is written as a whole draft file outside `spec/` and created with `specdev step create NN --from <draft>`; a step that exists is edited with `specdev json patch|insert|delete --id <node-id>`; a file written by hand into `spec/` gets E761 for each of its links until `specdev attest <node-id> --yes`.
   - Ensure the artifact conforms to the seed requirements declared in `spec/common/seed_manifest.json`.
5. **Persist Artifact**
   - A new step: `specdev step create NN --from <draft>` writes `spec/NN_name.json` and the lock entry of each of its links; the draft carries the `$schema` of the step.
   - An existing step: edit it node by node with `specdev json patch|insert|delete --id <node-id>`; the file keeps the `$schema` it has.
6. **Validate**
   - Run the [core validation commands](../developers/reference.md#core-validation-commands) and inspect results.
   - On failure, re-run with additional clarifications from the guide.
7. **Update Traceability**
   - When FRs, APIs, fixtures, or NFRs change, ensure the validation sequence above completes successfully.

## 4. Step Reference
| Step | Artifact | Required Follow-Up |
|------|----------|-------------------|
| 00–03 | `spec/0*_*.json` | Validate-only |
| 04 | `spec/04_fr_list.json` | Gate with `spec-check --step 04`; then `specdev stale` for the links it makes suspect |
| 05 | `spec/05_interface_contracts.json` | Gate with `spec-check --step 05`; then `specdev stale`, and fixtures lint |
| 06 | `spec/06_invariants.json` | Re-run invariants check |
| 07 | `spec/07_nfrs.json` | Gate with `spec-check --step 07`; then `specdev stale` for the links it makes suspect |
| 08 | `spec/08_fixtures.json` | Run `fixtures-lint` |
| 09–12 | `spec/09*_*.json` | Validate-only unless trace references change |
| 13 | `spec/13_extension_manifest.json` | Review proposed extension schemas |
| 14 | `spec/14_roadmap.json` | Run `specdev step ready 14` first (it lists the blockers owned by the steps below 14, to fix first; the gaps step 14 owns, E566, E742, E744, E745 and the E740 of nodes a task criterion uses, are not blockers: the task criteria of step 14 clear them); gate with `spec-check --step 14`; then initiate the JIT implementation loop |
| 15 | `spec/15_scaffold.json` | Implement scaffold manually |
| 16a | `spec/impl_context/ms_<batch>_plan.json` | Trinity Plan: Tasks, Security, Delivery, Drift (`step create 16a <batch>`) |
| 16b | `spec/impl_context/ms_<batch>_plan.json` | Trinity Build: Code, Configs, Docs (`plan record`, `verify run`) |
| 16c | `spec/impl_context/ms_<batch>_plan.json` | Trinity Review: Verification (`review record`); a person signs off, `milestone close` closes |

## 5. Escalation Triggers
- `spec-check --step NN` still blocks after `/specdev-review` has run its `max_rounds` (5) → HALT; report the findings path and wait for a person. A blocker unanswered, or raised more than twice in one dispatch chain, also halts.
- Phase A repeated twice without sufficient answers → summarize blockers and request escalation/decisions.
- A referenced ID is missing from expected step → highlight the missing ID and halt.
- `fixtures-lint` produces new warnings, or `spec-check --step NN` reports BLOCKED → include the command output in your response and stop.
- Unrecognized command or missing tool → inform the user; do not attempt to install packages without approval.

## 6. Commit & Governance
- Use commit messages that match `spec/10_governance.json`.
- When opening a PR, summarize the affected spec IDs and attach validation logs.

## 7. Output Contract For Agents
When reporting back to humans, include:
1. List of files touched (spec, prompts, docs, etc.).
2. Commands executed and whether they succeeded.
3. Outstanding issues or reasons for escalation.

During Phase A (Clarify), output only a bulleted list of questions grouped by topic (an agent dispatched by a skill returns the blocker JSON of section 9 instead). During Phase B (Emit), write the JSON artifact to disk (a new step with `specdev step create NN --from <draft>`, an existing step with `specdev json patch|insert|delete --id`) and return only a concise status/path confirmation.

## 8. Runner Tips
- Treat prompts as the contract; do not modify them at runtime.
- Honor `interaction_mode` from the manifest; switch phases only when conditions are met.
- For every step, ingest the seeds listed in `step_requirements[NN]` (resolved to paths via `seeds[]`, in `global_seed_order` order — read order only, not inclusion) before any other context. A seed is routed to each step that distils a part of it: a node of that step lists the seed in `derives_from` (beside the upstream node where the field is required and also names upstream nodes: see the seed rules of `docs/prompts/shared_expectations.md`), and `spec-check` reports a route that no node of its step uses, and any route to step 13 or a trinity step, as E748. A step with empty or absent `step_requirements[NN]` ingests no seeds; there is no fallback to `global_seed_order`. Avoid external sources.
- Build private ledgers in memory only; never persist them or include them in outputs.
- In Phase A of an interactive session, emit only grouped, concise questions; never include JSON, code fences, or speculative answers.
- Stop generation when the self‑audit gate is not met; wait for human input rather than guessing.
- Prefer deterministic decoding to keep outputs stable across retries.
- De‑duplicate questions and prioritize gating items that block emission.
- Resolve IDs and traces against current artifacts; flag unknown or missing IDs as gaps instead of inventing them.
- Preserve `$schema` and file naming; do not add fields outside the schema.
- After emission, run the step gate and surface short, actionable failure summaries. A fix is applied only from a finding or a person's instruction, never to make a check pass.
- Do not perform network/package installs; report missing tools or commands succinctly.
- Keep file paths relative to the repo root in user‑visible output; avoid absolute paths.

## 9. The specdev agents and the review-fix loop
The skills `/specdev-step`, `/specdev-review` and `/specdev-trinity` dispatch five agents (`.claude/agents/`). An agent never dispatches another; the skill does.

| Agent | Model | Tools | Reads | Writes | Stops when |
|---|---|---|---|---|---|
| `specdev-scope` | haiku | Bash, Read, Grep | default mode: the change set; mode `milestone_state`: the milestone state (`specdev milestone-state`) | default mode: a fan-out plan; mode `milestone_state`: that command's JSON (both returned, not written) | the plan or the state is returned |
| `specdev-reviewer` | sonnet | Bash, Read, Grep, Write | its cluster of spec artifacts, by `specdev json read` (never `Read` on `spec/`) | one findings file `.specdev/findings/findings_<scope>_<round>_<reviewer_id>.json` (`vc:infra:findings`; reviewer ids are `r1`, `r2`, ...); no spec edit | the file is written |
| `specdev-impl` | sonnet | Bash, Read, Edit, Write, Grep | the prompt contract, upstream nodes by `specdev json read` | author: `specdev step create`; fix and author-extend: `specdev json patch|insert|delete --id`; returns status JSON | the step gate ran, or a blocker is returned before the first edit |
| `specdev-trinity-impl` | sonnet | Bash, Read, Edit, Write | mode `execute`: one plan item and its actions; mode `fix`: a per-item findings file; mode `milestone_fix`: a milestone-wide findings file | host code inside `target_file_patterns`; `specdev plan record` | `execute`: every action is recorded; `fix` and `milestone_fix`: every finding is addressed or reported back |
| `specdev-trinity-reviewer` | sonnet | Bash, Read, Grep, Write | code and the plan item | a findings file; no code edit | the file is written |

The review-fix loop (`/specdev-review`): `specdev-scope` plans clusters; each round dispatches every cluster to a fresh `specdev-reviewer` in waves of at most `SPECDEV_REVIEW_CONCURRENCY` (default 6) and waits for the whole round; the findings files are merged with one `jq` command and de-duplicated on `(kind, location, signature)`; the round converges when the merged findings are empty; otherwise `specdev-impl` (fix mode) repairs the findings and the next round starts, at most 5 rounds, after which the loop halts with the findings path. A blocker returned by `specdev-impl` is put to the person by the skill and the agent is re-dispatched with the answers, at most twice per dispatch chain.

Following this contract keeps the spec workflow repeatable and predictable for both automated and human contributors.
