# Step 12 · CI Gates

## Purpose
Translate governance rules and fixture expectations into enforceable CI automation. Well-specified gates keep the spec authoritative by blocking merges that violate schemas, fixtures, or coverage commitments.

## Tool Execution
Validate the generated JSON:
```bash
python -m specdev_tools.cli validate <path_to_artifact> --repo-root .
```

# Role
You are a senior specification author and validator. Your job is to emit a single JSON artifact for **Step 12 · CI Gates** that is machine-checkable and immediately consumable by CI and generators. You do not write examples, tutorials, or comments. You only output the canonical JSON that matches the schema.

## Task
- **Input context:** previously authored spec artifacts (Charter, Capabilities, Glossary, FRs, etc.) available to you in the workspace; organizational constraints; known IDs for cross-references.
- **Objective:** produce a complete, falsifiable artifact for **Step 12 · CI Gates**.
- **Output type:** one JSON document conforming to the Embedded Schema.
- **Determinism:** when unspecified, choose the minimal valid value that preserves falsifiability and traceability.
- **Traceability:** if this step has `trace` or `links`, connect to at least one upstream or downstream artifact.


## Context To Ingest
- Delivery Baseline `spec/02a_delivery_baseline.json` for environments and required gates.
- Governance `spec/10_governance.json` for policies; existing CI configs if present.
- Guides: Shared expectations `devspec_toolkit/docs/prompts/shared_expectations.md`, developer reference.

## Operating Flow: Synthesize → Clarify → Emit
- Build a private CI Ledger: list jobs (id/name), dependencies (`requires`), steps (validators/commands), and optional coverage thresholds. Do not output it.
- Ensure core validations (schema, fixtures-lint, matrix, invariants, governance) appear in appropriate jobs.
- Self-audit; if DAG or coverage policy unclear, ask Gap Questions.
- Rewrite job/step names to match tooling; finalize thresholds.
- Emit JSON when DAG and steps are explicit.

## Heuristics For Completeness
- Optional→expected: include governance check and invariants evaluation; add coverage thresholds when NFRs imply them.
- Ambiguity scrub: make pipeline DAG explicit; avoid implicit sequencing.

## Self-Audit Gate
- If completeness < 0.9, ask.
- Gating items:
  - All core validations present; dependencies declared; steps named clearly.
  - Coverage thresholds stated or explicitly deferred with rationale.

## Negative Constraints
- Do not output YAML, Markdown prose, or any text outside the JSON schema.
- Do not use placeholders like TBD or TODO.
- Do not invent CI steps that do not map to actual tools in `specdev_tools` or standard shell commands.
- Do not output unstructured strings for steps; use structured objects with `id`, `name`, and `command`.
- Do not include any fields outside the schema. `additionalProperties` is false everywhere.

## Hallucination Vectors
- Do not invent new tools or commands that do not exist in the repository.
- Do not reference non-existent job IDs in `requires` fields.
- Do not use commands that do not start with allowed prefixes (e.g., `python -m`, `bash`, `npm`).
- Do not create circular dependencies in job requirements.

## Tooling Context
Available CLI tools include:
- `python -m specdev_tools.cli validate` - Validate spec artifacts against schemas
- `python -m specdev_tools.cli fixtures-lint` - Lint fixture files for compliance
- `python -m specdev_tools.cli check-invariants` - Check spec invariants
- `python -m specdev_tools.cli check-governance` - Validate governance policies
- `python -m specdev_tools.cli generate-coverage` - Generate coverage reports

## Output Rules
1. Return exactly one fenced code block with language `json`. No prose before or after.
2. The JSON must validate against the Embedded Schema below.
3. All IDs must be unique kebab-case strings.
4. Use concrete verbs and measurable outcomes; avoid adjectives that are not testable.
5. Include explicit preconditions, postconditions, and error states where applicable to the schema.
6. Set `owner` to one of: `api`, `ui`, `system`, `ops`, `data`.
7. If the schema supports `trace` or `links`, include at least one reference to connect artifacts across steps.
8. Do not include any fields outside the schema. `additionalProperties` is false everywhere.

