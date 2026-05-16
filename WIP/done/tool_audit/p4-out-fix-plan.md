> **ARCHIVE NOTE (2026-05-16):** Canonical trace_matrix path is now `spec/extras/trace_matrix.json`. The `tools/trace_matrix.json` references below reflect the state at the time of writing.

# P4: Fix Plan

## Summary
- Total tasks: 52
- Batches: 7 (Batch 0–6)
- Max parallel agents per batch: 15 (Batch 1), 10 (Batch 5)
- Findings covered: 70 of 70 (CRITICAL: 1, HIGH: 13, MEDIUM: 30, LOW: 16, INFO: 10)
- Estimated LOC delta: ~+1,800 / ~-680 / net ~+1,120 (summed from individual task estimates)
- Research alignment items folded in: ALIGN-3 (partial), ALIGN-7 (partial), ALIGN-9 (partial)

## Dependency Graph

```
Batch 0: Foundation (shared modules)
    |
    v
Batch 1: Consumer DRY Fixes (highly parallel — each touches different file)
    |
    v
Batch 2: Error System + Format Fixes
    |
    v
Batch 3: Structure + Cleanup (large refactors)
    |
    v
Batch 4: Test Reorganization
    |
    v
Batch 5: New Tests (highly parallel — new files only)
    |
    v
Batch 6: CI + Docs + Research
```

---

## Batch 0: Foundation (Shared Modules — Must Complete First)

These tasks CREATE new shared modules that later batches import from.

### FIX-001: Create core/loaders.py — Shared Upstream ID Loaders

- **Batch:** 0
- **Audit ref:** AUDIT-002, AUDIT-003, AUDIT-015, AUDIT-016, AUDIT-017, AUDIT-018, AUDIT-019, AUDIT-030, AUDIT-045
- **Target file:** tools/specdev_tools/core/loaders.py
- **Change type:** CREATE
- **Dependencies:** none
- **Description:** Create a new shared module with these functions:
  1. `load_upstream_ids(toolkit_root: Path, step_prefix: str, array_key: str, id_field: str, *, fallback_keys: tuple[str,...] = ()) -> Optional[set[str]]` — Replaces all 6 `_load_fr_ids` copies (AUDIT-002), all 5 `_load_api_ids` copies (AUDIT-003), 2 `_load_capability_ids` copies (AUDIT-015), 2 `_load_nfr_ids` copies (AUDIT-016), and 1 `_load_inv_ids` copy in step_08 (AUDIT-018). Scans `spec/` for `{step_prefix}_*.json`, loads JSON, extracts `id_field` from `array_key` array, with optional fallback key search. **MUST preserve `None` return for missing upstream files — W590 depends on this.** Returns `None` if no source file is found; returns `set[str]` (possibly empty) if the file exists. Callers keep their `if ids is None: errors.append(W590...)` pattern.
  2. `load_sibling_artifact(artifact_path: Path, sibling_prefix: str, array_key: str, id_field: str, *, fallback_root: Path | None = None) -> set[str]` — Replaces the 4 loaders in step_14 that take `(toolkit_root, artifact_path)` (AUDIT-017). Resolves sibling files relative to artifact_path. **Note:** step_14's loaders check BOTH the artifact_path sibling AND `toolkit_root/spec/` as a fallback. The `fallback_root` parameter supports this: when set, if the sibling path does not exist, the function also checks `fallback_root/spec/{sibling_prefix}_*.json`.
  3. `check_cross_step_refs(targets: list[str], upstream_map: dict[str, set[str]], errors: list[str], code_prefix: str) -> None` — Replaces 3 copies of the upstream_map + W590/E590 pattern (AUDIT-018).
  4. `KEBAB_ID_RE` compiled regex and `kebab_id_re(prefix: str) -> re.Pattern` factory — Replaces 8 copies of `re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")` (AUDIT-045). The factory returns `re.compile(rf"^{prefix}-[a-z0-9]+(?:-[a-z0-9]+)*$")`.
  5. `load_json_artifact(path: Path) -> dict` — Shared JSON loading with error handling. Replaces `_load_json_artifact` in validate.py (AUDIT-019).
  All step file prefixes are parameters, not hardcoded (AUDIT-030).
  **Error handling contract:** For `load_upstream_ids`: on file-not-found, return `None` (preserves W590 caller pattern). For `load_sibling_artifact` and `load_json_artifact`: on file-not-found, return empty set / empty dict respectively. On malformed JSON (parse error), raise `json.JSONDecodeError` (let caller handle). On permission error, propagate the exception.
- **Test gate:** pytest tests/ -x --tb=short (no dedicated test file yet — full suite verifies no import errors; dedicated tests created in Batch 5 at tests/unit/core/test_loaders.py)
- **Estimated LOC:** +180 / -0 / net +180

### FIX-002: Create validation/linter_utils.py — Shared Linter Helpers

- **Batch:** 0
- **Audit ref:** AUDIT-012, AUDIT-040, AUDIT-041
- **Target file:** tools/specdev_tools/validation/linter_utils.py
- **Change type:** CREATE
- **Dependencies:** none
- **Description:** Create a new shared module with these functions:
  1. `collect_ids_and_refs(data: dict, ...) -> tuple[set[str], set[str]]` — Replaces duplicate `_collect_ids_and_refs` in hallucination_lint.py and spec_quality_lint.py (AUDIT-012, ~40 LOC each).
  2. `iter_json(data, path="") -> Iterator[tuple[str, Any]]` — Replaces duplicate `_iter_json` helper (AUDIT-012).
  3. `is_reference_context(key: str, parent_key: str) -> bool` — Replaces duplicate `_is_reference_context`/`_in_ref_context` (AUDIT-012).
  4. `DERIVATION_STOPWORDS: frozenset[str]` and `CONTENT_STOPWORDS: frozenset[str]` — Shared 24-word sets replacing duplicates in hallucination_lint.py:294-300 and forward_replay_check.py:329-335 (AUDIT-040).
  5. `tokenize_free_text(text: str) -> list[str]` — Replaces 3 copies of free-text tokenizer (~50 LOC) (AUDIT-040).
  6. `check_no_duplicates(items: list[dict], id_field: str, label: str, errors: list[str], *, code: str = "") -> None` — Replaces 11 independent duplicate-ID detection patterns (AUDIT-041).
- **Test gate:** pytest tests/ -x --tb=short (no dedicated test file yet — full suite verifies no import errors; dedicated tests created in Batch 5 at tests/unit/validation/linters/test_linter_utils.py)
- **Estimated LOC:** +150 / -0 / net +150

### FIX-003: Create core/config.py — Centralized Env Var Config

- **Batch:** 0
- **Audit ref:** AUDIT-036
- **Target file:** tools/specdev_tools/core/config.py
- **Change type:** CREATE
- **Dependencies:** none
- **Description:** Create a centralized configuration module:
  1. `class SpecdevConfig` with typed properties for all 7 SPECDEV_* env vars:
     - `warnings_as_errors: bool` (from SPECDEV_WARNINGS_AS_ERRORS)
     - `promote_codes: set[str]` (from SPECDEV_PROMOTE_CODES, parsed to set)
     - `matrix_strict: bool` (from SPECDEV_MATRIX_STRICT)
     - `replay_base_ref: str | None` (from SPECDEV_REPLAY_BASE_REF)
     - `replay_diff_error_mode: str` (from SPECDEV_REPLAY_DIFF_ERROR_MODE)
     - `staleness_threshold: int` (from SPECDEV_STALENESS_THRESHOLD, default 3)
  2. `get_config() -> SpecdevConfig` — Singleton factory. Reads env vars once, caches.
  3. Boolean parsing: `os.environ.get(key, "").strip().lower() in ("1", "true", "yes")`.
  Replaces 12 call sites across cli.py, validate.py, forward_replay_check.py.
- **Test gate:** pytest tests/ -x --tb=short (no dedicated test file yet — full suite verifies no import errors; dedicated tests created in Batch 5 at tests/unit/core/test_config.py)
- **Estimated LOC:** +60 / -0 / net +60

**[Batch 0 Gate]:** `source devspec_env/bin/activate && pytest tests/ -x --tb=short` — Expected: 830 tests passing (no consumers yet, only new modules created).

---

## Batch 1: Consumer DRY Fixes (Highly Parallel)

Each task modifies ONE existing file to import from the new shared modules (Batch 0). All tasks in each parallel set touch DIFFERENT files and can run simultaneously.

### Parallel Set 1A: Validator DRY Fixes (FR/API loaders + regex)

### FIX-004: step_05.py — Replace _load_fr_ids, _load_api_ids, Fix E310 Registry Name

