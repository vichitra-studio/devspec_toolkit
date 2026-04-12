# Step 08 · Test Plan & Fixtures

> **REQUIRED**: Before starting, read `$TOOLKIT_ROOT/docs/prompts/shared_expectations.md` in full. All directives in that document apply to this step unless explicitly overridden below. Do not proceed without reading it.

Run `specdev prompt-context 08` to see downstream consumers. This prompt's output feeds 2 downstream steps.

## Role
You are a **test architect specializing in fixture design**. Your job is to emit a single JSON artifact for **Step 08 · Fixtures** that provides concrete test data covering every high-priority FR acceptance criterion. You do not write examples, tutorials, or comments. You only output the canonical JSON that matches the schema.

## Purpose
Supply deterministic inputs and expected outputs that exercise functional and non-functional behaviors across the spec. These fixtures form the backbone of automated validation, red-team loops, and regression detection.

## Tool Execution
Lint the fixtures for completeness:
```bash
./tools/run_specdev.sh fixtures-lint <spec_dir> --repo-root ./devspec_toolkit
```

### Extraction Intent
For each upstream artifact ingested, extract the following:
- **00_charter.json**: Product scope boundaries and success metrics to determine which behaviors are in-scope for fixture coverage and to tag smoke fixtures for critical business flows
- **01_capabilities.json**: Capability IDs and priority rankings to identify high-priority capabilities whose FRs require mandatory smoke-tagged fixtures and to prioritize fixture creation order
- **02_system_sketch.json**: Component IDs, inter-component data flow paths, and **tech_stack** (framework choices that determine test runner, fixture format, and setup/teardown patterns — e.g., pytest fixtures for Python, Jest for TypeScript, testcontainers for integration tests) to determine which components need contract-mode fixtures and to structure end-to-end fixture chains across service boundaries
- **02a_delivery_baseline.json**: Environment definitions and CI pipeline configuration to determine which fixture tags map to which pipeline stages and to validate that fixture execution is feasible in each environment
- **03_glossary.json**: Canonical term IDs, entity field names, and domain vocabulary to ensure all fixture input payloads and expected output fields use exact glossary terms rather than invented or inconsistent field names
- **04_fr_list.json**: Functional requirement IDs, acceptance criteria including happy-path and negative cases, preconditions, and postconditions to generate at least one fixture per acceptance criterion with matching target references
- **05_interface_contracts.json**: API IDs, request/response schema references, error definitions with status codes, and security requirements to build contract-mode fixtures with exact payload shapes and negative fixtures for every enumerated error
- **06_invariants.json**: Invariant IDs with severity error and their executable expressions to create negative-case fixtures that verify each critical invariant is enforced and that violations produce the expected rejection behavior
- **07_nfrs.json**: NFR IDs with category latency or throughput, their numeric targets, and units to generate benchmark and load-test fixtures tagged appropriately for performance validation in CI pipelines

## Operating Flow: Map → Generate → Validate → Emit
- **Map**: For each high-priority FR and its acceptance criteria, identify the fixture(s) needed. Track coverage in a private Context Ledger.
- **Generate**: Create fixture data that is concrete, realistic, and deterministic. Each fixture should represent a specific scenario (happy path, boundary case, error case).
- **Validate**: Verify every high-priority FR has ≥1 fixture; every acceptance criterion that is automatable has a `fixture_ref`; no fixture is missing a `target` ID.
- **Emit**: Write the artifact only when coverage is complete.

**Extraction Mandate**: Every high-priority FR (`priority: high`) must have ≥1 fixture. Every automatable acceptance criterion must have a `fixture_ref` pointing to a fixture ID. List any high-priority FR without a fixture and explain why.

### Weak-vs-Strong Fixture Examples

| Weak | Strong |
|------|--------|
| Test login | `fixture-auth-login-success`: POST /auth/sessions with valid credentials → 200 + signed token |
| Error case | `fixture-auth-login-bad-password`: POST /auth/sessions with wrong password → 401 `INVALID_CREDENTIALS` |
| Data test | `fixture-user-profile-update-valid`: PUT /users/{id} with valid fields → 200 + updated profile |
| Edge case | `fixture-search-empty-results`: GET /products?q=zzznomatch → 200 + `{"results": [], "total_count": 0}` |

