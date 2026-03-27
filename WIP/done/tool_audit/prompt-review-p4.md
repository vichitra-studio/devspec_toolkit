# Prompt Review: P4 -- Structured Fix Plan

Reviewed: 2026-03-18
Prompt file: `WIP/tool_audit/p4-prompt-fix-plan.md`
Reviewed against: `p0-ground-truth-FINAL.md`, `p3-out-master-findings.md`, live codebase

---

## Claims Verified

| Claim | Source Line | Verified Against | Match? |
|-------|-----------|-----------------|--------|
| 830 tests, all passing | P4 line 27 | p0-ground-truth L13-14 | YES |
| 23 _load_* functions in validators/ | P4 line 28 | p0-ground-truth L36 | YES |
| 21 step validator files | P4 line 29 | p0-ground-truth L34 | YES |
| 61 source files, 13,228 LOC | P4 line 30 | p0-ground-truth L15-16 | YES |
| 73 test files, 17,709 LOC | P4 line 31 | p0-ground-truth L17-18 | YES |
| Input: p3-out-master-findings.md | P4 line 23 | File exists on disk | YES |
| Input: p0-ground-truth-FINAL.md | P4 line 24 | File exists on disk | YES |
| Batch gate command uses devspec_env | P4 line 90 | MEMORY.md (virtualenv name) | YES |
| Batch 5 for research alignment quick wins | P4 line 54 | P3 output has ALIGN-* items with Quick Win field | YES |
| Final gate expects 830+ tests | P4 line 149 | p0-ground-truth L13 | YES |

---

## Issues Found

### MUST_FIX

**MF-1: Batch gate revert protocol is destructive without safety check**

The batch gate protocol (lines 96-102) says: "Revert the breaking change: `git checkout -- <file>`". This is a destructive operation that discards all changes to the file. The protocol has no instruction to:
- Stage/commit working changes before running the batch gate
- Create a WIP commit per batch so reverts don't lose work
- Verify the reverted file was actually the cause (vs. a dependency issue)

If an agent runs batch 1 with 5 tasks, doesn't commit, and then one test fails, `git checkout -- <file>` reverts the file but leaves 4 other modified files uncommitted. A second failure could cascade into losing all work.

**Fix:** Add to batch gate protocol:
1. Before running batch gate: `git add -A && git commit -m "WIP: batch N complete"`
2. If FAIL: revert specific file from last commit: `git checkout HEAD -- <file>`
3. After confirming green: `git commit --amend` to remove the reverted file, or create a new commit without it.

Alternatively, simplify: "Commit after each successful task's individual test gate. If batch gate fails, revert the last commit."

---

**MF-2: No individual task test gate protocol**

The prompt says "Each task has a test gate -- a specific pytest command" (line 43) but the batch gate protocol (lines 87-102) only describes what to do after ALL tasks in a batch complete. There is no instruction for:
- Running the individual task's test gate after completing each task
- What to do if an individual task's test gate fails (before reaching the batch gate)
- Whether to proceed to the next task in the same batch if one task's gate fails

This is critical because catching failures early (per-task) is far cheaper than catching them at batch level and having to diagnose which of N tasks broke things.

**Fix:** Add a "Task Gate Protocol" section:
1. After completing each FIX-NNN task, run its specific test gate command.
2. If PASS: proceed to next task in batch.
3. If FAIL: fix the issue or revert. Do not proceed to next task until green.
4. After all tasks in batch pass individually, run the full batch gate.

---

### SHOULD_FIX

**SF-1: Severity filter excludes LOW but P3 output has 16 LOW findings -- some are legitimate quick fixes**

The prompt says "Include: CRITICAL, HIGH, MEDIUM only. Exclude: LOW and INFO." This is reasonable for scope control, but several LOW findings from P3 are trivial quick fixes that would take <5 minutes each:
- AUDIT-047: Delete orphaned UNKNOWN.egg-info directory (1 command)
- AUDIT-048: Add trace_matrix.json to .gitignore (1 line)
- AUDIT-050: Fix governance.py file handle leak (3 lines)

These should arguably be in Batch 4 (Cleanup) rather than excluded entirely.

**Fix:** Change severity filter to: "Include: CRITICAL, HIGH, MEDIUM. Also include LOW findings marked as quick-fix (<5 LOC change). Exclude: remaining LOW and all INFO."

---

**SF-2: Batch 5 scope is unclear -- "only items marked Quick Win: YES in P2 output"**

The P3 output has an ALIGN-* table with a "Quick Win" column, but the values are `YES`, `NO`, `Partial`, not just `YES/NO`. The prompt doesn't say what to do with `Partial`. Also:
- ALIGN-4 is "NONE (achieved)" -- should it be excluded even though marked YES?
- ALIGN-6 and ALIGN-9 are marked YES but reference effort levels M and S respectively.

**Fix:** Clarify: "Include ALIGN-* items where Quick Win is YES and Gap is not NONE. For Partial items, include only the quick-win portion (reference the relevant AUDIT-NNN)."

---

**SF-3: No instruction for handling findings that span the entire codebase**

Several P3 findings have Location = "All validators" or "Throughout codebase":
- AUDIT-007: "All validators, all linters, validate.py" (structured errors)
- AUDIT-030: "All 23 _load_* functions across validators" (hardcoded prefixes)
- AUDIT-046: "All 21 validator files" (import inconsistency)

