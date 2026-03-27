# Findings: Test Structure and Organization

SOURCE: T-tools-tests-review-006
REVIEWED_FILES: tests/**/*.py, tests/conftest.py, tests/integration/conftest.py, tests/test_r9_*.py
DATE: 2026-03-11

---

## B1 — Directory structure

FINDING | B1 | MODERATE | tests/ root has 51 .py files (50 test files + conftest.py) in a flat layout with only 2 subdirectories (fixtures/, integration/). No tests/unit/ directory exists. All unit-style tests sit at root level alongside integration-named files (test_validate_integration.py, test_forward_replay_check_integration.py). Industry standard for 50+ test files is nested by type then feature (tests/unit/canonical/, tests/unit/validation/, etc.). The 73 total .py files across all directories and 736 test functions make navigation difficult without IDE tooling. | tests/:line-N/A | Evidence: `ls tests/*.py | wc -l` returns 51; subdirectories are only `tests/fixtures/` and `tests/integration/` (22 files). Files like `test_canonical_integrity.py`, `test_canonical_lint.py`, `test_canonical_registry.py` could be grouped under `tests/unit/canonical/`; similarly `test_forward_replay_check.py`, `test_forward_replay_check_integration.py`, `test_forward_replay_submodule.py` all address forward-replay but sit flat at root.

## B2 — R9 test duplication

FINDING | B2 | MODERATE | 10 test_r9_*.py files exist with 246 test functions (33% of all 736 tests). Most R9 files test NEW functionality not present in base files and should be KEPT, but the `test_r9_` prefix creates a misleading naming convention implying they are a separate category rather than feature tests. Specific analysis per file:

- **test_r9_validate.py** (27 tests): Tests W->E promotion logic. No overlap with test_validate_integration.py (19 tests on different topics). UNIQUE — KEEP, but rename to test_warning_promotion.py.
- **test_r9_cross_step.py** (40 tests, 1047 lines): Tests 8 cross-step validators. No base test_cross_step.py exists. UNIQUE — KEEP, rename to test_cross_step_validators.py.
- **test_r9_dag_lint.py** (26 tests): No base test_dag_lint.py exists. UNIQUE — KEEP, rename to test_dag_lint.py.
- **test_r9_error_codes.py** (7 tests): Overlaps with test_error_code_coverage.py (2 tests) on code registration checks. test_promotable_pairs_codes_registered duplicates the intent of test_expected_codes_present. 5 of 7 tests are unique. PARTIAL OVERLAP — MERGE into test_error_code_coverage.py.
- **test_r9_extraction_intent.py** (19 tests): No base file. UNIQUE — KEEP, rename to test_extraction_intent.py.
- **test_r9_forward_replay.py** (29 tests): Tests new _extract_content_tokens, _get_downstream_steps, and staleness detection. No overlap with test_forward_replay_check.py (15 tests on different helpers). UNIQUE — KEEP, rename to test_forward_replay_staleness.py.
- **test_r9_hallucination.py** (28 tests): Tests _check_content_derivation, _tokenize. Different scope from test_hallucination_lint.py (18 tests). UNIQUE — KEEP, rename to test_hallucination_derivation.py.
- **test_r9_matrix.py** (19 tests): Tests coverage threshold enforcement. No base test_matrix.py. UNIQUE — KEEP, rename to test_matrix_thresholds.py.
- **test_r9_quality_lint.py** (31 tests): Tests W593 vague language expansion. Different scope from test_spec_quality_lint.py (10 tests). UNIQUE — KEEP, rename to test_quality_vague_language.py.
- **test_r9_cli.py** (20 tests): Tests env-check and dag-lint CLI commands. Zero function name overlap with test_cli.py (39 tests). UNIQUE — KEEP, but consider merging into test_cli.py for a single CLI test surface.

Summary: 246 R9 tests are overwhelmingly unique (240+), with only ~2-3 functions in test_r9_error_codes.py partially overlapping test_error_code_coverage.py. The primary issue is naming convention, not duplication. | tests/test_r9_validate.py:1, tests/test_r9_error_codes.py:1

FINDING | B2 | LOW | test_r9_validate.py lines 367-387 (TestR9PromotablePairsIntegrity) duplicate assertions also present in test_r9_error_codes.py lines 26-40. Both test PROMOTABLE_PAIRS count, W-to-E mapping, and ERROR_CODES registration. One copy should be removed. | tests/test_r9_validate.py:370-387, tests/test_r9_error_codes.py:26-40

## B6 — Test markers

