# ALIGN-1: $ref/$defs DRY Authoring — Execution Plan

> **Review status**: Plan v2 — incorporates findings from 4-agent exhaustive review (C1, H1-H5, M1-M8, L1-L4).

## Objective

Extract duplicated inline enum definitions from step schemas into shared `$defs` in `schema/core/atoms.schema.json`, then replace inline definitions with `$ref` references. This eliminates enum duplication across step schemas, establishes a single source of truth for domain vocabulary, and makes future enum changes atomic.

## Pre-Existing Coverage (ALIGN-1 Audit Closure)

The ALIGN-1 description called out four categories of duplication. Three are **already resolved** — this plan addresses only the fourth:

| Category | Status | Evidence |
|----------|--------|----------|
| **id format constraints** | ALREADY RESOLVED | `kebabId` in `atoms.schema.json` is `$ref`'d by all step schemas. Step-specific prefixed patterns (e.g., `^nfr-…$` in 07, `^ext-…$` in 13) are intentionally more restrictive than the generic atom and cannot use it. |
| **owner enums** | ALREADY RESOLVED | `owner` in `atoms.schema.json` is `$ref`'d by step_base and all step schemas that need it (02, 05, 07, etc.). |
| **trace_type definitions** | ALREADY RESOLVED | `traceRef` in `collections.schema.json` is `$ref`'d by all step schemas. No inline trace definitions remain. |
| **Inline enum duplication** | THIS PLAN | 17 inline enums across 9 step schemas → 14 new core atoms with `$ref`. |

## Scope

### IN SCOPE — Tier 1: True Duplications (identical enum in 2+ schemas)

| Atom Name | Enum Values | Schemas Using It | JSON Path |
|-----------|-------------|------------------|-----------|
| `milestoneStatus` | `["pending","in_progress","done","deferred"]` | 09, 14 | `$.milestones[*].status` |
| `severityLevel` | `["low","medium","high","critical"]` | 11, 14, 16 `$defs` | `$.threats[*].severity`, `$.milestones[*].risk_status`, `$defs.severityLevel` |

### IN SCOPE — Tier 2: Canonical Vocabulary Centralization (single-use today, extracted for single-source-of-truth)

> **Rationale**: These are not DRY fixes (they appear in only one schema each). They are extracted because they represent **canonical domain vocabulary** — architectural types, protocols, security mechanisms, quality categories — that should have a single authoritative definition in core. This follows the same principle as `owner`, `kebabId`, and `stageName` which are also single-definition atoms referenced by many schemas. When a second consumer appears, the atom is already available. If atoms.schema.json exceeds ~30 `$defs`, split domain enums into `schema/core/domain_enums.schema.json`.

| Atom Name | Enum Values | Schema | JSON Path |
|-----------|-------------|--------|-----------|
| `httpMethod` | `["GET","POST","PUT","PATCH","DELETE"]` | 05 | `$.apis[*].method` |
| `httpMethodFull` | `["GET","POST","PUT","DELETE","PATCH","OPTIONS","HEAD"]` | 15 | `$.interface_map[*].method` |
| `componentType` | `["service","db","queue","cache","job","ui","lib","external"]` | 02 | `$.components[*].type` |
| `connectionProtocol` | `["http","grpc","event","rpc","db","file"]` | 02 | `$.connections[*].protocol` |
| `apiProtocol` | `["http","grpc","ws","mqtt"]` | 05 | `$.apis[*].protocol` |
| `trustBoundary` | `["internal","partner","public"]` | 02 | `$.connections[*].trust_boundary` |
| `connectionAuth` | `["none","basic","oauth2","jwt","mTLS","key"]` | 02 | `$.connections[*].auth` |
| `apiSecurity` | `["none","api-key","oauth2","jwt","mTLS"]` | 05 | `$.apis[*].security` |
| `nfrCategory` | `["latency","throughput","availability","durability","cost","security","privacy","maintainability","usability","portability","energy"]` | 07 | `$.nfrs[*].category` |
| `testingMode` | `["unit","contract","e2e","redteam"]` | 08 | `$.fixtures[*].mode` |
| `threatCategory` | `["authn","authz","business_logic","transport","data_privacy"]` | 11 | `$.threats[*].category` |
| `messageReliability` | `["best-effort","at-least-once","exactly-once"]` | 02 | `$.connections[*].reliability` |

