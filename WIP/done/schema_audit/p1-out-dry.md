# P1-A: DRY & Reusability -- Findings

## Summary
- Total findings: 14
- Critical: 0 | High: 4 | Medium: 6 | Low: 3 | Info: 1

---

## Findings

### FINDING-001: Common 11-field boilerplate repeated across all 19 step schemas (~988 LOC total)
- **Severity**: HIGH
- **Category**: DRY
- **Location**: All 19 step schemas (schema/00_charter.schema.json through schema/16_impl_context.schema.json)
- **Description**: Every step schema repeats 11 identical top-level property declarations (`id`, `owner`, `created_at`, `seed_refs`, `spec_refs_ingested`, `generation_quality`, `canonical_refs_used`, `canonical_proposals`, `canonical_conflicts`, `coverage_gaps`, `_migration_notes`) and 10 corresponding `required` array entries. This boilerplate consumes approximately 52 LOC per schema (15 lines for the first 5 props, 27 lines for the last 6 props, 10 required entries). Across 19 schemas: 19 * 52 = ~988 LOC of pure duplication.
- **Evidence**: From `schema/00_charter.schema.json` lines 8-22 (id, owner, created_at, spec_refs_ingested, seed_refs declarations), lines 158-184 (generation_quality through _migration_notes), and lines 187-200 (10 common required entries). Identical blocks appear in all 19 step schemas -- verified programmatically that all 19 contain all 11 fields.
- **Recommendation**: Create a `core/step_base.schema.json` with `$anchor: stepBase` defining these 11 common properties and 10 common required fields. Each step schema would then use `allOf: [{"$ref": "core/.../stepBase"}, {step-specific properties}]`. This reduces ~988 LOC to ~19 `$ref` lines plus the single 52-LOC base definition. **Compatibility note**: The `_schema_properties` function in `tools/specdev_tools/canonical/integrity.py` (line 553) already handles `allOf` composition via `_schema_candidates()` which traverses `allOf` branches and collects properties. The `spec_quality_lint.py` `_check_required_top_level()` (line 173) operates on **data** (checks `key not in data`), not schema structure, so it is also compatible. The `seed_lint.py` reads `instance.get("seed_refs")` from data, not schema properties. No validator relies on flat schema-level property enumeration that would break with allOf composition.

---

### FINDING-002: `spec_refs_ingested` is dead schema -- zero tool code consumers
- **Severity**: HIGH
- **Category**: DRY
- **Location**: All 19 step schemas (required field) + `schema/core/collections.schema.json` lines 432-462 (definitions: `specRefIngested`, `specRefsIngestedArray`)
- **Description**: The field `spec_refs_ingested` is required in all 19 step schemas and defined in core/collections (2 definitions, ~30 LOC). However, `grep -r "spec_refs_ingested" tools/specdev_tools/` returns **zero results**. No validator, linter, or generator reads this field. The `spec_quality_lint.py` `_check_required_top_level()` function (line 173) deliberately omits it from its 8-field check list. Every test fixture populates it with an empty array.
- **Evidence**: `grep -r "spec_refs_ingested" tools/specdev_tools/` produces no matches. The `_check_required_top_level()` in `spec_quality_lint.py` checks: `id`, `owner`, `created_at`, `seed_refs`, `generation_quality`, `canonical_refs_used`, `canonical_proposals`, `canonical_conflicts` -- 8 fields. It skips both `spec_refs_ingested` and `coverage_gaps`.
- **Recommendation**: Demote `spec_refs_ingested` from `required` to optional in all 19 step schemas. This field does NOT appear in `DRIFT_SENSITIVE_FIELDS` in `prompt_schema_sync.py` (line 24), so removal has no prompt-schema sync impact. If the field serves a theoretical future purpose (upstream artifact hash tracking), document that intent and keep the definition in core/collections but remove it from the required arrays.

---

