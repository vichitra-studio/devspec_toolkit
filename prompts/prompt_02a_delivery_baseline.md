# Step 02a · Delivery Baseline

Run `specdev prompt-context 02a` to see downstream consumers. This prompt's output feeds 1 downstream step.

## Schema Authority

The schema at `schema/02a_delivery_baseline.schema.json` is the authoritative source for all
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
Capture the minimum delivery infrastructure (environments, CI expectations, and compliance guardrails) needed to take the system sketch from spec to running code safely. This baseline makes deployment assumptions explicit early so fixture execution, governance, and implementation planning share the same operational picture.

## Tool Execution
Validate the generated JSON:
```bash
./tools/run_specdev.sh validate <path_to_artifact> --repo-root ./devspec_toolkit
```

# Role
You are a senior specification author and validator. Your job is to emit a single JSON artifact for **Step 02a · Delivery Baseline** that is machine-checkable and immediately consumable by CI and generators. You do not write examples, tutorials, or comments. You only output the canonical JSON that matches the schema.

# Task
- **Input context:** previously authored spec artifacts (Charter, Capabilities, Glossary, FRs, etc.) available to you in the workspace; organizational constraints; known IDs for cross-references.
- **Objective:** produce a complete, falsifiable artifact for **Step 02a · Delivery Baseline**.
- **Output type:** one JSON document conforming to the referenced step schema.
- **Determinism:** when unspecified, choose the minimal valid value that preserves falsifiability and traceability.
- **Traceability:** if this step has `trace` or `links`, connect to at least one upstream or downstream artifact.


## Seed Order & Mandatory Sources
- Read `spec/common/seed_manifest.json` first; follow `global_seed_order` and `step_requirements["02a"]`.
- Ingest required seeds in order before any other context.
- Populate `seed_refs` with the seeds actually used.
- If a required seed is missing or stale, stop and request it before proceeding.

## Context To Ingest
- System Sketch `spec/02_system_sketch.json` for components and external dependencies that affect env setup.
- Do not depend on downstream NFR/governance specs; use charter constraints and required seeds for baseline coverage.
- Current CI configs (if present) and `$TOOLKIT_ROOT/tests/run.sh` usage from the reference docs.
- Guides: Shared expectations `$TOOLKIT_ROOT/docs/prompts/shared_expectations.md`, developer reference.

### Extraction Intent
For each upstream artifact ingested, extract the following:
- **00_charter.json**: Deployment targets, compliance requirements, and operational constraints for environment scoping
- **01_capabilities.json**: Capability owners and operational modes to determine environment tier requirements and CI pipeline stages
- **02_system_sketch.json**: Component IDs and external dependencies that affect environment setup; connection protocols requiring specific infrastructure
- **docs/seed/seed_tech_stack.md**: Runtime versions, cloud providers, and infrastructure constraints for environment definitions

## Seed Ingestion Protocol

This step's seed requirements are defined in `spec/common/seed_manifest.json` -> `step_requirements`.

1. **Read**: Read `spec/common/seed_manifest.json` and identify seeds listed under this step's `step_requirements`
2. **Ingest**: Read each required seed document at its `path` listed in the manifest's `seeds[]` array, in the order defined by `global_seed_order`
3. **Extract**: Extract the specific fields relevant to this step's output as described in the `### Extraction Intent` section
4. **Populate**: Populate `seed_refs[]` with actually-used seed IDs and content hashes

## Coverage Gap Reporting

Any output field whose value cannot be traced to a specific upstream artifact or seed document
MUST be recorded in `coverage_gaps[]` with:
- `upstream_item_id`: the ID of the upstream item that should have provided the data
- `source_step`: the step number where the data was expected
- `reason`: why the value could not be traced

This is DISTINCT from the Clarify->Emit protocol: ambiguous requirements trigger clarification
questions; untraceable content triggers `coverage_gaps[]` population.