### IN SCOPE — Tool Code Update (Review Finding C1)

| File | Change | Reason |
|------|--------|--------|
| `tools/specdev_tools/validation/canon_schema_alignment.py` | Update `_ENUM_CANON_PAIRINGS` line 17: path for `nfr_category` moves from `07_nfrs.schema.json` to `core/atoms.schema.json` | After Batch 3, the inline enum at `07_nfrs[…].category.enum` no longer exists — the JSON path would fail with E553 |

### OUT OF SCOPE — Intentionally Kept Inline (Exhaustive)

**Step-specific enums (single-use, unlikely to be reused):**

| Enum | Schema | Values | Reason |
|------|--------|--------|--------|
| `capabilityScope` | 01 | `["in","out","future"]` | Step-specific scoping concept, 3 values |
| `rateLimitScope` | 02 | `["ip","client","token","global"]` | Nested in `rate_limit` object, specific to rate-limit context |
| `componentTag` | 02 | 20-value enum | Large step-specific classification taxonomy |
| `expressionLanguage` | 06 | `["jsonlogic","cel","text"]` | Tied to invariant rule engines |
| `invariantSeverity` | 06 | `["warn","error"]` | Diagnostic severity (validation output), not risk severity. Subset of `errorState.severity` in errors.schema.json. |
| `ciCheckCommand` (pr_rules) | 10 | 13 tooling commands | Tooling-specific, changes when CLI commands change |
| `completenessCategory` | 13a | `["traceability","completeness","quality","ambiguity"]` | Step-specific assessment concept |
| `priority` | 13a | `["high","medium","low"]` | Subset of severityLevel without `critical` — different semantics (urgency vs impact) |
| `buildStatus` | 15 | `["pending","green","red"]` | CI signal semantics, not progress tracking |

**Step 05 specific:**

| Enum | Values | Reason |
|------|--------|--------|
| `parameterIn` | `["query","path","header"]` | OpenAPI-specific parameter location, 3 values, single use |

**Step 12 specific:**

| Enum | Values | Reason |
|------|--------|--------|
| `tokenPermission` | `["read","write","none"]` | CI token permission level, nested in security context |

**Step 16 — local $defs (already structured as local definitions):**

| Enum | Values | Reason |
|------|--------|--------|
| `specRef.type` | `["fr","api","nfr","inv","fixture","doc","code"]` | Includes `code` (absent elsewhere); step-specific code-binding context |
| `executionStatus` | `["passed","failed","blocked","partial"]` | Step-specific execution outcome |
| `evidenceType` | `["log","snippet","screenshot","reference"]` | Step-specific evidence classification |
| `planStatus` | `["active","deferred"]` | Step-specific plan lifecycle, 2 values |
| `docsImpactStatus` | `["required","not_required"]` | Step-specific boolean-like status, 2 values |

**Step 16 — inline enums in deeply nested properties (~19 additional):**

| Category | Enums | Reason |
|----------|-------|--------|
| Checklist item enums | `type` (9 values), `layer` (9 values), `checklist_status` (2 values), `implementation.status` (4 values), `actions[*].type` (4 values) | Step-specific checklist-driven implementation vocabulary; tightly coupled to step 16's CDI protocol |
| Ambiguity enums | `source` (5 values), `severity` (2 values), `status` (4 values) | Step-specific ambiguity tracking fields |
| Drift detection enums | `checks[*].target` (6 values), `checks[*].method` (4 values) | Step-specific observability fields |
| Review enums | `findings[*].type` (7 values), `findings[*].severity` (4 values), `verdict` (3 values), `fixture_status.test_results[*].status` (3 values) | Step-specific review protocol vocabulary |
| Status signal enums | `ci_status` (2 values: green/red), `security_status` (2 values), `deployments[*].status` (3 values), `deployments[*].env` allOf subset (3 values) | Step-specific CI/deployment signals |

