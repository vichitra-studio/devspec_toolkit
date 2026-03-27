# P7: Follow-Up Implementation Plan

## Overview

- **What**: SpecError migration (AUDIT-007/008) + `--json` output on all commands (AUDIT-025)
- **Why**: Structured errors enable machine-parsable output, consistent formatting, proper W-to-E promotion without regex hacks, and CI/LLM-consumable JSON output
- **Dependency**: AUDIT-025 depends on AUDIT-007 (structured errors make JSON serialization trivial)
- **Unblocks**: AUDIT-008 (inconsistent format), AUDIT-026 (CLI output standardization), AUDIT-033 (programmatic error handling)

## Current State

### SpecError Infrastructure (Exists, Unused)

**File**: `tools/specdev_tools/core/errors.py`

- Lines 7-16: `SpecError` dataclass with fields `code`, `message`, `path` and `render()` method
- Lines 19-108: `ERROR_CODES` registry with **82 registered codes** (E1xx-E5xx, W1xx-W5xx)
- Lines 115-140: `PROMOTABLE_PAIRS` dict mapping 18 W-codes to E-code counterparts
- Lines 143-146: `make_error()` factory that validates code against `ERROR_CODES`
- **Neither `SpecError` nor `make_error()` is called anywhere in production code**

### Error Emission Sites (All Return `list[str]`)

| Module Group | Files | Total `.append()` Sites | Sites Without Error Code |
|---|---|---|---|
| Validators (`validation/validators/step_*.py`) | 21 files | 158 | ~75 |
| Linters (`validation/*_lint.py`) | 7 files | 66 | ~19 |
| Canonical (`canonical/lint.py`, `integrity.py`, `registry.py`) | 3 files | 60 | ~3 |
| Canonical autofix (`canonical/autofix.py`) | 1 file | ~12 | ~3 |
| Forward replay (`forward_replay_check.py`) | 1 file | 7 (string errors) + 5 (internal dict appends) | 0 |
| Traceability (`traceability_closure.py`) | 1 file | 7 | 0 |
| Extraction intent (`extraction_intent_check.py`) | 1 file | 4 | 0 |
| Dependency order (`dependency_order_lint.py`) | 1 file | 1 | 0 |
| Governance (`governance.py`) | 1 file | 2 | 2 |
| Prompt-schema sync (`generation/prompt_schema_sync.py`) | 1 file | 20 + 1 list-return | 0 |
| Canon-schema alignment (`canon_schema_alignment.py`) | 1 file | 5 | 0 |
| Matrix (`matrix.py`) | 1 file | 2 | ~1 |
| validate.py (orchestrator) | 1 file | ~12 inline | ~2 |
| **TOTAL** | **41 files** | **~362 sites** | **~105 without code prefix** |

**Note on forward_replay_check.py**: The file has 12 total `errors.append` calls, but 5 of those (lines 250, 261, 270, 289, 319) append dicts to an internal list in `_check_semantic_coverage()`, not error strings. Only 7 are actual error-string emission sites that need SpecError migration.

**Note on prompt_schema_sync.py**: The file has 20 `.append()` sites plus 1 additional error created via list-literal return in `_required_canonical_ref_errors()` (line 279). Total: 21 emission sites.

### Shared Helper: `linter_utils.py:check_no_duplicates()`

**CRITICAL DEPENDENCY**: `validation/linter_utils.py:check_no_duplicates()` (lines 155-187) takes `errors: list[str]` and appends raw strings directly. It is called by **9 validators**:

| Caller | Call Site |
|---|---|
| `step_04.py` | `check_no_duplicates(instance.get("functional_requirements", []), "fr_id", "fr_id", errors)` |
| `step_05.py` | `check_no_duplicates(instance.get("apis", []), "api_id", "api_id", errors)` |
| `step_06.py` | `check_no_duplicates(instance.get("rules", []), "inv_id", "inv_id", errors)` |
| `step_07.py` | `check_no_duplicates(instance.get("nfrs", []), "nfr_id", "nfr_id", errors)` |
| `step_08.py` | `check_no_duplicates(instance.get("fixtures", []), "fixture_id", "fixture_id", errors)` |
| `step_09.py` | `check_no_duplicates(instance.get("milestones", []), "milestone_id", "milestone_id", errors)` |
| `step_11.py` | `check_no_duplicates(instance.get("threats", []), "threat_id", "threat_id", errors)` |
| `step_12.py` | `check_no_duplicates(instance.get("jobs", []), "job_id", "job_id", errors)` |
| `step_13.py` | `check_no_duplicates(instance.get("extensions", []), "extension_id", "extension_id", errors)` |

**This helper MUST be migrated to accept `list[SpecError]` before any validator batch runs.** If validators switch to `list[SpecError]` but `check_no_duplicates` still appends `str`, the type mismatch will cause runtime failures.

Other shared helpers in `linter_utils.py` that may need migration review:
- `collect_ids_and_refs()` — populates `refs: list[tuple[str, str, str]]`, not error lists; **no migration needed**
- `tokenize_free_text()` — returns `set[str]` tokens; **no migration needed**
- `is_reference_context()` — returns `bool`; **no migration needed**
- `iter_json()` — yields file paths; **no migration needed**

### Current Error Flow

```
validator/linter -> list[str]
    -> validate.py aggregates list[str]
    -> _apply_we_promotion() does regex W->E swapping on strings (lines 300-335)
    -> cli.py receives list[str], prints to stderr
    -> _is_warning_message() uses regex to classify W vs E (lines 21-29)
    -> _has_error_messages() decides exit code based on regex (lines 36-39)
```

### W-to-E Promotion (Current Regex Approach)

**File**: `tools/specdev_tools/validation/validate.py`, lines 300-335

`_apply_we_promotion()` uses `re.sub()` with word-boundary matching to swap W-codes to E-codes in raw strings. This is fragile: it depends on error messages always starting with the code, and the regex can silently fail on messages with embedded codes.

