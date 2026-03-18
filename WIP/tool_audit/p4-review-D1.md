# P4 Fix Plan Review (Agent D1)

Reviewed: 2026-03-18
Source: `WIP/tool_audit/p4-out-fix-plan.md` (52 FIX tasks, 7 batches)
Against: `p3-out-master-findings.md` (70 AUDIT findings), `p0-ground-truth-FINAL.md`, `p0-baseline.md`, live codebase

---

## Coverage Checklist

| AUDIT-NNN | Mapped to FIX-NNN | Covered? | Notes |
|-----------|-------------------|----------|-------|
| AUDIT-001 | FIX-014, FIX-015, FIX-017 | YES | |
| AUDIT-002 | FIX-001, FIX-004-009 | YES | |
| AUDIT-003 | FIX-001, FIX-004-007, FIX-009-011 | YES | |
| AUDIT-004 | FIX-025 | YES | Docstring only (acceptable) |
| AUDIT-005 | FIX-025 | YES | |
| AUDIT-006 | FIX-035, FIX-036, FIX-037, FIX-051 | YES | |
| AUDIT-007 | FIX-025 (partial) | YES | Documented as future migration |
| AUDIT-008 | FIX-017, FIX-025 (partial) | YES | Documented as future standardization |
| AUDIT-009 | FIX-016, FIX-018 | YES | |
| AUDIT-010 | FIX-042 | YES | |
| AUDIT-011 | FIX-019 | YES | |
| AUDIT-012 | FIX-002, FIX-019, FIX-020 | YES | |
| AUDIT-013 | FIX-047, FIX-048 | YES | |
| AUDIT-014 | FIX-025 | YES | |
| AUDIT-015 | FIX-001, FIX-012, FIX-013 | YES | |
| AUDIT-016 | FIX-001, FIX-007, FIX-008 | YES | |
| AUDIT-017 | FIX-001, FIX-014 | YES | |
| AUDIT-018 | FIX-001, FIX-007-009 | YES | |
| AUDIT-019 | FIX-001, FIX-025 | YES | |
| AUDIT-020 | FIX-029 | YES | Documented, not split |
| AUDIT-021 | FIX-030 | YES | |
| AUDIT-022 | FIX-006, FIX-019 | YES | |
| AUDIT-023 | FIX-023 | YES | |
| AUDIT-024 | FIX-019 | YES | |
| AUDIT-025 | FIX-030 | YES | Partial: 5 commands |
| AUDIT-026 | FIX-025 | YES | Documented as future |
| AUDIT-027 | FIX-039 | YES | |
| AUDIT-028 | FIX-040, FIX-041 | YES | |
| AUDIT-029 | FIX-023, FIX-024 | YES | |
| AUDIT-030 | FIX-001 | YES | |
| AUDIT-031 | FIX-046 | YES | |
| AUDIT-032 | Out of scope | YES | Per user instruction |
| AUDIT-033 | FIX-025 | YES | |
| AUDIT-034 | FIX-051 | YES | |
| AUDIT-035 | FIX-031, FIX-032 | YES | |
| AUDIT-036 | FIX-003, FIX-021, FIX-025, FIX-030 | YES | |
| AUDIT-037 | FIX-016, FIX-018 | YES | |
| AUDIT-038 | FIX-017, FIX-022 | YES | |
| AUDIT-039 | FIX-004, FIX-017 | YES | |
| AUDIT-040 | FIX-002, FIX-019, FIX-021 | YES | |
| AUDIT-041 | FIX-002 | YES | |
| AUDIT-042 | FIX-052 | YES | Roadmap only |
| AUDIT-043 | FIX-025 | YES | |
| AUDIT-044 | FIX-027, FIX-028 | YES | |
| AUDIT-045 | FIX-001, FIX-004-010, FIX-012, FIX-014 | YES | |
| AUDIT-046 | FIX-052 | YES | Roadmap only |
| AUDIT-047 | FIX-033 | YES | |
| AUDIT-048 | FIX-033 | YES | |
| AUDIT-049 | FIX-040 | YES | |
| AUDIT-050 | FIX-026 | YES | |
| AUDIT-051 | FIX-011, FIX-016 | YES | |
| AUDIT-052 | No action | YES | Accepted as-is |
| AUDIT-053 | FIX-025 | YES | |
| AUDIT-054 | FIX-025 | YES | |
| AUDIT-055 | FIX-030 | YES | |
| AUDIT-056 | FIX-034 | YES | |
| AUDIT-057 | FIX-020 | YES | |
| AUDIT-058 | FIX-052 | YES | Roadmap only |
| AUDIT-059 | FIX-020 | YES | |
| AUDIT-060 | FIX-052 | YES | Roadmap only |
| AUDIT-061 | FIX-035 | YES | |
| AUDIT-062 | FIX-033 | YES | |
| AUDIT-063 | FIX-025 | YES | Documented, intentional |
| AUDIT-064 | FIX-030 | YES | |
| AUDIT-065 | FIX-030 | YES | |
| AUDIT-066 | FIX-029 | YES | |
| AUDIT-067 | FIX-050 | YES | |
| AUDIT-068 | FIX-052 | YES | Roadmap only |
| AUDIT-069 | FIX-040, FIX-041 | YES | |
| AUDIT-070 | FIX-038 | YES | |

