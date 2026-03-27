# P4 Fix Plan R2: Cross-Reference Review

**Date**: 2026-03-19
**Reviewer**: Claude Opus 4.6
**Scope**: Verify the revised 82-task fix plan against the actual codebase. Check for gaps, dependency errors, count errors, hallucinations, and batch ordering issues.

---

## Executive Summary

The revised plan is substantially sound. The 10 deep-review decisions (D1-D10) are well-reasoned and the new FIX tasks (061-084) correctly identify the primary consumers. However, I found **12 gaps** (uncovered consumers), **2 count errors**, **1 dependency concern**, and **3 scope observations** that should be addressed before execution begins.

**Severity breakdown of findings**:
- BLOCKING: 0
- HIGH (must fix before execution): 5
- MEDIUM (fix during execution): 5
- LOW (informational): 4

---

## 1. COUNT ERRORS

### CE-1: Header says 84 tasks but only 82 FIX entries exist (MEDIUM)

The plan header states "Total tasks: 84" but `grep -c "^### FIX-" p4-out-fix-plan.md` returns **82**. The FIX numbering skips 053-055 (superseded) and jumps from 060 to 061, so the actual task count is 82 (FIX-001 through FIX-006, FIX-007 through FIX-010, FIX-011 through FIX-019, FIX-020 through FIX-034, FIX-035 through FIX-045, FIX-046 through FIX-052, FIX-056 through FIX-059, FIX-060 through FIX-084). The last section header "FIX-019 Risk Mitigation" is an appendix item, not a task.

**Fix**: Update header to "Total tasks: 82".

### CE-2: Severity coverage table WONTFIX count is wrong (MEDIUM)

Header says "WONTFIX: 3 (AUDIT-040, AUDIT-031, AUDIT-051)" but the severity coverage table shows total WONTFIX = 2. The error is in the MEDIUM row: it shows WONTFIX=1, but both AUDIT-040 (MEDIUM) and AUDIT-031 (MEDIUM) are WONTFIX, so MEDIUM WONTFIX should be **2**. This makes total WONTFIX = 3, matching the header.

Cascading fix: MEDIUM row should read `Fix Tasks=20 | WONTFIX=2` (not `21 | 1`). Total Fix Tasks = 47 (not 48).

---

## 2. GAPS (Uncovered Consumers)

### GAP-1: `step_16.py` validator reads `docs_policy.doc_paths` -- NOT covered by any FIX task (HIGH)

**File**: `tools/specdev_tools/validation/validators/step_16.py` (lines 180-183)

The step_16 validator reads `docs_policy.doc_paths` from `seed_manifest.json` to validate `docs_impact` paths. When `docs_policy` is removed (FIX-069), this code will fail with a warning (`W570`). No FIX task covers updating this validator.

**Impact**: After Batch 6 (FIX-069 removes docs_policy), the step_16 validator will emit spurious W570 warnings for every step_16 validation.

**Fix**: Add a new FIX task in Batch 7 to update `step_16.py` -- either remove the `doc_paths` check entirely (since docs_policy is scope creep) or hardcode a reasonable default. This should be a dependency of FIX-069.

### GAP-2: `test_step_16.py` integration tests construct `docs_policy` in test data -- NOT covered (HIGH)

**File**: `tests/integration/test_step_16.py` (lines 162, 194, 220, 240, 288, 342)

Six test methods create mock `seed_manifest.json` data containing `docs_policy`. These tests will fail after `docs_policy` is removed from the schema and `step_16.py` is updated.

**Impact**: Test failures in Batch 8 that are not accounted for in FIX-081 (which only covers test fixtures, not integration test code).

**Fix**: FIX-081 should explicitly mention `tests/integration/test_step_16.py` or a separate FIX task should cover it.

### GAP-3: `test_seed_propagation_trim.py` and `test_seed_content_overlap.py` construct `docs_policy` in test data (MEDIUM)

**Files**:
- `tests/unit/validation/linters/test_seed_propagation_trim.py` (line 58)
- `tests/unit/validation/linters/test_seed_content_overlap.py` (line 31)

