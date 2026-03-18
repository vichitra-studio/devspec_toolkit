# P4 Fix Plan Final Review (Agent F1)

**Reviewer:** F1 (Fresh-Eyes Final Review)
**Date:** 2026-03-18
**Documents reviewed:** `p4-out-fix-plan.md`, `p4-review-D1.md`, `p4-review-D2.md`, `p4-fix-report-E.md`, `p3-out-master-findings.md`

---

## D1/D2 Fix Verification

| Fix | Applied Correctly? | Evidence |
|-----|-------------------|----------|
| D1-M1 / D2-MF2: Hallucinated test gate filenames (22 corrections) | YES | Grepped fix plan for all `pytest tests/` commands. All 22 test gates now reference files confirmed to exist in the codebase (e.g., `test_step_validators_core.py`, `test_step_05_route_fix.py`, `integration/test_step_NN.py`). Zero instances of `test_step_NN_validator.py` pattern remain. |
| D1-M2 / D2-MF3: R9 rename list (5 hallucinated names removed) | YES | FIX-039 now lists 10 actual R9 files (`test_r9_cli.py`, `test_r9_cross_step.py`, etc.) verified against `find tests -name 'test_r9_*'`. No hallucinated names remain. |
| D2-MF1: Prompt-schema-sync sequencing bug | YES | FIX-025 now only adds a TODO comment (line 412). FIX-030 item 0 (line 491) performs both removal from validate.py and addition to cli.py atomically. FIX-030 declares validate.py as secondary target (line 489). Gap eliminated. |
| D1-M3: FIX-014 intra-batch dependency | YES | FIX-014 moved from Set 1B to Set 1C (line 251). Sequencing note added (line 256). |
| D1-M4: FIX-024/FIX-023 parallel set conflict | YES | Set 1D relabeled "sequential" (line 998). Explicit ordering: FIX-023 FIRST, FIX-024 AFTER (lines 1000-1002). |
| D1-M5: FIX-027 missing CREATE for constants.py | YES | FIX-027 now declares dual targets: `core/constants.py (CREATE) + prompt_generator.py (MODIFY)` (line 440-441). Change type documented as dual-file exception. |
| D1-S1: FIX-015 no-op merged into FIX-017 | YES | FIX-015 marked as MERGED (line 270). FIX-017 description updated to include E320 verification. |
| D1-S2: FIX-022/FIX-017 ordering | YES | Sequencing note added to FIX-022 (lines 363-364). |
| D1-S3 / D2-MF1: Prompt-schema-sync gap | YES | See D2-MF1 above. |
| D1-S4: FIX-038 pytest configuration check | YES | Items 6 (`pytest --collect-only`) and 7 (check relative imports, sys.path, pyproject.toml testpaths) added (lines 623-624). |
| D1-S5: LOC summary mismatch | YES | Summary updated to `~+1,800 / ~-680 / net ~+1,120` (line 8). |
| D1-S6: Batch gate `git add -A` | YES | Changed to targeted file adds (line 1062). |
| D2-SF1: FIX-025 too large | PARTIAL | Execution ordering guidance added (line 411) but task is NOT split into smaller subtasks as D2 recommended. Still 9 sub-items in one task. |
| D2-SF2: Baseline test count 736 vs 830 | NOT APPLIED | Agent E verified 830 is correct via `pytest --co -q`. D2's count was incorrect per E's verification. Acceptable. |
| D2-SF3: FIX-001 error-handling contract | YES | Error contract added (line 55): empty set on file-not-found, raise on malformed JSON, propagate permission errors. |
| D2-SF4: FIX-038 unnecessary conftest | YES | Explicit note NOT to create intermediate conftest added (line 621). |
| D2-SF5: Intra-batch dependency clarification | YES | See D1-M3 and D1-M4 above. |

**Summary: 15 of 16 fix items fully applied. 1 partial (FIX-025 not split but guidance added).**

