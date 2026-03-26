# Step 14 · Roadmap

> **Inherits**: `$TOOLKIT_ROOT/docs/prompts/shared_expectations.md` — all directives apply unless explicitly overridden below.

Run `specdev prompt-context 14` to see downstream consumers.

## Role
You are a **senior technical program manager and roadmap strategist**. Your job is to emit a single JSON artifact for **Step 14 · Roadmap** that translates the implementation plan into an execution-ready milestone sequence with FR-level task decomposition. You do not write examples, tutorials, or comments. You only output the canonical JSON that matches the schema.

## Purpose
Synthesize the foundational strategy (Step 09: Implementation Plan), the detailed core specifications (Steps 00–12), and any discovered domain extensions (Step 13) into a cohesive **Execution Roadmap**. This artifact drives the "Just-In-Time" implementation loop by breaking the scope down into sequential, verifiable milestones, where **Each Milestone** corresponds to exactly **One User Story** decomposed into atomic sub-tasks.

## Extraction Intent

### Primary Sources (directly consumed)
- **09_impl_plan.json**: Design-level milestones as the starting structure; derive execution milestones from these; copy `tech_stack` into the roadmap tech_stack and use Step 09 milestone IDs in `source_milestones`
- **04_fr_list.json**: FR IDs and acceptance criteria for milestone `fr_refs` and task-level acceptance criteria — every FR ID must appear in ≥1 milestone's `fr_refs`
- **01_capabilities.json**: Capability IDs for milestone-level `capability_refs` ensuring every capability is scheduled for delivery in at least one milestone

### Reference Sources (context only)
- **00_charter.json**: Project scope, timeline constraints, and success criteria used to bound roadmap milestones and validate that no out-of-scope work is scheduled
- **02_system_sketch.json**: Component architecture, subsystem dependencies, and `tech_stack` decisions (Step 02 is the authoritative source for technology choices) used to determine milestone sequencing so infrastructure precedes dependent application layers; the roadmap `tech_stack` must be grounded in Step 02's declarations
- **02a_delivery_baseline.json**: Deployment environment specifications and release cadence constraints incorporated into milestone target dates and infrastructure task planning
- **03_glossary.json**: Canonical domain terminology used to ensure consistent naming of milestones, tasks, and deliverables across the roadmap artifact
- **05_interface_contracts.json**: API endpoint definitions and dependencies used to sequence API implementation tasks and verify deliverable traceability to specific contract IDs
- **06_invariants.json**: System invariant rules incorporated as task constraints and acceptance criteria to ensure milestone completion preserves data integrity guarantees
- **07_nfrs.json**: Performance thresholds, security requirements, and compliance constraints incorporated as milestone risks and acceptance criteria for non-functional validation
- **08_fixtures.json**: Test fixture definitions used to bind milestone acceptance criteria to concrete fixture references ensuring each deliverable has verifiable test coverage
- **10_governance.json**: PR/commit rules that tasks must satisfy; used to ensure roadmap tasks align with governance-compliant delivery workflows and labeling requirements
- **11_redteam.json**: Identified threats and mitigations used to populate milestone risks and inform task prioritization for security-critical implementation sequences
- **12_ci_gates.json**: CI pipeline gate definitions used to ensure roadmap milestones include validation tasks that satisfy all required continuous integration quality checks
- **13_extension_generator.json**: Extension manifest entries used to schedule extension implementation work as dedicated milestones with proper dependency ordering after core infrastructure
- **13a_completeness_assessment.json** (if present): Coverage gaps to address in milestone decomposition; high-priority missing elements used to schedule remediation tasks before implementation begins

## Operating Flow: Ingest → Synthesize → Sequence → Decompose → Emit
- **Ingest**: Scan all `spec/` artifacts (Steps 00-13) to understand the complete scope.
- **Synthesize**: Identify every distinct feature, capability, and dependency across all specs.
- **Sequence**: Arrange milestones in logical order based on dependencies and critical path.
- **Decompose**: Break down Step 09 technical milestones into atomic user stories for Step 14.
- **Emit**: Generate a roadmap that groups these items into logical milestones using the JIT (Just-In-Time) philosophy—plan details iteratively while still providing required fields.

### Task vs FR Acceptance Criteria Relationship
Task `acceptance_criteria` in Step 14 REFINE the FR `acceptance_criteria` from Step 04 — they break high-level behavioral criteria into implementation-verifiable checks. Rules:
- Task acceptance criteria MUST NOT contradict FR acceptance criteria.
- Task acceptance criteria SHOULD be more specific and implementation-testable (e.g., "unit test passes for UserService.deactivate()" refines "user account is deactivated and sessions invalidated").
- Every task criterion should be verifiable by a specific CI check, unit test, or manual procedure.

**Step Authority**: Step 14 is the authoritative source for execution-level `migration_plan` entries and task-level `dependencies`. Step 09 provides the design-level implementation plan. When Step 09 and Step 14 disagree on sequencing or scope, Step 14 takes precedence for execution decisions.

