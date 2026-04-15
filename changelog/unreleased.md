# [Unreleased]

## Summary

Completes the 4-Layer Determinism Closure: cross-step ID validation, DAG integrity enforcement, content derivation checks, dynamic W→E promotion, and Extraction Intent sections across all prompts.

## Added

### Trinity Anchor Schema Split (Phase 2 — anchor hardening)

- **`vc:16-anchor` schema** (`schema/16_anchor.schema.json`): dedicated schema for the Step 16 Trinity Anchor artifact (`spec/16_impl_context.json`). Requires `artifact_role: "anchor"`, `plan.summary`, `plan.ambiguities`, `plan.drift`, and `plan.milestone_index`. Forbids `execution` and `review` via `unevaluatedProperties: false` — these sections belong only to milestone plans (16a/16b/16c).
- **`step_16_anchor` validator** (`validation/validators/step_16_anchor.py`): cross-milestone drift detection.
  - **E308 ANCHOR_SCOPE_DRIFT**: bidirectional scope contradiction (milestone `scope_in` ∩ anchor `scope_out`, or reverse) and FR ownership conflict (same FR active in two simultaneous milestones).
  - **E309 ANCHOR_CHECKLIST_DRIFT**: same checklist `id` maps to different `spec_ref.id` across milestone context files.
  - **W580 ANCHOR_DRIFT_SKIP**: guard for routing errors or missing spec_path.
- **Routing fix** (`validation/validate.py`): files in `impl_context/` now route to step `"16a"` (milestone plans); `16_impl_context.json` at the spec root routes to step `"16"` (anchor). Fixes long-standing routing bug where every impl_context artifact silently used the base validator.
- **E306 path fix** (`validation/validators/step_16.py`): when an artifact lives in `impl_context/`, `04_fr_list.json` is now resolved from the parent spec directory instead of from `impl_context/` itself.
- **`prompt_schema_sync` step-key collision fix**: `16_anchor.schema.json` and `16_impl_context.schema.json` both derive step `"16"` via filename split; the anchor now gets a distinct `"16anchor"` step key, and `_PROMPT_STEP_OVERRIDE` maps `prompt_16_impl_context.md` to validate against the anchor schema.
- **Fixture reorganization**: `tests/fixtures/step_16/impl_context/` holds all 17 milestone-plan fixtures; 4 new anchor fixtures live at the root of `tests/fixtures/step_16/`.
- **14 new anchor integration tests** (`tests/integration/test_step_16_anchor.py`): schema pass/fail, E308 scope contradiction and FR ownership, E309 checklist drift, W580 guard paths.

### Phase 1 — Seed & Spec Dependency Hardening

- **`seedRef` / `seedRefArray`** (`schema/core/collections.schema.json`): new reusable type with `seed_id` (required) plus optional `hash` (SHA-256) and `version` for drift detection against seed content changes.
- **`specRefIngested` / `specRefIngestedArray`** (`schema/core/collections.schema.json`): new reusable type recording `{step_id, artifact_id, hash?}` so downstream artifacts can declare which upstream artifacts they were derived from.
- **`spec_refs_ingested` and `seed_refs_ingested`** (`schema/core/step_base.schema.json`): optional properties inherited by all 20 step schemas composed via `allOf` — no per-step changes required.
- **`seed_manifest` optional `hash` and `version` fields** on each seed entry — populated by `seed-index` tooling for integrity tracking.
- **`step_metadata` block in `tools/step_order.json`** (schema-validated): for all 22 steps, declares `required_spec_inputs` (inverse of `downstream_consumers`), `required_seed_inputs` (mirror of seed manifest step_requirements), and a one-line `extraction_intent` summary. Prevents drift between forward/reverse DAG views.
- **`_lint_step_metadata_consistency`** (`validation/dependency_order_lint.py`): new consistency validator that rejects any `step_metadata.required_spec_inputs` that is not the exact inverse of `downstream_consumers`. Emits E540 STEP_METADATA_INCONSISTENT.
- **4 new unit tests** for the consistency linter (absent/consistent/missing/extra cases).

### R9 Validator & CI Enforcement

