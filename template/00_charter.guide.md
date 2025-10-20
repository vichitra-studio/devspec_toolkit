# 0. Project Charter

## Purpose
Establish the authoritative charter that captures the business problem, intended users, constraints, and measurable success criteria in falsifiable language. This artifact anchors downstream decisions by making scope boundaries, stakeholder needs, and success metrics explicit enough to trace through every later step.

## Template / Fields
- Canonical artifact: **spec/00_charter.json**
- Schema reference: `schema/00_charter.schema.json` (do not inline schema; rely on `$schema` in JSON artifacts)
- Core atoms: `kebabId`, `owner`, `timestamp`, `tag` (see `schema/core/atoms.schema.json`)
- Core collections: `kebabIdArray`, `stringArray`, `link`, `traceRef`, `errorState`, `anyJson` (see `schema/core/collections.schema.json`)

## Prompt File
- Contract: `prompts/prompt_00_project_charter.md`
- Prompts produce exactly one fenced ```json``` block that validates against the above schema.

## Definition of Ready (DoR) / Guardrails
See [Shared Template Expectations](../docs/templates/shared_expectations.md#definition-of-ready-dor-guardrails).


## Working Increment
See [Shared Template Expectations](../docs/templates/shared_expectations.md#working-increment).


## Checks
See [Shared Template Expectations](../docs/templates/shared_expectations.md#checks).


## Failure Modes
See [Shared Template Expectations](../docs/templates/shared_expectations.md#failure-modes).


## Best Practices
- Pair each `success_metric` with a realistic baseline, target, unit, and measurement method so CI can validate progress.
- Capture scope in both `in_scope` and `out_of_scope` lists to prevent downstream capability creep.
- Describe each `user_segment` with jobs-to-be-done, pains, and gains so requirements map cleanly to user value.
- Record critical `assumptions` and `risks` with enough context to inform governance and red-team work.

## Common Pitfalls
- Writing solution statements instead of clear problem statements, which hides falsifiable success measures.
- Leaving success metrics without baselines or units, making progress impossible to evaluate.
- Forgetting stakeholders or user segments, which breaks traceability to downstream capabilities and FRs.
- Treating assumptions as implicit, leaving governance and risk mitigation blind.

## Related Steps
- Step 1: Capabilities - Derive verbs and boundaries from the charter's scope statements.
- Step 4: Functional Requirements - Translate the problem statement and metrics into falsifiable behaviors.
- Step 9: Implementation Plan - Sequence delivery to hit the charter's success metrics and mitigate captured risks.

## Quick Reference
- **ID Format**: `project_charter-<descriptor>`; keep stable once referenced.
- **Minimum Required**: `problem_statement` plus at least one `success_metric`.
- **Trace Hooks**: Use `links` to connect governance docs or discovery research.
- **Stakeholder Data**: `stakeholders` and `user_segments` should align with FR owners and test personas.