### FINDING-003: `environmentName` and `stageName` are exact duplicates in core/collections
- **Severity**: MEDIUM
- **Category**: DRY
- **Location**: `schema/core/collections.schema.json` lines 198-216
- **Description**: `environmentName` and `stageName` are defined with identical type (`string`), identical enum values (`["dev", "ci", "staging", "prod"]`), and identical structure. They are separate `$anchor`s with no semantic distinction. `environmentName` is referenced by `02a_delivery_baseline.schema.json` (line 32) and `16_impl_context.schema.json` (line 1711). `stageName` is referenced by `07_nfrs.schema.json` (line 71). Both serve the same purpose: naming deployment stages/environments.
- **Evidence**: `core/collections.schema.json` lines 198-216:
  ```json
  "environmentName": { "$anchor": "environmentName", "type": "string", "enum": ["dev", "ci", "staging", "prod"] },
  "stageName": { "$anchor": "stageName", "type": "string", "enum": ["dev", "ci", "staging", "prod"] }
  ```
- **Recommendation**: Deprecate `stageName` in favor of `environmentName` (or vice versa). Update the single `stageName` reference in `07_nfrs.schema.json` line 71 to use `environmentName`. Keep `stageName` as an alias temporarily for backward compatibility, then remove.

---

### FINDING-004: HTTP method enum inconsistency between Step 05 and Step 15
- **Severity**: MEDIUM
- **Category**: DRY
- **Location**: `schema/05_interface_contracts.schema.json` lines 52-59, `schema/15_scaffold.schema.json` lines 57-65
- **Description**: Step 05 defines `method` as `["GET", "POST", "PUT", "PATCH", "DELETE"]` (5 values). Step 15 defines `method` as `["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"]` (7 values). Step 15 adds OPTIONS and HEAD, and reorders PATCH/DELETE. Since Step 15 (scaffold) generates routes from Step 05 (interface contracts), the scaffold schema accepts methods that cannot be defined in the contract schema. This mismatch will cause validation failures if a scaffold uses OPTIONS or HEAD.
- **Evidence**: Step 05 line 53: `"enum": ["GET", "POST", "PUT", "PATCH", "DELETE"]`. Step 15 line 57: `"enum": ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"]`.
- **Recommendation**: Extract an `httpMethod` atom to `core/atoms.schema.json` with the full 7-value enum `["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]` and reference it from both Step 05 and Step 15. If Step 05 intentionally restricts to 5 methods, document that as a constraint and use `allOf` to narrow the base enum. The 16_impl_context `drift.checks[].method` enum (`["runtime-sample", "log-diff", "schema-diff", "trace-replay"]`) is semantically different and should NOT share this atom.

---

### FINDING-005: Protocol enum inconsistency between Step 02 and Step 05
- **Severity**: MEDIUM
- **Category**: DRY
- **Location**: `schema/02_system_sketch.schema.json` lines 116-123, `schema/05_interface_contracts.schema.json` lines 41-46
- **Description**: Step 02 defines `protocol` as `["http", "grpc", "event", "rpc", "db", "file"]` (6 values). Step 05 defines `protocol` as `["http", "grpc", "ws", "mqtt"]` (4 values). The sets overlap on `http` and `grpc` but diverge: Step 02 has `event`, `rpc`, `db`, `file` (infrastructure-level); Step 05 has `ws`, `mqtt` (API-level). This is partially intentional (different abstraction levels) but creates confusion when tracing connections to APIs.
- **Evidence**: Step 02 line 117: `"enum": ["http", "grpc", "event", "rpc", "db", "file"]`. Step 05 line 42: `"enum": ["http", "grpc", "ws", "mqtt"]`.
- **Recommendation**: Create a `core/atoms#protocol` definition with the union set or two clearly-named variants: `connectionProtocol` (Step 02's infrastructure-level) and `apiProtocol` (Step 05's application-level). This makes the intentional divergence explicit rather than appearing as an accidental inconsistency.

---