- **Batch:** 1 (Parallel Set 1A)
- **Audit ref:** AUDIT-002, AUDIT-003, AUDIT-039
- **Target file:** tools/specdev_tools/validation/validators/step_05.py
- **Change type:** MODIFY
- **Dependencies:** FIX-001
- **Description:**
  1. Replace `_load_fr_ids` (~20 LOC) with `from specdev_tools.core.loaders import load_upstream_ids` call: `load_upstream_ids(toolkit_root, "04", "functional_requirements", "fr_id")` (AUDIT-002).
  2. Replace `_load_api_ids` (~20 LOC) with `load_upstream_ids(toolkit_root, "05", "endpoints", "endpoint_id")` (AUDIT-003).
  3. Assign a NEW code **E311** for MISSING_ENUM_PROVENANCE in step_05.py (AUDIT-039). Do NOT rename E310 — it stays as PROMPT_SCHEMA_DRIFT in the registry (errors.py). FIX-017 does NOT need to change E310. Register E311 in step_05.py's local emission only; FIX-017 will add E311 to the global registry as part of its error code audit.
  4. Replace local kebab-case regex with `from specdev_tools.core.loaders import KEBAB_ID_RE` (AUDIT-045).
- **Test gate:** pytest tests/test_step_validators_core.py tests/test_step_05_route_fix.py tests/integration/test_step_05.py -x --tb=short
- **Estimated LOC:** +5 / -45 / net -40

### FIX-005: step_06.py — Replace _load_fr_ids, _load_api_ids, Kebab Regex

- **Batch:** 1 (Parallel Set 1A)
- **Audit ref:** AUDIT-002, AUDIT-003, AUDIT-045
- **Target file:** tools/specdev_tools/validation/validators/step_06.py
- **Change type:** MODIFY
- **Dependencies:** FIX-001
- **Description:**
  1. Replace `_load_fr_ids` with `load_upstream_ids(toolkit_root, "04", "functional_requirements", "fr_id")` (AUDIT-002).
  2. Replace `_load_api_ids` with `load_upstream_ids(toolkit_root, "05", "endpoints", "endpoint_id")` (AUDIT-003).
  3. Replace local kebab-case regex (lines 8-9) with import from `core.loaders` (AUDIT-045).
- **Test gate:** pytest tests/test_step_validators_03_10.py tests/integration/test_step_06.py -x --tb=short
- **Estimated LOC:** +4 / -42 / net -38

### FIX-006: step_07.py — Replace _load_fr_ids, Fix KNOWN_STAGES, Kebab Regex

- **Batch:** 1 (Parallel Set 1A)
- **Audit ref:** AUDIT-002, AUDIT-022, AUDIT-045
- **Target file:** tools/specdev_tools/validation/validators/step_07.py
- **Change type:** MODIFY
- **Dependencies:** FIX-001
- **Description:**
  1. Replace `_load_fr_ids` with shared loader (AUDIT-002).
  2. Replace hardcoded `KNOWN_STAGES = {"dev", "ci", "staging", "prod"}` (line 9) with loading from `canon/kinds/stage.json`. Add fallback to hardcoded set if file not found (AUDIT-022).
  3. Replace local kebab-case regex (line 10) with import from `core.loaders` (AUDIT-045).
- **Test gate:** pytest tests/test_step_07_deep.py tests/test_step_validators_03_10.py tests/integration/test_step_07.py -x --tb=short
- **Estimated LOC:** +10 / -25 / net -15

### FIX-007: step_08.py — Replace _load_fr_ids, _load_api_ids, _load_nfr_ids, _load_inv_ids, upstream_map, Kebab Regex

- **Batch:** 1 (Parallel Set 1A)
- **Audit ref:** AUDIT-002, AUDIT-003, AUDIT-016, AUDIT-018, AUDIT-045
- **Target file:** tools/specdev_tools/validation/validators/step_08.py
- **Change type:** MODIFY
- **Dependencies:** FIX-001
- **Description:**
  1. Replace `_load_fr_ids` with shared loader (AUDIT-002).
  2. Replace `_load_api_ids` with shared loader (AUDIT-003).
  3. Replace `_load_nfr_ids` (~20 LOC) with `load_upstream_ids(toolkit_root, "07", "nfrs", "nfr_id")` (AUDIT-016).
  4. Replace `_load_inv_ids` (~20 LOC) with `load_upstream_ids(toolkit_root, "06", "invariants", "inv_id")` (AUDIT-018). **Note:** step_08 has 4 loaders total — all 4 must be replaced.
  5. Replace upstream_map pattern (lines 41-56, ~15 LOC) with `check_cross_step_refs()` (AUDIT-018).
  6. Replace local kebab-case regex (lines 8-9) with import from `core.loaders` (AUDIT-045).
- **Test gate:** pytest tests/test_step_validators_03_10.py tests/integration/test_step_08.py -x --tb=short
- **Estimated LOC:** +6 / -75 / net -69

### FIX-008: step_12.py — Replace _load_fr_ids, _load_nfr_ids, upstream_map, Kebab Regex

- **Batch:** 1 (Parallel Set 1A)
- **Audit ref:** AUDIT-002, AUDIT-016, AUDIT-018, AUDIT-045
- **Target file:** tools/specdev_tools/validation/validators/step_12.py
- **Change type:** MODIFY
- **Dependencies:** FIX-001
- **Description:**
  1. Replace `_load_fr_ids` with shared loader (AUDIT-002).
  2. Replace `_load_nfr_ids` with shared loader (AUDIT-016).
  3. Replace upstream_map pattern (lines 42-55, ~13 LOC) with `check_cross_step_refs()` (AUDIT-018).
  4. Replace local kebab-case regex (lines 10-11) with import from `core.loaders` (AUDIT-045).
- **Test gate:** pytest tests/integration/test_step_12.py -x --tb=short
- **Estimated LOC:** +5 / -55 / net -50

### FIX-009: step_13a.py — Replace _load_fr_ids, _load_api_ids, upstream_map, Kebab Regex

- **Batch:** 1 (Parallel Set 1A)
- **Audit ref:** AUDIT-002, AUDIT-003, AUDIT-018, AUDIT-045
- **Target file:** tools/specdev_tools/validation/validators/step_13a.py
- **Change type:** MODIFY
- **Dependencies:** FIX-001
- **Description:**
  1. Replace `_load_fr_ids` with shared loader (AUDIT-002).
  2. Replace `_load_api_ids` with shared loader (AUDIT-003).
  3. Replace upstream_map pattern (lines 35-48, ~13 LOC) with `check_cross_step_refs()` (AUDIT-018).
  4. Replace local kebab-case regex (line 8) with import from `core.loaders` (AUDIT-045).
- **Test gate:** pytest tests/integration/test_step_13.py -x --tb=short
- **Estimated LOC:** +5 / -55 / net -50

### Parallel Set 1B: More Validator DRY Fixes

### FIX-010: step_15.py — Replace _load_api_ids

- **Batch:** 1 (Parallel Set 1B)
- **Audit ref:** AUDIT-003, AUDIT-045
- **Target file:** tools/specdev_tools/validation/validators/step_15.py
- **Change type:** MODIFY
- **Dependencies:** FIX-001
- **Description:**
  1. Replace `_load_api_ids` with `load_upstream_ids(toolkit_root, "05", "endpoints", "endpoint_id", fallback_keys=("contracts",))` (AUDIT-003). Note step_15's unique fallback key "contracts".
  2. Replace local kebab-case regex (line 44) with import from `core.loaders` (AUDIT-045).
- **Test gate:** pytest tests/integration/test_step_15.py -x --tb=short
- **Estimated LOC:** +3 / -22 / net -19

### FIX-011: step_11.py — Replace _load_api_ids

- **Batch:** 1 (Parallel Set 1B)
- **Audit ref:** AUDIT-003, AUDIT-051
- **Target file:** tools/specdev_tools/validation/validators/step_11.py
- **Change type:** MODIFY
- **Dependencies:** FIX-001
- **Description:**
  1. Replace `_load_api_ids` with `load_upstream_ids(toolkit_root, "05", "endpoints", "endpoint_id", fallback_keys=("endpoint_id",))` (AUDIT-003). Note step_11's unique fallback key.
  2. Move `warnings.warn()` at import time (lines 33-43) into the validate function body or behind a `_warned` module flag so it fires once per session, not at import (AUDIT-051).
- **Test gate:** pytest tests/test_step_11_deep.py tests/integration/test_step_11.py -x --tb=short
- **Estimated LOC:** +8 / -25 / net -17

### FIX-012: step_04.py — Replace _load_capability_ids, Kebab Regex

- **Batch:** 1 (Parallel Set 1B)
- **Audit ref:** AUDIT-015, AUDIT-045
- **Target file:** tools/specdev_tools/validation/validators/step_04.py
- **Change type:** MODIFY
- **Dependencies:** FIX-001
- **Description:**
  1. Replace `_load_capability_ids` (~20 LOC at line 63) with `load_upstream_ids(toolkit_root, "01", "capabilities", "capability_id")` (AUDIT-015).
  2. Replace local kebab-case regex (line 6) with import from `core.loaders` (AUDIT-045).
- **Test gate:** pytest tests/test_step_validators_core.py tests/integration/test_step_04.py -x --tb=short
- **Estimated LOC:** +3 / -22 / net -19

### FIX-013: step_09.py — Replace _load_capability_ids