### Adapter Gap: Linter Calls in validate_dir() and validate_file()

**CRITICAL**: The original plan only placed an adapter in `_run_deep_validation()` at line 434. However, linter results are aggregated in **three** locations:

1. **`_run_deep_validation()` (line 434)**: Calls validators from `DEEP_VALIDATORS` dict. Returns `list[str]`.
2. **`validate_file()` (lines 171-183)**: Calls `lint_spec_quality_file()` and `validate_canonical_integrity_file()` directly, extending `enhanced_errors` with their results.
3. **`validate_dir()` (lines 208-297)**: Calls 7+ linters/checkers directly via `.extend()`:
   - `lint_canon_dir()` (line 211)
   - `validate_file()` (line 225, which itself aggregates)
   - `lint_spec_quality()` (line 234)
   - `lint_hallucinations()` (line 239)
   - `validate_canonical_integrity()` (line 247)
   - `check_traceability_closure()` (line 254)
   - `lint_dependency_order()` (line 261)
   - `check_forward_replay()` (line 280)
   - `check_extraction_intent()` (line 293)

If linters (Phase 2) or canonical modules (Phase 3) are migrated to return `list[SpecError]` before `validate_dir()`/`validate_file()` are updated (Phase 4), then mixed `str`/`SpecError` items will end up in the same list. `_apply_we_promotion()` will crash when it tries to run `re.sub()` on a `SpecError` object.

**Resolution**: Add `ensure_spec_errors()` adapters in `validate_dir()` and `validate_file()` as part of **Phase 0 (Prerequisites)**, before any linter/validator migration begins. This way, as each module is migrated, its `SpecError` returns pass through the adapter harmlessly (identity conversion), and unmigrated modules' `str` returns are parsed into `SpecError` objects.

### canonical/autofix.py

**MISSING FROM ORIGINAL PLAN**: `canonical/autofix.py` returns `dict[str, list[str]]` where values contain a mix of:
- E-coded error strings (e.g., `f"E520 UNRESOLVED_INPUT {path} invalid_json ..."`)
- Informational change strings (e.g., `f"{path} add {target_ref_field} from {source_field}"`)
- Warning strings (e.g., `f"WARN {path} skipped autofix for deprecated alias ..."`)

The CLI handler at `cli.py` lines ~347-392 checks `change.startswith("E")` to detect errors. This module has a unique return type (`dict[str, list[str]]` not `list[str]`) and needs special handling in the migration.

### CLI Subcommands (25 total, 2 have --json)

Commands with `--json`: `validate` (line 97), `traceability-check` (line 160)
Commands without `--json` (23):
1. `validate-all` 2. `matrix` 3. `fixtures-lint` 4. `invariants-check`
5. `seed-lint` 6. `docs-lint` 7. `prompt-sync` 8. `canonical-lint`
9. `canonical-integrity` 10. `canonical-autofix` 11. `spec-quality-lint`
12. `hallucination-lint` 13. `dependency-order-lint` 14. `forward-replay-check`
15. `governance-check` 16. `ai-help` 17. `changelog` 18. `align`
19. `prompt-context` 20. `canon-schema-alignment` 21. `env-check`
22. `dag-lint` 23. `extraction-intent-check`

### Test Baseline

- **997 tests** collected (all passing as of P6)
- **~235 test assertions** reference error codes directly (e.g., `assert "E590" in ...`) across **34 files** (includes integration test files `tests/integration/test_step_16.py` and `tests/integration/test_step_14.py`)
- **76 test assertions** match on unstructured strings (e.g., `"Duplicate"`, `"missing targets"`)
- **589 total [EW]\d{3} pattern occurrences** across the 34 test files (some files have many assertions)

---

## Key Design Decision: Migration Strategy

**Decision**: Change return types from `list[str]` to `list[SpecError]` incrementally, using a **dual-return adapter** during transition.

**Rationale**: A big-bang migration of 41 files + 997 tests is too risky. Instead:

1. Add a `to_strings()` helper on `list[SpecError]` for backward compatibility
2. **Migrate shared helpers first** (`check_no_duplicates` in linter_utils.py)
3. **Add adapters in validate.py** (`validate_file`, `validate_dir`, `_run_deep_validation`) before any producer migration
4. Migrate validators/linters one batch at a time
5. Update validate.py to accept both types during transition
6. Flip cli.py last, once all producers return `list[SpecError]`

**Helper additions to `core/errors.py`**:
```python
def render_errors(errors: list[SpecError]) -> list[str]:
    """Convert SpecError list to string list for backward compat."""
    return [e.render() for e in errors]

def ensure_spec_errors(items: list[str | SpecError]) -> list[SpecError]:
    """Parse string errors into SpecError objects during transition.

    Parsing heuristics (applied in order):
    1. If item is already a SpecError, pass through unchanged.
    2. If item is a string matching r'^([EW]\\d{3})\\s+(\\S+)\\s+(.*)':
       - group(1) = code, group(2) = mnemonic/path, group(3) = rest
       - If code is in ERROR_CODES, create SpecError(code=code, message=f"{mnemonic} {rest}")
    3. If item is a string matching r'^([EW]\\d{3})\\s+(.*)':
       - group(1) = code, group(2) = message
       - Create SpecError(code=code, message=message)
    4. Fallback: SpecError(code="E521", message=str(item))
       E521 VALIDATOR_RUNTIME is the catch-all for unrecognized error strings.
    """
    ...
```

---

## Phase 0: Prerequisites (MUST complete before any Phase 1-3 batch)

### Batch 0A: Core Helpers in `errors.py`

**File**: `tools/specdev_tools/core/errors.py`

Changes:
1. Add `render_errors(errors: list[SpecError]) -> list[str]` helper function
2. Add `make_errors(code: str, message: str, path: str | None = None) -> SpecError` alias (already exists as `make_error`)
3. Add `ensure_spec_errors(items: list[str | SpecError]) -> list[SpecError]` with the parsing heuristics documented above