---

## Coverage Audit

| AUDIT-NNN | FIX-NNN | Covered? |
|-----------|---------|----------|
| AUDIT-001 | FIX-014, FIX-015 (merged into FIX-017), FIX-017 | YES |
| AUDIT-002 | FIX-001, FIX-004-009 | YES |
| AUDIT-003 | FIX-001, FIX-004-007, FIX-009-011 | YES |
| AUDIT-004 | FIX-025 | YES (docstring only) |
| AUDIT-005 | FIX-025, FIX-030 | YES |
| AUDIT-006 | FIX-035, FIX-036, FIX-037, FIX-051 | YES |
| AUDIT-007 | FIX-025 (partial, documented as future) | YES |
| AUDIT-008 | FIX-017, FIX-025 (partial, documented as future) | YES |
| AUDIT-009 | FIX-016, FIX-018 | YES |
| AUDIT-010 | FIX-042 | YES |
| AUDIT-011 | FIX-019 | YES |
| AUDIT-012 | FIX-002, FIX-019, FIX-020 | YES |
| AUDIT-013 | FIX-047, FIX-048 | YES |
| AUDIT-014 | FIX-025 | YES |
| AUDIT-015 | FIX-001, FIX-012, FIX-013 | YES |
| AUDIT-016 | FIX-001, FIX-007, FIX-008 | YES |
| AUDIT-017 | FIX-001, FIX-014 | YES |
| AUDIT-018 | FIX-001, FIX-007-009 | YES |
| AUDIT-019 | FIX-001, FIX-025 | YES |
| AUDIT-020 | FIX-029 (documented, not split) | YES |
| AUDIT-021 | FIX-030 | YES |
| AUDIT-022 | FIX-006, FIX-019 | YES |
| AUDIT-023 | FIX-023 | YES |
| AUDIT-024 | FIX-019 | YES |
| AUDIT-025 | FIX-030 | YES |
| AUDIT-026 | FIX-025 (documented as future) | YES |
| AUDIT-027 | FIX-039 | YES |
| AUDIT-028 | FIX-040, FIX-041 | YES |
| AUDIT-029 | FIX-023, FIX-024 | YES |
| AUDIT-030 | FIX-001 | YES |
| AUDIT-031 | FIX-046 | YES |
| AUDIT-032 | Out of scope (per user) | YES |
| AUDIT-033 | FIX-025 | YES |
| AUDIT-034 | FIX-051 | YES |
| AUDIT-035 | FIX-031, FIX-032 | YES |
| AUDIT-036 | FIX-003, FIX-021, FIX-025, FIX-030 | YES |
| AUDIT-037 | FIX-016, FIX-018 | YES |
| AUDIT-038 | FIX-017, FIX-022 | YES |
| AUDIT-039 | FIX-004, FIX-017 | YES |
| AUDIT-040 | FIX-002, FIX-019, FIX-021 | YES |
| AUDIT-041 | FIX-002 | YES |
| AUDIT-042 | FIX-052 (roadmap) | YES |
| AUDIT-043 | FIX-025 | YES |
| AUDIT-044 | FIX-027, FIX-028 | YES |
| AUDIT-045 | FIX-001, FIX-004-010, FIX-012, FIX-014 | YES |
| AUDIT-046 | FIX-052 (roadmap) | YES |
| AUDIT-047 | FIX-033 | YES |
| AUDIT-048 | FIX-033 | YES |
| AUDIT-049 | FIX-040 | YES |
| AUDIT-050 | FIX-026 | YES |
| AUDIT-051 | FIX-011, FIX-016 | YES |
| AUDIT-052 | No action (acceptable) | YES |
| AUDIT-053 | FIX-025 | YES |
| AUDIT-054 | FIX-025 | YES |
| AUDIT-055 | FIX-030 | YES |
| AUDIT-056 | FIX-034 | YES |
| AUDIT-057 | FIX-020 | YES |
| AUDIT-058 | FIX-052 (roadmap) | YES |
| AUDIT-059 | FIX-020 | YES |
| AUDIT-060 | FIX-052 (roadmap) | YES |
| AUDIT-061 | FIX-035 | YES |
| AUDIT-062 | FIX-033 | YES |
| AUDIT-063 | FIX-025 (documented) | YES |
| AUDIT-064 | FIX-030 | YES |
| AUDIT-065 | FIX-030 | YES |
| AUDIT-066 | FIX-029 | YES |
| AUDIT-067 | FIX-050 | YES |
| AUDIT-068 | FIX-052 (roadmap) | YES |
| AUDIT-069 | FIX-040, FIX-041 | YES |
| AUDIT-070 | FIX-038 | YES |

