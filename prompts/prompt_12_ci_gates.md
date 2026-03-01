# Step 12 · CI Gates

Run `specdev prompt-context 12` to see downstream consumers.

## Path Variables
| Variable | Description |
|---|---|
| `$PRODUCT_ROOT` | Root of the consumer/product repository |
| `$TOOLKIT_ROOT` | Root of the devspec_toolkit directory |
| `$SPEC_DIR` | `$PRODUCT_ROOT/spec` — where spec artifacts live |
| `$SCHEMA_DIR` | `$TOOLKIT_ROOT/schema` — where JSON Schemas live |

## Purpose
Translate governance rules and fixture expectations into enforceable CI automation. Well-specified gates keep the spec authoritative by blocking merges that violate schemas, fixtures, or coverage commitments.

## Tool Execution
Validate the generated JSON:
```bash
./tools/run_specdev.sh validate <path_to_artifact> --repo-root ./devspec_toolkit
```

# Role
You are a senior specification author and validator. Your job is to emit a single JSON artifact for **Step 12 · CI Gates** that is machine-checkable and immediately consumable by CI and generators. You do not write examples, tutorials, or comments. You only output the canonical JSON that matches the schema.

## Task
- **Input context:** previously authored spec artifacts (Charter, Capabilities, Glossary, FRs, etc.) available to you in the workspace; organizational constraints; known IDs for cross-references.
- **Objective:** produce a complete, falsifiable artifact for **Step 12 · CI Gates**.
- **Output type:** one JSON document conforming to the referenced step schema.
- **Determinism:** when unspecified, choose the minimal valid value that preserves falsifiability and traceability.
- **Traceability:** if this step has `trace` or `links`, connect to at least one upstream or downstream artifact.


## Context To Ingest
- Delivery Baseline `spec/02a_delivery_baseline.json` for environments and required gates.
- Governance `spec/10_governance.json` for policies; existing CI configs if present.
- Guides: Shared expectations `$TOOLKIT_ROOT/docs/prompts/shared_expectations.md`, developer reference.

### Extraction Intent
For each upstream artifact ingested, extract the following:
- **02a_delivery_baseline.json**: Environment definitions and required CI gate names for job creation
- **10_governance.json**: PR rules and validation commands that must be implemented as CI job steps

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
- Populate `generation_quality.assumptions` with specific, testable claims about decisions made during generation.
- Gating items:
  - All core validations present; dependencies declared; steps named clearly.
  - Coverage thresholds stated or explicitly deferred with rationale.
- If coverage thresholds or CI runner infrastructure preferences are not derivable from upstream specs, ask Gap Questions — do not assume default thresholds.
- If score < 0.9, output clarifying questions only — do not emit JSON.


### Coverage Closure
Before emitting, verify:
- Every `ci_gate` defined in `spec/02a_delivery_baseline.json` is implemented as a `job_id` in this artifact, OR explicitly listed in `out_of_scope` with rationale.
- All `pr_rules` commands from `spec/10_governance.json` have corresponding CI job steps.
- Every environment stage (`dev`, `ci`, `staging`, `prod`) in the delivery baseline has coverage from ≥1 CI job.
- All `requires` dependencies between jobs form a valid DAG — no circular dependencies.
- If any required gate cannot be expressed as a CI job: add a gap question (Clarify mode) rather than omitting it.
- [ ] Every upstream ID referenced in extraction intent has been consumed
- [ ] No placeholder tokens remain (TBD, TODO, FIXME, XXX)
- [ ] All required fields populated from actual upstream data (not hallucinated)
- [ ] `seed_refs` is `[]` (this step derives from upstream specs, not seeds)

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
- `./tools/run_specdev.sh validate --repo-root ./devspec_toolkit` - Validate spec artifacts against schemas
- `./tools/run_specdev.sh validate-all --repo-root ./devspec_toolkit` - Validate all spec artifacts
- `./tools/run_specdev.sh fixtures-lint --repo-root ./devspec_toolkit` - Lint fixture files for compliance
- `./tools/run_specdev.sh matrix --repo-root ./devspec_toolkit` - Generate traceability matrix
- `./tools/run_specdev.sh invariants-check --repo-root ./devspec_toolkit --sample ./path/to/sample.json` - Check spec invariants
- `./tools/run_specdev.sh governance-check --repo-root ./devspec_toolkit` - Validate governance policies
- `./tools/run_specdev.sh seed-lint --repo-root ./devspec_toolkit` - Validate seed requirements
- `./tools/run_specdev.sh docs-lint --repo-root ./devspec_toolkit` - Enforce docs policy

## Canonical Registry (Required Input)
- Load `canon/manifest.json` — the authoritative registry of all canonical terms.
- Load `canon/aliases.json` — the alias resolution table.
- For every semantic field you populate, search the manifest for a matching entry by `kind` + `preferred_label` or alias.
- If a match exists: populate the corresponding `*_ref` field with `{id, kind}` at minimum.
- If no match exists: add an entry to `canonical_proposals` with `temp_id`, `kind`, `proposed_label`, `definition`, and `source_field`.
- If multiple matches exist or the match is ambiguous: add an entry to `canonical_conflicts`.
- NEVER leave a `*_ref` field empty when a matching canonical entry exists.
- NEVER use a deprecated canonical without checking `replaced_by` first.


## Output Rules
1. Write the final JSON artifact directly to disk at the step path under `spec/` (or runner-provided path).
2. The JSON must validate against the referenced step schema listed in `Schema Reference`.
3. All IDs must be unique kebab-case strings.
4. Use concrete verbs and measurable outcomes; avoid adjectives that are not testable.
5. Include explicit preconditions, postconditions, and error states where applicable to the schema.
6. Set owner to one of: `api`, `ui`, `system`, `ops`, `data`, `product`, `business`, `engineering`.
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

# Schema Reference
- Schema URI: https://specdev.local/schema/12_ci_gates.schema.json
- Schema File: schema/12_ci_gates.schema.json
- Schema Registry: tools/schema_registry.json

## Hardening Protocol
- fail-closed preflight: verify required fields, allowed enums, referenced IDs, and command/tool existence before emitting JSON.
- No-Invention Rules: do not invent IDs, enums, commands, files, metrics, stages, or canonical mappings that are not grounded in provided inputs.
- Completeness Closure: run a final closure pass to confirm required sections, trace/canonical closure, and seed coverage are complete.
- blocker report: if required inputs are missing, conflicting, or ambiguous after clarification, stop and return a blocker report instead of speculative output.

# Output Contract
```json
{
  "id": "ci-gates-catalog",
  "owner": "api",
  "created_at": "2025-01-01T00:00:00Z",
  "seed_refs": [],
  "spec_refs_ingested": [],
  "jobs": [],
  "generation_quality": {
    "assumptions": []
  },
  "canonical_refs_used": [],
  "canonical_proposals": [],
  "canonical_conflicts": []

}
```

## Canonical Binding Rules
1. `canonical_refs_used` is REQUIRED and must list every canonical ID referenced by any `*_ref` field in this artifact.
2. `canonical_proposals` is REQUIRED (may be empty `[]`). Populate it for any new term, metric, entity, role, etc. that does not exist in the registry.
3. `canonical_conflicts` is REQUIRED (may be empty `[]`). Populate it when a field value matches multiple canonical entries or contradicts an existing definition.
4. `generation_quality` is REQUIRED. Populate `generation_quality.assumptions` with specific, testable claims about decisions made during generation.
5. For each `*_ref` field in the schema: if the semantic content exists, the ref MUST be populated. This is not optional.
