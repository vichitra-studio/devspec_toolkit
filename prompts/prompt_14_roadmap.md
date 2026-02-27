# Step 14 · Roadmap

Run `specdev prompt-context 14` to see downstream consumers.

## Path Variables
| Variable | Description |
|---|---|
| `$PRODUCT_ROOT` | Root of the consumer/product repository |
| `$TOOLKIT_ROOT` | Root of the devspec_toolkit directory |
| `$SPEC_DIR` | `$PRODUCT_ROOT/spec` — where spec artifacts live |
| `$SCHEMA_DIR` | `$TOOLKIT_ROOT/schema` — where JSON Schemas live |

## Purpose
Synthesize the foundational strategy (Step 09: Implementation Plan), the detailed core specifications (Steps 00–12), and any discovered domain extensions (Step 13) into a cohesive **Execution Roadmap**. This artifact drives the "Just-In-Time" implementation loop by breaking the scope down into sequential, verifiable milestones, where **Each Milestone** corresponds to exactly **One User Story** decomposed into atomic sub-tasks.

## Tool Execution
Validate the generated JSON:
```bash
./tools/run_specdev.sh validate <path_to_artifact> --repo-root ./devspec_toolkit
```

Verify that the entire spec suite is consistent before finalizing the roadmap:
```bash
./tools/run_specdev.sh validate-all <spec_dir> --repo-root ./devspec_toolkit
```

# Role
You are a senior program manager and architect. Your job is to emit a single JSON artifact for **Step 14 · Roadmap** that aggregates all discovery specs (Core 00-12 and Extensions) into a cohesive implementation plan.

# Task
- **Input context:** Completed Phase 1 specs (`00_charter.json` through `12_ci_gates.json`) AND any Phase 2 Custom Extensions.
- **Objective:** Produce a high-level roadmap that sequences the work defined in both phases.
- **Output type:** One JSON document conforming to the referenced step schema.
- **Timing:** This step is executed AFTER all specifications are defined but BEFORE the detailed JIT Implementation Loop begins.

## Seed Order & Mandatory Sources
- Read `spec/common/seed_manifest.json` first; follow `global_seed_order` and `step_requirements["14"]`.
- Ingest required seeds in order before any other context.
- Populate `seed_refs` with the seeds actually used.
- If a required seed is missing or stale, stop and request it before proceeding.

## Context To Ingest
- Core Specs: `spec/00_charter.json` through `spec/12_ci_gates.json`.
- Extension Manifest: `spec/13_extension_manifest.json`.
- Extension Specs: All `spec/ext_*.json` files defined in the manifest.
- Charter: `spec/00_charter.json` for strategic goals.
- Completeness: `spec/13a_completeness_assessment.json`.
- Guide: Shared expectations `$TOOLKIT_ROOT/docs/prompts/shared_expectations.md`.

### Extraction Intent
For each upstream artifact ingested, extract the following:
- **00_charter.json**: Strategic goals and success metrics for milestone alignment
- **09_impl_plan.json**: Tech stack decisions and milestone IDs for `source_milestones` binding
- **13_extension_manifest.json**: Extension IDs and areas of concern for scheduling extension work
- **13a_completeness_assessment.json**: High-priority missing elements to schedule as remediation milestones
- **04_fr_list.json**: FR IDs for `fr_refs` binding on milestones
- **01_capabilities.json**: Capability IDs for `capability_refs` binding on milestones

## Operating Flow: Ingest → Synthesize → Sequence → Decompose → Emit
- **Ingest**: Scan all `spec/` artifacts (Steps 00-13) to understand the complete scope.
- **Synthesize**: Identify every distinct feature, capability, and dependency across all specs.
- **Sequence**: Arrange milestones in logical order based on dependencies and critical path.
- **Decompose**: Break down Step 09 technical milestones into atomic user stories for Step 14.
- **Emit**: Generate a roadmap that groups these items into logical milestones using the JIT (Just-In-Time) philosophy—plan details iteratively while still providing required fields.

## Heuristics For Completeness
- **Unified View**: The roadmap must include items from BOTH the Core specs and any found Extensions.
- **Ordering**: Core dependencies (e.g., Auth, Base API) must precede dependent Extensions.

## Self-Audit Gate
- Confirm that existing specs cover enough scope to justify a roadmap.
- Confirm all "High" priority items from `13a_completeness_assessment` are accounted for (either fixed or scheduled).
- If score < 0.9, output clarifying questions only — do not emit JSON.


### Coverage Closure
Before emitting, verify:
- Every upstream requirement referenced in "Context To Ingest" is represented in this artifact's `trace`, `links`, or `fr_refs` array, OR explicitly listed in `out_of_scope` with rationale.
- No upstream capability, FR, or milestone ID is silently dropped.
- All `trace` / `links` IDs resolve to IDs present in the referenced upstream spec file.
- If any upstream ID cannot be traced: add a gap question (Clarify mode) rather than omitting it.
- [ ] Every upstream ID referenced in extraction intent has been consumed
- [ ] No placeholder tokens remain (TBD, TODO, FIXME, XXX)
- [ ] All required fields populated from actual upstream data (not hallucinated)
- [ ] `seed_refs` only contains seeds actually referenced in the output