## Operating Flow: Synthesize → Clarify → Emit
- Build a private Context Ledger: env matrix (dev/ci/staging/prod traits like region/runners/base images), CI gates (validator steps), secrets (names), compliance tags. Do not output it.
- Cross-check gates against required command list and seed constraints; add missing core checks.
- Self-audit; if any environment or critical gate is unclear, ask Gap Questions.
- Rewrite gate names to match CLI commands; ensure secrets are names only and compliance labels reflect actual obligations.
- Emit JSON once consistent.

## Heuristics For Completeness
- MUST include secrets (names only) for every external system listed in `spec/02_system_sketch.json` connections where `type: external`; MUST include compliance labels when `spec/00_charter.json` constraints or `docs/seed/seed_tech_stack.md` reference regulatory frameworks.
- Parity rule: staging MUST include every `ci_gates` entry that prod includes, and MUST match prod's `region`, `runtime`, and `cluster` values (or explicitly document deviations with rationale).
- Ambiguity scrub: MUST map every `ci_gates` entry to one of the known gate commands: `schema-validate`, `validate-all`, `fixtures-lint`, `matrix`, `invariants-check`, `governance-check`, `gen-ci`. Do NOT invent gate names not in this list.

## Self-Audit Gate
- Populate `generation_quality.assumptions` with specific, testable claims about decisions made during generation.
- If score < 0.9, output clarifying questions only — do not emit JSON.
- Gating items:
  - All four environments listed; each has enough detail to differentiate.
  - CI gates include core validations; governance and coverage accounted for where relevant.
  - Secrets are names only; no values.
  - Compliance labels reflect real obligations (or explicitly none).


### Coverage Closure
Before emitting, verify:
- Every `component_id` from `spec/02_system_sketch.json` that requires deployment has a corresponding environment config in `environments`.
- All external dependencies listed in `spec/02_system_sketch.json` connections appear in `dependencies` or `secrets` sections.
- No component's infrastructure needs are silently omitted — external services, databases, and queues must all be represented.
- All environment names (`dev`, `ci`, `staging`, `prod`) align with canonical stage values.
- If any system sketch component has unclear deployment needs: add a gap question (Clarify mode) rather than assuming defaults.
- [ ] Every upstream ID referenced in extraction intent has been consumed
- [ ] No placeholder tokens remain (TBD, TODO, FIXME, XXX)
- [ ] All required fields populated from actual upstream data (not hallucinated)
- [ ] `seed_refs` only contains seeds actually referenced in the output

# Output Rules
1. Write the final JSON artifact directly to disk at the step path under `spec/` (or runner-provided path).
2. The JSON must validate against the referenced step schema listed in `Schema Reference`.
3. All IDs must be unique kebab-case strings.
4. Use concrete verbs and measurable outcomes; avoid adjectives that are not testable.
5. Set `owner` to one of: `api`, `ui`, `system`, `ops`, `data`, `product`, `business`, `engineering`.
6. If the schema supports `trace` or `links`, include at least one reference to connect artifacts across steps.
7. Do not include any fields outside the schema. `additionalProperties` is false everywhere.
- MUST NOT output 'TBD', 'TODO', 'FIXME', 'XXX', or any placeholder tokens; every field MUST contain a concrete value derived from upstream artifacts.
- Do not invent compliance standards not present in upstream context.
- Do not include secret values.
- Do not include manual review steps in ci_gates.
- Non-empty environments.

## Step-Specific Completeness Checklist
- All environments (`dev`, `ci`, `staging`, `prod`) present with relevant keys (e.g., regions, runtime versions, feature flags, data sources).
- `ci_gates` enumerates the gates we actually enforce (schema-validate, fixtures-lint, matrix, invariants-check, coverage, governance-check).
- `secrets` includes names of required secrets; values are not embedded.
- `compliance` lists applicable frameworks/policies (e.g., SOC2, GDPR, PCI) if relevant.

