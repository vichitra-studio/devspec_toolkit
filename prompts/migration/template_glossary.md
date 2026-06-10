# Migration: Glossary (Step 03)

## Schema URI

`vc:03-glossary`

## Required Changes

**Step-base fields (required in every artifact):**

- `id`: String — unique kebab-case identifier for this artifact instance (e.g., `glossary-v1`). Convention: `{step-noun}-v{N}`.
- `owner`: String enum — must be one of `api | ui | system | ops | data | product | business | engineering`.
- `created_at`: String — ISO 8601 UTC timestamp (e.g., `2025-10-16T22:06:04.202593Z`).
- `canonical_refs_used`: Array of canonical reference objects — required even when empty (`[]`).

**Step-specific fields:**

- `$schema`: Must reference the URI above for the target toolkit version.
- `terms`: Array of term objects (minItems: 1). Each entry requires:
  - `term_id`: kebab-case identifier (e.g., `term-billing-reconciliation`).
  - `term`: String (minLength: 2) — canonical form of the term as it appears in project documentation.
  - `definition`: String (minLength: 20) — precise definition as used in this project.
  - `term_ref`: Canonical reference object (kind: `term`) — required.
- `canonical_proposals`: Array — required at the top level (may be empty array `[]`).

## Output Contract

The migrated artifact MUST include:

- `$schema`: Set to the canonical URI above.
- `canonical_refs_used`: Array of canonical reference objects.

## Optional Fields

- `_migration_notes`: Array of strings — migration annotations written exclusively by specdev tooling (canonical-autofix, align apply). Do NOT populate manually.
- `terms[].acronym`: Uppercase string (pattern: `^[A-Z0-9]{2,}$`) — include only if the acronym appears 3+ times or is standard industry usage.
- `terms[].domain`: Lowercase alphabetic-only kebab-case string (pattern: `^[a-z]+(?:-[a-z]+)*$`) — no digits allowed.
- `terms[].units`: String (pattern: `^[A-Za-z0-9/]+$`) — unit of measurement if the term is quantifiable.
- `terms[].acronym_ref`: Canonical reference (kind: `acronym`) — only when `acronym` field is also set.
- `terms[].unit_ref`: Canonical reference (kind: `term`) — only when `units` field is also set.

## Validation

After migration, run:

```bash
./tools/run_specdev.sh spec-check spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
```

## Context

The glossary provides shared vocabulary across all spec artifacts. Terms are
referenced by canonical-lint and canonical-integrity checks. During migration,
ensure no definitions are truncated below the 20-character minimum. The top-level
`canonical_proposals` field is now required (even as an empty array). Add a
`term_ref` canonical reference to every term entry. The `domain` field pattern
prohibits digits (`^[a-z]+(?:-[a-z]+)*$`) — correct any `domain` values that
contain numbers. After migration, run `canon-accept` to promote new glossary
terms to the canonical registry.


## Full Generation Reference

To generate this artifact from scratch (rather than migrate an existing one), use the canonical step prompt:

- `prompts/prompt_03_glossary.md`

The generation prompt contains the complete Output Contract, Self-Audit Gate, and schema authority reference needed to produce a valid artifact.