**Coverage: 70/70 findings mapped. No gaps.**

---

## File Conflict Check

### Batch 0 (FIX-001, FIX-002, FIX-003)
All CREATE new files. **No conflicts.**

### Batch 1 Parallel Set 1A (FIX-004 through FIX-009)
Each touches a different step_*.py file. **No conflicts.**

### Batch 1 Parallel Set 1B (FIX-010 through FIX-014)
Each touches a different file. **No conflicts.**

### Batch 1 Parallel Set 1C (FIX-015 through FIX-022)
Each touches a different file. **No conflicts.**

### Batch 1 Parallel Set 1D (FIX-023, FIX-024)
FIX-023 targets step_16.py; FIX-024 targets step_16a/16b/16c. **No conflicts.**

### Batch 2 (FIX-025 through FIX-029)
All different files. **ISSUE: FIX-028 depends on FIX-027 (shared constant must exist). Plan notes this but the conflict matrix says "all different files" -- this is a DEPENDENCY issue, not a conflict. See Dependency section.**

### Batch 3 (FIX-030 through FIX-037)
All different files. **No conflicts.**

### Batch 4 (FIX-038 through FIX-042)
Sequential by design. **No conflicts.**

### Batch 5 (FIX-043 through FIX-049)
All CREATE new files. **No conflicts.**

### Batch 6 (FIX-050 through FIX-052)
All different files. **No conflicts.**

**Result: Zero file conflicts within any parallel set. CONFIRMED.**

---

## Dependency Verification

### Correct Dependencies

1. Batch 0 -> Batch 1: Correct. Batch 1 tasks import from modules created in Batch 0.
2. FIX-028 depends on FIX-027: Correct. FIX-027 creates the shared `_STEP_TO_TEMPLATE` constant.
3. FIX-038 -> FIX-039, FIX-040: Correct. Directory restructure must complete before renames/conftest changes.
4. FIX-040 -> FIX-041: Correct. Root conftest must be updated before integration conftest.

### MUST_FIX: Intra-Batch Dependency Violations

**D1. FIX-014 depends on FIX-017, but both are in Batch 1 (different parallel sets).**
- FIX-014 is in Parallel Set 1B
- FIX-017 is in Parallel Set 1C
- FIX-014 says "Dependencies: FIX-001, FIX-017 (E141/E142 must be registered in errors.py first)"
- If Set 1B runs before Set 1C, FIX-014 will attempt to verify codes that don't yet exist in errors.py
- **Fix**: Move FIX-014 to Parallel Set 1C (after FIX-017), OR remove the FIX-017 dependency from FIX-014 since FIX-014's description says "Verify E141/E142 usage matches newly registered codes" -- the verification can happen after both are done. The actual step_14.py code already emits E141/E142; the registration is in errors.py (FIX-017). FIX-014's changes to step_14.py (replacing loaders) don't actually depend on errors.py being updated. **Clarify the description: FIX-014 does NOT need FIX-017 as a hard dependency. It modifies step_14.py loaders independently.**

**D2. FIX-015 depends on FIX-017, but both are in Parallel Set 1C.**
- FIX-015 says "Dependencies: FIX-017 (E320 must be registered in errors.py first)"
- FIX-015's description says "No other changes needed; the code emitting E320 is correct, only registration was missing"
- FIX-015 has net 0 LOC change -- it's a verification task, not a modification task
- Within the same parallel set, these could run simultaneously since FIX-015 doesn't actually modify step_13.py
- **Fix**: FIX-015 is effectively a no-op that verifies FIX-017's work. Either merge it into FIX-017 or make it run sequentially after FIX-017.