**Coverage: 70/70 findings mapped. No gaps.**

---

## Test Gate Validation

Every test gate command was extracted and each referenced file verified against `find tests -name 'test_*.py' | sort`.

### Batch 0 Test Gates (files created in Batch 5 -- gates deferred)

| FIX | Test Gate Command | File Exists? | Notes |
|-----|-------------------|-------------|-------|
| FIX-001 | `pytest tests/test_loaders.py` | NO -- created in Batch 5 as `tests/unit/core/test_loaders.py` | **MISMATCH**: Gate path is `tests/test_loaders.py` but Batch 5 creates it at `tests/unit/core/test_loaders.py` |
| FIX-002 | `pytest tests/test_linter_utils.py` | NO -- created in Batch 5 as `tests/unit/validation/linters/test_linter_utils.py` | **MISMATCH**: Same issue as FIX-001 |
| FIX-003 | `pytest tests/test_config.py` | NO -- created in Batch 5 as `tests/unit/core/test_config.py` | **MISMATCH**: Same issue |

### Batch 1 Test Gates (all files verified to exist)

| FIX | Test Gate Command | File Exists? |
|-----|-------------------|-------------|
| FIX-004 | `pytest tests/test_step_validators_core.py tests/test_step_05_route_fix.py tests/integration/test_step_05.py` | YES (all 3) |
| FIX-005 | `pytest tests/test_step_validators_03_10.py tests/integration/test_step_06.py` | YES (both) |
| FIX-006 | `pytest tests/test_step_07_deep.py tests/test_step_validators_03_10.py tests/integration/test_step_07.py` | YES (all 3) |
| FIX-007 | `pytest tests/test_step_validators_03_10.py tests/integration/test_step_08.py` | YES (both) |
| FIX-008 | `pytest tests/integration/test_step_12.py` | YES |
| FIX-009 | `pytest tests/integration/test_step_13.py` | YES |
| FIX-010 | `pytest tests/integration/test_step_15.py` | YES |
| FIX-011 | `pytest tests/test_step_11_deep.py tests/integration/test_step_11.py` | YES (both) |
| FIX-012 | `pytest tests/test_step_validators_core.py tests/integration/test_step_04.py` | YES (both) |
| FIX-013 | `pytest tests/test_step_validators_03_10.py tests/integration/test_step_09.py` | YES (both) |
| FIX-014 | `pytest tests/integration/test_step_14.py` | YES |
| FIX-015 | MERGED into FIX-017 | N/A |
| FIX-016 | `pytest tests/test_step_validators_core.py tests/test_r9_validate.py tests/integration/test_step_01.py` | YES (all 3) |
| FIX-017 | `pytest tests/test_error_code_coverage.py tests/test_r9_error_codes.py` | YES (both) |
| FIX-018 | `pytest tests/integration/test_step_02.py` | YES |
| FIX-019 | `pytest tests/test_hallucination_lint.py tests/test_r9_hallucination.py` | YES (both) |
| FIX-020 | `pytest tests/test_spec_quality_lint.py` | YES |
| FIX-021 | `pytest tests/test_forward_replay_check.py` | YES |
| FIX-022 | `pytest tests/test_seed_strict_mode.py tests/test_seed_path_validation.py tests/test_seed_propagation_trim.py tests/test_seed_content_overlap.py` | YES (all 4) |
| FIX-023 | `pytest tests/integration/test_step_16.py` | YES |
| FIX-024 | `pytest tests/integration/test_step_16.py tests/test_validate_integration.py -k "step_16"` | YES (both) |

