# P5 Dead Code & Unused Import Cleanup Report

**Date**: 2026-03-18
**Test gate**: 997 passed (down from 999 -- 2 tests removed with their dead code target)

## Changes Made

### 1. Unused imports removed from validator files

| File | Removed Import | Reason |
|------|---------------|--------|
| `validators/step_10.py` | `import json`, `import os` | Neither `json.` nor `os.` referenced anywhere in file |
| `validators/step_08.py` | `check_cross_step_refs` (from loaders) | Imported but never called |
| `validators/step_12.py` | `KEBAB_ID_RE` (from loaders) | Imported but never referenced |
| `validators/step_13a.py` | `import re` | `re` never used; file uses `KEBAB_ID_RE` from loaders instead |
| `validators/step_15.py` | `import re` | `re` never used; file uses `KEBAB_ID_RE` from loaders instead |

### 2. Dead code removed from linter files

| File | Removed Code | Reason |
|------|-------------|--------|
| `hallucination_lint.py` | `_tokenize` lambda alias (line 264) | Backward-compat alias labeled "for tests that import _tokenize" -- no tests or production code import it from this module |

### 3. Dead code removed from validate.py

| File | Removed Code | Reason |
|------|-------------|--------|
| `validate.py` | `_detect_spec_root()` function (9 LOC) | Defined but never called from any production code path |

### 4. Test updates

| File | Change | Reason |
|------|--------|--------|
| `tests/unit/validation/linters/test_hallucination_lint_rules.py` | Updated import to use `tokenize_free_text` from `linter_utils` + local `_tokenize` alias | Removed backward-compat `_tokenize` from hallucination_lint.py |
| `tests/unit/validation/test_validate_submodule.py` | Removed `TestDetectSpecRoot` class (2 tests), removed `_detect_spec_root` import | Tests covered dead function that was removed |

### 5. Files examined but clean (no changes needed)

- `validators/step_01.py` -- all imports used
- `validators/step_02.py` -- all imports used
- `validators/step_02a.py` -- all imports used
- `validators/step_03.py` -- all imports used
- `validators/step_04.py` -- all imports used
- `validators/step_05.py` -- all imports used
- `validators/step_06.py` -- all imports used
- `validators/step_07.py` -- `json` and `os` used in `_load_canonical_stages`
- `validators/step_09.py` -- all imports used
- `validators/step_11.py` -- `json` and `os` used in `_load_component_ids` / `_load_api_ids`
- `validators/step_13.py` -- `json`, `os`, `re` all used; `Optional`/`Set` used in type hints
- `validators/step_14.py` -- all imports used
- `validators/step_16.py` -- all imports used
- `validators/step_16a.py` -- all imports used
- `validators/step_16b.py` -- all imports used
- `validators/step_16c.py` -- all imports used
- `spec_quality_lint.py` -- no dead helpers; uses linter_utils properly
- `forward_replay_check.py` -- no dead helpers; uses linter_utils properly
- `validate.py` -- no other dead code found; all remaining `_load_*` helpers are called from `_build_validation_context`

## Summary

- **7 unused imports** removed across 5 validator files
- **1 dead backward-compat alias** removed from hallucination_lint.py
- **1 dead function** removed from validate.py
- **2 dead tests** removed (tested the removed dead function)
- **1 test file** updated to import from the correct centralized module
- **997 tests passing** (999 - 2 removed dead tests)
