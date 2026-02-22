# Migration: Add Required Field

## Purpose

Infer and populate a new required field that was added to a specification schema in a newer version of the DevSpec Toolkit. This migration preserves all existing data while adding the new field with a value derived from context.

The goal is **zero data loss**: keep all existing content and add ONLY the new required field.

## Context

- Source Version: {{SOURCE_VERSION}}
- Target Version: {{TARGET_VERSION}}
- Step ID: {{STEP_ID}}
- Field Path: `{{FIELD_PATH}}`
- Operation: Add Required Field

## Source Data

The following is your current specification file. ALL of this content must be preserved in the output. You are ONLY adding the new field.

```json
{{SOURCE_CONTENT}}
```

## Target Schema

The output must conform to this updated schema:

```json
{{TARGET_SCHEMA}}
```

## New Field Requirements

### Field: `{{FIELD_PATH}}`

- **Type**: `{{FIELD_TYPE}}`
- **Description**: {{FIELD_DESCRIPTION}}
- **Constraints**: {{FIELD_CONSTRAINTS}}
- **Required**: Yes

### Context for Inference

Use these additional spec files to infer an appropriate value:

{{#each CONTEXT_SOURCES}}
### {{this.filename}}

```json
{{this.content}}
```

{{/each}}

## Transformation Rules

### Rule 1: Preserve All Existing Data
- Copy ALL existing fields from source data exactly as-is
- Do not modify, rename, or remove any existing content
- Only ADD the new required field

### Rule 2: Infer Value from Context
- Analyze existing data and context files to determine appropriate value
- For array fields, create entries that reference existing IDs
- For string fields, derive from descriptions, names, or patterns in context

### Rule 3: Type Coercion
- Ensure the value matches the required type exactly
- If the field is an array, provide at least one element (unless empty is valid)
- If the field is an object, provide all nested required fields

### Rule 4: Reference Integrity
- If the field references other IDs (e.g., `trace_ref`), use only valid IDs from context
- Verify all cross-references exist in the referenced spec files

## Handling Edge Cases

### If the field value cannot be inferred:
1. Use a placeholder value: `"MIGRATION-REQUIRED: [description of what's needed]"`
2. Add `"_needs_review": true` at the object level containing this field
3. Document in `_migration_notes` why inference failed

### If the field is nested within an array:
Add the field to EACH item in the array where it's required.

### If existing data seems inconsistent with the new field:
Preserve the existing data as-is. Document the inconsistency in `_migration_notes`.

## Self-Audit Gate

Before returning your output, you MUST verify each item:

- [ ] **Lossless**: ALL existing fields are preserved exactly
- [ ] **Field Added**: The new required field is present at `{{FIELD_PATH}}`
- [ ] **Valid Value**: The new field's value matches the required type
- [ ] **Valid JSON**: Output parses as valid JSON
- [ ] **Schema Compliance**: Output validates against target schema
- [ ] **No Hallucination**: Values derived only from provided context

## Output Contract

Write the final JSON artifact directly to disk at the step path under `spec/` (or runner-provided path).

The JSON must:
1. Be valid, parseable JSON
2. Contain ALL original data plus the new field
3. Conform to the target schema
4. Include `_migration_notes` if any inference was uncertain

```json
{
  // Complete output with new field added
}
```
