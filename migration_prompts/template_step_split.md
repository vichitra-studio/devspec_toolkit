# Migration: Split Step

## Purpose

Decompose a single specification file into multiple separate files. This occurs when the toolkit breaks a monolithic step into more focused, specialized steps.

The goal is **logical separation**: distribute content into appropriate new files while maintaining all relationships.

## Context

- Source Version: {{SOURCE_VERSION}}
- Target Version: {{TARGET_VERSION}}
- Source Step: `{{SOURCE_STEP_ID}}`
- Target Steps: {{TARGET_STEP_IDS}}
- Operation: Split Step

## Source Data

The following file will be split:

### {{SOURCE_STEP_ID}} ({{SOURCE_FILENAME}})

```json
{{SOURCE_CONTENT}}
```

## Target Schemas

{{#each TARGET_SCHEMAS}}
### {{this.step_id}}

```json
{{this.schema}}
```

{{/each}}

## Split Mapping

| Source Field/Section | Target Step | Target Field |
|---------------------|-------------|--------------|
{{#each SPLIT_MAPPINGS}}
| `{{this.source_path}}` | `{{this.target_step}}` | `{{this.target_path}}` |
{{/each}}

## Transformation Rules

### Rule 1: Complete Distribution
- Every field from the source must go to exactly one target file
- No data should be duplicated across target files (unless explicitly shared)
- No data should be dropped

### Rule 2: Maintain References
If split sections reference each other:
- Convert internal references to cross-file references
- Update reference paths to point to new file locations
- Add trace references where appropriate

### Rule 3: Appropriate Grouping
- Related items should stay together in the same target file
- Follow the target schema's structure requirements
- Don't split arrays arbitrarily; keep logical groupings intact

### Rule 4: Individual Validity
- Each target file must be independently valid
- Each must have its own `$schema` reference
- Shared metadata should be appropriately distributed

## Handling Edge Cases

### If a field doesn't clearly belong to any target:
Place it in the most related target file for now. Document in `_migration_notes` with a recommendation for review.

### If splitting breaks references:
Update all affected references in ALL output files.

### If the source has a flat structure being split into nested:
Create appropriate nesting in target files based on schema requirements.

## Self-Audit Gate

For EACH output file, verify:

- [ ] **Complete**: All designated source content is included
- [ ] **No Overlap**: Content appears in only one file (unless shared)
- [ ] **Valid Schema**: File conforms to its target schema
- [ ] **References Valid**: Cross-file references are correct
- [ ] **Valid JSON**: Each file parses as valid JSON

Overall verification:
- [ ] **Lossless**: Combined content of all outputs equals source
- [ ] **Origin Documented**: Each file notes it came from a split

## Output Contract

Return a fenced code block for EACH target file, clearly labeled:

### File 1: `{{TARGET_STEP_1}}.json`

```json
{
  "$schema": "../devspec_toolkit/schema/{{TARGET_STEP_1}}.schema.json",
  // Content for first split file...
  
  "_migration_notes": {
    "split_from": "{{SOURCE_STEP_ID}}"
  }
}
```

### File 2: `{{TARGET_STEP_2}}.json`

```json
{
  "$schema": "../devspec_toolkit/schema/{{TARGET_STEP_2}}.schema.json",
  // Content for second split file...
  
  "_migration_notes": {
    "split_from": "{{SOURCE_STEP_ID}}"
  }
}
```

(Continue for all target files)
