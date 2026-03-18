# P4: Structured Fix Plan

Agent Type: general-purpose
**READ-ONLY -- do NOT modify source files. Write ONLY to the output file.**
Repo Root: /Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/

---

## Objective

Convert master findings into an executable fix plan with dependency-ordered batches. Each task modifies exactly one file and has a specific test gate.

---

## Prerequisites

Runs AFTER P3 completes.

---

## Inputs

- `WIP/tool_audit/p3-out-master-findings.md` (master findings with AUDIT-NNN IDs)
- `WIP/tool_audit/p0-ground-truth-FINAL.md` (baseline metrics for sizing estimates)

Key baseline numbers:
- **830** tests, all passing -- this is the regression bar
- **23** `_load_*` functions in validators/ (primary DRY target)
- **21** step validator files in `tools/specdev_tools/validation/validators/`
- **61** source files, **13,228** LOC
- **73** test files, **17,709** LOC

---

## Rules

### Task Granularity

1. **One task = one file.** No task touches more than one file.
2. **New shared module creation** = its own task (Batch 1). Consumer updates importing the new module = separate tasks (Batch 2+).
3. **Multi-finding files:** ONE task addresses ALL findings for that file. The description must cover every linked AUDIT-NNN.
4. **MOVE operations:** One task handles the file move (source deletion + destination creation) and updates `__init__.py` re-exports (acceptable exception to one-file rule). Import updates in consuming files are separate tasks in a later batch.
5. **Each task has a test gate** -- a specific `pytest` command that validates the change.
6. A single AUDIT-NNN that spans multiple files becomes multiple FIX-NNN tasks, one per file, with explicit cross-references between them.
7. **Codebase-wide findings (>5 files with the same pattern change):** Create (a) one Foundation task for the shared module/interface, (b) one Consumer task per affected subpackage (not per file), with the description listing all files in that subpackage. This is an exception to the one-file rule for bulk pattern changes.
8. **Superseded findings:** Check P3 descriptions for "subsumed by", "solved by", or "part of" references. When finding X is subsumed by finding Y, do NOT create a separate FIX-NNN for X -- fold it into Y's task description.

### Batch Ordering

| Batch | Purpose | Dependencies |
|-------|---------|-------------|
| Batch 1 | **Foundation** -- new shared modules, core changes, conftest consolidation (as applicable) | Zero dependencies. These create the imports that later batches consume. |
| Batch 2 | **Consumer refactors** -- validators/linters importing new shared modules from Batch 1 (as applicable) | Depends on Batch 1 completion. |
| Batch 3 | **New tests + fixture migration** -- new test files for shared modules, spec/ to fixtures/ moves (as applicable) | Depends on Batches 1-2. |
| Batch 4 | **Cleanup** -- dead code removal, documentation fixes, version alignment, quick-fix LOW findings (as applicable) | Depends on Batches 1-3. |
| Batch 5 | **Research alignment quick wins** -- include ALIGN-* items from the P3 Research Alignment Gaps table where Quick Win is YES and Gap is not NONE. For Partial items, include only the quick-win portion (reference the relevant AUDIT-NNN). | Depends on Batches 1-4. |

### Severity Filter

- **Include:** CRITICAL, HIGH, MEDIUM findings. Also include LOW findings that are quick fixes (<5 LOC change).
- **Exclude:** Remaining LOW and all INFO findings go into a "Future Work" appendix (listed but not planned).

---

## Task Specification Template

Every task MUST follow this exact format:

```
### FIX-{NNN}: [Title]

- **Batch:** N
- **Audit ref:** AUDIT-001, AUDIT-005 (list all findings addressed)
- **Target file:** tools/specdev_tools/path/to/file.py (exact path from repo root)
- **Change type:** CREATE | MODIFY | DELETE | MOVE | RENAME
- **Description:** Comprehensive description of the change. Include:
  - Specific function names to add/modify/remove
  - Import changes
  - Behavioral changes
  - For multi-finding tasks: address each AUDIT-NNN explicitly
- **Test gate:** pytest tests/test_specific_file.py -x --tb=short
- **Dependencies:** FIX-001, FIX-002 | "none"
- **Estimated LOC:** +NN / -NN / net NN (use N/A for non-code changes such as directory deletion or .gitignore edits)
```

---

## Task Gate Protocol

After completing each FIX-NNN task, immediately run its specific test gate command:

1. Run the task's test gate: `pytest tests/test_specific_file.py -x --tb=short`
2. **If PASS:** Proceed to the next task in the batch.
3. **If FAIL:** Fix the issue or revert the task's file. Do NOT proceed to the next task until the gate is green.

This catches failures early -- diagnosing a single-task failure is far cheaper than diagnosing which of N tasks broke the batch.

---

## Batch Gate Protocol

After all tasks in a batch pass their individual task gates, commit and run the full suite:

**Pre-gate commit (safety net):**
```bash
git add -A && git commit -m "WIP: batch N complete"
```

**Run the batch gate:**
```bash
source devspec_env/bin/activate && pytest tests/ -x --tb=short
```

**If PASS:** Proceed to next batch.

**If FAIL:**
1. Read the traceback to identify which file caused the failure.
2. Map the failing file back to its FIX-NNN task.
3. Revert the specific file from the WIP commit: `git checkout HEAD -- <file>`
4. Re-run the batch gate to confirm green.
5. Create a new commit without the reverted file.
6. Mark the task as DEFERRED with the failure reason.
7. After reverting a task, check whether any tasks in the NEXT batch depend on the reverted task. If so, mark those downstream tasks as BLOCKED.
8. Continue to next batch.

**Note:** The final gate uses `-v` (not `-x`) to capture full test results rather than failing fast.

---

## Output

**Write to:** `WIP/tool_audit/p4-out-fix-plan.md`

### Required Structure

```
# P4: Fix Plan

## Summary
- Total tasks: NN
- By batch: B1: N, B2: N, B3: N, B4: N, B5: N
- Findings covered: NN of NN (CRITICAL: N, HIGH: N, MEDIUM: N)
- Estimated LOC delta: +NNN / -NNN / net NNN

## Batch 1: Foundation

### FIX-001: [Title]
[full template as above]

### FIX-002: [Title]
[full template as above]

[Batch gate: pytest tests/ -x --tb=short]

## Batch 2: Consumer Refactors
[tasks...]
[Batch gate]

## Batch 3: New Tests + Fixture Migration
[tasks...]
[Batch gate]

## Batch 4: Cleanup
[tasks...]
[Batch gate]

## Batch 5: Research Alignment Quick Wins
[tasks...]
[Batch gate]

## Final Gate
pytest tests/ -v
Expected: 830+ tests passing (new tests may increase count)

## Future Work (LOW / INFO -- not planned)

| AUDIT Ref | Severity | Description | Target File |
|-----------|----------|-------------|-------------|
| AUDIT-0XX | LOW | ... | ... |
```

### Conflict Check (Primary Planning Input)

Use the P3 "Findings by Target File" table as the primary task planning input. Each row becomes one FIX-NNN task (covering all AUDIT-NNN findings for that file). This naturally ensures no two tasks in the same batch share a target file. Before finalizing, verify this constraint holds. If conflicts exist, merge into a single task or move one to a later batch.
