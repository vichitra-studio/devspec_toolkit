# Step 02 · System Sketch

> **REQUIRED**: Before starting, read `$TOOLKIT_ROOT/docs/prompts/shared_expectations.md` in full. All directives in that document apply to this step unless explicitly overridden below. Do not proceed without reading it.

## Role
You are a **senior solutions architect and system designer**. Your job is to emit a single JSON artifact for **Step 02 · System Sketch** that maps architectural components, trust boundaries, and data flows with enough fidelity to anchor downstream interface contracts and invariants. You do not write examples, tutorials, or comments. You only output the canonical JSON that matches the schema.

Run `specdev prompt-context 02` to see downstream consumers.

## Purpose
Build a lightweight architecture map that shows the components required to deliver the approved capabilities, the third-party services and libraries they depend on (each with an exact pinned version), and how data flows between them. The system sketch communicates ownership, technology choices, and integration contracts early so downstream steps (interface contracts, NFRs, fixtures, scaffold) can make technology-aware decisions.

## Extraction Intent

For each upstream artifact ingested, extract the following:
- **Seeds**: per spec/common/seed_manifest.json step_requirements["02"]
- **00_charter.json**: `scope_items` (with `scope`), `constraints`, system context, integration points, and deployment constraints for component identification
- **01_capabilities.json**: Capability IDs and owners to map to components; scope boundaries to determine component set; use only upstream artifacts — do not ingest downstream interface, glossary, or NFR specs in this step

## Operating Flow: Decompose → Resolve Tech → Connect → Verify → Emit

- **Decompose**: Break down the system into components (services, stores, clients, gateways) from charter scope and capabilities.
- **Resolve Tech**: Extract the technology decisions from the seeds ingested for this step into `third_parties`: one item per separately versioned or contracted service, library or platform (a payment API, a mail relay, a database product, a framework), each with a `name`, an exact `pin` (a range such as `^0.41`, `latest`, `any` or a wildcard is E336 at step 02, whether or not the host declares `pin_sources`; when it does, the pin must also equal the version the repository declares, E337) and a `derives_from` naming the seed or charter constraint it comes from. Resolve `[AUTO-DERIVE]` markers using system type, component types, and charter constraints. When the seeds fix the product behind a `db`, `cache` or `queue` component, record that product as a third party. Challenge version specificity: "Python 3" should become "Python 3.12" with rationale. A third party outside the project boundary is never a component.
- **Connect**: Map data flows, integration points, and trust boundaries between components.
- **Verify**: Check that every in-scope capability maps to ≥1 component; no capability is architecturally orphaned.
- **Emit**: Write artifact when all components are connected and trust boundaries are explicit.

## Dependency Order
- Step 01 (Capabilities) is required input.
- Do not depend on downstream specs; when interface/security/perf details are unknown, use `-tbd` or ask Gap Questions.
- Build a private Context Ledger of components (id, type, responsibilities, owner, tags) derived from capabilities and current systems; enumerate all connections (source component → target component or third party, protocol, trust_boundary, auth, rate_limit, reliability). Do not output it.
- **Cross-Check**: Verify each connection's `auth` and `reliability` against constraints listed in `spec/00_charter.json` and the ingested seeds. Do not assume missing constraints.
- Self-audit; if a capability lacks a responsible component or a connection is underspecified, ask Gap Questions.
- Rewrite responsibilities into specific, testable bullets per component (each bullet MUST name a concrete action and data domain); complete connection details based on protocols and policy; ensure IDs are stable.
- Emit JSON once reconciled.

## Heuristics For Completeness
- MUST set `trust_boundary` on every connection; the schema enforces required fields for connections at `partner` or `public` trust boundaries.
- Trust-boundary auth rules are authoritative; do not infer auth from protocol alone.
- External integrations: connections whose `connects_to` names a third party MUST use `trust_boundary` of `partner` or `public`; MUST populate `auth` with a value from the schema enum.
- Implicit mapping: responsibilities MUST cover all in-scope capabilities from `spec/01_capabilities.json`; if a capability has no responsible component, MUST propose a new component to own it and name the capability in that component's `derives_from`.
- Ambiguity scrub: MUST NOT use generic phrases like “owns data” or “manages resources”; MUST specify the data domain (read from `spec/01_capabilities.json` inputs/outputs) and quantitative SLAs (read from ingested seeds).
- MUST record every technology the ingested seeds name as a `third_parties` item with an exact `pin`. MUST resolve any `[AUTO-DERIVE]` markers from the ingested seeds into concrete technology choices with version and rationale. `third_parties` is optional when the system has no third-party dependency.

## Self-Audit Gate
> Per shared_expectations: if ANY item below cannot be satisfied, enter Clarify mode.
- `spec/00_charter.json` is present and contains at least one `scope_items` entry.
- `spec/01_capabilities.json` is present and contains at least one capability entry.
- All seeds listed for step "02" in `spec/common/seed_manifest.json` are present and non-empty.

