# 2. System Sketch

## Purpose
Build a lightweight architecture map that shows the components required to deliver the approved capabilities and how data flows between them. The system sketch communicates ownership, technology choices, and integration contracts early so interface design and delivery planning stay coherent.

## Template / Fields
- Canonical artifact: **spec/02_system_sketch.json**
- Schema reference: `schema/02_system_sketch.schema.json` (do not inline schema; rely on `$schema` in JSON artifacts)
- Core atoms: `kebabId`, `owner`, `timestamp`, `tag` (see `schema/core/atoms.schema.json`)
- Core collections: `kebabIdArray`, `stringArray`, `link`, `traceRef`, `errorState`, `anyJson` (see `schema/core/collections.schema.json`)

## Prompt File
- Contract: `prompts/prompt_02_system_sketch.md`
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
- Assign deterministic `component_id` values and tag each component with the correct `type` and owning team.
- List concrete `responsibilities` that map back to capabilities or FRs instead of vague descriptors.
- Define `connections` with protocol, auth, and reliability details so interface contracts and NFRs inherit accurate constraints.
- Mark external dependencies explicitly (`type: external`) to surface integration risk and monitoring needs.

## Common Pitfalls
- Treating the sketch as a diagram dump without responsibilities, leaving FRs unclear on ownership.
- Omitting external systems or shared services, causing blind spots in CI gates and monitoring.
- Forgetting to update `connections` when components change, breaking trace links for Step 05 APIs.
- Reusing IDs from other steps, which confuses schema validation and traceability tooling.

## Related Steps
- Step 1: Capabilities - Drives which components must exist and what they do.
- Step 5: Interface Contracts - Elaborates the requests/responses implied by each connection.
- Step 9: Implementation Plan - Uses component ownership and dependencies to order work.

## Quick Reference
- **ID Format**: `system_sketch-<descriptor>`; component IDs follow `component-<name>`.
- **Required Arrays**: `components` must be non-empty; `connections` optional but recommended when multiple components exist.
- **Component Types**: choose from `service`, `db`, `queue`, `cache`, `job`, `ui`, `lib`, `external`.
- **Trace Hooks**: populate `tags` and `owner` to align with FR packages and monitoring slices.
