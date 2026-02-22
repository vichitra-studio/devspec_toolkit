# Step 05 · Interface Contracts

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


## Seed Order & Mandatory Sources
- Read `spec/common/seed_manifest.json` first; follow `global_seed_order` and `step_requirements["05"]`.
- Ingest required seeds in order before any other context.
- Populate `seed_refs` with the seeds actually used.
- If a required seed is missing or stale, stop and request it before proceeding.

## Context To Ingest
- FRs `spec/04_fr_list.json` to derive behaviors and acceptance evidence.
- System Sketch `spec/02_system_sketch.json` for owners and integration points.
- Glossary `spec/03_glossary.json` for resource/action naming.
- Guides: Shared expectations `devspec_toolkit/docs/prompts/shared_expectations.md`, developer reference.
- Use example fixtures for payload shapes and error cases; do not depend on downstream fixture artifacts.

## Operating Flow: Synthesize → Clarify → Emit
- Build a private Context Ledger of APIs (id, name, version, protocol, route/method, request/response schemas, security, errors, owner, traces). Do not output it.
- Map APIs to FRs; ensure each FR with external behavior has an interface or rationale for being internal-only.
- Self-audit; if schemas, security, or errors are unclear, ask Gap Questions (do not guess).
- Rewrite for precision: fill schema refs, enumerate meaningful errors, define security consistent with governance; finalize traces.
- Emit JSON when contracts are testable.

## Heuristics For Completeness
- Optional→expected: provide schema refs when fixtures or FRs imply payloads; include at least one error state for non-GET mutating operations.
- Versioning: bump version when request/response formats or semantics change materially.
- Security: avoid `none` for sensitive resources; align with NFRs and governance.

## Self-Audit Gate
- If `generation_quality.preflight_passed` cannot be set to `true` with current evidence, stop and ask targeted questions.
- Gating items:
  - For HTTP: route and method set; for gRPC: service/method identified.
  - Request/response schemas known or marked `-tbd` with plan; errors enumerated.
  - Security explicitly chosen and justified; owner set; traces to FRs/capabilities present.

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
- `security` reflects real enforcement aligned with governance (e.g., `jwt`, `mTLS`).
- `trace` links to FRs/capabilities that justify the API; add example_refs where helpful for fixtures.
- No mixed concerns: separate entries for distinct behaviors or versioned variants.

## Field-by-Field Guidance
- api_id: `api-<resource>-<action>`; stable across codegen and monitoring.
- name: human-readable, maps to resource/action.
- version: `v<major>[.<minor>]` per semver pattern in schema.
- protocol: `http`, `grpc`, `ws`, or `mqtt`; route/method must align with protocol semantics.
- route/method: concrete path and verb for HTTP; use gRPC service/method names for grpc.
- request_schema_ref/response_schema_ref: pointers to canonical schemas; prefer machine-resolvable locations.
- errors: use shared error objects where possible; include codes/messages.
- security: `none`, `api-key`, `oauth2`, `jwt`, or `mTLS` based on threat model.
- trace: `fr-*`, `capability-*`, `nfr-*` as applicable to justify existence.
- **Trace Format**: When specifying trace references, use the exact JSON object format: `[{"type": "fr", "id": "fr-login", "note": "..."}]` - not string arrays like `["fr-login"]` or simple objects like `{"fr": "fr-login"}`.

## Best Practices
- **Stability**: Keep `api_id` stable and map each entry to an owning component from the system sketch.
- **Versioning**: Use semver-compatible `version` strings (`v1`, `v1.1`) and update in lockstep with schema changes.
- **Payloads**: Provide `request_schema_ref`, `response_schema_ref`, and enumerated `errors` so fixtures and clients know exact payloads.
- **Security**: Define `security` and `auth` expectations explicitly to align with governance and monitoring.
- **Trace**: Populate `trace` references to FR IDs or capabilities proving why the interface exists.
- **Protocols**: For non-HTTP protocols like gRPC, use POST method; for MQTT, map routes to topic paths.
- **Non-HTTP Protocols**: For gRPC methods, use POST method; for MQTT, map routes to topic paths (e.g., `/topic/{id}`).

## Common Pitfalls
- **Sync Drift**: Forgetting to sync `route` or `method` with implementation scaffolds, breaking generated clients.
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

## Quick Reference
- ID Format: `interface_contracts-<descriptor>`; APIs use `api-<resource>-<action>`.
- Required Fields: each API needs `api_id`, `name`, `version`, `protocol`, and `owner`.
- Allowed Protocols: `http`, `grpc`, `ws`, `mqtt`.
- Security Flag: choose from `none`, `api-key`, `oauth2`, `jwt`, `mTLS`.
- Trace: use `trace` to reference FRs (`fr-*`) or Capabilities (`capability-*`).

# Clarification Questions
- For each API, what is the exact behavior and which FR(s) does it satisfy?
- What are the request/response schemas and example payloads? Where are schemas versioned?
- What authentication, authorization, and transport security are required? Any tenant or PII handling constraints?
- What error conditions must be first-class (validation, authorization, conflict, not found, rate limit)?
- What is the versioning strategy and deprecation policy? Any breaking changes planned soon?

# Schema Reference
- Schema URI: https://specdev.local/schema/05_interface_contracts.schema.json
- Schema File: schema/05_interface_contracts.schema.json
- Schema Registry: tools/schema_registry.json

## Hardening Protocol
- fail-closed preflight: verify required fields, allowed enums, referenced IDs, and command/tool existence before emitting JSON.
- No-Invention Rules: do not invent IDs, enums, commands, files, metrics, stages, or canonical mappings that are not grounded in provided inputs.
- Completeness Closure: run a final closure pass to confirm required sections, trace/canonical closure, and seed coverage are complete.
- blocker report: if required inputs are missing, conflicting, or ambiguous after clarification, stop and return a blocker report instead of speculative output.

# Output Contract
```json
{
  "id": "interface-contracts-catalog",
  "owner": "api",
  "created_at": "2025-01-01T00:00:00Z",
  "seed_refs": [
    {"seed_id": "seed-overview"}
  ],
  "apis": [],
  "generation_quality": {
    "preflight_passed": true,
    "evidence_records": [],
    "unresolved_inputs": [],
    "assumptions": [],
    "placeholder_scan": {
      "has_placeholders": false,
      "tokens_found": []
    },
    "self_check_results": []
  },
  "canonical_refs_used": [],
  "canonical_proposals": [],
  "canonical_conflicts": []

}
```

## B4 Metadata Contract
- Include `generation_quality`, `canonical_refs_used`, `canonical_proposals`, and `canonical_conflicts` in the output artifact whenever those fields exist in the step schema.
- `canonical_refs_used` must list canonicals actually referenced by `*_ref` fields in this artifact.
- Put unresolved or new terms into `canonical_proposals`; put ambiguous/conflicting mappings into `canonical_conflicts`.
