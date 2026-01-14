# Migration: Resolve Structural Conflict

## Purpose

Resolve a structural incompatibility where data cannot be automatically mapped from the old format to the new. This requires human-guided decision making to determine how to transform or preserve the incompatible data.

The goal is **informed resolution**: provide all context needed for a human or AI to make the best decision about handling the conflict.

## Context

- Source Version: {{SOURCE_VERSION}}
- Target Version: {{TARGET_VERSION}}
- Step ID: {{STEP_ID}}
- Conflict Type: {{CONFLICT_TYPE}}
- Operation: Resolve Conflict

## Source Data

The following contains data that cannot be automatically migrated:

```json
{{SOURCE_CONTENT}}
```

## Target Schema

The new schema expects a different structure:

```json
{{TARGET_SCHEMA}}
```

## Conflict Details

### What's Incompatible

{{CONFLICT_DESCRIPTION}}

### Specific Fields Affected

| Source Field | Expected by Target | Issue |
|--------------|-------------------|-------|
{{#each CONFLICT_FIELDS}}
| `{{this.source_path}}` | `{{this.target_expectation}}` | {{this.issue}} |
{{/each}}

### Why Automatic Migration Failed

{{AUTO_MIGRATION_FAILURE_REASON}}

## Resolution Options

Consider these approaches to resolve the conflict:

### Option 1: Restructure Data
Transform the source data to match the target schema, potentially reorganizing or splitting fields.

### Option 2: Archive and Regenerate
Archive the incompatible data in `_migration_notes` and generate fresh content for the target schema based on project context.

### Option 3: Partial Migration
Migrate what's compatible and clearly mark incompatible sections for manual intervention.

### Option 4: Custom Mapping
Define a custom transformation that preserves semantic meaning even if not structurally obvious.

## Transformation Guidelines

### Preserve Semantic Meaning
- The output should convey the same information as the input
- If exact representation isn't possible, preserve the intent

### Document All Decisions
- Explain why you chose a particular resolution
- Note any data that couldn't be migrated
- Mark areas needing human review

### Maintain Validity
- Output must be valid JSON
- Output should conform to target schema
- Use `_migration_notes` for data that doesn't fit

## Self-Audit Gate

Before returning your output, you MUST verify each item:

- [ ] **Resolved**: All conflicting fields have been addressed
- [ ] **Valid JSON**: Output parses as valid JSON
- [ ] **Schema Compliance**: Output validates against target schema
- [ ] **Documented**: Resolution decisions are explained in `_migration_notes`
- [ ] **Lossless**: Incompatible data is archived, not deleted
- [ ] **Reviewable**: `_needs_review` flags highlight uncertain resolutions

## Output Contract

Return exactly one fenced code block with language `json`.

The JSON must:
1. Be valid, parseable JSON
2. Conform to the target schema
3. Include comprehensive `_migration_notes` explaining resolutions

```json
{
  "$schema": "{{SCHEMA_REF}}",
  // Resolved content...
  
  "_migration_notes": {
    "conflicts_resolved": [
      {
        "original_field": "{{CONFLICT_FIELD}}",
        "resolution": "Description of how it was resolved",
        "original_value": "archived value if complex"
      }
    ],
    "human_review_needed": [
      "Description of any items needing manual review"
    ]
  },
  "_needs_review": true
}
```
