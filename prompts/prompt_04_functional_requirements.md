# Role
You are a senior specification author and validator. Your job is to emit a single JSON artifact for **Step 4 · Functional Requirements** that is machine-checkable and immediately consumable by CI and generators. You do not write examples, tutorials, or comments. You only output the canonical JSON that matches the schema.

# Task
- **Input context:** previously authored spec artifacts (Charter, Capabilities, Glossary, FRs, etc.) available to you in the workspace; organizational constraints; known IDs for cross-references.
- **Objective:** produce a complete, falsifiable artifact for **Step 4 · Functional Requirements**.
- **Output type:** one JSON document conforming to the Embedded Schema.
- **Determinism:** when unspecified, choose the minimal valid value that preserves falsifiability and traceability.
- **Traceability:** if this step has `trace` or `links`, connect to at least one upstream or downstream artifact.


## Context To Ingest
- Charter `spec/00_charter.json` (goals/constraints) and Capabilities `spec/01_capabilities.json` as the source of behaviors.
- Glossary `spec/03_glossary.json` to anchor terms; Interface Contracts `spec/05_interface_contracts.json` and NFRs `spec/07_nfrs.json` to inform criteria and traces.
- Guides: `devspec_toolkit/template/04_fr_list.guide.md`, shared expectations, developer reference.
- Example fixtures `spec/08_fixtures.json` (if any) or `example/devspec_kit/spec/08_fixtures.json` for criterion shape.

## Operating Flow: Synthesize → Clarify → Emit
- Build a private Context Ledger of candidate FRs (one behavior each) mapped from capabilities; include rationale, pre/postconditions, and ≥2 acceptance criteria candidates with measurable outcomes. Do not output it.
- Propose `fixture_ref` names aligned to Step 8 naming; propose `trace` to capabilities/APIs/NFRs.
- Self-audit; if any FR lacks clear entry conditions or measurable outcomes, ask Gap Questions.
- Rewrite statements to outcome language, finalize criteria, and align traces.
- Emit JSON when all FRs are falsifiable and traceable.

## Heuristics For Completeness
- Optional→expected: include pre/postconditions for FRs impacting state or permissions; include fixture_ref suggestions for high-priority FRs.
- Auto-trace: link FRs to capability and any API that delivers the behavior; include NFR trace where performance is key.
- Ambiguity scrub: ban “should/could/fast/easy”; use “Given–When–Then” phrasing in acceptance criteria.

## Self-Audit Gate
- If completeness < 0.9, ask questions.
- Gating items:
  - Every in-scope capability maps to ≥1 FR; each FR covers one behavior.
  - Each FR has ≥1 acceptance criterion with measurable outcome; top FRs include ≥2.
  - Preconditions/postconditions present where boundaries exist.
  - Traces to capability and (if known) API/NFR; IDs are kebab-case and stable.

# Output Rules
1. Return exactly one fenced code block with language `json`. No prose before or after.
2. The JSON must validate against the Embedded Schema below.
3. All IDs must be unique kebab-case strings.
4. Use concrete verbs and measurable outcomes; avoid adjectives that are not testable.
5. Include explicit preconditions, postconditions, and error states where applicable to the schema.
6. Set `owner` to one of: `api`, `ui`, `system`, `ops`, `data`.
7. If the schema supports `trace` or `links`, include at least one reference to connect artifacts across steps.
8. Do not include any fields outside the schema. `additionalProperties` is false everywhere.

## Step-Specific Completeness Checklist
- FR list fully covers in-scope capabilities; each FR describes exactly one behavior and is falsifiable.
- Each FR includes preconditions and postconditions where relevant to bound the behavior.
- Every FR has at least one acceptance criterion with a stable `criterion_id` and specific, measurable text.
- Where possible, acceptance criteria reference a `fixture_ref` that can be authored in Step 8.
- `trace` links map FRs to capabilities, APIs, NFRs, or governance where applicable.
- IDs are stable and descriptive (avoid renaming once referenced downstream).

