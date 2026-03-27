# P4: Schema Audit Fix Plan (Revised)

**Revision**: R4 (R3 review fixes applied)
**Date**: 2026-03-19
**Revision date**: 2026-03-19

## Summary

- Total tasks: 83
- Batches: 9 (Batch 0-8)
- Findings covered: 52 of 65 original audit findings + 28 deep review decisions
- WONTFIX: 3 (AUDIT-040, AUDIT-031, AUDIT-051)
- Estimated LOC delta: ~+1,324 / ~-1,863 / net ~-539
- INFO findings acknowledged: 13 (AUDIT-053 through AUDIT-065)

## Deep Review Decisions (R2)

These decisions override previous plan dispositions. They were made after independent architectural review of user concerns (see `p4-deep-review-user-concerns.md`, `p4-deep-review-user-concerns-r2.md`, `p4-deep-review-user-concerns-r3.md`, `p4-deep-review-coverage-gaps-docs-policy.md`, `p4-docs-lint-assessment.md`).

### Decision Summary

| # | Decision | Previous Disposition | New Disposition | Rationale |
|---|---|---|---|---|
| D1 | Remove `generation_quality` from all 19 step schemas | KEEP (AUDIT-020, Appendix B) | **REMOVE** | Ceremonial; always empty; LLM introspection unreliable; consumers check presence only, never extract value |
| D2 | Remove `seed_refs` from all 19 step schemas | KEEP (AUDIT-053, INFO) | **REMOVE** | Triple redundancy with prompts + seed_manifest; LLM self-report adds no independent value; derive mappings from seed_manifest |
| D3 | Remove `spec_refs_ingested` from all 19 step schemas | Demote to optional (FIX-053) | **REMOVE** | Dead schema, zero consumers. Escalated from "demote" to "remove" |
| D4 | Remove `coverage_gaps` from all 19 step schemas | Demote to optional in 18/19 (FIX-054) | **REMOVE** | Always empty; validator in step_12 iterates empty array; no tool computes it |
| D5 | Remove `nested_order` from seed_manifest | Make optional (FIX-055) | **REMOVE** | Redundant with global_seed_order. Escalated from "make optional" to "remove" |
| D6 | Remove `allowed_upstream_dependencies` from step_order.json | KEEP (AUDIT-058, INFO) | **REMOVE** | 100% derivable from step position under strict waterfall policy |
| D7 | Remove `docs_policy` from seed_manifest | WONTFIX (AUDIT-044) | **REMOVE** | Scope creep; lint config masquerading as spec data. Overrides WONTFIX. |
| D8 | Delete docs_lint entirely | Not in plan | **DELETE** | Scope creep; not part of spec pipeline; checks generic repo READMEs, not spec artifacts |
| D9 | Make `canonical_proposals` optional | Required (AUDIT-054, INFO) | **OPTIONAL** | Never non-empty anywhere in codebase; consumers handle absence gracefully |
| D10 | Make `canonical_conflicts` optional | Required (AUDIT-054, INFO) | **OPTIONAL** | Never non-empty anywhere in codebase; consumers handle absence gracefully |

### Impact on Previous Plan

- **FIX-001** (step_base.schema.json): MODIFIED -- base schema now has fewer fields (remove generation_quality, seed_refs, spec_refs_ingested, coverage_gaps from properties and required; make canonical_proposals/conflicts optional)
- **FIX-053**: SUPERSEDED -- was "demote spec_refs_ingested to optional", now "remove entirely" (new FIX-061)
- **FIX-054**: SUPERSEDED -- was "demote coverage_gaps to optional in 18/19", now "remove entirely" (new FIX-062)
- **FIX-055**: SUPERSEDED -- was "make nested_order optional", now "remove entirely" (new FIX-063)
- **AUDIT-020**: Was KEEP -- now REMOVE (new FIX-064)
- **AUDIT-044**: Was WONTFIX -- now REMOVE + DELETE docs_lint (new FIX-069 through FIX-074)
- **AUDIT-053**: Was INFO/KEEP -- now REMOVE (new FIX-065)
- **AUDIT-054**: Partially overridden -- canonical_refs_used stays required; proposals/conflicts made optional (new FIX-067, FIX-068)
- **AUDIT-058**: Partially overridden -- allowed_upstream_dependencies removed; downstream_consumers stays (new FIX-066)
- **FIX-051** (step_order.schema.json): MODIFIED -- no longer needs allowed_upstream_dependencies definition

### Conflicts with Existing Tasks

1. **FIX-001** (step_base.schema.json) listed 12 common properties including generation_quality, seed_refs, spec_refs_ingested, coverage_gaps. These 4 must be excluded from the base schema. canonical_proposals and canonical_conflicts must be in properties but NOT in required. **Resolution**: Update FIX-001 description. Base schema now has 6 required fields: `$schema`, `id`, `owner`, `created_at`, `canonical_refs_used`, `_migration_notes` (optional). Properties section includes canonical_proposals and canonical_conflicts as optional.
2. **FIX-019** (allOf adoption) referenced 11 common property declarations to remove. Now only 6-8 properties move to base. LOC savings reduced. **Resolution**: Update FIX-019 LOC estimate.
3. **Batch 3 description tasks** (FIX-020 through FIX-034) referenced adding descriptions to fields that are now being removed. **Resolution**: Skip descriptions for removed fields; net LOC estimate reduced slightly.

## Severity Coverage

| Severity | Total | Fix Tasks | WONTFIX | No Fix Needed | INFO (no fix) |
|---|---|---|---|---|---|
| CRITICAL | 1 | 1 | 0 | 0 | 0 |
| HIGH | 15 | 15 | 0 | 0 | 0 |
| MEDIUM | 24 | 20 | 2 | 2 | 0 |
| LOW | 12 | 11 | 1 | 0 | 0 |
| INFO | 13 | 0 | 0 | 0 | 13 |
| **Total** | **65** | **47** | **3** | **2** | **13** |

*WONTFIX: AUDIT-040 (MEDIUM), AUDIT-031 (MEDIUM), AUDIT-051 (LOW).*
*Removed from WONTFIX: AUDIT-044 (now REMOVE per D7).*
*"No Fix Needed" includes: AUDIT-028 (DEFERRED -- subsumed by ALIGN-2), AUDIT-037 (NO ACTION -- descriptions adequate).*

## WONTFIX Findings

| AUDIT ID | Title | Justification |
|---|---|---|
| AUDIT-040 | ALIGN-2 URI migration (534 URIs across 70+ files) | Requires atomic migration script across 93+ files. Depends on ALIGN-1 DRY fixes first. Out of scope for this audit's execution phase. Remains on research roadmap. |
| AUDIT-031 | Canon schemas outside `schema/` directory | Intentional co-location of canon schema + data files. Moving would require updating `$ref` paths in canon.schema.json, kind.schema.json, aliases.schema.json, registry entries, and all canon data files. Cost exceeds benefit. |
| AUDIT-051 | ALIGN-10 src/dist schema split | Originally motivated by required-field saturation forcing LLMs to emit empty ceremony fields. D1-D4 remove the 4 worst offenders (`generation_quality`, `seed_refs`, `spec_refs_ingested`, `coverage_gaps`) entirely, and D9/D10 make `canonical_proposals`/`canonical_conflicts` optional. These removals largely solve the underlying problem through elimination rather than mode-based relaxation, significantly reducing the need for a src/dist split. Still requires CLI flag infrastructure if revisited. Remains on research roadmap. |

## INFO Findings (No Fix Required)

| AUDIT ID | Title | Status |
|---|---|---|
| AUDIT-053 | `seed_refs` actively consumed | **OVERRIDDEN by D2**: Now REMOVE. See FIX-065. |
| AUDIT-054 | Canonical triad architecture sound | **PARTIALLY OVERRIDDEN by D9/D10**: canonical_refs_used stays required; proposals/conflicts made optional. See FIX-067/068. |
| AUDIT-055 | Step 16 has 228 missing descriptions | Addressed by FIX-041 through FIX-044 (Batch 3). |
| AUDIT-056 | 11 schemas already generic | No changes needed. |
| AUDIT-057 | Flat schema directory adequate | No restructuring at current scale. |
| AUDIT-058 | `allowed_upstream_dependencies` well-consumed | **OVERRIDDEN by D6**: derivable from step position. See FIX-066. |
| AUDIT-059 | `coverage_thresholds` well-consumed | No changes needed. |
| AUDIT-060 | `status_write_exemptions` well-consumed | No changes needed. |
| AUDIT-061 | seed_manifest merge NOT recommended | Keep separate. |
| AUDIT-062 | Registry complete, no orphans | No action needed. |
| AUDIT-063 | URI change affects 93+ files | Captured as prerequisite context for WONTFIX AUDIT-040. |
| AUDIT-064 | ALIGN-3/7/8/9 out of scope | Tool/CLI gaps, not schema. |
| AUDIT-065 | Registry location acceptable | Keep in `tools/`. |

## Dependency Graph

```
Batch 0: Foundation (new shared definitions in core/)
    |
    v
Batch 1: Core Schema Fixes (atoms, collections, canon, errors)
    |
    v
Batch 2: Step Schema DRY Fixes (allOf base, remove inline dupes)
    |
    v
Batch 3: Descriptions (core -> step -> Step 16 dedicated)
    |
    v
Batch 4: Genericity Fixes (extensible enums, naming)
    |
    v
Batch 5: Structure & Registry (missing $schema, fixture fixes)
    |
    v
Batch 6: Schema Removals (remove dead/redundant fields from schemas and config)
    |
    v
Batch 7: Tool Code Updates (update validators, linters, CLI for removed fields)
    |
    v
Batch 8: Test, Fixture, Prompt & CI Updates (regression lints, fixture cleanup, prompt updates, docs_lint deletion)
```

---

## Batch 0: Foundation (New Shared Definitions -- Must Complete First)

These tasks CREATE new core definitions that Batch 1+ consumers will reference.

### FIX-001: Create core/step_base.schema.json -- shared base for all step schemas (REVISED per D1-D4, D9-D10)

- **Batch**: 0
- **Audit ref**: AUDIT-004, AUDIT-027
- **Target file**: `schema/core/step_base.schema.json`
- **Change type**: CREATE
- **Description**: Create a base schema defining the common top-level properties shared by all 19 step schemas. **REVISED**: Per deep review decisions D1-D4, exclude `generation_quality`, `seed_refs`, `spec_refs_ingested`, and `coverage_gaps` from this schema entirely -- they are being removed. Per D9-D10, include `canonical_proposals` and `canonical_conflicts` as properties but NOT in the required array. Include `$schema` as `{ "type": "string", "format": "uri" }` (addresses AUDIT-027). Use `$anchor: stepBase`. Properties: `$schema`, `id`, `owner`, `created_at`, `canonical_refs_used`, `canonical_proposals` (optional), `canonical_conflicts` (optional), `_migration_notes` (optional). Required: `id`, `owner`, `created_at`, `canonical_refs_used`. Do NOT set `additionalProperties: false` -- this is a base fragment. Add `$id` following versioned path convention: `https://specdev.local/schema/core/step_base/1`.
- **Test gate**: `python -c "import json; json.load(open('schema/core/step_base.schema.json'))"` (syntax check only)
- **Dependencies**: none
- **Estimated LOC**: +45 / -0 / net +45

### FIX-002: Add `severityLevel` atom to core/atoms.schema.json

- **Batch**: 0
- **Audit ref**: AUDIT-006
- **Target file**: `schema/core/atoms.schema.json`
- **Change type**: MODIFY
- **Description**: Add `$defs.severityLevel` with `$anchor: severityLevel`, type string, enum `["low", "medium", "high", "critical"]`. This is the 4-level severity scale duplicated in Steps 11, 14, and 16. Note: the 2-value `["warn", "error"]` in Step 06 and `["blocking", "non_blocking"]` in Step 16 are semantically distinct and remain separate.
- **Test gate**: `python -c "import json; d=json.load(open('schema/core/atoms.schema.json')); assert 'severityLevel' in str(d)"`
- **Dependencies**: none
- **Estimated LOC**: +8 / -0 / net +8

### FIX-003: Add `milestoneStatus` atom to core/atoms.schema.json

- **Batch**: 0
- **Audit ref**: AUDIT-007
- **Target file**: `schema/core/atoms.schema.json`
- **Change type**: MODIFY (same file as FIX-002 -- execute sequentially)
- **Description**: Add `$defs.milestoneStatus` with `$anchor: milestoneStatus`, type string, enum `["pending", "in_progress", "done", "deferred"]`, default `"pending"`. Replaces inline duplicate in Steps 09 and 14.
- **Test gate**: `python -c "import json; d=json.load(open('schema/core/atoms.schema.json')); assert 'milestoneStatus' in str(d)"`
- **Dependencies**: FIX-002 (same file)
- **Estimated LOC**: +9 / -0 / net +9

### FIX-004: Add `referenceType` atom to core/atoms.schema.json