The one-task-one-file rule cannot apply to these. The prompt says "A single AUDIT-NNN that spans multiple files becomes multiple FIX-NNN tasks" (line 44), but for AUDIT-007 (structured errors across 38+ files), that would create 38 tasks. This needs a scoping strategy.

**Fix:** Add a rule: "For findings that affect >5 files with the same pattern change, create: (a) one Foundation task for the shared module/interface, (b) one Consumer task per affected subpackage (not per file), with the description listing all files in that subpackage. Exception to one-file rule for bulk pattern changes."

---

**SF-4: MOVE operations exception is underspecified**

Line 40: "MOVE operations: One task handles both source and destination (acceptable exception to one-file rule)." But it doesn't specify:
- How to handle import updates in consuming files (are those separate tasks?)
- Whether test file moves are also covered
- Whether the MOVE task's test gate should cover both old and new paths

**Fix:** Clarify: "MOVE operations: One task handles the file move (source deletion + destination creation) and updates `__init__.py` re-exports. Import updates in consuming files are separate tasks in a later batch."

---

**SF-5: FIX-NNN template missing "Batch" field**

The task template has: Audit ref, Target file, Change type, Description, Test gate, Dependencies, Estimated LOC. It does not have a "Batch" field. While the batch is implicit from the section heading, having it in the template makes each task self-contained and simplifies reference.

**Fix:** Add `- **Batch:** N` to the template.

---

**SF-6: No instruction for handling AUDIT-NNN items that are superseded by others**

P3 output has several findings that are explicitly subsumed:
- AUDIT-037 says "subsumed by AUDIT-009 fix"
- AUDIT-030 says "solved by AUDIT-002/003 fix"
- AUDIT-033 says "part of AUDIT-007 fix"

The P4 prompt has no instruction for detecting and handling these supersession relationships. If the agent creates separate FIX-NNN tasks for both the parent and the subsumed finding, work is duplicated.

**Fix:** Add: "Check P3 descriptions for 'subsumed by', 'solved by', or 'part of' references. When finding X is subsumed by finding Y, do NOT create a separate FIX-NNN for X -- fold it into Y's task description."

---

**SF-7: Conflict check is at the end but should be during planning**

Line 159: "Before finalizing, verify: no two tasks in the same batch share a target file." This is a post-hoc check. Since P3 already provides a "Findings by Target File" table mapping files to their AUDIT-NNN IDs, the P4 agent should use this table as the primary planning input (not as a final check).

**Fix:** Reframe: "Use the P3 'Findings by Target File' table as the primary task planning input. Each row becomes one FIX-NNN task. This naturally ensures no two tasks in the same batch share a target file."

---

### MINOR

**MN-1: Batch descriptions assume all audit patterns will be present**

The batch purposes are prescriptive:
- Batch 1: "new shared modules, core changes, conftest consolidation"
- Batch 3: "spec/ to fixtures/ moves"

If P3 findings don't include conftest consolidation or fixture moves, these batch descriptions are misleading. The P3 output does have conftest findings (AUDIT-028) and fixture concerns (AUDIT-010, AUDIT-060), so this works for the current run.

**Fix:** Add "(as applicable)" to batch descriptions, or note they are examples.

---

**MN-2: Estimated LOC format "+NN / -NN / net NN" doesn't account for zero changes**

For DELETE or documentation-only changes, the format is awkward. AUDIT-047 (delete egg-info) has +0 / -0 / net 0 in LOC terms but is a directory deletion.

**Fix:** Add "N/A for non-code changes (directory deletion, .gitignore edits)."

---

**MN-3: Final gate says "pytest tests/ -v" but batch gates say "pytest tests/ -x --tb=short"**

The final gate uses `-v` (verbose) while batch gates use `-x --tb=short` (fail-fast, short traceback). The inconsistency is intentional (final gate wants full output) but should be explicitly noted.

**Fix:** Add a note: "Final gate uses -v (not -x) to capture full test results rather than failing fast."

---

**MN-4: No mention of the P3 "Research Alignment Gaps" table format**

P4 batch 5 references "items marked Quick Win: YES in P2 output" but P3 reformatted the P2 output into an ALIGN-* table. The P4 prompt should reference the P3 table format, not the raw P2 output.

**Fix:** Change "in P2 output" to "in P3 Research Alignment Gaps table."

---

**MN-5: Template says "Change type: CREATE | MODIFY | DELETE | MOVE" -- missing RENAME**

P3 has AUDIT-027 recommending renaming test_r9_* files. RENAME is semantically different from MOVE (same directory, different name). Minor distinction but could cause confusion.

**Fix:** Add RENAME to the change type enum: `CREATE | MODIFY | DELETE | MOVE | RENAME`

---

## Verdict: APPROVED_WITH_FIXES

The P4 prompt is well-structured with sound batch ordering logic, a clear task template, and a practical batch gate protocol. The two MUST_FIX items address operational safety: the destructive revert without commit safety (MF-1) and the missing per-task gate protocol (MF-2). Without these, an executing agent could lose work or compound failures across a batch.

The SHOULD_FIX items address edge cases that the P3 output reveals: superseded findings, codebase-wide patterns, and Batch 5 scoping ambiguity. These are quality improvements that reduce the need for agent improvisation.

Overall, the prompt is production-ready after addressing MF-1 and MF-2. The remaining items improve clarity but the prompt would still produce a usable fix plan without them.
