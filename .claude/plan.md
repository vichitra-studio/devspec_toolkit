# Canonical Drift Review: Gap Analysis & Implementation Plan

## Executive Summary

**371 tests pass. All 61 RFC findings (Phases 0–6) have been addressed.** The review
found **3 real bugs** and **0 regressions** against the RFC. No hallucinated or
assumed findings — every item below is verified against actual file contents.

---

## Part A: Gap Analysis (Finding-by-Finding)

### Phase 0: Foundation & Cleanup — ✅ COMPLETE (1 minor bug)

| Task | Status | Notes |
|------|--------|-------|
| 0.1 Generalize schema 16 | ✅ DONE | `patternProperties` for nfr_measurement_methods (L773) and timeout_constants (L797) |
| 0.2 Align schema vs validator | ✅ DONE | if/then conditionals (L507-539) enforce nfr_refs/fixture_ref for non-deferred items |
| 0.3 Repository cleanup | ✅ DONE | .gitignore has `*.egg-info/` and `tools/trace_matrix.json` |
| 0.4 Migration template contracts | ✅ DONE | All templates use canonical URIs + B4 fields |
| 0.5 Unify path references | ✅ DONE | path_conventions.md created, all 22 prompts use $PRODUCT_ROOT/$TOOLKIT_ROOT |

**Bug found:** CLAUDE.md:64 has stale version `0.1.0` in changelog example (should be `0.3.0`).

### Phase 1: Seed & Spec Dependency Hardening — ✅ COMPLETE

| Task | Status | Notes |
|------|--------|-------|
| 1.1 step_order.json extension | ✅ DONE | required_spec_inputs, required_seed_inputs, extraction_intent for all 22 steps |
| 1.2 spec_refs_ingested | ✅ DONE | Defined in collections.schema.json:506-535, referenced in all 19 step schemas |
| 1.3 seed_refs integrity | ✅ DONE | Optional hash (SHA-256) and version fields added to seedRef |
| 1.4 Extraction intent in prompts | ✅ DONE | All 22 prompts have Extraction Intent + Coverage Closure sections |
| 1.5 Seed manifest coverage | ✅ DONE | seed_lint.py validates path existence + W550 for undeclared seeds |
| 1.6 Deep validators 16a/b/c | ✅ DONE | DEEP_VALIDATORS entries registered; impl_context/ routing implemented |

### Phase 2: Roadmap & Implementation Hardening — ✅ COMPLETE

| Task | Status | Notes |
|------|--------|-------|
| 2.1 Harden roadmap schema | ✅ DONE | fr_refs, capability_refs, depends_on, assumptions, exit_conditions; E141/E142 validators |
| 2.2 Roadmap-to-checklist (E304) | ✅ DONE | step_16.py:290-324 |
| 2.3 ci_status gate (E303) | ✅ DONE | step_16.py:275-288 + schema conditional |
| 2.4 Planned-vs-executed (E305) | ✅ DONE | step_16.py:326-349 |
| 2.5 semantic_review | ✅ DONE | Schema L1741-1770 + E306 validator |
| 2.6 Roadmap→checklist mandate | ✅ DONE | prompt_16a + E307 behavior/validation pairing |

### Phase 3: Semantic Drift Prevention — ✅ COMPLETE

| Task | Status | Notes |
|------|--------|-------|
| 3.1 Transitive traceability | ✅ DONE | traceability_closure.py (122 lines), E560 error codes |
| 3.2 Independent placeholder scan | ✅ DONE | spec_quality_lint.py:171-191, E511 agreement check |
| 3.3 Hallucination lint | ✅ DONE | existing_structures, linked_test_expectation, NFR cross-ref (E530) |
| 3.4 Coverage closure in prompts | ✅ DONE | All 22 prompts have Coverage Closure self-audit gate |
| 3.5 init_project.py path | ✅ DONE | Configurable --toolkit-root, fixed seed_templates resolution |
| 3.6 Assumption validation | ✅ DONE | E512/W571/W572/W573 pattern-based checks |
| 3.7 Forward replay semantic | ✅ DONE | E550 SEMANTIC_COVERAGE_REGRESSION with git-based comparison |

### Phase 4: Migration Hardening — ✅ COMPLETE (1 bug)

| Task | Status | Notes |
|------|--------|-------|
| 4.1 Migration planner | ✅ DONE | planner.py with schema diff integration, DAG ordering |
| 4.2 Rollback support | ✅ DONE | runner.py with backup/restore |
| 4.3 Multi-file migrations | ✅ DONE | Transaction boundaries with atomic commit/rollback |
| 4.4 Migration tests | ⚠️ BUG | test_migration_templates.py lists 14 templates but 19 exist on disk; 5 are referenced by planner.py but untracked in git |
| 4.5 Handlebars decision | ✅ DONE | Step-based template mapping, no Handlebars/Jinja2 needed |

