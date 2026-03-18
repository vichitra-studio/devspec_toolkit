# P1-B2: Linters, Canonical, Generation & Migration -- SoC Analysis (Run B)

## Executive Summary

The package layering is generally sound: core/ is a leaf, canonical/ and generation/ depend on core/, validation/ depends on all, migration/ depends on core/+generation/. The main SoC concerns are: (1) validate.py is a 537-LOC mega-orchestrator doing too much, (2) validate.py depends on generation/, (3) hallucination_lint.py duplicates hardcoded value sets that should come from canon, and (4) schema_differ.py at 1331 LOC should be split.

## Findings

### FINDING-SL1: validate.py is a mega-orchestrator (537 LOC, 6+ responsibilities)
- **Severity**: high
- **Category**: SOC_BREACH
- **Locations**: `validation/validate.py` (537 LOC)
- **Description**: validate.py handles: schema validation, deep validation dispatch, canonical integrity, canonical lint preflight, hallucination lint, spec quality lint, prompt-schema sync, forward-replay check, dependency-order lint, extraction-intent check, traceability closure, and W->E promotion. validate_dir() alone is 112 lines of orchestration.
- **Evidence**: validate_dir() calls 9+ separate lint/validation modules. It also contains 6 private helper functions (_load_json_artifact, _load_component_ids, _load_capability_ids, etc.) that duplicate the same pattern found in step validators.
- **Recommendation**: Extract validate_dir orchestration to a separate `orchestrator.py`. Move the _load_* helpers to shared validators/_loaders.py (aligns with P1-B1 recommendation).

### FINDING-SL2: validate.py depends on generation.prompt_schema_sync
- **Severity**: medium
- **Category**: LAYER_VIOLATION
- **Locations**: `validation/validate.py:20`
- **Description**: validation/ imports from generation/ via `from ..generation.prompt_schema_sync import run_prompt_schema_sync`. This creates a circular conceptual dependency since generation/ should be downstream of validation/.
- **Evidence**: Line 20: `from ..generation.prompt_schema_sync import run_prompt_schema_sync`
- **Recommendation**: Move prompt_schema_sync to validation/ (it performs validation-like checks), or accept this as architectural (validate.py is the orchestrator, not a pure validator).

### FINDING-SL3: hallucination_lint.py has hardcoded value sets
- **Severity**: medium
- **Category**: DRY_VIOLATION
- **Locations**: `validation/hallucination_lint.py:13-22`
- **Description**: KNOWN_STAGES, DEFAULT_COMMAND_PREFIXES, and KNOWN_UNITS are hardcoded sets that overlap with canonical registry data. KNOWN_STAGES duplicates `canon/kinds/stage.json`.
- **Evidence**: Line 13: `KNOWN_STAGES = {"dev", "ci", "staging", "prod"}`; Line 19: `KNOWN_UNITS = {"%", "percent", ...}`.
- **Recommendation**: Load from canon/kinds/ or accept as fallback defaults (the module does load CanonicalRegistry later).

### FINDING-SL4: schema_differ.py is 1331 LOC -- should be split
- **Severity**: medium
- **Category**: SOC_BREACH
- **Locations**: `generation/schema_differ.py` (1331 LOC)
- **Description**: Largest module in the codebase. Handles: schema diffing, status/diff/plan report formatting, auto-fix application, backup management, pre/post migration validation, operation logging. At least 3-4 distinct responsibilities.
- **Evidence**: Module exports: diff_spec_directory, format_status_report, format_diff_report, format_plan_report, apply_auto_fixes, format_apply_report, list_backups, restore_backup, validate_pre_migration, validate_post_migration, get_toolkit_version, log_operation.
- **Recommendation**: Split into: `schema_differ.py` (diffing), `migration_formatter.py` (reports), `migration_ops.py` (apply/backup/restore).

### FINDING-SL5: canonical/lint.py (472 LOC) and canonical/integrity.py (640 LOC) boundary
- **Severity**: low
- **Category**: SOC_BREACH
- **Locations**: `canonical/lint.py`, `canonical/integrity.py`
- **Description**: lint.py validates canon/ directory structure, schema compliance, manifest consistency. integrity.py validates spec files against canonical registry (values match canon kinds). The boundary is: lint = "is the canon registry itself valid?"; integrity = "do spec files use canon values correctly?". This is reasonable but not documented.
- **Evidence**: lint.py imports from core.registry; integrity.py also imports from core.registry. Both are called from validate.py but at different stages.
- **Recommendation**: Add module-level docstrings clarifying the boundary. No structural change needed.

### FINDING-SL6: governance.py (37 LOC) uses file handle leak
- **Severity**: low
- **Category**: SOC_BREACH
- **Locations**: `validation/governance.py:12`
- **Description**: `json.load(open(p, "r", encoding="utf-8"))` opens a file without closing it. Minor resource leak.
- **Evidence**: Line 12: `data = json.load(open(p, "r", encoding="utf-8"))`
- **Recommendation**: Use `with open(...) as f: data = json.load(f)`.

### FINDING-SL7: _extraction_intent_parser.py is correctly private
- **Severity**: info
- **Category**: SOC_BREACH
- **Locations**: `validation/_extraction_intent_parser.py` (124 LOC)
- **Description**: Leading underscore suggests private module. Verified: only imported by extraction_intent_check.py.
- **Evidence**: Grep for `_extraction_intent_parser` shows only extraction_intent_check.py importing it.
- **Recommendation**: No change needed.

### FINDING-SL8: validate.py has _load_* helpers duplicating validator patterns
- **Severity**: medium
- **Category**: DRY_VIOLATION
- **Locations**: `validation/validate.py:303-370`
- **Description**: validate.py defines _load_json_artifact, _load_component_ids, _load_capability_ids, _load_nfrs_data, _load_monitoring_data. These are similar to but different from the 23 _load_* functions in validators/. validate.py's versions use a candidate-path strategy (artifact_path + spec/ fallback) while most validators only check spec/.
- **Evidence**: Lines 303-370 define 5 loader functions. Only used by _build_validation_context() for step_01/02/03 context injection.
- **Recommendation**: Unify with the shared _loaders.py proposed in P1-B1.

### FINDING-SL9: core/trace_types.py placement
- **Severity**: info
- **Category**: SOC_BREACH
- **Locations**: `core/trace_types.py` (53 LOC)
- **Description**: trace_types.py is in core/ but imports from canonical.registry (a reverse dependency: core -> canonical). This is mitigated by a try/except fallback, but conceptually core/ should not depend on canonical/.
- **Evidence**: Line 10-11: `from ..canonical.registry import CanonicalRegistry` (inside try block with fallback)
- **Recommendation**: Accept: the try/except fallback makes it safe, and trace_types needs to be in core/ because 9+ modules depend on it.

## PASS

- core/ package (errors.py, registry.py, trace_types.py, changelog_parser.py) is well-factored with clear responsibilities.
- canonical/autofix.py (397 LOC) has a single clear responsibility (auto-fixing canon references in spec files).
- canonical/registry.py (318 LOC) cleanly encapsulates the canonical registry loading and querying.
- migration/planner.py and migration/runner.py have clear separation (plan vs execute).
- generation/prompt_generator.py (813 LOC) is large but has a single coherent responsibility (generating upgrade prompts).
- Error codes are centralized in core/errors.py -- no linters define their own error codes inline.
- cross_artifact_checks.py and traceability_closure.py have distinct scopes despite both dealing with cross-artifact references.
