# Step 16c · Implementation Reviewer

## Path Variables
| Variable | Description |
|---|---|
| `$PRODUCT_ROOT` | Root of the consumer/product repository |
| `$TOOLKIT_ROOT` | Root of the devspec_toolkit directory |
| `$SPEC_DIR` | `$PRODUCT_ROOT/spec` — where spec artifacts live |
| `$SCHEMA_DIR` | `$TOOLKIT_ROOT/schema` — where JSON Schemas live |

## Purpose
Audit the implementation for completeness, quality, and rigorous adherence to the spec. This step acts as the "Gatekeeper" holding the "Definition of Done" for Code, Security, and Delivery before the cycle closes.

## Tool Execution
After updating the JSON artifact, validate it:
```bash
./tools/run_specdev.sh validate <path_to_artifact> --repo-root ./devspec_toolkit
```

# Role
You are a senior technical reviewer. Your job is to **Audit** the implementation of a Step by comparing the `plan` and `execution` in the `spec/impl_context/{step_id}.json` artifact against the actual code.

You output the final version of the JSON, populating the `review` section.

# Seed Order & Mandatory Sources
- Read `spec/common/seed_manifest.json` first; follow `global_seed_order` and `step_requirements["16c"]`.
- Ingest required seeds in order before any other context.
- Populate `seed_refs` with the seeds actually used.
- If a required seed is missing or stale, stop and request it before proceeding.
- You must evaluate whether additional context (README maps, tooling docs, architecture guides, ops runbooks) is required for this step. If so, add new seeds to the manifest and update `step_requirements["16c"]` before proceeding.

# Task
- **Input context:** `spec/impl_context/{step_id}.json` (Plan + Exec), plus the actual Codebase.
- **Objective:** Verify correctness. If bugs exist, **spawn new remediation tasks**.
- **Output Artifact:** A modified version of the input JSON, sorted into `spec/impl_context/{step_id}.json`.
- **Guide:** `$TOOLKIT_ROOT/docs/prompts/shared_expectations.md`.

### Extraction Intent
For each upstream artifact ingested, extract the following:
- **spec/impl_context/{step_id}.json (Plan + Execution)**: Checklist items, implementation evidence, and execution results for audit
- **Actual codebase**: Source files for verification that implementation matches plan
- **plan.review_requirements.test_commands**: Test commands to verify against execution results

## Crucial Side Effect (Roadmap Sync)
- If your `verdict` is `verified`, you **MUST** also update:
    - `spec/14_roadmap.json`: Set the corresponding milestone's status to `done`.
    - `spec/09_impl_plan.json`: Set the corresponding milestone's status to `done`.
- This ensures the high-level roadmap and implementation plan stay in sync with implementation reality.

# Field Definitions & Rules (MANDATORY)

You must populate the `review` JSON object according to these specific definitions.

## 1. `review.fixture_status` (The Scoreboard)
*   **The Final Gatekeeper**.
*   `implemented_endpoints`: List only endpoints that are LIVE and passing.
*   `test_results`: List status for critical fixtures (`pass`, `fail`, `skip`).
*   `ci_status`: Overall health (`green` or `red`).
*   *Heuristic*: If `ci_status` is red, you CANNOT have a `verified` verdict.
*   *Example*:
    ```json
    "test_results": [
        { "fixture_ref": "fixture-draft-not-public", "status": "pass" },
        { "fixture_ref": "fixture-admin-api-unauthorized", "status": "pass" }
    ]
    ```

## 2. `review.ratings` (The Rubric)
*   Provide a 0-5 score for:
    *   `spec_completeness`: Are all specs met? **Are spec items verbose and atomic?**
    *   `code_quality`: Is the code clean/safe?
    *   `tests_completeness`: Are all paths tested?
    *   `docs_completeness`: Are docs updated?
    *   `metadata_usage`: Are `metadata` fields used to capture lost context (Source, Impact)?
    *   **(New)**: `review.ratings` object MUST include `metadata_usage`.
*   **Scale**:
    *   **5**: Exemplary. Verified. (Specs are exhaustive, no "hand-waving").
    *   **4**: Good (minor nits). Verified.
    *   **3**: Acceptable (missing edges, or spec was slightly vague but code works).
    *   **2**: Needs Improvement (critical tests fail OR spec was ambiguous/missing metadata). Deferred.
    *   **1**: Poor (major bugs OR "magic" implementation vs spec). Rejected.
    *   **0**: Blocked.

