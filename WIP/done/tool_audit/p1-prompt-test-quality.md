# P1-D: Test Quality, Fixtures & Coverage Analysis

Agent Type: Explore (very thorough)
Repo Root: /Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/

## Objective

Audit the test suite for quality, fixture management, coverage gaps, redundancy, and spec/ directory usage. Focus ONLY on test concerns -- not DRY in tool source (P1-B), hardcoding in tool source (P1-C), or separation of concerns (P1-B2).

## Exclusive Scope

- `tests/conftest.py` (46 LOC)
- `tests/integration/conftest.py` (40 LOC)
- Unit test files (`tests/test_*.py`): 50 files, 14,690 LOC
- Integration test files (`tests/integration/test_*.py`): 21 files, 2,933 LOC
- Test fixtures (`tests/fixtures/`): 133 files across 22 directories + 1 top-level file
- `spec/` directory: 3 files (`.gitkeep`, `05_interface_contracts.json`, `common/seed_manifest.json`)

Total: 73 Python files, 17,709 LOC, 830 tests (all passing, zero skips/xfails).

## Known Context (from verified ground truth)

### Verified Counts
- 830 tests collected, 830 passed in 36.16s
- 50 unit test files + 21 integration test files + 2 conftest files = 73 total
- 133 test fixture files (130 JSON + 3 non-JSON in dependency_order/)
- 22 fixture directories + 1 top-level file (`tests/fixtures/14_roadmap.json`)

### spec/ Directory Contents (3 files only)
```
spec/.gitkeep
spec/05_interface_contracts.json
spec/common/seed_manifest.json
```

### R9 Test Files (10 files)
```
tests/test_r9_cli.py              (286 LOC)
tests/test_r9_cross_step.py       (1047 LOC)
tests/test_r9_dag_lint.py         (461 LOC)
tests/test_r9_error_codes.py      (84 LOC)
tests/test_r9_extraction_intent.py (459 LOC)
tests/test_r9_forward_replay.py   (648 LOC)
tests/test_r9_hallucination.py    (584 LOC)
tests/test_r9_matrix.py           (263 LOC)
tests/test_r9_quality_lint.py     (433 LOC)
tests/test_r9_validate.py         (475 LOC)
```

R9 = Round 9 feature additions. R9 tasks referenced in source: T18 (vague language), T20 (content derivation), T22 (content staleness), T24 (coverage thresholds), T26 (extraction intent + W->E promotion), T28 (env-check). R9 added new CLI commands (dag-lint, extraction-intent-check, env-check) and the 59x error code family (E590-E599, W590-W597).

### Conftest Diff (verified)
Both conftest files define `REPO_ROOT` via `Path(__file__).resolve().parents[N]`:
- `tests/conftest.py`: `parents[1]` (up 1 from tests/)
- `tests/integration/conftest.py`: `parents[2]` (up 2 from tests/integration/)

Shared fixtures (5): `repo_root`, `schema_root`, `spec_root`, `canon_root`, `fixtures_root`
Only in `tests/conftest.py` (1): `migration_prompts_root` -- returns `repo_root / "prompts" / "migration"`

### Spec Directory File I/O (verified -- section 12 of ground truth)

Only `tests/integration/test_step_11.py` does direct file I/O from `spec/`:

```python
test_step_11.py:14  def load_json_file(filepath):
test_step_11.py:58  contracts = load_json_file("spec/05_interface_contracts.json")
test_step_11.py:64  sketch = load_json_file("spec/02_system_sketch.json")
test_step_11.py:70  frs = load_json_file("spec/04_fr_list.json")
test_step_11.py:76  nfrs = load_json_file("spec/07_nfrs.json")
test_step_11.py:82  invs = load_json_file("spec/06_invariants.json")
test_step_11.py:88  caps = load_json_file("spec/01_capabilities.json")
test_step_11.py:94  fixtures = load_json_file("spec/08_fixtures.json")
```

Most of these spec files do NOT exist in the repo. Only `spec/05_interface_contracts.json` exists. The `load_json_file` function returns None and prints a warning when the file doesn't exist (verified in test_step_11.py:14-29).

### Source Module Coverage Reference
These source modules exist and need test coverage (for gap analysis):
- `tools/specdev_tools/core/`: errors.py (186), registry.py (85), trace_types.py (53), changelog_parser.py (394)
- `tools/specdev_tools/validation/`: 17 modules + __init__.py + validators/ (21 step files + __init__.py). Notable modules include `_extraction_intent_parser.py` (124), `extraction_intent_check.py` (118), `dag_lint.py` (195).
- `tools/specdev_tools/canonical/`: autofix.py (397), integrity.py (640), lint.py (472), registry.py (318)
- `tools/specdev_tools/generation/`: prompt_generator.py (813), prompt_schema_sync.py (501), schema_differ.py (1331)
- `tools/specdev_tools/migration/`: planner.py (335), runner.py (385), scripts/strip_generation_quality.py (66)
- `tools/specdev_tools/cli.py` (757)
- `tools/core/json_utils.py` (499 -- standalone, outside specdev_tools package)

