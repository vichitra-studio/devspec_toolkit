# Migration: Implementation Planner (Step 16a)

## Schema URI

`vc:16-impl-context`

## Required Changes

**Step-base fields (required in every artifact)**

- `id`: Unique kebab-case identifier for this artifact instance (`$ref: vc:core:atoms#kebabId`).
- `owner`: Owner of this spec artifact. Must be one of: `api | ui | system | ops | data | product | business | engineering`.
- `created_at`: ISO 8601 timestamp of when this artifact was generated or last regenerated (`$ref: vc:core:atoms#timestamp`).
- `canonical_refs_used`: array of canonical reference objects used in this artifact

- `$schema`: Must reference the URI above for the target toolkit version.
- `plan.status`: Must be `"active"` or `"deferred"`.
- `plan.summary.functional_summary`: 1–3 sentences naming the capability, primary actor, and key constraints.
- `plan.summary.scope_in`: Array of strings — items explicitly included in scope.
- `plan.summary.scope_out`: Array of strings — items explicitly excluded from scope.
- `plan.summary.target_file_patterns`: Array of glob patterns (relative to repo root) for files the coder may touch. Must have at least one item when `plan.status == "active"`.
- `plan.spec_alignment.checklist`: Array of atomic requirement items. Each item requires `id` (SCREAMING_SNAKE_CASE), `spec_ref` (object with `type`, `id`, `line_range`, `commit_hash`), `description`, and `linked_test_expectation`. When `checklist_status` is not `"deferred"`, each item additionally requires `implementation` (with `status` and `actions`), `nfr_refs`, and `fixture_ref`.
- `plan.review_requirements.test_commands`: Array with at least one entry when `plan.status == "active"`.

## Output Contract

The migrated artifact MUST include:

- `$schema`: Set to `vc:16-impl-context`.
- `id`: Kebab-case identifier for this artifact.
- `owner`: One of the allowed owner enum values.
- `created_at`: ISO 8601 timestamp.
- `canonical_refs_used`: Array of canonical reference objects (e.g. `[{ "id": "cn:core:unit:ms", "kind": "unit" }]`).
- `plan`: Object with at minimum `status` populated.

## Optional Fields

- `_migration_notes`: Array of strings — migration annotations written exclusively by specdev tooling (canonical-autofix, align apply). Do NOT populate manually.
- `plan.summary`: Recommended for active plans — required fields are listed in Required Changes above.
- `plan.spec_alignment.checklist[].type`: Classification of the checklist item (`behavior`, `constraint`, `validation`, `metadata`, `perf`, `logging`, `docs`, `security`).
- `plan.spec_alignment.checklist[].layer`: Architecture layer (`db`, `model`, `service`, `api`, `integration`, `tests`, `docs`, `config`, `security`).
- `plan.spec_alignment.checklist[].milestone_ref`: Kebab-case milestone ID from `spec/14_roadmap.json`.
- `plan.spec_alignment.requirements_summary`: 2–4 themed requirement groups, each with `theme` and `summary`.
- `plan.ambiguities`: Array of ambiguity records; each requires `id`, `description`, and `severity`; when `severity == "non_blocking"`, `mitigation` is also required.
- `plan.solution`: Architecture sketch (`architecture_sketch` required), sequence of concerns, and risks.
- `plan.context.existing_structures`: Verified codebase structures (do not hallucinate).
- `plan.security`: Security plan (`status` required; either `not_applicable` with `reason`, or `planned` with optional `new_fixtures` and `spec_mutations`).
- `plan.delivery`: Delivery observability plan (`status` required).
- `plan.drift`: Drift monitoring plan (`status` required).
- `plan.docs_impact`: Documentation impact (`status` and `rationale` required; when `status == "required"`, `docs_touched` with minItems:1 also required).
- `plan.deferred_reason`: Required when `plan.status == "deferred"`.
- `extensions`: Structured data that does not fit in core schema fields.

## Validation

After migration, run:

```bash
./tools/run_specdev.sh validate spec/16_impl_context.json --repo-root ./devspec_toolkit
```

## Context

Step 16a is the Planning phase of the Trinity Loop. It produces a machine-checkable blueprint
consumed by the Implementation Coder (Step 16b). During migration, verify that every roadmap
`task_id` from the active milestone in `spec/14_roadmap.json` maps to at least one checklist item.
The `commit_hash` in each `spec_ref` must be a valid 40-character SHA — never a placeholder.
The `plan` section must not contradict or expand scope beyond the upstream `spec/16_impl_context.json`.
When `plan.status == "active"`, `review_requirements.test_commands` must be populated with at
least one entry matching the `linked_test_expectation` values on the checklist items.

## Full Generation Reference

To generate this artifact from scratch (rather than migrate an existing one), use the canonical step prompt:

- `prompts/prompt_16a_impl_planner.md`

The generation prompt contains the complete Output Contract, Self-Audit Gate, and schema authority reference needed to produce a valid artifact.