**D3. FIX-022 depends on FIX-017, but both are in Parallel Set 1C.**
- FIX-022 changes W550 to W551 in seed_lint.py
- FIX-017 registers W551 in errors.py
- If they run in parallel, seed_lint.py would emit W551 before it's registered
- **Fix**: The code change (W550 -> W551) in seed_lint.py doesn't actually depend on the registration at runtime -- the registration is for consistency, not enforcement. But an agent executing FIX-022 would need to know the code is W551. Since FIX-017 defines the code name, **FIX-022 should run after FIX-017 or they need explicit sequencing notes.**

**D4. FIX-024 depends on FIX-023, but both are in Parallel Set 1D.**
- FIX-024 says "Dependencies: FIX-023"
- They are in the same parallel set, meaning they'd run simultaneously
- FIX-024 says "may need no modification" but depends on FIX-023's caching approach
- **Fix**: Mark as sequential within Set 1D: FIX-023 first, then FIX-024.

### SHOULD_FIX: Hidden Dependencies

**D5. FIX-025 removes `run_prompt_schema_sync` import from validate.py and moves it to cli.py (FIX-030).**
- FIX-025 is Batch 2, FIX-030 is Batch 3
- If FIX-025 removes the import without FIX-030 adding it to cli.py, the `prompt-sync` CLI command may break between batches
- **Fix**: FIX-025 description should clarify: remove the import from validate.py AND add a thin wrapper in validation/ or add a TODO comment. The cli.py integration happens in FIX-030 (Batch 3). Verify that the `prompt-sync` subcommand doesn't route through validate.py's import.

**D6. FIX-027 creates `core/constants.py` (or adds to step_order.json), but FIX-027's target is `prompt_generator.py`.**
- Where does the shared constant actually get created? FIX-027 says "Create the constant in core/constants.py if it doesn't exist." But the target file is prompt_generator.py, not core/constants.py.
- FIX-027 would need to CREATE core/constants.py AND modify prompt_generator.py -- this violates the one-file-per-task rule.
- **Fix**: Add a FIX-027a (Batch 2) that creates core/constants.py, then FIX-027 and FIX-028 import from it. Or change FIX-027 to explicitly state it modifies TWO files (with justification).

---

## Task Description Quality

### Tasks Too Vague for Agent Execution

**FIX-024**: "This task verifies that existing tests still pass after the step_16 cache change." This is not an actionable code change -- it's a test gate, not a task. If the caching approach requires caller changes, the description says "if so, add _cache={} parameter" -- an agent cannot determine this without understanding the caching implementation from FIX-023.

**FIX-025**: Mega-refactor with 9 sub-items. While each sub-item is clear, an agent needs to understand all 9 interactions simultaneously. Risk of conflicts between sub-items within the same file. Consider adding explicit ordering notes (e.g., "do item 1 first as it removes an import, then item 5 which replaces env var usage").

**FIX-030**: Also a mega-task (6 sub-items on cli.py). The `--json` output addition is underspecified -- no concrete JSON schema is provided. "Wrap the output of validation commands in JSON format" needs more specifics about which internal API changes are needed.

### Tasks With Excellent Specificity

FIX-001, FIX-002, FIX-003 (Batch 0): Function signatures, parameter lists, and purpose are fully specified. An agent can execute these directly.

FIX-004 through FIX-013 (Batch 1 validators): Clear before/after with specific function replacements.

FIX-019 (hallucination_lint): Five sub-items, each with line numbers and specific changes. Good.

---

## Spot-Check Results

