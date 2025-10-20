# 13. Scaffold Generation

## Purpose
Generate compile-clean service skeletons and route bindings directly from the spec, capturing any manual follow-up required to keep the scaffold aligned. This artifact proves the contracts are implementable and tracks validation tasks before teams start feature work.

## Template / Fields
- Canonical artifact: **spec/13_scaffold.json**
- Schema reference: `schema/13_scaffold.schema.json` (do not inline schema; rely on `$schema` in JSON artifacts)
- Core atoms: `kebabId`, `owner`, `timestamp`, `tag` (see `schema/core/atoms.schema.json`)
- Core collections: `kebabIdArray`, `stringArray`, `link`, `traceRef`, `errorState`, `anyJson` (see `schema/core/collections.schema.json`)

## Prompt File
- Contract: `prompts/prompt_13_scaffold.md`
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
- Mirror Step 05 interface contracts when building the `route_map`, keeping `api_ref`, `path`, and `method` in sync.
- Document `service_skeleton` choices (language, framework, modules) so contributors can bootstrap identical environments.
- Populate `validators` with commands (lint, type-check, schema validation) executed after scaffold generation.
- Track `build_status` honestly (`green`, `red`, `pending`) to surface blockers before implementation accelerates.

## Common Pitfalls
- Leaving modules unspecified, forcing teams to rediscover scaffold layout.
- Forgetting to include new or versioned APIs, leading to missing routes and broken fixtures.
- Marking build status green without running validators, giving a false sense of readiness.
- Creating route paths that differ from Step 05 definitions, breaking client compatibility.

## Related Steps
- Step 5: Interface Contracts - Supplies the API definitions that scaffolding must honor.
- Step 9: Implementation Plan - Uses scaffold status to schedule feature development.
- Step 14: Fixture Implementation - Builds on the scaffold to satisfy fixtures and acceptance criteria.

## Quick Reference
- **ID Format**: `scaffold-<descriptor>`; routes reference `api-*` IDs.
- **Required Fields**: must include `service_skeleton.language` and a non-empty `route_map`.
- **Build Status**: one of `pending`, `green`, or `red`; update as validators run.
- **Validator List**: capture exact CLI commands to reproduce scaffold health checks.
