## [unreleased]

### Breaking Changes

- DEVSPEC-38: removed the `status_ref` field from 21 schema properties (under
  `additionalProperties: false`); host specs carrying `status_ref` become
  schema-invalid and must migrate. See the Migration section below.

- DEVSPEC-89: added E590 cross-reference enforcement for all step-11 mitigation
  IDs against upstream steps 01/04/05/06/07/08; added W615/E615
  `INVARIANT_UNEXERCISED_BY_THREAT` invariant-coverage warning (promotable).
  Host specs with stale/invented mitigation IDs or net-new `type: capability`
  controls will newly fail `spec-check`; remediate by referencing existing
  upstream artifacts or switching net-new controls to `type: doc`. The fixes
  are spec edits an AI agent can assist with — see the DEVSPEC-89 Migration
  section below.

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

- **DEVSPEC-91: incorrect W→E promotions removed (`W597 → E597`, `W590 → E590`).**
  Removed two entries from `PROMOTABLE_PAIRS` in `core/errors.py` where the
  warning and its same-numbered error describe structurally different defects,
  so promotion mislabelled the problem and pointed users at the wrong fix:
  - `W597` (`EXTRACTION_INTENT_VAGUE` — a present intent entry whose text is too
    short/weaselly) vs. `E597` (`EXTRACTION_INTENT_UPSTREAM_GAP` — a required
    upstream artifact has no intent entry at all).
  - `W590` (`CROSS_STEP_UPSTREAM_MISSING` — the upstream artifact file is absent)
    vs. `E590` (`CROSS_STEP_ID_NOT_FOUND` — a referenced ID is absent from a
    *present* upstream file).

  Under `SPECDEV_WARNINGS_AS_ERRORS=1` (or a matching `SPECDEV_PROMOTE_CODES`)
  these now stay warnings; neither has a semantically-correct fatal counterpart
  (a fatal "upstream missing" would need a dedicated new E-code). Also removed a
  dead backtick-formatted extraction-intent entry in `prompt_15_scaffold.md`
  that the parser never read (step 14 stays covered by its bold entry).

- **`SPECDEV_PROMOTE_CODES` now warns on ignored codes.** When the variable lists
  a code that is not promotable — a valid-but-non-promotable warning (e.g.
  `W590`/`W597`) or an unrecognised/typo code — `validate-all` and `spec-check`
  now print a one-time stderr warning that the code will be ignored, instead of
  silently dropping it. (The warning is suppressed under
  `SPECDEV_WARNINGS_AS_ERRORS=1`, which ignores `SPECDEV_PROMOTE_CODES` wholesale.)

