# P4 Fix Report (Agent G)

**Date:** 2026-03-18
**Input:** p4-review-F1.md, p4-review-F2.md
**Target:** p4-out-fix-plan.md

---

## Fixes Applied

### 1. CRITICAL: load_upstream_ids return type (F2 MF-1)

**Location:** FIX-001, lines 49, 55

**Changes:**
- Changed `load_upstream_ids` return type from `set[str]` to `Optional[set[str]]`
- Added bold note: "MUST preserve None return for missing upstream files — W590 depends on this"
- Clarified semantics: returns `None` if no source file found, `set[str]` if file exists
- Updated error handling contract: `load_upstream_ids` returns `None` on file-not-found (not empty set)
- Also added `_load_inv_ids` to the list of functions replaced by `load_upstream_ids` (1 copy in step_08)

### 2. HIGH: Batch 0 test gate paths (F1 MF-1)

**Location:** FIX-001 line 56, FIX-002 line 73, FIX-003 line 94

**Changes:**
- FIX-001 test gate: `pytest tests/test_loaders.py` → `pytest tests/ -x --tb=short` with note about Batch 5 path
- FIX-002 test gate: `pytest tests/test_linter_utils.py` → `pytest tests/ -x --tb=short` with note about Batch 5 path
- FIX-003 test gate: `pytest tests/test_config.py` → `pytest tests/ -x --tb=short` with note about Batch 5 path

**Rationale:** Batch 0 runs before test reorganization (Batch 4) and before dedicated tests are created (Batch 5). At Batch 0 time, these modules have no consumers and no dedicated test files. Full suite run confirms no import errors or regressions. Each test gate notes where the dedicated tests will be created in Batch 5.

### 3. HIGH: E310 rename ambiguity (F1 MF-2)

**Location:** FIX-004 item 3, line 117

**Changes:**
- Removed ambiguous "use E311 or rename E310" language
- Explicit decision: assign NEW code E311 for MISSING_ENUM_PROVENANCE
- E310 stays as PROMPT_SCHEMA_DRIFT — no rename
- FIX-017 does NOT need to change E310
- FIX-017 adds E311 to the global registry as part of its error code audit

This eliminates runtime coordination between FIX-004 (Set 1A) and FIX-017 (Set 1C).

### 4. MEDIUM: FIX-025 sub-step ordering (F2 SF-2)

**Location:** FIX-025 description, lines 412-427

**Changes:**
- Restructured 9 sub-steps into 3 explicit phases: Phase A (Imports & Config), Phase B (Logic), Phase C (Documentation)
- Numbered sub-steps 1-9 with explicit dependency annotations
- Phase A: sub-steps 1, 2, 3 (no interdependencies)
- Phase B: sub-steps 4, 5 (sequential — both touch W->E promotion), 6, 7 (independent)
- Phase C: sub-steps 8, 9 (safe documentation-only changes)
- Added note on sub-step 3 clarifying that validate.py loaders should use `load_sibling_artifact` (not `load_upstream_ids`) due to different interface pattern

### 5. MEDIUM: step_08 _load_inv_ids (F2 SF-4)

**Location:** FIX-007 title and description, lines 150-163

**Changes:**
- Added `_load_inv_ids` to FIX-007 title
- Added new item 4: `Replace _load_inv_ids (~20 LOC) with load_upstream_ids(toolkit_root, "06", "invariants", "inv_id")`
- Added bold note: "step_08 has 4 loaders total — all 4 must be replaced"
- Renumbered existing items 4-5 to 5-6

### 6. MEDIUM: load_sibling_artifact fallback_root (F2 SF-1)

**Location:** FIX-001 item 2, line 50

**Changes:**
- Added `fallback_root: Path | None = None` keyword parameter to `load_sibling_artifact` signature
- Added note explaining that step_14's loaders check both artifact_path sibling AND toolkit_root/spec/ as fallback
- The `fallback_root` parameter enables this: when set, if sibling path does not exist, function checks `fallback_root/spec/{sibling_prefix}_*.json`

---

## Summary

| # | Priority | Issue | Status |
|---|----------|-------|--------|
| 1 | CRITICAL | load_upstream_ids return type | FIXED — Optional[set[str]], None semantics preserved |
| 2 | HIGH | Batch 0 test gate paths | FIXED — full suite gates with Batch 5 path notes |
| 3 | HIGH | E310 rename ambiguity | FIXED — E311 new code, E310 unchanged |
| 4 | MEDIUM | FIX-025 sub-step ordering | FIXED — 3 phases with dependency annotations |
| 5 | MEDIUM | step_08 _load_inv_ids missing | FIXED — added as item 4 in FIX-007 |
| 6 | MEDIUM | load_sibling_artifact fallback | FIXED — fallback_root parameter added |

All 6 fixes applied. No structural changes to batch ordering or task boundaries.
