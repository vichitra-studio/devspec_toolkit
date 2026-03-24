# Step 04 · Functional Requirements

> **Inherits**: `$TOOLKIT_ROOT/docs/prompts/shared_expectations.md` — all directives apply unless explicitly overridden below.

Run `specdev prompt-context 04` to see downstream consumers. This prompt's output feeds 13 downstream steps.

## Role
You are a **senior requirements engineer specializing in falsifiable behavioral specifications**. Your job is to emit a single JSON artifact for **Step 04 · Functional Requirements** that transforms capabilities into verifiable system behaviors. You do not write examples, tutorials, or comments. You only output the canonical JSON that matches the schema.

## Purpose
Turn capabilities into falsifiable statements of system behavior with clear entry conditions, expected outcomes, and measurable acceptance evidence. These requirements become the contract linking stakeholder intent to APIs, fixtures, and monitoring.

## Extraction Intent

For each upstream artifact ingested, extract the following:
- **00_charter.json**: Project scope boundaries, success criteria, and constraints for grounding FR rationale and priority decisions
- **01_capabilities.json**: Capability IDs for traceability binding; scope (in/out/future) to determine which behaviors need FRs; use as primary source of behaviors alongside charter goals/constraints
- **02_system_sketch.json**: Component IDs and trust boundaries for mapping FRs to responsible system components and integration points
- **02a_delivery_baseline.json**: Environment definitions and deployment stages for determining FR acceptance criteria feasibility constraints
- **03_glossary.json**: Domain terms for consistent naming in FR statements and acceptance criteria; do not depend on downstream interface/NFR artifacts in this step

## Operating Flow: Enumerate → Decompose → Falsify → Trace → Emit
- **Enumerate**: Build a private Context Ledger mapping every in-scope capability to ≥1 candidate FR. Include rationale and boundary conditions. Do not output it.
- **Decompose**: Split multi-behavior candidates using the Granularity Heuristic. One FR = one observable behavior = one subject + one verb + one measurable outcome.
- **Falsify**: For each FR, write ≥2 acceptance criteria that could prove the FR false if violated. Confirm Given–When–Then phrasing and measurability.
- **Trace**: Link every FR to its originating capability; add API, NFR, and governance trace refs where known IDs exist.
- **Emit**: Write artifact only when every FR is falsifiable, decomposed to a single behavior, and fully traced.

### Implicit Requirements Discovery Checklist
Before emitting, verify these system-level behaviors have been considered as FR candidates:
- **Error handling**: What happens on invalid input, service failure, or timeout?
- **Authorization**: Which operations require authenticated/authorized actors?
- **Input validation**: What are the bounds and formats for every user-provided input?
- **Audit logging**: Which state-changing operations must produce an audit trail?
- **Idempotency**: Which operations must produce the same result when repeated?
- **Pagination**: Which list operations must support bounded page sizes?
- **Concurrency**: Which operations need locking, queuing, or conflict detection?
- **Rate limiting**: Which operations must be protected from abusive call volumes?
- **Data lifecycle**: Where must data be retained, archived, or purged?
If any of these apply to in-scope capabilities, they MUST generate FRs unless explicitly excluded in the charter.

### Granularity Heuristics
**Rule**: One FR = one behavior = one subject + one verb + one measurable outcome.
**Split when**:
- The statement has multiple subjects (“users and admins shall…”)
- The statement has multiple conditions joined by “and”
- The statement describes both a happy path and an error path
- The behavior maps to more than one distinct acceptance criterion topic

**Granularity test**: If you cannot write a single failing test that specifically disproves this FR (and only this FR), it is too coarse.

### Forbidden Actions
- DO NOT combine multiple behaviors into one FR
- DO NOT use subjective language ("fast", "secure", "user-friendly")
- DO NOT reference implementation details (function names, DB tables, internal methods)
- DO NOT write FRs that are implementation steps rather than observable behaviors

## Heuristics For Completeness
- MUST include pre/postconditions for FRs that modify state or enforce permissions (as identified in `spec/01_capabilities.json` scope); MUST include `fixture_ref` for every FR with `priority: high` in the capabilities.
- Auto-trace: link FRs to capability and any API that delivers the behavior; include NFR trace where performance is key.
- Ambiguity scrub: ban “should/could/fast/easy”; use “Given–When–Then” phrasing in acceptance criteria.

### Weak-vs-Strong FR Examples

| ❌ Weak | ✅ Strong |
|---------|----------|
| The system should let users log in easily. | The system shall authenticate a registered user with valid credentials and return a signed session token within 2s. |
| Admins can manage users. | The system shall allow an admin to deactivate a user account, immediately invalidating all active sessions for that account. |
| The API should handle errors. | The system shall return HTTP 422 with a structured error body when required fields are missing from a POST request. |
| Reports must be fast. | The system shall generate a usage report for ≤10,000 records within 5 seconds at p99. |
| The system should support pagination. | The system shall return paginated results for all list endpoints, with a default page size of 20 and a maximum of 100. |

