# Migration: Handle Deprecated Field Removal

## Purpose

Safely handle the removal of a field that has been deprecated in the newer schema version. This migration ensures no data is lost by archiving the deprecated field's content to `_migration_notes`.

The goal is **zero data loss**: the deprecated field's value is preserved in migration notes for reference, and the output conforms to the new schema.

## Context

- Source Version: {{SOURCE_VERSION}}
- Target Version: {{TARGET_VERSION}}
- Step ID: {{STEP_ID}}
- Deprecated Field Path: `{{FIELD_PATH}}`
- Operation: Remove Deprecated Field

## Source Data

The following is your current specification file containing the deprecated field:

```json
{{SOURCE_CONTENT}}
```

## Target Schema

The new schema no longer includes the deprecated field:

```json
{{TARGET_SCHEMA}}
```

## Deprecated Field Details

### Field: `{{FIELD_PATH}}`

- **Old Type**: `{{FIELD_TYPE}}`
- **Reason for Removal**: {{REMOVAL_REASON}}
- **Replacement Field**: {{REPLACEMENT_FIELD}} (if applicable)

## Transformation Rules

### Rule 1: Archive, Don't Delete
- Move the deprecated field's value to `_migration_notes.archived_fields`
- Include the original field path as the key
- Preserve the exact value for reference

### Rule 2: Migrate to Replacement (if applicable)
If a replacement field exists:
- Map the old value to the new field location
- Apply any necessary value transformations
- Document the mapping in `_migration_notes`

### Rule 3: Preserve All Other Data
- Copy ALL other fields from source data exactly as-is
- Do not modify any field except the deprecated one
- Maintain all existing structure and references

## Handling Edge Cases

### If the deprecated field contains complex nested data:
Archive the entire nested structure as-is in `_migration_notes.archived_fields`.

### If multiple instances exist (in an array):
Archive each instance with an index suffix: `fieldname_0`, `fieldname_1`, etc.

### If the field value is referenced elsewhere:
1. Check if any other fields reference this deprecated field
2. If so, those references should also be updated or noted
3. Document reference chains in `_migration_notes`

## Self-Audit Gate

Before returning your output, you MUST verify each item:

- [ ] **Archived**: Deprecated field value saved in `_migration_notes.archived_fields`
- [ ] **Removed**: Deprecated field no longer appears at original location
- [ ] **Lossless**: All other fields preserved exactly
- [ ] **Valid JSON**: Output parses as valid JSON
- [ ] **Schema Compliance**: Output validates against target schema
- [ ] **Documented**: `_migration_notes` explains what was removed and why

## Output Contract

Write the final JSON artifact directly to disk at the step path under `spec/` (or runner-provided path).

The JSON must:
1. Be valid, parseable JSON
2. NOT contain the deprecated field (except in `_migration_notes`)
3. Conform to the target schema
4. Include `_migration_notes.archived_fields` with the preserved value

```json
{
  // All valid fields from original...
  
  "_migration_notes": {
    "archived_fields": {
      "{{FIELD_PATH}}": "original value here"
    },
    "removal_reason": "{{REMOVAL_REASON}}"
  }
}
```