- **Batch:** 1 (Parallel Set 1B)
- **Audit ref:** AUDIT-015
- **Target file:** tools/specdev_tools/validation/validators/step_09.py
- **Change type:** MODIFY
- **Dependencies:** FIX-001
- **Description:**
  1. Replace `_load_capability_ids` (~20 LOC at line 52) with `load_upstream_ids(toolkit_root, "01", "capabilities", "capability_id")` (AUDIT-015).
- **Test gate:** pytest tests/test_step_validators_03_10.py tests/integration/test_step_09.py -x --tb=short
- **Estimated LOC:** +3 / -20 / net -17

### FIX-014: step_14.py — Verify E141/E142 Usage, Replace Loaders, Kebab Regex

- **Batch:** 1 (Parallel Set 1C)
- **Audit ref:** AUDIT-001, AUDIT-017, AUDIT-045
- **Target file:** tools/specdev_tools/validation/validators/step_14.py
- **Change type:** MODIFY
- **Dependencies:** FIX-001, FIX-017 (E141/E142 must be registered in errors.py first)
- **Sequencing note:** Moved from Set 1B to Set 1C so FIX-017 (also in 1C) runs first or in parallel. The loader replacements in step_14.py do not depend on errors.py registration at runtime; the dependency is for verification only.
- **Description:**
  1. Verify E141 (line 126) and E142 (line 79) usage matches newly registered codes in errors.py (AUDIT-001, coordinated with FIX-017).
  2. Replace 4 loaders at lines 152, 184, 203, 228 (~100 LOC) with `load_sibling_artifact()` calls (AUDIT-017).
  3. Replace local kebab-case regex (lines 10-12) with import from `core.loaders` (AUDIT-045).
- **Test gate:** pytest tests/integration/test_step_14.py -x --tb=short
- **Estimated LOC:** +8 / -95 / net -87

### Parallel Set 1C: Linter + Remaining Validator Fixes

### FIX-015: step_13.py — Verify E320 Usage (MERGED INTO FIX-017)

- **Batch:** 1 (Parallel Set 1C)
- **Audit ref:** AUDIT-001
- **Status:** MERGED into FIX-017. This was a no-op verification task (net 0 LOC). FIX-017 now includes the E320 registration AND verification that step_13.py emissions at lines 32, 40, 51 match the newly registered code. No separate task needed.
- **Estimated LOC:** +0 / -0 / net 0

### FIX-016: step_01.py — Remove Duplicate Schema Validation, Fix Import-time Warning

- **Batch:** 1 (Parallel Set 1C)
- **Audit ref:** AUDIT-009, AUDIT-037, AUDIT-051
- **Target file:** tools/specdev_tools/validation/validators/step_01.py
- **Change type:** MODIFY
- **Dependencies:** none
- **Description:**
  1. Remove duplicate schema validation at lines 56-74 (SchemaRegistry creation, schema load, iter_errors call). validate.py already does this before calling deep validators (AUDIT-009).
  2. Remove hardcoded schema URI at line 57 — becomes unnecessary when schema validation is removed (AUDIT-037).
  3. Move `warnings.warn()` at lines 20-25 into the validate function body or behind a `_warned` flag (AUDIT-051).
- **Test gate:** pytest tests/test_step_validators_core.py tests/test_r9_validate.py tests/integration/test_step_01.py -x --tb=short
- **Estimated LOC:** +5 / -25 / net -20

### FIX-017: errors.py — Register E141, E142, E320, Fix W550, Fix E310

- **Batch:** 1 (Parallel Set 1C)
- **Audit ref:** AUDIT-001, AUDIT-038, AUDIT-039
- **Target file:** tools/specdev_tools/core/errors.py
- **Change type:** MODIFY
- **Dependencies:** none
- **Description:**
  1. Register E141, E142, E320 in `ERROR_CODES` dict (AUDIT-001). E141 and E142 are step_14 validation codes; E320 is step_13 validation code. Add entries like `"E141": "STEP14_FIELD_VALIDATION"`, `"E142": "STEP14_STRUCTURAL_ERROR"`, `"E320": "STEP13_EXTENSION_ERROR"` (choose names matching actual usage). After registration, verify step_13.py emissions at lines 32, 40, 51 match E320 (absorbed from FIX-015).
  2. Assign a new W-code (e.g., W551) for UNDECLARED_SEED used in seed_lint.py, since W550 is registered as SEMANTIC_COVERAGE_SKIP for forward_replay_check (AUDIT-038). Add `"W551": "UNDECLARED_SEED"` to ERROR_CODES and update PROMOTABLE_PAIRS if applicable.
  3. Rename E310 from "PROMPT_SCHEMA_DRIFT" to match its actual usage as "MISSING_ENUM_PROVENANCE" in step_05.py, OR register a new E311 code (AUDIT-039). Choose whichever is semantically clearest.
- **Test gate:** pytest tests/test_error_code_coverage.py tests/test_r9_error_codes.py -x --tb=short
- **Estimated LOC:** +12 / -2 / net +10

### FIX-018: step_02.py — Remove Duplicate Schema Validation

- **Batch:** 1 (Parallel Set 1C)
- **Audit ref:** AUDIT-009, AUDIT-037
- **Target file:** tools/specdev_tools/validation/validators/step_02.py
- **Change type:** MODIFY
- **Dependencies:** none
- **Description:**
  1. Remove duplicate schema validation at line 127+ (SchemaRegistry creation, schema load, iter_errors call). validate.py already does this (AUDIT-009).
  2. Remove hardcoded schema URI at line 127 (AUDIT-037).
- **Test gate:** pytest tests/integration/test_step_02.py -x --tb=short
- **Estimated LOC:** +0 / -20 / net -20

### FIX-019: hallucination_lint.py — Fix NFR Key Bug, Replace Duplicates, Fix KNOWN_STAGES, Fix allowed_pr_rules

- **Batch:** 1 (Parallel Set 1C)
- **Audit ref:** AUDIT-011, AUDIT-012, AUDIT-022, AUDIT-024, AUDIT-040
- **Target file:** tools/specdev_tools/validation/hallucination_lint.py
- **Change type:** MODIFY
- **Dependencies:** FIX-002
- **Description:**
  1. **BUG FIX** (AUDIT-011): At lines 277-278, change `n["id"]` to `n.get("nfr_id")` in `_load_nfr_ids`. The schema field is `nfr_id`, not `id`. This is a real bug causing silent false E530 errors.
  2. Replace `_collect_ids_and_refs` (lines 138-161), `_iter_json`, `_is_reference_context` with imports from `linter_utils` (AUDIT-012).
  3. Replace `KNOWN_STAGES = {"dev", "ci", "staging", "prod"}` (line 13) with loading from `canon/kinds/stage.json` with hardcoded fallback (AUDIT-022).
  4. Replace hardcoded `allowed_pr_rules` (lines 116-120, 14 values) with derivation from CLI subcommand list or extract to a shared constant in `core/` (AUDIT-024).
  5. Replace `_DERIVATION_STOPWORDS` and `_CONTENT_STOPWORDS` (lines 294-300) and free-text tokenizer with imports from `linter_utils` (AUDIT-040).
- **Test gate:** pytest tests/test_hallucination_lint.py tests/test_r9_hallucination.py -x --tb=short
- **Estimated LOC:** +15 / -80 / net -65

### FIX-020: spec_quality_lint.py — Replace Duplicates, Document Vague Words, Name Constants

- **Batch:** 1 (Parallel Set 1C)
- **Audit ref:** AUDIT-012, AUDIT-057, AUDIT-059
- **Target file:** tools/specdev_tools/validation/spec_quality_lint.py
- **Change type:** MODIFY
- **Dependencies:** FIX-002
- **Description:**
  1. Replace `_collect_ids_and_refs` (lines 215-232) and related helpers with imports from `linter_utils` (AUDIT-012).
  2. Add a comment above the vague quantifier word list (lines 14-18) documenting its purpose and noting it could be made configurable in future (AUDIT-057).
  3. Replace magic number `ASSUMPTION_THRESHOLD=10` at line 114 with module-level named constant `_ASSUMPTION_THRESHOLD = 10` with explanatory comment (AUDIT-059).
- **Test gate:** pytest tests/test_spec_quality_lint.py -x --tb=short
- **Estimated LOC:** +5 / -25 / net -20

### FIX-021: forward_replay_check.py — Replace Stopwords/Tokenizer, Use Config

- **Batch:** 1 (Parallel Set 1C)
- **Audit ref:** AUDIT-040, AUDIT-036
- **Target file:** tools/specdev_tools/validation/forward_replay_check.py
- **Change type:** MODIFY
- **Dependencies:** FIX-002, FIX-003
- **Description:**
  1. Replace `_DERIVATION_STOPWORDS`, `_CONTENT_STOPWORDS` (lines 329-335), and free-text tokenizer with imports from `linter_utils` (AUDIT-040).
  2. Replace direct `os.environ.get("SPECDEV_REPLAY_BASE_REF")` at line 86 with `get_config().replay_base_ref` (AUDIT-036).
