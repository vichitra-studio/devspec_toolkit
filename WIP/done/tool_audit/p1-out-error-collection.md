# P1-E: Error Collection & Reporting Pipeline — Findings

## Executive Summary
The pipeline correctly uses collect-all (iter_errors + list accumulation). Errors are flat strings with embedded codes, not structured objects. The W->E promotion works only in validate_dir, not validate_file. JSON output exists on only 2 of 25 commands. Error messages lack field-path precision in deep validators.

## Pipeline Diagram

```
Validator/Linter -> list[str] -> validate_file() accumulates -> validate_dir() aggregates
                                                                 -> W->E promotion
                                                                 -> dedup (dict.fromkeys)
                                                    -> cli.py _print_and_exit_if_errors()
                                                       -> stderr (each error)
                                                       -> exit(1) if has errors
                                                       -> "OK" / "OK (warnings)"
```

---

### FINDING-E1: Errors Are Flat Strings, Not Structured Objects
- **Severity**: high
- **Category**: LLM_UNFRIENDLY
- **Location**: All validators, all linters, validate.py
- **Current behavior**: Validators return `list[str]`. Format varies: some use `"E590 CROSS_STEP_ID_NOT_FOUND ..."`, others use `"Duplicate fr_id 'x' at index 3"` (no error code). SpecError dataclass exists in errors.py but is NEVER used by validators.
- **Expected behavior**: All errors should be SpecError objects with code, message, path fields
- **Recommendation**: Migrate validators to return list[SpecError]; render to strings at CLI output layer

### FINDING-E2: Inconsistent Error Message Format
- **Severity**: high
- **Category**: FORMAT_INCONSISTENCY
- **Location**: validators/step_04.py, step_05.py, step_06.py vs step_08.py, step_12.py
- **Current behavior**: step_04/step_05 emit plain messages ("Duplicate fr_id 'x'") with no error code. step_08/step_12/step_13/step_13a emit coded messages ("E590 CROSS_STEP_ID_NOT_FOUND ..."). Within the SAME validator, some errors have codes and some don't.
- **Expected behavior**: Every error should have an error code prefix
- **Recommendation**: Add error codes to all validator messages; use SpecError

### FINDING-E3: W->E Promotion Only Works in validate_dir
- **Severity**: medium
- **Category**: PROPAGATION_BUG
- **Location**: validate.py:267-289
- **Current behavior**: SPECDEV_WARNINGS_AS_ERRORS promotion logic is in validate_dir() only. validate_file() does not promote. CLI validate command calls validate_file() directly.
- **Expected behavior**: Promotion should work for both single-file and directory validation
- **Recommendation**: Move promotion logic to _print_and_exit_if_errors or add it to validate_file

### FINDING-E4: validate_file Continues After Schema Errors
- **Severity**: info
- **Category**: PROPAGATION_BUG
- **Location**: validate.py:136-173
- **Current behavior**: After iter_errors() finds schema errors, validate_file() still runs deep validators and quality lint. This means you can get both schema errors AND deep validation errors for the same file.
- **Expected behavior**: This is arguably correct — collect-all behavior. But deep validators may crash on malformed data if schema validation failed.
- **Recommendation**: Consider short-circuiting deep validation if schema errors exist (or add defensive guards in validators)

### FINDING-E5: Only 2 of 25 Commands Support --json Output
- **Severity**: medium
- **Category**: MISSING_JSON
- **Location**: cli.py (validate, traceability-check only)
- **Current behavior**: 23 commands output human-readable text only. No machine-parsable output for matrix, canonical-lint, hallucination-lint, etc.
- **Expected behavior**: All validation commands should support --json for CI integration and LLM consumption
- **Recommendation**: Add --json flag to all validation commands; use a shared JSON formatter

### FINDING-E6: _is_warning_message Uses Prefix Matching
- **Severity**: low
- **Category**: FORMAT_INCONSISTENCY
- **Location**: cli.py:6-14
- **Current behavior**: Matches `^\s*W\d{3}\b` or `^path: W\d{3}\b`. This correctly identifies W-codes at message start.
- **Expected behavior**: Works correctly for current format
- **Recommendation**: No action needed if all warnings consistently start with W-codes. But FINDING-E2 shows some warnings DON'T have codes, so those would be misclassified as errors.

### FINDING-E7: Deep Validation Errors Lack File Path Context
- **Severity**: medium
- **Category**: LLM_UNFRIENDLY
- **Location**: validate.py:158
- **Current behavior**: Deep validator errors are prefixed with `f"{path}: {e}"` but the error `e` itself doesn't include the JSON field path within the document.
- **Expected behavior**: Errors should include the JSON path (e.g., "functional_requirements[3].fr_id") for LLM self-correction
- **Recommendation**: Deep validators should include JSON path in error messages

### FINDING-E8: Unregistered Error Codes Used in Validators
- **Severity**: high
- **Category**: FORMAT_INCONSISTENCY
- **Location**: step_14.py (E141, E142), step_13.py (E320), step_16.py (E301-E307)
- **Current behavior**: Several error codes are emitted by validators but not registered in errors.py ERROR_CODES dict. E301-E307 ARE registered, but E141, E142, E320 are not.
- **Expected behavior**: All error codes should be in ERROR_CODES
- **Recommendation**: Register E141, E142, E320 in errors.py; or use make_error() to enforce registration

## Summary Table

| # | Severity | Category | Location |
|---|----------|----------|----------|
| E1 | High | LLM_UNFRIENDLY | All validators |
| E2 | High | FORMAT_INCONSISTENCY | Mixed validator formats |
| E3 | Medium | PROPAGATION_BUG | validate.py W->E |
| E4 | Info | PROPAGATION_BUG | validate_file flow |
| E5 | Medium | MISSING_JSON | 23/25 commands |
| E6 | Low | FORMAT_INCONSISTENCY | cli.py |
| E7 | Medium | LLM_UNFRIENDLY | validate.py:158 |
| E8 | High | FORMAT_INCONSISTENCY | Unregistered codes |