- **Batch**: 0
- **Audit ref**: AUDIT-011
- **Target file**: `schema/core/atoms.schema.json`
- **Change type**: MODIFY (same file as FIX-003 -- execute sequentially)
- **Description**: Add `$defs.referenceType` with `$anchor: referenceType`, type string, enum `["fr", "api", "nfr", "inv", "fixture", "doc", "code", "capability"]`. This is the union of Step 16 `specRef.type` (7 values) and Step 11 `mitigations[].type` (7 values), covering all 8 unique values. Individual schemas can narrow via `allOf` if needed.
- **Test gate**: `python -c "import json; d=json.load(open('schema/core/atoms.schema.json')); assert 'referenceType' in str(d)"`
- **Dependencies**: FIX-003 (same file)
- **Estimated LOC**: +8 / -0 / net +8

### FIX-005: Add `httpMethod` atom to core/atoms.schema.json

- **Batch**: 0
- **Audit ref**: AUDIT-018
- **Target file**: `schema/core/atoms.schema.json`
- **Change type**: MODIFY (same file as FIX-004 -- execute sequentially)
- **Description**: Add `$defs.httpMethod` with `$anchor: httpMethod`, type string, enum `["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"]` (the full 7-value set from Step 15). Replaces the inconsistent 5-value enum in Step 05 and 7-value enum in Step 15.
- **Test gate**: `python -c "import json; d=json.load(open('schema/core/atoms.schema.json')); assert 'httpMethod' in str(d)"`
- **Dependencies**: FIX-004 (same file)
- **Estimated LOC**: +8 / -0 / net +8

### FIX-006: Add `connectionProtocol` and `apiProtocol` atoms to core/atoms.schema.json

- **Batch**: 0
- **Audit ref**: AUDIT-019
- **Target file**: `schema/core/atoms.schema.json`
- **Change type**: MODIFY (same file as FIX-005 -- execute sequentially)
- **Description**: Add two protocol enums to make the intentional divergence explicit: (1) `connectionProtocol` with `$anchor: connectionProtocol`, enum `["http", "grpc", "event", "rpc", "db", "file"]` (Step 02's infrastructure-level protocol). (2) `apiProtocol` with `$anchor: apiProtocol`, enum `["http", "grpc", "ws", "mqtt"]` (Step 05's API-level protocol). Description on each explains the semantic difference.
- **Test gate**: `python -c "import json; d=json.load(open('schema/core/atoms.schema.json')); assert 'connectionProtocol' in str(d) and 'apiProtocol' in str(d)"`
- **Dependencies**: FIX-005 (same file)
- **Estimated LOC**: +18 / -0 / net +18

**[Batch 0 Gate]:** `pytest tests/ -x --tb=short` -- Expected: all existing tests pass (no consumers modified yet, only new definitions added).

---

## Batch 1: Core Schema Fixes (atoms, collections, canon, errors)

Changes to existing core definitions. Must complete before step schemas reference new core atoms.

### FIX-007: Deduplicate `environmentName`/`stageName` in core/collections.schema.json

- **Batch**: 1
- **Audit ref**: AUDIT-017
- **Target file**: `schema/core/collections.schema.json`
- **Change type**: MODIFY
- **Description**: Remove `stageName` definition (lines ~209-216). It is an exact duplicate of `environmentName` with identical enum `["dev", "ci", "staging", "prod"]`. Step 07 (the sole `stageName` consumer) will be updated in Batch 2 to reference `environmentName` instead. Add a comment or description noting the deprecation. Related to AUDIT-008 (environment flexibility) addressed in Batch 4.
- **Test gate**: `pytest tests/ -x --tb=short`
- **Dependencies**: FIX-001 (base schema must exist first so Batch 2 step updates have a foundation)
- **Estimated LOC**: +0 / -10 / net -10

### FIX-008: Fix `canonicalId` pattern duplication between core/canon and core/collections

- **Batch**: 1
- **Audit ref**: AUDIT-041
- **Target file**: `schema/core/collections.schema.json`
- **Change type**: MODIFY
- **Description**: Replace the inline `canonicalId` pattern (`^cn:[a-z0-9.]+:[a-z_]+:[a-z0-9-]+$`) in `canonicalRef.properties.id` with a `$ref` to `core/canon/1#canonicalId`. This eliminates the pattern duplication between collections and canon.
- **Test gate**: `pytest tests/ -x --tb=short`
- **Dependencies**: none
- **Estimated LOC**: +1 / -3 / net -2

### FIX-009: Rename `canon#owner` to `canon#canonOwner` to avoid naming collision

- **Batch**: 1
- **Audit ref**: AUDIT-042
- **Target file**: `schema/core/canon.schema.json`
- **Change type**: MODIFY
- **Description**: Rename `$defs.owner` to `$defs.canonOwner` and update `$anchor` from `owner` to `canonOwner`. The pattern `^[a-z][a-z0-9-]*$` (hyphens only) is intentionally different from `atoms#owner` pattern `^[a-z][a-z0-9_-]*$` (underscores AND hyphens). Renaming makes the distinction explicit. Update all internal `$ref` references within `canon.schema.json` (entry.owners items). Check `canon/kind.schema.json` and `canon/aliases.schema.json` for references that need updating.
- **Test gate**: `pytest tests/ -x --tb=short`
- **Dependencies**: none
- **Estimated LOC**: +3 / -3 / net 0

### FIX-010: Promote Step 16 `executionStatus` to core/collections.schema.json

- **Batch**: 1
- **Audit ref**: AUDIT-005
- **Target file**: `schema/core/collections.schema.json`
- **Change type**: MODIFY
- **Description**: Add `$defs.executionStatus` with `$anchor: executionStatus`, type string, enum `["passed", "failed", "blocked", "partial"]`. Currently only defined in Step 16's local `$defs`. Also add `$defs.evidenceObject` with `$anchor: evidenceObject` (type object with `type` enum `["log", "snippet", "screenshot", "reference"]`, plus `content` (string, minLength: 20), `evidence_ref` (string), `path` (string), `section` (string) properties; required: `type`, `content`). These are reusable test/review concepts. Step 16 will be updated to `$ref` these in Batch 2.
- **Test gate**: `pytest tests/ -x --tb=short`
- **Dependencies**: none
- **Estimated LOC**: +30 / -0 / net +30

**[Batch 1 Gate]:** `pytest tests/ -x --tb=short` -- Expected: all tests pass. Core definitions updated, no consumers modified yet.

---

## Batch 2: Step Schema DRY Fixes (allOf base, remove inline duplicates)

Refactor step schemas to use new core definitions. Each task modifies ONE step schema file. Highly parallel within sub-groups.

### FIX-011: Step 07 -- Replace `stageName` $ref with `environmentName`

- **Batch**: 2
- **Audit ref**: AUDIT-017
- **Target file**: `schema/07_nfrs.schema.json`
- **Change type**: MODIFY
- **Description**: Replace `$ref` to `collections/1#stageName` with `$ref` to `collections/1#environmentName`. Step 07 is the sole consumer of `stageName`.
- **Test gate**: `pytest tests/unit/validation/validators/test_step_validators_core.py -x --tb=short`
- **Dependencies**: FIX-007
- **Estimated LOC**: +1 / -1 / net 0

### FIX-012: Step 09 -- Replace inline `milestoneStatus` with $ref to core atom

- **Batch**: 2
- **Audit ref**: AUDIT-007
- **Target file**: `schema/09_impl_plan.schema.json`
- **Change type**: MODIFY
- **Description**: Replace inline `milestones[].status` enum `["pending", "in_progress", "done", "deferred"]` with `$ref` to `core/atoms/1#milestoneStatus`.
- **Test gate**: `pytest tests/unit/validation/validators/test_step_validators_core.py -x --tb=short`
- **Dependencies**: FIX-003
- **Estimated LOC**: +1 / -5 / net -4

### FIX-013: Step 14 -- Replace inline `milestoneStatus` and `severityLevel` with $ref

- **Batch**: 2
- **Audit ref**: AUDIT-006, AUDIT-007
- **Target file**: `schema/14_roadmap.schema.json`
- **Change type**: MODIFY
- **Description**: (1) Replace inline `milestones[].status` enum with `$ref` to `core/atoms/1#milestoneStatus` (AUDIT-007). (2) Replace inline `milestones[].risk_status` enum `["low", "medium", "high", "critical"]` with `$ref` to `core/atoms/1#severityLevel` (AUDIT-006).
- **Test gate**: `pytest tests/unit/validation/validators/test_step_validators_core.py -x --tb=short`
- **Dependencies**: FIX-002, FIX-003
- **Estimated LOC**: +2 / -10 / net -8

### FIX-014: Step 11 -- Replace inline `severityLevel` and `referenceType` with $ref

- **Batch**: 2
- **Audit ref**: AUDIT-006, AUDIT-011
- **Target file**: `schema/11_redteam.schema.json`
- **Change type**: MODIFY
- **Description**: (1) Replace inline `threats[].severity` enum `["low", "medium", "high", "critical"]` with `$ref` to `core/atoms/1#severityLevel` (AUDIT-006). (2) Replace inline `mitigations[].type` enum with `$ref` to `core/atoms/1#referenceType` (AUDIT-011). If step 11 needs a narrower set than the full 8-value union, use `allOf` with the `$ref` plus an additional constraint.
- **Test gate**: `pytest tests/unit/validation/validators/test_step_validators_core.py tests/integration/test_step_11.py -x --tb=short`
- **Dependencies**: FIX-002, FIX-004
- **Estimated LOC**: +2 / -10 / net -8

### FIX-015: Step 05 -- Replace inline `method` and `protocol` with $ref

- **Batch**: 2
- **Audit ref**: AUDIT-018, AUDIT-019
- **Target file**: `schema/05_interface_contracts.schema.json`
- **Change type**: MODIFY
- **Description**: (1) Replace inline `apis[].method` enum with `$ref` to `core/atoms/1#httpMethod` (AUDIT-018). This upgrades Step 05 from 5 to 7 HTTP verbs, matching Step 15. (2) Replace inline `apis[].protocol` enum with `$ref` to `core/atoms/1#apiProtocol` (AUDIT-019).
- **Test gate**: `pytest tests/unit/validation/validators/test_step_validators_core.py tests/integration/test_step_05.py -x --tb=short`
- **Dependencies**: FIX-005, FIX-006
- **Estimated LOC**: +2 / -10 / net -8

### FIX-016: Step 15 -- Replace inline `method` with $ref

- **Batch**: 2
- **Audit ref**: AUDIT-018
- **Target file**: `schema/15_scaffold.schema.json`
- **Change type**: MODIFY
- **Description**: Replace inline `route_map[].method` enum with `$ref` to `core/atoms/1#httpMethod`.
- **Test gate**: `pytest tests/unit/validation/validators/test_step_validators_core.py tests/integration/test_step_15.py -x --tb=short`
- **Dependencies**: FIX-005
- **Estimated LOC**: +1 / -5 / net -4

### FIX-017: Step 02 -- Replace inline `protocol` with $ref

- **Batch**: 2
- **Audit ref**: AUDIT-019
- **Target file**: `schema/02_system_sketch.schema.json`
- **Change type**: MODIFY
- **Description**: Replace inline `connections[].protocol` enum with `$ref` to `core/atoms/1#connectionProtocol`.
- **Test gate**: `pytest tests/unit/validation/validators/test_step_validators_core.py -x --tb=short`
- **Dependencies**: FIX-006
- **Estimated LOC**: +1 / -5 / net -4

### FIX-018: Step 16 -- Replace local $defs with $ref to core definitions, fix fr_id inline

- **Batch**: 2
- **Audit ref**: AUDIT-005, AUDIT-006, AUDIT-011, AUDIT-043
- **Target file**: `schema/16_impl_context.schema.json`
- **Change type**: MODIFY
- **Description**: This is the largest single schema (1,868 LOC). Changes: (1) Replace `$defs.severityLevel` with `$ref` to `core/atoms/1#severityLevel` at all 5+ usage sites (AUDIT-006). (2) Replace `$defs.specRef.type` enum with `$ref` to `core/atoms/1#referenceType` (AUDIT-011). (3) Replace `$defs.executionStatus` with `$ref` to `core/collections/1#executionStatus` (AUDIT-005). (4) Replace `$defs.evidenceObject` with `$ref` to `core/collections/1#evidenceObject` (AUDIT-005). (5) Replace inline `fr_id` pattern at line ~1753 with `$ref` to `core/atoms/1#kebabId` (AUDIT-043). (6) Remove the entire `$defs` block (lines 8-100) after all internal references are replaced with core `$ref`s. Verify all 7 local `$ref` targets are replaced.
- **Test gate**: `pytest tests/unit/validation/validators/test_step_validators_core.py tests/integration/test_step_16*.py -x --tb=short`
- **Dependencies**: FIX-002, FIX-004, FIX-010
- **Estimated LOC**: +7 / -95 / net -88

### FIX-019: Adopt allOf base schema across all 19 step schemas (REVISED per D1-D4, D9-D10)