## Heuristics For Completeness
- **Unified View**: The roadmap must include items from BOTH the Core specs and any found Extensions.
- **Ordering**: Core dependencies (e.g., Auth, Base API) must precede dependent Extensions.

## Self-Audit Gate
> Per shared_expectations: if ANY item below cannot be satisfied, enter Clarify mode.
- `spec/09_impl_plan.json` is present and contains at least one milestone entry.
- `spec/04_fr_list.json` is present and contains at least one functional_requirements entry.
- `spec/01_capabilities.json` is present and contains at least one capability entry.
- `spec/13a_completeness_assessment.json` is present.

## Negative Constraints
- **NO Hallucinations**: Do not list technologies not in Step 02, Step 09, or Step 13.
- **NO String Tech Stack**: `tech_stack` entries must be objects with `name` and `version` (optional `rationale`).
- **NO String Deliverables**: `deliverables` items must be traceRef objects with `type` and `id` (optional `note`).
- **NO Vague Tasks**: Tasks must be atomic and specific.
- **NO Orphan Milestones**: Every milestone must map to a user story.
- **NO Missing Source Milestones**: Every milestone must include `source_milestones` that map to Step 09 IDs.
- **NO Backward Planning**: Dates must proceed logically from earliest to latest.
- **NEVER create a `depends_on` cycle**: Task A depending on B which depends on A is forbidden and will fail validation.
- **NEVER use a `fr_refs` ID not present in `spec/04_fr_list.json`**: All FR references must be grounded in Step 04.
- **NEVER use a `capability_refs` ID not present in `spec/01_capabilities.json`**: All capability references must be grounded in Step 01.

## Coverage Closure
Before emitting, verify:
- Every upstream requirement from ingested context is represented in this artifact's `trace`, `links`, or `fr_refs` array, OR explicitly listed in `out_of_scope` with rationale.
- No upstream capability, FR, or milestone ID is silently dropped.
- All `trace` / `links` IDs resolve to IDs present in the referenced upstream spec file.
- If any upstream ID cannot be traced: add a gap question (Clarify mode) rather than omitting it.
- [ ] Every upstream ID from ingested context has been consumed
- [ ] No placeholder tokens remain (TBD, TODO, FIXME, XXX)
- [ ] All required fields populated from actual upstream data (not hallucinated)
- [ ] Every Step 09 milestone deliverable is addressed by ≥1 Step 14 task
- [ ] Every FR referenced in milestone `fr_refs` is covered by ≥1 task's `fr_refs`
- [ ] Task acceptance criteria refine (not contradict) the originating FR acceptance criteria
- [ ] Every FR from Step 04 appears in at least one task's `fr_refs`
- [ ] Every milestone's `source_milestones` references valid `milestone_id` values from Step 09

**Extraction Mandate**:
- Every FR ID from `04_functional_requirements.json` must appear in ≥1 milestone's `fr_refs`. List any FR not covered.