**Test gate**: Unit test for `ensure_spec_errors` covering all 4 parsing paths.

### Batch 0B: Migrate `linter_utils.py:check_no_duplicates()`

**File**: `tools/specdev_tools/validation/linter_utils.py`

**Current signature**: `check_no_duplicates(items, id_field, label, errors: list[str], *, code="")`
**New signature**: `check_no_duplicates(items, id_field, label, errors: list[SpecError], *, code="")`

Changes:
1. `from ..core.errors import make_error, SpecError`
2. Change `errors` type annotation to `list[SpecError]`
3. Replace line 186: `errors.append(f"{code}Duplicate {label} '{value}' at index {i}".strip())`
   With: `errors.append(make_error(code.strip() or "E520", f"Duplicate {label} '{value}' at index {i}"))`
4. The `code` parameter currently receives strings like `"E310 "` (with trailing space). The new version should accept just the code string (e.g., `"E310"`) since `make_error` handles formatting.

**Callers to update simultaneously** (9 files — all must pass the `SpecError` list):
All 9 callers listed in the "Shared Helper" section above already pass their local `errors` list. Once those validators are migrated to `list[SpecError]`, the calls work naturally. During the transition, callers in Phase 1 batches must be updated to pass `list[SpecError]` lists.

**Test gate**: `pytest tests/unit/validation/linters/test_linter_utils.py` — update assertions from string matching to `SpecError.code` checks.

### Batch 0C: Add Adapters in validate.py

**File**: `tools/specdev_tools/validation/validate.py`

Add `ensure_spec_errors()` adapters at **every aggregation point** where linter/validator results are collected, so that mixed `str`/`SpecError` lists are normalized before further processing:

1. **`_run_deep_validation()` (line 440)**: Wrap return value:
   ```python
   result = validator(data, repo_root, context)
   return [e.render() for e in ensure_spec_errors(result)] if result else []
   ```

2. **`validate_file()` (line 169)**: Wrap deep_errors:
   ```python
   deep_errors = _run_deep_validation(step, data, repo_root, path)
   if deep_errors:
       enhanced_errors.extend([f"{path}: {e}" for e in deep_errors])
   ```
   (This already works because `_run_deep_validation` renders to strings. But once Phase 4 changes return types, the adapter ensures safety.)

3. **`validate_file()` (lines 172-174)**: Wrap quality lint:
   ```python
   quality_errors = lint_spec_quality_file(path, spec_dir=os.path.dirname(path))
   if quality_errors:
       enhanced_errors.extend([e if isinstance(e, str) else e.render() for e in quality_errors])
   ```

4. **`validate_file()` (lines 176-183)**: Wrap canonical integrity:
   ```python
   canonical_errors = validate_canonical_integrity_file(...)
   if canonical_errors:
       enhanced_errors.extend([e if isinstance(e, str) else e.render() for e in canonical_errors])
   ```

5. **`validate_dir()` (lines 209-218)**: Wrap `canonical_preflight_errors` from `lint_canon_dir()`:
   ```python
   canonical_preflight_errors = [
       e if isinstance(e, str) else e.render()
       for e in dict.fromkeys(lint_canon_dir(repo_root, canon_dir=canon_dir))
   ]
   ```
   This path has TWO consumers: (a) early return at line 218 (`return canonical_preflight_errors`), and (b) `.extend()` at line 236. Both must receive `list[str]` until Phase 4.

   **Also update `_has_canonical_bootstrap_failure()` (line 338)**: This helper does `token in err` string containment checks. During transition, add a guard:
   ```python
   def _has_canonical_bootstrap_failure(errors: list[str]) -> bool:
       # errors are always strings at this point (adapters render SpecError upstream)
   ```
   No code change needed as long as the adapter at lines 209-216 renders to strings. But document this dependency so Phase 4 doesn't accidentally break it.

6. **`validate_dir()` (line 234)**: Wrap `lint_spec_quality`:
   ```python
   failures.extend([e if isinstance(e, str) else e.render() for e in lint_spec_quality(spec_dir)])
   ```

7. **`validate_dir()` (lines 238-244)**: Wrap `lint_hallucinations`
8. **`validate_dir()` (lines 246-251)**: Wrap `validate_canonical_integrity`
9. **`validate_dir()` (lines 253-256)**: Wrap `check_traceability_closure`
10. **`validate_dir()` (lines 261-262)**: Wrap `lint_dependency_order`
11. **`validate_dir()` (lines 279-287)**: Wrap `check_forward_replay`
12. **`validate_dir()` (line 293)**: Wrap `check_extraction_intent`

The adapters are lightweight (identity for strings, `.render()` for SpecError) and will be removed in Phase 4 when the orchestrator itself migrates to `list[SpecError]`.

**Also fix line 442**: `_run_deep_validation` catch-all error:
```python
# Before:
return [f"Deep Validation Critical Error: {str(e)}"]
# After:
return [f"E521 VALIDATOR_RUNTIME Deep Validation Critical Error: {str(e)}"]
```

**Test gate**: `pytest tests/ (997 pass, no regressions)` — adapters are transparent.

### Batch 0D: Assign Error Codes to Uncoded Sites

Before migrating, every `.append(f"...")` site that lacks an `E/W` prefix must be assigned a code. The audit found ~105 such sites. Most map naturally to existing codes:
- Duplicate ID errors -> `E410` or `E520`
- Missing field errors -> `E520 UNRESOLVED_INPUT`
- Format/convention violations -> `E530 INVENTED_ENUM_OR_ID` or `E520`
- Governance errors -> needs new code `E303 CI_GATE_VIOLATION` (already registered but unused)

**TEST GATE**: `pytest tests/ (997 pass, no regressions)`

---

## Phase 1: SpecError Migration -- Validators (AUDIT-007)

