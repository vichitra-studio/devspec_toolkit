# Migration: Merge Steps

## Purpose

Combine multiple specification files into a single unified file. This occurs when the toolkit consolidates related steps into a more cohesive structure.

The goal is **complete integration**: all data from all source files is preserved in a logically organized unified structure.

## Context

- Source Version: {{SOURCE_VERSION}}
- Target Version: {{TARGET_VERSION}}
- Source Steps: {{SOURCE_STEP_IDS}}
- Target Step: `{{TARGET_STEP_ID}}`
- Operation: Merge Steps

## Source Data

The following files will be merged:

{{#each SOURCE_FILES}}
### {{this.step_id}} ({{this.filename}})

```json
{{this.content}}
```

{{/each}}

## Target Schema

The merged output must conform to this unified schema:

```json
{{TARGET_SCHEMA}}
```

## Merge Mapping

| Source Step | Source Fields | Target Location |
|-------------|---------------|-----------------|
{{#each MERGE_MAPPINGS}}
| `{{this.source_step}}` | `{{this.source_fields}}` | `{{this.target_path}}` |
{{/each}}

## Transformation Rules

### Rule 1: Preserve All Data
- Every field from every source file must appear in the output
- No data should be silently dropped
- If data doesn't fit the target schema, archive in `_migration_notes`

### Rule 2: Resolve ID Conflicts
If the same ID appears in multiple source files:
1. Prefer the more specific/detailed version
2. Merge complementary data from both
3. Document the resolution in `_migration_notes`

### Rule 3: Maintain References
- Update any internal references to use the merged file's structure
- Cross-file references become internal references
- Trace integrity must be maintained

### Rule 4: Logical Organization
- Group related items together
- Maintain a sensible order (e.g., by original step order)
- Use arrays to collect items from different sources

### Rule 5: Unified Metadata
- Create a single `$schema` reference for the merged file
- Combine or summarize descriptions
- Merge any notes or comments

## Handling Edge Cases

### If source files have conflicting structures:
Create a structure that accommodates both. Use optional fields where needed.

### If some source files don't exist:
Proceed with available files. Document missing sources in `_migration_notes`.

### If the merge creates a very large file:
This is expected. Ensure valid JSON and document the merged sources in `_migration_notes`.

## Self-Audit Gate

Before returning your output, you MUST verify each item:

- [ ] **All Sources Included**: Data from ALL source files is present
- [ ] **No Data Loss**: Every field from every source appears somewhere
- [ ] **Valid Structure**: Output matches target schema
- [ ] **ID Uniqueness**: No duplicate IDs in the merged file
- [ ] **References Valid**: All internal references resolve correctly
- [ ] **Valid JSON**: Output parses as valid JSON
- [ ] **Origin Documented**: `_migration_notes` lists merged sources

## Output Contract

Return exactly one fenced code block with language `json`.

The JSON must:
1. Be valid, parseable JSON
2. Contain ALL data from ALL source files
3. Conform to the target schema
4. Include `_migration_notes.merged_from` listing source files

```json
{
  "$schema": "../devspec_toolkit/schema/{{TARGET_STEP_ID}}.schema.json",
  // Merged content from all sources...
  
  "_migration_notes": {
    "merged_from": [
      "{{SOURCE_STEP_IDS}}"
    ]
  }
}
```