- **Batch**: 2
- **Audit ref**: AUDIT-004, AUDIT-027
- **Target file**: All 19 step schemas (00 through 16)
- **Change type**: MODIFY (19 files)
- **Description**: For each of the 19 step schemas: (1) Wrap existing schema in `allOf` composition: `{"allOf": [{"$ref": "core/step_base/1#stepBase"}, {existing-step-specific-schema}]}`. (2) Remove the common property declarations now inherited from base (id, owner, created_at, canonical_refs_used, canonical_proposals, canonical_conflicts, _migration_notes, $schema). (3) Remove the common `required` entries (id, owner, created_at, canonical_refs_used). (4) **REVISED**: Do NOT include generation_quality, seed_refs, spec_refs_ingested, or coverage_gaps in any step schema -- these are being removed entirely in Batch 6. If they still exist in step schemas at this point, remove them here. Keep step-specific properties and required fields. Use `unevaluatedProperties: false` instead of `additionalProperties: false` (see Appendix B for rationale). **Note**: Because the base schema has fewer fields than originally planned (D1-D4 removals), the per-schema LOC reduction is smaller (~15-20 LOC per schema instead of ~25-30). Estimated ~300-380 LOC total reduction.
- **Test gate**: `pytest tests/ -x --tb=short` (FULL suite -- this is the highest-risk change)
- **Dependencies**: FIX-001
- **Pre-execution check**: Audit all tool code for direct schema `properties` traversal beyond `_schema_candidates` in `integrity.py` (which already handles `allOf`).
- **Estimated LOC**: +19 / -380 / net -361

**[Batch 2 Gate]:** `pytest tests/ -x --tb=short` -- Expected: all tests pass. This is the highest-risk batch. If FIX-019 causes failures, investigate `unevaluatedProperties` interaction with `allOf` and verify jsonschema library support.

**Execution note**: Consider splitting Batch 2 into two sub-batches for risk isolation:
- **Batch 2a**: FIX-011 through FIX-018 (individual step `$ref` replacements, low-risk, highly parallel)
- **Batch 2b**: FIX-019 (allOf base adoption across 19 files, highest-risk single task)

---

## Batch 3: Descriptions (808 Missing -- Split by Schema Group)

Add descriptions to all 808 properties. Source: `WIP/schema_audit/p1-out-descriptions.md` draft descriptions. Split into sub-tasks by schema group.

**Note**: Per D1-D4, skip adding descriptions to fields being removed (generation_quality, seed_refs, spec_refs_ingested, coverage_gaps). Net description count reduced slightly.

### FIX-020: Add descriptions to core/atoms.schema.json

- **Batch**: 3
- **Audit ref**: AUDIT-014, AUDIT-001
- **Target file**: `schema/core/atoms.schema.json`
- **Change type**: MODIFY
- **Description**: Add descriptions to all 4 atoms missing descriptions (P1-B counts: 4/6 missing). These propagate to 60+ downstream `$ref` usages. Also add descriptions to the new atoms added in Batch 0 (severityLevel, milestoneStatus, referenceType, httpMethod, connectionProtocol, apiProtocol) if not already described.
- **Test gate**: `pytest tests/ -x --tb=short`
- **Dependencies**: FIX-002 through FIX-006 (Batch 0 atoms)
- **Estimated LOC**: +20 / -0 / net +20

### FIX-021: Add descriptions to core/collections.schema.json (REVISED per D1-D4)

- **Batch**: 3
- **Audit ref**: AUDIT-014, AUDIT-001
- **Target file**: `schema/core/collections.schema.json`
- **Change type**: MODIFY
- **Description**: Add descriptions to properties missing descriptions. **REVISED**: Skip descriptions for `generationQuality`, `seedRef`/`seedRefArray`, `specRefIngested`/`specRefsIngestedArray`, and `coverageGap`/`coverageGapsArray` -- these definitions are being removed or deprecated in Batch 6. Focus on remaining ~35 properties. Also add descriptions to new definitions added in Batch 1 (executionStatus, evidenceObject).
- **Test gate**: `pytest tests/ -x --tb=short`
- **Dependencies**: FIX-010 (Batch 1 collections additions)
- **Estimated LOC**: +40 / -0 / net +40

### FIX-022: Add descriptions to core/errors.schema.json

- **Batch**: 3
- **Audit ref**: AUDIT-014, AUDIT-001
- **Target file**: `schema/core/errors.schema.json`
- **Change type**: MODIFY
- **Description**: Add descriptions to all 3 properties (0% coverage currently).
- **Test gate**: `pytest tests/ -x --tb=short`
- **Dependencies**: none
- **Estimated LOC**: +5 / -0 / net +5

### FIX-023: Add descriptions to core/canon.schema.json

- **Batch**: 3
- **Audit ref**: AUDIT-014, AUDIT-038, AUDIT-001
- **Target file**: `schema/core/canon.schema.json`
- **Change type**: MODIFY
- **Description**: Add descriptions to all 31 properties (0% coverage currently). This schema defines the canonical registry structure consumed by 3+ tools.
- **Test gate**: `pytest tests/ -x --tb=short`
- **Dependencies**: FIX-009 (canonOwner rename)
- **Estimated LOC**: +35 / -0 / net +35

### FIX-024: Add descriptions to core/step_base.schema.json (REVISED per D1-D4, D9-D10)

- **Batch**: 3
- **Audit ref**: AUDIT-001, AUDIT-015, AUDIT-039
- **Target file**: `schema/core/step_base.schema.json`
- **Change type**: MODIFY
- **Description**: Add descriptions to all base properties. **REVISED**: Fewer properties than original plan (generation_quality, seed_refs, spec_refs_ingested, coverage_gaps removed). Properties to describe: `$schema`, `id`, `owner`, `created_at`, `canonical_refs_used`, `canonical_proposals` (note: optional), `canonical_conflicts` (note: optional), `_migration_notes`. Since these are the most ambiguous reused fields (AUDIT-015: `id`, `owner` have multiple meanings), descriptions here must be generic enough for all 19 step schemas.
- **Test gate**: `pytest tests/ -x --tb=short`
- **Dependencies**: FIX-001
- **Estimated LOC**: +10 / -0 / net +10

### FIX-025: Add descriptions to schema/seed_manifest.schema.json (REVISED per D5, D7)

- **Batch**: 3
- **Audit ref**: AUDIT-038, AUDIT-001
- **Target file**: `schema/seed_manifest.schema.json`
- **Change type**: MODIFY
- **Description**: Add descriptions to properties (0% coverage currently). **REVISED**: Skip `nested_order` and `docs_policy` -- these are being removed in Batch 6. Focus on remaining ~18 properties.
- **Test gate**: `pytest tests/ -x --tb=short`
- **Dependencies**: none
- **Estimated LOC**: +22 / -0 / net +22

### FIX-026: Add descriptions to canon/kind.schema.json

- **Batch**: 3
- **Audit ref**: AUDIT-038, AUDIT-001
- **Target file**: `canon/kind.schema.json`
- **Change type**: MODIFY
- **Description**: Add descriptions to all 4 properties (0% coverage).
- **Test gate**: `pytest tests/ -x --tb=short`
- **Dependencies**: none
- **Estimated LOC**: +6 / -0 / net +6

### FIX-027: Add descriptions to canon/aliases.schema.json

- **Batch**: 3
- **Audit ref**: AUDIT-038, AUDIT-001
- **Target file**: `canon/aliases.schema.json`
- **Change type**: MODIFY
- **Description**: Add descriptions to all 3 properties (0% coverage).
- **Test gate**: `pytest tests/ -x --tb=short`
- **Dependencies**: none
- **Estimated LOC**: +5 / -0 / net +5

### FIX-028: Add descriptions to step schemas 00-04

- **Batch**: 3
- **Audit ref**: AUDIT-001, AUDIT-015
- **Target file**: `schema/00_charter.schema.json`, `schema/01_capabilities.schema.json`, `schema/02_system_sketch.schema.json`, `schema/02a_delivery_baseline.schema.json`, `schema/03_glossary.schema.json`, `schema/04_fr_list.schema.json`
- **Change type**: MODIFY (6 files)
- **Description**: Add descriptions to all step-specific properties in these 6 schemas. After base schema extraction (Batch 2), only step-specific properties remain. Approximate counts: 00 (25 props), 01 (16 props), 02 (30 props), 02a (8 props), 03 (10 props), 04 (15 props). Use P1-B draft descriptions. For ambiguous names (AUDIT-015: `scope`, `type`, `status`), use step-specific descriptions.
- **Test gate**: `pytest tests/ -x --tb=short`
- **Dependencies**: FIX-019 (base schema adoption)
- **Estimated LOC**: +110 / -0 / net +110

### FIX-029: Add descriptions to step schemas 05-08

- **Batch**: 3
- **Audit ref**: AUDIT-001, AUDIT-015
- **Target file**: `schema/05_interface_contracts.schema.json`, `schema/06_invariants.schema.json`, `schema/07_nfrs.schema.json`, `schema/08_fixtures.schema.json`
- **Change type**: MODIFY (4 files)
- **Description**: Add descriptions to all step-specific properties. Approximate counts: 05 (27 props), 06 (13 props), 07 (14 props), 08 (9 props). For `method`, `protocol`, `severity` (AUDIT-015), add step-specific disambiguation.
- **Test gate**: `pytest tests/ -x --tb=short`
- **Dependencies**: FIX-019
- **Estimated LOC**: +70 / -0 / net +70

### FIX-030: Add descriptions to step schemas 09-12

- **Batch**: 3
- **Audit ref**: AUDIT-001, AUDIT-015
- **Target file**: `schema/09_impl_plan.schema.json`, `schema/10_governance.schema.json`, `schema/11_redteam.schema.json`, `schema/12_ci_gates.schema.json`
- **Change type**: MODIFY (4 files)
- **Description**: Add descriptions to all step-specific properties. Approximate counts: 09 (16 props), 10 (19 props), 11 (18 props), 12 (16 props).
- **Test gate**: `pytest tests/ -x --tb=short`
- **Dependencies**: FIX-019
- **Estimated LOC**: +75 / -0 / net +75

### FIX-031: Add descriptions to step schemas 13-15

- **Batch**: 3
- **Audit ref**: AUDIT-001, AUDIT-015
- **Target file**: `schema/13_extension_generator.schema.json`, `schema/13a_completeness_assessment.schema.json`, `schema/14_roadmap.schema.json`, `schema/15_scaffold.schema.json`
- **Change type**: MODIFY (4 files)
- **Description**: Add descriptions to all step-specific properties. Approximate counts: 13 (9 props), 13a (14 props), 14 (26 props), 15 (14 props).
- **Test gate**: `pytest tests/ -x --tb=short`
- **Dependencies**: FIX-019
- **Estimated LOC**: +70 / -0 / net +70

### FIX-032: Add descriptions to Step 16 (plan section)

- **Batch**: 3
- **Audit ref**: AUDIT-001, AUDIT-055, AUDIT-015
- **Target file**: `schema/16_impl_context.schema.json`
- **Change type**: MODIFY
- **Description**: Step 16 has 228 missing descriptions (28.2% of total gap). Split into 3 tasks by section due to size. This task covers the `plan` section properties (~80 properties). Includes `plan.status`, `plan.docs_impact`, `plan.spec_alignment`, `plan.ambiguities`, `plan.drift`. For `status`, `severity`, `type` fields (AUDIT-015), add step-16-specific disambiguation.
- **Test gate**: `pytest tests/ -x --tb=short`
- **Dependencies**: FIX-018 (Step 16 $defs extraction), FIX-019
- **Estimated LOC**: +90 / -0 / net +90

### FIX-033: Add descriptions to Step 16 (execution section)

- **Batch**: 3
- **Audit ref**: AUDIT-001, AUDIT-055
- **Target file**: `schema/16_impl_context.schema.json`
- **Change type**: MODIFY
- **Description**: Add descriptions to `execution` section properties (~70 properties). Includes `execution.final_status`, `execution.testing`, `execution.implementation`.
- **Test gate**: `pytest tests/ -x --tb=short`
- **Dependencies**: FIX-032 (same file, execute sequentially)
- **Estimated LOC**: +80 / -0 / net +80

### FIX-034: Add descriptions to Step 16 (review section)

- **Batch**: 3
- **Audit ref**: AUDIT-001, AUDIT-055
- **Target file**: `schema/16_impl_context.schema.json`
- **Change type**: MODIFY
- **Description**: Add descriptions to `review` section properties (~78 properties). Includes `review.findings`, `review.verdict`, `review.fixture_status`, `review.security_status`, `review.delivery_status`, `review.semantic_review`.
- **Test gate**: `pytest tests/ -x --tb=short`
- **Dependencies**: FIX-033 (same file, execute sequentially)
- **Estimated LOC**: +85 / -0 / net +85

### FIX-060: Fix research roadmap ALIGN-5 depth and naming inaccuracy