**Extraction Mandate**:
- Every FR ID from `04_functional_requirements.json` must appear in ≥1 milestone's `fr_refs`. List any FR not covered.

## Best Practices
- **One Milestone = One User Story**: Every milestone must map individually to a specific user story. Do not bundle multiple stories into one vague milestone.
- **Atomic Decomposition**: Each User Story must be broken down into specific, unambiguous, atomic sub-tasks.
- **Reuse Tech Stack**: In most cases, copy the `tech_stack` from `spec/09_impl_plan.json`. Only update it if Step 13 Extensions introduced new mandated tools.
- **Sequence Dependencies**: Ensure "Infrastructure" or "Base API" milestones precede "UI" or "Complex Logic" milestones.
- **JIT Granularity**: Plan the immediate next 1-2 milestones in high detail (dates, deliverables). Later milestones can use tentative target dates and lighter task detail but still include required fields.
- **Audit Trace**: Use the `milestones[].risks` field to note *why* a complex extension was deferred or split.

## Common Pitfalls
- **Ignoring Extensions**: Failing to schedule the work defined in `ext_01_database.json` or `ext_02_security.json`.
- **Redoing Step 09**: Spending time debating "Python vs Go" (which was settled in Step 09) instead of planning "Sprint 1 vs Sprint 2".
- **Skipping Completeness**: Creating a roadmap for a spec full of holes; the Roadmap step is the final quality gate before coding.

## Negative Constraints
- **NO Hallucinations**: Do not list technologies not in Step 09/13.
- **NO String Tech Stack**: `tech_stack` entries must be objects with `name` and `version` (optional `rationale`).
- **NO String Deliverables**: `deliverables` items must be traceRef objects with `type` and `id` (optional `note`).
- **NO Vague Tasks**: Tasks must be atomic and specific.
- **NO Orphan Milestones**: Every milestone must map to a user story.
- **NO Missing Source Milestones**: Every milestone must include `source_milestones` that map to Step 09 IDs.
- **NO Backward Planning**: Dates must proceed logically from earliest to latest.
- **NEVER create a `depends_on` cycle**: Task A depending on B which depends on A is forbidden and will fail validation.
- **NEVER use a `fr_refs` ID not present in `spec/04_fr_list.json`**: All FR references must be grounded in Step 04.
- **NEVER use a `capability_refs` ID not present in `spec/01_capabilities.json`**: All capability references must be grounded in Step 01.

## Field-by-Field Guidance
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

# Output Rules
1. Write the final JSON artifact directly to disk at the step path under `spec/` (or runner-provided path).
2. The JSON (excluding `$schema`) must validate against the referenced step schema listed in `Schema Reference`.
3. Include a top-level `$schema` field that matches the schema URI.
4. All milestones must have `target_date`, `deliverables`, and `source_milestones`.

# Note on `$schema`
The `$schema` field is required in the output and is stripped before validation during prompt-schema sync checks.

# Schema Reference
- Schema URI: https://specdev.local/schema/14_roadmap.schema.json
- Schema File: schema/14_roadmap.schema.json
- Schema Registry: tools/schema_registry.json

## Hardening Protocol
- fail-closed preflight: verify required fields, allowed enums, referenced IDs, and command/tool existence before emitting JSON.
- No-Invention Rules: do not invent IDs, enums, commands, files, metrics, stages, or canonical mappings that are not grounded in provided inputs.
- Completeness Closure: run a final closure pass to confirm required sections, trace/canonical closure, and seed coverage are complete.
- blocker report: if required inputs are missing, conflicting, or ambiguous after clarification, stop and return a blocker report instead of speculative output.

# Output Contract
```json
{
  "$schema": "https://specdev.local/schema/14_roadmap.schema.json",
  "id": "roadmap-v1",
  "owner": "system",
  "created_at": "2025-01-01T00:00:00Z",
  "seed_refs": [
    {"seed_id": "seed-overview"}
  ],
  "spec_refs_ingested": [],
  "migration_plan": "none",
  "tech_stack": {
    "languages": [
      { "name": "python", "version": "3.11" }
    ],
    "frameworks": [
      { "name": "fastapi", "version": "0.110.0" }
    ],
    "infrastructure": [
      { "name": "docker", "version": "24.0" }
    ],
    "tools": [
      { "name": "poetry", "version": "1.7.0" }
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
              { "criterion_id": "project-structure-ready", "text": "Project boots with FastAPI app and expected folder layout." }
            ]
          },
          { "task_id": "configure-docker-compose", "description": "Configure Docker compose for DB and App", "acceptance_criteria": [{ "criterion_id": "docker-ready", "text": "docker-compose up starts DB and App containers." }] },
          { "task_id": "implement-health-check", "description": "Implement health check endpoint", "acceptance_criteria": [{ "criterion_id": "health-ok", "text": "GET /health returns 200 with status ok." }] }
      ],
      "deliverables": [
        { "type": "doc", "id": "charter" },
        { "type": "nfr", "id": "ci-gates" }
      ],
      "target_date": "2025-02-01",
      "fr_refs": [],
      "capability_refs": [],
      "risks": [],
      "spikes": []
    }
  ],
  "generation_quality": {
    "assumptions": []
  },
  "canonical_refs_used": [],
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
