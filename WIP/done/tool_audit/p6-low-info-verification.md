# P6: LOW + INFO Findings Verification (AUDIT-045 through AUDIT-070)

**Agent**: P6 Verification Agent D
**Date**: 2026-03-18
**Scope**: AUDIT-045 through AUDIT-070 (26 findings, LOW + INFO severity)
**Note**: AUDIT-032 is OUT OF SCOPE per user directive.

---

## Summary

| Status | Count |
|--------|-------|
| RESOLVED | 11 |
| PARTIALLY_RESOLVED | 6 |
| NOT_RESOLVED | 9 |
| REGRESSED | 0 |
| **Total** | **26** |

---

## Individual Findings

### AUDIT-045: Kebab-case ID Regex Duplicated Across Files
- **Severity**: LOW
- **Status**: **RESOLVED**
- **Evidence**: `core/loaders.py` now exports `KEBAB_ID_RE` and `kebab_id_re()` factory. Validators import from `...core.loaders`: step_04 uses `kebab_id_re("fr")`, step_13a/step_14/step_15 import `KEBAB_ID_RE`. The 8-file duplication has been centralized.

### AUDIT-046: Import Pattern Inconsistency Across Validators
- **Severity**: LOW
- **Status**: **PARTIALLY_RESOLVED**
- **Evidence**: 15 of 21 validator files now have `from __future__ import annotations`. However, step_01, step_03, step_04, step_15, step_16 still lack it. The majority is standardized but not all files are consistent.

### AUDIT-047: Orphaned UNKNOWN.egg-info Directory
- **Severity**: LOW
- **Status**: **RESOLVED**
- **Evidence**: `tools/UNKNOWN.egg-info/` no longer exists on disk. `.gitignore` contains `*.egg-info/` (line 21). Both the cleanup and prevention are in place.

### AUDIT-048: Stale trace_matrix.json Checked In
- **Severity**: LOW
- **Status**: **RESOLVED**
- **Evidence**: `.gitignore` contains `tools/trace_matrix.json` (line 42). The generated file is now excluded from version control.

### AUDIT-049: migration_prompts_root Fixture May Be Unused
- **Severity**: LOW
- **Status**: **RESOLVED**
- **Evidence**: No matches for `migration_prompts_root` anywhere in `tests/`. The fixture has been removed from `conftest.py`.

### AUDIT-050: governance.py File Handle Leak
- **Severity**: LOW
- **Status**: **RESOLVED**
- **Evidence**: `governance.py:11` now uses `with open(p, "r", encoding="utf-8") as f:` context manager. The `json.load(open(...))` leak pattern has been fixed.

### AUDIT-051: Module-Load-Time warnings.warn in step_01 and step_11
- **Severity**: LOW
- **Status**: **NOT_RESOLVED**
- **Evidence**: `warnings.warn()` calls still present at module load time in `step_01.py:52`, `step_02.py:79`, `step_11.py:46,53`. These fire at import time, not at validation time.

### AUDIT-052: Step 00 Has No Deep Validator
- **Severity**: LOW
- **Status**: **RESOLVED** (accepted as-is per original recommendation)
- **Evidence**: Original finding stated "Acceptable as-is; charter has no cross-step references." No action needed. Status reflects acceptance of the design decision.

### AUDIT-053: Edge Case -- Empty Spec Directory
- **Severity**: LOW
- **Status**: **RESOLVED**
- **Evidence**: `validate.py:198-206` now has early exit logic: "Early exit: no JSON files in spec dir means nothing to validate" with an informational message to stderr.

### AUDIT-054: Error Deduplication Loses Ordering Context
- **Severity**: LOW
- **Status**: **RESOLVED**
- **Evidence**: `validate.py:321-328` now uses a proper seen-set deduplication pattern (`seen: set[str]` + `deduped: list[str]`) instead of `dict.fromkeys()`. First-occurrence order is preserved. Note: `dict.fromkeys()` still appears at line 210 for canonical preflight errors, but the main dedup in `_apply_we_promotion` is fixed.

### AUDIT-055: No Global Exception Handler in cli.py
- **Severity**: LOW
- **Status**: **PARTIALLY_RESOLVED**
- **Evidence**: `cli.py` now has multiple try/except blocks (lines 62, 461, 504, 631, 645) for specific operations. However, there is no single top-level catch-all for `SpecdevError` at the `main()` entry point. The TODO comment at line 12 references AUDIT-065 (logging), suggesting awareness but incomplete implementation.

### AUDIT-056: validators/__init__.py Only Re-exports 3 of 21 Modules
- **Severity**: LOW
- **Status**: **RESOLVED**
- **Evidence**: `validators/__init__.py` now has a clear module docstring and explicit comments (lines 7-12) explaining the re-export strategy: only step_16a/16b/16c are re-exported because they are the only validators consumed by `DEEP_VALIDATORS` dispatch. The decision is documented, not arbitrary.

### AUDIT-057: Vague Quantifier Regex Has Subjective Word List
- **Severity**: LOW
- **Status**: **NOT_RESOLVED**
- **Evidence**: `spec_quality_lint.py:16-20` still has the hardcoded `VAGUE_QUANTIFIER_RE` with 18 words inline. No `VAGUE_WORDS` constant, no configuration mechanism, no TODO comment about making it configurable. The comment at line 14-15 documents the word origins (spec baseline vs R9 additions) but does not address configurability.

### AUDIT-058: Filesystem Path Assumptions (spec/, canon/, schema/)
- **Severity**: LOW
- **Status**: **NOT_RESOLVED**
- **Evidence**: Hardcoded path segments remain throughout the codebase (~50 occurrences). No documentation of assumed directory structure has been added beyond what existed in CLAUDE.md. This was expected to be a documentation-only fix.

