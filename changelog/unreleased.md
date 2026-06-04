## [unreleased]

### Breaking Changes

- DEVSPEC-38: removed the `status_ref` field from 21 schema properties (under
  `additionalProperties: false`); host specs carrying `status_ref` become
  schema-invalid and must migrate. See the host migration guide
  (`WIP/migration/DEVSPEC-38_host_migration.md`).

DEVSPEC-37 — schema-aware `json` writes, `_effective_schema` fix, and merge
consolidation.

### Added

- **`vc:canon:command-prefixes` schema** (`canon/command_prefixes.schema.json`)
  for the `command_prefixes.json` allowlist. Registered in
  `tools/schema_registry.json`. The toolkit's `tools/command_prefixes.json`
  gains a `$schema` key. This ensures the new mandatory schema-validation
  invariant does not block the E530 remediation flow, which emits
  `specdev json insert` commands targeting `command_prefixes.json`.

- **`specdev json insert --create-schema <uri>`** bootstrap flag. When the
  target file does not exist and `--create-schema` is given, the command seeds
  the file with `{"$schema": "<uri>"}` and bootstraps the missing array-valued
  field, then runs the standard differential validation against the seed. This
  closes the first-use gap where E530 remediation on a project with no existing
  `spec/canon/command_prefixes.json` would previously error with
  `File not found`.

- **`core/schema_nav.py`** — new canonical `effective_schema` helper
  consolidating three previously independent schema-property-merge
  implementations (`_effective_schema`, `merge_allof`, `_get_all_properties`).
  Injection of `resolve_ref` keeps Separation of Concerns; `include_conditionals`
  flag is OFF by default (behavior byte-preserved for existing callers) and ON
  only for `specdev json schema` discovery. Companion module
  **`core/schema_validate.py`** factors the schema-layer validation logic shared
  by `validate_file` and the new write constraint.

### Changed

- **Implicit differential schema validation on `json patch` and `json insert`.**
  Every write is now validated before it lands. The file's own `$schema` URI
  drives schema selection — the step-16 multi-schema disambiguation that broke
  the old opt-in flag is not an issue here. A write is refused only when it
  *introduces* a new schema violation (differential before/after diff), so
  incremental one-patch-at-a-time repair workflows are not deadlocked. Writes
  are also refused when the file carries no `$schema` or when the write targets
  the `$schema` key itself. No `--no-validate` CLI bypass is exposed. Bare agent
  invocations (no `--repo-root`) resolve the toolkit root via a package-relative
  fallback so the constraint holds in submodule/host deployments automatically.

### Fixed

- **`specdev json schema` / `_effective_schema` now navigates step-specific and
  conditional-gated fields.** Previously, the allOf merge overwrote a node's own
  `properties` with the properties gathered from `allOf` branches, discarding
  all step-specific fields on any node that combined own properties with an
  `allOf`. This made `specdev json schema` unable to navigate to `.plan`,
  `.execution`, `.review`, or any other step-specific key on step-16
  impl-context plan files (and similarly for other steps). The fix resolves
  properties own-first and also unions properties from `oneOf`/`anyOf`/
  `if-then-else` conditional branches for discovery, making fields such as
  `plan.docs.required_updates` navigable. The false claim in the docstring
  that conditional branches "never add navigable properties" is corrected.

- **`specdev validate` / `spec-check` (and the new `json` write guard) now
  fail closed on all `registry.load` I/O errors, not just `FileNotFoundError`.**
  Previously, `validate.py` only caught `FileNotFoundError`; `PermissionError`
  and other `OSError`s escaped uncaught. The new `core/schema_validate.py`
  helper catches the full `OSError` family and routes every case to
  `SchemaNotFoundError` → E520 `schema_not_found`. The E520 message format is
  unchanged; only the set of caught exception types is wider.

### Removed

- **`--against-schema-field` flag** removed from `specdev json patch` and
  `specdev json insert`. The flag was broken (wrong schema selected for
  multi-schema steps such as step 16; top-level-only resolution could not
  reach any nested or leaf write), structurally inadequate, and universally
  unused by agents. The associated internals (`validate_against_schema_field`,
  `_find_schema_file`) are deleted. The `specdev-context` SKILL.md mandate for
  the flag is replaced with a note that validation is now automatic.

---

DEVSPEC-38 — Remove `status_ref` from the spec data model; retire the `status`
canon kind; add deterministic milestone-state engine.

