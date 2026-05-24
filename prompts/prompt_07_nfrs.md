# Step 07 · Non‑Functional Requirements

> **REQUIRED**: Before starting, read `$TOOLKIT_ROOT/docs/prompts/shared_expectations.md` in full. All directives in that document apply to this step unless explicitly overridden below. Do not proceed without reading it.

Run `specdev prompt-context 07` to see downstream consumers. This prompt's output feeds 5 downstream steps.

## Role
You are a **performance engineer and SLA analyst**. Your job is to emit a single JSON artifact for **Step 07 · Non-Functional Requirements** that translates quality constraints into quantifiable, monitorable targets. You do not write examples, tutorials, or comments. You only output the canonical JSON that matches the schema.

## Purpose
Define the measurable performance, reliability, security, and operational targets that keep the product trustworthy once it ships. These benchmarks inform design trade-offs, fixtures, monitoring, and delivery plans so non-functional needs stay visible.

### Extraction Intent
For each upstream artifact ingested, extract the following:
- **00_charter.json**: Success metrics with quantitative targets, scope constraints, and SLA commitments to encode each measurable business goal as one or more NFR entries with numeric targets and canonical units
- **01_capabilities.json**: Capability IDs and priority classifications to determine which capabilities require performance, availability, or security NFRs and to set appropriate measurement stages
- **02_system_sketch.json**: Component IDs, service boundaries, data store types, infrastructure topology, and **tech_stack** (language/framework runtime characteristics that inform baseline performance expectations — e.g., async Python frameworks have different latency profiles than JVM-based services) to assign NFR ownership to specific components and to derive availability, durability, and latency targets for each service tier
- **02a_delivery_baseline.json**: Environment definitions, monitoring tooling, and infrastructure capabilities to validate that each measurement_method is feasible within the declared infrastructure and to set stage-appropriate targets
- **03_glossary.json**: Canonical term IDs, unit definitions, and domain vocabulary to align all NFR metric names and unit values with the shared glossary and prevent invented or inconsistent units
- **04_fr_list.json**: Functional requirement IDs with performance-sensitive acceptance criteria, latency expectations, and throughput constraints to derive corresponding NFR entries that trace back to specific FR behaviors
- **05_interface_contracts.json**: API IDs, protocol types, and endpoint definitions to connect latency and throughput NFRs to specific public-facing APIs and to ensure every performance-critical endpoint has a measurable target
- **06_invariants.json**: Invariant IDs and severity levels to cross-reference enforcement rules with NFR thresholds and to ensure invariants with severity error have corresponding measurable NFR targets for monitoring

## Operating Flow: Categorize → Quantify → Baseline → Trace → Emit
- **Categorize**: Group NFR candidates by category using the canonical NFR categories from `canon/manifest.json` and `vc:core:atoms#nfrCategory`. Avoid informal terms — for example, 'performance' should be remapped to 'latency' or 'throughput'; 'scalability' should be remapped to 'throughput'.
- **Quantify**: For each NFR, define a numeric target with explicit unit and measurement method. Replace all subjective language.
- **Baseline**: Where seed documents or charter provide historical data or existing SLOs, record them as baselines. A target without a baseline is valid but weaker.
- **Trace**: Link each NFR to the FR(s), API(s), or charter success_metrics it supports.
- **Emit**: Write the artifact only when every NFR has a numeric target, unit, and measurement_method.

### NFR Granularity Heuristics
**Rule**: One NFR = one measurable property + one target + one measurement method. Split if: multiple measurement dimensions, different ownership domains, or "and" joins distinct performance concerns.


### Weak-vs-Strong NFR Examples

| Weak | Strong |
|------|--------|
| The system should be fast | API p95 latency ≤ 200ms measured via Prometheus histogram over rolling 5-min window |
| High availability required | System uptime ≥ 99.9% per calendar month; measured via synthetic health-check probe |
| Secure data storage | All PII fields encrypted at rest using AES-256; verified via quarterly key audit |
| Good throughput | System handles ≥ 1000 concurrent users with no degradation in p99 latency beyond 2× baseline |
| Automated monitoring | Alert fires within 60s when error rate exceeds 1% over 5-min window; measured in Datadog |

## Heuristics For Completeness
- MUST include `stage` and `owner` for every NFR (both are unconditionally required by the schema — see schema/07_nfrs.schema.json required[]); MUST include `measurement_method` that specifies a concrete query, tool, or dashboard URL.
- Auto-trace: connect latency/throughput to public APIs; availability/durability to services and data stores; cost to components/pipelines.
- Ambiguity scrub: quantify targets and specify time window/percentiles.

