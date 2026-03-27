# P4 Fix Plan Review -- Round 3

**Date**: 2026-03-20
**Reviewer**: Deep Review Agent (R3)
**Document reviewed**: p4-out-fix-plan.md (96 tasks, 11 batches: 0a-0c, 1-8)
**Prior reviews**: R1 (29 issues: 9 important, 20 minor), R2 (5 minor -- all fixed)

---

## Prior Fix Verification

### R1 Important Fixes (9)

| # | R1 Issue | Status | Verification |
|---|----------|--------|--------------|
| 1 | A.2: AUDIT-100 in N/A section | VERIFIED | N/A section (lines 1023-1029) lists only AUDIT-036, 063, 065. AUDIT-100 appears only in Task 3-03 Addresses line (line 534). |
| 2 | A.3: Task counts wrong | VERIFIED | Summary table: Batch 0b=22, Batch 1=10, Batch 7=12, Total=96. Counted actual `### Task` headings: 5+22+1+10+5+5+15+7+4+12+10=96. All match. |
| 3 | B.1: Task 0b-13 too large | VERIFIED | Old 0b-13 split into 0b-13 (02a), 0b-14 (03), 0b-15 (08), 0b-16 (10), 0b-17 (11), 0b-18 (12), 0b-19 (13), 0b-20 (13a), 0b-21 (15). Nine individual one-file tasks. |
| 4 | B.2: Task 0c-01 split optional | VERIFIED | Line 315 says "MUST be split into 17 sub-tasks (0c-01a through 0c-01q)". |
| 5 | B.3: Multi-file tasks hedge language | VERIFIED | Line 26 uses "MUST be split" and lists all 11 multi-file tasks (0c-01, 2-02, 2-03, 2-04, 4-07, 4-08, 4-09, 4-10, 4-11, 6-01, 6-04). |
| 6 | D.3: Batch 1 internal deps | VERIFIED | Summary table Batch 1 row (line 17) says "Internal deps: 1-02/1-03 depend on 1-01; 1-05 depends on 1-04". |
| 7 | E.11: Task 7-12 wrong file path | VERIFIED | Task 7-12 (line 932) references `forward_replay_check.py`. File confirmed to exist at `tools/specdev_tools/validation/forward_replay_check.py`. |
| 8 | F.6: Task 1-09 logic gap | VERIFIED | Task 1-09 (lines 400-421) includes `else` branch filtering by milestone status `("done", "completed")` when `milestone_ref` is absent. |
| 9 | H.2/J.1: Prompt contract test fragility | VERIFIED | Risk R7 (lines 1074-1077) added with mitigation requiring each restructuring task to update test expectations. |

**All 9 important R1 fixes correctly applied.**

### R2 Minor Fixes (5)

| # | R2 Issue | Status | Verification |
|---|----------|--------|--------------|
| N-1 | 0b-14a numbering gap | VERIFIED | Tasks now numbered sequentially: 0b-13 (02a), 0b-14 (03), 0b-15 (08), etc. No "0b-14a" in the document. |
| N-2 | AUDIT-036 in Batch 2 summary | VERIFIED | Batch 2 summary row (line 18) lists "AUDIT-002, 006(extract), 007, 018, 026, 091, 101". AUDIT-036 removed. |
| N-3 | 0c dependency says 0a | VERIFIED | Batch 0c summary row (line 16) now says dependency "0b". Matches Task 0c-01 dependency (line 314). |
| N-4 | 4-07, 4-08 not in split list | VERIFIED | Line 26 includes both 4-07 and 4-08 in the mandatory split parenthetical. |
| N-5 | Task 2-04 approximate file count | VERIFIED | Task 2-04 (line 491) now lists all 18 files explicitly. No "~" approximation. |

**All 5 R2 minor fixes correctly applied.**

---

## A. Coverage Completeness

### A.1 All 101 AUDIT IDs Present