- **Test gate:** pytest tests/test_forward_replay_check.py -x --tb=short
- **Estimated LOC:** +5 / -35 / net -30

### FIX-022: seed_lint.py — Fix W550 Code to W551

- **Batch:** 1 (Parallel Set 1C)
- **Audit ref:** AUDIT-038
- **Target file:** tools/specdev_tools/validation/seed_lint.py
- **Change type:** MODIFY
- **Dependencies:** FIX-017 (W551 must be registered)
- **Sequencing note:** FIX-017 must complete before FIX-022 executes, since the agent needs to know the exact code name W551. Both are in Set 1C but FIX-017 targets a different file (errors.py), so there is no file conflict -- just an ordering requirement.
- **Description:**
  1. Change W550 code at line 253 to W551 (the new UNDECLARED_SEED code registered in FIX-017) (AUDIT-038).
- **Test gate:** pytest tests/test_seed_strict_mode.py tests/test_seed_path_validation.py tests/test_seed_propagation_trim.py tests/test_seed_content_overlap.py -x --tb=short
- **Estimated LOC:** +1 / -1 / net 0

### Parallel Set 1D: step_16 Family

### FIX-023: step_16.py — Document CHECKLIST_TYPES/LAYERS, Address Triple Execution

- **Batch:** 1 (Parallel Set 1D)
- **Audit ref:** AUDIT-023, AUDIT-029
- **Target file:** tools/specdev_tools/validation/validators/step_16.py
- **Change type:** MODIFY
- **Dependencies:** none
- **Description:**
  1. Add comments above `VALID_CHECKLIST_TYPES` and `VALID_LAYERS` frozensets (lines 7-8) documenting they should ideally come from schema enum or canon/kinds/ (AUDIT-023). Mark as future migration candidate.
  2. Add a `_step16_cache` module-level dict to cache step_16 validation results by file hash. When step_16a/16b/16c call `validate_step_16()`, check cache first and return cached results if available (AUDIT-029). This prevents triple re-execution without changing the public API.
- **Test gate:** pytest tests/integration/test_step_16.py -x --tb=short
- **Estimated LOC:** +20 / -0 / net +20

### FIX-024: step_16a.py, step_16b.py, step_16c.py — No Changes Needed

- **Batch:** 1 (Parallel Set 1D)
- **Audit ref:** AUDIT-029
- **Target file:** tools/specdev_tools/validation/validators/step_16a.py (representative — also step_16b.py and step_16c.py)
- **Change type:** MODIFY (minimal)
- **Dependencies:** FIX-023
- **Description:**
  1. The triple-execution fix is handled by caching in step_16.py (FIX-023). These files need no modification unless the caching approach requires the callers to pass a cache dict. If so, add `_cache={}` default parameter to the `validate_step_16()` call (AUDIT-029).
  2. This task verifies that existing tests still pass after the step_16 cache change.
- **Test gate:** pytest tests/integration/test_step_16.py tests/test_validate_integration.py -k "step_16" -x --tb=short
- **Estimated LOC:** +3 / -0 / net +3

**[Batch 1 Gate]:** `source devspec_env/bin/activate && pytest tests/ -x --tb=short` — Expected: 830 tests passing.

---

## Batch 2: Error System + Format Fixes

### FIX-025: validate.py — Mega-Refactor (10 Findings)

- **Batch:** 2
- **Audit ref:** AUDIT-004, AUDIT-005, AUDIT-014, AUDIT-019, AUDIT-033, AUDIT-036, AUDIT-043, AUDIT-053, AUDIT-054
- **Target file:** tools/specdev_tools/validation/validate.py
- **Change type:** MODIFY
- **Dependencies:** FIX-001, FIX-003
- **Description:** This is the highest-density file with 9 findings (layer violation removal deferred to FIX-030). Apply sub-steps in the numbered order below. Dependencies between sub-steps are noted explicitly.

  **Phase A — Imports & Config (no interdependencies, apply first):**
  1. **Layer violation** (AUDIT-005): Mark the `from specdev_tools.generation.prompt_schema_sync import run_prompt_schema_sync` import at line 20 with a `# TODO: move to cli.py in FIX-030 (Batch 3)` comment. Do NOT remove the import or call here -- the actual removal happens in FIX-030 (Batch 3) simultaneously with adding it to cli.py, to avoid orphaning the functionality between batches.
  2. **Centralized config** (AUDIT-036): Replace all inline `os.environ.get("SPECDEV_*")` calls with `get_config().*` properties. Add `from specdev_tools.core.config import get_config` import. _(No dependencies within FIX-025.)_
  3. **Replace _load_* functions** (AUDIT-019): Replace `_load_json_artifact`, `_load_component_ids`, `_load_capability_ids`, `_load_nfrs_data`, `_load_monitoring_data` (lines 303-370, ~50 LOC) with imports from `core.loaders`. Note: validate.py's loaders take `(repo_root, file_path)` and resolve siblings — use `load_sibling_artifact` (with `fallback_root` parameter) for these, NOT `load_upstream_ids`. _(No dependencies within FIX-025.)_

  **Phase B — Logic changes (apply after Phase A):**
  4. **W->E promotion in validate_file** (AUDIT-014): Add W->E promotion logic to `validate_file()` (currently only in `validate_dir()` at lines 267-289). Use `get_config().warnings_as_errors` and `get_config().promote_codes` from FIX-003. _(Depends on sub-step 2 for config import.)_
  5. **Fragile string W->E promotion** (AUDIT-033): Improve string prefix replacement at lines 274-282 with a more robust approach — use regex `re.sub(r'\bW(\d{3})\b', ...)` with the PROMOTABLE_PAIRS map. This makes promotion independent of message position. _(Depends on sub-step 4 — both touch the W->E promotion code path.)_
  6. **Dedup ordering** (AUDIT-054): Replace `dict.fromkeys` dedup at line 284 with ordered set that preserves first occurrence while deduplicating. _(Independent of other Phase B steps.)_
  7. **Empty spec dir** (AUDIT-053): Add early exit at line 180 in `validate_dir()`: if `spec_dir` has no `.json` files, print info message and return empty results. _(Independent of other Phase B steps.)_

  **Phase C — Documentation (apply last, safe — no logic changes):**
  8. **DEEP_VALIDATORS hardcoding** (AUDIT-043): Add a comment documenting the DEEP_VALIDATORS dict (lines 376-402) and noting it should be auto-discovered in future. No structural change — auto-discovery is a larger refactor.
  9. **SoC documentation** (AUDIT-004): Add module-level docstring clarifying that validate.py is intentionally the central orchestrator and future work could split `validate_dir` into a separate `orchestrator.py`. No structural split in this task.
- **Test gate:** pytest tests/test_validate_integration.py tests/test_validate_submodule.py tests/test_r9_validate.py -x --tb=short
- **Estimated LOC:** +40 / -65 / net -25

### FIX-026: governance.py — Fix File Handle Leak

- **Batch:** 2
- **Audit ref:** AUDIT-050
- **Target file:** tools/specdev_tools/validation/governance.py
- **Change type:** MODIFY
- **Dependencies:** none
- **Description:**
  1. Replace `json.load(open(...))` at line 11 with `with open(...) as f: data = json.load(f)` (AUDIT-050).
- **Test gate:** pytest tests/ -k governance -x --tb=short
- **Estimated LOC:** +2 / -1 / net +1

### FIX-027: Create core/constants.py + Extract _STEP_TO_TEMPLATE from prompt_generator.py

- **Batch:** 2
- **Audit ref:** AUDIT-044
- **Target file:** tools/specdev_tools/core/constants.py (CREATE) + tools/specdev_tools/generation/prompt_generator.py (MODIFY)
- **Change type:** CREATE + MODIFY (dual-file exception: the new module and its first consumer must be created together)
- **Dependencies:** none
- **Description:**
  1. Create `core/constants.py` with the shared `STEP_TO_TEMPLATE` dict, either copied from prompt_generator.py lines 523-537 or derived from `step_order.json` entries (AUDIT-044).
  2. In `prompt_generator.py`, replace local `_STEP_TO_TEMPLATE` dict (lines 523-537) with `from specdev_tools.core.constants import STEP_TO_TEMPLATE`.
  Note: planner.py also has a copy — handled in FIX-028.
- **Test gate:** pytest tests/ -k "prompt_generator or prompt_gen" -x --tb=short
- **Estimated LOC:** +5 / -18 / net -13

### FIX-028: planner.py — Use Shared _STEP_TO_TEMPLATE

- **Batch:** 2
- **Audit ref:** AUDIT-044
- **Target file:** tools/specdev_tools/migration/planner.py
- **Change type:** MODIFY
- **Dependencies:** FIX-027
- **Description:**
  1. Replace local `_STEP_TO_TEMPLATE` dict (lines 38-57) with import from the shared location created in FIX-027 (AUDIT-044).
- **Test gate:** pytest tests/ -k planner -x --tb=short
- **Estimated LOC:** +2 / -22 / net -20