- **8 cross-step validators enhanced** (steps 05, 06, 08, 09, 12, 13, 13a, 15): each now loads upstream artifacts and validates referenced IDs exist. E590 CROSS_STEP_ID_NOT_FOUND when a ref is broken; W590 CROSS_STEP_UPSTREAM_MISSING when the upstream file is absent.
- **`extraction_intent_check` validator**: validates prompt `### Extraction Intent` sections against derived allowed upstream steps (computed from the `steps` array in step_order.json via `derive_allowed_upstream()`). Error codes: E591, E597, E598, W597.
- **`dag_lint` validator + CLI command**: validates DAG completeness in step_order.json. Error codes: E596 (dead-end producer), E599 (consumer inconsistency), E585 (circular dependency), W596 (undeclared upstream ref).
- **`spec_quality_lint` expanded**: vague language scanning now covers all 12 free-text fields (was assumptions-only). W593 VAGUE_LANGUAGE_FREE_TEXT for non-assumption matches; 8 new vague terms added.
- **`hallucination_lint` content derivation check**: W594 CONTENT_DERIVATION_LOW_OVERLAP fires when downstream content shares fewer than 5 distinct tokens with upstream artifacts.
- **`forward_replay_check` content staleness detection**: W595 CONTENT_STALENESS fires when upstream content changes are not reflected downstream. Configurable via `SPECDEV_STALENESS_THRESHOLD`.
- **`matrix` coverage threshold enforcement**: W592/E592 fires when FR coverage falls below configured threshold. Defaults: 80% FR coverage, warn mode. Configured via `coverage_thresholds` in step_order.json.
- **Dynamic W→E promotion**: `PROMOTABLE_PAIRS` dict (18 pairs) replaces the hard-coded 4-pair list. `SPECDEV_WARNINGS_AS_ERRORS=1` promotes all 18; `SPECDEV_PROMOTE_CODES=W571,W593` promotes selectively.
- **`env-check` CLI command**: read-only diagnostic showing active `SPECDEV_*` env vars, promotion status, replay base ref, and spec paths.
- **`dag-lint` CI gate**: added to `.github/workflows/ci.yml` as a blocking check.
- **`dag-lint` pre-commit hook**: fires when `step_order.json` or prompt files are modified.
- **26 new error/warning codes** registered (E150, E554, E555, E571-E573, E580-E581, E590-E599, W590-W597).
- **4 previously unregistered codes** now registered (E551, E552, E553, W552).

### P7: Structured Error Output (2026-03-19)

- **`SpecError` dataclass** (`core/errors.py`): All 41 error-producing modules now return structured `SpecError(code, message, path)` objects instead of plain strings. ~370 `make_error()` call sites.
- **Helper functions**: `make_error()` (validates code exists in ERROR_CODES), `render_errors()` (SpecError → string list), `ensure_spec_errors()` (string → SpecError bridge for transition).
- **`core/json_output.py`**: New module with `format_errors_json()` for deterministic JSON output envelopes.
- **`--json` CLI flag**: Added to all 25 subcommands. Produces JSON with `status` (PASS/WARN/FAIL), `error_count`, `warning_count`, and `errors` array.
- **`_apply_we_promotion()` rewrite**: W→E code promotion in `validate.py` rewritten from regex-based string manipulation to field-based `SpecError.code` swapping.
- **Test count**: 1271 (up from 997 pre-P7, 830 at original baseline).

### Prompt Updates

- **Extraction Intent sections** added to all 16 remaining prompts (05, 06, 07, 08, 09, 10, 11, 12, 13, 13a, 14, 15, 16, 16a, 16b, 16c). Each lists upstream artifacts consumed and what is extracted.

## Changed

- **`downstream_consumers` completed** in step_order.json: 22+ entries added for steps 08, 11, 12, 15 to close DAG blind spots.
- **E550 collision resolved**: `canon_schema_alignment.py` now uses E554 CANON_ENUM_DRIFT (was E550); `forward_replay_check.py` now uses E555 SEMANTIC_COVERAGE_REGRESSION for ID regressions (was E550). E550 is now exclusively FORWARD_REPLAY_MISSING.

## Fixed

- **W→E promotion coverage**: previously only 4 codes (W560-W563) could be promoted; now all 18 promotable warning codes are supported.
- **Error code semantic collision**: E550 was overloaded for 3 different semantics; now split across E550, E554, E555.
- **`spec-check` and sub-validators now skip `spec/samples/`**: recursive spec-dir discovery (`validate-all`, `canonical-integrity`, `spec-quality-lint`, `hallucination-lint`, `fixtures-lint`, `seed-lint`, `governance-check`, `matrix`, `canonical-autofix`) all route through the new `core.loaders.iter_spec_artifacts` helper, which excludes `<spec_dir>/samples/` at the first level. This fixes a discovery collision where `spec/samples/invariants_sample.json` — the runtime evaluation context authored per `prompt_08_fixtures.md` guidance — was flagged as E520 (missing `$schema`) and E210 (unresolved canonical references), despite being intentionally schema-free. `invariants-check --sample` is unaffected because it receives the path explicitly, not via discovery.

