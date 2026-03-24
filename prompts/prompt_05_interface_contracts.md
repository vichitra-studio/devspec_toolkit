# Step 05 · Interface Contracts

> **Inherits**: `$TOOLKIT_ROOT/docs/prompts/shared_expectations.md` — all directives apply unless explicitly overridden below.

Run `specdev prompt-context 05` to see downstream consumers. This prompt's output feeds 9 downstream steps.

## Purpose
Document the external facing contracts (routes, schemas, security, and versioning) that expose capabilities to clients and downstream systems. Accurate interface contracts let scaffolding tools, test fixtures, and runtime monitors enforce the spec without hand translation.

### Extraction Intent
For each upstream artifact ingested, extract the following:
- **00_charter.json**: Product scope boundaries, success metrics, and high-level constraints that determine which interfaces are in-scope and what security or compliance postures apply to each API
- **01_capabilities.json**: Capability IDs and their priority rankings to ensure every high-priority capability surfaces at least one corresponding API contract entry
- **02_system_sketch.json**: Component IDs, trust boundaries, and inter-component communication paths to assign each API to an owning component and enforce correct security at boundary crossings
- **02a_delivery_baseline.json**: Deployment environments and infrastructure constraints that influence protocol choices, versioning strategies, and transport-level security requirements for each API
- **03_glossary.json**: Term IDs, canonical resource names, and action vocabulary to align all route paths, request/response field names, and error names with the shared domain language
- **04_fr_list.json**: Functional requirement IDs, acceptance criteria, preconditions, postconditions, and input/output payload descriptions to derive one or more API contracts per externally observable FR behavior

## Operating Flow: Synthesize → Clarify → Emit
- Build a private Context Ledger of APIs (id, name, version, protocol, route/method, request/response schemas, security, errors, owner, traces). Do not output it.
- Map APIs to FRs; ensure each FR with external behavior has an interface or rationale for being internal-only.
- Self-audit; if schemas, security, or errors are unclear, ask Gap Questions (do not guess).
- Rewrite for precision: fill schema refs, enumerate meaningful errors, define security consistent with governance; finalize traces.
- Emit JSON when contracts are testable.

## Heuristics For Completeness
- MUST provide `input_schema_ref` and `output_schema_ref` when the corresponding FR in `spec/04_functional_requirements.json` specifies input/output payloads or when fixtures in Step 8 will need payload shapes; MUST include at least one error state for every non-GET mutating operation.
- Versioning: MUST bump version when request/response formats or semantics change materially.
- Security: MUST NOT use `none` for APIs that access authenticated resources, PII, or state-mutating operations as identified in `spec/04_functional_requirements.json` preconditions; MUST align with NFRs and governance.

## Self-Audit Gate
- Gating items:
  - For HTTP: route and method set; for gRPC: service/method identified.
  - Request/response schemas known or marked `-tbd` with plan; errors enumerated.
  - Security explicitly chosen and justified; owner set; traces to FRs/capabilities present.
  - Access control for each interface is defined, or explicitly marked as open/public with rationale.
  - If access control rules, permission boundaries, or identity model are not defined in `spec/04_functional_requirements.json` preconditions or `spec/00_charter.json` constraints, MUST ask Gap Questions — do not assume a model.

### Coverage Closure
Before emitting, verify:
- Every FR in `spec/04_functional_requirements.json` that specifies an observable external behavior is covered by ≥1 `api_id` in this artifact, OR explicitly listed in `out_of_scope` with rationale.
- All `trace` entries on APIs reference valid `fr_id` values from `spec/04_functional_requirements.json`.
- Every `component_id` from `spec/02_system_sketch.json` that exposes an interface has at least one API contract defined here.
- All resource and action names align with `term_id` values from `spec/03_glossary.json`.
- If any FR requires an API that cannot be defined yet: add a gap question (Clarify mode) rather than omitting the endpoint.
- [ ] Every upstream ID from ingested context has been consumed
- [ ] No placeholder tokens remain (TBD, TODO, FIXME, XXX)
- [ ] All required fields populated from actual upstream data (not hallucinated)

