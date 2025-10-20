# 4. Functional Requirements

## Purpose
Turn capabilities into falsifiable statements of system behavior with clear entry conditions, expected outcomes, and measurable acceptance evidence. These requirements become the contract linking stakeholder intent to APIs, fixtures, and monitoring.

## Template / Fields
- Canonical artifact: **spec/04_fr_list.json**
- Schema reference: `schema/04_fr_list.schema.json` (do not inline schema; rely on `$schema` in JSON artifacts)
- Core atoms: `kebabId`, `owner`, `timestamp`, `tag` (see `schema/core/atoms.schema.json`)
- Core collections: `kebabIdArray`, `stringArray`, `link`, `traceRef`, `errorState`, `anyJson` (see `schema/core/collections.schema.json`)

## Prompt File
- Contract: `prompts/prompt_04_functional_requirements.md`
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
- Write `statement` text that is testable, scoped to a single behavior, and measurable against success metrics.
- Provide `preconditions` and `postconditions` so testers and implementers know the boundaries of each requirement.
- Ensure every acceptance criterion has a stable `criterion_id` and, when possible, a `fixture_ref` to drive automation.
- Use `trace` arrays to link FRs back to capabilities, APIs, NFRs, or governance rules.

## Common Pitfalls
- Bundling multiple behaviors into one FR, making it impossible to prove completeness.
- Leaving acceptance criteria generic or missing, which blocks fixture authoring.
- Skipping trace links, severing coverage reporting across spec steps.
- Embedding implementation details (e.g., method names) instead of outcomes, limiting design options.

## Related Steps
- Step 0: Project Charter - Supplies success metrics and scope constraints.
- Step 1: Capabilities - Provides the verbs and boundaries each FR must honor.
- Step 5: Interface Contracts - Converts FR expectations into request/response semantics.
- Step 8: Fixtures - Operationalizes acceptance criteria into automated checks.

## Quick Reference
- **ID Format**: `fr-<descriptor>` with stable suffixes for traceability.
- **Required Fields**: every FR needs `statement`, `acceptance_criteria`, and `fr_id`.
- **Criteria Structure**: each criterion requires `criterion_id` and `text`; add `fixture_ref` when automation exists.
- **Trace Hooks**: expect coverage from `trace` to Capabilities (`capability-*`), APIs (`api-*`), or NFRs.
