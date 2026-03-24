# Step 16 · Implementation Context (Trinity Anchor)

> **Inherits**: `$TOOLKIT_ROOT/docs/prompts/shared_expectations.md` — all directives apply unless explicitly overridden below.

Run `specdev prompt-context 16` to see downstream consumers.

## Purpose
Create or update the **canonical Step 16 anchor** at the Step 16 anchor artifact in the `spec` root.
This file is the **root reference** for the Trinity Loop and exists alongside per‑milestone execution files in `spec/impl_context/`. It must:
1. Summarize the current execution scope.
2. Declare traceable checklist items for the active implementation cycle.
3. Record documentation impact decisions and spec provenance.
4. act as the union/root of all active milestone implementation contexts (16a/16b/16c).

## When To Use This Prompt
- You need a **single, canonical Step 16** artifact in `spec/`.
- You want a root view of the current Trinity cycle that references active milestone contexts.
- You are aligning a repo to the toolkit version that expects a Step 16 anchor artifact.

# Role
You are a senior software architect producing the Step 16 **Trinity Anchor**.
Generate a **machine‑checkable JSON artifact** that captures the plan,
implementation checklist, and review expectations for the *current* execution cycle.

### Extraction Intent

#### Primary Sources (directly consumed)
- `spec/14_roadmap.json`: active milestone, tasks, and fr_refs — primary source for implementation context; milestone identifiers, deliverables, scheduling, and status fields drive checklist coverage mapping and roadmap sync updates
- `spec/04_functional_requirements.json`: FR statements and acceptance criteria for the active milestone; functional requirement identifiers, acceptance criteria, and priority levels directly populate checklist spec_ref entries and linked_test_expectations
- `spec/05_interface_contracts.json`: API contracts to implement; endpoint definitions, request/response schemas, and method constraints bind checklist items to concrete interface contracts

#### Reference Sources (context only)
- `spec/00_charter.json`: Product vision, success criteria, and stakeholder constraints that bound the execution scope and inform scope_in/scope_out decisions
- `spec/01_capabilities.json`: Capability identifiers and descriptions used to trace checklist items back to declared product capabilities
- `spec/02_system_sketch.json`: component boundaries and trust zones; component topology, integration boundaries, and data flow paths that determine target_file_patterns and architecture_sketch content
- `spec/02a_delivery_baseline.json`: Environment definitions, deployment targets, and infrastructure constraints that inform delivery status and drift check scheduling
- `spec/03_glossary.json`: Canonical term definitions and domain vocabulary enforced in checklist descriptions and functional_summary text
- `spec/06_invariants.json`, `spec/07_nfrs.json`: constraints to respect during implementation; invariant rules and NFR thresholds inform checklist validation items, nfr_refs, and delivery alert rules
- `spec/08_fixtures.json`: Test fixture identifiers, target bindings, and expected outcomes used to populate fixture_ref fields and linked_test_expectation commands
- `spec/09_implementation_plan.json`: Milestone definitions, task decompositions, and tech stack constraints that determine implementation sequencing and milestone status tracking
- `spec/10_governance.json`: Commit message patterns, PR rules, and approval workflows that constrain how implementation changes are committed and reviewed
- `spec/11_redteam.json`: Threat identifiers, attack vectors, and severity ratings used to populate security fixture bindings and remediation checklist items
- `spec/12_ci_gates.json`: CI pipeline stage definitions, gate conditions, and required checks that inform review_requirements test_commands and verification expectations
- `spec/13_extension_generator.json`: Extension point declarations and plugin interface contracts used to identify additional target_file_patterns for extensibility concerns
- `spec/13a_completeness_assessment.json`: Coverage gap analysis, missing spec items, and completeness scores used to inform scope boundary decisions
- `spec/15_scaffold.json`: existing scaffold structure; generated file structure, directory layout, and scaffold templates that ground target_file_patterns and existing_structures references