### FIX-029: schema_differ.py — Add Git Timeout, Scope git add

- **Batch:** 2
- **Audit ref:** AUDIT-066
- **Target file:** tools/specdev_tools/generation/schema_differ.py
- **Change type:** MODIFY
- **Dependencies:** none
- **Description:**
  1. Add `timeout=10` to all `subprocess.run()` git calls at lines 888, 970, 976, 983 (AUDIT-066).
  2. Change `git add -A` to `git add <specific_paths>` scoped to spec files only (AUDIT-066).
  3. Add module-level docstring noting this is the largest module (1331 LOC) and a future candidate for splitting into core/reports/apply (AUDIT-020, documented but not split in this batch).
- **Test gate:** pytest tests/ -k schema_differ -x --tb=short
- **Estimated LOC:** +8 / -4 / net +4

**[Batch 2 Gate]:** `source devspec_env/bin/activate && pytest tests/ -x --tb=short` — Expected: 830 tests passing.

---

## Batch 3: Structure + Cleanup

### FIX-030: cli.py — Derive STEP_NAMES, Add Exception Handler, Document SoC

- **Batch:** 3
- **Audit ref:** AUDIT-021, AUDIT-025, AUDIT-034, AUDIT-055, AUDIT-064, AUDIT-065
- **Target file:** tools/specdev_tools/cli.py
- **Change type:** MODIFY
- **Dependencies:** FIX-003, FIX-025
- **Secondary target:** tools/specdev_tools/validation/validate.py (remove prompt_schema_sync import + call)
- **Description:**
  0. **Complete layer violation fix** (AUDIT-005): Remove `from specdev_tools.generation.prompt_schema_sync import run_prompt_schema_sync` import and the call site from validate.py (deferred from FIX-025 to keep functionality intact between batches). Add the `run_prompt_schema_sync` dispatch to cli.py as a standalone subcommand step.
  1. **STEP_NAMES derivation** (AUDIT-021): Replace hardcoded 22-entry `STEP_NAMES` dict (lines 666-675) with derivation from `step_order.json`. Load `tools/step_order.json`, iterate entries, build dict.
  2. **Global exception handler** (AUDIT-055): Wrap `main()` dispatch in try/except that catches `Exception` and prints a clean error message (with `--verbose` flag for full traceback). Exit code 1.
  3. **JSON output foundation** (AUDIT-025, ALIGN-7 partial): Add a `--json` flag to the top-level parser. When set, wrap the output of validation commands in JSON format `{"command": "...", "errors": [...], "warnings": [...], "exit_code": N}`. Start with `validate` and `validate-all` (already partially supported), then `canonical-lint`, `seed-lint`, `docs-lint`. Other commands get JSON support documented as future work.
  4. **Config usage** (AUDIT-036): Replace remaining `os.environ.get("SPECDEV_*")` calls (lines 18, 233, 705, 706, 734, 736) with `get_config().*`.
  5. **SoC documentation** (AUDIT-064): Add module-level docstring noting the monolithic dispatch pattern and that a future refactor could split into command groups.
  6. **Logging documentation** (AUDIT-065): Add a TODO comment at module level noting that 118 print() calls should migrate to logging module in a future pass.
- **Test gate:** pytest tests/test_cli.py tests/test_r9_cli.py -x --tb=short
- **Estimated LOC:** +55 / -30 / net +25

### FIX-031: canonical/lint.py — Add Module Docstring

- **Batch:** 3
- **Audit ref:** AUDIT-035
- **Target file:** tools/specdev_tools/canonical/lint.py
- **Change type:** MODIFY
- **Dependencies:** none
- **Description:**
  1. Add module-level docstring clarifying the boundary between lint.py and integrity.py: "lint.py validates canon directory structure and file format. integrity.py validates spec artifacts against canonical registry. integrity.py calls lint_canon_dir() as a preflight check." (AUDIT-035).
- **Test gate:** pytest tests/test_canonical_lint.py -x --tb=short
- **Estimated LOC:** +8 / -0 / net +8

### FIX-032: canonical/integrity.py — Add Module Docstring

- **Batch:** 3
- **Audit ref:** AUDIT-035
- **Target file:** tools/specdev_tools/canonical/integrity.py
- **Change type:** MODIFY
- **Dependencies:** none
- **Description:**
  1. Add module-level docstring clarifying the coupling with lint.py: "integrity.py validates spec artifacts against the canonical registry. Calls lint_canon_dir() as preflight to ensure canon directory is valid before checking spec compliance." (AUDIT-035).
- **Test gate:** pytest tests/test_canonical_integrity.py -x --tb=short
- **Estimated LOC:** +8 / -0 / net +8

### FIX-033: Delete Orphaned Artifacts

- **Batch:** 3
- **Audit ref:** AUDIT-047, AUDIT-048, AUDIT-062
- **Target file:** tools/UNKNOWN.egg-info/ (DELETE), .gitignore (MODIFY)
- **Change type:** DELETE + MODIFY
- **Dependencies:** none
- **Description:**
  1. Delete `tools/UNKNOWN.egg-info/` directory (AUDIT-047).
  2. Delete `tools/context/` empty directory (AUDIT-062).
  3. Add `*.egg-info/` and `tools/trace_matrix.json` to `.gitignore` (AUDIT-047, AUDIT-048).
- **Test gate:** pytest tests/ -x --tb=short (full suite — deletions should not affect tests)
- **Estimated LOC:** N/A (non-code changes)

### FIX-034: validators/__init__.py — Document Re-export Strategy

- **Batch:** 3
- **Audit ref:** AUDIT-056
- **Target file:** tools/specdev_tools/validation/validators/__init__.py
- **Change type:** MODIFY
- **Dependencies:** none
- **Description:**
  1. Add comment explaining why only step_16a/16b/16c are re-exported: these are the sub-step validators that share a common base. All other validators are imported directly by validate.py's DEEP_VALIDATORS dict (AUDIT-056).
- **Test gate:** pytest tests/ -k "step_16" -x --tb=short
- **Estimated LOC:** +5 / -0 / net +5

### FIX-035: __init__.py — Add __version__

- **Batch:** 3
- **Audit ref:** AUDIT-006, AUDIT-061
- **Target file:** tools/specdev_tools/__init__.py
- **Change type:** MODIFY
- **Dependencies:** none
- **Description:**
  1. Add `__version__ = "0.4.0"` (or use `importlib.metadata.version("specdev-tools")`) (AUDIT-006).
  2. Add comment documenting the `_MOVED` dict's purpose and that it provides backward-compat lazy imports for 22-23 module names (AUDIT-061).
- **Test gate:** pytest tests/ -x --tb=short -q
- **Estimated LOC:** +5 / -0 / net +5

### FIX-036: pyproject.toml — Verify Version Consistency

- **Batch:** 3
- **Audit ref:** AUDIT-006
- **Target file:** tools/pyproject.toml
- **Change type:** MODIFY (if needed)
- **Dependencies:** none
- **Description:**
  1. Verify version is "0.4.0" (should already be correct per baseline). If any mismatch, update (AUDIT-006).
- **Test gate:** python -c "import tomllib; d=tomllib.load(open('tools/pyproject.toml','rb')); assert d['project']['version']=='0.4.0'"
- **Estimated LOC:** +0 / -0 / net 0

### FIX-037: tools/README.md — Update Version Reference

- **Batch:** 3
- **Audit ref:** AUDIT-006
- **Target file:** tools/README.md
- **Change type:** MODIFY
- **Dependencies:** none
- **Description:**
  1. Update version reference from "v3 Full" to "v0.4.0" or "v4" to match pyproject.toml (AUDIT-006).
- **Test gate:** N/A (documentation only)
- **Estimated LOC:** +1 / -1 / net 0

**[Batch 3 Gate]:** `source devspec_env/bin/activate && pytest tests/ -x --tb=short` — Expected: 830 tests passing.

---

## Batch 4: Test Reorganization

### FIX-038: Restructure tests/ to Mirror Source Package

