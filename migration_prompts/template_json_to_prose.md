# Migration: Generate Documentation from JSON

## Purpose

Convert a structured JSON specification into human-readable markdown documentation. This operation is typically used to regenerate prose documentation after JSON specs have been updated.

The goal is **readable documentation**: create clear, well-organized markdown that humans can easily read and understand.

## Context

- Source Version: {{SOURCE_VERSION}}
- Target Version: {{TARGET_VERSION}}
- Operation: Paradigm Shift (JSON → Prose)
- Source File: `{{SOURCE_FILE}}`
- Target File: `{{TARGET_FILE}}`

## Source Data

The following is the complete JSON specification to convert:

```json
{{SOURCE_CONTENT}}
```

## Target Format

The output should be a well-formatted markdown document. Reference this existing document for style guidance (if available):

```markdown
{{EXISTING_DOC_STYLE}}
```

## Transformation Rules

### Rule 1: Object Hierarchy → Document Structure

Map JSON structure to document sections:
- Root object name/id → Document title (H1)
- Top-level arrays → Major sections (H2)
- Array items → Subsections or list items
- Nested objects → Nested headings or details

**Example**:
```json
{
  "milestones": [{
    "name": "Foundation",
    "tasks": ["Set up database", "Configure auth"]
  }]
}
```

Becomes:
```markdown
## Foundation

- Set up database
- Configure auth
```

### Rule 2: Enum Values → Human-Readable Status

Convert status enums to readable text:
- `"done"` → "✓ Complete"
- `"in_progress"` → "🔄 In Progress"
- `"pending"` → "⏳ Pending"
- `"blocked"` → "🚫 Blocked"

### Rule 3: ISO 8601 → Readable Dates

Convert dates to readable format:
- `"2026-01-14"` → "January 14, 2026"
- Or keep as-is if consistency is preferred

### Rule 4: Trace References → Links

Convert trace refs to readable references:
- `"trace_refs": ["fr-001"]` → "See: FR-001"
- If possible, include the referenced item's name

### Rule 5: Omit Internal Fields

Do NOT include in the markdown:
- `$schema` references
- `_migration_notes`
- `_needs_review` flags
- Technical metadata meant for tooling

## Handling Edge Cases

### If the JSON contains `_migration_notes`:
These are migration artifacts. Optionally include as a "Migration Notes" section at the end, or omit entirely.

### If arrays are empty:
Either omit the section or note "None defined yet."

### If technical IDs are present:
Use the associated `name` or `description` for display, optionally include ID in parentheses.

## Self-Audit Gate

Before returning your output, you MUST verify each item:

- [ ] **Completeness**: All significant data from JSON is represented
- [ ] **Readable**: Clear, well-organized document structure
- [ ] **Accurate**: No information changed or misrepresented
- [ ] **Well-Formatted**: Proper markdown syntax
- [ ] **No Technical Artifacts**: Internal fields omitted

## Output Contract

Return exactly one fenced code block with language `markdown`.

The markdown must:
1. Be valid markdown syntax
2. Represent all significant content from the JSON
3. Be human-readable and well-organized
4. Follow the style of existing project documentation

```markdown
# {{DOCUMENT_TITLE}}

[Your complete documentation here]
```
