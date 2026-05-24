# Step 10 · Governance & Change Control

> **REQUIRED**: Before starting, read `$TOOLKIT_ROOT/docs/prompts/shared_expectations.md` in full. All directives in that document apply to this step unless explicitly overridden below. Do not proceed without reading it.

Run `specdev prompt-context 10` to see downstream consumers.

## Role
You are a **senior engineering manager and governance architect**. Your job is to emit a single JSON artifact for **Step 10 · Governance** that encodes commit conventions, PR rules, and branch policies as machine-enforceable constraints. You do not write examples, tutorials, or comments. You only output the canonical JSON that matches the schema.

## Purpose
Set the policies that keep the spec authoritative by covering change control, versioning, reviewer expectations, and how code changes reference spec artifacts. Strong governance ensures every update flows through spec-first workflows and remains auditable.

## Tool Execution
To enforce the governance policies defined here (specifically commit messages), use:
```bash
./tools/run_specdev.sh governance-check <spec_dir> --message "commit message"
```
Failures here MUST block the merge.

### Extraction Intent
For each upstream artifact ingested, extract the following:
- **00_charter.json**: Organizational constraints, compliance requirements, and change-control mandates that must be encoded as enforceable governance rules and PR policies
- **01_capabilities.json**: Capability IDs and ownership assignments to determine which disciplines require reviewer representation and which spec ID prefixes appear in commit patterns
- **02_system_sketch.json**: Component boundaries, ownership domains, and `tech_stack` technology decisions to map reviewer coverage across system areas, ensure governance rules span all architectural layers, and encode technology-specific change-control policies (e.g., database migration gates, framework upgrade procedures)
- **02a_delivery_baseline.json**: Deployment environments, release cadence expectations, and infrastructure constraints that inform the versioning strategy and branching model
- **03_glossary.json**: Canonical domain terms and naming conventions to ensure governance policy language, commit message patterns, and PR rule descriptions use consistent vocabulary
- **04_fr_list.json**: Functional requirement IDs and their format patterns to configure commit message regex patterns that enforce FR traceability in code changes
- **05_interface_contracts.json**: API IDs and contract versioning to define PR validation scope and ensure API-touching changes trigger schema validation gates
- **06_invariants.json**: Invariant IDs and enforcement rules to mandate invariants-check as a required PR rule and ensure governance covers invariant compliance
- **07_nfrs.json**: NFR coverage metrics and quality thresholds that define minimum CI validation requirements and coverage expectations enforced through PR rules
- **08_fixtures.json**: Fixture target definitions and coverage expectations that mandate fixtures-lint as a required PR rule for spec-first enforcement
- **09_impl_plan.json**: Milestone schedule, delivery cadence, and team dependencies to align review cadence, branching strategy, and release governance with the delivery timeline

## Operating Flow: Audit → Formalize → Validate → Emit
- **Audit**: Examine existing governance practices and stakeholder constraints from the charter; identify all change-control mandates, compliance requirements, and organizational policies that must be encoded.
- **Formalize**: Translate audited constraints into commit message patterns and PR rules; assign each control to the governance schema fields and verify allowed enum values from schema.
- **Validate**: Check that all mandatory spec steps are gated; ensure commit patterns are valid regex; PR rules reference valid roles from the canon; branch rules reference real branch naming patterns.
- **Emit**: Write the artifact only when all rules are machine-checkable.

## Heuristics For Completeness
- MUST populate `commit_message_rules.pattern` with a valid regex when `require_spec_ids=true`. SHOULD populate `pr_rules` with at least `validate-all`, `fixtures-lint`, `matrix`, `invariants-check`, `governance-check` when `spec_first_policy=true`.
- Ambiguity scrub: make each rule testable (yes/no), not advisory.

## Self-Audit Gate
> Per shared_expectations: if ANY item below cannot be satisfied, enter Clarify mode.
- `spec/00_charter.json` is present and contains at least one stakeholders entry.
- `spec/04_fr_list.json` is present and contains at least one functional_requirements entry.
- `spec/09_impl_plan.json` is present and contains at least one milestone entry.

## Negative Constraints
- Do not output text-only logic where regex patterns could be used (e.g., "must include spec IDs" instead of "require spec IDs").
- Do not omit spec IDs in commit message patterns when `require_spec_ids` is true.
- Do not set `spec_first_policy: false` unless `spec/00_charter.json` explicitly states a non-spec-first workflow; if set to `false`, MUST include a rationale.
- Do not create invalid regex patterns in `commit_message_rules.pattern`.
- Do not omit required fields that are present in the schema.

