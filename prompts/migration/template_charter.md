<!-- Migration template for {{project_name}} — specdev v{{spec_version}} — step {{step_id}} -->
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
- `scope_items`: Array of scope item objects (minItems: 1). Replaces `in_scope` and `out_of_scope`: each requires `scope_id` (kebab-case), `text`, `scope` (`in | later | out`) and `derives_from` (seed or need ids); `scope_reason` is required when `scope` is `later` or `out`.
- `assumptions`: Array of assumption objects (minItems: 1). Each requires `assumption_id` (kebab-case), `text` (a falsifiable present-tense statement taken for granted during scoping) and `derives_from`.
- `risks`: Array of risk objects (minItems: 1). Each requires `risk_id` (kebab-case), `text`, `scope` and `derives_from`.
- `success_metrics`: Array of metric objects (minItems: 2). Each requires `metric_id` (kebab-case), `name`, `target`, `unit`, `measurement_method`, `unit_ref` and `derives_from`.
- `stakeholders`: Array of stakeholder objects. Each requires `stakeholder_id` (kebab-case), `role` (string) and `needs` (array of need objects, each with `need_id`, `text` and `derives_from`).
- `user_segments`: Array of segment objects. Each requires `segment_id` (kebab-case), `description`, `jobs_to_be_done`, `pains`, `gains` and `derives_from`.

## Output Contract

The migrated artifact MUST include:

- `$schema`: Set to the canonical URI above.
- `canonical_refs_used`: Array of canonical reference objects.

## Optional Fields

- `_migration_notes`: Array of strings — migration annotations written exclusively by specdev tooling (canonical-autofix, align apply). Do NOT populate manually.
- `title`: Short human-readable title (2–6 words, Title Case noun phrase).
- `stakeholders[].role_ref`: Canonical reference (kind: `entity`) for the stakeholder role.
- `success_metrics[].baseline`: Current measured value before the project (number or string).
- `constraints`: Array of constraint objects. Each requires `constraint_id` (kebab-case), `text`, `scope` and `derives_from`.

## Validation

After migration, run:

```bash
./tools/run_specdev.sh spec-check spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
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
