# Step 06 · Invariants & Rules

## Purpose
Capture the non-negotiable truths, guardrails, and data relationships the system must uphold regardless of implementation. These invariants feed governance, contract validation, and monitoring so deviations trigger alerts before customers feel impact.

## Tool Execution
Validate the generated JSON:
```bash
./tools/run_specdev.sh validate <path_to_artifact> --repo-root ./devspec_toolkit
```

To verify your invariants logic, verify against a sample data file:
```bash
./tools/run_specdev.sh invariants-check <spec_dir> --sample <path_to_sample_json> --repo-root ./devspec_toolkit
```

# Role
You are a senior specification author and validator. Your job is to emit a single JSON artifact for **Step 6 · Invariants & Rules** that is machine-checkable and immediately consumable by CI and generators. You do not write examples, tutorials, or comments. You only output the canonical JSON that matches the schema.

# Task
- **Input context:** previously authored spec artifacts (Charter, Capabilities, Glossary, FRs, etc.) available to you in the workspace; organizational constraints; known IDs for cross-references.
- **Objective:** produce a complete, falsifiable artifact for **Step 6 · Invariants & Rules**.
- **Output type:** one JSON document conforming to the Embedded Schema.
- **Determinism:** when unspecified, choose the minimal valid value that preserves falsifiability and traceability.
- **Traceability:** if this step has `trace` or `links`, connect to at least one upstream or downstream artifact.


## Seed Order & Mandatory Sources
- Read `spec/common/seed_manifest.json` first; follow `global_seed_order` and `step_requirements["06"]`.
- Ingest required seeds in order before any other context.
- Populate `seed_refs` with the seeds actually used.
- If a required seed is missing or stale, stop and request it before proceeding.

## Context To Ingest
- FRs `spec/04_fr_list.json` to motivate rules.
- Interface Contracts `spec/05_interface_contracts.json` for request/response constraints.
- Governance expectations from project policy docs/seeds if rules reflect policies (e.g., commit references, versioning).
- Guides: Shared expectations `devspec_toolkit/docs/prompts/shared_expectations.md`, developer reference.

## Operating Flow: Synthesize → Clarify → Emit
- Build a private Context Ledger of candidate invariants with: inv_id, business description, executable expression (jsonlogic/CEL), scope (components/apis), severity, and traces. Do not output it.
- Validate expressions against referenced fields in fixtures/schemas to ensure evaluability.
- Self-audit; if any critical FR/NFR lacks a rule or scope is too broad, ask Gap Questions.
- Rewrite into executable expressions; constrain scope to reduce false positives; finalize traces.
- Emit JSON when rules are enforceable.

## Heuristics For Completeness
- Optional→expected: use `jsonlogic` for data predicates and `cel` for field-level logic; set `severity=error` for hard guarantees.
- Scope discipline: enumerate only affected components/APIs; avoid global rules unless necessary.
- Ambiguity scrub: translate narrative policies into boolean/evaluable forms.

## Self-Audit Gate
- If `generation_quality.preflight_passed` cannot be set to `true` with current evidence, stop and ask targeted questions.
- Gating items:
  - Each critical FR/NFR has at least one corresponding invariant or rationale for omission.
  - Expressions are syntactically valid and reference existing fields; scope defined for each rule; severity set.

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
- Every rule has a precise description, executable `language`, and concrete `expression` when automation is possible.
- `scope` limits rules to specific components or APIs to avoid false positives.
- `severity` set to `error` for hard guarantees and `warn` for observability; choose deliberately.
- `trace` connects rules to FRs/NFRs/governance to explain rationale.
- Avoid purely textual rules unless automation is truly not feasible.

## Field-by-Field Guidance
- inv_id: kebab-case; prefer `invariant-<domain>-<constraint>`.
- description: business-readable statement of the invariant.
- language: `jsonlogic`, `cel`, or `text`; prefer executable forms.
- expression: the actual rule; test for syntactic validity.
- scope.components/apis: k-ID lists to constrain where the rule applies. Example: `{"components": ["auth-service"], "apis": ["api-login"]}`.
- severity: `warn` or `error` based on impact.
- trace: `fr-*`, `nfr-*`, `api-*`, or governance refs. Example: `[{"type": "fr", "id": "fr-user-authentication"}]`.

