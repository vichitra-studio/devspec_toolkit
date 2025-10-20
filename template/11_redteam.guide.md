# 11. Red-Team / Failure Modes

## Purpose
Anticipate how the system can fail, whether through malicious actors, misuse, or rare scenarios, and document mitigations before implementation begins. Red-team findings inform fixtures, monitoring, and governance so the spec remains resilient under stress.

## Template / Fields
- Canonical artifact: **spec/11_redteam.json**
- Schema reference: `schema/11_redteam.schema.json` (do not inline schema; rely on `$schema` in JSON artifacts)
- Core atoms: `kebabId`, `owner`, `timestamp`, `tag` (see `schema/core/atoms.schema.json`)
- Core collections: `kebabIdArray`, `stringArray`, `link`, `traceRef`, `errorState`, `anyJson` (see `schema/core/collections.schema.json`)

## Prompt File
- Contract: `prompts/prompt_11_redteam.md`
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
- Describe each `threat` with clear attack vectors or failure mechanisms, then prioritize using `severity`.
- Tie `mitigations` to specific actions, invariants, or monitoring hooks instead of vague statements.
- Populate `edge_cases` with scenarios that warrant dedicated fixtures or UI handling.
- Revisit threats after every major spec update to keep the catalog synchronized with new capabilities.

## Common Pitfalls
- Labeling everything "high" severity without triage, making it impossible to focus mitigation work.
- Listing generic mitigations such as "add logging" without specifying owners or steps.
- Forgetting to propagate serious threats into fixtures or governance, leaving gaps in automation.
- Treating red-team outputs as one-time, leading to drift during implementation.

## Related Steps
- Step 8: Fixtures - Converts high-priority threats into executable adversarial tests.
- Step 12: CI Gates - Ensures mitigations (linting, security scans) run on every change.
- Step 15: Red-Team Loop - Extends this artifact after implementation uncovers new attack paths.
- Step 17: Spec-Drift Audit - Checks that mitigations continue to hold in production.

## Quick Reference
- **ID Format**: `redteam-<descriptor>`; threats use `threat-<vector>-<number>`.
- **Required Fields**: each threat must include `threat_id`, `description`, and `severity`.
- **Severity Scale**: choose from `low`, `medium`, `high`, `critical` and document rationale.
- **Edge Cases**: capture notable non-malicious scenarios needing fixtures or UX cues.
