# Migration: Delivery Baseline (Step 02a)

## Schema URI

`https://specdev.local/schema/02a_delivery_baseline.schema.json`

## Required Changes

- `$schema`: Must reference the URI above for the target toolkit version.
- `baseline`: Object containing delivery parameters and constraints.
- `team_size`: Must be a positive integer.
- `timeline`: Object with `start_date` and `end_date` in ISO 8601 format.
- `environments`: Array of environment names from canonical registry.

## Output Contract

The migrated artifact MUST include:

- `$schema`: Set to the canonical URI above.
- `generation_quality`: Object with `preflight_passed` boolean.
- `canonical_refs_used`: Array of canonical reference objects.

## Optional Fields

- `_migration_notes`: String describing what changed during migration.
- `assumptions`: Array of baseline assumption strings.

## Validation

After migration, run:

```bash
./tools/run_specdev.sh validate spec/02a_delivery_baseline.json --repo-root ./devspec_toolkit
```

## Context

The delivery baseline anchors the implementation plan (Step 09) and roadmap
(Step 14). Environment names must match the canonical registry in
`canon/manifest.json`. If the schema version introduces new required fields
for team structure or velocity estimates, populate from existing data or flag
for manual review. Dates should remain unchanged unless the migration itself
requires a timeline reset.
