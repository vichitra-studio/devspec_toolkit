# Step 02a · Delivery Baseline

## Purpose
Capture the minimum delivery infrastructure (environments, CI expectations, and compliance guardrails) needed to take the system sketch from spec to running code safely. This baseline makes deployment assumptions explicit early so fixture execution, governance, and implementation planning share the same operational picture.

# Role
You are a senior specification author and validator. Your job is to emit a single JSON artifact for **Step 2.5 · Delivery Baseline** that is machine-checkable and immediately consumable by CI and generators. You do not write examples, tutorials, or comments. You only output the canonical JSON that matches the schema.

# Task
- **Input context:** previously authored spec artifacts (Charter, Capabilities, Glossary, FRs, etc.) available to you in the workspace; organizational constraints; known IDs for cross-references.
- **Objective:** produce a complete, falsifiable artifact for **Step 2.5 · Delivery Baseline**.
- **Output type:** one JSON document conforming to the Embedded Schema.
- **Determinism:** when unspecified, choose the minimal valid value that preserves falsifiability and traceability.
- **Traceability:** if this step has `trace` or `links`, connect to at least one upstream or downstream artifact.


## Context To Ingest
- System Sketch `spec/02_system_sketch.json` for components and external dependencies that affect env setup.
- NFRs `spec/07_nfrs.json` for coverage and monitoring expectations impacting CI.
- Governance `spec/10_governance.json` for required checks.
- Current CI configs (if present) and `devspec_toolkit/tests/run.sh` usage from the reference docs.
- Guides: Shared expectations `devspec_toolkit/docs/prompts/shared_expectations.md`, developer reference.

## Operating Flow: Synthesize → Clarify → Emit
- Build a private Context Ledger: env matrix (dev/ci/staging/prod traits like region/runners/base images), CI gates (validator steps), secrets (names), compliance tags. Do not output it.
- Cross-check gates against governance and reference command list; add missing core checks.
- Self-audit; if any environment or critical gate is unclear, ask Gap Questions.
- Rewrite gate names to match CLI commands; ensure secrets are names only and compliance labels reflect actual obligations.
- Emit JSON once consistent.

## Heuristics For Completeness
- Optional→expected: include secrets required by external systems in the sketch; include compliance labels when NFRs or governance imply policies.
- Parity hint: staging should mirror prod critical gates and environment traits.
- Ambiguity scrub: map gates to `validate`, `validate-all`, `fixtures-lint`, `matrix`, `invariants-check`, `governance-check`, `gen-ci`.

## Self-Audit Gate
- If completeness < 0.9, ask and stop.
- Gating items:
  - All four environments listed; each has enough detail to differentiate.
  - CI gates include core validations; governance and coverage accounted for where relevant.
  - Secrets are names only; no values.
  - Compliance labels reflect real obligations (or explicitly none).

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
- All environments (`dev`, `ci`, `staging`, `prod`) present with relevant keys (e.g., regions, runtime versions, feature flags, data sources).
- `ci_gates` enumerates the gates we actually enforce (schema validate, fixtures-lint, matrix, invariants-check, coverage, governance-check).
- `secrets` includes names of required secrets; values are not embedded.
- `compliance` lists applicable frameworks/policies (e.g., SOC2, GDPR, PCI) if relevant.

## Field-by-Field Guidance
- environments.dev/ci/staging/prod: include minimal structure describing infra/tooling expectations (e.g., cloud, region, cluster, runners).
- ci_gates: ordered list of gate names as strings.
- secrets: namespaced identifiers (e.g., `PAYMENTS_API_KEY`), not values.
- compliance: list of applicable labels/policies (e.g., `gdpr-data-exportable`).

## Best Practices
- **Environments**: Document each environment (`dev`, `ci`, `staging`, `prod`) with the critical configuration knobs, dependencies, and access paths.
- **Reproducibility**: Define minimal environment descriptors to make CI/CD reproducible (runner type, region, base images).
- **Gates**: Enumerate `ci_gates` as actionable job names (schema, fixtures, security scans) that map directly to Step 12 output.
- **Secrets**: Track sensitive material in `secrets` by name only (no values), with ownership and rotation expectations.
- **Compliance**: Capture regulatory or contractual obligations under `compliance` to feed governance.

## Common Pitfalls
- **Empty Shells**: Leaving environment objects empty, forcing teams to guess runtime dependencies.
- **Manual Gates**: Mixing manual review steps into `ci_gates`, which belong in governance policies instead.
- **Secret Values**: Embedding secret values instead of names (security risk).
- **Staging Drift**: Missing staging environment parity causing late-stage surprises.
- **Optional Compliance**: Treating compliance requirements as optional notes instead of binding constraints.

## Quick Reference
- Environments: objects for `dev`, `ci`, `staging`, `prod`.
- CI Gates: strings naming the checks to run.

# Clarification Questions
- What deployment environments are required now and in the near term? Any differences in config or data sources?
- Which CI gates must block merges? Any minimum coverage thresholds or invariants that must run?
- What secrets are needed to run locally, in CI, and in prod? Where are they stored?
- What compliance or audit requirements apply to environments and pipelines?

# Embedded Schema
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://specdev.local/schema/02a_delivery_baseline.schema.json",
  "title": "02a_delivery_baseline",
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
    "environments": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "dev": {
          "type": "object"
        },
        "ci": {
          "type": "object"
        },
        "staging": {
          "type": "object"
        },
        "prod": {
          "type": "object"
        }
      },
      "required": [
        "dev",
        "ci",
        "staging",
        "prod"
      ]
    },
    "ci_gates": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "string"
      }
    },
    "secrets": {
      "$ref": "https://specdev.local/schema/core/collections/1#stringArray"
    },
    "compliance": {
      "$ref": "https://specdev.local/schema/core/collections/1#stringArray"
    }
  },
  "required": [
    "id",
    "owner",
    "created_at",
    "environments",
    "ci_gates"
  ]
}
```

# Output Contract
```json
{
  "id": "delivery_baseline-catalog",
  "owner": "api",
  "created_at": "2025-01-01T00:00:00Z",
  "environments": {
    "dev": {},
    "ci": {},
    "staging": {},
    "prod": {}
  },
  "ci_gates": []
}
```
