# Migration: Non-Functional Requirements (Step 07)

## Schema URI

`https://specdev.local/schema/07_nfrs.schema.json`

## Required Changes

- `$schema`: Must reference the URI above for the target toolkit version.
- `nfrs`: Array of NFR objects; each needs `id`, `category`, `description`, `target`.
- `id` format: Must be kebab-case with `nfr-` prefix (e.g., `nfr-response-time`).
- `category`: Must use canonical NFR category values from the canonical registry.
- `target`: Quantitative or qualitative target with units from canonical registry.

## Output Contract

The migrated artifact MUST include:

- `$schema`: Set to the canonical URI above.
- `generation_quality`: Object with `preflight_passed` boolean.
- `canonical_refs_used`: Array of canonical reference objects.

## Optional Fields

- `_migration_notes`: String describing what changed during migration.
- `measurement_method`: How the NFR target is measured.

## Validation

After migration, run:

```bash
./tools/run_specdev.sh validate spec/07_nfrs.json --repo-root ./devspec_toolkit
```

## Context

NFRs define quality attributes and are referenced in the trace matrix alongside
FRs and fixtures. The `category` field must match values from the canonical
registry (`canon/manifest.json`). Units in `target` (e.g., `ms`, `%`, `req/s`)
must also be canonical. During migration, verify that all NFR IDs referenced in
fixtures (Step 08) still exist. Regenerate the trace matrix after migration.
