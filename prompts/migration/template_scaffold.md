# Migration: Scaffold (Step 15)

## Schema URI

`https://specdev.local/schema/15_scaffold.schema.json`

## Required Changes

- `$schema`: Must reference the URI above for the target toolkit version.
- `service_skeleton`: Object with at least `language` (lowercase/kebab-case string).
- `route_map`: Array of route objects; each needs `api_ref`, `path`, and `method`.
- `route_map[].api_ref`: Must be a kebab-case ID matching a defined API in Step 05; no duplicates.
- `route_map[].method`: Must be one of `GET | POST | PUT | DELETE | PATCH | OPTIONS | HEAD`.
- `validators`: Array of validator strings; required to be non-empty when `build_status` is `green`.
- `build_status`: Must be one of `pending | green | red`.

## Output Contract

The migrated artifact MUST include:

- `$schema`: Set to the canonical URI above.
- `generation_quality`: Object with `assumptions` array.
- `canonical_refs_used`: Array of canonical reference objects.
- `canonical_proposals`: Array (may be empty).
- `canonical_conflicts`: Array (may be empty).

## Optional Fields

- `_migration_notes`: String describing what changed during migration.
- `service_skeleton.framework`: String for the web framework (lowercase/kebab-case).
- `service_skeleton.modules`: Array of module name strings.
- `route_map[].interface_ref`: Canonical reference to an interface protocol entry.
- `command_ref`: Canonical reference to the scaffold build command.
- `trace`: Array of trace refs for provenance.
- `links`: Array of link objects pointing to generated code or docs.

## Validation

After migration, run:

```bash
./tools/run_specdev.sh validate spec/15_scaffold.json --repo-root ./devspec_toolkit
```

## Context

The scaffold artifact maps interface contracts (Step 05) onto a concrete
service skeleton that the Trinity Loop (Steps 16a–16c) iterates over. The
`route_map` must have one entry per API defined in Step 05 — add or remove
entries to stay in sync after any interface changes. Duplicate `api_ref` values
are rejected by the validator. If `build_status` is `green`, at least one
validator must be listed; downgrade to `pending` during migration if validators
have not yet been confirmed. The `service_skeleton.language` and `framework`
values drive code generation in Step 16b, so ensure they accurately reflect the
target tech stack from `seed_tech_stack.md`.