### Batch 2 Test Gates

| FIX | Test Gate Command | File Exists? |
|-----|-------------------|-------------|
| FIX-025 | `pytest tests/test_validate_integration.py tests/test_validate_submodule.py tests/test_r9_validate.py` | YES (all 3) |
| FIX-026 | `pytest tests/ -k governance` | YES (keyword search) |
| FIX-027 | `pytest tests/ -k "prompt_generator or prompt_gen"` | YES (keyword search) |
| FIX-028 | `pytest tests/ -k planner` | YES (keyword search) |
| FIX-029 | `pytest tests/ -k schema_differ` | YES (keyword search) |

### Batch 3 Test Gates

| FIX | Test Gate Command | File Exists? |
|-----|-------------------|-------------|
| FIX-030 | `pytest tests/test_cli.py tests/test_r9_cli.py` | YES (both) |
| FIX-031 | `pytest tests/test_canonical_lint.py` | YES |
| FIX-032 | `pytest tests/test_canonical_integrity.py` | YES |
| FIX-033 | `pytest tests/ -x --tb=short` (full suite) | YES |
| FIX-034 | `pytest tests/ -k "step_16"` | YES (keyword) |
| FIX-035 | `pytest tests/ -x --tb=short -q` | YES (full suite) |
| FIX-036 | `python -c "import tomllib; ..."` | N/A (non-pytest) |
| FIX-037 | N/A (documentation) | N/A |

### Batch 4 Test Gates

| FIX | Test Gate Command | File Exists? |
|-----|-------------------|-------------|
| FIX-038 | `pytest tests/ -x --tb=short` (full suite) | YES |
| FIX-039 | `pytest tests/ -x --tb=short` (full suite) | YES |
| FIX-040 | `pytest tests/ -x --tb=short` | YES |
| FIX-041 | `pytest tests/integration/ -x --tb=short` | YES |
| FIX-042 | `pytest tests/integration/test_step_11.py` | YES |

### Batch 5 Test Gates (all CREATE into new directories from FIX-038)

| FIX | Test Gate Command | File Exists? | Notes |
|-----|-------------------|-------------|-------|
| FIX-043 | `pytest tests/unit/core/test_loaders.py` | NO (will be created by this task) | OK -- file is being created |
| FIX-044 | `pytest tests/unit/validation/linters/test_linter_utils.py` | NO (will be created by this task) | OK |
| FIX-045 | `pytest tests/unit/core/test_config.py` | NO (will be created by this task) | OK |
| FIX-046 | `pytest tests/unit/validation/test_governance.py` | NO (will be created by this task) | OK |
| FIX-047 | `pytest tests/unit/generation/test_schema_differ.py` | NO (will be created by this task) | OK |
| FIX-048 | `pytest tests/unit/generation/test_prompt_generator.py` | NO (will be created by this task) | OK |
| FIX-049 | `pytest tests/unit/validation/test_regression_bugs.py` | NO (will be created by this task) | OK |

### Batch 6 Test Gates

| FIX | Test Gate Command | File Exists? |
|-----|-------------------|-------------|
| FIX-050 | YAML syntax check | N/A |
| FIX-051 | N/A (documentation) | N/A |
| FIX-052 | N/A (documentation) | N/A |

### MUST_FIX Test Gate Issues

