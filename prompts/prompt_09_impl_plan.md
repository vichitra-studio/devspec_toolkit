# Step 09 · Implementation Plan

## Purpose
Translate the validated spec into an executable delivery roadmap that covers technology choices, sequencing, risks, and migration strategy. The implementation plan aligns teams on what will ship when, how dependencies are managed, and which experiments or spikes de-risk the path.

## Tool Execution
Validate the generated JSON:
```bash
./tools/run_specdev.sh validate <path_to_artifact> --repo-root ./devspec_toolkit
```

# Role
You are a senior specification author and validator. Your job is to emit a single JSON artifact for **Step 9 · Implementation Plan** that is machine-checkable and immediately consumable by CI and generators. You do not write examples, tutorials, or comments. You only output the canonical JSON that matches the schema.

# Task
- **Input context:** previously authored spec artifacts (Charter, Capabilities, Glossary, FRs, etc.) available to you in the workspace; organizational constraints; known IDs for cross-references.
- **Objective:** produce a complete, falsifiable artifact for **Step 9 · Implementation Plan**.
- **Output type:** one JSON document conforming to the Embedded Schema.
- **Determinism:** when unspecified, choose the minimal valid value that preserves falsifiability and traceability.
- **Traceability:** if this step has `trace` or `links`, connect to at least one upstream or downstream artifact.


## Seed Order & Mandatory Sources
- Read `spec/common/seed_manifest.json` first; follow `global_seed_order` and `step_requirements["09"]`.
- Ingest required seeds in order before any other context.
- Populate `seed_refs` with the seeds actually used.
- If a required seed is missing or stale, stop and request it before proceeding.

## Context To Ingest
- Charter `spec/00_charter.json` (goals/risks), System Sketch `spec/02_system_sketch.json` (components/dependencies).
- Capabilities `spec/01_capabilities.json` (approved languages/frameworks) - **CRITICAL**: You must strictly adhere to this allowed stack.
- FRs/APIs `spec/04_fr_list.json`/`spec/05_interface_contracts.json` for scope; NFRs `spec/07_nfrs.json` for performance/reliability constraints.
- Use governance/CI expectations from required seeds and project policy docs; do not depend on downstream specs.
- Guides: Shared expectations `devspec_toolkit/docs/prompts/shared_expectations.md`, developer reference.

## Operating Flow: Synthesize → Clarify → Emit
- Build a private Plan Ledger: tech_stack (language/framework/db/tooling + versions), milestones (id/name/date/risks/spikes), migration plan (if replacing), dependencies (teams/vendors/apis). Do not output it.
- **Cross-Check**: Verify your `tech_stack` selection against `spec/01_capabilities.json`. Do not introduce technologies not listed in capabilities unless explicitly justified as a Spike.
- Align milestones with governance/CI cadence from seeds/project policy docs; add spikes for unknowns.
- Self-audit; if risks/spikes/dependencies are vague, ask Gap Questions.
- Rewrite milestones for outcomes and acceptance signals; finalize plan.
- Emit JSON when the plan is actionable.

## Heuristics For Completeness
- Optional→expected: include target_date when sequencing matters; include migration plan for any deprecation/replacement.
- Ambiguity scrub: milestones should map to delivered FRs/APIs and passing CI gates.

## Self-Audit Gate
- If `generation_quality.preflight_passed` cannot be set to `true` with current evidence, stop and ask targeted questions.
- Gating items:
  - Tech choices include versions and rationale; milestones have names and acceptance signals; known risks/spikes captured.
  - `tech_stack` aligns with `01_capabilities.json`.
  - Dependencies listed for external teams/systems; plan aligns with governance/CI expectations.

# Output Rules
1. Return exactly one fenced code block with language `json`. No prose before or after.
2. The JSON must validate against the Embedded Schema below.
3. All IDs must be unique kebab-case strings.
4. Use concrete verbs and measurable outcomes; avoid adjectives that are not testable.
5. Include explicit preconditions, postconditions, and error states where applicable to the schema.
6. Set `owner` to one of: `api`, `ui`, `system`, `ops`, `data`, `product`, `business`, `engineering`.
7. **Traceability**: You MUST include a top-level `trace` array linking to the Charter (`00_charter.json`) or System Sketch (`02_system_sketch.json`).
8. Do not include any fields outside the schema. `additionalProperties` is false everywhere.

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