## Best Practices
- **One Milestone = One User Story**: Every milestone must map individually to a specific user story. Do not bundle multiple stories into one vague milestone.
- **Atomic Decomposition**: Each User Story must be broken down into specific, unambiguous, atomic sub-tasks.
- **Reuse Tech Stack**: Copy the `tech_stack` from `spec/09_impl_plan.json` (Step 09 is a required superset of Step 02's `tech_stack`). Only add entries if Step 13 Extensions introduced new mandated tools. Note: `spec/02_system_sketch.json` is the *origin* of tech stack decisions — Step 09 inherits and may refine them, but MUST NOT remove any Step 02 entries.
- **Sequence Dependencies**: Ensure "Infrastructure" or "Base API" milestones precede "UI" or "Complex Logic" milestones.
- **JIT Granularity**: Plan the immediate next 1-2 milestones in high detail (dates, deliverables). Later milestones MUST use tentative target dates and MUST include at minimum a `task_id`, `description` (>=2 words, imperative verb), and `status` for each task, but MAY omit `acceptance_criteria` and `depends_on`.
- **Audit Trace**: Use the `milestones[].risks` field to note *why* a complex extension was deferred or split.

## Common Pitfalls
- **Ignoring Extensions**: Failing to schedule the work defined in `ext_01_database.json` or `ext_02_security.json`.
- **Redoing Step 09**: Spending time debating "Python vs Go" (which was settled in Step 09) instead of planning "Sprint 1 vs Sprint 2".
- **Skipping Completeness**: Creating a roadmap for a spec full of holes; the Roadmap step is the final quality gate before coding.

## Cross-Step Synthesis Notes

### tech_stack.languages / tech_stack.frameworks / tech_stack.infrastructure / tech_stack.tools
- Use arrays of objects with `name` and `version` (optional `rationale`).
- Prefer copying from `spec/09_impl_plan.json`; only add entries if Step 13 extensions require them.

### milestones[].deliverables
- Use traceRef objects: `{ "type": "...", "id": "..." }` (optional `note`).
- Keep deliverables tightly tied to the milestone's user story.

### milestones[].target_date
- Use `YYYY-MM-DD` format.
- Ensure milestones are listed in chronological order.

### milestones[].status / milestones[].risk_status
- Use only the enum values from the schema.
- Omit if you want defaults (`pending`, `low`).

### milestones[].tasks
- Use objects with `task_id` and `description` (optional `status`).
- `task_id` must be kebab-case and unique within the milestone.
- `description` must be atomic and specific (at least two words).
- Use imperative verb form in `description` (e.g., "Implement authentication module").
- Use `acceptance_criteria` for non-trivial tasks; include `criterion_id` and a >=15 character `text` (optional `fixture_ref`).

### tasks[].depends_on
- List `task_id` values this task depends on (within the same milestone only).
- Do not create circular dependencies (A → B → A is forbidden).
- Omit or use `[]` when the task has no intra-milestone dependencies.

### tasks[].assumptions
- List assumptions that must hold for this task to succeed (≥10 characters each).
- Include at least one item when the task has external dependencies or uncertain preconditions.
- Example: "Database migration scripts are applied before service restarts."

### tasks[].exit_conditions
- List conditions that definitively mark this task complete (≥10 characters each).
- Be specific and verifiable (e.g., "All unit tests pass with 100% coverage for this module").
- Do not duplicate `acceptance_criteria`; exit conditions describe the done state, not the test.

### milestones[].source_milestones
- Provide one or more Step 09 milestone IDs this roadmap milestone decomposes.
- Use kebab-case IDs; include multiple when a milestone spans upstream work.

### milestones[].fr_refs
- List FR IDs from `spec/04_fr_list.json` that this milestone delivers.
- Must use exact IDs (e.g., `fr-user-login`). Every ID must exist in Step 04.
- **If this milestone has deliverables, `fr_refs` MUST be non-empty.** Omit or use `[]` only if the milestone is purely infrastructure with no user-facing functional requirements (e.g., CI pipeline setup, dependency upgrades). A milestone with deliverables but no `fr_refs` is a traceability gap and a red flag.
- Note: `fr_refs` and `capability_refs` belong on milestones, not on individual tasks. Tasks within a milestone inherit traceability through the milestone's refs.

### milestones[].capability_refs
- Bind to capability IDs from `spec/01_capabilities.json` that this milestone implements.
- Must use exact IDs (e.g., `cap-authentication`). Every ID must exist in Step 01.
- Omit or use `[]` if the milestone does not map to a specific capability.

### milestones[].risks
- List only risks that are directly related to the milestone.
- Use clear, actionable language (e.g., "Dependency on external API" rather than "Technical risk").

### milestones[].spikes
- Document only technical investigations that are necessary to resolve uncertainty.
- Keep spikes brief and focused on a single question or hypothesis.

### migration_plan
- Use a short string describing how legacy work is migrated, or `"none"` if not applicable.
- Keep it to one or two sentences; avoid rehashing Step 09.
- If not `"none"`, use at least three words and keep it under 40 words.

### dependencies
- Use objects with `type` and `id`; `owner` and `note` are required for external dependencies.
- For internal dependencies: `{ "type": "milestone", "id": "<milestone_id>" }` (`id` must be kebab-case).
- For external dependencies: `{ "type": "external", "id": "<dependency>", "owner": "<team-or-system>", "note": "<rationale>" }` (`id` must be kebab-case).

### trace
- Use traceRef objects to cite upstream specs that shape the roadmap.

# Note on `$schema`
The `$schema` field is required in the output and is stripped before validation during prompt-schema sync checks.

# Schema Reference
- Schema URI: vc:14-roadmap
- Schema File: schema/14_roadmap.schema.json
- Schema Registry: tools/schema_registry.json

# Output Contract
```json
{
  "$schema": "vc:14-roadmap",
  "id": "roadmap-v1",
  "owner": "system",
  "created_at": "2025-01-01T00:00:00Z",
  "migration_plan": "none",
  "tech_stack": {
    "languages": [
      { "name": "python", "version": "3.11" }
    ],
    "frameworks": [
      { "name": "fastapi", "version": "0.110.0" }
    ]
  },
  "milestones": [
    {
      "milestone_id": "m1-core-foundation",
      "name": "Core Foundation",
      "user_story": "As a developer, I want a stable base API so that I can build authentication features.",
      "source_milestones": ["m1-core-foundation"],
      "tasks": [
        {
          "task_id": "init-fastapi-project",
          "description": "Initialize FastAPI project structure",
          "acceptance_criteria": [
            {
              "criterion_id": "project-structure-ready",
              "text": "Project boots with FastAPI app and expected folder layout."
            }
          ]
        }
      ],
      "deliverables": [
        { "type": "doc", "id": "charter" }
      ],
      "target_date": "2025-02-01",
      "fr_refs": [],
      "capability_refs": []
    }
  ],
  "canonical_refs_used": []
}
```

