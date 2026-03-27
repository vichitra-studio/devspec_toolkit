# P4 Fix Plan Review

**Date**: 2026-03-19
**Reviewer**: Claude Opus 4.6 (1M context)
**Scope**: Cross-reference P4 fix plan against P3 master findings + codebase verification
**Verdict**: CONDITIONAL PASS -- 3 blockers, 8 significant issues, 4 minor issues

---

## 1. COVERAGE GAPS

### 1.1 AUDIT-031 missing from WONTFIX table (SIGNIFICANT)

AUDIT-031 (Canon schemas live outside `schema/` directory, MEDIUM severity) is marked WONTFIX in the cross-reference table (line 828) and has a justification in Appendix B. However, it is **not listed** in the WONTFIX Findings table at the top of the document, which shows only 4 items (AUDIT-040, 051, 052, 044). This means the summary count "WONTFIX: 4" is wrong -- it should be 5.

**Fix**: Add AUDIT-031 to the WONTFIX table and update the count to 5. Adjust the severity coverage table accordingly (MEDIUM Fix Tasks drops from 21 to 20).

### 1.2 Non-standard disposition categories not tracked (MINOR)

Three findings use disposition categories not represented in the summary statistics:
- AUDIT-020: "KEEP (actively consumed, drift-sensitive)"
- AUDIT-028: "DEFERRED (subsumed by ALIGN-2)"
- AUDIT-037: "NO ACTION (descriptions adequate)"

These are all reasonable dispositions but the summary table only tracks Fix Tasks / WONTFIX / INFO. The 48 "Fix Tasks" count is actually 48 AUDIT-to-FIX mappings, but 3 non-INFO findings have no FIX and no WONTFIX label.

**Fix**: Add a "KEEP/DEFERRED/NO ACTION" column to the severity coverage table, or consolidate these 3 under a "No Fix Needed" label distinct from WONTFIX.

### 1.3 All non-INFO findings verified mapped

Every AUDIT-001 through AUDIT-052 (non-INFO) is present in the cross-reference table with either a FIX ID, WONTFIX, KEEP, DEFERRED, or NO ACTION disposition. No gaps found.

---

## 2. DEPENDENCY ERRORS

### 2.1 No dependency errors found

All `Dependencies` fields reference FIX tasks in earlier or same batches. Verified:
- Batch 0: no deps (correct)
- Batch 1: FIX-007 depends on FIX-001 (Batch 0) -- correct
- Batch 2: all depend on Batch 0/1 tasks -- correct
- Batch 3: FIX-028-031 depend on FIX-019 (Batch 2) -- correct
- Batch 4-7: all reference earlier batches -- correct

---

## 3. CONFLICTING TASKS

### 3.1 FIX-002 through FIX-006 modify same file sequentially (ACKNOWLEDGED)

Five tasks sequentially modify `schema/core/atoms.schema.json`. The plan correctly notes "execute sequentially" on each. No conflict, but execution must be strictly ordered.

### 3.2 FIX-032/033/034 modify Step 16 schema sequentially (ACKNOWLEDGED)

Three Step 16 description tasks on the same file. Plan correctly notes sequential dependency.

### 3.3 Batch 4 multiple modifications to Step 05 (MINOR)

FIX-035, FIX-036, and FIX-044 all modify `schema/05_interface_contracts.schema.json`. FIX-036 depends on FIX-035, and FIX-044 depends on FIX-036. Correctly sequenced, but the combined changes (conditional validation + enum extension + field renames) make this the highest-risk step schema modification in Batch 4. Consider adding an intermediate test gate between FIX-036 and FIX-044.

---

## 4. INFEASIBLE TASKS

### 4.1 FIX-019 `additionalProperties: false` with `allOf` -- CORRECTLY IDENTIFIED AS RISK (SIGNIFICANT)

The plan's Appendix B correctly identifies the core problem: `additionalProperties` in JSON Schema evaluates against properties defined in the **current schema object**, not properties inherited via `allOf`. The recommendation to use `unevaluatedProperties: false` is the correct Draft 2020-12 approach.

