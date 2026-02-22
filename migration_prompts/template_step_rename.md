# Migration: Step Rename

## Purpose

Rename a specification step file following a step renumbering in the toolkit. This typically occurs when new steps are inserted, causing existing steps to shift to new numbers.

This is primarily a file rename operation, but also requires updating any internal references.

## Context

- Source Version: {{SOURCE_VERSION}}
- Target Version: {{TARGET_VERSION}}
- Old Step ID: `{{OLD_STEP_ID}}`
- New Step ID: `{{NEW_STEP_ID}}`
- Operation: Step File Rename

## Source Data

The following is your current specification file that needs renaming:

```json
{{SOURCE_CONTENT}}
```

## Target Schema

The schema for the renamed step:

```json
{{TARGET_SCHEMA}}
```

## Rename Details

| Property | Old | New |
|----------|-----|-----|
| Step ID | `{{OLD_STEP_ID}}` | `{{NEW_STEP_ID}}` |
| Filename | `{{OLD_STEP_ID}}.json` | `{{NEW_STEP_ID}}.json` |
| Schema Ref | `{{OLD_STEP_ID}}.schema.json` | `{{NEW_STEP_ID}}.schema.json` |

## Transformation Rules

### Rule 1: Update $schema Reference
The `$schema` field must point to the new schema filename:
```json
"$schema": "../devspec_toolkit/schema/{{NEW_STEP_ID}}.schema.json"
```

### Rule 2: Preserve All Content
- ALL other fields remain exactly the same
- Do not modify IDs, descriptions, or references
- The step's content is unchanged, only its position/number is different

### Rule 3: No Internal ID Changes
The step renumber is about file organization, not content:
- Item IDs within the file stay the same
- Trace references from other files to this step's items remain valid
- (Other files may need separate updates to reference the new filename)

## Handling Edge Cases

### If the source file references its own step number:
Update any self-references to use the new step number.

### If the $schema path uses a different format:
Preserve the path structure, only update the filename portion.

### If the file contains step-number-prefixed IDs:
Generally, do NOT rename IDs. The ID naming convention is project-specific. Document any ID patterns in `_migration_notes` for manual review.

## Self-Audit Gate

Before returning your output, you MUST verify each item:

- [ ] **Schema Updated**: `$schema` points to new schema file
- [ ] **Content Preserved**: All other content is identical to source
- [ ] **Valid JSON**: Output parses as valid JSON
- [ ] **No ID Changes**: Item IDs within the file are unchanged

## Output Contract

Write the final JSON artifact directly to disk at the step path under `spec/` (or runner-provided path).

The JSON must:
1. Be valid, parseable JSON
2. Have updated `$schema` reference
3. Be otherwise identical to the source file

```json
{
  "$schema": "../devspec_toolkit/schema/{{NEW_STEP_ID}}.schema.json",
  // All original content preserved...
}
```
