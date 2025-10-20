# {{STEP_TITLE}}

## Purpose
{{PURPOSE_STATEMENT}}

## Template / Fields
- Canonical artifact: **spec/{{STEP_FILE_NAME}}**
- Schema reference: `schema/{{STEP_SCHEMA_NAME}}` (do not inline schema; rely on `$schema` in JSON artifacts)
- Core atoms: `kebabId`, `owner`, `timestamp`, `tag` (see [schema/core/atoms.schema.json](../../schema/core/atoms.schema.json))
- Core collections: `kebabIdArray`, `stringArray`, `link`, `traceRef`, `errorState`, `anyJson` (see [schema/core/collections.schema.json](../../schema/core/collections.schema.json))

## Prompt File
- Contract: `prompts/prompt_{{STEP_ID}}_{{STEP_SLUG}}.md`
- Prompts include sections for context ingestion, operating flow, soft heuristics, and a self‑audit gate. Assistants follow a two‑phase flow:
  - Phase A — Clarify: ingest context and, if gating items are missing, output only a short bulleted list of questions.
  - Phase B — Emit: once clarified, output exactly one fenced ```json``` block that validates against the schema.

## Definition of Ready (DoR) / Guardrails
- All required fields present and semantically filled, not placeholders like "TBD" except where explicitly allowed for bootstrapping.
- IDs are **kebab-case** and stable across files.
- `owner ∈ {api, ui, system, ops, data}`. Pick the team actually responsible.
- Traces reference existing IDs or temporary `*-tbd` anchors which must be resolved by Step 8.
- No fields outside schema. No redefinition of atoms/collections/errors.
- JSON must be machine-checkable with CI validators.

## Working Increment
- Store the generated JSON and guide under your host repo’s `spec/` directory using the matching filenames.
- CI runs: schema validation and step-specific checks (see below).

## Checks
- Schema validation: required keys, enums, formats.
- Cross-step traceability: IDs referenced here must exist by their milestone deadlines.
- Quality: keep prose succinct; prefer measurable statements; avoid ambiguity.

## Failure Modes
- Over-broad scope or vague statements that cannot be falsified.
- Broken references to other steps.
- Hidden assumptions not captured in the artifact.

## Best Practices
{{BEST_PRACTICES_CONTENT}}

## Common Pitfalls
{{COMMON_PITFALLS_CONTENT}}

## Related Steps
{{RELATED_STEPS_CONTENT}}

## Quick Reference
{{QUICK_REFERENCE_CONTENT}}
