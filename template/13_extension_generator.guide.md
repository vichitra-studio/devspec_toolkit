# 13. Extension Generator

## Purpose
Formalizes the creation of domain-specific specifications (extensions). Instead of letting the roadmap or implementation drift into undefined territory, this step explicitly "discovers" complex areas (Database, Security, ML Models) and creates a manifest of dedicated specs to describe them.

## Template / Fields
- Canonical artifact: **spec/13_extension_manifest.json**
- Schema reference: `schema/13_extension_generator.schema.json` (do not inline schema; rely on `$schema` in JSON artifacts)
- Core atoms: `kebabId`, `owner`, `timestamp`, `tag` (see `schema/core/atoms.schema.json`)
- **Extensions List**:
    - `file_name`: Must follow `13[a-z]_[topic].json`.
    - `required_schema_sections`: Guiding the next step on what to include.

## Prompt File
- Contract: `prompts/prompt_13_extension_generator.md`
- Prompts include context ingestion, operating flow, soft heuristics, and a self‑audit gate. Assistants follow a two‑phase flow:
  - Phase A — Clarify: ingest context and, if gating items are missing, output only a short bulleted list of questions.
  - Phase B — Emit: once clarified, output exactly one fenced ```json``` block that validates against the schema.

## Definition of Ready (DoR) / Guardrails
- **Naming Protocol**: Files must ensure correct sorting order (13a, 13b, ...).
- **Core Verification**: All proposed extensions must have a clear `justification` based on the System Sketch.
- See [Definition of Ready](../docs/templates/definition_of_ready.md) for shared gates.

## Working Increment
See [Shared Template Expectations](../docs/templates/shared_expectations.md#working-increment).

## Checks
See [Shared Template Expectations](../docs/templates/shared_expectations.md#checks).

## Failure Modes
See [Shared Template Expectations](../docs/templates/shared_expectations.md#failure-modes).

## Best Practices
- **Don't Over-Splicing**: Only create extensions for truly complex domains. A simple CRUD app might not need a dedicated Database Spec if the Interface Contracts (Step 05) are sufficient.
- **Traceability**: Extensions should link back to Functional Requirements or NFRs that justify their existence.
- **Justification**: Explaining *why* an extension is needed helps the Roadmap (Step 14) prioritize it correctly.

## Common Pitfalls
- **Creating "Library" Extensions**: Making `13a_logging.json` just to list log levels. Use Step 07 NFRs for that.
- **Redefining Core APIs**: Creating `13b_api.json` that conflicts with `05_interface_contracts.json`.
- **Ignoring Flow**: Extensions are for *deep* verticals (AI, Blockchain, Hardware), not horizontal layers (Frontend, Backend).

## Related Steps
- **Step 02: System Sketch**: The primary source of truth for discovering complex bubbles (Database, AI).
- **Step 07: NFRs**: Constrains the extensions (e.g. "We need a Vector DB because of < 100ms latency NFR").
- **Step 14: Roadmap**: The consumer of the Extension Manifest.
