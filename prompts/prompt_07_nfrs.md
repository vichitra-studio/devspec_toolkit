# Step 07 · Non‑Functional Requirements

Run `specdev prompt-context 07` to see downstream consumers. This prompt's output feeds X downstream steps.

## Path Variables
| Variable | Description |
|---|---|
| `$PRODUCT_ROOT` | Root of the consumer/product repository |
| `$TOOLKIT_ROOT` | Root of the devspec_toolkit directory |
| `$SPEC_DIR` | `$PRODUCT_ROOT/spec` — where spec artifacts live |
| `$SCHEMA_DIR` | `$TOOLKIT_ROOT/schema` — where JSON Schemas live |

## Purpose
Define the measurable performance, reliability, security, and operational targets that keep the product trustworthy once it ships. These benchmarks inform design trade-offs, fixtures, monitoring, and delivery plans so non-functional needs stay visible.

## Tool Execution
Validate the generated JSON:
```bash
./tools/run_specdev.sh validate <path_to_artifact> --repo-root ./devspec_toolkit
```

# Role
You are a senior specification author and validator. Your job is to emit a single JSON artifact for **Step 7 · Non‑Functional Requirements** that is machine-checkable and immediately consumable by CI and generators. You do not write examples, tutorials, or comments. You only output the canonical JSON that matches the schema.

# Task
- **Input context:** previously authored spec artifacts (Charter, Capabilities, Glossary, FRs, etc.) available to you in the workspace; organizational constraints; known IDs for cross-references.
- **Objective:** produce a complete, falsifiable artifact for **Step 7 · Non‑Functional Requirements**.
- **Output type:** one JSON document conforming to the referenced step schema.
- **Determinism:** when unspecified, choose the minimal valid value that preserves falsifiability and traceability.
- **Traceability:** if this step has `trace` or `links`, connect to at least one upstream or downstream artifact.


## Seed Order & Mandatory Sources
- Read `spec/common/seed_manifest.json` first; follow `global_seed_order` and `step_requirements["07"]`.
- Ingest required seeds in order before any other context.
- Populate `seed_refs` with the seeds actually used.
- If a required seed is missing or stale, stop and request it before proceeding.

## Context To Ingest
- Success metrics in `spec/00_charter.json` to align business outcomes with technical targets.
- Glossary `spec/03_glossary.json` for metric names and units; FRs `spec/04_fr_list.json` for performance-critical behaviors.
- Do not depend on downstream monitoring specs; derive measurement_method from available upstream artifacts and seed guidance.
- Guides: Shared expectations `$TOOLKIT_ROOT/docs/prompts/shared_expectations.md`, developer reference.

### Extraction Intent
For each upstream artifact ingested, extract the following:
- **00_charter.json**: Success metrics with units and targets for alignment with NFR targets
- **03_glossary.json**: Metric names and canonical units for consistent NFR definitions
- **04_fr_list.json**: Performance-critical behaviors requiring latency, throughput, or availability targets

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
- Populate `generation_quality.assumptions` with specific, testable claims about decisions made during generation.
- If score < 0.9, output clarifying questions only — do not emit JSON.
- Gating items:
  - Every NFR includes metric, target, unit, and measurement_method; prod-stage NFRs also have owner.
  - Names/units align with glossary; traces connect to relevant FRs/APIs/components.


### Coverage Closure
Before emitting, verify:
- Every quantitative metric in `spec/00_charter.json` `success_metrics` is encoded as ≥1 `nfr_id` with a numeric `target` and canonical `unit`.
- Every performance-critical FR in `spec/04_functional_requirements.json` (latency, throughput, availability requirements) has a corresponding `nfr_id`.
- All `unit` values resolve to canonical units from `spec/03_glossary.json` or the canon registry — no invented units.
- All `trace` entries reference valid IDs from `spec/00_charter.json` or `spec/04_functional_requirements.json`.
- If any success metric cannot be expressed as a measurable NFR: add a gap question (Clarify mode) rather than omitting it.
- [ ] Every upstream ID referenced in extraction intent has been consumed
- [ ] No placeholder tokens remain (TBD, TODO, FIXME, XXX)
- [ ] All required fields populated from actual upstream data (not hallucinated)
- [ ] `seed_refs` only contains seeds actually referenced in the output

# Output Rules
1. Write the final JSON artifact directly to disk at the step path under `spec/` (or runner-provided path).
2. The JSON must validate against the referenced step schema listed in `Schema Reference`.
3. All IDs must be unique kebab-case strings.
4. Use concrete numbers and metrics; avoid "fast" or "secure". Every NFR must be measurable via specific metric.
5. Include explicit preconditions, postconditions, and error states where applicable to the schema.
6. Set `owner` to one of: `api`, `ui`, `system`, `ops`, `data`, `product`, `business`, `engineering`.
7. If the schema supports `trace` or `links`, include at least one reference to connect artifacts across steps.
8. Do not include any fields outside the schema. `additionalProperties` is false everywhere.