> **PREREQUISITE**: Phase 0 (Batches 0A-0D) MUST be complete before any Phase 1 batch begins.
> In particular, `check_no_duplicates()` in `linter_utils.py` must already accept `list[SpecError]` (Batch 0B).
> Once Phase 0 is complete, **Phase 1 batches can run in parallel** since each validator is independently called via `_run_deep_validation()` and the adapter in Batch 0C ensures backward compatibility.

### Batch 1A: Simple Validators (5 files, ~12 emission sites)

| File | Function | Emission Sites | Notes |
|---|---|---|---|
| `validators/step_01.py` | `validate_step_01()` | 1 | Single capability cross-ref check |
| `validators/step_02.py` | `validate_step_02()` | 7 | 4 uncoded (duplicate, naming) |
| `validators/step_02a.py` | `validate_step_02a()` | 1 | 1 uncoded (glossary definition) |
| `validators/step_04.py` | `validate_step_04()` | 4 | 4 uncoded (FR naming, duplication); calls `check_no_duplicates` |
| `validators/step_05.py` | `validate_step_05()` | 5 | 2 uncoded (duplicate API, method); calls `check_no_duplicates` |

**Changes per file**:
1. `from ...core.errors import make_error, SpecError`
2. Change return type annotation: `-> list[SpecError]`
3. Replace `errors.append(f"E590 CROSS_STEP_ID_NOT_FOUND ...")` with `errors.append(make_error("E590", "...", path=...))`
4. Replace uncoded `errors.append(f"Duplicate ...")` with `errors.append(make_error("E520", "duplicate_id ...", path=...))`

**Test gate**: Run `pytest tests/unit/validation/validators/ -k "step_01 or step_02 or step_04 or step_05"`. Tests that assert on strings must be updated to assert on `SpecError.render()` output or `SpecError.code`.

### Batch 1B: Medium Validators (5 files, ~44 emission sites)

| File | Function | Emission Sites | Notes |
|---|---|---|---|
| `validators/step_06.py` | `validate_step_06()` | 12 | 5 uncoded (invariant format); calls `check_no_duplicates` |
| `validators/step_07.py` | `validate_step_07()` | 6 | 4 uncoded (NFR naming); calls `check_no_duplicates` |
| `validators/step_08.py` | `validate_step_08()` | 7 | 5 uncoded (fixture naming/target); calls `check_no_duplicates` |
| `validators/step_09.py` | `validate_step_09()` | 5 | 2 uncoded (tech_stack, milestones); calls `check_no_duplicates` |
| `validators/step_10.py` | `validate_step_10()` | 6 | 5 uncoded (governance format) |

**Test gate**: `pytest tests/unit/validation/validators/ -k "step_06 or step_07 or step_08 or step_09 or step_10"`

### Batch 1C: Complex Validators (5 files, ~39 emission sites)

| File | Function | Emission Sites | Notes |
|---|---|---|---|
| `validators/step_11.py` | `validate_step_11()` | 9 | 6 uncoded (red-team threats); calls `check_no_duplicates` |
| `validators/step_12.py` | `validate_step_12()` | 7 | 4 uncoded (CI gates); calls `check_no_duplicates` |
| `validators/step_13.py` | `validate_step_13()` | 7 | 1 uncoded (extension); calls `check_no_duplicates` |
| `validators/step_13a.py` | `validate_step_13a()` | 6 | 3 uncoded (completeness) |
| `validators/step_14.py` | `validate_step_14()` | 14 | 5 uncoded (roadmap) |

**Test gate**: `pytest tests/unit/validation/validators/ -k "step_11 or step_12 or step_13 or step_14"`

### Batch 1D: Trinity Loop Validators (5 files, ~48 emission sites)

| File | Function | Emission Sites | Notes |
|---|---|---|---|
| `validators/step_15.py` | `validate_step_15()` | 11 | 5 uncoded (scaffold) |
| `validators/step_16.py` | `validate_step_16()` | 29 | 8 uncoded (impl context) |
| `validators/step_16a.py` | `validate_step_16a()` | 4 | 1 uncoded |
| `validators/step_16b.py` | `validate_step_16b()` | 4 | 1 uncoded |
| `validators/step_16c.py` | `validate_step_16c()` | 3 | 1 uncoded |

**Note**: step_16 has 29 `errors.append` sites (verified by line-by-line count), not the previously estimated higher number. This includes helper function `_check_behavior_validation_pairing` (1 site at line 71).

**Test gate**: `pytest tests/unit/validation/validators/ -k "step_15 or step_16"`

### Batch 1E: step_03 (standalone, 10 emission sites)

| File | Function | Emission Sites | Notes |
|---|---|---|---|
| `validators/step_03.py` | `validate_step_03()` | 10 | 5 uncoded (glossary) |

**Test gate**: `pytest tests/unit/validation/validators/ -k "step_03"`

---

## Phase 2: SpecError Migration -- Linters (AUDIT-007 continued)

> **PREREQUISITE**: Phase 0 MUST be complete (adapters in validate.py ensure mixed types are handled).
> Phase 2 batches **can run in parallel** since each linter is independently called. The adapters in `validate_dir()` and `validate_file()` (Batch 0C) ensure that as each linter switches from `list[str]` to `list[SpecError]`, the orchestrator handles both types correctly.

### Batch 2A: Core Linters (4 files, ~38 emission sites)

| File | Function | Emission Sites | Uncoded Sites |
|---|---|---|---|
| `validation/spec_quality_lint.py` | `lint_spec_quality()`, `lint_spec_quality_file()` | 10 | 0 (all have E/W codes) |
| `validation/hallucination_lint.py` | `lint_hallucinations()` | 16 | 0 (all have E/W codes) |
| `validation/fixtures_lint.py` | `lint_fixtures()` | 7 | 7 (all uncoded!) |
| `validation/seed_lint.py` | `lint_seeds()` | 22 | 12 uncoded |

