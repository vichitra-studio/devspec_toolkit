# Step 13 · Extension Generator

> **Inherits**: `$TOOLKIT_ROOT/docs/prompts/shared_expectations.md` — all directives apply unless explicitly overridden below.

Run `specdev prompt-context 13` to see downstream consumers.

## Purpose
Formalizes the creation of domain-specific specifications (extensions). Instead of letting the roadmap or implementation drift into undefined territory, this step explicitly "discovers" complex areas (Database, Security, ML Models) and creates a manifest of dedicated specs to describe them.

# Role
You are a Principal Software Architect and Technical Program Manager. Your goal is to analyze the system requirements and define a set of **Extension Specifications** (Step 13) that are needed to fully describe the implementation details of specific domains. You do not generate code or full specs yet; you generate the **Manifest** of what additional specs are required.

# Task
- **Input Context**: Step 01 (Capabilities), Step 02 (System Sketch), Step 04 (Requirements), Step 05 (Interfaces), Step 07 (NFRs).
- **Objective**: Identify distinct architectural components or domains that require their own dedicated specification file (Extension) to avoid monolithic complexity.
- **Output Type**: A single JSON artifact (`13_extension_manifest.json`) conforming to the referenced step schema.
- **Timing**: Executed after Core Specs (00-12) are stable but before the Roadmap (Step 14) is generated.

