# Migration: Interface Contracts (Step 05)

## Schema URI

`vc:05-interface-contracts`

## Required Changes

**Step-base fields (required in every artifact):**

- `id`: String — unique kebab-case identifier for this artifact instance (e.g., `interface-contracts-v1`). Convention: `{step-noun}-v{N}`.
- `owner`: String enum — must be one of `api | ui | system | ops | data | product | business | engineering`.
- `created_at`: String — ISO 8601 UTC timestamp (e.g., `2025-10-16T22:06:04.202593Z`).
- `canonical_refs_used`: Array of canonical reference objects — required even when empty (`[]`).

**Step-specific fields:**

- `$schema`: Must reference the URI above for the target toolkit version.
- `apis`: Array of API contract objects (minItems: 1). Each entry requires:
  - `api_id`: kebab-case identifier; `api-` prefix recommended (e.g., `api-user-auth`, `api-session-create`).
  - `name`: Human-readable endpoint name (e.g., `Create User Session`).
  - `version`: String matching pattern `^v\d+(?:\.\d+)*$` (e.g., `v1`, `v2.1`).
  - `protocol`: Must be one of `http | grpc | ws | mqtt`.
  - `owner`: Canonical owner enum (`api | ui | system | ops | data | product | business | engineering`).
  - `interface_ref`: Canonical reference object (kind: `interface`) — required.
  - `scope`: Must be one of `in | later | out`; `later` and `out` also require `scope_reason`.
  - `derives_from`: Array of functional requirement ids (minItems: 1) that this API implements.

## Output Contract

The migrated artifact MUST include:

- `$schema`: Set to the canonical URI above.
- `canonical_refs_used`: Array of canonical reference objects.

## Optional Fields

- `_migration_notes`: Array of strings — migration annotations written exclusively by specdev tooling (canonical-autofix, align apply). Do NOT populate manually.
- `apis[].path`: URL path string (omit for non-HTTP protocols).
- `apis[].method`: HTTP method — one of `GET | POST | PUT | PATCH | DELETE` (omit for non-HTTP).
- `apis[].security`: Auth mechanism — one of `none | jwt | oauth2 | api-key | mTLS`.
- `apis[].input_schema_ref`: Relative path to request body JSON Schema file (use `-tbd` as placeholder).
- `apis[].output_schema_ref`: Relative path to response body JSON Schema file (use `-tbd` as placeholder).
- `apis[].errors`: Array of error objects, each requiring `error_id` (kebab-case), `code` (kebab-case), `message`, `scope` (`in | later | out`) and `derives_from` (ids of acceptance criteria, minItems: 1); `severity` (`info | warn | error | fatal`) is optional, and `scope_reason` is required when `scope` is `later` or `out`.
- `apis[].parameters`: Array of parameter objects, each requiring `name`, `in` (`query | path | header`), and `required` (boolean).
- `apis[].provided_by`: Array of component ids that provide this API.
- `apis[].relies_on`: Array of third-party ids this API relies on.
- `apis[].event_ref`: Canonical reference (kind: `event`) for events emitted or consumed.
- `apis[].entity_ref`: Canonical reference (kind: `entity`) for the primary domain entity.
- `apis[].policy_ref`: Canonical reference (kind: `policy`) for access control policy.
- `apis[].enum_provenance`: Object required whenever a parameter declares `enum`; needs `source_url`, `source_date`, and `resolved_at`.

## Validation

After migration, run:

```bash
./tools/run_specdev.sh spec-check spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
```

## Context

Interface contracts define the API surface. The top-level array field is `apis`
(not `interfaces`) — rename accordingly. Each entry requires `interface_ref` as
a canonical object (not a bare string). The `method` field accepts only
`GET | POST | PUT | PATCH | DELETE` (not OPTIONS or HEAD — those are scaffold-only);
ensure no lowercase or non-standard HTTP verbs remain. Duplicate `interface_ref`
values will cause Step 15 (scaffold) validation failures. Each API must list at least one FR in
`derives_from`. Step 08 fixtures reference the API from the fixture side, so
there is no fixture list to maintain on the API.


## Full Generation Reference

To generate this artifact from scratch (rather than migrate an existing one), use the canonical step prompt:

- `prompts/prompt_05_interface_contracts.md`

The generation prompt contains the complete Output Contract, Self-Audit Gate, and schema authority reference needed to produce a valid artifact.
