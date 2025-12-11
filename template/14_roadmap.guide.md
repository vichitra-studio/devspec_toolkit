# 14. Roadmap

## Purpose
Synthesize the foundational strategy (Step 09: Implementation Plan), the detailed core specifications (Steps 00–12), and any discovered domain extensions (Step 13) into a cohesive **Execution Roadmap**. This artifact drives the "Just-In-Time" implementation loop by breaking the massive scope down into sequential, verifiable milestones.

While Step 09 defined the *Strategic Baseline* (locked tech stack capabilities), Step 14 defines the *Tactical Schedule* (what we build next Monday).

## Template / Fields
- Canonical artifact: **spec/14_roadmap.json**
- Schema reference: `schema/09_impl_plan.schema.json` (REUSES Step 09 Schema; there is no 14 schema).
- Core atoms: `kebabId`, `owner`, `timestamp`, `tag` (see `schema/core/atoms.schema.json`)
- Core collections: `kebabIdArray`, `stringArray`, `link`, `traceRef`, `errorState`, `anyJson` (see `schema/core/collections.schema.json`)

## Prompt File
- Contract: `prompts/prompt_14_roadmap.md`
- Prompts include context ingestion (Core + Extensions), operating flow, soft heuristics, and a self‑audit gate. Assistants follow a two‑phase flow:
  - Phase A — Clarify: ingest context and, if gating items are missing (including "Completeness Check" failures), output only a short bulleted list of questions.
  - Phase B — Emit: once clarified, output exactly one fenced ```json``` block that validates against the `09_impl_plan` schema.

## Definition of Ready (DoR) / Guardrails
- **Completeness Check**: The roadmap MUST NOT be generated if significant "TBDs" exist in Steps 00–13. The prompt explicitly scans for this.
- **Extensions Ingested**: The roadmap MUST explicitly account for every Extension identified in `spec/13_extension_manifest.json`.

## Best Practices
- **Reuse Tech Stack**: In most cases, copy the `tech_stack` from `spec/09_impl_plan.json`. Only update it if Step 13 Extensions introduced new mandated tools (e.g., a specific Vector DB).
- **Sequence Dependencies**: Ensure "Infrastructure" or "Base API" milestones precede "UI" or "Complex Logic" milestones.
- **JIT Granularity**: Plan the immediate next 1-2 milestones in high detail (dates, deliverables) and leave later milestones fuzzier.
- **Audit Trace**: Use the `milestones[].risks` field to note *why* a complex extension was deferred or split.

## Common Pitfalls
- **Ignoring Extensions**: Failing to schedule the work defined in `13a_database.json` or `13b_security.json`.
- **Redoing Step 09**: Spending time debating "Python vs Go" (which was settled in Step 09) instead of planning "Sprint 1 vs Sprint 2".
- **Skipping Completeness**: Creating a roadmap for a spec full of holes; the Roadmap step is the final quality gate before coding.

## Related Steps
- **Step 09**: Implementation Plan - The strategic baseline this roadmap refines.
- **Step 13**: Extension Generator - The source of domain-specific work this roadmap schedules.
- **Step 15**: Scaffold - The first action taken based on Milestone 1 of this roadmap.
