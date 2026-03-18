# P1-F: Gaps, Misses, Bugs & Regressions Analysis (Run B)

## Executive Summary

No critical bugs found. Key findings: step_01 and step_02 validators perform redundant schema validation, step_16a/16b/16c validators run step_16's full validation every time (triple execution risk), step_14 uses error codes (E141, E142) not defined in errors.py, and the noqa in validators/__init__.py is justified. Zero TODOs in specdev_tools/, zero skips/xfails confirmed.

## Findings

### FINDING-G1: step_01 and step_02 redundantly validate schemas
- **Severity**: high
- **Category**: SCHEMA_VALIDATOR_MISMATCH
- **Location**: `validators/step_01.py:55-74`, `validators/step_02.py:127+`
- **Description**: step_01 and step_02 deep validators load SchemaRegistry, construct a Draft202012Validator, and run iter_errors(). This duplicates what validate.py:validate_file() already does at lines 130-136 before calling DEEP_VALIDATORS.
- **Evidence**: step_01.py constructs `Draft202012Validator(schema, registry=registry_obj)` and calls `iter_errors()`. validate.py does the same at line 130.
- **Impact**: Schema errors are reported twice for steps 01 and 02. No functional breakage, but confusing output and wasted cycles.
- **Recommendation**: Remove schema validation from step_01 and step_02 deep validators. They should only perform semantic/cross-reference checks.

### FINDING-G2: step_16a/16b/16c all call validate_step_16() -- triple execution
- **Severity**: medium
- **Category**: SCHEMA_VALIDATOR_MISMATCH
- **Location**: `validators/step_16a.py:15`, `step_16b.py:15`, `step_16c.py:17`
- **Description**: Each sub-step validator calls `validate_step_16(data, toolkit_root, spec_path)` as its first line. If validate_dir processes a spec directory containing all three sub-step artifacts, step_16's validation runs 3 extra times.
- **Evidence**: step_16a.py:15 `errors = validate_step_16(data, toolkit_root, spec_path)`. Same in 16b and 16c.
- **Impact**: Redundant validation of step_16 base checks. The base step_16 validator (415 LOC) does file I/O (reads roadmap, seed_manifest, FR list) on each call.
- **Recommendation**: Either cache step_16 validation results or restructure so base checks run once and sub-step checks add incrementally.

### FINDING-G3: step_14 uses undeclared error codes E141 and E142
- **Severity**: medium
- **Category**: REGISTRY_INCONSISTENCY
- **Location**: `validators/step_14.py:126-128` (E141), `step_14.py:79` (E142)
- **Description**: step_14 emits `E141 TASK_DEPENDENCY_CYCLE` and `E142 TECH_STACK_MISMATCH` error codes, but neither E141 nor E142 appear in core/errors.py ERROR_CODES dict.
- **Evidence**: errors.py has no entry for E141 or E142. The 1xx range is "Canonical integrity" in the error family scheme, not "roadmap validation".
- **Impact**: make_error() would reject these codes. They bypass the centralized error code system. Numbering conflicts with 1xx canonical range.
- **Recommendation**: Register E141 and E142 in errors.py or renumber to the appropriate family (e.g., E30x for proof/closure or a new E14x sub-range).

### FINDING-G4: Step 00 has no deep validator -- is schema-only sufficient?
- **Severity**: low
- **Category**: SCHEMA_VALIDATOR_MISMATCH
- **Location**: `schema/00_charter.schema.json` (202 lines, 21 top-level properties)
- **Description**: Step 00 (Project Charter) has no deep validator. DEEP_VALIDATORS has no "00" entry. Schema validation alone handles it.
- **Evidence**: No step_00.py in validators/. DEEP_VALIDATORS starts at "01".
- **Impact**: No semantic cross-reference checks for the charter. Since step 00 is the root with no upstream dependencies, this is acceptable.
- **Recommendation**: No change needed. Step 00 has no cross-step references to validate.

