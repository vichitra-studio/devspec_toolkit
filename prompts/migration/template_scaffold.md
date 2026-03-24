# Migration: Scaffold (Step 15)

## Schema URI

`vc:15-scaffold`

## Required Changes

**Step-base fields (required in every artifact)**

- `id`: Unique kebab-case identifier for this artifact instance (`$ref: vc:core:atoms#kebabId`).
- `owner`: Owner of this spec artifact. Must be one of: `api | ui | system | ops | data | product | business | engineering`.
- `created_at`: ISO 8601 timestamp of when this artifact was generated or last regenerated (`$ref: vc:core:atoms#timestamp`).
- `canonical_refs_used`: array of canonical reference objects used in this artifact

- `$schema`: Must reference the URI above for the target toolkit version.
- `project_skeleton`: Object requiring `language` (lowercase string, no version suffix). Optional: `framework` (lowercase kebab-case), `modules` (array of directory path strings).
- `validators`: Array of validator identifier strings — must be non-empty when `build_status` is `green`.
- `build_status`: Must be one of `pending | green | red`.

## Output Contract

The migrated artifact MUST include:

- `$schema`: Set to the canonical URI above.
- `canonical_refs_used`: Array of canonical reference objects.

## Optional Fields

- `_migration_notes`: Array of strings — migration annotations written exclusively by specdev tooling (canonical-autofix, align apply). Do NOT populate manually.
- `interface_map`: Array of route objects; each requires `interface_ref` (kebab-case api_id from Step 05, no duplicates), `path` (relative forward-slash path), and `method` (one of `GET | POST | PUT | DELETE | PATCH | OPTIONS | HEAD`).
- `command_ref`: Canonical reference (kind: `action`) to the scaffold build/generate command.
- `trace`: Array of trace reference objects — use `type: implements` pointing to `fr-*` or `api-*` IDs.
- `links`: Array of link objects pointing to generated code or documentation.

## Validation

After migration, run:

```bash
./tools/run_specdev.sh validate spec/15_scaffold.json --repo-root ./devspec_toolkit
```

## Context

The scaffold artifact maps interface contracts (Step 05) onto a concrete
service skeleton that the Trinity Loop (Steps 16a–16c) iterates over. The
`interface_map` must have one entry per API defined in Step 05 — add or remove
entries to stay in sync after any interface changes. Duplicate `interface_ref` values
are rejected by the validator. If `build_status` is `green`, at least one
validator must be listed; downgrade to `pending` during migration if validators
have not yet been confirmed. The `project_skeleton.language` and `framework`
values drive code generation in Step 16b, so ensure they accurately reflect the
target tech stack from `seed_tech_stack.md`.


## Full Generation Reference

To generate this artifact from scratch (rather than migrate an existing one), use the canonical step prompt:

- `prompts/prompt_15_scaffold.md`

The generation prompt contains the complete Output Contract, Self-Audit Gate, and schema authority reference needed to produce a valid artifact.
