# P1-B2: Linters, Canonical, Generation & Migration — SoC Findings

## Executive Summary
validate.py (537 LOC) is an over-centralized orchestrator importing from 3 subpackages. The validate.py -> generation.prompt_schema_sync import is a confirmed layer violation. hallucination_lint.py and spec_quality_lint.py share 3 duplicated patterns. schema_differ.py (1331 LOC) is oversized but functionally cohesive.

---

### FINDING-SL1: validate.py Is an Over-Centralized Orchestrator
- **Severity**: high
- **Category**: SOC_BREACH
- **Locations**: validation/validate.py (537 LOC)
- **Description**: validate.py orchestrates schema validation, deep validation, quality lint, canonical integrity, canonical lint, prompt-schema sync, dependency ordering, forward replay, extraction intent, traceability closure, and W->E promotion. It imports from canonical/, generation/, and core/.
- **Evidence**: 7 cross-package imports at lines 14-23. validate_dir() alone runs 10 distinct checks.
- **Recommendation**: Extract validate_dir orchestration into a separate orchestrator module; keep validate_file focused on single-file validation

### FINDING-SL2: Layer Violation: validation/ -> generation/
- **Severity**: high
- **Category**: LAYER_VIOLATION
- **Locations**: validation/validate.py:20
- **Description**: validate.py imports `run_prompt_schema_sync` from generation/. This means validation depends on generation, creating a cross-cutting dependency.
- **Evidence**: `from ..generation.prompt_schema_sync import run_prompt_schema_sync`
- **Recommendation**: Either move prompt_schema_sync to validation/, or invoke it from cli.py as a standalone step (not nested inside validate_dir)

### FINDING-SL3: _collect_ids_and_refs Duplicated Between Linters
- **Severity**: medium
- **Category**: DRY_VIOLATION
- **Locations**: hallucination_lint.py:138-161, spec_quality_lint.py:215-232
- **Description**: Both linters implement `_collect_ids_and_refs` with nearly identical logic. Both scan for _id suffixes, ref contexts, and _ref/_refs fields.
- **Evidence**: Compare hallucination_lint.py lines 138-161 with spec_quality_lint.py lines 215-232. Same keys checked, same pattern.
- **Recommendation**: Extract to a shared utility in validation/

### FINDING-SL4: _iter_json Duplicated Between Linters
- **Severity**: low
- **Category**: DRY_VIOLATION
- **Locations**: hallucination_lint.py:131-135, spec_quality_lint.py:243-247
- **Description**: Identical os.walk + .json filter pattern
- **Evidence**: Both are 5-line functions with identical logic
- **Recommendation**: Extract to shared utility

### FINDING-SL5: _is_reference_context / _in_ref_context Duplicated
- **Severity**: low
- **Category**: DRY_VIOLATION
- **Locations**: hallucination_lint.py:164-167, spec_quality_lint.py:235-240
- **Description**: Same logic checking if a JSON path is in a reference context (trace, targets, etc.)
- **Evidence**: hallucination_lint uses set intersection; spec_quality_lint uses `any()` with segment check. Same semantic result.
- **Recommendation**: Unify into shared utility

### FINDING-SL6: canonical/lint.py and canonical/integrity.py Boundary
- **Severity**: medium
- **Category**: SOC_BREACH
- **Locations**: canonical/lint.py (472 LOC), canonical/integrity.py (640 LOC)
- **Description**: lint.py validates the canonical registry structure (manifest, aliases, kinds schemas). integrity.py validates that spec artifacts correctly reference canonical entries. The boundary is clear in principle but integrity.py calls lint_canon_dir() as a preflight, creating tight coupling.
- **Evidence**: integrity.py:25 calls `lint_canon_dir()` as preflight. validate.py also calls lint_canon_dir() independently.
- **Recommendation**: Accept coupling (lint is a precondition for integrity) but document the dependency

### FINDING-SL7: schema_differ.py Is Oversized (1331 LOC)
- **Severity**: medium
- **Category**: SOC_BREACH
- **Locations**: generation/schema_differ.py (1331 LOC)
- **Description**: Largest module in codebase. Handles diff computation, status/diff/plan report formatting, auto-fix application, backup/restore, pre/post migration validation, and operation logging.
- **Evidence**: 1331 LOC with ~15 public functions
- **Recommendation**: Split into schema_differ_core.py (diff computation), schema_differ_reports.py (formatting), schema_differ_apply.py (auto-fix, backup, restore)

### FINDING-SL8: governance.py Is Undersized (37 LOC)
- **Severity**: info
- **Category**: SOC_BREACH
- **Locations**: validation/governance.py (37 LOC)
- **Description**: Extremely thin module with one function. May not justify a separate file.
- **Evidence**: Single function `check_commit_message` that loads governance spec and regex-matches
- **Recommendation**: Could merge into a validators/ file or keep as-is for clarity

### FINDING-SL9: KNOWN_STAGES Duplicated
- **Severity**: low
- **Category**: DRY_VIOLATION
- **Locations**: hallucination_lint.py:13, step_07.py:9
- **Description**: Both define `KNOWN_STAGES = {"dev", "ci", "staging", "prod"}` as a local constant
- **Evidence**: Identical set in both files
- **Recommendation**: Load from canon/kinds/stage.json or centralize in core/

## PASS

- core/trace_types.py (53 LOC) is correctly placed in core/ — used by 9 modules across packages
- core/errors.py is the single source of truth for all 77 error codes
- _extraction_intent_parser.py is correctly private — only imported by extraction_intent_check.py
- generation/prompt_generator.py (813 LOC) is cohesive despite size
- migration/ package correctly depends on generation/ and core/ only (no validation dependency)
- canonical/registry.py is cleanly separated from canonical/lint.py
- No linters re-implement jsonschema validation (they delegate to validate.py)