### FINDING-006: `severityLevel` enum `["low", "medium", "high", "critical"]` duplicated in 3 locations
- **Severity**: MEDIUM
- **Category**: DRY
- **Location**: `schema/16_impl_context.schema.json` `$defs.severityLevel` (lines 50-57), `schema/11_redteam.schema.json` `threats[].severity` (lines 92-98), `schema/14_roadmap.schema.json` `milestones[].risk_status` (lines 67-73)
- **Description**: The 4-level severity scale `["low", "medium", "high", "critical"]` is defined inline in three separate schemas with identical values. Step 16 already extracts it to a `$defs` local definition but does not promote it to core/. Steps 11 and 14 inline it directly in property definitions.
- **Evidence**: Step 16 `$defs.severityLevel` line 51: `"enum": ["low", "medium", "high", "critical"]`. Step 11 line 93: `"enum": ["low", "medium", "high", "critical"]`. Step 14 line 68: `"enum": ["low", "medium", "high", "critical"]`.
- **Recommendation**: Promote `severityLevel` to `core/atoms.schema.json` as a new atom with `$anchor: severityLevel`. Replace all three inline definitions with `$ref`. Note: the 2-value variant `["warn", "error"]` in Step 06 (invariants) is semantically different (rule enforcement levels) and should remain separate. The `["blocking", "non_blocking"]` and `["blocking", "major", "minor", "nit"]` variants in Step 16 are also distinct concepts (ambiguity severity vs. review finding severity).

---

### FINDING-007: Milestone `status` enum duplicated identically in Steps 09 and 14
- **Severity**: MEDIUM
- **Category**: DRY
- **Location**: `schema/09_impl_plan.schema.json` `milestones[].status` (lines 57-66), `schema/14_roadmap.schema.json` `milestones[].status` (lines 55-64)
- **Description**: Both Step 09 and Step 14 define `milestones[].status` with identical enum `["pending", "in_progress", "done", "deferred"]` and identical `"default": "pending"`. Since Step 14's roadmap refines Step 09's implementation plan, these are the same concept and should share a definition.
- **Evidence**: Step 09 line 59: `"enum": ["pending", "in_progress", "done", "deferred"]`. Step 14 line 57: `"enum": ["pending", "in_progress", "done", "deferred"]`. Both include `"default": "pending"`.
- **Recommendation**: Extract a `milestoneStatus` atom to `core/atoms.schema.json` with values `["pending", "in_progress", "done", "deferred"]` and `"default": "pending"`. Reference from both Step 09 and Step 14. Step 14's `tasks[].status` uses a subset `["pending", "in_progress", "done"]` (no `deferred`) which could use `allOf` to narrow, or remain as a separate `taskStatus` atom.

---

### FINDING-008: `canonicalId` pattern duplicated between `core/canon.schema.json` and `core/collections.schema.json`
- **Severity**: LOW
- **Category**: DRY
- **Location**: `schema/core/canon.schema.json` line 39, `schema/core/collections.schema.json` line 95
- **Description**: The canonical ID pattern `^cn:[a-z0-9.]+:[a-z_]+:[a-z0-9-]+$` is defined in two places: as `$defs.canonicalId` in `core/canon.schema.json` (line 37-40) with `$anchor: canonicalId`, and inline in `core/collections.schema.json` `canonicalRef.properties.id` (line 95) as a direct pattern property without `$ref`. The canon.schema.json definition is canonical, but collections.schema.json inlines the same pattern rather than referencing it.
- **Evidence**: `core/canon.schema.json` line 39: `"pattern": "^cn:[a-z0-9.]+:[a-z_]+:[a-z0-9-]+$"`. `core/collections.schema.json` line 95: `"pattern": "^cn:[a-z0-9.]+:[a-z_]+:[a-z0-9-]+$"`.
- **Recommendation**: Replace the inline pattern in `core/collections.schema.json` `canonicalRef.properties.id` with `"$ref": "https://specdev.local/schema/core/canon/1#canonicalId"` to ensure a single source of truth.

---