Extracted all unique `AUDIT-NNN` references from the fix plan: 101 unique IDs found. Every ID from AUDIT-001 through AUDIT-101 is present.

- **98 findings** in task Addresses lines or inline task change descriptions
- **3 findings** in N/A section: AUDIT-036 (subsumed by 026), AUDIT-063 (already purged), AUDIT-065 (INFO implemented via 006)
- N/A rationales match master findings

### A.2 Master Findings Batch Assignments Verified

Cross-referenced master findings Batch Summary table (p3 lines 1371-1382) against fix plan:

| Batch | Master Findings Count | Fix Plan Tasks | Match |
|-------|----------------------|----------------|-------|
| 0 (0a+0b+0c) | 18 | 28 tasks (5+22+1) | Yes -- findings split across sub-batches |
| 1 | 7 | 10 tasks | Yes -- some findings have multiple tasks (AUDIT-017: 3 tasks, AUDIT-023: 2 tasks) |
| 2 | 7 | 5 tasks | Yes -- some tasks address multiple findings |
| 3 | 6 | 5 tasks | Yes |
| 4 | 24 | 15 tasks | Yes -- many tasks address 2-4 findings each |
| 5 | 6 | 7 tasks | Yes |
| 6 | 6 | 4 tasks | Yes |
| 7 | 12 | 12 tasks | Yes -- 1:1 mapping |
| 8 | 15 | 10 tasks | Yes -- some tasks bundle related findings |
| N/A | 3 | 3 | Yes |

All batch assignments faithfully match master findings.

### A.3 AUDIT-029 Not in Any Addresses Line [Minor]

AUDIT-029 (Weak-vs-Strong Examples) appears in Batch 4 summary range "027-031" and is referenced inline within Tasks 4-01 through 4-05 change descriptions. However, it does NOT appear in any task's "Addresses" line. This was noted by R2 (H.4) as "adequate" since the coverage is traceable through inline references. The finding is implemented by five tasks that each add weak-vs-strong example tables, but none claims sole ownership.

This is a minor traceability gap: automated tooling searching "Addresses" lines would miss AUDIT-029. Adding it to Task 4-01's Addresses line (as the primary implementor with the most detailed example table) would close this gap.

### A.4 Multi-Batch Findings Cross-Reference Table Verified

The 6 multi-batch findings (lines 1033-1044) are correct:
- AUDIT-006: Batch 0 (schema/deletion) + Batch 2 (extraction). Verified.
- AUDIT-008: Batch 0c (Quick Reference) + Batch 4 (Field-by-Field). Verified.
- AUDIT-015: Batch 0a (schema) + Batch 5 (validation). Verified.
- AUDIT-040: Batch 0b (schema descriptions) + Batch 4 (prompt fix). Verified.
- AUDIT-053: Batch 0b (description) + Batch 3 (consolidation). Verified.
- AUDIT-071: Batch 0b (all schemas) + Batch 4 (prompts reference). Verified.

---

## B. Batch Dependency Validation

### B.1 Dependency Chain

| Batch | Declared Dependencies | Acyclic | Correct |
|-------|----------------------|---------|---------|
| 0a | None | Yes | Yes |
| 0b | 0a | Yes | Yes -- 0b-01, 0b-04, 0b-07, 0b-08, 0b-10 depend on 0a structural changes |
| 0c | 0b | Yes | Yes -- Quick Reference deletion requires enriched schema descriptions (Decision 9) |
| 1 | None | Yes | Yes -- config/bug fixes independent of schema work |
| 2 | 0b, 0c | Yes | Yes -- extraction needs enriched schemas and deleted Quick Reference |
| 3 | 0 | Yes | Yes -- independent per master findings line 1394 |
| 4 | 0b, 0c, 2 | Yes | Yes -- prompt enrichment follows extraction |
| 5 | 4 | Yes | Yes -- validators complement extraction mandates |
| 6 | 2, 4 | Yes | Yes -- Self-Audit Gate restructure follows prompt content establishment |
| 7 | 0-6 | Yes | Yes -- incremental improvements |
| 8 | 0-7 | Yes | Yes -- docs reflect final state |

