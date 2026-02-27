# Migration: Capabilities (Step 01)

## Schema URI

`https://specdev.local/schema/01_capabilities.schema.json`

## Required Changes

- `$schema`: Must reference the URI above for the target toolkit version.
- `capabilities`: Array of capability objects; each needs `id`, `name`, `description`.
- `id` format: Must be kebab-case (e.g., `cap-user-auth`).
- `goal_refs`: Each capability must reference valid goal IDs from `00_charter.json`.
- `owner`: Must use canonical owner enum values.

## Output Contract

The migrated artifact MUST include:

- `$schema`: Set to the canonical URI above.
- `generation_quality`: Object with `assumptions` array.
- `canonical_refs_used`: Array of canonical reference objects.

## Optional Fields

- `_migration_notes`: String describing what changed during migration.
- `priority`: Capability-level priority if supported by the target schema.

## Validation

After migration, run:

```bash
./tools/run_specdev.sh validate spec/01_capabilities.json --repo-root ./devspec_toolkit
```

## Context

Capabilities bridge goals to functional requirements. Preserve all capability
IDs since they are referenced by FRs in Step 04. If any capability is removed
or renamed, trace all downstream references and update them accordingly. New
schema versions may require additional fields like `status` or `phase`.