## IMPORTANT: spec/ Usage Distinction

Tests reference "spec/" in three different ways. Only one is potential misuse:

1. **Actual file I/O from spec/** (open/load_json_file calls) -- POTENTIAL MISUSE (coupling to live spec dir)
2. **String literals in mock return values** (e.g., `mock.return_value = "spec/04_fr_list.json"`) -- NOT misuse
3. **spec_root fixture from conftest** (parameterized path) -- LEGITIMATE

When analyzing, distinguish these three cases carefully.

## Questions (22)

### Spec Directory (4)
1. Which tests do actual file I/O from `spec/` (beyond what is listed in the Known Context above)? Search for `open(`, `json.load`, `load_json_file`, `Path(` with `spec/` arguments.
2. In `test_step_11.py`, what does `load_json_file` return when the file doesn't exist? Does the test handle this gracefully or silently skip assertions?
3. Could `test_step_11.py` be refactored to use test fixtures instead of live spec files? What would break?
4. Are there any other integration tests that implicitly depend on `spec/05_interface_contracts.json` existing?

### Conftest (4)
5. Given that both conftest files exist primarily to set REPO_ROOT at different directory depths, could they be refactored to share a common helper? Or is the duplication justified by pytest's fixture scoping model?
6. Are there fixtures defined inline in individual test files that duplicate conftest fixtures?
7. Is `migration_prompts_root` (only in top-level conftest) actually used by any test? If not, it should be removed.
8. Are there any test files that import directly from conftest rather than using pytest fixture injection?

### Test Quality (5)
9. Which tests have weak assertions? Look for: `assert result is not None`, `assert len(x) > 0`, `assert True`, tests with no assertions, tests that only check return code.
10. Are there duplicate test functions (same logic, different names)? Especially between unit and integration tests.
11. Are there integration tests that should be unit tests (no I/O, no subprocess, all mocked)?
12. Are there unit tests that should be integration tests (require filesystem, subprocess, or real schema files)?
13. Are tests hermetic? Do any tests modify shared state, write to disk without cleanup, or depend on test execution order?

### test_r9_* Pattern (3)
14. What is the relationship between `test_r9_*` files and the pre-existing test files? Specifically check these pairs for overlap:
    - `test_r9_forward_replay.py` (648) vs `test_forward_replay_check.py` (320)
    - `test_r9_hallucination.py` (584) vs `test_hallucination_lint.py` (320)
    - `test_r9_quality_lint.py` (433) vs `test_spec_quality_lint.py` (140)
    - `test_r9_validate.py` (475) vs `test_validate_integration.py` (419)
    - `test_r9_matrix.py` (263) vs any matrix test
    - `test_r9_cli.py` (286) vs `test_cli.py` (1801)
15. Do any `test_r9_*` tests duplicate assertions already covered in pre-existing tests? (Check for identical fixture data + identical assertion logic)
16. Could `test_r9_*` tests be merged into their corresponding pre-existing test files as additional test cases?

### Coverage Gaps (4)
17. Which validators in `tools/specdev_tools/validation/validators/` lack dedicated test files? (Cross-reference the 21 validator files against test files)
18. Which linter modules in `tools/specdev_tools/validation/` lack dedicated test files? (e.g., governance.py at 37 LOC -- is it tested?)
19. Are there untested error paths? Search for error codes (E-codes) that never appear in test assertions.
20. What is the test coverage for `tools/specdev_tools/generation/` (prompt_generator.py 813 LOC, schema_differ.py 1331 LOC) and `tools/specdev_tools/migration/` (planner.py 335 LOC, runner.py 385 LOC)?

### Redundancy (2)
21. Are there unused fixtures (defined in conftest but never referenced by any test)?
22. Are there inline JSON blobs in test files that duplicate existing files in `tests/fixtures/`? Could `@pytest.mark.parametrize` reduce repetition?

## Output Format

Write findings to: `WIP/tool_audit/p1-out-test-quality.md`

Use this format for each finding:

```
### FINDING-T{N}: {short title}

- **Severity**: critical | high | medium | low | info
- **Category**: SPEC_MISUSE | CONFTEST_DUP | TEST_QUALITY | R9_OVERLAP | COVERAGE_GAP | REDUNDANCY | TOKEN_WASTE
- **Location**: {file}:{line} (or {file} if spread across file)
- **Description**: {what the issue is}
- **Evidence**: {specific code or data supporting the finding}
- **Recommendation**: {specific fix}
```

**Limit**: 200 lines maximum. Prioritize critical and high severity findings. Group related minor findings.

## Exclusions

Do NOT report:
- DRY violations in source code (P1-B scope)
- Hardcoded values in source code (P1-C scope)
- Separation of concerns in source code (P1-B2 scope)
- The fact that all 830 tests pass (this is known context, not a finding)
- Zero skips/xfails (this is known context, not a finding)
