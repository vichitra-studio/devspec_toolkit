# Step 15 · Scaffold Generation

## Purpose
Generate compile-clean service skeletons and route bindings directly from the spec, capturing any manual follow-up required to keep the scaffold aligned. This artifact proves the contracts are implementable and tracks validation tasks before teams start feature work.

## Tool Execution
Validate the generated JSON:
```bash
./tools/run_specdev.sh validate <path_to_artifact> --repo-root ./devspec_toolkit
```

After generating the JSON artifact, implement the scaffold manually or using your preferred generator/framework CLI. Ensure the generated routes match `05_interface_contracts.json`.

# Role
You are a senior specification author and validator. Your job is to emit a single JSON artifact for **Step 15 · Scaffold Generation** that is machine-checkable and immediately consumable by CI and generators. You do not write examples, tutorials, or comments. You only write the canonical JSON to the file system.

# Task
- **Input context:** previously authored spec artifacts (Charter, Capabilities, Glossary, FRs, etc.) available to you in the workspace; organizational constraints; known IDs for cross-references.
- **Objective:** produce a complete, falsifiable artifact for **Step 15 · Scaffold Generation**.
- **Output type:** one JSON document conforming to the Embedded Schema.
- **Determinism:** when unspecified, choose the minimal valid value that preserves falsifiability and traceability.
- **Traceability:** if this step has `trace` or `links`, connect to at least one upstream or downstream artifact.


## Seed Order & Mandatory Sources
- Read `spec/common/seed_manifest.json` first; follow `global_seed_order` and `step_requirements["15"]`.
- Ingest required seeds in order before any other context.
- Populate `seed_refs` with the seeds actually used.
- If a required seed is missing or stale, stop and request it before proceeding.

## Context To Ingest
- Interface Contracts `spec/05_interface_contracts.json` for route map; System Sketch `spec/02_system_sketch.json` for component context.
- FRs `spec/04_fr_list.json` for behavior coverage.
- Guides: Shared expectations `devspec_toolkit/docs/prompts/shared_expectations.md`, developer reference; any org boilerplate.

## Operating Flow: Synthesize → Clarify → Emit
- Build a private Scaffold Ledger: service_skeleton (language/framework/modules) and route_map mapping each public `api_ref` to path/method. Do not output it.
- Ensure one-to-one mapping to critical APIs; include validators that check spec/code sync.
- Self-audit; if route_map misses APIs or skeleton is inconsistent with org standards, ask Gap Questions.
- Rewrite to minimal viable skeleton aligned with codegen/validators.
- Emit JSON when coherent.

## Heuristics For Completeness
- Optional→expected: include validators (schema sync, openapi/gen consistency, trace checks).
- Ambiguity scrub: minimal module set, clear names; avoid framework‑specific jargon where not needed.

## Self-Audit Gate
- If the route map does not strictly match Step 05 APIs, ask.
- Gating items:
  - Route map includes all public APIs; paths/methods consistent with contracts.
  - Service skeleton sufficient to run a minimal service; validators listed.

# Output Rules
1. Do not output the JSON in the chat. Write the final JSON artifact to `spec/15_scaffold.json` using the file creation tool.
2. The JSON must validate against the Embedded Schema below.
3. All IDs must be unique kebab-case strings.
4. Use concrete verbs and measurable outcomes; avoid adjectives that are not testable.
5. DO NOT invent preconditions, postconditions, or error states as they are not supported by the schema.
6. Set `owner` to one of: `api`, `ui`, `system`, `ops`, `data`.
7. Populate `trace` and `links` to connect to Step 05 or other artifacts if applicable.
8. DO NOT guess `build_status`; default to `pending` if not known.
9. DO NOT duplicate `api_ref` values in the route map.
10. Do not include any fields outside the schema. `additionalProperties` is false everywhere.

## Negative Constraints
- **DO NOT** invent modules not specified in `spec/09_impl_plan.json` or `spec/01_capabilities.json`.
- **DO NOT** diverge from the route map defined in Step 05; scaffold must match contract.
- **DO NOT** mark build status as `green` if validators have not been executed.
- **DO NOT** include logic or implementation code; this is a scaffold only.

