# P5 Batch 2 Review — FIX-011 through FIX-019

**Reviewer**: Claude Opus 4.6 (1M context)
**Date**: 2026-03-19
**Verdict**: PASS with 1 MEDIUM advisory

---

## 1. Schema Structure Verification (all 19 step schemas)

All 19 step schemas verified. Every schema has:

| Check | Result |
|-------|--------|
| `$id` at root level | PASS (all 19) |
| `allOf` with step_base `$ref` as first element | PASS (all 19) |
| Step-specific object as second `allOf` element | PASS (all 19) |
| `unevaluatedProperties: false` at root | PASS (all 19) |
| No root-level `additionalProperties: false` | PASS (all 19) |
| Common properties NOT duplicated in step-specific block | PASS — `id`, `owner`, `created_at`, `$schema` come from step_base only |
| Common required entries removed from step-level | PASS — `id`, `owner`, `created_at`, `canonical_refs_used` not in step required |
| Step-specific properties preserved | PASS |
| Step-specific required fields preserved | PASS |

**Note on `canonical_proposals` / `canonical_conflicts`**: These appear in BOTH step_base (as `$ref` to collections) AND step-level schemas (with inline `items` + `default: []`). This is intentional — the step schemas override with specific defaults and constraints. Both declare the same property name, so `unevaluatedProperties: false` correctly treats them as evaluated.

---

## 2. $ref Replacements Verified

| FIX | Atom | Schemas | Status |
|-----|------|---------|--------|
| FIX-012 | `milestoneStatus` | 09 (milestone.status) | PASS — `$ref: atoms/1#milestoneStatus` |
| FIX-013 | `milestoneStatus` + `severityLevel` | 14 (milestone.status, milestone.risk_status) | PASS |
| FIX-014 | `severityLevel` + `referenceType` | 11 (threat.severity, mitigation.type) | PASS |
| FIX-015 | `httpMethod` + `apiProtocol` | 05 (api.method, api.protocol) | PASS |
| FIX-016 | `httpMethod` | 15 (route_map.method) | PASS |
| FIX-017 | `connectionProtocol` | 02 (connection.protocol) | PASS |
| FIX-018 | Step 16 — 3 local `$defs` replaced with core `$refs` | 16 | PASS |

**Step 14 task.status**: Correctly left as inline 3-value enum `["pending", "in_progress", "done"]` — NOT replaced with `milestoneStatus` which adds `"deferred"`. Semantically correct.

---

## 3. Orphaned Reference Checks

| Check | Result |
|-------|--------|
| `additionalProperties` in step schemas at root level | ZERO — all root-level closures use `unevaluatedProperties` |
| `additionalProperties` in nested objects (items, sub-objects) | Present and correct — nested objects properly use `additionalProperties: false` |
| Inline milestone status enums (`pending/in_progress/done/deferred`) | ZERO in step schemas (except Step 14 task.status with 3-value subset — intentional) |
| Inline severity enums (`low/medium/high/critical`) | ZERO |
| Inline HTTP method enums (`GET/POST/...`) | ZERO |
| Inline protocol enums (`http/grpc/...`) | ZERO |
| `#/$defs/severityLevel` in step 16 | ZERO |
| `#/$defs/executionStatus` in step 16 | ZERO |
| `#/$defs/evidenceObject` in step 16 | ZERO |

---

## 4. Schema Registry

`tools/schema_registry.json` — PASS

- `step_base` entry present: `"https://specdev.local/schema/core/step_base/1": "schema/core/step_base.schema.json"`
- All 19 step schemas mapped correctly
- Core schemas (atoms, collections, errors, canon) mapped correctly

---

## 5. Test Verification

### test_schema_contracts.py
- `_collect_all_properties()` helper correctly resolves allOf + step_base `$ref` to collect inherited properties
- Uses `Draft202012Validator` (not Draft7)
- PASS

### test_step_02a.py
- Uses `Draft202012Validator` with registry
- PASS

### Full test suite
```
1271 passed in 41.05s
```
ZERO failures.

---

## 6. Advisory: allOf-Unaware Code in generation/ (MEDIUM)

Three functions in `tools/specdev_tools/generation/` read `schema.get("properties")` and `schema.get("required")` directly from the root level, which will return empty results for allOf-wrapped schemas:

| File | Line | Function |
|------|------|----------|
| `prompt_schema_sync.py` | 109-110 | `_load_contract()` |
| `prompt_generator.py` | 458-459 | `_extract_required_fields()` |
| `schema_differ.py` | 410-411 | `_diff_fields()` |

**Impact**: These functions will silently miss all step-specific required fields and properties when operating on the new allOf schemas. They will return empty/incomplete results rather than crashing.

**Severity**: MEDIUM — prompt-sync, prompt generation, and schema diffing may produce incomplete results. Not a test blocker (tests pass because test helpers were updated), but a correctness issue for CLI commands `prompt-sync`, prompt generation, and `align diff`.

**Recommendation**: Update these three functions to resolve allOf before reading properties/required, similar to the `_collect_all_properties()` helper in test_schema_contracts.py. This should be added to the fix plan for a future batch.

---

## 7. Step 16 `$defs`

Step 16 retains ONE local `$def`:
- `specRef` — a step-16-specific object with `line_range` and `commit_hash` fields not present in core atoms

This is correct. The three previously local `$defs` (`severityLevel`, `executionStatus`, `evidenceObject`) have been replaced with core `$ref`s.

---

## Summary

| Category | Status |
|----------|--------|
| Schema structure (allOf + unevaluatedProperties) | PASS |
| $ref replacements (6 atom types) | PASS |
| Orphaned references | CLEAN |
| Schema registry | PASS |
| Tests (1271) | ALL PASS |
| allOf awareness in generation/ code | MEDIUM advisory — 3 functions need update |

**Overall**: Batch 2 is structurally sound. The only issue is the generation-layer allOf awareness gap, which should be tracked for a future fix batch.