All step 16 inline enums are kept out of scope: they are deeply coupled to the CDI (Checklist-Driven Implementation) protocol, used only within step 16, and would not be meaningful in other steps.

**Step 14 specific:**

| Enum | Values | Reason |
|------|--------|--------|
| `taskStatus` | `["pending","in_progress","done"]` | Strict subset of milestoneStatus without `deferred`; different context (tasks complete or not, they don't get deferred — milestones do) |

**Step 11 specific:**

| Enum | Values | Reason |
|------|--------|--------|
| `mitigationType` | `["fr","api","nfr","inv","fixture","doc","capability"]` | 6/7 values overlap with 16's specRef.type, but semantic difference: mitigation evidence types include `capability` (high-level feature covers risk) and exclude `code` (code isn't evidence of threat mitigation). Unifying would conflate "what mitigates a threat" with "what binds to implementation code". |

**Infrastructure schemas:**

| Enum | Schema | Values | Reason |
|------|--------|--------|--------|
| `sourceType` | seed_manifest | `["doc","spec","config","other"]` | Seed-specific document classification |
| `coverageMode` | step_order | `["warn","error"]` | Infrastructure config, not domain vocabulary |

---

## Design Decisions

### D1: $anchor Naming Convention
Follow existing pattern in atoms.schema.json: **camelCase** (`milestoneStatus`, `severityLevel`, etc.).

### D2: Atom Shape — Type + Enum + Description, No Default
Atoms define `type`, `enum`, `description`, and `$anchor`. Defaults are NOT included in atoms because different consumers may want different defaults (e.g., `severityLevel` has `default: "low"` in 14 but no default in 11). Consumers add `default` as a sibling keyword alongside `$ref`.

**Exception**: `milestoneStatus` includes `default: "pending"` because ALL consumers (09, 14) use the same default. (Note: this is the first use of `$ref` + sibling `default` in this codebase — the pattern is valid per Draft 2020-12 and proven by `jsonschema`/`referencing` library behavior.)

### D3: $ref Sibling Keywords (Draft 2020-12)
In JSON Schema Draft 2020-12, sibling keywords alongside `$ref` ARE evaluated. This means:
```json
"risk_status": {
  "$ref": "https://specdev.local/schema/core/atoms/1#severityLevel",
  "default": "low",
  "description": "Risk level associated with this milestone."
}
```
This is valid — `$ref` resolves `type`+`enum`, `default` and `description` apply as siblings. Verified: 271 existing `$ref` + sibling `description` instances in codebase prove the pattern.

### D4: httpMethod vs httpMethodFull — Two Separate Atoms
Step 05 uses 5 methods (REST standard), Step 15 uses 7 (adds OPTIONS/HEAD for CORS/health). These are intentionally different scopes — a single unified enum would be too permissive for 05.

### D5: connectionAuth vs apiSecurity — Two Separate Atoms
Connection auth (02) uses `basic`/`key`, API security (05) uses `api-key`. These are genuinely different security contexts with different value sets.

### D6: severityLevel in 16_impl_context $defs
Step 16 currently defines `severityLevel` in its local `$defs`. After extraction to core, the local `$defs.severityLevel` is REPLACED with a `$ref` to the core atom. All internal `$ref: "#/$defs/severityLevel"` references within step 16 continue to work — the local `$defs` entry delegates to core. This creates a 2-hop resolution (pragmatic: avoids touching all internal refs in the largest schema).

