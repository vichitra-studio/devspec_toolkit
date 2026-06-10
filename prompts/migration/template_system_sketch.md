# Migration: System Sketch (Step 02)

## Schema URI

`vc:02-system-sketch`

## Required Changes

**Step-base fields (required in every artifact):**

- `id`: String — unique kebab-case identifier for this artifact instance (e.g., `system-sketch-v1`). Convention: `{step-noun}-v{N}`.
- `owner`: String enum — must be one of `api | ui | system | ops | data | product | business | engineering`.
- `created_at`: String — ISO 8601 UTC timestamp (e.g., `2025-10-16T22:06:04.202593Z`).
- `canonical_refs_used`: Array of canonical reference objects — required even when empty (`[]`).

**Step-specific fields:**

- `$schema`: Must reference the URI above for the target toolkit version.
- `components`: Array of component objects (minItems: 1). Each entry requires:
  - `component_id`: kebab-case identifier (e.g., `api-gateway`, `user-service`).
  - `type`: Must be one of `service | db | queue | cache | job | ui | lib | external`.
  - `responsibilities`: Array of strings (minItems: 3, maxItems: 6) — present-tense action phrases.
  - `owner`: Canonical owner enum (`api | ui | system | ops | data | product | business | engineering`).
  - `trace`: Array of trace reference objects (minItems: 1) — each requires `type` and `id`.
- `connections`: Required when 2 or more components exist (minItems: 1). Each entry requires:
  - `from`: kebab-case component_id of the source.
  - `to`: kebab-case component_id of the destination.
  - `protocol`: Must be one of `http | grpc | event | db | file`.
  - `trust_boundary`: Must be one of `internal | partner | public`.
  - `trace`: Array of trace reference objects (minItems: 1).
  - When `trust_boundary` is `partner` or `public`: `auth` and `rate_limit` are also required.
  - When `protocol` is `event`: `reliability` is also required.

## Output Contract

The migrated artifact MUST include:

- `$schema`: Set to the canonical URI above.
- `canonical_refs_used`: Array of canonical reference objects.

## Optional Fields

- `_migration_notes`: Array of strings — migration annotations written exclusively by specdev tooling (canonical-autofix, align apply). Do NOT populate manually.
- `components[].tags`: Array of enum strings from the approved tag vocabulary (e.g., `critical-path`, `stateful`, `pii`).
- `components[].entity_ref`: Canonical reference (kind: `entity`) for the primary domain entity this component owns.
- `connections[].schema_ref`: Reference to the interface schema (pattern: `file://`, `https://`, `glossary:`, `api:`, or `-tbd`).
- `connections[].rate_limit`: **Conditionally required** — must be present when `trust_boundary` is `partner` or `public` (enforced by schema `if/then`). Object with `rps` (integer, 1–100000) and `scope` (`ip | client | token | global`) required; `burst` and `window_s` optional. Omit only for `internal` trust boundary connections where back-pressure is not needed.
- `connections[].reliability`: Must be one of `best-effort | at-least-once | exactly-once` (required for event connections).
- `connections[].interface_ref`: Canonical reference (kind: `entity`) for the named interface contract.
- `connections[].event_ref`: Canonical reference (kind: `event`) for the event type (required when `protocol` is `event`).

## Validation

After migration, run:

```bash
./tools/run_specdev.sh spec-check spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
```

## Context

The system sketch defines the architectural topology. Component IDs
(`component_id`) are referenced by interface contracts (Step 05), invariants
(Step 06), and the implementation plan (Step 09). Rename any legacy `id` field
to `component_id`. The schema no longer uses `name` as a required field —
human-readable labels come from `responsibilities`. Connections between 2+
components are required; if no `connections` array exists, add at least one.
For external components (`type: external`), the tag `external-dependency` is
required in `tags`.


## Full Generation Reference

To generate this artifact from scratch (rather than migrate an existing one), use the canonical step prompt:

- `prompts/prompt_02_system_sketch.md`

The generation prompt contains the complete Output Contract, Self-Audit Gate, and schema authority reference needed to produce a valid artifact.