- **Batch**: 3
- **Audit ref**: AUDIT-052
- **Target file**: WIP research roadmap document containing ALIGN-5 entry
- **Change type**: MODIFY
- **Description**: Correct two inaccuracies in the WIP research roadmap ALIGN-5 entry: (1) change "19 levels" to "9 levels" (actual max nesting depth). (2) Change "scaffolding" to "impl_context" (correct Step 16 name). Trivial 2-word documentation fix.
- **Test gate**: none (documentation-only change)
- **Dependencies**: none
- **Estimated LOC**: +2 / -2 / net 0

**[Batch 3 Gate]:** `pytest tests/ -x --tb=short` -- Expected: all tests pass. Description additions are additive and should not break validation. Verify description coverage is now above 90%.

---

## Batch 4: Genericity Fixes (Extensible Enums, Naming)

Make schemas usable for non-web-service projects. These changes are potentially breaking for existing spec files that use hardcoded enum values.

### FIX-035: Step 05 -- Generalize `method` with conditional validation by protocol

- **Batch**: 4
- **Audit ref**: AUDIT-009
- **Target file**: `schema/05_interface_contracts.schema.json`
- **Change type**: MODIFY
- **Description**: Make `apis[].method` conditionally validated based on `protocol`. For `protocol: "http"`, validate against `httpMethod` atom. For other protocols, accept any non-empty string (allowing gRPC method names, CLI commands, etc.). Implement via `allOf` with `if/then` conditions. Add description explaining the conditional behavior.
- **Test gate**: `pytest tests/unit/validation/validators/test_step_validators_core.py tests/integration/test_step_05.py -x --tb=short`
- **Dependencies**: FIX-015 (Step 05 already uses $ref for method)
- **Estimated LOC**: +15 / -3 / net +12

### FIX-036: Step 05 -- Extend `parameters[].in` enum for non-HTTP contexts

- **Batch**: 4
- **Audit ref**: AUDIT-010
- **Target file**: `schema/05_interface_contracts.schema.json`
- **Change type**: MODIFY
- **Description**: Extend `parameters[].in` enum to include non-HTTP locations: add `"body"`, `"cookie"`, `"argv"`, `"stdin"`, `"env"`, `"config"`, `"payload"`, `"metadata"`. Alternatively, change to pattern-validated string and move to canonical registry. If extending enum: `["query", "path", "header", "body", "cookie", "argv", "stdin", "env", "config", "payload", "metadata"]`.
- **Test gate**: `pytest tests/unit/validation/validators/test_step_validators_core.py tests/integration/test_step_05.py -x --tb=short`
- **Dependencies**: FIX-035 (same file, execute after)
- **Estimated LOC**: +3 / -1 / net +2

### FIX-037: Step 15 -- Rename `service_skeleton` to `project_skeleton`, generalize `route_map`

- **Batch**: 4
- **Audit ref**: AUDIT-012, AUDIT-023
- **Target file**: `schema/15_scaffold.schema.json`
- **Change type**: MODIFY
- **Description**: (1) AUDIT-023: Rename `service_skeleton` to `project_skeleton`. Update `framework` description from "Web framework" to "Primary framework (e.g., fastapi, electron, click, react-native)". (2) AUDIT-012: Rename `route_map` to `interface_map`. Remove from unconditional `required`. Make items more generic: rename `api_ref` to `interface_ref`, keep `path` and `method` (method is already $ref to httpMethod). Add description noting that for non-HTTP projects, `method` can be omitted. **Breaking change**: field renames require updating Step 15 validator, prompts, and test fixtures.
- **Test gate**: `pytest tests/unit/validation/validators/test_step_validators_core.py -x --tb=short`
- **Dependencies**: FIX-016 (Step 15 method $ref)
- **Estimated LOC**: +10 / -5 / net +5

### FIX-038: Step 12 -- Generalize `token_permissions` description

- **Batch**: 4
- **Audit ref**: AUDIT-013
- **Target file**: `schema/12_ci_gates.schema.json`
- **Change type**: MODIFY
- **Description**: Update `token_permissions` description to be CI-provider-agnostic. Keep the structure generic (additionalProperties with enum values). Also update `runner_labels` description to mention non-GitHub equivalents.
- **Test gate**: `pytest tests/unit/validation/validators/test_step_validators_core.py -x --tb=short`
- **Dependencies**: none
- **Estimated LOC**: +5 / -2 / net +3

### FIX-039: Step 02a -- Remove hardcoded environment requirements

- **Batch**: 4
- **Audit ref**: AUDIT-008
- **Target file**: `schema/02a_delivery_baseline.schema.json`
- **Change type**: MODIFY
- **Description**: Remove `required: ["dev", "ci", "staging", "prod"]` and `minProperties: 4` from environments definition. Replace with `minProperties: 1` and `additionalProperties` referencing `environmentConfig`. This allows non-web projects to define their own environments.
- **Test gate**: `pytest tests/unit/validation/validators/test_step_validators_core.py -x --tb=short`
- **Dependencies**: none
- **Estimated LOC**: +3 / -5 / net -2

### FIX-040: Core collections -- Make `environmentName` extensible

- **Batch**: 4
- **Audit ref**: AUDIT-008
- **Target file**: `schema/core/collections.schema.json`
- **Change type**: MODIFY
- **Description**: Change `environmentName` from closed enum `["dev", "ci", "staging", "prod"]` to a pattern-validated string `^[a-z][a-z0-9_-]*$` with a description listing the canonical values as examples. This allows projects to define custom environments while maintaining naming consistency.
- **Test gate**: `pytest tests/ -x --tb=short`
- **Dependencies**: FIX-039 (Step 02a fix first), FIX-011 (Step 07 $ref update)
- **Estimated LOC**: +5 / -3 / net +2

### FIX-041: Step 16 -- Rename `implemented_endpoints` and generalize `layer` enum

- **Batch**: 4
- **Audit ref**: AUDIT-024, AUDIT-025
- **Target file**: `schema/16_impl_context.schema.json`
- **Change type**: MODIFY
- **Description**: (1) AUDIT-025: Rename `implemented_endpoints` to `implemented_interfaces`. Structure is already generic (array of traceIds). (2) AUDIT-024: Change `checklist[].layer` from closed enum to pattern-validated string `^[a-z][a-z0-9_-]*$` with description listing current values as examples. **Breaking change**: field rename requires updating Step 16 validator and test fixtures.
- **Test gate**: `pytest tests/unit/validation/validators/test_step_validators_core.py tests/integration/test_step_16*.py -x --tb=short`
- **Dependencies**: FIX-018 (Step 16 $defs extraction)
- **Estimated LOC**: +8 / -5 / net +3

### FIX-042: Step 16 -- Generalize `drift.checks[].target` enum

- **Batch**: 4
- **Audit ref**: AUDIT-047
- **Target file**: `schema/16_impl_context.schema.json`
- **Change type**: MODIFY
- **Description**: Add `"interface"` to `drift.checks[].target` enum as an alternative to `"api"`. Updated enum: `["api", "interface", "schema", "nfr", "invariant", "fixture", "config"]`.
- **Test gate**: `pytest tests/unit/validation/validators/test_step_validators_core.py -x --tb=short`
- **Dependencies**: FIX-041 (same file, execute after)
- **Estimated LOC**: +2 / -1 / net +1

### FIX-043: Step 10 -- Generalize `evidence_source_by_phase`

- **Batch**: 4
- **Audit ref**: AUDIT-048
- **Target file**: `schema/10_governance.schema.json`
- **Change type**: MODIFY
- **Description**: Remove `required: ["dev", "staging", "prod"]` from `evidence_source_by_phase`. Replace with `minProperties: 1` and `additionalProperties: { "type": "string" }`. This allows projects to define evidence sources for their own phases/environments.
- **Test gate**: `pytest tests/unit/validation/validators/test_step_validators_core.py -x --tb=short`
- **Dependencies**: none
- **Estimated LOC**: +3 / -3 / net 0

### FIX-044: Step 05 -- Rename `route` to `path`, generalize `request_schema_ref`/`response_schema_ref`

- **Batch**: 4
- **Audit ref**: AUDIT-021, AUDIT-022
- **Target file**: `schema/05_interface_contracts.schema.json`
- **Change type**: MODIFY
- **Description**: (1) AUDIT-021: Rename `apis[].route` to `apis[].path`. Field is optional, low impact. (2) AUDIT-022: Rename `request_schema_ref` to `input_schema_ref` and `response_schema_ref` to `output_schema_ref`. Both are optional. Add descriptions explaining these work for any paradigm. **Breaking change**: field renames require updating Step 05 validator and prompts.
- **Test gate**: `pytest tests/unit/validation/validators/test_step_validators_core.py tests/integration/test_step_05.py -x --tb=short`
- **Dependencies**: FIX-036 (same file, execute after)
- **Estimated LOC**: +6 / -3 / net +3

### FIX-045: Step 12 -- Generalize `environment_protection` descriptions

- **Batch**: 4
- **Audit ref**: AUDIT-046
- **Target file**: `schema/12_ci_gates.schema.json`
- **Change type**: MODIFY
- **Description**: Update `required_reviewers` and `wait_timer_minutes` descriptions to be CI-provider-agnostic. Fields are conceptually generic; only descriptions need updating.
- **Test gate**: `pytest tests/ -x --tb=short`
- **Dependencies**: FIX-038 (same file, execute after)
- **Estimated LOC**: +4 / -2 / net +2

**[Batch 4 Gate]:** `pytest tests/ -x --tb=short` -- Expected: some test fixtures may need updating due to field renames. Fix fixtures before proceeding. **Important**: Run `./tools/run_specdev.sh validate-all spec --repo-root .` to verify spec data files still validate.

---

## Batch 5: Structure & Registry (Missing $schema, Fixture Fixes)

Fix structural issues: missing `$schema` properties, fixture references, canon schema location.

### FIX-046: Add `$schema` property to seed_manifest.schema.json

- **Batch**: 5
- **Audit ref**: AUDIT-026
- **Target file**: `schema/seed_manifest.schema.json`
- **Change type**: MODIFY
- **Description**: Add `"$schema": { "type": "string", "format": "uri" }` to properties. The data file `spec/common/seed_manifest.json` includes `$schema` but the schema rejects it via `additionalProperties: false`. Currently masked by validator stripping `$schema` before validation.
- **Test gate**: `pytest tests/ -x --tb=short`
- **Dependencies**: none
- **Estimated LOC**: +3 / -0 / net +3

### FIX-047: Add `$schema` to 22 canon/kinds/ data files

- **Batch**: 5
- **Audit ref**: AUDIT-030
- **Target file**: `canon/kinds/*.json` (22 files)
- **Change type**: MODIFY (22 files)
- **Description**: Add `"$schema": "https://specdev.local/schema/canon/kind/1"` to each of the 22 kind registry files that lack it.
- **Test gate**: `pytest tests/ -x --tb=short`
- **Dependencies**: none
- **Estimated LOC**: +22 / -0 / net +22

### FIX-048: Fix test fixture `step_13/valid_extension.json` -- stale $schema reference

- **Batch**: 5
- **Audit ref**: AUDIT-029
- **Target file**: `tests/fixtures/step_13/valid_extension.json`
- **Change type**: MODIFY
- **Description**: Update `$schema` from `https://specdev.local/schema/13b_database_schema.schema.json` to `https://specdev.local/schema/13_extension_generator.schema.json`. No `13b` schema exists.
- **Test gate**: `pytest tests/ -x --tb=short`
- **Dependencies**: none
- **Estimated LOC**: +1 / -1 / net 0

### FIX-049: Fix test fixture `step_00/00_charter.json` -- stale relative $schema path

- **Batch**: 5
- **Audit ref**: AUDIT-049
- **Target file**: `tests/fixtures/step_00/00_charter.json`
- **Change type**: MODIFY
- **Description**: Update `$schema` from relative path `../../schema/00_charter.schema.json` to canonical URI `https://specdev.local/schema/00_charter.schema.json`.
- **Test gate**: `pytest tests/ -x --tb=short`
- **Dependencies**: none
- **Estimated LOC**: +1 / -1 / net 0

### FIX-050: Fix test fixture `14_roadmap.json` -- GitHub raw URL $schema

- **Batch**: 5
- **Audit ref**: AUDIT-050
- **Target file**: `tests/fixtures/14_roadmap.json`
- **Change type**: MODIFY
- **Description**: Update `$schema` from `https://raw.githubusercontent.com/...` to `https://specdev.local/schema/14_roadmap.schema.json`.
- **Test gate**: `pytest tests/ -x --tb=short`
- **Dependencies**: none
- **Estimated LOC**: +1 / -1 / net 0

### FIX-051: Create step_order.schema.json for self-validation (REVISED per D6)