## Heuristics For Completeness
- MUST add `targets` referencing every `fr_id`, `api_id`, `inv_id`, or `nfr_id` that the fixture exercises (as identified in `spec/04_fr_list.json`, `spec/05_interface_contracts.json`, `spec/06_invariants.json`, `spec/07_nfrs.json`); MUST add `smoke` tag for fixtures covering FRs listed as high-priority in capabilities; MUST add `load` tag for fixtures covering NFRs with `category: latency` or `category: throughput`.
- Error coverage: at least one fixture per meaningful error in interface contracts.
- Ambiguity scrub: express expected state/data exactly; avoid “approximate/maybe”.

## Self-Audit Gate
> Per shared_expectations: if ANY item below cannot be satisfied, enter Clarify mode.
- `spec/04_fr_list.json` is present and contains at least one functional_requirements entry.
- `spec/05_interface_contracts.json` is present and contains at least one api entry.
- `spec/06_invariants.json` is present and contains at least one invariant entry.

## Negative Constraints
- **NEVER** invent new IDs. Every trace ID must exist in the upstream specs.
- **NEVER** use generic placeholder IDs (e.g., `api-login`) unless they match the actual spec.
- **NEVER** include markdown commentary or key-value pairs outside the JSON block.
- **NEVER** generate a fixture without at least one target (orphan fixtures are invalid).

## Coverage Closure
Before emitting, verify:
- Every FR acceptance criterion in `spec/04_fr_list.json` has ≥1 fixture with a matching `targets` entry referencing that `fr_id`.
- Every `api_id` in `spec/05_interface_contracts.json` has ≥1 contract-mode fixture covering its request/response shape.
- Every `inv_id` with `severity: error` in `spec/06_invariants.json` has a negative-case fixture that verifies the invariant is enforced.
- Performance-critical `nfr_id` values from `spec/07_nfrs.json` have benchmark or load-test fixtures.
- All `targets[*].id` values resolve to IDs present in the referenced upstream spec files.
- If any acceptance criterion cannot be expressed as a fixture: add a gap question (Clarify mode) rather than omitting the test case.
- [ ] Every upstream ID from ingested context has been consumed
- [ ] No placeholder tokens remain (TBD, TODO, FIXME, XXX)
- [ ] All required fields populated from actual upstream data (not hallucinated)
- [ ] Every high-priority FR (`priority: high`) has at least one fixture covering its happy path
- [ ] Every FR with error conditions has at least one fixture covering the failure path
- [ ] Fixture IDs in this step match the `fixture_ref` values used in Step 04 FR acceptance criteria
- [ ] Every fixture has a valid `target` ID referencing an existing FR or acceptance criterion
- [ ] No ID referenced by this step conflicts with the same ID defined in a sibling step

## Step-Specific Completeness Checklist
- Fixtures cover happy-path, edge, and failure scenarios for high-priority FRs and APIs.
- Mix `mode` values across layers (unit, contract, e2e, redteam) to prove behavior.
- Each fixture has minimal `input` and precise `expected` output/state; ambiguous assertions are avoided.
- `targets` link fixtures to FRs/APIs/NFRs/invariants to enable coverage reporting.
- Tag important scenarios (e.g., `smoke`, `load`) for CI gating.

## Cross-Step Synthesis Notes
- **contract mode**: `expected` MUST have `status`, `body`, and optionally `headers`.
- **expected**: MUST contain the exact expected payload fields and values as defined by the `output_schema_ref` in `spec/05_interface_contracts.json`; MUST include error shapes (status code + error body) for negative cases.

## Best Practices
- **Coverage**: Cover happy-path, edge, and failure scenarios by mixing `mode` values (unit, contract, e2e, redteam).
- **Trace**: Use `targets` to reference FRs, APIs, NFRs, or invariants so coverage reports stay accurate.
- **Minimalism**: Keep `input` and `expected` payloads to the minimum fields required to prove the requirement (only fields referenced in the FR acceptance criteria or API request/response schemas), reusing `term_id` values from `spec/03_glossary.json`.
- **Gating**: Tag fixtures (e.g., `smoke`, `load`) to guide CI gating and spec-to-impl planning.