| FIX-NNN | Claim | Verified Against | Match? |
|---------|-------|-----------------|--------|
| FIX-001 | Target: tools/specdev_tools/core/loaders.py (CREATE) | `ls core/` shows no loaders.py | YES -- file doesn't exist, CREATE is correct |
| FIX-002 | Target: tools/specdev_tools/validation/linter_utils.py (CREATE) | `ls validation/` | YES -- file doesn't exist |
| FIX-003 | Target: tools/specdev_tools/core/config.py (CREATE) | `ls core/` | YES -- file doesn't exist |
| FIX-004 | step_05.py has _load_fr_ids at line 85 | grep confirms line 85 | YES |
| FIX-004 | E310 MISSING_ENUM_PROVENANCE at line 27 | grep confirms line 27 | YES |
| FIX-014 | E142 at line 79, E141 at line 126 in step_14.py | grep confirms both | YES |
| FIX-015 | E320 at lines 32, 40, 51 in step_13.py | grep confirms all three | YES |
| FIX-019 | hallucination_lint.py line 277: n["id"] bug | grep confirms `n["id"]` at line 277 | YES |
| FIX-022 | seed_lint.py W550 at line 253 | grep confirms W550 UNDECLARED_SEED at line 253 | YES |
| FIX-025 | validate.py imports run_prompt_schema_sync at line 20 | grep confirms line 20 | YES |
| FIX-025 | validate.py is 537 LOC | wc -l confirms 537 | YES |
| FIX-025 | DEEP_VALIDATORS at line 376 | grep confirms line 376 | YES |
| FIX-025 | _load_json_artifact at line 303 | grep confirms line 303 | YES |
| FIX-026 | governance.py json.load(open(...)) at line 11 | grep confirms line 11 | YES |
| FIX-029 | schema_differ.py subprocess.run at lines 888, 970, 976, 983 | grep confirms all four | YES |
| FIX-029 | schema_differ.py is 1331 LOC | wc -l confirms 1331 | YES |
| FIX-030 | cli.py STEP_NAMES at line 666 | grep confirms line 666 | YES |
| FIX-033 | UNKNOWN.egg-info/ exists | ls confirms directory exists | YES |
| FIX-033 | tools/context/ exists | ls confirms (empty) | YES |
| FIX-040 | migration_prompts_root unused | grep shows only the definition in conftest.py, no test uses it | YES |

**20/20 spot-checks passed. No hallucinations detected in file paths, line numbers, or function names.**

---

## Test Gate Verification

### MUST_FIX: Hallucinated Test File Names

**This is the most critical issue in the entire fix plan.** The following test gate commands reference files that DO NOT EXIST:

| FIX | Test Gate References | Actual File Name | Status |
|-----|---------------------|-----------------|--------|
| FIX-004 | `tests/test_step_05_validator.py` | Does NOT exist | HALLUCINATED |
| FIX-004 | `tests/test_r9_step_05.py` | Does NOT exist | HALLUCINATED |
| FIX-005 | `tests/test_step_06_validator.py` | Does NOT exist | HALLUCINATED |
| FIX-006 | `tests/test_step_07_validator.py` | Does NOT exist (nearest: `test_step_07_deep.py`) | HALLUCINATED |
| FIX-007 | `tests/test_step_08_validator.py` | Does NOT exist | HALLUCINATED |
| FIX-008 | `tests/test_step_12_validator.py` | Does NOT exist | HALLUCINATED |
| FIX-009 | `tests/test_step_13a_validator.py` | Does NOT exist | HALLUCINATED |
| FIX-010 | `tests/test_step_15_validator.py` | Does NOT exist | HALLUCINATED |
| FIX-011 | `tests/test_step_11_validator.py` | Does NOT exist (nearest: `test_step_11_deep.py`) | HALLUCINATED |
| FIX-012 | `tests/test_step_04_validator.py` | Does NOT exist | HALLUCINATED |
| FIX-013 | `tests/test_step_09_validator.py` | Does NOT exist | HALLUCINATED |
| FIX-014 | `tests/test_step_14_validator.py` | Does NOT exist | HALLUCINATED |
| FIX-015 | `tests/test_step_13_validator.py` | Does NOT exist | HALLUCINATED |
| FIX-016 | `tests/test_step_01_validator.py` | Does NOT exist | HALLUCINATED |
| FIX-018 | `tests/test_step_02_validator.py` | Does NOT exist | HALLUCINATED |
| FIX-022 | `tests/test_seed_lint.py` | Does NOT exist | HALLUCINATED |
| FIX-023 | `tests/test_step_16_validator.py` | Does NOT exist | HALLUCINATED |
| FIX-023 | `tests/test_r9_step_16.py` | Does NOT exist | HALLUCINATED |
| FIX-024 | `tests/test_step_16a_validator.py` | Does NOT exist | HALLUCINATED |
| FIX-024 | `tests/test_step_16b_validator.py` | Does NOT exist | HALLUCINATED |
| FIX-024 | `tests/test_step_16c_validator.py` | Does NOT exist | HALLUCINATED |
| FIX-025 | `tests/test_validate.py` | Does NOT exist | HALLUCINATED |
| FIX-025 | `tests/test_r9_warning_promotion.py` | Does NOT exist (but `test_r9_validate.py` exists) | HALLUCINATED |
| FIX-026 | `tests/test_governance.py` | Does NOT exist | HALLUCINATED |
| FIX-039 | `test_r9_step_05.py`, `test_r9_step_16.py`, `test_r9_canonical_lint.py`, `test_r9_canonical_integrity.py`, `test_r9_governance.py`, `test_r9_warning_promotion.py` | None of these exist | HALLUCINATED |