FINDING | B6 | MODERATE | No @pytest.mark.unit or @pytest.mark.integration markers exist anywhere in the test suite. The only @pytest.mark usage is @pytest.mark.parametrize (4 files: test_migration_templates.py:54, test_gap_remediation.py:66, test_invariants.py:86, test_invariants.py:156). Without markers, CI cannot tier tests into fast unit vs slow integration runs. Running `pytest tests/` executes all 736 tests with no ability to selectively run `pytest -m unit` for fast feedback or `pytest -m integration` for full validation. | tests/test_migration_templates.py:54, tests/test_invariants.py:86 | Evidence: `grep -r "@pytest.mark\." tests/ --include="*.py"` returns only parametrize usages, zero unit/integration/slow markers.

## B8 — spec/ as test data

FINDING | B8 | LOW | 12 test files reference `spec/` paths, but analysis shows these are predominantly string literals inside mock return values and test data (e.g., `"spec/04.json"` as part of error message strings in test_r9_validate.py, or mock `_changed_files` return values like `["spec/00_charter.json"]` in test_forward_replay_check.py). These are NOT filesystem reads of the live spec/ directory. The actual spec/ directory contains only production artifacts (05_interface_contracts.json, common/seed_manifest.json), not test data. Key references:

- **test_r9_validate.py**: 30+ refs — all string literals inside injected failure messages (e.g., line 86: `"W571 ASSUMPTION_VAGUE_QUANTIFIER spec/04.json ref=some"`). Would NOT break if spec/ moved.
- **test_forward_replay_check.py**: 10 refs — all inside mock return values for `_changed_files`. Would NOT break.
- **test_r9_cross_step.py**: line 976 — comment about `spec/` subdirectory in tmp. Would NOT break.
- **test_dependency_order_lint.py**: 6 refs — string literals in test data. Would NOT break.
- **tests/integration/test_step_11.py**: lines 58-94 — uses `load_json_file("spec/05_interface_contracts.json")` etc. These DO read from the live spec/ directory and WOULD break if spec/ relocated.
- **tests/integration/test_v2_migration.py**: line 63 — `glob.glob("spec/impl_context/*.json")`. WOULD break.
- **conftest.py**: line 28 — `spec_root` fixture returns `repo_root / "spec"`. WOULD break.

The conftest.py `spec_root` fixture (line 28) and 2 integration test files are the only code that would break if spec/ were relocated. The spec/ directory contains real project artifacts, not test-only data. | tests/conftest.py:28, tests/integration/test_step_11.py:58, tests/integration/test_v2_migration.py:63

## E4 — Test helper duplication

FINDING | E4 | MODERATE | The integration conftest.py (tests/integration/conftest.py) is a near-exact copy of the root conftest.py (tests/conftest.py). The only differences are: (1) the docstring, (2) REPO_ROOT uses `parents[2]` instead of `parents[1]`, and (3) root conftest has one extra fixture `migration_prompts_root`. The 4 shared fixtures (repo_root, schema_root, spec_root, canon_root, fixtures_root) are duplicated verbatim. The integration conftest should inherit from the root conftest via pytest's conftest hierarchy rather than duplicating fixtures. | tests/conftest.py:13-41, tests/integration/conftest.py:13-40

FINDING | E4 | MODERATE | Multiple helper functions are independently reimplemented across test files instead of being extracted to conftest.py or a shared test utilities module:

1. **_make_repo / _make_minimal_repo pattern**: 4 distinct implementations — test_r9_validate.py:25 (`_make_minimal_repo`), test_r9_dag_lint.py:25 (`_make_repo`), test_r9_extraction_intent.py:22 (`_make_repo`), test_r9_matrix.py:78 (`_make_repo_with_thresholds`). Each creates a temporary repo layout with tools/step_order.json. These share ~60% structural overlap but differ in required files.

2. **_write_spec / _write_json pattern**: 5 distinct implementations — test_r9_cross_step.py:38 (`_write_json`), test_r9_forward_replay.py:33 (`_write_json`), test_r9_hallucination.py:35 (`_write_spec`), test_r9_quality_lint.py:193 (`_write_spec`), test_forward_replay_check_integration.py:95 (`_write_spec`). All write JSON to a temp directory.

3. **_write_step_order pattern**: 3 implementations — test_r9_hallucination.py:20, test_forward_replay_check_integration.py:83-89, and inline in test_r9_dag_lint.py:29-43. All write tools/step_order.json.

4. **tempfile.TemporaryDirectory boilerplate**: 60+ occurrences across test files (test_cli.py alone has 30+). A shared pytest fixture using `tmp_path` would reduce this.

A shared `tests/helpers.py` or conftest fixtures for `make_minimal_repo`, `write_spec`, and `write_step_order` would reduce ~200 lines of duplicated setup code. | tests/test_r9_validate.py:25, tests/test_r9_dag_lint.py:25, tests/test_r9_extraction_intent.py:22, tests/test_r9_hallucination.py:20, tests/test_r9_cross_step.py:38

---
