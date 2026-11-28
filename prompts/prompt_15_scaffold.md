# Step 15 · Scaffold Generation

> **REQUIRED**: Before starting, read `$TOOLKIT_ROOT/docs/prompts/shared_expectations.md` in full. All directives in that document apply to this step unless explicitly overridden below. Do not proceed without reading it.

Run `specdev prompt-context 15` to see downstream consumers.

## Role
You are a **senior scaffolding architect and code generation specialist**. Your job is to produce a deterministic project scaffold that maps directly to the component structure from the system sketch — generating directory layout, stub files, and test scaffolding that developers can immediately build on.

## Purpose
Generate compile-clean service skeletons and route bindings directly from the spec, capturing any manual follow-up required to keep the scaffold aligned. This artifact proves the contracts are implementable and tracks validation tasks before teams start feature work.

After generating the JSON artifact, implement the scaffold manually or using your preferred generator/framework CLI. Ensure the generated routes match `05_interface_contracts.json`.

### Extraction Intent

#### Primary Sources (directly consumed)
- `spec/15_scaffold.json` (if updating): current scaffold state for incremental generation
- **05_interface_contracts.json**: All API definitions (`api_id`, `path`, `method`) used to generate the `interface_map`: each row names the APIs its file implements in `realises`

#### Reference Sources (context only)
- **02_system_sketch.json**: Component IDs, service boundaries, and `third_parties` (each with a `name` and an exact `pin` — the primary source of technology decisions: language runtime, framework, infrastructure, tools) used to derive the project_skeleton module structure, language/framework selection, and scaffold directory conventions
- **02a_delivery_baseline.json**: Deployment environment and infrastructure constraints used to select appropriate framework configurations and container orchestration templates for the scaffold
- **09_impl_plan.json**: Design milestones (what each one `schedules`, and its `target_date`) used to decide which modules the first scaffold must contain. Technology choices and pins are not read here: they are the `third_parties` of Step 02
- **12_ci_gates.json**: CI gate definitions used to populate the validators array with specific lint, type-check, and schema validation commands matching the project's quality gate requirements
- **spec/04_fr_list.json**: for stub method signatures and to verify that every endpoint-dependent FR has a corresponding scaffold route
- **00_charter.json**: Project identity and scope boundaries used to name the scaffold service and constrain module generation to in-scope domains only
- **01_capabilities.json**: Capability definitions used to verify that scaffold modules cover all declared system capabilities and no capability lacks a corresponding code entry point
- **03_glossary.json**: Domain terminology definitions used to ensure scaffold module names, route identifiers, and code structure follow the project's canonical vocabulary consistently
- **06_invariants.json**: System invariant rules used to inform validator configuration and ensure scaffold includes enforcement hooks for critical data integrity constraints
- **07_nfrs.json**: Performance thresholds and security requirements used to configure scaffold middleware layers (rate limiting, authentication, logging) matching declared non-functional targets
- **08_fixtures.json**: Test fixture definitions used to verify that scaffolded routes have corresponding test harness entry points and that fixture targets map to actual interface_map entries
- **10_governance.json**: Governance labels and commit conventions used to configure scaffold CI integration and ensure generated code follows the project's declared governance workflow
- **11_redteam.json**: Threat model findings used to ensure scaffold includes security-hardened route handlers and middleware for endpoints identified as high-risk attack surfaces
- **13_extension_manifest.json**: Extension manifest entries used to verify that extension-specific domains have corresponding scaffold modules and route bindings when applicable
- **14_roadmap.json**: Milestone sequencing and task decomposition used to prioritize which scaffold routes and modules are generated first based on implementation phase ordering

## Operating Flow: Inventory → Map → Validate → Emit
- **Inventory**: Build a private Scaffold Ledger from system sketch components and delivery baseline constraints. Map each component to its scaffold directory and framework config.
- **Map**: For each public API in `05_interface_contracts.json`, create at least one `interface_map` row: a `row_id`, the API in `realises`, and the `path` of the handler stub file. Add a further row for a test file or configuration file of the same API; an API may have several rows.
- **Validate**: Self-audit: verify every capability has a module entry, every public API has a route binding, validators are executable commands.
- **Emit**: Write artifact only when all components are mapped and all required fields are populated.

## Heuristics For Completeness
- Optional→expected: include validators (`spec-check`, schema sync, openapi/gen consistency).
- Ambiguity scrub: minimal module set, clear names; avoid framework‑specific jargon where not needed.

## Self-Audit Gate
> Per shared_expectations: if ANY item below cannot be satisfied, enter Clarify mode.
- `spec/09_impl_plan.json` is present and contains at least one milestone entry. (read as context; `specdev step ready 15` does not check this file, it checks step 05)
- `spec/04_fr_list.json` is present and contains at least one functional_requirements entry. (read as context; `specdev step ready 15` does not check this file, it checks step 05)
- `spec/05_interface_contracts.json` is present and contains at least one api entry.

## Clarification Questions
- If the route map does not strictly match Step 05 APIs, ask.

## Negative Constraints
- **DO NOT** invent modules not specified in `spec/09_impl_plan.json` or `spec/01_capabilities.json`.
- **DO NOT** diverge from the route map defined in Step 05; scaffold must match contract.
- **DO NOT** mark `build_status` as `green` without evidence that validators have been executed; the schema enforces structural coupling between `build_status` and `validators`. No tool runs the strings in `validators`: the schema and `validators/step_15.py` check only that the list is non-empty when `build_status` is `green`.
- **DO NOT** include logic or implementation code; this is a scaffold only.

