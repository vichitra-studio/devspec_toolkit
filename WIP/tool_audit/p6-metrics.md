# P6: Before/After Metrics Comparison

Captured at: 2026-03-18
Branch: codex/canonical-drift-review-plan
Baseline reference: `WIP/tool_audit/p0-baseline.md` (2026-03-17T18:42:25Z)

## Summary

997 tests collected, 997 passed, 0 failed. Full green suite.

## Before/After Comparison

| Metric | Before (P0) | After (P6) | Delta |
|--------|-------------|------------|-------|
| **Tests collected** | 830 | 997 | +167 (+20.1%) |
| **Tests passed** | 830 | 997 | +167 |
| **Tests failed** | 0 | 0 | 0 |
| **Test runtime** | — | 34.23s | — |
| **Source files (specdev_tools/)** | 61 | 65 | +4 |
| **Source LOC (specdev_tools/)** | 13,228 | 13,426 | +198 (+1.5%) |
| **Test .py files (all)** | 73 | 88 | +15 |
| **Test LOC** | 17,709 | 19,047 | +1,338 (+7.6%) |
| **Unit test files** | 50 | 57 | +7 |
| **Integration test files** | 21 | 21 | 0 |
| **Conftest files** | 2 | 2 | 0 |
| **Unit test subdirectories** | — | 5 | — |
| **`_load_*` functions (validators/)** | 23 | 6 | -17 (consolidated) |
| **Schema registry entries** | 29 | 29 | 0 |
| **CLI subcommands** | 25 | 25 | 0 |
| **Error codes total** | 77 | 82 | +5 |
| **E-codes** | 52 | 56 | +4 |
| **W-codes** | 25 | 26 | +1 |
| **PROMOTABLE_PAIRS** | 18 | 19 | +1 |
| **Test fixture files** | 133 | 133 | 0 |
| **Schema files** | 24 | 24 | 0 |
| **pyproject.toml version** | 0.4.0 | 0.4.0 | 0 |
| **Step count (step_order.json)** | 22 | 22 | 0 |
| **DEEP_VALIDATORS entries** | 21 | 21 | 0 |
| **validate_step_* entry points** | 21 | 21 | 0 |
| **Top-level test files (tests/test_*.py)** | — | 0 | all moved to unit/ |
| **R9 test files** | — | 0 | — |

## Import Consolidation Metrics

| Shared import | Count |
|---------------|-------|
| `core.loaders` imports | 11 |
| `linter_utils` imports | 3 |
| `core.config` imports | 3 |

## Key Observations

1. **Test growth**: +167 tests (+20.1%) with zero failures — all new coverage from the audit fixes.
2. **Source LOC efficiency**: Only +198 source LOC (+1.5%) to support the additional validation, indicating consolidation offset new code.
3. **`_load_*` consolidation**: 23 -> 6 duplicated loader functions in validators — 17 removed via DRY refactoring.
4. **Error code expansion**: 5 new codes (4 E-codes, 1 W-code) added for tighter validation.
5. **Test file restructuring**: +15 test files, +7 unit test files; all tests now under `tests/unit/` and `tests/integration/` (0 top-level test files remain).
6. **Stable surface area**: Schema registry (29), CLI subcommands (25), schema files (24), step count (22), DEEP_VALIDATORS (21), and fixture files (133) all unchanged — no unintended scope creep.
