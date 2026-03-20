# Migration: System Sketch (Step 02)

## Schema URI

`vc:02-system-sketch`

## Required Changes

- `$schema`: Must reference the URI above for the target toolkit version.
- `components`: Array of component objects; each needs `id`, `name`, `type`.
- `connections`: Array describing inter-component relationships.
- `id` format: Must be kebab-case (e.g., `comp-api-gateway`).
- `type`: Must match canonical component type values.

## Output Contract

The migrated artifact MUST include:

- `$schema`: Set to the canonical URI above.
- `canonical_refs_used`: Array of canonical reference objects.

## Optional Fields

- `_migration_notes`: String describing what changed during migration.
- `deployment_context`: Object describing infrastructure assumptions.

## Validation

After migration, run:

```bash
./tools/run_specdev.sh validate spec/02_system_sketch.json --repo-root ./devspec_toolkit
```

## Context

The system sketch defines the architectural topology. Component IDs are
referenced by interface contracts (Step 05) and the implementation plan
(Step 09). Ensure all component IDs are stable across migration. If the
schema adds new required fields to connections (e.g., `protocol`, `direction`),
populate them from the existing connection descriptions or mark for manual review.
