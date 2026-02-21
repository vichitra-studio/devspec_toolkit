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
- **Output type:** one JSON document conforming to the Embedded Schema.
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
- If completeness < 0.9, ask questions.
- Gating items:
  - For HTTP: route and method set; for gRPC: service/method identified.
  - Request/response schemas known or marked `-tbd` with plan; errors enumerated.
  - Security explicitly chosen and justified; owner set; traces to FRs/capabilities present.

# Output Rules
1. Return exactly one fenced code block with language `json`. No prose before or after.
2. The JSON must validate against the Embedded Schema below.
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

# Embedded Schema
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://specdev.local/schema/05_interface_contracts.schema.json",
  "title": "05_interface_contracts",
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "id": {
      "$ref": "https://specdev.local/schema/core/atoms/1#kebabId"
    },
    "owner": {
      "$ref": "https://specdev.local/schema/core/atoms/1#owner"
    },
    "created_at": {
      "$ref": "https://specdev.local/schema/core/atoms/1#timestamp"
    },
    "apis": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
          "api_id": {
            "$ref": "https://specdev.local/schema/core/atoms/1#kebabId"
          },
          "name": {
            "type": "string"
          },
          "version": {
            "type": "string",
            "pattern": "^v\\d+(?:\\.\\d+)*$"
          },
          "protocol": {
            "type": "string",
            "enum": [
              "http",
              "grpc",
              "ws",
              "mqtt"
            ]
          },
          "route": {
            "type": "string"
          },
          "method": {
            "type": "string",
            "enum": [
              "GET",
              "POST",
              "PUT",
              "PATCH",
              "DELETE"
            ]
          },
          "request_schema_ref": {
            "type": "string"
          },
          "response_schema_ref": {
            "type": "string"
          },
          "errors": {
            "type": "array",
            "items": {
              "$ref": "https://specdev.local/schema/core/errors/1#errorState"
            }
          },
          "parameters": {
            "type": "array",
            "items": {
              "type": "object",
              "additionalProperties": false,
              "properties": {
                "name": {
                  "type": "string"
                },
                "in": {
                  "type": "string",
                  "enum": [
                    "query",
                    "path",
                    "header"
                  ]
                },
                "required": {
                  "type": "boolean"
                },
                "schema": {
                  "$ref": "https://specdev.local/schema/core/atoms/1#kebabId"
                }
              },
              "required": [
                "name",
                "in",
                "required"
              ]
            }
          },

          "example_refs": {
            "$ref": "https://specdev.local/schema/core/collections/1#stringArray"
          },
          "security": {
            "type": "string",
            "enum": [
              "none",
              "api-key",
              "oauth2",
              "jwt",
              "mTLS"
            ]
          },
          "owner": {
            "$ref": "https://specdev.local/schema/core/atoms/1#owner"
          },
          "trace": {
            "type": "array",
            "items": {
              "$ref": "https://specdev.local/schema/core/collections/1#traceRef"
            }
          }
        },
        "required": [
          "api_id",
          "name",
          "version",
          "protocol",
          "owner"
        ]
      }
    }
  },
  "required": [
    "id",
    "owner",
    "created_at",
    "seed_refs",
    "apis"
  ]
}
```

# Output Contract
```json
{
  "id": "interface_contracts-catalog",
  "owner": "api",
  "created_at": "2025-01-01T00:00:00Z",
  "apis": []
}
```
