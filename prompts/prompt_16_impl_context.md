# Step 16 · Implementation Context (Trinity Anchor)

## Purpose
Create or update the **canonical Step 16 anchor** at `spec/16_impl_context.json`.
This file is the **root reference** for the Trinity Loop and exists alongside per‑milestone execution files in `spec/impl_context/`. It must:
1. Summarize the current execution scope.
2. Declare traceable checklist items for the active implementation cycle.
3. Record documentation impact decisions and seed provenance.
4. act as the union/root of all active milestone implementation contexts (16a/16b/16c).

## When To Use This Prompt
- You need a **single, canonical Step 16** artifact in `spec/`.
- You want a root view of the current Trinity cycle that references active milestone contexts.
- You are aligning a repo to the toolkit version that expects `spec/16_impl_context.json`.

## Tool Execution
Validate the generated JSON:
```bash
./tools/run_specdev.sh validate spec/16_impl_context.json --repo-root ./devspec_toolkit
```

# Role
You are a senior software architect producing the Step 16 **Trinity Anchor**.
Generate a **machine‑checkable JSON artifact** to the file system that captures the plan,
implementation checklist, and review expectations for the *current* execution cycle.

## Output Mode (Compatibility)
- **Trinity harness mode (canonical):**
  - Phase A: questions only (if blocked).
  - Phase B: write/update artifact file on disk and return concise status (artifact path + validation result).
- **Manual coding-agent mode (Codex-style default):**
  - Write/update `spec/16_impl_context.json` directly.
  - Return a short confirmation with validation outcome.
  - Do not emit fenced JSON in chat.

## Zero-Assumption Protocol (Mandatory)
You must treat this step as evidence compilation, not creative generation.

1. Every non-trivial field must be backed by a concrete source artifact read in this run.
2. If source evidence is missing, return questions-only output; do not fill with defaults except schema-safe empty values explicitly allowed by prompt rules.
3. Do not infer step scope, checklist content, or file patterns from prior chats. Use only current governed artifacts.
4. Do not invent `spec_ref` IDs, `commit_hash` values, file paths, or test commands.
5. If two sources conflict, record an ambiguity and block final emission until resolved.
6. Replace vague language ("standard", "common", "obvious", "etc.") with explicit statements or remove it.
7. Before emit, run a hallucination scrub: verify every identifier in checklist/spec refs appears in source files.

# Seed Order & Mandatory Sources
- Read `spec/common/seed_manifest.json` first.
- Use `step_requirements["16"]` if present. If missing, use the union of `16a/16b/16c`.
- Ingest required seeds in order before any other context.
- Populate `seed_refs` with the seeds actually used.
- If a required seed is missing or stale, stop and request it before proceeding.

# Context To Ingest
- **Roadmap**: Step sequencing and current milestone selection from `spec/14_roadmap.json`.
- **Implementation Plan**: Tech stack and constraints from `spec/09_impl_plan.json`.
- **Core Specs**: Relevant FRs (04), APIs (05), Invariants (06), NFRs (07), Fixtures (08).
- **Active Impl Contexts**: Enumerate any active files in `spec/impl_context/` (16a/b/c).
- **Documentation Map**: `README.md` and `docs/README.md` for current doc surface.

# Operating Flow (MANDATORY)
1. **Context Review**: Resolve seeds and ingest required sources.
2. **Scope**: Identify the exact execution scope for the current cycle.
3. **Active Contexts**: List `spec/impl_context/*.json` files in `plan.context.existing_structures`.
4. **Drift Check**: Verify that the Anchor (Step 16) does not conflict with Milestone contexts (16a/b/c).
5. **Checklist**: Convert relevant spec requirements into atomic checklist items.
6. **Docs Impact**: Decide whether docs updates are required and list impacted docs.
7. **Emit**: Produce the anchor artifact.

Roadmap/progress status mutation is owned by Verifier + Orchestrator closure logic, not by anchor generation.

# FORBIDDEN ACTIONS (Immediate Rejection)
1. **NEVER** hallucinate `step_id` or use loose references.
2. **NEVER** omit `commit_hash` in `spec_ref`.
3. **NEVER** emit incomplete JSON or use placeholder values.
4. **NEVER** use `plan.tasks` or `metadata`.

# Field Definitions & Rules (MANDATORY)

> **Schema Authority**: The schema (`schema/16_impl_context.schema.json`) is the single source of truth for field types, ranges, and required properties. The rules below are behavioral guidelines for how to populate them. When in conflict, the schema wins.

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
    *   For code objects: `{ signature, source_file }` are required; `line_range` is strongly recommended for traceability.
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
5. **Anchor (Step 16) does not conflict with Milestone contexts (16a/b/c)** (check for drift).

# Self-Audit Gate
Before emitting `spec/16_impl_context.json`, verify:
- [ ] All `spec_ref.commit_hash` values are valid 40-char SHAs (not `0000...`).
- [ ] Every checklist item with `checklist_status: active` has an `implementation` block.
- [ ] `target_file_patterns` are explicit (no `**/*` unless deferred).
- [ ] If `docs_impact.status` is `required`, `docs_touched` has at least one entry.
- [ ] `plan.review_requirements` exists and contains test commands for active plans.
- [ ] If `plan.status` is `deferred`, `deferred_reason` is provided.
- [ ] No active Milestone Contexts (16a/b/c) conflict with this Anchor.