- **`spec-check` now honours W→E promotion in its per-check results.** Previously
  `run_spec_check` / `run_spec_check_json` classified and returned each check's
  errors *before* applying promotion, so under `SPECDEV_WARNINGS_AS_ERRORS=1` (or a
  matching `SPECDEV_PROMOTE_CODES`) a check whose only errors were promotable
  W-codes still reported `WARN` and emitted W-prefixed codes in the JSON `findings`
  and the aggregate. All per-check results now flow through a single
  promote-then-classify path, so the per-check status, the stderr breakdown, and the
  JSON codes consistently reflect the active promotion contract. Because `spec-check`
  is the authoritative gate (core rule #1), this can make it intentionally stricter
  than bare `validate-all` — e.g. on promotable traceability-closure warnings, which
  `validate-all` drops before promotion.

- **Deprecated `datetime.utcnow()` in schema-diff timestamping.** `_get_timestamp()`
  in `schema_differ.py` now uses timezone-aware `datetime.now(timezone.utc)`
  (output format unchanged). Silences the Python 3.13 deprecation warning.

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

- **Two duplicate test files removed** (lossless — coverage preserved by the
  surviving tests): `tests/unit/core/test_r9_error_codes.py` (byte-identical to
  `tests/unit/core/test_error_code_registry.py`) and
  `tests/unit/validation/test_r9_validate.py` (a redundant, less-isolated
  near-duplicate of `tests/unit/validation/test_validate_deep.py`). Removed during
  P2 audit remediation; the R9 error-code-registry and W→E promotion coverage they
  exercised continues to run in the retained files.

---

DEVSPEC-38 — Remove `status_ref` from the spec data model; retire the `status`
canon kind; add deterministic milestone-state engine.

> **Versioning note (D4):** this change removes a schema field under
> `additionalProperties: false` — a semver-breaking change. It is consciously
> landing in version 1.0.1 (on the `1.0.1_bug_fixes` branch) rather
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
  optional-field lists. The same pass also corrected three pre-existing
  schema-accuracy drifts in these templates (independent of the `status_ref`
  removal):
  - `template_frs.md`: `functional_requirements` `minItems` corrected `1 → 2`
    to match `schema/04_fr_list.schema.json`.
  - `template_invariants.md`: `policy_ref` kind corrected `risk_category →
    policy` to match `schema/06_invariants.schema.json` (the sibling
    `rules[].risk_category_ref`, kind `risk_category`, is intentionally unchanged).
  - `template_impl_plan.md` and `template_roadmap.md`: `tech_stack_ref` kind
    corrected `capability → tech_stack` to match `schema/09_impl_plan.schema.json`
    and `schema/14_roadmap.schema.json`.

- **All 22 migration templates** normalized their post-migration validation step
  from a per-file `./tools/run_specdev.sh validate spec/NN_*.json --repo-root
  ./devspec_toolkit` invocation to the unified `spec-check spec --repo-root
  ./devspec_toolkit --spec-root ./spec --git-root .` form — matching core rule #1
  (use `spec-check`, which resolves project canon, rather than bare `validate`).

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
`specdev spec-check` by performing the following steps:

1. Delete every `status_ref` object from all spec artifacts.
2. Remove now-orphaned `cn:*:status:*` IDs from each file's `canonical_refs_used[]`.
3. Run `specdev spec-check spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root .`
   to confirm clean.

---

DEVSPEC-89 — Cross-reference enforcement for step-11 mitigation IDs; W615/E615
invariant-coverage warning; prompt and step_order alignment.

> **Versioning note:** this change adds new hard E590 enforcement and a W615
> warning with promotable E615 — spec-check will newly fail on host specs
> with stale/invented mitigation IDs or net-new `type: capability` controls.
> Breaking in the same sense as DEVSPEC-38 (single private host; cost is near
> zero; consciously recorded).

### Added

- **W615 / E615 `INVARIANT_UNEXERCISED_BY_THREAT`** — new warning (promotable
  via `SPECDEV_WARNINGS_AS_ERRORS=1` or `SPECDEV_PROMOTE_CODES=W615`) fired
  when a step-06 invariant carries a `risk_category_ref` but no step-11 threat
  mitigation of `type: inv` references it.  The `risk_category_ref` field is
  the discriminator; invariants without it are not checked.

- **E590 mitigation cross-reference enforcement** — `validate_step_11` now
  cross-references mitigation IDs against their source step for all mitigation
  types except `doc`: `capability` → step 01 (`capabilities[].capability_id`),
  `fr` → step 04, `api` → step 05, `inv` → step 06, `nfr` → step 07,
  `fixture` → step 08.  When the upstream file is absent the check is skipped
  (guard: `None` ≠ empty set).  `doc` mitigations remain exempt from all
  cross-reference validation.

- **Matrix `invariant_threat_coverage` output** — `specdev matrix` emits an
  `invariant_threat_coverage` map (`inv_id → [threat_ids]`) derived from
  step-11 mitigations of `type: inv`.

### Changed

- **`target_ids` schema description** updated to reflect that only `api` and
  `component` are valid threat-target types (no `fr` or `inv`; description-only
  change, no schema structure change).

- **`prompt_11_redteam.md` guidance** updated: net-new controls with no existing
  upstream artifact now use `type: doc` (exempt from cross-reference); `type:
  capability` is reserved for referencing an EXISTING `cap-*` ID from Step 01.
  Coverage Closure, Mitigate step, and examples updated accordingly.

- **`step_order.json`** — added `"01"` and `"08"` to
  `step_metadata["11"].required_spec_inputs` (ascending order: 01,02,04,05,06,07,08);
  added `"11"` to `downstream_consumers["01"]` and `downstream_consumers["08"]`.

### Fixed

- **`validate_step_11` fails soft on malformed `threats[]` / `target_ids[]`
  entries.** Non-dict entries in those arrays now emit a structured `E520`
  (mirroring the existing mitigation-object guard) instead of raising an
  unhandled `AttributeError`. Post-audit (P2) robustness hardening.

### Migration

Host specs with step-11 artifacts must be reviewed before running `specdev spec-check`:

1. Replace any mitigation with `type: capability` and an invented `cap-*` ID with
   `type: doc` (and a descriptive `note`) unless `cap-*` is an existing ID in
   `spec/01_capabilities.json`.
2. Verify all other mitigation IDs (`fr`, `api`, `nfr`, `inv`, `fixture`) reference
   IDs that exist in their respective upstream spec files.
3. For every step-06 invariant with `risk_category_ref`, ensure at least one
   threat mitigation of `type: inv` references it (or suppress W615 with
   `SPECDEV_PROMOTE_CODES` if coverage is intentionally deferred).
4. Run `specdev spec-check spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root .`
   to confirm clean.

**AI-assisted migration path:** E590 remediation is a spec-content edit, not a
schema-structure migration, so `specdev align` does not detect or fix it (align
diffs schema shape, while E590 is a cross-step ID-resolution error from the
step-11 validator). Instead, the manual steps above are well-suited to an AI
coding agent: point it at the `spec-check` E590/W615 output and have it update
the offending mitigation IDs (or switch net-new controls to `type: doc`) against
the upstream artifacts loaded via the `/specdev-context` skill, then re-run
`spec-check` to confirm clean. This is the `ai_assisted` migration action
recorded in `changelog/unreleased.yaml`.

---

DEVSPEC-87 — `specdev update` command: a single post-submodule-bump entry point
that re-stamps or routes specs through migration.

### Added

**CLI**
- `specdev update <spec_dir> --repo-root <toolkit>` — primary post-submodule-bump
  entry point. Re-stamps `spec/specdev_version` instantly when no structural schema
  changes are present; directs through the `specdev align` flow
  (`apply --auto` → optionally `prompts` → `validate`) when schema migration is
  required, exiting 1 so CI catches un-migrated specs. Supports `--dry-run` and
  `--json` output modes. (DEVSPEC-87)

### Changed

- `spec_check` E608 messages now direct users to `specdev update` instead of
  `specdev align` directly. (DEVSPEC-87)
- `stamp_specdev_version` extracted from `validate_post_migration` into
  `schema_differ.py` as a shared helper. Plain re-stamps (`is_migration=False`)
  preserve `last_migration` and never add a `migration_history` entry; migration
  stamps (`is_migration=True`, called only by `align validate`) append a history
  entry and update `last_migration`. (DEVSPEC-87)
