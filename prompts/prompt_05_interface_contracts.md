# Step 05 · Interface Contracts

Run `specdev prompt-context 05` to see downstream consumers. This prompt's output feeds 9 downstream steps.

## Schema Authority

The schema at `schema/05_interface_contracts.schema.json` is the authoritative source for all
field definitions, types, required vs optional markers, enum values, patterns, and minItems rules.
MUST read the schema before generating output. Do NOT guess field names, types, or valid values —
all structural constraints are defined in the schema. Do NOT output fields not defined in the schema.

## Path Variables
| Variable | Description |
|---|---|
| `$PRODUCT_ROOT` | Root of the consumer/product repository |
| `$TOOLKIT_ROOT` | Root of the devspec_toolkit directory |
| `$SPEC_DIR` | `$PRODUCT_ROOT/spec` — where spec artifacts live |
| `$SCHEMA_DIR` | `$TOOLKIT_ROOT/schema` — where JSON Schemas live |

## Purpose
Document the external facing contracts (routes, schemas, security, and versioning) that expose capabilities to clients and downstream systems. Accurate interface contracts let scaffolding tools, test fixtures, and runtime monitors enforce the spec without hand translation.

## Tool Execution
Validate the generated JSON:
```bash
./tools/run_specdev.sh validate <path_to_artifact> --repo-root ./devspec_toolkit
```

# Role
You are a senior specification author and validator. Your job is to emit a single JSON artifact for **Step 5 · Interface Contracts** that is machine-checkable and immediately consumable by CI and generators. You do not write examples, tutorials, or comments. You only output the canonical JSON that matches the schema.

# Task
- **Input context:** previously authored spec artifacts (Charter, Capabilities, Glossary, FRs, etc.) available to you in the workspace; organizational constraints; known IDs for cross-references.
- **Objective:** produce a complete, falsifiable artifact for **Step 5 · Interface Contracts**.
- **Output type:** one JSON document conforming to the referenced step schema.
- **Determinism:** when unspecified, choose the minimal valid value that preserves falsifiability and traceability.
- **Traceability:** if this step has `trace` or `links`, connect to at least one upstream or downstream artifact.

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
- If score < 0.9, output clarifying questions only — do not emit JSON.
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

# Output Rules
1. Write the final JSON artifact directly to disk at the step path under `spec/` (or runner-provided path).
2. The JSON must validate against the referenced step schema listed in `Schema Reference`.
3. All IDs must be unique kebab-case strings.
4. Use concrete verbs and measurable outcomes; avoid adjectives that are not testable.
5. Include explicit preconditions, postconditions, and error states where applicable to the schema.
6. Set `owner` to one of: `api`, `ui`, `system`, `ops`, `data`, `product`, `business`, `engineering`.
7. If the schema supports `trace` or `links`, include at least one reference to connect artifacts across steps.
8. Do not include any fields outside the schema. `additionalProperties` is false everywhere.

## Step-Specific Completeness Checklist
- Each API entry has version, protocol, route/path (or equivalent), method (where applicable), and owner.
- Request/response schema refs are provided or marked `-tbd` with intent to deliver before fixtures.
- `errors` enumerates meaningful error states (codes, names) to enable negative fixtures.
- `security` MUST reflect real enforcement aligned with governance; valid values are defined in the schema's `security` enum (`none`, `api-key`, `oauth2`, `jwt`, `mTLS`).
- `trace` links to FRs/capabilities that justify the API; add example_refs where helpful for fixtures.
- No mixed concerns: separate entries for distinct behaviors or versioned variants.

## Field-by-Field Guidance
- api_id: `api-<resource>-<action>`; stable across codegen and monitoring.
- name: human-readable, maps to resource/action.
- version: `v<major>[.<minor>]` per semver pattern in schema.
- protocol: `http`, `grpc`, `ws`, or `mqtt`; route/method must align with protocol semantics.
- path/method: concrete path and verb for HTTP; use gRPC service/method names for grpc.
- input_schema_ref/output_schema_ref: pointers to canonical schemas; MUST use machine-resolvable locations when schema files exist in the repository.
- errors: use shared error objects where possible; include codes/messages.
- security: `none`, `api-key`, `oauth2`, `jwt`, or `mTLS` based on threat model.
- trace: `fr-*`, `capability-*`, `nfr-*` as applicable to justify existence.
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

## Hardening Protocol
- fail-closed preflight: verify required fields, allowed enums, referenced IDs, and command/tool existence before emitting JSON.
- No-Invention Rules: do not invent IDs, enums, commands, files, metrics, stages, or canonical mappings that are not grounded in provided inputs.
- Completeness Closure: run a final closure pass to confirm required sections, trace/canonical closure, and seed coverage are complete.
- blocker report: if required inputs are missing, conflicting, or ambiguous after clarification, stop and return a blocker report instead of speculative output.

## Canonical Registry (Required Input)

Before generating output, you MUST load and search `canon/manifest.json` for existing canonical entries. Use this registry to:
1. Bind `*_ref` fields to existing canonical IDs (`cn:<namespace>:<kind>:<slug>`)
2. Resolve aliases via `canon/aliases.json`
3. Propose new entries in `canonical_proposals` when no match exists
4. Flag conflicts in `canonical_conflicts` when ambiguous matches are found
## Canonical Binding Rules
1. `canonical_refs_used` is REQUIRED and must list every canonical ID referenced by any `*_ref` field in this artifact.
2. `canonical_proposals` is OPTIONAL. Populate it for any new term, metric, entity, role, etc. that does not exist in the registry.
3. `canonical_conflicts` is OPTIONAL. Populate it when a field value matches multiple canonical entries or contradicts an existing definition.
4. For each `*_ref` field in the schema: if the semantic content exists, the ref MUST be populated. This is not optional.

## Metadata Contract

This step's output artifact MUST include every field listed in the schema's `required[]` array (see Schema Authority). Do NOT add fields not defined in the schema. Refer to the schema for the complete list of required fields, types, and structural constraints — do NOT restate them here.

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
