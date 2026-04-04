# Step 03 · Glossary

> **REQUIRED**: Before starting, read `$TOOLKIT_ROOT/docs/prompts/shared_expectations.md` in full. All directives in that document apply to this step unless explicitly overridden below. Do not proceed without reading it.

Run `specdev prompt-context 03` to see downstream consumers. This prompt's output feeds 3 downstream steps.

## Role
You are a **senior domain modeler and terminology specialist**. Your job is to emit a single JSON artifact for **Step 03 · Glossary** that establishes a canonical, conflict-free domain vocabulary traceable to the project charter. You do not write examples, tutorials, or comments. You only output the canonical JSON that matches the schema.

## Purpose
Create a single vocabulary that removes ambiguity across product, engineering, and governance stakeholders. The glossary keeps later artifacts crisp by codifying domain terms, measurement units, and context that might otherwise drift between documents.

## Extraction Intent

For each upstream artifact ingested, extract the following:
- **00_charter.json**: Business terms from `goals`, metric names and units from `success_metrics`, persona names from `user_segments`; derive metric names/units from charter and seed sources — do not depend on downstream NFR/monitoring artifacts
- **01_capabilities.json**: Recurring nouns and action verbs from capability names and descriptions for domain vocabulary
- **02_system_sketch.json**: Component names, protocol terms, architectural patterns, and technology names from `tech_stack` (languages, frameworks, infrastructure, tools) for technical vocabulary alignment; technology names are domain terms that downstream specs will reference
- **02a_delivery_baseline.json**: Environment names, CI pipeline terminology, and infrastructure concepts for deployment domain terms

## Operating Flow: Collect → Define → Canonicalize → Emit

- **Collect**: Build a private Context Ledger of candidate terms grouped by domain (billing, auth, analytics, operations), including aliases and units for metrics. Do not output it.
- **Define**: Rewrite definitions to include boundaries and units where applicable; ensure terms match upstream artifact usage.
- **Canonicalize**: MUST normalize to one canonical `term_id` per concept (check `canon/manifest.json` for existing canonical entries); MUST track aliases in the `definition` text field. Self-audit; if any term driving upstream artifacts is ambiguous, ask Gap Questions.
- **Emit**: Write artifact JSON once all terms are reconciled and canonical proposals are prepared.

## Heuristics For Completeness
- MUST include `units` for every term whose `term_id` corresponds to a metric in `spec/00_charter.json` `success_metrics`; MUST include `domain` for every term to enable downstream grouping.
- Coverage rule: every metric name in `spec/00_charter.json` `success_metrics[*].name` MUST have a corresponding `term_id` entry with `units` populated.
- Completeness formula: % of key nouns from charter/capability statements and upstream metrics covered in the glossary.
- Ambiguity scrub: MUST NOT use circular definitions (a definition MUST NOT reference the term being defined); MUST NOT use marketing language; every definition MUST state what the term includes and excludes.

## Self-Audit Gate
> Per shared_expectations: if ANY item below cannot be satisfied, enter Clarify mode.
- `spec/00_charter.json` is present and contains at least one user_segments entry.
- `spec/01_capabilities.json` is present and contains at least one capability entry.
- `spec/02_system_sketch.json` is present and contains at least one component entry.

## Negative Constraints
- Do not emit empty terms arrays.
- Do not write circular definitions.
- Do not use empty optional fields (domain, units).

## Coverage Closure
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
- [ ] Every domain entity referenced in the project charter has a glossary entry
- [ ] No two terms have overlapping or conflicting definitions
- [ ] Every term with a lifecycle has its valid stages explicitly enumerated
- [ ] Every domain term used in charter, capabilities, and system sketch is defined here
- [ ] No circular definitions (A defined using B, B defined using A without resolution)
- [ ] Every term with a matching canonical entry has `canonical_ref` populated

## Step-Specific Completeness Checklist
- Terms include all domain objects, key metrics, roles, and acronyms used across specs.
- Each term has an unambiguous definition written for engineers and auditors.
- Include `domain` and `units` where relevant (especially for quantities used in NFRs/monitoring).
- Require `units` for metric-like terms referenced by NFRs or monitoring.
- Avoid synonyms and duplicates; prefer one canonical term with aliases captured in the definition text.

## Cross-Step Synthesis Notes
- terms[*].term_ref *(required)*: Canonical registry reference for this term. Construct as `{"id": "cn:<namespace>:<kind>:<temp_id>", "kind": "<kind>", "label": "<term>"}`. For new project terms, use the anticipated canon ID matching the `canonical_proposals` entry. For terms already in the registry, use the existing `canon/manifest.json` ID. See Canonical Binding Rules below.

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
      "domain": "api",
      "term_ref": {
        "id": "cn:core:term:api-endpoint",
        "kind": "term"
      }
    },
    {
      "term_id": "term-response-time",
      "term": "Response Time",
      "definition": "Elapsed wall-clock duration from the moment a client sends an HTTP request to the moment the complete response is received, measured at the edge.",
      "domain": "api",
      "units": "ms",
      "term_ref": {
        "id": "cn:project:term:response-time",
        "kind": "term",
        "label": "Response Time"
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
      "temp_id": "response-time",
      "kind": "term",
      "proposed_label": "Response Time",
      "definition": "Elapsed wall-clock duration from the moment a client sends an HTTP request to the moment the complete response is received, measured at the edge.",
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