### D7: No Python Validator Changes Needed
Python validators (step_15, step_11, hallucination_lint, etc.) hardcode enum values for defense-in-depth validation. These are NOT affected by this work because:
1. We're changing HOW the schema defines enums (inline → $ref), not WHAT the enum values are
2. Schema validation runs first; Python validators add business-logic checks
3. The hardcoded Python sets are independent of schema $ref resolution

**Exception**: `canon_schema_alignment.py` has a hardcoded JSON path for the `nfr_category` pairing (line 17) that MUST be updated when the inline enum moves to core atoms. See Batch 3.

### D8: Test Fixtures Unaffected
All 130 test fixtures use enum VALUES in their JSON data. Since enum values don't change, all fixtures continue to validate without modification. Verified: no tests assert on jsonschema-specific error message text or error paths that would change due to `$ref` indirection.

### D9: `unevaluatedProperties: false` Unaffected
All step schemas use `unevaluatedProperties: false` at root level. This works correctly with `$ref` inside `properties` because the `$ref` is within an `allOf` member's `properties` declaration, so the property IS "evaluated". Confirmed for Draft 2020-12.

### D10: Registry Requires No Changes
The `referencing` library automatically discovers `$anchor` declarations within registered schemas. Since `atoms.schema.json` is already registered at URI `https://specdev.local/schema/core/atoms/1`, any new `$anchor` entries added to its `$defs` are automatically resolvable. No changes to `schema_registry.json` or `registry.py` are needed.

---

## Pre-Execution Verification

Before any batch executes:

```bash
# Baseline: record current test count and pass rate
pytest tests/ -q 2>&1 | tail -3

# Baseline: validate all spec fixtures
./tools/run_specdev.sh validate-all spec --repo-root . --json

# Baseline: canon-schema-alignment (must pass before AND after)
./tools/run_specdev.sh canon-schema-alignment --repo-root .
```

---

## Batch 0: Create New Atoms in Core

**Target file**: `schema/core/atoms.schema.json`

**Action**: Add 14 new `$defs` entries to the existing atoms file. Each entry follows the pattern:
```json
"milestoneStatus": {
  "$anchor": "milestoneStatus",
  "type": "string",
  "enum": ["pending", "in_progress", "done", "deferred"],
  "default": "pending",
  "description": "Progress status for milestones: pending (not started), in_progress, done, or deferred."
}
```

**New atoms (14 total)**:

1. `milestoneStatus` — `["pending","in_progress","done","deferred"]`, default: `"pending"` (D2 exception — all consumers agree)
2. `severityLevel` — `["low","medium","high","critical"]`, no default
3. `httpMethod` — `["GET","POST","PUT","PATCH","DELETE"]`, no default
4. `httpMethodFull` — `["GET","POST","PUT","DELETE","PATCH","OPTIONS","HEAD"]`, no default
5. `componentType` — `["service","db","queue","cache","job","ui","lib","external"]`, no default
6. `connectionProtocol` — `["http","grpc","event","rpc","db","file"]`, no default
7. `apiProtocol` — `["http","grpc","ws","mqtt"]`, no default
8. `trustBoundary` — `["internal","partner","public"]`, no default
9. `connectionAuth` — `["none","basic","oauth2","jwt","mTLS","key"]`, no default
10. `apiSecurity` — `["none","api-key","oauth2","jwt","mTLS"]`, no default
11. `nfrCategory` — `["latency","throughput","availability","durability","cost","security","privacy","maintainability","usability","portability","energy"]`, no default
12. `testingMode` — `["unit","contract","e2e","redteam"]`, no default
13. `threatCategory` — `["authn","authz","business_logic","transport","data_privacy"]`, no default
14. `messageReliability` — `["best-effort","at-least-once","exactly-once"]`, no default

**Verification**:
```bash
# Validate atoms schema is valid JSON
python3 -c "import json; json.load(open('schema/core/atoms.schema.json'))"
# Full test suite (atoms addition is additive — no breakage expected)
pytest tests/ -q
```

**Risk**: NONE — purely additive. No existing schema references change.