No cycles. Dependency chain is sound.

### B.2 Intra-Batch Dependencies Verified

Key intra-batch dependencies documented in the plan:
- **Batch 0b**: Tasks 0b-01, 0b-04, 0b-07, 0b-08, 0b-10 depend on specific 0a tasks. Correct.
- **Batch 1**: 1-02/1-03 depend on 1-01; 1-05 depends on 1-04. Correct per task-level dependency lines.
- **Batch 2**: 2-02 depends on 2-01; 2-03 depends on 2-01, 2-02; 2-04 depends on 0b, 0c, 2-01; 2-05 depends on 2-01. Correct.
- **Batch 3**: 3-02 depends on 3-01; 3-03 depends on 3-01; 3-04 depends on 3-01, 3-03. Correct.
- **Batch 5**: 5-04 depends on 0a-02; 5-05 depends on 1-07, 1-09; 5-06 depends on 5-01 to 5-04; 5-07 depends on 5-01 to 5-06. Correct serial chain.
- **Batch 6**: 6-02, 6-03, 6-04 depend on 6-01. Correct.
- **Batch 8**: 8-04 depends on 8-01, 8-02; 8-08 depends on 8-01. Correct.

No task depends on a task in a later batch. No hidden dependency violations detected.

### B.3 Multi-File Task "MUST be split" List Completeness

The 11 tasks in the mandatory split declaration (line 26): 0c-01, 2-02, 2-03, 2-04, 4-07, 4-08, 4-09, 4-10, 4-11, 6-01, 6-04. Each of these tasks lists the exact files and specifies split into sub-tasks within the task description. Verified.

---

## C. Design Decision Compliance

All 13 locked design decisions verified:

| # | Decision | Compliance | Verification |
|---|----------|-----------|-------------|
| D1 | Schema sole owner | Compliant | Batch 0b enriches schemas; 0c/2-04 delete prompt duplication |
| D2 | Cross-step from DAG | Compliant | Task 2-01 adds conflict resolution and cross-step directive to shared_expectations (sections 11, 13) |
| D3 | Delete allowed_upstream | Compliant | Tasks 1-04 (derive), 1-05 (migrate + delete) |
| D4 | Universal pairwise | Compliant | Tasks 5-01 through 5-05 implement 5-transition chain |
| D5 | No NL tooling | Compliant | Task 4-12 adds prompt guidance for verbatim text only |
| D6 | Glossary to canon | Compliant | Tasks 3-01 through 3-04 build full pipeline |
| D7 | Seed blind spots misframed | Compliant | Tasks 4-01, 4-07 enrich prompts, not seed templates |
| D8 | Don't steer | Compliant | No violations found |
| D9 | Schema before prompts | Compliant | Batch 0 (schema) precedes Batch 4 (prompts) via dependency chain |
| D10 | Self-Audit decomposition | Compliant | Tasks 6-01 through 6-04 implement 3-concern split (threshold, gating items, coverage) |
| D11 | Three-tier DEPTH | Compliant | 0b tasks use Tier 1/2/3 model; 0b-01 shows examples |
| D12 | 13a redesign | Compliant | Task 5-07 redesigns as machine-computed coverage with structured dimensions |
| D13 | Validity not completeness | Compliant | Tasks 5-01 through 5-06 use W-codes (warnings) |

No design decision violations found.

---

## D. Codebase Spot-Checks

12 spot-checks performed against the actual codebase:

