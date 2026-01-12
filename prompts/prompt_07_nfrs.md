# Step 07 · Non‑Functional Requirements

## Purpose
Define the measurable performance, reliability, security, and operational targets that keep the product trustworthy once it ships. These benchmarks inform design trade-offs, fixtures, monitoring, and delivery plans so non-functional needs stay visible.

# Role
You are a senior specification author and validator. Your job is to emit a single JSON artifact for **Step 7 · Non‑Functional Requirements** that is machine-checkable and immediately consumable by CI and generators. You do not write examples, tutorials, or comments. You only output the canonical JSON that matches the schema.

# Task
- **Input context:** previously authored spec artifacts (Charter, Capabilities, Glossary, FRs, etc.) available to you in the workspace; organizational constraints; known IDs for cross-references.
- **Objective:** produce a complete, falsifiable artifact for **Step 7 · Non‑Functional Requirements**.
- **Output type:** one JSON document conforming to the Embedded Schema.
- **Determinism:** when unspecified, choose the minimal valid value that preserves falsifiability and traceability.
- **Traceability:** if this step has `trace` or `links`, connect to at least one upstream or downstream artifact.


## Context To Ingest
- Success metrics in `spec/00_charter.json` to align business outcomes with technical targets.
- Glossary `spec/03_glossary.json` for metric names and units; FRs `spec/04_fr_list.json` for performance-critical behaviors.
- Monitoring `spec/16_delivery_monitoring.json` (if exists) to align measurement_method and dashboards.
- Guides: Shared expectations `devspec_toolkit/docs/prompts/shared_expectations.md`, developer reference.

## Operating Flow: Synthesize → Clarify → Emit
- Build a private Context Ledger of NFRs by category (latency/throughput/availability/etc.), with metric→target→unit→measurement_method, stage, owner, and traces to FRs/APIs/components. Do not output it.
- Align names/units with glossary; ensure measurement_method is practically measurable via dashboards/queries.
- Self-audit; if units/methods/owners or stage are missing, ask Gap Questions.
- Rewrite targets to numeric/operational formats; finalize traces.
- Emit JSON when measurable.

## Heuristics For Completeness
- Optional→expected: include stage and owner for all prod-impact NFRs; include measurement_method that is queryable.
- Auto-trace: connect latency/throughput to public APIs; availability/durability to services and data stores; cost to components/pipelines.
- Ambiguity scrub: quantify targets and specify time window/percentiles.

## Self-Audit Gate
- If completeness < 0.9, ask first.
- Gating items:
  - Every NFR includes metric, target, unit, and measurement_method; prod-stage NFRs also have owner.
  - Names/units align with glossary; traces connect to relevant FRs/APIs/components.

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
- NFRs cover latency, throughput, availability, durability, cost, security/privacy, maintainability, usability, portability, and energy as applicable.
- Each NFR includes metric, numeric/string target, unit, and measurement_method aligned with Step 18 dashboards/alerts.
- Stage is set for when the target must be met (dev/staging/prod) and owner is named.
- `trace` links to FRs, interfaces, or invariants where the NFR applies.

## Field-by-Field Guidance
- nfr_id: `nfr-<category>-<metric>`.
- category: choose from schema enum; pick most specific dimension.
- metric: human-readable metric name (e.g., p95 latency, monthly cost).
- target: concrete target (e.g., 300, "99.95%", "<= $1k/mo").
- unit: units like ms, rps, %, USD.
- measurement_method: how/where measured (e.g., PromQL query, vendor dashboard).
- stage: `dev`, `staging`, or `prod`.
- owner: who is accountable for meeting the target.
- trace: references to FRs/APIs/components/invariants.

## Best Practices
- **Metrics**: Assign each NFR to a schema `category` and describe the `metric` in precise, customer-facing terms.
- **Targets**: Provide numeric `target` values with `unit` and `measurement_method` so monitoring and CI use the same test.
- **Observability**: Tie `measurement_method` to an actual query or dashboard to ensure observability.
- **Staging**: Set `stage` to the earliest environment that must enforce the target (dev, staging, prod) to guide rollout plans.
- **Trace**: Use `trace` to connect NFRs to FRs, invariants, or delivery tasks that uphold the requirement.

## Common Pitfalls
- **Qualitative**: Writing qualitative statements (e.g., "fast") instead of measurable targets.
- **Immeasurable**: Targets that cannot be measured with existing tooling or missing measurement methods.
- **Prod-Only**: Using prod-only targets without staging or dev expectations, making regressions invisible until go-live.
- **Orphans**: No owner assigned or missing traces, causing untracked regressions.
- **Duplicates**: Duplicating NFR IDs across categories, which breaks coverage tooling.

## Quick Reference
- Categories: latency, throughput, availability, durability, cost, security, privacy, maintainability, usability, portability, energy.
- Stage: `dev`, `staging`, `prod`.

# Clarification Questions
- Which performance, reliability, cost, security/privacy, and energy targets are non-negotiable? Which are stretch?
- What are the exact units and where will each metric be measured (tool/query/url)?
- At what stage must each target be met (dev/staging/prod)? Who owns it?
- Which FRs, APIs, or components does each NFR apply to? Any invariants required to enforce it?

# Embedded Schema
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://specdev.local/schema/07_nfrs.schema.json",
  "title": "07_nfrs",
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
    "nfrs": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
          "nfr_id": {
            "$ref": "https://specdev.local/schema/core/atoms/1#kebabId"
          },
          "category": {
            "type": "string",
            "enum": [
              "latency",
              "throughput",
              "availability",
              "durability",
              "cost",
              "security",
              "privacy",
              "maintainability",
              "usability",
              "portability",
              "energy"
            ]
          },
          "metric": {
            "type": "string"
          },
          "target": {
            "oneOf": [
              {
                "type": "number"
              },
              {
                "type": "string"
              }
            ]
          },
          "unit": {
            "type": "string"
          },
          "measurement_method": {
            "type": "string"
          },
          "stage": {
            "type": "string",
            "enum": [
              "dev",
              "staging",
              "prod"
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
          "nfr_id",
          "category",
          "metric",
          "target",
          "unit"
        ]
      }
    }
  },
  "required": [
    "id",
    "owner",
    "created_at",
    "nfrs"
  ]
}
```

# Output Contract
```json
{
  "id": "nfrs-catalog",
  "owner": "api",
  "created_at": "2025-01-01T00:00:00Z",
  "nfrs": []
}
```
