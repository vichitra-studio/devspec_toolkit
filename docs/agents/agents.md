# Agent Operations Contract

This document defines how automated agents should work with the AI Spec Driven Development Toolkit. Follow it verbatim to avoid hallucinations and maintain deterministic outputs.

## 1. Locating Agent Guidance
- Prefer machine-readable metadata in [docs/agents/manifest.json](manifest.json).
- If the manifest is missing, fall back to this file ([docs/agents/agents.md](agents.md)).
- A root-level pointer ([README.md](../../README.md)) also links here; use it to discover agent docs when scanning the repository top-down.

## 2. Repository Expectations
- The toolkit is checked out at repo root as [./devspec_toolkit/](../../); adjust if your checkout differs.
- Live spec artifacts reside in the host repository under `spec/` (sibling to the toolkit submodule).
- Prompts required to generate artifacts live under [./devspec_toolkit/prompts/](../../prompts/) (adjust the path if you store the toolkit elsewhere).
- Schemas are referenced from [./devspec_toolkit/schema/](../../schema/) and resolved using [./devspec_toolkit/tools/schema_registry.json](../../tools/schema_registry.json).
- Validation commands are executed via `python -m specdev_tools.cli ... --repo-root <toolkit-path>` with `PYTHONPATH` including `<toolkit-path>/tools`.

## 3. Operating Protocol (Two‑Phase)
This toolkit uses a two‑phase interaction to maximize completeness without hard‑coding schemas.

1. **Read Inputs**
   - Load the relevant human guide: `spec/NN_name.guide.md`.
   - Load the deterministic prompt: [./devspec_toolkit/prompts/prompt_NN_name.md](../../prompts/).
   - In prompts, use the new sections: `Context To Ingest`, `Operating Flow`, `Heuristics For Completeness`, and `Self‑Audit Gate`.
2. **Prepare Context**
   - Ingest the paths listed in `Context To Ingest` for the step.
   - Build a private ledger per step (e.g., FR ledger, API ledger) as described in `Operating Flow` (do not output it).
3. **Phase A — Clarify**
   - Apply the `Self‑Audit Gate`. If the private completeness score is < 0.9 or any gating item is missing:
     - Output only a short, bulleted list of targeted gap questions (no code fences, no JSON).
     - Group questions by field/impact (e.g., “Success Metrics”, “Security”, “Schemas”).
     - Stop and wait for human answers.
4. **Phase B — Emit**
   - Once answers resolve gating items, run the same prompt to generate the artifact.
   - Output exactly one fenced `json` code block that validates against the embedded schema; no extra prose.
5. **Persist Artifact**
   - Replace the contents of `spec/NN_name.json` with the generated block.
   - Preserve the `$schema` field already present in the file.
6. **Validate**
   - Run the [core validation commands](../developers/reference.md#core-validation-commands) and inspect results.
   - On failure, re-run with additional clarifications from the guide.
7. **Update Traceability**
   - When FRs, APIs, fixtures, or NFRs change, ensure the validation sequence above completes successfully.

## 4. Step Reference
| Step | Artifact | Required Follow-Up |
|------|----------|-------------------|
| 00–03 | `spec/0*_*.json` | Validate-only |
| 04 | `spec/04_fr_list.json` | Recompute trace matrix |
| 05 | `spec/05_interface_contracts.json` | Recompute trace matrix + fixtures lint |
| 06 | `spec/06_invariants.json` | Re-run invariants check |
| 07 | `spec/07_nfrs.json` | Ensure `16_delivery_monitoring.json` links remain valid |
| 08 | `spec/08_fixtures.json` | Run `fixtures-lint` |
| 09–12 | `spec/09*_*.json` | Validate-only unless trace references change |
| 13 | `spec/13_extension_manifest.json` | Review proposed extension schemas |
| 13a | `spec/13a_completeness_assessment.json` | Check for gaps before Roadmap |
| 14 | `spec/14_roadmap.json` | Initiate JIT implementation loop |
| 15 | `spec/15_scaffold.json` | Implement scaffold manually |
| 16a | `spec/impl_context/{step_id}.json` | Trinity Plan: Tasks, Security, Delivery, Drift |
| 16b | `spec/impl_context/{step_id}.json` | Trinity Build: Code, Configs, Docs |
| 16c | `spec/impl_context/{step_id}.json` | Trinity Review: Verification & closure |

## 5. Escalation Triggers
- Schema validation fails after two retries → request human clarification.
- Phase A repeated twice without sufficient answers → summarize blockers and request escalation/decisions.
- A referenced ID is missing from expected step → highlight the missing ID and halt.
- `fixtures-lint` or `matrix` produce new warnings → include the command output in your response and stop.
- Unrecognized command or missing tool → inform the user; do not attempt to install packages without approval.

## 6. Commit & Governance
- Use commit messages that match `spec/10_governance.json`.
- When opening a PR, summarize the affected spec IDs and attach validation logs.

## 7. Output Contract For Agents
When reporting back to humans, include:
1. List of files touched (spec, prompts, docs, etc.).
2. Commands executed and whether they succeeded.
3. Outstanding issues or reasons for escalation.

During Phase A (Clarify), output only a bulleted list of questions grouped by topic. During Phase B (Emit), output only the single fenced `json` block.

## 8. Runner Tips
- Treat prompts as the contract; do not modify them at runtime.
- Honor `interaction_mode` and `phase_triggers` from the manifest; switch phases only when conditions are met.
- Read only the paths listed in the prompt’s “Context To Ingest” for that step; avoid external sources.
- Build private ledgers in memory only; never persist them or include them in outputs.
- In Phase A, emit only grouped, concise questions; never include JSON, code fences, or speculative answers.
- Stop generation when the self‑audit gate is not met; wait for human input rather than guessing.
- Prefer deterministic decoding to keep outputs stable across retries.
- De‑duplicate questions and prioritize gating items that block emission.
- Resolve IDs and traces against current artifacts; flag unknown or missing IDs as gaps instead of inventing them.
- Preserve `$schema` and file naming; do not add fields outside the schema.
- After emission, run validations and surface short, actionable failure summaries; do not auto‑correct silently.
- Do not perform network/package installs; report missing tools or commands succinctly.
- Keep file paths relative to the repo root in user‑visible output; avoid absolute paths.

Following this contract keeps the spec workflow repeatable and predictable for both automated and human contributors.