**fixtures_lint.py** is the worst offender -- all 7 messages are plain text like `f"{fid}: missing targets"`. Each needs a code assigned:
- `"{fid}: missing targets"` -> `E520 UNRESOLVED_INPUT`
- `"{fid}: targets unknown {label} '{tid}'"` -> `E590 CROSS_STEP_ID_NOT_FOUND`
- `"{fid}: missing input/expected"` -> `E520 UNRESOLVED_INPUT`
- `"{fid}: expected.status must be..."` -> `E520 UNRESOLVED_INPUT`
- `"{fid}: expected.body must be..."` -> `E520 UNRESOLVED_INPUT`
- `"{fid}: expected.headers must be..."` -> `E520 UNRESOLVED_INPUT`
- `"{fid}: expected should be..."` -> `E520 UNRESOLVED_INPUT`

**seed_lint.py** has 12 uncoded messages:
- `"Missing seed manifest: ..."` -> `E520 UNRESOLVED_INPUT`
- `"Failed to read seed manifest: ..."` -> `E520 UNRESOLVED_INPUT`
- `"Seed manifest has duplicate seed_id values."` -> `E410 CANONICAL_ALIAS_COLLISION`
- `"Seed '...' path '...' does not exist..."` -> `E520 UNRESOLVED_INPUT`
- `"Seed '...' path escapes project root"` -> `E520 UNRESOLVED_INPUT`
- Various `f"{file_path}: ..."` messages -> `E520 UNRESOLVED_INPUT`
- `"global_seed_order references unknown..."` -> `E520 UNRESOLVED_INPUT`
- `"spec_dir scope warning..."` -> `W570 GRACEFUL_SKIP`

**Test gate**: `pytest tests/unit/validation/linters/`

### Batch 2B: Structural Linters (3 files, ~11 emission sites)

| File | Function | Emission Sites | Uncoded Sites |
|---|---|---|---|
| `validation/docs_lint.py` | `lint_docs()` | 5 | 5 uncoded |
| `validation/dag_lint.py` | `lint_dag()` | 5 | 0 |
| `validation/dependency_order_lint.py` | `lint_dependency_order()` | 1 | 0 |

**docs_lint.py** messages:
- `"Missing root README.md at ..."` -> `E520 UNRESOLVED_INPUT`
- `"Docs scope not found: ..."` -> `E520 UNRESOLVED_INPUT`
- `"Missing README.md in ..."` -> `E520 UNRESOLVED_INPUT`
- `"Missing seed manifest: ..."` -> `E520 UNRESOLVED_INPUT`
- `"Failed to read seed manifest: ..."` -> `E520 UNRESOLVED_INPUT`

**Test gate**: `pytest tests/unit/validation/linters/ -k "docs or dag or dependency"`

### Batch 2C: Cross-Step Linters (3 files, ~18 emission sites)

| File | Function | Emission Sites | Uncoded Sites |
|---|---|---|---|
| `validation/forward_replay_check.py` | `check_forward_replay()` | 7 (string) | 0 |
| `validation/traceability_closure.py` | `check_traceability_closure()` | 7 | 0 |
| `validation/extraction_intent_check.py` | `check_extraction_intent()` | 4 | 0 |

All already emit coded messages. Migration is purely mechanical: change `str` appends to `make_error()` calls.

**Note on forward_replay_check.py**: Only 7 of the 12 `errors.append` calls in this file produce error strings. The other 5 (lines 250, 261, 270, 289, 319) append internal dict structures inside `_check_semantic_coverage()` and do not need SpecError migration.

**Test gate**: `pytest tests/unit/validation/linters/ -k "forward_replay or traceability or extraction"`

### Batch 2D: Governance + Other (3 files, ~27 emission sites)

| File | Function | Emission Sites | Uncoded Sites |
|---|---|---|---|
| `validation/governance.py` | `check_commit_message()` | 2 | 2 uncoded |
| `validation/canon_schema_alignment.py` | `lint_canon_schema_alignment()` | 5 | 0 |
| `generation/prompt_schema_sync.py` | `run_prompt_schema_sync()` | 21 (20 appends + 1 list-return) | 0 |

**governance.py** needs codes: `"Commit message mismatch..."` -> `E303 CI_GATE_VIOLATION` (already registered in ERROR_CODES)

**Test gate**: `pytest tests/unit/validation/ -k "governance" && pytest tests/unit/generation/ -k "prompt_schema"`

---

## Phase 3: SpecError Migration -- Canonical Package

### Batch 3A: Canonical Registry + Lint (3 files, ~60 emission sites)

| File | Function | Emission Sites | Uncoded Sites |
|---|---|---|---|
| `canonical/registry.py` | `CanonicalRegistry.validate_ref()`, `load()` | 16 | 0 |
| `canonical/lint.py` | `lint_canon_dir()`, `lint_manifest()` | 35 | 0 |
| `canonical/integrity.py` | `validate_canonical_integrity()` | 9 | 1 |

All three files already emit coded messages. Migration is mechanical.

**Test gate**: `pytest tests/unit/canonical/`

### Batch 3B: Canonical Autofix (1 file, ~12 emission sites)

**File**: `tools/specdev_tools/canonical/autofix.py`

This module is unique: it returns `dict[str, list[str]]` (keyed by file path), not `list[str]`. The strings are a mix of:
- E-coded errors: `f"E520 UNRESOLVED_INPUT {path} invalid_json ..."` (migration target)
- Informational changes: `f"{path} add {target_ref_field} from {source_field}"` (not errors)
- Deprecation warnings: `f"WARN {path} skipped autofix ..."` (not standard E/W coded)

**Migration approach**:
1. Return type changes to `dict[str, list[str | SpecError]]` during transition, then `dict[str, list[SpecError]]` at completion.
2. E-coded error strings -> `make_error("E520", ...)` calls
3. Informational/WARN strings need a decision: either assign a W-code (e.g., `W570 GRACEFUL_SKIP`) or keep as plain strings with a new informational SpecError variant.
4. CLI handler (`cli.py` lines ~347-392) that checks `change.startswith("E")` must be updated to check `isinstance(change, SpecError) and change.code.startswith("E")`.

