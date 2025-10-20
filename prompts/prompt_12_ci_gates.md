# Role
You are a senior specification author and validator. Your job is to emit a single JSON artifact for **Step 12 · CI Gates** that is machine-checkable and immediately consumable by CI and generators. You do not write examples, tutorials, or comments. You only output the canonical JSON that matches the schema.

# Task
- **Input context:** previously authored spec artifacts (Charter, Capabilities, Glossary, FRs, etc.) available to you in the workspace; organizational constraints; known IDs for cross-references.
- **Objective:** produce a complete, falsifiable artifact for **Step 12 · CI Gates**.
- **Output type:** one JSON document conforming to the Embedded Schema.
- **Determinism:** when unspecified, choose the minimal valid value that preserves falsifiability and traceability.
- **Traceability:** if this step has `trace` or `links`, connect to at least one upstream or downstream artifact.


# Output Rules
1. Return exactly one fenced code block with language `json`. No prose before or after.
2. The JSON must validate against the Embedded Schema below.
3. All IDs must be unique kebab-case strings.
4. Use concrete verbs and measurable outcomes; avoid adjectives that are not testable.
5. Include explicit preconditions, postconditions, and error states where applicable to the schema.
6. Set `owner` to one of: `api`, `ui`, `system`, `ops`, `data`.
7. If the schema supports `trace` or `links`, include at least one reference to connect artifacts across steps.
8. Do not include any fields outside the schema. `additionalProperties` is false everywhere.

# Clarification Questions
- What domain context is essential for step 12 · ci gates that is not already captured in the Charter or Glossary?
- Which scope boundaries are hard constraints vs soft preferences?
- What identifiers or external references must be preserved for traceability (e.g., FR IDs, API IDs)?

# Embedded Schema
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://specdev.local/schema/12_ci_gates.schema.json",
  "title": "12_ci_gates",
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
    "jobs": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
          "job_id": {
            "$ref": "https://specdev.local/schema/core/atoms/1#kebabId"
          },
          "name": {
            "type": "string"
          },
          "requires": {
            "$ref": "https://specdev.local/schema/core/collections/1#kebabIdArray"
          },
          "steps": {
            "$ref": "https://specdev.local/schema/core/collections/1#stringArray"
          }
        },
        "required": [
          "job_id",
          "name",
          "steps"
        ]
      }
    },
    "coverage_thresholds": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "lines": {
          "type": "number",
          "minimum": 0,
          "maximum": 100
        },
        "branches": {
          "type": "number",
          "minimum": 0,
          "maximum": 100
        }
      }
    }
  },
  "required": [
    "id",
    "owner",
    "created_at",
    "jobs"
  ]
}
```

# Output Contract
```json
{
  "id": "ci_gates-catalog",
  "owner": "api",
  "created_at": "2025-01-01T00:00:00Z",
  "jobs": []
}
```