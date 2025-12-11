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
- Extension Specs: All `spec/13[a-z]_*.json` files defined in the manifest.
- Charter: `spec/00_charter.json` for strategic goals.
- Completeness: `spec/13a_completeness_assessment.json`.
- Guide: `template/14_roadmap.guide.md`.

## Operating Flow: Synthesize → Clarify → Emit
- **Synthesize**: Scan all `spec/` artifacts. Identify every distinct feature, capability, and schema defined.
- **Clarify**: If there are orphaned specs (extensions without clear dependencies) or circular dependencies between extensions and core, ask Gap Questions.
- **Emit**: Generate a roadmap that groups these items into logical milestones using the JIT (Just-In-Time) philosophy—plan high level now, detail later.

## Heuristics For Completeness
- **Unified View**: The roadmap must include items from BOTH the Core specs and any found Extensions.
- **Ordering**: Core dependencies (e.g., Auth, Base API) must precede dependent Extensions.

## Self-Audit Gate
- Confirm that existing specs cover enough scope to justify a roadmap.
- Confirm all "High" priority items from `13a_completeness_assessment` are accounted for (either fixed or scheduled).

# Output Rules
1. Return exactly one fenced code block with language `json`.
2. The JSON must validate against the Embedded Schema (reuse 09_impl_plan schema or a dedicated roadmap schema if available—defaulting to 09 format for compatibility).
3. All milestones must have `target_date` and `deliverables` list.

# Embedded Schema
(Note: This step reuses `09_impl_plan.schema.json` because the Roadmap is structurally identical to the Implementation Plan. There is no separate `14_roadmap.schema.json`.)
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://specdev.local/schema/09_impl_plan.schema.json",
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
        "languages": { "$ref": "https://specdev.local/schema/core/collections/1#stringArray" },
        "frameworks": { "$ref": "https://specdev.local/schema/core/collections/1#stringArray" },
        "infrastructure": { "$ref": "https://specdev.local/schema/core/collections/1#stringArray" },
        "tools": { "$ref": "https://specdev.local/schema/core/collections/1#stringArray" }
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
          "risks": { "$ref": "https://specdev.local/schema/core/collections/1#stringArray" },
          "spikes": { "$ref": "https://specdev.local/schema/core/collections/1#stringArray" }
        },
        "required": ["milestone_id", "name"]
      }
    },
    "migration_plan": { "type": "string" },
    "dependencies": { "$ref": "https://specdev.local/schema/core/collections/1#stringArray" }
  },
  "required": ["id", "owner", "created_at", "tech_stack"]
}
```

# Output Contract
```json
{
  "id": "roadmap-v1",
  "owner": "system",
  "created_at": "2025-01-01T00:00:00Z",
  "tech_stack": {
    "languages": ["python"],
    "frameworks": ["fastapi"],
    "infrastructure": ["docker"],
    "tools": ["poetry"]
  },
  "milestones": [
    {
      "milestone_id": "m1-core-foundation",
      "name": "Core Foundation",
      "target_date": "2025-02-01",
      "risks": [],
      "spikes": []
    }
  ]
}
```
