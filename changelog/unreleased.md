## [unreleased]

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