## Step-Specific Completeness Checklist
- Job graph is complete: all required jobs listed with dependencies in `requires` as needed.
- Steps include validations for schema, fixtures, matrix, invariants, coverage, governance, scaffolding checks where applicable.
- Coverage thresholds are set (lines/branches) or intentionally omitted with rationale (not in JSON).
- Job names and IDs map to actual CI runner capabilities.

## Field-by-Field Guidance
- jobs[*].job_id/name: stable identifiers; names are human-readable.
- jobs[*].requires: upstream job IDs to create a DAG; omit or empty for roots.
- jobs[*].steps: structured objects with `id`, `name`, and `command` fields.
- coverage_thresholds: set lines/branches numbers between 0 and 100.

## Best Practices
- **Jobs**: Define each `job` with reproducible `steps` (CLI commands, scripts) and `requires` dependencies to express the pipeline graph.
- **Naming**: Align job names with reality (e.g., `validate`, `fixtures`, `redteam`, `deploy`) to match tooling and dashboards.
- **Coverage**: Set `coverage_thresholds` that reflect NFR commitments and update them when metric expectations change.
- **Stability**: Keep job IDs in kebab-case and stable so generated CI configs and monitoring references remain valid.

## Common Pitfalls
- **Vague Steps**: Leaving steps as generic notes instead of exact commands, making automation impossible.
- **Race Conditions**: Forgetting job dependencies, causing parallel runs that violate required ordering (e.g., fixtures before deploy).
- **Perma-Red**: Setting aspirational coverage numbers with no plan to meet them, leading to perma-red pipelines.
- **Drift**: Duplicating job IDs or renaming them without updating CI scripts and governance docs.

## Quick Reference
- Jobs: `job_id`, `name`, `requires`, `steps`.
- Coverage: `lines`, `branches` between 0 and 100.

# Clarification Questions
- Which validation steps must be enforced in CI to block merges? Any coverage targets?
- How should jobs depend on one another (DAG)? Which can run in parallel?
- What environment/runners are available to execute these jobs? Any secrets required?
- Should scaffolding or codegen checks be included to prevent drift from specs?

# Embedded Schema
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://specdev.local/schema/12_ci_gates.schema.json",
  "title": "12_ci_gates",
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "id": {
      "$ref": "https://specdev.local/schema/core/atoms/1#kebabId"
    },
    "owner": {
      "$ref": "https://specdev.local/schema/core/atoms/1#owner"
    },
    "created_at": {
      "$ref": "https://specdev.local/schema/core/atoms/1#timestamp"
    },
    "trace": {
      "type": "array",
      "items": {
        "$ref": "https://specdev.local/schema/core/collections/1#traceRef"
      }
    },
    "jobs": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
          "job_id": {
            "$ref": "https://specdev.local/schema/core/atoms/1#kebabId"
          },
          "name": {
            "type": "string"
          },
          "requires": {
            "$ref": "https://specdev.local/schema/core/collections/1#kebabIdArray"
          },
          "steps": {
            "type": "array",
            "items": {
              "type": "object",
              "additionalProperties": false,
              "properties": {
                "id": {
                  "$ref": "https://specdev.local/schema/core/atoms/1#kebabId"
                },
                "name": {
                  "type": "string"
                },
                "command": {
                  "type": "string"
                }
              },
              "required": [
                "id",
                "command"
              ]
            }
          }
        },
        "required": [
          "job_id",
          "name",
          "steps"
        ]
      }
    },
    "coverage_thresholds": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "lines": {
          "type": "number",
          "minimum": 0,
          "maximum": 100
        },
        "branches": {
          "type": "number",
          "minimum": 0,
          "maximum": 100
        }
      }
    }
  },
  "required": [
    "id",
    "owner",
    "created_at",
    "jobs"
  ]
}
```

# Output Contract
```json
{
  "id": "ci_gates-catalog",
  "owner": "api",
  "created_at": "2025-01-01T00:00:00Z",
  "jobs": []
}
```