- **Batch**: 5
- **Audit ref**: AUDIT-032
- **Target file**: `schema/step_order.schema.json`
- **Change type**: CREATE
- **Description**: Create a JSON schema validating `tools/step_order.json` structure. **REVISED per D6**: Do NOT include `allowed_upstream_dependencies` in the schema -- it is being removed. Schema should validate: `version` (semver string), `policy` object (with `mode`, `allow_self_dependency`, `allow_forward_dependency`, `require_full_forward_replay_on_change`, `status_write_exemptions`), `steps` array of step IDs, `downstream_consumers` (object mapping step IDs to arrays), `coverage_thresholds` (object). Register in `tools/schema_registry.json`.
- **Test gate**: `python -c "import json; json.load(open('schema/step_order.schema.json'))"`
- **Dependencies**: none
- **Estimated LOC**: +65 / -0 / net +65

### FIX-052: Add 16a/16b/16c phase discrimination to schema registry or schema

- **Batch**: 5
- **Audit ref**: AUDIT-016
- **Target file**: `schema/16_impl_context.schema.json`
- **Change type**: MODIFY
- **Description**: Add `allOf` conditions based on `id` prefix pattern to enforce phase-specific required fields. When `id` matches `^16a-.*`: only `plan` required (current behavior). When `id` matches `^16b-.*`: `plan` AND `execution` required. When `id` matches `^16c-.*`: `plan`, `execution`, AND `review` required. Implement using `allOf` with `if/then` blocks keyed on the `id` pattern.
- **Test gate**: `pytest tests/unit/validation/validators/test_step_validators_core.py tests/integration/test_step_16*.py -x --tb=short`
- **Dependencies**: FIX-018 (Step 16 $defs extraction)
- **Estimated LOC**: +25 / -0 / net +25

**[Batch 5 Gate]:** `pytest tests/ -x --tb=short` -- Expected: all tests pass. Fixture fixes are non-breaking.

---

## Batch 6: Schema Removals (REVISED -- Complete Field Removal per Deep Review)

**This batch is significantly expanded from the original plan.** Previously "Bloat Removal" with 3 tasks (demote to optional). Now "Schema Removals" with 10 tasks (full removal of dead/redundant fields from schemas and config files).

**Ordering within Batch 6**: Schema removals must complete before tool code updates in Batch 7.

### FIX-061: Remove `spec_refs_ingested` from all schemas and core definitions (SUPERSEDES FIX-053)

- **Batch**: 6
- **Audit ref**: AUDIT-002, Deep Review D3
- **Target file**: `schema/core/step_base.schema.json` (primary), `schema/core/collections.schema.json` (definitions)
- **Change type**: MODIFY (2 files)
- **Description**: **SUPERSEDES FIX-053** (was: demote to optional). Per D3, remove entirely: (1) Remove `spec_refs_ingested` from properties and required in `step_base.schema.json`. (2) Remove any residual inline `spec_refs_ingested` declarations from step schemas (safety net if FIX-019 missed some). Zero tool code consumers exist. **Note**: The `specRefIngested` and `specRefsIngestedArray` definitions in `core/collections.schema.json` are removed by FIX-084 (Batch 8), not here.
- **Test gate**: `pytest tests/ -x --tb=short`
- **Dependencies**: FIX-019 (base schema adoption)
- **Estimated LOC**: +0 / -35 / net -35

### FIX-062: Remove `coverage_gaps` from all schemas and core definitions (SUPERSEDES FIX-054)

- **Batch**: 6
- **Audit ref**: AUDIT-003, Deep Review D4
- **Target file**: `schema/core/step_base.schema.json` (primary), `schema/core/collections.schema.json` (definitions), `schema/12_ci_gates.schema.json`
- **Change type**: MODIFY (3 files)
- **Description**: **SUPERSEDES FIX-054** (was: demote to optional in 18/19, keep required in step 12). Per D4, remove entirely from ALL schemas including step 12: (1) Remove `coverage_gaps` from properties and required in `step_base.schema.json`. (2) Remove any residual inline `coverage_gaps` declarations from step schemas, including step-12-specific requirements. The step_12 validator iterates an always-empty array; removing has zero functional impact. **Note**: The `coverageGap` and `coverageGapsArray` definitions in `core/collections.schema.json` are removed by FIX-084 (Batch 8), not here.
- **Test gate**: `pytest tests/ -x --tb=short`
- **Dependencies**: FIX-019 (base schema adoption)
- **Estimated LOC**: +0 / -30 / net -30

### FIX-063: Remove `nested_order` from seed_manifest schema and data (SUPERSEDES FIX-055)

- **Batch**: 6
- **Audit ref**: AUDIT-045, Deep Review D5
- **Target file**: `schema/seed_manifest.schema.json`, `spec/common/seed_manifest.json`
- **Change type**: MODIFY (2 files)
- **Description**: **SUPERSEDES FIX-055** (was: make optional). Per D5, remove entirely: (1) Remove `nested_order` from `required` array AND from `properties` in `seed_manifest.schema.json`. (2) Remove the `nested_order` data block from `spec/common/seed_manifest.json` (~10 lines).
- **Test gate**: `pytest tests/ -x --tb=short`
- **Dependencies**: none
- **Estimated LOC**: +0 / -20 / net -20

### FIX-064: Remove `generation_quality` from all schemas and core definitions (NEW per D1)

- **Batch**: 6
- **Audit ref**: AUDIT-020, Deep Review D1
- **Target file**: `schema/core/step_base.schema.json` (primary), `schema/core/collections.schema.json` (definitions)
- **Change type**: MODIFY (2 files)
- **Description**: **OVERRIDES AUDIT-020 KEEP disposition.** Per D1, remove entirely: (1) Remove `generation_quality` from properties and required in `step_base.schema.json`. (2) Remove any residual inline `generation_quality` declarations from step schemas. Previously kept because of 2 consumers (spec_quality_lint and prompt_schema_sync), but deep review confirmed consumers only check structural presence, never extract value; the assumptions array is always empty; and LLM introspection is unreliable. **Note**: The `generationQuality` definition in `core/collections.schema.json` is removed by FIX-084 (Batch 8), not here.
- **Test gate**: `pytest tests/ -x --tb=short` (will fail until Batch 7 tool updates)
- **Dependencies**: FIX-019 (base schema adoption)
- **Estimated LOC**: +0 / -20 / net -20

### FIX-065: Remove `seed_refs` from all schemas and core definitions (NEW per D2)

- **Batch**: 6
- **Audit ref**: AUDIT-053, Deep Review D2
- **Target file**: `schema/core/step_base.schema.json` (primary), `schema/core/collections.schema.json` (definitions)
- **Change type**: MODIFY (2 files)
- **Description**: **OVERRIDES AUDIT-053 INFO/KEEP disposition.** Per D2, remove entirely: (1) Remove `seed_refs` from properties and required in `step_base.schema.json`. (2) Remove any residual inline `seed_refs` declarations from step schemas. Triple redundancy with prompts + seed_manifest makes this field unnecessary. Seed-to-step mappings should be derived from seed_manifest.json step_requirements. **Note**: The `seedRef` and `seedRefArray` definitions in `core/collections.schema.json` are removed by FIX-084 (Batch 8), not here.
- **Test gate**: `pytest tests/ -x --tb=short` (will fail until Batch 7 tool updates)
- **Dependencies**: FIX-019 (base schema adoption)
- **Estimated LOC**: +0 / -40 / net -40

### FIX-066: Remove `allowed_upstream_dependencies` from step_order.json (NEW per D6)

- **Batch**: 6
- **Audit ref**: AUDIT-058, Deep Review D6
- **Target file**: `tools/step_order.json`
- **Change type**: MODIFY
- **Description**: **OVERRIDES AUDIT-058 INFO/KEEP disposition.** Per D6, remove entirely: Remove the `allowed_upstream_dependencies` object from `tools/step_order.json`. Under strict waterfall, every step's allowed upstream deps are derivable as `steps[0:index_of(step)]`. This removes ~120 lines of redundant, maintenance-heavy configuration. The `downstream_consumers` field is NOT removed (it encodes non-derivable knowledge).
- **Test gate**: `pytest tests/ -x --tb=short` (will fail until Batch 7 tool updates)
- **Dependencies**: none
- **Estimated LOC**: +0 / -120 / net -120

### FIX-067: Make `canonical_proposals` optional in step_base schema (NEW per D9)

- **Batch**: 6
- **Audit ref**: AUDIT-054, Deep Review D9
- **Target file**: `schema/core/step_base.schema.json`
- **Change type**: MODIFY
- **Description**: **PARTIALLY OVERRIDES AUDIT-054 INFO/KEEP disposition.** Per D9, remove `canonical_proposals` from the `required` array in `step_base.schema.json`. Keep the property definition with `default: []`. Consumers already handle absence gracefully (`_proposal_index()` returns empty set if value is not a list). Never non-empty in any real data.
- **Test gate**: `pytest tests/ -x --tb=short`
- **Dependencies**: FIX-001 (base schema creation)
- **Estimated LOC**: +0 / -0 / net 0 (just remove from required array)

### FIX-068: Make `canonical_conflicts` optional in step_base schema (NEW per D10)

- **Batch**: 6
- **Audit ref**: AUDIT-054, Deep Review D10
- **Target file**: `schema/core/step_base.schema.json`
- **Change type**: MODIFY
- **Description**: **PARTIALLY OVERRIDES AUDIT-054 INFO/KEEP disposition.** Per D10, remove `canonical_conflicts` from the `required` array in `step_base.schema.json`. Keep the property definition with `default: []`. Consumers already handle absence gracefully (`_conflict_index()` returns empty set if value is not a list). Never non-empty in any real data.
- **Test gate**: `pytest tests/ -x --tb=short`
- **Dependencies**: FIX-067 (same file, execute sequentially)
- **Estimated LOC**: +0 / -0 / net 0 (just remove from required array)

### FIX-069: Remove `docs_policy` from seed_manifest schema and data (NEW per D7)

- **Batch**: 6
- **Audit ref**: AUDIT-044, Deep Review D7
- **Target file**: `schema/seed_manifest.schema.json`, `spec/common/seed_manifest.json`
- **Change type**: MODIFY (2 files)
- **Description**: **OVERRIDES AUDIT-044 WONTFIX disposition.** Per D7, remove entirely: (1) Remove `docs_policy` from `required` array AND from `properties` in `seed_manifest.schema.json`. (2) Remove the `docs_policy` data block from `spec/common/seed_manifest.json` (~25 lines). docs_policy is lint configuration masquerading as spec data. Its sole consumer (docs_lint.py) is being deleted in Batch 8.
- **Test gate**: `pytest tests/ -x --tb=short` (will fail until Batch 8 docs_lint deletion)
- **Dependencies**: none
- **Estimated LOC**: +0 / -35 / net -35

**[Batch 6 Gate]:** Some tests will fail after this batch because tool code still references removed fields. This is expected -- Batch 7 updates tool code. Run `pytest tests/ --tb=short` to identify all failures, then proceed to Batch 7.

---

## Batch 7: Tool Code Updates (Update validators, linters, CLI for removed fields)

**This is a NEW batch** created by the deep review. It updates all tool code that consumed the fields removed in Batch 6. Must complete before test/fixture updates in Batch 8.

### FIX-070: Update spec_quality_lint.py -- remove checks for removed fields (NEW per D1, D2, D4, D9, D10)

- **Batch**: 7
- **Audit ref**: Deep Review D1, D2, D4, D9, D10
- **Target file**: `tools/specdev_tools/validation/spec_quality_lint.py`
- **Change type**: MODIFY
- **Description**: Update the `_check_required_top_level` function (lines ~175-183). Currently checks 8 of 10 common fields. Remove checks for: `generation_quality` (D1), `seed_refs` (D2), `canonical_proposals` (D9, now optional), `canonical_conflicts` (D10, now optional). The checked field list should now contain only: `id`, `owner`, `created_at`, `canonical_refs_used`. Also remove `coverage_gaps` if it appears anywhere in checks.
- **Test gate**: `pytest tests/ -x --tb=short`
- **Dependencies**: FIX-064, FIX-065, FIX-062, FIX-067, FIX-068
- **Estimated LOC**: +2 / -6 / net -4

### FIX-071: Update prompt_schema_sync.py -- remove removed fields from DRIFT_SENSITIVE_FIELDS (NEW per D1, D2, D9, D10)

- **Batch**: 7
- **Audit ref**: Deep Review D1, D2, D9, D10
- **Target file**: `tools/specdev_tools/generation/prompt_schema_sync.py`
- **Change type**: MODIFY
- **Description**: Update the `DRIFT_SENSITIVE_FIELDS` tuple (line ~27). Remove: `generation_quality` (D1), `seed_refs` (D2), `canonical_proposals` (D9), `canonical_conflicts` (D10). Keep `canonical_refs_used` and other remaining fields.
- **Test gate**: `pytest tests/ -x --tb=short`
- **Dependencies**: FIX-064, FIX-065, FIX-067, FIX-068
- **Estimated LOC**: +1 / -4 / net -3

### FIX-072: Update seed_lint.py -- remove seed_refs validation, derive from seed_manifest (NEW per D2)

