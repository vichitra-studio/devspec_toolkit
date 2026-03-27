# P5: Parallel Fix Execution

Agent Type: Per-task -- one general-purpose agent per FIX-NNN
Repo Root: /Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/

---

## Objective

Execute the fix plan from P4. Each FIX-NNN task runs as an independent agent that modifies exactly one file and verifies via its test gate.

---

## Prerequisites

Runs AFTER P4 completes. Execute batches in order (1 through 5). Within each batch, all tasks run in parallel.

---

## Per-Task Agent Prompt Template

Copy this template for each FIX-NNN task. Fill in the bracketed fields from P4.

```
# Fix Task: FIX-{NNN}

Agent Type: general-purpose
Repo Root: /Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/

## Task
- **Task ID:** FIX-{NNN}
- **Target file:** {exact path from repo root}
- **Change type:** {CREATE | MODIFY | DELETE | MOVE}
- **Audit reference:** {AUDIT-NNN list}
- **Dependencies completed:** {FIX-NNN list that are already done, or "none"}

## Description
{Full description from P4 fix plan -- include function names, imports, behavioral changes}

## Instructions
0. **Dependency gate:** Verify that all tasks listed in "Dependencies completed" have status PASS. If any dependency has status FAIL or DEFERRED, report this task as BLOCKED and do not execute.
1. Read the target file in full. For CREATE tasks, skip this step (the file does not exist yet). When your target file was modified by a task in an earlier batch, you are working on the already-modified version. Do not attempt to revert earlier changes.
2. Make the specific changes described above. Nothing more, nothing less.
3. Run the test gate.

## Constraints
- Modify ONLY the target file listed above. Do not touch any other file. Exception: For MOVE operations, both the source and destination files are in scope.
- Do not add features, docstrings, or comments beyond what the description specifies.
- Match the existing code style (indentation, naming conventions, import ordering).
- If the change type is CREATE, verify the parent directory exists first.
- If the change type is MOVE, handle both source removal and destination creation.

## Test Gate
Run:
```
source devspec_env/bin/activate && {exact pytest command from P4}
```

### Retry Protocol
- **Attempt 1:** Run test gate. If PASS, done.
- **Attempt 2:** If FAIL, read the traceback, fix the issue in the target file, re-run.
- **Attempt 3:** If FAIL again, read the traceback, fix, re-run.
- **After 3 failures:** STOP. Do not retry further. Report as FAIL with all 3 tracebacks.
- If the target file does not match the description (function does not exist, file structure differs from expected), report status as PLAN_ERROR with details. Do not attempt to improvise a different fix.
- **If your test gate fails and the traceback points to a file modified by another task in this batch**, report status as FAIL and note `CROSS_TASK_CONFLICT` in the Notes field rather than attempting to fix another task's file.

### Revert by Change Type
- **DELETE:** Revert by running `git checkout -- <target-file>` to restore the deleted file.
- **MOVE:** Revert both files: `git checkout -- <source-file>` to restore the source, and `rm <destination-file>` to remove the newly created destination.

## Output
Report:
- **Status:** PASS | FAIL | PLAN_ERROR | DEFERRED
- **File:** {target file}
- **LOC delta:** +N / -N / net N (actual, not estimated)
- **Test gate result:** PASS at attempt N | FAIL after 3 attempts
- **Tracebacks (if any):** Include the final traceback if FAIL.
- **Notes:** Any observations about unexpected behavior or related issues discovered.
```

---

## Batch Execution Protocol

### Execution Order

1. **Batch 1 (Foundation):** Launch all Batch 1 tasks in parallel. No inter-task dependencies.
2. **Batch 1 Gate:** After all Batch 1 tasks complete:
   ```bash
   source devspec_env/bin/activate && pytest tests/ -x --tb=short
   ```
   - If PASS: proceed to Batch 2.
   - If FAIL: follow Failure Protocol below.
3. **Batch 2 (Consumer Refactors):** Launch all Batch 2 tasks in parallel.
4. **Batch 2 Gate:** Full suite again.
5. Repeat for Batches 3, 4, 5.

### Failure Protocol (Batch Gate)

If the batch gate fails:
1. Read the traceback. Identify the failing test and the file it tests.
2. Map back to the FIX-NNN task that modified that file.
3. Revert based on change type:
   - **MODIFY:** `git checkout -- <target-file>`
   - **CREATE:** `rm <target-file>` (file was newly created, not in git)
   - **DELETE:** `git checkout -- <target-file>` (restores the deleted file)
   - **MOVE:** Revert both files: `git checkout -- <source-file>` and `rm <destination-file>`
4. Re-run the batch gate to confirm it passes without that change.
5. Mark the task as DEFERRED in the execution report.
6. Proceed to the next batch -- deferred tasks do not block progress.

### Cross-Task Conflict Prevention

- Tasks within the same batch MUST target different files. P4 should guarantee this.
- If you discover two tasks in the same batch targeting the same file, STOP and merge them into a single task before executing.
- Tasks in different batches may target the same file (Batch 1 creates, Batch 3 adds tests).

---

## Final Gate

After all 5 batches:

```bash
source devspec_env/bin/activate && pytest tests/ -v
```

Expected: 830+ tests passing (Batch 3 may add new tests). Zero failures.

---

## Collected Reporting

After all batches complete, collect per-task reports into a single file.

**Write to:** `WIP/tool_audit/p5-out-execution-report.md`

### Required Structure

```
# P5: Execution Report

## Summary
- Tasks executed: NN
- PASS: NN
- FAIL: NN
- DEFERRED: NN
- Total LOC delta: +NNN / -NNN / net NNN
- Final test count: NNN passed

## Batch 1: Foundation

| Task | File | Status | LOC | Test Gate | Attempts | Notes |
|------|------|--------|-----|-----------|----------|-------|
| FIX-001 | tools/specdev_tools/... | PASS | +50/-0/+50 | PASS@1 | 1 | -- |
| FIX-002 | ... | FAIL | +30/-10/+20 | FAIL@3 | 3 | TypeError in ... |

Batch Gate: PASS | FAIL (with details)

## Batch 2: Consumer Refactors
[same table format]
Batch Gate: PASS | FAIL

[repeat for all batches]

## Final Gate
pytest tests/ -v
Result: NNN passed, 0 failed

## Deferred Tasks
| Task | Reason | Traceback Summary |
|------|--------|-------------------|
| FIX-0XX | Batch gate failure -- reverted | ... |
```
