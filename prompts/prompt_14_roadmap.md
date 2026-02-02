# Step 14 · Roadmap

## Purpose
Synthesize the foundational strategy (Step 09: Implementation Plan), the detailed core specifications (Steps 00–12), and any discovered domain extensions (Step 13) into a cohesive **Execution Roadmap**. This artifact drives the "Just-In-Time" implementation loop by breaking the scope down into sequential, verifiable milestones, where **Each Milestone** corresponds to exactly **One User Story** decomposed into atomic sub-tasks.

## Tool Execution
Validate the generated JSON:
```bash
python -m specdev_tools.cli validate <path_to_artifact> --repo-root .
```

Verify that the entire spec suite is consistent before finalizing the roadmap:
```bash
python -m specdev_tools.cli validate-all <spec_dir> --repo-root .
```

# Role
You are a senior program manager and architect. Your job is to emit a single JSON artifact for **Step 14 · Roadmap** that aggregates all discovery specs (Core 00-12 and Extensions) into a cohesive implementation plan.

# Task
- **Input context:** Completed Phase 1 specs (`00_charter.json` through `12_ci_gates.json`) AND any Phase 2 Custom Extensions.
- **Objective:** Produce a high-level roadmap that sequences the work defined in both phases.
- **Output type:** One JSON document conforming to the Embedded Schema.
- **Timing:** This step is executed AFTER all specifications are defined but BEFORE the detailed JIT Implementation Loop begins.

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
1. Return exactly one fenced code block with language `json`.
2. The JSON (excluding `$schema`) must validate against the Embedded Schema (specifically `schema/14_roadmap.schema.json`).
3. Include a top-level `$schema` field that matches the schema URI.
4. All milestones must have `target_date`, `deliverables`, and `source_milestones`.

# Note on `$schema`
The `$schema` field is required in the output and is stripped before validation, so it is intentionally omitted from the Embedded Schema block below.

# Embedded Schema
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://specdev.local/schema/14_roadmap.schema.json",
  "title": "14_roadmap",
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "id": {
      "$ref": "https://specdev.local/schema/core/atoms/1#kebabId"
    },
    "owner": {
      "$ref": "https://specdev.local/schema/core/atoms/1#owner"
    },
    "created_at": {
      "$ref": "https://specdev.local/schema/core/atoms/1#timestamp"
    },
    "tech_stack": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "languages": {
          "type": "array",
          "items": {
            "type": "object",
            "additionalProperties": false,
            "properties": {
              "name": {
                "type": "string"
              },
              "version": {
                "type": "string"
              },
              "rationale": {
                "type": "string"
              }
            },
            "required": [
              "name",
              "version"
            ]
          }
        },
        "frameworks": {
          "type": "array",
          "items": {
            "type": "object",
            "additionalProperties": false,
            "properties": {
              "name": {
                "type": "string"
              },
              "version": {
                "type": "string"
              },
              "rationale": {
                "type": "string"
              }
            },
            "required": [
              "name",
              "version"
            ]
          }
        },
        "infrastructure": {
          "type": "array",
          "items": {
            "type": "object",
            "additionalProperties": false,
            "properties": {
              "name": {
                "type": "string"
              },
              "version": {
                "type": "string"
              },
              "rationale": {
                "type": "string"
              }
            },
            "required": [
              "name",
              "version"
            ]
          }
        },
        "tools": {
          "type": "array",
          "items": {
            "type": "object",
            "additionalProperties": false,
            "properties": {
              "name": {
                "type": "string"
              },
              "version": {
                "type": "string"
              },
              "rationale": {
                "type": "string"
              }
            },
            "required": [
              "name",
              "version"
            ]
          }
        }
      },
      "required": ["languages", "frameworks"]
    },
    "milestones": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
          "milestone_id": { "$ref": "https://specdev.local/schema/core/atoms/1#kebabId" },
          "name": { "type": "string" },
          "target_date": { "type": "string", "format": "date" },
          "status": {
            "type": "string",
            "enum": [
              "pending",
              "in_progress",
              "done",
              "deferred"
            ],
            "default": "pending"
          },
          "risk_status": {
            "type": "string",
            "enum": [
              "low",
              "medium",
              "high",
              "critical"
            ],
            "default": "low"
          },
          "user_story": { "type": "string", "description": "The specific user story this milestone addresses." },
          "source_milestones": {
            "$ref": "https://specdev.local/schema/core/collections/1#kebabIdArray",
            "description": "Upstream Step 09 milestone IDs this roadmap milestone maps to."
          },
          "tasks": { 
              "type": "array",
              "items": {
                "type": "object",
                "additionalProperties": false,
                "properties": {
                  "task_id": { "$ref": "https://specdev.local/schema/core/atoms/1#kebabId" },
                  "description": { "type": "string", "pattern": "^\\S+\\s+\\S+.*$" },
                  "acceptance_criteria": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                      "type": "object",
                      "additionalProperties": false,
                      "properties": {
                        "criterion_id": { "$ref": "https://specdev.local/schema/core/atoms/1#kebabId" },
                        "text": { "type": "string", "minLength": 15 },
                        "fixture_ref": { "$ref": "https://specdev.local/schema/core/atoms/1#kebabId" }
                      },
                      "required": ["criterion_id", "text"]
                    }
                  },
                  "status": { "type": "string", "enum": ["pending", "in_progress", "done"] }
                },
                "required": ["task_id", "description"]
              },
              "description": "Atomic sub-tasks required to complete the user story."
          },
          "deliverables": {
            "type": "array",
            "items": { "$ref": "https://specdev.local/schema/core/collections/1#traceRef" }
          },
          "risks": { "$ref": "https://specdev.local/schema/core/collections/1#stringArray" },
          "spikes": { "$ref": "https://specdev.local/schema/core/collections/1#stringArray" }

        },
        "required": ["milestone_id", "name", "target_date", "user_story", "source_milestones", "tasks", "deliverables"]
      }
    },
    "migration_plan": { "type": "string", "minLength": 1 },
    "dependencies": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
          "type": { "type": "string", "enum": ["milestone", "external"] },
          "id": { "$ref": "https://specdev.local/schema/core/atoms/1#kebabId" },
          "owner": { "type": "string" },
          "note": { "type": "string", "pattern": "^\\S+\\s+\\S+.*$" }
        },
        "required": ["type", "id"],
        "allOf": [
          {
            "if": { "properties": { "type": { "const": "external" } }, "required": ["type"] },
            "then": { "required": ["owner", "note"] }
          }
        ]
      }
    },
    "trace": {
      "type": "array",
      "items": {
        "$ref": "https://specdev.local/schema/core/collections/1#traceRef"
      }
    }
  },
  "required": ["id", "owner", "created_at", "tech_stack", "milestones"]
}
```

# Output Contract
```json
{
  "$schema": "https://specdev.local/schema/14_roadmap.schema.json",
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
  ]
}
```
