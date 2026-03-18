# P1-E: Error Collection & Reporting Pipeline Analysis (Run B)

## Executive Summary

The error pipeline is collect-all at schema level (iter_errors) and through deep validators (all return lists). Errors flow: validator -> list[str] -> validate.py -> cli.py -> stderr. Key issues: errors are flat strings (not structured objects), only 2 of 25 commands support --json, error format is inconsistent between schema errors and deep validator errors, and W->E promotion operates on string prefix matching.

## Pipeline Diagram

```
Schema JSON ──► Draft202012Validator.iter_errors() ──► enhanced_errors[]
                                                          │
Deep Validator ──► validate_step_NN() returns list[str] ──┤
                                                          │
Quality Lint ──► lint_spec_quality_file() returns list[str] ─┤
                                                          │
Canonical Integrity ──► validate_canonical_integrity_file() ─┤
                                                          ▼
                                              validate_file() returns list[str]
                                                          │
                                              validate_dir() aggregates across files
                                                          │ + prompt-sync, replay, dag, etc.
                                                          │ + W->E promotion (string replace)
                                                          │ + dedup (dict.fromkeys)
                                                          ▼
                                              cli.py _print_and_exit_if_errors()
                                                          │
                                              stderr (plain text) or JSON (2 commands)
```

## Findings

### FINDING-E1: Errors are flat strings, not structured objects
- **Severity**: high
- **Category**: LLM_UNFRIENDLY
- **Location**: All validators and linters
- **Current behavior**: Validators return `list[str]` with messages like `"E590 CROSS_STEP_ID_NOT_FOUND api 'foo' references unknown FR 'bar'"`. Schema errors are formatted as `"path:field/path: message"`.
- **Expected behavior**: Structured error objects: `{"code": "E590", "path": "apis[0].trace[1].id", "message": "...", "expected": "...", "actual": "..."}`.
- **Recommendation**: Migrate to SpecError dataclass (already defined in errors.py but unused by validators). Return `list[SpecError]` from validators, render to strings only at CLI output.

### FINDING-E2: Schema errors and deep validator errors have different formats
- **Severity**: medium
- **Category**: FORMAT_INCONSISTENCY
- **Location**: `validation/validate.py:145-158`
- **Current behavior**: Schema errors: `"filepath:/field/path: message\n  See: prompts/prompt_NN*.md for guidance"`. Deep validator errors: `"filepath: E590 CROSS_STEP_ID_NOT_FOUND ..."`. Quality lint errors start with `"W593"` or `"E510"` directly.
- **Expected behavior**: Consistent format: `"[CODE] filepath:path message"` across all error sources.
- **Recommendation**: Standardize error formatting in a single renderer function.

### FINDING-E3: validate_file continues after schema errors
- **Severity**: info
- **Category**: PROPAGATION_BUG (not a bug -- by design)
- **Location**: `validation/validate.py:155-173`
- **Current behavior**: After schema validation (iter_errors), validate_file always runs deep validators, quality lint, and canonical integrity regardless of schema errors. This is collect-all behavior.
- **Expected behavior**: This is correct for collect-all. However, deep validators may crash on malformed data that failed schema validation.
- **Recommendation**: Consider short-circuiting deep validation when critical schema errors exist (e.g., missing required fields).

### FINDING-E4: Only 2 of 25 commands support --json output
- **Severity**: medium
- **Category**: MISSING_JSON
- **Location**: `cli.py:54` (validate), `cli.py:117` (traceability-check)
- **Current behavior**: Only `validate` and `traceability-check` have `--json` flag. JSON output format: `[{"file": "...", "error": "...", "status": "FAIL|WARN|PASS"}]`.
- **Expected behavior**: All validation commands should support `--json` for machine consumption.
- **Recommendation**: Add `--json` to at least: validate-all, canonical-lint, canonical-integrity, spec-quality-lint, hallucination-lint, seed-lint.

### FINDING-E5: W->E promotion uses string prefix replacement
- **Severity**: medium
- **Category**: FORMAT_INCONSISTENCY
- **Location**: `validation/validate.py:274-282`
- **Current behavior**: `failures = [f.replace(w_code, e_code, 1) if f.startswith(w_code) else f for f in failures]`. This replaces the first occurrence of a W-code prefix with the corresponding E-code.
- **Expected behavior**: If errors were structured objects, promotion would just change the code field.
- **Recommendation**: This works correctly with current flat-string format. Would be cleaner with structured errors.

### FINDING-E6: _is_warning_message uses regex on first character
- **Severity**: low
- **Category**: FORMAT_INCONSISTENCY
- **Location**: `cli.py:6-14`
- **Current behavior**: Two regexes check if message starts with `W\d{3}` or `path: W\d{3}`. This correctly handles both direct warnings and path-prefixed warnings.
- **Expected behavior**: With structured errors, this would check `error.code.startswith("W")`.
- **Recommendation**: No immediate fix needed. Works correctly for current format.

### FINDING-E7: Error deduplication loses ordering context
- **Severity**: low
- **Category**: PROPAGATION_BUG
- **Location**: `validation/validate.py:284`
- **Current behavior**: `failures = list(dict.fromkeys(failures))` deduplicates while preserving first-occurrence order.
- **Expected behavior**: This is correct behavior. But it can mask repeated errors from different files if the error message doesn't include the file path.
- **Recommendation**: Ensure all error messages include file path context (most already do).

### FINDING-E8: Exception handling in cli.py is per-command, not global
- **Severity**: low
- **Category**: PROPAGATION_BUG
- **Location**: `cli.py:190-753`
- **Current behavior**: Each command block handles its own imports and calls. No global try/except. Unhandled exceptions produce full tracebacks.
- **Expected behavior**: A global try/except around the command dispatch would provide cleaner error output for unexpected failures.
- **Recommendation**: Add a top-level try/except in main() that catches SpecdevError and prints a clean message, letting other exceptions traceback for debugging.

## Summary Table

| # | Severity | Category | Description |
|---|----------|----------|-------------|
| E1 | High | LLM_UNFRIENDLY | Flat string errors, not structured |
| E2 | Medium | FORMAT_INCONSISTENCY | Inconsistent format across error sources |
| E3 | Info | (by design) | Collect-all continues after schema errors |
| E4 | Medium | MISSING_JSON | Only 2/25 commands support --json |
| E5 | Medium | FORMAT_INCONSISTENCY | W->E promotion via string replace |
| E6 | Low | FORMAT_INCONSISTENCY | Warning detection via regex |
| E7 | Low | PROPAGATION_BUG | Dedup may mask repeated errors |
| E8 | Low | PROPAGATION_BUG | No global exception handler |
