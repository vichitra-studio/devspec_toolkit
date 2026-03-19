# Migration: Fixtures (Step 08)

## Schema URI

`https://specdev.local/schema/08_fixtures.schema.json`

## Required Changes

- `$schema`: Must reference the URI above for the target toolkit version.
- `fixtures`: Array of fixture objects; each needs `id`, `target_ids`, `input`, `expected`.
- `id` format: Must be kebab-case (e.g., `fix-login-success`).
- `target_ids`: Array of valid IDs from FRs (`fr-*`), APIs (`api-*`), NFRs (`nfr-*`), or invariants (`inv-*`).
- All referenced target IDs must exist in their respective spec files.

## Output Contract

The migrated artifact MUST include:

- `$schema`: Set to the canonical URI above.
- `canonical_refs_used`: Array of canonical reference objects.

## Optional Fields

- `_migration_notes`: String describing what changed during migration.
- `tags`: Array of fixture classification tags.

## Validation

After migration, run:

```bash
./tools/run_specdev.sh validate spec/08_fixtures.json --repo-root ./devspec_toolkit
./tools/run_specdev.sh fixtures-lint spec --repo-root ./devspec_toolkit
```

## Context

Fixtures provide concrete test data for the spec pipeline. The `target_ids`
field is the most common source of migration failures: if any upstream artifact
renamed or removed an ID, fixtures will report "Unknown Target." Always run
`fixtures-lint` after migration to catch dangling references. If the schema
adds structured `expected` objects (replacing plain strings), convert each
fixture's expected value to the new format.
