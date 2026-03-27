# P5 Batch 0+1 Review -- Schema Audit Implementation

**Date**: 2026-03-19
**Reviewer**: Claude Opus 4.6 (1M context)
**Test suite**: 1271 passed, 0 failed (36.83s)

---

## Overall Verdict: CLEAN

All Batch 0 and Batch 1 changes are correctly implemented. No blocking issues found. Two low-severity advisory notes documented below.

---

## 1. File-by-File Verification

### FIX-001: schema/core/step_base.schema.json

- **Structure**: Valid JSON, correct `$schema`, `$id` (`https://specdev.local/schema/core/step_base/1`), `$anchor` (`stepBase`).
- **$ref URIs**: All 5 `$ref` values use the established `https://specdev.local/schema/core/{module}/1#{anchor}` pattern, consistent with other core schemas.
- **Required array**: `["id", "owner", "created_at", "canonical_refs_used"]` -- correctly includes only the 4 universally required fields.
- **Excluded fields verified**:
  - `generation_quality` -- NOT present (correct per D1-D4)
  - `seed_refs` -- NOT present (correct)
  - `spec_refs_ingested` -- NOT present (correct per D3)
  - `coverage_gaps` -- NOT present (correct per D4)
- **Optional fields verified**:
  - `canonical_proposals` -- present in properties, NOT in required (correct per D9)
  - `canonical_conflicts` -- present in properties, NOT in required (correct per D10)
  - `_migration_notes` -- present as optional array of strings (correct)
- **additionalProperties**: intentionally omitted (correct -- composable fragment, documented in description)

### FIX-002 to FIX-006: schema/core/atoms.schema.json (7 new atoms)

All 7 new atoms verified:

| Atom | $anchor | Type | Values | OK |
|------|---------|------|--------|----|
| severityLevel | severityLevel | string enum | low, medium, high, critical | YES |
| milestoneStatus | milestoneStatus | string enum | pending, in_progress, done, deferred | YES |
| referenceType | referenceType | string enum | fr, api, nfr, inv, fixture, doc, code, capability | YES |
| httpMethod | httpMethod | string enum | GET, POST, PUT, DELETE, PATCH, OPTIONS, HEAD | YES |
| connectionProtocol | connectionProtocol | string enum | http, grpc, event, rpc, db, file | YES |
| apiProtocol | apiProtocol | string enum | http, grpc, ws, mqtt | YES |

Each has: correct `$anchor` matching `$defs` key, appropriate `description`, correct `type: "string"`, valid `enum` array. `milestoneStatus` includes `default: "pending"` (acceptable).

Note: The fix plan listed 7 atoms but `severityLevel` through `apiProtocol` is 6. Reviewing the fix plan more carefully, FIX-002 was `severityLevel`, FIX-003 was `milestoneStatus`, FIX-004 was `referenceType`, FIX-005 was `httpMethod`, and FIX-006 covered both `connectionProtocol` and `apiProtocol`. Total: 6 new atoms across 5 FIX items. All present and correct.

### FIX-007: stageName removal from collections.schema.json

- `stageName` definition: completely removed from `schema/core/collections.schema.json` (grep confirms zero hits in `schema/` directory)
- `environmentName` retained at line 197-206 with the same enum `["dev", "ci", "staging", "prod"]`

### FIX-008: canonicalId $ref in collections.schema.json

- Line 94: `"$ref": "https://specdev.local/schema/core/canon/1#canonicalId"` -- correctly references canon schema
- No inline `^cn:` patterns exist anywhere in schema files except `canon.schema.json` (the canonical definition at line 39)

### FIX-009: owner -> canonOwner rename in canon.schema.json

- `$defs/canonOwner` at line 46 with `$anchor: "canonOwner"` -- correct
- `owners` array items at line 143: `"$ref": "#/$defs/canonOwner"` -- correctly updated
- Grep for `canon/1#owner` (old anchor): zero hits across entire codebase -- clean

### FIX-010: executionStatus and evidenceObject in collections.schema.json

- `executionStatus` at lines 509-519: enum `["passed", "failed", "blocked", "partial"]`, has `$anchor`, description -- correct
- `evidenceObject` at lines 520-553: object with `type` (enum: log/snippet/screenshot/reference), `content` (minLength: 20), optional `evidence_ref`/`path`/`section`, `additionalProperties: false`, required `["type", "content"]` -- correct

---

## 2. Orphaned Reference Check

| Pattern | Expected hits outside WIP/ | Actual | Status |
|---------|---------------------------|--------|--------|
| `stageName` in schema/ | 0 | 0 | CLEAN |
| `stageName` in tools/ | 0 | 0 | CLEAN |
| `stageName` in tests/ | 0 | 0 | CLEAN |
| `canon/1#owner` (old anchor) | 0 | 0 | CLEAN |
| Inline `^cn:` pattern in schema/ (excl. canon.schema.json) | 0 | 0 | CLEAN |

---

## 3. FIX-007 Downstream Updates Verified

| File | Change | Verified |
|------|--------|----------|
| schema/07_nfrs.schema.json (line 71) | `$ref` now points to `#environmentName` | YES |
| tools/specdev_tools/validation/canon_schema_alignment.py (line 15) | Pairing uses `environmentName` not `stageName` | YES |
| tests/unit/generation/test_schema_contracts.py (line 79) | `expected_refs` for 07_nfrs uses `#environmentName` | YES |
| tests/unit/test_cli.py | No `stageName` references remain | YES (grep: 0 hits) |

---

## 4. Missed Downstream Consumers

One stale reference found in **documentation only** (not code/tests):

- `docs/plans/phase_0_governance_plan.md` lines 752, 776, 928: still references `stageName` in three locations.

**Severity**: INFORMATIONAL -- This is a historical planning document, not active code. The references describe what the schema *used to* have. No functional impact. Can be updated opportunistically.

---

## 5. Test Suite Results

```
1271 passed in 36.83s
```

- Zero failures, zero errors, zero warnings
- All schema contract tests pass (including `test_d022_targeted_schemas_reuse_shared_environment_stage_and_dependency_anchors` which validates `#environmentName` in 07_nfrs.schema.json)
- All canonical autofix tests pass (including NFR tests that exercise the updated schema)

---

## 6. Advisory Notes (non-blocking)

### NOTE-1: step_base.schema.json not yet registered in schema_registry.json (LOW)

`step_base.schema.json` exists but has no entry in `tools/schema_registry.json`. This is expected -- the fix plan defers registry registration to a later batch (the FIX that adds `core/step_base/1 -> schema/core/step_base.schema.json`). Currently no code resolves this URI at runtime, so no breakage. Will become needed when FIX-019 (Batch 2) wires step schemas to `allOf: [{$ref: stepBase}, ...]`.

### NOTE-2: docs/plans/phase_0_governance_plan.md has stale stageName references (LOW)

Three references to `stageName` remain in a historical planning document. Non-functional, can be cleaned up opportunistically.

---

## Summary

| Check | Result |
|-------|--------|
| step_base.schema.json structure & exclusions | PASS |
| 6 new atoms in atoms.schema.json | PASS |
| stageName removed from collections.schema.json | PASS |
| canonicalId $ref in collections.schema.json | PASS |
| canonOwner rename in canon.schema.json | PASS |
| executionStatus + evidenceObject added | PASS |
| Orphaned references (stageName, canon#owner, inline canonicalId) | CLEAN |
| FIX-007 downstream updates (07_nfrs, canon_schema_alignment, tests) | PASS |
| Missed downstream consumers | CLEAN (1 doc-only stale ref, informational) |
| Test suite (1271 tests) | ALL GREEN |
