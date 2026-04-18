# Toolkit bug — W576 lint / 16b schema mismatch

**Discovered**: 2026-04-18 during C2 cluster execution of `ms-bootstrap-local-ghost` Step 16b implementation.

**Severity**: Low. Lint noise only. No impact on implementation correctness.

## Repro

```bash
./tools/run_specdev.sh forward-replay-check --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
```

Even with checklist items verified and full evidence populated in `spec/impl_context/<ms>_plan.json:execution`, W576 fires for every task that was actually executed.

## Root cause

**Lint** (`devspec_toolkit/tools/specdev_tools/validation/traceability_closure.py:428`):

```python
for exec_entry in code_exec_data.get("execution", {}).get("execution_results", []):
    if isinstance(exec_entry, dict):
        task_ref = exec_entry.get("task_id")   # <-- reads task_id
        if isinstance(task_ref, str) and task_ref:
            executed_task_ids.add(task_ref)
```

**Schema** (`devspec_toolkit/schema/16_impl_context.schema.json`, execution_results items):

```json
{
  "additionalProperties": false,
  "properties": {
    "status": {...}, "outcome_description": {...}, "reasoning": {...},
    "command": {...}, "evidence": {...}, "evidence_ref": {...},
    "evidence_binding": {...}, "status_ref": {...}, "command_ref": {...}
  }
}
```

`task_id` is not in the allowed property list. Any attempt to add it fails schema validation with `Additional properties are not allowed ('task_id' was unexpected)`.

**Result**: the lint expects a field the schema forbids. W576 is unclosable via artifact content.

## Proposed fix (preferred — option 2 of 3)

Change the lint to trace the task ID through existing fields rather than requiring a new one:

```python
# Pseudocode
executed_task_ids = set()
for entry in code_exec_data.get("execution", {}).get("critical_evidence", {}).get("satisfied_checklist_ids", []):
    # Look up the checklist item by ID
    checklist = code_exec_data.get("plan", {}).get("spec_alignment", {}).get("checklist", [])
    for item in checklist:
        if item.get("id") == entry:
            spec_ref = item.get("spec_ref", {})
            if isinstance(spec_ref, dict) and spec_ref.get("id"):
                executed_task_ids.add(spec_ref["id"])
            break
```

This uses the already-populated `critical_evidence.satisfied_checklist_ids` plus the checklist's `spec_ref.id` pointer to the roadmap task — no schema change required.

## Alternative fixes

1. **Schema change**: add `task_id` as an allowed property on `execution_results` items and update prompt_16b_impl_coder.md to require it. More invasive (touches schema, prompt, output contract, existing plans).
2. **Add `satisfied_task_ids` to `critical_evidence`**: mirrors `satisfied_checklist_ids` shape, explicit tracking at the roadmap-task level. Also schema change, but less invasive than per-entry `task_id`.

## Observed impact in ms-bootstrap-local-ghost

After verifying `BOOTSTRAP_BUILD_THEME_01` and `BOOTSTRAP_BUILD_THEME_02` with full evidence chain, `forward-replay-check` still emits:

```
W576 TASK_EXECUTION_MISSING task-build-theme-zip has no corresponding Step 16b execution entry
```

Despite `spec_ref.id == "task-build-theme-zip"` on both verified checklist items and both being listed in `execution.critical_evidence.satisfied_checklist_ids`.

Expected to fire identically for the remaining three bootstrap tasks (`task-install-ghost-local`, `task-upload-activate-theme`, `task-smoke-test-publish`) once their clusters complete.
