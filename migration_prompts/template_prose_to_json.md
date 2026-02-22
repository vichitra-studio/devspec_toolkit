# Migration: Convert Prose Document to Structured JSON

## Purpose

Convert a prose/markdown specification document into a structured JSON format that conforms to the DevSpec Toolkit schema. This operation is required when the toolkit evolves from prose-based specs to machine-readable JSON specs.

The goal is **zero information loss**: every piece of information in the source document must appear somewhere in the output JSON.

## Context

- Source Version: {{SOURCE_VERSION}}
- Target Version: {{TARGET_VERSION}}
- Operation: Paradigm Shift (Prose → JSON)
- Source File: `{{SOURCE_FILE}}`
- Target File: `{{TARGET_FILE}}`

## Source Document

The following is the complete content of the source prose document. Read it carefully and ensure ALL information is preserved in the output.

```markdown
{{SOURCE_CONTENT}}
```

## Target Schema

The output must conform to this JSON Schema. Pay careful attention to required fields, field types, and constraints.

```json
{{TARGET_SCHEMA}}
```

## Required Fields

The following fields are REQUIRED in the output:

{{#each REQUIRED_FIELDS}}
### `{{this.path}}`

- **Type**: `{{this.type}}`
- **Description**: {{this.description}}
- **Constraints**: {{this.constraints}}
- **Extraction Hint**: {{this.extraction_hint}}

{{/each}}

## Transformation Rules

### Rule 1: Document Structure → Object Hierarchy

Map document structure to JSON objects:
- Document title → Root `id` and `name` fields
- Top-level sections (H1, H2) → Top-level object properties
- Nested sections → Nested objects or array items
- Bullet lists → Array items

**Example**:
```markdown
## Phase 1: Foundation
- Set up database
- Configure auth
```

Becomes:
```json
{
  "milestones": [{
    "name": "Foundation",
    "tasks": ["Set up database", "Configure auth"]
  }]
}
```

### Rule 2: Status Annotations → Enum Values

Convert status text to schema enum values:
- "Done", "Complete", "Finished", "✓" → `"done"`
- "In Progress", "WIP", "Started" → `"in_progress"`
- "TODO", "Pending", "Planned" → `"pending"`
- "Blocked", "On Hold" → `"blocked"`

**Example**:
```markdown
- [x] Set up database (Complete)
```

Becomes:
```json
{"task": "Set up database", "status": "done"}
```

### Rule 3: Dates and Times → ISO 8601

Convert any date references to ISO 8601 format:
- "January 14, 2026" → `"2026-01-14"`
- "Jan 14" (no year) → `"2026-01-14"` (use current year)
- "Q1 2026" → `"2026-03-31"` (end of quarter)

### Rule 4: References and Links → Trace Fields

Convert cross-references to `trace_ref` arrays:
- "See FR-001" → `"trace_refs": ["fr-001"]`
- "Depends on Auth module" → `"dependencies": ["auth-module"]`

### Rule 5: Preserve Rich Context

If the source contains detailed notes, explanations, or context that doesn't map to a specific schema field:
- Keep brief notes in the nearest `notes` or `description` field
- Move lengthy context to `_migration_notes` object

## Handling Edge Cases

### If a section has no clear schema mapping:
Add to `_migration_notes` object with section heading as key:
```json
{
  "_migration_notes": {
    "unmapped_section_legacy_notes": "Original content here..."
  }
}
```

### If a required field has no source data:
1. First, attempt to infer from related context
2. If inference impossible, use placeholder: `"MIGRATION-REQUIRED: [description]"`
3. Document in `_migration_notes` why field couldn't be populated

### If source contains ambiguous or conflicting information:
1. Use the most recent information
2. Document the ambiguity in `_migration_notes`
3. Mark with `"_needs_review": true` at that object level

## Self-Audit Gate

Before returning your output, you MUST verify each item:

- [ ] **Completeness**: Every section of the source document is accounted for
      (either in schema fields or in `_migration_notes`)
- [ ] **Required Fields**: All required fields have values
- [ ] **Valid JSON**: Output parses as valid JSON
- [ ] **Schema Compliance**: JSON structure matches target schema
- [ ] **No Hallucination**: All values derive from source document only
- [ ] **Lossless**: Nothing from source is silently dropped
- [ ] **Notes Review**: `_migration_notes` explains any caveats

## Output Contract

Write the final JSON artifact directly to disk at the step path under `spec/` (or runner-provided path).

The JSON must:
1. Be valid, parseable JSON
2. Conform to the target schema
3. Contain NO explanatory text outside the code block
4. Include `_migration_notes` object if any data couldn't be mapped

```json
{
  "$schema": "{{SCHEMA_REF}}",
  // Your complete output here
}
```
