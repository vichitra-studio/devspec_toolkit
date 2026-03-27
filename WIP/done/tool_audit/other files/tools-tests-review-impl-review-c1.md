# Review: tools-tests-review-plan-c1.md
Topic: tools-tests-review
Generated: 2026-03-11
Reference: WIP/tools-tests-review-plan-c1.md

## Summary
- Total findings: 8 (2 blocking; 6 non-blocking)
- Critical: 0 | High: 1 | Medium: 1 | Low: 6
- By category: Gaps: 1 | Misses: 7 | Bugs: 0 | Regressions: 0 | Improvements: 0 | Assumptions: 0 | Hallucinations: 0
- Files reviewed: 8 (all findings files from Tasks 001-008)
- Uncovered requirements: 0

## High Findings

### F-tools-tests-review-001 — Task 009 consolidated report not created
- **File**: WIP/tools-tests-review-review-c1.md:0
- **Severity**: high
- **Category**: gap
- **Reference**: T-tools-tests-review-009
- **Evidence**: `glob WIP/tools-tests-review-review-c1.md` returns no results; all 8 source findings files exist
- **Detail**: The consolidated findings report specified by Task 009 does not exist. This task depends on all 8 Group 1 tasks (which are complete) and should merge their findings into a single structured document with Executive Summary, severity counts, all FINDING/PASS records organized by category A-F, an Actionable Fix Plan with phased grouping, and a Decision Log. Without this report, the audit pipeline output is fragmented across 8 separate files and not directly consumable by /vc-plan.
- **Fix**: Create WIP/tools-tests-review-review-c1.md per Task 009 action spec: read all 8 findings files, merge into structured document with Header, Executive Summary (counts by severity and category), Critical Findings, All Findings (organized A-F, deduplicated), Actionable Fix Plan (Phase 1: quick wins, Phase 2: DRY refactoring, Phase 3: structural changes, Phase 4: advanced improvements), Observations, and Decision Log.

## Medium Findings

### F-tools-tests-review-002 — B8 spec/ reference enumeration incomplete
- **File**: WIP/tools-tests-review-findings-test-structure.md:38
- **Severity**: medium
- **Category**: miss
- **Reference**: B8
- **Evidence**: `grep -rl "spec/" tests/` finds 12 files but only 7 are enumerated in B8 section: test_r9_validate.py, test_forward_replay_check.py, test_r9_cross_step.py, test_dependency_order_lint.py, integration/test_step_11.py, integration/test_v2_migration.py, conftest.py
- **Detail**: B8 verify criterion #4 requires "spec/ references are enumerated with breakage analysis." Five files are missing from the enumeration: test_seed_propagation_trim.py, test_forward_replay_submodule.py, test_migration_planner.py, test_gap_remediation.py, and test_r9_cli.py. Without full enumeration, the breakage assessment for a spec/ relocation is incomplete.
- **Fix**: Add the 5 missing files to the B8 section with per-file analysis of how they reference spec/ and what would break if spec/ contents were relocated to tests/fixtures/.

## Low Findings
(none — all low findings are non-blocking and routed to Observations)

## Pass Confirmations

