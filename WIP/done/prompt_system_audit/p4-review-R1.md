# P4 Fix Plan Review -- Round 1

**Date**: 2026-03-20
**Reviewer**: Deep Review Agent (R1)
**Document reviewed**: p4-out-fix-plan.md (85 tasks, 11 batches: 0a-0c, 1-8)
**Reference**: p3-out-master-findings-v2.md (101 findings)

---

## A. Finding Coverage

### A.1 Systematic AUDIT ID Coverage Check

All 101 AUDIT IDs (001-101) have been accounted for. The plan addresses them through:

- **Tasks with explicit "Addresses" lines**: 97 findings appear in at least one task's "Addresses" field.
- **N/A section**: AUDIT-036, 063, 065, 100 listed as no-action. (See A.2 for issue with this.)
- **Multi-batch findings**: AUDIT-006, 008, 015, 040, 053, 071 correctly appear across multiple batches with clear delineation.

### A.2 N/A Section Lists 4 Findings but Master Says 3 [Important]

The master findings Batch Summary table (line 1382) lists 3 N/A findings: AUDIT-036, 063, 065. The fix plan's N/A section (line 963-970) lists 4: AUDIT-036, 063, 065, **100**.

However, AUDIT-100 IS addressed by Task 3-03 (canon-accept CLI) -- the "Addresses" line on Task 3-03 says "AUDIT-073, AUDIT-100". So AUDIT-100 appears in BOTH a task AND the N/A list. This is contradictory. The master findings place AUDIT-100 in Batch 3 (line 1376). The N/A entry should be removed.

### A.3 Execution Summary Task Counts vs Actual Tasks [Minor]

The Execution Summary table (line 12-24) says:
- Batch 1: 8 tasks. Actual tasks: 1-01 through 1-10 = **10 tasks**. Table is wrong.
- Batch 7: 11 tasks. Actual tasks: 7-01 through 7-12 = **12 tasks**. Table is wrong.
- Batch 4: 15 tasks. Actual tasks: 4-01 through 4-15 = 15. Correct.
- Total stated: 85 tasks. Actual count: 5 + 14 + 1 + 10 + 5 + 5 + 15 + 7 + 4 + 12 + 10 = **88 tasks**. Statement says 85.

The Execution Checklist at the bottom (lines 1027-1039) also says "10 config/bug fix tasks" for Batch 1 and "12 validator/lint tasks" for Batch 7, contradicting the summary table.

### A.4 Batch 2 AUDIT-036 in Addresses Line [Minor]

Task 2-02 lists "AUDIT-006, AUDIT-036" in Addresses. AUDIT-036 is N/A (subsumed by AUDIT-026). While Task 2-02 does implement the fix that subsumes AUDIT-036, listing a subsumed finding in a task's Addresses line is confusing. It should reference AUDIT-026 instead.

### A.5 Master Findings Batch Assignments vs Fix Plan Batch Assignments

Verified cross-reference between master findings Batch Summary table and fix plan:

- **Batch 0 (18)**: Master lists AUDIT-014, 015(schema), 051, 052, 053, 054, 055, 057, 066, 071, 075, 084, 086, 008(schema), 040(schema), 041, 042, 043. All present in 0a/0b/0c tasks. Correct.
- **Batch 1 (7)**: Master lists AUDIT-017, 023, 035, 069, 076, 082, 088. All present in Batch 1 tasks. Correct.
- **Batch 2 (7)**: Master lists AUDIT-002, 006(extraction), 007, 018, 026, 091, 101. All addressed in Tasks 2-01 through 2-05. Correct.
- **Batch 3 (6)**: Master lists AUDIT-072, 073, 074, 095, 096, 100. All present in Tasks 3-01 through 3-05. Correct.
- **Batch 4 (24)**: Master lists AUDIT-001, 003, 008(deletion), 016, 019, 027, 028, 029, 030, 031, 038, 039, 040(prompt), 044, 056, 058, 062, 079, 080, 081, 083, 085, 092, 097. All addressed across Tasks 4-01 through 4-15. Correct.
- **Batch 5 (6)**: Master lists AUDIT-004, 005, 013, 015(validation), 067, 068. All present. Correct.
- **Batch 6 (6)**: Master lists AUDIT-009, 010, 011, 012, 037, 050. All present. Correct.
- **Batch 7 (12)**: Master lists AUDIT-022, 024, 032, 033, 034, 070, 077, 078, 087, 093, 094, 098. All present. Correct.
- **Batch 8 (15)**: Master lists AUDIT-020, 021, 025, 045, 046, 047, 048, 049, 059, 060, 061, 064, 089, 090, 099. All present. Correct.

