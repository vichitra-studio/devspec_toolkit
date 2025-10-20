# 1. Capabilities

## Purpose
Translate the charter into a catalog of system capabilities with explicit verbs, scope boundaries, and operating conditions. This step defines what value the system must deliver, when it is intentionally deferred, and how each capability traces back to stakeholders and success metrics.

## Template / Fields
- Canonical artifact: **spec/01_capabilities.json**
- Schema reference: `schema/01_capabilities.schema.json` (do not inline schema; rely on `$schema` in JSON artifacts)
- Core atoms: `kebabId`, `owner`, `timestamp`, `tag` (see `schema/core/atoms.schema.json`)
- Core collections: `kebabIdArray`, `stringArray`, `link`, `traceRef`, `errorState`, `anyJson` (see `schema/core/collections.schema.json`)

## Prompt File
- Contract: `prompts/prompt_01_capabilities.md`
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
- Phrase each `verb` as an observable action (e.g., "issue invoice") and align `scope` with the charter's in/out/future decisions.
- Enumerate `inputs`, `outputs`, `preconditions`, and `postconditions` so downstream FRs and interfaces know the full handshake.
- Capture `error_states` with user-visible impacts to drive fixture coverage and red-team scenarios.
- Use `trace` references to link capabilities to charter metrics, FR IDs, or governance requirements.

## Common Pitfalls
- Copying marketing language instead of measurable verbs leads to ambiguous FRs.
- Marking items `in` scope without explicit preconditions, causing hidden dependencies later.
- Duplicating capabilities with different IDs, breaking traceability to FRs and CI gates.
- Leaving future work as `in` scope, which undermines milestone planning in Step 09.

## Related Steps
- Step 0: Project Charter - Provides constraints and goals that justify each capability.
- Step 4: Functional Requirements - Breaks each capability into falsifiable behaviors.
- Step 9: Implementation Plan - Uses scope labels to schedule what ships when.

## Quick Reference
- **ID Format**: `capability-<verb>`; keep consistent if referenced by FRs.
- **Required Fields**: every entry needs `capability_id`, `verb`, and `scope`.
- **Scope Values**: only `in`, `out`, or `future` are allowed; no free-form text.
- **Trace Hooks**: prefer `trace` entries pointing to charter metrics or FR IDs.
