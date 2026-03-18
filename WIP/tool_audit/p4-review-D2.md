# P4 Fix Plan Review (Agent D2)

**Reviewer:** D2 (Executability & Completeness)
**Document reviewed:** `WIP/tool_audit/p4-out-fix-plan.md`
**Date:** 2026-03-18

---

## User Requirements Coverage

| # | Requirement | FIX Tasks | Fully Addressed? | Notes |
|---|-------------|-----------|-----------------|-------|
| 1 | Wiring (run_specdev.sh, tools connected) | FIX-025 (layer violation), FIX-030 (cli.py), FIX-035 (__version__) | PARTIAL | run_specdev.sh itself is never audited or modified. The fix plan only addresses internal Python wiring. If the shell wrapper has issues, they are not covered. |
| 2 | Clean structure | FIX-038 (test reorg), FIX-033 (orphan cleanup), FIX-034 (validators/__init__), FIX-031/032 (docstrings) | YES | |
| 3 | DRY + Separation of Concerns | FIX-001, FIX-002, FIX-003 (foundation), FIX-004-024 (consumers), FIX-025 (validate.py SoC), FIX-027/028 (shared template) | YES | Core strength of the plan. |
| 4 | No hardcoding/assumptions/hallucinations | FIX-006/019 (KNOWN_STAGES from canon), FIX-023 (CHECKLIST_TYPES documented), FIX-030 (STEP_NAMES derived), FIX-001 (parameterized prefixes) | YES | AUDIT-024 (allowed_pr_rules) addressed in FIX-019. AUDIT-058 (filesystem paths) deferred to roadmap. |
| 5 | No redundancy, optimize | FIX-023/024 (step_16 caching), FIX-016/018 (remove duplicate schema validation), FIX-039 (rename R9 tests), FIX-040/041 (conftest dedup) | YES | |
| 6 | spec/ directory as test fixture | FIX-042 (test_step_11.py replace live spec/ reads) | PARTIAL | Only test_step_11.py is explicitly addressed. The plan does not audit whether other tests also read live spec/ files. A sweep for `spec/` references in other test files is missing. |
| 7 | Token/LLM optimization | FIX-025 (structured errors documented), FIX-030 (--json flag), FIX-017 (error registry fixes) | PARTIAL | AUDIT-007 (SpecError migration) and AUDIT-026 (JSON field paths) are both marked "documented as future" rather than implemented. The --json flag in FIX-030 is limited to 5 commands. The core LLM optimization ask (structured error objects) is explicitly deferred. |
| 8 | No gaps, misses, bugs, regressions | FIX-017 (E141/E142/E320 registration), FIX-019 (NFR key bug), FIX-022 (W550 reuse), FIX-025 (W->E in validate_file), FIX-049 (regression tests) | YES | All identified bugs get fixes and regression tests. |
| 9 | Code simplifier (post-fix) | FIX-052 (research alignment roadmap) | PARTIAL | The roadmap document is created but no actual simplification pass is included. The user asked for a post-fix simplification step; the plan only documents future work. |

**Summary:** 5 of 9 fully addressed, 4 partially addressed. The partial items are not blocking -- they are strategic deferrals -- but they should be explicitly acknowledged in the plan summary so the user knows what remains after execution.

---

## Execution Feasibility Assessment

### High-Risk Tasks Needing More Detail

1. **FIX-025 (validate.py mega-refactor):** 10 findings in one task on a 537-LOC file. An agent would need to juggle 9 distinct changes simultaneously. High risk of merge conflicts with Batch 1 changes that also modify validate.py's behavior expectations.

2. **FIX-030 (cli.py multi-change):** 6 findings, 757 LOC file. Adding --json flag requires understanding the output contract of every validation command.

3. **FIX-038 (test reorganization):** Moving 50+ files with pytest discovery implications. Conftest resolution paths change. A single wrong `__init__.py` or conftest placement breaks the entire suite.

4. **FIX-019 (hallucination_lint.py 5-change task):** Touches 5 different concerns in one file. The bug fix (NFR key) is trivial but the DRY refactoring requires understanding the linter_utils API that was just created in Batch 0.

5. **FIX-001 (core/loaders.py creation):** The API surface must exactly match what 15+ consumer tasks in Batch 1 expect. If the function signatures drift from the plan description, every Batch 1 task fails.

### Step-by-Step Walkthrough (5 Complex Tasks)

