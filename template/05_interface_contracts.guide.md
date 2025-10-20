# 5. Interface Contracts

## Purpose
Document the external facing contracts (routes, schemas, security, and versioning) that expose capabilities to clients and downstream systems. Accurate interface contracts let scaffolding tools, test fixtures, and runtime monitors enforce the spec without hand translation.

## Template / Fields
- Canonical artifact: **spec/05_interface_contracts.json**
- Schema reference: `schema/05_interface_contracts.schema.json` (do not inline schema; rely on `$schema` in JSON artifacts)
- Core atoms: `kebabId`, `owner`, `timestamp`, `tag` (see `schema/core/atoms.schema.json`)
- Core collections: `kebabIdArray`, `stringArray`, `link`, `traceRef`, `errorState`, `anyJson` (see `schema/core/collections.schema.json`)

## Prompt File
- Contract: `prompts/prompt_05_interface_contracts.md`
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
- Keep `api_id` stable and map each entry to an owning component from the system sketch.
- Use semver-compatible `version` strings (`v1`, `v1.1`) and update in lockstep with schema changes.
- Provide `request_schema_ref`, `response_schema_ref`, and enumerated `errors` so fixtures and clients know exact payloads.
- Define `security` and `auth` expectations explicitly to align with governance and monitoring.
- Populate `trace` references to FR IDs or capabilities proving why the interface exists.

## Common Pitfalls
- Forgetting to sync `route` or `method` with implementation scaffolds, breaking generated clients.
- Mixing multiple behaviors into a single API entry, hiding error handling and version strategy.
- Leaving `errors` empty, which prevents negative fixture coverage and red-team planning.
- Using free-form version strings that violate the schema pattern and confuse change management.

## Related Steps
- Step 2: System Sketch - Supplies component owners and integration points for each API.
- Step 4: Functional Requirements - Drives the acceptance criteria that each API must satisfy.
- Step 8: Fixtures - Consumes example refs and error states to build automated contract tests.
- Step 13: Scaffold - Generates code stubs directly from these definitions.

## Quick Reference
- **ID Format**: `interface_contracts-<descriptor>`; APIs use `api-<resource>-<action>`.
- **Required Fields**: each API needs `api_id`, `name`, `version`, `protocol`, and `owner`.
- **Allowed Protocols**: `http`, `grpc`, `ws`, `mqtt`; keep routes consistent with protocol semantics.
- **Security Flag**: choose from `none`, `api-key`, `oauth2`, `jwt`, `mTLS`; match governance policies.
- **Trace Hooks**: use `trace` to reference FRs (`fr-*`) or Capabilities (`capability-*`).