**The `_has_errors()` helper** (line 222) currently does `item.startswith("E")` and must also be updated.

**Test gate**: `pytest tests/unit/canonical/ -k "autofix"`

---

## Phase 4: SpecError Integration -- validate.py (AUDIT-007/008)

**File**: `tools/specdev_tools/validation/validate.py`

This is the central orchestrator. Changes:

### 4A: Update `validate_file()` (lines 97-192)

1. Change return type to `list[SpecError]`
2. Replace all inline `f"E520 UNRESOLVED_INPUT ..."` strings with `make_error("E520", ...)`
3. Convert jsonschema errors (lines 154-164) to SpecError objects
4. Remove the `ensure_spec_errors()` adapters added in Batch 0C — at this point all producers return `list[SpecError]`
5. Quality lint and canonical integrity calls: at this point Phases 1-3 are done, so these return `list[SpecError]` too

### 4B: Update `validate_dir()` (lines 194-297)

1. Change return type to `list[SpecError]`
2. All linter/checker calls now return `list[SpecError]` (Phases 1-3 done)
3. Remove all `ensure_spec_errors()` adapters added in Batch 0C
4. The `check_traceability_closure` E/W filtering (line 256) becomes: `if not e.code.startswith("W")`

### 4C: Rewrite `_apply_we_promotion()` (lines 300-335)

This is the biggest win of the entire migration. Current implementation:
```python
# Current: regex-based, fragile
failures = [re.sub(r'\b' + re.escape(w_code) + r'\b', e_code, f, count=1) for f in failures]
```

New implementation with SpecError:
```python
def _apply_we_promotion(failures: list[SpecError]) -> list[SpecError]:
    cfg = get_config()
    if cfg.warnings_as_errors:
        codes_to_promote = set(PROMOTABLE_PAIRS.keys())
    elif cfg.promote_codes:
        codes_to_promote = set(cfg.promote_codes) & set(PROMOTABLE_PAIRS.keys())
    else:
        codes_to_promote = set()

    promoted: list[SpecError] = []
    for err in failures:
        if err.code in codes_to_promote:
            new_code = PROMOTABLE_PAIRS[err.code]
            promoted.append(SpecError(code=new_code, message=err.message, path=err.path))
        else:
            promoted.append(err)

    # Dedup by (code, message, path)
    seen: set[tuple[str, str, str | None]] = set()
    deduped: list[SpecError] = []
    for err in promoted:
        key = (err.code, err.message, err.path)
        if key not in seen:
            seen.add(key)
            deduped.append(err)

    # Drop W-codes when matching E-code exists (non-promotion mode)
    if not codes_to_promote:
        e_messages = {(PROMOTABLE_PAIRS.get(err.code, ""), err.message, err.path)
                      for err in deduped if err.code.startswith("E")}
        deduped = [err for err in deduped
                   if not (err.code.startswith("W") and
                           (PROMOTABLE_PAIRS.get(err.code, ""), err.message, err.path) in e_messages)]

    return deduped
```

This eliminates all regex operations, is testable by field comparison, and handles edge cases that the string regex approach cannot.

**Test gate**: `pytest tests/unit/validation/test_validate_deep.py tests/unit/validation/test_validate_integration.py tests/unit/validation/test_regression_bugs.py`

---

## Phase 5: --json Output on All Commands (AUDIT-025)

### 5A: Shared JSON Formatter

**New file**: `tools/specdev_tools/core/json_output.py`

```python
from __future__ import annotations
import json
from typing import Any
from .errors import SpecError

def format_errors_json(
    errors: list[SpecError],
    context: dict[str, Any] | None = None,
) -> str:
    """Format SpecError list as JSON for --json output."""
    output: list[dict[str, Any]] = []
    for err in errors:
        entry = {
            "code": err.code,
            "message": err.message,
            "severity": "warning" if err.code.startswith("W") else "error",
        }
        if err.path:
            entry["path"] = err.path
        output.append(entry)
    result: dict[str, Any] = {
        "status": "PASS" if not errors else ("WARN" if all(e.code.startswith("W") for e in errors) else "FAIL"),
        "error_count": sum(1 for e in errors if e.code.startswith("E")),
        "warning_count": sum(1 for e in errors if e.code.startswith("W")),
        "errors": output,
    }
    if context:
        result.update(context)
    return json.dumps(result, indent=2)
```

**Output Schema** (documented, not enforced by JSON Schema initially):
```json
{
  "status": "PASS | WARN | FAIL",
  "error_count": 0,
  "warning_count": 0,
  "errors": [
    {
      "code": "E590",
      "message": "CROSS_STEP_ID_NOT_FOUND fixture 'fix-login' target 'fr-missing' not found in 04_fr_list.json",
      "severity": "error",
      "path": "spec/08_fixtures.json"
    }
  ]
}
```

### 5B: Add --json Flag to Error-Returning Commands (18 commands)

These commands follow the `errs = linter(); _print_and_exit_if_errors(errs)` pattern and can be trivially extended:

| Batch | Commands | CLI Lines |
|---|---|---|
| 5B-1 | `validate-all`, `fixtures-lint`, `seed-lint`, `docs-lint` | 256-306 |
| 5B-2 | `prompt-sync`, `canonical-lint`, `canonical-integrity`, `spec-quality-lint` | 307-397 |
| 5B-3 | `hallucination-lint`, `dependency-order-lint`, `forward-replay-check` | 398-455 |
| 5B-4 | `governance-check`, `dag-lint`, `extraction-intent-check`, `canon-schema-alignment` | 456-788 |

**Change pattern per command**:
```python
# Before:
errs = lint_foo(...)
_print_and_exit_if_errors(errs)

# After:
errs = lint_foo(...)
if getattr(args, "json", False):
    print(format_errors_json(errs, context={"command": "foo", ...}))
    if _has_error_messages_from_spec_errors(errs):
        sys.exit(1)
else:
    _print_and_exit_if_errors([e.render() for e in errs])
```

