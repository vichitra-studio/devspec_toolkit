# Step 09 · Implementation Plan

> **REQUIRED**: Before starting, read `$TOOLKIT_ROOT/docs/prompts/shared_expectations.md` in full. All directives in that document apply to this step unless explicitly overridden below. Do not proceed without reading it.

Run `specdev prompt-context 09` to see downstream consumers. This prompt's output feeds 3 downstream steps.

## Role
You are a **technical program manager and delivery planner**. Your job is to emit a single JSON artifact for **Step 09 · Implementation Plan** that sequences deliverables into milestones with explicit dependencies, resource estimates, and traceability to capabilities. You do not write examples, tutorials, or comments. You only output the canonical JSON that matches the schema.

## Purpose
Translate the validated spec into an executable delivery roadmap that covers technology choices, sequencing, risks, and migration strategy. The implementation plan aligns teams on what will ship when, how dependencies are managed, and which experiments or spikes de-risk the path.

### Extraction Intent
For each upstream artifact ingested, extract the following:
- **00_charter.json**: Project constraints, stated risks, timeline boundaries, and success metrics that bound milestone sequencing, target dates, and risk mitigation planning
- **01_capabilities.json**: Capability IDs and priority rankings to ensure every capability is covered by at least one milestone deliverable or explicitly scoped out with rationale
- **02_system_sketch.json**: Component IDs, component status (active vs deprecated), inter-component data flows, and **tech_stack** decisions (languages, frameworks, infrastructure, tools) as the baseline technology stack to inherit and optionally refine
- **02a_delivery_baseline.json**: Deployment environment definitions, infrastructure constraints, and CI gate expectations that shape infrastructure tech stack selections and milestone phasing
- **03_glossary.json**: Domain term definitions and canonical vocabulary to ensure milestone names, deliverable descriptions, and tech stack rationale use consistent domain language
- **04_fr_list.json**: Functional requirement IDs and acceptance criteria to populate milestone deliverables arrays with traceable FR references ensuring full coverage
- **05_interface_contracts.json**: API IDs, protocol choices, and endpoint definitions to populate milestone deliverables arrays with traceable API references and inform framework selection
- **06_invariants.json**: Invariant IDs and enforcement conditions that constrain tech stack choices and must be satisfied as acceptance criteria within milestone deliverables
- **07_nfrs.json**: Non-functional requirement IDs, performance targets, and quality thresholds that constrain tech stack selection and define spike success criteria for unknowns
- **08_fixtures.json**: Test fixture definitions and target coverage expectations that validate milestone acceptance signals and inform spike scoping for test infrastructure

## Operating Flow: Scope → Sequence → Resource → Trace → Reconcile → Emit
- **Scope**: Derive the set of deliverables from in-scope capabilities and FRs. Every in-scope capability must appear in ≥1 deliverable.
- **Sequence**: Order milestones using `depends_on` references. Identify the critical path. A later milestone cannot depend on a future milestone (no cycles).
- **Resource**: Inherit `tech_stack` from `spec/02_system_sketch.json` as the baseline. Refine only when implementation planning reveals needs not covered at architecture time (e.g., a testing tool discovered during spike scoping, a version pin change based on compatibility testing). Validate feasibility against charter constraints.
- **Trace**: Link each milestone to the capability(ies) it delivers. Reference FR IDs where applicable.
- **Reconcile**: Verify cross-step consistency before emitting:
  - Verify `tech_stack` entries are a superset of `spec/02_system_sketch.json` `tech_stack` — Step 09 may ADD refinements (version pins, spike-discovered tools) but MUST NOT REMOVE or contradict entries from Step 02. Any tech stack item in Step 02 that is absent from Step 09 is a gap requiring explicit justification.
  - Verify milestones collectively cover all in-scope FRs from `spec/04_fr_list.json` — any uncovered FR must be explained in a gap question (enter Clarify mode).
  - Verify milestone delivery order does not contradict enforcement conditions in `spec/06_invariants.json` — a milestone must not ship a behavior before the invariant that governs it is in place.
  - If any inconsistency is found, add it as a gap question (enter Clarify mode) — do not silently resolve or defer.
