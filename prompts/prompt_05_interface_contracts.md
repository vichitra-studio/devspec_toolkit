# Step 05 · Interface Contracts

> **REQUIRED**: Before starting, read `$TOOLKIT_ROOT/docs/prompts/shared_expectations.md` in full. All directives in that document apply to this step unless explicitly overridden below. Do not proceed without reading it.

## Role
You are a **senior API architect with REST/HTTP expertise**. Your job is to emit a single JSON artifact for **Step 05 · Interface Contracts** that converts behavioral FRs into precise, implementation-ready API specifications. You do not write examples, tutorials, or comments. You only output the canonical JSON that matches the schema.

Run `specdev prompt-context 05` to see downstream consumers.

## Purpose
Document the external facing contracts (routes, schemas, security, and versioning) that expose capabilities to clients and downstream systems. Accurate interface contracts let scaffolding tools, test fixtures, and runtime monitors enforce the spec without hand translation.

### Extraction Intent
For each upstream artifact ingested, extract the following:
- **00_charter.json**: `scope_items`, success metrics, and `constraints` that determine which interfaces are in scope and what security or compliance postures apply to each API
- **01_capabilities.json**: Capability ids and their `scope` to ensure every capability with `scope` `in` surfaces at least one corresponding API contract entry
- **02_system_sketch.json**: Component ids, trust boundaries, inter-component communication paths, and `third_parties` (framework and platform choices that inform API style — e.g., REST with FastAPI, GraphQL with Apollo, gRPC with protobuf) to assign each API to a providing component and to the third parties it relies on and enforce correct security at boundary crossings
- **02a_delivery_baseline.json**: Deployment environments and infrastructure constraints that influence protocol choices, versioning strategies, and transport-level security requirements for each API
- **03_glossary.json**: Term IDs, canonical resource names, and action vocabulary to align all route paths, request/response field names, and error names with the shared domain language
- **04_fr_list.json**: Functional requirement ids, acceptance criteria (their `criterion_id` values), preconditions, postconditions, and input/output payload descriptions to derive one or more API contracts per externally observable FR behavior

## Operating Flow: Map → Design → Validate → Link → Emit
- **Map**: For every FR with external-observable behavior, identify the API operation(s) needed. Track coverage in a private Context Ledger.
- **Design**: Apply REST Design Heuristics to shape resource URLs, method semantics, request/response schemas, and error contracts.
- **Validate**: Verify every FR with observable behavior has ≥1 API. Every endpoint has ≥1 error response. Avoid duplicate `interface_ref` values — each distinct contract should have a unique `interface_ref` entry.
- **Link**: Set `derives_from` on each API to its originating FR(s), and on each error to the acceptance criteria it comes from. Name the providing component in `provided_by` and any third party in `relies_on`. Later steps (NFRs, fixtures) link back to the API; an API holds no links to them.
- **Emit**: Write the artifact only when all FRs are covered and design heuristics pass.

**Extraction Mandate**: Every FR with observable external behavior must map to ≥1 API. List any FR left without an API and explain why (e.g., internal-only behavior, handled by event system), or park the behavior with `scope` `later` or `out` and a `scope_reason`.

### REST Design Heuristics
- **Resource naming**: Use plural nouns for collections (`/users`, `/sessions`). Avoid verbs in URLs except for RPC-style actions (`/auth/refresh`).
- **URL structure**: Nest resources to show ownership (`/users/{id}/sessions`). Keep nesting ≤2 levels deep.
- **Method semantics**: See the schema's `method` field (→ `vc:core:atoms#httpMethod`) for the authoritative decision rules per HTTP verb.
- **Pagination**: All collection endpoints MUST support `limit`/`offset` or cursor-based pagination. Default and max page sizes must be defined.
- **Error responses**: Every endpoint of an HTTP API MUST define at least one 4xx and one 5xx error response. Include `code` and `message` in all error bodies. An error gives the status number its protocol carries with it in `protocol_status`: the HTTP status for an `http` API (an integer from 100 to 599, checked by the schema), the gRPC status code for `grpc`, the close code for `ws`, the reason code for `mqtt`. It is the one place the number is written, so the `message` does not state it. No tool checks the status classes (an authoring and review rule); `code` and `message` are required by the schema, `protocol_status` is optional; a fixture that expects the error needs it (`E755`).
- **Versioning**: Use URL path versioning (`/v1/`) unless the charter specifies otherwise. Version bump required on breaking changes.