### FINDING-G5: Code health confirmed clean
- **Severity**: info
- **Category**: CODE_HEALTH
- **Location**: All specdev_tools/ source files
- **Description**: Zero TODOs in specdev_tools/ (confirmed). One TODO in tools/core/json_utils.py (outside package). One noqa at validators/__init__.py:7 (justified -- F401 for re-exports). Zero skip/xfail markers in tests.
- **Evidence**: Verified via grep.
- **Impact**: No known incomplete implementations.
- **Recommendation**: No action needed.

### FINDING-G6: warnings.warn in step_01 and step_11 -- module-load-time side effects
- **Severity**: low
- **Category**: CODE_HEALTH
- **Location**: `validators/step_01.py:20-25`, `validators/step_11.py:32-44`
- **Description**: Both modules emit `warnings.warn()` at module load time if their business-rule trace-type constants are not valid canonical types. This is a runtime self-check, not a bug indicator.
- **Evidence**: step_01.py:20 `if not is_valid_trace_type(...)` triggers at import time. step_11.py:32-43 does the same for both target and mitigation type sets.
- **Impact**: If canon/kinds/trace_type.json is missing or broken, these warnings fire on every import. They don't block validation.
- **Recommendation**: Acceptable pattern -- warnings are appropriate for self-checks.

### FINDING-G7: step_08 validator DAG consistency check
- **Severity**: info
- **Category**: SCHEMA_VALIDATOR_MISMATCH
- **Location**: `validators/step_08.py`
- **Description**: step_08 loads from steps 04, 05, 06, 07. step_order.json confirms "08" has allowed_upstream_dependencies including "04", "05", "06", "07". DAG is consistent.
- **Evidence**: step_order.json "08" deps: [00,01,02,02a,03,04,05,06,07]. step_08 loads from 04,05,06,07.
- **Impact**: None -- correctly aligned.
- **Recommendation**: No change needed.

### FINDING-G8: step_14 loads from steps 01, 04, 09 -- DAG consistent
- **Severity**: info
- **Category**: SCHEMA_VALIDATOR_MISMATCH
- **Location**: `validators/step_14.py`
- **Description**: step_14 loads from steps 01 (capabilities), 04 (FRs), 09 (milestones, tech_stack). step_order.json confirms "14" has allowed_upstream_dependencies including all of these.
- **Evidence**: step_order.json "14" deps include "01", "04", "09" (among others).
- **Impact**: None -- correctly aligned.
- **Recommendation**: No change needed.

## R9 Coverage Matrix

| R9 Task | Feature | Test File(s) | Covered? |
|---------|---------|-------------|----------|
| T18 | Vague language scan | test_r9_quality_lint.py, test_r9_hallucination.py | YES |
| T20 | Content derivation | test_r9_hallucination.py | YES |
| T22 | Content staleness | test_r9_forward_replay.py | YES |
| T24 | Coverage thresholds | test_r9_matrix.py | YES |
| T26 | Extraction intent + W->E | test_r9_extraction_intent.py, test_r9_error_codes.py | YES |
| T28 | env-check diagnostic | test_r9_cli.py | YES |

All R9 features have dedicated test coverage.

## Summary Table

| # | Severity | Category | Description |
|---|----------|----------|-------------|
| G1 | High | SCHEMA_VALIDATOR_MISMATCH | step_01/02 redundant schema validation |
| G2 | Medium | SCHEMA_VALIDATOR_MISMATCH | step_16a/b/c triple-execute step_16 |
| G3 | Medium | REGISTRY_INCONSISTENCY | E141/E142 not in errors.py |
| G4 | Low | SCHEMA_VALIDATOR_MISMATCH | Step 00 no deep validator (acceptable) |
| G5 | Info | CODE_HEALTH | Zero TODOs, zero skips confirmed |
| G6 | Low | CODE_HEALTH | Module-load warnings (acceptable) |
| G7 | Info | SCHEMA_VALIDATOR_MISMATCH | step_08 DAG consistent |
| G8 | Info | SCHEMA_VALIDATOR_MISMATCH | step_14 DAG consistent |
