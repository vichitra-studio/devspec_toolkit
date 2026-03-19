# Discovery Workflow (Steps 00–12)

Phase I turns fuzzy product ideas into falsifiable, machine-checkable artifacts.

## Objectives
- Capture scope, users, and measurable success metrics.
- Define system capabilities, contracts, and invariants.
- Establish governance and CI gates that keep the spec authoritative.

## Step Progression
| Step | Goal | Key Outputs |
|------|------|-------------|
| 00 — Charter | Align on problem, scope, stakeholders | `spec/00_charter.json` |
| 01 — Capabilities | Describe system verbs and boundaries | `spec/01_capabilities.json` |
| 02 — System Sketch | Shape components and connections | `spec/02_system_sketch.json` |
| 02a — Delivery Baseline | Nail environments, CI, compliance | `spec/02a_delivery_baseline.json` |
| 03 — Glossary | Eliminate ambiguous terms | `spec/03_glossary.json` |
| 04 — Functional Requirements | Define falsifiable behavior | `spec/04_fr_list.json` |
| 05 — Interface Contracts | Establish API surface | `spec/05_interface_contracts.json` |
| 06 — Invariants | Capture truths that must hold | `spec/06_invariants.json` |
| 07 — NFRs | Set performance/reliability targets | `spec/07_nfrs.json` |
| 08 — Fixtures | Provide traceable test data | `spec/08_fixtures.json` |
| 09 — Implementation Plan | Sequence delivery milestones | `spec/09_impl_plan.json` |
| 10 — Governance | Define change control policies | `spec/10_governance.json` |
| 11 — Red Team | Enumerate threats and mitigations | `spec/11_redteam.json` |
| 12 — CI Gates | Wire automated enforcement | `spec/12_ci_gates.json` |

## Transition: Extensions & Completeness
1.  **Step 13 (Extension Generator)**: Identify if you need specialized extensions (e.g., `ext_01_database.json`) for complex domains found in System Sketch.
2.  **Step 13a (Completeness)**: Run `spec/13a_completeness_assessment.json` to identify unresolved tracing or definitions.
3.  **Step 14 (Roadmap)**: Only once 13/13a are clear, proceed to the Roadmap phase.

Consult the matching `spec/NN_name.guide.md` before running the prompt for each step.

## AI Assist Flow
Prompts are designed for a two‑phase interaction to reduce rework:
- Phase A — Clarify: the assistant ingests the step’s context and asks targeted Gap Questions when the “Self‑Audit Gate” is not satisfied.
- Phase B — Emit: once answers are provided, the assistant writes the artifact JSON directly to disk and validates against the schema.
Clarify responses should be short, bulleted questions grouped by topic (no JSON, no code fences), prioritizing gating items; the assistant stops until answers are provided.

