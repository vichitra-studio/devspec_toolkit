# Migration: Implementation Context (Step 16)

## Schema URI

`vc:16-impl-context`

## Required Changes

- `$schema`: Must reference the URI above for the target toolkit version.
- `context`: Object containing implementation state and decisions.
- `scaffold_ref`: Must reference a valid scaffold ID from Step 15.
- `decisions`: Array of architectural decision records.
- `current_phase`: Must reference a valid phase from the implementation plan (Step 09).

## Output Contract

The migrated artifact MUST include:

- `$schema`: Set to the canonical URI above.
- `canonical_refs_used`: Array of canonical reference objects.

## Optional Fields

- `_migration_notes`: String describing what changed during migration.
- `blockers`: Array of current implementation blockers.

## Validation

After migration, run:

```bash
./tools/run_specdev.sh validate spec/16_impl_context.json --repo-root ./devspec_toolkit
```

## Context

The implementation context captures the live state of the build phase. It feeds
the Trinity Loop (Steps 16a/16b/16c) with plan, code, and review context.
During migration, ensure scaffold references (Step 15) are still valid. If the
schema version changes how decisions are structured (e.g., from flat strings to
ADR objects), convert each entry. The `current_phase` must match a phase ID
from the implementation plan.