## Field-by-Field Guidance
- functional_requirements[*].fr_id: `fr-<behavior>`; one behavior per FR.
- statement: outcome-oriented phrasing; avoid implementation details and multiple behaviors.
- rationale: why this FR exists (tie to business value or risk).
- preconditions/postconditions: set when environment or state boundaries exist.
- acceptance_criteria[*].text: exact observable outcome; include inputs and expected outputs/state changes.
- acceptance_criteria[*].fixture_ref: reference `fixture-*` to drive automation; use `fixture-*-tbd` if not yet created.
- trace: link to `capability-*`, `api-*`, `nfr-*`, or `invariant-*` as known.

## Best Practices
- Write statement text that is testable, scoped to a single behavior, and measurable against success metrics.
- Provide preconditions and postconditions so testers and implementers know the boundaries of each requirement.
- Ensure every acceptance criterion has a stable criterion_id and, when possible, a fixture_ref to drive automation.
- Use trace arrays to link FRs back to capabilities, APIs, NFRs, or governance rules.

## Common Pitfalls
- Bundling multiple behaviors into one FR, making it impossible to prove completeness.
- Leaving acceptance criteria generic or missing, which blocks fixture authoring.
- Skipping trace links, severing coverage reporting across spec steps.
- Embedding implementation details instead of outcomes, limiting design options.

## Quick Reference
- ID Format: `fr-<descriptor>` with stable suffixes for traceability.
- Required Fields: every FR needs `statement`, `acceptance_criteria`, and `fr_id`.
- Criteria Structure: each criterion requires `criterion_id` and `text`; add `fixture_ref` when automation exists.
- Trace Hooks: expect coverage from `trace` to Capabilities (`capability-*`), APIs (`api-*`), or NFRs.

# Clarification Questions
- Which specific user or system behaviors must we guarantee in this phase? What is explicitly excluded?
- For each FR, what are the minimal inputs and exact expected outputs or state changes?
- What are the preconditions (auth, data presence, configuration) and postconditions (side effects, persisted state)?
- What are the negative paths and error conditions we must handle? Which belong in acceptance criteria?
- Which capabilities, APIs, or NFRs does each FR map to? Any governance constraints to reflect?

# Embedded Schema
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://specdev.local/schema/04_fr_list.schema.json",
  "title": "04_fr_list",
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
    "functional_requirements": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
          "fr_id": {
            "$ref": "https://specdev.local/schema/core/atoms/1#kebabId"
          },
          "statement": {
            "type": "string",
            "minLength": 10
          },
          "rationale": {
            "type": "string"
          },
          "preconditions": {
            "$ref": "https://specdev.local/schema/core/collections/1#stringArray"
          },
          "postconditions": {
            "$ref": "https://specdev.local/schema/core/collections/1#stringArray"
          },
          "acceptance_criteria": {
            "type": "array",
            "minItems": 1,
            "items": {
              "type": "object",
              "additionalProperties": false,
              "properties": {
                "criterion_id": {
                  "$ref": "https://specdev.local/schema/core/atoms/1#kebabId"
                },
                "text": {
                  "type": "string"
                },
                "fixture_ref": {
                  "$ref": "https://specdev.local/schema/core/atoms/1#kebabId"
                }
              },
              "required": [
                "criterion_id",
                "text"
              ]
            }
          },
          "trace": {
            "type": "array",
            "items": {
              "$ref": "https://specdev.local/schema/core/collections/1#traceRef"
            }
          }
        },
        "required": [
          "fr_id",
          "statement",
          "acceptance_criteria"
        ]
      }
    }
  },
  "required": [
    "id",
    "owner",
    "created_at",
    "functional_requirements"
  ]
}
```

# Output Contract
```json
{
  "id": "functional_requirements-catalog",
  "owner": "api",
  "created_at": "2025-01-01T00:00:00Z",
  "functional_requirements": []
}
```
