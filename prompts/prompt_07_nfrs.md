# Step 07 · Non‑Functional Requirements

> **Inherits**: `$TOOLKIT_ROOT/docs/prompts/shared_expectations.md` — all directives apply unless explicitly overridden below.

Run `specdev prompt-context 07` to see downstream consumers. This prompt's output feeds 5 downstream steps.

## Purpose
Define the measurable performance, reliability, security, and operational targets that keep the product trustworthy once it ships. These benchmarks inform design trade-offs, fixtures, monitoring, and delivery plans so non-functional needs stay visible.

### Extraction Intent
For each upstream artifact ingested, extract the following:
- **00_charter.json**: Success metrics with quantitative targets, scope constraints, and SLA commitments to encode each measurable business goal as one or more NFR entries with numeric targets and canonical units
- **01_capabilities.json**: Capability IDs and priority classifications to determine which capabilities require performance, availability, or security NFRs and to set appropriate measurement stages
- **02_system_sketch.json**: Component IDs, service boundaries, data store types, and infrastructure topology to assign NFR ownership to specific components and to derive availability, durability, and latency targets for each service tier
- **02a_delivery_baseline.json**: Environment definitions, monitoring tooling, and infrastructure capabilities to validate that each measurement_method is feasible within the declared infrastructure and to set stage-appropriate targets
- **03_glossary.json**: Canonical term IDs, unit definitions, and domain vocabulary to align all NFR metric names and unit values with the shared glossary and prevent invented or inconsistent units
- **04_fr_list.json**: Functional requirement IDs with performance-sensitive acceptance criteria, latency expectations, and throughput constraints to derive corresponding NFR entries that trace back to specific FR behaviors
- **05_interface_contracts.json**: API IDs, protocol types, and endpoint definitions to connect latency and throughput NFRs to specific public-facing APIs and to ensure every performance-critical endpoint has a measurable target
- **06_invariants.json**: Invariant IDs and severity levels to cross-reference enforcement rules with NFR thresholds and to ensure invariants with severity error have corresponding measurable NFR targets for monitoring

## Operating Flow: Synthesize → Clarify → Emit
- Build a private Context Ledger of NFRs by category (latency/throughput/availability/etc.), with metric→target→unit→measurement_method, stage, owner, and traces to FRs/APIs/components. Do not output it.
- Align names/units with `spec/03_glossary.json`; MUST ensure measurement_method references a specific tool, query, or dashboard endpoint (not generic phrases like "automated monitoring").
- Self-audit; if units/methods/owners or stage are missing, ask Gap Questions.
- If measurement_method cannot be implemented with the system's infrastructure as defined in `spec/02_system_sketch.json` components and `spec/02a_delivery_baseline.json` environments, MUST ask Gap Questions for the intended measurement approach rather than inventing one.
- Rewrite targets to numeric/operational formats; finalize traces.
- Emit JSON when measurable.

## Heuristics For Completeness
- MUST include `stage` and `owner` for every NFR where `stage` is `prod` or `staging`; MUST include `measurement_method` that specifies a concrete query, tool, or dashboard URL.
- Auto-trace: connect latency/throughput to public APIs; availability/durability to services and data stores; cost to components/pipelines.
- Ambiguity scrub: quantify targets and specify time window/percentiles.

## Self-Audit Gate
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
- [ ] Every upstream ID from ingested context has been consumed
- [ ] No placeholder tokens remain (TBD, TODO, FIXME, XXX)
- [ ] All required fields populated from actual upstream data (not hallucinated)

## Step-Specific Completeness Checklist
- NFRs cover latency, throughput, availability, durability, cost, security/privacy, maintainability, usability, portability, and energy as applicable.
- Each NFR includes metric, numeric/string target, unit, and measurement_method aligned with Step 18 dashboards/alerts.
- Stage is set for when the target must be met (dev/ci/staging/prod) and owner is named.
- `trace` links to FRs, interfaces, or invariants where the NFR applies.

## Best Practices
- **Metrics**: Assign each NFR to a schema `category` and describe the `metric` in precise, customer-facing terms.
- **Targets**: Provide numeric `target` values with `unit` and `measurement_method` so monitoring and CI use the same test.
- **Observability**: Tie `measurement_method` to an actual query or dashboard to ensure observability.
- **Staging**: Set `stage` to the earliest environment that must enforce the target (dev, ci, staging, prod) to guide rollout plans.
- **Trace**: Use `trace` to connect NFRs to FRs, invariants, or delivery tasks that uphold the requirement. For component-level NFRs, trace to relevant API, doc, or capability references.
- **Measurement Verification**: Ensure `measurement_method` is a verifiable query or URL (e.g., "PromQL: ...", "Grafana dashboard: ...").

## Common Pitfalls
- **Qualitative**: Writing qualitative statements ("fast", "secure", "reliable") instead of measurable targets with numeric values and units.
- **Immeasurable**: Targets that cannot be measured with existing tooling or missing measurement methods.
- **Prod-Only**: Using prod-only targets without staging or dev expectations, making regressions invisible until go-live.
- **Orphans**: Every NFR MUST have an `owner` assigned and at least one `trace` entry; NFRs without both are invalid and cause untracked regressions.
- **Duplicates**: Duplicating NFR IDs across categories, which breaks coverage tooling.

## Negative Constraints
- NEVER invent new owner categories.
- NEVER emit qualitative targets without metrics.
- NEVER skip `trace` for critical NFRs.

# Clarification Questions
- Which performance, reliability, cost, security/privacy, and energy targets are non-negotiable? Which are stretch?
- What are the exact units and where will each metric be measured (tool/query/url)?
- At what stage must each target be met (dev/ci/staging/prod)? Who owns it?
- Which FRs, APIs, or components does each NFR apply to? Any invariants required to enforce it?

# Schema Reference
- Schema URI: vc:07-nfrs
- Schema File: schema/07_nfrs.schema.json
- Schema Registry: tools/schema_registry.json

# Output Contract
```json
{
  "id": "nfrs-catalog",
  "owner": "api",
  "created_at": "2025-01-01T00:00:00Z",
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
      "owner": "api",
      "trace": [
        {
          "type": "fr",
          "id": "fr-auth-login"
        }
      ]
    }
  ],
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
  ]
}
```
