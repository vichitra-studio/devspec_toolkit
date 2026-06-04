# Migration: Fixtures (Step 08)

## Schema URI

`vc:08-fixtures`

## Required Changes

**Step-base fields (required in every artifact):**

- `id`: String — unique kebab-case identifier for this artifact instance (e.g., `fixtures-v1`). Convention: `{step-noun}-v{N}`.
- `owner`: String enum — must be one of `api | ui | system | ops | data | product | business | engineering`.
- `created_at`: String — ISO 8601 UTC timestamp (e.g., `2025-10-16T22:06:04.202593Z`).
- `canonical_refs_used`: Array of canonical reference objects — required even when empty (`[]`).

**Step-specific fields:**

- `$schema`: Must reference the URI above for the target toolkit version.
- `fixtures`: Array of fixture objects (minItems: 1). Each entry requires:
  - `fixture_id`: kebab-case identifier (e.g., `fix-auth-login-success`).
  - `mode`: Must be one of `unit | contract | e2e | redteam`.
  - `input`: Any JSON value representing the fixture's input data.
  - `expected`: Any JSON value representing the expected system behavior.
  - `targets`: Array of trace reference objects (minItems: 1) — each requires `type: validates` and an `id` from `fr-*`, `api-*`, `nfr-*`, or `inv-*`.
  - `tag_ref`: Canonical reference object (kind: `term`) — required on every fixture.

## Output Contract

The migrated artifact MUST include:

- `$schema`: Set to the canonical URI above.
- `canonical_refs_used`: Array of canonical reference objects.

## Optional Fields

- `_migration_notes`: Array of strings — migration annotations written exclusively by specdev tooling (canonical-autofix, align apply). Do NOT populate manually.
- `fixtures[].description`: String in `Given/when/then` format describing what the fixture tests.
- `fixtures[].tags`: Array of short label strings (pattern: `^[A-Za-z0-9_.:-]{1,64}$`).

## Validation

After migration, run:

```bash
./tools/run_specdev.sh spec-check spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
./tools/run_specdev.sh fixtures-lint spec --repo-root ./devspec_toolkit
```

## Context

Fixtures provide concrete test data for the spec pipeline. The field is `targets`
(not `target_ids`) — rename accordingly. Each target is now a trace reference
object (`{type: validates, id: "fr-..."}`) not a bare string. The `tag_ref`
canonical reference is now required on every fixture — add it. The `fixture_id`
field (not `id`) must use the `fix-` prefix convention. Always run `fixtures-lint`
after migration to catch dangling references. If any upstream artifact renamed or
removed an ID, fixtures will report "Unknown Target."


## Full Generation Reference

To generate this artifact from scratch (rather than migrate an existing one), use the canonical step prompt:

- `prompts/prompt_08_fixtures.md`

The generation prompt contains the complete Output Contract, Self-Audit Gate, and schema authority reference needed to produce a valid artifact.
