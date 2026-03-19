# Migration: Roadmap (Step 14)

## Schema URI

`https://specdev.local/schema/14_roadmap.schema.json`

## Required Changes

- `$schema`: Must reference the URI above for the target toolkit version.
- `milestones`: Array of roadmap milestone objects with `id`, `name`, `target_date`.
- `target_date`: Must be in ISO 8601 date format.
- `dependencies`: Array of milestone dependency references.
- `fr_refs`: Each milestone should trace to functional requirements from Step 04.

## Output Contract

The migrated artifact MUST include:

- `$schema`: Set to the canonical URI above.
- `canonical_refs_used`: Array of canonical reference objects.

## Optional Fields

- `_migration_notes`: String describing what changed during migration.
- `release_notes`: Descriptive text for each milestone.

## Validation

After migration, run:

```bash
./tools/run_specdev.sh validate spec/14_roadmap.json --repo-root ./devspec_toolkit
```

## Context

The roadmap organizes delivery milestones and their dependencies. It references
FRs from Step 04 and aligns with the implementation plan (Step 09) and delivery
baseline (Step 02a). During migration, verify that all `fr_refs` still point to
valid FR IDs. Date formats must be strict ISO 8601. If the new schema version
adds a `status` field to milestones, default to `planned` unless evidence of
completion exists.
