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
| 10 — Governance | Set the commit-message convention and the rules that enforce the charter's constraints | `spec/10_governance.json` |
| 11 — Red Team | Enumerate threats and mitigations | `spec/11_redteam.json` |
| 12 — CI Gates | Wire automated enforcement | `spec/12_ci_gates.json` |

## Transition: Extensions
1.  **Step 13 (Extension Generator)**: Identify if you need specialized extensions for complex domains found in System Sketch. Each extension the manifest declares has two files in `spec/extensions/` (for `ext-01-database`: `ext_01_database.schema.json` and `ext_01_database.json`), and the step ends with `specdev spec-check spec --step 13` (see [extension_schemas.md](../extension_schemas.md)).
2.  **Step 14 (Roadmap)**: Run `specdev step ready 14`. Before step 14 is written it checks the steps it will read (07, 08 and 12 among them): it exits 0 and prints `step 14: ready` when each has a file and no pending replay or coverage gap; otherwise it lists the blockers, and those are the findings to fix first (on a copy of the worked example with steps 14 to 16 removed: 11 blockers, 1 at step 07, 5 at step 08 and 5 at step 12, the same that `specdev stale` lists under those steps). The gaps that step 14 itself owns (E740 of the nodes a task criterion uses, E742 of the fixtures, and E566 of the FRs no criterion reaches, which `spec-check` reports) are not blockers: the task criteria of step 14 clear them. Step 13a (the completeness assessment) was removed in 1.2.0: `specdev coverage` and the role findings of `specdev spec-check` (E740 to E745) answer the same question.

Consult the matching `spec/NN_name.guide.md` before running the prompt for each step.

## AI Assist Flow
Prompts are designed for a two‑phase interaction to reduce rework:
- Phase A — Clarify: the assistant ingests the step’s context and asks targeted Gap Questions when the “Self‑Audit Gate” is not satisfied.
- Phase B — Emit: once answers are provided, the assistant writes the artifact JSON to disk (`specdev step create NN --from <draft>` for a new step, `specdev json patch|insert|delete --id` for an existing one) and validates against the schema.
Clarify responses should be short, bulleted questions grouped by topic (no JSON, no code fences), prioritizing gating items; the assistant stops until answers are provided.

