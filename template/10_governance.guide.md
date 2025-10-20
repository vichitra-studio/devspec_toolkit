# 10. Governance / Change Control

## Purpose
Set the policies that keep the spec authoritative by covering change control, versioning, reviewer expectations, and how code changes reference spec artifacts. Strong governance ensures every update flows through spec-first workflows and remains auditable.

## Template / Fields
- Canonical artifact: **spec/10_governance.json**
- Schema reference: `schema/10_governance.schema.json` (do not inline schema; rely on `$schema` in JSON artifacts)
- Core atoms: `kebabId`, `owner`, `timestamp`, `tag` (see `schema/core/atoms.schema.json`)
- Core collections: `kebabIdArray`, `stringArray`, `link`, `traceRef`, `errorState`, `anyJson` (see `schema/core/collections.schema.json`)

## Prompt File
- Contract: `prompts/prompt_10_governance.md`
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
- Document the `versioning` strategy (calendar, semver, spec revision) so downstream tooling can bump versions consistently.
- Encode `pr_rules` that require spec diffs before implementation merges, including checklist items for validation commands.
- Flip `spec_first_policy` to true and describe when, if ever, exceptions are granted.
- Configure `commit_message_rules` with regex patterns and spec ID requirements to maintain traceability.
- List accountable `reviewers` with rotation notes or escalation paths to avoid approval bottlenecks.

## Common Pitfalls
- Leaving governance implied, leading teams to bypass spec updates during urgent fixes.
- Setting commit patterns that conflict with CI verification, causing constant false negatives.
- Forgetting to identify reviewers across disciplines, resulting in siloed approvals.
- Treating versioning as incidental, which breaks automation in Step 12 and Step 17.

## Related Steps
- Step 9: Implementation Plan - Uses governance policies to plan review bandwidth and sequencing.
- Step 12: CI Gates - Operationalizes PR rules and commit checks into automated enforcement.
- Step 17: Spec-Drift Audit - Relies on consistent governance to resolve drift findings.

## Quick Reference
- **ID Format**: `governance-<descriptor>` with `owner` commonly `ops` or `system`.
- **Required Fields**: must declare `spec_first_policy`; other sections should be filled for practical governance.
- **Commit Rules**: `require_spec_ids` should align with ID formats like `fr-*`, `api-*`, `fixture-*`.
- **Reviewer List**: maintain stable names or roles; update when ownership shifts.
