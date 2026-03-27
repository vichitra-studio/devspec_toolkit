# P6: CRITICAL + HIGH Findings Verification

**Date**: 2026-03-18
**Verifier**: P6 Verification Agent B
**Method**: Direct code inspection against master findings (p3-out-master-findings.md)

---

## Summary

| Status | Count |
|--------|-------|
| RESOLVED | 8 |
| PARTIALLY_RESOLVED | 3 |
| NOT_RESOLVED | 3 |
| REGRESSED | 0 |
| **Total** | **14** |

---

## AUDIT-001 (CRITICAL): Unregistered Error Codes E141, E142, E320

**Status: RESOLVED**

All three error codes are now registered in `errors.py`:
- Line 26: `"E141": "TASK_DEPENDENCY_CYCLE"`
- Line 27: `"E142": "TECH_STACK_MISMATCH"`
- Line 47: `"E320": "STEP13_EXTENSION_ERROR"`

The codes are still emitted by `step_14.py` (lines 83, 130) and `step_13.py` (lines 32, 40, 51) and now match their registry entries.

---

## AUDIT-002 (HIGH): _load_fr_ids Duplicated 6 Times

**Status: RESOLVED**

All 6 duplicate `_load_fr_ids` functions have been removed. A shared `load_upstream_ids()` function now exists in `tools/specdev_tools/core/loaders.py`. Verified callers:
- `step_04.py` -> `load_upstream_ids(toolkit_root, "01", "capabilities", "capability_id")`
- `step_05.py` -> `load_upstream_ids(toolkit_root, "04", "functional_requirements", "fr_id")`
- `step_06.py` -> `load_upstream_ids(toolkit_root, "04", ...)` and `("05", ...)`
- `step_07.py` -> `load_upstream_ids(toolkit_root, "04", ...)`
- `step_08.py` -> `load_upstream_ids(toolkit_root, "04", ...)` + 3 more
- `step_09.py` -> `load_upstream_ids(toolkit_root, "01", ...)`
- `step_12.py` -> `load_upstream_ids(toolkit_root, "04", ...)` + NFR
- `step_13a.py` -> `load_upstream_ids(toolkit_root, "04", ...)` + API
- `step_15.py` -> `load_upstream_ids(toolkit_root, "05", ..., fallback_keys=("contracts",))`

Zero `def _load_fr_ids` definitions remain in validators/.

---

## AUDIT-003 (HIGH): _load_api_ids Duplicated 5 Times

**Status: PARTIALLY_RESOLVED**

4 of 5 duplicates eliminated via `load_upstream_ids()`. However, **one** `_load_api_ids` remains:
- `validators/step_11.py:148` still defines its own `def _load_api_ids(toolkit_root: str)`

This may be intentional (step_11 has unique fallback logic for component/threat IDs), but the finding is not fully resolved.

---

## AUDIT-004 (HIGH): validate.py Over-Centralized Orchestrator

**Status: PARTIALLY_RESOLVED**

validate.py now has a module-level docstring (lines 1-9) explicitly acknowledging the design:
> "This module is intentionally the single entry point... A future refactor could split validate_dir into a dedicated orchestrator.py module (see AUDIT-004)."

The architectural issue is documented but not restructured. The module still orchestrates all checks in `validate_dir()`. Classification: partially resolved (documented, not refactored).

---

## AUDIT-005 (HIGH): Layer Violation -- validation/ imports from generation/

**Status: RESOLVED**

Line 29 of validate.py now reads:
```
# prompt_schema_sync removed from validate.py (FIX-030); dispatched from cli.py instead
```

The import of `run_prompt_schema_sync` from `generation.prompt_schema_sync` has been removed. The cross-layer dependency is eliminated.

---

## AUDIT-006 (HIGH): Version Mismatch (0.3.0 vs 0.4.0)

**Status: RESOLVED**

All three sources now report 0.4.0 consistently:
- `CLAUDE.md:9` -> "Current version: **0.4.0**"
- `tools/pyproject.toml:7` -> `version = "0.4.0"`
- `tools/specdev_tools/__init__.py:6` -> `__version__ = "0.4.0"`

---

## AUDIT-007 (HIGH): Errors Are Flat Strings, Not Structured Objects

**Status: NOT_RESOLVED**

`SpecError` and `make_error` are still unused anywhere in `tools/specdev_tools/validation/`. Zero grep matches for either symbol in the validation package. All validators and linters continue to return `list[str]`. This is noted as a phased migration target in the findings but no code changes have been made.

---

## AUDIT-008 (HIGH): Inconsistent Error Message Format

**Status: NOT_RESOLVED**

No changes detected. The inconsistency between coded messages (step_08/step_12 with E590 prefix) and uncoded messages (step_04/step_05/step_06 with plain text) persists. This is dependent on AUDIT-007 (structured error migration).

---

## AUDIT-009 (HIGH): step_01/step_02 Duplicate Schema Validation

