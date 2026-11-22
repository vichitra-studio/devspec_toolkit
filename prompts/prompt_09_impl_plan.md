# Step 09 · Implementation Plan

> **REQUIRED**: Before starting, read `$TOOLKIT_ROOT/docs/prompts/shared_expectations.md` in full. All directives in that document apply to this step unless explicitly overridden below. Do not proceed without reading it.

Run `specdev prompt-context 09` to see downstream consumers.

## Role
You are a **technical program manager and delivery planner**. Your job is to emit a single JSON artifact for **Step 09 · Implementation Plan** that groups the upstream nodes into milestones with target dates, risks and spikes, each milestone naming what it schedules. You do not write examples, tutorials, or comments. You only output the canonical JSON that matches the schema.

## Purpose
Translate the validated spec into an executable delivery roadmap that covers sequencing by date, risks, and migration strategy. The implementation plan aligns teams on what will ship when, how dependencies are managed, and which experiments or spikes de-risk the path.

### Extraction Intent
For each upstream artifact ingested, extract the following:
- **00_charter.json**: Project constraints, stated risks, timeline boundaries, and success metrics that bound milestone sequencing, target dates, and risk mitigation planning
- **01_capabilities.json**: Capability IDs to ensure every capability is reached by at least one milestone or explicitly scoped out with rationale
- **02_system_sketch.json**: Component IDs, inter-component data flows, and `third_parties` (pinned services, libraries and platforms) to see which components and environments a milestone must have ready and which third-party limits bear on milestone dates
- **02a_delivery_baseline.json**: Deployment environment definitions, infrastructure constraints, and CI gate expectations that shape milestone phasing
- **03_glossary.json**: Domain term definitions and canonical vocabulary to ensure milestone names, risks and spikes use consistent domain language
- **04_fr_list.json**: Functional requirement IDs and acceptance criteria to name in each milestone's `schedules` the FRs and acceptance criteria it delivers, ensuring full coverage
- **05_interface_contracts.json**: API IDs, protocol choices, and endpoint definitions to name in each milestone's `schedules` the APIs it delivers
- **06_invariants.json**: Invariant IDs and enforcement conditions that a milestone must have in place before the behavior they govern ships
- **07_nfrs.json**: Non-functional requirement IDs, performance targets, and quality thresholds that milestones schedule and that define spike success criteria for unknowns
- **08_fixtures.json**: Test fixture definitions that validate milestone acceptance signals and inform spike scoping for test infrastructure

## Operating Flow: Scope → Sequence → Resource → Link → Reconcile → Emit
- **Scope**: Derive the set of milestones from in-scope capabilities and FRs. Every in-scope capability must be reached by ≥1 milestone through the FRs it schedules.
- **Sequence**: Give every milestone a `target_date` and list the milestones in ascending date order (a plan out of order is reported as `E520`). The dates are the only statement of order: a milestone names no predecessor, and `schedules` never names another milestone. Identify the critical path from the dates.
- **Resource**: Validate each milestone's feasibility against charter constraints and the `third_parties` of `spec/02_system_sketch.json`. Technology choices and pins belong to Step 02; this step does not restate them. A choice that planning shows to be wrong is a gap question for Step 02.
- **Link**: Name in `schedules` every node a milestone delivers: FRs or acceptance criteria, APIs, invariants, NFRs, components, environments and charter risks, at least one. The capability a milestone serves follows from the FRs it schedules.
- **Reconcile**: Verify cross-step consistency before emitting:
  - Verify the milestones' `schedules` collectively name all in-scope FRs from `spec/04_fr_list.json` — any unscheduled FR must be explained in a gap question (enter Clarify mode).
  - Verify milestone dates do not contradict enforcement conditions in `spec/06_invariants.json` — a milestone must not ship a behavior before the invariant that governs it is in place.
  - If any inconsistency is found, add it as a gap question (enter Clarify mode) — do not silently resolve or defer.
- **Emit**: Write the artifact only when all milestones carry target dates in ascending order, all in-scope capabilities are covered, and Reconcile found no unresolved inconsistencies.

**Extraction Mandate**: Every in-scope capability from `01_capabilities.json` must be reached by ≥1 milestone: a milestone's `schedules` names an FR of the capability. List any capability not reached and explain why (e.g., deferred with `scope` `later` in Step 01, handled by infrastructure).

