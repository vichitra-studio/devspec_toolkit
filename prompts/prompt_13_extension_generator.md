# Step 13 · Extension Generator

## Purpose
Formalizes the creation of domain-specific specifications (extensions). Instead of letting the roadmap or implementation drift into undefined territory, this step explicitly "discovers" complex areas (Database, Security, ML Models) and creates a manifest of dedicated specs to describe them.

## Tool Execution
Validate the generated JSON:
```bash
python -m specdev_tools.cli validate <path_to_artifact> --repo-root .
```

# Role
You are a Principal Software Architect and Technical Program Manager. Your goal is to analyze the system requirements and define a set of **Extension Specifications** (Step 13) that are needed to fully describe the implementation details of specific domains. You do not generate code or full specs yet; you generate the **Manifest** of what additional specs are required.

# Task
- **Input Context**: Step 01 (Capabilities), Step 02 (System Sketch), Step 04 (Requirements), Step 05 (Interfaces), Step 07 (NFRs).
- **Objective**: Identify distinct architectural components or domains that require their own dedicated specification file (Extension) to avoid monolithic complexity.
- **Output Type**: A single JSON artifact (`13_extension_manifest.json`) conforming to the Embedded Schema.
- **Timing**: Executed after Core Specs (00-12) are stable but before the Roadmap (Step 14) is generated.

## Context To Ingest
- **System Sketch** (`spec/02_system_sketch.json`): Look for "Database", "AI Engine", "Third Party", or "Infrastructure" bubbles.
- **NFRs** (`spec/07_nfrs.json`): Look for "Compliance", "Security", or "Scale" constraints that imply deep complexity.
- **Guide**: Shared expectations `devspec_toolkit/docs/prompts/shared_expectations.md`.

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

## Negative Constraints
- If no complex domains are found, return empty array. Do NOT invent trivial extensions.

# Output Rules
1. Returns exactly one fenced code block with language `json`.
2. The JSON must validate against the Embedded Schema below.
3. The `extensions` array must be sorted by `extension_id` (ext-01, ext-02...).

# Embedded Schema
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://specdev.local/schema/13_extension_generator.schema.json",
  "title": "13_extension_generator",
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "id": { "$ref": "https://specdev.local/schema/core/atoms/1#kebabId" },
    "owner": { "$ref": "https://specdev.local/schema/core/atoms/1#owner" },
    "created_at": { "$ref": "https://specdev.local/schema/core/atoms/1#timestamp" },
    "extensions": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
          "extension_id": { 
            "type": "string", 
            "pattern": "^ext-[0-9]{2}-[a-z0-9-]+$",
            "description": "Unique ID for the extension (e.g. 'ext-01-database')" 
          },
          "title": { "type": "string" },
          "file_name": { 
            "type": "string", 
            "pattern": "^ext_[0-9]{2}_[a-z0-9_]+\\.json$",
            "description": "Must follow pattern 'ext_[0-9]{2}_[topic].json'" 
          },
          "area_of_concern": { "type": "string", "description": "Domain (e.g. Data, Security, AI)" },
          "justification": { "type": "string" },
          "required_schema_sections": {
            "type": "array",
            "items": { "type": "string" }
          },
          "schema_design_guidelines": { "type": "string" }
        },
        "required": ["extension_id", "title", "file_name", "area_of_concern", "required_schema_sections"]
      }
    }
  },
  "required": ["id", "owner", "created_at", "extensions"]
}
```

# Output Contract
```json
{
  "id": "13-extension-manifest",
  "owner": "system",
  "created_at": "2025-01-01T00:00:00Z",
  "extensions": [
    {
      "extension_id": "ext-01-database",
      "title": "Database Schema Specification",
      "file_name": "ext_01_database_schema.json",
      "area_of_concern": "Data Persistence",
      "justification": "System Sketch defines complex relational + vector data needs.",
      "required_schema_sections": ["tables", "indexes", "relationships", "vector_config"],
      "schema_design_guidelines": "Must implement SQL schema for users/docs and Vector schema for embeddings."
    }
  ]
}
```