## Breaking Changes

- **`00_charter` schema**: `in_scope`, `out_of_scope`, `assumptions`, and `risks` promoted to `required`. Existing charter artifacts that omit any of these four fields will now fail validation with a missing-required-field error.
- **`seed_manifest` schema — `docs_policy` removed, `doc_paths` promoted to top-level** (BREAKING): The entire `docs_policy` object (including sub-fields `readme_required`, `root_readme_required`, `readme_depth_default`, `readme_depth_by_scope`, `scope`, `exclusions`, `doc_paths`) has been removed. The `doc_paths` array has been extracted to a top-level optional field. Existing `seed_manifest.json` files containing `docs_policy` will fail schema validation due to `additionalProperties: false`. Migration: remove the `docs_policy` block and add `"doc_paths": [...]` at the top level. The `step_16` validator now reads `doc_paths` directly from the top-level seed manifest and emits W570 when it is missing or empty.
- **`seed_manifest` schema — `nested_order` removed**: The `nested_order` hierarchical seed-ordering array has been removed as an unrecognized property. Existing manifests with this field will fail schema validation.
- **`05_interface_contracts` schema — `trace` promoted to required** (BREAKING): `trace` is now a required field on every API entry in the `apis[]` array. Existing `05_interface_contracts.json` artifacts that omit `trace` on any API will fail validation with E520. Migration: add `"trace": [{"type": "satisfies", "target": "fr-<your-requirement>"}]` to each API object.
- **`14_roadmap` schema — `fr_refs` and `capability_refs` promoted to required on milestones** (BREAKING): Every milestone in the `milestones[]` array must now include `fr_refs` (array of FR IDs) and `capability_refs` (array of capability IDs). Existing `14_roadmap.json` artifacts that omit these fields on any milestone will fail validation. Migration: add `"fr_refs": []` and `"capability_refs": []` to each milestone object. Note: this is an intentional scope expansion beyond the original fix plan (which targeted only task-level `fr_refs` as optional). Milestone-level `fr_refs` and `capability_refs` use inline prefix-enforcing patterns (`^fr-[a-z0-9-]+$`, `^cap-[a-z0-9-]+$`) rather than the generic `vc:core:atoms#kebabId` ref — this is deliberate, as the stricter patterns catch cross-type ID misuse. Both milestone-level arrays also carry `uniqueItems: true`.
- **`owner` atom restricted to 8 canonical enum values** (BREAKING): The `owner` field in `schema/core/atoms.schema.json` previously accepted any lowercase-kebab string matching `^[a-z][a-z0-9_-]*$`. It now enforces a strict `enum` of the 8 canonical team/role values: `api`, `ui`, `system`, `ops`, `data`, `product`, `business`, `engineering`. Any spec artifact with a non-canonical owner value (e.g. `"frontend"`, `"backend"`, `"team-a"`) will now fail schema validation. Migration: replace all non-canonical owner values with the closest matching canonical value.
- **`02_system_sketch` schema — `tech_stack` promoted to required** (BREAKING): `tech_stack`
  is now a required field in `spec/02_system_sketch.json`. Host repos with an existing
  `02_system_sketch.json` that lacks `tech_stack` will fail `specdev validate` after upgrading.
  Migration: add a `tech_stack` object with at least one entry per category (`languages`,
  `frameworks`, `infrastructure`, `tools`). Re-run `specdev validate spec/02_system_sketch.json`
  to verify.

## Pre-R8 / R8 Changes (carried forward)

- E561/E562/E563 differentiated traceability codes.
- W140 seed content overlap check.
- W581/E582 milestone_ref binding; seed-tech-stack required for step 14.
- **R8 Schema Tightening**: `milestone_ref` added to Step 16 checklist item properties; `trace` promoted to required in Steps 01 and 07; `milestones` promoted to required in Step 09 with `deliverables`+`status` required on milestone items; `acceptance_criteria` removed from Step 14 task required; Step 14 assumptions minLength 15→10; Step 13a category enum added + `specification_source` promoted to required. (`coverage_gaps` field and `generationQuality.assumptions` required promotion were subsequently removed as dead fields.)
- **Post-R8 cleanup**: 189 cross-schema `$ref` URIs normalized from JSON Pointer (`#/$defs/`) to anchor (`#`) syntax; W580 SUBSTEP_DRIFT validator updated to forward-only drift detection.