**F1-TG1: Batch 0 test gate paths mismatch Batch 5 creation paths.** FIX-001 says its test gate is `pytest tests/test_loaders.py` but FIX-043 creates the test at `tests/unit/core/test_loaders.py`. Same for FIX-002 (`tests/test_linter_utils.py` vs `tests/unit/validation/linters/test_linter_utils.py`) and FIX-003 (`tests/test_config.py` vs `tests/unit/core/test_config.py`). The Batch 0 test gates are noted as "(created in Batch 5)" so they are deferred gates -- but when Batch 5 runs, the paths won't match. **Either update FIX-001/002/003 test gates to match the Batch 5 paths, or update FIX-043/044/045 to create files at the paths FIX-001/002/003 expect.** The current plan creates a contradiction.

---

## File Conflict Re-Check

### Batch 0
FIX-001 (core/loaders.py CREATE), FIX-002 (validation/linter_utils.py CREATE), FIX-003 (core/config.py CREATE). **No conflicts.**

### Batch 1 Set 1A
FIX-004 through FIX-009: each targets a different step_NN.py. **No conflicts.**

### Batch 1 Set 1B
FIX-010 (step_15), FIX-011 (step_11), FIX-012 (step_04), FIX-013 (step_09). **No conflicts.**

### Batch 1 Set 1C
FIX-014 (step_14), FIX-015 (MERGED), FIX-016 (step_01), FIX-017 (errors.py), FIX-018 (step_02), FIX-019 (hallucination_lint), FIX-020 (spec_quality_lint), FIX-021 (forward_replay_check), FIX-022 (seed_lint). All different files. **No conflicts.**

**Implicit dependency note:** FIX-022 depends on FIX-017 (W551 code). FIX-014 depends on FIX-017 (E141/E142 verification). The plan correctly notes these ordering requirements.

### Batch 1 Set 1D
FIX-023 (step_16), FIX-024 (step_16a/b/c). Sequential ordering declared. **No conflicts.**

### Batch 2
FIX-025 (validate.py), FIX-026 (governance.py), FIX-027 (constants.py CREATE + prompt_generator.py MODIFY), FIX-028 (planner.py), FIX-029 (schema_differ.py). **ISSUE: Conflict matrix at line 1009 only lists `generation/prompt_generator.py` for FIX-027 but omits `core/constants.py`.** No actual file conflict since nothing else creates constants.py, but the matrix is incomplete.

### Batch 3
FIX-030 (cli.py + validate.py secondary), FIX-031-037 (various). **ISSUE: FIX-030 declares validate.py as secondary target (line 489), but the conflict matrix at line 1018 only lists `cli.py`.** No actual conflict since FIX-025 (Batch 2) already finished, but the matrix is incomplete.

### Batch 4
Sequential ordering declared. FIX-038 (directory restructure) -> FIX-039 (renames) -> FIX-040 (conftest) -> FIX-041 (integration conftest). FIX-042 parallel with FIX-039. **No conflicts.**

### Batch 5
All CREATE new files. **No conflicts.**

### Batch 6
All different files. **No conflicts.**

---

## Dependency Chain Walkthrough

### Chain 1: loaders.py creation -> consumer DRY fixes -> test reorganization

```
FIX-001 (Batch 0): CREATE core/loaders.py
    |
    v
FIX-004-014 (Batch 1): Import from core.loaders, replace local _load_* functions
    |
    v
FIX-025 (Batch 2): Replace validate.py's _load_* functions with core.loaders imports
    |
    v
FIX-038 (Batch 4): Move all test files to subdirectories
    |
    v
FIX-043 (Batch 5): CREATE tests/unit/core/test_loaders.py
```

**Assessment:** Chain is sound. Each batch builds on the previous. No hidden dependencies.

**Concern:** FIX-001's function signatures are the contract that 15+ consumer tasks depend on. If FIX-001's implementation diverges from the documented signatures, all Batch 1 tasks fail. The plan mitigates this with detailed signatures (lines 49-54) and error contract (line 55). Adequate.

