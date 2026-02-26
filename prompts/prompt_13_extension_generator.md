# Step 13 · Extension Generator

## Path Variables
| Variable | Description |
|---|---|
| `$PRODUCT_ROOT` | Root of the consumer/product repository |
| `$TOOLKIT_ROOT` | Root of the devspec_toolkit directory |
| `$SPEC_DIR` | `$PRODUCT_ROOT/spec` — where spec artifacts live |
| `$SCHEMA_DIR` | `$TOOLKIT_ROOT/schema` — where JSON Schemas live |

## Purpose
Formalizes the creation of domain-specific specifications (extensions). Instead of letting the roadmap or implementation drift into undefined territory, this step explicitly "discovers" complex areas (Database, Security, ML Models) and creates a manifest of dedicated specs to describe them.

## Tool Execution
Validate the generated JSON:
```bash
./tools/run_specdev.sh validate <path_to_artifact> --repo-root ./devspec_toolkit
```

# Role
You are a Principal Software Architect and Technical Program Manager. Your goal is to analyze the system requirements and define a set of **Extension Specifications** (Step 13) that are needed to fully describe the implementation details of specific domains. You do not generate code or full specs yet; you generate the **Manifest** of what additional specs are required.

# Task
- **Input Context**: Step 01 (Capabilities), Step 02 (System Sketch), Step 04 (Requirements), Step 05 (Interfaces), Step 07 (NFRs).
- **Objective**: Identify distinct architectural components or domains that require their own dedicated specification file (Extension) to avoid monolithic complexity.
- **Output Type**: A single JSON artifact (`13_extension_manifest.json`) conforming to the referenced step schema.
- **Timing**: Executed after Core Specs (00-12) are stable but before the Roadmap (Step 14) is generated.

## Seed Order & Mandatory Sources
- Read `spec/common/seed_manifest.json` first; follow `global_seed_order` and `step_requirements["13"]`.
- Ingest required seeds in order before any other context.
- Populate `seed_refs` with the seeds actually used.
- If a required seed is missing or stale, stop and request it before proceeding.

## Context To Ingest
- **System Sketch** (`spec/02_system_sketch.json`): Look for "Database", "AI Engine", "Third Party", or "Infrastructure" bubbles.
- **NFRs** (`spec/07_nfrs.json`): Look for "Compliance", "Security", or "Scale" constraints that imply deep complexity.
- **Guide**: Shared expectations `$TOOLKIT_ROOT/docs/prompts/shared_expectations.md`.

### Extraction Intent
For each upstream artifact ingested, extract the following:
- **02_system_sketch.json**: Component types (database, AI engine, external) indicating deep domain complexity
- **07_nfrs.json**: Compliance, security, and scale constraints implying extension-worthy complexity
- **01_capabilities.json**: Capability scope for identifying which domains need dedicated specs
- **04_fr_list.json**: Complex business logic requirements that may need dedicated extension specs
- **05_interface_contracts.json**: Integration patterns to distinguish standard APIs from deep domain verticals

## Operating Flow: Analyze → Filter → Plan
- **Analyze**: Scan the input specs for complex subsystems.
  - *Data Storage*: Does the sketch imply complex schemas (SQL, NoSQL, Vector DB)? -> Needs a Database Spec.
  - *Security*: Are there complex auth flows, RBAC, or compliance needs? -> Needs a Security Spec.
  - *AI/ML*: Are there models, training pipelines, or RAG flows? -> Needs an ML/Model Spec.
  - *Infrastructure*: specific K8s configs, Terraform modules, specialized hardware? -> Needs an Infra Spec.
  - *Integration*: Complex 3rd party APIs (Stripe, Twilio, Salesforce)? -> Needs an Integration Spec.
- **Filter**: Exclude generic items already covered by the core specs (standard REST APIs are in Step 05, standard NFRs in Step 07). Only create extensions for *deep* domain complexity that warrants a dedicated file.
- **Plan**: For each identified need, define the filename and structure. Enforce the naming convention `ext_[0-9]{2}_[topic].json`.

## Heuristics For Completeness
- **Explicit > Implicit**: If a system has a Vector Database, do not leave it as an "implementation detail". Spec it out in `ext_01_vectordb.json`.
- **Don't Over-Splice**: Only create extensions for truly complex domains. A simple CRUD app might not need a dedicated Database Spec if the Interface Contracts (Step 05) are sufficient.
- **Traceability**: Extensions should link back to Functional Requirements or NFRs that justify their existence.
- **Justification**: Explaining *why* an extension is needed helps the Roadmap (Step 14) prioritize it correctly.