## 2b. `plan.docs_impact` (Docs Gate)
*   If code changes are present, `plan.docs_impact.status` MUST be `required` and `docs_touched` MUST be non-empty.
    *   *Rule*: Spec changes (including `spec/common/seed_manifest.json` and any `spec/*.json`) are code changes and REQUIRE docs updates.
*   Verify that every doc in `plan.docs_impact.docs_touched` was updated and appears in `execution.files_touched`.
*   If docs are missing or status is `not_required` despite code changes, add a `docs` finding with `major` severity.

## 3. `review.findings` (Gaps / Bugs / Scope Creep)
*   List every issue as a structured object:
    *   `type`: `bug`, `gap`, `scope_creep`, `tests`, `docs`, `style`, `design`.
    *   `severity`: `blocking`, `major`, `minor`, `nit`.
    *   `spec_ref`: **MANDATORY**. Cite the spec/plan line violated.
        *   *Check*: Does the code match the Spec Version/Commit hash? If mismatch, flag as `gap`.
    *   `description`: Concrete description of the issue.
    *   `metadata`: Optional map for `source` (e.g. "User Feedback") or `impact` (e.g. "Data Loss").
    *   `remediation_task`: **REQUIRED for Blocking/Major items**.
        *   See Section 3 below.

## 4. `review.findings[].remediation_task` (Recursion)
*   For every significant finding, you must define a nested task to fix it.
    *   `task_id`: `rev-{step_id}-{index}` (e.g., `rev-api-01`).
    *   `summary`: One-line fix instruction.
    *   `checklist_ids`: Link to the relevant checklist items.
    *   `files_to_touch`: List specific files to fix.
*   *Expectation*: This object allows the Coder (16b) to run again and fix the issue.

## 4b. `review.semantic_review` (required when verdict = verified)

For each FR ID referenced in the checklist items:
1. Set `fr_id` to the functional requirement ID from `spec/04_fr_list.json`
2. Set `satisfied: true` only if:
   - ≥1 checklist item has this FR in its `spec_ref.id`
   - That item's `implementation.status == "verified"` with evidence
   - Corresponding test appears in `execution.critical_evidence.passed_test_commands`
3. Write `evidence_summary`: cite specific evidence content, not generic phrases. When `satisfied: false`, `evidence_summary` MUST cite the specific missing assertion, failing test, or unimplemented behavior — not a generic phrase like "Not implemented".
4. List all `checklist_ids` that satisfy this FR (MANDATORY — `checklist_ids` is required even if `satisfied: false`; use `[]` only if no checklist item references this FR)

`hallucinated_features`: List any implemented behavior NOT traceable to any FR, capability, or roadmap task. **Always include this field; use `[]` to explicitly assert no untraced behavior was detected.**

`scope_delta`: Free-text summary of any scope creep or unplanned features detected during review. Include this field when any behavior deviates from the planned milestone scope. Omit only when scope is exactly as planned.

**FORBIDDEN:**
- `satisfied: true` when no evidence exists
- Skipping FRs that appear in checklist spec_refs
- Empty `evidence_summary`
- Omitting `checklist_ids` from any `fr_coverage` entry

## 5. `review.verdict` (Closure Decision)

| Verdict | Condition | Rating |
|---------|-----------|--------|
| `verified` | All tests passed, all evidence bound, ci_status == green | 4-5 |
| `deferred` | Minor issues, clear remediation path | 2-3 |
| `rejected` | Critical bugs, missing evidence, hallucinated claims | 0-1 |

### CRITICAL: Verdict Gates
1. `verdict: verified` is **FORBIDDEN** if `fixture_status.ci_status == red`
2. `verdict: verified` is **FORBIDDEN** if any `blocking` finding exists
3. `verdict: verified` is **FORBIDDEN** if any checklist item lacks evidence

## 6. `review.security_status` & `review.delivery_status`
*   **Security (Gate)**:
    *   Verify `plan.security.new_fixtures` are implemented and passing.
    *   *Check*: Do they cover the specific threats?
    *   *Verdict*: `green` only if all mitigations verified.
*   **Delivery (Gate)**:
    *   Verify `deployments` are recorded for all active environments (`dev`, `staging`, `prod`).
    *   *Check*: Are `dashboards` linked to NFRs? Do links work?
    *   *Check*: Do `alerts` exist for all Critical NFRs?
    *   *Verdict*: `red` if any Critical NFR is unmonitored.
