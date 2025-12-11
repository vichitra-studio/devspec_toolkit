# Extension Architecture & Schemas

This guide explains how the DevSpec Toolkit handles domain-specific specifications via the **Extension Generator (Step 13)**.

## Purpose
The toolkit's Core specs (00-12) cover the foundational software delivery lifecycle. However, specific domains (e.g., AI/ML, Embedded, Data Pipelines) require specialized attributes. The **Extension Architecture** allows strict extensions to be dynamically discovered and defined without cluttering the core.

## The Workflow

1.  **Core Definition**: Steps 00-12 are completed first.
2.  **Step 13 (Extension Generator)**: The agent analyzes the system sketch (02) and requirements (04).
3.  **Manifest Generation**: The agent produces `spec/13_extension_manifest.json`, identifying necessary extensions.
4.  **Extension Creation**: The distinct extension artifacts (e.g., `spec/13a_database.json`) are created to elaborate on those domains.
5.  **Step 14 (Roadmap)**: The Roadmap ingests both Core specs and Extension specs to build the implementation plan.

## Naming Convention

All extensions follow a strict naming pattern to ensure correct ordering and ingestion by the Roadmap.

- **Manifest**: `13_extension_manifest.json`
- **Extension Artifacts**: `13[a-z]_<topic>.json`
    - Example: `13a_database.json`
    - Example: `13b_security.json`
    - Example: `13c_ml_models.json`
- **Extension Schemas**: `13[a-z]_<topic>.schema.json` (if a custom schema is defined)

## The Extension Manifest

The manifest (`13_extension_manifest.json`) dictates which extensions exist. It validates against `schema/13_extension_generator.schema.json`.

```json
{
  "$schema": "https://specdev.local/schema/13_extension_generator.schema.json",
  "id": "13-extension-manifest",
  "extensions": [
    {
      "extension_id": "13a-database",
      "title": "Database Schema Specification",
      "file_name": "13a_database_schema.json",
      "area_of_concern": "Data Persistence",
      "justification": "System Sketch defines complex relational + vector data needs.",
      "required_schema_sections": ["tables", "indexes", "relationships", "vector_config"]
    }
  ]
}
```

## Authoring Extension Schemas

If you need to enforce strict structure for an extension (e.g. `13c_ml_models.json`), create a matching schema:

1.  **Create Schema**: `schema/13c_ml_models.schema.json`
2.  **Reference Atoms**: Use standard atoms from `schema/core/atoms.schema.json`.
3.  **Link in Artifact**: Ensure `spec/13c_ml_models.json` points to this schema in its `$schema` field.

### Example Schema
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://specdev.local/schema/13c_ml_models.schema.json",
  "title": "13c_ml_models",
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "id": { "$ref": "https://specdev.local/schema/core/atoms/1#kebabId" },
    "owner": { "$ref": "https://specdev.local/schema/core/atoms/1#owner" },
    "created_at": { "$ref": "https://specdev.local/schema/core/atoms/1#timestamp" },
    "model_type": {
      "type": "string",
      "enum": ["regression", "classification", "llm"]
    }
  },
  "required": ["id", "owner", "created_at", "model_type"]
}
```
