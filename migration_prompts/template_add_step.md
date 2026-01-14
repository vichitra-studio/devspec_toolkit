# Migration: Generate Missing Step

## Purpose

Generate a new specification step that was introduced in a newer version of the DevSpec Toolkit. This migration is required when the toolkit adds a new step that your project doesn't have yet.

The goal is to create a complete, valid JSON specification that conforms to the target schema while leveraging existing project context to generate meaningful content.

## Context

- Source Version: {{SOURCE_VERSION}}
- Target Version: {{TARGET_VERSION}}
- Step ID: {{STEP_ID}}
- Operation: Add New Step

## Existing Project Context

The following existing specification files provide context about your project. Use these to generate content that is consistent with your project's domain, terminology, and architecture.

{{#each CONTEXT_SOURCES}}
### {{this.filename}}

```json
{{this.content}}
```

{{/each}}

## Target Schema

The generated JSON must conform to this schema. Pay careful attention to required fields, field types, and constraints.

```json
{{TARGET_SCHEMA}}
```

## Required Fields

The following fields are REQUIRED in the output:

{{#each REQUIRED_FIELDS}}
- `{{this.path}}`: {{this.description}}
  - Type: `{{this.type}}`
  - Constraints: {{this.constraints}}
{{/each}}

## Transformation Rules

### Rule 1: Derive from Existing Context
- Extract relevant information from the provided context files
- Use consistent terminology from the glossary (if available)
- Reference existing capability IDs, FR IDs, and interface IDs where appropriate

### Rule 2: Follow Naming Conventions
- All IDs must use kebab-case (e.g., `my-component-name`)
- IDs must be unique within the file
- Reference IDs must match existing IDs exactly

### Rule 3: Maintain Trace Integrity
- All `trace_ref` arrays must contain valid references to existing IDs
- New IDs should follow the pattern established in other spec files
- Cross-references must be bidirectional where required

### Rule 4: No Placeholder Content
- Do not use placeholder text like "TBD" or "TODO"
- If information cannot be derived from context, make a reasonable inference
- Document any inferences in the `notes` field if available

## Handling Edge Cases

### If no context files are available:
Generate a minimal valid spec with reasonable defaults. Document in `_migration_notes` that context was unavailable.

### If the step requires domain-specific knowledge not in context:
1. Generate a structural template with placeholder-like but valid values
2. Add `"_needs_review": true` to the root object
3. Document what needs human review in `_migration_notes`

### If required fields cannot be inferred:
Use the schema's default values if available. Otherwise, create a syntactically valid placeholder that clearly indicates human input is needed (e.g., `"MIGRATION-REQUIRED-value-description"`).

## Self-Audit Gate

Before returning your output, you MUST verify each item:

- [ ] **Schema Compliance**: JSON structure matches target schema exactly
- [ ] **Required Fields**: All required fields have valid values
- [ ] **Valid JSON**: Output parses as valid JSON (no trailing commas, proper quotes)
- [ ] **ID Consistency**: All IDs use kebab-case format
- [ ] **Trace Validity**: All trace references point to existing IDs from context
- [ ] **No Examples**: Output is project-specific, not generic examples
- [ ] **Terminology**: Uses terms from glossary/context where available

## Output Contract

Return exactly one fenced code block with language `json`.

The JSON must:
1. Be valid, parseable JSON
2. Conform to the target schema
3. Contain NO explanatory text outside the code block
4. Include `_migration_notes` object if any content needed special handling

```json
{
  "$schema": "{{SCHEMA_REF}}",
  // Your complete specification here
}
```
