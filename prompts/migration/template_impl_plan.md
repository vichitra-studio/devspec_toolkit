# Migration: Implementation Plan (Step 09)

## Schema URI

`https://specdev.local/schema/09_impl_plan.schema.json`

## Required Changes

- `$schema`: Must reference the URI above for the target toolkit version.
- `tech_stack`: Must be an object (not an array); keys are technology categories.
- `milestones`: Array of milestone objects; each needs `id`, `name`, `deliverables`.
- `deliverables`: Must be an array within each milestone.
- `phases`: Array of implementation phases with ordering.

## Output Contract

The migrated artifact MUST include:

- `$schema`: Set to the canonical URI above.
- `generation_quality`: Object with `assumptions` array.
- `canonical_refs_used`: Array of canonical reference objects.

## Optional Fields

- `_migration_notes`: String describing what changed during migration.
- `risks`: Array of risk objects associated with the plan.

## Validation

After migration, run:

```bash
./tools/run_specdev.sh validate spec/09_impl_plan.json --repo-root ./devspec_toolkit
```

## Context

The implementation plan is a common source of migration errors. The `tech_stack`
field must be an object, not an array -- older versions sometimes used an array
format. Each milestone must contain a `deliverables` array; missing this field
causes validation failure. Cross-reference milestones with the delivery baseline
(Step 02a) to ensure timeline consistency. Component references should match
IDs from the system sketch (Step 02).
