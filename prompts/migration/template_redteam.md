# Migration: Red Team / Threat Model (Step 11)

## Schema URI

`vc:11-redteam`

## Required Changes

- `$schema`: Must reference the URI above for the target toolkit version.
- `threats`: Array of threat objects; each needs `threat_id`, `description`, `severity`, `category`, `target_ids`, `mitigations`, and `risk_category_ref`.
- `threat_id` format: Must be kebab-case (e.g., `threat-unauth-api-access`).
- `category`: Must be one of the allowed enum values: `authn | authz | business_logic | transport | data_privacy`.
- `severity`: Must be one of `low | medium | high | critical`.
- `target_ids`: Array of trace refs; each entry must target a valid API or component ID from earlier steps.
- `mitigations`: Array of structured objects — each requires `type` and `id`; plain strings are not accepted.
- `mitigations[].type`: Must be one of `fr | api | nfr | inv | fixture | doc | capability`.
- `risk_category_ref`: Required canonical reference object on every threat entry.

## Output Contract

The migrated artifact MUST include:

- `$schema`: Set to the canonical URI above.
- `canonical_refs_used`: Array of canonical reference objects.
- `canonical_proposals`: Array (OPTIONAL).
- `canonical_conflicts`: Array (OPTIONAL).

## Optional Fields

- `_migration_notes`: String describing what changed during migration.
- `edge_cases`: Array of edge-case objects, each with `id` and `description`.
- `threats[].vector`: String describing the attack vector.
- `threats[].policy_ref`: Canonical reference to a policy entry.
- `trace`: Array of trace refs for top-level provenance.

## Validation

After migration, run:

```bash
./tools/run_specdev.sh validate spec/11_redteam.json --repo-root ./devspec_toolkit
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