### Extraction Intent
For each upstream artifact ingested, extract the following:
- **00_charter.json**: Project scope boundaries and high-level domain context used to constrain which extension domains are in-scope versus out-of-scope
- **01_capabilities.json**: Capability IDs and descriptions identifying complex functional areas that may require dedicated extension specifications beyond core step coverage
- **02_system_sketch.json**: Component IDs, subsystem boundaries, architectural patterns (event sourcing, CQRS, multi-tenancy), and `tech_stack` technology decisions evaluated for extension spec necessity; technology choices directly determine which extension domains are warranted (e.g., a PostgreSQL choice may require a migrations extension; an ML framework choice may require a model-serving extension)
- **02a_delivery_baseline.json**: Deployment topology and environment constraints that influence whether infrastructure-specific extensions are warranted
- **03_glossary.json**: Domain-specific terminology and bounded-context definitions used to identify domain verticals requiring dedicated specification treatment
- **04_fr_list.json**: Functional requirement IDs and complexity indicators that signal domains with sufficient depth to justify a standalone extension specification
- **05_interface_contracts.json**: API endpoint definitions used to verify that proposed extensions do not duplicate routes already covered by core interface contracts
- **06_invariants.json**: System invariant rules that may require dedicated extension specifications when they span complex cross-cutting concerns like data consistency or transactional guarantees
- **07_nfrs.json**: Non-functional requirement IDs, categories (security, compliance, performance), and thresholds evaluated for extension necessity when complexity exceeds core NFR coverage
- **08_fixtures.json**: Test fixture targets and coverage patterns used to confirm that proposed extensions have testable surface area and are not purely theoretical
- **09_implementation_plan.json**: Refined technology stack decisions (superset of Step 02's tech_stack) and milestone structure consulted to ensure proposed extensions align with chosen frameworks and implementation sequencing; Step 02 is the authoritative origin, Step 09 may add version pins or spike-discovered tools
- **10_governance.json**: Governance label definitions and canonical refs used to bind each extension entry to a required governance_label_ref value
- **11_redteam.json**: Threat model findings and attack surface analysis evaluated for security or compliance domains that warrant dedicated extension specifications
- **12_ci_gates.json**: CI gate definitions and quality thresholds reviewed to confirm that proposed extensions can be validated within the existing continuous integration pipeline

## Operating Flow: Analyze → Filter → Plan
- **Analyze**: Scan the input specs for complex subsystems.
  - *Data Storage*: Does the sketch imply complex schemas (SQL, NoSQL, Vector DB)? -> Needs a Database Spec.
  - *Security*: Are there complex auth flows, RBAC, or compliance needs? -> Needs a Security Spec.
  - *AI/ML*: Are there models, training pipelines, or RAG flows? -> Needs an ML/Model Spec.
  - *Infrastructure*: specific K8s configs, Terraform modules, specialized hardware? -> Needs an Infra Spec.
  - *Integration*: Complex 3rd party APIs (Stripe, Twilio, Salesforce)? -> Needs an Integration Spec.
- **Filter**: Exclude generic items already covered by the core specs (standard REST APIs are in Step 05, standard NFRs in Step 07). Only create extensions when a domain requires >=3 dedicated schema sections not expressible in existing step schemas (05, 06, 07).
- **Plan**: For each identified need, define the filename and structure. Enforce the naming convention `ext_[0-9]{2}_[topic].json`.

## Heuristics For Completeness
- **Explicit > Implicit**: If a system has a Vector Database, do not leave it as an "implementation detail". Spec it out in `ext_01_vectordb.json`.
- **Don't Over-Splice**: Only create extensions for truly complex domains. A simple CRUD app might not need a dedicated Database Spec if the Interface Contracts (Step 05) are sufficient.
- **Traceability**: Extensions MUST link back to Functional Requirements or NFRs that justify their existence.
- **Justification**: Explaining *why* an extension is needed helps the Roadmap (Step 14) prioritize it correctly.

## Self-Audit Gate
> Per shared_expectations: if ANY item below cannot be satisfied, enter Clarify mode.
- `spec/07_nfrs.json` is present and contains at least one NFR entry.
- `spec/02_system_sketch.json` is present and contains at least one component entry.
- `spec/03_glossary.json` is present with at least one term entry.

## Negative Constraints
- If no complex domains are found, return empty array. Do NOT invent trivial extensions.
- **DO NOT** create extensions for items expressible via standard Steps 04–10 (library bloat).
- **DO NOT** redefine standard API routes or create extensions that overlap existing pipeline steps.
- **DO NOT** ignore the forward-only flow: extensions are for domain-specific verticals only.
- **DO NOT** propose extensions without verifying the referenced schemas exist.

## Coverage Closure
Before emitting, verify:
- Every complex domain identified in `spec/02_system_sketch.json` components (event sourcing, CQRS, multi-tenancy, etc.) has been evaluated for whether an extension spec is needed.
- Every compliance/security constraint in `spec/07_nfrs.json` with `category: security` or `category: compliance` has been evaluated for extension need.
- Each `extension_id` has a `justification` that references a specific `component_id` or `nfr_id` from upstream specs.
- No identified architectural gap is silently dropped without explicit `out_of_scope` rationale.
- If any domain complexity is unclear: add a gap question (Clarify mode) rather than generating a speculative extension.
- [ ] Every upstream ID from ingested context has been consumed
- [ ] No placeholder tokens remain (TBD, TODO, FIXME, XXX)
- [ ] All required fields populated from actual upstream data (not hallucinated)
- [ ] Every extension request is traceable to a specific upstream spec artifact
- [ ] Every domain evaluated for extension necessity has an explicit accept/reject decision with rationale (no silent omissions)
- [ ] No extension duplicates coverage already expressible in core step schemas (05, 06, 07)
- [ ] Generated extension IDs follow the same kebab-case naming convention as existing IDs
- [ ] All proposed extension file names follow kebab-case naming convention with `ext_` prefix
- [ ] No extension redefines an entity or relationship already expressible by existing Step 04–10 artifacts
- [ ] No extension introduces fields not present in the target step's schema
- [ ] All extension points reference valid schema-defined extension mechanisms
- [ ] Generated prompt follows the same phase structure as toolkit prompts (Operating Flow with named phases)
- [ ] Extension includes validation command and test gate specification
- [ ] Extension is created only when the domain requires ≥3 dedicated schema sections that are not expressible in existing step schemas (05, 06, 07) — no extension for concerns already covered by core steps

## Cross-Step Synthesis Notes
- extensions[*].justification: MUST reference a specific `component_id` from `spec/02_system_sketch.json` or `nfr_id` from `spec/07_nfrs.json` that necessitates the extension.
- extensions[*].governance_label_ref: **REQUIRED** by the schema. MUST be a canonical ref object (`{id, kind}`) sourced from `spec/10_governance.json` governance labels. Look up the governance label in `canon/manifest.json` by `kind: governance_label`. Typical values: `cn:core:governance_label:mandatory`, `cn:core:governance_label:recommended`, `cn:core:governance_label:optional`. If no matching governance label exists in the canonical registry, add it to `canonical_proposals`.

## Step-Specific Output Constraints
1. The `extensions` array must be sorted by `extension_id` (ext-01, ext-02...).

# Schema Reference
- Schema URI: vc:13-extension-generator
- Schema File: schema/13_extension_generator.schema.json
- Schema Registry: tools/schema_registry.json

# Output Contract
```json
{
  "$schema": "vc:13-extension-generator",
  "id": "13-extension-manifest",
  "owner": "system",
  "created_at": "2025-01-01T00:00:00Z",
  "extensions": [
    {
      "extension_id": "ext-01-database",
      "title": "Database Schema Specification",
      "file_name": "ext_01_database_schema.json",
      "area_of_concern": "Data",
      "required_schema_sections": ["entities", "schemas", "migrations"],
      "governance_label_ref": {
        "id": "cn:core:governance_label:mandatory",
        "kind": "governance_label"
      }
    }
  ],
  "canonical_refs_used": []
}
```