## Step-Specific Completeness Checklist
- Each API entry has version, protocol, route/path (or equivalent), method (where applicable), and owner.
- Request/response schema refs are provided or marked `-tbd` with intent to deliver before fixtures.
- `errors` enumerates meaningful error states (codes, names) to enable negative fixtures.
- `security` MUST reflect real enforcement aligned with governance; valid values are defined in the schema's `security` enum (`none`, `api-key`, `oauth2`, `jwt`, `mTLS`).
- `trace` links to FRs/capabilities that justify the API; add example_refs where helpful for fixtures.
- No mixed concerns: separate entries for distinct behaviors or versioned variants.

## Cross-Step Synthesis Notes
- **Trace Format**: When specifying trace references, use the exact JSON object format: `[{"type": "fr", "id": "fr-login", "note": "..."}]` - not string arrays like `["fr-login"]` or simple objects like `{"fr": "fr-login"}`.

## Best Practices
- **Stability**: Keep `api_id` stable and map each entry to an owning component from the system sketch.
- **Versioning**: Use semver-compatible `version` strings (`v1`, `v1.1`) and update in lockstep with schema changes.
- **Payloads**: Provide `input_schema_ref`, `output_schema_ref`, and enumerated `errors` so fixtures and clients know exact payloads.
- **Security**: Define `security` and `auth` expectations explicitly to align with governance and monitoring.
- **Trace**: Populate `trace` references to FR IDs or capabilities proving why the interface exists.
- **Protocols**: For non-HTTP protocols like gRPC, use POST method; for MQTT, map routes to topic paths.
- **Non-HTTP Protocols**: For gRPC methods, use POST method; for MQTT, map routes to topic paths (e.g., `/topic/{id}`).

## Common Pitfalls
- **Sync Drift**: Forgetting to sync `path` or `method` with implementation scaffolds, breaking generated clients.
- **Mixed Concerns**: Mixing multiple behaviors into a single API entry, hiding error handling and version strategy.
- **Empty Errors**: Leaving `errors` empty, which prevents negative fixture coverage and red-team planning.
- **Bad Versioning**: Using free-form version strings that violate the schema pattern and confuse change management.
## Negative Constraints
- **DO NOT** use generic error names like 'Error'—be specific (e.g., 'user-not-found').
- **DO NOT** use `TBD` without a plan.
- **DO NOT** skip security for non-public APIs.
- **DO NOT** mix HTTP verbs in a single API entry (one entry per method).
- **DO NOT** mix error types in a single API entry (separate distinct behaviors).
- **DO NOT** use vague or non-specific error codes.

# Clarification Questions
- For each API, what is the exact behavior and which FR(s) does it satisfy?
- What are the request/response schemas and example payloads? Where are schemas versioned?
- What authentication, authorization, and transport security are required? Any tenant or PII handling constraints?
- What error conditions must be first-class (validation, authorization, conflict, not found, rate limit)?
- What is the versioning strategy and deprecation policy? Any breaking changes planned soon?

# Schema Reference
- Schema URI: vc:05-interface-contracts
- Schema File: schema/05_interface_contracts.schema.json
- Schema Registry: tools/schema_registry.json

# Output Contract
```json
{
  "id": "interface-contracts-catalog",
  "owner": "api",
  "created_at": "2025-01-01T00:00:00Z",
  "apis": [
    {
      "api_id": "api-example-resource",
      "name": "Example Resource API",
      "version": "v1",
      "protocol": "http",
      "owner": "api",
      "interface_ref": {"id": "cn:project:term:example-resource", "kind": "term"},
      "trace": [{"type": "implements", "id": "fr-example"}]
    }
  ],
  "canonical_refs_used": []
}
```
