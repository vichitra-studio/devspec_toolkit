# Step 02 · System Sketch

## Purpose
Build a lightweight architecture map that shows the components required to deliver the approved capabilities and how data flows between them. The system sketch communicates ownership, technology choices, and integration contracts early so interface design and delivery planning stay coherent.

## Tool Execution
Validate the generated JSON:
```bash
./tools/run_specdev.sh validate <path_to_artifact> --repo-root ./devspec_toolkit
```

# Role
You are a senior specification author and validator. Your job is to emit a single JSON artifact for **Step 2 · System Sketch** that is machine-checkable and immediately consumable by CI and generators. You do not write examples, tutorials, or comments. You only write the canonical JSON to the file system.

# Task
- **Input context:** previously authored spec artifacts (Charter, Capabilities, Glossary, FRs, etc.) available to you in the workspace; organizational constraints; known IDs for cross-references.
- **Objective:** produce a complete, falsifiable artifact for **Step 2 · System Sketch**.
- **Output type:** one JSON document conforming to the Embedded Schema.
- **Determinism:** when unspecified, choose the minimal valid value that preserves falsifiability and traceability.
- **Traceability:** include `trace` that connect components and connections to upstream or downstream artifacts.


## Seed Order & Mandatory Sources
- Read `spec/common/seed_manifest.json` first; follow `global_seed_order` and `step_requirements["02"]`.
- Ingest required seeds in order before any other context.
- Populate `seed_refs` with the seeds actually used.
- If a required seed is missing or stale, stop and request it before proceeding.

## Context To Ingest
- **Primary Source:** `docs/seed/seed_tech_stack.md` (required) for architecture decisions, patterns, and constraints.
- Capabilities and owners from `spec/01_capabilities.json` to inform components.
- Any existing `spec/05_interface_contracts.json` to align external interfaces and protocols.
- Glossary terms `spec/03_glossary.json` to name components and connections consistently.
- NFRs `spec/07_nfrs.json` that imply reliability and rate limits.
- Guides: Shared expectations `devspec_toolkit/docs/prompts/shared_expectations.md`, developer reference.

## Operating Flow: Synthesize → Clarify → Emit

## Dependency Order
- Step 01 (Capabilities) is required input.
- Step 05 (Interface Contracts) and Step 07 (NFRs) are optional context only if already drafted.
- DO NOT hallucinate Step 05/07 content when missing; use `-tbd` or ask Gap Questions.
- Build a private Context Ledger of components (id, type, responsibilities, owner, tags) derived from capabilities and current systems; enumerate all connections (from→to, protocol, trust_boundary, auth, rate_limit, reliability, schema_ref). Do not output it.
- **Cross-Check**: If NFRs (`spec/07_nfrs.json`) or Interface Contracts (`spec/05_interface_contracts.json`) are present, align connection security and reliability with them. Do not assume constraints if these files are missing or empty.
- Self-audit; if a capability lacks a responsible component or a connection is underspecified, ask Gap Questions.
- Rewrite responsibilities into 3–6 crisp bullets per component; complete connection details based on protocols and policy; ensure IDs are stable.
- Emit JSON once reconciled.

## Heuristics For Completeness
- Optional→expected: set `trust_boundary` on every connection; require `auth` and `rate_limit` for `partner` and `public` boundaries.
- Trust-boundary auth rules are authoritative; do not infer auth from protocol alone.
- External integrations: connections touching `type: external` components must use `trust_boundary` of `partner` or `public`.
- Implicit mapping: responsibilities should cover all in-scope capabilities; if not, propose a missing component.
- Ambiguity scrub: avoid generic “owns data”; specify data domains and SLAs.

## Self-Audit Gate
- If completeness < 0.9, ask questions.
- Gating items:
  - Each in-scope capability maps to at least one component.
  - Every Step 01 capability appears in at least one component `trace` entry.
  - All cross-component integrations appear as connections with protocol/auth; event connections include reliability.
  - External systems are identified with clear boundaries and owners.

# Output Rules
1. Do not output the JSON in the chat. Write the final JSON artifact to `spec/02_system_sketch.json` using the file creation tool.
2. The JSON must validate against the Embedded Schema below.
3. All IDs must be unique kebab-case strings.
4. Use concrete verbs and measurable outcomes; avoid adjectives that are not testable.
5. Include explicit preconditions, postconditions, and error states only if the schema defines them (Step 02 does not).
6. Set `owner` to one of: `api`, `ui`, `system`, `ops`, `data`, `product`, `business`, `engineering`.
7. Include `trace` as required by the schema (Step 02 requires them on components and connections).
8. Do not include any fields outside the schema. `additionalProperties` is false everywhere.