- **A1** (command dispatch): 25 subcommands and flat grouping assessment verified — `WIP/tools-tests-review-findings-cli-package.md:11`
- **A2** (separation of concerns): 5 specific handlers mixing concerns identified with line ranges — `WIP/tools-tests-review-findings-cli-package.md:19`
- **A5** (entry point & wrapper): run_specdev.sh, pyproject.toml entry point, init_project.py all covered — `WIP/tools-tests-review-findings-cli-package.md:43`
- **A7** (dependency management): requirements.txt floor pins, dual setup.py/pyproject.toml documented — `WIP/tools-tests-review-findings-cli-package.md:57`
- **A4/E3** (configuration centralization): os.getenv scatter quantified — 7 env vars, 12 call sites, 3 files with per-file counts — `WIP/tools-tests-review-findings-config-imports.md:12`
- **A6** (import hygiene): re-exports and circular import risk assessment present — `WIP/tools-tests-review-findings-config-imports.md:99`
- **A8** (error handling): full chain traced validators → validate.py → cli.py — `WIP/tools-tests-review-findings-config-imports.md:139`
- **A9** (logging): 118 print() calls across 4 files, 1 file with logging import — `WIP/tools-tests-review-findings-config-imports.md:35`
- **F6** (environment assumptions): bare subprocess calls, git assumptions, CI behavior documented — `WIP/tools-tests-review-findings-config-imports.md:240`
- **C1** (error collection): validate() vs iter_errors() patterns documented per module — `WIP/tools-tests-review-findings-validation-arch.md:10`
- **C2** (error code registry): 52 E-codes, 25 W-codes (77 total) verified — `WIP/tools-tests-review-findings-validation-arch.md:21`
- **C3** (severity system): W/E code consistency checks present — `WIP/tools-tests-review-findings-validation-arch.md:32`
- **C4** (layered validation): separation analysis present — `WIP/tools-tests-review-findings-validation-arch.md:43`
- **C7** (W→E promotion): 18 PROMOTABLE_PAIRS, centralized at validate.py:267-289 — `WIP/tools-tests-review-findings-validation-arch.md:53`
- **E2** (error message duplication): cross-module duplication analysis present — `WIP/tools-tests-review-findings-validation-arch.md:63`
- **E6** (linter pattern duplication): ~143 LOC extractable shared patterns identified — `WIP/tools-tests-review-findings-validation-arch.md:75`
- **C5/E1** (cross-step ID resolution): 14 validators, 24 load functions, ~408 duplicated LOC — `WIP/tools-tests-review-findings-validators-dry.md:21`
- **C6** (determinism): 18 unsorted os.listdir sites, dict/set iteration checked — `WIP/tools-tests-review-findings-validators-dry.md:148`
- **E5** (schema loading): 26 direct json.load calls across 13 files vs 2 registry users — `WIP/tools-tests-review-findings-validators-dry.md:189`
- **F1** (magic numbers): categorized as intentional vs problematic with override mechanisms — `WIP/tools-tests-review-findings-hardcoded.md:10`
- **F3** (schema URI): hardcoded vs registry usage clearly documented — `WIP/tools-tests-review-findings-hardcoded.md:30`
- **F4** (step ordering): hardcoded step lists vs step_order.json systematically identified — `WIP/tools-tests-review-findings-hardcoded.md:40`
- **B1** (directory structure): 51 .py files in tests/ root, flat structure confirmed — `WIP/tools-tests-review-findings-test-structure.md:1`
- **B2** (R9 test duplication): all 10 test_r9_*.py files with per-file unique-vs-duplicated analysis — `WIP/tools-tests-review-findings-test-structure.md:1`
- **B6** (test markers): B6 criterion covered — finding documents that no @pytest.mark.unit or @pytest.mark.integration markers exist; only @pytest.mark.parametrize appears in 4 files; impact on CI test tiering analysed — `WIP/tools-tests-review-findings-test-structure.md:32-34`
- **E4** (test helper duplication): conftest hierarchy and 4 helper duplication categories identified — `WIP/tools-tests-review-findings-test-structure.md:1`
- **B3** (parametrization): 40-60 functions reducible to ~15 parametrized, 8 usages across 736 functions — `WIP/tools-tests-review-findings-test-quality.md:1`
- **B4** (fixture management): all function-scope, no session/module, 130 ad-hoc fixtures — `WIP/tools-tests-review-findings-test-quality.md:1`
- **B5** (test-to-code ratio): 7 uncovered modules identified, 1.33:1 ratio — `WIP/tools-tests-review-findings-test-quality.md:1`
- **B7** (assertion quality): 4 weak assertion patterns, majority strong — `WIP/tools-tests-review-findings-test-quality.md:1`
- **D1** (two-tier testing): gap identified with pyproject.toml and CI analysis — `WIP/tools-tests-review-findings-pipeline.md:11`
- **D2** (property-based fixtures): specific fixture directories identified — `WIP/tools-tests-review-findings-pipeline.md:17`
- **D3** (token efficiency): expensive tests: subprocess spawning, real git repos — `WIP/tools-tests-review-findings-pipeline.md:21`
- **D4** (spec drift detection): layered detection patterns assessed — `WIP/tools-tests-review-findings-pipeline.md:27`
- **D5** (declarative rules): candidate linters evaluated, existing pattern noted — `WIP/tools-tests-review-findings-pipeline.md:33`
- **D6** (golden file testing): absence documented, trace_matrix.json as CI artifact — `WIP/tools-tests-review-findings-pipeline.md:39`

