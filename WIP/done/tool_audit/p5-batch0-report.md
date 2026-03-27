# P5 Batch 0 Execution Report

**Date:** 2026-03-18
**Status:** PASS
**Test gate:** 830/830 tests passing (36.28s)

---

## FIX-001: core/loaders.py — PASS

**File:** `tools/specdev_tools/core/loaders.py`
**LOC:** ~200 (estimated 180)

### Functions created:
1. **`load_upstream_ids(toolkit_root, step_prefix, array_key, id_field, *, fallback_keys=())`** — Returns `Optional[set[str]]`; `None` when no upstream file found (preserves W590 caller pattern). Scans `spec/` for `{step_prefix}_*.json`.
2. **`load_sibling_artifact(artifact_path, sibling_prefix, array_key, id_field, *, fallback_root=None)`** — Returns `set[str]`; checks sibling directory first, falls back to `fallback_root/spec/`. Matches step_14 dual-path pattern.
3. **`check_cross_step_refs(targets, upstream_map, errors, code_prefix="")`** — In-place error appender for the upstream_map + W590/E590 pattern (step_08, step_12, step_13a).
4. **`KEBAB_ID_RE`** — Compiled `^[a-z0-9]+(?:-[a-z0-9]+)*$` regex.
5. **`kebab_id_re(prefix)`** — Factory returning `^{prefix}-[a-z0-9]+(?:-[a-z0-9]+)*$`.
6. **`load_json_artifact(path)`** — Returns `dict`; empty dict on missing file, propagates `json.JSONDecodeError`.

### Patterns extracted from:
- `step_05.py::_load_fr_ids` (AUDIT-002)
- `step_08.py::_load_fr_ids, _load_api_ids, _load_inv_ids, _load_nfr_ids` (AUDIT-002/003/016/018)
- `step_14.py::_load_step04_fr_ids, _load_step01_cap_ids` (AUDIT-017)
- `validate.py::_load_json_artifact` (AUDIT-019)
- 8+ copies of kebab regex (AUDIT-045)

---

## FIX-002: validation/linter_utils.py — PASS

**File:** `tools/specdev_tools/validation/linter_utils.py`
**LOC:** ~175 (estimated 150)

### Functions/constants created:
1. **`DERIVATION_STOPWORDS`** — `frozenset[str]` (24 words), aligned with `hallucination_lint._DERIVATION_STOPWORDS`.
2. **`CONTENT_STOPWORDS`** — `frozenset[str]` (24 words), aligned with `forward_replay_check._CONTENT_STOPWORDS`.
3. **`tokenize_free_text(text, *, stopwords=None)`** — Returns `set[str]` of 4+ char tokens, excluding stopwords. Replaces `hallucination_lint._tokenize` and `forward_replay_check._extract_content_tokens` inner logic.
4. **`iter_json(spec_dir)`** — `Iterator[str]` yielding all `.json` paths. Replaces duplicate `_iter_json` in hallucination_lint and spec_quality_lint.
5. **`collect_ids_and_refs(obj, rel, ids, refs, path="")`** — Replaces duplicate `_collect_ids_and_refs` in hallucination_lint and spec_quality_lint (AUDIT-012). Includes the `"requires"` list handling from hallucination_lint.
6. **`is_reference_context(path)`** — Replaces `_in_ref_context` (hallucination_lint) and `_is_reference_context` (spec_quality_lint). Unified to handle both normalization styles.
7. **`check_no_duplicates(items, id_field, label, errors, *, code="")`** — Generic duplicate-ID detector replacing 11 independent patterns (AUDIT-041).

### Patterns extracted from:
- `hallucination_lint.py::_collect_ids_and_refs, _in_ref_context, _iter_json, _DERIVATION_STOPWORDS, _tokenize` (AUDIT-012/040)
- `spec_quality_lint.py::_collect_ids_and_refs, _is_reference_context, _iter_json` (AUDIT-012)
- `forward_replay_check.py::_CONTENT_STOPWORDS` (AUDIT-040)

---

## FIX-003: core/config.py — PASS

**File:** `tools/specdev_tools/core/config.py`
**LOC:** ~100 (estimated 60)

### Classes/functions created:
1. **`SpecdevConfig`** — Typed, read-only class with `__slots__` for all 7 SPECDEV_* env vars:
   - `warnings_as_errors: bool` (SPECDEV_WARNINGS_AS_ERRORS)
   - `promote_codes: set[str]` (SPECDEV_PROMOTE_CODES, comma-parsed)
   - `matrix_strict: bool` (SPECDEV_MATRIX_STRICT)
   - `replay_base_ref: str | None` (SPECDEV_REPLAY_BASE_REF)
   - `replay_diff_error_mode: str` (SPECDEV_REPLAY_DIFF_ERROR_MODE)
   - `staleness_threshold: int` (SPECDEV_STALENESS_THRESHOLD, default 3)
2. **`get_config()`** — Thread-safe singleton factory. Reads env vars on first call only.
3. **`reset_config()`** — Clears cached singleton (for test isolation).
4. **`_parse_bool(key)`** — Boolean env var parser (`"1"`, `"true"`, `"yes"` → True).
5. **`_parse_set(key)`** — Comma-separated env var parser → `set[str]`.

### Patterns extracted from:
- `cli.py` lines 18, 233, 705-706 (AUDIT-036)
- `validate.py` lines 238, 269-270, 484 (AUDIT-036)
- `forward_replay_check.py` line 86 (AUDIT-036)

---

## Batch Gate

```
============================= 830 passed in 36.28s =============================
```

**Import verification:** All three modules import cleanly and basic functionality confirmed:
- `KEBAB_ID_RE.match("hello-world")` → True
- `tokenize_free_text("This is a test description with some words")` → `{'description', 'words', 'test'}`
- `is_reference_context("trace.id")` → True
- `get_config()` → `SpecdevConfig(warnings_as_errors=False, ...)`

---

## Next: Batch 1

Batch 1 tasks (FIX-004 through FIX-016) can now proceed — they import from these three foundation modules to replace inline duplicates in individual validator/linter files.