Both tests construct mock `seed_manifest` data containing `docs_policy`. After removal, these tests will either fail or have dead data that should be cleaned up.

**Fix**: Include in FIX-081 scope or add to FIX-079 (docs_lint test removal).

### GAP-4: `tests/fixtures/seed_manifest/valid_minimal.json` contains `docs_policy` and `nested_order` (MEDIUM)

**File**: `tests/fixtures/seed_manifest/valid_minimal.json`

This fixture includes both `docs_policy` and `nested_order`. After schema removal (FIX-063, FIX-069), this fixture will either fail validation or contain dead data.

**Fix**: Add to FIX-081 scope (fixture cleanup).

### GAP-5: `tests/fixtures/seed_manifest/invalid_missing_required.json` likely tests `docs_policy` as required (MEDIUM)

**File**: `tests/fixtures/seed_manifest/invalid_missing_required.json`

This fixture likely tests that missing required fields (including `docs_policy` and possibly `nested_order`) cause validation errors. After these fields are removed from `required`, the fixture's expected behavior changes.

**Fix**: Add to FIX-081 scope.

### GAP-6: `tools/specdev_tools/__init__.py` has docs_lint module registration (HIGH)

**File**: `tools/specdev_tools/__init__.py` (line 31)

```python
"docs_lint": "specdev_tools.validation.docs_lint",
```

FIX-078 covers removing docs-lint from `cli.py`, but `__init__.py` also registers the module. If this registry is used for dynamic imports, leaving it will cause import errors after `docs_lint.py` is deleted.

**Fix**: FIX-078 should explicitly include `__init__.py` cleanup, or a separate task should cover it.

### GAP-7: `.github/workflows/ci.yml` runs docs-lint (HIGH)

**File**: `.github/workflows/ci.yml` (line 56)

```yaml
run: python -m specdev_tools.cli docs-lint spec --repo-root .
```

FIX-080 mentions "Any CI config files (.github/workflows, etc.) that run docs-lint" but does not explicitly name `ci.yml`. This is the most critical reference because it will cause CI failures.

**Impact**: CI pipeline will break immediately after docs_lint deletion.

**Fix**: FIX-080 should explicitly list `.github/workflows/ci.yml`.

### GAP-8: `tools/README.md` lists docs-lint in CLI overview (LOW)

**File**: `tools/README.md` (line 63)

FIX-080 mentions CLAUDE.md and prompt files but does not mention `tools/README.md`.

**Fix**: Add to FIX-080 scope.

### GAP-9: `docs/developers/reference.md` has docs-lint examples and instructions (LOW)

**File**: `docs/developers/reference.md` (lines 86, 212)

Contains both a CLI example and a validation ritual reference to docs-lint.

**Fix**: Add to FIX-080 scope.

### GAP-10: `docs/developers/getting_started.md` and `docs/architecture/governance_architecture.md` reference docs_policy or docs-lint (LOW)

**Files**:
- `docs/developers/getting_started.md`
- `docs/architecture/governance_architecture.md`
- `docs/audit/review_prompt_04_canonical_drift.md`
- `docs/audit/review_prompt_02_tooling.md`

FIX-080 should include these documentation files.

### GAP-11: `prompts/prompt_16a_impl_planner.md` references `docs_policy.readme_depth_by_scope` (HIGH)

**File**: `prompts/prompt_16a_impl_planner.md` (line 246)

This prompt instructs the LLM to update `docs_policy.readme_depth_by_scope` when adding directories. After `docs_policy` removal, this instruction becomes invalid and will confuse LLM runners.

**Impact**: LLM-generated step 16a artifacts may reference a non-existent config field.

**Fix**: Should be covered by FIX-082 (prompt cleanup) but FIX-082 only mentions "generation_quality, seed_refs, coverage_gaps" -- it does not mention `docs_policy`. Add `docs_policy` prompt references to FIX-082's scope.

### GAP-12: `hallucination_lint.py` and `step_10.py` validator contain `docs-lint` as a hardcoded valid CI command string (MEDIUM)

