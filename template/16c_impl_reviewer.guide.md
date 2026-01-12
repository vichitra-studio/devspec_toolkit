# Step 16c: Implementation Review Guide

This step reviews the code against the plan and closes the loop. It acts as the "Gatekeeper".

### Purpose
To audit the implementation for completeness, quality, and rigorous adherence to the spec. It holds the "Definition of Done" for Code, Security, and Delivery.

### Schema Deep-Links
*   **Review Object**: `schema/16_impl_context.schema.json#/properties/review`
*   **Findings**: `.../properties/review/properties/findings`
*   **Verdict**: `.../properties/review/properties/verdict`

## Input: Implementation Context + Code
You consume the JSON artifact (Plan + Exec) and the codebase.

## Activities
1.  **Audit**: Compare Code vs `plan.checklist`.
2.  **Findings**:
    *   If bugs found, create a `finding` entry.
    *   **Remediation**: Nest a `remediation_task` (prefix `rev-`) inside the finding.
3.  **Verdict**:
    *   **Verified**: If all tests pass and spec is met (Ratings 4-5).
    *   **Deferred**: If blocked or needs improvement (Rating 2-3).
    *   **Rejected**: If strictly non-compliant (Rating 0-1).

## Heuristics & gates (MANDATORY)
The Reviewer is the final line of defense.

### 1. Review Logic
*   **Review-Origin Tasks**: Do not just comment on bugs. Create a new `task` with `origin: review` to force a fix.
*   **Deterministic Closure**: A task is `verified` ONLY if:
    1. Code matches Spec.
    2. Tests Pass.
    3. Failure Logs are empty.
*   **Spec Version Alignment**: Verify the code matches the *current* spec hash. If spec drifted, flag as ambiguity.

### 2. The Scoreboard (Gatekeeper)
*   **CI Status**: Verify the overall CI status is **GREEN**. If Red, the verdict MUST be `deferred` or `rejected`.
*   **Fixture Status**: Only mark endpoints as `implemented` if they pass the full test suite.
*   **Best Practice**: Update `implemented_endpoints` as soon as scaffolded routes gain real logic.
*   **Pitfall**: Marking fixtures as pass without rerunning after code changes (Stale Truth).

### 3. Security Gate
*   **Mitigation Verification**: Verify `plan.security.new_fixtures` actually cover the threats.
*   **Verdict Rule**: If `security_status` is RED (unmitigated threats), you cannot Verify.
*   **Pitfall**: Declaring green status without covering listed threats.

### 4. Delivery Gate
*   **Deployment Check**: Verify `deployments` are recorded for all active environments (`dev`, `staging`, `prod`).
*   **Monitoring Coverage**: Ensure Critical NFRs have active Alerts.
*   **Pitfall**: Leaving deployments undocumented makes rollback impossible.

### 5. Task Spawning (Recursive Fixes)
*   **Pattern**: Do not just say "Fix it". spawn a `remediation_task` with:
    *   `checklist_ids`: What requirement failed?
    *   `files_to_touch`: Where is the fix?
    *   This allows the Coder (16b) to run again immediately.

## Failure Modes
*   **Rubber Stamping**: Approving based on prose summary, not test logs. *Fix*: Verify `execution.execution_results` matches `critical_evidence`.
*   **Infinite Loop**: Failing to spawn recursive `remediation_tasks` for findings. *Fix*: Every finding must have a `task` unless it's a "won't fix".
*   **Security Bypass**: Verifying while `security_status` is RED. *Fix*: Check Step 11/17 gates explicitly.

## Output
*   **Artifact**: `spec/impl_context/{step_id}.json` (Final)
*   **Fields**: `review` object populated. `plan.tasks` statuses updated.