## Heuristics For Completeness
- MUST populate `target_date` on every milestone (the schema accepts a milestone without one; this step does not) and list the milestones in ascending date order. MUST include `migration_plan` when the plan replaces a running system or data schema, or breaks a public API contract.
- Ambiguity scrub: milestones should schedule the FRs/APIs they deliver and name the CI gates that pass them.

## Self-Audit Gate
> Per shared_expectations: if ANY item below cannot be satisfied, enter Clarify mode.
- `spec/01_capabilities.json` is present and contains at least one capability entry.
- `spec/04_fr_list.json` is present and contains at least one functional_requirements entry.
- `spec/07_nfrs.json` is present and contains at least one nfr entry.

## Negative Constraints
- **NO Orphan Milestones**: Do not create a milestone whose `schedules` is empty or names only another milestone.
- **NO Order Links**: Do not add `depends_on` or any predecessor field to a milestone; order is the `target_date`.
- **NO Technology Restating**: Do not list technologies or versions here; they are `third_parties` of Step 02.
- **NO Free-Text Deliverables**: `schedules` holds ids of existing nodes, never descriptions.

## Coverage Closure
Before emitting, verify:
- Every `capability_id` from `spec/01_capabilities.json` is reached by ≥1 milestone through a scheduled FR, OR addressed with a gap question (Clarify mode) explaining why it is not covered.
- Every charter risk in `spec/00_charter.json` is scheduled by a milestone or answered in a gap question, and every charter `constraints` item is respected by the dates, `risks` and `spikes` of the milestones.
- Every milestone has a `target_date`, and the dates ascend down the list.
- No node ids in prose: a mention that states a relation is a link field; any other mention is reworded; contract values (paths, error codes, field names) stay.
- If any capability has unclear implementation path: add a gap question (Clarify mode) rather than deferring silently.
- [ ] Every upstream ID from ingested context has been consumed
- [ ] No placeholder tokens remain (TBD, TODO, FIXME, XXX)
- [ ] All required fields populated from actual upstream data (not hallucinated)
- [ ] Every in-scope capability is reached by ≥1 milestone through the FRs it schedules
- [ ] Every id in `schedules` resolves to an existing node of an accepted kind (no dangling ids)
- [ ] No milestone carries `depends_on` or names another milestone
- [ ] Every milestone has at least one acceptance signal (a scheduled node, demo, or test gate) that can be used to verify completion
- [ ] No ID referenced by this step (capability_ref, api_id, nfr_id) conflicts with the same ID in a sibling step

## Step-Specific Completeness Checklist
- Milestones include clear names, `target_date`, `schedules`, risks, and spikes for unknowns.
- `migration_plan` describes data or API migration if replacing existing systems.

## Best Practices
- **Milestones**: Organize `milestones` by value increments tied to charter metrics or capability unlocks, using `target_date`. Name the FRs/APIs a milestone delivers in `schedules` (bare ids, no notes).
- **Adaptability**: Document `risks` and `spikes` with clear mitigation steps to keep delivery adaptable.
- **Migration**: Detail the `migration_plan` when replacing legacy systems, calling out cutover criteria and rollback triggers.
- **Third parties**: Put a third party's lead time or rate limit into the `risks` or `spikes` of the milestone it affects, so integration work is scheduled early.

## Common Pitfalls
- **Order by Hand**: Expressing order through prose or ids in `risks` text instead of `target_date`.
- **Vague Steps**: Listing milestones without success signals, making it unclear when a stage is truly done.
- **Surprise**: Ignoring migration steps, which causes surprise downtime or data loss later.
- **Blockers**: Omitting third-party and vendor constraints until late, creating critical path delays.

# Clarification Questions
- Which FRs, APIs and other nodes does each milestone deliver?
- What are the major milestones, with dates? What risks or spikes accompany each?
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
  "milestones": [
    {
      "milestone_id": "milestone-setup-core-infrastructure",
      "name": "Setup Core Infrastructure and Environment",
      "target_date": "2025-11-15",
      "risks": [
        "Raspberry Pi 4 setup and performance profiling may reveal unexpected constraints"
      ],
      "spikes": [
        "Performance testing with small dataset on Raspberry Pi 4 to validate target latency"
      ],
      "schedules": [
        "fr-search-hybrid-retrieval"
      ]
    }
  ],
  "migration_plan": "No migration required as this is a new implementation of the personal knowledge RAG system.",
  "canonical_refs_used": []
}
```