**Files**:
- `tools/specdev_tools/validation/hallucination_lint.py` (line 132): `"docs-lint"` in valid CI command list
- `tools/specdev_tools/validation/validators/step_10.py` (line 44): `"docs-lint"` in valid `pr_rules` enum

After docs-lint deletion, these validators will still accept `docs-lint` as a valid CI command / pr_rule. This is a logic error (accepting a nonexistent command as valid).

**Fix**: Add a FIX task in Batch 7 or Batch 8 to remove `"docs-lint"` from these hardcoded lists.

---

## 3. ADDITIONAL UNCOVERED CONSUMERS (Non-Blocking)

### NC-1: `tools/specdev_tools/validation/matrix.py` uses `seed_refs` as a REFERENCE_CONTEXT key (LOW)

**File**: `tools/specdev_tools/validation/matrix.py` (line 72)

The `REFERENCE_CONTEXTS` set includes `"seed_refs"` as a context name for distinguishing reference IDs from definition IDs during matrix traversal. This is a string constant, not a data reader -- it is used to recognize JSON keys named `seed_refs` during traversal. After `seed_refs` is removed from spec files, this entry becomes dead but harmless.

**Recommendation**: Clean up in FIX-081 or a follow-up. Not blocking.

### NC-2: `docs/prompts/shared_expectations.md` references `generation_quality` (LOW)

**File**: `docs/prompts/shared_expectations.md` (lines 25, 38)

This shared prompt document mentions `generation_quality` as part of evidence tracking.

**Recommendation**: Include in FIX-082 prompt cleanup scope.

### NC-3: Migration templates in `prompts/migration/` reference removed fields (LOW)

**Files**: All 19 `prompts/migration/template_*.md` files contain `generation_quality`, `seed_refs`, `spec_refs_ingested`, and/or `coverage_gaps`.

FIX-082 mentions `prompts/prompt_*.md` (24+ files) but does not mention `prompts/migration/template_*.md` (19 files).

**Recommendation**: Add migration templates to FIX-082 scope.

### NC-4: Migration script `strip_generation_quality.py` becomes dead code (LOW)

**File**: `tools/specdev_tools/migration/scripts/strip_generation_quality.py`

After `generation_quality` is removed from schemas, this migration script has no purpose.

**Recommendation**: Delete in Batch 8 or mark as dead code.

### NC-5: `tests/unit/migration/test_migration_templates.py` references `generation_quality` (LOW)

This test file will need updating after the migration templates are cleaned.

### NC-6: `changelog/v0.4.0.yaml` and `changelog/v0.4.0.md` reference `generation_quality` (INFORMATIONAL)

Historical records -- no action needed.

### NC-7: Numerous `docs/audit/` files reference removed fields (INFORMATIONAL)

Historical audit records that document the evolution. No action needed for correctness, but FIX-080 should consider whether any active (non-historical) docs need updating.

### NC-8: 15 test files reference `allowed_upstream_dependencies` (HIGH -- partially covered)

**Files**: 15 test files in `tests/unit/` reference `allowed_upstream_dependencies`. FIX-074 covers the 5 tool code consumers but does not explicitly address test file updates.

FIX-081 covers "test fixtures" but not unit test code that constructs mock `step_order.json` data. These tests will fail when the tool code stops reading `allowed_upstream_dependencies`.

**Recommendation**: FIX-074 should list the 15 test files that need updating, or a dedicated Batch 8 task should cover them.

---

## 4. DEPENDENCY AND ORDERING ISSUES

### DEP-1: FIX-061/062/064/065 remove fields from `step_base.schema.json` -- but fields may not exist there yet (MEDIUM)

FIX-001 (Batch 0) creates `step_base.schema.json` and is told to exclude the 4 removed fields. FIX-019 (Batch 2) adopts allOf and removes common fields from step schemas. So by Batch 6, the removed fields should already be gone from both the base and step schemas.

