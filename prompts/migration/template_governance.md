# Migration: Governance (Step 10)

## Schema URI

`vc:10-governance`

## Required Changes

- `$schema`: Must reference the URI above for the target toolkit version.
- `commit_rules`: Object defining commit message patterns and conventions.
- `pr_rules`: Object with review and approval requirements; enum values must be from the allowed set.
- `branch_rules`: Object defining branch naming and protection policies.
- `roles`: Array of role objects referencing canonical owner enum values.

## Output Contract

The migrated artifact MUST include:

- `$schema`: Set to the canonical URI above.
- `canonical_refs_used`: Array of canonical reference objects.

## Optional Fields

- `_migration_notes`: String describing what changed during migration.
- `exceptions`: Array of governance exception policies.

## Validation

After migration, run:

```bash
./tools/run_specdev.sh validate spec/10_governance.json --repo-root ./devspec_toolkit
./tools/run_specdev.sh governance-check spec --repo-root ./devspec_toolkit --message "feat(spec): test migration"
```

## Context

Governance rules are enforced on every commit via `governance-check`. The
`pr_rules` field must use allowed enum values; invalid values cause rejection.
Commit message patterns defined here are validated by CI hooks. During
migration, ensure the commit pattern regex is compatible with the target
toolkit version. Role references must align with the canonical owner enum.
