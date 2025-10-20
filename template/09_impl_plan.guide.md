# 9. Implementation Plan

## Purpose
Translate the validated spec into an executable delivery roadmap that covers technology choices, sequencing, risks, and migration strategy. The implementation plan aligns teams on what will ship when, how dependencies are managed, and which experiments or spikes de-risk the path.

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

## Best Practices
- Capture `tech_stack` decisions with rationale, version constraints, and ownership so scaffold generation is predictable.
- Organize `milestones` by value increments tied to charter metrics or capability unlocks, including `target_date` where commitments exist.
- Document `risks` and `spikes` with clear mitigation steps to keep delivery adaptable.
- Detail the `migration_plan` when replacing legacy systems, calling out cutover criteria and rollback triggers.
- Enumerate `dependencies` across teams or vendors to schedule integration work early.

## Common Pitfalls
- Treating `tech_stack` as a grab bag with no versioning, leading to incompatible scaffolds or security gaps.
- Listing milestones without success signals, making it unclear when a stage is truly done.
- Ignoring migration steps, which causes surprise downtime or data loss later.
- Omitting external dependencies until late, creating critical path delays.

## Related Steps
- Step 2a: Delivery Baseline - Provides environment and CI assumptions this plan must satisfy.
- Step 8: Fixtures - Supplies the verification suite that gates milestone completion.
- Step 13: Scaffold - Consumes stack decisions and milestone ordering for code generation.
- Step 16: Delivery & Monitoring - Uses the plan to align deployments and operational readiness.

## Quick Reference
- **ID Format**: `impl_plan-<descriptor>`.
- **Required Fields**: must specify `tech_stack`; milestones, migration, and dependencies strengthen the plan.
- **Milestone IDs**: use `milestone-<sequence>`; include dates in ISO `YYYY-MM-DD` when known.
- **Trace Hooks**: connect milestones to FRs, capabilities, or charter metrics via references in descriptions.