#### FIX-025: validate.py Mega-Refactor
An agent would need to:
1. Read validate.py (537 LOC) in full.
2. Identify and remove the `from ..generation.prompt_schema_sync import run_prompt_schema_sync` import at line 20 and the call at line 261. Determine where to relocate this call (cli.py dispatch logic).
3. Copy the W->E promotion logic from `validate_dir()` (lines 267-289) and adapt it for `validate_file()`. Import `get_config()` from the newly created `core/config.py`.
4. Replace 5 `_load_*` functions (lines 303-370) with imports from `core/loaders` -- must match FIX-001's exact function signatures.
5. Rewrite string-based W->E promotion at lines 274-282 with regex-based approach.
6. Replace all `os.environ.get("SPECDEV_*")` calls with `get_config().*`.
7. Add a comment about DEEP_VALIDATORS auto-discovery.
8. Add early exit for empty spec dir.
9. Replace `dict.fromkeys` dedup with ordered approach.
10. Add module-level docstring.

**Gap:** The description says "Move prompt-schema-sync invocation to cli.py" but cli.py is NOT a target of FIX-025 -- it's FIX-030 in Batch 3. This creates a **dangling import removal**: after FIX-025, `run_prompt_schema_sync` is no longer called from `validate_dir()`, but FIX-030 (which adds it to cli.py) is 2 batches later. Tests calling `validate_dir()` that expect prompt-schema-sync results will fail between Batch 2 and Batch 3. **This is a sequencing bug.**

#### FIX-001: core/loaders.py Creation
An agent would need to:
1. Survey all 23 `_load_*` functions across 10+ validator files to understand parameter variations.
2. Design `load_upstream_ids()` with a signature flexible enough to cover FR IDs (step 04), API IDs (step 05), capability IDs (step 01), NFR IDs (step 07). Each has different `step_prefix`, `array_key`, `id_field`.
3. Handle step_11's and step_15's `fallback_keys` parameter (divergent key names).
4. Implement `load_sibling_artifact()` for step_14's unique resolution pattern.
5. Implement `check_cross_step_refs()` matching the W590/E590 pattern in 3 validators.
6. Implement `KEBAB_ID_RE` + factory matching 8 copies.
7. Write all with proper error handling, type hints, docstrings.

**Gap:** The description is detailed enough for implementation but does not specify what happens when a spec file is malformed JSON (parse error). The existing `_load_*` functions have varying error handling -- some return None, some return empty set, some silently skip. The plan should specify the unified error contract.

#### FIX-038: Test Restructure
An agent would need to:
1. Create 7 new directories with `__init__.py` files.
2. Move ~50 test files to correct subdirectories.
3. Create `tests/unit/conftest.py`.
4. Verify that pytest can discover all tests in the new structure.
5. Verify conftest fixture resolution (root conftest fixtures auto-propagate to subdirectories in pytest).

**Gap:** The plan says "Create tests/unit/conftest.py that imports shared fixtures from tests/conftest.py" -- but this is unnecessary. Pytest automatically makes root conftest fixtures available to all subdirectories. Creating an intermediate conftest that re-imports would be redundant. The plan should say "NO intermediate conftest needed; pytest propagates root conftest fixtures to all subdirectories automatically."

Also: the plan lists `test_validate.py` as a move target, but `test_validate.py` does not exist in the current codebase. The actual files are `test_validate_integration.py`, `test_validate_submodule.py`, and `test_r9_validate.py`.

#### FIX-030: cli.py Multi-Change
An agent would need to:
1. Read cli.py (757 LOC) to understand the dispatch structure.
2. Load and parse `tools/step_order.json` to derive STEP_NAMES.
3. Implement a global try/except wrapper.
4. Add `--json` flag to argparse and implement JSON output for 5 commands.
5. Replace 6 `os.environ.get()` calls.
6. Receive the `run_prompt_schema_sync` call from validate.py (from FIX-025).

**Gap:** Step 6 (receiving prompt_schema_sync) depends on FIX-025 having already removed it from validate.py. But as noted above, this creates a gap between Batch 2 and Batch 3 where the function is neither in validate.py nor cli.py.

#### FIX-039: Rename R9 Test Files
An agent would need to:
1. Identify all 10 test_r9_* files.
2. Rename each to descriptive name.
3. Merge ~6 overlapping tests from test_r9_error_codes.py into test_error_code_coverage.py.
4. Verify no import references break.

