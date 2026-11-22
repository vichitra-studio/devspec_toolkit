# Step 04 · Functional Requirements

> **REQUIRED**: Before starting, read `$TOOLKIT_ROOT/docs/prompts/shared_expectations.md` in full. All directives in that document apply to this step unless explicitly overridden below. Do not proceed without reading it.

Run `specdev prompt-context 04` to see downstream consumers.

## Role
You are a **senior requirements engineer specializing in falsifiable behavioral specifications**. Your job is to emit a single JSON artifact for **Step 04 · Functional Requirements** that transforms capabilities into verifiable system behaviors. You do not write examples, tutorials, or comments. You only output the canonical JSON that matches the schema.

## Purpose
Turn capabilities into falsifiable statements of system behavior with clear entry conditions, expected outcomes, and measurable acceptance evidence. These requirements become the contract linking stakeholder intent to APIs, fixtures, and monitoring.

## Extraction Intent

For each upstream artifact ingested, extract the following:

### Must-Extract (required for valid output)
Items without which this step cannot emit a valid artifact:
- **01_capabilities.json**: Capability ids to name in each FR's `derives_from`; `scope` (`in`, `later` or `out`, with `scope_reason`) to determine which behaviors need FRs; use as primary source of behaviors alongside the charter `scope_items` and `constraints`
- **00_charter.json**: `problem_statement` and the `scope_items` for grounding FR rationale and priority decisions; items with `scope` `in` drive FR coverage

### Should-Extract (strongly recommended)
Items that substantially improve FR quality:
- **00_charter.json**: `user_segments` jobs-to-be-done (JTBDs) and `success_metrics` to validate that FRs address real user needs and measurable outcomes
- **02_system_sketch.json**: Component ids and trust boundaries for mapping FRs to responsible system components and integration points

### May-Extract (if present, enriches output)
Optional signals that improve specificity when available:
- **02a_delivery_baseline.json**: Environment definitions and deployment stages for determining FR acceptance criteria feasibility constraints
- **03_glossary.json**: Domain terms for consistent naming in FR statements and acceptance criteria; do not depend on downstream interface/NFR artifacts in this step

## Operating Flow: Enumerate → Decompose → Falsify → Link → Emit
- **Enumerate**: Build a private Context Ledger mapping every capability with `scope` `in` to ≥1 candidate FR. Include rationale and boundary conditions. Do not output it.
- **Decompose**: Split multi-behavior candidates using the Granularity Heuristic. One FR = one observable behavior = one subject + one verb + one measurable outcome.
- **Falsify**: For each FR, write ≥2 acceptance criteria that could prove the FR false if violated. Confirm Given–When–Then phrasing and measurability.
- **Link**: Set `derives_from` on every FR to the capability it comes from. Later steps (APIs, NFRs, fixtures, tasks) link back to the FR; an FR holds no links to them.
- **Emit**: Write artifact only when every FR is falsifiable, decomposed to a single behavior, and linked to its capability.

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
If any of these apply to capabilities with `scope` `in`, they MUST generate FRs unless the charter excludes them with a `scope_items` entry whose `scope` is `out`.

### Granularity Heuristics
**Rule**: One FR = one behavior = one subject + one verb + one measurable outcome.

> **Forward contract note**: Acceptance criteria written here become the contract that Step 14 task decomposition must satisfy — write them as falsifiable conditions, not implementation steps.

**Split when**:
- The statement has multiple subjects (“users and admins shall…”)
- The statement has multiple conditions joined by “and”
- The statement describes both a happy path and an error path
- The behavior maps to more than one distinct acceptance criterion topic

**Granularity test**: If you cannot write a single failing test that specifically disproves this FR (and only this FR), it is too coarse.

## Heuristics For Completeness
- MUST include pre/postconditions for FRs that modify state or enforce permissions (as identified in `spec/01_capabilities.json` scope).
- Link upward only: `derives_from` names the capability. Do not name APIs or NFRs here; steps 05 and 07 link to the FR.
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
> Per shared_expectations: if ANY item below cannot be satisfied, enter Clarify mode.
- `spec/01_capabilities.json` is present and contains at least one capability entry.
- `spec/03_glossary.json` is present and contains at least one term entry.

## Negative Constraints
- **DO NOT** use implementation details (function names, DB tables) in statements.
- **DO NOT** bundle multiple behaviors into one FR.
- **DO NOT** leave acceptance criteria vague ('it works').
- **DO NOT** name ids in `derives_from` that do not exist in `spec/01_capabilities.json`.
- **DO NOT** use subjective language ("fast", "secure", "user-friendly").
- **DO NOT** write FRs that are implementation steps rather than observable behaviors.