### Chain 2: errors.py fixes -> SpecError references -> validate.py refactor

```
FIX-017 (Batch 1, Set 1C): Register E141/E142/E320, fix W550->W551, fix E310
    |
    +-> FIX-014 (Set 1C): Verify E141/E142 in step_14.py (verification only)
    +-> FIX-022 (Set 1C): Change W550 to W551 in seed_lint.py
    +-> FIX-004 (Set 1A): Fix E310 in step_05.py
    |
    v
FIX-025 (Batch 2): Use new codes in validate.py W->E promotion logic
    |
    v
FIX-049 (Batch 5): Regression tests for E141/E142/E320/W551
```

**Assessment:** Chain is correct. FIX-017 properly precedes its consumers within Set 1C via explicit sequencing notes. FIX-004 is in Set 1A which can run in parallel with Set 1C -- but FIX-004 only changes the label/emitted text for E310, it doesn't depend on the registration happening first (step_05.py already emits E310; FIX-017 just corrects the registry name). This is safe.

**Hidden concern:** FIX-004 item 3 says to "Change E310 emission at line 27 ... or update the emitted label to match registry name" and says "Coordinate with FIX-017 (errors.py)." This coordination is vague -- the agent executing FIX-004 cannot coordinate in real time with an agent executing FIX-017 if they run in parallel (Set 1A vs Set 1C). **The plan should decide which approach to take (rename E310 vs add E311) and state it explicitly, not leave it as a coordination choice.**

### Chain 3: validate.py refactor -> cli.py changes

```
FIX-025 (Batch 2): Refactor validate.py (9 sub-items)
    - Marks prompt_schema_sync import with TODO
    - Replaces _load_* with core.loaders
    - Adds W->E promotion to validate_file()
    |
    v
FIX-030 (Batch 3): cli.py changes
    - Item 0: Atomically removes prompt_schema_sync from validate.py AND adds to cli.py
    - Items 1-6: STEP_NAMES derivation, exception handler, --json, config, docs
```

**Assessment:** Chain is correct after D2-MF1 fix. The atomic removal+addition in FIX-030 eliminates the gap. However, FIX-030 modifying validate.py (secondary target) means validate.py is touched in both Batch 2 (FIX-025) and Batch 3 (FIX-030). This is safe because they are in different batches (sequential), but an agent executing FIX-030 must understand that validate.py was already modified by FIX-025 and work against the post-Batch-2 state of the file.

---

## Agent Executability

Three tasks selected (FIX-006, FIX-026, FIX-042) for spot-check.

### FIX-006: step_07.py -- Replace _load_fr_ids, Fix KNOWN_STAGES, Kebab Regex

| Criterion | Rating |
|-----------|--------|
| Target file clear? | YES -- `tools/specdev_tools/validation/validators/step_07.py` |
| What to do clear? | YES -- 3 specific sub-items with line numbers |
| Dependencies stated? | YES -- FIX-001 |
| Test gate valid? | YES -- all 3 files exist |
| Missing context? | MINOR -- agent needs to know where `canon/kinds/stage.json` is relative to toolkit root. Plan says "loading from `canon/kinds/stage.json`" but doesn't specify the import pattern or how to resolve the path at runtime. |

**Rating: EXECUTABLE** -- minor clarification about canon path resolution needed, but an agent with codebase access can figure it out from existing patterns.

### FIX-026: governance.py -- Fix File Handle Leak

| Criterion | Rating |
|-----------|--------|
| Target file clear? | YES -- `tools/specdev_tools/validation/governance.py` |
| What to do clear? | YES -- single change, exact line number |
| Dependencies stated? | YES -- none |
| Test gate valid? | YES -- `-k governance` keyword search |
| Missing context? | NONE |

**Rating: EXECUTABLE** -- trivially clear.

### FIX-042: test_step_11.py -- Replace Live spec/ Reads With Fixtures

