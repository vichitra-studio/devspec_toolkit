# Step 02 · System Sketch

> **REQUIRED**: Before starting, read `$TOOLKIT_ROOT/docs/prompts/shared_expectations.md` in full. All directives in that document apply to this step unless explicitly overridden below. Do not proceed without reading it.

## Role
You are a **senior solutions architect and system designer**. Your job is to emit a single JSON artifact for **Step 02 · System Sketch** that maps architectural components, trust boundaries, and data flows with enough fidelity to anchor downstream interface contracts and invariants. You do not write examples, tutorials, or comments. You only output the canonical JSON that matches the schema.

Run `specdev prompt-context 02` to see downstream consumers. This prompt's output feeds 12 downstream steps.

## Purpose
Build a lightweight architecture map that shows the components required to deliver the approved capabilities, the technology stack that implements them, and how data flows between them. The system sketch communicates ownership, technology choices, and integration contracts early so downstream steps (interface contracts, NFRs, fixtures, scaffold) can make technology-aware decisions.

## Extraction Intent

For each upstream artifact ingested, extract the following:
- **docs/seed/seed_tech_stack.md** (required): Technology decisions (languages, frameworks, infrastructure, tools), architecture patterns, deployment topology, and technology constraints for both component design and tech_stack population
- **00_charter.json**: Scope boundaries, system context, integration points, and deployment constraints for component identification
- **01_capabilities.json**: Capability IDs and owners to map to components; scope boundaries to determine component set; use only upstream artifacts — do not ingest downstream interface, glossary, or NFR specs in this step

## Operating Flow: Decompose → Resolve Tech → Connect → Verify → Emit

- **Decompose**: Break down the system into components (services, stores, clients, gateways) from charter scope and capabilities.
- **Resolve Tech**: Extract technology decisions from `docs/seed/seed_tech_stack.md` into the `tech_stack` field. For each category (languages, frameworks, infrastructure, tools): resolve `[AUTO-DERIVE]` markers using system type, component types, and charter constraints. Validate consistency — a component of `type: db` should have a matching entry in `tech_stack.infrastructure`. Challenge version specificity: "Python 3" should become "Python 3.12" with rationale.
- **Connect**: Map data flows, integration points, and trust boundaries between components.
- **Verify**: Check that every in-scope capability maps to ≥1 component; no capability is architecturally orphaned.
- **Emit**: Write artifact when all components are connected and trust boundaries are explicit.

## Dependency Order
- Step 01 (Capabilities) is required input.
- Do not depend on downstream specs; when interface/security/perf details are unknown, use `-tbd` or ask Gap Questions.
- Build a private Context Ledger of components (id, type, responsibilities, owner, tags) derived from capabilities and current systems; enumerate all connections (from→to, protocol, trust_boundary, auth, rate_limit, reliability, schema_ref). Do not output it.
- **Cross-Check**: Verify each connection's `auth` and `reliability` against constraints listed in `spec/00_charter.json` and `docs/seed/seed_tech_stack.md`. Do not assume missing constraints.
- Self-audit; if a capability lacks a responsible component or a connection is underspecified, ask Gap Questions.
- Rewrite responsibilities into specific, testable bullets per component (each bullet MUST name a concrete action and data domain); complete connection details based on protocols and policy; ensure IDs are stable.
- Emit JSON once reconciled.

## Heuristics For Completeness
- MUST set `trust_boundary` on every connection; the schema enforces required fields for connections at `partner` or `public` trust boundaries.
- Trust-boundary auth rules are authoritative; do not infer auth from protocol alone.
- External integrations: connections touching `type: external` components MUST use `trust_boundary` of `partner` or `public`; MUST populate `auth` with a value from the schema enum.
- Implicit mapping: responsibilities MUST cover all in-scope capabilities from `spec/01_capabilities.json`; if a capability has no responsible component, MUST propose a new component to own it.
- Ambiguity scrub: MUST NOT use generic phrases like “owns data” or “manages resources”; MUST specify the data domain (read from `spec/01_capabilities.json` inputs/outputs) and quantitative SLAs (read from `docs/seed/seed_tech_stack.md` constraints).
- MUST populate `tech_stack` with at least one entry in each of `languages`, `frameworks`, `infrastructure`, and `tools`. MUST resolve any `[AUTO-DERIVE]` markers from `docs/seed/seed_tech_stack.md` into concrete technology choices with version and rationale. MUST cross-check that `type: db` components have corresponding `tech_stack.infrastructure` entries.

## Self-Audit Gate
> Per shared_expectations: if ANY item below cannot be satisfied, enter Clarify mode.
- `spec/00_charter.json` is present and contains at least one in_scope entry.
- `spec/01_capabilities.json` is present and contains at least one capability entry.
- `docs/seed/seed_tech_stack.md` is present and non-empty.

## Negative Constraints
DO NOT:
- Include out-of-scope capabilities in components or responsibilities
- Use non-enum protocols (must be one of: http, grpc, event, rpc, db, file)
- Use generic responsibilities (must be specific and measurable)
- Reuse component IDs from other steps or artifacts
- Create dangling connections (from/to must reference existing components)
- Omit auth or rate_limit requirements for partner or public trust boundaries
- Mark `type: external` without the `external-dependency` tag
- Use `trust_boundary: internal` on connections that touch `type: external` components