## Validation Cadence
Use the [core validation commands](../reference.md#core-validation-commands) after each artifact update to keep discovery outputs consistent before moving to implementation.

## Step 02 Troubleshooting
- Missing `trace_refs` on components or connections will fail schema validation.
- Components must include 3–6 responsibilities and an owner.
- Multiple components require at least one connection; each connection must include `trust_boundary`.
- `partner`/`public` connections require `auth` and `rate_limit`; `event` protocol requires `reliability`.
- `schema_ref` must use `file://`, `https://`, `glossary:`, `api:`, or `-tbd`.

## Step 02a Troubleshooting
- **Empty Environments**: Validation fails with `minProperties: 1` if an environment (`dev`, `ci`, etc.) object is empty. You must properly define keys (e.g., region, runner) or remove the environment from the list if not applicable (though all 4 are required by default).
- **Invalid Gate Names**: `ci_gates` must be kebab-case strings (regex: `^[a-z0-9-]+$`). "Run Tests" or "Schema Validate" will fail; use `run-tests` or `schema-validate`.
- **Missing Trace**: `trace` array is required to link the delivery baseline to upstream capabilities or charter.

## Step 03 Troubleshooting
- **Empty Terms**: Validation fails if `terms` array is empty (`minItems: 1`).
- **Lazy Definitions**: Validation fails if `definition` is under 20 characters.
- **Missing Optional Fields**: `domain` and `units` are recommended; if provided, they must follow strict patterns (lowercase kebab-case for domain, alphanumeric/slash for units) and cannot be empty strings.
- **NFR/Monitor Coverage**: Tooling will flag if metrics in NFRs/Monitoring do not match glossary terms or units.

## Step 04 Troubleshooting
- **Broken Bridge**: Every FR must trace to at least one upstream `capability-*`. Matrix validation will fail if this link is missing or broken.
- **Trace Format**: The `trace` field must be an array of objects (`{type, id, note}`), not strings.
- **Lazy Requirements**: Validation fails if `statement` < 20 chars or `acceptance_criteria.text` < 15 chars.
- **Invalid ID**: `fr_id` must follow kebab-case and be unique.

## Step 05 Troubleshooting
- **Missing Parameters**: Validation fails if `parameters` are needed but not defined in the new array format.
- **Invalid Schema Refs**: `input_schema_ref` and `output_schema_ref` should point to valid `file://`, `glossary:`, or be marked `-tbd`.
- **Protocol Mismatch**: Non-HTTP protocols like `grpc` must mapping their methods (e.g., to `POST`) as per proper guidance.
- **Empty Errors**: Every API must define at least one error state or explicitly justify why it cannot fail.

## Step 07 Troubleshooting
- **Invalid ID Pattern**: NFR IDs must follow the `nfr-<category>-<metric>` pattern (e.g., `nfr-latency-p95`).
- **Qualitative Targets**: Target values cannot be purely qualitative strings (e.g., "fast"). They must contain at least one digit or be a number.
- **Missing Owner**: Owners must be one of the allowed types (e.g., `product`, `engineering`, `ops`) and cannot be invented.

## Step 08 Troubleshooting
- **Orphan Fixtures**: Validation fails if `targets` is missing or empty. Every fixture must trace to at least one ID (`fr-*`, `api-*`, `nfr-*`, or `inv-*`).
- **Unknown Target**: The linter will flag any target ID that does not exist in the ingested spec context. Ensure you are referencing real IDs from Steps 4, 5, 6, or 7.
- **Mode Strictness**: If `mode` is `contract`, you must provide an `expected` object with `status` (integer 100-599).
- **Format Errors**: String IDs in `targets` are invalid; they must be objects `{ "type": "...", "id": "..." }`.

## Step 09 Troubleshooting
- **Unstructured Tech Stack**: Validation fails if `tech_stack` is a simple list of strings. It must be an object with keys `languages`, `frameworks`, `infrastructure`, `tools`, each containing objects with `name` and `version`.
- **Missing Traceability**: `milestones[].deliverables` is now required to link execution steps to FRs or APIs. Ensure you have valid `fr-*` or `api-*` IDs.
- **Capabilities Mismatch**: If you list a technology in `tech_stack` that isn't in `spec/01_capabilities.json`, you must either add it to Step 1 or justify it as a "Spike" in the plan.
- **Date Format**: `target_date` must use YYYY-MM-DD format.

## Step 10 Troubleshooting
- **Traceability**: Validation now supports `trace` and `links`. If you reference an upstream requirement (like Charter), ensure the IDs exist.
- **Spec Policy**: `spec_first_policy` must be a boolean. If set to `false`, justify it in the PR rules.
- **Invalid PR Rules**: `pr_rules` must use the allowed enum values (e.g., `validate`, `test`, `audit`). Free-form strings are forbidden.
- **Regex Errors**: `commit_message_rules.pattern` must be a valid regular expression. Invalid patterns will fail the verification script.
- **Schema Detection**: Ensure your file is named `spec/10_governance.json` or has an ID starting with `governance-` so tooling can detect it.

## Step 11 Troubleshooting
- **Missing Targets**: Validation fails if `target_ids` is missing or empty. Every threat must trace to at least one `api-*` or `component-*`.
- **Bad Mitigation Links**: `mitigations` keys must use strict `traceRef` objects. If you link to `inv-*` or `nfr-*`, the tooling verifies those IDs exist.
- **Invalid Category**: `category` must be one of the strict enum values (`authn`, `authz`, `business_logic`, `transport`, `data_privacy`).
- **Schema Sync**: `prompt_11_redteam.md` has an referenced step schema that must match `schema/11_redteam.schema.json`. Ensure they are kept in sync.

## Step 12 Troubleshooting
- **Cycle Detected**: The validation tool (`validators/step_12.py`) enforces a DAG. If you have a cycle (A->B->A), you must break it by refactoring job dependencies.
- **Missing Dependency**: All job IDs listed in `requires` must exist in the `jobs` list.
- **Unstructured Steps**: Steps must be objects with `id`, `name`, `command`. String steps are forbidden to prevent hallucinations.
- **Invalid Trace**: The `trace` field must be an **array of objects** (e.g., `[{ "type": "doc", "id": "10-governance" }]`) linking to upstream authority. Valid types are defined in `core/collections.schema.json`.
- **Command Prefixes**: Commands should theoretically map to standard tools (`python`, `bash`, `npm`). While not strictly enforced as a blocking error yet, stick to known tools.


## Step 14 Troubleshooting
- **Referential Integrity**: Validation fails if `source_milestones` contains IDs that do not exist in `09_impl_plan.json`. Ensure the upstream milestone IDs are correct.
- **Tech Stack Mismatch**: Validation fails if `tech_stack` items in Roadmap do not match (name and version) the items defined in Step 09.
- **Date Sequencing**: Milestones must be ordered chronologically. If `m2` lists `target_date` earlier than `m1`, validation fails.
- **Migration Plan**: `migration_plan` cannot be empty. If no migration is needed, explicitly state "No migration required..." (must be > 3 words). "none" or "n/a" is also allowed but monitored.
- **Dependency Rationale**: External dependencies must include a `note` explaining *why* they are blocking.

## Outputs
- Validated JSON artifacts under `spec/00*` through `spec/12*`.
- Updated trace matrix demonstrating FR ↔ API ↔ fixture ↔ NFR coverage.
- Governance rules embedded in CI to keep the spec authoritative.
