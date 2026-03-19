# Step 09 · Implementation Plan

Run `specdev prompt-context 09` to see downstream consumers. This prompt's output feeds 3 downstream steps.

## Schema Authority

The schema at `schema/09_impl_plan.schema.json` is the authoritative source for all
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
Translate the validated spec into an executable delivery roadmap that covers technology choices, sequencing, risks, and migration strategy. The implementation plan aligns teams on what will ship when, how dependencies are managed, and which experiments or spikes de-risk the path.

## Tool Execution
Validate the generated JSON:
```bash
./tools/run_specdev.sh validate <path_to_artifact> --repo-root ./devspec_toolkit
```

# Role
You are a senior specification author and validator. Your job is to emit a single JSON artifact for **Step 9 · Implementation Plan** that is machine-checkable and immediately consumable by CI and generators. You do not write examples, tutorials, or comments. You only output the canonical JSON that matches the schema.

# Task
- **Input context:** previously authored spec artifacts (Charter, Capabilities, Glossary, FRs, etc.) available to you in the workspace; organizational constraints; known IDs for cross-references.
- **Objective:** produce a complete, falsifiable artifact for **Step 9 · Implementation Plan**.
- **Output type:** one JSON document conforming to the referenced step schema.
- **Determinism:** when unspecified, choose the minimal valid value that preserves falsifiability and traceability.
- **Traceability:** if this step has `trace` or `links`, connect to at least one upstream or downstream artifact.

### Extraction Intent
For each upstream artifact ingested, extract the following:
- **00_charter.json**: Project constraints, stated risks, timeline boundaries, and success metrics that bound milestone sequencing, target dates, and risk mitigation planning
- **01_capabilities.json**: Capability IDs and priority rankings to ensure every capability is covered by at least one milestone deliverable or explicitly scoped out with rationale
- **02_system_sketch.json**: Component IDs, component status (active vs deprecated), and inter-component data flows to inform architecture decisions and trigger migration plan requirements
- **02a_delivery_baseline.json**: Deployment environment definitions, infrastructure constraints, and CI gate expectations that shape infrastructure tech stack selections and milestone phasing
- **03_glossary.json**: Domain term definitions and canonical vocabulary to ensure milestone names, deliverable descriptions, and tech stack rationale use consistent domain language
- **04_fr_list.json**: Functional requirement IDs and acceptance criteria to populate milestone deliverables arrays with traceable FR references ensuring full coverage
- **05_interface_contracts.json**: API IDs, protocol choices, and endpoint definitions to populate milestone deliverables arrays with traceable API references and inform framework selection
- **06_invariants.json**: Invariant IDs and enforcement conditions that constrain tech stack choices and must be satisfied as acceptance criteria within milestone deliverables
- **07_nfrs.json**: Non-functional requirement IDs, performance targets, and quality thresholds that constrain tech stack selection and define spike success criteria for unknowns
- **08_fixtures.json**: Test fixture definitions and target coverage expectations that validate milestone acceptance signals and inform spike scoping for test infrastructure

## Operating Flow: Synthesize → Clarify → Emit
- Build a private Plan Ledger: tech_stack (language/framework/db/tooling + versions), milestones (id/name/date/risks/spikes), migration plan (if replacing), dependencies (teams/vendors/apis). Do not output it.
- **Cross-Check**: Verify your `tech_stack` selection against `spec/01_capabilities.json`. Do not introduce technologies not listed in capabilities unless a corresponding Spike entry exists in `milestones[*].spikes` with explicit rationale referencing the capability gap.
- Align milestones with governance/CI cadence from upstream charter constraints and governance specs; add spikes for unknowns.
- Self-audit; if any risk lacks a measurable impact statement, any spike lacks a success criterion, or any dependency lacks an owner and timeline, ask Gap Questions.
- Rewrite milestones for outcomes and acceptance signals; finalize plan.
- Emit JSON when the plan is actionable.

