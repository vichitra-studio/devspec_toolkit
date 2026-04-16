# [Unreleased]

## Summary

Completes the 4-Layer Determinism Closure: cross-step ID validation, DAG integrity enforcement, content derivation checks, dynamic W→E promotion, and Extraction Intent sections across all prompts.

## Added

### Trinity Anchor Schema Split (Phase 2 — anchor hardening)

- **`vc:16-anchor` schema** (`schema/16_anchor.schema.json`): dedicated schema for the Step 16 Trinity Anchor artifact (`spec/16_impl_context.json`). Requires `artifact_role: "anchor"`, `plan.summary`, `plan.ambiguities`, `plan.drift`, and `plan.milestone_index`. Forbids `execution` and `review` via `unevaluatedProperties: false` — these sections belong only to milestone plans (16a/16b/16c).
- **`step_16_anchor` validator** (`validation/validators/step_16_anchor.py`): cross-milestone drift detection.
  - **E308 ANCHOR_SCOPE_DRIFT**: bidirectional scope contradiction (milestone `scope_in` ∩ anchor `scope_out`, or reverse) and FR ownership conflict (same FR active in two simultaneous milestones).
  - **E309 ANCHOR_CHECKLIST_DRIFT**: same checklist `id` maps to different `spec_ref.id` across milestone context files.
  - **W585 ANCHOR_DRIFT_SKIP**: guard for routing errors or missing spec_path. (Note: `W580` retains its prior meaning `SUBSTEP_DRIFT` and is unchanged.)
- **Routing fix** (`validation/validate.py`): files in `impl_context/` now route to step `"16a"` (milestone plans); `16_impl_context.json` at the spec root routes to step `"16"` (anchor). Fixes long-standing routing bug where every impl_context artifact silently used the base validator.
- **E306 path fix** (`validation/validators/step_16.py`): when an artifact lives in `impl_context/`, `04_fr_list.json` is now resolved from the parent spec directory instead of from `impl_context/` itself.
- **`prompt_schema_sync` step-key collision fix**: `16_anchor.schema.json` and `16_impl_context.schema.json` both derive step `"16"` via filename split; the anchor now gets a distinct `"16anchor"` step key, and `_PROMPT_STEP_OVERRIDE` maps `prompt_16_impl_context.md` to validate against the anchor schema.
- **Fixture reorganization**: `tests/fixtures/step_16/impl_context/` holds all 17 milestone-plan fixtures; 6 anchor fixtures live at the root of `tests/fixtures/step_16/` (2 valid: minimal + with_milestones; 4 invalid: missing_drift, missing_milestone_index, has_execution, has_milestone_ref).
- **28 new anchor integration tests** (`tests/integration/test_step_16_anchor.py`): schema pass/fail, E308 scope contradiction and FR ownership (forward/reverse/done-exempt), E309 checklist drift (cross-milestone + prefix-collision), W585/W586/W587/W588 guard paths, misfiled-anchor routing, and content-based sub-step dispatch.

### Phase 1 — Seed & Spec Dependency Hardening

- **`seedRef` / `seedRefArray`** (`schema/core/collections.schema.json`): new reusable type with `seed_id` (required) plus optional `hash` (SHA-256) and `version` for drift detection against seed content changes.
- **`specRefIngested` / `specRefIngestedArray`** (`schema/core/collections.schema.json`): new reusable type recording `{step_id, artifact_id, hash?}` so downstream artifacts can declare which upstream artifacts they were derived from.
- **`spec_refs_ingested` and `seed_refs_ingested`** (`schema/core/step_base.schema.json`): optional properties inherited by all 20 step schemas composed via `allOf` — no per-step changes required.
- **`seed_manifest` optional `hash` and `version` fields** on each seed entry — populated by `seed-index` tooling for integrity tracking.
- **`step_metadata` block in `tools/step_order.json`** (schema-validated): for all 22 steps, declares `required_spec_inputs` (inverse of `downstream_consumers`) and `required_seed_inputs` (mirror of seed manifest step_requirements). Prevents drift between forward/reverse DAG views.
- **`_lint_step_metadata_consistency`** (`validation/dependency_order_lint.py`): new consistency validator that rejects any `step_metadata.required_spec_inputs` that is not the exact inverse of `downstream_consumers`. Emits **E543 STEP_METADATA_INCONSISTENT** (dedicated code — previously shared E540 with `SELF_OR_FORWARD_DEPENDENCY`, which broke selective error-code promotion).
- **`_lint_step_metadata_seed_consistency`** (`validation/dependency_order_lint.py`): symmetric check on the seed side — `step_metadata.required_seed_inputs` must match `seed_manifest.step_requirements` exactly. Silently skips when either file or block is absent. Also emits E543 STEP_METADATA_INCONSISTENT with a message distinguishing `required_seed_inputs` from `required_spec_inputs`.
- **8 new unit tests** for the consistency linters (4 spec-edge + 4 seed-edge: absent/consistent/missing/extra cases).

