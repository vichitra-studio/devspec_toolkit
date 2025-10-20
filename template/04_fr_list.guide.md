# 4. Functional Requirements

## Purpose
State behavioral requirements with acceptance criteria and traces.

## Template / Fields
- Canonical artifact: **spec/04_fr_list.json**
- Schema reference: `schema/04_fr_list.schema.json` (do not inline schema; rely on `$schema` in JSON artifacts)
- Core atoms: `kebabId`, `owner`, `timestamp`, `tag` (see `schema/core/atoms.schema.json`)
- Core collections: `kebabIdArray`, `stringArray`, `link`, `traceRef`, `errorState`, `anyJson` (see `schema/core/collections.schema.json`)

## Prompt File
- Contract: `prompts/prompt_04_functional_requirements.md`
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
- Write FRs that are testable and measurable.
- Include clear acceptance criteria for each requirement.
- Link FRs to specific capabilities or APIs using trace references.
- Keep statements concise and avoid ambiguity.

## Common Pitfalls
- Non-testable requirements that cannot be verified.
- Missing acceptance criteria for functional requirements.
- Failure to link FRs to underlying APIs or capabilities.
- Including too much implementation detail in the requirement.

## Related Steps
- Step 0: Project Charter - Provides context for defining requirements
- Step 1: Capabilities - Functional requirements derive from capabilities
- Step 5: Interface Contracts - FRs map to API contracts
- Step 8: Test Plan & Fixtures - FR acceptance criteria become fixtures

## Quick Reference
- **ID Format**: `fr-<descriptor>`
- **Owner**: Typically `api`, `ui`, or `system`
- **Key Fields**: statement, acceptance_criteria, trace