## Step-Specific Completeness Checklist
- NFRs cover latency, throughput, availability, durability, cost, security/privacy, maintainability, usability, portability, and energy as applicable.
- Each NFR includes metric, numeric/string target, unit, and measurement_method aligned with Step 18 dashboards/alerts.
- Stage is set for when the target must be met (dev/ci/staging/prod) and owner is named.
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
- **Staging**: Set `stage` to the earliest environment that must enforce the target (dev, ci, staging, prod) to guide rollout plans.
- **Trace**: Use `trace` to connect NFRs to FRs, invariants, or delivery tasks that uphold the requirement. For component-level NFRs, trace to relevant API, doc, or capability references.
- **Measurement Verification**: Ensure `measurement_method` is a verifiable query or URL (e.g., "PromQL: ...", "Grafana dashboard: ...").

## Common Pitfalls
- **Qualitative**: Writing qualitative statements (e.g., "fast") instead of measurable targets.
- **Immeasurable**: Targets that cannot be measured with existing tooling or missing measurement methods.
- **Prod-Only**: Using prod-only targets without staging or dev expectations, making regressions invisible until go-live.
- **Orphans**: No owner assigned or missing traces, causing untracked regressions.
- **Duplicates**: Duplicating NFR IDs across categories, which breaks coverage tooling.

## Negative Constraints
- NEVER invent new owner categories.
- NEVER emit qualitative targets without metrics.
- NEVER skip `trace` for critical NFRs.

## Quick Reference
- Categories: latency, throughput, availability, durability, cost, security, privacy, maintainability, usability, portability, energy.
- Stage: `dev`, `ci`, `staging`, `prod`.

# Clarification Questions
- Which performance, reliability, cost, security/privacy, and energy targets are non-negotiable? Which are stretch?
- What are the exact units and where will each metric be measured (tool/query/url)?
- At what stage must each target be met (dev/ci/staging/prod)? Who owns it?
- Which FRs, APIs, or components does each NFR apply to? Any invariants required to enforce it?

# Schema Reference
- Schema URI: https://specdev.local/schema/07_nfrs.schema.json
- Schema File: schema/07_nfrs.schema.json
- Schema Registry: tools/schema_registry.json

## Hardening Protocol
- fail-closed preflight: verify required fields, allowed enums, referenced IDs, and command/tool existence before emitting JSON.
- No-Invention Rules: do not invent IDs, enums, commands, files, metrics, stages, or canonical mappings that are not grounded in provided inputs.
- Completeness Closure: run a final closure pass to confirm required sections, trace/canonical closure, and seed coverage are complete.
- blocker report: if required inputs are missing, conflicting, or ambiguous after clarification, stop and return a blocker report instead of speculative output.

# Output Contract
```json
{
  "id": "nfrs-catalog",
  "owner": "api",
  "created_at": "2025-01-01T00:00:00Z",
  "seed_refs": [
    {
      "seed_id": "seed-overview"
    }
  ],
  "spec_refs_ingested": [],
  "nfrs": [
    {
      "nfr_id": "nfr-latency-auth-login",
      "category": "latency",
      "metric": "p95 login latency",
      "target": 200,
      "unit": "ms",
      "metric_ref": {
        "id": "cn:core:metric:error-rate",
        "kind": "metric"
      },
      "unit_ref": {
        "id": "cn:core:unit:ms",
        "kind": "unit"
      },
      "environment_ref": {
        "id": "cn:core:environment:prod",
        "kind": "environment"
      },
      "measurement_method": "automated monitoring",
      "stage": "prod",
      "owner": "api"
    }
  ],
  "generation_quality": {
    "assumptions": []
  },
  "canonical_refs_used": [
    {
      "id": "cn:core:metric:error-rate",
      "kind": "metric"
    },
    {
      "id": "cn:core:unit:ms",
      "kind": "unit"
    },
    {
      "id": "cn:core:environment:prod",
      "kind": "environment"
    }
  ],
  "canonical_proposals": [],
  "canonical_conflicts": []
}
```

## Canonical Registry (Required Input)

Before generating output, you MUST load and search `canon/manifest.json` for existing canonical entries. Use this registry to:
1. Bind `*_ref` fields to existing canonical IDs (`cn:<namespace>:<kind>:<slug>`)
2. Resolve aliases via `canon/aliases.json`
3. Propose new entries in `canonical_proposals` when no match exists
4. Flag conflicts in `canonical_conflicts` when ambiguous matches are found
## Canonical Binding Rules
1. `canonical_refs_used` is REQUIRED and must list every canonical ID referenced by any `*_ref` field in this artifact.
2. `canonical_proposals` is REQUIRED (may be empty `[]`). Populate it for any new term, metric, entity, role, etc. that does not exist in the registry.
3. `canonical_conflicts` is REQUIRED (may be empty `[]`). Populate it when a field value matches multiple canonical entries or contradicts an existing definition.
4. `generation_quality` is REQUIRED. Populate `generation_quality.assumptions` with specific, testable claims about decisions made during generation.
5. For each `*_ref` field in the schema: if the semantic content exists, the ref MUST be populated. This is not optional.