All batch assignments are faithful to the master findings.

---

## B. Task Specificity & Executability

### B.1 Task 0b-13 Is Too Large [Important]

Task 0b-13 covers 9 schemas (02a, 03, 08, 10, 11, 12, 13, 13a, 15) in a single task. The plan acknowledges this ("LARGE task. Consider splitting into 2-3 sub-tasks") but leaves the split as optional. For P5 execution with one-file-per-task rules, this MUST be split into 9 individual tasks (one per schema file).

### B.2 Task 0c-01 Is 17 File Edits Listed as 1 Task [Important]

Task 0c-01 lists 17 prompt files to edit but is a single task. The note says "split into individual sub-tasks (0c-01a through 0c-01q)" but this is presented as optional. For P5 execution, the split is mandatory. The plan should explicitly define these as 17 sub-tasks.

### B.3 Tasks 2-02, 2-03, 4-09, 4-10, 4-11, 6-01, 6-04 All Touch "All 22 Prompts" [Important]

Seven tasks each modify all 22 prompt files. The notes say "split per prompt file" but leave this as guidance. These are effectively 7 x 22 = 154 sub-tasks. The plan should state explicitly that each of these will be split for execution, or provide a strategy for how to batch them per-file (i.e., do all Batch 4 changes to a single prompt file in one sub-task).

### B.4 Task 2-01 Change Description Is Specific and Actionable [Good]

The shared_expectations.md redesign (Task 2-01) has 13 specific sections enumerated with content descriptions. This is well-specified.

### B.5 Task 1-05 Is 7 File Changes Listed as 1 Task [Minor]

Task 1-05 migrates 5 consumers plus deletes from 2 JSON/schema files. The note acknowledges splitting. For a cross-cutting change like this, the plan correctly identifies that ALL consumers must be migrated before the JSON deletion, but could be more explicit about the sub-task ordering.

### B.6 Task 4-13 Groups 4+ Distinct AUDIT Findings Into One Task [Minor]

Task 4-13 addresses AUDIT-040, 044, 056, 062 across multiple files with different changes per file. This works as a "fix Output Contracts" meta-task but should be split per-file for execution.

---

## C. Design Decision Compliance

All 13 locked design decisions verified against tasks:

1. **Schema sole owner (D1)**: Tasks 0b-*, 0c-01, 2-04 correctly enrich schemas first then delete prompt duplication. Compliant.
2. **Cross-step from DAG (D2)**: Task 2-01 adds cross-step relationships and conflict resolution to shared_expectations. Compliant.
3. **Delete allowed_upstream (D3)**: Tasks 1-04, 1-05 derive at runtime, delete JSON. Compliant.
4. **Universal pairwise (D4)**: Tasks 5-01 through 5-07 implement the full 5-transition chain. Compliant.
5. **No NL tooling (D5)**: Task 4-12 adds prompt guidance for verbatim text only. No semantic validators proposed. Compliant.
6. **Glossary to canon (D6)**: Tasks 3-01 through 3-04 build the full pipeline. Compliant.
7. **Seed blind spots misframed (D7)**: Tasks 4-01, 4-07 add prompt synthesis guidance, not seed template changes. Compliant.
8. **Don't steer (D8)**: No tasks reference this. Compliant (no violation).
9. **Schema before prompts (D9)**: Batch 0 (schema) precedes Batch 4 (prompts). Compliant.
10. **Self-Audit decomposition (D10)**: Tasks 6-01 through 6-04 implement the 3-concern split. Compliant.
11. **Three-tier DEPTH (D11)**: Tasks 0b-* use the Tier 1/2/3 model. Compliant.
12. **13a redesign (D12)**: Task 5-07 redesigns as machine-computed coverage. Compliant.
13. **Validity not completeness (D13)**: Tasks 5-01 through 5-06 use W-codes (warnings). Compliant.

No design decision violations found.

---

## D. Dependency Correctness

### D.1 Batch Dependencies Verified

The plan's dependency chain:

| Batch | Declared Dependencies | Verified |
|-------|----------------------|----------|
| 0a | None | Correct |
| 0b | 0a | Correct -- some 0b tasks reference 0a outputs (e.g., 0b-07 depends on 0a-01) |
| 0c | 0b | Correct -- Quick Reference deletion should follow schema enrichment |
| 1 | None | Correct -- config/bug fixes independent of schema work |
| 2 | 0b, 0c | Correct -- extraction needs enriched schemas and deleted Quick Reference |
| 3 | 2 | See D.2 below |
| 4 | 0b, 0c | Correct -- prompt enrichment follows schema enrichment |
| 5 | 4 | Correct -- validators complement prompt extraction mandates |
| 6 | 4 | Correct -- Self-Audit Gate restructure follows prompt content establishment |
| 7 | 0-6 | Correct -- incremental validator improvements |
| 8 | 0-7 | Correct -- docs reflect final state |

### D.2 Batch 3 Dependency on Batch 2 May Be Too Strict [Minor]

The Execution Summary says Batch 3 depends on Batch 2. However, the master findings (line 1394) note Batch 3 is "independent but enables canonical enforcement" and suggests it can run in parallel with Batch 2. The fix plan Tasks 3-01 through 3-05 have no actual dependency on shared_expectations.md (Batch 2). Only Task 3-04 (Step 03 prompt redesign) might benefit from shared_expectations existing, but it could proceed without it.

The master findings execution order (line 1393-1394) lists Batch 3 BEFORE Batch 2 and calls it "independent." The fix plan's Execution Summary table says Batch 3 depends on Batch 2. This contradicts the master findings.

**Fix**: Change Batch 3 dependency from "2" to "None" (or "0" if canon work needs schema enrichment).

### D.3 Hidden Intra-Batch Dependency in Batch 1 [Important]

Tasks 1-02 and 1-03 both declare dependency on Task 1-01 (lines 283, 289). Tasks 1-04 and 1-05 have a sequential dependency (1-05 depends on 1-04). Task 1-02 depends on 1-01. These are correctly noted within the tasks, but the batch description says "parallel with Batch 0" which could be misread as "all tasks in Batch 1 are parallel with each other." The within-batch dependencies should be called out more prominently.

### D.4 Execution Summary Dependency Column Inconsistent [Minor]

The Execution Summary table shows:
- Batch 4 depends on "0b, 0c" but Batch 4 tasks (e.g., 4-01) say "Dependencies: 0c, 2-03". Batch 2 is a missing dependency in the summary table for Batch 4.
- Batch 6 depends on "4" per the table, but Task 6-01 says "Dependencies: 2-01, 4-10". Batch 2 is also missing from the Batch 6 dependency.

The task-level dependencies are more accurate than the summary table.

---

## E. Codebase Accuracy (Hallucination Checks)

15 tasks spot-checked against the actual codebase:

### E.1 Task 0a-03: Charter required array -- VERIFIED
`schema/00_charter.schema.json` line 182: `required: ["problem_statement", "success_metrics", "stakeholders", "user_segments"]`. Fields `in_scope`, `out_of_scope`, `assumptions`, `risks` exist as properties in the schema. Task is accurate.

### E.2 Task 0a-04: Step 05 trace required -- VERIFIED
`schema/05_interface_contracts.schema.json` line 170: required array lacks `trace`. Task correctly identifies the gap. `trace` property exists in the API item schema.

### E.3 Task 0a-05: Owner atoms schema -- VERIFIED
`schema/core/atoms.schema.json` line 38-42: `owner` uses `pattern: "^[a-z][a-z0-9_-]*$"`. Task correctly proposes enum replacement.

### E.4 Task 1-05: Consumer files for allowed_upstream -- VERIFIED
All 5 consumer files exist: `cli.py`, `hallucination_lint.py`, `extraction_intent_check.py`, `dependency_order_lint.py`, `dag_lint.py`. `step_order.json` contains the `allowed_upstream` field. Task is accurate.

### E.5 Task 1-07: Step 16c enforcement bug -- VERIFIED
`step_16c.py` line 34: `semantic_review = review.get("semantic_review")` followed by `if isinstance(semantic_review, dict):`. Missing enforcement for verified verdict confirmed. Task fix is correct.

