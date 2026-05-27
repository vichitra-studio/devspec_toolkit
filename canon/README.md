# Canon Registry

The canon registry is the shared vocabulary layer for the AI Spec Driven Development Toolkit. It provides stable, versioned term definitions that span all spec pipeline steps and prevent semantic drift across artifacts.

## Directory Structure

```
canon/
  manifest.json          # Flat registry of all active canon entries (source of truth)
  aliases.json           # Alias mappings for alternate term spellings
  aliases.schema.json    # JSON Schema for aliases.json
  kind.schema.json       # JSON Schema for individual kinds/ files
  kinds/                 # 25 per-kind JSON files (one per vocabulary kind)
```

`manifest.json` is the authoritative flat registry. The `kinds/` files are the editable source; `manifest.json` is regenerated from them.

## Namespace Convention

Canon entry IDs follow the pattern: `cn:<namespace>:<kind>:<label>`

### `cn:core:` — Toolkit-mechanical canons

Pre-populated and maintained by the toolkit team. These are stable, shared vocabulary that all spec pipelines use regardless of project domain.

- **Managed by**: toolkit team (`spec-platform` owner)
- **Contents**: owner values, trace types, pipeline stages, environments, units, NFR categories, governance labels, roles, etc.
- **Stability**: stable across toolkit versions; changes are versioned
- **Examples**:
  - `cn:core:owner:api` — artifact ownership domain
  - `cn:core:trace-type:implements` — traceability link type
  - `cn:core:stage:ci` — CI pipeline stage
  - `cn:core:unit:ms` — milliseconds unit

To add a new `cn:core:` entry, edit the relevant file in `canon/kinds/` and regenerate `manifest.json`.

### `cn:project:` — Pipeline-populated project canons

Populated during spec authoring, specific to each project. These terms come from the project's domain model.

- **Managed by**: spec authors via `specdev canon-accept`
- **Source**: `canonical_proposals` emitted by Step 03 (Glossary)
- **Contents**: domain entities, capabilities, project-specific actions, custom terms
- **Stability**: evolves with the project spec
- **Examples**:
  - `cn:project:entity:user` — project's user entity
  - `cn:project:capability:authenticate` — project authentication capability

Workflow: Step 03 (Glossary) emits `canonical_proposals` → run `specdev canon-accept` → entries land in the project's canon registry.

### `cn:starter:` — Example/demo canons

Used for auth-domain demo content, tutorial examples, and starter kits. Not for production specs.

- **Managed by**: toolkit team (demo content)
- **Contents**: illustrative entities, capabilities, and terms for tutorials
- **Stability**: may change between toolkit versions as demos evolve
- **Warning**: do NOT use `cn:starter:` IDs in production specs — they are illustrative only
- **Convention**: new demo/example entries should use `cn:starter:` namespace:
  - `cn:starter:entity:user` — demo user entity for tutorials
  - `cn:starter:capability:authenticate` — example auth capability

### Backward Compatibility: Auth Demo Entries

`canon/examples/auth_demo.json` is the canonical starter-kit example file. It currently contains **10 entries + 11 aliases (21 items total)**.

> **Note**: The entries in `canon/examples/auth_demo.json` currently use `cn:core:` namespace for backward compatibility. A future migration will move them to `cn:starter:`. New demo/example entries should use `cn:starter:` namespace.

| Kind | ID |
|------|----|
| capability | `cn:core:capability:authentication` |
| action | `cn:core:action:authenticate` |
| entity | `cn:core:entity:user` |
| event | `cn:core:event:login-succeeded` |
| dependency | `cn:core:dependency:auth-service` |
| acronym | `cn:core:acronym:jwt` (deprecated, replaced by term) |
| term | `cn:core:term:jwt` |
| risk_category | `cn:core:risk_category:authn` |
| risk_category | `cn:core:risk_category:authz` |
| risk_category | `cn:core:risk_category:data-privacy` |

`risk_category:data-privacy` is included as a general-purpose starter entry to show that a real auth product must account for data-handling risk beyond authn/authz concerns. It is not auth-specific but demonstrates multi-domain risk coverage in the starter kit.

**Why these IDs use `cn:core:` instead of `cn:starter:`**: These IDs were established before the `cn:starter:` namespace was introduced and are referenced by test fixtures in `tests/unit/test_cli.py`, `tests/unit/canonical/`, and `tests/unit/generation/test_schema_contracts.py`. Renaming them would break those fixtures without any semantic benefit. New tutorial/demo content added in future should use `cn:starter:` IDs as described above. The `auth_demo.json` file's `_description` field also documents this rationale inline.

## Checking the Registry

```bash
# Lint spec files for canonical term compliance
./tools/run_specdev.sh canonical-lint canon --repo-root ./devspec_toolkit

# Check integrity of spec references against the canon registry
./tools/run_specdev.sh canonical-integrity spec --repo-root ./devspec_toolkit

# Apply canonical corrections (dry-run first)
./tools/run_specdev.sh canonical-autofix spec --repo-root ./devspec_toolkit --dry-run
./tools/run_specdev.sh canonical-autofix spec --repo-root ./devspec_toolkit --write
```

## Adding a New `cn:core:` Entry

1. Open the relevant `canon/kinds/<kind>.json` file (e.g., `kinds/owner.json` for a new owner value).
2. Add a new entry object following the existing schema (id, kind, preferred_label, definition, version, status, owners, aliases, lifecycle).
3. Set `"owners": ["spec-platform"]` and `"status": "active"`.
4. Regenerate `manifest.json` from the kinds files.
5. Run `canonical-lint` to verify no regressions.

## How `cn:project:` Entries Are Created

1. Author Step 03 (Glossary) artifact — AI runner emits `canonical_proposals` in the JSON.
2. Review proposals, then run `specdev canon-accept` to promote them into the project's canon.
3. Entries are written with `cn:project:` prefix and tracked in the registry.
4. Downstream steps reference these entries by their canonical ID.

### Important Details

- **Project entries live only in `manifest.json`**: `cn:project:` entries are written directly to `manifest.json` by `canon-accept` and are NOT sourced from `kinds/` files. The `kinds/` files contain only `cn:core:` entries. If `manifest.json` is ever regenerated from `kinds/`, project entries must be preserved separately.

- **Aliases for project entries**: Aliases for `cn:project:` entries are not automatically created by `canon-accept`. To add aliases for project-scoped terms, manually edit `canon/aliases.json`. The `aliases` array on each manifest entry is also initially empty and can be populated manually.

- **Workflow ordering**: After emitting a glossary (Step 03), run `specdev canon-accept` to promote proposals **before** running `canonical-integrity` or `canonical-lint`, since anticipated `term_ref.id` values will not resolve until promotion.