# Operating Flow (MANDATORY)
1. **Context Review**: Ingest required upstream spec artifacts.
2. **Scope**: Identify the exact execution scope for the current cycle.
3. **Active Contexts**: List `spec/impl_context/*.json` files in `plan.context.existing_structures`.
4. **Drift Check**: MUST verify that no `checklist[].id`, `scope_in`, or `scope_out` value in this Anchor contradicts the corresponding values in any active Milestone context (16a/b/c) under `spec/impl_context/`.
5. **Checklist**: Convert relevant spec requirements into atomic checklist items.
6. **Docs Impact**: Decide whether docs updates are required and list impacted docs.
7. **Roadmap Sync**: If you identify that milestones are fully completed based on the ingested context, you MUST update:
    - `spec/14_roadmap.json`: Statuses to `done`.
    - `spec/09_impl_plan.json`: Statuses to `done`.
8. **Emit**: Write the Step 16 anchor artifact in the `spec` root.

## Self-Audit Gate
> Per shared_expectations: if ANY item below cannot be satisfied, enter Clarify mode.
- `spec/14_roadmap.json` is present and contains at least one milestone entry.
- `spec/04_fr_list.json` is present and contains at least one functional_requirements entry.
- `spec/05_interface_contracts.json` is present and contains at least one api entry.
- `spec/15_scaffold.json` is present and contains at least one file entry.

