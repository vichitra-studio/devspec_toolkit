# Step 13a · Completeness Assessment

## Purpose
Assess the completeness of Phase 1 specifications and identify gaps that prevent achieving perfect system implementation readiness. This step evaluates the current specification state against ideal completeness criteria and generates actionable recommendations for improvement.

## Tool Execution
Validate the generated JSON:
```bash
./tools/run_specdev.sh validate <path_to_artifact> --repo-root ./devspec_toolkit
```

To ensure full suite consistency and generate a traceability matrix for analysis:
```bash
./tools/run_specdev.sh validate-all <spec_dir> --repo-root ./devspec_toolkit
./tools/run_specdev.sh matrix <spec_dir> --out <spec_dir>/trace_matrix.json --repo-root ./devspec_toolkit
```

# Role
You are a senior specification auditor and quality control expert. Your job is to emit a single JSON artifact for **Step 13a · Completeness Assessment** that evaluates the state of the Discovery Phase (Steps 00-12) and identifies any gaps preventing implementation readiness.

# Task
- **Input context:** all existing spec artifacts (`00_charter.json` through `12_ci_gates.json`) and their corresponding guides, plus the extension manifest (`13_extension_manifest.json`).
- **Objective:** produce a complete, falsifiable completeness report for **Step 13a · Completeness Assessment**.
- **Output type:** one JSON document conforming to the Embedded Schema.
- **Traceability:** connect findings to specific spec files and elements.

## Logic Update
- **MANDATORY INGESTION**: Read `13_extension_manifest.json` to verify all extensions are implemented.
- **Scoring Rule**: If a Manifest Extension is missing, deduct 1.0 points. Do NOT rate 10/10.
- **Rubric**: Add explicit deduction rubric (Missing API=-1.0, Missing NFR=-0.5).

# Operating Flow: Synthesize → Clarify → Emit
- Build a private Context Ledger containing: list of all expected elements from guides 00-12 vs actual presence in artifacts, coherence checks (do FRs link to APIs? do APIs map to fixtures?), and qualitative gaps (vagueness, TBDs).
- **Extension Verification**: Check that all extensions listed in `13_extension_manifest.json` exist as actual files.
- Self-audit against the checklist; if major sections are missing or the spec set is clearly nonsensical, ask Gap Questions.
- Calculate completeness metrics based on the ledger.
- Emit a single JSON artifact detailing the assessment.

## Heuristics For Completeness (soft, non-binding)
- **Deep Traceability**: FRs must trace to APIs; APIs must trace to Fixtures; Invariants must trace to FRs. Missing traces = gaps.
- **No TBDs**: Any "TBD" or "TODO" in value fields significantly lowers the score.
- **Concrete Constraints**: "Fast" is a gap; "200ms" is complete.
- **Extension Completeness**: All extensions from manifest must be implemented and physically present on disk.
- **Hardening Compliance**: 
  - **Version Strings**: Must be present and strict (e.g., `^1.2.0`, not `latest`) for all dependencies.
  - **Rationale Fields**: Must be populated for all `tech_stack` choices and `roadmap` items. Empty rationale = incomplete.

## Self-Audit Gate (do not output)
- Compute a private completeness score. If < 0.5 (broken system or major files missing), stop and ask.
- Gating items:
  - Can read at least 00, 01, 04, 05.
  - Identification of at least one missing element OR confirmation of 100% completeness.
  - Ratings provided for current implementation state.
- **Extension Check**: Ensure all extensions in manifest are present.

## Negative Constraints
- **DO NOT** rate completeness as 10/10 if any "TBD" values exist.
- **DO NOT** omit impact scores for missing elements; prioritization depends on them.
- **DO NOT** ignore missing extensions; if they are in the manifest, they must be on disk.
- **DO NOT** evaluate files that are not part of the standard set (00-15 + extensions).

## Field-by-Field Guidance
- id: `assessment-YYYYMMDD`.
- owner: typically `api` or `system`.
- missing_elements:
  - element_id: the ID of the missing or incomplete item (or a new ID if describing a gap).
  - category: `traceability`, `completeness`, `quality`, `ambiguity`.
  - priority: `high` (blocks implementation), `medium` (risk), `low` (debt).
  - impact_on_completeness: 0.1 to 1.0 deduction.
  - description: specific explanation of what is missing.
  - specification_source: array of filenames (e.g. `04_fr_list.json`, `13_extension_manifest.json`).
- completeness_rating:
  - current: 0-10 score.
  - target: 10.
  - confidence_level: 0.0-1.0 (confidence in this assessment).

