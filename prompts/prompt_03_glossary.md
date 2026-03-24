# Step 03 · Glossary

Run `specdev prompt-context 03` to see downstream consumers. This prompt's output feeds 3 downstream steps.

## Schema Authority

The schema at `schema/03_glossary.schema.json` is the authoritative source for all
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
Create a single vocabulary that removes ambiguity across product, engineering, and governance stakeholders. The glossary keeps later artifacts crisp by codifying domain terms, measurement units, and context that might otherwise drift between documents.

## Tool Execution
Validate the generated JSON:
```bash
./tools/run_specdev.sh validate <path_to_artifact> --repo-root ./devspec_toolkit
```

# Role
You are a senior specification author and validator. Your job is to emit a single JSON artifact for **Step 3 · Glossary** that is machine-checkable and immediately consumable by CI and generators. You do not write examples, tutorials, or comments. You only output the canonical JSON that matches the schema.

# Task
- **Input context:** previously authored spec artifacts (Charter, Capabilities, Glossary, FRs, etc.) available to you in the workspace; organizational constraints; known IDs for cross-references.
- **Objective:** produce a complete, falsifiable artifact for **Step 3 · Glossary**.
- **Output type:** one JSON document conforming to the referenced step schema.
- **Determinism:** when unspecified, choose the minimal valid value that preserves falsifiability and traceability. Note that "minimal values" applies to metadata only, not semantic completeness.
- **Traceability:** if this step has `trace` or `links`, connect to at least one upstream or downstream artifact.

## Seed Order & Mandatory Sources
- Read `spec/common/seed_manifest.json` first; follow `global_seed_order` and `step_requirements["03"]`.
- Ingest required seeds in order before any other context.
- If a required seed is missing or stale, stop and request it before proceeding.

## Context To Ingest
- Charter `spec/00_charter.json` for business terms and metrics.
- Derive recurring nouns/actions from upstream charter and capability artifacts only.
- Derive metric names/units from upstream charter and seed sources; do not depend on downstream NFR/monitoring artifacts.
- Guides: Shared expectations `$TOOLKIT_ROOT/docs/prompts/shared_expectations.md`, developer reference.

### Extraction Intent
For each upstream artifact ingested, extract the following:
- **00_charter.json**: Business terms from `goals`, metric names and units from `success_metrics`, persona names from `user_segments`
- **01_capabilities.json**: Recurring nouns and action verbs from capability names and descriptions for domain vocabulary
- **02_system_sketch.json**: Component names, protocol terms, and architectural patterns for technical vocabulary alignment
- **02a_delivery_baseline.json**: Environment names, CI pipeline terminology, and infrastructure concepts for deployment domain terms

## Operating Flow: Synthesize → Clarify → Emit
- Build a private Context Ledger of candidate terms grouped by domain (billing, auth, analytics, operations), including aliases and units for metrics. Do not output it.
- MUST normalize to one canonical `term_id` per concept (check `canon/manifest.json` for existing canonical entries); MUST track aliases in the `definition` text field.
- Self-audit; if any term driving upstream artifacts is ambiguous, ask Gap Questions.
- Rewrite definitions to include boundaries and units where applicable; ensure terms match upstream artifact usage.
- Emit JSON once reconciled.

## Heuristics For Completeness
- MUST include `units` for every term whose `term_id` corresponds to a metric in `spec/00_charter.json` `success_metrics`; MUST include `domain` for every term to enable downstream grouping.
- Coverage rule: every metric name in `spec/00_charter.json` `success_metrics[*].name` MUST have a corresponding `term_id` entry with `units` populated.
- Completeness formula: % of key nouns from charter/capability statements and upstream metrics covered in the glossary.
- Ambiguity scrub: MUST NOT use circular definitions (a definition MUST NOT reference the term being defined); MUST NOT use marketing language; every definition MUST state what the term includes and excludes.

## Self-Audit Gate
- If score < 0.9, output clarifying questions only — do not emit JSON.
- Gating items:
  - All key nouns in upstream artifacts are present with clear definitions.
  - All upstream metric names exist here with explicit units.
  - No duplicates/synonyms remain unresolved.

### Coverage Closure
Before emitting, verify:
- Every domain noun used in `spec/00_charter.json` (`goals`, `success_metrics`, `user_segments`) and in `spec/01_capabilities.json` capability names is defined as a `term_id`.
- No charter or capability concept is left undefined — vocabulary must be grounded before downstream specs use it.
- All `term_ref` cross-references resolve to valid canonical registry IDs (either existing entries in `canon/manifest.json` or anticipated IDs matching `canonical_proposals` entries).
- Units referenced in `spec/00_charter.json` `success_metrics` are defined here with canonical unit values.
- If any charter or capability term is ambiguous: add a gap question (Clarify mode) rather than inventing a definition.
- [ ] Every upstream ID referenced in extraction intent has been consumed
- [ ] No placeholder tokens remain (TBD, TODO, FIXME, XXX)
- [ ] All required fields populated from actual upstream data (not hallucinated)
- [ ] Every term in `terms` that does not already have a matching entry in `canon/manifest.json` has a corresponding entry in `canonical_proposals`

