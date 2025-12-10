# 13a. Completeness Assessment

## Purpose
Assess the completeness of Phase 1 specifications and identify gaps that prevent achieving perfect system implementation readiness. This step evaluates the current specification state against ideal completeness criteria and generates actionable recommendations for improvement.

## Template / Fields
- Canonical artifact: **spec/13a_completeness_assessment.json**
- Schema reference: `schema/13a_completeness_assessment.schema.json` (do not inline schema; rely on `$schema` in JSON artifacts)
- Core atoms: `kebabId`, `owner`, `timestamp`, `tag` (see `schema/core/atoms/1#atoms.schema.json`)
- Core collections: `kebabIdArray`, `stringArray`, `link`, `traceRef`, `errorState`, `anyJson` (see `schema/core/collections/1#collections.schema.json`)

## Prompt File
- Contract: `prompts/prompt_13a_completeness_assessment.md`
- Prompts include context ingestion, operating flow, soft heuristics, and a self‑audit gate. Assistants follow a two‑phase flow:
  - Phase A — Clarify: ingest context and, if gating items are missing, output only a short bulleted list of questions.
  - Phase B — Emit: once clarified, output exactly one fenced ```json``` block that validates against the schema.

## Definition of Ready (DoR) / Guardrails
See [Shared Template Expectations](../docs/templates/shared_expectations.md#definition-of-ready-dor-guardrails).

## Working Increment
See [Shared Template Expectations](../docs/templates/shared_expectations.md#working-increment).

## Checks
See [Shared Template Expectations](../docs/templates/shared_expectations.md#checks).

## Failure Modes
See [Shared Template Expectations](../docs/templates/shared_expectations.md#failure-modes).

## Best Practices
- Provide specific, actionable recommendations for each missing element.
- Use clear categorization (high/medium/low priority) to prioritize improvements.
- Include impact scores for each missing element to guide implementation decisions.
- Reference source specifications to maintain traceability.
- Update completeness rating based on comprehensive evaluation.
- Focus on implementation readiness - what would be needed to build the system successfully
- Consider both technical and organizational completeness requirements

## Common Pitfalls
- Providing generic recommendations instead of specific implementation details.
- Overlooking critical implementation details that affect system readiness.
- Failing to categorize missing elements by priority and impact.
- Not referencing source specifications for traceability.
- Providing incomplete or vague recommendations that don't guide implementation.
- Neglecting to evaluate how missing elements affect overall system completeness
- Failing to assess the impact of gaps on delivery timeline and resource allocation

## Related Steps
- Step 0: Project Charter - Provides the foundation for completeness evaluation.
- Step 1: Capabilities - Defines system functionality that should be fully specified.
- Step 2: System Sketch - Provides architectural context for completeness assessment.
- Step 5: Interface Contracts - Specifies API contracts that need complete schema definitions.
- Step 13: Scaffold - Provides the implementation structure for validation.

## Best Practices for Conducting Completeness Assessments
- **Systematic Review**: Evaluate all specification artifacts from 00_charter.json through 12_ci_gates.json in a structured way
- **Implementation Focus**: Prioritize elements that would directly impact implementation success and code quality  
- **Traceability**: Always link missing elements back to their source specifications
- **Impact Assessment**: Quantify how each missing element affects overall system completeness (0.0 to 1.0 scale)
- **Priority Matrix**: Categorize missing elements based on both impact and effort required
- **Confidence Scoring**: Provide a confidence level (0.0 to 1.0) for your completeness assessment
- **Actionable Recommendations**: For each missing element, provide concrete steps that can be taken by implementation teams

## Completeness Assessment Framework
When evaluating completeness, consider these dimensions:
1. **Technical Completeness** - Implementation-ready details (API schemas, data models, algorithms)
2. **Organizational Completeness** - Governance, documentation, and operational readiness  
3. **Testability Completeness** - Fixture definitions, acceptance criteria, and validation requirements
4. **Security Completeness** - Security considerations, privacy controls, and compliance requirements

## Example Assessment Structure
```
{
  "id": "completeness-assessment-phase1",
  "owner": "api", 
  "created_at": "2025-11-02T00:00:00Z",
  "missing_elements": [
    {
      "element_id": "data-processing-details", 
      "category": "implementation-details",
      "description": "Specific chunking strategies for different document types (text, code, images) and exact parameters for parent-child document expansion",
      "priority": "high",
      "impact_on_completeness": 0.15,
      "specification_source": [
        "spec/00_charter.json",
        "docs/missing_details.md"
      ]
    }
  ],
  "completeness_rating": {
    "current": 8.5,
    "target": 10.0,
    "confidence_level": 0.9
  }
}
```

## Quick Reference
- **ID Format**: `completeness-assessment-<descriptor>`
- **Required Fields**: must include assessment results and recommendations.
- **Completeness Rating**: current and target ratings with confidence levels.
- **Missing Elements**: detailed list of missing specifications with priorities.
- **Assessment Dimensions**: Evaluate completeness across technical, organizational, testability, and security aspects
