# Migration: Non-Functional Requirements (Step 07)

## Schema URI

`vc:07-nfrs`

## Required Changes

**Step-base fields (required in every artifact):**

- `id`: String — unique kebab-case identifier for this artifact instance (e.g., `nfrs-v1`). Convention: `{step-noun}-v{N}`.
- `owner`: String enum — must be one of `api | ui | system | ops | data | product | business | engineering`.
- `created_at`: String — ISO 8601 UTC timestamp (e.g., `2025-10-16T22:06:04.202593Z`).
- `canonical_refs_used`: Array of canonical reference objects — required even when empty (`[]`).

**Step-specific fields:**

- `$schema`: Must reference the URI above for the target toolkit version.
- `nfrs`: Array of NFR objects (minItems: 1). Each entry requires:
  - `nfr_id`: String matching pattern `^nfr-[a-z0-9]+-[a-z0-9-]+$` (e.g., `nfr-latency-api-response`).
  - `category`: Must be one of `latency | throughput | availability | durability | cost | security | privacy | maintainability | usability | portability | energy`.
  - `metric`: String — specific measurable dimension (e.g., `P95 response time for POST /auth/login`).
  - `target`: Number or string containing at least one digit (e.g., `< 200ms`).
  - `unit`: String using canonical abbreviations (`ms`, `percent`, `req/s`, `count`, `MB`, `GB`).
  - `metric_ref`: Canonical reference object (kind: `metric`) — required.
  - `unit_ref`: Canonical reference object (kind: `term`) — required; must be consistent with `unit`.
  - `environment_ref`: Canonical reference object (kind: `environment`) — required.
  - `measurement_method`: String describing the tool and metric collected.
  - `stage`: Must be one of `dev | ci | staging | prod`.
  - `owner`: Canonical owner enum (`api | ui | system | ops | data | product | business | engineering`).
  - `trace`: Array of trace reference objects (minItems: 1) — at least one must use `type: derives_from`.

## Output Contract

The migrated artifact MUST include:

- `$schema`: Set to the canonical URI above.
- `canonical_refs_used`: Array of canonical reference objects.

## Optional Fields

- `_migration_notes`: Array of strings — migration annotations written exclusively by specdev tooling (canonical-autofix, align apply). Do NOT populate manually.
- `nfrs[].name`: String (minLength: 2) — human-readable label for dashboards.
- `nfrs[].baseline`: Current measured value before optimization (number or string).
- `nfrs[].measurement_frequency`: One of `real-time | hourly | daily | weekly | monthly | per-release | on-demand`.
- `nfrs[].stage_ref`: Canonical reference (kind: `stage`) binding the `stage` value to the registry.

## Validation

After migration, run:

```bash
./tools/run_specdev.sh validate spec/07_nfrs.json --repo-root ./devspec_toolkit
```

## Context

NFRs define quality attributes and are referenced in the trace matrix alongside
FRs and fixtures. The field name `id` must be renamed to `nfr_id` and must
match the pattern `^nfr-[a-z0-9]+-[a-z0-9-]+$`. The fields `metric_ref`,
`unit_ref`, and `environment_ref` are now required on every entry — add them
using canonical IDs from `canon/manifest.json`. The `category` enum contains
11 specific values; map legacy `performance` to `latency` or `throughput`,
`reliability` to `availability` or `durability`. Verify all `nfr_id` values
referenced in fixtures (Step 08) still exist. Regenerate the trace matrix
after migration.


## Full Generation Reference

To generate this artifact from scratch (rather than migrate an existing one), use the canonical step prompt:

- `prompts/prompt_07_nfrs.md`

The generation prompt contains the complete Output Contract, Self-Audit Gate, and schema authority reference needed to produce a valid artifact.