## Step-Specific Completeness Checklist
- Components enumerate services, data stores, queues, jobs, caches, UIs, libs, and external systems; each has a type and clear responsibilities.
- Connections cover all cross-component interactions; ensure `from` and `to` component IDs exist and `trust_boundary` is set.
- Connections that touch external components use `trust_boundary` of `partner` or `public`.
- Protocols/auth match real integration constraints (e.g., gRPC with mTLS, events with exactly-once semantics where needed).
- Include reliability semantics on event/async paths; specify rate limits where known.
- Tag external dependencies and their owners; `type: external` must include the `external-dependency` tag.

## Field-by-Field Guidance
- components[*].component_id: kebab-case; map to ownership later in scaffolding.
- components[*].type: one of service, db, queue, cache, job, ui, lib, external.
- components[*].responsibilities: top 3–6 duties with clear boundaries; avoid overlap across components.
- components[*].tags: allowed values only: `critical-path`, `supporting`, `external-dependency`, `shared-platform`, `stateful`, `stateless`, `realtime`, `batch`, `latency-sensitive`, `throughput-sensitive`, `pii`, `phi`, `pci`, `confidential`, `public-data`, `multi-tenant`, `single-tenant`, `experimental`, `legacy`, `deprecated`. Include `external-dependency` when `type: external`.
- components[*].trace: required; include capability references that this component fulfills (use `type: doc` for capability IDs).
- connections[*].from/to: existing component IDs.
- connections[*].protocol: `http`, `grpc`, `event`, `rpc`, `db`, or `file` matching the interface.
- connections[*].trust_boundary: `internal`, `partner`, or `public` (required).
- connections[*].schema_ref: pointer to schema used on the wire (if known) or `-tbd`.
- connections[*].auth: `none`, `basic`, `oauth2`, `jwt`, `mTLS`, or `key` (required for `partner`/`public`).
- connections[*].rate_limit: required for `partner`/`public` trust boundaries; object `{ "rps": int, "burst": int, "window_s": int, "scope": "ip"|"client"|"token"|"global" }`; bounds: `rps` 1..100000, `burst` 1..200000 and >= `rps` when present, `window_s` 1..3600, `scope` required.
- connections[*].reliability: `best-effort`, `at-least-once`, `exactly-once` aligned with business risk.
- connections[*].trace: required; link each integration to the capabilities it supports (use `type: doc` for capability IDs, `nfr` for NFRs).

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

## Quick Reference
- Component Types: `service`, `db`, `queue`, `cache`, `job`, `ui`, `lib`, `external`.
- Connection Protocols: `http`, `grpc`, `event`, `rpc`, `db`, `file`.
- Auth Methods: `none`, `basic`, `oauth2`, `jwt`, `mTLS`, `key`.
- Trust Boundaries: `internal`, `partner`, `public`.
- Rate Limit Shape: `{ rps, burst?, window_s?, scope }`.
- Tag Vocabulary: `critical-path`, `supporting`, `external-dependency`, `shared-platform`, `stateful`, `stateless`, `realtime`, `batch`, `latency-sensitive`, `throughput-sensitive`, `pii`, `phi`, `pci`, `confidential`, `public-data`, `multi-tenant`, `single-tenant`, `experimental`, `legacy`, `deprecated`.

## External Definition
Define `type: external` as a component that represents third-party services or systems that are not owned or controlled by the organization. Examples include cloud APIs (AWS, GCP), payment processors (Stripe), identity providers (Auth0), or analytics services (Google Analytics). Internal partner services should be marked as `type: service` with appropriate `trust_boundary` and authentication. External components must include the `external-dependency` tag.

## Schema Ref and Rate Limit Formats
Specify acceptable formats for `schema_ref`: `file://`, `https://`, `glossary:`, `api:`, or `-tbd`. For `rate_limit` (required on `partner`/`public` connections), use the structured object with required fields `rps` (1-100000) and `scope` (ip, client, token, or global), with optional `burst` (1-200000) and `window_s` (1-3600). `burst` must be >= `rps` when present.

# Clarification Questions
- What components exist (or must be created) to deliver the in-scope capabilities? Who owns each?
- Which third-party systems are involved (identity, payments, analytics), and how are they integrated and secured?
- For each connection, what protocol, auth method, and reliability semantics are required?
- What data schemas or message contracts exist for each integration? Where are they tracked?
- What rate limits and backpressure expectations apply? Any multi-region or data-residency constraints?

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

