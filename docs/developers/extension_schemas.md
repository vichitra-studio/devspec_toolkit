# Extension Schemas

This guide explains how to extend the DevSpec Toolkit by creating custom schemas for domain-specific specifications (Phase 2).

## Purpose
The toolkit's Core specs (00-12) cover the foundational software delivery lifecycle. However, specific domains (e.g., AI/ML, Embedded, Data Pipelines) require specialized attributes. Extensions allow you to define these needs formally while maintaining compatibility with the roadmap and generator tools.

## The Extension Pattern
Extensions are simply additional JSON Schema files that live alongside your core specs.

### Naming Convention
- **Schema File**: `NN_<topic>.schema.json` (where NN is a number > 17, or a distinct sequence like 90+)
- **Artifact File**: `NN_<topic>.json`
- **ID Format**: `<topic>-<descriptor>` (kebab-case)

### Structure
All extension schemas MUST:
1. Reference `draft/2020-12`.
2. Reference Core Atoms for standard fields (`id`, `owner`, `created_at`).
3. Disallow `additionalProperties` (strict validation).

### Example: `90_ml_model.schema.json`
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://specdev.local/schema/90_ml_model.schema.json",
  "title": "90_ml_model",
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "id": { "$ref": "https://specdev.local/schema/core/atoms/1#kebabId" },
    "owner": { "$ref": "https://specdev.local/schema/core/atoms/1#owner" },
    "created_at": { "$ref": "https://specdev.local/schema/core/atoms/1#timestamp" },
    "model_type": {
      "type": "string",
      "enum": ["regression", "classification", "llm"]
    },
    "training_data_ref": {
      "$ref": "https://specdev.local/schema/core/collections/1#traceRef"
    }
  },
  "required": ["id", "owner", "created_at", "model_type"]
}
```

## Integrating Extensions
1. **Define Schema**: Save your schema in `schema/`.
2. **Author Spec**: Create the corresponding spec JSON in `spec/` (e.g., `spec/90_churn_model.json`).
3. **Validate**: Run `python -m specdev_tools.cli validate spec/90_churn_model.json`.
4. **Roadmap**: The Roadmap Prompt (Step 13) is designed to scan `spec/` for ALL valid JSON artifacts, so your extension will automatically be picked up and planned.

## Best Practices
- **Reuse Atoms**: Do not redefine `id` or `timestamps`; use the Core Atoms to ensure tools can parse your metadata.
- **Trace Back**: Use `traceRef` to link your extension back to a Core Requirement (Step 04) or Interface (Step 05).
- **Keep it Strict**: Always set `additionalProperties: false` to prevent "drift by typo".