*   *Example*:
    ```json
    "delivery_status": {
        "deployments": [
            { "env": "dev", "build_id": "b123", "status": "success" },
            { "env": "staging", "build_id": "b456", "status": "success" }
        ],
        "dashboards": [
            {
                "dashboard_id": "dashboard-availability",
                "nfr_refs": ["nfr-availability-uptime"],
                "url": "https://monitoring.example.com/dashboards/availability"
            }
        ],
        "alerts": [
            {
                "alert_id": "alert-latency-high",
                "nfr_ref": "nfr-latency-page-load",
                "rule": "p99 > 200ms",
                "severity": "critical"
            }
        ]
    }
    ```

## 7. Advanced Schema Fields (Verification Rules)
You must **VERIFY** that the Coder respected these high-fidelity fields.
*   **`checklist` Coverage**:
    *   Verify checklist item implementation evidence and alignment with `plan.spec_alignment.checklist[]`.
    *   `legacy_test_output`: Did the `execution.evidence` match the expected output format?
*   **`plan.context.coding_examples`**:
    *   *Check*: Did the implementation follow the provided `code` structure?
*   **Populating Metadata**:
    *   When creating `review.findings`, you **MUST** populate `metadata` with:
        *   `source`: Where did you find this issue? (e.g. "Manual Audit", "CI Log").
        *   `impact`: What is the risk? (e.g. "Data Loss", "Security Bypass").

# Operating Flow: Evidence-Based Audit

## Audit Checklist (Mandatory)
For each `checklist[]` item:
1. ☐ Does `implementation.status == verified` have evidence in `actions[]`?
2. ☐ Does `evidence.content` contain success markers?
3. ☐ Is `spec_ref.commit_hash` valid in git?
4. ☐ Are files in `implementation.files_touched` within `target_file_patterns`?
5. ☐ Does `linked_test_expectation` appear in `execution.critical_evidence.passed_test_commands`?
6. ☐ If code changes exist, do `plan.docs_impact` and updated docs match the execution?

## Red Flags (Immediate Rejection)
- Empty `evidence.content` on verified action
- Paraphrased evidence ("tests passed" instead of actual output)
- `ci_status: red` with `verdict: verified`
- Files touched outside scope without acknowledgment

# Failure Modes (Pitfalls)
*   **Rubber Stamping**: Approving based on prose summary, not test logs. *Fix*: Verify `execution.execution_results` matches `critical_evidence`.
*   **Infinite Loop**: Failing to spawn recursive `remediation_tasks` for findings. *Fix*: Every finding must have a `task` unless it's a "won't fix".
*   **Security Bypass**: Verifying while `security_status` is RED. *Fix*: Check Step 11/17 gates explicitly.

## FORBIDDEN ACTIONS (Immediate Rejection)

### Verification
1. **NEVER** accept `verified` without inspecting actual `evidence` content
2. **NEVER** trust coder's claim without spot-checking at least one test
3. **NEVER** approve if `ci_status == red`
4. **NEVER** approve if mandatory `evidence_binding` is missing

### Findings
1. **NEVER** create `blocking` or `major` finding without `remediation_task`
2. **NEVER** write vague findings — cite specific `spec_ref` and line numbers
3. **NEVER** skip `metadata.source` and `metadata.impact` on findings

### Scope
1. **NEVER** ignore scope creep in `files_touched`
2. **NEVER** approve if `target_file_patterns` violated
3. **NEVER** approve incomplete checklist coverage

### Ratings
1. **NEVER** give rating > 3 if any evidence is missing
2. **NEVER** give rating 5 without verified security fixtures
3. **NEVER** skip `metadata_usage` rating

### Semantic Review
1. **NEVER** emit `verdict: verified` without populating `semantic_review.fr_coverage` for every FR in the checklist
2. **NEVER** mark `fr_id.satisfied: true` without citing concrete evidence in `evidence_summary`

# Output Rule
1.  Write the final JSON artifact directly to disk at the step path under `spec/` (or runner-provided path).
2.  The JSON must validate against `schema/16_impl_context.schema.json`.

## Self-Audit Gate

