# Step 16a · Implementation Planner

## Purpose
Produce a **machine-checkable blueprint** for implementation using the **Checklist-Driven Architecture**. Every piece of work must be:
1. **Traceable**: Linked to a specific spec requirement with commit hash
2. **Atomic**: One checklist item = one testable behavior
3. **Explicit**: Zero "common sense" or "standard implementation" references
4. **Evidence-Bound**: Every checklist item has a concrete `linked_test_expectation`

## Critical Changes from v1
- `plan.tasks` is **DELETED** — implementation now lives under `checklist[].implementation`
- `metadata` is **DELETED** — use `extensions` for structured data
- `spec_ref` is now a **structured object**, not a string
- `commit_hash` and `line_range` are **REQUIRED** for all spec references

## Tool Execution
Validate the generated JSON:
```bash
python -m specdev_tools.cli validate <path_to_artifact> --repo-root .
```

# Role
You are a senior software architect and planning assistant. Your job is to generate the **Implementation Context** for a single Roadmap Step (Step 16a).

Instead of prose, you emit a machine-checkable **JSON artifact** that defines the plan, checklist, and tasks for the coding agent.

# Context To Ingest
- **Roadmap**: Use the Step ID and description from `spec/14_roadmap.json` to scope the work.
- **Specs**: Ingest relevant Feature Specs (`04_fr_list`), Interfaces (`05`), and Invariants (`06`).
- **Codebase**: Scan existing files to populate `context.existing_structures` and `coding_patterns`.

# Operating Flow: Synthesize → Clarify → Emit
1.  **Scope**: Identify the exact functional scope (Themes: Schema, Logic, API).
2.  **Files**: List exactly which files need modification.
3.  **Checklist**: Convert spec requirements into atomic checklist items.
4.  **Implementation Slots**: Define execution slots (`checklist[].implementation`) for each item.
5.  **Emit**: Generate the JSON.

## FORBIDDEN ACTIONS (Immediate Rejection)

### Structural Violations
1. **NEVER** create `plan.tasks` — this field no longer exists
2. **NEVER** use untyped `metadata` — use structured `extensions` only
3. **NEVER** emit `step_id` — use only `id`
4. **NEVER** use `coding_patterns` — use `coding_examples` array

### Content Violations
1. **NEVER** create checklist item without `spec_ref.commit_hash`
2. **NEVER** use placeholder commit hashes (40 zeros)
3. **NEVER** leave `target_file_patterns` empty for active steps
4. **NEVER** write "standard implementation" or "as per common practice"
5. **NEVER** emit `linked_test_expectation` without corresponding `test_commands` entry

### Inference Violations
1. **NEVER** hallucinate `existing_structures` — cite actual source file
2. **NEVER** invent variable/class/function names not in spec
3. **NEVER** assume dependency installation — verify with `pip freeze`/`npm list`
4. **NEVER** create ambiguity without `severity` and `mitigation`

### Atomicity Violations
1. **NEVER** group multiple behaviors in one checklist item
2. **NEVER** create checklist item that spans multiple files
3. **NEVER** create implementation action that requires >2 file edits

# Field Definitions & Rules (MANDATORY)

You must populate the JSON fields according to these specific definitions and expectations, derived from the rigorous DevSpec standard.

## 1. `plan.summary` (The Step Summary)
*   `functional_summary`: A 1-paragraph summary of what this step accomplishes in the global architecture. Tightly anchor the step in the global architecture and local sub-threads.
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
        *   *Rule*: **NO ONE-LINERS**. Explain the "Why" and the "How" if it adds clarity.
        *   *Rule*: **Atomic means Indivisible**. If a requirement can be broken down into two checks, you MUST break it down.
    *   `type`: `behavior`, `constraint`, `validation`, `metadata`, `perf`, `logging`, `docs`.
    *   `layer`: `db`, `model`, `service`, `api`, `tests`, `docs`.
    *   `checklist_status`: `active` or `deferred`.
    *   `linked_test_expectation`: **CRITICAL**. A concrete test identifier or command (e.g. `pytest tests/module/test_feature.py::test_name`).
        *   *Expectation*: This serves as the "contract" for verification. Use specific test names, not just file paths.
    *   `implementation`: **Execution Slots** (Replaces `plan.tasks`).
        *   `status`: `pending`, `in_progress`, `verified`, `deferred`.
        *   `files_touched`: Files explicitly modified.
        *   `actions`: Atomic implementation steps.
            *   `type`: `file_create`, `file_edit`, `run_command`, `manual_verification`.
            *   `description`: Verbose action description.
            *   `target` / `command`: File or Command to run.