Each command's parser gets: `parser.add_argument("--json", action="store_true", help="Output results as JSON")`

### 5C: Refactor Existing --json (2 commands)

`validate` (line 238-255) and `traceability-check` (line 418-435) already have `--json` but use ad-hoc formatting. Refactor to use the shared formatter from 5A.

### 5D: Handle Non-Error Commands (5 commands)

These commands produce structured output, not error lists. **Effort note**: `align` (currently in 5E) and `matrix`/`invariants-check` have non-trivial output structures that don't follow the simple error-list pattern. Budget extra time for these.

| Command | Current Output | JSON Approach |
|---|---|---|
| `matrix` | Already JSON | Add `--json` for consistency (wraps with status envelope) |
| `invariants-check` | Already JSON | Same |
| `ai-help` | Plain text | `--json` wraps in `{"command": "ai-help", "output": "..."}` |
| `changelog` | Plain text | `--json` outputs structured changelog data |
| `env-check` | Plain text | `--json` outputs config as structured object |

### 5E: Handle Complex Commands (2 commands)

| Command | Notes |
|---|---|
| `align` | Has 7 sub-actions (`status`, `diff`, `plan`, `apply`, `prompts`, `validate`, `report`). Each produces different output types. `--json` must be threaded through each action's handler. Budget 1+ session for this alone. |
| `prompt-context` | Currently prints markdown table. `--json` outputs the consumer list as array |

### 5F: Update `_print_and_exit_if_errors()` and `_is_warning_message()`

Once all commands use `list[SpecError]`, these helpers are simplified:

```python
def _is_warning(err: SpecError) -> bool:
    return err.code.startswith("W")

def _has_hard_errors(errs: list[SpecError]) -> bool:
    if _warnings_as_errors():
        return bool(errs)
    return any(not _is_warning(e) for e in errs)
```

The current regex-based `WARNING_CODE_RE` and `WARNING_CODE_PREFIXED_RE` patterns (cli.py lines 21-23) become dead code and are removed.

**Test gate**: `pytest tests/unit/test_cli.py tests/unit/test_cli_subcommands.py`

---

## Phase 6: Test Updates

Tests are updated **in lockstep with each phase**, not as a separate phase. This section documents the patterns.

### Pattern A: Direct Code Assertion (~235 sites across 34 files)

```python
# Before:
assert any("E590" in e for e in errors)

# After (still works with render()):
assert any(e.code == "E590" for e in errors)
# or, if testing via CLI/string output:
assert any("E590" in e for e in rendered_errors)
```

### Pattern B: Unstructured String Assertion (76 sites across 23 files)

```python
# Before:
assert any("Duplicate fixture_id" in e for e in errors)

# After:
assert any(e.code == "E520" and "Duplicate fixture_id" in e.message for e in errors)
```

### Pattern C: Mock Return Values (test_validate_deep.py)

The deep validation tests mock linters and inject `list[str]` return values. These must change to `list[SpecError]`:

```python
# Before:
patch("...lint_spec_quality", return_value=["W571 ASSUMPTION_VAGUE_QUANTIFIER ..."])

# After:
from specdev_tools.core.errors import make_error
patch("...lint_spec_quality", return_value=[make_error("W571", "ASSUMPTION_VAGUE_QUANTIFIER ...")])
```

### Pattern D: Error Code Coverage Test

**File**: `tests/unit/core/test_error_code_coverage.py`

- `test_all_emitted_codes_registered()` (line 45): scans source for `"[EW]\d{3}"` string patterns. After migration, these will be `make_error("E590", ...)` calls. The regex pattern needs updating to also match `make_error("E590"` patterns.

### Integration Test Files (not in original estimate)

The following integration test files also contain error-code assertions and must be updated:
- `tests/integration/test_step_16.py` (41 occurrences)
- `tests/integration/test_step_14.py` (5 occurrences)

### Estimated Test Changes Per Phase

| Phase | Test Files Affected | Assertion Changes |
|---|---|---|
| 0A-0D (Prerequisites) | ~3 | ~10 (new tests for helpers + linter_utils updates) |
| 1A-1E (Validators) | ~12 | ~90 (includes integration tests) |
| 2A-2D (Linters) | ~14 | ~70 |
| 3A-3B (Canonical + Autofix) | ~5 | ~25 |
| 4A-4C (validate.py) | ~5 | ~40 |
| 5A-5F (--json) | ~3 | ~15 (new tests) |
| **TOTAL** | **~34-38 files** | **~250-280 changes** |

---

## Risk Assessment

### What Could Break

1. **String comparison in tests**: Tests that do `assert errors == ["exact string"]` will fail. Mitigated by lockstep updates.
2. **External consumers of CLI output**: Any CI scripts that grep for specific error strings. Mitigated by `render()` producing identical output format during transition.
3. **_apply_we_promotion regex edge cases**: The new field-based promotion is strictly more correct, but may surface errors that were previously silently swallowed by regex mismatches. This is a feature, not a bug.
4. **import cycles**: `make_error` is in `core/errors.py`. All validators/linters already import from `core/` or `..core/`, so no new cycles.
5. **check_no_duplicates callers**: If any caller is missed during the Batch 0B migration, runtime type errors will occur. All 9 callers are listed explicitly above.
6. **canonical/autofix.py dict return type**: The unique `dict[str, list[str]]` return type requires careful handling since `ensure_spec_errors` expects flat lists.

### Rollback Strategy

Each batch is a self-contained PR:
- Batch can be reverted independently
- The adapters in Batch 0C (validate_file, validate_dir, _run_deep_validation) mean partially-migrated modules coexist with unmigrated ones
- `render()` output is identical to current string format, so CLI output is unchanged until Phase 5

### Backward Compatibility

- `SpecError.render()` produces the same `f"{code} {path} {message}"` format as current strings
- `--json` is opt-in; default output is unchanged
- `list[str]` return type is preserved at the CLI boundary until Phase 5 is complete