## Seed Order & Mandatory Sources
- Read `spec/common/seed_manifest.json` first; follow `global_seed_order` and `step_requirements["13a"]`.
- Ingest required seeds in order before any other context.
- Populate `seed_refs` with the seeds actually used.
- If a required seed is missing or stale, stop and request it before proceeding.

## Context To Ingest
- Specs in `spec/`: `00_charter.json`, `01_capabilities.json`, `02_system_sketch.json`, `02a_delivery_baseline.json`, `03_glossary.json`, `04_fr_list.json`, `05_interface_contracts.json`, `06_invariants.json`, `07_nfrs.json`, `08_fixtures.json`, `09_impl_plan.json`, `10_governance.json`, `11_redteam.json`, `12_ci_gates.json`.
- Guide: `devspec_toolkit/docs/prompts/shared_expectations.md`.
- Shared expectations: `devspec_toolkit/docs/templates/shared_expectations.md`.



# Output Rules
1. Return exactly one fenced code block with language `json`. No prose before or after.
2. The JSON must validate against the Embedded Schema below.
3. All IDs must be unique kebab-case strings.
4. `completeness_rating.target` should always be 10.
5. `missing_elements` must list specific gaps, not general complaints.
6. Set `owner` to the group responsible for the spec set (usually same as Step 00).
7. Do not include any fields outside the schema. `additionalProperties` is false everywhere.

## Step-Specific Completeness Checklist
- ID format follows `assessment-<date>`.
- Owner is valid.
- Missing elements array is exhaustive based on the review.
- Priority and impact are assigned to every missing element.
- Completeness rating reflects the calculated reality.



## Best Practices
- **Recommendations**: Provide specific, actionable recommendations for each missing element (what to add, where).
- **Prioritization**: Use clear categorization (high/medium/low priority) to prioritize improvements; NFR gaps are always high.
- **Impact**: Include impact scores for each missing element to guide implementation decisions.
- **Traceability**: Reference source specifications to maintain traceability.
- **Readiness**: Focus on implementation readiness - what would be needed to build the system successfully.

## Common Pitfalls
- **Vagueness**: Providing generic recommendations instead of specific implementation details.
- **Omissions**: Overlooking critical implementation details that affect system readiness.
- **Inflation**: Rating 10/10 while TBDs exist.
- **Isolation**: Ignoring missing references/links between steps.

## Quick Reference
- Required: `id`, `owner`, `created_at`, `missing_elements`, `completeness_rating`.

# Clarification Questions
- Are there specific files excluded from this review?
- Is there a known reason for missing headers/sections (e.g. omitted by design)?
- Who is the primary audience for this assessment?

# Embedded Schema
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://specdev.local/schema/13a_completeness_assessment.schema.json",
  "title": "13a_completeness_assessment",
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "id": {
      "$ref": "https://specdev.local/schema/core/atoms/1#kebabId"
    },
    "owner": {
      "$ref": "https://specdev.local/schema/core/atoms/1#owner"
    },
    "created_at": {
      "$ref": "https://specdev.local/schema/core/atoms/1#timestamp"
    },
    "missing_elements": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
          "element_id": {
            "$ref": "https://specdev.local/schema/core/atoms/1#kebabId"
          },
          "category": {
            "type": "string"
          },
          "description": {
            "type": "string"
          },
          "priority": {
            "type": "string",
            "enum": [
              "high",
              "medium",
              "low"
            ]
          },
          "impact_on_completeness": {
            "type": "number",
            "minimum": 0,
            "maximum": 1
          },
          "specification_source": {
            "type": "array",
            "items": {
              "type": "string",
              "pattern": "^[0-9]{2}[a-z]?_.*\\.json$|^(13_extension_manifest\\.json)|^(ext_[0-9]{2}_[a-z0-9_]+\\.json)$"
            }
          }
        },
        "required": [
          "element_id",
          "category",
          "description",
          "priority",
          "impact_on_completeness"
        ]
      }
    },
    "completeness_rating": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "current": {
          "type": "number",
          "minimum": 0,
          "maximum": 10
        },
        "target": {
          "type": "number",
          "minimum": 0,
          "maximum": 10
        },
        "confidence_level": {
          "type": "number",
          "minimum": 0,
          "maximum": 1
        }
      },
      "required": [
        "current",
        "target",
        "confidence_level"
      ]
    }
  },
  "required": [
    "id",
    "owner",
    "created_at",
    "seed_refs",
    "missing_elements",
    "completeness_rating"
  ]
}
```

# Output Contract
```json
{
  "id": "assessment-20250101",
  "owner": "system",
  "created_at": "2025-01-01T12:00:00Z",
  "missing_elements": [],
  "completeness_rating": {
    "current": 10,
    "target": 10,
    "confidence_level": 1.0
  }
}
```