> **Versioning note (D4):** this change removes a schema field under
> `additionalProperties: false` — a semver-breaking change. It is consciously
> landing on the `1.0.1_bug_fixes` branch and staying at version 1.0.0 rather
> than bumping to 2.0.0. There is a single private host repo with no external
> consumers, so the breaking-change cost is near zero. The host migration is
> mandatory; see the migration guide referenced below.

### Added

- **`specdev milestone-state` CLI command** — deterministic per-milestone phase-position
  computation for the Trinity loop. Reads `spec/impl_context/ms_<batch-id>_plan.json`,
  probes `.specdev/findings/` under the host git root, and emits a single JSON object
  (`milestone_id`, `groups[]`, `derived_phase_position`, `blockers[]`) to stdout.
  This replaces the LLM-evaluated `milestone_state` mode of the `specdev-scope` agent,
  which now delegates to this command (D7/D7a). Benefits over the previous approach:
  deterministic and unit-testable; removes macOS/Linux `stat`/`date` shell branches;
  heuristic results are consistent run-to-run. See `docs/developers/reference.md` for
  the full flag reference and output contract.

### Changed

- **`specdev-scope` agent `milestone_state` mode** now delegates to `specdev milestone-state`
  and passes its output through unchanged. The orchestration contract is identical;
  `specdev-trinity` skill parsing is unaffected.

- **Trinity `verified`/`closed` transition keyed on `implementation.status` string only.**
  The dual-gate ("both `status` string and `status_ref.id` required") is removed from
  `specdev-trinity-impl.md`. Setting `implementation.status = "verified"` is sufficient
  to advance a group and close a milestone. This was already the de-facto state on the
  host (status string and ref agreed for all 240 impl objects).

- **Emergent-ambiguity optional-field lists** in `specdev-trinity-impl.md` and
  `specdev-trinity-reviewer.md` drop `status_ref`.

- **Prompts updated:** `prompt_06_invariants.md` and `prompt_16a_impl_planner.md`
  remove instructions to populate `status_ref`.

- **Migration templates** (`template_frs.md`, `template_invariants.md`,
  `template_impl_plan.md`, `template_roadmap.md`) drop `status_ref` from their
  optional-field lists.

### Removed

- **`status_ref` canonical-reference field removed from 21 schema properties** across
  six files: `schema/04_fr_list.schema.json` (1), `schema/06_invariants.schema.json` (1),
  `schema/09_impl_plan.schema.json` (1), `schema/14_roadmap.schema.json` (2),
  `schema/16_impl_context.schema.json` (15), and `schema/core/collections.schema.json` (1).
  All affected schemas use `additionalProperties: false`, so host spec files carrying
  `status_ref` will fail validation and must be migrated.

- **Canon `status` kind retired** (`canon/kinds/status.json`, 7 entries:
  `active`, `blocked`, `deferred`, `green`, `pending`, `red`, `verified`).
  The `status` string enums in the affected schemas are now the single source of truth
  for status vocabulary. Retired alongside:
  - 7 status aliases removed from `canon/aliases.json`
    (`approved→verified`, `fail→red`, `failed→red`, `not started→pending`,
    `pass→green`, `passed→green`, `postponed→deferred`)
  - 14 `kind: "status"` entries removed from `canon/manifest.json`
    (7 canonical entries + 7 mirrored alias entries)

  This resolves the titular enum↔label divergence reported in DEVSPEC-38: the
  milestone-lifecycle status enums (`in_progress`, `done`, `needs_work`) and the
  health/CI canon labels (`active`, `green`, `red`) were never the same vocabulary.
  Retiring the canon kind removes the second vocabulary entirely.

- **Dead Python status machinery removed:** `INFERENCE_RULES` status rule
  (`core/constants.py`), `alias_value_fields["status_ref"]` (`canonical/integrity.py`),
  and `"status"` from `_FALLBACK_DIRECT_FIELDS` (`canonical/integrity.py`).

### Migration

Host repositories carrying `status_ref` in spec artifacts must migrate before running
`specdev spec-check`. Full migration steps are in
[`WIP/migration/DEVSPEC-38_host_migration.md`](../WIP/migration/DEVSPEC-38_host_migration.md):

1. Delete every `status_ref` object from all spec artifacts.
2. Remove now-orphaned `cn:*:status:*` IDs from each file's `canonical_refs_used[]`.
3. Run `specdev spec-check spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root .`
   to confirm clean.