## Observations

- F-tools-tests-review-003 | medium | FINDING record format varies across files — some use 6-field pipe-delimited, others use markdown sections, instead of 13-field pipe-delimited format per plan Reference Patterns. Content is present and accurate; format standardization is cosmetic for this audit phase since downstream consumption is via Task 009 consolidation.
- F-tools-tests-review-004 | low | A3 package layout analysis omits migration/ subpackage (3 modules, 804 LOC). Covered indirectly through other criteria.
- F-tools-tests-review-005 | low | F2 path assumptions lack systematic deployment context matrix across standalone, submodule with --repo-root, and submodule with --spec-root/--git-root modes.
- F-tools-tests-review-006 | low | F5 hallucinated references does not distinguish R1-R9 intentional additions from actual hallucinations as required by plan.
- F-tools-tests-review-007 | low | B6 claims "4 files" use @pytest.mark but only 3 unique files confirmed — double-counts test_invariants.py (appears at lines 86 and 156).
- F-tools-tests-review-008 | low | B4-01 states 5 fixtures in conftest.py but actual count is 6 — omits migration_prompts_root.

## Actionable Fix Plan

This section uses the exact format that /vc-parallel-fix parses.
Each fix maps to one file. One file appears in at most one task.
Group by parallel execution order.

### Group 1 — Independent fixes

Task 1:
  file: WIP/tools-tests-review-findings-test-structure.md
  reads: tests/test_seed_propagation_trim.py, tests/test_forward_replay_submodule.py, tests/test_migration_planner.py, tests/test_gap_remediation.py, tests/test_r9_cli.py
  action: Fix F-tools-tests-review-002: Add the 5 missing files to the B8 section. For each file, document how it references spec/ (import path, string literal, or fixture path), what specific content it depends on, and what would break if spec/ were relocated to tests/fixtures/. Insert the new entries into the existing B8 finding's file enumeration list, maintaining the same format as the existing 7 entries.
  test_gate: none
  depends_on: none
  parallel_group: 1
  source: F-tools-tests-review-002

### Group 2 — Consolidated report assembly (depends on Group 1)

Task 2:
  file: WIP/tools-tests-review-review-c1.md
  reads: WIP/tools-tests-review-findings-cli-package.md, WIP/tools-tests-review-findings-config-imports.md, WIP/tools-tests-review-findings-validation-arch.md, WIP/tools-tests-review-findings-validators-dry.md, WIP/tools-tests-review-findings-hardcoded.md, WIP/tools-tests-review-findings-test-structure.md, WIP/tools-tests-review-findings-test-quality.md, WIP/tools-tests-review-findings-pipeline.md
  action: Fix F-tools-tests-review-001: Create the consolidated findings report. Read all 8 category findings files and merge into a single document with: (1) Header with title, topic, date, source goal doc, audit scope summary; (2) Executive Summary with total finding counts by severity and by category A-F, key themes, top 5 most impactful findings; (3) Critical Findings section with all critical and high severity findings organized by theme; (4) All Findings section with every FINDING and PASS record organized by category A through F, deduplicated by file:line; (5) Actionable Fix Plan with phased grouping — Phase 1: quick wins (hardcoded values, magic numbers), Phase 2: DRY refactoring (validator dedup, linter patterns), Phase 3: structural changes (CLI split, test reorganization), Phase 4: advanced improvements (property-based testing, declarative rules); (6) Observations section; (7) Empty Decision Log. Preserve all file:line references from source findings. The report must be directly consumable by /vc-plan.
  test_gate: none
  depends_on: 1
  parallel_group: 2
  source: F-tools-tests-review-001

## Test Baseline
- **Test count**: 830
- **Passed**: 830 | **Failed**: 0 | **Skipped**: 0
- **Command**: `pytest tests/`

## Next Steps

Run /vc-parallel-fix WIP/tools-tests-review-impl-review-c1.md to fix 2 blocking findings.

## Decision Log
