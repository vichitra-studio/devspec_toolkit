# Migration: Completeness Assessment (Step 13a)

## Schema URI

`vc:13a-completeness-assessment`

## Required Changes

**Step-base fields (required in every artifact)**

- `id`: Unique kebab-case identifier for this artifact instance (`$ref: vc:core:atoms#kebabId`).
- `owner`: Owner of this spec artifact. Must be one of: `api | ui | system | ops | data | product | business | engineering`.
- `created_at`: ISO 8601 timestamp of when this artifact was generated or last regenerated (`$ref: vc:core:atoms#timestamp`).
- `canonical_refs_used`: array of canonical reference objects used in this artifact

- `$schema`: Must reference the URI above for the target toolkit version.
- `dimensions`: Object with four required coverage dimension keys (all machine-computed from actual spec content — do not estimate):
  - `fr_api_coverage`: Coverage dimension object.
  - `fr_fixture_coverage`: Coverage dimension object.
  - `fr_milestone_coverage`: Coverage dimension object.
  - `capability_fr_coverage`: Coverage dimension object.
- Each coverage dimension object requires: `covered_count` (integer ≥ 0), `total_count` (integer ≥ 0), `ratio` (number 0–1, must equal `covered_count / total_count`), and `uncovered_ids` (array of actual upstream IDs with no downstream link).

## Output Contract

The migrated artifact MUST include:

- `$schema`: Set to the canonical URI above.
- `canonical_refs_used`: Array of canonical reference objects.

## Optional Fields

- `_migration_notes`: Array of strings — migration annotations written exclusively by specdev tooling (canonical-autofix, align apply). Do NOT populate manually.
- `dimensions.milestone_decomp_completeness`: Optional fifth coverage dimension for milestone decomposition completeness (same structure as the four required dimensions).

## Validation

After migration, run:

```bash
./tools/run_specdev.sh validate spec/13a_completeness_assessment.json --repo-root ./devspec_toolkit
```

## Context

The completeness assessment schema was completely redesigned. The old
`missing_elements` / `completeness_rating` structure no longer exists — the
entire content must be rebuilt using the `dimensions` object. Run
`specdev completeness-check spec --repo-root ./devspec_toolkit --json` to
obtain machine-computed values for all four required dimensions; do not
estimate or guess the `ratio` or `uncovered_ids` values. A ratio below 0.8
on any dimension triggers warning W592 (promotable to E592). The artifact
depends on Steps 01, 04, 05, 08, and 09 being finalised before it can be
accurately computed.


## Full Generation Reference

To generate this artifact from scratch (rather than migrate an existing one), use the canonical step prompt:

- `prompts/prompt_13a_completeness_assessment.md`

The generation prompt contains the complete Output Contract, Self-Audit Gate, and schema authority reference needed to produce a valid artifact.
