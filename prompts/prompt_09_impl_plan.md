# Step 09 · Implementation Plan

> **Inherits**: `$TOOLKIT_ROOT/docs/prompts/shared_expectations.md` — all directives apply unless explicitly overridden below.

Run `specdev prompt-context 09` to see downstream consumers. This prompt's output feeds 3 downstream steps.

## Purpose
Translate the validated spec into an executable delivery roadmap that covers technology choices, sequencing, risks, and migration strategy. The implementation plan aligns teams on what will ship when, how dependencies are managed, and which experiments or spikes de-risk the path.

### Extraction Intent
For each upstream artifact ingested, extract the following:
- **00_charter.json**: Project constraints, stated risks, timeline boundaries, and success metrics that bound milestone sequencing, target dates, and risk mitigation planning
- **01_capabilities.json**: Capability IDs and priority rankings to ensure every capability is covered by at least one milestone deliverable or explicitly scoped out with rationale
- **02_system_sketch.json**: Component IDs, component status (active vs deprecated), and inter-component data flows to inform architecture decisions and trigger migration plan requirements
- **02a_delivery_baseline.json**: Deployment environment definitions, infrastructure constraints, and CI gate expectations that shape infrastructure tech stack selections and milestone phasing
- **03_glossary.json**: Domain term definitions and canonical vocabulary to ensure milestone names, deliverable descriptions, and tech stack rationale use consistent domain language
- **04_fr_list.json**: Functional requirement IDs and acceptance criteria to populate milestone deliverables arrays with traceable FR references ensuring full coverage
- **05_interface_contracts.json**: API IDs, protocol choices, and endpoint definitions to populate milestone deliverables arrays with traceable API references and inform framework selection
- **06_invariants.json**: Invariant IDs and enforcement conditions that constrain tech stack choices and must be satisfied as acceptance criteria within milestone deliverables
- **07_nfrs.json**: Non-functional requirement IDs, performance targets, and quality thresholds that constrain tech stack selection and define spike success criteria for unknowns
- **08_fixtures.json**: Test fixture definitions and target coverage expectations that validate milestone acceptance signals and inform spike scoping for test infrastructure

## Operating Flow: Synthesize → Clarify → Emit
- Build a private Plan Ledger: tech_stack (language/framework/db/tooling + versions), milestones (id/name/date/risks/spikes), migration plan (if replacing), dependencies (teams/vendors/apis). Do not output it.
- **Cross-Check**: Verify your `tech_stack` selection against `spec/01_capabilities.json`. Do not introduce technologies not listed in capabilities unless a corresponding Spike entry exists in `milestones[*].spikes` with explicit rationale referencing the capability gap.
- Align milestones with governance/CI cadence from upstream charter constraints and governance specs; add spikes for unknowns.
- Self-audit; if any risk lacks a measurable impact statement, any spike lacks a success criterion, or any dependency lacks an owner and timeline, ask Gap Questions.
- Rewrite milestones for outcomes and acceptance signals; finalize plan.
- Emit JSON when the plan is actionable.