---

## Metrics

### Expected End State

| Metric | Before | After |
|---|---|---|
| Validators/linters returning `list[SpecError]` | 0/41 | 41/41 |
| Error emission sites with error codes | ~257/362 | 362/362 |
| CLI commands with `--json` | 2/25 | 25/25 |
| W-to-E promotion via regex | Yes (fragile) | No (field-based) |
| Test count | 997 | 997+ (new JSON output tests) |
| `SpecError`/`make_error` usage in production | 0 calls | ~362 calls |

---

## Batch Execution Order

All batches are numbered for sequential execution. Parallel groups are marked with `||`.

```
Phase 0 -- Prerequisites (ALL must complete before Phase 1-3):
  B0A: Add render_errors(), ensure_spec_errors() to core/errors.py
  B0B: Migrate linter_utils.py:check_no_duplicates() to accept list[SpecError]
       (BLOCKS all Phase 1 batches — 9 validators depend on this helper)
  B0C: Add ensure_spec_errors() adapters in validate.py:
       - _run_deep_validation() (line 434)
       - validate_file() (lines 169, 172-174, 176-183)
       - validate_dir() (lines 234, 238, 247, 254, 261, 280, 293)
       Also fix _run_deep_validation catch-all: add E521 code prefix (line 442)
  B0D: Assign error codes to all ~105 uncoded emission sites (document mapping)
  TEST GATE: pytest tests/ (997 pass, no regressions)

Phase 1 -- Validators (batches can run in parallel AFTER Phase 0 completes):
  B1A: step_01, step_02, step_02a, step_04, step_05 (12 sites)
  B1B: step_06, step_07, step_08, step_09, step_10 (44 sites)    || B1A
  B1C: step_11, step_12, step_13, step_13a, step_14 (39 sites)   || B1A, B1B
  B1D: step_15, step_16, step_16a, step_16b, step_16c (48 sites) || B1A-B1C
  B1E: step_03 (10 sites)                                         || B1A-B1D
  TEST GATE: pytest tests/unit/validation/validators/ (all pass)

Phase 2 -- Linters (batches can run in parallel AFTER Phase 0 completes):
  B2A: spec_quality_lint, hallucination_lint, fixtures_lint, seed_lint (38 sites)
  B2B: docs_lint, dag_lint, dependency_order_lint (11 sites)       || B2A
  B2C: forward_replay_check, traceability_closure, extraction_intent_check (18 sites) || B2A, B2B
  B2D: governance, canon_schema_alignment, prompt_schema_sync (27 sites) || B2A-B2C
  TEST GATE: pytest tests/unit/validation/linters/ tests/unit/generation/ (all pass)

Phase 3 -- Canonical (AFTER Phase 0 completes; can run parallel with Phase 1/2):
  B3A: canonical/registry.py, canonical/lint.py, canonical/integrity.py (60 sites)
  B3B: canonical/autofix.py (12 sites, unique dict return type)
  TEST GATE: pytest tests/unit/canonical/ (all pass)

Phase 4 -- Orchestrator (depends on Phases 1-3 ALL complete):
  B4A: validate.py validate_file() return type change + remove adapters
  B4B: validate.py validate_dir() return type change + remove adapters
  B4C: validate.py _apply_we_promotion() rewrite (regex -> field-based)
  TEST GATE: pytest tests/unit/validation/test_validate_deep.py
             pytest tests/unit/validation/test_validate_integration.py
             pytest tests/unit/validation/test_regression_bugs.py (all pass)

Phase 5 -- JSON Output (depends on Phase 4):
  B5A: Create core/json_output.py shared formatter
  B5B-1: Add --json to validate-all, fixtures-lint, seed-lint, docs-lint
  B5B-2: Add --json to prompt-sync, canonical-lint, canonical-integrity, spec-quality-lint
  B5B-3: Add --json to hallucination-lint, dependency-order-lint, forward-replay-check
  B5B-4: Add --json to governance-check, dag-lint, extraction-intent-check, canon-schema-alignment
  B5C: Refactor existing --json on validate + traceability-check
  B5D: Add --json to matrix, invariants-check, ai-help, changelog, env-check
       (Note: matrix/invariants-check have non-trivial structured output — budget extra time)
  B5E: Add --json to align (7 sub-actions), prompt-context
       (Note: align is the most complex — budget 1+ session for this alone)
  B5F: Remove legacy regex helpers from cli.py
  TEST GATE: pytest tests/unit/test_cli.py tests/unit/test_cli_subcommands.py (all pass)

Final gate:
  pytest tests/ (997+ pass, all green)
```

### Time Estimates

| Phase | Batches | Est. Effort | Key Risk |
|---|---|---|---|
| P0: Prerequisites | 4 | 1-2 sessions | Medium -- check_no_duplicates migration must be correct for 9 callers |
| Phase 1: Validators | 5 | 2-3 sessions | Medium -- many test updates (including integration tests) |
| Phase 2: Linters | 4 | 2 sessions | Medium -- uncoded sites need code assignment |
| Phase 3: Canonical + Autofix | 2 | 1-2 sessions | Medium -- autofix has unique dict return type |
| Phase 4: Orchestrator | 3 | 1-2 sessions | High -- central integration point |
| Phase 5: JSON Output | 8 | 3-4 sessions | Medium -- align command has 7 sub-actions; matrix/invariants non-trivial |
| **TOTAL** | **26 batches** | **10-15 sessions** | |

### Success Criteria

1. All 41 error-producing modules return `list[SpecError]` (or `dict[str, list[SpecError]]` for autofix)
2. All ~362 error emission sites use `make_error()` with a registered code
3. All 25 CLI commands support `--json` flag
4. `_apply_we_promotion()` uses field-based code swapping (no regex)
5. Test count >= 997, all passing
6. `render()` output matches previous string format (no user-visible change in default mode)