- **Batch**: 7
- **Audit ref**: Deep Review D2
- **Target file**: `tools/specdev_tools/validation/seed_lint.py`
- **Change type**: MODIFY
- **Description**: Remove the seed_refs validation logic. Currently, `lint_seeds()` reads `seed_refs` from each spec JSON file (lines ~277-312) and validates against seed_manifest requirements. Per D2, seed_refs no longer exists in spec files. The seed-to-step mapping should be derived from `seed_manifest.json` `step_requirements` directly. Specifically: (1) Remove the `seed_refs` reading loop. (2) Update `_check_seed_content_overlap()` to derive seed-artifact pairs from `step_requirements` instead of from artifact's `seed_refs`. (3) Keep the content overlap check itself (it validates spec output contains tokens from referenced seeds). (4) Remove E520 errors for missing seed_refs (the field no longer exists).
- **Test gate**: `pytest tests/ -x --tb=short`
- **Dependencies**: FIX-065
- **Estimated LOC**: +15 / -40 / net -25

### FIX-073: Update step_12.py validator -- remove coverage_gaps validation (NEW per D4)

- **Batch**: 7
- **Audit ref**: Deep Review D4
- **Target file**: `tools/specdev_tools/validation/validators/step_12.py`
- **Change type**: MODIFY
- **Description**: Remove the coverage_gaps cross-reference validation (lines ~67-72). This code iterates `instance.get("coverage_gaps", [])` and checks each gap's `upstream_item_id` against upstream FR/NFR ID sets (E590). Since coverage_gaps is always empty and is being removed from schemas, this validation code is dead. Remove the entire coverage_gaps iteration block.
- **Test gate**: `pytest tests/ -x --tb=short`
- **Dependencies**: FIX-062
- **Estimated LOC**: +0 / -8 / net -8

### FIX-074: Update consumers of allowed_upstream_dependencies -- derive from step position (NEW per D6)

- **Batch**: 7
- **Audit ref**: Deep Review D6, AUDIT-058
- **Target file**: Multiple files (5 consumers)
- **Change type**: MODIFY (5 files)
- **Description**: The 5 consumers of `allowed_upstream_dependencies` must be updated to derive dependencies from step position instead of reading the explicit map. Create a utility function `compute_allowed_upstream(steps: list, step_id: str) -> list` that returns `steps[0:steps.index(step_id)]`. Tool files to update: (1) `tools/specdev_tools/validation/dag_lint.py` (2) `tools/specdev_tools/validation/dependency_order_lint.py` (3) `tools/specdev_tools/validation/extraction_intent_check.py` (4) `tools/specdev_tools/validation/hallucination_lint.py` (5) `tools/specdev_tools/cli.py`. Place the utility in `tools/specdev_tools/core/constants.py` or a new `tools/specdev_tools/core/step_utils.py`. **R2 addition**: Also update 15 test files in `tests/unit/` that construct mock `step_order.json` data containing `allowed_upstream_dependencies`. These tests will fail when tool code stops reading the field. Update test mocks to omit `allowed_upstream_dependencies` and instead rely on the new `compute_allowed_upstream` utility or provide step lists in the expected order.
- **Test gate**: `pytest tests/ -x --tb=short`
- **Dependencies**: FIX-066
- **Estimated LOC**: +25 / -15 / net +10

### FIX-075: Update canonical/integrity.py -- handle optional canonical_proposals/conflicts (NEW per D9, D10)

- **Batch**: 7
- **Audit ref**: Deep Review D9, D10
- **Target file**: `tools/specdev_tools/canonical/integrity.py`
- **Change type**: MODIFY
- **Description**: Verify that `_proposal_index()` and `_conflict_index()` handle missing fields gracefully. Per the deep review, these already return empty sets when the field is not a list, so this may be a no-op verification. If any code path assumes canonical_proposals/conflicts are always present (e.g., `data["canonical_proposals"]` without `.get()`), update to use `.get("canonical_proposals", [])`.
- **Test gate**: `pytest tests/ -x --tb=short`
- **Dependencies**: FIX-067, FIX-068
- **Estimated LOC**: +2 / -2 / net 0

### FIX-076: Update seed_lint.py -- remove nested_order validation (NEW per D5)

- **Batch**: 7
- **Audit ref**: Deep Review D5
- **Target file**: `tools/specdev_tools/validation/seed_lint.py`
- **Change type**: MODIFY
- **Description**: Remove the `nested_order` referential integrity check (lines ~263-266). This code validates that seed IDs in nested_order exist in the seeds registry. Since nested_order is being removed from the schema and data, this validation is no longer needed. The `global_seed_order` check (lines ~259-261) remains.
- **Test gate**: `pytest tests/ -x --tb=short`
- **Dependencies**: FIX-063
- **Estimated LOC**: +0 / -5 / net -5

### FIX-085: Update step_16.py validator -- remove docs_policy.doc_paths check (NEW per R2 review GAP-1)

- **Batch**: 7
- **Audit ref**: Deep Review D7, D8 (R2 review GAP-1)
- **Target file**: `tools/specdev_tools/validation/validators/step_16.py`
- **Change type**: MODIFY
- **Description**: The step_16 validator reads `docs_policy.doc_paths` from `seed_manifest.json` (lines ~180-183) to validate `docs_impact` paths. After FIX-069 removes `docs_policy` from the schema and data, this code will emit spurious W570 warnings. Remove the `doc_paths` check entirely -- docs_policy is scope creep and should not gate spec validation.
- **Test gate**: `pytest tests/ -x --tb=short`
- **Dependencies**: FIX-069 (docs_policy removal)
- **Estimated LOC**: +0 / -5 / net -5

### FIX-086: Remove `docs-lint` from hardcoded valid command lists (NEW per R2 review GAP-12)

- **Batch**: 7
- **Audit ref**: Deep Review D8 (R2 review GAP-12)
- **Target files**: `tools/specdev_tools/validation/hallucination_lint.py`, `tools/specdev_tools/validation/validators/step_10.py`, `schema/10_governance.schema.json`, `tests/unit/validation/validators/test_step_validators_03_10.py`
- **Change type**: MODIFY (4 files)
- **Description**: After docs-lint deletion, two validators still accept `"docs-lint"` as a valid command string: (1) `hallucination_lint.py` (line ~132) lists it in the valid CI command set. (2) `step_10.py` (line ~44) lists it in valid `pr_rules` enum. Remove `"docs-lint"` from both hardcoded lists to prevent accepting references to a nonexistent command. **R3 additions**: (3) `schema/10_governance.schema.json` (line ~38) -- remove `"docs-lint"` from the `pr_rules` enum in the schema itself (authoritative source). (4) `tests/unit/validation/validators/test_step_validators_03_10.py` -- update `test_step_10_accepts_seed_docs_lint` to remove `"docs-lint"` from the test assertion (test constructs `pr_rules: ["seed-lint", "docs-lint"]` which will fail after enum change).
- **Test gate**: `pytest tests/ -x --tb=short`
- **Dependencies**: FIX-077 (docs_lint.py deletion)
- **Estimated LOC**: +0 / -4 / net -4

**[Batch 7 Gate]:** `pytest tests/ -x --tb=short` -- Expected: most tests pass. Some test fixtures may still reference removed fields; those are addressed in Batch 8.

---

## Batch 8: Test, Fixture, Prompt & CI Updates (REVISED -- expanded from original Batch 7)

**This batch combines the original Batch 7 (test/CI updates) with the massive fixture/prompt cleanup required by the deep review removals, plus the complete docs_lint deletion.**

### Sub-batch 8A: docs_lint Deletion (NEW per D8)

### FIX-077: Delete docs_lint.py (NEW per D8)

- **Batch**: 8
- **Audit ref**: Deep Review D8
- **Target file**: `tools/specdev_tools/validation/docs_lint.py`
- **Change type**: DELETE
- **Description**: Delete the entire docs_lint module. It is scope creep -- checks generic repo READMEs, not spec artifacts. Not part of the spec pipeline. Reuses error code E520 opportunistically. Per the docs_lint assessment, removing it breaks no spec workflow step.
- **Test gate**: `pytest tests/ -x --tb=short` (will fail if tests import docs_lint -- see FIX-079)
- **Dependencies**: FIX-069 (docs_policy removal from schema/data)
- **Estimated LOC**: +0 / -122 / net -122

### FIX-078: Remove docs-lint CLI command from cli.py (NEW per D8)

- **Batch**: 8
- **Audit ref**: Deep Review D8
- **Target file**: `tools/specdev_tools/cli.py`
- **Change type**: MODIFY
- **Description**: Remove the `docs-lint` subcommand registration from cli.py. Remove any import of `docs_lint` module. **R2 addition**: Also remove the `docs_lint` module registration from `tools/specdev_tools/__init__.py` (line ~31: `"docs_lint": "specdev_tools.validation.docs_lint"`). If this registry is used for dynamic imports, leaving it will cause import errors after `docs_lint.py` is deleted.
- **Test gate**: `pytest tests/ -x --tb=short`
- **Dependencies**: FIX-077
- **Estimated LOC**: +0 / -8 / net -8

### FIX-079: Remove docs_lint tests (NEW per D8)

- **Batch**: 8
- **Audit ref**: Deep Review D8
- **Target file**: Test files for docs_lint (search for `test_docs_lint` or `docs_lint` in tests/)
- **Change type**: DELETE or MODIFY
- **Description**: Remove all test files and test functions that test docs_lint functionality. Search `tests/` directory for files importing or testing docs_lint.
- **Test gate**: `pytest tests/ -x --tb=short`
- **Dependencies**: FIX-077, FIX-078
- **Estimated LOC**: +0 / -50 / net -50 (estimated)

### FIX-080: Remove docs-lint from CLAUDE.md and documentation (NEW per D8)

- **Batch**: 8
- **Audit ref**: Deep Review D8
- **Target file**: `CLAUDE.md`, any CI config or prompt files referencing docs-lint
- **Change type**: MODIFY
- **Description**: Remove `docs-lint` from: (1) CLAUDE.md "Core CLI Commands" section. (2) CLAUDE.md "Validation Ritual" section (currently step 3). (3) `prompts/prompt_12_ci_gates.md` (listed as CI gate command). (4) `.github/workflows/ci.yml` (line ~56: `python -m specdev_tools.cli docs-lint spec --repo-root .`) -- **critical, will break CI**. (5) `tools/README.md` (line ~63: lists docs-lint in CLI overview). (6) `docs/developers/reference.md` (lines ~86, 212: CLI example and validation ritual reference). (7) `docs/developers/getting_started.md`, `docs/architecture/governance_architecture.md`, `docs/audit/review_prompt_04_canonical_drift.md`, `docs/audit/review_prompt_02_tooling.md` -- remove any docs-lint or docs_policy references. (8) Any other documentation referencing the command.
- **Test gate**: none (documentation-only)
- **Dependencies**: FIX-077
- **Estimated LOC**: +0 / -10 / net -10

### Sub-batch 8B: Test Fixture and Prompt Cleanup

### FIX-081: Remove generation_quality, seed_refs, spec_refs_ingested, coverage_gaps from all test fixtures (NEW per D1-D4)

- **Batch**: 8
- **Audit ref**: Deep Review D1, D2, D3, D4
- **Target file**: `tests/fixtures/` (40+ files across all step_* directories)
- **Change type**: MODIFY (40+ files)
- **Description**: Scriptable mass removal. For every JSON fixture file in `tests/fixtures/`: (1) Remove `"generation_quality": {"assumptions": []}` or any variant. (2) Remove `"seed_refs": [...]` (whether empty or populated). (3) Remove `"spec_refs_ingested": []`. (4) Remove `"coverage_gaps": []`. Also remove `"canonical_proposals": []` and `"canonical_conflicts": []` from fixtures (D9/D10 -- these are now optional, so removing empty arrays is correct). Execute via script for consistency. **Note**: Some test fixtures may have non-empty seed_refs (e.g., step_00, step_04) -- remove those too. **R2 additions**: Also update: (5) `tests/integration/test_step_16.py` -- 6 test methods construct mock `seed_manifest.json` data containing `docs_policy` (lines ~162, 194, 220, 240, 288, 342); remove `docs_policy` from test data. (6) `tests/unit/validation/linters/test_seed_propagation_trim.py` (line ~58) and `tests/unit/validation/linters/test_seed_content_overlap.py` (line ~31) -- remove `docs_policy` from mock seed_manifest data. (7) `tests/fixtures/seed_manifest/valid_minimal.json` -- remove `docs_policy` and `nested_order`. (8) `tests/fixtures/seed_manifest/invalid_missing_required.json` -- update expected required fields (docs_policy and nested_order are no longer required).
- **Test gate**: `pytest tests/ -x --tb=short`
- **Dependencies**: FIX-061 through FIX-065, FIX-070 through FIX-073
- **Estimated LOC**: +0 / -250 / net -250 (estimated, ~6 lines per fixture x 40+ fixtures)

### FIX-082: Remove generation_quality, seed_refs, coverage_gaps from all prompt Output Contract sections (NEW per D1, D2, D4)