## Validation Cadence
Use the [core validation commands](../reference.md#core-validation-commands) after each artifact update to keep discovery outputs consistent before moving to implementation.

## Step 02 Troubleshooting
- Components, connections and third parties require `derives_from` (links to capabilities or constraints, components, seeds or constraints respectively; a component and a connection may list a seed routed to step 02 beside them); a missing one fails schema validation.
- Components must include 3–6 responsibilities and an owner.
- Multiple components require at least one connection; each connection must include `connection_id`, `protocol`, `trust_boundary`, `derives_from` (the source component) and `connects_to` (a component or third party).
- `partner`/`public` connections require `auth` and `rate_limit`; `event` protocol requires `reliability`.
- Connections no longer carry `schema_ref` or `interface_ref`; `tech_stack` is removed in favour of `third_parties`.

## Step 02a Troubleshooting
- **Empty Environments**: an empty environment object (`"dev": {}`) fails schema validation: every environment needs `scope` and a non-empty `derives_from`, plus `scope_reason` when `scope` is `later` or `out`. Host keys (region, runner, replica count and so on) are optional and go under the environment's `config` object, never beside `scope`; `config`, when present, needs at least one key (`"dev": {"config": {}}` fails). All four environments (`dev`, `ci`, `staging`, `prod`) are required by default.
- **Invalid Gate Names**: each `ci_gates[]` entry is an object whose `gate_id` must be kebab-case (regex: `^[a-z0-9]+(?:-[a-z0-9]+)*$`). "Run Tests" or "Schema Validate" will fail; use `run-tests` or `schema-validate`.
- **Missing `derives_from`**: every environment, gate and secret requires `derives_from`; the artifact-level `trace` is gone. Environment host keys go under the environment's optional `config` object.

## Step 03 Troubleshooting
- **Empty Terms**: Validation fails if `terms` array is empty (`minItems: 1`).
- **Lazy Definitions**: Validation fails if `definition` is under 20 characters.
- **Missing Optional Fields**: `domain` and `units` are recommended; if provided, they must follow strict patterns (lowercase kebab-case for domain, alphanumeric/slash for units) and cannot be empty strings.
- **NFR/Monitor Coverage**: Tooling will flag if metrics in NFRs/Monitoring do not match glossary terms or units.

## Step 04 Troubleshooting
- **Missing `derives_from`**: Every FR must list at least one upstream capability in `derives_from`; schema validation fails if it is missing. FR-to-FR dependencies go in `depends_on`.
- **No `trace`**: the `trace` field is gone; use `derives_from` and `depends_on`.
- **Lazy Requirements**: Validation fails if `statement` < 20 chars or `acceptance_criteria.text` < 15 chars.
- **Invalid ID**: `fr_id` must follow kebab-case and be unique.

## Step 05 Troubleshooting
- **Missing Parameters**: Validation fails if `parameters` are needed but not defined in the new array format.
- **Invalid Schema Refs**: `input_schema_ref` and `output_schema_ref` are a path relative to the repository root, a JSON Pointer into the current document or an absolute URL; use `-tbd` while the schema is not defined, and omit the field when the endpoint has no body.
- **Protocol Mismatch**: For a non-HTTP protocol (`grpc`, `ws`, `mqtt`) omit `method` and `path`; the schema requires them only for `http`.
- **Error Objects**: each `errors[]` entry is an object with `error_id`, `code`, `message`, `scope` and `derives_from` (acceptance criteria ids); `severity` is optional, and so is `protocol_status` (the status number the API's protocol carries with the error, the one place the number is written: the HTTP status for an `http` API, an integer from 100 to 599; a gRPC status code, a WebSocket close code or an MQTT reason code for the others). A string entry fails schema validation. The schema does not require the list to be non-empty; for an `http` API include at least one 4xx and one 5xx error by convention.

## Step 07 Troubleshooting
- **Invalid ID Pattern**: NFR IDs must follow the `nfr-<category>-<metric>` pattern (e.g., `nfr-latency-p95`).
- **Qualitative Targets**: Target values cannot be purely qualitative strings (e.g., "fast"). They must contain at least one digit or be a number.
- **Missing Owner**: Owners must be one of the allowed types (e.g., `product`, `engineering`, `ops`) and cannot be invented.

## Step 08 Troubleshooting
- **Orphan Fixtures**: Validation fails if a fixture carries neither `verifies` nor `removes`. `verifies` takes one or more ids of acceptance criteria, APIs, invariants or NFRs (not FRs).
- **Link Targets**: `specdev spec-check` reports a `verifies` id that no node has (E700) and one that names a node of a kind the field does not accept (E701); `specdev validate` of the fixtures file alone does not.
- **Mode Strictness**: If `mode` is `contract`, you must provide an `expected` object with `status`: an HTTP status (integer 100-599), or, for a fixture that names APIs and no `http` API among them (in `verifies`, or through an API error in `expects`), the status number of that protocol (an integer of 0 or more). A contract fixture that names no API either way is held to the HTTP range: add the API to its `verifies`.
- **Error Outcomes**: A fixture names in `expects` every API error it expects as its outcome (usually one id, more when one response carries several errors). A fixture whose `expected.status` is in the HTTP error range (400 to 599) and that names none is E754, except for a fixture that holds `removes`. When `expected` gives a `status`, it equals the `protocol_status` of every error named (E755), and when the fixture verifies an invariant, that invariant names at least one of those errors in `constrains` (E756). `expects` is not a proof: the error is proven through the criterion it derives from.
- **Manual Mode**: `mode: manual` requires `manual_reason`, a string of at least 10 characters.

## Step 09 Troubleshooting
- **Missing Schedules**: Every `milestones[]` entry requires `schedules`, with at least one id of a functional requirement, acceptance criterion, API, invariant, NFR, component, environment or risk. `deliverables`, `depends_on`, `status` and the top-level `tech_stack`, `dependencies` and `trace` are not part of the schema.
- **Date Format**: `target_date` must use YYYY-MM-DD format.

## Step 10 Troubleshooting
- **Rules**: The artifact needs `rules` (at least one) and `commit_message_rules`. Each rule needs `rule_id`, `text` and `derives_from` (at least one id of a constraint, risk, scope item, gate, environment or stakeholder). `pr_rules`, `spec_first_policy`, `review_policy`, `reviewers`, `trace` and `links` are not part of the schema.
- **Enforcer**: `enforcer` accepts only `review`, and a rule that carries `enforcer` must not carry `cli_command`.
- **Regex Errors**: `commit_message_rules.pattern` must be a valid regular expression. An invalid pattern is reported by `specdev governance-check` as E303 (`commit_message_rules.pattern is not a valid regular expression`).
- **Schema Detection**: Ensure your file is named `spec/10_governance.json` or has an ID starting with `governance-` so tooling can detect it.
- **Enforcement**: the rules are checked by the merge check (`specdev spec-check --merge`, run by the `specdev-merge-check.yml` workflow); the toolkit does not block a pull request.

## Step 11 Troubleshooting
- **Missing Targets**: Validation fails if a threat has no `threatens` (at least one id of an API, component, connection or third party). An edge case needs `threatens` (API, component or FR ids) and `mitigated_by` (at least one id).
- **Mitigation Links**: `mitigated_by` on a threat is optional. W583 and W615 read `threatens` and `mitigated_by`. `target_ids` and `mitigations` are not part of the schema.
- **Invalid Category**: `category` must be one of the strict enum values (`authn`, `authz`, `business_logic`, `transport`, `data_privacy`).
- **Schema Sync**: `prompt_11_redteam.md` has an referenced step schema that must match `schema/11_redteam.schema.json`. Ensure they are kept in sync.

## Step 12 Troubleshooting
- **Cycle Detected**: The `graph` check of `specdev spec-check` reports a cycle among the jobs as E703 ("Link cycle within step 12: ..."); `specdev validate` on `12_ci_gates.json` alone does not. If you have a cycle (A->B->A), you must break it by refactoring job dependencies.
- **Missing Dependency**: All job IDs listed in `depends_on` must exist in the `jobs` list (the job field was `requires` in 1.1.1); `specdev spec-check` reports one that does not as E700.
- **Unstructured Steps**: Steps must be objects with `name` and `command`. String steps are forbidden to prevent hallucinations; the step `id` field is gone.
- **Links**: `realises` (environments, gates, secrets, rules) and `verifies` (NFRs) on a job are optional. The `trace` field is gone.
- **Command Prefixes**: Commands should theoretically map to standard tools (`python`, `bash`, `npm`). While not strictly enforced as a blocking error yet, stick to known tools.


## Step 14 Troubleshooting
- **Criterion Links**: Every `acceptance_criteria[]` entry needs `refines` (at least one id) or `removes` (at least one id). `verified_by` takes ids of fixtures, jobs or rules (it was `fixture_ref` in 1.1.1).
- **Task Deferral**: A task is set aside with `disposition`, which needs both `value` (`deferred` or `wont_do`) and `reason`. Task and milestone `status` are gone.
- **Removed Fields**: `fr_refs`, `capability_refs`, `source_milestones`, `deliverables`, `tech_stack` and `dependencies` are not part of the schema.
- **Date Sequencing**: Milestones must be ordered chronologically. If `m2` lists `target_date` earlier than `m1`, validation fails.
- **Migration Plan**: `migration_plan` cannot be empty (the schema requires at least one character; the vague-language lint, W593, also scans it). If no migration is needed, state it explicitly ("No migration required because ...").

## Outputs
- Validated JSON artifacts under `spec/00*` through `spec/12*`.
- Links between the nodes of the steps, which `specdev coverage` counts (FRs with an API, FRs with a fixture, capabilities with an FR) and `specdev trace` follows. `specdev matrix` and the stored trace matrix were removed in 1.2.0.
- Governance rules embedded in CI to keep the spec authoritative.
