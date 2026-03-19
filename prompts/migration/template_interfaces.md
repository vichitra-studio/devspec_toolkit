# Migration: Interface Contracts (Step 05)

## Schema URI

`https://specdev.local/schema/05_interface_contracts.schema.json`

## Required Changes

- `$schema`: Must reference the URI above for the target toolkit version.
- `interfaces`: Array of interface objects; each needs `id`, `method`, `path`.
- `id` format: Must be kebab-case with `api-` prefix (e.g., `api-session-create`).
- `method`: Must be one of GET, POST, PUT, DELETE, PATCH, OPTIONS, HEAD.
- No duplicate `api_ref` values allowed.
- `fr_refs`: Each interface must reference valid FR IDs from Step 04.

## Output Contract

The migrated artifact MUST include:

- `$schema`: Set to the canonical URI above.
- `canonical_refs_used`: Array of canonical reference objects.

## Optional Fields

- `_migration_notes`: String describing what changed during migration.
- `request_schema` / `response_schema`: Inline JSON Schema objects for payloads.

## Validation

After migration, run:

```bash
./tools/run_specdev.sh validate spec/05_interface_contracts.json --repo-root ./devspec_toolkit
```

## Context

Interface contracts define the API surface. They are referenced by fixtures
(Step 08) and the scaffold (Step 15). The `method` field is strictly validated;
ensure no lowercase or non-standard HTTP verbs remain. If migrating from a
version that used a flat string `api_ref` to one with structured references,
convert accordingly. Duplicate `api_ref` values will cause Step 15 validation
failures.