### E.6 Task 1-09: E304 milestone filtering -- VERIFIED
`step_16.py` lines 313-318: confirms set comprehension over ALL milestones. No `milestone_ref` filtering. Task correctly describes the bug and proposed fix.

### E.7 Task 7-02: seed_lint ordering vs membership -- VERIFIED
`seed_lint.py` around line 62: `global_required = set(manifest.get("global_seed_order", []))` followed by `required.update(global_required)`. This does union global seeds into step-specific requirements. Task correctly identifies the bug.

### E.8 Task 7-10: Step 13 pattern bug -- VERIFIED
`step_13.py` line 13: `_STEP_PATTERN = re.compile(r"^[0-9]{2}[a-z]?_")`. Used to validate `required_schema_sections`. Domain sections like "tables" would fail. Task is accurate.

### E.9 Task 2-01: shared_expectations.md location -- VERIFIED
File exists at `docs/prompts/shared_expectations.md`. Task correctly identifies it for redesign.

### E.10 Task 3-01: canon/README.md -- VERIFIED
`canon/README.md` does NOT exist. Task correctly proposes creating it.

### E.11 Task 7-12: forward_replay.py file path -- HALLUCINATION [Important]
Task 7-12 references `tools/specdev_tools/validation/forward_replay.py`. The actual file is `tools/specdev_tools/validation/forward_replay_check.py`. The "(or relevant module)" qualifier partially mitigates this, but the primary path is wrong.

### E.12 Task 7-05: matrix.py -- VERIFIED
`tools/specdev_tools/validation/matrix.py` exists. Task references "lines 170-305" which is within the file's scope (would need line-level verification for exact function, but file exists and is the right module).

### E.13 Task 8-02: constants.py -- VERIFIED
`tools/specdev_tools/core/constants.py` exists. Task references `STEP_TO_TEMPLATE` entries, which is correct per AUDIT-021.

### E.14 Task 5-04: traceability_closure.py -- VERIFIED
`tools/specdev_tools/validation/traceability_closure.py` exists. Correct location for pairwise checks.

### E.15 Task 8-06: workflow_bootstrap_legacy.md -- VERIFIED
`docs/developers/workflows/workflow_bootstrap_legacy.md` exists.

**Summary**: 14 of 15 spot-checks verified. 1 hallucination found (file path in Task 7-12).

---

## F. Completeness of Change Description

### F.1 Schema Tasks Are Well-Specified [Good]

Tasks 0a-01 through 0a-05 include exact JSON snippets, property paths, and line number references. These are executable as-is.

### F.2 Schema Description Enrichment Tasks Are Appropriately Scoped [Good]

Tasks 0b-01 through 0b-12 provide specific field lists with tier assignments and example descriptions. Task 0b-01 even includes full example description text. This is sufficient for an agent to execute without reading the finding.

### F.3 Task 2-01 Is Well-Specified With 13 Sections [Good]

The shared_expectations redesign lists all 13 sections with content summaries. An agent can execute this with the task description alone.

### F.4 Batch 4 Prompt Enrichment Tasks Vary in Specificity [Minor]

Tasks 4-01 through 4-04 (Steps 04-07) are detailed with specific phases, checklists, and examples. Tasks 4-07 and 4-08 are less specific ("Add step-specific reasoning phases to each" without enumerating). Tasks 4-05 and 4-06 are medium detail. The later tasks should include the same level of specificity as 4-01 for consistent execution quality.

### F.5 Task 5-07 Defers Blocking Gate Design [Acceptable]

Task 5-07 (13a redesign) correctly scopes to machine-computed coverage and defers gate enforcement per the Design Note. The schema changes are specified with field names and structure. This is a reasonable scope boundary.

### F.6 Task 1-09 Proposed Fix Has a Logic Gap [Important]

Task 1-09 proposes filtering by `milestone_ref`, but the fix code snippet filters with `if milestone_ref and mid != milestone_ref: continue`. If `milestone_ref` is empty/absent (which is possible for the first Trinity Loop cycle), the filter falls through and collects ALL tasks -- the same bug as before. The fix should handle the case where `milestone_ref` is absent. Consider: if `milestone_ref` is absent, filter by milestone status instead (only include non-"done" milestones).

---

## G. Test Gate Quality

### G.1 All Test File Paths Verified [Good]

