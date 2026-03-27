# Test Quality Findings — T-tools-tests-review-007

Source: T-tools-tests-review-007
Criteria: B3 (Parametrization), B4 (Fixture management), B5 (Test-to-code ratio), B7 (Assertion quality)
Date: 2026-03-11

---

## B3 — Parametrization

FINDING | B3-01 | severity=medium | file=tests/test_r9_cross_step.py:56-971 | title=8 cross-step validator classes repeat identical 3-test pattern without parametrization | detail=Each of the 8 TestStep*CrossStep classes (step_05 through step_15) repeats the same 3-method pattern: test_valid_upstream_refs_pass, test_missing_upstream_emits_w590, test_broken_ref_emits_e590. 24 test functions could be collapsed to 3 parametrized functions (one per scenario) with 8 parameter sets each, reducing ~1000 LOC to ~200 LOC. The per-class data (step function, upstream filename, ID format) varies but the assertion structure is identical.

FINDING | B3-02 | severity=low | file=tests/test_hallucination_lint.py:232-278 | title=4 existing_structures tests are valid/invalid pairs that could be parametrized | detail=test_existing_structures_missing_path, test_existing_structures_real_path, test_existing_structures_object_path_missing, test_existing_structures_object_path_real form two valid/invalid pairs. These could be consolidated into a single @pytest.mark.parametrize test with 4 cases (string-missing, string-real, object-missing, object-real).

FINDING | B3-03 | severity=low | file=tests/test_hallucination_lint.py:95-130 | title=command prefix loop uses subTest instead of pytest.mark.parametrize | detail=test_common_js_command_prefixes_are_allowed iterates 5 commands using self.subTest. Since the file already uses unittest.TestCase, subTest is acceptable, but conversion to @pytest.mark.parametrize would provide better failure reporting and parallelization. Same pattern at tests/test_r9_quality_lint.py:73, :110, :132, :368, :391 (5 more subTest loops).

FINDING | B3-04 | severity=medium | file=tests/test_step_validators_core.py:1-146 | title=24 step-validator tests are isolated one-liner functions that could be grouped by validator and parametrized | detail=This file has 24 separate test functions for 12 step validators. Many test the same function with a single valid or invalid input. For example, step_04 has test_step_04_bad_fr_id_format and test_step_04_valid_fr_id — both call validate_step_04 with different data. These could be parametrized by (input, expected_error_pattern) tuples, consolidating 24 functions to ~12 parametrized ones.

FINDING | B3-05 | severity=info | title=Only 8 @pytest.mark.parametrize usages across 736 test functions | detail=Only tests/test_migration_templates.py (4 uses), tests/test_invariants.py (2 uses), and tests/test_gap_remediation.py (2 uses) employ parametrize. The remaining 67 test files use no parametrization at all. Combined with 7 subTest loops, this means ~99% of test functions are manually written per-case. Estimated consolidation potential: 40-60 test functions could be reduced to ~15 parametrized functions.

---

## B4 — Fixture Management

FINDING | B4-01 | severity=medium | file=tests/conftest.py:1-47 | title=All conftest fixtures use default function scope — no session or module scoping | detail=The root conftest.py defines 5 fixtures (repo_root, schema_root, spec_root, canon_root, fixtures_root) all using the default function scope. Zero @pytest.fixture(scope=...) annotations exist across the entire test suite. The repo_root and schema_root fixtures return static Path objects that never change — these should use scope="session" to avoid redundant object creation across 736 tests.

FINDING | B4-02 | severity=medium | file=tests/conftest.py:1-47 | title=Root and integration conftest.py files are nearly identical — duplicated fixture definitions | detail=tests/conftest.py (47 lines) and tests/integration/conftest.py (41 lines) define identical fixtures (repo_root, schema_root, spec_root, canon_root, fixtures_root) with the only difference being REPO_ROOT = Path(__file__).resolve().parents[1] vs .parents[2]. The integration conftest could import from root conftest or use a shared fixture module.

FINDING | B4-03 | severity=medium | title=130 fixture JSON files loaded ad-hoc with no shared caching | detail=The tests/fixtures/ directory contains 130 JSON files. Grep shows 125 json.load/read_text calls across 32 test files. No caching layer (lru_cache, module-level dict, or session-scoped fixture) exists. Files like tests/test_schema_contracts.py (43 JSON loads) and tests/test_prompt_contracts.py (13 loads) parse the same fixture files repeatedly across test methods. A session-scoped fixture that pre-loads all fixtures into a dict would eliminate redundant I/O.

