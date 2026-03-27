# P4 Fix Plan R3: Final Cross-Reference Review

**Date**: 2026-03-19
**Reviewer**: Claude Opus 4.6
**Scope**: Verify all R2 findings addressed, grep every removed field against the full codebase, check counts, dependencies, and hallucinations.

---

## Executive Summary

The R2 fixes are almost entirely incorporated. The plan is in strong shape. I found **4 issues**: 1 count error (carried forward from R2 with incomplete fix), 2 uncovered consumers, and 1 informational note. None are blocking.

**Severity breakdown**:
- BLOCKING: 0
- HIGH: 0
- MEDIUM: 2
- LOW: 2

---

## 1. COUNT ERROR (Carried from R2, incompletely fixed)

### CE-1: Header says 84 tasks; actual count is 83 (LOW)

R2 finding CE-1 said to update from 84 to 82. The plan was revised but landed on 84 (presumably accounting for FIX-085 and FIX-086 added per R2). However, the actual count of `### FIX-NNN` entries (excluding the appendix heading "FIX-019 Risk Mitigation") is **83**.

Verification:
- FIX-001 through FIX-052 = 52 tasks
- FIX-053/054/055 = 3 SUPERSEDED (not present as task entries) = 0
- FIX-056 through FIX-060 = 5 tasks
- FIX-061 through FIX-069 = 9 tasks
- FIX-070 through FIX-076 = 7 tasks
- FIX-077 through FIX-086 = 10 tasks
- Total: 52 + 5 + 9 + 7 + 10 = **83**

Appendix C LOC table also says 84 and lists Batch 6 as "10 tasks" but Batch 6 has 9 tasks (FIX-061 through FIX-069). This is the discrepancy. All other batch counts in Appendix C are correct.

**Fix**: Update header from 84 to 83. Update Appendix C Batch 6 row from "10" to "9". Update Appendix C total row from "84" to "83".

### CE-2: WONTFIX footer text incomplete (LOW)

The severity table footer says `*WONTFIX: AUDIT-040 (MEDIUM), AUDIT-031 (MEDIUM).*` but the third WONTFIX, AUDIT-051 (LOW), is listed only on the next line with different formatting. The header correctly says "WONTFIX: 3 (AUDIT-040, AUDIT-031, AUDIT-051)". The table rows correctly show MEDIUM WONTFIX=2 and LOW WONTFIX=1, summing to 3. This is a cosmetic inconsistency in the footer text only.

**Fix**: Change footer to `*WONTFIX: AUDIT-040 (MEDIUM), AUDIT-031 (MEDIUM), AUDIT-051 (LOW).*` and remove the separate line.

---

## 2. UNCOVERED CONSUMERS

### UC-1: `schema/10_governance.schema.json` has `"docs-lint"` in `pr_rules` enum (MEDIUM)

**File**: `schema/10_governance.schema.json` (line ~38)

The step_10 schema itself contains `"docs-lint"` in the `pr_rules` enum. FIX-086 removes `"docs-lint"` from the **validator** (`step_10.py` line ~44) and from `hallucination_lint.py`, but does not mention removing it from the **schema** itself. The schema enum is the authoritative source; the validator hardcodes it separately. Both must be updated.

**Impact**: After FIX-086 execution, the schema would still accept `"docs-lint"` as valid in `pr_rules`, contradicting the validator change. Spec files written against the schema could include `"docs-lint"` and pass schema validation but this references a deleted command.

**Fix**: Add `schema/10_governance.schema.json` to FIX-086's target files. Remove `"docs-lint"` from the `pr_rules` enum in the schema.

### UC-2: `tests/unit/validation/validators/test_step_validators_03_10.py` tests `docs-lint` as valid pr_rule (MEDIUM)

**File**: `tests/unit/validation/validators/test_step_validators_03_10.py` (lines 17-21)

The test `test_step_10_accepts_seed_docs_lint` constructs test data with `"pr_rules": ["seed-lint", "docs-lint"]` and asserts validation passes. After FIX-086 removes `"docs-lint"` from both the schema enum and the validator, this test will fail.

This test file is not covered by FIX-079 (which targets docs_lint test files) or FIX-081 (which targets test fixtures). It falls in the gap between "docs-lint reference removal" and "test cleanup".

**Fix**: Add this test file to FIX-086's scope (update or delete the test method `test_step_10_accepts_seed_docs_lint`). Alternatively, add it to FIX-081's scope.

---

## 3. R2 FINDINGS VERIFICATION

All 12 R2 findings have been addressed. Verification:

| R2 Finding | Expected Fix | Verified In Plan |
|---|---|---|
| CE-1 (task count) | Update header | Partially -- says 84, should be 83 (see CE-1 above) |
| CE-2 (WONTFIX table) | Fix MEDIUM row | Table rows are correct (MEDIUM WONTFIX=2, Fix Tasks=20) |
| GAP-1 (step_16.py docs_policy) | New FIX task | FIX-085 created in Batch 7 |
| GAP-2 (test_step_16.py docs_policy) | Add to FIX-081 | FIX-081 R2 additions item (5) covers this |
| GAP-3 (test_seed_* docs_policy) | Add to FIX-081 | FIX-081 R2 additions item (6) covers this |
| GAP-4/5 (seed_manifest fixtures) | Add to FIX-081 | FIX-081 R2 additions items (7) and (8) cover this |
| GAP-6 (__init__.py docs_lint) | Add to FIX-078 | FIX-078 R2 addition covers this |
| GAP-7 (ci.yml docs-lint) | Add to FIX-080 | FIX-080 item (4) explicitly names ci.yml |
| GAP-8/9/10 (docs references) | Add to FIX-080 | FIX-080 items (5)-(7) cover reference.md, getting_started.md, governance_architecture.md, review_prompt files |
| GAP-11 (prompt_16a docs_policy) | Add to FIX-082 | FIX-082 R2 addition item (7) covers this |
| GAP-12 (hallucination/step_10 docs-lint) | New FIX task | FIX-086 created in Batch 7 |
| NC-1-5 (matrix.py, migration templates, etc.) | Add to FIX-082 | FIX-082 R2 additions items (8) and (9) cover migration templates and shared_expectations.md |
| NC-8 (15 test files allowed_upstream_deps) | Add to FIX-074 | FIX-074 R2 addition covers 15 test files |
| DEP-1/3 (FIX-061-065 vs FIX-084 overlap) | Clarify scope | FIX-084 scope clarification added; FIX-061/062/064/065 each note "definitions removed by FIX-084, not here" |

---

## 4. FIELD-BY-FIELD GREP VERIFICATION

For each removed field, I grepped the entire repo (excluding WIP/, docs/audit/, changelog/) and verified every active consumer is covered by a FIX task.

### `generation_quality` (245 files total, ~13 active non-WIP/non-docs consumers)

| Consumer Type | Files | Covered By |
|---|---|---|
| 19 step schemas | `schema/00_charter.schema.json` through `schema/16_impl_context.schema.json` | FIX-019 (Batch 2) + FIX-064 (Batch 6) |
| Tool: spec_quality_lint.py | 1 file | FIX-070 |
| Tool: prompt_schema_sync.py | 1 file | FIX-071 |
| Tool: strip_generation_quality.py | 1 file (dead code after removal) | R2 NC-4 acknowledged; not blocking |
| Test: test_schema_contracts.py, test_prompt_schema_sync.py, etc. | 5 files | FIX-081 |
| Prompts: prompt_*.md | 19 files | FIX-082 |
| Migration templates | 19 files | FIX-082 R2 addition |
| Test fixtures: 40+ JSON files | All fixture dirs | FIX-081 |
| Spec data: spec/05_interface_contracts.json | 1 file | FIX-083 |

**Status**: All covered.

### `seed_refs` (215 files total)

| Consumer Type | Files | Covered By |
|---|---|---|
| 19 step schemas | As above | FIX-019 + FIX-065 |
| Tool: seed_lint.py | 1 file | FIX-072 |
| Tool: spec_quality_lint.py | 1 file | FIX-070 |
| Tool: matrix.py | 1 file (string constant, harmless) | R2 NC-1 acknowledged |
| Test/fixture/prompt files | Many | FIX-081, FIX-082 |

**Status**: All covered.

### `spec_refs_ingested` (187 files total)

All consumers covered by FIX-061 (schema), FIX-081 (fixtures), FIX-082 (prompts), FIX-083 (spec data).

**Status**: All covered.

### `coverage_gaps` (194 files total)

| Consumer Type | Files | Covered By |
|---|---|---|
| Tool: step_12.py | 1 file | FIX-073 |
| Schema/fixture/prompt files | Many | FIX-062, FIX-081, FIX-082, FIX-083 |

**Status**: All covered.

### `docs_policy` (31 files total, ~10 active)