## Best Practices
- **Language**: Choose the appropriate `language` (`jsonlogic`, `cel`, or `text`) and write evaluable `expression` strings for automated enforcement.
- **Scoping**: Describe each invariant in business language first, then map `scope.components` or `scope.apis` to constrain where it applies.
- **Severity**: Tag severity as `error` for hard guarantees and `warn` for observability alerts to guide escalation paths.
- **Trace**: Link invariants to FRs, NFRs, or governance rules using `trace` so auditors know why the rule exists.

## Negative Constraints
- ❌ DO NOT use `text` language unless absolutely necessary.
- ❌ DO NOT invent component IDs; use only those from Step 2.
- ❌ DO NOT skip tracing; every rule must have a reason (trace).

## Common Pitfalls
- **Empty Logic**: Leaving the `expression` empty or non-executable, which prevents automation in CI and runtime.
- **Severity Drill**: Setting severity to `warn` for hard requirements, letting regressions slip past controls.
- **False Positives**: Forgetting to scope the invariant, causing checks to fail on unrelated components.
- **Bad IDs**: Failing to version or reuse `inv_id`, leading to duplicate or orphaned invariants.

## Quick Reference
- ID Format: `invariant-<descriptor>`; keep stable for cross-step traceability.
- Required Fields: every rule needs `inv_id`, `description`, `language`, and `expression`.
- Scope Usage: populate `components` or `apis` arrays to target enforcement precisely.
- Trace Hooks: reference FR (`fr-*`), API (`api-*`), or governance policy IDs to show motivation.

# Clarification Questions
- Which truths must always hold regardless of implementation (data relationships, auth requirements, idempotency)?
- Where can we encode these as executable rules (jsonlogic or CEL)? Provide expressions or field-level specs.
- What scope should each rule have (components, APIs) to reduce noise and false alerts?
- Which rules are hard errors vs warnings? Who is accountable for remediation?
- Which FRs, NFRs, or governance policies motivate each invariant?

# Embedded Schema
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://specdev.local/schema/06_invariants.schema.json",
  "title": "06_invariants",
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
    "rules": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
          "inv_id": {
            "$ref": "https://specdev.local/schema/core/atoms/1#kebabId"
          },
          "description": {
            "type": "string"
          },
          "language": {
            "type": "string",
            "enum": [
              "jsonlogic",
              "cel",
              "text"
            ]
          },
          "expression": {
            "type": "string"
          },
          "scope": {
            "type": "object",
            "additionalProperties": false,
            "properties": {
              "components": {
                "$ref": "https://specdev.local/schema/core/collections/1#kebabIdArray"
              },
              "apis": {
                "$ref": "https://specdev.local/schema/core/collections/1#kebabIdArray"
              }
            }
          },
          "severity": {
            "type": "string",
            "enum": [
              "warn",
              "error"
            ]
          },
          "trace": {
            "type": "array",
            "items": {
              "$ref": "https://specdev.local/schema/core/collections/1#traceRef"
            }
          }
        },
        "required": [
          "inv_id",
          "description",
          "language",
          "expression",
          "trace"
        ]
      }
    },
    "generation_quality": {
      "$ref": "https://specdev.local/schema/core/collections/1#/$defs/generationQuality"
    },
    "canonical_refs_used": {
      "$ref": "https://specdev.local/schema/core/collections/1#/$defs/canonicalRefArray"
    },
    "canonical_proposals": {
      "type": "array",
      "items": {
        "$ref": "https://specdev.local/schema/core/collections/1#/$defs/canonicalProposal"
      },
      "default": []
    },
    "canonical_conflicts": {
      "type": "array",
      "items": {
        "$ref": "https://specdev.local/schema/core/collections/1#/$defs/canonicalConflict"
      },
      "default": []
    }
  },
  "required": [
    "id",
    "owner",
    "created_at",
    "seed_refs",
    "rules"
  ]
}
```

# Output Contract
```json
{
  "id": "invariants-catalog",
  "owner": "api",
  "created_at": "2025-01-01T00:00:00Z",
  "seed_refs": [
    {"seed_id": "seed-overview"}
  ],
  "rules": [
    {
      "inv_id": "inv-session-token-required",
      "description": "Authenticated endpoints require a valid session token.",
      "language": "text",
      "expression": "request.authenticated == true",
      "scope": {
        "components": ["auth-service"]
      },
      "trace": [
        {
          "type": "doc",
          "id": "fr-auth-login"
        }
      ]
    }
  ],
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
