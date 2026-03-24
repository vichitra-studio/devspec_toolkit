# Step 10 · Governance & Change Control

Run `specdev prompt-context 10` to see downstream consumers.

## Schema Authority

The schema at `schema/10_governance.schema.json` is the authoritative source for all
field definitions, types, required vs optional markers, enum values, patterns, and minItems rules.
MUST read the schema before generating output. Do NOT guess field names, types, or valid values —
all structural constraints are defined in the schema. Do NOT output fields not defined in the schema.

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
Failures here MUST block the merge.

# Role
You are a senior specification author and validator. Your job is to emit a single JSON artifact for **Step 10 · Governance & Change Control** that is machine-checkable and immediately consumable by CI and generators. You do not write examples, tutorials, or comments. You only output the canonical JSON that matches the schema.

# Task
- **Input context:** previously authored spec artifacts (Charter, Capabilities, Glossary, FRs, etc.) available to you in the workspace; organizational constraints; known IDs for cross-references.
- **Objective:** produce a complete, falsifiable artifact for **Step 10 · Governance & Change Control**.
- **Output type:** one JSON document conforming to the referenced step schema.
- **Determinism:** when unspecified, choose the minimal valid value that preserves falsifiability and traceability.
- **Traceability:** if this step has `trace` or `links`, connect to at least one upstream or downstream artifact.

### Extraction Intent
For each upstream artifact ingested, extract the following:
- **00_charter.json**: Organizational constraints, compliance requirements, and change-control mandates that must be encoded as enforceable governance rules and PR policies
- **01_capabilities.json**: Capability IDs and ownership assignments to determine which disciplines require reviewer representation and which spec ID prefixes appear in commit patterns
- **02_system_sketch.json**: Component boundaries and ownership domains to map reviewer coverage across system areas and ensure governance rules span all architectural layers
- **02a_delivery_baseline.json**: Deployment environments, release cadence expectations, and infrastructure constraints that inform the versioning strategy and branching model
- **03_glossary.json**: Canonical domain terms and naming conventions to ensure governance policy language, commit message patterns, and PR rule descriptions use consistent vocabulary
- **04_fr_list.json**: Functional requirement IDs and their format patterns to configure commit message regex patterns that enforce FR traceability in code changes
- **05_interface_contracts.json**: API IDs and contract versioning to define PR validation scope and ensure API-touching changes trigger schema validation gates
- **06_invariants.json**: Invariant IDs and enforcement rules to mandate invariants-check as a required PR rule and ensure governance covers invariant compliance
- **07_nfrs.json**: NFR coverage metrics and quality thresholds that define minimum CI validation requirements and coverage expectations enforced through PR rules
- **08_fixtures.json**: Fixture target definitions and coverage expectations that mandate fixtures-lint as a required PR rule for spec-first enforcement
- **09_impl_plan.json**: Milestone schedule, delivery cadence, and team dependencies to align review cadence, branching strategy, and release governance with the delivery timeline

## Operating Flow: Synthesize → Clarify → Emit
- Build a private Governance Ledger: versioning strategy, PR rules (required validations), spec_first_policy, commit message pattern, reviewers/roles. Do not output it.
- Validate PR rules cover core spec validations; ensure commit pattern supports traceability.
- Self-audit; if policies are ambiguous or unenforceable, ask Gap Questions.
- Rewrite into concise, enforceable statements and patterns; finalize reviewers.
- Emit JSON when enforceable.

## Heuristics For Completeness
- MUST populate `commit_message_rules.pattern` with a valid regex when `require_spec_ids=true`. SHOULD populate `pr_rules` with at least `validate-all`, `fixtures-lint`, `matrix`, `invariants-check`, `governance-check` when `spec_first_policy=true`.
- Ambiguity scrub: make each rule testable (yes/no), not advisory.

## Self-Audit Gate
- Gating items:
  - Versioning strategy present; spec_first_policy explicit; commit message requirements clear and actionable.
  - PR rules list core validations; reviewers cover necessary disciplines.
  - If versioning strategy, review process, or release cadence are not derivable from upstream specs, ask Gap Questions for organizational preferences.
- If score < 0.9, output clarifying questions only — do not emit JSON.

### Coverage Closure
Before emitting, verify:
- Every organizational constraint in `spec/00_charter.json` (`constraints`, `compliance`) is encoded as a governance rule, PR policy, or commit convention.
- All `pr_rules` commands reference valid `specdev` CLI subcommands (validate, validate-all, matrix, fixtures-lint, etc.).
- The review cadence and branching strategy align with the milestone schedule in `spec/09_impl_plan.json`.
- No charter-level change-control requirement is silently dropped.
- If any organizational constraint cannot be expressed as a governance rule: add a gap question (Clarify mode) rather than omitting it.
- [ ] Every upstream ID from ingested context has been consumed
- [ ] No placeholder tokens remain (TBD, TODO, FIXME, XXX)
- [ ] All required fields populated from actual upstream data (not hallucinated)

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
- Do not set `spec_first_policy: false` unless `spec/00_charter.json` explicitly states a non-spec-first workflow; if set to `false`, MUST include a rationale.
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
- **Spec-First**: MUST set `spec_first_policy` to `true` when `spec/00_charter.json` defines spec-driven workflow constraints; document exceptions in `pr_rules` if any are granted.
- **Traceability**: Configure `commit_message_rules` with regex patterns and spec ID requirements to maintain traceability.
- **Reviewers**: List accountable `reviewers` with rotation notes or escalation paths to avoid approval bottlenecks.

## Common Pitfalls
- **Implicit Rules**: Leaving governance implied, leading teams to bypass spec updates during urgent fixes.
- **Friction**: Setting commit patterns that conflict with CI verification, causing constant false negatives.
- **Silos**: Forgetting to identify reviewers across disciplines, resulting in siloed approvals.
- **Breaking Automation**: Treating versioning as incidental, which breaks automation in CI and drift audits.

# Clarification Questions
- What versioning scheme should we follow for specs and APIs? Who owns version bumps?
- Which CI validations must be mandatory before merge? Any coverage thresholds?
- Must commit messages include spec IDs? Provide the exact regex/pattern to enforce.
- Who are the required reviewers by change type (spec vs code)? Any escalation paths?

# Schema Reference
- Schema URI: vc:10-governance
- Schema File: schema/10_governance.schema.json
- Schema Registry: tools/schema_registry.json

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
2. `canonical_proposals` is OPTIONAL. Populate it for any new term, metric, entity, role, etc. that does not exist in the registry.
3. `canonical_conflicts` is OPTIONAL. Populate it when a field value matches multiple canonical entries or contradicts an existing definition.
4. For each `*_ref` field in the schema: if the semantic content exists, the ref MUST be populated. This is not optional.

## Metadata Contract

This step's output artifact MUST include every field listed in the schema's `required[]` array (see Schema Authority). Do NOT add fields not defined in the schema. Refer to the schema for the complete list of required fields, types, and structural constraints — do NOT restate them here.

# Output Contract
```json
{
  "id": "governance-catalog",
  "owner": "api",
  "created_at": "2025-01-01T00:00:00Z",
  "spec_first_policy": true,
  "commit_message_rules": {
    "require_spec_ids": true
  },
  "canonical_refs_used": []
}
```

