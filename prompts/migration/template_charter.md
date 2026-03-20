# Migration: Charter (Step 00)

## Schema URI

`vc:00-charter`

## Required Changes

- `$schema`: Must reference the URI above for the target toolkit version.
- `project_name`: Verify non-empty string, unchanged unless project was renamed.
- `vision`: Must be a non-empty string (>20 characters).
- `goals`: Array of goal objects; ensure each has `id`, `description`, and `priority`.
- `stakeholders`: Array with at least one entry; each needs `role` and `name`.
- `constraints`: Verify structure matches current schema (array of objects).

## Output Contract

The migrated artifact MUST include:

- `$schema`: Set to the canonical URI above.
- `canonical_refs_used`: Array of canonical reference objects.

## Optional Fields

- `_migration_notes`: String describing what changed during migration.
- `assumptions`: Array of assumption strings (added in later schema revisions).

## Validation

After migration, run:

```bash
./tools/run_specdev.sh validate spec/00_charter.json --repo-root ./devspec_toolkit
```

## Context

The charter is the root artifact of every spec pipeline. During migration,
preserve all goal IDs since downstream FRs and capabilities trace back to them.
If goal IDs change, every downstream artifact referencing them will break
traceability closure. Validate stakeholder roles against the canonical owner
enum: `api | ui | system | ops | data | product | business | engineering`.