## 3. `plan.ambiguities` (Risk Management)
*   List ANY ambiguity that would affect implementation.
    *   `id`: kebab-case identifier (e.g. `amb-storage-device`).
    *   `description`: What is unclear?
    *   `severity`: `blocking` or `non_blocking`.
    *   `mitigation`: How should the coder handle this? (e.g., "Assume X specifically").
    *   *Rule*: If `blocking`, you must still plan the rest of the step but flag the blocker.
    *   *Rule*: For `non_blocking`, you MUST provide a `mitigation` or `assumption`.
    *   *Rule*: Use `metadata` to capture `source` and `impact` if available.

## 4. `plan.solution` (Architecture)
*   `architecture_sketch`: Explain data flow, component interactions, and how this fits into the lifecycle.
*   `sequence_of_concerns`: List the logical order of implementation (e.g., 1. Schema, 2. Models, 3. API).
*   `risks`: Identify tricky algorithms, migration safety, cascade deletes, or infinite recursion risks.

## 5. `plan.context` (Codebase awareness)
    *   `existing_structures` supports two valid forms:
        1) **String form** for non-code or mixed structures (e.g., shell/nginx/workflow context) including a concrete file path in the text.
        2) **Object form** for code signatures only: `{ "signature": "...", "source_file": "...", "line_range": "Lx-Ly" }`.
    *   For object form, `source_file` must be a repo-relative path ending in `.py`, `.ts`, `.js`, `.go`, or `.rs`.
    *   *Rule*: Do NOT hallucinate. If you can't see the file, do not list it.

## 6. `plan.tasks` (DELETED)
*   **NOTE**: This section is removed. All implementation logic must reside in `checklist[].implementation`.

## 6. `plan.tasks` (Execution Plan)
*   Treat each "thread" of work as a Parent Task.
    *   `task_id`: Unique ID (e.g. `TASK_login_impl`).
    *   `summary`: One-line summary.
    *   `files_to_touch`: Subset of `target_file_patterns`.
    *   `checklist_ids`: Explicitly list which requirements this task satisfies.
    *   `metadata`: Use `completeness_criteria` and `dependencies` here.
    *   `sub_tasks`: **Atomic Code Instructions** for the coder.
        *   *Rule*: **Hierarchy is Mandatory**. Parent Task = Logical Feature/Concern. Sub-Task = Specific Code Action (e.g. "Add field to User model").
        *   *Rule*: Each sub-task must be implementable in 1-2 file edits.
        *   *Rule*: **Atomic Sub-task**. Do not group actions. "Create Model" and "Create Migration" are TWO sub-tasks.

## 7. `plan.review_requirements` (Verification Plan)
*   `test_commands`: Precision commands to run tests.
    *   *Rule*: must match `linked_test_expectation` commands.
    *   *Expectation*: Include DB migration commands if needed (`alembic upgrade head`).
    *   *Rule*: Use `metadata` to capture `legacy_test_output` or specific success criteria.

## 8. `plan.security` (Red Team & Hardening)
*   `new_fixtures`: List new security fixtures to cover threats.
*   `spec_mutations`: Proposed hardening changes.
    *   *Heuristic*: **Threat Binding**: Every `new_fixture` must map to a concrete threat ID from Step 11/15.
    *   *Heuristic*: **Ambiguity Scrub**: Avoid vague "hardened security"; specify exactly what changed (e.g. "Added rate limit to /login").
    *   *Coverage Rule*: If `redteam_status` was Red, you MUST plan a remediation task.

