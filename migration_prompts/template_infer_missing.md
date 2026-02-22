# Migration: Infer Missing Required Data

## Purpose

Infer a value for a required field when no direct source data exists. This uses contextual analysis of related specification files to derive a reasonable value.

The goal is **best-effort inference**: create a valid value based on available context, clearly documenting the inference for human review.

## Context

- Source Version: {{SOURCE_VERSION}}
- Target Version: {{TARGET_VERSION}}
- Step ID: {{STEP_ID}}
- Missing Field: `{{FIELD_PATH}}`
- Operation: Infer Missing Data

## Current Specification

The following file is missing a required field:

```json
{{SOURCE_CONTENT}}
```

## Target Schema

The field requirements from the target schema:

```json
{{TARGET_SCHEMA}}
```

## Missing Field Details

### Field: `{{FIELD_PATH}}`

- **Type**: `{{FIELD_TYPE}}`
- **Description**: {{FIELD_DESCRIPTION}}
- **Required**: Yes
- **Default**: {{FIELD_DEFAULT}} (if any)

## Available Context for Inference

The following related files may help infer the missing value:

{{#each CONTEXT_SOURCES}}
### {{this.filename}}

```json
{{this.content}}
```

{{/each}}

## Inference Strategies

### Strategy 1: Derive from Related Fields
Look for related fields in the same file that might indicate the missing value:
- Similar field names with different suffixes
- Parent or sibling objects that provide context
- Pattern matching with existing data

### Strategy 2: Cross-Reference Other Specs
The missing field might be derivable from:
- Charter (project purpose and scope)
- Capabilities (system functions)
- FR List (functional requirements)
- Glossary (domain terminology)

### Strategy 3: Use Schema Defaults
If the schema provides examples or defaults, use those as a starting point and customize for the project.

### Strategy 4: Minimal Valid Value
If no inference is possible, create the minimum valid value that satisfies the schema:
- Empty array for array types: `[]`
- Empty object for object types: `{}`
- Placeholder string: `"MIGRATION-REQUIRED: [field description]"`

## Transformation Rules

### Rule 1: Explain Your Inference
Always document HOW you derived the value in `_migration_notes`:
- What source data informed the inference
- What assumptions were made
- Confidence level in the inference

### Rule 2: Mark for Review
All inferred values should be marked with `"_needs_review": true` at the containing object level.

### Rule 3: Prefer Specific Over Generic
If context suggests a project-specific value, use it instead of a generic placeholder.

### Rule 4: Maintain Consistency
The inferred value should:
- Use the same terminology as other specs
- Follow the same ID patterns
- Reference valid existing IDs where applicable

## Self-Audit Gate

Before returning your output, you MUST verify each item:

- [ ] **Field Present**: The missing field now has a value
- [ ] **Valid Type**: The value matches the required type
- [ ] **Valid JSON**: Output parses as valid JSON
- [ ] **Schema Compliance**: Output validates against target schema
- [ ] **Documented**: `_migration_notes` explains the inference
- [ ] **Marked for Review**: `_needs_review` flag is set

## Output Contract

Write the final JSON artifact directly to disk at the step path under `spec/` (or runner-provided path).

The JSON must:
1. Be valid, parseable JSON
2. Contain the inferred field value
3. Include comprehensive inference documentation

```json
{
  // All existing fields preserved...
  
  "{{FIELD_PATH}}": "inferred value",
  
  "_migration_notes": {
    "inferred_fields": [
      {
        "field": "{{FIELD_PATH}}",
        "inferred_value": "the value you generated",
        "inference_source": "What data informed this inference",
        "confidence": "high|medium|low",
        "assumptions": ["List of assumptions made"]
      }
    ]
  },
  "_needs_review": true
}
```
