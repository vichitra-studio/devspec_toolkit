# 16. Fixture-Driven Implementation

## Purpose
Track implementation progress against the fixture suite, recording which endpoints are live and how each automated test is behaving. This artifact keeps delivery honest by requiring fixture parity before declaring features done.

## Template / Fields
- Canonical artifact: **spec/16_fixture_impl.json**
- Schema reference: `schema/16_fixture_impl.schema.json` (do not inline schema; rely on `$schema` in JSON artifacts)
- Core atoms: `kebabId`, `owner`, `timestamp`, `tag` (see `schema/core/atoms.schema.json`)
- Core collections: `kebabIdArray`, `stringArray`, `link`, `traceRef`, `errorState`, `anyJson` (see `schema/core/collections.schema.json`)

## Prompt File
- Contract: `prompts/prompt_16_fixture_impl.md`
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
- Update `implemented_endpoints` as soon as scaffolded routes gain real logic so trace coverage stays current.
- Log every fixture run in `test_results`, including failures or skips with actionable `notes`.
- Keep `ci_status` in sync with pipeline health; treat `red` as a signal to pause merges.
- Use failing fixture notes to capture hypotheses or next steps, feeding back into FR or red-team updates when needed.

## Common Pitfalls
- Marking fixtures as pass without rerunning after code changes, producing stale truth.
- Leaving failed fixtures without notes, making it unclear who owns the fix.
- Forgetting to list newly implemented endpoints, leading to underreported progress.
- Treating CI status as green even when local runs fail, eroding trust in the artifact.

## Related Steps
- Step 8: Fixtures - Provides the canonical list of tests each implementation must satisfy.
- Step 13: Scaffold - Establishes the baseline routes that implementation builds upon.
- Step 15: Red-Team Loop - Adds new adversarial fixtures that must be reflected here.

## Quick Reference
- **ID Format**: `fixture_impl-<descriptor>`.
- **Required Fields**: must include `implemented_endpoints` plus `test_results` entries for executed fixtures.
- **Status Values**: fixture status is `pass`, `fail`, or `skip`; CI status is `green` or `red`.
- **Trace Hooks**: align endpoint IDs with `api-*` values and fixture refs with Step 08 definitions.
