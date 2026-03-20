# Extension Architecture & Schemas

This guide explains how the DevSpec Toolkit handles domain-specific specifications via the **Extension Generator (Step 13)**.

## Purpose
The toolkit's Core specs (00-12) cover the foundational software delivery lifecycle. However, specific domains (e.g., AI/ML, Embedded, Data Pipelines) require specialized attributes. The **Extension Architecture** allows strict extensions to be dynamically discovered and defined without cluttering the core.

## The Workflow

1.  **Core Definition**: Steps 00-12 are completed first.
2.  **Step 13 (Extension Generator)**: The agent analyzes the system sketch (02) and requirements (04).
3.  **Manifest Generation**: The agent produces `spec/13_extension_manifest.json`, identifying necessary extensions.
4.  **Extension Creation**: The distinct extension artifacts (e.g., `spec/ext_01_database.json`) are created to elaborate on those domains.
5.  **Step 14 (Roadmap)**: The Roadmap ingests both Core specs and Extension specs to build the implementation plan.

## Naming Convention

All extensions follow a strict naming pattern to ensure correct ordering and ingestion by the Roadmap.

- **Manifest**: `13_extension_manifest.json`
- **Extension Artifacts**: `ext_[0-9]{2}_<topic>.json`
    - Example: `ext_01_database.json`
    - Example: `ext_02_security.json`
    - Example: `ext_03_ml_models.json`
- **Extension Schemas**: `ext_03_ml_models.schema.json` (if a custom schema is defined)

## The Extension Manifest

The manifest (`13_extension_manifest.json`) dictates which extensions exist. It validates against `schema/13_extension_generator.schema.json`.

```json
{
  "$schema": "vc:13-extension-generator",
  "id": "13-extension-manifest",
  "extensions": [
    {
      "extension_id": "ext-01-database",
      "title": "Database Schema Specification",
      "file_name": "ext_01_database_schema.json",
      "area_of_concern": "Data Persistence",
      "justification": "System Sketch defines complex relational + vector data needs.",
      "required_schema_sections": ["tables", "indexes", "relationships", "vector_config"]
    }
  ]
}
```

## Authoring Extension Schemas

If you need to enforce strict structure for an extension (e.g. `ext_03_ml_models.json`), create a matching schema:

1.  **Create Schema**: `schema/ext_03_ml_models.schema.json`
2.  **Reference Atoms**: Use standard atoms from `schema/core/atoms.schema.json`.
3.  **Link in Artifact**: Ensure `spec/ext_03_ml_models.json` points to this schema in its `$schema` field.

### Example Schema
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "vc:ext-03-ml-models",
  "title": "ext_03_ml_models",
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "id": { "$ref": "vc:core:atoms#kebabId" },
    "owner": { "$ref": "vc:core:atoms#owner" },
    "created_at": { "$ref": "vc:core:atoms#timestamp" },
    "model_type": {
      "type": "string",
      "enum": ["regression", "classification", "llm"]
    }
  },
  "required": ["id", "owner", "created_at", "model_type"]
}
```
