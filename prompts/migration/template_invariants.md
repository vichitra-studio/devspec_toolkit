# Migration: Invariants (Step 06)

## Schema URI

`vc:06-invariants`

## Required Changes

- `$schema`: Must reference the URI above for the target toolkit version.
- `invariants`: Array of invariant objects; each needs `id`, `description`, `scope`.
- `id` format: Must be kebab-case with `inv-` prefix (e.g., `inv-no-orphan-frs`).
- `scope`: Must reference valid component or system-level identifiers.
- `enforcement`: Must describe how the invariant is checked.

## Output Contract

The migrated artifact MUST include:

- `$schema`: Set to the canonical URI above.
- `canonical_refs_used`: Array of canonical reference objects.

## Optional Fields

- `_migration_notes`: String describing what changed during migration.
- `severity`: Invariant violation severity level.

## Validation

After migration, run:

```bash
./tools/run_specdev.sh validate spec/06_invariants.json --repo-root ./devspec_toolkit
```

## Context

Invariants define system-wide rules that must hold at all times. They are
verified by `invariants-check` and referenced in fixtures (Step 08). The
`enforcement` field was changed from a plain string to a structured object
in some schema revisions; ensure the migrated format matches the target
schema. Invariant IDs appear in fixture target_ids, so preserve them.
