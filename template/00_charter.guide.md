# 0. Project Charter

## Purpose
Define problem, scope, users, and success metrics in falsifiable terms.

## Template / Fields
- Canonical artifact: **spec/00_charter.json**
- Schema reference: `schema/00_charter.schema.json` (do not inline schema; rely on `$schema` in JSON artifacts)
- Core atoms: `kebabId`, `owner`, `timestamp`, `tag` (see `schema/core/atoms.schema.json`)
- Core collections: `kebabIdArray`, `stringArray`, `link`, `traceRef`, `errorState`, `anyJson` (see `schema/core/collections.schema.json`)

## Prompt File
- Contract: `prompts/prompt_00_project_charter.md`
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

## Best Practices
- Clearly define success metrics with units and baselines.
- Use concrete language instead of vague terms like "good" or "efficient".
- Ensure stakeholder needs are captured in the problem statement.
- Include explicit preconditions and postconditions where applicable.

## Common Pitfalls
- Vague problem statements that cannot be tested or verified.
- Missing success metrics or metrics without baselines.
- Failing to distinguish between in-scope and out-of-scope items.
- Not identifying key assumptions that could impact the solution.

## Related Steps
- Step 1: Capabilities - Links to capabilities that this charter supports
- Step 4: Functional Requirements - Provides context for FRs to be defined
- Step 9: Implementation Plan - Uses charter as a foundation for planning

## Quick Reference
- **ID Format**: `project_charter-<descriptor>`
- **Owner**: Typically `api`, `ui`, or `system`
- **Key Fields**: problem_statement, success_metrics, in_scope, out_of_scope