---

## Batch 1: True Duplications — Steps 09, 14, 16

**Files modified**: 3 step schemas

### 1a. `schema/09_impl_plan.schema.json`
- `$.milestones[*].status`: Replace inline enum with:
  ```json
  "status": {
    "$ref": "https://specdev.local/schema/core/atoms/1#milestoneStatus",
    "description": "Current progress status of the milestone."
  }
  ```
  Note: `default` is in the atom, so no sibling `default` needed.

### 1b. `schema/14_roadmap.schema.json`
- `$.milestones[*].status`: Replace inline enum with `$ref` to `milestoneStatus` (same as 1a)
- `$.milestones[*].risk_status`: Replace inline enum with:
  ```json
  "risk_status": {
    "$ref": "https://specdev.local/schema/core/atoms/1#severityLevel",
    "default": "low",
    "description": "Risk level associated with this milestone."
  }
  ```

### 1c. `schema/16_impl_context.schema.json`
- `$defs.severityLevel`: Replace local definition with `$ref` delegation to core atom:
  ```json
  "severityLevel": {
    "$ref": "https://specdev.local/schema/core/atoms/1#severityLevel"
  }
  ```
- **Internal refs**: All existing `"$ref": "#/$defs/severityLevel"` within step 16 continue to work — the local `$defs` entry delegates to core. No changes to internal refs needed.

**Verification**:
```bash
pytest tests/ -q
pytest tests/unit/validation/ -k "step_09 or step_14 or step_16" -v
pytest tests/integration/ -k "step_09 or step_14 or step_16" -v
```

**Risk**: LOW — enum values unchanged. $ref resolution proven for 229 existing cross-file refs.

---

## Batch 2: HTTP, Protocols, Auth — Steps 02, 05, 15

**Files modified**: 3 step schemas

### 2a. `schema/05_interface_contracts.schema.json`
- `$.apis[*].protocol`: Replace inline enum with `$ref` to `apiProtocol`, retain `description`
- `$.apis[*].method`: Replace inline enum with `$ref` to `httpMethod`, retain `description`
- `$.apis[*].security`: Replace inline enum with `$ref` to `apiSecurity`, retain `description`

### 2b. `schema/15_scaffold.schema.json`
- `$.interface_map[*].method`: Replace inline enum with `$ref` to `httpMethodFull`, retain `description`

### 2c. `schema/02_system_sketch.schema.json`
- `$.components[*].type`: Replace inline enum with `$ref` to `componentType`, retain `description`
- `$.connections[*].protocol`: Replace inline enum with `$ref` to `connectionProtocol`, retain `description`
- `$.connections[*].trust_boundary`: Replace inline enum with `$ref` to `trustBoundary`, retain `description`
- `$.connections[*].auth`: Replace inline enum with `$ref` to `connectionAuth`, retain `description`
- `$.connections[*].reliability`: Replace inline enum with `$ref` to `messageReliability`, retain `description`

**Note on allOf conditionals in 02**: The `allOf` blocks in connections test specific enum values via `if` conditions (e.g., `"trust_boundary": {"enum":["partner","public"]}`, `"protocol": {"enum":["event"]}`). These IF conditions check subsets of values — they do NOT define the enum. The actual enum definition moves to core via `$ref`, but the IF conditions remain inline unchanged. No changes needed to allOf blocks.

**Verification**:
```bash
pytest tests/ -q
pytest tests/unit/validation/ -k "step_02 or step_05 or step_15" -v
pytest tests/integration/ -k "step_02 or step_05 or step_15" -v
```

**Risk**: LOW — same enum values, just sourced via $ref.

---

## Batch 3: Domain Enums — Steps 07, 08, 11 + Tool Code Fix

**Files modified**: 3 step schemas + 1 Python tool file

### 3a. `schema/07_nfrs.schema.json`
- `$.nfrs[*].category`: Replace inline enum with `$ref` to `nfrCategory`, retain `description`