**Verified**: The installed `jsonschema` library version is 4.25.1, which fully supports Draft 2020-12 `unevaluatedProperties`. The fix is feasible.

**However**, the plan says "JSON Schema 2020-12 evaluates `additionalProperties` against properties defined anywhere in the `allOf`, so this should work" in the FIX-019 description itself. This statement is **wrong** -- it contradicts the correct analysis in Appendix B. `additionalProperties` does NOT see `allOf` sibling properties. The FIX-019 description should be corrected to match Appendix B's analysis.

### 4.2 FIX-019 LOC estimate appears aggressive (MINOR)

The plan estimates -988 LOC for removing 11 properties x 19 schemas (~52 LOC per schema). Verified against `schema/00_charter.schema.json`: the 11 common properties and their `required` entries occupy roughly 25-30 LOC (since most are single-line `$ref` entries), not 52. The actual reduction may be closer to ~500-600 LOC, not ~988. This does not affect feasibility but the net LOC estimate in Appendix C may be significantly off.

---

## 5. MISSING TEST GATES

### 5.1 BLOCKER: `tests/test_step_validators_core.py` does not exist (BLOCKER)

**14 FIX tasks** (FIX-011 through FIX-018, FIX-035 through FIX-037, FIX-041, FIX-042, FIX-043) reference `pytest tests/test_step_validators_core.py` as their test gate. This file does NOT exist.

The actual file is at: `tests/unit/validation/validators/test_step_validators_core.py`

All test gate references must be corrected to use the full path.

**Affected tasks**: FIX-011, FIX-012, FIX-013, FIX-014, FIX-015, FIX-016, FIX-017, FIX-018, FIX-035, FIX-036, FIX-037, FIX-038, FIX-041, FIX-042, FIX-043, FIX-044, FIX-045

### 5.2 Integration test references correct but incomplete (MINOR)

FIX-014 references `tests/integration/test_step_11.py` and FIX-018 references `tests/integration/test_step_16*.py` -- both verified to exist. However, FIX-015 references `tests/integration/test_step_05.py` which exists, but FIX-016 (Step 15) does not reference `tests/integration/test_step_15.py` (which also exists). Recommend adding it.

### 5.3 FIX-056/057/058 target `tests/test_schema_quality.py` -- new file (ACKNOWLEDGED)

These create a new file at `tests/test_schema_quality.py` (top-level tests directory). Given the project's test structure (`tests/unit/`, `tests/integration/`), this file should probably be placed at `tests/unit/test_schema_quality.py` for consistency.

---

## 6. WONTFIX REVIEW

### 6.1 AUDIT-040 (URI migration) -- VALID WONTFIX

534 URIs across 70+ files. Correctly deferred -- depends on DRY fixes completing first to reduce URI count. The prerequisite relationship is genuine.

### 6.2 AUDIT-051 (src/dist split) -- VALID WONTFIX

Future feature requiring CLI infrastructure. Correctly deferred to post-DRY cleanup.

### 6.3 AUDIT-052 (WIP doc correction) -- QUESTIONABLE WONTFIX

This is a trivial documentation fix: changing "19 levels" to "9 levels" and "scaffolding" to "impl_context" in a WIP file. The WONTFIX justification says "Owner can correct ad hoc" -- but the same could be said of any description fix. Given that it is literally a 2-word correction in a file already tracked, it should be a 1-LOC FIX task in Batch 3 or 7, not WONTFIX. The effort cost is near zero.

**Recommendation**: Downgrade from WONTFIX to FIX (add as FIX-060 in Batch 7 or Batch 3).

### 6.4 AUDIT-044 (docs_policy location) -- VALID WONTFIX

Actively consumed by 2 validators. Migration cost exceeds benefit. Correct.

### 6.5 AUDIT-031 (canon schema location) -- VALID WONTFIX (but missing from table, see 1.1)

Intentional co-location. Cost exceeds benefit. Correct -- but needs to be added to the WONTFIX table.

---

## 7. RISK ASSESSMENT

### 7.1 Batch ordering is correct

