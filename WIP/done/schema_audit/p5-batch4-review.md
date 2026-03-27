# Batch 4 Review: Schema Audit FIX-035 through FIX-045

**Reviewer**: Claude Opus 4.6
**Date**: 2026-03-19
**Test Suite Result**: 1271 passed (0 failures)

---

## Summary

**Verdict: PASS with 3 non-blocking findings (orphaned prompt/doc references)**

All schema changes are structurally correct, validators are updated, test fixtures pass, and no orphaned old field names remain in schemas, validators, or test files. Three prompt/doc files still reference the old `request_schema_ref`/`response_schema_ref` names and need updating.

---

## FIX-by-FIX Verification

### FIX-035: Step 05 — Conditional method validation by protocol
**Status: PASS**

- Schema (`schema/05_interface_contracts.schema.json`):
  - `method` field at line 49-52: `type: string`, `minLength: 1` (any non-empty string for non-HTTP)
  - `allOf[0].if/then` at lines 198-214: when `protocol == "http"`, constrains `method` to `$ref: httpMethod` atom (GET/POST/PUT/DELETE/PATCH/OPTIONS/HEAD)
  - Conditional validation is structurally correct JSON Schema (if/then inside allOf)
- `path` field (renamed from `route`) at line 45: present with correct description

### FIX-036: Step 05 — Extended parameters[].in enum
**Status: PASS**

- `parameters[].in` enum at lines 82-94 now has 11 values: `query, path, header, body, cookie, argv, stdin, env, config, payload, metadata`
- Description updated to cover HTTP, gRPC, CLI parameter locations

### FIX-037: Step 15 — Field renames
**Status: PASS**

- `project_skeleton` (was `service_skeleton`): line 23, in required array at line 12
- `interface_map` (was `route_map`): line 45, NOT in required array (made optional per fix plan)
- `interface_ref` (was `api_ref`): line 52, in items required array at line 66
- Validator (`tools/specdev_tools/validation/validators/step_15.py`): all references use new names (`project_skeleton`, `interface_map`, `interface_ref`)
- No orphaned old names in schema or validator

### FIX-038+045: Step 12 — CI-provider-agnostic descriptions
**Status: PASS**

- `runner_labels` (line 96): description mentions GitHub Actions, GitLab CI, Jenkins as examples
- `token_permissions` (line 108): description references GitHub Actions permissions, GitLab CI job permissions
- `environment_protection` (line 111): description mentions GitHub environment protection, GitLab protected environments
- Sub-fields `required_reviewers` and `wait_timer_minutes` also have CI-agnostic descriptions

### FIX-039: Step 02a — Removed hardcoded environment requirements
**Status: PASS**

- `environments` at line 38: `minProperties: 1` (was `required: [dev, ci, staging, prod]`)
- `propertyNames` validates against `environmentName` pattern
- Test fixture `invalid_empty_env.json` tests empty-object env `{}` (minProperties violation)
- Valid minimal fixture has custom env names, confirming flexibility

### FIX-040: Core collections — environmentName pattern
**Status: PASS**

- `environmentName` in `schema/core/collections.schema.json` line 229-233: `type: string`, `pattern: ^[a-z][a-z0-9_-]*$`
- No longer a closed enum; any lowercase alphanumeric-with-hyphens-and-underscores string is valid
- Description: "Common values: dev, ci, staging, prod. Projects may define custom environments."

### FIX-041: Step 16 — implemented_interfaces and layer pattern
**Status: PASS**

- `implemented_interfaces` (was `implemented_endpoints`): confirmed at line 1775 of schema
- In `required` array at line 1827
- `checklist[].layer`: `type: string`, `pattern: ^[a-z][a-z0-9_-]*$` (was closed enum)
- Description: "Implementation layer (examples: db, model, service, api, integration, tests, docs, config, security)."

### FIX-042: Step 16 — "interface" in drift.checks[].target enum
**Status: PASS**

- `drift.checks[].target` enum at lines 1117-1125: `["api", "interface", "schema", "nfr", "invariant", "fixture", "config"]`
- "interface" added as second value