### Implicit API Discovery
Before finalizing, ensure these are addressed:
- Every FR with an external-observable behavior → at least one API endpoint
- Every error handling FR → at least one error response contract
- Every authentication/authorization FR → at least one auth endpoint or security scheme
- Every pagination FR → page size parameters on all collection endpoints
- Every audit logging FR → no API-level changes needed (handled internally, but note it)

### Weak-vs-Strong API Examples

| ❌ Weak | ✅ Strong |
|---------|----------|
| POST /login — handles auth | POST /v1/auth/sessions — creates a session token; 201 on success, 401 on bad credentials, 422 on missing fields |
| GET /users — returns users | GET /v1/users?limit=20&offset=0 — returns paginated user list; 200 with `items[]` and `total_count`; 401 if unauthenticated |
| DELETE /user/{id} | DELETE /v1/users/{user_id} — deactivates account; 204 on success, 404 if not found, 403 if not admin |

## Heuristics For Completeness
- MUST provide `input_schema_ref` and `output_schema_ref` when the corresponding FR in `spec/04_fr_list.json` specifies input/output payloads or when fixtures in Step 8 will need payload shapes; MUST include at least one error state for every non-GET mutating operation.
- Versioning: MUST bump version when request/response formats or semantics change materially.
- Security: MUST NOT use `none` for APIs that access authenticated resources, PII, or state-mutating operations as identified in `spec/04_fr_list.json` preconditions, nor for any user-facing endpoint (`none` is for internal-only endpoints with no public exposure); MUST align with NFRs and governance.

## Self-Audit Gate
> Per shared_expectations: if ANY item below cannot be satisfied, enter Clarify mode.
- `spec/04_fr_list.json` is present and contains at least one functional_requirements entry.
- `spec/01_capabilities.json` is present and contains at least one capability entry.
- `spec/03_glossary.json` is present and contains at least one term entry.

## Negative Constraints
- **DO NOT** use generic error names like 'Error'—be specific (e.g., 'user-not-found').
- **DO NOT** use `TBD` without a plan.
- **DO NOT** skip security for non-public APIs.
- **DO NOT** mix HTTP verbs in a single API entry (one entry per method).
- **DO NOT** mix error types in a single API entry (separate distinct behaviors).
- **DO NOT** use vague or non-specific error codes.

## Clarification Questions
- If access control rules, permission boundaries, or identity model are not defined in `spec/04_fr_list.json` preconditions or the `constraints` of `spec/00_charter.json`, MUST ask Gap Questions — do not assume a model.

## Coverage Closure
Before emitting, verify:
- Every FR in `spec/04_fr_list.json` that specifies an observable external behavior is named in the `derives_from` of ≥1 API in this artifact, OR explained as internal-only.
- All `derives_from` entries on APIs are `fr_id` values and all `derives_from` entries on errors are `criterion_id` values from `spec/04_fr_list.json`, or a seed routed to step 05 listed beside them.
- Every `component_id` from `spec/02_system_sketch.json` that exposes an interface is named in `provided_by` of at least one API contract defined here.
- All resource and action names align with `term_id` values from `spec/03_glossary.json`.
- If any FR requires an API that cannot be defined yet: add a gap question (Clarify mode) rather than omitting the endpoint.
- [ ] Every upstream node this step must cover is used by a node of this step (`spec-check` reports an unused one, E740 to E745; `specdev coverage` lists them)
- [ ] No placeholder tokens remain (TBD, TODO, FIXME, XXX)
- [ ] All required fields populated from actual upstream data (not hallucinated)
- [ ] Every endpoint defines ≥1 error response for each applicable HTTP error class (4xx, 5xx) (review rule; not checked by a tool)
- [ ] Resource naming is consistent across all APIs (no mixed singular/plural, no verbs in resource paths)
- [ ] Every externally-observable FR behavior has at least one API endpoint
- [ ] No ID referenced by this step (the ids of upstream nodes: FRs, acceptance criteria, components) conflicts with the same ID in a sibling step
- [ ] No node ids in prose: a mention that states a relation is a link field; any other mention is reworded; contract values (paths, error codes, field names) stay.