**Gap:** The plan lists `test_r9_step_05.py` and `test_r9_step_16.py` for renaming, but the actual R9 files are: `test_r9_cli.py`, `test_r9_cross_step.py`, `test_r9_dag_lint.py`, `test_r9_error_codes.py`, `test_r9_extraction_intent.py`, `test_r9_forward_replay.py`, `test_r9_hallucination.py`, `test_r9_matrix.py`, `test_r9_quality_lint.py`, `test_r9_validate.py`. There are no `test_r9_step_05.py`, `test_r9_step_16.py`, `test_r9_hallucination_lint.py`, `test_r9_canonical_lint.py`, `test_r9_canonical_integrity.py`, or `test_r9_governance.py` in the codebase. **5 of the 10 proposed renames target files that do not exist.** The actual 10 R9 files have different names than what the plan lists.

---

## Risk Assessment

| Risk | Severity | Affected Tasks | Mitigation |
|------|----------|---------------|------------|
| Prompt-schema-sync gap between Batch 2 and 3 | HIGH | FIX-025, FIX-030 | Move the prompt_schema_sync relocation INTO FIX-025 (add to cli.py in the same task) or defer removal to Batch 3 |
| validate.py mega-refactor breaks tests | HIGH | FIX-025 | Split into 2-3 smaller tasks; test after each sub-change |
| Test reorganization breaks pytest discovery | MEDIUM | FIX-038 | Run `pytest --collect-only` after moves to verify discovery before running tests |
| FIX-001 API mismatch with 15 consumers | HIGH | FIX-001, FIX-004-014 | Include a contract test in FIX-001 that imports and calls each function with representative args |
| R9 file rename targets nonexistent files | MEDIUM | FIX-039 | Update the rename list to match actual file names |
| Test gate references nonexistent test files | MEDIUM | FIX-004-013 | Many test gates reference `test_step_NN_validator.py` which do not exist (see validation below) |
| Batch 1 FIX-014 depends on FIX-017, but they're in same batch | LOW | FIX-014, FIX-015, FIX-022 | Must run FIX-017 before FIX-014/015/022 within Batch 1; plan says parallel sets but these cross parallel set boundaries |

### Rollback Plan
The plan lacks an explicit rollback strategy. If Batch 2 (validate.py refactor) breaks things:
- Git revert the Batch 2 commit(s)
- Batch 0 and Batch 1 changes are additive (new modules + consumer rewrites) and independently stable
- The biggest risk is FIX-025 because it touches the central orchestrator

---

## P3 Completeness Check

### WIP Findings (AUDIT-064 through AUDIT-070)
| Finding | In Fix Plan? | FIX Task |
|---------|-------------|----------|
| AUDIT-064: cli.py monolithic dispatch | YES | FIX-030 (documented, not split) |
| AUDIT-065: No logging, 118 print() calls | YES | FIX-030 (TODO comment only) |
| AUDIT-066: schema_differ git timeout | YES | FIX-029 |
| AUDIT-067: No CI pytest job | YES | FIX-050 |
| AUDIT-068: No property-based testing | YES | FIX-052 (roadmap) |
| AUDIT-069: Conftest session scoping | YES | FIX-040, FIX-041 |
| AUDIT-070: Flat test structure | YES | FIX-038 |

**All 7 WIP cross-check findings are covered.**

Note: P3 lists AUDIT-064 through AUDIT-069 (6 findings from WIP cross-check), plus AUDIT-070 from user feedback. The fix plan summary says "70 of 70 findings covered" which is correct.

### Dropped Findings
| Finding | Correctly Excluded? |
|---------|-------------------|
| A:S10 (pre-commit python -m) | YES -- false positive |
| A:T6 (invariants.py coverage) | YES -- false positive per B |
| A:SL8 (governance.py undersized) | YES -- observation, not problem |
| B:H8 (hardcoded spec field names) | YES -- acceptable by design |
| B:G5/G7/G8 (positive confirmations) | YES -- not findings |
| B:T9 (low integration count) | YES -- observation level |

**All dropped findings correctly excluded.**

### Research Alignment
| ALIGN | In Roadmap/Plan? |
|-------|-----------------|
| ALIGN-3 (structured errors) | Partial in FIX-025, rest in FIX-052 |
| ALIGN-7 (--json all commands) | Partial in FIX-030 (5 commands), rest in FIX-052 |
| ALIGN-9 (pre-commit hooks) | In FIX-052 roadmap |
| ALIGN-1,2,4,5,6,8,10 | All in FIX-052 roadmap |

**All 10 ALIGN items accounted for.**

---

## Live Codebase Validation

