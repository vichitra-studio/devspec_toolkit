# Batch 7 Review — Schema Audit FIX-070 through FIX-076, FIX-085, FIX-086

**Date**: 2026-03-19
**Reviewer**: Claude (automated)
**Test results**: 1270 passed, 0 failed

---

## 1. FIX-070: spec_quality_lint.py — Required top-level fields trimmed

**File**: `tools/specdev_tools/validation/spec_quality_lint.py`

**Status**: PASS

- `_check_required_top_level` (line 173) checks only `id`, `owner`, `created_at`, `canonical_refs_used` -- confirmed correct.
- No references to removed fields (`generation_quality`, `spec_refs_ingested`, etc.) remain.
- No dead imports or unused variables.
- Control flow is clean.

---

## 2. FIX-071: prompt_schema_sync.py — DRIFT_SENSITIVE_FIELDS trimmed

**File**: `tools/specdev_tools/generation/prompt_schema_sync.py`

**Status**: PASS

- `DRIFT_SENSITIVE_FIELDS` (line 24-28) contains only `dependencies`, `trace`, `canonical_refs_used` -- confirmed correct.
- No references to removed fields.
- No dead imports.

---

## 3. FIX-072: seed_lint.py — seed_refs validation removed

**File**: `tools/specdev_tools/validation/seed_lint.py`

**Status**: PASS

- Content overlap (`_check_seed_content_overlap`, line 129) now derives seed-artifact pairs from `step_requirements` via `_collect_required_seeds()` instead of reading `seed_refs` from individual artifacts. Logic is correct:
  1. Walks spec_dir for JSON files
  2. Determines step_id from filename
  3. Calls `_collect_required_seeds(manifest, step_id)` to get required seeds from manifest's `step_requirements`
  4. Checks token overlap between seed content and artifact content
- E520 errors for missing `seed_refs` are fully removed (grep confirmed zero matches for `E520.*seed_refs`).
- `seed_refs` appears only in `matrix.py` line 72 as a key to scan for trace links -- this is legitimate (matrix scans data keys generically).

---

## 4. FIX-073: step_12.py — coverage_gaps cross-reference removed

**File**: `tools/specdev_tools/validation/validators/step_12.py`

**Status**: PASS (with note)

- The comment on line 57 still mentions `coverage_gaps`: `"Collect and validate spec references from trace, coverage_gaps, and jobs"` but the actual code below only processes `trace` (lines 59-64) and `jobs` (lines 67-79). No code reads `coverage_gaps`.
- **Note**: The comment is stale -- it references `coverage_gaps` but the code no longer processes it. Minor documentation debt, not a functional issue.

---

## 5. FIX-074: compute_allowed_upstream utility

**File**: `tools/specdev_tools/core/constants.py`

**Status**: PASS

- Function is correct: `steps[:steps.index(step_id)]` returns all steps before the given step.
- Edge case handling:
  - `step_id == "00"` (first step): `steps.index("00")` returns 0, `steps[:0]` returns `[]` -- correct.
  - `step_id` not in list: `ValueError` caught, returns `[]` -- correct.
- **4 consumers** (not 5 as stated in the batch description):
  1. `dag_lint.py` (line 58)
  2. `extraction_intent_check.py` (line 59)
  3. `hallucination_lint.py` (line 326)
  4. `dependency_order_lint.py` (line 62)
- All consumers use it consistently: `compute_allowed_upstream(steps_list, step_id)`.
- No test files import `compute_allowed_upstream` -- tests exercise it indirectly through the consumers.

---

## 6. FIX-075: canonical/integrity.py — no-op

**Status**: PASS (no-op confirmed, already handles optional fields)

---

## 7. FIX-076: seed_lint.py — nested_order validation removed

**File**: `tools/specdev_tools/validation/seed_lint.py`

**Status**: PASS

- Zero occurrences of `nested_order` in all of `tools/specdev_tools/` (grep confirmed).

---

## 8. FIX-085: step_16.py — docs_policy.doc_paths check removed

**File**: `tools/specdev_tools/validation/validators/step_16.py`

**Status**: PASS

- Zero occurrences of `docs_policy` in `tools/specdev_tools/validation/validators/` (grep confirmed).
- `docs_policy` only remains in `validation/docs_lint.py` where it is the primary feature -- that's the correct and expected location (docs-lint reads governance manifest's `docs_policy`).

---

## 9. FIX-086: "docs-lint" removed from hallucination/governance validation

**File**: `tools/specdev_tools/validation/hallucination_lint.py`

**Status**: PASS

- `allowed_pr_rules` set (line 131-135) does NOT contain `"docs-lint"` -- confirmed removed.
- `docs-lint` CLI subcommand still exists in `cli.py` (lines 163, 386, 391) -- correct, the CLI command itself should remain; only the governance validation enum was removed.
- Zero occurrences of `docs-lint` in `tests/` directory.
- Zero occurrences of `docs-lint` in `step_10.py`.

---

## Orphaned Reference Audit

| Pattern | Expected | Actual | Status |
|---------|----------|--------|--------|
| `generation_quality` in validation/ | 0 | 0 | PASS |
| `generation_quality` in tools/specdev_tools/ | 0 (validation) | Only in `migration/scripts/strip_generation_quality.py` (migration script) | PASS |
| `seed_refs` in tools/specdev_tools/ | minimal | 2 occurrences: seed_lint comment (line 139), matrix.py key scan (line 72) | PASS |
| `spec_refs_ingested` | 0 | 0 | PASS |
| `coverage_gaps` in tools/specdev_tools/ | 0 | 1 stale comment in step_12.py line 57 | MINOR |
| `nested_order` in validators/ | 0 | 0 | PASS |
| `docs_policy` in validators/ | 0 | 0 | PASS |
| `allowed_upstream_dependencies` in production code | 0 (non-DAG) | Only in dag_lint.py and extraction_intent_check.py (referencing step_order.json field) | PASS |

---

## Test Results

```
1270 passed in 35.38s
```

All tests pass. No failures to map to Batch 8.

---

## Summary

**All 8 FIX items verified PASS.** No functional issues found.

### Minor items (non-blocking):

1. **Stale comment in step_12.py line 57**: Comment still references `coverage_gaps` but code no longer processes it. Cosmetic fix only.
2. **Consumer count discrepancy**: Batch description says "5 tool files" for FIX-074 but only 4 consumers of `compute_allowed_upstream` were found in production code.

### No remaining test failures. Batch 8 has no carry-forward items from this review.
