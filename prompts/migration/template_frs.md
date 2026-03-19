# Migration: Functional Requirements (Step 04)

## Schema URI

`https://specdev.local/schema/04_fr_list.schema.json`

## Required Changes

- `$schema`: Must reference the URI above for the target toolkit version.
- `requirements`: Array of FR objects; each needs `id`, `description`, `priority`, `owner`.
- `id` format: Must be kebab-case with `fr-` prefix (e.g., `fr-user-login`).
- `owner`: Must use canonical owner enum values.
- `capability_refs`: Each FR must trace back to a valid capability ID from Step 01.
- `acceptance_criteria`: Array of criteria strings; must not be empty.

## Output Contract

The migrated artifact MUST include:

- `$schema`: Set to the canonical URI above.
- `canonical_refs_used`: Array of canonical reference objects.

## Optional Fields

- `_migration_notes`: String describing what changed during migration.
- `tags`: Array of classification tags.

## Validation

After migration, run:

```bash
./tools/run_specdev.sh validate spec/04_functional_requirements.json --repo-root ./devspec_toolkit
```

## Context

Functional requirements are the primary traceability anchor. FR IDs appear in
interface contracts (Step 05), fixtures (Step 08), the trace matrix, and NFRs
(Step 07). Never rename an FR ID without updating all downstream references.
The trace matrix must be regenerated after migration. If the new schema version
changes `acceptance_criteria` from strings to structured objects, convert each
string into the required object format.
