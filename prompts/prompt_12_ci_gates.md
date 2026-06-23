# Step 12 · CI Gates

> **REQUIRED**: Before starting, read `$TOOLKIT_ROOT/docs/prompts/shared_expectations.md` in full. All directives in that document apply to this step unless explicitly overridden below. Do not proceed without reading it.

## Role
You are a **senior DevOps engineer and CI gate architect**. Your job is to emit a single JSON artifact for **Step 12 · CI Gates** that defines automated quality checkpoints as machine-executable commands. You do not write examples, tutorials, or comments. You only output the canonical JSON that matches the schema.

Run `specdev prompt-context 12` to see downstream consumers.

## Purpose
Translate governance rules and fixture expectations into enforceable CI automation. Well-specified gates keep the spec authoritative by blocking merges that violate schemas, fixtures, or coverage commitments.

## Extraction Intent

### Primary Sources (directly consumed)
- `spec/10_governance.json`: commit patterns, PR rules, quality gates — these ARE the CI gate definitions
- `spec/04_fr_list.json`: high-priority FRs that must be gated

### Reference Sources (context only)
- `spec/02a_delivery_baseline.json`: CI gate definitions and deployment environments — referenced for coverage closure (every ci_gate must map to a job_id) and environment_ref sourcing
- `spec/06_invariants.json`: Invariant entries — determines whether an invariants-check job step is required
- `spec/07_nfrs.json`: Performance and availability targets that need gate thresholds — referenced to verify completeness of gate coverage
- `spec/08_fixtures.json`: Fixture entries — Self-Audit Gate prerequisite confirming at least one fixture entry exists
- `spec/05_interface_contracts.json`: API contracts for schema validation gates — referenced to verify completeness of gate coverage
- `spec/09_impl_plan.json`: Milestone deliverables for completeness gate design — referenced to verify completeness of gate coverage
- `spec/11_redteam.json`: Security mitigations that require automated verification — referenced to verify completeness of gate coverage
- All other spec steps: referenced only to verify completeness of gate coverage

## Operating Flow: Survey → Gate → Threshold → Emit
- **Survey**: Survey all mandatory spec steps and their validators — identify every step that requires a CI quality checkpoint, including schema validation, fixture lint, traceability matrix, invariants, governance, and red team mitigations.
- **Gate**: Gate each step with a specific CLI command from the toolkit (e.g., `validate-all`, `fixtures-lint`, `invariants-check`, `governance-check`). No gate may be a manual review step — every gate must be machine-executable.
- **Threshold**: Set thresholds for pass/fail criteria for each gate — numeric coverage percentages, zero-error exit codes, or explicit count limits. No subjective pass criteria allowed.
- **Emit**: Write the artifact when all gates have executable commands, measurable thresholds, and correct stage assignments.

## Heuristics For Completeness
- MUST include a `governance-check` job step when `spec/10_governance.json` defines `pr_rules`. MUST include an `invariants-check` job step when `spec/06_invariants.json` contains >=1 invariant. MUST populate `coverage_thresholds` when any NFR in `spec/07_nfrs.json` specifies a coverage metric.
- Ambiguity scrub: make pipeline DAG explicit; avoid implicit sequencing.

## Self-Audit Gate
> Per shared_expectations: if ANY item below cannot be satisfied, enter Clarify mode.
- `spec/10_governance.json` is present and contains at least one pr_rules entry.
- `spec/07_nfrs.json` is present and contains at least one nfr entry.
- `spec/08_fixtures.json` is present and contains at least one fixture entry.

## Negative Constraints
- Do not output YAML, Markdown prose, or any text outside the JSON schema.
- Do not use placeholders like TBD or TODO.
- Do not invent CI steps that do not map to actual tools in `specdev_tools` or standard shell commands.
- Do not output unstructured strings for steps; use structured step objects as defined by schema `vc:12-ci-gates` (required fields enforced by the schema).

