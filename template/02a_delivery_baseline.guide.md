# 2a Delivery Baseline

## Purpose
Capture the minimum delivery infrastructure (environments, CI expectations, and compliance guardrails) needed to take the system sketch from spec to running code safely. This baseline makes deployment assumptions explicit early so fixture execution, governance, and implementation planning share the same operational picture.

## Template / Fields
- Canonical artifact: **spec/02a_delivery_baseline.json**
- Schema reference: `schema/02a_delivery_baseline.schema.json` (do not inline schema; rely on `$schema` in JSON artifacts)
- Core atoms: `kebabId`, `owner`, `timestamp`, `tag` (see `schema/core/atoms.schema.json`)
- Core collections: `kebabIdArray`, `stringArray`, `link`, `traceRef`, `errorState`, `anyJson` (see `schema/core/collections.schema.json`)

## Prompt File
- Contract: `prompts/prompt_02a_delivery_baseline.md`
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
- Document each environment (`dev`, `ci`, `staging`, `prod`) with the critical configuration knobs, dependencies, and access paths teams need to self-serve.
- Enumerate `ci_gates` as actionable job names (schema, fixtures, security scans) that map directly to Step 12 output.
- Track sensitive material in `secrets` with ownership and rotation expectations to stay compliant during scaffolding.
- Capture regulatory or contractual obligations under `compliance` to feed governance and monitoring steps.

## Common Pitfalls
- Leaving environment objects empty, forcing teams to guess runtime dependencies.
- Mixing manual review steps into `ci_gates`, which belong in governance policies instead.
- Forgetting to include secrets discovered during discovery, creating blockers during scaffold generation.
- Treating compliance requirements as optional notes instead of binding constraints for later steps.

## Related Steps
- Step 2: System Sketch - Drives which environments and integrations must be provisioned.
- Step 9: Implementation Plan - Turns gates and environments into milestone tasks.
- Step 12: CI Gates - Expands these baseline checks into enforceable automation.

## Quick Reference
- **ID Format**: `delivery_baseline-<descriptor>`; stick with ops-owned `owner` values.
- **Required Fields**: must define `environments.dev/ci/staging/prod` plus at least one `ci_gate`.
- **Secrets List**: capture names or vault paths, not the secret values themselves.
- **Compliance Hooks**: use `compliance` entries to reference frameworks (e.g., SOC2, HIPAA) or internal policies.