## Heuristics For Completeness
- MUST populate `target_date` when milestones have ordering dependencies (i.e., one milestone's `deliverables` are consumed by another milestone). MUST include `migration_plan` when any `component_id` in `spec/02_system_sketch.json` has `status: deprecated` or is being replaced.
- Ambiguity scrub: milestones should map to delivered FRs/APIs and passing CI gates.

## Self-Audit Gate
- Gating items:
  - Tech choices include versions and rationale; milestones have names and acceptance signals; known risks/spikes captured.
  - `tech_stack` aligns with `01_capabilities.json`.
  - Dependencies listed for external teams/systems; plan aligns with governance/CI expectations.
  - If milestone dates are not stated in `spec/00_charter.json` constraints, delivery sequencing is ambiguous, or resource constraints are not specified in any upstream artifact, ask Gap Questions — do not invent timeline commitments.

### Coverage Closure
Before emitting, verify:
- Every `capability_id` from `spec/01_capabilities.json` appears in ≥1 milestone's scope or deliverables, OR explicitly listed in `out_of_scope` with rationale.
- All `component_id` values from `spec/02_system_sketch.json` are reflected in the `tech_stack` or architecture decisions.
- Every charter constraint in `spec/00_charter.json` (`constraints`, `risks`) is addressed in milestones, risks, or migration plan.
- All dependencies between milestones are explicit — no implicit ordering assumptions.
- If any capability has unclear implementation path: add a gap question (Clarify mode) rather than deferring silently.
- [ ] Every upstream ID from ingested context has been consumed
- [ ] No placeholder tokens remain (TBD, TODO, FIXME, XXX)
- [ ] All required fields populated from actual upstream data (not hallucinated)

## Negative Constraints
- **NO Hallucinations**: Do not list technologies in `tech_stack` that are not present in `spec/01_capabilities.json` without a clear "Spike" justification.
- **NO Generic Versions**: Do not use "latest" or "stable". You must allow the specific version pinning (e.g., "^3.9", "^1.2.3").
- **NO Orphan Milestones**: Do not create milestones that do not link to at least one FR or API in `deliverables`.
- **NO Unstructured Tech Stack**: Do not provide `tech_stack` as a list of strings. It MUST be an object with `languages`, `frameworks`, `infrastructure`, and `tools` arrays.
- **NO Missing Rationale**: Do not omit `rationale` for `tech_stack` items. Explain WHY a technology was chosen.

## Step-Specific Completeness Checklist
- `tech_stack` declares languages, frameworks, data stores, and major infra choices with rationale where contentious.
- Milestones include clear names, target dates, risks, and spikes for unknowns.
- `migration_plan` describes data or API migration if replacing existing systems.
- `dependencies` enumerate external systems, teams, or contracts that impact delivery.

## Best Practices
- **Stack**: Capture `tech_stack` decisions with rationale, version constraints, and ownership so scaffold generation is predictable.
- **Milestones**: Organize `milestones` by value increments tied to charter metrics or capability unlocks, using `target_date`. Link deliverables to FRs/APIs.
- **Adaptability**: Document `risks` and `spikes` with clear mitigation steps to keep delivery adaptable.
- **Migration**: Detail the `migration_plan` when replacing legacy systems, calling out cutover criteria and rollback triggers.
- **Dependencies**: Enumerate `dependencies` across teams or vendors to schedule integration work early.

## Common Pitfalls
- **Grab Bag**: Treating `tech_stack` as a grab bag with no versioning, leading to incompatible scaffolds.
- **Vague Steps**: Listing milestones without success signals, making it unclear when a stage is truly done.
- **Surprise**: Ignoring migration steps, which causes surprise downtime or data loss later.
- **Blockers**: Omitting external dependencies until late, creating critical path delays.

# Clarification Questions
- What tech choices are locked vs flexible? Any org standards to follow?
- What are the major deliverable milestones with dates? What risks or spikes accompany each?
- Are we migrating from an existing system? What is the plan for data, compatibility, and rollback?
- What external dependencies (teams, vendors) could block delivery? How will we mitigate?

# Schema Reference
- Schema URI: vc:09-impl-plan
- Schema File: schema/09_impl_plan.schema.json
- Schema Registry: tools/schema_registry.json

# Output Contract
```json
{
  "id": "impl-plan-catalog",
  "owner": "api",
  "created_at": "2025-01-01T00:00:00Z",
  "tech_stack": {
    "languages": [
      {
        "name": "python",
        "version": "^3.9",
        "rationale": "Required for ONNX Runtime compatibility"
      }
    ],
    "frameworks": [
      {
        "name": "FastAPI",
        "version": "^0.110.0",
        "rationale": "High-performance web framework"
      }
    ],
    "infrastructure": [
      {
        "name": "Raspberry Pi 4",
        "version": "Model B 4GB",
        "rationale": "Primary deployment target"
      }
    ],
    "tools": [
      {
        "name": "structlog",
        "version": "^24.1.0",
        "rationale": "Structured logging implementation"
      }
    ]
  },
  "milestones": [
    {
      "milestone_id": "milestone-setup-core-infrastructure",
      "name": "Setup Core Infrastructure and Environment",
      "target_date": "2025-11-15",
      "status": "pending",
      "risks": [
        "Raspberry Pi 4 setup and performance profiling may reveal unexpected constraints"
      ],
      "spikes": [
        "Performance testing with small dataset on Raspberry Pi 4 to validate target latency"
      ],
      "deliverables": [
        {
          "type": "fr",
          "id": "fr-search-hybrid-retrieval"
        }
      ]
    }
  ],
  "migration_plan": "No migration required as this is a new implementation of the personal knowledge RAG system.",
  "dependencies": [
    "Raspberry Pi 4 hardware (for deployment)",
    "Cloudflare Access for admin authentication"
  ],
  "trace": [
    {
      "type": "doc",
      "id": "personal-knowledge-rag-system"
    }
  ],
  "canonical_refs_used": []
}
```