# Embedded Schema
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://specdev.local/schema/02_system_sketch.schema.json",
  "title": "02_system_sketch",
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
    "components": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
          "component_id": {
            "$ref": "https://specdev.local/schema/core/atoms/1#kebabId"
          },
          "type": {
            "type": "string",
            "enum": [
              "service",
              "db",
              "queue",
              "cache",
              "job",
              "ui",
              "lib",
              "external"
            ]
          },
          "responsibilities": {
            "$ref": "https://specdev.local/schema/core/collections/1#stringArray",
            "minItems": 3,
            "maxItems": 6
          },
          "owner": {
            "$ref": "https://specdev.local/schema/core/atoms/1#owner"
          },
          "tags": {
            "type": "array",
            "items": {
              "type": "string",
              "enum": [
                "critical-path",
                "supporting",
                "external-dependency",
                "shared-platform",
                "stateful",
                "stateless",
                "realtime",
                "batch",
                "latency-sensitive",
                "throughput-sensitive",
                "pii",
                "phi",
                "pci",
                "confidential",
                "public-data",
                "multi-tenant",
                "single-tenant",
                "experimental",
                "legacy",
                "deprecated"
              ]
            }
          },
          "trace_refs": {
            "type": "array",
            "items": {
              "$ref": "https://specdev.local/schema/core/collections/1#traceRef"
            },
            "minItems": 1
          }
        },
        "required": [
          "component_id",
          "type",
          "responsibilities",
          "owner",
          "trace_refs"
        ]
      }
    },
    "connections": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
          "from": {
            "$ref": "https://specdev.local/schema/core/atoms/1#kebabId"
          },
          "to": {
            "$ref": "https://specdev.local/schema/core/atoms/1#kebabId"
          },
          "protocol": {
            "type": "string",
            "enum": [
              "http",
              "grpc",
              "event",
              "rpc",
              "db",
              "file"
            ]
          },
          "trust_boundary": {
            "type": "string",
            "enum": [
              "internal",
              "partner",
              "public"
            ]
          },
          "schema_ref": {
            "type": "string",
            "pattern": "^(?:-tbd|(file://|https://|glossary:|api:).+)$"
          },
          "auth": {
            "type": "string",
            "enum": [
              "none",
              "basic",
              "oauth2",
              "jwt",
              "mTLS",
              "key"
            ]
          },
          "rate_limit": {
            "type": "object",
            "additionalProperties": false,
            "properties": {
              "rps": {
                "type": "integer",
                "minimum": 1,
                "maximum": 100000
              },
              "burst": {
                "type": "integer",
                "minimum": 1,
                "maximum": 200000
              },
              "window_s": {
                "type": "integer",
                "minimum": 1,
                "maximum": 3600
              },
              "scope": {
                "type": "string",
                "enum": [
                  "ip",
                  "client",
                  "token",
                  "global"
                ]
              }
            },
            "required": [
              "rps",
              "scope"
            ]
          },
          "reliability": {
            "type": "string",
            "enum": [
              "best-effort",
              "at-least-once",
              "exactly-once"
            ]
          },
          "trace_refs": {
            "type": "array",
            "items": {
              "$ref": "https://specdev.local/schema/core/collections/1#traceRef"
            },
            "minItems": 1
          }
        },
        "allOf": [
          {
            "if": {
              "properties": {
                "trust_boundary": {
                  "enum": [
                    "partner",
                    "public"
                  ]
                }
              }
            },
            "then": {
              "required": [
                "auth",
                "rate_limit"
              ]
            }
          },
          {
            "if": {
              "properties": {
                "protocol": {
                  "enum": [
                    "event"
                  ]
                }
              }
            },
            "then": {
              "required": [
                "reliability"
              ]
            }
          }
        ],
        "required": [
          "from",
          "to",
          "protocol",
          "trust_boundary",
          "trace_refs"
        ]
      }
    }
  },
  "required": [
    "id",
    "owner",
    "created_at",
    "components"
  ],
  "allOf": [
    {
      "if": {
        "properties": {
          "components": {
            "minItems": 2
          }
        }
      },
      "then": {
        "required": [
          "connections"
        ],
        "properties": {
          "connections": {
            "type": "array",
            "minItems": 1
          }
        }
      }
    },
    {
      "if": {
        "properties": {
          "connections": {
            "type": "array",
            "minItems": 1
          }
        }
      },
      "then": {
        "properties": {
          "connections": {
            "items": {
              "allOf": [
                {
                  "if": {
                    "properties": {
                      "from": {
                        "type": "string"
                      }
                    }
                  },
                  "then": {
                    "required": [
                      "from"
                    ]
                  }
                },
                {
                  "if": {
                    "properties": {
                      "to": {
                        "type": "string"
                      }
                    }
                  },
                  "then": {
                    "required": [
                      "to"
                    ]
                  }
                }
              ]
            }
          }
        }
      }
    }
  ]
}
```

# Output Contract
```json
{
  "id": "system_sketch-catalog",
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
      "trace_refs": [
        {
          "type": "doc",
          "id": "capability-user-management"
        }
      ]
    }
  ],
  "connections": []
}
```