### 3b. `schema/08_fixtures.schema.json`
- `$.fixtures[*].mode`: Replace inline enum with `$ref` to `testingMode`, retain `description`

### 3c. `schema/11_redteam.schema.json`
- `$.threats[*].category`: Replace inline enum with `$ref` to `threatCategory`, retain `description`
- `$.threats[*].severity`: Replace inline enum with `$ref` to `severityLevel`, retain `description`

### 3d. `tools/specdev_tools/validation/canon_schema_alignment.py` (Review Finding C1)
- **Line 17**: Update `_ENUM_CANON_PAIRINGS` entry for `nfr_category`:
  ```python
  # BEFORE:
  ("07_nfrs.schema.json", ["properties", "nfrs", "items", "properties", "category", "enum"], "nfr_category"),
  # AFTER:
  ("core/atoms.schema.json", ["$defs", "nfrCategory", "enum"], "nfr_category"),
  ```
  **Why**: After 3a replaces the inline enum with `$ref`, the old JSON path no longer resolves (the `enum` key is gone, replaced by `$ref`). The canonical alignment check would emit E553 MISSING_ENUM_PATH.

**Verification**:
```bash
pytest tests/ -q
pytest tests/unit/validation/ -k "step_07 or step_08 or step_11" -v
pytest tests/integration/ -k "step_07 or step_08 or step_11" -v
# Explicit canon-schema-alignment check (exercises the updated pairing)
./tools/run_specdev.sh canon-schema-alignment --repo-root .
```

**Risk**: LOW for schema changes. MEDIUM for 3d (must be done atomically with 3a to avoid E553).

---

## Batch 4: Full Verification & Regression Check

**No file changes** — verification only.

```bash
# 1. Full test suite
pytest tests/ -v

# 2. Validate all spec fixtures
./tools/run_specdev.sh validate-all spec --repo-root . --json

# 3. Schema quality lint
./tools/run_specdev.sh spec-quality-lint spec --repo-root .

# 4. Canonical lint
./tools/run_specdev.sh canonical-lint canon --repo-root .

# 5. Canonical integrity
./tools/run_specdev.sh canonical-integrity spec --repo-root .

# 6. Canon-schema alignment (critical — exercises C1 fix)
./tools/run_specdev.sh canon-schema-alignment --repo-root .

# 7. Prompt-schema sync (exercises $ref resolution in prompt validation)
./tools/run_specdev.sh prompt-sync spec --repo-root .

# 8. Verify $ref resolution works for all 14 new atoms
python3 -c "
from specdev_tools.core.registry import SchemaRegistry
from specdev_tools.validation.validate import _registry_for
reg = SchemaRegistry('.')
ref_reg = _registry_for(reg)
print(f'Registry loaded: {len(reg.store)} schemas')
atoms_uri = 'https://specdev.local/schema/core/atoms/1'
for anchor in ['milestoneStatus','severityLevel','httpMethod','httpMethodFull',
               'componentType','connectionProtocol','apiProtocol','trustBoundary',
               'connectionAuth','apiSecurity','nfrCategory','testingMode',
               'threatCategory','messageReliability']:
    resource = ref_reg.resolver(atoms_uri).lookup(f'#{anchor}')
    enum_vals = resource.contents.get('enum', [])
    print(f'  {anchor}: {len(enum_vals)} values ✓')
print('All 14 atoms resolved successfully.')
"
```

**Pass criteria**:
- All tests pass (same count as baseline — currently 1343)
- All spec fixtures validate
- All 14 new atoms resolve via $ref
- `canon-schema-alignment` passes with zero E553/E554 errors
- `prompt-sync` passes
- No new warnings or errors from any linter

---

## Files Modified Summary