But the descriptions for FIX-061/062/064/065 say "Remove X from properties and required in `step_base.schema.json`" -- if FIX-001 correctly excludes them, there's nothing to remove from the base. The actual removal target in Batch 6 should be:
1. Any step schemas that still have these fields inline (if FIX-019 missed some)
2. The `core/collections.schema.json` type definitions

FIX-084 (Batch 8) also removes collections definitions, creating a potential double-removal with FIX-061/062/064/065 which also list collections as a target.

**Risk**: Task descriptions may confuse executors about what to actually do. Some tasks may be partially no-ops.

**Recommendation**: Clarify that Batch 6 FIX-061/062/064/065 target:
- Any residual inline declarations in step schemas (safety net)
- The definitions will be handled by FIX-084

OR merge the collections cleanup from FIX-084 into FIX-061/062/064/065 and eliminate FIX-084 as redundant.

### DEP-2: FIX-069 (remove docs_policy, Batch 6) will break tests before Batch 7/8 (EXPECTED, documented)

The plan acknowledges that Batch 6 removals will cause test failures. This is fine given the documented Batch 6 gate. No issue.

### DEP-3: FIX-084 (Batch 8) duplicates scope with FIX-061/062/064/065 (Batch 6) (MEDIUM)

FIX-061 says: "Remove `specRefIngested` and `specRefsIngestedArray` definitions from `core/collections.schema.json`"
FIX-084 says: "Remove `specRefIngested` and `specRefsIngestedArray` definitions from `core/collections.schema.json`"

Both tasks claim to remove the same definitions from collections.schema.json. Only one can actually do the work.

**Fix**: Either (a) remove the collections cleanup from FIX-061/062/064/065 descriptions and leave it to FIX-084, or (b) remove FIX-084 entirely and ensure FIX-061/062/064/065 each handle their respective collections cleanup.

---

## 5. BATCH ORDERING ASSESSMENT

The batch ordering is correct for the critical path:

```
Batch 0 (new definitions) -> Batch 1 (core fixes) -> Batch 2 (step DRY) -> Batch 3 (descriptions) -> Batch 4 (genericity) -> Batch 5 (structure) -> Batch 6 (removals) -> Batch 7 (tool code) -> Batch 8 (tests/fixtures/prompts/docs)
```

This sequencing is sound because:
- Schema additions (Batch 0-1) precede schema consumers (Batch 2)
- Schema removals (Batch 6) precede tool code removals (Batch 7)
- Tool code removals (Batch 7) precede test/fixture removals (Batch 8)

The one concern is that Batch 6 removals will cause test failures until Batch 7+8 complete, but the plan acknowledges this at the Batch 6 gate.

**Recommendation for Batch 6-8**: Consider merging into a single "atomic removal" batch if parallelism allows, to minimize the window of test failures. The plan's current sub-batch approach (8A/8B/8C/8D) is a good structure.

---

## 6. WONTFIX REVIEW

### AUDIT-040 (ALIGN-2 URI migration): Still valid WONTFIX

534 URIs across 70+ files. Depends on ALIGN-1 (DRY fixes in Batch 0-2). Still out of scope for this audit. Correctly deferred.

### AUDIT-031 (Canon schemas outside schema/ directory): Still valid WONTFIX

Intentional co-location. Cost exceeds benefit. No change from expanded removal scope.

### AUDIT-051 (src/dist schema split): WONTFIX rationale weakened by D1-D4

AUDIT-051 specifically lists `generation_quality`, `spec_refs_ingested`, `coverage_gaps`, `seed_refs` as "candidate fields for src-mode optionality." Since all four are now being removed entirely (D1-D4), the src/dist split has fewer candidate fields. The remaining candidates (canonical triad) are being made optional (D9/D10). This significantly reduces the need for a src/dist split.

**Recommendation**: Update AUDIT-051 WONTFIX justification to note that D1-D4 and D9/D10 have largely solved the underlying problem (required field saturation) through removal rather than through mode-based relaxation. The WONTFIX disposition is still correct but for different reasons now.

---

## 7. HALLUCINATION CHECK

### No hallucinated files or functions found