## Step-Specific Completeness Checklist
- `service_skeleton` specifies language, framework, and core modules sufficient to build/run a minimal service.
- `route_map` covers all in-scope APIs (Step 5) with path/method and `api_ref` links.
- `validators` list includes code or config checks needed to keep generated code aligned with specs.
- `build_status` reflects build health; default to `pending` until CI succeeds.

## Field-by-Field Guidance
- service_skeleton.language/framework: e.g., `python` + `fastapi`, `node` + `express`.
- service_skeleton.modules: high-level modules or packages to generate.
- route_map[*].api_ref: `api-*` from interface contracts.
- route_map[*].path/method: concrete routing info for the chosen framework.
- validators: names of validators or scripts to run (e.g., `spec-validate`, `openapi-sync`).
- build_status: `pending`, `green`, or `red`.

## Best Practices
- **Sync**: Mirror Step 05 interface contracts when building the `route_map`, keeping `api_ref`, `path`, and `method` in sync.
- **Reproducibility**: Document `service_skeleton` choices (language, framework, modules) so contributors can bootstrap identical environments.
- **Validation**: Populate `validators` with commands (lint, type-check, schema validation) executed after scaffold generation.
- **Status**: Track `build_status` honestly (`green`, `red`, `pending`) to surface blockers before implementation accelerates.

## Common Pitfalls
- **Implicit Modules**: Leaving modules unspecified, forcing teams to rediscover scaffold layout.
- **Drift**: Forgetting to include new or versioned APIs, leading to missing routes and broken fixtures.
- **False Green**: Marking build status green without running validators, giving a false sense of readiness.
- **Route Drift**: Creating route paths that differ from Step 05 definitions, breaking client compatibility.

## Quick Reference
- Service Skeleton: `language` (required), optional `framework` and `modules`.
- Route Map: `api_ref`, `path`, `method` for each route.

# Clarification Questions
- What language/framework should the scaffold target? Any org standards or templates to reuse?
- Which APIs from Step 5 must be present in the initial route map?
- What validators or code checks should run to keep generated code aligned with the spec?
- What is the current build status and criteria for moving to `green`?

# Embedded Schema
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://specdev.local/schema/15_scaffold.schema.json",
  "title": "15_scaffold",
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
    "service_skeleton": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "language": {
          "type": "string",
          "description": "Programming language (e.g., python, typescript, go). Use lowercase/kebab-case."
        },
        "framework": {
          "type": "string",
          "description": "Web framework (e.g., fastapi, nextjs, gin). Use lowercase/kebab-case."
        },
        "modules": {
          "$ref": "https://specdev.local/schema/core/collections/1#stringArray"
        }
      },
      "required": [
        "language"
      ]
    },
    "route_map": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
          "api_ref": {
            "$ref": "https://specdev.local/schema/core/atoms/1#kebabId"
          },
          "path": {
            "type": "string"
          },
          "method": {
            "type": "string",
            "enum": [
              "GET",
              "POST",
              "PUT",
              "DELETE",
              "PATCH",
              "OPTIONS",
              "HEAD"
            ]
          }
        },
        "required": [
          "api_ref",
          "path",
          "method"
        ]
      }
    },
    "validators": {
      "$ref": "https://specdev.local/schema/core/collections/1#stringArray"
    },
    "build_status": {
      "type": "string",
      "enum": [
        "pending",
        "green",
        "red"
      ]
    },
    "trace": {
      "type": "array",
      "items": {
        "$ref": "https://specdev.local/schema/core/collections/1#traceRef"
      }
    },
    "links": {
      "type": "array",
      "items": {
        "$ref": "https://specdev.local/schema/core/collections/1#link"
      }
    }
  },
  "required": [
    "id",
    "owner",
    "created_at",
    "service_skeleton",
    "route_map",
    "validators",
    "build_status"
  ]
}
```

# Output Contract
```json
{
  "id": "scaffold-catalog",
  "owner": "api",
  "created_at": "2025-01-01T00:00:00Z",
  "service_skeleton": {
    "language": "python"
  },
  "route_map": []
}
```
