# Migration: Implementation Context (Step 16)

## Schema URI

`vc:16-impl-context`

## Required Changes

**Step-base fields (required in every artifact)**

- `id`: Unique kebab-case identifier for this artifact instance (`$ref: vc:core:atoms#kebabId`).
- `owner`: Owner of this spec artifact. Must be one of: `api | ui | system | ops | data | product | business | engineering`.
- `created_at`: ISO 8601 timestamp of when this artifact was generated or last regenerated (`$ref: vc:core:atoms#timestamp`).
- `canonical_refs_used`: array of canonical reference objects used in this artifact

- `$schema`: Must reference the URI above for the target toolkit version.
- `plan`: Object (the primary required field). Requires:
  - `status`: Must be one of `active | deferred`.
  - When `status` is `active`: `review_requirements` object with `test_commands` array (minItems: 1) is required; `summary.target_file_patterns` must also have `minItems: 1` (schema `else` branch constraint when `status != "deferred"`).
  - When `status` is `deferred`: `deferred_reason` string is required.
  - `spec_alignment`: Object with `checklist` array. Each checklist item requires `id` (SCREAMING_SNAKE_CASE), `spec_ref` (specRef object with `type`, `id`, `line_range`, `commit_hash`), `description`, and `linked_test_expectation`.
  - Non-deferred checklist items also conditionally require `implementation` (with `status` and `actions`) and `nfr_refs` and `fixture_ref`.

## Output Contract

The migrated artifact MUST include:

- `$schema`: Set to the canonical URI above.
- `canonical_refs_used`: Array of canonical reference objects.

## Optional Fields

- `_migration_notes`: Array of strings — migration annotations written exclusively by specdev tooling (canonical-autofix, align apply). Do NOT populate manually.
- `plan.summary`: Object with `functional_summary`, `scope_in`, `scope_out`, and `target_file_patterns`.
- `plan.docs_impact`: Object with `status` (`required | not_required`) and `rationale` (minLength: 10).
- `plan.ambiguities`: Array of ambiguity objects, each requiring `id`, `description`, and `severity` (`blocking | non_blocking`).
- `plan.solution`: Object with `architecture_sketch` (required when present).
- `plan.context`: Object with `existing_structures` and `coding_examples`.
- `plan.review_requirements.guidelines`: String with 3–7 implementation rules.
- `plan.review_requirements.nfr_measurement_methods`: Object mapping `nfr_id` → measurement object.
- `plan.review_requirements.timeout_constants`: Object mapping SCREAMING_SNAKE_CASE constant names to millisecond integer values.
- `plan.security`: Either `{status: not_applicable, reason}` or `{status: planned, ...}`.
- `plan.docs`: Either `{status: not_applicable, reason}` or `{status: planned, required_updates}`.
- `plan.delivery`: Either `{status: not_applicable, reason}` or `{status: planned, dashboards, alerts}`.
- `plan.drift`: Either `{status: not_applicable, reason}` or `{status: planned, checks}`.
- `plan.coverage_status`: Object with `total`, `verified`, `deferred`, `pending` integer counts.
- `execution`: Object tracking files touched, execution results, and critical evidence.
- `review`: Object with `findings`, `ratings` (5 integer scores 0–5), `verdict` (`verified | needs_work | blocked | deferred`), and `next_actions`.
- `extensions`: Object with optional `review_state` and `execution_context` sub-objects.
- `policy_ref`: Canonical reference (kind: `risk_category`) for the governance policy.
- `risk_category_ref`: Canonical reference (kind: `risk_category`) for the primary risk category.

## Validation

After migration, run:

```bash
./tools/run_specdev.sh validate spec/16_impl_context.json --repo-root ./devspec_toolkit
```

## Context

The implementation context schema was completely redesigned as a Checklist-Driven
Implementation artifact. The old `context`, `scaffold_ref`, `decisions`, and
`current_phase` fields no longer exist — the entire artifact must be rebuilt
around the `plan` object. The `plan` object is the sole required field, and it
must contain `status` and (for active plans) `review_requirements` with
`test_commands`. Checklist items in `plan.spec_alignment.checklist` require
`spec_ref` objects that include `line_range` and `commit_hash` for evidence
binding. The `review` sub-object captures post-implementation review findings
and a final `verdict`. Migrate existing decision records into `plan.ambiguities`
or `plan.solution.architecture_sketch` as appropriate.


## Full Generation Reference

To generate this artifact from scratch (rather than migrate an existing one), use the canonical step prompt:

- `prompts/prompt_16_impl_context.md`

The generation prompt contains the complete Output Contract, Self-Audit Gate, and schema authority reference needed to produce a valid artifact.
