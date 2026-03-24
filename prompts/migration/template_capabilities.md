# Migration: Capabilities (Step 01)

## Schema URI

`vc:01-capabilities`

## Required Changes

**Step-base fields (required in every artifact):**

- `id`: String — unique kebab-case identifier for this artifact instance (e.g., `capabilities-v1`). Convention: `{step-noun}-v{N}`.
- `owner`: String enum — must be one of `api | ui | system | ops | data | product | business | engineering`.
- `created_at`: String — ISO 8601 UTC timestamp (e.g., `2025-10-16T22:06:04.202593Z`).
- `canonical_refs_used`: Array of canonical reference objects — required even when empty (`[]`).

**Step-specific fields:**

- `$schema`: Must reference the URI above for the target toolkit version.
- `capabilities`: Array of capability objects (minItems: 1). Each entry requires:
  - `capability_id`: kebab-case identifier (e.g., `cap-user-authentication`).
  - `verb`: String (minLength: 2) — specific imperative action verb (e.g., `authenticate`, `reconcile`).
  - `scope`: Must be one of `in | out | future`.
  - `capability_ref`: Canonical reference object (kind: `capability`) — required.
  - `trace`: Array of trace reference objects (minItems: 1) — each requires `type` and `id`.

## Output Contract

The migrated artifact MUST include:

- `$schema`: Set to the canonical URI above.
- `canonical_refs_used`: Array of canonical reference objects.

## Optional Fields

- `_migration_notes`: Array of strings — migration annotations written exclusively by specdev tooling (canonical-autofix, align apply). Do NOT populate manually.
- `capabilities[].description`: String (minLength: 20) — `[Beneficiary] can [outcome] by [mechanism]`.
- `capabilities[].owner`: Canonical owner enum (`api | ui | system | ops | data | product | business | engineering`).
- `capabilities[].inputs`: Array of strings — data or signals required to exercise the capability.
- `capabilities[].outputs`: Array of strings — observable results of successful execution.
- `capabilities[].preconditions`: Array of strings — conditions that must hold before execution.
- `capabilities[].postconditions`: Array of strings — conditions guaranteed after execution.
- `capabilities[].name`: String (minLength: 2) — Title Case human-readable label.
- `capabilities[].goal_id`: Kebab-case ID of the charter goal this capability directly serves.
- `capabilities[].success_metric_refs`: Array of charter `metric_id` values this capability drives.
- `capabilities[].error_states`: Array of `errorState` objects with named error codes.
- `capabilities[].action_ref`: Canonical reference (kind: `action`) for the verb.
- `capabilities[].entity_ref`: Canonical reference (kind: `entity`) for the primary domain entity.
- `capabilities[].role_ref`: Canonical reference (kind: `entity`) for the actor exercising this capability.

## Validation

After migration, run:

```bash
./tools/run_specdev.sh validate spec/01_capabilities.json --repo-root ./devspec_toolkit
```

## Context

Capabilities bridge charter artifacts to functional requirements. Preserve all
`capability_id` values since they are referenced by FRs in Step 04, NFRs in
Step 07, and the system sketch in Step 02. The schema no longer uses `id` —
rename any `id` field to `capability_id`. Each capability must have a `trace`
array pointing back to charter artifacts using type `derives_from`. The `verb`
field drives downstream `action_ref` values; do not use generic verbs like
`manage` or `handle`.


## Full Generation Reference

To generate this artifact from scratch (rather than migrate an existing one), use the canonical step prompt:

- `prompts/prompt_01_capabilities.md`

The generation prompt contains the complete Output Contract, Self-Audit Gate, and schema authority reference needed to produce a valid artifact.