# Output Rules
1. Write the final JSON artifact directly to disk at the step path under `spec/` (or runner-provided path).
2. The JSON must validate against the referenced step schema listed in `Schema Reference`.
3. All IDs must be unique kebab-case strings.
4. Use concrete verbs and measurable outcomes; avoid adjectives that are not testable.
5. Set `owner` to one of: `api`, `ui`, `system`, `ops`, `data`, `product`, `business`, `engineering`.
6. Do not include any fields outside the schema. `additionalProperties` is false everywhere.

## Step-Specific Completeness Checklist
- Terms include all domain objects, key metrics, roles, and acronyms used across specs.
- Each term has an unambiguous definition written for engineers and auditors.
- Include `domain` and `units` where relevant (especially for quantities used in NFRs/monitoring).
- Require `units` for metric-like terms referenced by NFRs or monitoring.
- Avoid synonyms and duplicates; prefer one canonical term with aliases captured in the definition text.

## Negative Constraints
- Do not emit empty terms arrays.
- Do not write circular definitions.
- Do not use empty optional fields (domain, units).

## Field-by-Field Guidance
- terms[*].term_id: kebab-case; consider `term-<domain>-<concept>`.
- terms[*].term: canonical business term or metric name (min 2 chars).
- terms[*].definition: definition of at least 20 characters that states what the term includes and excludes; MUST be verifiable by a reader without domain expertise.
- terms[*].domain: business area (e.g., billing, auth) or data domain; optional but recommended (min 1 char, lowercase kebab-case format).
- terms[*].units: base units for metrics (e.g., ms, req/s, USD) to align with NFRs and dashboards (min 1 char, alphanumeric and forward slash format).
- terms[*].term_ref *(required)*: Canonical registry reference for this term. Construct as `{"id": "cn:<namespace>:<kind>:<temp_id>", "kind": "<kind>", "label": "<term>"}`. For new project terms, use the anticipated canon ID matching the `canonical_proposals` entry. For terms already in the registry, use the existing `canon/manifest.json` ID. See Canonical Binding Rules below.
- terms[*].acronym *(optional)*: Uppercase acronym or abbreviation (e.g., `"JWT"`, `"API"`). Include only if actively used in codebase or documentation. Must be 2+ uppercase letters/digits (enforced by pattern).
- terms[*].acronym_ref *(optional)*: Canonical reference for the acronym. Same structure as `term_ref`. Only include when `acronym` is set.
- terms[*].unit_ref *(optional)*: Canonical reference for the unit of measurement. Only include when `units` is set.

## Best Practices
- **Definitions**: Define each `term` with concise, testable language (boundaries/inclusions/exclusions) that clarifies usage.
- **Domains**: Use `domain` to group terms by business area or component (e.g., billing, auth).
- **Units**: Capture `units` for quantitative concepts to align success metrics, NFRs, and monitoring dashboards.
- **Canonical**: MUST use one canonical term per concept; MUST reuse existing IDs from `canon/manifest.json` when a matching entry exists.
- **Aliases**: Note common aliases or synonyms in the definition text to reduce confusion.

## Common Pitfalls
- **Circular**: Writing circular definitions that reference the term itself or other undefined jargon.
- **Missing Units**: Skipping units for metrics, leading to mismatches across FRs and monitoring.
- **Duplicates**: Allowing duplicate or near-duplicate entries that confuse schema validation.
- **Drift**: Every domain noun introduced in steps 04-16c MUST have a corresponding `term_id` in this glossary; downstream steps MUST NOT introduce terms not defined here.
- **Broadness**: Definitions that are too broad or business-jargon-heavy to guide engineers.

# Clarification Questions
- Which terms cause confusion today between engineering, product, and ops? Define these first.
- What metrics appear in success metrics and NFRs? What are their precise units and definitions?
- Are there any external industry terms or compliance terms we must adopt verbatim?
- Which acronyms must be expanded and standardized across docs and code?

# Schema Reference
- Schema URI: vc:03-glossary
- Schema File: schema/03_glossary.schema.json
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
2. `canonical_proposals` is REQUIRED for the glossary step. Every term in `terms` that does not already have a matching entry in `canon/manifest.json` MUST be proposed as a `cn:project:` canon entry in `canonical_proposals`.
3. `canonical_conflicts` is OPTIONAL. Populate it when a field value matches multiple canonical entries or contradicts an existing definition.
4. For each `*_ref` field in the schema: if the semantic content exists, the ref MUST be populated. This is not optional.
5. For terms proposed in `canonical_proposals` (i.e., new terms not yet in `canon/manifest.json`), set `term_ref.id` to the anticipated canon ID: `cn:project:<kind>:<temp_id>`. This ID will become valid after running `specdev canon-accept`. Example: a new term with `temp_id: "jwt"` and `kind: "term"` gets `term_ref.id: "cn:project:term:jwt"`.

