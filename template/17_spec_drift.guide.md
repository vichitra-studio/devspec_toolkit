# 17. Spec-Drift Audit

## Purpose
Define the automated audits that continuously compare live systems against the spec and trigger remediation when they diverge. This keeps the spec authoritative long after launch by closing the loop between runtime evidence and documented intent.

## Template / Fields
- Canonical artifact: **spec/17_spec_drift.json**
- Schema reference: `schema/17_spec_drift.schema.json` (do not inline schema; rely on `$schema` in JSON artifacts)
- Core atoms: `kebabId`, `owner`, `timestamp`, `tag` (see `schema/core/atoms.schema.json`)
- Core collections: `kebabIdArray`, `stringArray`, `link`, `traceRef`, `errorState`, `anyJson` (see `schema/core/collections.schema.json`)

## Prompt File
- Contract: `prompts/prompt_17_spec_drift.md`
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
- Create `checks` targeting APIs, schemas, NFRs, invariants, fixtures, or configs with `method` selections that reflect how drift is detected (runtime samples, log diffs, trace replays).
- Set meaningful `schedule` values (cron, per-release, hourly) and align them with operational reality.
- Use `severity` to communicate business impact and define `remediation` steps that include owners or playbooks.
- Update `last_run_at` after audits execute to provide traceable evidence of enforcement.

## Common Pitfalls
- Listing checks without specifying schedule or remediation, leaving responders unsure when and how to act.
- Choosing detection methods that cannot access the required data (e.g., runtime samples without observability hooks).
- Assigning all checks low severity, leading teams to ignore critical drift.
- Failing to keep `last_run_at` updated, which undermines audits during reviews.

## Related Steps
- Step 10: Governance - Defines how drift findings escalate into policy or spec updates.
- Step 16: Delivery & Monitoring - Provides telemetry sources that drift checks consume.
- Step 15: Red-Team Loop - Introduces new fixtures or mitigations that drift audits must cover.

## Quick Reference
- **ID Format**: `spec_drift-<descriptor>`; check IDs use `drift-<target>-<suffix>`.
- **Required Fields**: each check must include `check_id`, `target`, and `method`; add `schedule` and `severity` for actionable audits.
- **Method Options**: `runtime-sample`, `log-diff`, `schema-diff`, `trace-replay`.
- **Timestamps**: keep `last_run_at` in ISO-8601 (`YYYY-MM-DDThh:mm:ssZ`) to document enforcement.
