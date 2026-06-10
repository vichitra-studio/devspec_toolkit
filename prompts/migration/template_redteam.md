# Migration: Red Team / Threat Model (Step 11)

## Schema URI

`vc:11-redteam`

## Required Changes

**Step-base fields (required in every artifact)**

- `id`: Unique kebab-case identifier for this artifact instance (`$ref: vc:core:atoms#kebabId`).
- `owner`: Owner of this spec artifact. Must be one of: `api | ui | system | ops | data | product | business | engineering`.
- `created_at`: ISO 8601 timestamp of when this artifact was generated or last regenerated (`$ref: vc:core:atoms#timestamp`).
- `canonical_refs_used`: array of canonical reference objects used in this artifact

- `$schema`: Must reference the URI above for the target toolkit version.
- `threats`: Array of threat objects (minItems: 1). Each entry requires:
  - `threat_id`: kebab-case identifier (e.g., `threat-auth-token-forgery`).
  - `description`: String — names the entry point, attack technique, and attacker's gain.
  - `severity`: Must be one of `low | medium | high | critical`.
  - `category`: Must be one of `authn | authz | business_logic | transport | data_privacy`.
  - `target_ids`: Array of trace reference objects (minItems: 1) — each requires `type` and `id`; should reference valid spec artifact IDs from earlier steps (e.g., `api_id` from Step 05, `component_id` from Step 02, or `inv_id` from Step 06). Any valid spec artifact reference is accepted; API and component IDs are common examples but not the only allowed targets.
  - `mitigations`: Array of structured objects (minItems: 1) — each requires `type` and `id`; plain strings are not accepted. `type` must be one of `fr | api | nfr | inv | fixture | doc | capability`.
  - `risk_category_ref`: Canonical reference object (kind: `risk_category`) — required on every threat entry.

## Output Contract

The migrated artifact MUST include:

- `$schema`: Set to the canonical URI above.
- `canonical_refs_used`: Array of canonical reference objects.

## Optional Fields

- `_migration_notes`: Array of strings — migration annotations written exclusively by specdev tooling (canonical-autofix, align apply). Do NOT populate manually.
- `edge_cases`: Array of edge-case objects, each with `id` and `description`.
- `threats[].vector`: String describing the attack vector.
- `threats[].policy_ref`: Canonical reference to a policy entry.
- `trace`: Array of trace refs for top-level provenance.

## Validation

After migration, run:

```bash
./tools/run_specdev.sh spec-check spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
```

## Context

The red team artifact is the primary threat model for the system. It traces
threats back to APIs and components defined in earlier steps. During migration,
the most common breaking change is `mitigations` being restructured from a flat
string array to an array of typed objects — convert each plain string into an
object with `type` and `id` fields. The `target_ids` field uses trace ref objects
(not bare strings); update any bare-string entries accordingly. Threat IDs are
referenced by downstream CI gates (Step 12) and governance checks, so preserve
them during migration. Validate all `risk_category_ref` values against the
canonical registry before committing.


## Full Generation Reference

To generate this artifact from scratch (rather than migrate an existing one), use the canonical step prompt:

- `prompts/prompt_11_redteam.md`

The generation prompt contains the complete Output Contract, Self-Audit Gate, and schema authority reference needed to produce a valid artifact.