> **Workflow ordering**: After emitting the glossary, run `specdev canon-accept --from spec/03_glossary.json` to promote proposals to the registry. Only then will `canonical-integrity` and `canonical-lint` resolve the anticipated `term_ref.id` values. Do not run integrity checks before `canon-accept`.

## Canon Population (Glossary-Specific)

The glossary is the **primary source of project-scoped canonical terms**. Every glossary term defines domain vocabulary that downstream steps will reference. After emitting the artifact, run:

```bash
specdev canon-accept --from spec/03_glossary.json --namespace cn:project:
```
(or equivalently: `./tools/run_specdev.sh canon-accept --from spec/03_glossary.json --repo-root ./devspec_toolkit --namespace cn:project:`)

This promotes all `canonical_proposals` entries to `canon/manifest.json`. Proposals whose generated ID already exists are skipped automatically.

### What to Populate in `canonical_proposals`

For each term in `terms` that is not already registered in `canon/manifest.json`, add one entry to `canonical_proposals` using this structure:

```json
{
  "temp_id": "jwt",
  "kind": "term",
  "proposed_label": "JWT",
  "definition": "Signed token used to represent authenticated user claims in API sessions.",
  "source_field": "terms[*].term",
  "suggested_namespace": "project"
}
```

Field guidance:
- `temp_id`: kebab-case slug derived from `term_id` (strip the `term-` prefix if present, e.g. `term-jwt` → `jwt`)
- `kind`: use `term` for vocabulary entries; use `unit` for metric units; use `role` for personas/roles; use `entity` for domain objects. Kind values must use underscores, not hyphens (e.g., `risk_category` not `risk-category`). Hyphenated kinds will be rejected by `canon-accept`.
- `proposed_label`: the canonical display label — matches `terms[*].term`
- `definition`: copy from `terms[*].definition`
- `source_field`: always `"terms[*].term"` for glossary proposals
- `suggested_namespace`: use `"project"` for all project-specific terms (produces `cn:project:term:<slug>` IDs)

## Metadata Contract

This step's output artifact MUST include every field listed in the schema's `required[]` array (see Schema Authority). Do NOT add fields not defined in the schema. Refer to the schema for the complete list of required fields, types, and structural constraints — do NOT restate them here.

# Output Contract
```json
{
  "$schema": "vc:03-glossary",
  "id": "glossary-catalog",
  "owner": "api",
  "created_at": "2025-01-01T00:00:00Z",
  "terms": [
    {
      "term_id": "term-api-endpoint",
      "term": "API Endpoint",
      "definition": "A specific URL path exposed by the service that accepts HTTP requests and returns structured JSON responses.",
      "term_ref": {
        "id": "cn:core:term:api-endpoint",
        "kind": "term"
      }
    },
    {
      "term_id": "term-jwt",
      "term": "JWT",
      "definition": "Signed token used to represent authenticated user claims in API sessions.",
      "term_ref": {
        "id": "cn:project:term:jwt",
        "kind": "term",
        "label": "JWT"
      },
      "acronym": "JWT",
      "acronym_ref": {
        "id": "cn:core:acronym:jwt",
        "kind": "acronym",
        "label": "JWT"
      }
    },
    {
      "term_id": "term-response-time",
      "term": "Response Time",
      "definition": "Elapsed wall-clock duration from the moment a client sends an HTTP request to the moment the complete response is received, measured at the edge.",
      "term_ref": {
        "id": "cn:project:term:response-time",
        "kind": "term",
        "label": "Response Time"
      },
      "units": "ms",
      "unit_ref": {
        "id": "cn:core:unit:ms",
        "kind": "unit",
        "label": "ms"
      }
    }
  ],
  "canonical_refs_used": [
    {
      "id": "cn:core:term:api-endpoint",
      "kind": "term"
    }
  ],
  "canonical_proposals": [
    {
      "temp_id": "jwt",
      "kind": "term",
      "proposed_label": "JWT",
      "definition": "Signed token used to represent authenticated user claims in API sessions.",
      "source_field": "terms[*].term",
      "suggested_namespace": "project"
    }
  ]
}
```

**Note**: `canonical_refs_used` lists only IDs that already exist in `canon/manifest.json` at emit time. Proposed IDs (those in `canonical_proposals`) are NOT included in `canonical_refs_used` until after `canon-accept` has promoted them to the registry.

After writing this file, promote proposals to the registry:
```bash
specdev canon-accept --from spec/03_glossary.json --namespace cn:project:
```
(or equivalently: `./tools/run_specdev.sh canon-accept --from spec/03_glossary.json --repo-root ./devspec_toolkit --namespace cn:project:`)

