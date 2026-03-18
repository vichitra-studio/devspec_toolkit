# P4 Fix Report (Agent E)

**Date:** 2026-03-18
**Source reviews:** `p4-review-D1.md`, `p4-review-D2.md`
**File fixed:** `p4-out-fix-plan.md`

---

## MUST_FIX Items Applied

### 1. Hallucinated Test Gate Filenames (D1-M1, D2-MF2) -- CRITICAL

**Status: FIXED (22 test gates corrected)**

Discovery: Ran `find tests -name 'test_*.py' | sort` to get the actual 70 test files. Confirmed baseline of 830 tests via `pytest --co -q`.

All test gate commands in the fix plan were verified against actual file inventory. Corrections applied:

| FIX | Old (hallucinated) | New (actual) |
|-----|-------------------|-------------|
| FIX-004 | `test_step_05_validator.py`, `test_r9_step_05.py` | `test_step_validators_core.py`, `test_step_05_route_fix.py`, `integration/test_step_05.py` |
| FIX-005 | `test_step_06_validator.py` | `test_step_validators_03_10.py`, `integration/test_step_06.py` |
| FIX-006 | `test_step_07_validator.py` | `test_step_07_deep.py`, `test_step_validators_03_10.py`, `integration/test_step_07.py` |
| FIX-007 | `test_step_08_validator.py` | `test_step_validators_03_10.py`, `integration/test_step_08.py` |
| FIX-008 | `test_step_12_validator.py` | `integration/test_step_12.py` |
| FIX-009 | `test_step_13a_validator.py` | `integration/test_step_13.py` |
| FIX-010 | `test_step_15_validator.py` | `integration/test_step_15.py` |
| FIX-011 | `test_step_11_validator.py` | `test_step_11_deep.py`, `integration/test_step_11.py` |
| FIX-012 | `test_step_04_validator.py` | `test_step_validators_core.py`, `integration/test_step_04.py` |
| FIX-013 | `test_step_09_validator.py` | `test_step_validators_03_10.py`, `integration/test_step_09.py` |
| FIX-014 | `test_step_14_validator.py` | `integration/test_step_14.py` |
| FIX-015 | `test_step_13_validator.py` | (merged into FIX-017; no standalone gate) |
| FIX-016 | `test_step_01_validator.py` | `test_step_validators_core.py`, `test_r9_validate.py`, `integration/test_step_01.py` |
| FIX-018 | `test_step_02_validator.py` | `integration/test_step_02.py` |
| FIX-019 | `test_r9_hallucination_lint.py` | `test_r9_hallucination.py` |
| FIX-022 | `test_seed_lint.py` | `test_seed_strict_mode.py`, `test_seed_path_validation.py`, `test_seed_propagation_trim.py`, `test_seed_content_overlap.py` |
| FIX-023 | `test_step_16_validator.py`, `test_r9_step_16.py` | `integration/test_step_16.py` |
| FIX-024 | `test_step_16a/b/c_validator.py` | `integration/test_step_16.py`, `test_validate_integration.py -k step_16` |
| FIX-025 | `test_validate.py`, `test_r9_warning_promotion.py` | `test_validate_integration.py`, `test_validate_submodule.py`, `test_r9_validate.py` |
| FIX-026 | `test_governance.py (if exists, else ...)` | `pytest tests/ -k governance` (unconditional) |

Zero hallucinated test file names remain in the fix plan. Verified via grep.

### 2. R9 Rename List (D1-M2, D2-MF3)

**Status: FIXED**

FIX-039's rename list was rebuilt from the actual 10 R9 test files:
- `test_r9_cli.py` -> `test_cli_subcommands.py`
- `test_r9_cross_step.py` -> `test_cross_step_validation.py`
- `test_r9_dag_lint.py` -> `test_dag_lint_rules.py`
- `test_r9_error_codes.py` -> `test_error_code_registry.py`
- `test_r9_extraction_intent.py` -> `test_extraction_intent_rules.py`
- `test_r9_forward_replay.py` -> `test_forward_replay_rules.py`
- `test_r9_hallucination.py` -> `test_hallucination_lint_rules.py`
- `test_r9_matrix.py` -> `test_matrix_rules.py`
- `test_r9_quality_lint.py` -> `test_quality_lint_rules.py`
- `test_r9_validate.py` -> `test_validate_deep.py`

All 5 previously hallucinated names (`test_r9_step_05.py`, `test_r9_step_16.py`, `test_r9_canonical_lint.py`, `test_r9_canonical_integrity.py`, `test_r9_governance.py`, `test_r9_warning_promotion.py`) removed.

### 3. Prompt-Schema-Sync Sequencing (D2-MF1)

**Status: FIXED**

Solution: Deferred the import removal from FIX-025 (Batch 2) to FIX-030 (Batch 3). FIX-025 now only adds a TODO comment marking the import for migration. FIX-030 was updated with a new item 0 that performs both the removal from validate.py and the addition to cli.py atomically. This eliminates the gap where `run_prompt_schema_sync` would be orphaned. FIX-030 now declares validate.py as a secondary target.

### 4. Intra-Batch Dependency Violations (D1-M3, D1-M4)