- **Emit**: Write the artifact only when all milestones are sequenced without cycles, all in-scope capabilities are covered, and Reconcile found no unresolved inconsistencies.

**Milestone Ordering with `depends_on`**: Use the `depends_on` field on each milestone to declare prerequisite milestone IDs. This enables dependency-order validation via `specdev dependency-order-lint`. Rules:
- A milestone with no prerequisites has an empty or absent `depends_on`.
- Circular dependencies (A → B → A) are forbidden and will fail lint.
- `depends_on` IDs must reference milestone IDs defined in this same artifact.

**Extraction Mandate**: Every in-scope capability from `01_capabilities.json` must appear in ≥1 milestone `deliverables` array. List any capability not addressed and explain why (e.g., deferred to a future milestone, handled by infrastructure).

## Heuristics For Completeness
- MUST populate `target_date` when milestones have ordering dependencies (i.e., one milestone's `deliverables` are consumed by another milestone). MUST include `migration_plan` when any `component_id` in `spec/02_system_sketch.json` has `status: deprecated` or is being replaced.
- Ambiguity scrub: milestones should map to delivered FRs/APIs and passing CI gates.

## Self-Audit Gate
> Per shared_expectations: if ANY item below cannot be satisfied, enter Clarify mode.
- `spec/01_capabilities.json` is present and contains at least one capability entry.
- `spec/04_fr_list.json` is present and contains at least one functional_requirements entry.
- `spec/07_nfrs.json` is present and contains at least one nfr entry.
- `docs/seed/seed_tech_stack.md` is present and non-empty.

## Negative Constraints
- **NO Hallucinations**: Do not list technologies in `tech_stack` that are not present in `spec/02_system_sketch.json` `tech_stack` or `spec/01_capabilities.json` without a clear "Spike" justification.
- **NO Generic Versions**: Do not use "latest" or "stable". You must allow the specific version pinning (e.g., "^3.9", "^1.2.3").
- **NO Orphan Milestones**: Do not create milestones that do not link to at least one FR or API in `deliverables`.
- **NO Unstructured Tech Stack**: Do not provide `tech_stack` as a list of strings. It must be a structured object with the sections required by schema/09_impl_plan.schema.json.
- **NO Missing Rationale**: Including `rationale` for `tech_stack` items is strongly recommended. Explain WHY a technology was chosen whenever possible.

## Coverage Closure
Before emitting, verify:
- Every `capability_id` from `spec/01_capabilities.json` appears in ≥1 milestone's scope or deliverables, OR addressed with a gap question (Clarify mode) explaining why it is not covered.
- All `component_id` values from `spec/02_system_sketch.json` are reflected in the `tech_stack` or architecture decisions.
- Every charter constraint in `spec/00_charter.json` (`constraints`, `risks`) is addressed in milestones, risks, or migration plan.
- All dependencies between milestones are explicit — no implicit ordering assumptions.
- If any capability has unclear implementation path: add a gap question (Clarify mode) rather than deferring silently.
- [ ] Every upstream ID from ingested context has been consumed
- [ ] No placeholder tokens remain (TBD, TODO, FIXME, XXX)
- [ ] All required fields populated from actual upstream data (not hallucinated)
- [ ] Every in-scope capability maps to ≥1 milestone deliverable
- [ ] All `depends_on` references resolve to milestone IDs defined in this artifact (no dangling refs)
- [ ] No circular milestone dependencies exist
- [ ] Every milestone has at least one acceptance signal (named deliverable, demo, or test gate) that can be used to verify completion
- [ ] No ID referenced by this step (capability_ref, api_id, nfr_id) conflicts with the same ID in a sibling step

## Step-Specific Completeness Checklist
- `tech_stack` inherits from `spec/02_system_sketch.json` `tech_stack` and may add implementation-time refinements. All Step 02 `tech_stack` entries must be present (superset rule). New entries require rationale.
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
  "$schema": "vc:09-impl-plan",
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

