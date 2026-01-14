# Migration: Fix Broken Trace References

## Purpose

Repair broken trace references (`trace_ref` arrays) that point to IDs that no longer exist or have been renamed. This ensures referential integrity across the specification suite.

The goal is **trace integrity**: all cross-references resolve to valid targets, maintaining the traceability graph.

## Context

- Source Version: {{SOURCE_VERSION}}
- Target Version: {{TARGET_VERSION}}
- Step ID: {{STEP_ID}}
- Operation: Validate and Fix Traces

## Source Data

The following file contains broken trace references:

```json
{{SOURCE_CONTENT}}
```

## Broken References

The following trace references don't resolve to valid targets:

| Field Location | Broken Reference | Reason |
|----------------|------------------|--------|
{{#each BROKEN_TRACES}}
| `{{this.location}}` | `{{this.reference}}` | {{this.reason}} |
{{/each}}

## Available Reference Targets

These are the valid IDs available in the specification suite:

{{#each VALID_TARGETS}}
### {{this.step_id}}

IDs available:
{{#each this.ids}}
- `{{this}}`
{{/each}}

{{/each}}

## Transformation Rules

### Rule 1: Find Correct Target
For each broken reference, determine the correct target:
1. Check if the ID was renamed (similar names)
2. Check if the ID was moved to a different file
3. Check if multiple IDs were merged into one

### Rule 2: Update or Remove
For each broken reference:
- **If a valid replacement exists**: Update to the new ID
- **If the target was deleted and no replacement**: Remove the reference
- **If uncertain**: Keep the reference and document in `_migration_notes`

### Rule 3: Maintain Bidirectionality
If trace references should be bidirectional:
- Ensure the target also references the source
- Document any one-way references for manual review

### Rule 4: Preserve Intent
The trace should still represent the same logical relationship:
- FR → Interface implementation
- Test → FR coverage
- Milestone → User Story

## Reference Resolution Hints

{{#each RESOLUTION_HINTS}}
- `{{this.old_id}}` → `{{this.new_id}}` ({{this.reason}})
{{/each}}

## Self-Audit Gate

Before returning your output, you MUST verify each item:

- [ ] **All Resolved**: Every broken reference is addressed
- [ ] **Valid Targets**: All remaining references point to valid IDs
- [ ] **Documented**: Resolution decisions explained in `_migration_notes`
- [ ] **Valid JSON**: Output parses as valid JSON
- [ ] **Schema Compliance**: Output validates against schema

## Output Contract

Return exactly one fenced code block with language `json`.

The JSON must:
1. Be valid, parseable JSON
2. Have all trace references resolved
3. Include documentation of fixes made

```json
{
  // Content with corrected trace references...
  
  "_migration_notes": {
    "trace_fixes": [
      {
        "location": "path.to.trace_refs[0]",
        "old_value": "broken-id",
        "new_value": "corrected-id",
        "reason": "ID was renamed in v{{TARGET_VERSION}}"
      }
    ],
    "removed_references": [
      {
        "location": "path.to.trace_refs[1]",
        "old_value": "deleted-id",
        "reason": "Target was removed with no replacement"
      }
    ],
    "unresolved": [
      {
        "location": "path.to.trace_refs[2]",
        "value": "uncertain-id",
        "reason": "Could not determine correct mapping - needs manual review"
      }
    ]
  }
}
```
