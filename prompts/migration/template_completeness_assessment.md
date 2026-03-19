# Migration: Completeness Assessment (Step 13a)

## Schema URI

`https://specdev.local/schema/13a_completeness_assessment.schema.json`

## Required Changes

- `$schema`: Must reference the URI above for the target toolkit version.
- `missing_elements`: Array of gap objects; each needs `element_id`, `category`, `description`, `priority`, and `impact_on_completeness`.
- `element_id` format: Must be kebab-case.
- `priority`: Must be one of `high | medium | low`.
- `impact_on_completeness`: Number between 0 and 1 (inclusive) representing fractional impact.
- `completeness_rating`: Object with `current`, `target` (both 0–10), and `confidence_level` (0–1).

## Output Contract

The migrated artifact MUST include:

- `$schema`: Set to the canonical URI above.
- `canonical_refs_used`: Array of canonical reference objects.
- `canonical_proposals`: Array (OPTIONAL).
- `canonical_conflicts`: Array (OPTIONAL).

## Optional Fields

- `_migration_notes`: String describing what changed during migration.
- `missing_elements[].specification_source`: Array of source file names matching the step file pattern.
- `missing_elements[].risk_category_ref`: Canonical reference to a risk category.
- `missing_elements[].completeness_dimension_ref`: Canonical reference to a completeness dimension.
- `missing_elements[].tag_ref`: Canonical reference to a classification tag.

## Validation

After migration, run:

```bash
./tools/run_specdev.sh validate spec/13a_completeness_assessment.json --repo-root ./devspec_toolkit
```

## Context

The completeness assessment is a scored gap analysis of the entire spec
pipeline as it stood when Step 13a was generated. It depends on the extension
generator (Step 13) having been finalised. During migration, recalculate
`completeness_rating.current` if new gaps have been identified or resolved
since the source version. The `specification_source` pattern accepts both core
step files (`NN[a]_*.json`) and extension files (`ext_NN_*.json`). Canonical
refs for `completeness_dimension_ref` and `risk_category_ref` must be verified
against the target toolkit's canonical registry. The `confidence_level` reflects
how thoroughly the pipeline has been reviewed; do not inflate it automatically
during migration without re-running the assessment.