**Actual test file inventory (50 unit test files):**
- Step validators are tested in: `test_step_validators_core.py`, `test_step_validators_03_10.py`, `test_step_05_route_fix.py`, `test_step_07_deep.py`, `test_step_10_deep.py`, `test_step_11_deep.py`
- Integration tests: `tests/integration/test_step_00.py` through `test_step_16.py`
- R9 tests: `test_r9_cli.py`, `test_r9_cross_step.py`, `test_r9_dag_lint.py`, `test_r9_error_codes.py`, `test_r9_extraction_intent.py`, `test_r9_forward_replay.py`, `test_r9_hallucination.py`, `test_r9_matrix.py`, `test_r9_quality_lint.py`, `test_r9_validate.py`

**Files that DO exist and are correctly referenced:**
- `tests/test_hallucination_lint.py` -- OK
- `tests/test_spec_quality_lint.py` -- OK
- `tests/test_forward_replay_check.py` -- OK
- `tests/test_cli.py` -- OK
- `tests/test_canonical_lint.py` -- OK
- `tests/test_canonical_integrity.py` -- OK
- `tests/test_error_code_coverage.py` -- OK
- `tests/test_r9_error_codes.py` -- OK
- `tests/test_r9_validate.py` -- OK
- `tests/test_r9_cli.py` -- OK
- `tests/test_r9_hallucination.py` -- OK (but plan says `test_r9_hallucination_lint.py`)
- `tests/integration/test_step_11.py` -- OK

**Impact**: If agents execute test gates with hallucinated file names, `pytest` will error with "no tests ran" or "file not found." Every FIX task with an incorrect test gate will appear to fail even if the code changes are correct.

### Test Gates That Need Correction

For validator DRY fixes (FIX-004 through FIX-018), the correct test gates should use:
- `pytest tests/test_step_validators_core.py tests/test_step_validators_03_10.py -x --tb=short` (covers steps 01-10)
- `pytest tests/integration/test_step_NN.py -x --tb=short` (integration tests exist per-step)
- Step-specific deep tests where they exist (e.g., `test_step_07_deep.py`, `test_step_11_deep.py`)

For R9 test renames in FIX-039:
- `test_r9_hallucination_lint.py` does not exist; it's `test_r9_hallucination.py`
- `test_r9_step_05.py` does not exist
- `test_r9_step_16.py` does not exist
- `test_r9_canonical_lint.py` does not exist
- `test_r9_canonical_integrity.py` does not exist
- `test_r9_governance.py` does not exist
- `test_r9_warning_promotion.py` does not exist

The FIX-039 rename list includes 10 files but only 10 R9 files exist -- with DIFFERENT names than claimed. The actual R9 files are: `test_r9_cli.py`, `test_r9_cross_step.py`, `test_r9_dag_lint.py`, `test_r9_error_codes.py`, `test_r9_extraction_intent.py`, `test_r9_forward_replay.py`, `test_r9_hallucination.py`, `test_r9_matrix.py`, `test_r9_quality_lint.py`, `test_r9_validate.py`.

---

## Batch Gate Protocol

### Adequacy

The protocol is sound:
1. Full `pytest tests/ -x --tb=short` after each batch -- correct
2. Pass criteria: 830+ tests -- matches baseline
3. Failure handling: revert, re-run, defer -- reasonable

### Issues

**G1. `git add -A` in pre-gate commit**: The batch gate protocol says `git add -A && git commit`. This stages ALL files including potential WIP artifacts, temp files, etc. Should use targeted `git add` of modified paths.

**G2. Expected test count after Batch 5 is "900+"**: Plan says 830 baseline + ~70-80 new tests. The LOC estimates for new test files (FIX-043 through FIX-049) sum to ~1,110 LOC, which at ~10 LOC/test suggests ~110 new tests. "900+" is reasonable but the plan should specify the minimum expected count more precisely.