## Coverage Closure
Before emitting, verify:
- Every `milestone_id` from `spec/14_roadmap.json` that is in scope for this session has ≥1 `checklist` item in `plan.spec_alignment.checklist`.
- All `spec_ref.id` values in the checklist resolve to IDs present in their referenced upstream spec files (`fr_id`, `api_id`, `inv_id`, `nfr_id`, `fixture_id`).
- Every selected FR, API, invariant, and NFR in scope has a corresponding checklist item or explicit `out_of_scope` entry with rationale.
- No milestone from `spec/14_roadmap.json` is silently excluded from scheduling without `out_of_scope` documentation.
- If any spec reference is ambiguous or the scope boundary is unclear: add a gap question (Clarify mode) rather than assuming inclusion or exclusion.
- [ ] All `canonical_refs_used` entries reference valid IDs from `canon/manifest.json`
- [ ] Every implementation context links to the active Step 14 milestone
- [ ] All cross-references resolve to valid IDs in the referenced spec files
- [ ] The `semantic_review` section covers all major implementation concerns (naming, structure, coverage) — not just surface-level checks
- [ ] Every `plan.spec_alignment.checklist` item has a corresponding `execution.execution_results` entry (no planned item left without an execution record)
- [ ] No active Milestone Contexts (16a/b/c) conflict with this Anchor — all checklist IDs and scope_in/scope_out values are consistent with spec/impl_context/*.json

## Negative Constraints
1. **NEVER** hallucinate `step_id` or use loose references.
2. **NEVER** omit `commit_hash` in `spec_ref`.
3. **NEVER** emit incomplete JSON or use placeholder values.
4. **NEVER** use `plan.tasks` or `metadata`.

# Field Definitions & Rules (MANDATORY)
**Crucial**: Use the following exact definitions to ensure compliance:

## 1. `plan.summary` (The Step Summary)
*   `functional_summary`: A 1-paragraph summary of what this step accomplishes in the global architecture.
*   `scope_in`: List explicit concerns that are IN scope.
*   `scope_out`: List explicit concerns that are OUT of scope.
*   `target_file_patterns`: List **ALL** likely files that will be modified.
    *   *Rule*: Use glob patterns (e.g. `src/auth/*.py`).
    *   *Expectation*: If a file is not matched here, the coder is forbidden from touching it.

## 2. `plan.spec_alignment.checklist` (The Contract)
*   `checklist`: A list of **Atomic Requirements**.
    *   `id`: Uppercase snake-case ID (stable, e.g. `CHK_AUTH_01`).
    *   `spec_ref`: **Structured Object**. `{ type, id, line_range, commit_hash }`.
        *   *Rule*: `commit_hash` is MANDATORY. Do not use placeholders.
    *   `description`: **Verbose, Atomic, and Self-Explanatory**.
        *   *Rule*: Use "Subject-Action-Constraint" format.
    *   `linked_test_expectation`: **CRITICAL**. A concrete test identifier or command (e.g. `pytest tests/module/test_feature.py::test_name`).
        *   *Expectation*: This serves as the "contract" for verification.
    *   `implementation`: **Execution Slots**.
        *   `status`: `pending`, `in_progress`, `verified`, `deferred`.
        *   `files_touched`: Files explicitly modified.
        *   `actions`: Atomic implementation steps.
            *   `type`: `file_create`, `file_edit`, `run_command`, `manual_verification`.
            *   `description`: Verbose action description.
            *   `target` / `command`: Mandatory based on type.

## 3. `plan.ambiguities` (Risk Management)
*   List ANY ambiguity that would affect implementation.
    *   `id`: unique kebab-case identifier.
    *   `description`: What is unclear?
    *   `source`: `spec`, `code`, `plan`, `mixed`, `review`.
    *   `severity`: `blocking` or `non_blocking`.
    *   `mitigation`: Required for non_blocking.
    *   `impact`: List of affected components/flows.
    *   `status`: `resolved`, `tracking`, `deferred`, `blocked`.

## 4. `plan.drift` (Sustainment)
*   `checks`: Define periodic drift checks.
    *   `target`: `api`, `schema`, `nfr`, `invariant`, `fixture`, `config`.
    *   `method`: `runtime-sample`, `log-diff`, `schema-diff`, `trace-replay`.
    *   `schedule`: hourly/daily/weekly/monthly or cron expression.
    *   `remediation_policy`: Explicit steps to fix.

## 5. `plan.review_requirements` (Verification Plan)
*   `test_commands`: Precision commands to run tests.
    *   *Rule*: must match `linked_test_expectation` commands.

## 6. `plan.docs_impact` (Documentation Update)
*   `status`: `required` or `not_required`.
    *   *Rule*: If code changes are planned, you MUST set `status: required` and list doc paths in `docs_touched`.

## 7. `plan.solution` (Architecture Sketch)
*   `architecture_sketch`: High-level description of the technical approach.
*   `sequence_of_concerns`: Ordered list of implementation phases (e.g., ["Models", "Views", "Tests"]).
*   `risks`: Array of identified technical risks.

## 8. `plan.context` (Existing Codebase Context)
*   `existing_structures`: Array of known code or non-code structures.
    *   *Rule*: Use strings for non-code artifacts, objects for code signatures.
    *   For code objects: `{ signature, source_file, line_range }` are required.
*   `coding_examples`: Optional array of illustrative code snippets.

## 9. `plan.security` (Security Considerations)
*   `status`: `not_applicable` or `planned`.
    *   If `not_applicable`: Provide `reason`.
    *   If `planned`: List `new_fixtures` (IDs) and `spec_mutations` (changes to specs).

## 10. `plan.delivery` (Observability & Monitoring)
*   `status`: `not_applicable` or `planned`.
    *   If `planned`: Define `dashboards` (with dashboard_id, nfr_refs) and `alerts` (with alert_id, nfr_ref, rule, severity).

## 11. `plan.docs` (Documentation Plan)
*   `status`: `not_applicable` or `planned`.
    *   If `not_applicable`: Provide `reason`.
    *   If `planned`: List `required_updates` with `path` and `update_summary`.

## 12. `plan.coverage_status` (Checklist Coverage Metrics)
*   `total`: Total checklist items.
*   `verified`: Count of verified items.
*   `deferred`: Count of deferred items.
*   `pending`: Count of pending items.

## 13. `plan.scope_validation` (Scope Acknowledgment)
*   `in_scope`: List of concerns IN scope.
*   `out_of_scope`: List of concerns OUT of scope.
*   `acknowledged`: Boolean, must be true if `out_of_scope` is non-empty.

# Heuristics For Completeness
1. **Every checklist item has a concrete `linked_test_expectation`** (not generic like "run tests").
2. **Every `spec_ref` has a valid 40-char SHA commit_hash** (no placeholders or zeros).
3. **`target_file_patterns` use explicit globs** (avoid `**/*` or empty arrays unless deferred).
4. **`docs_impact.status` is `required` if any non-doc file is in `target_file_patterns`**.
5. **Anchor (Step 16) MUST NOT contradict any `checklist[].id`, `scope_in`, or `scope_out` value in active Milestone contexts (16a/b/c)** — run drift comparison against each `spec/impl_context/*.json`.

# Best Practices
1. **Always validate drift** between Step 16 Anchor and active 16a/b/c contexts before emit.
2. **Use specific test commands**, not vague placeholders (e.g., `pytest tests/auth/test_login.py::test_success`).
3. **Document EVERY environmental dependency** in `docs_impact` (env vars, secrets, config files).
4. **Prefer atomic checklist items** (one testable behavior per item, not compound requirements).
5. **Link evidence explicitly** when marking items as `verified` (use `evidence_ref` field).

# Failure Modes (Pitfalls)
*   **Anchor Drift**: Producing a Step 16 context that conflicts with the specific Milestone contexts (16a/b/c). *Fix*: Anchor must be the union/root, not a distinct implementation plan.
*   **Lazy Scope**: Leaving `target_file_patterns` empty or using broad `**/*` patterns. *Fix*: Must be explicit glob patterns based on `spec/impl_context/*.json`.
*   **Hidden Dependencies**: Introducing code changes that require new env vars or secrets without documenting them in `docs_impact`. *Fix*: Check `env` usage.
*   **JSON dumps**: Dumping the JSON in the chat output. *Fix*: Only write the file.
*   **Schema Hallucination**: Using fields like `plan.tasks` (deprecated) or `metadata` (untyped). *Fix*: Strict adherence to the referenced step schema.

# Clarification Questions
- "Are there any active Milestone Contexts (16a/16b/16c) I should merge?"
- "Does this Step 16 Anchor require specific documentation updates beyond the standard set?"
- "Are there specific file patterns that should be strictly OUT of scope?"

# Schema Reference
- Schema URI: vc:16-impl-context
- Schema File: schema/16_impl_context.schema.json
- Schema Registry: tools/schema_registry.json

# Output Contract
```json
{
  "$schema": "vc:16-impl-context",
  "id": "step-16-example",
  "owner": "system",
  "created_at": "2026-02-08T00:00:00Z",
  "plan": {
    "status": "active",
    "summary": {
      "functional_summary": "Implement Core Authentication flow.",
      "scope_in": ["Login", "Logout", "Session Management"],
      "scope_out": ["OAuth", "MFA"],
      "target_file_patterns": ["src/auth/*.py", "tests/auth/*.py"]
    },
    "docs_impact": {
      "status": "required",
      "rationale": "New auth module requires API documentation updates.",
      "docs_touched": ["docs/api/auth.md"]
    },
    "spec_alignment": {
      "requirements_summary": [{ "theme": "Security", "summary": "Implement JWT handling" }],
      "checklist": [
        {
          "id": "CHK_AUTH_01",
          "spec_ref": {
            "type": "fr",
            "id": "fr-auth-login",
            "line_range": "L10-L20",
            "commit_hash": "a1b2c3d4e5f67890a1b2c3d4e5f67890a1b2c3d4"
          },
          "description": "User can login with valid credentials.",
          "linked_test_expectation": "pytest tests/auth/test_login.py::test_login_success",
          "nfr_refs": ["nfr-availability-uptime"],
          "fixture_ref": "fixture-auth-login",
          "checklist_status": "active",
          "implementation": {
            "status": "pending",
            "files_touched": ["src/auth/login.py"],
            "actions": [
              { "type": "file_create", "description": "Create login handler", "target": "src/auth/login.py" }
            ]
          }
        }
      ]
    },
    "ambiguities": [
      {
        "id": "amb-token-storage",
        "description": "Token storage mechanism not specified (in-memory vs Redis)",
        "source": "spec",
        "severity": "non_blocking",
        "mitigation": "Default to in-memory for MVP, Redis for production",
        "impact": ["session-management"],
        "status": "resolved"
      }
    ],
    "solution": {
      "architecture_sketch": "Flask Blueprint with JWT extended.",
      "sequence_of_concerns": ["Models", "Views", "Tests"],
      "risks": ["Token leakage in logs"]
    },
    "context": {
      "existing_structures": [
        { "signature": "class User(db.Model)", "source_file": "src/models.py", "line_range": "L1-L50" }
      ]
    },
    "review_requirements": { "test_commands": ["pytest tests/auth"] },
    "security": {
      "status": "planned",
      "new_fixtures": ["fix-auth-token-leak"],
      "spec_mutations": [
        { "ref": { "type": "nfr", "id": "nfr-sec-01" }, "change": "Add token rotation requirement", "reason": "Mitigate token replay attacks" }
      ]
    },
    "delivery": { "status": "not_applicable", "reason": "No observability changes required for initial implementation" },
    "drift": {
      "status": "planned",
      "checks": [
        { "check_id": "drift-auth-api", "target": "api", "method": "runtime-sample", "schedule": "daily", "remediation_policy": "Regenerate API fixtures from live endpoints" }
      ]
    }
  },
  "execution": {
    "files_touched": ["src/auth/login.py", "tests/auth/test_login.py"],
    "execution_results": [
      {
        "status": "passed",
        "outcome_description": "Login test passed with valid credentials",
        "reasoning": "Implemented JWT token generation and validation",
        "command": "pytest tests/auth/test_login.py::test_login_success",
        "evidence": "tests/auth/test_login.py::test_login_success PASSED",
        "evidence_ref": "artifacts/test_run_2026_02_08.log",
        "evidence_binding": {
          "timestamp": "2026-02-08T03:00:00Z",
          "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
          "exit_code": 0,
          "command": "pytest tests/auth/test_login.py::test_login_success"
        }
      }
    ],
    "critical_evidence": {
      "satisfied_checklist_ids": ["CHK_AUTH_01"],
      "passed_test_commands": ["pytest tests/auth"]
    }
  },
  "review": {
    "findings": [
      {
        "id": "rev-auth-01",
        "type": "docs",
        "severity": "minor",
        "spec_ref": {
          "type": "doc",
          "id": "doc-api-auth",
          "line_range": "L1-L10",
          "commit_hash": "b1c2d3e4f5a67890b1c2d3e4f5a67890b1c2d3e4"
        },
        "description": "API documentation missing error response codes",
        "related_checklist_ids": ["CHK_AUTH_01"],
        "metadata": { "source": "reviewer", "impact": "Documentation completeness" }
      }
    ],
    "ratings": { "spec_completeness": 5, "code_quality": 5, "tests_completeness": 5, "docs_completeness": 4, "metadata_usage": 5 },
    "verdict": "verified",
    "next_actions": "Update API documentation with error codes",
    "semantic_review": {
      "fr_coverage": [
        {
          "fr_id": "fr-auth-login",
          "satisfied": true,
          "evidence_summary": "Login handler implemented with JWT token generation and validation, confirmed by passing pytest tests/auth/test_login.py::test_login_success",
          "checklist_ids": ["CHK_AUTH_01"]
        }
      ],
      "hallucinated_features": [],
      "scope_delta": "No scope creep detected; implementation matches plan exactly."
    },
    "fixture_status": {
      "implemented_interfaces": ["api-auth-login"],
      "test_results": [{ "fixture_ref": "fix-auth-login-success", "status": "pass", "notes": "All assertions passed" }],
      "ci_status": "green"
    }
  },
  "canonical_refs_used": []
}
```