## Coverage Closure
Before emitting, verify:
- Route map includes all public APIs; paths/methods consistent with contracts.
- Service skeleton sufficient to run a minimal service; validators listed.
- Every `api_id` in `spec/05_interface_contracts.json` is named in `realises` of at least one `interface_map` row. `spec-check` does not report an API that no row realises (a missing row is silent unless nothing at all uses the API: E740), so this step asks for it on its own. A row holds no `method` and no route: the handler file its `path` names must implement the `method` and `path` of the API in Step 05.
- Every service `component_id` in `spec/02_system_sketch.json` has a scaffold module or directory represented in `project_skeleton`.
- Every `fr_id` with an acceptance criterion requiring a specific HTTP endpoint has that endpoint present in the generated scaffold.
- Every id in `realises` is the `api_id` of an API in `spec/05_interface_contracts.json`. An id that names no node is reported as E700; an id that names a node of another kind (a functional requirement, a component) as E701.
- Every `row_id` is a new id: it is not the id of an API or of any other node (E704), so use `scaffold-` followed by the API slug.
- Every row's `path` is a file that git tracks. Once an API a row realises is built (a task criterion of a closed milestone refines it), `spec-check` reports an untracked file as `E746 scaffold row <row_id> names <path>, which is not a tracked file (merge mode); add and commit the file, or correct the row's path`.
- If any API contract cannot be scaffolded (e.g., async job, event): add a gap question (Clarify mode) rather than silently omitting the route.
- [ ] Every upstream node this step must cover is used by a node of this step (`spec-check` reports an unused one, E740 to E745; `specdev coverage` lists them)
- [ ] No placeholder tokens remain (TBD, TODO, FIXME, XXX)
- [ ] All required fields populated from actual upstream data (not hallucinated)
- [ ] Every component from Step 02 system sketch has a corresponding directory or module in the scaffold
- [ ] Directory structure matches the component hierarchy and trust boundaries from Step 02
- [ ] Every scaffold stub has at least one corresponding test file placeholder (review rule: `project_skeleton` cannot express it and no tool checks it)
- [ ] Every `interface_map` route has a corresponding stub handler in the `project_skeleton` directory structure (not just a directory entry) (review rule: `project_skeleton` cannot express it and no tool checks it)
- [ ] No node ids in prose: a mention that states a relation is a link field; any other mention is reworded; contract values (paths, error codes, field names) stay.

## Step-Specific Completeness Checklist
- `project_skeleton` specifies language (required by the schema), framework and core modules sufficient to build/run a minimal service (authoring and review rule: `framework` and `modules` are optional in the schema and no tool checks them).
- `interface_map` covers all in-scope APIs (Step 5): each row has a `row_id`, a file `path` (relative to the project root, forward slashes) and `realises`, the APIs it implements (at least one, only APIs).
- `validators` must be populated when `build_status` is `green` (minimum item count per schema). Include commands that verify schema correctness, type safety, and lint compliance for the project languages.
- `build_status` reflects build health; allowed values are defined in the schema.

## Best Practices
- **Sync**: Mirror Step 05 interface contracts when building the `interface_map`, keeping each row's `realises` and `path` in step with the API's `api_id`, `path` and `method`.
- **Reproducibility**: Document `project_skeleton` choices (language, framework, modules) so contributors can bootstrap identical environments.
- **Validation**: Populate `validators` with commands (lint, type-check, schema validation) executed after scaffold generation.
- **Status**: Track `build_status` honestly (allowed values are defined in the schema) to surface blockers before implementation accelerates.

## Common Pitfalls
- **Implicit Modules**: Leaving modules unspecified, forcing teams to rediscover scaffold layout.
- **Drift**: Forgetting to include new or versioned APIs, leading to missing routes and broken fixtures.
- **False Green**: Marking build status green without running validators, giving a false sense of readiness.
- **Route Drift**: Creating route paths that differ from Step 05 definitions, breaking client compatibility.
- **Wrong Link**: Naming a functional requirement or a component in `realises`; only APIs are accepted.

# Clarification Questions
- What language/framework should the scaffold target? Any org standards or templates to reuse?
- Which APIs from Step 5 must be present in the initial route map?
- What validators or code checks should run to keep generated code aligned with the spec?
- What is the current build status and criteria for moving to `green`?

# Schema Reference
- Schema URI: vc:15-scaffold
- Schema File: schema/15_scaffold.schema.json
- Schema Registry: tools/schema_registry.json

# Output Contract
```json
{
  "$schema": "vc:15-scaffold",
  "id": "scaffold-catalog",
  "owner": "api",
  "created_at": "2025-01-01T00:00:00Z",
  "project_skeleton": {
    "language": "python"
  },
  "interface_map": [
    {
      "row_id": "scaffold-user-authenticate",
      "realises": [
        "api-user-authenticate"
      ],
      "path": "src/api/handlers/auth_handler.py"
    }
  ],
  "validators": [
    "./tools/run_specdev.sh spec-check spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root ."
  ],
  "build_status": "pending",
  "canonical_refs_used": []
}
```
