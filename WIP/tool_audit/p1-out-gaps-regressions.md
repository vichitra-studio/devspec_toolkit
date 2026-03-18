# P1-F: Gaps, Misses, Bugs & Regressions — Findings

## Executive Summary
3 unregistered error codes (E141, E142, E320) are functional bugs. step_01/step_02 duplicate schema validation unnecessarily. Steps 16a/16b/16c all run the full step_16 base validator (415 LOC) — intentional but expensive. No TODOs, no skips, no xfails. R9 coverage is complete.

---

### FINDING-G1: Unregistered Error Codes E141, E142, E320
- **Severity**: critical
- **Category**: REGISTRY_INCONSISTENCY
- **Location**: validators/step_14.py:79,126, validators/step_13.py:32,40,50
- **Description**: Three error codes are emitted by validators but not registered in errors.py ERROR_CODES dict. make_error() would reject these if used. They bypass the error code registry entirely.
- **Evidence**: E141 TASK_DEPENDENCY_CYCLE (step_14:126), E142 TECH_STACK_MISMATCH (step_14:79), E320 (step_13:32,40,50) — none appear in errors.py
- **Impact**: Error code coverage tests may not catch these. W->E promotion cannot target these codes.
- **Recommendation**: Register all three in errors.py ERROR_CODES dict

### FINDING-G2: step_01/step_02 Duplicate Schema Validation
- **Severity**: high
- **Category**: SCHEMA_VALIDATOR_MISMATCH
- **Location**: validators/step_01.py:56-74, validators/step_02.py (similar)
- **Description**: step_01.validate_step_01() creates its own SchemaRegistry, loads the schema by hardcoded URI, and runs iter_errors(). But validate.py already runs schema validation BEFORE calling deep validators. This means step_01/step_02 artifacts get double schema validation.
- **Evidence**: step_01.py:56 `registry = SchemaRegistry(repo_root)`, step_01.py:72 `for err in validator.iter_errors(data_for_validation)`. Same pattern in step_02.
- **Impact**: Duplicate errors in output; wasted computation; hardcoded schema URIs
- **Recommendation**: Remove schema validation from step_01 and step_02 validators; they should only do semantic checks

### FINDING-G3: Steps 16a/16b/16c Run Full step_16 Validator
- **Severity**: medium
- **Category**: SCHEMA_VALIDATOR_MISMATCH
- **Location**: step_16a.py:15, step_16b.py:15, step_16c.py:17
- **Description**: All three sub-step validators call `validate_step_16(data, toolkit_root, spec_path)` as their first line, inheriting all 415 LOC of checks. This is intentional (sub-steps share the schema) but means a 16c artifact runs step_16's full checklist validation plus 16c-specific review checks.
- **Evidence**: `errors = validate_step_16(data, toolkit_root, spec_path)` in all three
- **Impact**: Correct behavior but expensive; some step_16 checks may not apply to all sub-steps
- **Recommendation**: Consider separating step_16 into base checks (shared) and full checks (16 only)

### FINDING-G4: Step 00 Has No Deep Validator
- **Severity**: low
- **Category**: SCHEMA_VALIDATOR_MISMATCH
- **Location**: N/A (no step_00.py exists)
- **Description**: Step 00 (Charter) relies solely on JSON Schema validation (202 lines, 21 top-level properties, depth 8). The schema is relatively rich but has no semantic checks (e.g., unique IDs, cross-references).
- **Evidence**: No step_00.py in validators/. DEEP_VALIDATORS has no "00" entry. Step 00 schema has 21 properties.
- **Impact**: Low — charter is the root document with no upstream dependencies to cross-reference
- **Recommendation**: Acceptable as-is; charter has no cross-step references to validate

### FINDING-G5: _load_nfr_ids in hallucination_lint Uses Different Key
- **Severity**: medium
- **Category**: SCHEMA_VALIDATOR_MISMATCH
- **Location**: hallucination_lint.py:270-279
- **Description**: hallucination_lint's _load_nfr_ids extracts `n["id"]` from nfrs array, but the schema field is `nfr_id`. The validators correctly use `nfr.get("nfr_id")`. If nfrs have `nfr_id` but not `id`, hallucination_lint will miss them.
- **Evidence**: hallucination_lint.py:278 `{n["id"] for n in data.get("nfrs", [])}` vs step_08.py:165 `nfr.get("nfr_id")`
- **Impact**: hallucination_lint may fail to load NFR IDs, causing false E530 errors
- **Recommendation**: Fix to use `nfr_id` field name, consistent with schema and validators

### FINDING-G6: Edge Case — Empty Spec Directory
- **Severity**: low
- **Category**: EDGE_CASE
- **Location**: validate.py:180 (validate_dir)
- **Description**: validate_dir walks spec_dir for .json files. If empty, it still runs canonical lint, quality lint, etc. These may produce confusing output on empty directories.
- **Evidence**: os.walk on empty dir yields nothing; subsequent linters still run
- **Impact**: Confusing output but no crash
- **Recommendation**: Add early exit with informational message if spec_dir has no .json files

### FINDING-G7: warnings.warn Used for Non-Error Conditions
- **Severity**: low
- **Category**: CODE_HEALTH
- **Location**: 12 call sites across codebase (listed in ground truth)
- **Description**: Python warnings.warn() is used for both development-time checks (e.g., trace type validation at import time in step_01, step_11) and runtime conditions. Import-time warnings fire on every import.
- **Evidence**: step_01.py:20-25, step_11.py:33-43, step_02.py:83 — all fire at module import time
- **Impact**: Import-time warnings could confuse users; should be deferred to validation time
- **Recommendation**: Move import-time checks to validation functions or use a once-per-session flag

## R9 Coverage Matrix

| R9 Task | Feature | Test File(s) | Status |
|---------|---------|-------------|--------|
| T18 | Vague language scan | test_r9_quality_lint.py, test_r9_hallucination.py | Covered |
| T20 | Content derivation | test_r9_hallucination.py | Covered |
| T22 | Content staleness | test_r9_forward_replay.py | Covered |
| T24 | Coverage thresholds | test_r9_matrix.py | Covered |
| T26 | Extraction intent + W->E | test_r9_extraction_intent.py, test_r9_validate.py, test_r9_error_codes.py | Covered |
| T28 | env-check diagnostic | test_r9_cli.py | Covered |

All R9 features have dedicated test coverage. R9 CLI commands (dag-lint, extraction-intent-check, env-check) are wired in cli.py:166-175.

## Summary Table

| # | Severity | Category | Description |
|---|----------|----------|-------------|
| G1 | Critical | REGISTRY_INCONSISTENCY | 3 unregistered error codes |
| G2 | High | SCHEMA_VALIDATOR_MISMATCH | step_01/02 duplicate schema validation |
| G3 | Medium | SCHEMA_VALIDATOR_MISMATCH | 16a/16b/16c inherit full step_16 |
| G4 | Low | SCHEMA_VALIDATOR_MISMATCH | No step_00 deep validator |
| G5 | Medium | SCHEMA_VALIDATOR_MISMATCH | hallucination_lint uses wrong NFR key |
| G6 | Low | EDGE_CASE | Empty spec dir handling |
| G7 | Low | CODE_HEALTH | Import-time warnings |
