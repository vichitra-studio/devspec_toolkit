# Step 06 · Invariants & Rules

> **Inherits**: `$TOOLKIT_ROOT/docs/prompts/shared_expectations.md` — all directives apply unless explicitly overridden below.

Run `specdev prompt-context 06` to see downstream consumers. This prompt's output feeds 3 downstream steps.

## Purpose
Capture the non-negotiable truths, guardrails, and data relationships the system must uphold regardless of implementation. These invariants feed governance, contract validation, and monitoring so deviations trigger alerts before customers feel impact.

## Tool Execution
To verify your invariants logic, verify against a sample data file:
```bash
./tools/run_specdev.sh invariants-check <spec_dir> --sample <path_to_sample_json> --repo-root ./devspec_toolkit
```

### Extraction Intent
For each upstream artifact ingested, extract the following:
- **00_charter.json**: Product scope boundaries and organizational constraints that establish which business truths are non-negotiable and which compliance or regulatory rules must be encoded as hard invariants
- **01_capabilities.json**: Capability IDs and priority levels to ensure every critical capability has at least one enforceable invariant guarding its core guarantees
- **02_system_sketch.json**: Component IDs, trust boundaries, and data flow paths to scope each invariant to specific components or APIs and derive access boundary rules from architectural separation
- **02a_delivery_baseline.json**: Environment definitions and deployment topology to determine which invariants apply at which deployment stage and to validate that enforcement mechanisms are feasible within the infrastructure
- **03_glossary.json**: Entity definitions, lifecycle states, and domain term IDs to derive state transition invariants for entities with defined stages and to ensure invariant descriptions use canonical terminology
- **04_fr_list.json**: Acceptance criteria with negative cases, error conditions, preconditions, and postconditions to encode each falsifiable constraint as a machine-checkable rule with correct severity
- **05_interface_contracts.json**: API IDs, error response definitions, and security settings to ensure every enumerated error has a corresponding invariant and that security boundaries are enforced by rules scoped to the correct APIs

## Operating Flow: Synthesize → Clarify → Emit
- Build a private Context Ledger of candidate invariants with: inv_id, business description, executable expression (jsonlogic/CEL), scope (components/apis), severity, and traces. Do not output it.
- Beyond FR-derived negative cases, MUST include: data integrity constraints implied by entities in `spec/03_glossary.json`, state transition rules for entities with lifecycle stages defined in the glossary, access boundary rules from trust boundaries in `spec/02_system_sketch.json`, and ordering guarantees identified in `spec/04_functional_requirements.json` preconditions/postconditions.
- Validate expressions against referenced fields in fixtures/schemas to ensure evaluability.
- Self-audit; if any critical FR/NFR lacks a rule or scope is too broad, ask Gap Questions.
- Rewrite into executable expressions; constrain scope to reduce false positives; finalize traces.
- Emit JSON when rules are enforceable.

## Heuristics For Completeness
- MUST use `jsonlogic` for data predicates and `cel` for field-level logic when the constraint is automatable; MUST set `severity=error` for invariants derived from FR acceptance criteria with error conditions or from security boundaries in `spec/02_system_sketch.json`.
- Scope discipline: enumerate only affected components/APIs; avoid global rules unless necessary.
- Ambiguity scrub: translate narrative policies into boolean/evaluable forms.

## Self-Audit Gate
- Gating items:
  - Each critical FR/NFR has at least one corresponding invariant or rationale for omission.
  - Expressions are syntactically valid and reference existing fields; scope defined for each rule; severity set.
  - MUST verify: if `spec/03_glossary.json` defines entities with lifecycle states, state transition invariants MUST exist for each such entity or Gap Questions MUST be raised.

### Coverage Closure
Before emitting, verify:
- Every constraint in `spec/04_functional_requirements.json` acceptance criteria (negative cases, error conditions) is encoded as an `inv_id`, OR explicitly listed in `out_of_scope` with rationale.
- Every error response defined in `spec/05_interface_contracts.json` `errors` array has a corresponding invariant governing it.
- All `trace` entries reference valid `fr_id` or `api_id` values from Steps 04 or 05.
- No business rule, security boundary, or data integrity constraint is silently omitted.
- If any constraint cannot be expressed in the supported `language` formats: add a gap question (Clarify mode) rather than skipping it.
- [ ] Every upstream ID from ingested context has been consumed
- [ ] No placeholder tokens remain (TBD, TODO, FIXME, XXX)
- [ ] All required fields populated from actual upstream data (not hallucinated)

## Step-Specific Completeness Checklist
- Every rule has a precise description, executable `language`, and concrete `expression` when automation is possible.
- `scope` limits rules to specific components or APIs to avoid false positives.
- `severity` set to `error` for hard guarantees and `warn` for observability; choose deliberately.
- `trace` connects rules to FRs/NFRs/governance to explain rationale.
- Avoid purely textual rules unless automation is truly not feasible.

## Best Practices
- **Language**: Choose the appropriate `language` (`jsonlogic`, `cel`, or `text`) and write evaluable `expression` strings for automated enforcement.
- **Scoping**: Describe each invariant in business language first, then map `scope.components` or `scope.apis` to constrain where it applies.
- **Severity**: Tag severity as `error` for hard guarantees and `warn` for observability alerts to guide escalation paths.
- **Trace**: Link invariants to FRs, NFRs, or governance rules using `trace` so auditors know why the rule exists.

## Negative Constraints
- ❌ DO NOT use `text` language unless absolutely necessary.
- ❌ DO NOT invent component IDs; use only those from Step 2.
- ❌ DO NOT skip tracing; every rule must have a reason (trace).

## Common Pitfalls
- **Empty Logic**: Leaving the `expression` empty or non-executable, which prevents automation in CI and runtime.
- **Severity Drill**: Setting severity to `warn` for hard requirements, letting regressions slip past controls.
- **False Positives**: Forgetting to scope the invariant, causing checks to fail on unrelated components.
- **Bad IDs**: Failing to version or reuse `inv_id`, leading to duplicate or orphaned invariants.

# Clarification Questions
- Which truths must always hold regardless of implementation (data relationships, auth requirements, idempotency)?
- Where can we encode these as executable rules (jsonlogic or CEL)? Provide expressions or field-level specs.
- What scope should each rule have (components, APIs) to reduce noise and false alerts?
- Which rules are hard errors vs warnings? Who is accountable for remediation?
- Which FRs, NFRs, or governance policies motivate each invariant?

# Schema Reference
- Schema URI: vc:06-invariants
- Schema File: schema/06_invariants.schema.json
- Schema Registry: tools/schema_registry.json

# Output Contract
```json
{
  "id": "invariants-catalog",
  "owner": "api",
  "created_at": "2025-01-01T00:00:00Z",
  "rules": [
    {
      "inv_id": "inv-session-token-required",
      "description": "Authenticated endpoints require a valid session token.",
      "language": "text",
      "expression": "request.authenticated == true",
      "scope": {
        "components": [
          "auth-service"
        ]
      },
      "trace": [
        {
          "type": "doc",
          "id": "fr-auth-login"
        }
      ],
      "policy_ref": {
        "id": "cn:core:policy:spec-first",
        "kind": "policy"
      }
    }
  ],
  "canonical_refs_used": [
    {
      "id": "cn:core:policy:spec-first",
      "kind": "policy"
    }
  ]
}
```