## Heuristics For Completeness
- MUST populate `target_date` when milestones have ordering dependencies (i.e., one milestone's `deliverables` are consumed by another milestone). MUST include `migration_plan` when any `component_id` in `spec/02_system_sketch.json` has `status: deprecated` or is being replaced.
- Ambiguity scrub: milestones should map to delivered FRs/APIs and passing CI gates.

## Self-Audit Gate
- If score < 0.9, output clarifying questions only — do not emit JSON.
- Gating items:
  - Tech choices include versions and rationale; milestones have names and acceptance signals; known risks/spikes captured.
  - `tech_stack` aligns with `01_capabilities.json`.
  - Dependencies listed for external teams/systems; plan aligns with governance/CI expectations.
  - If milestone dates are not stated in `spec/00_charter.json` constraints, delivery sequencing is ambiguous, or resource constraints are not specified in any upstream artifact, ask Gap Questions — do not invent timeline commitments.

### Coverage Closure
Before emitting, verify:
- Every `capability_id` from `spec/01_capabilities.json` appears in ≥1 milestone's scope or deliverables, OR explicitly listed in `out_of_scope` with rationale.
- All `component_id` values from `spec/02_system_sketch.json` are reflected in the `tech_stack` or architecture decisions.
- Every charter constraint in `spec/00_charter.json` (`constraints`, `risks`) is addressed in milestones, risks, or migration plan.
- All dependencies between milestones are explicit — no implicit ordering assumptions.
- If any capability has unclear implementation path: add a gap question (Clarify mode) rather than deferring silently.
- [ ] Every upstream ID from ingested context has been consumed
- [ ] No placeholder tokens remain (TBD, TODO, FIXME, XXX)
- [ ] All required fields populated from actual upstream data (not hallucinated)

# Output Rules
1. Write the final JSON artifact directly to disk at the step path under `spec/` (or runner-provided path).
2. The JSON must validate against the referenced step schema listed in `Schema Reference`.
3. All IDs must be unique kebab-case strings.
4. Use concrete verbs and measurable outcomes; avoid adjectives that are not testable.
5. Include explicit preconditions, postconditions, and error states where applicable to the schema.
6. Set `owner` to one of: `api`, `ui`, `system`, `ops`, `data`, `product`, `business`, `engineering`.
7. **Traceability**: You MUST include a top-level `trace` array linking to the Charter (`00_charter.json`) or System Sketch (`02_system_sketch.json`).
8. Do not include any fields outside the schema. `additionalProperties` is false everywhere.

## Negative Constraints
- **NO Hallucinations**: Do not list technologies in `tech_stack` that are not present in `spec/01_capabilities.json` without a clear "Spike" justification.
- **NO Generic Versions**: Do not use "latest" or "stable". You must allow the specific version pinning (e.g., "^3.9", "^1.2.3").
- **NO Orphan Milestones**: Do not create milestones that do not link to at least one FR or API in `deliverables`.
- **NO Unstructured Tech Stack**: Do not provide `tech_stack` as a list of strings. It MUST be an object with `languages`, `frameworks`, `infrastructure`, and `tools` arrays.
- **NO Missing Rationale**: Do not omit `rationale` for `tech_stack` items. Explain WHY a technology was chosen.

## Step-Specific Completeness Checklist
- `tech_stack` declares languages, frameworks, data stores, and major infra choices with rationale where contentious.
- Milestones include clear names, target dates, risks, and spikes for unknowns.
- `migration_plan` describes data or API migration if replacing existing systems.
- `dependencies` enumerate external systems, teams, or contracts that impact delivery.

## Field-by-Field Guidance
- tech_stack: structured object with arrays for `languages`, `frameworks`, `infrastructure`, `tools`. Each item must have `name`, `version`, and `rationale`.
    - `name`: exact library/tool name (e.g., "pydantic", "postgresql").
    - `version`: semantic version constraint (e.g., "^2.0.0").
    - `rationale`: brief reason for selection (e.g., "Standard backend language per capabilities").
- milestones[*].milestone_id/name: kebab-case ID and descriptive name.
- milestones[*].target_date: ISO date for planning; can be tentative.
- milestones[*].status: `pending`, `in_progress`, `done`, `deferred`.
- milestones[*].risks/spikes: concrete bullets (e.g., perf unknowns, vendor limits, schema evolution).
- milestones[*].deliverables: array of trace references linking to FRs/APIs.
- migration_plan: narrative plan for cutover/backfill/rollback.
- dependencies: list of external dependencies and agreements.

## Best Practices
- **Stack**: Capture `tech_stack` decisions with rationale, version constraints, and ownership so scaffold generation is predictable.
- **Milestones**: Organize `milestones` by value increments tied to charter metrics or capability unlocks, using `target_date`. Link deliverables to FRs/APIs.
- **Adaptability**: Document `risks` and `spikes` with clear mitigation steps to keep delivery adaptable.
- **Migration**: Detail the `migration_plan` when replacing legacy systems, calling out cutover criteria and rollback triggers.
- **Dependencies**: Enumerate `dependencies` across teams or vendors to schedule integration work early.

## Common Pitfalls
- **Grab Bag**: Treating `tech_stack` as a grab bag with no versioning, leading to incompatible scaffolds.
- **Vague Steps**: Listing milestones without success signals, making it unclear when a stage is truly done.
- **Surprise**: Ignoring migration steps, which causes surprise downtime or data loss later.
- **Blockers**: Omitting external dependencies until late, creating critical path delays.

## Quick Reference
- Required: `tech_stack`.
- Milestones: `milestone_id`, `name`, optional `target_date`, `risks`, `spikes`.

# Clarification Questions
- What tech choices are locked vs flexible? Any org standards to follow?
- What are the major deliverable milestones with dates? What risks or spikes accompany each?
- Are we migrating from an existing system? What is the plan for data, compatibility, and rollback?
- What external dependencies (teams, vendors) could block delivery? How will we mitigate?

# Schema Reference
- Schema URI: https://specdev.local/schema/09_impl_plan.schema.json
- Schema File: schema/09_impl_plan.schema.json
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
  "id": "impl-plan-catalog",
  "owner": "api",
  "created_at": "2025-01-01T00:00:00Z",
  "tech_stack": {
    "languages": [
      {
        "name": "python",
        "version": "^3.9",
        "rationale": "Required for ONNX Runtime compatibility"
      }
    ],
    "frameworks": [
      {
        "name": "FastAPI",
        "version": "^0.110.0",
        "rationale": "High-performance web framework"
      }
    ],
    "infrastructure": [
      {
        "name": "Raspberry Pi 4",
        "version": "Model B 4GB",
        "rationale": "Primary deployment target"
      }
    ],
    "tools": [
      {
        "name": "structlog",
        "version": "^24.1.0",
        "rationale": "Structured logging implementation"
      }
    ]
  },
  "milestones": [
    {
      "milestone_id": "milestone-setup-core-infrastructure",
      "name": "Setup Core Infrastructure and Environment",
      "target_date": "2025-11-15",
      "status": "pending",
      "risks": [
        "Raspberry Pi 4 setup and performance profiling may reveal unexpected constraints"
      ],
      "spikes": [
        "Performance testing with small dataset on Raspberry Pi 4 to validate target latency"
      ],
      "deliverables": [
        {
          "type": "fr",
          "id": "fr-search-hybrid-retrieval"
        }
      ]
    }
  ],
  "migration_plan": "No migration required as this is a new implementation of the personal knowledge RAG system.",
  "dependencies": [
    "Raspberry Pi 4 hardware (for deployment)",
    "Cloudflare Access for admin authentication"
  ],
  "trace": [
    {
      "type": "doc",
      "id": "personal-knowledge-rag-system"
    }
  ],
  "canonical_refs_used": []
}
```