---

## LOC Estimates

| Batch | Estimated + | Estimated - | Net | Assessment |
|-------|------------|-------------|-----|------------|
| 0 | +390 | -0 | +390 | Reasonable for 3 new modules |
| 1 | +67 | -485 | -418 | Reasonable for DRY replacements |
| 2 | +57 | -110 | -53 | Reasonable |
| 3 | +82 | -31 | +51 | Reasonable for docs + cleanup |
| 4 | +45 | -45 | +0 | Reasonable for restructure |
| 5 | +1,110 | -0 | +1,110 | Reasonable for 7 new test files |
| 6 | +45 | -5 | +40 | Reasonable |
| **Total** | **+1,796** | **-676** | **+1,120** | Plan claims +2,850/-1,420/+1,430 |

**Note**: My summation of individual task estimates yields different totals than the plan's summary. The plan claims +2,850/-1,420/net+1,430 but summing individual tasks gives roughly +1,796/-676/net+1,120. This discrepancy is not critical but suggests the summary was estimated separately from the tasks.

---

## Edge Cases

### AUDIT-052 (step_00 has no validator)
Correctly handled: "No action (acceptable as-is per finding)." step_00 (Charter) has no cross-step references. The fix plan acknowledges this.

### AUDIT-032 (json_utils.py excluded per user)
Correctly handled: "Out of scope per user instruction."

### `break` in step_13a.py:65
Not mentioned in the fix plan. This is the "first-error-only" pattern. FIX-009 modifies step_13a.py but only replaces loaders and upstream_map. The `break` pattern is not addressed. This is acceptable -- it was not flagged as an AUDIT finding.

### Test Reorganization (Batch 4) Import Paths
FIX-038 moves 50 test files into subdirectories. The plan says "Create __init__.py in each new directory" and "Verify all imports and fixture references still resolve." However, the plan does NOT specify:
- Whether conftest.py fixtures use relative imports that would break
- Whether any test file imports from other test files
- Whether pytest.ini / pyproject.toml testpaths need updating

This is a **SHOULD_FIX** -- add a note about checking pytest configuration for testpaths.

---

## Research Alignment

### Roadmap Coverage

The research alignment roadmap at `WIP/future/research-alignment-roadmap.md` covers all 10 ALIGN items:

| ALIGN | Status | In Roadmap? | In FIX Plan? |
|-------|--------|-------------|-------------|
| ALIGN-1 | FUTURE | YES | No (correct) |
| ALIGN-2 | FUTURE | YES | No (correct) |
| ALIGN-3 | PARTIAL | YES | FIX-017, FIX-025, FIX-030 |
| ALIGN-4 | ACHIEVED | YES | No (correct) |
| ALIGN-5 | FUTURE | YES | No (correct) |
| ALIGN-6 | FUTURE | YES | No (correct) |
| ALIGN-7 | PARTIAL | YES | FIX-030 |
| ALIGN-8 | FUTURE | YES | No (correct) |
| ALIGN-9 | PARTIAL | YES | FIX-050 |
| ALIGN-10 | FUTURE | YES | No (correct) |

The 3 folded-in items (ALIGN-3, ALIGN-7, ALIGN-9) are properly reflected:
- **ALIGN-3**: FIX-017 (register codes), FIX-025 (improve W->E), FIX-030 (--json foundation). Roadmap correctly notes full SpecError migration is deferred.
- **ALIGN-7**: FIX-030 adds --json to 5 commands. Roadmap notes remaining 18 commands as future work.
- **ALIGN-9**: FIX-050 adds pytest CI job. Roadmap notes pre-commit hook expansion as future work.

**Assessment: Roadmap is complete and consistent with the fix plan.**

---

## Issues Found

### MUST_FIX

**M1. [CRITICAL] 25+ test gate commands reference hallucinated file names.**
Every FIX task for validator changes (FIX-004 through FIX-018) and several others reference test files that do not exist (e.g., `test_step_05_validator.py`, `test_step_06_validator.py`, etc.). The actual test files have different naming conventions. This will cause every test gate to fail with "file not found" errors, making agents unable to verify their work. See "Test Gate Verification" section for complete list and corrections.

