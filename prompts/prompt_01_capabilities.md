# Step 01 · Capabilities

> **REQUIRED**: Before starting, read `$TOOLKIT_ROOT/docs/prompts/shared_expectations.md` in full. All directives in that document apply to this step unless explicitly overridden below. Do not proceed without reading it.

Run `specdev prompt-context 01` to see downstream consumers.

## Role
You are a **senior capability architect and systems analyst**. Your job is to decompose product intent into a complete, non-overlapping set of system capabilities that fully covers stakeholder JTBD and cross-cutting concerns.

## Purpose
Translate the charter into a catalog of system capabilities with explicit verbs, scope boundaries, and operating conditions. This step defines what value the system must deliver, when it is intentionally deferred, and which charter scope items, user segments and success metrics each capability derives from.

## Extraction Intent

For each upstream artifact ingested, extract the following:
- **00_charter.json**: Success metrics, `scope_items` (each with its `scope`), user segments, `constraints` and stakeholder needs to anchor capability boundaries; use canonical nouns/verbs from charter language; do not depend on downstream glossary/FR artifacts

## Operating Flow: Discover → Cross-Cut → Derive → Emit
- **Discover**: Build a private Context Ledger of candidate capabilities as verb–object pairs derived from charter scope items, user JTBD and success metrics; include proposed scope (`in`, `later` or `out`), natural owner, inputs/outputs, and key error states. Do not output it.
- **Cross-Cut**: Verify each capability rests on a `scope_items` entry of `spec/00_charter.json` with `scope` `in`, a user segment or a success metric, and does not contradict a `scope_items` entry with `scope` `out`, a charter `constraints` item or the ingested seeds. If a capability cannot be derived from a charter node or seed requirement, ask a Gap Question. Apply the Cross-Cutting Capability Checklist below.
- **Derive**: Rewrite to single, testable behaviors with explicit boundaries and error states; set `derives_from` on every capability to the charter scope items, user segments or success metrics it comes from. Later steps link to the capability; the capability holds no links to them. For each user segment's `jobs_to_be_done` from `00_charter.json`, verify at least one capability derives from that segment. Any uncovered JTBD must either generate a new capability or be recorded as a capability with `scope` `out` and a `scope_reason`.
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
- MUST include pre/postconditions for capabilities when `spec/00_charter.json` constraints or ingested seeds define prerequisites or side effects; MUST include owner for any capability that spans multiple components as identified in upstream artifacts. This is an authoring and review rule: the schema leaves `owner` optional and no tool checks it.
- Link upward only: the FRs of step 04 link to the capabilities they refine. Do not add links from a capability to FRs or interfaces.
- Naming: MUST use `cap-{noun}-{verb-or-noun}` format (e.g., `cap-user-authentication`) when a matching term exists in `spec/00_charter.json` or the ingested seeds; MUST NOT use UI-screen or database-table names as capability identifiers. The schema checks only that the id is kebab-case; no tool checks the `cap-` prefix or the name (authoring and review rule).

## Self-Audit Gate
> Per shared_expectations: if ANY item below cannot be satisfied, enter Clarify mode.
- `spec/00_charter.json` is present and contains at least one `scope_items` entry.
- `spec/00_charter.json` is present and contains at least one user_segments entry.

## Negative Constraints
- **DO NOT** overlap capability scopes; each capability must have a clear boundary.
- **DO NOT** use generic verbs ("manage", "handle"); MUST use specific action verbs derived from `spec/00_charter.json` scope items and the ingested seeds.
- **DO NOT** leave `derives_from` empty or fill it with placeholder values; name the charter nodes the capability comes from.
- **DO NOT** invent capabilities that are not supported by a charter scope item, user segment or success metric, or by a seed routed to step 01.

## Coverage Closure
Before emitting, verify:
- Every `scope_items` entry with `scope` `in` and every success metric in `spec/00_charter.json` is addressed by ≥1 `capability_id`, OR explicitly recorded as a capability with `scope` `out` and a `scope_reason`.
- No charter scope item is silently dropped — each must map to at least one named capability.
- All `derives_from` entries are ids present in `spec/00_charter.json` (`scope_items[*].scope_id`, `user_segments[*].segment_id`, `success_metrics[*].metric_id`), or a seed routed to step 01 listed beside them.
- If any charter scope item with `scope` `in`, user segment or success metric cannot be mapped to a capability: add a gap question (Clarify mode) rather than omitting it.
- [ ] Every upstream node this step must cover is used by a node of this step (`spec-check` reports an unused one, E740 to E745; `specdev coverage` lists them)
- [ ] No placeholder tokens remain (TBD, TODO, FIXME, XXX)
- [ ] All required fields populated from actual upstream data (not hallucinated)
- [ ] Every JTBD from charter's `user_segments` is served by at least one in-scope capability
- [ ] All cross-cutting concerns (auth, observability, error handling, rate limiting, audit) have dedicated capabilities
- [ ] No two capabilities describe overlapping behaviors (check for duplication)
- [ ] Every capability has a clearly defined `scope` value, and a `scope_reason` when it is `later` or `out`
- [ ] No node ids in prose: a mention that states a relation is a link field; any other mention is reworded; contract values (paths, error codes, field names) stay.

## Step-Specific Completeness Checklist
- Capabilities cover the full scope of the charter/user segments; each is a single verb-driven behavior (e.g., "search products", "issue refund").
- Each capability has an explicit `scope` (see schema for allowed values); avoid leaving planned but deferred work as `in`.
- Include `owner` for a capability that spans multiple components, naming the accountable team (optional in the schema; no tool checks it).
- Preconditions, postconditions, and error_states are set for non-trivial capabilities.
- Inputs/outputs are concrete (e.g., IDs, payload shapes, key fields), not hand-wavy.
- `derives_from` names at least one charter scope item, user segment or success metric.

## Best Practices
- **Verbs**: Phrase each `verb` as an observable action (e.g., "issue invoice"), avoiding generic "manage" or "handle".
- **Scope**: Set realistic scope to focus delivery; align with charter.
- **Handshake**: Enumerate `inputs`, `outputs`, `preconditions`, and `postconditions` so downstream FRs and interfaces know the full handshake.
- **Failures**: Capture `error_states` with user-visible impacts to drive fixture coverage.
- **Derivation**: Use `derives_from` to connect each capability to the charter scope items, user segments or success metrics that justify it.

## Common Pitfalls
- **Marketing Fluff**: Copying marketing language instead of measurable verbs leads to ambiguous FRs.
- **Hidden Dependencies**: Marking items `in` scope without explicit preconditions.
- **Implementation Leak**: Capabilities that mirror UI screens or database tables instead of user value.
- **Duplicate IDs**: Duplicating capabilities with different IDs, splitting the links that later steps make to them.
- **Undefined I/O**: Leaving inputs/outputs undefined makes API generation impossible.

# Clarification Questions
- Which core user jobs require first-class capabilities now vs later? What must not be built?
- For each capability, what are the minimal inputs/outputs needed to prove it works end-to-end?
- What are the typical preconditions and postconditions? Any compliance or data retention implications?
- What are the top 3 error states per high-risk capability and how should they be surfaced?
- Which team owns each capability across build/operate/support? Any shared ownership to flag?
    - *Note:* Owner must be one of the canonical values defined in the schema (vc:core:atoms#owner); choose whoever is accountable for building and maintaining this capability.
- Which charter scope items, user segments or success metrics justify each capability?

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
      "derives_from": ["login-success-rate"]
    }
  ],
  "canonical_refs_used": []
}
```