Every test file referenced in test gates exists in the codebase:
- `tests/integration/test_step_*.py` for steps 00, 05, 09, 14, 16 -- all exist
- `tests/unit/generation/test_prompt_contracts.py` -- exists
- `tests/unit/generation/test_prompt_schema_sync.py` -- exists
- `tests/unit/canonical/` tests -- exist
- `tests/unit/migration/test_migration_templates.py` -- exists
- `tests/unit/validation/linters/test_seed_*.py` -- exist

### G.2 Batch 4 Tasks Over-Rely on test_prompt_contracts.py [Minor]

14 of 15 Batch 4 tasks use `test_prompt_contracts.py` as their sole test gate. If this test checks structural contracts (required sections, headings), it may not catch quality issues in the added synthesis reasoning content. The test gate is necessary but may be insufficient for detecting regressions in prompt effectiveness.

### G.3 Manual Verification Test Gates in Batch 8 [Acceptable]

Tasks 8-03, 8-05, 8-06, 8-07, 8-09 use "Manual verification" as test gates. These are documentation tasks where automated testing is impractical. Acceptable for INFO/LOW findings.

### G.4 Task 1-05 Full Test Suite Gate Is Appropriate [Good]

Task 1-05 (cross-cutting consumer migration) uses `pytest tests/ -v` (full suite). This is correct for a change that touches 5+ consumer files.

### G.5 Missing Test Gate for New Test Files [Minor]

Tasks that create new test fixtures (0a-03 mentions adding `invalid_missing_scope.json`, 1-07 mentions `invalid_verified_no_semantic_review.json`) should verify these new fixtures are actually tested by existing test infrastructure. The test gates run existing tests but don't confirm the new fixtures are discovered.

---

## H. Risk Assessment

### H.1 Risk Register Is Comprehensive [Good]

The 8 identified risks (R1-R8) cover the major concerns: Batch 0b scope creep, breaking changes, shared_expectations extraction complexity, pairwise completeness scope, blocking gate infrastructure, prompt quality, test stability, and host repo compatibility.

### H.2 Missing Risk: Prompt Test Contract Fragility [Important]

Many tasks in Batches 2, 4, and 6 will substantially restructure prompts (delete sections, add new sections, rename headings). If `test_prompt_contracts.py` checks for specific section headings or structural patterns, these tests will break during execution. The plan doesn't identify which prompt contracts will need updating as part of the restructuring, and doesn't identify a task for updating the test expectations.

This is a meta-risk: the test gates themselves may need modification as part of the task, but the tasks don't mention this. Each prompt restructuring task should include "update test expectations if prompt contracts check for section headings."

### H.3 Missing Risk: Batch 0a Breaking Changes Stack [Minor]

Three breaking changes in Batch 0a (charter required fields, Step 05 trace required, owner enum) are all in separate tasks. If a host repo runs the toolkit after one but not all three are applied, they get partial breakage. The plan correctly suggests bundling into version 0.5.0 (R8), but doesn't explicitly state that ALL three must be applied together.

### H.4 Missing Risk: Step 13a Validator May Not Exist Yet [Minor]

Task 5-07 references `tools/specdev_tools/validation/validators/step_13a.py` for modification. The file exists, but the task proposes a substantial redesign (replacing subjective scoring with structured coverage). If the existing validator has consumers or tests that depend on current behavior, the redesign could break them. The task should mention checking existing test fixtures at `tests/fixtures/step_13a/` (if they exist) and updating them.

---

## I. Scope Creep / Gold Plating

### I.1 Task 3-02 Proposes Three Alternatives Without Choosing [Minor]

Task 3-02 (move auth-domain canon entries) lists three options (a/b/c) and says "Preferred: option (a)." This is fine for documentation but the task should commit to one option for execution clarity.

### I.2 Task 0a-05 Leaves Enum vs Regex Unresolved [Minor]

Task 0a-05 says "Prefer enum for strictness; host repos can override atoms.schema.json if needed" but then adds "Alternatively, keep the regex for extensibility and add `examples` array instead." The implementation note suggests enum, but the hedge language may confuse the executor. The task should make a firm decision.

### I.3 No Scope Creep Detected [Good]

All tasks trace to specific AUDIT findings. No tasks introduce features beyond what findings require. The plan maintains focus on the audit findings and locked design decisions.

---

## J. Gaps and Missing Tasks

### J.1 No Task for Updating test_prompt_contracts.py Expectations [Important]

