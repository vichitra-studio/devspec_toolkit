# Migration: Rename Field

## Purpose

Rename a field to its new name as specified in the updated schema. This is a mechanical operation that preserves the value while updating the field key.

The goal is **exact value preservation**: only the field name changes, not its content.

## Context

- Source Version: {{SOURCE_VERSION}}
- Target Version: {{TARGET_VERSION}}
- Step ID: {{STEP_ID}}
- Old Field Path: `{{OLD_FIELD_PATH}}`
- New Field Path: `{{NEW_FIELD_PATH}}`
- Operation: Rename Field

## Source Data

The following is your current specification file with the old field name:

```json
{{SOURCE_CONTENT}}
```

## Target Schema

The updated schema uses the new field name:

```json
{{TARGET_SCHEMA}}
```

## Rename Details

| Property | Value |
|----------|-------|
| Old Name | `{{OLD_FIELD_PATH}}` |
| New Name | `{{NEW_FIELD_PATH}}` |
| Value Type | `{{FIELD_TYPE}}` |
| Reason | {{RENAME_REASON}} |

## Transformation Rules

### Rule 1: Direct Rename
- Change ONLY the field key, not the value
- The value must be copied exactly as-is
- Preserve any nested structure within the value

### Rule 2: Handle All Instances
If the field appears in multiple places (e.g., in array items):
- Rename ALL instances
- Maintain the same order

### Rule 3: Update Internal References
If any other fields reference the old field name:
- Update those references to use the new name
- This applies to `trace_ref` and similar reference arrays

### Rule 4: Preserve Field Order
Keep the renamed field in approximately the same position within the object for readability (though JSON doesn't require order).

## Handling Edge Cases

### If the old field doesn't exist in source:
This is not an error for a rename migration. Simply ensure the output is valid without this field.

### If both old and new field names exist:
1. Prefer the old field's value (as it's the source of truth)
2. Document the conflict in `_migration_notes`
3. Archive the new field's value if different

### If the field is nested deeply:
Apply the rename at the correct nesting level. For paths like `milestones[].old_name`, rename within each array item.

## Self-Audit Gate

Before returning your output, you MUST verify each item:

- [ ] **Renamed**: Old field name no longer appears
- [ ] **Value Preserved**: New field has exactly the same value
- [ ] **All Instances**: Every occurrence of the old name is renamed
- [ ] **References Updated**: Any internal references use the new name
- [ ] **Valid JSON**: Output parses as valid JSON
- [ ] **Schema Compliance**: Output validates against target schema

## Output Contract

Write the final JSON artifact directly to disk at the step path under `spec/` (or runner-provided path).

The JSON must:
1. Be valid, parseable JSON
2. Use the new field name with the original value
3. Conform to the target schema
4. NOT contain the old field name anywhere

```json
{
  // Output with renamed field
}
```