## Negative Constraints
DO NOT:
- Include capabilities with `scope` `later` or `out` in components or responsibilities
- Use non-enum protocols (must be one of: http, grpc, event, rpc, db, file)
- Use generic responsibilities (must be specific and measurable)
- Reuse component IDs from other steps or artifacts
- Create dangling connections (`derives_from` names a component of this file, with a seed routed to step 02 beside it at most; `connects_to` names a component or third party of this file)
- Omit auth or rate_limit requirements for partner or public trust boundaries
- Model a third-party service as a component; record it under `third_parties`
- Use `trust_boundary: internal` on connections whose `connects_to` names a third party

## Coverage Closure
Before emitting, verify:
- Every `capability_id` from `spec/01_capabilities.json` with `scope` `in` is named in the `derives_from` of ≥1 component.
- No capability is left without an architectural home — every capability must be owned by a `component_id`.
- All `owner` values on components resolve to owner enums defined in canonical registry or `spec/01_capabilities.json`.
- All tech choices align with constraints in the ingested seeds; no stack choice contradicts a seed constraint.
- If any capability cannot be assigned to a component: add a gap question (Clarify mode) rather than omitting it.
- [ ] Every upstream node this step must cover is used by a node of this step (`spec-check` reports an unused one, E740 to E745; `specdev coverage` lists them)
- [ ] No placeholder tokens remain (TBD, TODO, FIXME, XXX)
- [ ] All required fields populated from actual upstream data (not hallucinated)
- [ ] Every in-scope capability from Step 01 maps to ≥1 component or integration point
- [ ] Every connection to a third party has an explicit `partner` or `public` trust boundary
- [ ] No component appears in a data flow without being defined in the components list
- [ ] All trust zone boundaries are explicit — no component straddles multiple trust zones silently
- [ ] Every external system dependency is represented as a distinct `third_parties` item with an exact `pin`
- [ ] Every `[AUTO-DERIVE]` marker from the ingested seeds has been resolved to a concrete choice
- [ ] Where the seeds fix the product behind a database, cache or queue component, that product is a `third_parties` item
- [ ] No node ids in prose: a mention that states a relation is a link field; any other mention is reworded; contract values (paths, error codes, field names) stay.

## Step-Specific Completeness Checklist
- Components enumerate services, data stores, queues, jobs, caches, UIs and libs; each has a type and clear responsibilities.
- Connections cover all cross-component interactions; ensure the source (`derives_from`) and target (`connects_to`) ids exist and `trust_boundary` is set.
- Connections to third parties use `trust_boundary` of `partner` or `public`.
- Protocols/auth match real integration constraints (e.g., gRPC with mTLS, events with exactly-once semantics where needed).
- Include reliability semantics on event/async paths; specify rate limits where known.
- `third_parties` covers all technology decisions from the ingested seeds; each item has `name`, an exact `pin`, `derives_from`, and a `rationale` for every non-obvious choice.
- Third parties that belong together (a library inside a platform) are tied with `part_of`.

## Best Practices
- **Components**: Assign deterministic `component_id` values and tag each component with the correct `type` and owning team.
- **Responsibilities**: List concrete `responsibilities` and name the capabilities they serve in `derives_from`, instead of vague descriptors.
- **Integration**: Define `connections` with protocol, auth, and reliability details so interface contracts and NFRs inherit accurate constraints.
- **Design Use**: Model only the necessary components and connections to support in-scope capabilities.
- **External**: Record external dependencies explicitly as `third_parties` to surface integration risk.

## Common Pitfalls
- **Diagram Dump**: Treating the sketch as a diagram dump without responsibilities, leaving FRs unclear on ownership.
- **Blind Spots**: Omitting external systems or shared services, causing blind spots in CI gates and monitoring.
- **Stale Links**: Forgetting to update `connections` when components change, leaving Step 05 APIs linked to a component that no longer exists.
- **ID Reuse**: Reusing IDs from other steps, which confuses schema validation and traceability tooling.
- **Hidden Constraints**: Missing auth/reliability on connections.

## External Definition
Define a third party as a service, library or platform that is not owned or controlled by the organization. Examples include cloud APIs (AWS, GCP), payment processors (Stripe), identity providers (Auth0), or analytics services (Google Analytics). Record each as a `third_parties` item, never as a component. Internal partner services are components of `type: service` with appropriate `trust_boundary` and authentication.

## Rate Limit Format
Consult the schema for the `rate_limit` object shape, sub-field ranges, and scope values. Validator rules also apply an additional cross-field check — see the fixtures for examples of valid and invalid configurations.

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
      "derives_from": ["cap-user-management"]
    }
  ],
  "connections": [],
  "third_parties": [
    {
      "third_party_id": "tp-postgresql",
      "name": "PostgreSQL",
      "pin": "16.3",
      "derives_from": ["seed-project-brief"]
    }
  ],
  "canonical_refs_used": []
}
```

