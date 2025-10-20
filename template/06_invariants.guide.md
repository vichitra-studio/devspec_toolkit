# 6. Invariants & Rules

## Purpose
Capture the non-negotiable truths, guardrails, and data relationships the system must uphold regardless of implementation. These invariants feed governance, contract validation, and monitoring so deviations trigger alerts before customers feel impact.

## Template / Fields
- Canonical artifact: **spec/06_invariants.json**
- Schema reference: `schema/06_invariants.schema.json` (do not inline schema; rely on `$schema` in JSON artifacts)
- Core atoms: `kebabId`, `owner`, `timestamp`, `tag` (see `schema/core/atoms.schema.json`)
- Core collections: `kebabIdArray`, `stringArray`, `link`, `traceRef`, `errorState`, `anyJson` (see `schema/core/collections.schema.json`)

## Prompt File
- Contract: `prompts/prompt_06_invariants.md`
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
- Choose the appropriate `language` (`jsonlogic`, `cel`, or `text`) and write evaluable `expression` strings for automated enforcement.
- Describe each invariant in business language first, then map `scope.components` or `scope.apis` to constrain where it applies.
- Tag severity as `error` for hard guarantees and `warn` for observability alerts to guide escalation paths.
- Link invariants to FRs, NFRs, or governance rules using `trace` so auditors know why the rule exists.

## Common Pitfalls
- Leaving the `expression` empty or non-executable, which prevents automation in CI and runtime.
- Setting severity to `warn` for hard requirements, letting regressions slip past controls.
- Forgetting to scope the invariant, causing false positives across unrelated components.
- Failing to version or reuse `inv_id`, leading to duplicate or orphaned invariants.

## Related Steps
- Step 4: Functional Requirements - Supplies behaviors that likely require invariants for enforcement.
- Step 7: NFRs - Ensures performance and reliability targets have matching invariants where feasible.
- Step 12: CI Gates - Implements automated checks that evaluate these invariants.

## Quick Reference
- **ID Format**: `invariant-<descriptor>`; keep stable for cross-step traceability.
- **Required Fields**: every rule needs `inv_id`, `description`, `language`, and `expression`.
- **Scope Usage**: populate `components` or `apis` arrays to target enforcement precisely.
- **Trace Hooks**: reference FR (`fr-*`), API (`api-*`), or governance policy IDs to show motivation.
