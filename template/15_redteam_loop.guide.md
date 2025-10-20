# 15. Continuous Red-Team / QA Loop

## Purpose
Capture the iterative security and QA learnings that emerge during implementation, making every new adversarial insight part of the spec before code changes land. This loop keeps fixtures, requirements, and mitigations evolving together.

## Template / Fields
- Canonical artifact: **spec/15_redteam_loop.json**
- Schema reference: `schema/15_redteam_loop.schema.json` (do not inline schema; rely on `$schema` in JSON artifacts)
- Core atoms: `kebabId`, `owner`, `timestamp`, `tag` (see `schema/core/atoms.schema.json`)
- Core collections: `kebabIdArray`, `stringArray`, `link`, `traceRef`, `errorState`, `anyJson` (see `schema/core/collections.schema.json`)

## Prompt File
- Contract: `prompts/prompt_15_redteam_loop.md`
- Prompts include context ingestion, operating flow, soft heuristics, and a self‑audit gate. Assistants follow a two‑phase flow:
  - Phase A — Clarify: ingest context and, if gating items are missing, output only a short bulleted list of questions.
  - Phase B — Emit: once clarified, output exactly one fenced ```json``` block that validates against the schema.

## Definition of Ready (DoR) / Guardrails
See [Shared Template Expectations](../docs/templates/shared_expectations.md#definition-of-ready-dor-guardrails).


## Working Increment
See [Shared Template Expectations](../docs/templates/shared_expectations.md#working-increment).


## Checks
See [Shared Template Expectations](../docs/templates/shared_expectations.md#checks).


## Failure Modes
See [Shared Template Expectations](../docs/templates/shared_expectations.md#failure-modes).

## Best Practices
- Log new adversarial or regression fixtures in `new_fixtures` using stable IDs that also appear in Step 08.
- Detail each `spec_update` with the impacted reference (`ref`), the change made, and the reason so audits reconstruct the decision.
- Keep `redteam_status` accurate to signal whether remaining high-severity issues block release.
- Pair fixture additions with governance updates or monitoring hooks when mitigations require process changes.

## Common Pitfalls
- Treating the loop as optional once implementation starts, leaving red-team findings untracked.
- Forgetting to update the original spec artifact referenced in `spec_updates`, causing drift.
- Recording vague reasons (e.g., "bug fix") that fail to capture threat context.
- Allowing status to stay green while critical fixtures fail, masking risk.

## Related Steps
- Step 11: Red-Team - Seeds the initial threat model that this loop evolves.
- Step 14: Fixture Implementation - Consumes new fixtures and ensures they pass before closure.
- Step 17: Spec-Drift Audit - Uses the change log to verify production behavior still matches spec updates.

## Quick Reference
- **ID Format**: `redteam_loop-<descriptor>`.
- **New Fixtures**: list `fixture-*` IDs promoted from exploratory testing.
- **Spec Updates**: include `ref` pointing to artifacts like `fr-*`, `api-*`, `invariant-*`.
- **Status Values**: `green` when high-severity items are mitigated; `red` when blockers remain.