### FINDING-009: `owner` pattern inconsistency between `core/atoms` and `core/canon`
- **Severity**: LOW
- **Category**: DRY
- **Location**: `schema/core/atoms.schema.json` line 38, `schema/core/canon.schema.json` line 49
- **Description**: Two different `owner` definitions exist in core: `atoms#owner` has pattern `^[a-z][a-z0-9_-]*$` (allows underscores AND hyphens), while `canon#owner` has pattern `^[a-z][a-z0-9-]*$` (allows hyphens only, NO underscores). They serve slightly different purposes (artifact owner vs. canonical registry entry owner), but the naming collision creates confusion. All 19 step schemas reference `atoms#owner` for their top-level `owner` field.
- **Evidence**: `core/atoms.schema.json` line 38: `"pattern": "^[a-z][a-z0-9_-]*$"`. `core/canon.schema.json` line 49: `"pattern": "^[a-z][a-z0-9-]*$"`.
- **Recommendation**: Either (a) unify to a single pattern (prefer `^[a-z][a-z0-9_-]*$` as the broader pattern), or (b) rename `canon#owner` to `canonOwner` to avoid the naming collision. Option (b) is safer as it avoids changing validation behavior for existing canonical registry data.

---

### FINDING-010: `fr_id` in Step 16 inlines kebabId pattern instead of using $ref
- **Severity**: LOW
- **Category**: DRY
- **Location**: `schema/16_impl_context.schema.json` line 1753
- **Description**: Step 16's `review.semantic_review.fr_coverage[].fr_id` inlines the pattern `"pattern": "^[a-z0-9]+(?:-[a-z0-9]+)*$"` directly instead of using `$ref` to `atoms/1#kebabId` (which defines the same pattern at `core/atoms.schema.json` line 20). This is a minor DRY violation but risks divergence if the kebabId pattern is ever updated.
- **Evidence**: Step 16 line 1753: `"fr_id": { "type": "string", "pattern": "^[a-z0-9]+(?:-[a-z0-9]+)*$" }`. Compare with `core/atoms.schema.json` line 20: `"pattern": "^[a-z0-9]+(?:-[a-z0-9]+)*$"`.
- **Recommendation**: Replace the inline definition with `"fr_id": { "$ref": "https://specdev.local/schema/core/atoms/1#kebabId" }`.

---

### FINDING-011: `specRef.type` (Step 16) vs `mitigations[].type` (Step 11) -- near-identical artifact reference enums
- **Severity**: MEDIUM
- **Category**: DRY
- **Location**: `schema/16_impl_context.schema.json` `$defs.specRef.type` (lines 13-22), `schema/11_redteam.schema.json` `mitigations[].type` (lines 67-76)
- **Description**: Both enums reference the same concept (artifact type for cross-referencing). Step 16 uses `["fr", "api", "nfr", "inv", "fixture", "doc", "code"]` while Step 11 uses `["fr", "api", "nfr", "inv", "fixture", "doc", "capability"]`. They share 6 of 7 values, differing only in `code` (Step 16) vs `capability` (Step 11). This creates a maintenance burden: adding a new traceable artifact type requires updating both enums independently.
- **Evidence**: Step 16 $defs.specRef.type line 15: `["fr", "api", "nfr", "inv", "fixture", "doc", "code"]`. Step 11 mitigations[].type line 68: `["fr", "api", "nfr", "inv", "fixture", "doc", "capability"]`.
- **Recommendation**: Extract a `core/atoms#artifactRefType` with the union enum `["fr", "api", "nfr", "inv", "fixture", "doc", "code", "capability"]`. If Step 16 and Step 11 need to restrict to subsets, use `allOf` with the base `$ref` plus a narrowing `enum` constraint. Alternatively, both schemas could use the full union.

---