### Trinity Anchor Follow-on (Phase 2 polish)

- **W586 ANCHOR_VALIDATOR_WRONG_ARTIFACT**: fires when the anchor validator is invoked on an artifact that is neither field-marked (`artifact_role == "anchor"`) nor path-marked (`spec/16_impl_context.json` outside `impl_context/`). Routing-bug signal.
- **W587 ANCHOR_DRIFT_CHECKS_STALE**: fires when `plan.milestone_index` is non-empty but `plan.drift.checks` is empty — the anchor is paying its maintenance cost without performing its one load-bearing job (cross-cycle drift monitoring).
- **Content-based sub-step dispatch** (`validation/validate.py::_refine_impl_context_substep`): artifacts in `impl_context/` initially land on `"16a"` via path regex, then are promoted to `"16b"` (when `execution.execution_results` is non-empty) or `"16c"` (when `review.verdict` is a non-empty string). Previously 16b/16c-specific checks (duplicate commands, verdict enum, W582 FR coverage) were only reachable by calling the validators directly.
- **Chain-up semantics** (`step_16b.py`, `step_16c.py`): `validate_step_16b` now transitively invokes `validate_step_16a`; `validate_step_16c` invokes `validate_step_16b`. `_step16_cache` (MD5-keyed on data+path) deduplicates the base pass so chain-up is O(1) in base work.
- **`_load_roadmap()` DRY helper** (`step_16.py`, reused by `step_16c.py` W582): resolves `14_roadmap.json` correctly whether the artifact lives at `spec/` root or inside `spec/impl_context/`. Previously `step_16c` used a sibling-only resolver that silently no-op'd W582 for review artifacts under `impl_context/`.
- **Prompt rewrite** (`prompts/prompt_16_impl_context.md`): all prose re-authored to describe only the anchor contract (`artifact_role`, `plan.summary`, `plan.ambiguities`, `plan.drift`, `plan.milestone_index`). Previous prose described the shared `vc:16-impl-context` shape and would lead LLM authors to emit fields the new schema forbids.
- **Orphan fixture cleanup**: 17 top-level `tests/fixtures/step_16/*.json` fixtures deleted after the `impl_context/` subdirectory migration — all tests now read from the new location.
- **`_step16_cache.clear()` on `validate_dir` entry** (`validation/validate.py`): prevents cross-run accumulation of content-hash cache entries in long-lived processes. The cache is a correctness-neutral optimisation for chain-up dedup within one `validate_dir` invocation; clearing between runs keeps memory bounded.

### Trinity Anchor Review Pass (cross-tool consistency sweep)