The batch dependency chain is well-structured:
- Batch 0 (foundation) -> Batch 1 (core fixes) -> Batch 2 (step DRY) is the critical path
- Batch 3 (descriptions) is additive and low-risk
- Batch 4 (genericity) contains breaking changes, correctly placed after structural work
- Batch 5 (structure) is low-risk
- Batch 6 (bloat removal) is correctly last among schema changes
- Batch 7 (tests/CI) is correctly final

### 7.2 FIX-019 is correctly identified as highest-risk (SIGNIFICANT)

The allOf base schema adoption touches all 19 step schemas simultaneously. The plan correctly gates this with full test suite. The `unevaluatedProperties` migration is the right approach.

**Additional risk not noted**: After FIX-019, any code that reads schema files and looks for `properties` at the top level will not find inherited properties. The plan should verify that no tool code (beyond `_schema_candidates` in integrity.py) traverses schema structure directly. Confirmed: `_schema_candidates` already handles `allOf`, but other tools should be checked.

### 7.3 Batch 4 breaking changes need migration plan (SIGNIFICANT)

FIX-037 (service_skeleton -> project_skeleton, route_map -> interface_map) and FIX-044 (route -> path, request_schema_ref -> input_schema_ref, response_schema_ref -> output_schema_ref) are field renames that will break:
- Existing spec data files
- Step validators (step_15.py, step_05.py)
- Prompt templates (prompt_15_scaffold.md, prompt_05_interface_contracts.md)
- Test fixtures

The plan mentions updating validators to accept BOTH old and new names but does not specify:
1. Whether the old names should be permanently supported or time-limited
2. How prompt templates will be updated (which ones, how many)
3. Whether a `canonical-autofix` migration should handle existing spec files

**Recommendation**: Add a sub-plan enumerating affected files for each rename, with explicit fixture counts.

---

## 8. LOC ESTIMATES

### 8.1 Summary table inconsistency (SIGNIFICANT)

The summary says "Total tasks: 55" but there are 59 `### FIX-` headings (FIX-001 through FIX-059). Appendix C says 59 tasks. The "55" appears to be stale.

**Fix**: Update summary to say "Total tasks: 59".

### 8.2 Appendix C LOC totals vs summary (MINOR)

Summary says "+2,400 / -1,200 / net +1,200" but Appendix C shows "+1,349 / -1,184 / net +165". These are very different. The Appendix C numbers appear more carefully computed. The summary numbers look like rough estimates that were not updated after task-level estimation.

**Fix**: Update summary LOC to match Appendix C.

### 8.3 FIX-019 LOC estimate likely inflated

See section 4.2. The ~988 LOC removal assumes ~52 LOC of common properties per schema, but actual common property declarations are closer to ~25-30 LOC per schema (most are single `$ref` lines). Net reduction probably ~500-600 LOC, not ~988.

---

## 9. HALLUCINATIONS

### 9.1 BLOCKER: FIX-010 `evidenceObject` property list incorrect (BLOCKER)

FIX-010 describes the `evidenceObject` to be promoted to core/collections with properties: `type`, `content`, `path`, `description`.

The actual Step 16 `evidenceObject` (lines 68-100 of `16_impl_context.schema.json`) has properties:
- `type` (enum)
- `content` (string, minLength: 20)
- `evidence_ref` (string)
- `path` (string)
- `section` (string)

There is no `description` property. The actual properties are `evidence_ref` and `section`, not `description`.

**Fix**: Correct FIX-010 to match the actual schema definition.

### 9.2 BLOCKER: Test file path hallucination (see 5.1)

`tests/test_step_validators_core.py` referenced 17 times but does not exist. Actual path: `tests/unit/validation/validators/test_step_validators_core.py`.

### 9.3 FIX-019 description contradicts Appendix B on additionalProperties (see 4.1)

The FIX-019 body says `additionalProperties` works correctly with `allOf` in 2020-12. Appendix B correctly says it does NOT. The description is wrong.

### 9.4 FIX-001 says 11 common properties but lists 12 (MINOR)