### FINDING-012: Canonical triad (`canonical_refs_used`, `canonical_proposals`, `canonical_conflicts`) -- architecture assessment
- **Severity**: INFO
- **Category**: DRY
- **Location**: All 19 step schemas + `schema/core/collections.schema.json` (6 definitions: canonicalRef, canonicalRefArray, canonicalProposal, canonicalProposalArray, canonicalConflict, canonicalConflictArray)
- **Description**: The canonical triad consists of 3 required fields in every step schema (3 * 19 = 57 field declarations). The core/collections file devotes 6 definitions (~100 LOC) to support them. Three of these fields (`canonical_refs_used`, `canonical_proposals`, `canonical_conflicts`) are listed in `DRIFT_SENSITIVE_FIELDS` in `prompt_schema_sync.py` (line 24). This triad serves a legitimate architectural purpose: tracking which canonical registry entries were used, proposing new ones, and flagging conflicts. The architecture is sound -- the three fields represent distinct phases of canonical vocabulary management (reference, proposal, conflict resolution). However, the "Array" wrapper definitions (`canonicalRefArray`, `canonicalProposalArray`, `canonicalConflictArray`) are thin wrappers that could be inlined.
- **Evidence**: `prompt_schema_sync.py` line 24: `DRIFT_SENSITIVE_FIELDS = ("dependencies", "trace", "generation_quality", "canonical_refs_used", "canonical_proposals", "canonical_conflicts")`. These are actively consumed by `canonical/integrity.py`, `canonical/autofix.py`, and `canonical/lint.py` (P1-C owns the full consumer analysis).
- **Recommendation**: The triad architecture is appropriate -- do NOT simplify to fewer fields. However, the base schema proposal (FINDING-001) would eliminate the per-schema duplication. The 3 "Array" wrapper definitions in collections.schema.json could be removed if step schemas referenced the singular definitions directly (e.g., `"type": "array", "items": {"$ref": "...#canonicalRef"}`), as `canonical_proposals` and `canonical_conflicts` already do in step schemas (they inline the array wrapper rather than using `$ref` to the Array definition). This would save ~18 LOC in core/collections.

---

### FINDING-013: `seed_refs` actively consumed -- confirmed NOT dead schema
- **Severity**: HIGH (positive confirmation -- corrects potential false removal)
- **Category**: DRY
- **Location**: `tools/specdev_tools/validation/seed_lint.py` lines 149-310, `tools/specdev_tools/validation/spec_quality_lint.py` line 179
- **Description**: Unlike `spec_refs_ingested` (FINDING-002), `seed_refs` IS actively consumed by multiple tool modules. `seed_lint.py` validates seed_refs arrays: checks that seed_ids exist in the registry (line 300-303), verifies required seeds per step (line 306-310), and validates hash integrity (line 149-154). `spec_quality_lint.py` includes `seed_refs` in its required-field checks (line 179). This field MUST remain required.
- **Evidence**: `seed_lint.py` line 149: `seed_refs = instance.get("seed_refs", [])`, line 300: `used_seed_ids = {ref.get("seed_id") for ref in seed_refs ...}`, line 303: `errors.append(make_error("E520", f"{file_path}: seed_refs includes unknown seed_id..."))`.
- **Recommendation**: No change needed. `seed_refs` is correctly required in all 19 step schemas and actively validated. Include in base schema (FINDING-001).

---

### FINDING-014: Step 16 local `$defs` are candidates for core/ extraction
- **Severity**: HIGH
- **Category**: DRY
- **Location**: `schema/16_impl_context.schema.json` lines 8-100 (`$defs` block: `specRef`, `severityLevel`, `executionStatus`, `evidenceObject`)
- **Description**: Step 16 defines 4 local `$defs` referenced 7 times within the schema via `#/$defs/...`. These definitions have reuse potential: `severityLevel` is already duplicated in Steps 11 and 14 (FINDING-006). `specRef` overlaps with Step 11's mitigations type enum (FINDING-011). `executionStatus` (`["passed", "failed", "blocked", "partial"]`) and `evidenceObject` are Step 16-specific but could benefit future schemas that model execution or review workflows.
- **Evidence**: Step 16 is the ONLY schema using local `$defs` (all others are $ref-only). This concentrates 7 local references in one 1,868-LOC schema. `$defs.severityLevel` and `$defs.specRef.type` have confirmed duplicates in other schemas.
- **Recommendation**: Promote at minimum: (1) `severityLevel` to `core/atoms.schema.json` (FINDING-006), (2) the artifact-ref-type enum to `core/atoms.schema.json` (FINDING-011). Consider promoting `executionStatus` and `evidenceObject` to `core/collections.schema.json` if implementation-loop schemas proliferate. Step 16 would then drop from 4 local `$defs` to 0-2.