- **`traceability_closure.py` drives off the anchor registry** — removed the phantom `16a_impl_planner.json`/`16b_code.json` entries from `SPEC_FILES` and the fallback that silently read the anchor as a 16a planner post-split. Checklist/execution data is now loaded from each `spec/impl_context/<plan>.json` declared in `plan.milestone_index[].context_path`; unreadable or missing declared plans emit **W588 ANCHOR_MILESTONE_UNREADABLE**. No glob, no auto-derivation — the anchor is the single source of truth.
- **`context/reviewer.py` `_CHECKLIST_STEPS` drops `"16"`** — the anchor is no longer a checklist step post-split. `ac-*` retention and the acceptance-gap Jaccard check now run only on 16a/16b/16c.
- **Extraction-intent parser accepts `spec/` prefix and routes `spec/impl_context/...` to both 16a and 16b** — the shared Trinity artifact convention. Unblocks `extraction-intent-check` (was previously exit-1 after the `779378d` prompt refactor).
- **Extraction-intent-check uses `step_metadata.required_spec_inputs`** (authoritative consumption set) as its coverage source of truth. Falls back to `derive_allowed_upstream` (DAG-ancestor set) when metadata is absent — preserves prior behaviour for test fixtures that don't declare metadata, narrows the check for real prompts.
- **Extraction Intent section format** on `prompt_16a_impl_planner.md` and `prompt_16c_impl_reviewer.md` — promoted `##` → `###` and `###` Primary/Reference sub-sections to `####`. The parser requires `### Extraction Intent`; before this change the two prompts were silently skipped. Bullet entries converted from backtick to bold to match the parser's `**filename**` contract.
- **Prompt phantom filenames fixed** — `09_implementation_plan.json` → `09_impl_plan.json` and `13_extension_generator.json` → `13_extension_manifest.json` across `prompt_13_extension_generator.md`, `prompt_14_roadmap.md`, `prompt_15_scaffold.md`, `prompt_16_impl_context.md`, `prompt_16a_impl_planner.md`, `prompt_16b_impl_coder.md`.
- **16a prompt** — checklist `id` rule now requires the `milestone_index[<this milestone>].checklist_id_prefix` from the anchor; Self-Audit Gate pins the anchor registration precondition; Coverage Closure adds an E309 guard; Negative Constraints forbid `artifact_role` on milestone plans. Example id updated from `CHK_AUTH_01` to `AUTH_LOGIN_01` to model the prefix convention. Behaviour-pairing rule softened to match E307's `{doc, code}` exemption.
- **Anchor prompt** — corrected `milestone_index[].status` enum in Coverage Closure (`active` → `not done`, aligned with `step_16_anchor.py:111`); added Negative Constraint forbidding the anchor inside `spec/impl_context/`; example `id` updated to `anchor-v1` to match the `{noun}-v{N}` convention.
- **`milestone_index[].context_path` pattern** (`schema/16_anchor.schema.json`): added `^(spec/)?impl_context/[a-z0-9_]+\.json$` so typos and mislocations are rejected at author time — the field is now load-bearing for traceability_closure and the anchor drift check.
- **Schema title fix** (`schema/16_anchor.schema.json`): `"16_impl_context (Trinity Anchor)"` → `"16_anchor (Trinity Anchor)"`.
- **W589 ANCHOR_MILESTONE_MISSCHEMAED**: new warning — fires when a file in `spec/impl_context/` parses as JSON but declares the wrong `$schema` (or none at all). Previously such files were silently skipped by the anchor drift check, hiding authoring mistakes.
- **W596 shared-artifact tolerance** (`dag_lint.py`): intra-Trinity cross-references through `spec/impl_context/...` no longer trigger UNDECLARED_UPSTREAM_REF for 16b/16c citing 16a/16b via the shared milestone plan file.
- **`prompt_schema_sync._SUBSTEP_EXPECTED_KEYS` covers the anchor domain**: anchor-exclusive keys (`artifact_role`, `milestone_index`) now forward-check against 16a/16b/16c payloads. A 16a prompt that accidentally emits `milestone_index` now fires W580 SUBSTEP_DRIFT instead of silently drifting.
- **`step_16.py` E304 scoping** — replaced the dead root `milestone_ref` read with checklist-item aggregation (matching the `step_16c.py` pattern). E304 now scopes to the milestones declared on checklist items; E582 reports every checklist-declared milestone_ref not found in the roadmap (previously only the first).
- **`e304_roadmap/impl_context/ms_test_plan.json` fixture** rewritten to be schema-valid except for the intended E304 gap (checklist covers `implement-login` as a behavior+validation pair; `implement-logout` is intentionally uncovered). The E304 integration test is no longer passing on a false witness.
- **Migration template** (`prompts/migration/template_impl_context.md`) rewritten to document the anchor/milestone-plan split, the migration procedure from a pre-split `spec/16_impl_context.json`, and the new E308/E309/W585–W589 error codes.
- **Changelog counts corrected**: anchor fixtures at `tests/fixtures/step_16/` (6, not 4); anchor integration tests in `test_step_16_anchor.py` (33 after this pass, not 18).
- **Tests added**:
  - `test_traceability_closure.py`: 4 new tests covering anchor-missing, declared context_path missing/unparseable, multi-milestone merge, empty milestone_index.
  - `test_extraction_intent_rules.py`: 3 new tests covering `spec/` prefix, `impl_context/` → 16a/16b credit, and the `step_metadata.required_spec_inputs` source of truth.
  - `test_step_16_anchor.py`: deferred-milestone E308, `context_path` pattern, W589 mis-schemaed (3 cases).
  - `test_prompt_schema_sync.py`: `_PROMPT_STEP_OVERRIDE` integrity, anchor prompt → `vc:16-anchor` validation, and 16a leaking `milestone_index` → W580.
  - `test_dag_lint_rules.py`: Trinity shared-artifact tolerance for W596.

