# Step 01 · Capabilities

> **REQUIRED**: Before starting, read `$TOOLKIT_ROOT/docs/prompts/shared_expectations.md` in full. All directives in that document apply to this step unless explicitly overridden below. Do not proceed without reading it.

Run `specdev prompt-context 01` to see downstream consumers. This prompt's output feeds 7 downstream steps.

## Role
You are a **senior capability architect and systems analyst**. Your job is to decompose product intent into a complete, non-overlapping set of system capabilities that fully covers stakeholder JTBD and cross-cutting concerns.

## Purpose
Translate the charter into a catalog of system capabilities with explicit verbs, scope boundaries, and operating conditions. This step defines what value the system must deliver, when it is intentionally deferred, and how each capability traces back to stakeholders and success metrics.

## Extraction Intent

For each upstream artifact ingested, extract the following:
- **docs/seed/seed_overview.md** (required): Scope boundaries, user persona definitions, high-level feature expectations, and product vision for capability derivation
- **00_charter.json**: Project goals, success metrics, in/out-of-scope items, and stakeholder needs to anchor capability boundaries; use canonical nouns/verbs from charter language; do not depend on downstream glossary/FR artifacts

## Operating Flow: Discover → Cross-Cut → Trace → Emit
- **Discover**: Build a private Context Ledger of candidate capabilities as verb–object pairs derived from charter goals, user JTBD, and glossary nouns; include proposed scope (in/out/future), natural owner, inputs/outputs, and key error states. Do not output it.
- **Cross-Cut**: Verify each capability exists in `spec/00_charter.json` `in_scope` or `goals`, and does not contradict `out_of_scope` or constraints in `docs/seed/seed_overview.md`. If a capability cannot be traced to a charter goal or seed requirement, ask a Gap Question. Apply the Cross-Cutting Capability Checklist below.
- **Trace**: Rewrite to single, testable behaviors with explicit boundaries and error states; propose `trace` hooks to FRs (if any exist) or omit the trace entry until FR IDs are known. For each in-scope user segment's `jobs_to_be_done` from `00_charter.json`, verify at least one capability traces to that job. Any uncovered JTBD must either generate a new capability or be explicitly listed as out-of-scope.
- **Emit**: Emit JSON after alignment.

### Cross-Cutting Capability Checklist (AUDIT-081)
Before finalizing, verify these system-level capabilities are considered:
- Authentication and authorization management
- Audit logging and observability
- Error handling and graceful degradation
- Configuration and feature-flag management
- Data lifecycle (retention, archival, deletion)
- Rate limiting and backpressure
- Notifications and event emission
- Multi-tenancy or environment isolation (if applicable)

## Heuristics For Completeness
- MUST include pre/postconditions for capabilities when `spec/00_charter.json` constraints or `docs/seed/seed_overview.md` define prerequisites or side effects; MUST include owner for any capability that spans multiple components as identified in upstream artifacts.
- Auto-trace seeds: if an FR list has been generated downstream and contains FR IDs, add a `trace` to matching FRs; otherwise, omit the trace entry until FR IDs are known.
- Naming: MUST use `cap-{noun}-{verb-or-noun}` format (e.g., `cap-user-authentication`) when a matching term exists in `spec/00_charter.json` or `docs/seed/seed_overview.md`; MUST NOT use UI-screen or database-table names as capability identifiers.

## Self-Audit Gate
> Per shared_expectations: if ANY item below cannot be satisfied, enter Clarify mode.
- `spec/00_charter.json` is present and contains at least one in_scope entry.
- `spec/00_charter.json` is present and contains at least one user_segments entry.
- `docs/seed/seed_overview.md` is present and non-empty.

## Negative Constraints
- **DO NOT** overlap capability scopes; each capability must have a clear boundary.
- **DO NOT** use generic verbs ("manage", "handle"); MUST use specific action verbs derived from `spec/00_charter.json` goals and `docs/seed/seed_overview.md` user jobs.
- **DO NOT** leave `trace` fields empty; omit `trace` entries whose target IDs are not yet known rather than using invalid placeholder values.
- **DO NOT** invent capabilities that are not supported by the Charter goals.

