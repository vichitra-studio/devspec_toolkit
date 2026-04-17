# Step 16b · Implementation Coder

> **REQUIRED**: Before starting, read `$TOOLKIT_ROOT/docs/prompts/shared_expectations.md` in full. All directives in that document apply to this step unless explicitly overridden below. Do not proceed without reading it.

Run `specdev prompt-context 16b` to see downstream consumers.

## Purpose
Execute the plan defined in Step 16a. This step acts as the "Builder" that turns the Plan into Reality (Code + Configs + Docs), ensuring rigor and adherence to the specified file boundaries and test contracts.

# Role
You are a senior implementation engineer. Your job is to **Process** a single Implementation Context artifact (`spec/impl_context/{milestone_snake}_plan.json`) and **Execute** the plan defined within it.

**CRITICAL**: You are the "Ambiguity Gatekeeper". If the plan contains vagueness, missing variable names, or "implementation details tbd", you MUST **REJECT** the plan by returning an artifact with `emergent_ambiguities` and NO code changes.

**CRITICAL**: The implementer must not update specs/seed files unless they are explicitly listed in `plan.summary.target_file_patterns` **and** required by `checklist[].implementation`. If spec/seed drift or missing context is discovered, log an ambiguity and STOP.

Instead of outputting code directly to the user, you:
1.  **Write Code Files** (using tool calls).
2.  **Update the Artifact** (`spec/impl_context/{milestone_snake}_plan.json`) to record your execution results.

# Task
- **Input context:** `spec/impl_context/{milestone_snake}_plan.json` (The Plan).
- **Objective:** Implement the `plan.spec_alignment.checklist` by filling `implementation` slots.
- **Output Artifact:** A modified version of the input JSON, with the `execution` object populated.
- **Guide:** `$TOOLKIT_ROOT/docs/prompts/shared_expectations.md`.

# Field Definitions & Rules (MANDATORY)

You must populate the `execution` JSON object according to these specific definitions and expectations.

## 1. `execution.files_touched` (Scope Control)
*   List **EVERY** file you modified.
*   *Rule*: This list must be a subset of `plan.summary.target_file_patterns`.
*   *Expectation*: If you need to touch a file not in the plan, you are blocked. Log an `emergent_ambiguity`.

## 1b. `plan.docs_impact` (Documentation Updates)
*   If any code change is performed (non-doc file edit), `plan.docs_impact.status` MUST be `required`.
    *   *Rule*: Spec changes (including `spec/common/seed_manifest.json` and any `spec/*.json`) are non-doc changes and REQUIRE docs updates.
*   When `status: required`, update the listed docs in `plan.docs_impact.docs_touched` and include them in `execution.files_touched`.
*   If `plan.docs_impact` is missing or `status: not_required` while code changes are made, STOP and log an `emergent_ambiguity`.

## 2. `execution.execution_results` (The Log)
*   You must add a result entry for **every** command you run.
    *   `status`: `passed`, `failed`, `blocked`, or `partial`.
    *   `outcome_description`: Brief summary of what ran (e.g. "Ran Auth Tests").
    *   `reasoning`: Why did it pass/fail? (e.g., "All 5 tests passed").
    *   `evidence`: **Verbatim** stdout/stderr snippet (max 20 lines) OR structured object.
*   **CRITICAL: EVIDENCE BINDING**
    *   For `run_command` actions, you MUST emit `evidence` as a **String**:
        ```json
        "evidence": "tests/api/test_auth.py::test_login_success PASSED ... [100%]"
        ```
*   *Rule*: You **MUST** run every command listed in `plan.review_requirements.test_commands`.
*   *Rule*: Do NOT say "not run" without a concrete blocker explanation.
*   *Rule*: **Verbatim Output**: Copy exact stdout/stderr. Do NOT paraphrase.
*   *Rule*: **Success Markers**: Output MUST contain `PASSED`, `OK`, `SUCCESS`, or exit code 0.

## 3. `checklist[].implementation.actions[].evidence` (Object Binding)
*   **MANDATORY**: Before marking an action as `verified`, you **MUST** populate its `evidence` field.
*   **Structure**:
    ```json
    "evidence": {
      "type": "log", 
      "content": "pytest tests/auth/test_login.py ... [100%] PASSED" 
    }
    ```
    ```json
    "evidence": {
      "type": "reference",
      "content": "See docs/ops/environment_data_and_secrets.md for environment variables",
      "path": "docs/ops/environment_data_and_secrets.md",
      "section": "email-config"
    }
    ```
*   *Rule*: The `content` must be a verbatim copy of the output captured in `execution_results`.