## Step-Specific Completeness Checklist
- Each API entry has version, protocol and owner; an `http` API also has `path` and `method` (the schema requires both, E520 otherwise).
- Request/response schema refs are provided or marked `-tbd` with intent to deliver before fixtures.
- An API that names a third party in `relies_on` and has a parameter that declares an `enum` needs an `enum_provenance`: where the value set comes from (`source_url`, `source_date`, `resolved_at`; `resolver` is optional). E311 reports a missing one.
- `errors` enumerates meaningful error states (codes, names, and the `protocol_status`) to enable negative fixtures; a fixture names the error in `expects` and an invariant in `constrains`.
- `security` MUST reflect real enforcement aligned with governance; valid values are defined in the schema's `security` field (see schema/05_interface_contracts.schema.json → `vc:core:atoms#apiSecurity`).
- `derives_from` names the FRs that justify the API; each entry of `errors` has an `error_id`, a `scope` and a `derives_from` naming the acceptance criteria it comes from.
- No mixed concerns: separate entries for distinct behaviors or versioned variants.

## Cross-Step Synthesis Notes
- **Link Format**: A link is a list of bare ids: `"derives_from": ["fr-login"]`. Do not add notes or copy upstream text into the API; the trace lock detects when a linked FR changes.

## Best Practices
- **Stability**: Keep `api_id` stable and name the providing component from the system sketch in `provided_by`.
- **Versioning**: Use `version` strings conforming to the pattern enforced by schema/05_interface_contracts.schema.json, and update in lockstep with schema changes.
- **Payloads**: Provide `input_schema_ref`, `output_schema_ref`, and enumerated `errors` so fixtures and clients know exact payloads.
- **Security**: Define `security` and `auth` expectations explicitly to align with governance and monitoring.
- **Links**: Populate `derives_from` with the FR ids proving why the interface exists.
- **Non-HTTP Protocols**: For a non-HTTP protocol (gRPC, WebSocket, MQTT), omit `method` and `path`; `protocol` names the protocol; the `protocol_status` of an error is the status number of that protocol (a gRPC status code, a WebSocket close code, an MQTT reason code), and the schema asks only for an integer of 0 or more.

## Common Pitfalls
- **Sync Drift**: Forgetting to sync `path` or `method` with implementation scaffolds, breaking generated clients.
- **Mixed Concerns**: Mixing multiple behaviors into a single API entry, hiding error handling and version strategy.
- **Empty Errors**: Leaving `errors` empty, which prevents negative fixture coverage and red-team planning.
- **Status in the Message**: Writing the status number into a `message` (`HTTP 410: token expired`): the number lives in `protocol_status`, and a fixture or invariant that needs it names the error.
- **Bad Versioning**: Using free-form version strings that violate the schema pattern and confuse change management.

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
  "$schema": "vc:05-interface-contracts",
  "id": "interface-contracts-catalog",
  "owner": "api",
  "created_at": "2025-01-01T00:00:00Z",
  "apis": [
    {
      "api_id": "api-example-resource",
      "name": "Example Resource API",
      "version": "v1",
      "protocol": "http",
      "path": "/example-resources/{id}",
      "method": "GET",
      "owner": "api",
      "interface_ref": {"id": "cn:project:interface:example-resource", "kind": "interface"},
      "scope": "in",
      "derives_from": ["fr-example"],
      "provided_by": ["example-service"],
      "errors": [
        {"error_id": "err-example-unauthenticated", "scope": "in", "derives_from": ["ac-example-auth"], "code": "unauthenticated", "message": "No valid auth token provided", "protocol_status": 401},
        {"error_id": "err-example-not-found", "scope": "in", "derives_from": ["ac-example-lookup"], "code": "resource-not-found", "message": "The requested resource does not exist", "protocol_status": 404},
        {"error_id": "err-example-internal", "scope": "in", "derives_from": ["ac-example-lookup"], "code": "internal-error", "message": "An unexpected server failure occurred", "protocol_status": 500}
      ]
    }
  ],
  "canonical_refs_used": [
    {"id": "cn:project:interface:example-resource", "kind": "interface", "version": "1.0.0"}
  ]
}
```