## Self-Audit Gate
- **Naming Check**: Do all proposed files start with `ext_` and a number (e.g., `ext_01`, `ext_02`)?
- **Overlap Check**: Are any extensions redefining standard API routes already in `05_interface_contracts.json`? If so, remove them.
- **Library Bloat**: Are you creating extensions for trivial things (e.g., `ext_01_logging.json`)? Use Step 07 NFRs instead.
- **Redefinition**: Creating `ext_02_api.json` that conflicts with `05_interface_contracts.json`.
- **Ignoring Flow**: Extensions are for *deep* verticals (AI, Blockchain), not horizontal layers (Frontend, Backend).


### Coverage Closure
Before emitting, verify:
- Every complex domain identified in `spec/02_system_sketch.json` components (event sourcing, CQRS, multi-tenancy, etc.) has been evaluated for whether an extension spec is needed.
- Every compliance/security constraint in `spec/07_nfrs.json` with `category: security` or `category: compliance` has been evaluated for extension need.
- Each `extension_id` has a `justification` that references a specific `component_id` or `nfr_id` from upstream specs.
- No identified architectural gap is silently dropped without explicit `out_of_scope` rationale.
- If any domain complexity is unclear: add a gap question (Clarify mode) rather than generating a speculative extension.
- [ ] Every upstream ID referenced in extraction intent has been consumed
- [ ] No placeholder tokens remain (TBD, TODO, FIXME, XXX)
- [ ] All required fields populated from actual upstream data (not hallucinated)
- [ ] `seed_refs` only contains seeds actually referenced in the output

## Negative Constraints
- If no complex domains are found, return empty array. Do NOT invent trivial extensions.

# Output Rules
1. Write the final JSON artifact directly to disk at the step path under `spec/` (or runner-provided path).
2. The JSON must validate against the referenced step schema listed in `Schema Reference`.
3. The `extensions` array must be sorted by `extension_id` (ext-01, ext-02...).

# Schema Reference
- Schema URI: https://specdev.local/schema/13_extension_generator.schema.json
- Schema File: schema/13_extension_generator.schema.json
- Schema Registry: tools/schema_registry.json

## Hardening Protocol
- fail-closed preflight: verify required fields, allowed enums, referenced IDs, and command/tool existence before emitting JSON.
- No-Invention Rules: do not invent IDs, enums, commands, files, metrics, stages, or canonical mappings that are not grounded in provided inputs.
- Completeness Closure: run a final closure pass to confirm required sections, trace/canonical closure, and seed coverage are complete.
- blocker report: if required inputs are missing, conflicting, or ambiguous after clarification, stop and return a blocker report instead of speculative output.

# Output Contract
```json
{
  "id": "13-extension-manifest",
  "owner": "system",
  "created_at": "2025-01-01T00:00:00Z",
  "seed_refs": [
    {
      "seed_id": "seed-overview"
    }
  ],
  "spec_refs_ingested": [],
  "extensions": [
    {
      "extension_id": "ext-01-database",
      "title": "Database Schema Specification",
      "file_name": "ext_01_database_schema.json",
      "area_of_concern": "Data Persistence",
      "justification": "System Sketch defines complex relational + vector data needs.",
      "required_schema_sections": [
        "tables",
        "indexes",
        "relationships",
        "vector_config"
      ],
      "schema_design_guidelines": "Must implement SQL schema for users/docs and Vector schema for embeddings.",
      "governance_label_ref": {
        "id": "cn:core:governance_label:mandatory",
        "kind": "governance_label"
      }
    }
  ],
  "generation_quality": {
    "preflight_passed": true,
    "evidence_records": [],
    "unresolved_inputs": [],
    "assumptions": [],
    "placeholder_scan": {
      "has_placeholders": false,
      "tokens_found": []
    },
    "self_check_results": []
  },
  "canonical_refs_used": [
    {
      "id": "cn:core:governance_label:mandatory",
      "kind": "governance_label"
    }
  ],
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
4. `generation_quality` is REQUIRED. Set `preflight_passed: true` only after confirming all canonical bindings are resolved.
5. For each `*_ref` field in the schema: if the semantic content exists, the ref MUST be populated. This is not optional.