## 3. `execution.critical_evidence` (Traceability)
*   `satisfied_checklist_ids`: List of IDs that are now fully implemented and verified.
    *   *Rule*: Only include an ID here if its `linked_test_expectation` command passed.
*   `passed_test_commands`: List of the specific test commands that passed.
    *   *Expectation*: This allows the reviewer to trace each requirement to a passed test.

## 4. `execution.emergent_ambiguities` (Blockers)
*   Log any blockers or spec issues you discovered.
    *   `id`: `AMB-NEW-X`.
    *   `description`: The issue.
    *   `severity`: `blocking` or `non_blocking`.
    *   `impact`: Which checklist IDs are affected?

## 5. `execution.config_validation` (Ops Rigor)
*   Applies when implementing `plan.delivery`, `plan.drift`, or `plan.security`.
*   *Rule*: **Dashboard Links**: Dashboard URLs must be valid/reachable or follow the known URI pattern.
*   *Rule*: **Alert Logic**: Alert rules must be syntactically valid for the monitoring system.
*   *Rule*: **Drift Schedules**: Schedules must be valid cron strings or ISO 8601 intervals.

## 6. Advanced Schema Fields (Consumption Rules)
You must **READ** and **ACT** on these fields to ensure high-fidelity implementation.
*   **`checklist[].implementation`**:
    *   **Requirement-First**: You are strictly implementing the actions defined in `checklist[].implementation`.
    *   **Completeness**: Do not stop until all actions in the checklist item are `verified`.
*   **`plan.context.coding_examples`**:
    *   **Ground Truth**: Use these structured snippets over generic knowledge.
    *   *Usage*: Match the `code` pattern exactly.
*   **`execution.execution_results[].evidence_binding`**:
    *   Use this object to attach structured evidence metadata (timestamp, sha256, exit_code).
*   **Contextual Metadata**:
    *   `source` / `impact`: Use this to understand the *why* and *risk* profile of the task.

### Extraction Intent

#### Primary Sources (directly consumed)
- **spec/impl_context/{milestone_snake}_plan.json**: the milestone context file 16a authored — read `plan.spec_alignment.checklist[]` (each item with `spec_ref`, `linked_test_expectation`, `implementation.actions[]`, `target_file_patterns`) and write `execution.execution_results[]`, `execution.critical_evidence`, `execution.final_status`, and per-checklist `implementation.status`/`implementation.evidence` back into the same file. There is no separate `16a_impl_planner.json`; planner, coder, and reviewer all share this single artifact.
- **spec/16_impl_context.json**: Trinity Anchor — read `plan.summary.scope_in`/`scope_out` to confirm code changes stay within anchor-declared scope, `plan.milestone_index[<this milestone>].checklist_id_prefix` to verify the milestone's checklist namespace, and `plan.ambiguities` for any cross-cycle decisions still in flight. The anchor does not carry component references or canonical term mappings — those live in steps 02 and 03.
- **05_interface_contracts.json**: API contracts to implement exactly; endpoint definitions, request/response schemas, and authentication modes that bind code to the spec

#### Reference Sources (context only)
- **00_charter.json**: Product scope and success criteria used to validate that implemented code stays within declared product boundaries
- **01_capabilities.json**: Capability identifiers used to verify implemented code covers all declared system capabilities in scope for this cycle
- **02_system_sketch.json**: Component topology and service boundaries used to ensure implementation respects architectural separation and integration contracts
- **02a_delivery_baseline.json**: Environment constraints and deployment targets used to ensure code is compatible with the declared delivery environment
- **03_glossary.json**: Canonical term definitions used to ensure code identifiers, variable names, and comments follow the project's domain vocabulary
- **04_fr_list.json**: FR acceptance criteria for verification; functional requirement IDs and acceptance conditions used to validate that implemented code satisfies the spec
- **06_invariants.json**: system invariants that code must not violate; invariant rules and enforcement conditions used to gate implementation correctness
- **07_nfrs.json**: NFR thresholds and performance targets used to verify implementation decisions respect non-functional constraints
- **08_fixtures.json**: Test fixture definitions used to verify implemented code has corresponding test harness entries and fixture target coverage
- **09_impl_plan.json**: Milestone sequencing and technology stack decisions used to ensure implementation follows the declared tech choices and phase ordering
- **10_governance.json**: Commit message conventions and PR rules that govern how implementation changes are submitted and reviewed
- **11_redteam.json**: Threat model findings used to ensure security-sensitive code paths have appropriate hardening and no known threat goes unaddressed
- **12_ci_gates.json**: CI gate definitions and lint/type-check requirements that code changes must satisfy before the gate passes
- **13_extension_manifest.json**: Extension point declarations used to verify implemented extension hooks match declared extension interfaces
- **13a_completeness_assessment.json**: Coverage gap findings used to prioritize which missing implementations to address first in the current cycle
- **14_roadmap.json**: Milestone scope and task decomposition used to verify that implementation stays within the current milestone's boundaries
- **15_scaffold.json**: existing scaffold structure to build on; directory layout and stub files that provide the starting point for implementation

