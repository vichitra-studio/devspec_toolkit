# 17. Spec-Drift Audit

## Purpose
Detect spec/runtime divergence and file remediation PRs.

## Template / Fields
- Canonical artifact: **spec/17_spec_drift.json**
- Schema reference: `schema/17_spec_drift.schema.json` (do not inline schema; rely on `$schema` in JSON artifacts)
- Core atoms: `kebabId`, `owner`, `timestamp`, `tag` (see `schema/core/atoms.schema.json`)
- Core collections: `kebabIdArray`, `stringArray`, `link`, `traceRef`, `errorState`, `anyJson` (see `schema/core/collections.schema.json`)

## Prompt File
- Contract: `prompts/prompt_17_spec_drift.md`
- Prompts produce exactly one fenced ```json``` block that validates against the above schema.

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
