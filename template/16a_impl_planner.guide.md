# Step 16a: Implementation Planning Guide

This step generates the **Implementation Context** (`spec/impl_context/{step_id}.json`) for a specific roadmap milestone/step. It acts as the "Architect" that defines not just *what* to build, but *how* to secure, monitor, and sustain it.

### Purpose
To produce a complete, falsifiable blueprint for implementation that bakes in security, delivery, and drift detection *before* a single line of code is written.

### Schema Deep-Links
*   **Plan Object**: `schema/16_impl_context.schema.json#/properties/plan`
*   **Checklist**: `.../properties/plan/properties/spec_alignment/properties/checklist`
*   **Tasks**: `.../properties/plan/properties/tasks`

## Input: Roadmap Step
You must identify a specific Step ID from `spec/14_roadmap.json` (e.g., `step-api-core`) to plan for.

## Activities
1.  **Synthesize Specs**: Read the Feature Specs (04), Interfaces (05), and Roadmap (14) to understand expectations.
2.  **Define Scope**:
    *   **In-Scope**: Only what is explicitly requested by the roadmap step.
    *   **Files**: Define exact `target_file_patterns` (e.g., `src/auth/*.py`).
3.  **Build Checklist**:
    *   Every spec requirement needs a checklist item.
    *   **Verification**: Every checklist item needs a `linked_test_expectation` (e.g. `pytest tests/test_login.py`).
4.  **Create Tasks**:
    *   Break down the work into logical Parent Tasks.

## Heuristics & Best Practices (MANDATORY)
The Planner is responsible for "Systems Thinking". You must apply these heuristics from the established engineering standards:

### 1. Checklist Rigor
*   **Atomicity**: Each checklist item must be atomic (one requirement) and distinct.
*   **Linked Test Expectation**: Every item MUST have a corresponding `linked_test_expectation` (e.g. `pytest tests/auth/test_login.py::test_rate_limit`).
*   **Spec Versioning**: Cite specific spec file paths and commit hashes for every requirements group.

### 2. Ambiguity Handling
*   **Blocking vs Non-Blocking**: Distinguish between ambiguities that stop work vs those allowing assumptions.
*   **Resolution**: If a blocking ambiguity exists, do not plan implementation; plan a "Clarification" task.
*   **Ambiguity Scrub**: Avoid vague terms like "harden security". Be specific: "Add rate limit to /login (10 req/min)".

### 3. Security (Red Team)
*   **Threat Binding**: Every new security fixture must map to a concrete Threat ID from Step 11/15.
*   **Best Practice**: Convert red-team findings into fixtures *in the same cycle*.
*   **Pitfall**: Logging findings without adding fixtures causes regressions later.

### 4. Delivery (Ops & Monitoring)
*   **Unit Alignment**: Alert rules must match NFR units (e.g. `latency > 500ms`, not `latency is high`).
*   **Coverage**: Every **High/Critical** NFR must have at least one Dashboard and one Alert.
*   **Best Practice**: Map dashboards to `nfr_refs` so metrics trace back to requirements.
*   **Pitfall**: Configuring alerts without clear thresholds or owners (pager fatigue).

### 5. Drift (Sustainment)
*   **Risk-Based Scheduling**: Schedule drift checks based on risk (e.g. Public APIs = Daily; Internal = Weekly).
*   **Concrete Remediation**: Remediation steps must specify *actions* (e.g. "Rollback release") and *owners*.
*   **Best Practice**: Choose detection methods (schema-diff, runtime-sample) that can run automatically in CI.
*   **Pitfall**: Listing checks without specifying schedule or remediation, leaving responders unsure when to act.

## Failure Modes
*   **Ambiguity Paralysis**: Planner finds a gap and stops. *Fix*: Raise a "Clarification" task or flag `blocking` ambiguity in `plan.ambiguities`.
*   **Checklist Fatigue**: Generating 50+ trivial items. *Fix*: Group related checks (but keep them atomic) or focus on high-risk areas.
*   **Security Blindness**: Ignoring Step 11 threats. *Fix*: Use **Threat Binding** to force coverage.
*   **Implementation Drift**: Plan ignores `target_file_patterns` constraints. *Fix*: Planner must strictly define file boundaries.

## Output
*   **Artifact**: `spec/impl_context/{step_id}.json`
*   **Schema**: `schema/16_impl_context.schema.json`
*   **Fields**: `plan` object fully populated. `execution` and `review` empty.