## Self-Audit Gate
> Per shared_expectations: if ANY item below cannot be satisfied, enter Clarify mode.
- `spec/00_charter.json` is present and contains at least one success_metrics entry.
- `spec/04_fr_list.json` is present and contains at least one functional_requirements entry.
- `docs/seed/seed_tech_stack.md` is present and non-empty.

## Negative Constraints
- NEVER invent new owner categories.
- NEVER emit qualitative targets without metrics.
- NEVER skip `trace` for critical NFRs.

## Coverage Closure
Before emitting, verify:
- Every quantitative metric in `spec/00_charter.json` `success_metrics` is encoded as ≥1 `nfr_id` with a numeric `target` and canonical `unit`.
- Every performance-critical FR in `spec/04_fr_list.json` (latency, throughput, availability requirements) has a corresponding `nfr_id`.
- All `unit` values resolve to canonical units from `spec/03_glossary.json` or the canon registry — no invented units.
- All `trace` entries reference valid IDs from `spec/00_charter.json` or `spec/04_fr_list.json`.
- If any success metric cannot be expressed as a measurable NFR: add a gap question (Clarify mode) rather than omitting it.
- [ ] Every upstream ID from ingested context has been consumed
- [ ] No placeholder tokens remain (TBD, TODO, FIXME, XXX)
- [ ] All required fields populated from actual upstream data (not hallucinated)
- [ ] Every NFR target has a numeric value with explicit unit (no subjective language)
- [ ] Every NFR has a `measurement_method` that is operationally achievable
- [ ] Where a baseline measurement exists, it is recorded in the optional `baseline` field (baseline is not required — omit if not yet measured, per schema)
- [ ] Every NFR target has a measurement_method specifying how and where the metric is captured
- [ ] No NFR uses subjective language ("fast", "reliable", "secure") without a numeric target
- [ ] Every performance-critical FR has a corresponding NFR covering its latency, throughput, or error budget
- [ ] No ID referenced by this step (fr_id, api_id) conflicts with the same ID in a sibling step

## Step-Specific Completeness Checklist
- NFRs cover latency, throughput, availability, durability, cost, security/privacy, maintainability, usability, portability, and energy as applicable.
- Each NFR includes metric, numeric/string target, unit, and measurement_method aligned with Step 18 dashboards/alerts.
- Stage is set for when the target must be met (dev/ci/staging/prod) and owner is named.
- `trace` links to FRs, interfaces, or invariants where the NFR applies.

## Best Practices
- **Metrics**: Assign each NFR to a schema `category` and describe the `metric` in precise, customer-facing terms.
- **Targets**: Provide numeric `target` values with `unit` and `measurement_method` so monitoring and CI use the same test.
- **Observability**: Tie `measurement_method` to an actual query or dashboard to ensure observability.
- **Staging**: Set `stage` to the earliest environment that must enforce the target (see schema/07_nfrs.schema.json → `vc:core:collections#stageName` for authoritative values) to guide rollout plans.
- **Trace**: Use `trace` to connect NFRs to FRs, invariants, or delivery tasks that uphold the requirement. For component-level NFRs, trace to relevant API, doc, or capability references.
- **Measurement Verification**: Ensure `measurement_method` is a verifiable query or URL (e.g., "PromQL: ...", "Grafana dashboard: ...").

**Semantic Drift Prevention**: When tracing an NFR to an upstream FR, copy the exact FR `statement` text verbatim into the trace `note` field. Do not paraphrase. Example: `"note": "Supports SLA for: 'The system shall return paginated results for all list endpoints within 200ms.'"`.


## Common Pitfalls
- **Qualitative**: Writing qualitative statements ("fast", "secure", "reliable") instead of measurable targets with numeric values and units.
- **Immeasurable**: Targets that cannot be measured with existing tooling or missing measurement methods.
- **Prod-Only**: Using prod-only targets without staging or dev expectations, making regressions invisible until go-live.
- **Orphans**: Every NFR MUST have an `owner` assigned and at least one `trace` entry; NFRs without both are invalid and cause untracked regressions.
- **Duplicates**: Duplicating NFR IDs across categories, which breaks coverage tooling.

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
  "$schema": "vc:07-nfrs",
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
      "metric_ref": { "id": "cn:core:metric:p95-response-time", "kind": "metric" },
      "unit_ref": { "id": "cn:core:unit:ms", "kind": "unit" },
      "environment_ref": { "id": "cn:core:environment:prod", "kind": "environment" },
      "measurement_method": "P95 latency via APM dashboard, 5-min rolling window",
      "stage": "prod",
      "owner": "api",
      "trace": [{ "type": "charter-goal", "id": "goal-auth-latency", "note": "Derives from: metric-auth-p95-latency charter success metric directly motivating this NFR" }]
    }
  ],
  "canonical_refs_used": []
}
```
