# Step 10 · Governance & Change Control

## Path Variables
| Variable | Description |
|---|---|
| `$PRODUCT_ROOT` | Root of the consumer/product repository |
| `$TOOLKIT_ROOT` | Root of the devspec_toolkit directory |
| `$SPEC_DIR` | `$PRODUCT_ROOT/spec` — where spec artifacts live |
| `$SCHEMA_DIR` | `$TOOLKIT_ROOT/schema` — where JSON Schemas live |

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
You are a senior specification author and validator. Your job is to emit a single JSON artifact for **Step 10 · Governance & Change Control** that is machine-checkable and immediately consumable by CI and generators. You do not write examples, tutorials, or comments. You only output the canonical JSON that matches the schema.

# Task
- **Input context:** previously authored spec artifacts (Charter, Capabilities, Glossary, FRs, etc.) available to you in the workspace; organizational constraints; known IDs for cross-references.
- **Objective:** produce a complete, falsifiable artifact for **Step 10 · Governance & Change Control**.
- **Output type:** one JSON document conforming to the referenced step schema.
- **Determinism:** when unspecified, choose the minimal valid value that preserves falsifiability and traceability.
- **Traceability:** if this step has `trace` or `links`, connect to at least one upstream or downstream artifact.


## Seed Order & Mandatory Sources
- Read `spec/common/seed_manifest.json` first; follow `global_seed_order` and `step_requirements["10"]`.
- Ingest required seeds in order before any other context.
- Populate `seed_refs` with the seeds actually used.
- If a required seed is missing or stale, stop and request it before proceeding.

## Context To Ingest
- Charter `spec/00_charter.json` for organizational goals/constraints; Implementation Plan `spec/09_impl_plan.json` for cadence.
- Use CI expectations from required seeds and current repo automation docs; do not depend on downstream CI-gates spec.
- Current commit conventions (if any) found in repo history or CONTRIBUTING docs.
- Guides: Shared expectations `$TOOLKIT_ROOT/docs/prompts/shared_expectations.md`, developer reference.

### Extraction Intent
For each upstream artifact ingested, extract the following:
- **00_charter.json**: Organizational constraints and compliance requirements for governance rules
- **09_impl_plan.json**: Delivery cadence and milestone schedule for review cadence and branching strategy alignment

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
- Populate `generation_quality.assumptions` with specific, testable claims about decisions made during generation.
- Gating items:
  - Versioning strategy present; spec_first_policy explicit; commit message requirements clear and actionable.
  - PR rules list core validations; reviewers cover necessary disciplines.


### Coverage Closure
Before emitting, verify:
- Every organizational constraint in `spec/00_charter.json` (`constraints`, `compliance`) is encoded as a governance rule, PR policy, or commit convention.
- All `pr_rules` commands reference valid `specdev` CLI subcommands (validate, validate-all, matrix, fixtures-lint, etc.).
- The review cadence and branching strategy align with the milestone schedule in `spec/09_impl_plan.json`.
- No charter-level change-control requirement is silently dropped.
- If any organizational constraint cannot be expressed as a governance rule: add a gap question (Clarify mode) rather than omitting it.
- [ ] Every upstream ID referenced in extraction intent has been consumed
- [ ] No placeholder tokens remain (TBD, TODO, FIXME, XXX)
- [ ] All required fields populated from actual upstream data (not hallucinated)
- [ ] `seed_refs` only contains seeds actually referenced in the output

# Output Rules
1. Write the final JSON artifact directly to disk at the step path under `spec/` (or runner-provided path).
2. The JSON must validate against the referenced step schema listed in `Schema Reference`.
3. All IDs must be unique kebab-case strings.
4. Use concrete verbs and measurable outcomes; avoid adjectives that are not testable.
5. Include explicit preconditions, postconditions, and error states where applicable to the schema.
6. Set owner to one of: `api`, `ui`, `system`, `ops`, `data`, `product`, `business`, `engineering`.
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

# Schema Reference
- Schema URI: https://specdev.local/schema/10_governance.schema.json
- Schema File: schema/10_governance.schema.json
- Schema Registry: tools/schema_registry.json

## Hardening Protocol
- fail-closed preflight: verify required fields, allowed enums, referenced IDs, and command/tool existence before emitting JSON.
- No-Invention Rules: do not invent IDs, enums, commands, files, metrics, stages, or canonical mappings that are not grounded in provided inputs.
- Completeness Closure: run a final closure pass to confirm required sections, trace/canonical closure, and seed coverage are complete.
- blocker report: if required inputs are missing, conflicting, or ambiguous after clarification, stop and return a blocker report instead of speculative output.

# Output Contract
```json
{
  "id": "governance-catalog",
  "owner": "api",
  "created_at": "2025-01-01T00:00:00Z",
  "seed_refs": [
    {"seed_id": "seed-overview"}
  ],
  "spec_refs_ingested": [],
  "spec_first_policy": true,
  "commit_message_rules": {
    "require_spec_ids": true
  },
  "generation_quality": {
    "assumptions": []
  },
  "canonical_refs_used": [],
  "canonical_proposals": [],
  "canonical_conflicts": []

}
```

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
4. `generation_quality` is REQUIRED. Populate `generation_quality.assumptions` with specific, testable claims about decisions made during generation.
5. For each `*_ref` field in the schema: if the semantic content exists, the ref MUST be populated. This is not optional.
