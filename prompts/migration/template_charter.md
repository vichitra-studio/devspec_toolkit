# Migration: Charter (Step 00)

## Schema URI

`vc:00-charter`

## Required Changes

**Step-base fields (required in every artifact):**

- `id`: String — unique kebab-case identifier for this artifact instance (e.g., `charter-v1`). Convention: `{step-noun}-v{N}`.
- `owner`: String enum — must be one of `api | ui | system | ops | data | product | business | engineering`.
- `created_at`: String — ISO 8601 UTC timestamp (e.g., `2025-10-16T22:06:04.202593Z`).
- `canonical_refs_used`: Array of canonical reference objects — required even when empty (`[]`).

**Step-specific fields:**

- `$schema`: Must reference the URI above for the target toolkit version.
- `problem_statement`: String (minLength: 20). Describe the problem this project solves; must not use solution-language.
- `in_scope`: Array of strings (minItems: 3). Each item names a concrete deliverable, capability, or integration point.
- `out_of_scope`: Array of strings (minItems: 3). Each item explicitly names something excluded from this project.
- `assumptions`: Array of strings (minItems: 1). Each is a falsifiable present-tense statement taken for granted during scoping.
- `risks`: Array of strings (minItems: 1). Each names a specific risk that could affect project success or timeline.
- `success_metrics`: Array of metric objects (minItems: 2). Each requires `metric_id` (kebab-case), `name`, `target`, `unit`, `measurement_method`, and `unit_ref`.
- `stakeholders`: Array of stakeholder objects. Each requires `role` (string) and `needs` (array of strings, minItems: 1).
- `user_segments`: Array of segment objects. Each requires `segment_id` (kebab-case), `description`, `jobs_to_be_done`, `pains`, and `gains`.

## Output Contract

The migrated artifact MUST include:

- `$schema`: Set to the canonical URI above.
- `canonical_refs_used`: Array of canonical reference objects.

## Optional Fields

- `_migration_notes`: Array of strings — migration annotations written exclusively by specdev tooling (canonical-autofix, align apply). Do NOT populate manually.
- `title`: Short human-readable title (2–6 words, Title Case noun phrase).
- `stakeholders[].role_ref`: Canonical reference (kind: `entity`) for the stakeholder role.
- `success_metrics[].baseline`: Current measured value before the project (number or string).
- `links`: Array of external link objects (each with `rel` and `href`).

## Validation

After migration, run:

```bash
./tools/run_specdev.sh validate spec/00_charter.json --repo-root ./devspec_toolkit
```

## Context

The charter is the root artifact of every spec pipeline. During migration,
preserve all `metric_id` values from `success_metrics` since downstream NFRs
and capabilities trace back to them via `metric-*` IDs. The `stakeholders[].owner`
field is NOT part of this schema — the `owner` field belongs to step-base.
Validate `success_metrics[].unit` against canonical abbreviations (`ms`, `percent`,
`req/s`, `count`) and ensure a matching `unit_ref` canonical reference is present.


## Full Generation Reference

To generate this artifact from scratch (rather than migrate an existing one), use the canonical step prompt:

- `prompts/prompt_00_project_charter.md`

The generation prompt contains the complete Output Contract, Self-Audit Gate, and schema authority reference needed to produce a valid artifact.
