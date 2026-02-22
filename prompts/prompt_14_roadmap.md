# Step 14 · Roadmap

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
- Guide: Shared expectations `devspec_toolkit/docs/prompts/shared_expectations.md`.

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

### milestones[].source_milestones
- Provide one or more Step 09 milestone IDs this roadmap milestone decomposes.
- Use kebab-case IDs; include multiple when a milestone spans upstream work.

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
          { "task_id": "configure-docker-compose", "description": "Configure Docker compose for DB and App" },
          { "task_id": "implement-health-check", "description": "Implement health check endpoint" }
      ],
      "deliverables": [
        { "type": "doc", "id": "charter" },
        { "type": "nfr", "id": "ci-gates" }
      ],
      "target_date": "2025-02-01",
      "risks": [],
      "spikes": []
    }
  ],
  "generation_quality": {
    "preflight_passed": true,
    "evidence_records": [],
    "unresolved_inputs": [],
    "assumptions": [],
    "placeholder_scan": {
      "has_placeholders": false,
      "tokens_found": []
    },
    "self_check_results": []
  },
  "canonical_refs_used": [],
  "canonical_proposals": [],
  "canonical_conflicts": []

}
```

## B4 Metadata Contract
- Include `generation_quality`, `canonical_refs_used`, `canonical_proposals`, and `canonical_conflicts` in the output artifact whenever those fields exist in the step schema.
- `canonical_refs_used` must list canonicals actually referenced by `*_ref` fields in this artifact.
- Put unresolved or new terms into `canonical_proposals`; put ambiguous/conflicting mappings into `canonical_conflicts`.

