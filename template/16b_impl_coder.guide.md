# Step 16b: Implementation Coding Guide

This step executes the plan defined in `spec/impl_context/{step_id}.json`. It acts as the "Builder" that turns the Plan into Reality (Code + Configs + Docs).

## Input: Implementation Context
You consume the JSON artifact created in Step 16a.

### Schema Deep-Links
*   **Execution Object**: `schema/16_impl_context.schema.json#/properties/execution`
*   **Files Touched**: `.../properties/execution/properties/files_touched`
*   **Results**: `.../properties/execution/properties/execution_results`

## Activities
1.  **Read Plan**: Understand `plan.tasks` and `plan.spec_alignment.checklist`.
2.  **Implement**: Write code, tests, and configuration files.
3.  **Verify**: Run the `linked_test_expectation` commands locally.
4.  **Log Results**:
    *   Update `execution.files_touched`.
    *   Record `execution.execution_results` (Pass/Fail).
    *   Record `execution.critical_evidence` (Checked Items).

## Heuristics & Rules (MANDATORY)
The Coder must be rigorous, not just "getting it to work".

### 1. The Immutable Plan
*   **Read-Only Context**: You treat the `plan` object as read-only. You do not change requirements or tasks.
*   **Pre-Implementation Verification**: Before editing, verify all `target_file_patterns` exist. If a path is wrong, `emergent_ambiguity` it.
*   **Test Obligations**: You MUST run every command listed in `linked_test_expectation`. No skipping.

### 2. Scope Control
*   **Strict Boundaries**: You may ONLY edit files that match `plan.target_file_patterns`.
*   **Scope Creep**: If you need to touch other files, you are **BLOCKED**. Log an `emergent_ambiguity` instead of guessing.

### 3. Ops & Config Rigor
*   **Config Validation**: When writing JSON configs (Dashboards, Alerts), ensure they are syntactically valid.
*   **Link Verification**: Dashboard URLs must be reachable or follow the established URI pattern.
*   **No Blind Copy**: Do not copy-paste example configs without verifying field names against the schema.

### 4. Evidence Quality
*   **Verbatim Logs**: `evidence` fields must contain actual stdout/stderr snippets (e.g. `pytest ... [100%] PASSED`).
*   **Traceability**: Every passed checklist item in `critical_evidence` must have a corresponding passed test command.

## Failure Modes
*   **Scope Creep**: Editing files outside `target_file_patterns`. *Fix*: Block implementation and raise `emergent_ambiguity`.
*   **Silent Failure**: Tests fail but `execution_results` says "PASS". *Fix*: Enforce strict log matching (evidence must contain "PASSED").
*   **Blind Copying**: Pasting config without validating against schema. *Fix*: Use `traceRef` or validate structure locally.

## Output
*   **Artifact**: `spec/impl_context/{step_id}.json`
*   **Fields**: `execution` object populated.
