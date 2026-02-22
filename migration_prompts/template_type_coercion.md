# Migration: Type Coercion

## Purpose

Convert a field's value from its old type to a new type as required by the updated schema. This migration handles type changes while preserving the semantic meaning of the data.

The goal is **semantic preservation**: the meaning of the data is maintained even as its structure changes.

## Context

- Source Version: {{SOURCE_VERSION}}
- Target Version: {{TARGET_VERSION}}
- Step ID: {{STEP_ID}}
- Field Path: `{{FIELD_PATH}}`
- Old Type: `{{OLD_TYPE}}`
- New Type: `{{NEW_TYPE}}`
- Operation: Type Coercion

## Source Data

The following is your current specification with the old type:

```json
{{SOURCE_CONTENT}}
```

## Target Schema

The updated schema requires a different type:

```json
{{TARGET_SCHEMA}}
```

## Type Change Details

| Property | Old | New |
|----------|-----|-----|
| Field | `{{FIELD_PATH}}` | `{{FIELD_PATH}}` |
| Type | `{{OLD_TYPE}}` | `{{NEW_TYPE}}` |
| Reason | {{CHANGE_REASON}} |

## Transformation Rules

### Rule 1: String → Array
If converting a single string to an array:
- Wrap the string in an array: `"value"` → `["value"]`
- If the string contains comma-separated values, split them: `"a, b, c"` → `["a", "b", "c"]`

### Rule 2: Array → String
If converting an array to a string:
- Join with appropriate delimiter: `["a", "b"]` → `"a, b"`
- If only one element, unwrap: `["value"]` → `"value"`

### Rule 3: String → Object
If converting a string to an object:
- Use the string as the primary field (usually `name` or `id`)
- Add other required fields with inferred or default values

### Rule 4: Object → String
If converting an object to a string:
- Extract the primary identifier field
- Archive the full object in `_migration_notes` if data would be lost

### Rule 5: Primitive → Complex
When converting simple types to complex:
- Preserve the original value in the most appropriate field
- Fill other required fields with sensible defaults
- Document any inferences in `_migration_notes`

### Rule 6: Numeric Coercion
- String to number: Parse the string, preserve precision
- Number to string: Convert directly

## Handling Edge Cases

### If the value cannot be coerced:
1. Create a valid value of the target type
2. Archive the original value in `_migration_notes.coercion_failures`
3. Add `"_needs_review": true` to the containing object

### If the field appears in multiple places:
Apply the same coercion logic to ALL instances consistently.

### If nested types are affected:
Recursively apply type coercion to nested fields as specified.

## Self-Audit Gate

Before returning your output, you MUST verify each item:

- [ ] **Type Changed**: Field now has the correct new type
- [ ] **Semantic Preserved**: The meaning of the data is maintained
- [ ] **All Instances**: Every occurrence is coerced
- [ ] **Valid JSON**: Output parses as valid JSON
- [ ] **Schema Compliance**: Output validates against target schema
- [ ] **Documented**: Any lossy coercions noted in `_migration_notes`

## Output Contract

Write the final JSON artifact directly to disk at the step path under `spec/` (or runner-provided path).

The JSON must:
1. Be valid, parseable JSON
2. Have the field with the new type
3. Conform to the target schema
4. Include `_migration_notes` if any data transformation was lossy

```json
{
  // Output with type-coerced field
}
```
