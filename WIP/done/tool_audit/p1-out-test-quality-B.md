# P1-D: Test Quality, Fixtures & Coverage Analysis (Run B)

## Executive Summary

830 tests, all passing, zero skips. Key concerns: test_step_11.py integration test reads from live spec/ directory (6 of 7 files don't exist), conftest fixtures are duplicated between top-level and integration, test_r9_* files overlap with pre-existing test files, and several source modules lack dedicated test coverage. The migration_prompts_root fixture is unused.

## Findings

### FINDING-T1: test_step_11.py reads nonexistent spec files
- **Severity**: high
- **Category**: SPEC_MISUSE
- **Location**: `tests/integration/test_step_11.py:58-94`
- **Description**: Integration test calls `load_json_file("spec/05_interface_contracts.json")` and 6 other spec files. Only spec/05_interface_contracts.json exists. The other 6 (02, 04, 06, 07, 08, 01) don't exist. The test likely handles this gracefully (returns None or empty) but this is fragile coupling to live spec state.
- **Evidence**: Grep confirms 7 `load_json_file("spec/...")` calls. Only `spec/05_interface_contracts.json` exists on disk.
- **Recommendation**: Refactor to use test fixtures from `tests/fixtures/` instead of live spec files. Create fixture copies of the needed upstream artifacts.

### FINDING-T2: Conftest fixtures duplicated between top-level and integration
- **Severity**: medium
- **Category**: CONFTEST_DUP
- **Location**: `tests/conftest.py`, `tests/integration/conftest.py`
- **Description**: 5 fixtures are identical between both conftest files: repo_root, schema_root, spec_root, canon_root, fixtures_root. Only REPO_ROOT resolution differs (parents[1] vs parents[2]).
- **Evidence**: Both files define the same 5 fixtures with identical bodies (differing only in REPO_ROOT calculation).
- **Recommendation**: Cannot eliminate integration conftest entirely (REPO_ROOT must resolve differently). Consider extracting shared fixture definitions to a helper module that accepts REPO_ROOT as parameter.

### FINDING-T3: migration_prompts_root fixture appears unused
- **Severity**: low
- **Category**: REDUNDANCY
- **Location**: `tests/conftest.py:43-46`
- **Description**: The `migration_prompts_root` fixture is defined only in the top-level conftest and returns `repo_root / "prompts" / "migration"`. Need to verify if any test file uses it.
- **Evidence**: Defined in conftest but not found in grep of test files importing or using it.
- **Recommendation**: Verify usage; remove if unused.

### FINDING-T4: test_r9_* files overlap with pre-existing tests
- **Severity**: medium
- **Category**: R9_OVERLAP
- **Location**: 10 test_r9_* files (4,740 LOC total)
- **Description**: R9 test files were added alongside pre-existing test files for the same modules. Overlapping pairs: test_r9_forward_replay.py (648 LOC) vs test_forward_replay_check.py, test_r9_hallucination.py (584 LOC) vs test_hallucination_lint.py (18 tests), test_r9_quality_lint.py (433 LOC) vs test_spec_quality_lint.py (10 tests), test_r9_validate.py (475 LOC) vs test_validate_integration.py (19 tests), test_r9_cli.py (286 LOC) vs test_cli.py (39 tests).
- **Evidence**: 5 clear overlapping pairs exist. Both test the same source modules.
- **Recommendation**: Merge R9 tests into their corresponding pre-existing test files. The R9 tests add new test cases for R9-specific features (59x error codes, vague language, etc.) which should be additional test methods in existing files.

### FINDING-T5: Coverage gap -- generation/ package lightly tested
- **Severity**: medium
- **Category**: COVERAGE_GAP
- **Location**: `tools/specdev_tools/generation/` (2,645 LOC total)
- **Description**: schema_differ.py (1331 LOC) and prompt_generator.py (813 LOC) are the two largest modules. Test coverage: test_prompt_schema_sync.py (20 tests) covers prompt_schema_sync.py. Migration tests (test_migration_planner.py 11 tests, test_migration_runner.py 10 tests) cover migration/. But schema_differ.py and prompt_generator.py lack dedicated test files.
- **Evidence**: No test_schema_differ.py or test_prompt_generator.py files exist. Coverage comes indirectly through integration tests.
- **Recommendation**: Add dedicated unit tests for schema_differ.py and prompt_generator.py.

### FINDING-T6: Coverage gap -- governance.py (37 LOC) test coverage unclear
- **Severity**: low
- **Category**: COVERAGE_GAP
- **Location**: `tools/specdev_tools/validation/governance.py`
- **Description**: 37-LOC module. No dedicated test_governance.py file. May be tested indirectly through CLI tests.
- **Evidence**: No test file with "governance" in the name. The governance-check CLI command is tested in test_cli.py.
- **Recommendation**: Add targeted unit tests for check_commit_message() edge cases.

### FINDING-T7: Coverage gap -- invariants.py (86 LOC) has extensive tests
- **Severity**: info
- **Category**: COVERAGE_GAP
- **Location**: `tests/test_invariants.py` (35 test functions)
- **Description**: invariants.py is well-tested with 35 test functions covering the _tiny_eval JSONLogic engine.
- **Evidence**: test_invariants.py has 35 `def test_` entries.
- **Recommendation**: No change needed -- this is well-covered.

### FINDING-T8: tools/core/json_utils.py (345 LOC) has no tests
- **Severity**: medium
- **Category**: COVERAGE_GAP
- **Location**: `tools/core/json_utils.py` (345 LOC)
- **Description**: Standalone module outside specdev_tools package. No test file exists. Module uses subprocess calls to `jq` for JSON manipulation.
- **Evidence**: No test file references json_utils. Module is outside the specdev_tools package tree.
- **Recommendation**: Either add tests or document that this is an external tool helper not part of the core package.

### FINDING-T9: Integration test count seems low relative to source complexity
- **Severity**: low
- **Category**: COVERAGE_GAP
- **Location**: `tests/integration/` (21 files, 2,933 LOC)
- **Description**: 21 integration test files for a pipeline with 22 steps, 25 CLI commands, and 61 source modules. Integration tests focus on steps 14, 16, and step_scripts_bridge. Many CLI commands lack integration tests.
- **Evidence**: Only 3 integration test files target specific steps (test_step_11.py, test_step_14.py, test_step_16.py). Others test infrastructure (conftest, schemas).
- **Recommendation**: Add integration tests for more CLI commands, especially validate-all, canonical-integrity, and align.

## PASS

- All 830 tests pass with zero skips and zero xfails.
- Test fixtures are organized in 22 directories matching step numbers.
- Tests are generally hermetic (use tmp_path or mock).
- conftest fixtures provide clean path resolution for both unit and integration contexts.
- Error code coverage: test_error_code_coverage.py and test_r9_error_codes.py verify error code consistency.
- test_schema_contracts.py (24 tests) validates all schemas load and have required structure.
