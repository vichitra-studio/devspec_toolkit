# 18. Delivery & Monitoring

## Purpose
Document how code ships to each environment and how operational telemetry proves NFRs are met in production. This ensures delivery pipelines, dashboards, and alerting stay aligned with the spec as the system evolves.

## Template / Fields
- Canonical artifact: **spec/18_delivery_monitoring.json**
- Schema reference: `schema/18_delivery_monitoring.schema.json` (do not inline schema; rely on `$schema` in JSON artifacts)
- Core atoms: `kebabId`, `owner`, `timestamp`, `tag` (see `schema/core/atoms.schema.json`)
- Core collections: `kebabIdArray`, `stringArray`, `link`, `traceRef`, `errorState`, `anyJson` (see `schema/core/collections.schema.json`)

## Prompt File
- Contract: `prompts/prompt_18_delivery_monitoring.md`
- Prompts include context ingestion, operating flow, soft heuristics, and a self‑audit gate. Assistants follow a two‑phase flow:
  - Phase A — Clarify: ingest context and, if gating items are missing, output only a short bulleted list of questions.
  - Phase B — Emit: once clarified, output exactly one fenced ```json``` block that validates against the schema.

## Definition of Ready (DoR) / Guardrails
See [Shared Template Expectations](../docs/templates/shared_expectations.md#definition-of-ready-dor-guardrails).


## Working Increment
See [Shared Template Expectations](../docs/templates/shared_expectations.md#working-increment).


## Checks
See [Shared Template Expectations](../docs/templates/shared_expectations.md#checks).


## Failure Modes
See [Shared Template Expectations](../docs/templates/shared_expectations.md#failure-modes).

## Best Practices
- Record each deployment event with `env`, `build_id`, `artifact_uri`, and `status` to maintain an auditable release trail.
- Map dashboards to `nfr_refs` so every monitored metric can be traced back to the requirement it protects.
- Define alerts with actionable `rule` text and risk-appropriate `severity` to minimize pager fatigue.
- Keep deployment and monitoring data in sync with Step 02a environments and Step 12 CI gates.

## Common Pitfalls
- Leaving deployments undocumented, making rollback or release audits impossible.
- Building dashboards that track vanity metrics unrelated to spec-defined NFRs.
- Configuring alerts without clear thresholds or owners, leading to ignored incidents.
- Forgetting to update monitoring entries when NFR targets change, causing misaligned alerts.

## Related Steps
- Step 7: NFRs - Provides the targets dashboards and alerts must enforce.
- Step 12: CI Gates - Ensures pre-deploy checks run before the recorded deployments trigger.
- Step 19: Spec-Drift Audit - Uses deployment and monitoring data to detect divergence.

## Quick Reference
- **ID Format**: `delivery_monitoring-<descriptor>`.
- **Deployments**: always include `env` (`dev`, `staging`, `prod`) and `build_id`; update `status` (`pending`, `success`, `failed`).
- **Dashboards**: link `dashboard_id` to one or more `nfr_refs`; store observational URLs.
- **Alerts**: severity options mirror red-team usage (`low`, `medium`, `high`, `critical`); reference NFR IDs when possible.
