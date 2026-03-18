# Fix Report: P3 and P4 Prompts

Applied: 2026-03-18
Review sources: `prompt-review-p3.md`, `prompt-review-p4.md`

---

## P3 Fixes Applied

### MUST_FIX

| ID | Description | Status |
|----|-------------|--------|
| MF-1 | Added all 8 Container B files to input list; updated header from "8 files" to "16 files (8 per container)" with Container A / Container B subheadings | DONE |
| MF-2 | Added dual-container reconciliation rules to Task 1: corroborated, severity resolution, verified genuine, and source attribution format `A:{id}, B:{id}; C:{resolution}` | DONE |
| MF-3 | Updated Prerequisites to: "P1 (7 agents x 2 containers = 14 output files) and P2 (1 agent x 2 containers = 2 output files)" | DONE |

### SHOULD_FIX

| ID | Description | Status |
|----|-------------|--------|
| SF-1 | Added false-positive handling instructions to Task 1 and Dropped Findings table to output template | DONE |
| SF-2 | Added Research Alignment Gaps section to output template with ALIGN-* table format | DONE |
| SF-3 | Updated Category field to specify UPPER_SNAKE_CASE convention with examples, replacing the short fixed enum | DONE |
| SF-4 | Changed WIP Cross-Check Report to file-level aggregation (total/confirmed/contradicted/stale/missed columns) instead of individual-item matching | DONE |
| SF-5 | Updated target length from "300-400 lines" to "500-700 lines" | DONE |

### MINOR

| ID | Description | Status |
|----|-------------|--------|
| MN-1 | Added note to WIP input header: "tools-tests-review-goal.md is a planning document, not findings -- exclude it" | DONE |
| MN-2 | Updated summary template to dual-container format: "NN unique after deduplication (from NN A + NN B raw findings)" | DONE |
| MN-3 | Updated WIP Status options to: `CONFIRMED (WIP ref) | NEW | MISSED_BY_AUDIT -- added from WIP:xxx` | DONE |

---

## P4 Fixes Applied

### MUST_FIX

| ID | Description | Status |
|----|-------------|--------|
| MF-1 | Added pre-gate commit safety net (`git add -A && git commit -m "WIP: batch N complete"`) before batch gate. Changed revert to `git checkout HEAD -- <file>` (from committed state, not destructive discard). Added instruction to create new commit after revert. | DONE |
| MF-2 | Added new "Task Gate Protocol" section: run each task's test gate immediately after completion, fix or revert before proceeding to next task | DONE |

### SHOULD_FIX

| ID | Description | Status |
|----|-------------|--------|
| SF-1 | Changed severity filter to include LOW findings that are quick fixes (<5 LOC change); updated Batch 4 description to mention quick-fix LOW findings | DONE |
| SF-2 | Updated Batch 5 scope to reference P3 Research Alignment Gaps table, clarified Quick Win YES + Gap not NONE, and Partial handling | DONE |
| SF-3 | Added rule 7 for codebase-wide findings (>5 files): Foundation task for shared module + Consumer task per subpackage (exception to one-file rule) | DONE |
| SF-4 | Clarified MOVE operations: covers source deletion + destination creation + `__init__.py` re-exports; import updates in consuming files are separate later-batch tasks | DONE |
| SF-5 | Added `Batch: N` field to task template | DONE |
| SF-6 | Added rule 8 for superseded findings: check for "subsumed by"/"solved by"/"part of" references, fold into parent task instead of creating separate FIX-NNN | DONE |
| SF-7 | Reframed Conflict Check as primary planning input: use P3 "Findings by Target File" table as starting point for task creation | DONE |

### MINOR

| ID | Description | Status |
|----|-------------|--------|
| MN-1 | Added "(as applicable)" to all batch descriptions | DONE |
| MN-2 | Added "N/A for non-code changes" to Estimated LOC field | DONE |
| MN-3 | Added note explaining final gate uses `-v` (full output) vs batch gate `-x` (fail-fast) | DONE |
| MN-4 | Changed Batch 5 reference from "P2 output" to "P3 Research Alignment Gaps table" (folded into SF-2) | DONE |
| MN-5 | Added RENAME to change type enum: `CREATE | MODIFY | DELETE | MOVE | RENAME` | DONE |

---

## Summary

- **P3:** 3 MUST_FIX + 5 SHOULD_FIX + 3 MINOR = 11 items applied
- **P4:** 2 MUST_FIX + 7 SHOULD_FIX + 5 MINOR = 14 items applied
- **Total:** 25 items applied, 0 skipped
