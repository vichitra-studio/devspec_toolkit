# Migration: Implementation Plan (Step 09)

## Schema URI

`vc:09-impl-plan`

## Required Changes

**Step-base fields (required in every artifact):**

- `id`: String — unique kebab-case identifier for this artifact instance (e.g., `impl-plan-v1`). Convention: `{step-noun}-v{N}`.
- `owner`: String enum — must be one of `api | ui | system | ops | data | product | business | engineering`.
- `created_at`: String — ISO 8601 UTC timestamp (e.g., `2025-10-16T22:06:04.202593Z`).
- `canonical_refs_used`: Array of canonical reference objects — required even when empty (`[]`).

**Step-specific fields:**

- `$schema`: Must reference the URI above for the target toolkit version.
- `tech_stack`: Object (not an array) with required keys: `languages`, `frameworks`, `infrastructure`, `tools`. Each key maps to an array of strings.
- `milestones`: Array of milestone objects (minItems: 1). Each entry requires:
  - `milestone_id`: kebab-case identifier (e.g., `milestone-phase1-user-auth`).
  - `name`: String — Title Case, 3–6 words describing the deliverable.
  - `deliverables`: Array of trace reference objects (minItems: 1) — each requires `type` and `id`; bare strings are not accepted.
  - `status`: Must be one of `pending | in_progress | done | deferred`.
- `trace`: Array of trace reference objects (minItems: 1) at the document level — use `type: derives_from` pointing to `nfr-*` or `inv-*` IDs.

## Output Contract

The migrated artifact MUST include:

- `$schema`: Set to the canonical URI above.
- `canonical_refs_used`: Array of canonical reference objects.

## Optional Fields

- `_migration_notes`: Array of strings — migration annotations written exclusively by specdev tooling (canonical-autofix, align apply). Do NOT populate manually.
- `tech_stack_ref`: Canonical reference (kind: `capability`) for the technology stack entry.
- `milestones[].target_date`: ISO 8601 date string (YYYY-MM-DD).
- `milestones[].risks`: Array of risk strings describing threats to the milestone.
- `milestones[].spikes`: Array of strings describing time-boxed investigations.
- `milestones[].depends_on`: Array of `milestone_id` strings (no cycles).
- `milestones[].status_ref`: Canonical reference (kind: `stage`) for the milestone status.
- `migration_plan`: String describing the migration strategy (required only when replacing existing systems).
- `dependencies`: Mixed array of dependency strings or objects describing cross-team dependencies.
- `dependency_ref`: Canonical reference (kind: `dependency`) for a registered external dependency.
- `environment_ref`: Canonical reference (kind: `environment`) for the deployment target.

## Validation

After migration, run:

```bash
./tools/run_specdev.sh validate spec/09_impl_plan.json --repo-root ./devspec_toolkit
```

## Context

The implementation plan is a common source of migration errors. The `tech_stack`
field must be an object with four required keys (`languages`, `frameworks`,
`infrastructure`, `tools`), not an array. The top-level `trace` array is required
(not optional) — add it if missing. Each milestone's `deliverables` field must
contain trace reference objects (`{type: implements, id: "fr-..."}`) not bare
strings. The `phases` field from older schemas does not exist in the current schema
— remove it and represent phase ordering through `depends_on` references instead.
The `milestone_id` field (not `id`) must be used. Cross-reference milestone
`status` with the delivery baseline (Step 02a).


## Full Generation Reference

To generate this artifact from scratch (rather than migrate an existing one), use the canonical step prompt:

- `prompts/prompt_09_impl_plan.md`

The generation prompt contains the complete Output Contract, Self-Audit Gate, and schema authority reference needed to produce a valid artifact.