## Coverage Closure
Before emitting, verify:
- Every in-scope item and success metric in `spec/00_charter.json` is addressed by ≥1 `capability_id`, OR explicitly listed in `out_of_scope` with rationale.
- No charter scope item is silently dropped — each must map to at least one named capability.
- All `trace` entries reference IDs present in `spec/00_charter.json` (`success_metrics[*].metric_id`, `user_segments[*].segment_id`).
- If any charter goal cannot be mapped to a capability: add a gap question (Clarify mode) rather than omitting it.
- [ ] Every upstream ID referenced in extraction intent has been consumed
- [ ] No placeholder tokens remain (TBD, TODO, FIXME, XXX)
- [ ] All required fields populated from actual upstream data (not hallucinated)
- [ ] Every JTBD from charter's `user_segments` is served by at least one in-scope capability
- [ ] All cross-cutting concerns (auth, observability, error handling, rate limiting, audit) have dedicated capabilities
- [ ] No two capabilities describe overlapping behaviors (check for duplication)
- [ ] Every capability has a clearly defined `scope` value

## Step-Specific Completeness Checklist
- Capabilities cover the full scope of the charter/user segments; each is a single verb-driven behavior (e.g., "search products", "issue refund").
- Each capability has an explicit `scope` (see schema for allowed values); avoid leaving planned but deferred work as `in`.
- Include `owner` for each capability reflecting the accountable team for delivery.
- Preconditions, postconditions, and error_states are set for non-trivial capabilities.
- Inputs/outputs are concrete (e.g., IDs, payload shapes, key fields), not hand-wavy.
- Trace includes at least one reference to FRs or known interfaces once available; omit trace entries whose target IDs are not yet known.

## Best Practices
- **Verbs**: Phrase each `verb` as an observable action (e.g., "issue invoice"), avoiding generic "manage" or "handle".
- **Scope**: Set realistic scope to focus delivery; align with charter.
- **Handshake**: Enumerate `inputs`, `outputs`, `preconditions`, and `postconditions` so downstream FRs and interfaces know the full handshake.
- **Failures**: Capture `error_states` with user-visible impacts to drive fixture coverage.
- **Trace**: Use `trace` to connect capabilities to charter metrics, FRs, or governance requirements.

## Common Pitfalls
- **Marketing Fluff**: Copying marketing language instead of measurable verbs leads to ambiguous FRs.
- **Hidden Dependencies**: Marking items `in` scope without explicit preconditions.
- **Implementation Leak**: Capabilities that mirror UI screens or database tables instead of user value.
- **Duplicate IDs**: Duplicating capabilities with different IDs, breaking traceability.
- **Undefined I/O**: Leaving inputs/outputs undefined makes API generation impossible.

# Clarification Questions
- Which core user jobs require first-class capabilities now vs later? What must not be built?
- For each capability, what are the minimal inputs/outputs needed to prove it works end-to-end?
- What are the typical preconditions and postconditions? Any compliance or data retention implications?
- What are the top 3 error states per high-risk capability and how should they be surfaced?
- Which team owns each capability across build/operate/support? Any shared ownership to flag?
    - *Note:* Owner must be one of the canonical values defined in the schema (vc:core:atoms#owner); choose whoever is accountable for building and maintaining this capability.
- Which FRs or APIs (existing or anticipated) does each capability map to?

# Schema Reference
- Schema URI: vc:01-capabilities
- Schema File: schema/01_capabilities.schema.json
- Schema Registry: tools/schema_registry.json

# Output Contract
```json
{
  "$schema": "vc:01-capabilities",
  "id": "capabilities-v1",
  "owner": "api",
  "created_at": "2025-01-01T00:00:00Z",
  "capabilities": [
    {
      "capability_id": "cap-user-authentication",
      "verb": "authenticate",
      "scope": "in",
      "capability_ref": {
        "id": "cn:project:capability:user-authentication",
        "kind": "capability"
      },
      "trace": [
        {
          "type": "charter-goal",
          "id": "goal-login-success-rate",
          "note": "Derives from: login-success-rate charter success metric; capability directly drives the login success rate success metric"
        }
      ]
    }
  ],
  "canonical_refs_used": []
}
```