| # | Task | Claim | Result |
|---|------|-------|--------|
| 1 | 0c-01 | 17 prompts have Quick Reference | VERIFIED: `grep "Quick Reference" prompts/` found exactly 17 matches across 17 files. All 17 files listed in Task 0c-01 confirmed. |
| 2 | 2-04 | 18 prompts have Field-by-Field | VERIFIED: `grep "Field-by-Field" prompts/` found 18 files. All 18 listed in Task 2-04 match. |
| 3 | 1-07 | step_16c.py semantic_review bug | VERIFIED: Lines 34-35 show `semantic_review = review.get("semantic_review")` then `if isinstance(semantic_review, dict):`. Missing enforcement for verified verdict confirmed. |
| 4 | 1-08 | prompt_16c "rejected" verdict mismatch | VERIFIED: Line 134 shows "rejected" in prompt; validator line 13 has `VALID_VERDICTS = frozenset({"verified", "needs_work", "blocked", "deferred"})` -- "rejected" absent. |
| 5 | 1-09 | step_16.py E304 bug at lines 313-318 | VERIFIED: Lines 313-317 show set comprehension iterating all milestones without filtering by milestone_ref. |
| 6 | 1-05 | 5 consumer files for allowed_upstream | VERIFIED: grep found exactly 5 files: cli.py, hallucination_lint.py, extraction_intent_check.py, dependency_order_lint.py, dag_lint.py. |
| 7 | 1-06 | nested_order in seed_manifest | VERIFIED: Found in both `spec/common/seed_manifest.json` and `schema/seed_manifest.schema.json`. |
| 8 | 7-10 | step_13.py pattern at line 13 | VERIFIED: `_STEP_PATTERN = re.compile(r"^[0-9]{2}[a-z]?_")` confirmed at line 13. |
| 9 | 7-12 | forward_replay_check.py | VERIFIED: File exists at `tools/specdev_tools/validation/forward_replay_check.py`. |
| 10 | 3-01 | canon/README.md does not exist | VERIFIED: File does not exist. Task correctly proposes creation. |
| 11 | 8-10 | future_extensions.md does not exist | VERIFIED: File does not exist. Task correctly proposes creation. |
| 12 | 8-02 | STEP_TO_TEMPLATE in constants.py | VERIFIED: `constants.py` line 15 has `STEP_TO_TEMPLATE` dict mapping step IDs to template filenames. |

**12/12 spot-checks verified. Zero hallucinations detected.**

Additional verifications:
- 22 prompt files exist (confirmed via `ls prompts/prompt_*.md | wc -l`)
- 19 migration template files exist (confirmed)
- `docs/prompts/shared_expectations.md` exists at the path referenced by Task 2-01
- `docs/ops/adr_template_engine.md` exists (Task 8-08)
- `docs/developers/workflows/workflow_feature_extension.md` exists (Task 8-07)
- `docs/developers/workflows/workflow_bootstrap_legacy.md` exists (Task 8-06)

---

## E. Hallucination Detection

No hallucinations found. Every file path referenced in the plan either:
1. Exists in the codebase at the stated path, or
2. Is explicitly marked as a new file to create (canon/README.md, canon/examples/auth_demo.json, canonical/accept.py, future_extensions.md, 3 new migration templates)

Code behavior descriptions (step_16c.py bug, step_16.py E304 bug, step_13.py pattern, seed_lint.py global_required expansion) all confirmed against actual source code.

---

## F. Internal Consistency

### F.1 Math Checks

- Total tasks: 5+22+1+10+5+5+15+7+4+12+10 = 96. Matches "Total: 96" statement. **Correct.**
- N/A findings: 3 (036, 063, 065). Matches master findings. **Correct.**
- Multi-batch findings: 6 documented in cross-reference table. **Correct.**
- Execution Checklist (lines 1088-1101) batch sizes match summary table. **Correct.**

### F.2 Task Numbering