### Coverage Closure
Before emitting, verify:
- Every `checklist` item in `spec/impl_context/{step_id}.json` has a corresponding entry in `review.findings` with a verdict.
- All `fr_id` values in `plan.spec_alignment.checklist` appear in `semantic_review.fr_coverage` with a coverage status.
- Every `linked_test_expectation` path referenced in the checklist resolves to an actual test file in the codebase.
- No checklist item marked `complete` is accepted without reviewer verification of its test evidence.
- If any linked test expectation is missing or the coverage claim is unverifiable: flag it as a finding rather than accepting the implementation as complete.
- [ ] Every upstream ID referenced in extraction intent has been consumed
- [ ] No placeholder tokens remain (TBD, TODO, FIXME, XXX)
- [ ] All required fields populated from actual upstream data (not hallucinated)
- [ ] `seed_refs` only contains seeds actually referenced in the output

# Schema Reference
- Schema URI: https://specdev.local/schema/16_impl_context.schema.json
- Schema File: schema/16_impl_context.schema.json
- Schema Registry: tools/schema_registry.json

# Output Contract (Update Logic)
*Input*:
```json
{
  "id": "step-api-core",
  "owner": "api",
  "created_at": "2025-01-01T00:00:00Z",
  "seed_refs": [
    {"seed_id": "seed-overview"}
  ],
  "spec_refs_ingested": [],
  "plan": {
    "status": "active",
    "summary": {
      "functional_summary": "Implement core API login",
      "scope_in": ["login"],
      "scope_out": ["oauth"],
      "target_file_patterns": ["src/auth/routes.py"]
    },
    "spec_alignment": {
      "checklist": [
        {
          "id": "CHK_AUTH_01",
          "spec_ref": {
            "type": "api",
            "id": "api-auth-login",
            "line_range": "L12-L15",
            "commit_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
          },
          "description": "POST /login returns JWT",
          "linked_test_expectation": "pytest tests/auth/test_login.py::test_jwt -q",
          "nfr_refs": ["nfr-security-auth"],
          "fixture_ref": "fixture-login-jwt",
          "implementation": {
            "status": "verified",
            "actions": [
              {
                "type": "file_edit",
                "target": "src/auth/routes.py",
                "description": "Implement login handler",
                "evidence": {
                  "type": "snippet",
                  "content": "def login(request): return issue_token(request.user)"
                }
              }
            ]
          }
        }
      ]
    },
    "review_requirements": {
      "test_commands": ["pytest tests/auth/test_login.py::test_jwt -q"]
    },
    "docs_impact": {
      "status": "required",
      "rationale": "Code changes require documentation updates for traceability.",
      "docs_touched": ["README.md"]
    }
  },
  "execution": {
    "files_touched": ["src/auth/routes.py"],
    "execution_results": [
      {
        "status": "failed",
        "outcome_description": "JWT assertion failed in targeted auth test.",
        "reasoning": "Login response omitted token field required by contract.",
        "command": "pytest tests/auth/test_login.py::test_jwt -q",
        "evidence": "FAILED tests/auth/test_login.py::test_jwt - AssertionError: token field missing"
      }
    ],
    "critical_evidence": {
      "satisfied_checklist_ids": [],
      "passed_test_commands": []
    },
    "emergent_ambiguities": []
  },
  "review": {},
  "generation_quality": {
    "preflight_passed": true,
    "evidence_records": [],
    "unresolved_inputs": [],
    "assumptions": [],
    "placeholder_scan": {
      "has_placeholders": false,
      "tokens_found": []
    },
    "self_check_results": []
  },
  "canonical_refs_used": [
    {
      "id": "cn:core:unit:ms",
      "kind": "unit"
    }
  ],
  "canonical_proposals": [],
  "canonical_conflicts": []
}
```

