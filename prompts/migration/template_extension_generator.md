# Migration: Extension Generator (Step 13)

## Schema URI

`vc:13-extension-generator`

## Required Changes

**Step-base fields (required in every artifact)**

- `id`: Unique kebab-case identifier for this artifact instance (`$ref: vc:core:atoms#kebabId`).
- `owner`: Owner of this spec artifact. Must be one of: `api | ui | system | ops | data | product | business | engineering`.
- `created_at`: ISO 8601 timestamp of when this artifact was generated or last regenerated (`$ref: vc:core:atoms#timestamp`).
- `canonical_refs_used`: array of canonical reference objects used in this artifact

- `$schema`: Must reference the URI above for the target toolkit version.
- `extensions`: Array of extension descriptor objects (minItems: 1). Each entry requires:
  - `extension_id`: String matching pattern `^ext-[0-9]{2}-[a-z0-9-]+$` (e.g., `ext-01-database`).
  - `title`: String — Title Case human-readable name (e.g., `Database Layer Extension`).
  - `file_name`: String matching pattern `^ext_[0-9]{2}_[a-z0-9_]+\.json$` — derived from `extension_id` with hyphens replaced by underscores.
  - `area_of_concern`: String — canonical domain category (e.g., `AI`, `ML`, `Payments`, `Data`, `Security`, `Notifications`, `Infrastructure`).
  - `required_schema_sections`: Array of section name strings — must include `trace` and `validation_rules` at minimum.
  - `governance_label_ref`: Canonical reference object — required on every extension entry. **Note**: the schema contains an internal inconsistency: the `description` text states `kind: 'capability'`, while the inline example uses `kind: "term"`. Both values appear in the schema source; use whichever resolves correctly in your project's canonical registry and document the choice in `_migration_notes`.

## Output Contract

The migrated artifact MUST include:

- `$schema`: Set to the canonical URI above.
- `canonical_refs_used`: Array of canonical reference objects.

## Optional Fields

- `_migration_notes`: Array of strings — migration annotations written exclusively by specdev tooling (canonical-autofix, align apply). Do NOT populate manually.
- `extensions[].justification`: String explaining why this extension is needed.
- `extensions[].schema_design_guidelines`: String with schema authoring guidance.
- `extensions[].tag_ref`: Canonical reference to a classification tag.
- `extensions[].policy_ref`: Canonical reference to a governing policy.
- `extensions[].id_pattern_ref`: Canonical reference to the ID naming convention.

## Validation

After migration, run:

```bash
./tools/run_specdev.sh validate spec/13_extension_generator.json --repo-root ./devspec_toolkit
```

## Context

The extension generator manifest declares all domain-specific spec extensions
(e.g., database schema, session management) that supplement the core pipeline.
Each extension produces an `ext_NN_*.json` file that must conform to the
`required_schema_sections` listed here. During migration, verify that every
`extension_id` and `file_name` still adhere to their strict regex patterns —
re-number them if the ordering has changed. The `governance_label_ref` must
resolve in the canonical registry; check that the referenced label still exists
in the target toolkit version. Extensions are consumed by the completeness
assessment (Step 13a) so extension IDs should not change after that step has
been generated.


## Full Generation Reference

To generate this artifact from scratch (rather than migrate an existing one), use the canonical step prompt:

- `prompts/prompt_13_extension_generator.md`

The generation prompt contains the complete Output Contract, Self-Audit Gate, and schema authority reference needed to produce a valid artifact.