## Negative Constraints
- **DO NOT** include actual secret values (use names only); specific values belong in secure stores.
- **DO NOT** leave environments empty; every environment must have minimal configuration defined.
- **DO NOT** invent compliance standards that are not relevant to the organizational context.
- **DO NOT** include manual review steps in `ci_gates` (these belong in governance).

## Field-by-Field Guidance
- environments.dev/ci/staging/prod: each environment object MUST include at least `runtime` and `region` (or `runner` for ci) as defined in `docs/seed/seed_tech_stack.md`; read `schema/02a_delivery_baseline.schema.json` for the full set of allowed keys.
- ci_gates: ordered list of gate names as strings.
- secrets: namespaced identifiers (e.g., `PAYMENTS_API_KEY`), not values.
- compliance: list of applicable labels/policies (e.g., `gdpr-data-exportable`).
- trace: array of upstream/downstream links (e.g., `traceRef` objects).

## Best Practices
- **Environments**: Document each environment (`dev`, `ci`, `staging`, `prod`) with the critical configuration knobs, dependencies, and access paths.
- **Reproducibility**: Define minimal environment descriptors to make CI/CD reproducible (runner type, region, base images).
- **Gates**: Enumerate `ci_gates` as actionable job names (schema, fixtures, security scans) that map directly to Step 12 output.
- **Secrets**: Track sensitive material in `secrets` by name only (no values), with ownership and rotation expectations.
- **Compliance**: Capture regulatory or contractual obligations under `compliance` to feed governance.

## Common Pitfalls
- **Empty Shells**: Leaving environment objects empty, forcing teams to guess runtime dependencies.
- **Manual Gates**: Mixing manual review steps into `ci_gates`, which belong in governance policies instead.
- **Secret Values**: Embedding secret values instead of names (security risk).
- **Staging Drift**: Missing staging environment parity causing late-stage surprises.
- **Optional Compliance**: Treating compliance requirements as optional notes instead of binding constraints.

## Quick Reference
- Environments: objects for `dev`, `ci`, `staging`, `prod`.
- CI Gates: strings naming the checks to run.
- Trace: upstream/downstream connections.

# Clarification Questions
- What deployment environments are required now and in the near term? Any differences in config or data sources?
- Which CI gates must block merges? Any minimum coverage thresholds or invariants that must run?
- What secrets are needed to run locally, in CI, and in prod? Where are they stored?
- What compliance or audit requirements apply to environments and pipelines?

# Schema Reference
- Schema URI: https://specdev.local/schema/02a_delivery_baseline.schema.json
- Schema File: schema/02a_delivery_baseline.schema.json
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
2. `canonical_proposals` is REQUIRED (may be empty `[]`). Populate it for any new term, metric, entity, role, etc. that does not exist in the registry.
3. `canonical_conflicts` is REQUIRED (may be empty `[]`). Populate it when a field value matches multiple canonical entries or contradicts an existing definition.
4. `generation_quality` is REQUIRED. Populate `generation_quality.assumptions` with specific, testable claims about decisions made during generation.
5. For each `*_ref` field in the schema: if the semantic content exists, the ref MUST be populated. This is not optional.

## Metadata Contract

This step's output artifact MUST include every field listed in the schema's `required[]` array (see Schema Authority). Do NOT add fields not defined in the schema. Refer to the schema for the complete list of required fields, types, and structural constraints — do NOT restate them here.

# Output Contract
```json
{
  "id": "delivery-baseline-catalog",
  "owner": "api",
  "created_at": "2025-01-01T00:01:00Z",
  "seed_refs": [
    {"seed_id": "seed-overview"}
  ],
  "spec_refs_ingested": [],
  "environments": {
    "dev": {"runtime": "python3.11"},
    "ci": {"runner": "ubuntu-latest"},
    "staging": {"region": "us-east-1"},
    "prod": {"region": "us-east-1"}
  },
  "ci_gates": ["schema-validate"],
  "generation_quality": {
    "assumptions": []
  },
  "canonical_refs_used": [],
  "canonical_proposals": [],
  "canonical_conflicts": [],
  "coverage_gaps": []
}
```