## Field-by-Field Guidance
- tech_stack: structured object with arrays for `languages`, `frameworks`, `infrastructure`, `tools`. Each item must have `name`, `version`, and `rationale`.
    - `name`: exact library/tool name (e.g., "pydantic", "postgresql").
    - `version`: semantic version constraint (e.g., "^2.0.0").
    - `rationale`: brief reason for selection (e.g., "Standard backend language per capabilities").
- milestones[*].milestone_id/name: kebab-case ID and descriptive name.
- milestones[*].target_date: ISO date for planning; can be tentative.
- milestones[*].status: `pending`, `in_progress`, `done`, `deferred`.
- milestones[*].risks/spikes: concrete bullets (e.g., perf unknowns, vendor limits, schema evolution).
- milestones[*].deliverables: array of trace references linking to FRs/APIs.
- migration_plan: narrative plan for cutover/backfill/rollback.
- dependencies: list of external dependencies and agreements.

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

## Quick Reference
- Required: `tech_stack`.
- Milestones: `milestone_id`, `name`, optional `target_date`, `risks`, `spikes`.

# Clarification Questions
- What tech choices are locked vs flexible? Any org standards to follow?
- What are the major deliverable milestones with dates? What risks or spikes accompany each?
- Are we migrating from an existing system? What is the plan for data, compatibility, and rollback?
- What external dependencies (teams, vendors) could block delivery? How will we mitigate?

# Embedded Schema
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://specdev.local/schema/09_impl_plan.schema.json",
  "title": "09_impl_plan",
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
    "seed_refs": {
      "$ref": "https://specdev.local/schema/core/collections/1#seedRefArray"
    },
    "tech_stack": {
      "type": "object"
    },
    "milestones": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
          "milestone_id": {
            "$ref": "https://specdev.local/schema/core/atoms/1#kebabId"
          },
          "name": {
            "type": "string"
          },
          "target_date": {
            "type": "string",
            "format": "date"
          },
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
          "risks": {
            "$ref": "https://specdev.local/schema/core/collections/1#stringArray"
          },
          "spikes": {
            "$ref": "https://specdev.local/schema/core/collections/1#stringArray"
          },
          "deliverables": {
            "type": "array",
            "items": {
              "$ref": "https://specdev.local/schema/core/collections/1#traceRef"
            }
          }
        },
        "required": [
          "milestone_id",
          "name"
        ]
      }
    },
    "migration_plan": {
      "type": "string"
    },
    "dependencies": {
      "$ref": "https://specdev.local/schema/core/collections/1#/$defs/dependencyList"
    },
    "trace": {
      "type": "array",
      "items": {
        "$ref": "https://specdev.local/schema/core/collections/1#traceRef"
      }
    },
    "generation_quality": {
      "$ref": "https://specdev.local/schema/core/collections/1#/$defs/generationQuality"
    },
    "canonical_refs_used": {
      "$ref": "https://specdev.local/schema/core/collections/1#/$defs/canonicalRefArray"
    },
    "canonical_proposals": {
      "type": "array",
      "items": {
        "$ref": "https://specdev.local/schema/core/collections/1#/$defs/canonicalProposal"
      },
      "default": []
    },
    "canonical_conflicts": {
      "type": "array",
      "items": {
        "$ref": "https://specdev.local/schema/core/collections/1#/$defs/canonicalConflict"
      },
      "default": []
    }
  },
  "required": [
    "id",
    "owner",
    "created_at",
    "seed_refs",
    "tech_stack",
    "trace"
  ]
}
```

# Output Contract
```json
{
  "id": "impl-plan-catalog",
  "owner": "api",
  "created_at": "2025-01-01T00:00:00Z",
  "seed_refs": [
    {"seed_id": "seed-overview"}
  ],
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