Sequential within each batch:
- 0a: 01-05 (5 tasks). Correct.
- 0b: 01-22 (22 tasks). Correct.
- 0c: 01 (1 task). Correct.
- 1: 01-10 (10 tasks). Correct.
- 2: 01-05 (5 tasks). Correct.
- 3: 01-05 (5 tasks). Correct.
- 4: 01-15 (15 tasks). Correct.
- 5: 01-07 (7 tasks). Correct.
- 6: 01-04 (4 tasks). Correct.
- 7: 01-12 (12 tasks). Correct.
- 8: 01-10 (10 tasks). Correct.

No gaps, no duplicate numbers.

### F.3 Risk Register

9 risks (R1-R9, with R8 split into R8a and R9):
- R1 (Batch 0b scope creep): Valid.
- R2 (Breaking schema changes): Valid.
- R3 (shared_expectations size): Valid.
- R4 (Pairwise completeness scope): Valid.
- R5 (13a blocking gate): Valid.
- R6 (Prompt quality): Valid.
- R7 (Prompt contract test fragility): Valid -- added per R1 fix.
- R8a (Test suite stability): Valid.
- R9 (Host repo compatibility): Valid.

All risk mitigations are reasonable and actionable.

---

## G. Gaps, Ambiguities, and Regression Risks

### G.1 No Material Gaps Found

All 101 findings are addressed. All design decisions are respected. Task descriptions are specific enough for P5 execution.

### G.2 Minor Ambiguity: Task 3-02 Still Offers Three Options

Task 3-02 (move auth-domain canon entries) still lists three options (a/b/c) with "Preferred: option (a)." R1 flagged this as Minor (I.1). The preferred option is clearly stated, so this is acceptable for P5 -- the executor will use option (a). Not a blocker.

### G.3 Regression Risk Assessment

The main regression risks are well-covered by the Risk Register:
- **Breaking changes** (0a-03, 0a-04, 0a-05): R2 and R9 cover this with version bump strategy.
- **Prompt restructuring** (Batches 0c, 2, 4, 6): R7 covers test contract fragility.
- **Cross-cutting changes** (Task 1-05): R8a covers with full suite gate.

No unmitigated regression risks identified.

---

## Summary Assessment

| # | Category | Severity | Description |
|---|----------|----------|-------------|
| 1 | A.3 | Minor | AUDIT-029 not in any task's "Addresses" line; only in inline change descriptions. Consider adding to Task 4-01 Addresses for traceability. |

**Total issues found: 1 (Minor)**

| Category | Issues Found | Critical | Important | Minor |
|----------|-------------|----------|-----------|-------|
| Prior Fix Verification | 0 | 0 | 0 | 0 |
| A. Coverage | 1 | 0 | 0 | 1 |
| B. Dependencies | 0 | 0 | 0 | 0 |
| C. Design Decisions | 0 | 0 | 0 | 0 |
| D. Codebase Checks | 0 | 0 | 0 | 0 |
| E. Hallucination | 0 | 0 | 0 | 0 |
| F. Internal Consistency | 0 | 0 | 0 | 0 |
| G. Gaps/Ambiguities | 0 | 0 | 0 | 0 |
| **Total** | **1** | **0** | **0** | **1** |

---

## Convergence Verdict: **YES -- Ready for P5**

The plan has converged. All 9 Important R1 fixes and all 5 Minor R2 fixes are correctly applied. Only 1 new Minor issue found (AUDIT-029 traceability gap), which does not affect executability.

The plan demonstrates:

- **Complete coverage**: All 101 AUDIT findings accounted for (98 in tasks, 3 N/A with rationale)
- **Full design compliance**: All 13 locked design decisions respected without contradiction
- **Zero hallucinations**: 12/12 codebase spot-checks verified against actual source code
- **Correct math**: Task counts (96), batch sizes, N/A count (3), multi-batch count (6) all consistent
- **Sound dependency ordering**: Acyclic chain with properly documented intra-batch dependencies
- **Comprehensive risk register**: 9 risks with actionable mitigations
- **Executable task descriptions**: Specific file paths, code snippets, test gates, and fixture updates

**Recommendation**: Proceed to P5 execution. No further review rounds needed.
