# Migration: Governance (Step 10)

## Schema URI

`vc:10-governance`

## Required Changes

**Step-base fields (required in every artifact)**

- `id`: Unique kebab-case identifier for this artifact instance (`$ref: vc:core:atoms#kebabId`).
- `owner`: Owner of this spec artifact. Must be one of: `api | ui | system | ops | data | product | business | engineering`.
- `created_at`: ISO 8601 timestamp of when this artifact was generated or last regenerated (`$ref: vc:core:atoms#timestamp`).
- `canonical_refs_used`: array of canonical reference objects used in this artifact

- `$schema`: Must reference the URI above for the target toolkit version.
- `spec_first_policy`: Boolean — enforces that spec artifacts are updated before corresponding implementation code.
- `commit_message_rules`: Object defining commit message format. Requires `require_spec_ids` (boolean). Optional sub-fields: `pattern` (string), `error_message` (string), `id_pattern_ref` (canonical reference).

## Output Contract

The migrated artifact MUST include:

- `$schema`: Set to the canonical URI above.
- `canonical_refs_used`: Array of canonical reference objects.

## Optional Fields

- `_migration_notes`: Array of strings — migration annotations written exclusively by specdev tooling (canonical-autofix, align apply). Do NOT populate manually.
- `versioning`: String — one of `semver | date-based | sequential`.
- `pr_rules`: Array of unique strings; each must be one of `validate | validate-all | matrix | fixtures-lint | invariants-check | governance-check | seed-lint | test | build | lint | format | audit | security`.
- `review_policy`: Object requiring `verdict_requirements` (array, minItems: 1), `required_metadata`, and `evidence_source_by_phase` (object with `dev`, `staging`, `prod` keys).
- `reviewers`: Array of GitHub handles or team names.
- `trace`: Array of trace reference objects linking governance to upstream artifacts.
- `links`: Array of external link objects for governance resources.
- `policy_ref`: Canonical reference (kind: `risk_category` or `capability`) for the governance policy.
- `command_ref`: Canonical reference (kind: `action`) for the CLI command this rule triggers.

## Validation

After migration, run:

```bash
./tools/run_specdev.sh spec-check spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
./tools/run_specdev.sh governance-check spec --repo-root ./devspec_toolkit --message "feat(spec): test migration"
```

## Context

Governance rules are enforced on every commit via `governance-check`. The
required fields are now `spec_first_policy` (boolean) and `commit_message_rules`
(object with `require_spec_ids`). The legacy `commit_rules` and `branch_rules`
fields do not exist in the current schema — rename `commit_rules` to
`commit_message_rules` and extract the `require_spec_ids` boolean. The
`pr_rules` field is now an array of string enum values (not an object); convert
any object format to the string-array format and verify each value is in the
approved enum. The `roles` field does not exist in the current schema — remove it.


## Full Generation Reference

To generate this artifact from scratch (rather than migrate an existing one), use the canonical step prompt:

- `prompts/prompt_10_governance.md`

The generation prompt contains the complete Output Contract, Self-Audit Gate, and schema authority reference needed to produce a valid artifact.
