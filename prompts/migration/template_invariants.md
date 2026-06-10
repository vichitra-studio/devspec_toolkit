# Migration: Invariants (Step 06)

## Schema URI

`vc:06-invariants`

## Required Changes

**Step-base fields (required in every artifact):**

- `id`: String — unique kebab-case identifier for this artifact instance (e.g., `invariants-v1`). Convention: `{step-noun}-v{N}`.
- `owner`: String enum — must be one of `api | ui | system | ops | data | product | business | engineering`.
- `created_at`: String — ISO 8601 UTC timestamp (e.g., `2025-10-16T22:06:04.202593Z`).
- `canonical_refs_used`: Array of canonical reference objects — required even when empty (`[]`).

**Step-specific fields:**

- `$schema`: Must reference the URI above for the target toolkit version.
- `rules`: Array of invariant rule objects (minItems: 1). Each entry requires:
  - `inv_id`: kebab-case with `inv-` prefix (e.g., `inv-payment-positive-amount`).
  - `description`: String — formal statement in the form `The system ensures [property] for [subject] whenever [trigger]`.
  - `language`: Must be one of `jsonlogic | cel | text`.
  - `expression`: String — machine-readable expression in the specified language.
  - `scope`: Object with at least one of `components` (array of component_id strings) or `apis` (array of api_id strings).
  - `trace`: Array of trace reference objects (minItems: 1) — each requires `type: capability` for `cap-*` targets or `type: fr` for `fr-*` targets; the derives-from relationship is described in the optional `note` field.
  - `policy_ref`: Canonical reference object (kind: `policy`) — required on every rule.

## Output Contract

The migrated artifact MUST include:

- `$schema`: Set to the canonical URI above.
- `canonical_refs_used`: Array of canonical reference objects.

## Optional Fields

- `_migration_notes`: Array of strings — migration annotations written exclusively by specdev tooling (canonical-autofix, align apply). Do NOT populate manually.
- `rules[].severity`: Must be one of `warn | error`.
- `rules[].owner`: Canonical owner enum override (when different from document-level owner).
- `rules[].enforcement_point`: Must be one of `database | service | api-gateway | client | queue | cache`.
- `rules[].risk_category_ref`: Canonical reference (kind: `risk_category`) grouping invariants by risk domain.

## Validation

After migration, run:

```bash
./tools/run_specdev.sh spec-check spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
```

## Context

Invariants define machine-verifiable always-true constraints. The top-level
array field is `rules` (not `invariants`) — rename accordingly. Each rule
requires `language` + `expression` + `scope` + `trace` + `policy_ref`. The
`enforcement` field from older schemas is replaced by `enforcement_point` (an
enum, optional). The `scope` object must have at least one of `components` or
`apis` populated — an empty scope object is rejected. Invariant IDs (`inv_id`)
appear in fixture `targets` and red team `target_ids`, so preserve them
through migration.


## Full Generation Reference

To generate this artifact from scratch (rather than migrate an existing one), use the canonical step prompt:

- `prompts/prompt_06_invariants.md`

The generation prompt contains the complete Output Contract, Self-Audit Gate, and schema authority reference needed to produce a valid artifact.
