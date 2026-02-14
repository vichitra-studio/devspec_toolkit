# Step 10 · Governance & Change Control

## Purpose
Set the policies that keep the spec authoritative by covering change control, versioning, reviewer expectations, and how code changes reference spec artifacts. Strong governance ensures every update flows through spec-first workflows and remains auditable.

## Tool Execution
Validate the generated JSON:
```bash
./tools/run_specdev.sh validate <path_to_artifact> --repo-root ./devspec_toolkit
```

To enforce the governance policies defined here (specifically commit messages), use:
```bash
./tools/run_specdev.sh governance-check <spec_dir> --message "commit message"
```
Failures here should block the merge.

# Role
You are a senior specification author and validator. Your job is to emit a single JSON artifact for **Step 10 · Governance & Change Control** that is machine-checkable and immediately consumable by CI and generators. You do not write examples, tutorials, or comments. You only write the canonical JSON to the file system.

# Task
- **Input context:** previously authored spec artifacts (Charter, Capabilities, Glossary, FRs, etc.) available to you in the workspace; organizational constraints; known IDs for cross-references.
- **Objective:** produce a complete, falsifiable artifact for **Step 10 · Governance & Change Control**.
- **Output type:** one JSON document conforming to the Embedded Schema.
- **Determinism:** when unspecified, choose the minimal valid value that preserves falsifiability and traceability.
- **Traceability:** if this step has `trace` or `links`, connect to at least one upstream or downstream artifact.


## Seed Order & Mandatory Sources
- Read `spec/common/seed_manifest.json` first; follow `global_seed_order` and `step_requirements["10"]`.
- Ingest required seeds in order before any other context.
- Populate `seed_refs` with the seeds actually used.
- If a required seed is missing or stale, stop and request it before proceeding.

## Context To Ingest
- Charter `spec/00_charter.json` for organizational goals/constraints; Implementation Plan `spec/09_impl_plan.json` for cadence.
- CI Gates `spec/12_ci_gates.json` to ensure governance aligns with automation.
- Current commit conventions (if any) found in repo history or CONTRIBUTING docs.
- Guides: Shared expectations `devspec_toolkit/docs/prompts/shared_expectations.md`, developer reference.

## Operating Flow: Synthesize → Clarify → Emit
- Build a private Governance Ledger: versioning strategy, PR rules (required validations), spec_first_policy, commit message pattern, reviewers/roles. Do not output it.
- Validate PR rules cover core spec validations; ensure commit pattern supports traceability.
- Self-audit; if policies are ambiguous or unenforceable, ask Gap Questions.
- Rewrite into concise, enforceable statements and patterns; finalize reviewers.
- Emit JSON when enforceable.

## Heuristics For Completeness
- Optional→expected: include commit pattern if `require_spec_ids=true`; include PR rules invoking `validate-all`, `fixtures-lint`, `matrix`, `invariants-check`, `governance-check`.
- Ambiguity scrub: make each rule testable (yes/no), not advisory.

## Self-Audit Gate
- If completeness < 0.9, ask.
- Gating items:
  - Versioning strategy present; spec_first_policy explicit; commit message requirements clear and actionable.
  - PR rules list core validations; reviewers cover necessary disciplines.

# Output Rules
1. Do not output the JSON in the chat. Write the final JSON artifact to `spec/10_governance.json` using the file creation tool.
2. The JSON must validate against the Embedded Schema below.
3. All IDs must be unique kebab-case strings.
4. Use concrete verbs and measurable outcomes; avoid adjectives that are not testable.
5. Include explicit preconditions, postconditions, and error states where applicable to the schema.
6. Set `owner` to one of: `api`, `ui`, `system`, `ops`, `data`.
7. If the schema supports `trace` or `links`, include at least one reference to connect artifacts across steps.
8. Do not include any fields outside the schema. `additionalProperties` is false everywhere.

## Negative Constraints
- Do not output text-only logic where regex patterns could be used (e.g., "must include spec IDs" instead of "require spec IDs").
- Do not omit spec IDs in commit message patterns when `require_spec_ids` is true.
- Do not use lazy policies (e.g., `spec_first_policy: false` without justification).
- Do not create invalid regex patterns in `commit_message_rules.pattern`.
- Do not omit required fields that are present in the schema.