## Self-Audit Gate
- Gating items:
  - Every in-scope capability maps to ≥1 FR; each FR covers one behavior.
  - Each FR has ≥2 acceptance criteria with measurable outcomes.
  - Preconditions/postconditions present where boundaries exist.
  - Traces to capability and (if known) API/NFR; IDs are kebab-case and stable.

### Coverage Closure
Before emitting, verify:
- Every upstream requirement referenced in "Extraction Intent" is represented in this artifact's `trace`, `links`, or `fr_refs` array, OR explicitly listed in `out_of_scope` with rationale.
- No upstream capability, FR, or milestone ID is silently dropped.
- All `trace` / `links` IDs resolve to IDs present in the referenced upstream spec file.
- If any upstream ID cannot be traced: add a gap question (Clarify mode) rather than omitting it.
- [ ] Every upstream ID referenced in extraction intent has been consumed
- [ ] No placeholder tokens remain (TBD, TODO, FIXME, XXX)
- [ ] All required fields populated from actual upstream data (not hallucinated)
- [ ] Every FR statement is falsifiable — there exists a test that could prove it wrong
- [ ] No two FRs describe overlapping behaviors (each FR has a unique behavior boundary)
- [ ] No ID referenced by this step (capability_ref, api_id, nfr_id) conflicts with the same ID in a sibling step

**Extraction Mandate**:
- Every capability ID from `01_capabilities.json` must map to ≥1 FR. List any capability left without an FR and explain why.

## Step-Specific Completeness Checklist
- FR list fully covers in-scope capabilities; each FR describes exactly one behavior and is falsifiable.
- Each FR includes preconditions and postconditions where relevant to bound the behavior.
- Every FR has at least two acceptance criteria with a stable `criterion_id` and specific, measurable text.
- MUST include a `fixture_ref` for every acceptance criterion whose behavior is automatable in Step 8; use `fixture-*-tbd` if the fixture does not yet exist.
- `trace` links MUST map every FR to its originating capability from `spec/01_capabilities.json`; MUST also map to APIs, NFRs, or governance IDs when those IDs exist in the corresponding upstream spec files.
- IDs are stable and descriptive (avoid renaming once referenced downstream).

## Cross-Step Synthesis Notes
- **Trace Object Structure**: The trace field must be an array of objects with the structure: `{"type": "capability", "id": "cap-user-auth", "note": "Implements core behavior"}`. Do not use simple strings or arrays of strings.

## Best Practices
- **Statement**: Write `statement` text that is testable, scoped to a single behavior, and measurable against success metrics.
- **Boundaries**: Provide `preconditions` and `postconditions` so testers and implementers know the boundaries of each behavior.
- **Criteria**: Ensure every acceptance criterion has a stable `criterion_id` and, when possible, a `fixture_ref` to drive automation.
- **Trace**: Use `trace` arrays to link FRs back to capabilities, APIs, NFRs, or governance rules cover-to-cover.

## Common Pitfalls
- **Bundling**: Bundling multiple behaviors into one FR, making it impossible to prove completeness.
- **Vague Criteria**: Leaving acceptance criteria generic or missing, which blocks fixture authoring.
- **Missing Link**: Skipping trace links, severing coverage reporting across spec steps.
- **Implementation**: Embedding implementation details (function names, DB tables, internal method signatures) instead of outcomes, limiting design options.

## Negative Constraints
- **DO NOT** use implementation details (function names, DB tables) in statements.
- **DO NOT** bundle multiple behaviors into one FR.
- **DO NOT** leave acceptance criteria vague ('it works').
- **DO NOT** trace to non-existent IDs.
- **DO NOT** use simple strings or arrays of strings for trace fields - always use the object structure.

# Clarification Questions
- Which specific user or system behaviors must we guarantee in this phase? What is explicitly excluded?
- For each FR, what are the minimal inputs and exact expected outputs or state changes?
- What are the preconditions (auth, data presence, configuration) and postconditions (side effects, persisted state)?
- What are the negative paths and error conditions we must handle? Which belong in acceptance criteria?
- Which capabilities, APIs, or NFRs does each FR map to? Any governance constraints to reflect?

# Schema Reference
- Schema URI: vc:04-fr-list
- Schema File: schema/04_fr_list.schema.json
- Schema Registry: tools/schema_registry.json

# Output Contract
```json
{
  "$schema": "vc:04-fr-list",
  "id": "functional-requirements-catalog",
  "owner": "api",
  "created_at": "2025-01-01T00:00:00Z",
  "functional_requirements": [
    {
      "fr_id": "fr-auth-login",
      "statement": "The system shall authenticate a user and issue a session token.",
      "acceptance_criteria": [
        {
          "criterion_id": "ac-auth-login-success",
          "text": "Valid credentials return a signed token and user id."
        },
        {
          "criterion_id": "ac-auth-login-failure",
          "text": "Invalid credentials return a 401 error with no token."
        }
      ],
      "trace": [
        {
          "type": "capability",
          "id": "cap-user-auth"
        },
        {
          "type": "api",
          "id": "api-session-create"
        }
      ],
      "capability_ref": {
        "id": "cn:core:capability:example",
        "kind": "capability"
      }
    }
  ],
  "canonical_refs_used": []
}
```