**Bug found:** 5 migration templates exist on disk and are referenced by `planner.py:51-56` (`_STEP_TO_TEMPLATE`) but are:
- NOT in `EXPECTED_TEMPLATES` list in `test_migration_templates.py`
- NOT staged in git (shown as `??` untracked)

Missing from test + git:
1. `template_ci_gates.md` (step 12)
2. `template_completeness_assessment.md` (step 13a)
3. `template_extension_generator.md` (step 13)
4. `template_redteam.md` (step 11)
5. `template_scaffold.md` (step 15)

### Phase 5: Test Suite Migration — ✅ COMPLETE

| Task | Status | Notes |
|------|--------|-------|
| 5.1 Test infrastructure | ✅ DONE | conftest.py + pytest config in pyproject.toml |
| 5.2 Rename B* files | ✅ DONE | All 8 files renamed |
| 5.3 Reorganize tools | ✅ DONE | 5 subpackages + deprecation shims in __init__.py |
| 5.4 New validator tests | ✅ DONE | test_gap_remediation, test_migration_*, test_traceability_closure, etc. |

### Phase 6: Documentation & Version — ✅ COMPLETE (same bug as Phase 0)

| Task | Status | Notes |
|------|--------|-------|
| 6.1 Version bump | ✅ DONE | pyproject.toml, CLAUDE.md line 9 = 0.3.0 |
| 6.2 CHANGELOG | ✅ DONE | Comprehensive with gap remediation section |
| 6.3 Documentation | ⚠️ BUG | CLAUDE.md:64 stale 0.1.0 (same as Phase 0 bug) |
| 6.4 Toolkit update workflow | ✅ DONE | docs/ops/toolkit_update_checklist.md created |
| 6.5 prompt_schema_sync | ✅ DEFERRED | Correctly deferred — 16a/b/c share one schema |

---

## Part B: All Bugs Found (Exhaustive)

### BUG-1: CLAUDE.md stale version reference (MEDIUM)
- **File:** `CLAUDE.md:64`
- **Current:** `./tools/run_specdev.sh changelog --validate 0.1.0 --repo-root ./devspec_toolkit`
- **Expected:** `./tools/run_specdev.sh changelog --validate 0.3.0 --repo-root ./devspec_toolkit`
- **Impact:** Users following docs will validate against wrong version

### BUG-2: 5 migration templates untracked in git (HIGH)
- **Files:** `prompts/migration/template_{ci_gates,completeness_assessment,extension_generator,redteam,scaffold}.md`
- **Impact:** `planner.py:38-58` (`_STEP_TO_TEMPLATE`) maps steps 11,12,13,13a,15 to these templates. If deployed without staging them, migration planner will fail with FileNotFoundError for these 5 steps.
- **Fix:** Stage the files + add them to `EXPECTED_TEMPLATES` in `test_migration_templates.py` + update count assertion from 14 to 19.

### BUG-3: test_migration_templates.py count assertion stale (HIGH)
- **File:** `tests/test_migration_templates.py:42-43`
- **Current:** `assert len(EXPECTED_TEMPLATES) == 14`
- **Expected:** `assert len(EXPECTED_TEMPLATES) == 19` (after adding 5 missing templates)
- **Impact:** Coupled to BUG-2. The test passes today because EXPECTED_TEMPLATES only has 14 entries, but it doesn't cover 5 templates that the planner depends on.

---

## Part C: Implementation Plan (Atomic, Dependency-Ordered)

Three bugs. Two are in the same file. Optimal sequencing is 2 tasks.

### Task 1: Fix CLAUDE.md stale version
**File:** `CLAUDE.md` (single edit)
**Subagent:** general-purpose, isolation: worktree
**Action:** Change `0.1.0` → `0.3.0` on line 64

### Task 2: Stage 5 migration templates + fix test expectations
**Files:** `tests/test_migration_templates.py` (edit), git stage 5 files
**Subagent:** general-purpose, isolation: worktree
**Actions:**
1. Add 5 template names to `EXPECTED_TEMPLATES` list (alphabetical order)
2. Update count assertion from 14 to 19
3. `git add prompts/migration/template_{ci_gates,completeness_assessment,extension_generator,redteam,scaffold}.md`

### Sequencing
Tasks 1 and 2 are independent — execute in parallel via subagents.

### Verification
After both tasks complete, run `pytest tests/test_migration_templates.py -v` to confirm the 5 new templates are covered.