| Criterion | Rating |
|-----------|--------|
| Target file clear? | YES -- `tests/integration/test_step_11.py` |
| What to do clear? | PARTIAL -- says "Replace `load_json_file` calls for 7 spec/ files (lines 58-94) with test fixtures from `tests/fixtures/`" but doesn't specify which fixture files to use or create. Item 2 says "Create minimal fixture files in `tests/fixtures/step_11/` if needed" but doesn't specify what the fixture JSON should contain. |
| Dependencies stated? | YES -- none |
| Test gate valid? | YES |
| Missing context? | YES -- agent needs to understand what data the 7 spec files should contain to keep tests passing. What are the 6 missing spec files? What fields do the tests rely on? |

**Rating: NEEDS_MORE_DETAIL** -- an agent would need to read the test file to understand what fixture data is required, and make judgment calls about fixture content. The plan should specify at minimum: which 7 spec files are referenced, which fields are accessed, and a minimal fixture schema.

| FIX-NNN | Rating | Issues |
|---------|--------|--------|
| FIX-006 | EXECUTABLE | Minor: canon path resolution pattern not specified |
| FIX-026 | EXECUTABLE | None |
| FIX-042 | NEEDS_MORE_DETAIL | Fixture file content unspecified; agent must reverse-engineer test expectations |

---

## New Issues Found

### MUST_FIX

**F1-M1: Batch 0 test gate paths do not match Batch 5 creation paths.** FIX-001's test gate references `tests/test_loaders.py`, FIX-002 references `tests/test_linter_utils.py`, FIX-003 references `tests/test_config.py`. But Batch 5 creates these files at `tests/unit/core/test_loaders.py`, `tests/unit/validation/linters/test_linter_utils.py`, and `tests/unit/core/test_config.py` respectively. The gates are annotated as "(created in Batch 5)" -- but Batch 5 creates them at different paths. When the Batch 5 agent runs FIX-043 and creates `tests/unit/core/test_loaders.py`, the Batch 0 gate path `tests/test_loaders.py` will never resolve. Either update the Batch 0 gate paths to match Batch 5 locations, or have Batch 5 create files at the Batch 0 paths (before FIX-038 moves them). Since FIX-038 (Batch 4) runs before FIX-043 (Batch 5), the `tests/unit/` directories will exist when Batch 5 runs, so the Batch 5 paths are correct. **Fix: update FIX-001/002/003 test gates to `tests/unit/core/test_loaders.py`, `tests/unit/validation/linters/test_linter_utils.py`, `tests/unit/core/test_config.py` respectively.**

**F1-M2: FIX-004 item 3 (E310 fix) requires coordination with FIX-017 but they run in parallel.** FIX-004 (Set 1A) says "Change E310 emission at line 27 ... or update the emitted label to match registry name ... Coordinate with FIX-017." An agent executing FIX-004 cannot coordinate with FIX-017 at runtime. The plan must decide: (a) rename E310 registry entry to MISSING_ENUM_PROVENANCE, or (b) register new E311 code. State the decision explicitly so both agents can act independently.

### SHOULD_FIX

**F1-S1: Conflict matrix is incomplete for dual-target tasks.** FIX-027 (Batch 2) declares dual targets `core/constants.py (CREATE) + prompt_generator.py (MODIFY)` but the Batch 2 conflict matrix only lists `prompt_generator.py`. FIX-030 (Batch 3) declares validate.py as secondary target but the Batch 3 conflict matrix only lists `cli.py`. No actual conflicts result, but the matrix should be accurate for agent reference.

**F1-S2: core/__init__.py has explicit `__all__` and imports but no FIX task updates it.** The existing `core/__init__.py` imports from `errors`, `registry`, and `trace_types` with an `__all__` list. FIX-001 (loaders.py), FIX-003 (config.py), and FIX-027 (constants.py) create new modules in `core/` but no task updates `core/__init__.py` to export from them. Consumer code uses direct imports (e.g., `from specdev_tools.core.loaders import ...`) so this works without `__init__.py` changes, but it creates an inconsistency -- some core modules are re-exported, others are not. Either add exports for all new modules or add a comment explaining the pattern.