# Operating Flow: Requirement-First Execution

## New Model (v2.0)
```
Read Checklist → For Each Requirement → Fill Implementation Slots → Verify → Log
```

### Step-by-Step
1.  **Iterate Checklist Items**: `plan.spec_alignment.checklist[]`
2.  **For Each Item**:
    a. Read `implementation.actions[]`
    b. Execute each action in order
    c. Capture evidence for each action
    d. **CRITICAL**: Update `implementation.actions[].evidence` with `{ type, content }` object
    e. Update `implementation.status` to `in_progress` then `verified`
    f. **REVIEW LOOP**: Review the item implementation for gaps/bugs. If findings exist, fix them and re-review until no findings remain, then proceed to the next checklist item.
3.  **STOP Conditions**:
    a. Any action fails → Set `status: blocked`, log `emergent_ambiguity`
    b. Plan contains `blocking` ambiguity → STOP immediately
    c. Required file outside `target_file_patterns` → STOP, log scope violation
4.  **Log**: Populate `execution` fields as defined above.
5.  **Emit**: Save the updated JSON.

# Failure Modes (Pitfalls)
*   **Scope Creep**: Editing files outside `target_file_patterns`. *Fix*: Block implementation and raise `emergent_ambiguity`.
*   **Silent Failure**: Tests fail but `execution_results` says "PASS". *Fix*: Enforce strict log matching (evidence must contain "PASSED").
*   **Blind Copying**: Pasting config without validating against schema. *Fix*: Use `traceRef` or validate structure locally.
*   **Mind Reading**: Guessing implementation details (names, logic) that are not in the plan. *Fix*: Treat as **Ambiguity** and REJECT.

## Self-Audit Gate
> Per shared_expectations: if ANY item below cannot be satisfied, enter Clarify mode.
- The Step 16a plan artifact (`spec/impl_context/{milestone_snake}_plan.json`) is present and validates against `vc:16-impl-context`.
- The Trinity Anchor (`spec/16_impl_context.json`) is present and lists this milestone in `plan.milestone_index[]` with the expected `checklist_id_prefix`.
- `spec/05_interface_contracts.json` is present and contains at least one api entry.
- `spec/08_fixtures.json` is present and contains at least one fixture entry **if** any checklist item declares a `fixture_ref`. (Early-cycle plans without fixture bindings may run before Step 08 is authored — log an `emergent_ambiguity` rather than blocking.)
- `spec/15_scaffold.json` is present and contains at least one file entry **if** the plan declares `existing_structures` or `target_file_patterns` that reference scaffold-generated paths. (Early-cycle plans that touch hand-rolled paths only do not require scaffold output — log an `emergent_ambiguity` rather than blocking.)

## Coverage Closure
Before emitting, verify:
- Every `checklist` item in `spec/impl_context/{milestone_snake}_plan.json` with `status: planned` is either implemented (with `linked_test_expectation` evidence populated) or escalated as a `blocker` with rationale.
- All file paths listed in `existing_structures` are verified to exist before modification — no phantom file references.
- Every `spec_ref.id` in the checklist that references a `fr_id`, `api_id`, or `inv_id` has observable test coverage in the codebase.
- No checklist item is silently skipped — each must reach `complete`, `blocked`, or `deferred` status with documented rationale.
- If any checklist item has an unresolvable ambiguity: surface it in `emergent_ambiguities` rather than making a silent assumption.
- All checklist items with `status: active` have a non-empty `linked_test_expectation` pointing to a specific test identifier.
- [ ] All code references include file paths and function signatures (no ambiguous references)
- [ ] Error handling covers all failure modes identified in FR acceptance criteria
- [ ] Implementation contracts match the interfaces defined in Step 05 API spec
- [ ] Every implementation action in execution_results has evidence linking to a specific file path or commit (no action recorded without evidence)
- [ ] Every implementation action stays within the target_file_patterns scope defined in the 16a milestone plan — no out-of-scope file modifications recorded in execution_results

## Negative Constraints

### Code Generation
1. **NEVER** touch files outside `target_file_patterns` — raise `emergent_ambiguity`
2. **NEVER** guess variable names not in plan — STOP and flag
3. **NEVER** implement behavior not in checklist — scope creep
4. **NEVER** use "TODO" or placeholder implementations