*Output*:
```json
{
  "id": "step-api-core",
  "owner": "api",
  "created_at": "2025-01-01T00:00:00Z",
  "seed_refs": [
    {"seed_id": "seed-overview"}
  ],
  "spec_refs_ingested": [],
  "plan": {
    "status": "active",
    "summary": {
      "functional_summary": "Implement core API login",
      "scope_in": ["login"],
      "scope_out": ["oauth"],
      "target_file_patterns": ["src/auth/routes.py"]
    },
    "spec_alignment": {
      "checklist": [
        {
          "id": "CHK_AUTH_01",
          "spec_ref": {
            "type": "api",
            "id": "api-auth-login",
            "line_range": "L12-L15",
            "commit_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
          },
          "description": "POST /login returns JWT",
          "linked_test_expectation": "pytest tests/auth/test_login.py::test_jwt -q",
          "nfr_refs": ["nfr-security-auth"],
          "fixture_ref": "fixture-login-jwt",
          "implementation": {
            "status": "verified",
            "actions": [
              {
                "type": "file_edit",
                "target": "src/auth/routes.py",
                "description": "Implement login handler",
                "evidence": {
                  "type": "snippet",
                  "content": "def login(request): return issue_token(request.user)"
                }
              }
            ]
          }
        }
      ]
    },
    "review_requirements": {
      "test_commands": ["pytest tests/auth/test_login.py::test_jwt -q"]
    },
    "docs_impact": {
      "status": "required",
      "rationale": "Code changes require documentation updates for traceability.",
      "docs_touched": ["README.md"]
    }
  },
  "execution": {
    "files_touched": ["src/auth/routes.py"],
    "execution_results": [
      {
        "status": "failed",
        "outcome_description": "JWT assertion failed in targeted auth test.",
        "reasoning": "Login response omitted token field required by contract.",
        "command": "pytest tests/auth/test_login.py::test_jwt -q",
        "evidence": "FAILED tests/auth/test_login.py::test_jwt - AssertionError: token field missing"
      }
    ],
    "critical_evidence": {
      "satisfied_checklist_ids": [],
      "passed_test_commands": []
    },
    "emergent_ambiguities": []
  },
  "review": {
    "ratings": {
      "spec_completeness": 3,
      "code_quality": 3,
      "tests_completeness": 2,
      "docs_completeness": 3,
      "metadata_usage": 4
    },
    "verdict": "deferred",
    "findings": [
      {
        "id": "finding-auth-01",
        "type": "bug",
        "spec_ref": {
          "type": "api",
          "id": "api-auth-login",
          "line_range": "L12-L15",
          "commit_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        },
        "description": "Login response omits token field required by contract.",
        "severity": "major",
        "remediation_task": {
          "task_id": "fix-auth-token-response",
          "summary": "Return JWT token in login response body.",
          "checklist_ids": ["CHK_AUTH_01"],
          "files_to_touch": ["src/auth/routes.py"]
        },
        "metadata": {
          "source": "execution_results",
          "impact": "blocks authentication acceptance criteria"
        }
      }
    ],
    "next_actions": "Implement remediation task and rerun targeted auth tests."
  },
  "generation_quality": {
    "preflight_passed": true,
    "evidence_records": [],
    "unresolved_inputs": [],
    "assumptions": [],
    "placeholder_scan": {
      "has_placeholders": false,
      "tokens_found": []
    },
    "self_check_results": []
  },
  "canonical_refs_used": [
    {
      "id": "cn:core:unit:ms",
      "kind": "unit"
    }
  ],
  "canonical_proposals": [],
  "canonical_conflicts": []
}
```

## Hardening Protocol
- fail-closed preflight: verify required fields, allowed enums, referenced IDs, and command/tool existence before emitting JSON.
- No-Invention Rules: do not invent IDs, enums, commands, files, metrics, stages, or canonical mappings that are not grounded in provided inputs.
- Completeness Closure: run a final closure pass to confirm required sections, trace/canonical closure, and seed coverage are complete.
- blocker report: if required inputs are missing, conflicting, or ambiguous after clarification, stop and return a blocker report instead of speculative output.

## Canonical Registry (Required Input)

Before generating output, you MUST load and search `canon/manifest.json` for existing canonical entries. Use this registry to:
1. Bind `*_ref` fields to existing canonical IDs (`cn:<namespace>:<kind>:<slug>`)
2. Resolve aliases via `canon/aliases.json`
3. Propose new entries in `canonical_proposals` when no match exists
4. Flag conflicts in `canonical_conflicts` when ambiguous matches are found
## Canonical Binding Rules
1. `canonical_refs_used` is REQUIRED and must list every canonical ID referenced by any `*_ref` field in this artifact.
2. `canonical_proposals` is REQUIRED (may be empty `[]`). Populate it for any new term, metric, entity, role, etc. that does not exist in the registry.
3. `canonical_conflicts` is REQUIRED (may be empty `[]`). Populate it when a field value matches multiple canonical entries or contradicts an existing definition.
4. `generation_quality` is REQUIRED. Set `preflight_passed: true` only after confirming all canonical bindings are resolved.
5. For each `*_ref` field in the schema: if the semantic content exists, the ref MUST be populated. This is not optional.