**Status: FIXED**

- **FIX-014**: Moved from Parallel Set 1B to Parallel Set 1C (where FIX-017 lives). Added sequencing note explaining the dependency is for verification only.
- **FIX-024 / FIX-023**: Set 1D relabeled from "Parallel" to "Sequential". Added explicit ordering: FIX-023 first, FIX-024 after.
- **Conflict matrix updated** to reflect FIX-014's move.

### 5. Missing CREATE for constants.py (D1-M5)

**Status: FIXED**

FIX-027 now explicitly declares dual targets: `core/constants.py` (CREATE) + `prompt_generator.py` (MODIFY). The change type is documented as a dual-file exception with justification. The description now says to create `core/constants.py` first, then import from it in `prompt_generator.py`.

---

## SHOULD_FIX Items Applied

| ID | Item | Status |
|----|------|--------|
| D1-S1 | FIX-015 is a no-op verification | FIXED: Merged into FIX-017. FIX-015 marked as MERGED with explanation. FIX-017 description updated to include E320 verification. |
| D1-S2 | FIX-022/FIX-017 ordering within Set 1C | FIXED: Added sequencing note to FIX-022 specifying FIX-017 must complete first. |
| D1-S3 / D2-MF1 | Prompt-schema-sync gap | FIXED: See MUST_FIX #3 above. |
| D1-S4 | FIX-038 pytest configuration check | FIXED: Added items 6 (pytest --collect-only) and 7 (check relative imports, sys.path, pyproject.toml testpaths). |
| D1-S5 | LOC summary mismatch | FIXED: Updated summary from "+2,850/-1,420/net+1,430" to "~+1,800/~-680/net~+1,120". |
| D1-S6 | Batch gate `git add -A` | FIXED: Changed to targeted file adds with warning about `git add -A`. |
| D2-SF1 | FIX-025 too large | FIXED: Added execution ordering guidance (imports/config first, logic changes second, documentation last). Layer violation removal deferred to FIX-030. |
| D2-SF2 | Baseline test count 736 vs 830 | NOT CHANGED: Verified actual baseline is 830 tests (`pytest --co -q` confirms). D2's check was incorrect. |
| D2-SF3 | FIX-001 error-handling contract | FIXED: Added explicit error contract: empty set on file-not-found, raise on malformed JSON, propagate permission errors. |
| D2-SF4 | FIX-038 unnecessary conftest | FIXED: Replaced "Create tests/unit/conftest.py" with explicit note NOT to create it, explaining pytest auto-propagation. |
| D2-SF5 | Intra-batch dependency clarification | FIXED: See MUST_FIX #4 above. |

---

## MINOR Items Applied

| ID | Item | Status |
|----|------|--------|
| D1-N1 | `test_r9_hallucination_lint.py` wrong suffix | FIXED in test gate corrections. |
| D1-N4 | FIX-026 conditional test gate | FIXED: Replaced with unconditional `-k governance`. |

---

## Items NOT Changed (With Rationale)

| Item | Rationale |
|------|-----------|
| D2-SF2 (test count 736 vs 830) | Verified 830 is correct. D2's count was wrong. |
| D1-N2 (FIX-024 may-do-nothing confusion) | Task description already says "verifies existing tests" which is a valid task. Left as-is. |
| D1-N3 (R9 file count) | Fixed by correcting the rename list. |
| D1-G2 (post-Batch 5 count precision) | The "900+" estimate is reasonable given 830 baseline + ~80-110 new tests. |
| D2-M1 (spec/ fixture sweep) | Out of scope for fix plan corrections -- this is a new audit finding, not a plan error. |
| D2-M2 (post-fix simplifier) | Correctly deferred to FIX-052 roadmap. Not a plan error. |
| D2-M3 (FIX-052 catch-all) | Acceptable -- these are all documentation/roadmap items grouped together. |

---

## FIX-038 Move List Updated

The file move list in FIX-038 was rebuilt from actual test file names (70 unit test files + 20 integration files). Previously referenced nonexistent files like `test_validate.py`, `test_seed_lint.py`, `test_r9_hallucination_lint.py`, `test_r9_canonical_*.py`. Now uses actual filenames with comprehensive subdirectory mapping. Added note that Batch 5 test files (test_loaders.py, test_config.py, etc.) are created directly in their target directories, not moved.

---

## Verification

Post-edit consistency checks:
1. `grep test_step_.*_validator.py` -- 0 matches (all hallucinated names removed)
2. `grep test_r9_step_` -- 0 matches
3. `grep test_r9_hallucination_lint` -- 0 matches
4. `grep test_r9_canonical_lint` -- 0 matches
5. `grep test_r9_warning_promotion` -- 0 matches
6. `grep test_validate\.py` -- 0 matches (bare name, not `test_validate_integration.py`)
7. `grep test_seed_lint\.py` -- 0 matches
8. All FIX-014 references now show Set 1C, not Set 1B
9. Set 1D now labeled "sequential" with explicit ordering
10. FIX-027 declares dual targets (CREATE + MODIFY)
11. FIX-030 includes validate.py as secondary target for prompt-schema-sync removal
