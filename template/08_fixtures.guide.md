# 8. Test Plan & Fixtures

## Purpose
Supply deterministic inputs and expected outputs that exercise functional and non-functional behaviors across the spec. These fixtures form the backbone of automated validation, red-team loops, and regression detection.

## Template / Fields
- Canonical artifact: **spec/08_fixtures.json**
- Schema reference: `schema/08_fixtures.schema.json` (do not inline schema; rely on `$schema` in JSON artifacts)
- Core atoms: `kebabId`, `owner`, `timestamp`, `tag` (see `schema/core/atoms.schema.json`)
- Core collections: `kebabIdArray`, `stringArray`, `link`, `traceRef`, `errorState`, `anyJson` (see `schema/core/collections.schema.json`)

## Prompt File
- Contract: `prompts/prompt_08_fixtures.md`
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
- Cover happy-path, edge, and failure scenarios by mixing `mode` values (unit, contract, e2e, redteam).
- Use `targets` to reference FRs, APIs, NFRs, or invariants so coverage reports stay accurate.
- Keep `input` and `expected` payloads minimal but sufficient to prove the requirement, reusing glossary terms and schema definitions.
- Tag fixtures (e.g., `smoke`, `load`) to guide CI gating and spec-to-impl planning.

## Common Pitfalls
- Creating fixtures without trace links, which prevents coverage tooling from counting them.
- Treating fixtures as documentation rather than executable payloads, leading to mismatch with generated tests.
- Overloading fixtures with multiple expectations, making failures hard to diagnose.
- Forgetting to update fixtures when interface contracts version, causing format mismatches.

## Related Steps
- Step 4: Functional Requirements - Acceptance criteria should map directly to fixture cases.
- Step 5: Interface Contracts - Provides schema refs that shape fixture input/output payloads.
- Step 15: Red-Team Loop - Extends fixtures with adversarial cases discovered later.

## Quick Reference
- **ID Format**: `fixture-<scenario>`; remain stable across revisions.
- **Required Fields**: `fixture_id`, `mode`, `input`, and `expected`.
- **Mode Choices**: `unit`, `contract`, `e2e`, `redteam`; use multiple to cover layers.
- **Trace Hooks**: populate `targets` with IDs like `fr-*`, `api-*`, `nfr-*`, or `invariant-*`.
