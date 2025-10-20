# 7. Non-Functional Requirements

## Purpose
Define the measurable performance, reliability, security, and operational targets that keep the product trustworthy once it ships. These benchmarks inform design trade-offs, fixtures, monitoring, and delivery plans so non-functional needs stay visible.

## Template / Fields
- Canonical artifact: **spec/07_nfrs.json**
- Schema reference: `schema/07_nfrs.schema.json` (do not inline schema; rely on `$schema` in JSON artifacts)
- Core atoms: `kebabId`, `owner`, `timestamp`, `tag` (see `schema/core/atoms.schema.json`)
- Core collections: `kebabIdArray`, `stringArray`, `link`, `traceRef`, `errorState`, `anyJson` (see `schema/core/collections.schema.json`)

## Prompt File
- Contract: `prompts/prompt_07_nfrs.md`
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
- Assign each NFR to a schema `category` and describe the `metric` in precise, customer-facing terms.
- Provide numeric `target` values with `unit` and `measurement_method` so monitoring and CI use the same test.
- Set `stage` to the earliest environment that must enforce the target (dev, staging, prod) to guide rollout plans.
- Use `trace` to connect NFRs to FRs, invariants, or delivery tasks that uphold the requirement.

## Common Pitfalls
- Writing qualitative statements (e.g., "fast") instead of measurable targets.
- Forgetting to specify the measurement method, leading to inconsistent monitoring dashboards.
- Using prod-only targets without staging or dev expectations, making regressions invisible until go-live.
- Duplicating NFR IDs across categories, which breaks coverage tooling.

## Related Steps
- Step 4: Functional Requirements - Reveals where NFRs must be applied to customer journeys.
- Step 16: Delivery & Monitoring - Maps these metrics to dashboards, alerts, and runbooks.
- Step 12: CI Gates - Implements automated tests or checks that enforce NFR thresholds.

## Quick Reference
- **ID Format**: `nfr-<category>-<descriptor>`.
- **Required Fields**: each entry needs `nfr_id`, `category`, `metric`, `target`, and `unit`.
- **Categories**: choose from latency, throughput, availability, durability, cost, security, privacy, maintainability, usability, portability, energy.
- **Trace Hooks**: link to FRs (`fr-*`), invariants (`invariant-*`), or monitoring tasks in Step 16.
