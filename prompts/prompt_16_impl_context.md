# Step 16 · Implementation Context (Trinity Anchor)

> **REQUIRED**: Before starting, read `$TOOLKIT_ROOT/docs/prompts/shared_expectations.md` in full. All directives in that document apply to this step unless explicitly overridden below. Do not proceed without reading it.

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
- **14_roadmap.json**: active milestone, tasks, and fr_refs — primary source for implementation context; milestone identifiers, deliverables, scheduling, and status fields drive checklist coverage mapping and roadmap sync updates
- **04_fr_list.json**: FR statements and acceptance criteria for the active milestone; functional requirement identifiers, acceptance criteria, and priority levels directly populate checklist spec_ref entries and linked_test_expectations
- **05_interface_contracts.json**: API contracts to implement; endpoint definitions, request/response schemas, and method constraints bind checklist items to concrete interface contracts

#### Reference Sources (context only)
- **00_charter.json**: Product vision, success criteria, and stakeholder constraints that bound the execution scope and inform scope_in/scope_out decisions
- **01_capabilities.json**: Capability identifiers and descriptions used to trace checklist items back to declared product capabilities
- **02_system_sketch.json**: component boundaries and trust zones; component topology, integration boundaries, and data flow paths that determine target_file_patterns and architecture_sketch content
- **02a_delivery_baseline.json**: Environment definitions, deployment targets, and infrastructure constraints that inform delivery status and drift check scheduling
- **03_glossary.json**: Canonical term definitions and domain vocabulary enforced in checklist descriptions and functional_summary text
- **06_invariants.json**: system invariants and enforcement conditions that inform checklist validation items and delivery constraints
- **07_nfrs.json**: NFR thresholds and availability targets that inform checklist nfr_refs and delivery alert rules
- **08_fixtures.json**: Test fixture identifiers, target bindings, and expected outcomes used to populate fixture_ref fields and linked_test_expectation commands
- **09_impl_plan.json**: Milestone definitions, task decompositions, and tech stack constraints that determine implementation sequencing and milestone status tracking
- **10_governance.json**: Commit message patterns, PR rules, and approval workflows that constrain how implementation changes are committed and reviewed
- **11_redteam.json**: Threat identifiers, attack vectors, and severity ratings used to populate security fixture bindings and remediation checklist items
- **12_ci_gates.json**: CI pipeline stage definitions, gate conditions, and required checks that inform review_requirements test_commands and verification expectations
- **13_extension_generator.json**: Extension point declarations and plugin interface contracts used to identify additional target_file_patterns for extensibility concerns
- **13a_completeness_assessment.json**: Coverage gap analysis, missing spec items, and completeness scores used to inform scope boundary decisions
- **15_scaffold.json**: existing scaffold structure; generated file structure, directory layout, and scaffold templates that ground target_file_patterns and existing_structures references

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
- Schema URI: vc:16-anchor
- Schema File: schema/16_anchor.schema.json
- Schema Registry: tools/schema_registry.json

# Output Contract
```json
{
  "$schema": "vc:16-anchor",
  "id": "step-16-example",
  "owner": "api",
  "created_at": "2026-02-08T00:00:00Z",
  "artifact_role": "anchor",
  "canonical_refs_used": [],
  "plan": {
    "summary": {
      "functional_summary": "Implement Core Authentication flow — login, logout, and session management across two milestones.",
      "scope_in": ["login-endpoint", "logout-endpoint", "session-management"],
      "scope_out": ["oauth-flows", "mfa", "third-party-sso"],
      "target_file_patterns": ["src/auth/*.py", "tests/auth/*.py"]
    },
    "ambiguities": [
      {
        "id": "amb-token-ttl",
        "description": "JWT token TTL not confirmed by security team — 24h vs 8h options remain open.",
        "severity": "medium",
        "status": "tracking"
      }
    ],
    "drift": {
      "checks": [
        "Verified ms-auth scope_in does not overlap anchor scope_out (2026-02-10)",
        "Verified ms-session fr_refs do not conflict with ms-auth fr_refs (2026-02-12)"
      ]
    },
    "milestone_index": [
      {
        "milestone_id": "ms-auth",
        "context_path": "spec/impl_context/ms_auth_plan.json",
        "status": "done",
        "fr_refs": ["fr-user-login", "fr-token-refresh"],
        "checklist_id_prefix": "AUTH",
        "summary": "Auth token issuance — all 4 checklist items verified, CI green"
      },
      {
        "milestone_id": "ms-session",
        "context_path": "spec/impl_context/ms_session_plan.json",
        "status": "active",
        "fr_refs": ["fr-session-create", "fr-session-revoke"],
        "checklist_id_prefix": "SESSION",
        "summary": "Session management — 2/4 checklist items in progress"
      }
    ]
  }
}
```

