# Agent Operations Contract

This document defines how automated agents should work with the AI Spec Driven Development Toolkit. Follow it verbatim to avoid hallucinations and maintain deterministic outputs.

## 1. Locating Agent Guidance
- Prefer machine-readable metadata in `docs/agents/manifest.json`.
- If the manifest is missing, fall back to this file (`docs/agents/agents.md`).
- A root-level pointer (`agents.md`) also links here; use it to discover agent docs when scanning the repository top-down.

## 2. Repository Expectations
- The toolkit is checked out at repo root as `./devspec_toolkit/`; adjust if your checkout differs.
- Live spec artifacts reside in the host repository under `spec/` (sibling to the toolkit submodule).
- Prompts required to generate artifacts live under `./devspec_toolkit/prompts/` (adjust the path if you store the toolkit elsewhere).
- Schemas are referenced from `./devspec_toolkit/schema/` and resolved using `./devspec_toolkit/tools/schema_registry.json`.
- Validation commands are executed via `python -m specdev_tools.cli ... --repo-root <toolkit-path>` with `PYTHONPATH` including `<toolkit-path>/tools`.

## 3. Operating Protocol
1. **Read Inputs**
   - Load the relevant human guide: `spec/NN_name.guide.md`.
   - Load the deterministic prompt: `./devspec_toolkit/prompts/prompt_NN_name.md`.
2. **Prepare Context**
   - Capture all `Clarification Questions` blocks from the prompt.
   - Record step dependencies listed in the guide (`consumers`, `inputs`).
3. **Generate Output**
   - Run the prompt unchanged against the target model.
   - Ensure the response is exactly one fenced `json` code block.
   - Reject outputs containing examples, commentary, or extra fencing.
4. **Persist Artifact**
   - Replace the contents of `spec/NN_name.json` with the generated block.
   - Preserve the `$schema` field already present in the file.
5. **Validate**
   ```bash
   python -m specdev_tools.cli validate spec/NN_name.json --repo-root ./devspec_toolkit
   ```
   - On failure, re-run with additional clarifications from the guide.
6. **Update Traceability**
   - When FRs, APIs, fixtures, or NFRs change, also run:
     ```bash
     python -m specdev_tools.cli matrix spec --repo-root ./devspec_toolkit --out tools/trace_matrix.json
     python -m specdev_tools.cli fixtures-lint spec --repo-root ./devspec_toolkit
     ```

## 4. Step Reference
| Step | Artifact | Required Follow-Up |
|------|----------|-------------------|
| 00–03 | `spec/0*_*.json` | Validate-only |
| 04 | `spec/04_fr_list.json` | Recompute trace matrix |
| 05 | `spec/05_interface_contracts.json` | Recompute trace matrix + fixtures lint |
| 06 | `spec/06_invariants.json` | Re-run invariants check if `tests/samples/` updated |
| 07 | `spec/07_nfrs.json` | Ensure `16_delivery_monitoring.json` links remain valid |
| 08 | `spec/08_fixtures.json` | Run `fixtures-lint` |
| 09–12 | `spec/09*_*.json` | Validate-only unless trace references change |
| 13 | `spec/13_scaffold.json` | Optionally run `scaffold` command |
| 14 | `spec/14_fixture_impl.json` | Confirm fixture statuses align with test outputs |
| 15 | `spec/15_redteam_loop.json` | Verify threats referenced by `spec/11_redteam.json` |
| 16 | `spec/16_delivery_monitoring.json` | Spot-check URLs / identifiers provided by humans |
| 17 | `spec/17_spec_drift.json` | Ensure schedules map to CI jobs |

## 5. Escalation Triggers
- Schema validation fails after two retries → request human clarification.
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

Following this contract keeps the spec workflow repeatable and predictable for both automated and human contributors.
