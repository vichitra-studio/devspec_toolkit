# P5 Batch 2: Error System + Format Fixes — Execution Report

**Date:** 2026-03-18
**Batch:** 2 (FIX-025 through FIX-029)
**Status:** PASS — 830/830 tests passing

---

## FIX-025: validate.py — Mega-Refactor (9 findings)

**File:** `tools/specdev_tools/validation/validate.py`
**Status:** COMPLETE

### Phase A — Imports & Config
1. **Layer violation (AUDIT-005):** Added `# TODO: move to cli.py in FIX-030 (Batch 3)` comment to `prompt_schema_sync` import. Import and call site preserved.
2. **Centralised config (AUDIT-036):** Replaced 3 inline `os.environ.get("SPECDEV_*")` calls with `get_config()` properties:
   - `SPECDEV_REPLAY_DIFF_ERROR_MODE` in `validate_dir()`
   - `SPECDEV_WARNINGS_AS_ERRORS` / `SPECDEV_PROMOTE_CODES` in promotion block
   - `SPECDEV_REPLAY_BASE_REF` in `_resolve_replay_base_ref()`
   - Added `reset_config()` call at top of `validate_dir()` to ensure tests that dynamically set env vars get fresh config.
3. **Replace _load_* functions (AUDIT-019):** Removed `_load_json_artifact` (~22 LOC). Rewrote `_load_component_ids` and `_load_capability_ids` to use `load_sibling_artifact()` from `core.loaders`. Rewrote `_load_nfrs_data` and `_load_monitoring_data` to use `load_json_artifact()` from `core.loaders`.

### Phase B — Logic Changes
4. **W->E promotion in validate_file (AUDIT-014):** Added `_apply_we_promotion()` call at end of `validate_file()` so single-file validation also applies W->E promotion.
5. **Fragile string W->E promotion (AUDIT-033):** Replaced `str.replace(w_code, e_code, 1)` with `re.sub(r'\b' + re.escape(w_code) + r'\b', ...)` — promotion now works regardless of W-code position in message.
6. **Dedup ordering (AUDIT-054):** Replaced `dict.fromkeys` with explicit `seen` set + list append for clearer first-occurrence-preserving dedup.
7. **Empty spec dir (AUDIT-053):** Added early exit in `validate_dir()` — if spec_dir has no `.json` files, prints info message and returns empty list.

### Phase C — Documentation
8. **DEEP_VALIDATORS (AUDIT-043):** Added comment documenting the hardcoded dict and noting auto-discovery as future work.
9. **Module docstring (AUDIT-004):** Added docstring explaining validate.py's role as central orchestrator and noting future split option.

**LOC delta:** ~+50 / -65 / net -15

---

## FIX-026: governance.py — Fix File Handle Leak

**File:** `tools/specdev_tools/validation/governance.py`
**Status:** COMPLETE

Replaced `json.load(open(p, "r", encoding="utf-8"))` with `with open(p, "r", encoding="utf-8") as f:` context manager to prevent file handle leak.

**LOC delta:** +2 / -1 / net +1

---

## FIX-027: Create core/constants.py + Extract _STEP_TO_TEMPLATE

**Files:**
- `tools/specdev_tools/core/constants.py` (CREATED)
- `tools/specdev_tools/generation/prompt_generator.py` (MODIFIED)

**Status:** COMPLETE

Created `core/constants.py` with the shared `STEP_TO_TEMPLATE` dict (18 entries, superset of both prompt_generator and planner copies). Updated `prompt_generator.py` to import from the shared location and alias to `_STEP_TO_TEMPLATE` for backward compat.

**LOC delta:** +38 (new file) / +2 -15 (prompt_generator) / net +25

---

## FIX-028: planner.py — Use Shared _STEP_TO_TEMPLATE

**File:** `tools/specdev_tools/migration/planner.py`
**Status:** COMPLETE (depends on FIX-027)

Replaced local 18-entry `_STEP_TO_TEMPLATE` dict with import from `core.constants.STEP_TO_TEMPLATE`. Local alias preserved for backward compat.

**LOC delta:** +2 / -20 / net -18

---

## FIX-029: schema_differ.py — Add Git Timeout, Scope git add

**File:** `tools/specdev_tools/generation/schema_differ.py`
**Status:** COMPLETE

1. Added `timeout=10` to all 4 `subprocess.run()` git calls (lines 888, 970, 976, 983).
2. Changed `git add -A` to `git add <spec_dir>` — scoped to spec directory only instead of staging everything.
3. Added module docstring noting the module's size (~1300 LOC) and future split candidate.

**LOC delta:** +8 / -4 / net +4

---

## Batch Gate

```
830 passed in 33.42s
```

All 830 tests passing. No regressions.

## Notes

- The `reset_config()` call at the top of `validate_dir()` is necessary because tests dynamically set `SPECDEV_*` env vars and the config singleton would otherwise return stale values. This is a minimal-impact solution that keeps the singleton pattern intact for production use while remaining test-friendly.
- The `_load_nfrs_data` and `_load_monitoring_data` functions could not use `load_sibling_artifact` directly because they return full dict data (not just ID sets). They were rewritten to use `load_json_artifact` from `core.loaders` for file loading while preserving the sibling-then-fallback search pattern.
