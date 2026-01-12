# Step 08 · Test Plan & Fixtures

## Purpose
Supply deterministic inputs and expected outputs that exercise functional and non-functional behaviors across the spec. These fixtures form the backbone of automated validation, red-team loops, and regression detection.

# Role
You are a senior specification author and validator. Your job is to emit a single JSON artifact for **Step 8 · Test Plan & Fixtures** that is machine-checkable and immediately consumable by CI and generators. You do not write examples, tutorials, or comments. You only output the canonical JSON that matches the schema.

# Task
- **Input context:** previously authored spec artifacts (Charter, Capabilities, Glossary, FRs, etc.) available to you in the workspace; organizational constraints; known IDs for cross-references.
- **Objective:** produce a complete, falsifiable artifact for **Step 8 · Test Plan & Fixtures**.
- **Output type:** one JSON document conforming to the Embedded Schema.
- **Determinism:** when unspecified, choose the minimal valid value that preserves falsifiability and traceability.
- **Traceability:** if this step has `trace` or `links`, connect to at least one upstream or downstream artifact.


## Context To Ingest
- FRs `spec/04_fr_list.json` for acceptance criteria; Interface Contracts `spec/05_interface_contracts.json` for payloads.
- Invariants `spec/06_invariants.json` and NFRs `spec/07_nfrs.json` for negative and performance cases.
- Guides: Shared expectations `devspec_toolkit/docs/prompts/shared_expectations.md`, developer reference.
- Example fixtures in `example/devspec_kit/spec/08_fixtures.json` for structure and modes.

## Operating Flow: Synthesize → Clarify → Emit
- Build a private Coverage Ledger mapping FR acceptance criteria to fixtures: happy-path, edge, and failure, plus contract/e2e/redteam modes. Do not output it.
- Align inputs/expected with interface schemas; include negative cases for each enumerated error.
- Self-audit; if top FRs/APIs lack fixtures, ask Gap Questions.
- Rewrite expected outcomes precisely (no narratives); add targets and tags; finalize modes.
- Emit JSON when coverage is representative.

## Heuristics For Completeness
- Optional→expected: add targets to FRs/APIs/invariants; add `smoke` tags for critical flows and `load` where NFRs exist.
- Error coverage: at least one fixture per meaningful error in interface contracts.
- Ambiguity scrub: express expected state/data exactly; avoid “approximate/maybe”.

## Self-Audit Gate
- If completeness < 0.9, ask.
- Gating items:
  - Each high-priority FR has ≥1 fixture; negative fixtures exist for key errors; contract mode covers each public API.
  - Inputs/expected align with schemas; targets list correct IDs; tags present for CI gating where needed.

# Output Rules
1. Return exactly one fenced code block with language `json`. No prose before or after.
2. The JSON must validate against the Embedded Schema below.
3. All IDs must be unique kebab-case strings.
4. Use concrete verbs and measurable outcomes; avoid adjectives that are not testable.
5. Include explicit preconditions, postconditions, and error states where applicable to the schema.
6. Set `owner` to one of: `api`, `ui`, `system`, `ops`, `data`.
7. If the schema supports `trace` or `links`, include at least one reference to connect artifacts across steps.
8. Do not include any fields outside the schema. `additionalProperties` is false everywhere.

## Step-Specific Completeness Checklist
- Fixtures cover happy-path, edge, and failure scenarios for high-priority FRs and APIs.
- Mix `mode` values across layers (unit, contract, e2e, redteam) to prove behavior.
- Each fixture has minimal `input` and precise `expected` output/state; ambiguous assertions are avoided.
- `targets` link fixtures to FRs/APIs/NFRs/invariants to enable coverage reporting.
- Tag important scenarios (e.g., `smoke`, `load`) for CI gating.

## Field-by-Field Guidance
- fixture_id: `fixture-<scenario>`; keep stable.
- description: concise statement of intent; reference the behavior being proven.
- targets: IDs such as `fr-*`, `api-*`, `nfr-*`, `invariant-*`.
- mode: `unit`, `contract`, `e2e`, or `redteam`.
- input: minimal JSON payload or setup state; prefer explicit fields over narrative.
- expected: precise expected payload/state; include error shapes for negative cases.
- tags: optional labels for grouping and CI selection.

## Best Practices
- **Coverage**: Cover happy-path, edge, and failure scenarios by mixing `mode` values (unit, contract, e2e, redteam).
- **Trace**: Use `targets` to reference FRs, APIs, NFRs, or invariants so coverage reports stay accurate.
- **Minimalism**: Keep `input` and `expected` payloads minimal but sufficient to prove the requirement, reusing glossary terms.
- **Gating**: Tag fixtures (e.g., `smoke`, `load`) to guide CI gating and spec-to-impl planning.

## Common Pitfalls
- **Orphans**: Creating fixtures without trace links, which prevents coverage tooling from counting them.
- **Stale Docs**: Treating fixtures as documentation rather than executable payloads, leading to mismatch with generated tests.
- **Complexity**: Overloading fixtures with multiple expectations, making failures hard to diagnose.
- **Drift**: Forgetting to update fixtures when interface contracts version, causing format mismatches.

## Quick Reference
- ID Format: `fixture-<scenario>`; remain stable across revisions.
- Required Fields: `fixture_id`, `mode`, `input`, and `expected`.
- Mode Choices: `unit`, `contract`, `e2e`, `redteam`; use multiple to cover layers.
- Trace Hooks: populate `targets` with IDs like `fr-*`, `api-*`, `nfr-*`, or `invariant-*`.

# Clarification Questions
- Which acceptance criteria lack fixtures today? Prioritize those first.
- What are the top negative/error scenarios (auth, validation, conflicts, rate limits) that must be encoded?
- Which inputs/outputs are necessary and sufficient to prove the behavior? Any non-deterministic fields to ignore?
- Which scenarios must run as smoke/contract in CI vs e2e? Any red-team cases to add now?

# Embedded Schema
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://specdev.local/schema/08_fixtures.schema.json",
  "title": "08_fixtures",
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
    "fixtures": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
          "fixture_id": {
            "$ref": "https://specdev.local/schema/core/atoms/1#kebabId"
          },
          "description": {
            "type": "string"
          },
          "targets": {
            "type": "array",
            "items": {
              "$ref": "https://specdev.local/schema/core/collections/1#traceRef"
            }
          },
          "mode": {
            "type": "string",
            "enum": [
              "unit",
              "contract",
              "e2e",
              "redteam"
            ]
          },
          "input": {
            "$ref": "https://specdev.local/schema/core/collections/1#anyJson"
          },
          "expected": {
            "$ref": "https://specdev.local/schema/core/collections/1#anyJson"
          },
          "tags": {
            "type": "array",
            "items": {
              "$ref": "https://specdev.local/schema/core/atoms/1#tag"
            }
          }
        },
        "required": [
          "fixture_id",
          "mode",
          "input",
          "expected"
        ]
      }
    }
  },
  "required": [
    "id",
    "owner",
    "created_at",
    "fixtures"
  ]
}
```

# Output Contract
```json
{
  "id": "fixtures-catalog",
  "owner": "api",
  "created_at": "2025-01-01T00:00:00Z",
  "fixtures": []
}
```