- **Batch**: 8
- **Audit ref**: Deep Review D1, D2, D4
- **Target file**: `prompts/prompt_*.md` (24+ files)
- **Change type**: MODIFY (24+ files)
- **Description**: For every prompt file in `prompts/`: (1) Remove `generation_quality` from Output Contract JSON examples and instructions. (2) Remove `seed_refs` from Output Contract JSON examples, "Seed Ingestion Protocol" sections, and "Coverage Closure" checklist items. (3) Remove `spec_refs_ingested` from Output Contract JSON examples. (4) Remove `coverage_gaps` from Output Contract JSON examples and "Coverage Closure" instructions. (5) Make `canonical_proposals` and `canonical_conflicts` shown as optional: update from "REQUIRED (may be empty [])" to "OPTIONAL -- include only if you encounter novel terms or ambiguous matches." (6) Remove "Self-Audit Gate" instructions about populating generation_quality.assumptions. (7) **R2 addition**: Remove `docs_policy` references from `prompts/prompt_16a_impl_planner.md` (line ~246: instructs LLM to update `docs_policy.readme_depth_by_scope` when adding directories -- invalid after docs_policy removal). (8) **R2 addition**: Also update `prompts/migration/template_*.md` (19 files) which contain `generation_quality`, `seed_refs`, `spec_refs_ingested`, and/or `coverage_gaps` references. (9) **R2 addition**: Update `docs/prompts/shared_expectations.md` (lines ~25, 38) which references `generation_quality`. Execute via script for consistency.
- **Test gate**: `pytest tests/ -x --tb=short` (prompt-schema sync should pass since DRIFT_SENSITIVE_FIELDS was updated in FIX-071)
- **Dependencies**: FIX-071 (prompt_schema_sync updated)
- **Estimated LOC**: +0 / -350 / net -350 (estimated, ~15 lines per prompt x 24 prompts)

### FIX-083: Remove spec_refs_ingested, coverage_gaps, generation_quality, seed_refs from spec data files (NEW per D1-D4)

- **Batch**: 8
- **Audit ref**: Deep Review D1, D2, D3, D4
- **Target file**: `spec/05_interface_contracts.json` (and any other spec JSON files)
- **Change type**: MODIFY
- **Description**: Remove the 4 fields from all spec data files. Currently only `spec/05_interface_contracts.json` exists. Also remove empty canonical_proposals and canonical_conflicts if present (now optional).
- **Test gate**: `./tools/run_specdev.sh validate-all spec --repo-root .`
- **Dependencies**: FIX-061 through FIX-065
- **Estimated LOC**: +0 / -6 / net -6

### Sub-batch 8C: Schema Core Definition Cleanup

### FIX-084: Remove unused definitions from core/collections.schema.json (NEW per D1-D4)

- **Batch**: 8
- **Audit ref**: Deep Review D1, D2, D3, D4
- **Target file**: `schema/core/collections.schema.json`
- **Change type**: MODIFY
- **Description**: Remove the following definitions that are no longer referenced by any schema: (1) `generationQuality` (~15 LOC). (2) `seedRef` and `seedRefArray` (~35 LOC). (3) `specRefIngested` and `specRefsIngestedArray` (~30 LOC). (4) `coverageGap` and `coverageGapsArray` (~25 LOC). Total removal: ~105 LOC. **Scope clarification (R2)**: This is the sole task that removes type definitions from `core/collections.schema.json`. FIX-061/062/064/065 (Batch 6) remove property references from `step_base.schema.json` and residual inline declarations from step schemas, but do NOT touch collections definitions -- that cleanup is deferred to this task.
- **Test gate**: `pytest tests/ -x --tb=short`
- **Dependencies**: FIX-061, FIX-062, FIX-064, FIX-065 (properties removed first)
- **Estimated LOC**: +0 / -105 / net -105

### Sub-batch 8D: Regression Lints & CI (Original Batch 7 tasks)

### FIX-056: Create CI lint for `additionalProperties: false` regression

- **Batch**: 8
- **Audit ref**: AUDIT-033
- **Target file**: `tests/unit/test_schema_quality.py`
- **Change type**: CREATE
- **Description**: Create a parametrized pytest test that recursively traverses all schema files and asserts `additionalProperties: false` (or `unevaluatedProperties: false` for allOf-composed schemas) on every `type: "object"` node. Should cover all schema files plus the new `step_base.schema.json` and `step_order.schema.json`.
- **Test gate**: `pytest tests/unit/test_schema_quality.py -x --tb=short`
- **Dependencies**: All previous batches
- **Estimated LOC**: +60 / -0 / net +60

### FIX-057: Create CI lint for schema nesting depth regression

- **Batch**: 8
- **Audit ref**: AUDIT-034, AUDIT-035
- **Target file**: `tests/unit/test_schema_quality.py` (append to file from FIX-056)
- **Change type**: MODIFY
- **Description**: Add a parametrized pytest test that measures nesting depth per schema and fails if any exceeds threshold. Initial threshold: 9 (current maximum, Step 16). Ratchet down over time. Include per-schema expected depths for regression detection.
- **Test gate**: `pytest tests/unit/test_schema_quality.py -x --tb=short`
- **Dependencies**: FIX-056 (same file)
- **Estimated LOC**: +50 / -0 / net +50

### FIX-058: Create CI lint for description coverage regression

- **Batch**: 8
- **Audit ref**: AUDIT-036
- **Target file**: `tests/unit/test_schema_quality.py` (append to file from FIX-057)
- **Change type**: MODIFY
- **Description**: Add a parametrized pytest test that counts description coverage per schema and fails if total coverage drops below threshold. After Batch 3, set threshold at 85%. Include per-schema coverage report in test output.
- **Test gate**: `pytest tests/unit/test_schema_quality.py -x --tb=short`
- **Dependencies**: FIX-057 (same file), Batch 3 completion
- **Estimated LOC**: +55 / -0 / net +55

### FIX-059: Register new schemas in schema_registry.json

- **Batch**: 8
- **Audit ref**: AUDIT-032 (step_order schema), FIX-001 (step_base)
- **Target file**: `tools/schema_registry.json`
- **Change type**: MODIFY
- **Description**: Add registry entries for: (1) `core/step_base/1` -> `schema/core/step_base.schema.json` (from FIX-001), (2) `step_order.schema.json` -> `schema/step_order.schema.json` (from FIX-051). Verify no duplicate entries introduced.
- **Test gate**: `pytest tests/ -x --tb=short`
- **Dependencies**: FIX-001, FIX-051
- **Estimated LOC**: +6 / -0 / net +6

**[Batch 8 Gate]:** `pytest tests/ -x --tb=short` -- Full suite green. Then run all CLI validation commands:
```bash
./tools/run_specdev.sh validate-all spec --repo-root .
./tools/run_specdev.sh canonical-lint canon --repo-root .
./tools/run_specdev.sh canonical-integrity spec --repo-root .
./tools/run_specdev.sh prompt-sync spec --repo-root .
./tools/run_specdev.sh seed-lint spec --repo-root .
```

Verify that `docs-lint` command is no longer registered (should produce "unknown command" error).

---

## Appendix A: AUDIT-to-FIX Cross-Reference

| AUDIT ID | Severity | FIX ID(s) | Batch | Status |
|---|---|---|---|---|
| AUDIT-001 | CRITICAL | FIX-020 to FIX-034 | 3 | FIX |
| AUDIT-002 | HIGH | FIX-061 | 6 | FIX (REVISED: full removal, was FIX-053 demote) |
| AUDIT-003 | HIGH | FIX-062 | 6 | FIX (REVISED: full removal, was FIX-054 demote) |
| AUDIT-004 | HIGH | FIX-001, FIX-019 | 0, 2 | FIX (REVISED: fewer base fields per D1-D4) |
| AUDIT-005 | HIGH | FIX-010, FIX-018 | 1, 2 | FIX |
| AUDIT-006 | HIGH | FIX-002, FIX-013, FIX-014, FIX-018 | 0, 2 | FIX |
| AUDIT-007 | HIGH | FIX-003, FIX-012, FIX-013 | 0, 2 | FIX |
| AUDIT-008 | HIGH | FIX-039, FIX-040 | 4 | FIX |
| AUDIT-009 | HIGH | FIX-035 | 4 | FIX |
| AUDIT-010 | HIGH | FIX-036 | 4 | FIX |
| AUDIT-011 | HIGH | FIX-004, FIX-014, FIX-018 | 0, 2 | FIX |
| AUDIT-012 | HIGH | FIX-037 | 4 | FIX |
| AUDIT-013 | HIGH | FIX-038 | 4 | FIX |
| AUDIT-014 | HIGH | FIX-020 to FIX-023 | 3 | FIX |
| AUDIT-015 | HIGH | FIX-024, FIX-028 to FIX-034 | 3 | FIX |
| AUDIT-016 | HIGH | FIX-052 | 5 | FIX |
| AUDIT-017 | MEDIUM | FIX-007, FIX-011 | 1, 2 | FIX |
| AUDIT-018 | MEDIUM | FIX-005, FIX-015, FIX-016 | 0, 2 | FIX |
| AUDIT-019 | MEDIUM | FIX-006, FIX-015, FIX-017 | 0, 2 | FIX |
| AUDIT-020 | MEDIUM | FIX-064, FIX-070, FIX-071 | 6, 7 | FIX (REVISED: was KEEP, now REMOVE per D1) |
| AUDIT-021 | MEDIUM | FIX-044 | 4 | FIX |
| AUDIT-022 | MEDIUM | FIX-044 | 4 | FIX |
| AUDIT-023 | MEDIUM | FIX-037 | 4 | FIX |
| AUDIT-024 | MEDIUM | FIX-041 | 4 | FIX |
| AUDIT-025 | MEDIUM | FIX-041 | 4 | FIX |
| AUDIT-026 | MEDIUM | FIX-046 | 5 | FIX |
| AUDIT-027 | MEDIUM | FIX-001, FIX-019 | 0, 2 | FIX |
| AUDIT-028 | MEDIUM | -- | -- | DEFERRED (subsumed by ALIGN-2 URI migration, WONTFIX AUDIT-040) |
| AUDIT-029 | MEDIUM | FIX-048 | 5 | FIX |
| AUDIT-030 | MEDIUM | FIX-047 | 5 | FIX |
| AUDIT-031 | MEDIUM | -- | -- | WONTFIX (intentional co-location) |
| AUDIT-032 | MEDIUM | FIX-051, FIX-059 | 5, 8 | FIX |
| AUDIT-033 | MEDIUM | FIX-056 | 8 | FIX |
| AUDIT-034 | MEDIUM | FIX-057 | 8 | FIX |
| AUDIT-035 | MEDIUM | FIX-057 | 8 | FIX |
| AUDIT-036 | MEDIUM | FIX-058 | 8 | FIX |
| AUDIT-037 | MEDIUM | -- | -- | NO ACTION (descriptions adequate; focus on 808 missing) |
| AUDIT-038 | MEDIUM | FIX-023, FIX-025 to FIX-027 | 3 | FIX |
| AUDIT-039 | MEDIUM | FIX-024, FIX-028 to FIX-034 | 3 | FIX |
| AUDIT-040 | MEDIUM | -- | -- | WONTFIX (ALIGN-2, see justification above) |
| AUDIT-041 | LOW | FIX-008 | 1 | FIX |
| AUDIT-042 | LOW | FIX-009 | 1 | FIX |
| AUDIT-043 | LOW | FIX-018 | 2 | FIX |
| AUDIT-044 | LOW | FIX-069, FIX-077-080, FIX-085, FIX-086 | 6, 7, 8 | FIX (REVISED: was WONTFIX, now REMOVE per D7/D8) |
| AUDIT-045 | LOW | FIX-063 | 6 | FIX (REVISED: was make optional, now REMOVE per D5) |
| AUDIT-046 | LOW | FIX-045 | 4 | FIX |
| AUDIT-047 | LOW | FIX-042 | 4 | FIX |
| AUDIT-048 | LOW | FIX-043 | 4 | FIX |
| AUDIT-049 | LOW | FIX-049 | 5 | FIX |
| AUDIT-050 | LOW | FIX-050 | 5 | FIX |
| AUDIT-051 | LOW | -- | -- | WONTFIX (see justification above) |
| AUDIT-052 | LOW | FIX-060 | 3 | FIX |
| AUDIT-053 | INFO | FIX-065, FIX-072 | 6, 7 | FIX (REVISED: was INFO/KEEP, now REMOVE per D2) |
| AUDIT-054 | INFO | FIX-067, FIX-068, FIX-075 | 6, 7 | PARTIALLY OVERRIDDEN (canonical_refs_used stays; proposals/conflicts optional per D9/D10) |
| AUDIT-055 | INFO | FIX-032 to FIX-034 | 3 | Addressed |
| AUDIT-056 | INFO | -- | -- | No fix (already generic) |
| AUDIT-057 | INFO | -- | -- | No fix (adequate) |
| AUDIT-058 | INFO | FIX-066, FIX-074 | 6, 7 | PARTIALLY OVERRIDDEN (allowed_upstream_deps removed per D6; downstream_consumers stays) |
| AUDIT-059 | INFO | -- | -- | No fix (healthy) |
| AUDIT-060 | INFO | -- | -- | No fix (healthy) |
| AUDIT-061 | INFO | -- | -- | No fix (keep separate) |
| AUDIT-062 | INFO | -- | -- | No fix (complete) |
| AUDIT-063 | INFO | -- | -- | No fix (context for AUDIT-040) |
| AUDIT-064 | INFO | -- | -- | No fix (out of scope) |
| AUDIT-065 | INFO | -- | -- | No fix (acceptable) |

