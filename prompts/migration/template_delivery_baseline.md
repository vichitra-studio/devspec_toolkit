# Migration: Delivery Baseline (Step 02a)

## Schema URI

`vc:02a-delivery-baseline`

## Required Changes

**Step-base fields (required in every artifact):**

- `id`: String — unique kebab-case identifier for this artifact instance (e.g., `delivery-baseline-v1`). Convention: `{step-noun}-v{N}`.
- `owner`: String enum — must be one of `api | ui | system | ops | data | product | business | engineering`.
- `created_at`: String — ISO 8601 UTC timestamp (e.g., `2025-10-16T22:06:04.202593Z`).
- `canonical_refs_used`: Array of canonical reference objects — required even when empty (`[]`).

**Step-specific fields:**

- `$schema`: Must reference the URI above for the target toolkit version.
- `environments`: Object (not an array) mapping environment names to config objects. Must include all four keys: `dev`, `ci`, `staging`, `prod`. Each value is a key-value config map with environment-specific settings.
- `ci_gates`: Array of kebab-case CI gate identifier strings (minItems: 1, pattern: `^[a-z0-9-]+$`). Each must match a pipeline job name.

## Output Contract

The migrated artifact MUST include:

- `$schema`: Set to the canonical URI above.
- `canonical_refs_used`: Array of canonical reference objects.

## Optional Fields

- `_migration_notes`: Array of strings — migration annotations written exclusively by specdev tooling (canonical-autofix, align apply). Do NOT populate manually.
- `trace`: Array of trace reference objects linking this baseline to upstream capabilities or charter artifacts.
- `secrets`: Array of secret name strings (environment variable keys required at runtime).
- `compliance`: Array of compliance standard strings (e.g., `SOC2`, `GDPR`, `PCI-DSS`).
- `environment_ref`: Canonical reference (kind: `environment`) to the environment definitions.
- `command_ref`: Canonical reference (kind: `capability`) for the CI command.
- `policy_ref`: Canonical reference (kind: `risk_category`) for the compliance framework enforced.

## Validation

After migration, run:

```bash
./tools/run_specdev.sh spec-check spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
```

## Context

The delivery baseline anchors the implementation plan (Step 09) and roadmap
(Step 14). The `environments` field is an object keyed by environment name
(not an array) — convert any array format from older versions. Each environment
must have a separate key (`dev`, `ci`, `staging`, `prod`); only include config
keys whose values actually differ between environments. The `ci_gates` array
must use kebab-case identifiers matching actual CI pipeline job names — no
uppercase letters or spaces.


## Full Generation Reference

To generate this artifact from scratch (rather than migrate an existing one), use the canonical step prompt:

- `prompts/prompt_02a_delivery_baseline.md`

The generation prompt contains the complete Output Contract, Self-Audit Gate, and schema authority reference needed to produce a valid artifact.