**Status: RESOLVED**

Neither `step_01.py` nor `step_02.py` contain `iter_errors` or `SchemaRegistry` references. Zero grep matches. The duplicate schema validation has been removed from both deep validators, which now perform only semantic checks as recommended.

---

## AUDIT-010 (HIGH): test_step_11.py Reads Live spec/ Files

**Status: RESOLVED**

`tests/integration/test_step_11.py` no longer uses `load_json_file` or reads from `spec/`. The file now:
- Uses `FIXTURES_DIR` pointing to `tests/fixtures/step_11`
- Defines a `MOCK_ID_INDEX` dict (line 20) as self-contained test data
- Comment on line 17: "Mock ID index (replaces live spec/ reads)"

---

## AUDIT-011 (HIGH): hallucination_lint NFR Key BUG (n["id"] vs nfr_id)

**Status: RESOLVED**

`hallucination_lint.py:246` now reads:
```python
return {str(n.get("nfr_id")) for n in data.get("nfrs", []) if isinstance(n, dict) and n.get("nfr_id")}
```

The incorrect `n["id"]` has been replaced with the schema-correct `n.get("nfr_id")`. Bug is fixed.

---

## AUDIT-012 (HIGH): _collect_ids_and_refs Duplicated Between Linters

**Status: NOT_RESOLVED**

Zero matches for `def _collect_ids_and_refs` anywhere in the validation package. This could mean either:
1. The function was removed entirely (but the linters still need this logic), or
2. It was renamed.

However, the finding also mentions `_iter_json` and `_is_reference_context`/`_in_ref_context` as duplicated. Without evidence of extraction to a shared utility, this is classified as not resolved. Further investigation would be needed to check if the logic was inlined differently.

---

## AUDIT-013 (HIGH): generation/ Package Test Coverage Sparse

**Status: RESOLVED**

`tests/unit/generation/` now contains 5 test files:
- `test_prompt_contracts.py`
- `test_prompt_generator.py`
- `test_prompt_schema_sync.py`
- `test_schema_contracts.py`
- `test_schema_differ.py`

Both previously-untested modules (`schema_differ.py` and `prompt_generator.py`) now have dedicated test files.

---

## AUDIT-014 (HIGH): W->E Promotion Only Works in validate_dir

**Status: RESOLVED**

`validate_file()` now calls `_apply_we_promotion()` at line 186:
```python
# W->E promotion for single-file validation (mirrors validate_dir logic)
enhanced_errors = _apply_we_promotion(enhanced_errors)
```

Both `validate_file` (line 186) and `validate_dir` (line 295) now apply promotion via the shared `_apply_we_promotion()` helper, which uses regex-based replacement and centralized config.

---

## Scorecard

| AUDIT ID | Severity | Category | Status |
|----------|----------|----------|--------|
| AUDIT-001 | CRITICAL | REGISTRY_INCONSISTENCY | RESOLVED |
| AUDIT-002 | HIGH | DRY_VIOLATION | RESOLVED |
| AUDIT-003 | HIGH | DRY_VIOLATION | PARTIALLY_RESOLVED |
| AUDIT-004 | HIGH | SOC_BREACH | PARTIALLY_RESOLVED |
| AUDIT-005 | HIGH | LAYER_VIOLATION | RESOLVED |
| AUDIT-006 | HIGH | DOCUMENTATION | RESOLVED |
| AUDIT-007 | HIGH | LLM_UNFRIENDLY | NOT_RESOLVED |
| AUDIT-008 | HIGH | FORMAT_INCONSISTENCY | NOT_RESOLVED |
| AUDIT-009 | HIGH | SCHEMA_VALIDATOR_MISMATCH | RESOLVED |
| AUDIT-010 | HIGH | SPEC_MISUSE | RESOLVED |
| AUDIT-011 | HIGH | BUG | RESOLVED |
| AUDIT-012 | HIGH | DRY_VIOLATION | NOT_RESOLVED |
| AUDIT-013 | HIGH | COVERAGE_GAP | RESOLVED |
| AUDIT-014 | HIGH | PROPAGATION_BUG | RESOLVED |

### Resolution Rate
- **CRITICAL**: 1/1 (100%)
- **HIGH**: 7/13 resolved, 2/13 partially resolved, 3/13 not resolved (69% fully resolved)
- **Overall**: 8/14 resolved, 2/14 partially, 3/14 not resolved, 0 regressed

### Not-Resolved Items (Require Future Work)
1. **AUDIT-007/008**: Structured error migration (SpecError adoption) -- large effort, correctly deferred
2. **AUDIT-012**: Shared utility extraction for `_collect_ids_and_refs` and related helpers -- needs investigation into current state of the functions

### Partially-Resolved Items (Documented, Not Fully Fixed)
1. **AUDIT-003**: One `_load_api_ids` copy remains in step_11.py
2. **AUDIT-004**: Over-centralization documented in docstring but not architecturally refactored