## Appendix B: Special Considerations

### AUDIT-020 (generation_quality) -- REVISED: Now REMOVE (was KEEP)

**Previous disposition**: KEEP -- actively consumed by `spec_quality_lint.py` and listed in `DRIFT_SENSITIVE_FIELDS`. Removing would break prompt-schema sync.

**New disposition per D1**: REMOVE. Deep review established that: (1) `spec_quality_lint.py` only checks key presence, never reads values. (2) `prompt_schema_sync.py` lists it in `DRIFT_SENSITIVE_FIELDS` for structural consistency, not value. (3) The `assumptions` array is always empty in all real data. (4) LLM introspection on assumptions is fundamentally unreliable. (5) A migration script already stripped it down once. Consumer code updates (FIX-070, FIX-071) are minimal (remove from check lists). The "breaking prompt-schema sync" concern is resolved by removing it from `DRIFT_SENSITIVE_FIELDS` simultaneously.

### AUDIT-044 (docs_policy) -- REVISED: Now REMOVE (was WONTFIX)

**Previous disposition**: WONTFIX -- actively consumed by 2 validators. Migration cost exceeds benefit.

**New disposition per D7/D8**: REMOVE docs_policy AND delete docs_lint entirely. Deep review established that: (1) docs_lint is scope creep -- it checks generic repo READMEs, not spec artifacts. (2) It has zero interaction with the spec pipeline (steps 00-16c). (3) It parasitically attaches to seed_manifest, which should only contain seed-related config. (4) It reuses E520 error code opportunistically. (5) The check is shallow (file existence only). Removing the entire feature (docs_lint.py + CLI command + tests + docs_policy config) is cleaner than migrating docs_policy to a separate config file.

### AUDIT-053 (seed_refs) -- REVISED: Now REMOVE (was INFO/KEEP)

**Previous disposition**: INFO -- confirmed healthy, include in base schema.

**New disposition per D2**: REMOVE. Deep review established triple redundancy: (1) seed_manifest.json `step_requirements` is the authoritative source. (2) Prompts hardwire which seeds to use. (3) seed_refs in the artifact is the LLM echoing back what it was told -- not independent verification. The content overlap check (the only genuinely valuable part) can derive seed-artifact pairs from step_requirements directly.

### AUDIT-054 (canonical triad) -- PARTIALLY REVISED per D9/D10

**Previous disposition**: INFO -- architecture sound, no simplification needed.

**New disposition**: `canonical_refs_used` remains required (4 active consumers, populated with real data). `canonical_proposals` and `canonical_conflicts` made optional: never non-empty in any real data; consumers handle absence gracefully; mandating empty arrays everywhere is ceremony without value.

### AUDIT-058 (allowed_upstream_dependencies) -- PARTIALLY REVISED per D6

**Previous disposition**: INFO -- well-consumed, complementary to downstream_consumers.

**New disposition**: Remove `allowed_upstream_dependencies`. Under strict waterfall, it is 100% derivable from step position (every entry is a prefix of the steps array). 5 consumers updated to call a utility function. `downstream_consumers` is NOT removed -- it encodes non-derivable workflow knowledge. `step_order.json` shrinks from ~345 lines to ~80 lines.

### AUDIT-028 (URI inconsistency) -- DEFERRED

URI normalization is subsumed by the larger ALIGN-2 URI migration effort (AUDIT-040, WONTFIX). Fixing just the naming inconsistency without the full migration would create churn that gets redone during ALIGN-2. Defer to that effort.

### AUDIT-031 (Canon schemas outside schema/) -- WONTFIX

P1-E proposes moving `canon/kind.schema.json` and `canon/aliases.schema.json` under `schema/canon/`. AUDIT-057 (INFO) confirms the flat structure is adequate. Canon schema-data co-location is intentional design. Moving would require updating `$ref` paths in `canon.schema.json`, `kind.schema.json`, `aliases.schema.json`, registry entries, and all canon data files. Cost exceeds benefit.

### AUDIT-037 (_migration_notes boilerplate) -- NO ACTION

The 19 identical `_migration_notes` descriptions inflate coverage metrics but the descriptions themselves are adequate. Focus effort on the 808 properties without any description. The coverage regression lint (FIX-058) should exclude `_migration_notes` from its denominator for accurate reporting.

### FIX-019 Risk Mitigation (allOf base schema adoption)

FIX-019 is the highest-risk task. `additionalProperties: false` in JSON Schema evaluates against properties defined in the current schema keyword, not properties inherited via `allOf`. This means:
- Option A: Move `additionalProperties: false` to each step schema's portion (NOT the base), listing all properties visible at that level. JSON Schema 2020-12 uses `unevaluatedProperties` instead, which DOES consider `allOf` siblings.
- Option B: Use `unevaluatedProperties: false` instead of `additionalProperties: false` in step schemas. This is the correct Draft 2020-12 approach.
- **Recommendation**: Use `unevaluatedProperties: false` on the step-specific portion. Verified: jsonschema 4.25.1 fully supports Draft 2020-12 `unevaluatedProperties`.
- **Additional risk**: After FIX-019, any tool code that reads schema files and looks for `properties` at the top level will not find inherited properties. Confirmed: `_schema_candidates` in `integrity.py` already handles `allOf`, but other tools should be audited before execution.

### Batch 4 Breaking Changes

Batch 4 contains field renames (FIX-037, FIX-041, FIX-044) that are breaking changes. For each:
1. Update the schema
2. Update the step validator to accept BOTH old and new names
3. Update test fixtures
4. Update prompt templates
5. Update spec data files (if any exist with old names)

Consider adding deprecation aliases in a migration period.

### Batch 4 Migration Sub-Plan: Affected Files per Rename

**FIX-037** (`service_skeleton` -> `project_skeleton`, `route_map` -> `interface_map`):
- Schema: `schema/15_scaffold.schema.json`
- Validator: `tools/specdev_tools/validation/validators/step_15.py`
- Prompt: `prompts/prompt_15_scaffold.md`
- Test fixtures: `tests/fixtures/step_15/` (all valid/invalid fixtures referencing these fields)
- Spec data: `spec/15_scaffold.json` (if exists)

**FIX-041** (`implemented_endpoints` -> `implemented_interfaces`):
- Schema: `schema/16_impl_context.schema.json`
- Validator: `tools/specdev_tools/validation/validators/step_16.py`
- Prompt: `prompts/prompt_16_impl_context.md`, `prompts/prompt_16a_plan.md`, `prompts/prompt_16b_code.md`, `prompts/prompt_16c_review.md`
- Test fixtures: `tests/fixtures/step_16*/` (all fixtures referencing `implemented_endpoints`)
- Spec data: any `spec/16*.json` files

**FIX-044** (`route` -> `path`, `request_schema_ref` -> `input_schema_ref`, `response_schema_ref` -> `output_schema_ref`):
- Schema: `schema/05_interface_contracts.schema.json`
- Validator: `tools/specdev_tools/validation/validators/step_05.py`
- Prompt: `prompts/prompt_05_interface_contracts.md`
- Test fixtures: `tests/fixtures/step_05/` (all fixtures referencing these fields)
- Spec data: `spec/05_interface_contracts.json` (if exists)

**Migration strategy**: Each validator should accept BOTH old and new field names for one minor version cycle, then drop old names. Consider adding a `canonical-autofix` rule to auto-rename fields in existing spec data files.

### Batch 6-8 Ordering Rationale (Deep Review Removals)

The deep review removals create a 3-phase dependency chain:
1. **Batch 6 (Schema Removals)**: Remove fields from JSON schemas and config files. This makes schemas stop requiring these fields, but tool code that reads them will break.
2. **Batch 7 (Tool Code Updates)**: Update validators, linters, and CLI code to stop reading removed fields. Some tests may still fail because fixtures still contain the fields (harmless but noisy).
3. **Batch 8 (Fixture/Prompt/Test Cleanup)**: Remove the fields from all test fixtures, prompts, spec data files, and documentation. Also delete docs_lint and add regression lints.

This ordering ensures: schemas are updated first (so new spec files validate correctly), then tools are updated (so validators work with new schemas), then test data is cleaned up (so tests pass cleanly).

## Appendix C: Estimated LOC Summary by Batch (REVISED)

| Batch | Tasks | Added | Removed | Net |
|---|---|---|---|---|
| 0: Foundation | 6 | +96 | -0 | +96 |
| 1: Core Fixes | 4 | +34 | -16 | +18 |
| 2: Step DRY | 9 | +36 | -521 | -485 |
| 3: Descriptions | 16 | +760 | -2 | +758 |
| 4: Genericity | 11 | +64 | -33 | +31 |
| 5: Structure | 7 | +118 | -3 | +115 |
| 6: Schema Removals | 9 | +0 | -300 | -300 |
| 7: Tool Code Updates | 9 | +45 | -87 | -42 |
| 8: Tests, Fixtures, Prompts, CI | 12 | +171 | -901 | -730 |
| **Total** | **83** | **+1,324** | **-1,863** | **-539** |

**Note on R2 revision**: The original plan had net +583 LOC. The deep review removals (D1-D10) flip the net to **-539 LOC** -- a significant reduction in total codebase size. The largest contributors to the reduction are: fixture cleanup (~-250 LOC), prompt cleanup (~-350 LOC), docs_lint deletion (~-190 LOC), core/collections definition cleanup (~-105 LOC), and step_order.json cleanup (~-120 LOC). These more than offset the description additions (~+760 LOC).

## Appendix D: Deep Review Decision Evidence Summary

For each decision, the evidence source and key finding:

| Decision | Evidence Source | Key Finding |
|---|---|---|
| D1: Remove generation_quality | p4-deep-review-user-concerns.md Q3, p4-deep-review-user-concerns-r3.md Q1 | Consumers check presence only; value always `{"assumptions": []}` everywhere; LLM introspection unreliable |
| D2: Remove seed_refs | p4-deep-review-user-concerns.md Q5, p4-deep-review-user-concerns-r3.md Q2 | Triple redundancy (seed_manifest + prompts + artifact); LLM self-report not independent verification |
| D3: Remove spec_refs_ingested | p4-deep-review-user-concerns.md Q5 Part A | Zero consumers in tool code; every instance is `[]`; confirmed dead by 2 agents |
| D4: Remove coverage_gaps | p4-deep-review-coverage-gaps-docs-policy.md Q1 | Always empty; sole consumer (step_12) iterates empty array; no tool computes it |
| D5: Remove nested_order | p4-deep-review-user-concerns.md Q4 Action 1, p4-deep-review-user-concerns-r2.md Q6 | Single layer with same 2 seeds as global_seed_order; zero information gain |
| D6: Remove allowed_upstream_dependencies | p4-deep-review-user-concerns.md Q4 Action 3, p4-deep-review-user-concerns-r2.md Q6 | 100% derivable from step position under strict waterfall; 250+ lines of pure redundancy |
| D7: Remove docs_policy | p4-deep-review-user-concerns-r3.md Q3, p4-deep-review-coverage-gaps-docs-policy.md Q2 | Lint config in seed metadata; semantically misplaced; sole consumer (docs_lint) being deleted |
| D8: Delete docs_lint | p4-docs-lint-assessment.md | Scope creep; checks repo READMEs not spec artifacts; not part of spec pipeline; reuses E520 opportunistically |
| D9: Optional canonical_proposals | p4-deep-review-user-concerns.md Q6, p4-deep-review-user-concerns-r2.md Q5 | Never non-empty in any file; consumers handle absence gracefully |
| D10: Optional canonical_conflicts | p4-deep-review-user-concerns.md Q6, p4-deep-review-user-concerns-r2.md Q5 | Never non-empty in any file; consumers handle absence gracefully |

## Appendix E: Superseded FIX Tasks

| Original FIX | Original Batch | Original Action | New FIX | New Action | Reason |
|---|---|---|---|---|---|
| FIX-053 | 6 | Demote spec_refs_ingested to optional | FIX-061 | Remove entirely | D3: escalated from demote to remove |
| FIX-054 | 6 | Demote coverage_gaps to optional (18/19) | FIX-062 | Remove entirely from all 19 | D4: escalated from demote to remove |
| FIX-055 | 6 | Make nested_order optional | FIX-063 | Remove entirely | D5: escalated from optional to remove |
