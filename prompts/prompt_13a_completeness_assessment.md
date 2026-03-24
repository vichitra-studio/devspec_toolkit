# Step 13a · Completeness Assessment

> **Inherits**: `$TOOLKIT_ROOT/docs/prompts/shared_expectations.md` — all directives apply unless explicitly overridden below.

Run `specdev prompt-context 13a` to see downstream consumers.

## Purpose
Assess the completeness of Phase 1 specifications and identify gaps that prevent achieving perfect system implementation readiness. This step evaluates the current specification state against ideal completeness criteria and generates actionable recommendations for improvement.

## Tool Execution
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
- **Output type:** one JSON document conforming to the referenced step schema.
- **Traceability:** connect findings to specific spec files and elements.

## Logic Update
- **MANDATORY INGESTION**: Read `13_extension_manifest.json` to verify all extensions are implemented.
- **Scoring Rule**: If a Manifest Extension is missing, deduct 1.0 points. Do NOT rate 10/10.
- **Rubric**: Add explicit deduction rubric (Missing API=-1.0, Missing NFR=-0.5).

### Extraction Intent
For each upstream artifact ingested, extract the following:
- **00_charter.json**: Project scope, stakeholders, and success criteria used as the baseline against which completeness of all downstream specs is measured
- **01_capabilities.json**: Capability IDs and definitions verified for full coverage in downstream FRs, APIs, and implementation plan milestones
- **02_system_sketch.json**: Component IDs and architectural topology checked for traceability into interface contracts, scaffold modules, and implementation plan coverage
- **02a_delivery_baseline.json**: Deployment environment definitions and infrastructure constraints verified for presence and consistency in NFRs and CI gate configurations
- **03_glossary.json**: Domain term definitions audited for completeness (no empty definitions, no TBDs) and consistent usage across all downstream specification artifacts
- **04_fr_list.json**: Functional requirement IDs checked for forward traceability into APIs, fixtures, and implementation plan tasks to identify orphaned or unimplemented requirements
- **05_interface_contracts.json**: API endpoint definitions verified for bidirectional traceability with functional requirements and fixture coverage to detect missing contract bindings
- **06_invariants.json**: System invariant rules verified for traceability to functional requirements and presence of corresponding fixture test coverage
- **07_nfrs.json**: Non-functional requirement IDs, thresholds, and categories checked for concrete measurable values (no vague descriptors) and traceability to implementation plan tasks
- **08_fixtures.json**: Test fixture target IDs and coverage mappings verified for completeness against all FRs, APIs, and invariants to identify untested specification elements
- **09_implementation_plan.json**: Technology stack entries verified for strict version strings and rationale fields; milestones checked for complete deliverable mappings and dependency coherence
- **10_governance.json**: Governance rules and commit conventions verified for completeness and consistency with the CI gate enforcement definitions
- **11_redteam.json**: Threat model entries verified for structured mitigations and traceability to specific API or component targets in upstream specifications
- **12_ci_gates.json**: CI gate definitions verified for coverage of all quality dimensions (lint, test, security, schema validation) and alignment with governance rules
- **13_extension_generator.json**: Extension manifest entries verified for physical file existence on disk and completeness of required schema sections and governance label bindings

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
- Gating items:
  - Can read at least 00, 01, 04, 05.
  - Identification of at least one missing element OR confirmation of 100% completeness.
  - Ratings provided for current implementation state.
- **Extension Check**: Ensure all extensions in manifest are present.

### Coverage Closure
Before emitting, verify:
- Every `extension_id` in `spec/13_extension_manifest.json` is either implemented (corresponding step spec artifact exists) or listed as a `missing_element` with impact assessment.
- Every `missing_element` has a `specification_source` that traces back to the originating artifact (e.g., `spec/07_nfrs.json`, `spec/02_system_sketch.json`).
- All specs 00–12 have been evaluated for completeness — no step is skipped in the assessment.
- No extension is marked complete without evidence of the corresponding spec file existing on disk.
- If any spec file is absent and its absence is ambiguous (skipped vs. not-yet-written): add a gap question (Clarify mode) rather than assuming completion.
- [ ] Every upstream ID from ingested context has been consumed
- [ ] No placeholder tokens remain (TBD, TODO, FIXME, XXX)
- [ ] All required fields populated from actual upstream data (not hallucinated)
- [ ] Every `uncovered_ids` entry references a real ID from the referenced upstream spec
- [ ] All coverage dimensions (FR→API, FR→fixture, capability→FR) have been assessed
- [ ] Coverage ratios are derived from actual spec content counts — not estimated or guessed
- [ ] All `uncovered_ids` reference valid IDs from their respective upstream spec files
- [ ] All four pairwise transitions (capability→FR, FR→API, FR→fixture, FR→milestone) are assessed — no transition silently skipped
- [ ] The completeness_rating reflects accumulated numeric deductions from the scoring rubric — not a subjective estimate
- [ ] Every uncovered_id identified in pairwise checks appears in at least one gap or finding in this assessment

## Negative Constraints
- **DO NOT** rate completeness as 10/10 if any "TBD" values exist.
- **DO NOT** omit impact scores for missing elements; prioritization depends on them.
- **DO NOT** ignore missing extensions; if they are in the manifest, they must be on disk.
- **DO NOT** evaluate files that are not part of the standard set (00-15 + extensions).

## Cross-Step Synthesis Notes
- missing_elements.priority: `high` = blocks implementation, `medium` = risk, `low` = debt.
- missing_elements.impact_on_completeness: numeric deduction from 0.1 to 1.0 per missing element (e.g., Missing API=-1.0, Missing NFR=-0.5).
- missing_elements.specification_source: array of filenames tracing the gap back to its origin (e.g. `04_fr_list.json`, `13_extension_manifest.json`).

## Step-Specific Output Constraints
1. `completeness_rating.target` MUST be 10.
2. `missing_elements` must list specific gaps, not general complaints.

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

# Clarification Questions
- Are there specific files excluded from this review?
- Is there a known reason for missing headers/sections (e.g. omitted by design)?
- Who is the primary audience for this assessment?

# Schema Reference
- Schema URI: vc:13a-completeness-assessment
- Schema File: schema/13a_completeness_assessment.schema.json
- Schema Registry: tools/schema_registry.json

# Output Contract
```json
{
  "$schema": "vc:13a-completeness-assessment",
  "id": "assessment-20250101",
  "owner": "system",
  "created_at": "2025-01-01T12:00:00Z",
  "missing_elements": [],
  "completeness_rating": {
    "current": 10,
    "target": 10,
    "confidence_level": 1.0
  },
  "canonical_refs_used": []
}
```
