# Migration: Glossary (Step 03)

## Schema URI

`https://specdev.local/schema/03_glossary.schema.json`

## Required Changes

- `$schema`: Must reference the URI above for the target toolkit version.
- `terms`: Array with at least one entry; each needs `term`, `definition`, `domain`.
- `definition`: Must be longer than 20 characters.
- `domain`: Must be kebab-case (e.g., `user-management`).
- No empty strings allowed in any field.

## Output Contract

The migrated artifact MUST include:

- `$schema`: Set to the canonical URI above.
- `generation_quality`: Object with `preflight_passed` boolean.
- `canonical_refs_used`: Array of canonical reference objects.

## Optional Fields

- `_migration_notes`: String describing what changed during migration.
- `aliases`: Array of alternative terms for each glossary entry.

## Validation

After migration, run:

```bash
./tools/run_specdev.sh validate spec/03_glossary.json --repo-root ./devspec_toolkit
```

## Context

The glossary provides shared vocabulary across all spec artifacts. Terms are
referenced by canonical-lint and canonical-integrity checks. During migration,
ensure no definitions are truncated below the 20-character minimum. If the new
schema version adds a `context` or `see_also` field, leave them empty rather
than inventing content. Domain values should align with the canonical registry.