| Batch | File | Changes |
|-------|------|---------|
| 0 | `schema/core/atoms.schema.json` | Add 14 new `$defs` entries |
| 1 | `schema/09_impl_plan.schema.json` | 1 inline → $ref (milestoneStatus) |
| 1 | `schema/14_roadmap.schema.json` | 2 inline → $ref (milestoneStatus, severityLevel) |
| 1 | `schema/16_impl_context.schema.json` | 1 local $defs → delegated $ref (severityLevel) |
| 2 | `schema/05_interface_contracts.schema.json` | 3 inline → $ref (httpMethod, apiProtocol, apiSecurity) |
| 2 | `schema/15_scaffold.schema.json` | 1 inline → $ref (httpMethodFull) |
| 2 | `schema/02_system_sketch.schema.json` | 5 inline → $ref (componentType, connectionProtocol, trustBoundary, connectionAuth, messageReliability) |
| 3 | `schema/07_nfrs.schema.json` | 1 inline → $ref (nfrCategory) |
| 3 | `schema/08_fixtures.schema.json` | 1 inline → $ref (testingMode) |
| 3 | `schema/11_redteam.schema.json` | 2 inline → $ref (threatCategory, severityLevel) |
| 3 | `tools/specdev_tools/validation/canon_schema_alignment.py` | Update `_ENUM_CANON_PAIRINGS` path for nfr_category (C1 fix) |

**Total**: 1 core schema + 9 step schemas + 1 Python file modified. 17 inline enums → $ref. 14 new atoms created.

## Files NOT Modified

| File | Reason |
|------|--------|
| Python validators (step_*.py) | D7: enum values unchanged, validators are defense-in-depth |
| Test fixtures (tests/fixtures/) | D8: enum values unchanged, data still validates |
| `tools/schema_registry.json` | D10: no new schemas, just new $defs in existing atoms file |
| `schema/core/collections.schema.json` | No collection-level extractions in scope |
| Prompts, docs, CLAUDE.md | No user-facing behavior changes |

---

## Risk Matrix

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| $ref resolution failure | LOW | HIGH | 229 existing cross-file $refs + D10 registry auto-discovery |
| allOf composition break | LOW | HIGH | allOf IF conditions test values, don't define enums — unaffected |
| canon_schema_alignment E553 | **HIGH** if C1 missed | HIGH | C1 fix in Batch 3d (atomic with 3a) |
| Test fixture regression | NONE | HIGH | D8: enum values unchanged, data validates identically |
| Python validator mismatch | NONE | MEDIUM | D7: validators check values, not $ref structure |
| Description loss | LOW | LOW | Each $ref site retains its own `description` as sibling keyword |
| Default value loss | LOW | MEDIUM | D2: defaults either in atom (milestoneStatus) or as $ref sibling |

---

## Rollback Plan

Each batch touches independent schema files (except Batch 0 which is additive). If a batch fails:
1. `git checkout -- schema/<affected_file>.schema.json`
2. For Batch 3: also `git checkout -- tools/specdev_tools/validation/canon_schema_alignment.py`
3. Re-run `pytest tests/ -q` to confirm baseline is restored
4. Investigate the failure before retrying

---

## Follow-Up Items (Out of Scope for ALIGN-1)

These are real DRY violations discovered during the review but are Python-level concerns, not schema-level. Track separately.

| Item | Location | Issue | Fix |
|------|----------|-------|-----|
| `allowed_owners` duplication | `step_10.py` L19, `test_step_10.py` L37, `canon/kinds/owner.json` | Same 8-value owner set hardcoded in 3 places | Have validator load from canonical registry at runtime |
| `allowed_pr_rules` duplication | `hallucination_lint.py` L130, `step_10.py` L42, `10_governance.schema.json` L22 | Same 13-value pr_rules set in 3 places | Import from shared constant or read from schema |
| `risk_category` canon expansion | `canon/kinds/risk_category.json` | Canon kind has 3 entries vs `threatCategory` atom's 5 values (60% overlap). If canon expands to include `business_logic`/`transport`, consider adding explicit `_ENUM_CANON_PAIRINGS` entry | Monitor during canon registry updates |