- **Batch:** 4
- **Audit ref:** AUDIT-070
- **Target file:** tests/ (directory restructure)
- **Change type:** MOVE
- **Dependencies:** FIX-001 through FIX-037 (all prior batches must be stable)
- **Description:** Reorganize the flat `tests/` directory to mirror the source package structure. This is a multi-file MOVE operation (exception to one-file rule per P4 template Rule 4):
  1. Create directories:
     - `tests/unit/core/`
     - `tests/unit/validation/`
     - `tests/unit/validation/validators/`
     - `tests/unit/validation/linters/`
     - `tests/unit/canonical/`
     - `tests/unit/generation/`
     - `tests/unit/migration/`
  2. Move test files to matching subdirectories (using actual file names):
     - `test_error_code_coverage.py`, `test_r9_error_codes.py`, `test_errors_submodule.py`, `test_trace_types.py`, `test_registry_error_handling.py` + new `test_loaders.py`, `test_config.py` (from Batch 5) -> `tests/unit/core/`
     - `test_validate_integration.py`, `test_validate_submodule.py`, `test_r9_validate.py` -> `tests/unit/validation/`
     - `test_step_validators_core.py`, `test_step_validators_03_10.py`, `test_step_05_route_fix.py`, `test_step_07_deep.py`, `test_step_10_deep.py`, `test_step_11_deep.py`, `test_r9_cross_step.py` -> `tests/unit/validation/validators/`
     - `test_hallucination_lint.py`, `test_r9_hallucination.py`, `test_spec_quality_lint.py`, `test_r9_quality_lint.py`, `test_seed_strict_mode.py`, `test_seed_path_validation.py`, `test_seed_propagation_trim.py`, `test_seed_content_overlap.py`, `test_forward_replay_check.py`, `test_forward_replay_check_integration.py`, `test_forward_replay_submodule.py`, `test_r9_forward_replay.py`, `test_r9_matrix.py`, `test_r9_dag_lint.py`, `test_r9_extraction_intent.py`, `test_fixtures_lint.py`, `test_invariants.py`, `test_dependency_order_lint.py`, `test_traceability_closure.py`, `test_gap_remediation.py` + new `test_linter_utils.py` (from Batch 5) -> `tests/unit/validation/linters/`
     - `test_canonical_lint.py`, `test_canonical_integrity.py`, `test_canonical_integrity_drift.py`, `test_canonical_registry.py`, `test_canon_schema_alignment.py` -> `tests/unit/canonical/`
     - `test_prompt_schema_sync.py`, `test_prompt_contracts.py`, `test_schema_contracts.py` + new `test_schema_differ.py`, `test_prompt_generator.py` (from Batch 5) -> `tests/unit/generation/`
     - `test_migration_planner.py`, `test_migration_runner.py`, `test_migration_templates.py` -> `tests/unit/migration/`
     - `test_cli.py`, `test_r9_cli.py`, `test_cli_submodule_params.py`, `test_init_project_submodule.py` -> `tests/unit/` (top-level unit)
     Note: `test_loaders.py`, `test_linter_utils.py`, `test_config.py`, `test_schema_differ.py`, `test_prompt_generator.py`, `test_governance.py` do not yet exist at Batch 4 time; they are created in Batch 5 directly into their target directories.
  3. Create `__init__.py` in each new directory (empty, for pytest discovery).
  4. Do NOT create `tests/unit/conftest.py` -- pytest automatically propagates root conftest fixtures to all subdirectories. An intermediate conftest that re-imports would be redundant.
  5. Keep `tests/conftest.py` as root conftest (shared fixtures propagate automatically).
  6. Run `pytest --collect-only` to verify all tests are discovered in the new structure.
  7. Verify no test files use relative imports or `sys.path` manipulation that would break after moves. Check `pyproject.toml` testpaths if configured.
- **Test gate:** pytest tests/ -x --tb=short (full suite — must find and run all moved tests)
- **Estimated LOC:** N/A (file moves, no logic changes)

### FIX-039: Rename test_r9_* Files to Descriptive Names

- **Batch:** 4
- **Audit ref:** AUDIT-027
- **Target file:** tests/test_r9_*.py (10 files)
- **Change type:** RENAME
- **Dependencies:** FIX-038 (must complete directory restructure first)
- **Description:** Rename R9 test files to descriptive names that reflect their content. The actual 10 R9 files are:
  - `test_r9_cli.py` -> `test_cli_subcommands.py`
  - `test_r9_cross_step.py` -> `test_cross_step_validation.py`
  - `test_r9_dag_lint.py` -> `test_dag_lint_rules.py`
  - `test_r9_error_codes.py` -> `test_error_code_registry.py` (merge ~6 overlapping tests into existing `test_error_code_coverage.py`)
  - `test_r9_extraction_intent.py` -> `test_extraction_intent_rules.py`
  - `test_r9_forward_replay.py` -> `test_forward_replay_rules.py`
  - `test_r9_hallucination.py` -> `test_hallucination_lint_rules.py`
  - `test_r9_matrix.py` -> `test_matrix_rules.py`
  - `test_r9_quality_lint.py` -> `test_quality_lint_rules.py`
  - `test_r9_validate.py` -> `test_validate_deep.py`
  All renames happen within their new subdirectories from FIX-038.
- **Test gate:** pytest tests/ -x --tb=short (full suite — verify test count unchanged at 830+)
- **Estimated LOC:** N/A (renames only)

### FIX-040: Consolidate Conftest Fixtures

- **Batch:** 4
- **Audit ref:** AUDIT-028, AUDIT-049, AUDIT-069
- **Target file:** tests/conftest.py
- **Change type:** MODIFY
- **Dependencies:** FIX-038
- **Description:**
  1. Extract 5 shared fixtures into a helper function that takes `depth` parameter. Root conftest calls with depth=3, integration conftest calls with depth=4 (or however the path resolution works) (AUDIT-028).
  2. Check if `migration_prompts_root` fixture (lines 43-46) is used by any test. If unused, remove it (AUDIT-049).
  3. Add `scope="session"` to idempotent fixtures like `repo_root`, `schema_registry_path`, `toolkit_root` that don't change between tests (AUDIT-069).
- **Test gate:** pytest tests/ -x --tb=short
- **Estimated LOC:** +15 / -10 / net +5

### FIX-041: Update Integration Conftest

- **Batch:** 4
- **Audit ref:** AUDIT-028, AUDIT-069
- **Target file:** tests/integration/conftest.py
- **Change type:** MODIFY
- **Dependencies:** FIX-040
- **Description:**
  1. Remove duplicated fixture definitions, import shared fixtures from root conftest helper (AUDIT-028).
  2. Add `scope="session"` to idempotent fixtures (AUDIT-069).
- **Test gate:** pytest tests/integration/ -x --tb=short
- **Estimated LOC:** +5 / -20 / net -15

### FIX-042: test_step_11.py — Replace Live spec/ Reads With Fixtures

- **Batch:** 4
- **Audit ref:** AUDIT-010
- **Target file:** tests/integration/test_step_11.py
- **Change type:** MODIFY
- **Dependencies:** none
- **Description:**
  1. Replace `load_json_file` calls for 7 spec/ files (lines 58-94) with test fixtures from `tests/fixtures/` (AUDIT-010).
  2. Create minimal fixture files in `tests/fixtures/step_11/` if needed for the 6 missing spec files.
  3. Remove coupling to live spec/ directory state.
- **Test gate:** pytest tests/integration/test_step_11.py -x --tb=short
- **Estimated LOC:** +25 / -15 / net +10

**[Batch 4 Gate]:** `source devspec_env/bin/activate && pytest tests/ -x --tb=short` — Expected: 830 tests passing (same count, different structure).

---

## Batch 5: New Tests (Highly Parallel)

All tasks CREATE new test files — no conflicts possible.

### FIX-043: Create test_loaders.py

- **Batch:** 5
- **Audit ref:** AUDIT-002, AUDIT-003, AUDIT-015, AUDIT-016, AUDIT-017, AUDIT-018, AUDIT-030, AUDIT-045
- **Target file:** tests/unit/core/test_loaders.py
- **Change type:** CREATE
- **Dependencies:** FIX-001, FIX-038
- **Description:** Create comprehensive tests for `core/loaders.py`:
  1. Test `load_upstream_ids` with valid spec dir, missing files, empty arrays, multiple matching files.
  2. Test `load_sibling_artifact` with sibling resolution.
  3. Test `check_cross_step_refs` with matching/missing refs.
  4. Test `KEBAB_ID_RE` and `kebab_id_re()` factory with valid/invalid IDs.
  5. Test `load_json_artifact` with valid/invalid/missing files.
  Target: 20+ tests.
- **Test gate:** pytest tests/unit/core/test_loaders.py -x --tb=short
- **Estimated LOC:** +250 / -0 / net +250

### FIX-044: Create test_linter_utils.py

- **Batch:** 5
- **Audit ref:** AUDIT-012, AUDIT-040, AUDIT-041
- **Target file:** tests/unit/validation/linters/test_linter_utils.py
- **Change type:** CREATE
- **Dependencies:** FIX-002, FIX-038
- **Description:** Create tests for `validation/linter_utils.py`:
  1. Test `collect_ids_and_refs` with nested JSON structures.
  2. Test `iter_json` traversal.
  3. Test `is_reference_context` with various key patterns.
  4. Test `DERIVATION_STOPWORDS` and `CONTENT_STOPWORDS` are non-empty frozensets.
  5. Test `tokenize_free_text` with various inputs.
  6. Test `check_no_duplicates` with/without duplicates, with/without error codes.
  Target: 15+ tests.
- **Test gate:** pytest tests/unit/validation/linters/test_linter_utils.py -x --tb=short
- **Estimated LOC:** +180 / -0 / net +180

### FIX-045: Create test_config.py