**F1-S3: FIX-039 renames happen "within their new subdirectories from FIX-038" but test gates throughout the plan reference old names.** After FIX-039 runs, files like `test_r9_cli.py` become `test_cli_subcommands.py`. But FIX-030's test gate references `tests/test_r9_cli.py`. Since FIX-030 (Batch 3) runs before FIX-039 (Batch 4), this is not a runtime problem -- but it means Batch 4+ test gates that use full suite runs are OK, while any hypothetical re-run of earlier batch gates after Batch 4 would fail. Acceptable as long as gates are only run once per batch in sequence.

**F1-S4: FIX-038 move list references Batch 5 files that don't exist yet.** Line 611 says `test_loaders.py`, `test_config.py` go to `tests/unit/core/` and line 619 notes they "do not yet exist at Batch 4 time." This is correctly documented but the move list is misleading -- it implies these files are being moved when they are not. The note at line 619 clarifies this, but the move list items should be removed or clearly separated as "Batch 5 will create directly here" entries.

**F1-S5: No conftest.py created for Batch 5 test directories.** FIX-038 creates `__init__.py` in each new directory for pytest discovery (line 620). But does `tests/unit/validation/linters/` get an `__init__.py`? The plan lists 7 directories (line 603-609) but `tests/unit/validation/linters/` would need its own `__init__.py` too. This appears to be covered since FIX-038 says "Create `__init__.py` in each new directory" which includes linters/. Confirmed OK on closer reading.

### MINOR

**F1-N1: FIX-025 is still 9 sub-items in one task.** D2 recommended splitting it. Agent E added ordering guidance but did not split. The risk remains that a single agent handles 9 interrelated changes to a 537-LOC file. If one sub-item fails, the entire task must be reverted. Acceptable if the executing agent is competent, but higher risk than split tasks.

**F1-N2: The plan summary says "Max parallel agents per batch: 15 (Batch 1)" (line 6) but the Summary by Batch table says "Max Parallel: 8 (Set 1C)" (line 1079).** The 15 figure counts all Set 1A+1B+1C tasks running at once, while the 8 figure is per-set. These are different metrics and both could be correct, but the inconsistency is confusing. Clarify which number represents the actual parallelism.

**F1-N3: Batch gate expected count "830 tests" is used for Batches 0 through 4 but Batch 5 says "830+" and Final Gate says "900+".** This is internally consistent but the jump between 830 and 900+ should specify the exact expected contribution from each FIX-043 through FIX-049 task (currently they list target test counts: 20+, 15+, 12+, 10+, 15+, 12+, 8+ = 92+ new tests, so "920+" would be more accurate than "900+").

---

## Verdict: APPROVED_WITH_FIXES

The fix plan is comprehensive (70/70 findings covered), well-structured (7 sequential batches, parallel sets within batches), and has been materially improved by Agent E's corrections to D1/D2 findings. The test gate hallucination issue -- the most critical problem found by D1/D2 -- has been fully resolved for Batch 1-4 gates.

**Two remaining MUST_FIX items before execution:**

1. **F1-M1 (path mismatch):** Update Batch 0 test gate paths to match Batch 5 creation locations (`tests/unit/core/test_loaders.py`, etc.). 3-line fix.
2. **F1-M2 (E310 coordination gap):** Decide between renaming E310 or creating E311, and state the decision in both FIX-004 and FIX-017. Eliminates need for runtime agent coordination.

These are both trivially fixable (under 5 minutes combined) and do not require structural changes to the plan. The SHOULD_FIX items are all cosmetic or defensive improvements.

**The plan is ready for execution after these two fixes are applied.**
