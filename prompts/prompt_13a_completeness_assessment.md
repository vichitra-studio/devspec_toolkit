# Prompt: 13a. Completeness Assessment

## Context
You are an expert in spec-driven development using the DevSpec toolkit. Your task is to assess the completeness of Phase 1 specifications for a system and identify gaps that prevent achieving perfect implementation readiness.

## Objective
Evaluate the current specification state against ideal completeness criteria and generate actionable recommendations for improvement. This assessment should cover all aspects of the specification to determine how close the current state is to 10/10 completeness.

## Instructions
1. Analyze all existing specification files (00_charter.json through 12_ci_gates.json) 
2. Identify gaps in specification completeness that would prevent achieving perfect implementation readiness
3. Provide specific, actionable recommendations for each missing element
4. Rate the system completeness on a 1-10 scale with confidence metrics
5. Categorize missing elements by priority (high, medium, low) and impact score

## Input Files
- spec/00_charter.json
- spec/01_capabilities.json  
- spec/02_system_sketch.json
- spec/02a_delivery_baseline.json
- spec/03_glossary.json
- spec/04_fr_list.json
- spec/05_interface_contracts.json
- spec/06_invariants.json
- spec/07_nfrs.json
- spec/08_fixtures.json
- spec/09_impl_plan.json
- spec/10_governance.json
- spec/11_redteam.json
- spec/12_ci_gates.json

## Output Format
Provide exactly one JSON block that validates against the schema for step 13a.

## Required Fields
- id: kebab-case identifier 
- owner: owner identifier
- created_at: timestamp
- missing_elements: array of objects with:
  - element_id: kebab-case identifier
  - category: string describing the type of missing element
  - description: detailed explanation of what's missing
  - priority: "high", "medium", or "low"
  - impact_on_completeness: decimal between 0-1
  - specification_source: array of spec files that reference this element
- completeness_rating: object with:
  - current: decimal between 0-10
  - target: decimal between 0-10 (should be 10.0)
  - confidence_level: decimal between 0-1

## Key Considerations
- Focus on implementation readiness - what would be needed to build the system successfully
- Prioritize elements that have the highest impact on completeness and implementation quality
- Provide concrete, actionable recommendations
- Ensure all source references are accurate and traceable
- Consider completeness across multiple dimensions:
  * Technical completeness (implementation-ready details)
  * Organizational completeness (governance, documentation, operational readiness)
  * Testability completeness (fixture definitions and acceptance criteria)
  * Security completeness (security considerations and compliance)

## Heuristics For Completeness Assessment
- Optional→expected: include detailed implementation specifications that are missing from previous steps
- Ambiguity scrub: make sure all implementation details are well-defined and unambiguous
- Traceability focus: ensure every missing element can be traced back to one or more source specification files
- Impact scoring: assess how each missing element affects the overall system completeness (0.0 to 1.0 scale)
- Priority matrix: categorize based on both impact and effort required

## Self-Audit Gate
If completeness < 0.9, ask questions to clarify:
- Are all implementation details specified in sufficient detail for developers to begin coding?
- Do we have complete API schema definitions and examples?
- Are there missing data models, algorithms, or interface specifications?
- Have we accounted for all testing requirements and acceptance criteria?

## Best Practices
- Use a systematic approach to review all 13 specification artifacts
- Prioritize missing elements that would block implementation or cause significant rework  
- Provide concrete, actionable recommendations that can guide development teams
- Quantify impact and priority to help stakeholders make informed decisions
- Reference specific source files to maintain traceability and context

## Common Pitfalls to Avoid
- Providing generic or vague recommendations instead of specific implementation details
- Overlooking critical technical specifications that would impact code quality or performance
- Failing to categorize missing elements by both priority and impact 
- Not referencing source specifications to maintain traceability
- Providing incomplete or poorly defined recommendations that don't guide implementation

## Example Output Structure
{
  "id": "completeness-assessment-example",
  "owner": "api",
  "created_at": "2025-10-22T00:00:00Z",
  "missing_elements": [
    {
      "element_id": "data-processing-details",
      "category": "implementation-details",
      "description": "Specific chunking strategies for different document types and exact parameters for parent-child document expansion",
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