| # | Check | Expected | Actual | Match? |
|---|-------|----------|--------|--------|
| 1 | core/loaders.py does NOT exist | Not found | Not found | YES |
| 2 | core/config.py does NOT exist | Not found | Not found | YES |
| 3 | validation/linter_utils.py does NOT exist | Not found | Not found | YES |
| 4 | validation/validate.py EXISTS | Found | Found (537 LOC) | YES |
| 5 | cli.py EXISTS | Found | Found (757 LOC) | YES |
| 6 | core/errors.py EXISTS | Found | Found | YES |
| 7 | STEP_NAMES dict in cli.py | Present at ~line 666 | Confirmed at line 666 | YES |
| 8 | DEEP_VALIDATORS in validate.py | Present at ~line 376 | Confirmed at line 376 | YES |
| 9 | _load_fr_ids duplicated 6 times | 6 copies | 6 copies confirmed (step_05, 06, 07, 08, 12, 13a) | YES |
| 10 | _load_api_ids duplicated 5 times | 5 copies | 5 copies confirmed (step_06, 08, 11, 13a, 15) | YES |
| 11 | KNOWN_STAGES hardcoded in 2 files | step_07.py:9 and hallucination_lint.py:13 | Confirmed both | YES |
| 12 | canon/kinds/stage.json EXISTS | Should exist for KNOWN_STAGES fix | Exists | YES |
| 13 | test_validate.py EXISTS (ref'd in test gates) | Should exist | DOES NOT EXIST | NO |
| 14 | test_seed_lint.py EXISTS (ref'd in FIX-022 test gate) | Should exist | DOES NOT EXIST | NO |
| 15 | test_governance.py EXISTS (ref'd in FIX-026 test gate) | Should exist | DOES NOT EXIST | NO |
| 16 | test_step_NN_validator.py pattern EXISTS | Ref'd in FIX-004-014 | DOES NOT EXIST | NO |
| 17 | test_r9_step_05.py EXISTS (ref'd in FIX-039) | Should exist for rename | DOES NOT EXIST | NO |
| 18 | test_r9_hallucination_lint.py EXISTS (ref'd in FIX-019 test gate) | Should exist | DOES NOT EXIST (actual: test_r9_hallucination.py) | NO |
| 19 | prompt_schema_sync import in validate.py | Line 20 | Confirmed at line 20 | YES |
| 20 | _collect_ids_and_refs in both linters | hallucination_lint.py and spec_quality_lint.py | Confirmed (lines 138 and 215 respectively) | YES |
| 21 | Total test function count ~830 | Plan says "830 tests" | Actual: 736 test functions | NO |
| 22 | tests/unit/ directory does NOT exist | Not found | Not found (correct for CREATE) | YES |

**6 of 22 checks FAIL.** The primary issues are:
- Test gate commands reference test files that do not exist under the names used
- The actual R9 file names differ from plan's rename list
- The baseline test count is 736, not 830

---

## Test Strategy Review

### Batch 4 (Test Reorganization)
- **conftest.py paths:** The plan correctly identifies the root conftest and integration conftest as targets. However, it unnecessarily proposes creating `tests/unit/conftest.py` that re-imports from root -- pytest handles this automatically through conftest propagation.
- **Missing concern:** After moving files to subdirectories, any tests using relative imports or `sys.path` manipulation will break. The plan does not mention checking for this.

### Batch 5 (New Tests)
- **Test targets are correct modules:** test_loaders.py (core/loaders.py), test_linter_utils.py (validation/linter_utils.py), test_config.py (core/config.py), test_governance.py (validation/governance.py), test_schema_differ.py (generation/schema_differ.py), test_prompt_generator.py (generation/prompt_generator.py). All correct.
- **Expected test count:** Plan says baseline 830, expects 900+ after Batch 5. Actual baseline is 736. With ~80 new tests from Batch 5, expect ~816. The plan's numbers are inflated by ~13%.
- **Circular dependency risk:** None identified. New test files are pure consumers of the modules they test.

### Test Gate Accuracy
Many FIX tasks reference test files that do not exist in the current codebase:
- `test_step_05_validator.py` -- does not exist (actual: `test_step_05_route_fix.py`)
- `test_step_06_validator.py` through `test_step_15_validator.py` -- do not exist
- `test_validate.py` -- does not exist (actual: `test_validate_integration.py`, `test_validate_submodule.py`)
- `test_seed_lint.py` -- does not exist (seed testing split across `test_seed_*.py` files)
- `test_governance.py` -- does not exist (created in FIX-046)
- `test_r9_hallucination_lint.py` -- does not exist (actual: `test_r9_hallucination.py`)
- `test_r9_step_05.py`, `test_r9_step_16.py` -- do not exist
- `test_r9_canonical_lint.py`, `test_r9_canonical_integrity.py` -- do not exist
- `test_r9_governance.py`, `test_r9_warning_promotion.py` -- do not exist

The test gates would need to reference actual file names or use `-k` keyword matching instead. This is a systematic issue affecting ~20 of the 52 tasks.

---

## Issues Found

### MUST_FIX

**D2-MF1: Prompt-schema-sync sequencing bug.** FIX-025 (Batch 2) removes `run_prompt_schema_sync` from validate.py, but FIX-030 (Batch 3) is where it gets added to cli.py. Between Batch 2 and Batch 3, this functionality is orphaned. Either (a) move the cli.py addition into FIX-025, (b) defer the removal to FIX-030, or (c) create a Batch 2 task that adds a thin cli.py wrapper for prompt_schema_sync.

**D2-MF2: Test gate file names are wrong for ~20 tasks.** The test gates reference files like `test_step_05_validator.py`, `test_validate.py`, `test_seed_lint.py` that do not exist. An executing agent will see "file not found" and either skip the gate or fail. Every test gate must be validated against actual filenames.

**D2-MF3: FIX-039 rename list references 5 nonexistent files.** The plan lists renames for `test_r9_step_05.py`, `test_r9_step_16.py`, `test_r9_hallucination_lint.py`, `test_r9_canonical_lint.py`, `test_r9_canonical_integrity.py`, and `test_r9_governance.py` -- none of which exist. The actual 10 R9 files are: `test_r9_cli.py`, `test_r9_cross_step.py`, `test_r9_dag_lint.py`, `test_r9_error_codes.py`, `test_r9_extraction_intent.py`, `test_r9_forward_replay.py`, `test_r9_hallucination.py`, `test_r9_matrix.py`, `test_r9_quality_lint.py`, `test_r9_validate.py`. The rename map must be corrected.

### SHOULD_FIX

**D2-SF1: FIX-025 is too large for a single task.** 10 findings in one 537-LOC file is high risk. Recommend splitting into: (a) FIX-025a: layer violation + config + load replacements; (b) FIX-025b: W->E promotion fixes; (c) FIX-025c: documentation + edge cases.

**D2-SF2: Baseline test count is 736, not 830.** All batch gates and the final gate reference "830 tests passing." This should be corrected to ~736 (or whatever `pytest --co -q` reports) to avoid false alarm when agents see fewer tests than expected.

**D2-SF3: FIX-001 needs an error-handling contract.** The plan specifies the happy-path API but not what happens on malformed JSON, missing files, or permission errors. Existing loaders have inconsistent handling (None vs empty set vs silent skip). The plan should specify: return empty set on file-not-found, raise on malformed JSON.

**D2-SF4: FIX-038 proposes unnecessary intermediate conftest.** `tests/unit/conftest.py` that re-imports from root conftest is unnecessary -- pytest propagates root conftest fixtures to all subdirectories automatically. Remove this step to avoid confusion.

**D2-SF5: Intra-batch dependency ordering in Batch 1 needs clarification.** FIX-014 and FIX-015 depend on FIX-017 (errors.py), and FIX-022 depends on FIX-017. These are in different parallel sets (1B, 1C) but FIX-017 is also in 1C. The plan implies 1A/1B/1C/1D run in parallel, but 1C:FIX-017 must complete before 1B:FIX-014/015 can run. Clarify the intra-batch ordering constraint.

### MINOR

**D2-M1: User requirement 6 (spec/ as test fixture) only addresses test_step_11.py.** A grep for other tests reading live spec/ files would strengthen confidence.

**D2-M2: User requirement 9 (code simplifier) is only a roadmap document.** Consider noting explicitly in the plan summary that a post-fix simplification pass is out of scope for this plan.

**D2-M3: FIX-052 is a catch-all documentation task.** 7 AUDIT findings are mapped to it (AUDIT-042, 046, 058, 060, 068 + ALIGN items). Verify the roadmap document actually covers all of these.

**D2-M4: FIX-026 test gate says "pytest tests/test_governance.py (if exists, else ...)"** -- the conditional test gate is good practice but should be standardized across all tasks.

---

## Verdict: APPROVED_WITH_FIXES

The fix plan is comprehensive, well-structured, and covers all 70 findings with appropriate batch sequencing. The three MUST_FIX issues are:

1. **Prompt-schema-sync sequencing bug** -- a real functional gap between Batch 2 and 3.
2. **Wrong test file names in ~20 test gates** -- agents will fail to run verification.
3. **FIX-039 rename list is wrong** -- 5 of 10 rename targets do not exist.

These are correctible without restructuring the plan. The SHOULD_FIX items (splitting FIX-025, correcting test count baseline, clarifying intra-batch deps) would improve execution reliability but are not blocking.