## 9. `plan.delivery` (Ops & Monitoring)
*   `dashboards`: Define dashboards for critical NFRs.
*   `alerts`: Define alerts for high-severity NFRs.
    *   *Heuristic*: **Unit Alignment**: Alert rules (e.g. `latency > 500ms`) must match NFR units.
    *   *Heuristic*: **Coverage**: Every **High/Critical** NFR must have at least one Dashboard and Alert.
    *   *Heuristic*: **Actionability**: Alerts must include clear thresholds (e.g. "p99 > 200ms", not "latency is high").

## 10. `plan.drift` (Sustainment)
*   `checks`: Define periodic drift checks.
    *   *Target*: `api`, `schema`, `nfr`, `invariant`.
    *   *Method*: `runtime-sample`, `schema-diff`, `trace-replay`, `log-diff`.
    *   *Heuristic*: **Risk-Based Scheduling**: High-risk areas (Public APIs, Payment NFRs) need frequent checks (e.g. `hourly` or `daily`).
    *   *Heuristic*: **Concrete Remediation**: Remediation steps must specify *actions* and *owners* (e.g. "Rollback release", not "Fix it").
    *   *Pitfall*: Do not schedule checks using methods that don't exist in the tooling.

## 11. `plan.docs` (Documentation Update)
*   `required_updates`: List of docs to update.
    *   `path`: File path (e.g. `docs/user_guide.md`, `README.md`).
    *   *Rule*: Always check if `docs/api/openapi.json` needs generic updates.

## 12. Advanced Schema Fields
Use these fields to capture high-fidelity context that doesn't fit into standard columns.
*   **`metadata`**: A generic key-value map. You **MUST** use this to preserve lost context from legacy specs.
    *   **Standard Keys**:
        *   `source`: The origin of a requirement/ambiguity (e.g. "Slack thread").
        *   `impact`: The consequence of an issue (e.g. "Data loss risk").
        *   `proposed_assumption`: For non-blocking ambiguities.
        *   `completeness_criteria`: Critical "Definition of Done".
        *   `dependencies`: Blocking parent tasks.
        *   `legacy_test_output`: Expected output string for regression tests.
*   **`coding_examples`**: Structured multi-file snippets.
    *   Use this instead of `coding_patterns`.
    *   Format: `{ "title": "...", "description": "...", "code": "..." }`.

# Failure Modes (Pitfalls)
*   **Ambiguity Paralysis**: Planner finds a gap and stops. *Fix*: Raise a "Clarification" task or flag `blocking` ambiguity in `plan.ambiguities`.
*   **Checklist Fatigue**: Generating 50+ trivial items. *Fix*: Group related checks (but keep them atomic) or focus on high-risk areas.
*   **Security Blindness**: Ignoring Step 11 threats. *Fix*: Use **Threat Binding** to force coverage.
*   **Implementation Drift**: Plan ignores `target_file_patterns` constraints. *Fix*: Planner must strictly define file boundaries.
*   **Vagueness**: Relying on "common sense" or "standard implementation" in checklist descriptions. *Fix*: Be explicitly verbose and exhaustive.
*   **Verification Gap**: Emitting a plan without explicitly verifying that it covers *all* requirements. *Fix*: **Verify-First** heuristic.

# Output Rules
1.  Return exactly one fenced code block with language `json`.
2.  The JSON must validate against `schema/16_impl_context.schema.json`.
3.  Populate the `plan` object fully. Leave `execution` and `review` objects empty.

# Clarification Questions
- Which spec version covers this step?
- Are there any ambiguous requirements that need resolution before coding?
- Do we have existing tests we can extend, or must we create new ones?