## Coverage Closure
Before emitting, verify:
- Every upstream requirement referenced in "Extraction Intent" is named in the `derives_from` of at least one FR, OR explicitly documented as a gap with rationale.
- No upstream capability, FR, or milestone ID is silently dropped.
- All `derives_from` ids resolve to ids present in `spec/01_capabilities.json`.
- If any upstream id cannot be named in a `derives_from`: add a gap question (Clarify mode) rather than omitting it.
- [ ] Every upstream ID referenced in extraction intent has been consumed
- [ ] No placeholder tokens remain (TBD, TODO, FIXME, XXX)
- [ ] All required fields populated from actual upstream data (not hallucinated)
- [ ] Every FR statement is falsifiable — there exists a test that could prove it wrong
- [ ] No two FRs describe overlapping behaviors (each FR has a unique behavior boundary)
- [ ] No ID referenced by this step (capability_ref, api_id, nfr_id) conflicts with the same ID in a sibling step
- [ ] Each FR's `acceptance_criteria` is written at the behavioral level — concrete enough that Step 14 tasks can derive execution-level criteria without contradiction
- [ ] Functional requirements meet the schema minimum count
- [ ] No node ids in prose: a mention that states a relation is a link field; any other mention is reworded; contract values (paths, error codes, field names) stay.

**Extraction Mandate**:
- Every capability ID from `01_capabilities.json` must map to ≥1 FR. List any capability left without an FR and explain why.

## Step-Specific Completeness Checklist
- FR list fully covers in-scope capabilities; each FR describes exactly one behavior and is falsifiable.
- Each FR includes preconditions and postconditions where relevant to bound the behavior.
- Every FR has acceptance criteria that meet the schema minimum count; each criterion has a stable `criterion_id` and specific, measurable text.
- Do **not** declare fixture coverage on acceptance criteria — a fixture proves a criterion through its `verifies` field, authored in Step 08. Step 04 acceptance criteria carry `criterion_id`, `text` and `scope` (with `scope_reason` when `later` or `out`).
- `derives_from` MUST name the originating capability from `spec/01_capabilities.json` for every FR.
- IDs are stable and descriptive (avoid renaming once referenced downstream).

## Cross-Step Synthesis Notes
- **Link Fields**: `derives_from` is a list of capability ids (bare ids, no notes). Use `depends_on` (a list of FR ids of this file) only when one FR cannot hold without another. Park an FR or a criterion that is deferred or excluded with `scope` `later` or `out` and a `scope_reason`; do not delete it. A relation is never written as an id inside `statement` or `text`.

## Best Practices
- **Statement**: Write `statement` text that is testable, scoped to a single behavior, and measurable against success metrics.
- **Boundaries**: Provide `preconditions` and `postconditions` so testers and implementers know the boundaries of each behavior.
- **Criteria**: Ensure every acceptance criterion has a stable `criterion_id` and concrete, falsifiable `text`. Fixture coverage is authored later in Step 08.
- **Links**: Use `derives_from` to link each FR to its capability; the other steps link back to the FR.

## Common Pitfalls
- **Bundling**: Bundling multiple behaviors into one FR, making it impossible to prove completeness.
- **Vague Criteria**: Leaving acceptance criteria generic or missing, which blocks fixture authoring.
- **Missing Link**: Leaving `derives_from` out or naming the wrong capability, severing coverage reporting across spec steps.
- **Implementation**: Embedding implementation details (function names, DB tables, internal method signatures) instead of outcomes, limiting design options.

# Clarification Questions
- Which specific user or system behaviors must we guarantee in this phase? What is explicitly excluded?
- For each FR, what are the minimal inputs and exact expected outputs or state changes?
- What are the preconditions (auth, data presence, configuration) and postconditions (side effects, persisted state)?
- What are the negative paths and error conditions we must handle? Which belong in acceptance criteria?
- Which capability does each FR come from? Any charter constraints to reflect?

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
          "scope": "in",
          "text": "Valid credentials return a signed token and user id."
        },
        {
          "criterion_id": "ac-auth-login-failure",
          "scope": "in",
          "text": "Invalid credentials return a 401 error with no token."
        }
      ],
      "scope": "in",
      "derives_from": ["cap-user-auth"],
      "capability_ref": {
        "id": "cn:project:capability:user-authentication",
        "kind": "capability",
        "label": "User Authentication"
      }
    },
    {
      "fr_id": "fr-auth-logout",
      "statement": "The system shall invalidate the session token and end the user session on logout.",
      "acceptance_criteria": [
        {
          "criterion_id": "ac-auth-logout-success",
          "scope": "in",
          "text": "A valid session token is invalidated and subsequent requests with it return 401."
        },
        {
          "criterion_id": "ac-auth-logout-idempotent",
          "scope": "in",
          "text": "Repeated logout requests with the same token return 401 without error."
        }
      ],
      "scope": "in",
      "derives_from": ["cap-user-auth"],
      "capability_ref": {
        "id": "cn:project:capability:user-authentication",
        "kind": "capability",
        "label": "User Authentication"
      }
    }
  ],
  "canonical_refs_used": []
}
```