## Common Pitfalls
- **Orphans**: Creating fixtures without trace links, which prevents coverage tooling from counting them.
- **Stale Docs**: Treating fixtures as documentation rather than executable payloads, leading to mismatch with generated tests.
- **Complexity**: Overloading fixtures with multiple expectations, making failures hard to diagnose.
- **Drift**: Forgetting to update fixtures when interface contracts version, causing format mismatches.

# Clarification Questions
- Which acceptance criteria lack fixtures today? Prioritize those first.
- What are the top negative/error scenarios (auth, validation, conflicts, rate limits) that must be encoded?
- Which inputs/outputs are necessary and sufficient to prove the behavior? Any non-deterministic fields to ignore?
- Which scenarios must run as smoke/contract in CI vs e2e? Any red-team cases to add now?

## Invariant Evaluation Sample

If Step 06 declares any invariants in a runtime-evaluable language (`cel` or `jsonlogic`), the project needs a dedicated sample fixture that provides the evaluation context for `invariants-check`. Without it, the CI gate added in Step 12 cannot exercise the rules and will either report zero evaluable rules or fail outright.

**Location.** Write the sample to `spec/samples/invariants_sample.json` in the project's spec directory. This is a dedicated file — do not embed it in `spec/08_fixtures.json`. Its shape (a context-only document) and its lifecycle (tracks Step 06, not Step 05) are different from request/response fixtures.

**Shape.** A single JSON document that populates every variable path referenced by the CEL or JSONLogic expressions in `spec/06_invariants.json`. The sample should represent one consistent happy-path scenario in which every invariant evaluates to `true`.

**Derivation procedure.** Walk every expression in Step 06, extract all variable references (e.g. `post.status`, `request.user.role`, `response.headers.cache_control`), take the union of those paths, and populate each one with a realistic value drawn from Step 05 contracts or Step 08 fixture data. Use concrete values — never `"TBD"` or other sentinels. Keep CEL-compatible key names (alphanumeric plus underscores); map hyphenated header names or similar to underscore form in the sample.

**Maintenance contract.** Any PR that adds, modifies, or removes an invariant in Step 06 MUST update this sample in the same PR. This is part of downstream replay discipline. Once Step 12 wires `invariants-check` into CI, a broken sample breaks CI.

**Verification.** After authoring or updating the sample, run:

```bash
./tools/run_specdev.sh invariants-check <spec_dir> \
  --sample spec/samples/invariants_sample.json \
  --repo-root <toolkit_root> \
  [--spec-root ./spec] [--git-root .]
```

Iterate until every rule reports `evaluable=true` and `result=true`. Any rule that stays unevaluable signals either a missing variable path in the sample or a malformed expression in Step 06 — fix the true root cause; do not weaken the sample to hide the problem. Run with `--strict` (or `SPECDEV_INVARIANTS_STRICT=1`) once the sample is complete so unevaluable rules become CI errors.

**When no sample is needed.** If every invariant in Step 06 uses a non-runtime language (`prose`, `informal`, or similar) and none are runtime-evaluable, the sample file is not required. Make this determination explicitly by inspecting `spec/06_invariants.json` — do not assume.

See also: Step 06 (`prompt_06_invariants.md`) for invariant authoring, and Step 12 (`prompt_12_ci_gates.md`) for the CI gate that consumes this sample.

# Schema Reference
- Schema URI: vc:08-fixtures
- Schema File: schema/08_fixtures.schema.json
- Schema Registry: tools/schema_registry.json

# Output Contract
```json
{
  "$schema": "vc:08-fixtures",
  "id": "fixtures-catalog",
  "owner": "api",
  "created_at": "2025-01-01T00:00:00Z",
  "fixtures": [
    {
      "fixture_id": "fixture-auth-login-success",
      "mode": "contract",
      "input": {
        "email": "user@example.com",
        "password": "valid-password"
      },
      "expected": {
        "status": 200
      },
      "targets": [{ "type": "validates", "id": "api-auth-login" }],
      "tag_ref": { "id": "cn:core:tag:smoke", "kind": "tag" }
    }
  ],
  "canonical_refs_used": []
}
```