### Known follow-ups (not in this release)

- **F-S3 / Phase 1 Task 1.2 — Prompt emission of `spec_refs_ingested` / `seed_refs_ingested`.** The schema hook is live on `step_base` and inherited by all 20 step schemas, but no prompt is yet authored to emit these fields. Until prompts populate them, downstream drift detection based on ingested-ref hashes has nothing to read. Tracked for a follow-up feat pass that will coordinate prompt updates across the pipeline.

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
- **`spec/16_impl_context.json` reshaped from `vc:16-impl-context` to `vc:16-anchor`** (BREAKING):
  Step 16 is now the **Trinity Anchor** — a scope/ownership/drift declaration that spans all
  milestones — and uses a dedicated schema. The 16a/16b/16c milestone artifacts continue to
  use `vc:16-impl-context` and have moved to `spec/impl_context/{step_id}.json`. Existing host
  repos that authored `spec/16_impl_context.json` against `vc:16-impl-context` will fail
  validation on multiple counts: missing required `artifact_role: "anchor"`, forbidden
  `plan.spec_alignment.checklist` / `plan.review_requirements` / `plan.docs_impact` /
  `plan.solution` / `plan.context` / `plan.security` / `plan.delivery` / `plan.coverage_status`
  / `plan.scope_validation`, forbidden top-level `execution` / `review` / `milestone_ref`,
  and missing required `plan.ambiguities` / `plan.drift` / `plan.milestone_index`.
  Migration:
    1. **Move milestone-plan content out** — copy the existing `spec/16_impl_context.json`
       to `spec/impl_context/<milestone_id>_plan.json` (the per-milestone 16a artifact); leave
       its `$schema` as `vc:16-impl-context`.
    2. **Rewrite `spec/16_impl_context.json` against the anchor contract** — see
       `prompts/prompt_16_impl_context.md` and `schema/16_anchor.schema.json`. The new file
       carries only `plan.summary` (scope), `plan.ambiguities`, `plan.drift.checks`, and
       `plan.milestone_index`. Each `milestone_index` entry registers
       `{milestone_id, context_path, status, fr_refs, checklist_id_prefix, summary}`.
    3. **Use the shared milestone status enum** — `milestone_index[].status` is
       `pending` | `in_progress` | `done` | `deferred` (from `vc:core:atoms#milestoneStatus`);
       the earlier draft used `active` / `planned` and those values are now schema-rejected.
    4. **Re-run `./tools/run_specdev.sh validate spec/16_impl_context.json --repo-root ./devspec_toolkit`**
       to confirm the anchor passes; then run `./tools/run_specdev.sh spec-check spec --repo-root ./devspec_toolkit`
       to surface any new E308 / E309 / W587 / W588 signals from the anchor's drift check.
  New error codes for this surface: **E308** ANCHOR_SCOPE_DRIFT (scope contradiction or
  FR/API ownership conflict between in-flight milestones), **E309** ANCHOR_CHECKLIST_DRIFT
  (cross-milestone checklist ID collision or duplicate `checklist_id_prefix` in
  `milestone_index`), **W585** ANCHOR_DRIFT_SKIP, **W586** ANCHOR_VALIDATOR_WRONG_ARTIFACT,
  **W587** ANCHOR_DRIFT_CHECKS_STALE, **W588** ANCHOR_MILESTONE_UNREADABLE.

## Pre-R8 / R8 Changes (carried forward)

- E561/E562/E563 differentiated traceability codes.
- W140 seed content overlap check.
- W581/E582 milestone_ref binding; seed-tech-stack required for step 14.
- **R8 Schema Tightening**: `milestone_ref` added to Step 16 checklist item properties; `trace` promoted to required in Steps 01 and 07; `milestones` promoted to required in Step 09 with `deliverables`+`status` required on milestone items; `acceptance_criteria` removed from Step 14 task required; Step 14 assumptions minLength 15→10; Step 13a category enum added + `specification_source` promoted to required. (`coverage_gaps` field and `generationQuality.assumptions` required promotion were subsequently removed as dead fields.)
- **Post-R8 cleanup**: 189 cross-schema `$ref` URIs normalized from JSON Pointer (`#/$defs/`) to anchor (`#`) syntax; W580 SUBSTEP_DRIFT validator updated to forward-only drift detection.
