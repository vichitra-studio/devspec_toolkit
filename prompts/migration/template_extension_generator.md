# Migration: Extension Generator (Step 13)

## Schema URI

`https://specdev.local/schema/13_extension_generator.schema.json`

## Required Changes

- `$schema`: Must reference the URI above for the target toolkit version.
- `extensions`: Array of extension descriptor objects; each needs `extension_id`, `title`, `file_name`, `area_of_concern`, `required_schema_sections`, and `governance_label_ref`.
- `extension_id` format: Must match `^ext-[0-9]{2}-[a-z0-9-]+$` (e.g., `ext-01-database-schema`).
- `file_name` format: Must match `^ext_[0-9]{2}_[a-z0-9_]+\.json$` (e.g., `ext_01_database_schema.json`).
- `governance_label_ref`: Required canonical reference on every extension entry.
- `required_schema_sections`: Non-empty array of section name strings.

## Output Contract

The migrated artifact MUST include:

- `$schema`: Set to the canonical URI above.
- `generation_quality`: Object with `preflight_passed` boolean.
- `canonical_refs_used`: Array of canonical reference objects.
- `canonical_proposals`: Array (may be empty).
- `canonical_conflicts`: Array (may be empty).

## Optional Fields

- `_migration_notes`: String describing what changed during migration.
- `extensions[].justification`: String explaining why this extension is needed.
- `extensions[].schema_design_guidelines`: String with schema authoring guidance.
- `extensions[].tag_ref`: Canonical reference to a classification tag.
- `extensions[].policy_ref`: Canonical reference to a governing policy.
- `extensions[].id_pattern_ref`: Canonical reference to the ID naming convention.

## Validation

After migration, run:

```bash
./tools/run_specdev.sh validate spec/13_extension_generator.json --repo-root ./devspec_toolkit
```

## Context

The extension generator manifest declares all domain-specific spec extensions
(e.g., database schema, session management) that supplement the core pipeline.
Each extension produces an `ext_NN_*.json` file that must conform to the
`required_schema_sections` listed here. During migration, verify that every
`extension_id` and `file_name` still adhere to their strict regex patterns —
re-number them if the ordering has changed. The `governance_label_ref` must
resolve in the canonical registry; check that the referenced label still exists
in the target toolkit version. Extensions are consumed by the completeness
assessment (Step 13a) so extension IDs should not change after that step has
been generated.
