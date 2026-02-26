# Step 03 · Glossary

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
- Populate `seed_refs` with the seeds actually used.
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

## Operating Flow: Synthesize → Clarify → Emit
- Build a private Context Ledger of candidate terms grouped by domain (billing, auth, analytics, operations), including aliases and units for metrics. Do not output it.
- Normalize to a canonical term per concept; track aliases in the definition text.
- Self-audit; if any term driving upstream artifacts is ambiguous, ask Gap Questions.
- Rewrite definitions to include boundaries and units where applicable; ensure terms match upstream artifact usage.
- Emit JSON once reconciled.

## Heuristics For Completeness
- Optional→expected: include `units` for any metric-like term; include `domain` to aid grouping.
- Coverage hint: ensure every upstream metric appears here with unit definitions.
- Completeness formula: % of key nouns from charter/capability statements and upstream metrics covered in the glossary.
- Ambiguity scrub: avoid circular or marketing language; specify inclusions/exclusions.

## Self-Audit Gate
- If `generation_quality.preflight_passed` cannot be set to `true` with current evidence, stop and ask targeted questions.
- Gating items:
  - All key nouns in upstream artifacts are present with clear definitions.
  - All upstream metric names exist here with explicit units.
  - No duplicates/synonyms remain unresolved.


### Coverage Closure
Before emitting, verify:
- Every domain noun used in `spec/00_charter.json` (`goals`, `success_metrics`, `user_segments`) and in `spec/01_capabilities.json` capability names is defined as a `term_id`.
- No charter or capability concept is left undefined — vocabulary must be grounded before downstream specs use it.
- All `term_ref` cross-references within this glossary resolve to other `term_id` values defined in this artifact.
- Units referenced in `spec/00_charter.json` `success_metrics` are defined here with canonical unit values.
- If any charter or capability term is ambiguous: add a gap question (Clarify mode) rather than inventing a definition.
- [ ] Every upstream ID referenced in extraction intent has been consumed
- [ ] No placeholder tokens remain (TBD, TODO, FIXME, XXX)
- [ ] All required fields populated from actual upstream data (not hallucinated)
- [ ] `seed_refs` only contains seeds actually referenced in the output

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
- terms[*].definition: concise, testable definition (min 20 chars); state inclusions/exclusions.
- terms[*].domain: business area (e.g., billing, auth) or data domain; optional but recommended (min 1 char, lowercase kebab-case format).
- terms[*].units: base units for metrics (e.g., ms, req/s, USD) to align with NFRs and dashboards (min 1 char, alphanumeric and forward slash format).

## Best Practices
- **Definitions**: Define each `term` with concise, testable language (boundaries/inclusions/exclusions) that clarifies usage.
- **Domains**: Use `domain` to group terms by business area or component (e.g., billing, auth).
- **Units**: Capture `units` for quantitative concepts to align success metrics, NFRs, and monitoring dashboards.
- **Canonical**: Prefer one canonical term; reuse or link existing IDs where possible.
- **Aliases**: Note common aliases or synonyms in the definition text to reduce confusion.

## Common Pitfalls
- **Circular**: Writing circular definitions that reference the term itself or other undefined jargon.
- **Missing Units**: Skipping units for metrics, leading to mismatches across FRs and monitoring.
- **Duplicates**: Allowing duplicate or near-duplicate entries that confuse schema validation.
- **Drift**: Treating glossary updates as optional, letting new terms leak into later steps without definitions.
- **Broadness**: Definitions that are too broad or business-jargon-heavy to guide engineers.

## Quick Reference
- Required: `term_id`, `term`, `definition`.
- Optional but recommended: `domain`, `units`.

# Clarification Questions
- Which terms cause confusion today between engineering, product, and ops? Define these first.
- What metrics appear in success metrics and NFRs? What are their precise units and definitions?
- Are there any external industry terms or compliance terms we must adopt verbatim?
- Which acronyms must be expanded and standardized across docs and code?

# Schema Reference
- Schema URI: https://specdev.local/schema/03_glossary.schema.json
- Schema File: schema/03_glossary.schema.json
- Schema Registry: tools/schema_registry.json

## Hardening Protocol
- fail-closed preflight: verify required fields, allowed enums, referenced IDs, and command/tool existence before emitting JSON.
- No-Invention Rules: do not invent IDs, enums, commands, files, metrics, stages, or canonical mappings that are not grounded in provided inputs.
- Completeness Closure: run a final closure pass to confirm required sections, trace/canonical closure, and seed coverage are complete.
- blocker report: if required inputs are missing, conflicting, or ambiguous after clarification, stop and return a blocker report instead of speculative output.

# Output Contract
```json
{
  "id": "glossary-catalog",
  "owner": "api",
  "created_at": "2025-01-01T00:00:00Z",
  "seed_refs": [
    {
      "seed_id": "seed-overview"
    }
  ],
  "spec_refs_ingested": [],
  "terms": [
    {
      "term_id": "term-jwt",
      "term": "JWT",
      "definition": "Signed token used to represent authenticated user claims in API sessions.",
      "term_ref": {
        "id": "cn:core:term:example",
        "kind": "term"
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
      "id": "cn:core:term:example",
      "kind": "term"
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