---

## Answers to Plan Questions

### Q1: Enums appearing in 2+ schemas with different values

| Enum Concept | Schemas | Values | Proposed Core Atom |
|---|---|---|---|
| HTTP method | 05, 15 | 5 vs 7 values | `core/atoms#httpMethod` (7 values) |
| Protocol | 02, 05 | 6 vs 4 values | `core/atoms#connectionProtocol` + `core/atoms#apiProtocol` |
| Severity (4-level) | 11, 14, 16 | identical `[low,med,high,critical]` | `core/atoms#severityLevel` |
| Milestone status | 09, 14 | identical `[pending,in_progress,done,deferred]` | `core/atoms#milestoneStatus` |
| Artifact ref type | 11, 16 | 7 values each, differ by 1 | `core/atoms#artifactRefType` (8-value union) |
| Environment name | core (x2) | identical `[dev,ci,staging,prod]` | Merge `stageName` into `environmentName` |

### Q2: Inline property definitions extractable to core/

- `severityLevel` (3 schemas) -> `core/atoms#severityLevel`
- `milestoneStatus` (2 schemas) -> `core/atoms#milestoneStatus`
- `httpMethod` (2 schemas) -> `core/atoms#httpMethod`
- `artifactRefType` (2 schemas) -> `core/atoms#artifactRefType`
- `executionStatus` (1 schema, but useful) -> `core/atoms#executionStatus`
- `evidenceObject` (1 schema) -> `core/collections#evidenceObject`

### Q3: Is allOf composition with a base schema feasible?

Yes. Verified against the 4 critical validators listed in the plan:
- `spec_quality_lint.py` `_check_required_top_level()` (line 173): checks `key not in data` -- operates on data instances, not schema structure. Compatible.
- `canonical/integrity.py` `_schema_properties()` (line 553): traverses `allOf` branches via `_schema_candidates()`. Already handles composition. Compatible.
- `canonical/autofix.py` (line 183): loads schema via registry and validates. Uses jsonschema library which natively supports allOf. Compatible.
- `seed_lint.py` (line 149): reads `instance.get("seed_refs")` from data. Compatible.

### Q4: Do `seed_refs` and `spec_refs_ingested` serve a real validation purpose?

- **`seed_refs`**: YES. Actively validated by `seed_lint.py` (hash verification, required seed checks, unknown seed detection). Also checked by `spec_quality_lint.py`. Must remain required.
- **`spec_refs_ingested`**: NO. Zero tool code consumers. Not in `DRIFT_SENSITIVE_FIELDS`. Not checked by `spec_quality_lint.py`. Dead schema -- recommend demotion to optional.

### Q5: Is the canonical triad architecturally sound?

Yes, the triad is architecturally sound. The three fields map to three distinct workflow phases:
1. `canonical_refs_used` -- tracking which canonical entries were referenced (consumption)
2. `canonical_proposals` -- proposing new vocabulary (creation)
3. `canonical_conflicts` -- flagging ambiguous matches (resolution)

All three are `DRIFT_SENSITIVE_FIELDS`. The architecture should NOT be simplified to fewer fields. The per-schema duplication should be addressed via the base schema (FINDING-001), not by removing fields.

### Q6: Drift-sensitive field impact for proposed removals

| Field Proposed for Change | In DRIFT_SENSITIVE_FIELDS? | Impact |
|---|---|---|
| `spec_refs_ingested` (demote to optional) | NO | Safe to demote |
| `generation_quality` (P1-C scope) | YES | Removal would break prompt-schema sync |
| `canonical_refs_used` | YES | Must remain |
| `canonical_proposals` | YES | Must remain |
| `canonical_conflicts` | YES | Must remain |
| `coverage_gaps` | NO | Safe to modify (but P1-C owns this analysis) |

### Q7: allOf base schema compatibility with validators

Verified -- see Q3 above. No validator relies on flat schema-level property enumeration. All operate either on data instances or use `_schema_candidates()` which already traverses `allOf` branches. An `allOf` base schema composition is safe to implement.
