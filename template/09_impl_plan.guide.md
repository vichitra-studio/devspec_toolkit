# 9. Implementation Plan

## Purpose
Outline tech stack, milestones, migration, and dependencies.

## Template / Fields
- Canonical artifact: **spec/09_impl_plan.json**
- Schema reference: `schema/09_impl_plan.schema.json` (do not inline schema; rely on `$schema` in JSON artifacts)
- Core atoms: `kebabId`, `owner`, `timestamp`, `tag` (see `schema/core/atoms.schema.json`)
- Core collections: `kebabIdArray`, `stringArray`, `link`, `traceRef`, `errorState`, `anyJson` (see `schema/core/collections.schema.json`)

## Prompt File
- Contract: `prompts/prompt_09_impl_plan.md`
- Prompts produce exactly one fenced ```json``` block that validates against the above schema.

## Definition of Ready (DoR) / Guardrails
See [Definition of Ready](../docs/templates/definition_of_ready.md)

## Working Increment
See [Shared Template Expectations](../docs/templates/shared_expectations.md#working-increment).

## Checks
See [Shared Template Expectations](../docs/templates/shared_expectations.md#checks).

## Failure Modes
See [Shared Template Expectations](../docs/templates/shared_expectations.md#failure-modes).