# Best Practices
1. **Always validate drift** between Step 16 Anchor and active 16a/b/c contexts before emit.
2. **Use specific test commands**, not vague placeholders (e.g., `pytest tests/auth/test_login.py::test_success`).
3. **Document EVERY environmental dependency** in `docs_impact` (env vars, secrets, config files).
4. **Prefer atomic checklist items** (one testable behavior per item, not compound requirements).
5. **Link evidence explicitly** when marking items as `verified` (use `evidence_ref` field).

# Quick Reference

| Field | Type | Required | Purpose |
|-------|------|----------|----------|
| `plan.summary` | object | yes | Scope definition (functional_summary, scope_in/out, target_file_patterns) |
| `plan.spec_alignment.checklist` | array | yes | Atomic requirements with spec_ref, linked_test_expectation, implementation |
| `plan.ambiguities` | array | no | Risk management (blocking/non_blocking issues) |
| `plan.solution` | object | no | Architecture sketch and sequence of concerns |
| `plan.context` | object | no | Existing codebase structures and coding examples |
| `plan.review_requirements` | object | yes | Verification plan (test_commands, guidelines) |
| `plan.docs_impact` | object | yes | Documentation impact assessment |
| `plan.security` | object | no | Security fixtures and spec mutations |
| `plan.delivery` | object | no | Observability (dashboards, alerts) |
| `plan.drift` | object | no | Sustainment (periodic drift checks) |
| `plan.docs` | object | no | Documentation plan |
| `plan.coverage_status` | object | no | Metrics (total, verified, deferred, pending) |
| `plan.scope_validation` | object | no | Scope acknowledgment |

# Failure Modes (Pitfalls)
*   **Anchor Drift**: Producing a Step 16 context that conflicts with the specific Milestone contexts (16a/b/c). *Fix*: Anchor must be the union/root, not a distinct implementation plan.
*   **Lazy Scope**: Leaving `target_file_patterns` empty or using broad `**/*` patterns. *Fix*: Must be explicit glob patterns based on `spec/impl_context/*.json`.
*   **Hidden Dependencies**: Introducing code changes that require new env vars or secrets without documenting them in `docs_impact`. *Fix*: Check `env` usage.
*   **Contract Drift**: Returning chat artifact dumps instead of disk-first artifact writes. *Fix*: write artifact on disk and return concise status only.
*   **Schema Hallucination**: Using fields like `plan.tasks` (deprecated) or `metadata` (untyped). *Fix*: Strict adherence to `devspec_toolkit/schema/16_impl_context.schema.json`.

# Clarification Questions
- "Are there any active Milestone Contexts (16a/16b/16c) I should merge?"
- "Does this Step 16 Anchor require specific documentation updates beyond the standard set?"
- "Are there specific file patterns that should be strictly OUT of scope?"

# Canonical Schema Reference
- Use `devspec_toolkit/schema/16_impl_context.schema.json` as the only schema source of truth.
- Do not rely on copied or embedded schema fragments in prompts.
- Validate generated artifacts with `./tools/run_specdev.sh validate <path_to_artifact> --repo-root ./devspec_toolkit`.

# Output Contract (Schema-Valid Example)
Manual mode note:
- In manual coding-agent workflow, writing the file directly plus concise confirmation is valid.
- This JSON block is reference-only; do not emit it in chat.
- For richer schema-valid examples, reuse fixtures under `tests/fixtures/step_16/`.

```json
{
  "$schema": "https://specdev.local/schema/16_impl_context.schema.json",
  "id": "step-impl-anchor-minimal",
  "owner": "api",
  "created_at": "2024-01-01T00:00:00Z",
  "seed_refs": [
    { "seed_id": "seed-overview" },
    { "seed_id": "seed-tech-stack" }
  ],
  "plan": {
    "status": "active",
    "summary": {
      "functional_summary": "Minimal anchor for active implementation cycle.",
      "scope_in": ["core"],
      "scope_out": ["extras"],
      "target_file_patterns": ["src/main.py", "src/auth.py"]
    },
    "spec_alignment": {
      "requirements_summary": [
        { "theme": "Core Logic", "summary": "Implement core business logic" }
      ],
      "checklist": [
        {
          "id": "REQ_CORE_001",
          "spec_ref": {
            "type": "fr",
            "id": "fr-core-login",
            "line_range": "L10-L20",
            "commit_hash": "a1b2c3d4e5f61234567890123456789012345678"
          },
          "description": "Implement login function",
          "type": "behavior",
          "layer": "service",
          "linked_test_expectation": "pytest tests/auth/test_login.py::test_login_success -q",
          "nfr_refs": ["nfr-availability-uptime"],
          "fixture_ref": "fixture-login-success",
          "implementation": {
            "status": "in_progress",
            "files_touched": ["src/auth.py"],
            "actions": [
              {
                "type": "file_create",
                "target": "src/auth.py",
                "description": "Create auth module"
              }
            ]
          }
        }
      ]
    },
    "docs_impact": {
      "status": "required",
      "rationale": "Code changes require documentation updates for traceability.",
      "docs_touched": ["README.md"]
    },
    "review_requirements": {
      "guidelines": "Run focused unit checks for checklist scope.",
      "test_commands": ["pytest tests/auth/test_login.py::test_login_success -q"]
    }
  }
}
```