### FIX-043: Step 10 — evidence_source_by_phase relaxed
**Status: PASS**

- `evidence_source_by_phase` at lines 97-104: `type: object`, `minProperties: 1`, `additionalProperties: { type: string }`
- No required phase names (was previously requiring specific phases)
- Still requires at least one entry

### FIX-044: Step 05 — Field renames (route->path, schema refs)
**Status: PASS**

- `path` (was `route`): line 45-48
- `input_schema_ref` (was `request_schema_ref`): line 54-57
- `output_schema_ref` (was `response_schema_ref`): line 58-61
- No orphaned old names in schema properties or required arrays

---

## Backward Compatibility

### Step 05 Validator — route->path fallback
**Status: CORRECT**

The validator at `tools/specdev_tools/validation/validators/step_05.py` line 17 has proper backward compatibility:
```python
route = api.get("path") or api.get("route")  # schema uses 'path'; fallback to legacy 'route'
```
This ensures existing spec files using the old `route` field name still validate correctly for duplicate detection.

---

## Orphaned Reference Search

### Schemas, Validators, Tests, Spec Files
**All clean** — zero orphaned references to old field names (`service_skeleton`, `route_map`, `implemented_endpoints`, `request_schema_ref`, `response_schema_ref`) in:
- `schema/` directory
- `tools/specdev_tools/` directory
- `tests/` directory
- `spec/` directory

### `api_ref` in test_linter_utils.py
**NOT an orphan** — the test at line 175 tests generic `_ref`-suffix field collection logic in `collect_ids_and_refs()`, which handles any field ending in `_ref`. The test value `"api_ref"` is a valid generic example, not a reference to the renamed Step 15 field.

---

## Findings: Orphaned References in Prompts and Docs

### FINDING-B4-001: prompt_05_interface_contracts.md — old field names
**Severity**: Non-blocking (prompt text, not validation logic)
**File**: `prompts/prompt_05_interface_contracts.md`
**Lines**: 67, 118, 127
**Issue**: Still references `request_schema_ref` and `response_schema_ref` (should be `input_schema_ref` and `output_schema_ref`)

### FINDING-B4-002: prompt_08_fixtures.md — old field name
**Severity**: Non-blocking (prompt text)
**File**: `prompts/prompt_08_fixtures.md`
**Line**: 129
**Issue**: References `response_schema_ref` (should be `output_schema_ref`)

### FINDING-B4-003: docs/developers/workflows/discovery.md — old field names
**Severity**: Non-blocking (documentation)
**File**: `docs/developers/workflows/discovery.md`
**Line**: 70
**Issue**: References `request_schema_ref` and `response_schema_ref` (should be `input_schema_ref` and `output_schema_ref`)

### Note: changelog/v0.2.0.md
The `route_map` reference in `changelog/v0.2.0.md` line 215 is **historical documentation** describing a past change. This is correct and should NOT be updated.

---

## Test Suite

```
1271 passed in 41.43s
```

All tests pass. No regressions introduced by Batch 4 changes.

---

## Cascade Update Summary

| Artifact Type | Updated? | Notes |
|---|---|---|
| Schemas | YES | All renames applied, no orphans |
| Validators | YES | step_05 has backward compat, step_15 uses new names |
| Test fixtures | YES | All fixtures use new names, all pass |
| Python tools | YES | No old references in tools/ |
| Prompts | **NO** | 3 orphaned refs in prompt_05, prompt_08 |
| Docs | **NO** | 1 orphaned ref in discovery.md |
| Spec data files | YES | No old references |
| CI/Scripts | YES | No old references |

---

## Recommended Follow-up

1. Update `prompts/prompt_05_interface_contracts.md` lines 67, 118, 127: `request_schema_ref` -> `input_schema_ref`, `response_schema_ref` -> `output_schema_ref`
2. Update `prompts/prompt_08_fixtures.md` line 129: `response_schema_ref` -> `output_schema_ref`
3. Update `docs/developers/workflows/discovery.md` line 70: `request_schema_ref` -> `input_schema_ref`, `response_schema_ref` -> `output_schema_ref`