After Batches 0c, 2, 4, and 6 restructure all 22 prompts (deleting Quick Reference, deleting Field-by-Field, adding Negative Constraints, restructuring Self-Audit Gate, adding inheritance references), the prompt contracts tests will likely need updated expectations. No task addresses this.

**Fix**: Add a task (or sub-task per batch) to update `tests/unit/generation/test_prompt_contracts.py` expectations after each major prompt restructuring phase.

### J.2 No Task for Updating test_prompt_schema_sync.py After Schema Enrichment [Minor]

After Batch 0b enriches schema descriptions and Batch 2 deletes schema-duplicated content from prompts, the prompt-schema sync test may need adjustment. No task mentions this.

### J.3 No Changelog Entry Task [Minor]

Multiple tasks note "Changelog entry required" (0a-03, 0a-04, 0a-05, 1-01) but no task is dedicated to writing the changelog. This could be a Batch 8 documentation task or a continuous task per breaking change. The plan should clarify when and how changelog entries are written.

### J.4 Missing Task for step_order.schema.json Update After allowed_upstream Removal [Minor]

Task 1-05 mentions "Update `schema/step_order.schema.json` to remove the field" as part of the consumer migration. This should be called out as a specific sub-task since it's a schema file modification, not a Python file modification.

### J.5 Task 8-09 References docs/ops/adr_template_engine.md Correctly [Verified]

File exists at `docs/ops/adr_template_engine.md`. No gap.

---

## Summary

| Category | Issues Found | Critical | Important | Minor |
|----------|-------------|----------|-----------|-------|
| A. Finding Coverage | 4 | 0 | 1 | 3 |
| B. Task Specificity | 6 | 0 | 3 | 3 |
| C. Design Decisions | 0 | 0 | 0 | 0 |
| D. Dependencies | 4 | 0 | 1 | 3 |
| E. Codebase Accuracy | 1 | 0 | 1 | 0 |
| F. Change Description | 2 | 0 | 1 | 1 |
| G. Test Gate Quality | 3 | 0 | 0 | 3 |
| H. Risk Assessment | 3 | 0 | 1 | 2 |
| I. Scope Creep | 2 | 0 | 0 | 2 |
| J. Gaps | 4 | 0 | 1 | 3 |
| **Total** | **29** | **0** | **9** | **20** |

---

## Important Issues (Must Fix Before P5)

1. **A.2**: Remove AUDIT-100 from N/A section (it's addressed by Task 3-03).
2. **A.3**: Fix Execution Summary task counts: Batch 1 = 10 (not 8), Batch 7 = 12 (not 11), Total = 88 (not 85).
3. **B.1**: Split Task 0b-13 into 9 individual tasks (one per schema file).
4. **B.2**: Explicitly define Task 0c-01 as 17 sub-tasks.
5. **B.3**: Clarify that multi-file tasks (2-02, 2-03, 4-09, 4-10, 4-11, 6-01, 6-04) WILL be split per-file for execution (not "consider splitting").
6. **D.3**: Call out within-Batch-1 dependencies more prominently (1-02/1-03 depend on 1-01; 1-05 depends on 1-04).
7. **E.11**: Fix Task 7-12 file path from `forward_replay.py` to `forward_replay_check.py`.
8. **F.6**: Fix Task 1-09 logic gap for absent `milestone_ref`.
9. **H.2 / J.1**: Add task(s) for updating `test_prompt_contracts.py` expectations after prompt restructuring batches.

---

## Verdict

**The plan is solid and nearly ready for P5 execution.** The 9 Important issues are all fixable in a single editing pass (15-20 minutes). No Critical issues were found. The plan demonstrates:

- Complete coverage of all 101 AUDIT findings
- Full compliance with all 13 locked design decisions
- Accurate codebase references (14/15 spot-checks verified)
- Well-specified schema tasks with exact JSON snippets
- Sound batch dependency ordering
- Comprehensive risk register

The primary structural concern is the gap between "tasks as documented" (85-88 high-level tasks) and "tasks for execution" (~200+ atomic sub-tasks after splitting multi-file tasks). The plan acknowledges this via notes but should make the split mandatory rather than optional.

**Recommendation**: Fix the 9 Important issues, then proceed to P5 execution. No R2 review round is needed unless the fixes introduce new structural changes.
