# Migration: Implementation Planner (Step 16a)

## Schema URI

`vc:16-impl-context` — see `schema/16_impl_context.schema.json` for the authoritative field set, types, required-status, enums, and conditional requirements. This document captures only migration-specific transformations; do NOT restate schema shape here.

## Migration-Specific Transformations

These rules apply only when migrating an existing 16a artifact forward — they are not part of the canonical generation prompt.

- **`plan.ambiguities[].assumption` → `proposed_assumption`** — older artifacts may carry the legacy field name `assumption`. Rename to `proposed_assumption`. The schema rejects the old name under `additionalProperties: false`.
- **`plan.review_requirements.test_commands[]` shape** — entries are `string` OR `{ command, command_ref?, description? }` (schema `oneOf`). Migration must NOT wrap commands as `bash -c "..."` to dodge hallucination-lint (E530); use one of the two supported escape routes:
  - **PRIMARY** — register `cn:project:command:<verb>` in `<spec-root>/canon/kinds/command.json` and emit the entry in object form with a sibling `command_ref`. Hallucination-lint bypasses the prefix check on shape; canonical-integrity (E110/E210) enforces resolution.
  - **ESCAPE** — for one-off verbs that don't merit a canon entry, append the verb to `<spec-root>/canon/command_prefixes.json` (project-level allowlist, merged with the toolkit default).
- **`canonical_refs_used`** — legacy artifacts may omit this top-level array. Populate it with every canonical reference the migrated artifact relies on (e.g. `[{ "id": "cn:core:unit:ms", "kind": "unit" }]`); the schema requires it on every step-base artifact.
- **`_migration_notes`** — written exclusively by tooling (`canonical-autofix`, `align apply`). Do NOT populate manually.

## Validation

After migration, run `spec-check` with the full flag set. When the `devspec_env`
venv is active, call `specdev` directly (shown below); from a host repo
(submodule deployment) without the venv active, run the same command through the
`./tools/run_specdev.sh` wrapper instead:

```bash
specdev spec-check spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
```

## Context

Step 16a is the Planning phase of the Trinity Loop. It produces a machine-checkable blueprint consumed by the Implementation Coder (Step 16b). During migration, verify that every roadmap `task_id` from the active milestone in `spec/14_roadmap.json` maps to at least one checklist item, and that every `commit_hash` in `spec_ref` is a valid 40-character SHA. The `plan` section must not contradict or expand scope beyond the upstream `spec/16_impl_context.json`.

## Full Generation Reference

To generate this artifact from scratch (rather than migrate an existing one), use the canonical step prompt:

- `prompts/prompt_16a_impl_planner.md`

The generation prompt + the schema together carry the complete contract — this document does not duplicate either.
