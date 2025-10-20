# 3. Glossary

## Purpose
Create a single vocabulary that removes ambiguity across product, engineering, and governance stakeholders. The glossary keeps later artifacts crisp by codifying domain terms, measurement units, and context that might otherwise drift between documents.

## Template / Fields
- Canonical artifact: **spec/03_glossary.json**
- Schema reference: `schema/03_glossary.schema.json` (do not inline schema; rely on `$schema` in JSON artifacts)
- Core atoms: `kebabId`, `owner`, `timestamp`, `tag` (see `schema/core/atoms.schema.json`)
- Core collections: `kebabIdArray`, `stringArray`, `link`, `traceRef`, `errorState`, `anyJson` (see `schema/core/collections.schema.json`)

## Prompt File
- Contract: `prompts/prompt_03_glossary.md`
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
- Define each `term` with concise, testable language that clarifies how it is used in specs and code.
- Use `domain` to group terms by business area or component so cross-functional teams know which glossary slice applies.
- Capture `units` for quantitative concepts to align success metrics, NFRs, and monitoring dashboards.
- Reuse or link existing term IDs when extending the vocabulary to maintain stable references.

## Common Pitfalls
- Writing circular definitions that reference the term itself or other undefined jargon.
- Skipping units for metrics, leading to mismatches across FRs and monitoring.
- Allowing duplicate or near-duplicate entries that confuse schema validation and readers.
- Treating glossary updates as optional, letting new terms leak into later steps without definitions.

## Related Steps
- Step 0: Project Charter - Seeds key business terms and success metrics that require precise language.
- Step 4: Functional Requirements - Relies on glossary definitions to keep acceptance criteria unambiguous.
- Step 16: Delivery & Monitoring - Uses consistent units and terminology for dashboards and alerts.

## Quick Reference
- **ID Format**: `glossary-<descriptor>`; individual entries use `term-<concept>`.
- **Required Fields**: each term needs `term_id`, `term`, and `definition`.
- **Optional Fields**: `domain` and `units` strengthen cross-team alignment and should be filled when applicable.
- **Update Cadence**: revisit the glossary whenever new FRs, APIs, or monitoring metrics introduce vocabulary.