## Coverage Closure
Before emitting, verify:
- Every organizational constraint in `spec/00_charter.json` (`constraints`, `compliance`) is encoded as a governance rule, PR policy, or commit convention.
- All `pr_rules` commands reference valid `specdev` CLI subcommands (validate, validate-all, matrix, fixtures-lint, etc.).
- The review cadence and branching strategy align with the milestone schedule in `spec/09_impl_plan.json`.
- No charter-level change-control requirement is silently dropped.
- If any organizational constraint cannot be expressed as a governance rule: add a gap question (Clarify mode) rather than omitting it.
- [ ] Every upstream ID from ingested context has been consumed
- [ ] No placeholder tokens remain (TBD, TODO, FIXME, XXX)
- [ ] All required fields populated from actual upstream data (not hallucinated)
- [ ] All commit message patterns are valid regex and tested against example commit messages
- [ ] All PR approval roles reference valid owner/role values from the canon registry
- [ ] Every CI gate references a command or check that actually exists in the repo
- [ ] Every commit pattern rule corresponds to a specific artifact type or spec step
- [ ] All PR rules use valid enum values from the schema
- [ ] Quality gates cover all mandatory spec steps (not just a subset)

## Step-Specific Completeness Checklist
- Governance defines a clear versioning strategy for spec and artifacts.
- `pr_rules` encode spec-first expectations and validation commands to run.
- `spec_first_policy` is explicitly true or false; exceptions documented via PR rules if false.
- `commit_message_rules` require spec IDs and provide a regex pattern compatible with CI.
- `reviewers` list includes cross-functional approvers (engineering, QA, security, ops) as needed.
- **Canonical Refs**: `commit_message_rules.id_pattern_ref` SHOULD be populated with a canon entry of kind `id_pattern` when the commit pattern aligns with a canonical ID pattern (e.g., `cn:core:id_pattern:conventional-commit`); the kind is schema-pinned to `id_pattern` — no other kind is accepted, but the field itself is optional. `policy_ref` SHOULD be populated with a canon entry of kind `policy` when a governing policy applies (e.g., `cn:core:policy:spec-first`); the kind is schema-pinned to `policy` — no other kind is accepted, but the field itself is optional. `command_ref` SHOULD be populated with a canon entry of kind `command` (e.g., `cn:core:command:governance-check`) when the rule maps to a CLI command — no other kind is accepted. All referenced IDs must also appear in `canonical_refs_used`, and canonical-integrity (E120) will reject any kind mismatch against the canon registry.

## Cross-Step Synthesis Notes
- pr_rules: Allowed values are enforced by the schema enum in `schema/10_governance.schema.json` (pr_rules items.enum). Consult the schema as the authoritative source rather than any inline list here — the enum is the contract.
- commit_message_rules.error_message: explicitly list the valid `type` enums so users know what to type without reading regex (e.g., "Format: type(scope): msg [id]. Allowed types: feat, fix, chore.")

## Emergent Ambiguities
If any organizational constraint from the upstream specs cannot be mapped to a governance rule, a PR policy, or a commit convention: record a gap question and enter Clarify mode rather than silently dropping the constraint or inventing a rule. Do not proceed to Emit until all clarifications are resolved or explicitly deferred with rationale.

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

# Output Contract
> **Note**: The ID strings for `id_pattern_ref`, `policy_ref`, and `command_ref` shown below (e.g., `cn:core:id_pattern:conventional-commit`) are illustrative examples. Authoritative canonical IDs must be resolved from `canon/manifest.json` — do not copy these IDs verbatim if the registry has changed. Validate with `canonical-integrity` lint after authoring.

```json
{
  "$schema": "vc:10-governance",
  "id": "governance-catalog",
  "owner": "api",
  "created_at": "2025-01-01T00:00:00Z",
  "spec_first_policy": true,
  "commit_message_rules": {
    "require_spec_ids": true,
    "pattern": "^(feat|fix|chore|docs|refactor|test)\\(spec\\): .+ \\[[a-z]+-[a-z0-9-]+\\]$",
    "id_pattern_ref": {
      "id": "cn:core:id_pattern:conventional-commit",
      "kind": "id_pattern",
      "label": "conventional-commit",
      "version": "1.0.0"
    }
  },
  "policy_ref": {
    "id": "cn:core:policy:spec-first",
    "kind": "policy",
    "label": "spec-first",
    "version": "1.0.0"
  },
  "command_ref": {
    "id": "cn:core:command:governance-check",
    "kind": "command",
    "label": "governance-check",
    "version": "1.0.0"
  },
  "canonical_refs_used": [
    {"id": "cn:core:id_pattern:conventional-commit", "kind": "id_pattern", "version": "1.0.0"},
    {"id": "cn:core:policy:spec-first", "kind": "policy", "version": "1.0.0"},
    {"id": "cn:core:command:governance-check", "kind": "command", "version": "1.0.0"}
  ]
}
```