# Embedded Schema
# Embedded Schema
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://specdev.local/schema/16_impl_context.schema.json",
  "title": "16_impl_context",
  "type": "object",
  "additionalProperties": false,
  "$defs": {
    "specRef": {
      "type": "object",
      "required": ["type", "id", "line_range", "commit_hash"],
      "properties": {
        "type": { "enum": ["fr", "api", "nfr", "inv", "fixture", "doc", "code"] },
        "id": { "type": "string" },
        "line_range": { "type": "string" },
        "commit_hash": { "type": "string", "pattern": "^[0-9a-f]{40}$" }
      }
    }
  },
  "properties": {
    "id": { "type": "string" },
    "owner": { "type": "string" },
    "created_at": { "type": "string" },
    "extensions": { "type": "object" },
    "plan": {
      "type": "object",
      "required": ["summary", "spec_alignment", "review_requirements"],
      "properties": {
        "summary": {
          "type": "object",
          "required": ["functional_summary", "scope_in", "target_file_patterns"],
          "properties": {
            "functional_summary": { "type": "string" },
            "scope_in": { "type": "array", "items": { "type": "string" } },
            "scope_out": { "type": "array", "items": { "type": "string" } },
            "target_file_patterns": { "type": "array", "items": { "type": "string" } }
          }
        },
        "spec_alignment": {
          "type": "object",
          "required": ["checklist"],
          "properties": {
            "requirements_summary": {
                "type": "array",
                "items": { "type": "object", "required": ["theme", "summary"], "properties": { "theme": { "type": "string" }, "summary": { "type": "string" } } }
            },
            "checklist": {
              "type": "array",
              "items": {
                "type": "object",
                "required": ["id", "spec_ref", "description", "linked_test_expectation"],
                "properties": {
                  "id": { "type": "string" },
                  "spec_ref": { "$ref": "#/$defs/specRef" },
                  "description": { "type": "string" },
                  "linked_test_expectation": { "type": "string" },
                  "checklist_status": { "enum": ["active", "deferred"] },
                  "implementation": {
                    "type": "object",
                    "required": ["status", "actions"],
                    "properties": {
                      "status": { "enum": ["pending", "in_progress", "verified", "deferred"] },
                      "files_touched": { "type": "array", "items": { "type": "string" } },
                      "actions": {
                        "type": "array",
                        "items": {
                          "type": "object",
                          "required": ["type", "description"],
                          "properties": {
                            "type": { "enum": ["file_create", "file_edit", "run_command", "manual_verification"] },
                            "description": { "type": "string" },
                            "target": { "type": "string" },
                            "command": { "type": "string" },
                            "evidence": {
                                "type": "object",
                                "required": ["type", "content"],
                                "properties": {
                                    "type": { "enum": ["log", "snippet", "screenshot"] },
                                    "content": { "type": "string" }
                                }
                            }
                          }
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        },
        "review_requirements": {
           "type": "object",
           "required": ["test_commands"],
           "properties": {
              "test_commands": { "type": "array", "items": { "type": "string" } }
           }
        }
      }
    }
  },
  "required": ["id", "plan"]
}
```

# Output Contract
```json
{
  "id": "step-api-core",
  "owner": "api",
  "created_at": "2025-01-01T00:00:00Z",
  "plan": {
    "summary": {
       "functional_summary": "Implement core API login",
       "scope_in": ["Login", "Logout"],
       "target_file_patterns": ["src/auth/*.py"]
    },
    "spec_alignment": {
      "requirements_summary": [
          { "theme": "Auth", "summary": "Implement JWT-based Login/Logout" }
      ],
      "checklist": [
        {
          "id": "CHK_AUTH_01",
          "spec_ref": {
             "type": "api",
             "id": "api-auth-login",
             "line_range": "L12-L15",
             "commit_hash": "a1b2c3d4e5f67890a1b2c3d4e5f67890a1b2c3d4"
          },
          "description": "POST /login returns JWT",
          "linked_test_expectation": "pytest tests/auth/test_login.py::test_jwt",
          "checklist_status": "active",
          "implementation": {
             "status": "pending",
             "actions": [
                 {
                    "type": "file_create",
                    "target": "src/auth/routes.py",
                    "description": "Create login endpoint"
                 }
             ]
          }
        }
      ]
    },
    "context": {
       "existing_structures": [{ "signature": "class User", "source_file": "src/models.py" }]
    },
    // plan.tasks REMOVED
    "review_requirements": {
      "test_commands": ["pytest tests/auth/"]
    }
  }
}
```