FIX-001 description says "11 common top-level properties" then lists: `$schema`, `id`, `owner`, `created_at`, `seed_refs`, `spec_refs_ingested`, `generation_quality`, `canonical_refs_used`, `canonical_proposals`, `canonical_conflicts`, `coverage_gaps`, `_migration_notes` -- that is 12 items. The count "11" likely excludes `$schema` (which is being added by AUDIT-027, not currently present). But then it says "Set `required` to the 10 common required fields (all except `_migration_notes` and `$schema`)" -- excluding 2 from 12 gives 10, which is consistent. The "11" should probably be "12" or the list should clarify that `$schema` is being added new.

---

## 10. BATCH BALANCE

### 10.1 Batch 3 is disproportionately large (15 tasks) but low-risk

Batch 3 has 15 description tasks. These are purely additive (adding `"description"` keys to JSON). Risk is near-zero. Highly parallel. Size is appropriate given the 808-property scope.

### 10.2 Batch 2 combines high-risk (FIX-019) with low-risk DRY fixes (SIGNIFICANT)

FIX-019 (allOf adoption, 19 files, highest-risk) is in the same batch as 8 simpler $ref replacement tasks. If FIX-019 fails, it blocks the entire batch. Consider splitting Batch 2 into:
- Batch 2a: FIX-011 through FIX-018 (individual step $ref fixes, low-risk)
- Batch 2b: FIX-019 (allOf base adoption, high-risk)

This way, if allOf adoption encounters issues, the individual DRY fixes are already complete and provide value.

### 10.3 Batch 4 has 11 tasks including breaking changes

Batch 4 is moderately heavy (11 tasks) and includes 3 breaking-change renames. Given the downstream impact (validators, prompts, fixtures), this batch will likely require more iteration time than estimated.

---

## Summary of Required Fixes Before Execution

### Blockers (must fix)

| # | Issue | Section |
|---|---|---|
| B1 | FIX-010 `evidenceObject` property list wrong (`description` should be `evidence_ref` + `section`) | 9.1 |
| B2 | 17 test gate references to non-existent `tests/test_step_validators_core.py` -- correct to `tests/unit/validation/validators/test_step_validators_core.py` | 5.1, 9.2 |
| B3 | FIX-019 description contains incorrect claim about `additionalProperties` + `allOf` -- contradicts correct Appendix B analysis | 4.1, 9.3 |

### Significant (should fix before execution)

| # | Issue | Section |
|---|---|---|
| S1 | AUDIT-031 missing from WONTFIX table; WONTFIX count wrong (4 -> 5) | 1.1 |
| S2 | Summary says 55 tasks, actual count is 59 | 8.1 |
| S3 | Summary LOC estimates (+2400/-1200/+1200) do not match Appendix C (+1349/-1184/+165) | 8.2 |
| S4 | Batch 4 breaking changes lack explicit file-level migration sub-plan | 7.3 |
| S5 | FIX-019 LOC estimate (~988 removal) likely ~2x inflated | 8.3 |
| S6 | AUDIT-052 WONTFIX is overkill for a 2-word doc fix -- should be a FIX task | 6.3 |
| S7 | Batch 2 combines highest-risk task (FIX-019) with low-risk tasks -- consider splitting | 10.2 |
| S8 | FIX-019 should audit tool code for direct schema property traversal beyond `_schema_candidates` | 7.2 |

### Minor

| # | Issue | Section |
|---|---|---|
| M1 | Non-standard dispositions (KEEP/DEFERRED/NO ACTION) not tracked in summary | 1.2 |
| M2 | FIX-001 says "11 properties" but lists 12 | 9.4 |
| M3 | FIX-056/057/058 target `tests/test_schema_quality.py` but should probably be `tests/unit/test_schema_quality.py` | 5.3 |
| M4 | Step 05 Batch 4 changes (FIX-035/036/044) need intermediate test gates | 3.3 |

---

## Overall Assessment

The fix plan is well-structured with correct batch ordering and thorough AUDIT-to-FIX mapping. The 3 blockers are all correctable without restructuring: fix the evidenceObject property list, fix the test paths, and fix the contradictory allOf/additionalProperties claim. The significant issues are mostly documentation accuracy and one strategic recommendation (Batch 2 splitting). Once blockers are resolved, the plan is executable.