| Consumer Type | Files | Covered By |
|---|---|---|
| Schema: seed_manifest.schema.json | 1 file | FIX-069 |
| Data: seed_manifest.json | 1 file | FIX-069 |
| Tool: docs_lint.py | 1 file | FIX-077 (delete) |
| Tool: step_16.py | 1 file | FIX-085 |
| Test: test_step_16.py | 1 file | FIX-081 R2 item (5) |
| Test: test_seed_propagation_trim.py, test_seed_content_overlap.py | 2 files | FIX-081 R2 item (6) |
| Test fixtures: seed_manifest/*.json | 2 files | FIX-081 R2 items (7-8) |
| Prompt: prompt_16a_impl_planner.md | 1 file | FIX-082 R2 item (7) |
| Docs: getting_started.md, governance_architecture.md | 2 files | FIX-080 item (7) |

**Status**: All covered.

### `docs-lint` / `docs_lint` (47 files total, ~8 active non-WIP)

| Consumer Type | Files | Covered By |
|---|---|---|
| Tool: cli.py | 1 file | FIX-078 |
| Tool: __init__.py | 1 file | FIX-078 R2 addition |
| Tool: docs_lint.py | 1 file | FIX-077 (delete) |
| Tool: hallucination_lint.py | 1 file | FIX-086 |
| Tool: step_10.py (validator) | 1 file | FIX-086 |
| **Schema: 10_governance.schema.json** | **1 file** | **NOT COVERED** (see UC-1) |
| **Test: test_step_validators_03_10.py** | **1 file** | **NOT COVERED** (see UC-2) |
| CI: .github/workflows/ci.yml | 1 file | FIX-080 item (4) |
| Docs: CLAUDE.md, README.md, reference.md, etc. | 5 files | FIX-080 |
| Prompt: prompt_12_ci_gates.md | 1 file | FIX-080 item (3) |

**Status**: 2 gaps found (UC-1, UC-2 above).

### `nested_order` (19 files total, ~4 active)

| Consumer Type | Files | Covered By |
|---|---|---|
| Schema: seed_manifest.schema.json | 1 file | FIX-063 |
| Data: seed_manifest.json | 1 file | FIX-063 |
| Tool: seed_lint.py | 1 file | FIX-076 |
| Test fixtures: seed_manifest/*.json | 2 files | FIX-081 R2 items (7-8) |

**Status**: All covered.

### `allowed_upstream_dependencies` (46 files total, ~20 active)

| Consumer Type | Files | Covered By |
|---|---|---|
| Data: tools/step_order.json | 1 file | FIX-066 |
| Tool: dag_lint.py, dependency_order_lint.py, extraction_intent_check.py, hallucination_lint.py, cli.py | 5 files | FIX-074 |
| Test files: 15 unit tests | 15 files | FIX-074 R2 addition |

**Status**: All covered.

---

## 5. SUPERSEDED TASK VERIFICATION

FIX-053, FIX-054, FIX-055 are properly marked as SUPERSEDED in Appendix E. No FIX task lists them as dependencies. The superseding tasks (FIX-061, FIX-062, FIX-063) correctly reference the supersession. Clean.

---

## 6. DEPENDENCY ORDERING VERIFICATION

Batch ordering is correct:
- Batch 0 (create definitions) precedes Batch 1 (modify core) and Batch 2 (consume definitions)
- Batch 2 (allOf adoption) precedes Batch 3 (descriptions on step-specific props)
- Batch 6 (schema removals) precedes Batch 7 (tool code updates)
- Batch 7 (tool updates) precedes Batch 8 (test/fixture/prompt cleanup)
- FIX-084 (Batch 8) explicitly depends on FIX-061/062/064/065 (Batch 6) -- scope clarification from R2 is clear

Within-batch dependencies are properly chained (e.g., FIX-002 -> FIX-003 -> FIX-004 -> FIX-005 -> FIX-006 for atoms.schema.json sequential edits).

No circular dependencies detected.

---

## 7. HALLUCINATION CHECK

All files referenced in FIX-085 and FIX-086 (the new R2 tasks) verified:
- `tools/specdev_tools/validation/validators/step_16.py` -- exists
- `tools/specdev_tools/validation/hallucination_lint.py` -- exists
- `tools/specdev_tools/validation/validators/step_10.py` -- exists

No hallucinated files or functions found in any task.

---

## 8. INFORMATIONAL NOTES

### NOTE-1: `strip_generation_quality.py` becomes dead code (LOW, carried from R2 NC-4)

`tools/specdev_tools/migration/scripts/strip_generation_quality.py` will become dead code after generation_quality removal. No FIX task covers its deletion. This is harmless but untidy. Consider adding to FIX-077 (which already deletes docs_lint.py) or creating a follow-up cleanup task.

### NOTE-2: `docs/audit/review_prompt_04_canonical_drift_pending.md` references docs_lint in directory tree

FIX-080 mentions `review_prompt_04_canonical_drift.md` but not the `_pending` variant. Both exist. The `_pending` file has a directory tree listing that includes `docs_lint.py`. This is an audit/historical document and not actionable, but FIX-080 item (7) should be aware it exists.

---

## Summary of Required Actions

| # | Finding | Severity | Action |
|---|---|---|---|
| CE-1 | Task count 84 should be 83 | LOW | Update header and Appendix C (Batch 6: 10->9, total: 84->83) |
| CE-2 | WONTFIX footer text incomplete | LOW | Add AUDIT-051 (LOW) to footer text |
| UC-1 | `schema/10_governance.schema.json` has `"docs-lint"` in pr_rules enum | MEDIUM | Add schema file to FIX-086 target files |
| UC-2 | `test_step_validators_03_10.py` tests `"docs-lint"` as valid pr_rule | MEDIUM | Add to FIX-086 scope (update test after enum change) |

**Verdict**: The plan is ready for execution after these 4 minor fixes. No blocking issues remain.