## Coverage Closure
Before emitting, verify:
- Every `capability_id` from `spec/01_capabilities.json` is reflected in ≥1 component's `trace` or `links`, OR explicitly listed in `out_of_scope` with rationale.
- No capability is left without an architectural home — every capability must be owned by a `component_id`.
- All `owner` values on components resolve to owner enums defined in canonical registry or `spec/01_capabilities.json`.
- All tech choices align with constraints in `docs/seed/seed_tech_stack.md`; no stack choice contradicts a seed constraint.
- If any capability cannot be assigned to a component: add a gap question (Clarify mode) rather than omitting it.
- [ ] Every upstream ID referenced in extraction intent has been consumed
- [ ] No placeholder tokens remain (TBD, TODO, FIXME, XXX)
- [ ] All required fields populated from actual upstream data (not hallucinated)
- [ ] Every in-scope capability from Step 01 maps to ≥1 component or integration point
- [ ] Every external dependency has an explicit trust boundary defined
- [ ] No component appears in a data flow without being defined in the components list
- [ ] All trust zone boundaries are explicit — no component straddles multiple trust zones silently
- [ ] Every external system dependency is represented as a distinct component with interface type defined
- [ ] `tech_stack` has at least one entry per category (languages, frameworks, infrastructure, tools)
- [ ] Every `[AUTO-DERIVE]` marker from seed_tech_stack.md has been resolved to a concrete choice
- [ ] Database/cache/queue component types have matching infrastructure entries in tech_stack

## Step-Specific Completeness Checklist
- Components enumerate services, data stores, queues, jobs, caches, UIs, libs, and external systems; each has a type and clear responsibilities.
- Connections cover all cross-component interactions; ensure `from` and `to` component IDs exist and `trust_boundary` is set.
- Connections that touch external components use `trust_boundary` of `partner` or `public`.
- Protocols/auth match real integration constraints (e.g., gRPC with mTLS, events with exactly-once semantics where needed).
- Include reliability semantics on event/async paths; specify rate limits where known.
- Tag external dependencies and their owners; `type: external` must include the `external-dependency` tag.
- `tech_stack` covers all technology decisions from `docs/seed/seed_tech_stack.md`; each entry has `name`, `version`, and `rationale` (rationale required for all non-obvious choices).
- Infrastructure entries in `tech_stack` are consistent with component types (db, cache, queue) declared in `components`.

## Best Practices
- **Components**: Assign deterministic `component_id` values and tag each component with the correct `type` and owning team.
- **Responsibilities**: List concrete `responsibilities` that map back to capabilities or FRs instead of vague descriptors.
- **Integration**: Define `connections` with protocol, auth, and reliability details so interface contracts and NFRs inherit accurate constraints.
- **Design Use**: Model only the necessary components and connections to support in-scope capabilities.
- **External**: Mark external dependencies explicitly (`type: external`) to surface integration risk.

## Common Pitfalls
- **Diagram Dump**: Treating the sketch as a diagram dump without responsibilities, leaving FRs unclear on ownership.
- **Blind Spots**: Omitting external systems or shared services, causing blind spots in CI gates and monitoring.
- **Stale Links**: Forgetting to update `connections` when components change, breaking trace links for Step 05 APIs.
- **ID Reuse**: Reusing IDs from other steps, which confuses schema validation and traceability tooling.
- **Hidden Constraints**: Missing auth/reliability on connections.

## External Definition
Define `type: external` as a component that represents third-party services or systems that are not owned or controlled by the organization. Examples include cloud APIs (AWS, GCP), payment processors (Stripe), identity providers (Auth0), or analytics services (Google Analytics). Internal partner services should be marked as `type: service` with appropriate `trust_boundary` and authentication. External components must include the `external-dependency` tag.

## Schema Ref and Rate Limit Formats
Consult the schema for valid `schema_ref` formats and the `rate_limit` object shape, sub-field ranges, and scope values. Validator rules also apply an additional cross-field check — see the fixtures for examples of valid and invalid configurations.

# Clarification Questions
- What components exist (or must be created) to deliver the in-scope capabilities? Who owns each?
- Which third-party systems are involved (identity, payments, analytics), and how are they integrated and secured?
- For each connection, what protocol, auth method, and reliability semantics are required?
- What data schemas or message contracts exist for each integration? Where are they tracked?
- What rate limits and backpressure expectations apply? Any multi-region or data-residency constraints?

# Schema Reference
- Schema URI: vc:02-system-sketch
- Schema File: schema/02_system_sketch.schema.json
- Schema Registry: tools/schema_registry.json

# Output Contract
```json
{
  "$schema": "vc:02-system-sketch",
  "id": "system-sketch-v1",
  "owner": "api",
  "created_at": "2025-01-01T00:00:00Z",
  "components": [
    {
      "component_id": "user-service",
      "type": "service",
      "responsibilities": [
        "Create user accounts",
        "Validate credentials",
        "Persist user preferences"
      ],
      "owner": "api",
      "trace": [
        {
          "type": "capability",
          "id": "cap-user-management",
          "note": "Implements: this component delivers the user management capability"
        }
      ]
    }
  ],
  "connections": [],
  "tech_stack": {
    "languages": [
      {
        "name": "TypeScript",
        "version": "5.4",
        "rationale": "Team expertise and type safety for API development"
      }
    ],
    "frameworks": [
      {
        "name": "Express",
        "version": "^4.19",
        "rationale": "Lightweight HTTP framework matching team experience"
      }
    ],
    "infrastructure": [
      {
        "name": "PostgreSQL",
        "version": "16",
        "rationale": "JSONB support for flexible schema evolution"
      }
    ],
    "tools": [
      {
        "name": "ESLint",
        "version": "^9.0",
        "rationale": "Standard linting for TypeScript projects"
      }
    ]
  },
  "canonical_refs_used": []
}
```

