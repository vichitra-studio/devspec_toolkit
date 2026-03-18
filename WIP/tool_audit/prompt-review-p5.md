# Prompt Review: P5 -- Parallel Fix Execution

Reviewed: 2026-03-18
Reviewed against: p0-ground-truth-FINAL.md, p0-baseline.md, live codebase

---

## Claims Verified

| Claim | Source Line | Verified Against | Match? |
|-------|-----------|-----------------|--------|
| Repo root path | L4, L28 | Live codebase | YES |
| Venv name `devspec_env` | L55, L84, L115 | MEMORY.md (devspec_env confirmed) | YES |
| Expected 830+ tests in final gate | L118 | p0-baseline.md (830 tests) | YES |
| Output path `WIP/tool_audit/p5-out-execution-report.md` | L127 | Consistent with pipeline naming | YES |
| Change types enumerated: CREATE, MODIFY, DELETE, MOVE | L33 | All four covered in constraints | YES |

---

## Issues Found

### MUST_FIX

**MF-1: PLAN_ERROR status listed in Retry Protocol but missing from Output Status enum**

Line 63 defines `PLAN_ERROR` as a possible status when the target file does not match the description. However, line 69 defines the Output Status field as `PASS | FAIL` only. An agent encountering the PLAN_ERROR condition would not know which status to report since it is not in the allowed enum.

Fix: Change line 69 from `PASS | FAIL` to `PASS | FAIL | PLAN_ERROR`.

**MF-2: DEFERRED status used in Failure Protocol but not defined in per-task Output**

Line 99 says "Mark the task as DEFERRED in the execution report" and the report template (line 137) has a DEFERRED count. But the per-task Output section (line 69) only allows `PASS | FAIL`. A task that is reverted and deferred has no valid status to report from its own output template.

Fix: Add `DEFERRED` to the per-task Status enum, or clarify that DEFERRED is set by the batch orchestrator (not the per-task agent) and document this explicitly.

**MF-3: DELETE operations have no revert instruction in per-task Retry Protocol**

The per-task Retry Protocol (lines 59-63) does not address what happens when a DELETE task fails its test gate. `git checkout -- <target-file>` would restore the deleted file (correct), but only if it was tracked by git. If the file was already untracked, the revert would silently fail. The Batch Failure Protocol (line 97) covers CREATE revert (`rm`) but not DELETE revert.

Fix: Add to Retry Protocol: "For DELETE tasks, revert by running `git checkout -- <target-file>` to restore the deleted file."

**MF-4: MOVE operations -- per-task Retry Protocol does not specify two-file revert**

Line 46 correctly notes that MOVE operations involve both source and destination files. But the Retry Protocol (lines 59-63) and the Batch Failure Protocol (line 97) only describe single-file revert. A failed MOVE requires reverting both files: restoring the source (via `git checkout`) and removing the destination (via `rm` if newly created).

Fix: Add to Failure Protocol: "For MOVE tasks, revert both files: `git checkout -- <source-file>` and `rm <destination-file>`."

### SHOULD_FIX

**SF-1: No instruction to verify that dependencies are actually completed before starting a task**

Line 35 has a field `Dependencies completed: {FIX-NNN list}` but there is no instruction for the agent to verify these are truly complete. If a batch is partially executed and a dependent task starts, it could operate on stale state.

Fix: Add to Instructions: "Before starting, verify that all listed dependency tasks have status PASS. If any dependency has status FAIL or DEFERRED, report this task as BLOCKED and do not execute."

**SF-2: No handling for test gate failures caused by other tasks in the same batch**

When tasks run in parallel within a batch, one task's changes could theoretically cause another task's test gate to fail (even though they target different files). The prompt does not address this scenario.

Fix: Add a note: "If your test gate fails and the traceback points to a file modified by another task in this batch, note this in the report as CROSS_TASK_CONFLICT rather than attempting to fix."

**SF-3: Cross-batch same-file targeting lacks explicit merge protocol**

Line 106 acknowledges "Tasks in different batches may target the same file" but provides no merge instructions. If Batch 1 modifies file X and Batch 3 also modifies file X, the Batch 3 agent needs to read the already-modified version. This is implicit (step 1 says "read the target file") but should be called out explicitly to avoid confusion.

Fix: Add: "When your target file was modified by a task in an earlier batch, you are working on the already-modified version. Do not attempt to revert earlier changes."

**SF-4: LOC delta calculation not defined for CREATE/DELETE**

Line 69 asks for LOC delta but does not specify how to calculate it for CREATE (all lines are new, so is it +N/-0?) or DELETE (all lines removed, so +0/-N?). The example on line 145 shows `+50/-0/+50` which implies CREATE = all positive, but this is never stated.

Fix: Add a note: "For CREATE tasks, LOC delta is +N/-0/net +N. For DELETE tasks, LOC delta is +0/-N/net -N."

### MINOR

**MI-1: "830+" in Final Gate is approximate**

Line 118 says "Expected: 830+ tests passing (Batch 3 may add new tests)." This is correct in intent (new tests may be added) but the baseline number 830 should be explicitly sourced. Consider adding "(baseline: 830 from p0-baseline.md)".

**MI-2: Template uses backtick-fenced block inside backtick-fenced block**

Lines 24-73 are a template inside a code fence, which contains its own code fence for the test gate command (lines 53-56). This will render incorrectly in standard Markdown. Consider using indentation or a different delimiter for the inner block.

**MI-3: No timestamp in the execution report template**

The report template (lines 131-164) has no field for when execution started/completed. Adding timestamps helps with post-mortem analysis.

---

## Verdict: APPROVED_WITH_FIXES

The prompt is structurally sound and covers the main execution workflow well. The MUST_FIX items are status enum inconsistencies (PLAN_ERROR and DEFERRED not in per-task output) and missing revert instructions for DELETE/MOVE operations. These are straightforward fixes that do not require restructuring the prompt. Once the 4 MUST_FIX items are addressed, the prompt is ready for use.