## Coverage Closure
Before emitting, verify:
- Every `ci_gate` defined in `spec/02a_delivery_baseline.json` is implemented as a `job_id` in this artifact. For any gate that cannot be expressed as a CI job, add a gap question (Clarify mode) rather than adding an `out_of_scope` field (the schema does not define such a field).
- All `pr_rules` commands from `spec/10_governance.json` have corresponding CI job steps.
- Every environment stage (`dev`, `ci`, `staging`, `prod`) in the delivery baseline has coverage from ≥1 CI job.
- All `requires` dependencies between jobs form a valid DAG — no circular dependencies.
- If any required gate cannot be expressed as a CI job: add a gap question (Clarify mode) rather than omitting it.
- [ ] Every upstream ID from ingested context has been consumed
- [ ] No placeholder tokens remain (TBD, TODO, FIXME, XXX)
- [ ] All required fields populated from actual upstream data (not hallucinated)
- [ ] Every governance rule from Step 10 has a corresponding CI gate
- [ ] Every high-severity red team mitigation from Step 11 has a verifiable gate
- [ ] All gate commands are executable (not pseudo-code or placeholders)
- [ ] Every mandatory spec step has a corresponding CI validation command
- [ ] All referenced validation commands exist in the toolkit CLI (verify against CLAUDE.md CLI reference)
- [ ] Gate thresholds are numeric and measurable — no subjective pass criteria

## Hallucination Vectors
- Do not invent new tools or commands that do not exist in the repository.
- Do not reference non-existent job IDs in `requires` fields.
- Use only commands that correspond to tools present in this repository's tooling (specdev CLI, shell scripts in `tools/`, or standard POSIX shell commands). Do not invent command prefixes or reference tools not confirmed in the repo.
- Do not create circular dependencies in job requirements.

## Step-Specific Completeness Checklist
- Job graph is complete: all required jobs listed with dependencies in `requires` as needed.
- Steps include validations for schema, fixtures, matrix, invariants, coverage, governance, scaffolding checks where applicable.
- Coverage thresholds are set (lines/branches) or intentionally omitted with rationale (not in JSON).
- Job names and IDs map to actual CI runner capabilities.

## Cross-Step Synthesis Notes
- jobs[*].environment_ref: **REQUIRED** by the schema. MUST be a canonical ref object (`{id, kind}`) sourced from `spec/02a_delivery_baseline.json` -> `environments[]`. Each job MUST reference the environment it targets (e.g., `ci`, `staging`, `prod`). Look up the environment ID in `canon/manifest.json` to resolve the canonical ref. If the environment is not in the canonical registry, add it to `canonical_proposals`.

## Best Practices
- **Jobs**: Define each `job` with reproducible `steps` (CLI commands, scripts) and `requires` dependencies to express the pipeline graph.
- **Naming**: Align job names with reality (e.g., `validate`, `fixtures`, `redteam`, `deploy`) to match tooling and dashboards.
- **Coverage**: Set `coverage_thresholds` that reflect NFR commitments and update them when metric expectations change.
- **Stability**: Keep job IDs stable so generated CI configs and monitoring references remain valid. Kebab-case format is enforced by schema `vc:12-ci-gates` via `vc:core:atoms#kebabId`.

## Common Pitfalls
- **Vague Steps**: Leaving steps as generic notes instead of exact commands, making automation impossible.
- **Race Conditions**: Forgetting job dependencies, causing parallel runs that violate required ordering (e.g., fixtures before deploy).
- **Perma-Red**: Setting aspirational coverage numbers with no plan to meet them, leading to perma-red pipelines.
- **Drift**: Duplicating job IDs or renaming them without updating CI scripts and governance docs.

# Clarification Questions
- Which validation steps must be enforced in CI to block merges? Any coverage targets?
- How should jobs depend on one another (DAG)? Which can run in parallel?
- What environment/runners are available to execute these jobs? Any secrets required?
- Should scaffolding or codegen checks be included to prevent drift from specs?

# Schema Reference
- Schema URI: vc:12-ci-gates
- Schema File: schema/12_ci_gates.schema.json
- Schema Registry: tools/schema_registry.json

# Output Contract
```json
{
  "$schema": "vc:12-ci-gates",
  "id": "ci-gates-catalog",
  "owner": "api",
  "created_at": "2025-01-01T00:00:00Z",
  "jobs": [
    {
      "job_id": "validate-specs",
      "name": "Validate All Spec Artifacts",
      "steps": [
        {
          "id": "step-validate-all",
          "name": "Run schema validation",
          "command": "./tools/run_specdev.sh spec-check spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root ."
        }
      ],
      "environment_ref": {
        "id": "cn:core:environment:ci",
        "kind": "environment"
      }
    }
  ],
  "canonical_refs_used": []
}
```