## Step-Specific Completeness Checklist
- Governance defines a clear versioning strategy for spec and artifacts.
- `pr_rules` encode spec-first expectations and validation commands to run.
- `spec_first_policy` is explicitly true or false; exceptions documented via PR rules if false.
- `commit_message_rules` require spec IDs and provide a regex pattern compatible with CI.
- `reviewers` list includes cross-functional approvers (engineering, QA, security, ops) as needed.

## Field-by-Field Guidance
- versioning: e.g., calendar-based, semver, or spec rev; state how bumps occur.
- pr_rules: list of required checks. Allowed values: `validate`, `validate-all`, `matrix`, `fixtures-lint`, `invariants-check`, `governance-check`, `test`, `build`, `lint`, `format`, `audit`, `security`.
- spec_first_policy: boolean indicating spec-before-impl requirement.
- commit_message_rules.require_spec_ids: true if commits must include spec IDs.
- commit_message_rules.pattern: regex enforcing prefix and ID inclusion.
- commit_message_rules.error_message: helpful text like "Format: type(scope): msg [id]. Allowed types: feat, fix, chore."
- reviewers: stable names/roles accountable for approvals. Use generic roles (e.g., 'API Owner') if specific names are not provided in Context.

## Best Practices
- **Versioning**: Document the `versioning` strategy (calendar, semver, spec revision) so downstream tooling can bump versions consistently.
- **Friendly Errors**: In `error_message`, explicitly list the valid `type` enums (e.g. `feat, fix, chore`) so the user knows what to type without reading regex.
- **Gates**: Encode `pr_rules` that require spec diffs before implementation merges, including checklist items for validation commands.
- **Spec-First**: Flip `spec_first_policy` to true and describe when, if ever, exceptions are granted.
- **Traceability**: Configure `commit_message_rules` with regex patterns and spec ID requirements to maintain traceability.
- **Reviewers**: List accountable `reviewers` with rotation notes or escalation paths to avoid approval bottlenecks.

## Common Pitfalls
- **Implicit Rules**: Leaving governance implied, leading teams to bypass spec updates during urgent fixes.
- **Friction**: Setting commit patterns that conflict with CI verification, causing constant false negatives.
- **Silos**: Forgetting to identify reviewers across disciplines, resulting in siloed approvals.
- **Breaking Automation**: Treating versioning as incidental, which breaks automation in CI and drift audits.

## Quick Reference
- ID Format: `governance-<descriptor>`; owner commonly `ops` or `system`.
- Required Fields: must declare `spec_first_policy`; other sections should be filled for practical governance.
- Commit Rules: `require_spec_ids` should align with ID formats like `fr-*`, `api-*`, `fixture-*`.
- Reviewer List: maintain stable names or roles; update when ownership shifts.

# Clarification Questions
- What versioning scheme should we follow for specs and APIs? Who owns version bumps?
- Which CI validations must be mandatory before merge? Any coverage thresholds?
- Must commit messages include spec IDs? Provide the exact regex/pattern to enforce.
- Who are the required reviewers by change type (spec vs code)? Any escalation paths?

# Embedded Schema
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://specdev.local/schema/10_governance.schema.json",
  "title": "10_governance",
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
    "versioning": {
      "type": "string"
    },
    "pr_rules": {
      "type": "array",
      "items": {
        "type": "string",
        "enum": [
          "validate",
          "validate-all",
          "matrix",
          "fixtures-lint",
          "invariants-check",
          "governance-check",
          "test",
          "build",
          "lint",
          "format",
          "audit",
          "security"
        ]
      },
      "uniqueItems": true
    },
    "spec_first_policy": {
      "type": "boolean"
    },
    "commit_message_rules": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "require_spec_ids": {
          "type": "boolean"
        },
        "pattern": {
          "type": "string"
        },
        "error_message": {
          "type": "string",
          "description": "Human readable guidance. MUST list allowed types/values if a specific set is required."
        }
      },
      "required": [
        "require_spec_ids"
      ]
    },
    "reviewers": {
      "$ref": "https://specdev.local/schema/core/collections/1#stringArray"
    },
    "trace": {
      "type": "array",
      "items": {
        "$ref": "https://specdev.local/schema/core/collections/1#traceRef"
      }
    },
    "links": {
      "type": "array",
      "items": {
        "$ref": "https://specdev.local/schema/core/collections/1#link"
      }
    }
  },
  "required": [
    "id",
    "owner",
    "created_at",
    "spec_first_policy"
  ]
}
```

# Output Contract
```json
{
  "id": "governance-catalog",
  "owner": "api",
  "created_at": "2025-01-01T00:00:00Z",
  "spec_first_policy": true
}
```