- **Batch:** 5
- **Audit ref:** AUDIT-036
- **Target file:** tests/unit/core/test_config.py
- **Change type:** CREATE
- **Dependencies:** FIX-003, FIX-038
- **Description:** Create tests for `core/config.py`:
  1. Test `SpecdevConfig` with all env vars set, none set, partial.
  2. Test boolean parsing ("1", "true", "yes", "0", "false", "no", "").
  3. Test `promote_codes` parsing (comma-separated).
  4. Test `staleness_threshold` default and override.
  5. Test `get_config()` singleton behavior.
  Target: 12+ tests.
- **Test gate:** pytest tests/unit/core/test_config.py -x --tb=short
- **Estimated LOC:** +120 / -0 / net +120

### FIX-046: Create test_governance.py

- **Batch:** 5
- **Audit ref:** AUDIT-031
- **Target file:** tests/unit/validation/test_governance.py
- **Change type:** CREATE
- **Dependencies:** FIX-038
- **Description:** Create dedicated tests for `validation/governance.py`:
  1. Test `check_governance_commit_message` with valid messages matching patterns from step 10.
  2. Test with invalid/missing commit types, scopes, references.
  3. Test edge cases: empty string, very long messages, special characters.
  4. Test pr_rules validation if applicable.
  Target: 10+ tests.
- **Test gate:** pytest tests/unit/validation/test_governance.py -x --tb=short
- **Estimated LOC:** +100 / -0 / net +100

### FIX-047: Create test_schema_differ.py

- **Batch:** 5
- **Audit ref:** AUDIT-013, AUDIT-020
- **Target file:** tests/unit/generation/test_schema_differ.py
- **Change type:** CREATE
- **Dependencies:** FIX-038
- **Description:** Create tests for `generation/schema_differ.py` (1331 LOC, currently untested):
  1. Test diff computation between two schema versions.
  2. Test status/diff/plan report formatting.
  3. Test backup/restore operations (mock subprocess).
  4. Test edge cases: identical schemas, missing files, malformed JSON.
  Target: 15+ tests.
- **Test gate:** pytest tests/unit/generation/test_schema_differ.py -x --tb=short
- **Estimated LOC:** +200 / -0 / net +200

### FIX-048: Create test_prompt_generator.py

- **Batch:** 5
- **Audit ref:** AUDIT-013
- **Target file:** tests/unit/generation/test_prompt_generator.py
- **Change type:** CREATE
- **Dependencies:** FIX-038
- **Description:** Create tests for `generation/prompt_generator.py` (813 LOC, currently untested):
  1. Test prompt generation for various step types.
  2. Test template resolution.
  3. Test schema embedding in prompts.
  4. Test edge cases: missing schema, missing template.
  Target: 12+ tests.
- **Test gate:** pytest tests/unit/generation/test_prompt_generator.py -x --tb=short
- **Estimated LOC:** +160 / -0 / net +160

### FIX-049: Regression Tests for Bug Fixes

- **Batch:** 5
- **Audit ref:** AUDIT-001, AUDIT-011
- **Target file:** tests/unit/validation/test_regression_bugs.py
- **Change type:** CREATE
- **Dependencies:** FIX-017, FIX-019, FIX-038
- **Description:** Create regression tests that verify the specific bugs found in audit:
  1. Test that E141, E142, E320 are in ERROR_CODES registry (AUDIT-001 regression).
  2. Test that hallucination_lint `_load_nfr_ids` uses `nfr_id` field, not `id` (AUDIT-011 regression).
  3. Test that W550 is used only for SEMANTIC_COVERAGE_SKIP, not UNDECLARED_SEED (AUDIT-038 regression).
  4. Test that validate_file applies W->E promotion (AUDIT-014 regression).
  Target: 8+ tests.
- **Test gate:** pytest tests/unit/validation/test_regression_bugs.py -x --tb=short
- **Estimated LOC:** +100 / -0 / net +100

**[Batch 5 Gate]:** `source devspec_env/bin/activate && pytest tests/ -x --tb=short` — Expected: 830+ tests (new tests increase count).

---

## Batch 6: CI + Documentation + Research

### FIX-050: Add pytest Job to CI Workflow

- **Batch:** 6
- **Audit ref:** AUDIT-067
- **Target file:** .github/workflows/ci.yml
- **Change type:** MODIFY
- **Dependencies:** FIX-038 (test structure finalized)
- **Description:**
  1. Add a `test` job to the CI workflow that:
     - Sets up Python (matching existing CI Python version)
     - Installs dependencies from requirements.txt
     - Installs package in editable mode
     - Runs `pytest tests/ -v --tb=short`
  2. Add pytest markers configuration in `pyproject.toml` or `pytest.ini`: define `unit` and `integration` markers.
  3. The job should run on push and PR, same triggers as existing lint jobs.
- **Test gate:** act -j test (if `act` is available) OR validate YAML syntax: `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"`
- **Estimated LOC:** +25 / -0 / net +25

### FIX-051: Update CLAUDE.md — Version + Missing Commands

- **Batch:** 6
- **Audit ref:** AUDIT-006, AUDIT-034
- **Target file:** CLAUDE.md
- **Change type:** MODIFY
- **Dependencies:** none
- **Description:**
  1. Update version from "0.3.0" to "0.4.0" at line 9 (AUDIT-006).
  2. Add missing CLI subcommands to Core CLI Commands section (AUDIT-034): `canonical-autofix`, `prompt-context`, `canon-schema-alignment`, `prompt-sync`, `align validate`, `align rollback`. Verify against actual `cli.py` subcommands.
- **Test gate:** N/A (documentation only)
- **Estimated LOC:** +20 / -5 / net +15

### FIX-052: Create Research Alignment Roadmap

- **Batch:** 6
- **Audit ref:** ALIGN-1 through ALIGN-10
- **Target file:** WIP/future/research-alignment-roadmap.md
- **Change type:** CREATE
- **Dependencies:** none
- **Description:** Create the research alignment roadmap document covering all 10 ALIGN items. See separate file below for content.
- **Test gate:** N/A (documentation only)
- **Estimated LOC:** N/A (documentation)

**[Batch 6 Gate]:** `source devspec_env/bin/activate && pytest tests/ -v` — Expected: 830+ tests passing.

---

## Final Gate

```bash
source devspec_env/bin/activate && pytest tests/ -v
```

Expected: 900+ tests passing (830 baseline + ~70-80 new tests from Batch 5).

---

## AUDIT-to-FIX Mapping (Completeness Check)

