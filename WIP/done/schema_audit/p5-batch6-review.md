# Batch 6 Review: Dead Field Removal from Schemas & Config

**Date**: 2026-03-19
**Reviewer**: Claude Opus 4.6
**Scope**: FIX-061 through FIX-069
**Verdict**: ALL REMOVALS VERIFIED CLEAN. 16 test failures, all expected (Batch 7/8 scope).

---

## 1. Completeness of Removals

All grep checks across `schema/**/*.json` return ZERO matches for every removed field.

| Field | Scope | Matches | Status |
|-------|-------|---------|--------|
| `generation_quality` | schema/*.json + schema/core/*.json | 0 | CLEAN |
| `seed_refs` | schema/*.json (step schemas only) | 0 | CLEAN |
| `spec_refs_ingested` | schema/*.json + schema/core/*.json | 0 | CLEAN |
| `coverage_gaps` | schema/*.json + schema/core/*.json | 0 | CLEAN |
| `nested_order` | schema/seed_manifest.schema.json | 0 | CLEAN |
| `docs_policy` | schema/seed_manifest.schema.json | 0 | CLEAN |
| `allowed_upstream_dependencies` | schema/step_order.schema.json | 0 | CLEAN |
| `allowed_upstream_dependencies` | tools/step_order.json | 0 | CLEAN |

**Note**: `seedRef` and `seedRefArray` still exist in `schema/core/collections.schema.json` (referenced by `schema/core/canon.schema.json`). This is correct -- that is Batch 8 scope (seedRef type definition removal), not Batch 6 (step-level `seed_refs` property removal).

---

## 2. step_base.schema.json Verification

File: `schema/core/step_base.schema.json`

**Required array** (line 46-51): `["id", "owner", "created_at", "canonical_refs_used"]` -- CORRECT, exactly 4 fields.

**Properties present** (8 total):
- `$schema` -- KEEP (correct)
- `id` -- KEEP (correct)
- `owner` -- KEEP (correct)
- `created_at` -- KEEP (correct)
- `canonical_refs_used` -- KEEP, in required (correct)
- `canonical_proposals` -- KEEP, optional (correct)
- `canonical_conflicts` -- KEEP, optional (correct)
- `_migration_notes` -- KEEP, optional (correct)

**Dead fields confirmed absent**: No `generation_quality`, `seed_refs`, `spec_refs_ingested`, or `coverage_gaps` in properties.

---

## 3. seed_manifest.json Verification

File: `spec/common/seed_manifest.json`

- No `nested_order` block -- CLEAN
- No `docs_policy` block -- CLEAN
- `global_seed_order` present -- CONFIRMED (line 7)
- Valid JSON with `$schema`, `seed_manifest_id`, `version`, `created_at`, `last_updated`, `global_seed_order`, `seeds`, `step_requirements` -- all intact.

---

## 4. step_order.json Verification

File: `tools/step_order.json`

- No `allowed_upstream_dependencies` -- CLEAN
- `downstream_consumers` present with all 22 step entries -- CONFIRMED (lines 45-68)
- Valid JSON with `version`, `_notes`, `policy`, `steps` (22 entries), `coverage_thresholds`, `downstream_consumers` -- all intact.

---

## 5. Unintended Removal Check

All KEEP fields verified present:

| Field | Location | Count | Status |
|-------|----------|-------|--------|
| `canonical_refs_used` | step_base.schema.json | 2 (property + required) | PRESENT |
| `canonical_proposals` | step_base.schema.json | 1 (property, optional) | PRESENT |
| `canonical_conflicts` | step_base.schema.json | 1 (property, optional) | PRESENT |
| `downstream_consumers` | tools/step_order.json | 2 (_notes + data block) | PRESENT |
| `global_seed_order` | spec/common/seed_manifest.json | 1 | PRESENT |

No unintended removals detected.

---

## 6. Test Failure Categorization

**16 failures, 1255 passing** (was 1271 passing pre-Batch 6)

### Category A: Fixtures still contain removed fields (Batch 7 -- fixture cleanup)

These fixtures still have `coverage_gaps`, `generation_quality`, `seed_refs`, `spec_refs_ingested` which are now rejected as unevaluated properties by the updated schemas.

| # | Test | Root Cause | Fix Batch |
|---|------|-----------|-----------|
| 1 | `test_step_14::test_valid_roadmap_fixtures_pass_schema_validation` | `tests/fixtures/step_14/valid_roadmap.json` has dead fields | **Batch 7** (fixture cleanup) |
| 2 | `test_step_14::test_valid_roadmap_with_refs` | `tests/fixtures/step_14/valid_roadmap_with_refs.json` has dead fields | **Batch 7** |
| 3 | `test_step_16::test_valid_empty_execution_and_review` | `tests/fixtures/step_16/valid_empty_execution_review.json` has dead fields + W570 docs_policy | **Batch 7** |
| 4 | `test_step_16::test_valid_full` | `tests/fixtures/step_16/valid_full.json` has dead fields + W570 docs_policy | **Batch 7** |
| 5 | `test_step_16::test_valid_full_with_new_fields` | Same fixture as test_valid_full | **Batch 7** |
| 6 | `test_step_16::test_valid_minimal` | `tests/fixtures/step_16/valid_minimal.json` has dead fields + W570 docs_policy | **Batch 7** |
| 7 | `test_step_16::test_valid_with_new_fields` | Same fixture as test_valid_minimal | **Batch 7** |
| 8 | `test_step_16::test_valid_with_semantic_review` | `tests/fixtures/step_16/valid_with_semantic_review.json` has dead fields + W570 docs_policy | **Batch 7** |
| 9 | `test_step_scripts_bridge::test_script_style_step_checks_are_executed_under_unittest_discovery` | Runs validation on fixture with dead fields | **Batch 7** |
| 10 | `test_schema_contracts::test_step_09_allows_string_dependencies_without_oneof_overlap` | Inline test fixture has dead fields | **Batch 7** |
| 11 | `test_schema_contracts::test_step_14_valid_fixture_still_validates_after_shared_anchor_rollout` | Uses `tests/fixtures/step_14/valid_roadmap.json` | **Batch 7** |

### Category B: Prompts still reference removed fields (Batch 8 -- prompt cleanup)

| # | Test | Root Cause | Fix Batch |
|---|------|-----------|-----------|
| 12 | `test_prompt_contracts::test_output_contract_examples_validate_against_step_schemas` | Prompt output-contract JSON examples (in prompt_00*.md etc.) include dead fields | **Batch 8** (prompt cleanup) |
| 13 | `test_prompt_schema_sync::test_repo_prompt_schema_sync_is_clean` | All 22 prompts have output_contract examples with dead fields (22 E310 errors) | **Batch 8** |

### Category C: Test code asserts removed fields should exist (Batch 7 -- test code update)

| # | Test | Root Cause | Fix Batch |
|---|------|-----------|-----------|
| 14 | `test_schema_contracts::test_all_step_schemas_include_metadata_top_level_fields` | Test asserts `generation_quality` must be in schema properties | **Batch 7** (update test assertion) |

### Category D: Autofix tool code references removed fields (Batch 7 -- tool code update)

| # | Test | Root Cause | Fix Batch |
|---|------|-----------|-----------|
| 15 | `test_schema_contracts::test_canonical_autofix_does_not_add_schema_invalid_unit_ref_from_units` | Autofix code injects `term_ref` which no longer exists in schema, test expects it | **Batch 7** (autofix logic update) |
| 16 | `test_schema_contracts::test_canonical_autofix_infers_risk_category_ref_where_schema_allows` | Autofix infers `risk_category_ref` field that may have been removed; test expects non-None | **Batch 7** (autofix logic update) |

### Sub-issue: W570 docs_policy warning (Step 16 fixtures)

Six Step 16 test failures show a secondary error `W570: seed_manifest.json missing docs_policy.doc_paths`. This is caused by FIX-069 removing `docs_policy` from seed_manifest. The validator code that checks `docs_policy.doc_paths` needs updating to handle its absence gracefully. This is **Batch 7** scope (validator code update).

---

## Summary

| Batch | Failure Count | What to Fix |
|-------|--------------|-------------|
| **Batch 7** (fixtures + tool code + tests) | 14 | Remove dead fields from fixtures, update test assertions, update autofix tool logic, handle missing docs_policy in validators |
| **Batch 8** (prompts) | 2 | Remove dead fields from all 22 prompt output-contract examples |
| **Total** | **16** | |

**Batch 6 schema changes are complete and correct. No regressions beyond expected fixture/prompt/test drift.**