FINDING | B4-04 | severity=low | title=363 tempfile.TemporaryDirectory contexts created across test suite | detail=363 TemporaryDirectory blocks are created across 31 test files. Many tests in the same class create identical directory structures (e.g., test_canonical_integrity.py creates root/canon/spec in 13 separate tests). A class-level or module-level fixture providing a pre-built temp directory skeleton would reduce setup duplication and improve speed.

---

## B5 — Test-to-Code Ratio

FINDING | B5-01 | severity=info | title=Test-to-code LOC ratio is 1.33:1 (17623 test LOC / 13228 source LOC) | detail=736 test functions across 71 test files for 13228 source LOC. Test density is reasonable overall but unevenly distributed.

FINDING | B5-02 | severity=medium | title=7 source modules have zero corresponding test files | detail=The following source modules lack dedicated test files: (1) tools/specdev_tools/validation/docs_lint.py, (2) tools/specdev_tools/validation/governance.py, (3) tools/specdev_tools/validation/seed_lint.py, (4) tools/specdev_tools/canonical/autofix.py, (5) tools/specdev_tools/generation/prompt_generator.py, (6) tools/specdev_tools/generation/schema_differ.py, (7) tools/specdev_tools/core/changelog_parser.py. These modules may receive incidental coverage through integration tests but have no targeted unit tests.

FINDING | B5-03 | severity=low | file=tests/test_cli.py | title=test_cli.py has highest test density: 39 tests in 1801 LOC (46 LOC/test avg) | detail=test_cli.py has 39 test functions at 1801 lines, followed by test_r9_cross_step.py (40 tests, 1047 lines) and test_r9_quality_lint.py (31 tests, 433 lines). The test_cli.py high LOC/test ratio suggests significant setup boilerplate per test that could benefit from shared fixtures or parametrization.

---

## B7 — Assertion Quality

FINDING | B7-01 | severity=medium | file=tests/test_r9_error_codes.py:42 | title=test_no_numeric_suffix_collision has no assertion statement — uses self.fail() in conditional branch only | detail=The function test_no_numeric_suffix_collision (line 42) iterates over error codes and calls self.fail() inside an `if` branch. If no collision exists, the test completes without any assertion executing. This is a code smell — the test passes silently when the expected invariant holds. Should add an explicit assertion after the loop (e.g., assertTrue(True) or assertEqual(len(e_nums), len(e_codes))).

FINDING | B7-02 | severity=low | file=tests/test_registry_error_handling.py:52-67 | title=3 test functions rely solely on pytest.raises context manager — no additional assertions | detail=test_missing_uri_no_default_raises (line 52), test_load_missing_suggests_registry (line 59), and test_load_missing_suggests_repo_root (line 64) use `with pytest.raises(...)` as their only assertion mechanism. While pytest.raises is a valid assertion, the last two tests use `match=` which provides content verification. test_missing_uri_no_default_raises (line 52) only checks exception type without verifying the exception message or contents.

FINDING | B7-03 | severity=low | title=10 isinstance assertions found with limited content verification | detail=10 `assert isinstance(result, ...)` calls found across 5 files (test_migration_runner.py:323, test_migration_templates.py:60, test_errors_submodule.py:13/20/35, test_migration_planner.py:88/163/186, test_gap_remediation.py:79, test_forward_replay_submodule.py:91). Most are followed by additional field-level assertions, which is acceptable. However test_gap_remediation.py:79 (`assert isinstance(result, list)`) and test_forward_replay_submodule.py:91 (`assert isinstance(errors, list)`) only check the container type without verifying contents or length.

FINDING | B7-04 | severity=low | file=tests/test_gap_remediation.py:91 | title=test uses `assert mod is not None` as sole meaningful assertion | detail=At line 91, `assert mod is not None` is the only assertion after importing a module. This verifies importability but not functionality. Only 2 `is not None` assertions exist across the entire suite (this one and test_migration_runner.py:87 which is followed by further assertions), so this is a minor issue.

PASS | B7-05 | title=Majority of test assertions are specific and content-verifying | detail=The dominant assertion pattern across the suite is `self.assertTrue(any("ERROR_CODE" in e for e in errs))` or `self.assertIn("specific_value", result)`, which verifies both the presence and content of error messages. This is a strong pattern. Over 90% of test functions use content-specific assertions.

---

## Summary

| Criterion | Status | Key Issue |
|-----------|--------|-----------|
| B3 Parametrization | FINDING | 40-60 functions consolidatable; only 8 parametrize uses in 736 tests |
| B4 Fixture management | FINDING | No scope annotations; 130 JSON fixtures loaded without caching; conftest duplication |
| B5 Test-to-code ratio | FINDING | 7 source modules lack any test coverage |
| B7 Assertion quality | FINDING | 4 tests with no/weak assertions; majority of suite has good assertion quality |