| AUDIT | Severity | FIX | Batch |
|-------|----------|-----|-------|
| AUDIT-001 | CRITICAL | FIX-014, FIX-015, FIX-017 | 1 |
| AUDIT-002 | HIGH | FIX-001, FIX-004–009 | 0, 1 |
| AUDIT-003 | HIGH | FIX-001, FIX-004–007, FIX-009–011 | 0, 1 |
| AUDIT-004 | HIGH | FIX-025 | 2 |
| AUDIT-005 | HIGH | FIX-025 | 2 |
| AUDIT-006 | HIGH | FIX-035, FIX-036, FIX-037, FIX-051 | 3, 6 |
| AUDIT-007 | HIGH | FIX-025 (partial, documented as future SpecError migration) | 2 |
| AUDIT-008 | HIGH | FIX-017, FIX-025 (partial, documented as future error code standardization) | 1, 2 |
| AUDIT-009 | HIGH | FIX-016, FIX-018 | 1 |
| AUDIT-010 | HIGH | FIX-042 | 4 |
| AUDIT-011 | HIGH | FIX-019 | 1 |
| AUDIT-012 | HIGH | FIX-002, FIX-019, FIX-020 | 0, 1 |
| AUDIT-013 | HIGH | FIX-047, FIX-048 | 5 |
| AUDIT-014 | HIGH | FIX-025 | 2 |
| AUDIT-015 | MEDIUM | FIX-001, FIX-012, FIX-013 | 0, 1 |
| AUDIT-016 | MEDIUM | FIX-001, FIX-007, FIX-008 | 0, 1 |
| AUDIT-017 | MEDIUM | FIX-001, FIX-014 | 0, 1 |
| AUDIT-018 | MEDIUM | FIX-001, FIX-007–009 | 0, 1 |
| AUDIT-019 | MEDIUM | FIX-001, FIX-025 | 0, 2 |
| AUDIT-020 | MEDIUM | FIX-029 (documented, not split) | 2 |
| AUDIT-021 | MEDIUM | FIX-030 | 3 |
| AUDIT-022 | MEDIUM | FIX-006, FIX-019 | 1 |
| AUDIT-023 | MEDIUM | FIX-023 | 1 |
| AUDIT-024 | MEDIUM | FIX-019 | 1 |
| AUDIT-025 | MEDIUM | FIX-030 | 3 |
| AUDIT-026 | MEDIUM | FIX-025 (documented as future JSON path enhancement) | 2 |
| AUDIT-027 | MEDIUM | FIX-039 | 4 |
| AUDIT-028 | MEDIUM | FIX-040, FIX-041 | 4 |
| AUDIT-029 | MEDIUM | FIX-023, FIX-024 | 1 |
| AUDIT-030 | MEDIUM | FIX-001 (solved by parameterized loaders) | 0 |
| AUDIT-031 | MEDIUM | FIX-046 | 5 |
| AUDIT-032 | MEDIUM | Out of scope per user (json_utils.py left as-is) | — |
| AUDIT-033 | MEDIUM | FIX-025 | 2 |
| AUDIT-034 | MEDIUM | FIX-051 | 6 |
| AUDIT-035 | MEDIUM | FIX-031, FIX-032 | 3 |
| AUDIT-036 | MEDIUM | FIX-003, FIX-021, FIX-025, FIX-030 | 0, 1, 2, 3 |
| AUDIT-037 | MEDIUM | FIX-016, FIX-018 (subsumed by AUDIT-009 fix) | 1 |
| AUDIT-038 | MEDIUM | FIX-017, FIX-022 | 1 |
| AUDIT-039 | MEDIUM | FIX-004, FIX-017 | 1 |
| AUDIT-040 | MEDIUM | FIX-002, FIX-019, FIX-021 | 0, 1 |
| AUDIT-041 | MEDIUM | FIX-002 | 0 |
| AUDIT-042 | MEDIUM | FIX-052 (documented in roadmap as future schema audit) | 6 |
| AUDIT-043 | MEDIUM | FIX-025 | 2 |
| AUDIT-044 | MEDIUM | FIX-027, FIX-028 | 2 |
| AUDIT-045 | LOW | FIX-001, FIX-004–009, FIX-010, FIX-012, FIX-014 | 0, 1 |
| AUDIT-046 | LOW | FIX-052 (documented in roadmap as future standardization) | 6 |
| AUDIT-047 | LOW | FIX-033 | 3 |
| AUDIT-048 | LOW | FIX-033 | 3 |
| AUDIT-049 | LOW | FIX-040 | 4 |
| AUDIT-050 | LOW | FIX-026 | 2 |
| AUDIT-051 | LOW | FIX-011, FIX-016 | 1 |
| AUDIT-052 | LOW | No action (acceptable as-is per finding) | — |
| AUDIT-053 | LOW | FIX-025 | 2 |
| AUDIT-054 | LOW | FIX-025 | 2 |
| AUDIT-055 | LOW | FIX-030 | 3 |
| AUDIT-056 | LOW | FIX-034 | 3 |
| AUDIT-057 | LOW | FIX-020 | 1 |
| AUDIT-058 | LOW | FIX-052 (documented in roadmap) | 6 |
| AUDIT-059 | LOW | FIX-020 | 1 |
| AUDIT-060 | LOW | FIX-052 (documented in roadmap as future audit) | 6 |
| AUDIT-061 | INFO | FIX-035 | 3 |
| AUDIT-062 | INFO | FIX-033 | 3 |
| AUDIT-063 | INFO | FIX-025 (documented, intentional design) | 2 |
| AUDIT-064 | INFO | FIX-030 | 3 |
| AUDIT-065 | INFO | FIX-030 | 3 |
| AUDIT-066 | INFO | FIX-029 | 2 |
| AUDIT-067 | INFO | FIX-050 | 6 |
| AUDIT-068 | INFO | FIX-052 (documented in roadmap) | 6 |
| AUDIT-069 | INFO | FIX-040, FIX-041 | 4 |
| AUDIT-070 | INFO | FIX-038 | 4 |

**Coverage: 70 of 70 findings mapped.** AUDIT-032 (json_utils.py) excluded per user instruction. AUDIT-052 (no step_00 validator) accepted as-is.

---

## Conflict Matrix

Verify: no two tasks within the same batch+parallel-set share a target file.

### Batch 0 (all CREATE — no conflicts)
| FIX | Target File |
|-----|-------------|
| FIX-001 | core/loaders.py (CREATE) |
| FIX-002 | validation/linter_utils.py (CREATE) |
| FIX-003 | core/config.py (CREATE) |

### Batch 1 Parallel Set 1A (all different files)
| FIX | Target File |
|-----|-------------|
| FIX-004 | validators/step_05.py |
| FIX-005 | validators/step_06.py |
| FIX-006 | validators/step_07.py |
| FIX-007 | validators/step_08.py |
| FIX-008 | validators/step_12.py |
| FIX-009 | validators/step_13a.py |

### Batch 1 Parallel Set 1B (all different files)
| FIX | Target File |
|-----|-------------|
| FIX-010 | validators/step_15.py |
| FIX-011 | validators/step_11.py |
| FIX-012 | validators/step_04.py |
| FIX-013 | validators/step_09.py |

### Batch 1 Parallel Set 1C (all different files — FIX-017 should run first or in parallel; FIX-014, FIX-015, FIX-022 verify its results)
| FIX | Target File |
|-----|-------------|
| FIX-014 | validators/step_14.py |
| FIX-015 | validators/step_13.py |
| FIX-016 | validators/step_01.py |
| FIX-017 | core/errors.py |
| FIX-018 | validators/step_02.py |
| FIX-019 | hallucination_lint.py |
| FIX-020 | spec_quality_lint.py |
| FIX-021 | forward_replay_check.py |
| FIX-022 | seed_lint.py |

### Batch 1 Set 1D (sequential — FIX-024 depends on FIX-023)
| FIX | Target File | Order |
|-----|-------------|-------|
| FIX-023 | validators/step_16.py | FIRST |
| FIX-024 | validators/step_16a.py + step_16b.py + step_16c.py | AFTER FIX-023 |

### Batch 2 (all different files)
| FIX | Target File |
|-----|-------------|
| FIX-025 | validation/validate.py |
| FIX-026 | validation/governance.py |
| FIX-027 | generation/prompt_generator.py |
| FIX-028 | migration/planner.py |
| FIX-029 | generation/schema_differ.py |

**Note:** FIX-028 depends on FIX-027 (shared constant must exist first). Run FIX-027 before FIX-028. All others in Batch 2 are parallel.

### Batch 3 (all different files)
| FIX | Target File |
|-----|-------------|
| FIX-030 | cli.py |
| FIX-031 | canonical/lint.py |
| FIX-032 | canonical/integrity.py |
| FIX-033 | UNKNOWN.egg-info/ + context/ + .gitignore |
| FIX-034 | validators/__init__.py |
| FIX-035 | __init__.py |
| FIX-036 | pyproject.toml |
| FIX-037 | tools/README.md |

### Batch 4 (sequential — directory restructure)
| FIX | Target File |
|-----|-------------|
| FIX-038 | tests/ (directory restructure) — FIRST |
| FIX-039 | tests/test_r9_*.py (renames) — after FIX-038 |
| FIX-040 | tests/conftest.py — after FIX-038 |
| FIX-041 | tests/integration/conftest.py — after FIX-040 |
| FIX-042 | tests/integration/test_step_11.py — parallel with FIX-039 |

### Batch 5 (all CREATE — no conflicts)
| FIX | Target File |
|-----|-------------|
| FIX-043 | tests/unit/core/test_loaders.py (CREATE) |
| FIX-044 | tests/unit/validation/linters/test_linter_utils.py (CREATE) |
| FIX-045 | tests/unit/core/test_config.py (CREATE) |
| FIX-046 | tests/unit/validation/test_governance.py (CREATE) |
| FIX-047 | tests/unit/generation/test_schema_differ.py (CREATE) |
| FIX-048 | tests/unit/generation/test_prompt_generator.py (CREATE) |
| FIX-049 | tests/unit/validation/test_regression_bugs.py (CREATE) |

### Batch 6 (all different files)
| FIX | Target File |
|-----|-------------|
| FIX-050 | .github/workflows/ci.yml |
| FIX-051 | CLAUDE.md |
| FIX-052 | WIP/future/research-alignment-roadmap.md (CREATE) |

**Result: ZERO file conflicts within any parallel set.**

---

## Batch Gate Protocol

After each batch:

1. **Pre-gate commit:** `git add <modified-files-from-this-batch> && git commit -m "WIP: batch N complete"` (use targeted file adds -- avoid `git add -A` which may stage unintended WIP artifacts)
2. **Run batch gate:** `source devspec_env/bin/activate && pytest tests/ -x --tb=short`
3. **Pass criteria:** All 830+ tests pass (count increases after Batch 5)
4. **If FAIL:** Identify failing file, map to FIX-NNN, revert that file, re-run gate, mark task as DEFERRED, check downstream dependencies.

Final gate uses `-v` for full output:
```bash
source devspec_env/bin/activate && pytest tests/ -v
```

---

## Summary by Batch

| Batch | Tasks | Max Parallel | Purpose |
|-------|-------|-------------|---------|
| 0 | 3 | 3 | Foundation (shared modules) |
| 1 | 21 | 8 (Set 1C) | Consumer DRY fixes |
| 2 | 5 | 4 | Error system + format fixes |
| 3 | 8 | 8 | Structure + cleanup |
| 4 | 5 | 2 | Test reorganization |
| 5 | 7 | 7 | New tests |
| 6 | 3 | 3 | CI + docs + research |
| **Total** | **52** | **8** | |
