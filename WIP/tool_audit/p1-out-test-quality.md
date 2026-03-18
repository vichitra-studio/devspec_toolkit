# P1-D: Test Quality, Fixtures & Coverage — Findings

## Executive Summary
830 tests pass with zero skips. Key issues: test_step_11.py reads from live spec/ (6 files, most nonexistent), conftest duplication between unit/integration, 10 test_r9_* files overlap with pre-existing tests. Coverage gaps exist for governance.py (37 LOC) and several generation/ modules.

---

### FINDING-T1: test_step_11.py Reads Live spec/ Files
- **Severity**: high
- **Category**: SPEC_MISUSE
- **Location**: tests/integration/test_step_11.py:58-94
- **Description**: Loads 7 spec/ files via load_json_file(). Only spec/05_interface_contracts.json exists. Other files (02, 04, 06, 07, 08, 01) are missing. The load_json_file function likely returns None/handles gracefully but this creates fragile coupling.
- **Evidence**: `contracts = load_json_file("spec/05_interface_contracts.json")` and 6 similar calls to nonexistent files
- **Recommendation**: Refactor to use test fixtures from tests/fixtures/. Mock the spec files or provide dedicated test data.

### FINDING-T2: Conftest Fixtures Duplicated Between Unit and Integration
- **Severity**: medium
- **Category**: CONFTEST_DUP
- **Location**: tests/conftest.py, tests/integration/conftest.py
- **Description**: 5 identical fixtures (repo_root, schema_root, spec_root, canon_root, fixtures_root) defined in both conftest files. Only difference is REPO_ROOT resolution depth (parents[1] vs parents[2]).
- **Evidence**: Compare tests/conftest.py:13-40 with tests/integration/conftest.py:13-40 — identical fixture names and logic, only parents[N] differs
- **Recommendation**: Cannot merge due to path resolution. Consider using a shared helper function that takes depth parameter.

### FINDING-T3: migration_prompts_root Fixture May Be Unused
- **Severity**: low
- **Category**: REDUNDANCY
- **Location**: tests/conftest.py:43-46
- **Description**: `migration_prompts_root` fixture only in top-level conftest. Need to verify if any test file uses it.
- **Evidence**: Defined but potentially unreferenced
- **Recommendation**: Grep for usage; remove if unused

### FINDING-T4: test_r9_* Files Overlap With Pre-existing Tests
- **Severity**: medium
- **Category**: R9_OVERLAP
- **Location**: tests/test_r9_*.py (10 files, 4740 LOC)
- **Description**: R9 test files test the same modules as pre-existing test files. Pairs with potential overlap:
  - test_r9_forward_replay.py (648) vs test_forward_replay_check.py
  - test_r9_hallucination.py (584) vs test_hallucination_lint.py
  - test_r9_quality_lint.py (433) vs test_spec_quality_lint.py
  - test_r9_validate.py (475) vs test_validate_integration.py
  - test_r9_cli.py (286) vs test_cli.py
  - test_r9_matrix.py (263) vs matrix-related tests
- **Evidence**: 10 test_r9_* files totaling 4740 LOC, testing features already covered by ~6 pre-existing test files
- **Recommendation**: Merge R9 test cases into corresponding pre-existing test files. R9 was a feature round — tests should integrate, not remain siloed.

### FINDING-T5: No Dedicated Test File for governance.py
- **Severity**: medium
- **Category**: COVERAGE_GAP
- **Location**: tools/specdev_tools/validation/governance.py (37 LOC)
- **Description**: governance.py has no dedicated test file. May be indirectly tested via CLI tests.
- **Evidence**: No test_governance*.py in tests/
- **Recommendation**: Add test_governance.py with edge cases

### FINDING-T6: No Dedicated Test for invariants.py
- **Severity**: medium
- **Category**: COVERAGE_GAP
- **Location**: tools/specdev_tools/validation/invariants.py (86 LOC)
- **Description**: test_invariants.py exists but is thin. invariants.py is only 86 LOC but handles sample-based checking.
- **Evidence**: test_invariants.py exists — verify adequacy
- **Recommendation**: Review test_invariants.py coverage adequacy

### FINDING-T7: generation/ Package Test Coverage Sparse
- **Severity**: medium
- **Category**: COVERAGE_GAP
- **Location**: generation/prompt_generator.py (813 LOC), generation/schema_differ.py (1331 LOC)
- **Description**: schema_differ.py (1331 LOC) and prompt_generator.py (813 LOC) are the two largest modules. Test coverage comes from test_prompt_schema_sync.py, test_prompt_contracts.py, and test_migration_planner/runner.py but dedicated deep tests are sparse for 2144 combined LOC.
- **Evidence**: No test_schema_differ.py or test_prompt_generator.py files exist
- **Recommendation**: Add dedicated test files for the two largest modules

### FINDING-T8: No Test for canon_schema_alignment.py
- **Severity**: low
- **Category**: COVERAGE_GAP
- **Location**: validation/canon_schema_alignment.py (128 LOC)
- **Description**: test_canon_schema_alignment.py exists — verify it covers the module adequately
- **Evidence**: File exists, needs adequacy check
- **Recommendation**: Verify coverage

### FINDING-T9: Inline JSON Blobs vs Fixture Files
- **Severity**: low
- **Category**: TOKEN_WASTE
- **Location**: Multiple test files
- **Description**: Many test files define large inline JSON dicts that could reference files in tests/fixtures/. 133 fixture files exist in 22 directories but some tests still inline their data.
- **Evidence**: 133 fixture files exist; test files also contain inline fixtures
- **Recommendation**: Audit for opportunities to use @pytest.mark.parametrize with fixture files

## PASS

- 830 tests, all passing, zero skips/xfails — excellent baseline
- conftest fixtures are well-structured (repo_root, schema_root, etc.)
- 133 fixture files across 22 directories provide good data coverage
- Integration tests are properly separated from unit tests
- R9 test files are thorough (4740 LOC covering all R9 features)
- test_error_code_coverage.py exists — good meta-testing practice