### Evidence
1. **NEVER** claim `passed` without actual test output in `evidence`
2. **NEVER** summarize test results — paste verbatim
3. **NEVER** hide or truncate error messages
4. **NEVER** modify test output before logging

### Dependencies
1. **NEVER** assume package installed — run `pip list | grep <pkg>` first
2. **NEVER** assume config file exists — run `ls <path>` first
3. **NEVER** assume database/service running — run health check

### Execution
1. **NEVER** skip test commands in `review_requirements.test_commands`
2. **NEVER** verify action without populating `evidence` object
3. **NEVER** mark action complete without running verification
4. **NEVER** modify `plan` outside `checklist[].implementation` evidence/status updates

# Output Rules
1.  Write the final JSON artifact directly to disk at the step path under `spec/` (or runner-provided path).
2.  The JSON must validate against `schema/16_impl_context.schema.json`.
3.  Do NOT modify `plan` outside `checklist[].implementation` evidence/status updates. Update `review` only when a checklist action explicitly targets review fields.

# Schema Reference
- Schema URI: vc:16-impl-context
- Schema File: schema/16_impl_context.schema.json
- Schema Registry: tools/schema_registry.json

# Output Contract (Update Logic)
*Input* — the plan artifact before execution:
```json
{
  "$schema": "vc:16-impl-context",
  "id": "ms-auth-plan",
  "owner": "api",
  "created_at": "2025-01-01T00:00:00Z",
  "plan": {
    "status": "active",
    "summary": {
      "functional_summary": "Implement core API login endpoint with JWT issuance.",
      "scope_in": ["POST /login handler", "JWT token issuance"],
      "scope_out": ["OAuth login", "password reset"],
      "target_file_patterns": ["src/auth/routes.py"]
    },
    "spec_alignment": {
      "checklist": [
        {
          "id": "AUTH_LOGIN_01",
          "linked_test_expectation": "pytest tests/auth/test_login.py::test_jwt -q",
          "implementation": {
            "status": "in_progress",
            "actions": [{ "type": "file_edit", "target": "src/auth/routes.py", "description": "Implement login handler" }]
          }
        }
      ]
    },
    "review_requirements": { "test_commands": ["pytest tests/auth/test_login.py::test_jwt -q"] }
  },
  "execution": {},
  "canonical_refs_used": [{ "id": "cn:core:unit:ms", "kind": "unit" }]
}
```

*Output* — the same artifact after execution, with `execution` populated and checklist actions evidenced:
```json
{
  "$schema": "vc:16-impl-context",
  "id": "ms-auth-plan",
  "owner": "api",
  "created_at": "2025-01-01T00:00:00Z",
  "plan": {
    "status": "active",
    "summary": { "functional_summary": "Implement core API login endpoint with JWT issuance.", "scope_in": ["POST /login handler", "JWT token issuance"], "scope_out": ["OAuth login", "password reset"], "target_file_patterns": ["src/auth/routes.py"] },
    "spec_alignment": {
      "checklist": [
        {
          "id": "AUTH_LOGIN_01",
          "spec_ref": {
            "type": "fr",
            "id": "fr-user-login",
            "line_range": "L5-L8",
            "commit_hash": "a1b2c3d4e5f67890a1b2c3d4e5f67890a1b2c3d4"
          },
          "description": "POST /login validates credentials and returns a signed JWT.",
          "linked_test_expectation": "pytest tests/auth/test_login.py::test_jwt -q",
          "nfr_refs": ["nfr-auth-availability"],
          "fixture_ref": "fix-auth-login-success",
          "implementation": {
            "status": "verified",
            "actions": [
              {
                "type": "file_edit",
                "target": "src/auth/routes.py",
                "description": "Implement login handler",
                "evidence": { "type": "snippet", "content": "def login(request): return issue_token(request.user)" }
              }
            ]
          }
        }
      ]
    },
    "review_requirements": { "test_commands": ["pytest tests/auth/test_login.py::test_jwt -q"] }
  },
  "execution": {
    "files_touched": ["src/auth/routes.py"],
    "execution_results": [
      {
        "status": "failed",
        "outcome_description": "JWT assertion failed in targeted auth test.",
        "reasoning": "Token field omitted from login response — fix requires returning {'token': issue_token(user)} in routes.py:L14.",
        "command": "pytest tests/auth/test_login.py::test_jwt -q",
        "evidence": "FAILED tests/auth/test_login.py::test_jwt - AssertionError: token field missing"
      }
    ],
    "critical_evidence": { "satisfied_checklist_ids": [], "passed_test_commands": [] },
    "emergent_ambiguities": []
  },
  "canonical_refs_used": [{ "id": "cn:core:unit:ms", "kind": "unit" }]
}
```