All files referenced in new FIX tasks (061-084) exist in the codebase:
- `schema/core/step_base.schema.json` -- will be created by FIX-001 (correct: referenced as target, not as existing)
- `schema/core/collections.schema.json` -- exists
- `schema/seed_manifest.schema.json` -- exists
- `spec/common/seed_manifest.json` -- exists
- `tools/step_order.json` -- exists
- `tools/specdev_tools/validation/spec_quality_lint.py` -- exists
- `tools/specdev_tools/generation/prompt_schema_sync.py` -- exists
- `tools/specdev_tools/validation/seed_lint.py` -- exists
- `tools/specdev_tools/validation/validators/step_12.py` -- exists
- `tools/specdev_tools/validation/dag_lint.py` -- exists
- `tools/specdev_tools/validation/dependency_order_lint.py` -- exists
- `tools/specdev_tools/validation/extraction_intent_check.py` -- exists
- `tools/specdev_tools/validation/hallucination_lint.py` -- exists
- `tools/specdev_tools/cli.py` -- exists
- `tools/specdev_tools/canonical/integrity.py` -- exists
- `tools/specdev_tools/validation/docs_lint.py` -- exists

### FIX-074 consumer list verified

FIX-074 lists 5 consumers of `allowed_upstream_dependencies`. Grep confirms all 5 tool files:
1. `dag_lint.py` -- confirmed (lines 56, 77, 100, 171, 190, 200)
2. `dependency_order_lint.py` -- confirmed (line 60)
3. `extraction_intent_check.py` -- confirmed (lines 31, 57)
4. `hallucination_lint.py` -- confirmed (line 324)
5. `cli.py` -- confirmed (line 1052)

But 15 test files also reference it (see NC-8 above) -- these are not listed.

---

## 8. SUPERSEDED TASK REFERENCES

FIX-053, FIX-054, FIX-055 are marked as SUPERSEDED. Verified: no other FIX task lists them as a dependency. The superseding tasks (FIX-061, FIX-062, FIX-063) correctly note the supersession. Clean.

---

## Summary of Required Actions

### Must fix before execution (HIGH):

| # | Finding | Action |
|---|---------|--------|
| GAP-1 | `step_16.py` reads `docs_policy.doc_paths` | Add FIX task in Batch 7 to update step_16.py validator |
| GAP-2 | `test_step_16.py` constructs `docs_policy` in 6 places | Add to FIX-081 scope or create separate task |
| GAP-6 | `__init__.py` registers docs_lint module | Add to FIX-078 scope |
| GAP-7 | `ci.yml` runs docs-lint | Explicitly name in FIX-080 |
| GAP-11 | `prompt_16a` references `docs_policy.readme_depth_by_scope` | Add docs_policy references to FIX-082 scope |

### Should fix (MEDIUM):

| # | Finding | Action |
|---|---------|--------|
| CE-1 | Task count 84 vs 82 | Update header |
| CE-2 | WONTFIX count in severity table | Fix MEDIUM row: WONTFIX=2, Fix Tasks=20 |
| GAP-3 | `test_seed_*` tests construct `docs_policy` | Add to FIX-081 |
| GAP-4/5 | seed_manifest test fixtures need cleanup | Add to FIX-081 |
| GAP-12 | `hallucination_lint.py` and `step_10.py` accept `docs-lint` as valid command | Add Batch 7/8 task |
| DEP-1/3 | FIX-061-065 vs FIX-084 scope overlap | Clarify which task handles collections cleanup |
| NC-8 | 15 test files reference `allowed_upstream_dependencies` | Add to FIX-074 scope or create Batch 8 task |

### Nice to have (LOW):

| # | Finding | Action |
|---|---------|--------|
| GAP-8/9/10 | Docs files reference docs-lint | Add to FIX-080 scope |
| NC-1-5 | Migration templates, matrix.py, shared_expectations.md | Add to FIX-082 scope |
| NC-4 | `strip_generation_quality.py` dead code | Delete in Batch 8 |
| AUDIT-051 | WONTFIX rationale weakened | Update justification text |