**M2. [HIGH] FIX-039 rename list contains 7 hallucinated R9 file names.**
The rename targets reference files like `test_r9_step_05.py`, `test_r9_step_16.py`, `test_r9_canonical_lint.py` that do not exist. The actual R9 files are: `test_r9_cli.py`, `test_r9_cross_step.py`, `test_r9_dag_lint.py`, `test_r9_error_codes.py`, `test_r9_extraction_intent.py`, `test_r9_forward_replay.py`, `test_r9_hallucination.py`, `test_r9_matrix.py`, `test_r9_quality_lint.py`, `test_r9_validate.py`. The rename mapping must be rebuilt from actual file names.

**M3. [HIGH] Intra-batch dependency violation: FIX-014 depends on FIX-017, but they are in different parallel sets within Batch 1.**
FIX-014 (Set 1B) lists FIX-017 (Set 1C) as a dependency. Parallel sets could execute concurrently. Either remove the false dependency (FIX-014's loader replacement doesn't actually need E141/E142 registration) or move FIX-014 to Set 1C.

**M4. [HIGH] FIX-024 depends on FIX-023, but both are in the same parallel set (1D).**
If they run in parallel, FIX-024 cannot verify or adapt to FIX-023's caching approach. Mark as sequential within Set 1D.

**M5. [HIGH] FIX-027 needs to CREATE core/constants.py but its target file is prompt_generator.py.**
The task modifies two files (creates new + modifies existing) without declaring it. Either split into FIX-027a (create constants.py) + FIX-027 (modify prompt_generator.py), or explicitly document the dual-file exception.

### SHOULD_FIX

**S1. FIX-015 is effectively a no-op verification task (net 0 LOC).**
It depends on FIX-017 and does nothing to step_13.py. Merge into FIX-017 to reduce task count and eliminate the intra-batch dependency.

**S2. FIX-022 and FIX-017 have an implicit ordering dependency within Parallel Set 1C.**
FIX-022 changes W550 to W551, and FIX-017 registers W551. An agent executing FIX-022 needs to know the code name. Add a sequential ordering note.

**S3. FIX-025 removes import from validate.py but FIX-030 (Batch 3) adds it to cli.py.**
Between Batch 2 and Batch 3, the `prompt-sync` command path may be broken. Add a note to FIX-025 about maintaining a temporary shim or verifying the command routing.

**S4. Test reorganization (FIX-038) should verify pytest configuration.**
Check `pyproject.toml` testpaths, `conftest.py` relative imports, and cross-test imports before moving files.

**S5. LOC totals in summary don't match individual task sums.**
Plan summary says +2,850/-1,420/net+1,430 but individual tasks sum to roughly +1,796/-676/net+1,120. Update summary to match.

**S6. Batch gate protocol uses `git add -A`.**
Should use targeted file adds to avoid staging unintended files.

### MINOR

**N1. FIX-019 test gate says `test_r9_hallucination_lint.py` but the actual file is `test_r9_hallucination.py` (no `_lint` suffix).**

**N2. FIX-024 says "step_16a.py, step_16b.py, step_16c.py" in the title but description says they may need no modification. A task that may do nothing is confusing for agents.**

**N3. The R9 test file count in AUDIT-027 says "10 files" which matches the actual count of 10, but the specific file names listed in FIX-039 are wrong.**

**N4. FIX-026 test gate has a conditional: "pytest tests/test_governance.py -x --tb=short (if exists, else pytest tests/ -k governance -x --tb=short)." No file test_governance.py exists, so the fallback will be used, but agents need clear non-conditional instructions.**

---

## Verdict: APPROVED_WITH_FIXES

The fix plan is comprehensive in coverage (70/70 AUDIT findings mapped), well-structured in batching, and free of file conflicts. Source file paths, function names, and line numbers are verified accurate against the live codebase (20/20 spot checks passed). The research alignment roadmap is complete.

However, **execution will fail** without addressing:

1. **M1 (CRITICAL)**: Rebuild ALL test gate commands using actual file names from the codebase
2. **M2 (HIGH)**: Rebuild FIX-039 rename mapping from actual R9 file names
3. **M3-M4 (HIGH)**: Fix intra-batch dependency violations in Batch 1
4. **M5 (HIGH)**: Resolve the FIX-027 dual-file creation issue

These are all fixable without restructuring the plan. The batching strategy, parallel sets, and code change descriptions are sound. The plan should be corrected and re-validated before execution begins.