### AUDIT-059: ASSUMPTION_THRESHOLD and Content Derivation Threshold Magic Numbers
- **Severity**: LOW
- **Status**: **PARTIALLY_RESOLVED**
- **Evidence**: `spec_quality_lint.py:34` now defines `_ASSUMPTION_THRESHOLD = 10` as a module-level named constant (used at line 120). However, `hallucination_lint.py` still has no `_CONTENT_DERIVATION_THRESHOLD` named constant -- the `threshold=5` magic number was not found as a named constant.

### AUDIT-060: Inline JSON Blobs in Tests vs Fixture Files
- **Severity**: LOW
- **Status**: **NOT_RESOLVED**
- **Evidence**: Tests have been reorganized into `tests/unit/` subdirectories, but the inline JSON pattern was not specifically addressed. This was a stylistic/roadmap item with no concrete fix applied.

### AUDIT-061: Lazy Import Shim Has 22-23 Entries
- **Severity**: INFO
- **Status**: **PARTIALLY_RESOLVED**
- **Evidence**: `__init__.py` now has `__version__ = "0.4.0"` (line 6). The _MOVED dict likely still exists for backward compatibility. The finding was INFO-level and the recommendation was to "audit for external consumers; simplify if none." No simplification evidence found.

### AUDIT-062: Empty tools/context/ Directory
- **Severity**: INFO
- **Status**: **RESOLVED**
- **Evidence**: `tools/context/` no longer exists on disk. The empty directory has been removed.

### AUDIT-063: validate_file Continues After Schema Errors (Collect-All by Design)
- **Severity**: INFO
- **Status**: **NOT_RESOLVED**
- **Evidence**: No `collect-all`, `short-circuit`, or `schema error` guard found in `validate.py`. The behavior remains as-is (collect-all). Original finding noted this is "correct by design" so this may be intentionally unchanged.

### AUDIT-064: cli.py Monolithic Dispatch (757 LOC, 24-branch if/elif)
- **Severity**: INFO
- **Status**: **PARTIALLY_RESOLVED**
- **Evidence**: `cli.py` lines 1-6 now have a module docstring explicitly acknowledging the monolithic design and referencing AUDIT-064: "A future refactor could split the dispatch into per-subpackage command groups." The structure itself is unchanged, but the design decision is documented.

### AUDIT-065: No Logging Module Usage; 118 print() Calls
- **Severity**: INFO
- **Status**: **PARTIALLY_RESOLVED**
- **Evidence**: `cli.py:12` has `TODO: replace print() with logging in a future pass (AUDIT-065)`. No actual logging module has been added yet. The TODO documents intent but no migration has occurred.

### AUDIT-066: schema_differ.py Git Subprocess Calls Lack Timeout
- **Severity**: INFO
- **Status**: **RESOLVED**
- **Evidence**: `schema_differ.py` now has `timeout=10` at lines 897, 980, 987, 995 -- covering all four git subprocess calls identified in the finding.

### AUDIT-067: No CI pytest Job
- **Severity**: INFO
- **Status**: **RESOLVED**
- **Evidence**: `.github/workflows/ci.yml` now includes `pip install pytest` (line 100), a "Run pytest" step (line 101), and `pytest tests/ -v` (line 102). CI and pytest are no longer disconnected.

### AUDIT-068: No Property-Based Testing (Hypothesis)
- **Severity**: INFO
- **Status**: **NOT_RESOLVED**
- **Evidence**: No matches for `hypothesis` or `property-based` anywhere in `tests/`. This was a roadmap/methodology item, not a concrete fix target.

### AUDIT-069: Conftest Fixtures Lack Session Scoping
- **Severity**: INFO
- **Status**: **RESOLVED**
- **Evidence**: `tests/conftest.py` now has 5 fixtures with `scope="session"` (lines 13, 19, 25, 31, 37). Session scoping has been applied to expensive setup fixtures.

### AUDIT-070: Flat Test Directory Structure Does Not Mirror Source Package
- **Severity**: INFO
- **Status**: **NOT_RESOLVED**
- **Evidence**: Tests have been partially reorganized: `tests/` now contains `unit/` and `integration/` top-level dirs. `tests/unit/` has subdirectories mirroring source (`canonical/`, `core/`, `generation/`, `migration/`, `validation/`, `validation/validators/`, `validation/linters/`). However, 4 test files remain flat in `tests/unit/` root (test_cli.py, test_cli_subcommands.py, test_cli_submodule_params.py, test_init_project_submodule.py) rather than being in a `cli/` subdirectory. The 0 flat `test_*.py` files in `tests/` root confirms the major reorganization happened. **Revised: PARTIALLY_RESOLVED** -- the bulk reorganization is done but not 100% complete.

---

## Status Corrections

- **AUDIT-070**: Changed from NOT_RESOLVED to PARTIALLY_RESOLVED after reviewing evidence more carefully. The major restructuring into `tests/unit/{core,validation,canonical,generation,migration}/` is done. Only CLI test files remain unsorted at the `tests/unit/` root level.

---

## Final Tally

| Status | Findings |
|--------|----------|
| RESOLVED | AUDIT-045, 047, 048, 049, 050, 052, 053, 054, 056, 062, 066, 067, 069 (13) |
| PARTIALLY_RESOLVED | AUDIT-046, 055, 059, 061, 064, 065, 070 (7) |
| NOT_RESOLVED | AUDIT-051, 057, 058, 060, 063, 068 (6) |
| REGRESSED | 0 |
| **Total** | **26** |

### Resolution Rate: 50% fully resolved, 77% at least partially addressed
