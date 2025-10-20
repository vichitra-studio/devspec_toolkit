# 12. CI Gates

## Purpose
Translate governance rules and fixture expectations into enforceable CI automation. Well-specified gates keep the spec authoritative by blocking merges that violate schemas, fixtures, or coverage commitments.

## Template / Fields
- Canonical artifact: **spec/12_ci_gates.json**
- Schema reference: `schema/12_ci_gates.schema.json` (do not inline schema; rely on `$schema` in JSON artifacts)
- Core atoms: `kebabId`, `owner`, `timestamp`, `tag` (see `schema/core/atoms.schema.json`)
- Core collections: `kebabIdArray`, `stringArray`, `link`, `traceRef`, `errorState`, `anyJson` (see `schema/core/collections.schema.json`)

## Prompt File
- Contract: `prompts/prompt_12_ci_gates.md`
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
- Define each `job` with reproducible `steps` (CLI commands, scripts) and `requires` dependencies to express the pipeline graph.
- Align job names with reality (e.g., `validate`, `fixtures`, `redteam`, `deploy`) to match tooling and dashboards.
- Set `coverage_thresholds` that reflect NFR commitments and update them when metric expectations change.
- Keep job IDs in kebab-case and stable so generated CI configs and monitoring references remain valid.

## Common Pitfalls
- Leaving steps as generic notes instead of exact commands, making automation impossible.
- Forgetting job dependencies, causing parallel runs that violate required ordering (e.g., fixtures before deploy).
- Setting aspirational coverage numbers with no plan to meet them, leading to perma-red pipelines.
- Duplicating job IDs or renaming them without updating CI scripts and governance docs.

## Related Steps
- Step 2a: Delivery Baseline - Seeds initial job list and secrets needed by the pipeline.
- Step 8: Fixtures - Provides test suites that CI must execute and report.
- Step 10: Governance - Defines policy that CI gates operationalize.
- Step 15: Red-Team Loop - Adds adversarial jobs or steps as the threat model evolves.

## Quick Reference
- **ID Format**: `ci_gates-<descriptor>`; jobs use `job-<name>`.
- **Required Fields**: each job needs `job_id`, `name`, and at least one `steps` entry.
- **Coverage Bounds**: numbers are percentages (0-100); omit only if intentionally unmanaged.
- **Dependency Graph**: `requires` lists upstream job IDs; leave empty for roots.
