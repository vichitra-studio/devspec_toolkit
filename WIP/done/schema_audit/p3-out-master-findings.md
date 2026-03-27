# P3: Consolidated Master Findings

**Date**: 2026-03-19
**Phase**: P3 Consolidation
**Source**: 6 P1 agents (P1-A DRY, P1-B Descriptions, P1-C Bloat, P1-D Genericity, P1-E Structure, P1-F Research)
**Branch**: `codex/canonical-drift-review-plan`

---

## Summary Statistics

### Total Findings

| Metric | Value |
|---|---|
| P1 findings (pre-dedup) | 74 |
| Duplicates merged/dropped | 9 |
| **Unique findings (post-dedup)** | **65** |

### Breakdown by Severity

| Severity | Count |
|---|---|
| CRITICAL | 1 |
| HIGH | 15 |
| MEDIUM | 24 |
| LOW | 12 |
| INFO | 13 |
| **Total** | **65** |

### Breakdown by Category

| Category | Count |
|---|---|
| DRY | 14 |
| DESCRIPTION | 7 |
| BLOAT | 8 |
| GENERICITY | 14 |
| STRUCTURE | 14 |
| RESEARCH | 8 |
| **Total** | **65** |

### Dropped/Merged Findings (Duplicates)

| Dropped Finding | Merged Into | Reason |
|---|---|---|
| P1-C:FINDING-C01 (`spec_refs_ingested` dead) | AUDIT-002 (P1-A:FINDING-002) | Same finding; P1-A more detailed on core/collections LOC. Both HIGH. P1-C evidence merged. |
| P1-C:FINDING-C10 (canonical triad consumers) | AUDIT-054 (P1-A:FINDING-012) | P1-A owns architecture; P1-C consumer evidence merged into AUDIT-054. |
| P1-F:FINDING-004 (ALIGN-1 inline patterns) | AUDIT-006, AUDIT-007, AUDIT-043 | P1-F confirmed P1-A findings; evidence merged into respective AUDIT entries. |
| P1-F:FINDING-014 (specRef.type vs mitigations[].type) | AUDIT-011 (P1-A:FINDING-011) | Same finding; P1-A more detailed. P1-F research gap context merged in. |
| P1-F:FINDING-013 (URI pattern inconsistency) | AUDIT-028 (P1-E:FINDING-003) | Same finding; P1-E more detailed. P1-F research roadmap context merged in. |
| P1-F:FINDING-003 (ALIGN-6 description coverage) | AUDIT-001, AUDIT-014 (P1-B findings) | P1-B is definitive source; P1-F confirms. Evidence merged. |
| P1-F:FINDING-010 (ALIGN-5 depth claim incorrect) | AUDIT-034 (P1-F:FINDING-002) | Merged into nesting depth finding as sub-point about roadmap inaccuracy. |
| P1-F:FINDING-008 (ALIGN-7 --json output) | AUDIT-064 (P1-F:FINDING-007) | All out-of-scope tool/CI gaps consolidated into single AUDIT entry. |
| P1-C:FINDING-C04 (spec_quality_lint 8/10 fields) | AUDIT-002 and AUDIT-003 | Reclassified as corroborating evidence, not standalone finding. |

---

## Findings by Severity

---

## CRITICAL

### AUDIT-001: 93.5% of schema properties lack descriptions -- critical LLM context gap
- **Severity**: CRITICAL
- **Category**: DESCRIPTION
- **Source**: P1-B:FINDING-001, corroborated by P1-F:FINDING-003
- **Location**: All 26 schema files
- **Description**: 808 of 864 unique properties across all schema files have no `"description"` field. LLMs consuming these schemas for spec generation have almost no semantic context beyond property names. For ambiguous properties (`status` with 13 variants, `severity` with 9 variants, `type` with 11 variants, `scope` with 4 incompatible types), the lack of descriptions creates high hallucination risk. Excluding the 19 identical `_migration_notes` descriptions, effective coverage drops to 37/845 = 4.4%.
- **Evidence**: P1-B verified counts: 56 properties with descriptions, 808 without, 864 total = 6.5% coverage. Core definitions have near-zero coverage: `core/canon.schema.json` 0%, `core/errors.schema.json` 0%, `core/atoms.schema.json` 33% (2/6), `core/collections.schema.json` 10.2% (5/49). Since core definitions are referenced 448 times via `$ref`, adding descriptions there has maximum propagation impact.
- **Recommendation**: Add descriptions to all 808 properties. Priority: (1) core/ definitions (~80 descriptions, 448 downstream references), (2) ambiguous properties (`status`, `severity`, `type`, `scope`, `method`), (3) step-specific properties. P1-B provides complete draft descriptions for all missing properties. Treat Step 16 (228 missing descriptions) as a dedicated batch.

---

## HIGH

### AUDIT-002: `spec_refs_ingested` is dead schema -- zero tool code consumers
- **Severity**: HIGH (corroborated by 2 agents; corroboration confirms accuracy but does not increase technical impact)
- **Category**: DRY
- **Source**: P1-A:FINDING-002, P1-C:FINDING-C01
- **Location**: All 19 step schemas (required field) + `schema/core/collections.schema.json` lines 432-462 (definitions: `specRefIngested`, `specRefsIngestedArray`)
- **Description**: `spec_refs_ingested` is required in all 19 step schemas and defined in core/collections (~30 LOC). However, `grep -r "spec_refs_ingested" tools/specdev_tools/` returns **zero results**. No validator, linter, or generator reads this field. `spec_quality_lint.py` deliberately omits it from its 8-field check list. Every test fixture and prompt populates it as `[]`. It does NOT appear in `DRIFT_SENSITIVE_FIELDS`. Both P1-A and P1-C independently confirmed this is dead schema.
- **Evidence**: Zero grep results in tool code. `spec_quality_lint.py:175-183` checks 8 of 10 common fields, skipping `spec_refs_ingested` and `coverage_gaps`. 38 occurrences across 19 schema files (2 per file). All 24+ prompt files reference it only as `"spec_refs_ingested": []`.
- **Recommendation**: Demote from `required` to optional in all 19 step schemas. Keep the core definition for potential future use. Update 24+ prompt templates. No prompt-schema sync impact (not in `DRIFT_SENSITIVE_FIELDS`).

---

### AUDIT-003: `coverage_gaps` -- mandatory in 19 schemas, consumed by only 1 step validator
- **Severity**: HIGH
- **Category**: BLOAT
- **Source**: P1-C:FINDING-C02
- **Location**: All 19 step schemas; consumer at `tools/specdev_tools/validation/validators/step_12.py:67-72`
- **Description**: `coverage_gaps` is required in all 19 step schemas but only read by the Step 12 (CI Gates) validator for `upstream_item_id` reference checking. `spec_quality_lint.py` deliberately skips it. Unlike `spec_refs_ingested`, it IS referenced in all 24+ prompt files with active instructions and serves a genuine traceability purpose. Not in `DRIFT_SENSITIVE_FIELDS`.
- **Evidence**: Only `step_12.py:67-72` reads `coverage_gaps`. No other module consumes it. Prompt files instruct: "MUST be recorded in `coverage_gaps[]`".
- **Recommendation**: Keep as a property in all 19 schemas (serves design-time traceability purpose in prompts), but make optional rather than required in schemas where no validator reads it (all except step 12). Alternatively, add a cross-step `coverage_gaps` validator to justify mandatory status.

---

### AUDIT-004: Common 11-field boilerplate repeated across all 19 step schemas (~988 LOC)
- **Severity**: HIGH
- **Category**: DRY
- **Source**: P1-A:FINDING-001
- **Location**: All 19 step schemas (`schema/00_charter.schema.json` through `schema/16_impl_context.schema.json`)
- **Description**: Every step schema repeats 11 identical top-level property declarations (`id`, `owner`, `created_at`, `seed_refs`, `spec_refs_ingested`, `generation_quality`, `canonical_refs_used`, `canonical_proposals`, `canonical_conflicts`, `coverage_gaps`, `_migration_notes`) and 10 corresponding `required` array entries. ~52 LOC per schema, ~988 LOC total across 19 schemas.
- **Evidence**: Verified programmatically that all 19 contain all 11 fields. Compatibility verified against 4 critical validators: `spec_quality_lint.py` operates on data not schema structure; `canonical/integrity.py` already handles `allOf` via `_schema_candidates()`; `seed_lint.py` reads from data instances.
- **Recommendation**: Create `core/step_base.schema.json` with `$anchor: stepBase` defining these 11 common properties. Each step schema would use `allOf: [{"$ref": "core/.../stepBase"}, {step-specific}]`. Reduces ~988 LOC to ~19 `$ref` lines plus single 52-LOC base. All validators confirmed compatible with `allOf` composition.

---

### AUDIT-005: Step 16 local `$defs` are candidates for core/ extraction
- **Severity**: HIGH
- **Category**: DRY
- **Source**: P1-A:FINDING-014
- **Location**: `schema/16_impl_context.schema.json` lines 8-100 (`$defs` block)
- **Description**: Step 16 defines 4 local `$defs` (`specRef`, `severityLevel`, `executionStatus`, `evidenceObject`) referenced 7 times within the schema. `severityLevel` is duplicated in Steps 11 and 14 (AUDIT-008). `specRef.type` overlaps with Step 11's mitigations type enum (AUDIT-011). Step 16 is the ONLY schema using local `$defs`.
- **Evidence**: 4 local `$defs` with 7 internal references in the 1,868-LOC schema. `severityLevel` and `specRef.type` have confirmed duplicates in other schemas.
- **Recommendation**: Promote at minimum: (1) `severityLevel` to `core/atoms.schema.json` (AUDIT-008), (2) artifact-ref-type enum to `core/atoms.schema.json` (AUDIT-011). Consider `executionStatus` and `evidenceObject` for `core/collections.schema.json`.

---

### AUDIT-006: `severityLevel` enum duplicated in 3 schemas
- **Severity**: HIGH (corroborated: P1-A + P1-F)
- **Category**: DRY
- **Source**: P1-A:FINDING-006, confirmed by P1-F:FINDING-004
- **Location**: `schema/16_impl_context.schema.json` `$defs.severityLevel`, `schema/11_redteam.schema.json` `threats[].severity`, `schema/14_roadmap.schema.json` `milestones[].risk_status`
- **Description**: The 4-level severity scale `["low", "medium", "high", "critical"]` is defined inline in three separate schemas with identical values. Step 16 extracts it to `$defs` but does not promote to core/. Steps 11 and 14 inline it directly.
- **Evidence**: Step 16 `$defs.severityLevel` line 51, Step 11 line 93, Step 14 line 68 -- all `["low", "medium", "high", "critical"]`.
- **Recommendation**: Promote to `core/atoms.schema.json` as `$anchor: severityLevel`. Replace all three inline definitions with `$ref`. Note: the 2-value variant `["warn", "error"]` in Step 06 and the `["blocking", "non_blocking"]` variant in Step 16 are semantically distinct and should remain separate.

---

### AUDIT-007: Milestone `status` enum duplicated in Steps 09 and 14
- **Severity**: HIGH (corroborated: P1-A + P1-F)
- **Category**: DRY
- **Source**: P1-A:FINDING-007, confirmed by P1-F:FINDING-004
- **Location**: `schema/09_impl_plan.schema.json` `milestones[].status`, `schema/14_roadmap.schema.json` `milestones[].status`
- **Description**: Both schemas define identical enum `["pending", "in_progress", "done", "deferred"]` with identical `"default": "pending"`. Step 14's roadmap refines Step 09's implementation plan, so these are the same concept.
- **Evidence**: Step 09 line 59, Step 14 line 57 -- identical values and defaults.
- **Recommendation**: Extract `milestoneStatus` atom to `core/atoms.schema.json` with `$anchor: milestoneStatus`. Reference from both schemas.

---

### AUDIT-008: Core `environmentName` enum hardcodes 4 deployment environments
- **Severity**: HIGH
- **Category**: GENERICITY
- **Source**: P1-D:FINDING-009
- **Location**: `schema/core/collections.schema.json`:198-206; `schema/02a_delivery_baseline.schema.json`:37-41
- **Description**: `environmentName` is hardcoded to `["dev", "ci", "staging", "prod"]`. Step 02a compounds this by requiring ALL FOUR environments as mandatory keys with `minProperties: 4`. This 4-environment model is wrong for: libraries/SDKs (no deployment environments), embedded systems (`["dev", "test", "factory", "field"]`), CLI tools (`["dev", "release"]`), mobile apps (`["debug", "release", "beta"]`). Step 02a validation would REJECT valid data for any non-web-service project.
- **Evidence**: `core/collections.schema.json` `environmentName` enum. Step 02a `required: ["dev", "ci", "staging", "prod"]` + `minProperties: 4`. Step 16 narrows to `["dev", "staging", "prod"]`.
- **Recommendation**: Move to canonical registry for project-specific extensibility. Change from closed enum to pattern-validated string. Remove hardcoded `required` and `minProperties: 4` from Step 02a; use `minProperties: 1` instead.

---

### AUDIT-009: Step 05 `method` enum hardcodes HTTP verbs only
- **Severity**: HIGH
- **Category**: GENERICITY
- **Source**: P1-D:FINDING-001
- **Location**: `schema/05_interface_contracts.schema.json`:51-59
- **Description**: `apis[].method` is restricted to `["GET", "POST", "PUT", "PATCH", "DELETE"]` -- pure HTTP verbs. This makes Step 05 unusable for CLI tools (commands/subcommands), event-driven systems (publish/subscribe), gRPC (unary/streaming), or library SDKs (function signatures). Ironically, the schema's own `protocol` field supports `"grpc"`, `"ws"`, and `"mqtt"`, but `method` only accepts HTTP verbs.
- **Evidence**: `method` enum `["GET", "POST", "PUT", "PATCH", "DELETE"]` but `protocol` allows `["http", "grpc", "ws", "mqtt"]`. A gRPC interface has no valid `method` value.
- **Recommendation**: Make `method` conditionally validated based on `protocol`, or make it a free-form string with pattern constraint and move valid values to canonical registry. Consider renaming to `operation_type`.

---

### AUDIT-010: Step 05 `parameters[].in` enum is HTTP-location-specific
- **Severity**: HIGH
- **Category**: GENERICITY
- **Source**: P1-D:FINDING-002
- **Location**: `schema/05_interface_contracts.schema.json`:83-88
- **Description**: `parameters[].in` enum `["query", "path", "header"]` -- HTTP-specific parameter locations matching OpenAPI. Missing even for HTTP: `"body"` and `"cookie"`. Entirely missing for non-HTTP: `"argv"`, `"stdin"`, `"env"`, `"config"`, `"payload"`, `"metadata"` (gRPC).
- **Evidence**: Enum `["query", "path", "header"]` with no non-HTTP options.
- **Recommendation**: Extend to cover non-HTTP locations or move to canonical registry. Consider making `in` conditional on `protocol` via `allOf/if/then`.

---

### AUDIT-011: `specRef.type` vs `mitigations[].type` -- near-identical artifact reference enums
- **Severity**: HIGH (corroborated: P1-A + P1-F)
- **Category**: DRY
- **Source**: P1-A:FINDING-011, P1-F:FINDING-014
- **Location**: `schema/16_impl_context.schema.json` `$defs.specRef.type`, `schema/11_redteam.schema.json` `mitigations[].type`
- **Description**: Both enums reference the same concept (artifact type for cross-referencing). Step 16: `["fr", "api", "nfr", "inv", "fixture", "doc", "code"]`. Step 11: `["fr", "api", "nfr", "inv", "fixture", "doc", "capability"]`. They share 6 of 7 values, differing only in `code` vs `capability`. No canonical "reference type" enum exists despite multiple schemas needing one. P1-F notes this gap is NOT captured in the research roadmap.
- **Evidence**: Step 16 `$defs.specRef.type` line 15; Step 11 `mitigations[].type` line 68. `core/collections#traceRef` also has a `type` property using a different pattern.
- **Recommendation**: Define canonical `referenceType` enum in core/ with union set `["fr", "api", "nfr", "inv", "fixture", "doc", "code", "capability"]`. Both schemas `$ref` the shared definition. If step-specific restrictions needed, use `allOf` narrowing.

---

### AUDIT-012: Step 15 `route_map` is inherently web-service-specific
- **Severity**: HIGH
- **Category**: GENERICITY
- **Source**: P1-D:FINDING-005
- **Location**: `schema/15_scaffold.schema.json`:43-76
- **Description**: `route_map` is a required field whose items have `api_ref`, `path`, and `method` (HTTP verb enum). This would be meaningless for CLI tools, libraries, data pipelines, desktop/mobile apps, or embedded systems. Making it required means Step 15 cannot validate for any non-web project.
- **Evidence**: `route_map` in top-level `required` array (line 139). Items require `api_ref`, `path`, `method` with HTTP verb enum.
- **Recommendation**: Rename to `interface_map` or `entry_points`. Generalize item schema. Remove from unconditional `required` array. Allow alternatives like `command_map` (CLIs), `export_map` (libraries), or `stage_map` (pipelines).

---

### AUDIT-013: Step 12 `token_permissions` is GitHub Actions-specific
- **Severity**: HIGH
- **Category**: GENERICITY
- **Source**: P1-D:FINDING-007
- **Location**: `schema/12_ci_gates.schema.json`:88-99
- **Description**: `token_permissions` uses GitHub Actions-specific pattern: object with string keys (`contents`, `packages`) mapped to `["read", "write", "none"]`. GitLab CI, Jenkins, CircleCI do not use this model. Description explicitly says "e.g. {'contents': 'read', 'packages': 'write'}" -- GitHub-specific scope names.
- **Evidence**: `token_permissions` with `additionalProperties: { type: "string", enum: ["read", "write", "none"] }`. `runner_labels` with examples `'self-hosted', 'ubuntu-latest'` also GitHub-flavored.
- **Recommendation**: Generalize to CI-provider-agnostic description. Consider adding `ci_provider` field for conditional validation. Or make `token_permissions` a generic key-value map.

---

### AUDIT-014: core/ definitions have near-zero descriptions -- maximum propagation impact
- **Severity**: HIGH
- **Category**: DESCRIPTION
- **Source**: P1-B:FINDING-003
- **Location**: `schema/core/atoms.schema.json`, `schema/core/collections.schema.json`, `schema/core/errors.schema.json`, `schema/core/canon.schema.json`
- **Description**: Core definitions referenced 448 times via `$ref` have the worst description coverage: `core/canon.schema.json` 0% (0/31), `core/errors.schema.json` 0% (0/3), `core/atoms.schema.json` 33% (2/6), `core/collections.schema.json` 10.2% (5/49). Adding descriptions here provides the highest-leverage fix for the description gap.
- **Evidence**: `kebabId` (most-referenced definition, 60+ uses) has no description. `core/errors.schema.json` zero descriptions. `core/canon.schema.json` zero descriptions on all 38 properties.
- **Recommendation**: Prioritize core/ descriptions first. ~80 descriptions propagating to 448 downstream references. P1-B provides complete draft descriptions.

---

### AUDIT-015: Ambiguous property names with different semantics across schemas
- **Severity**: HIGH
- **Category**: DESCRIPTION
- **Source**: P1-B:FINDING-004
- **Location**: Multiple schemas
- **Description**: Several property names are reused with incompatible semantics: `status` (13+ variants), `severity` (9 variants), `type` (11 variants), `scope` (4 incompatible types), `method` (3 contexts), `target` (3 contexts), `id` (3 formats). Without descriptions, LLMs cannot distinguish which semantics apply.
- **Evidence**: Step 16 alone uses `severity` with 3 different scales: `["blocking", "non_blocking"]` for ambiguities, `["low", "medium", "high", "critical"]` for alerts, `["blocking", "major", "minor", "nit"]` for findings.
- **Recommendation**: These properties MUST have descriptions. P1-B provides specifically crafted draft descriptions for disambiguation.

---

### AUDIT-016: 16a/16b/16c share a single schema despite distinct pipeline phases
- **Severity**: HIGH
- **Category**: STRUCTURE
- **Source**: P1-E:FINDING-004
- **Location**: `tools/schema_registry.json:25-27` (all point to `schema/16_impl_context.schema.json`)
- **Description**: Steps 16a (plan), 16b (code), 16c (review) are distinct pipeline phases with different data expectations. The single schema marks only `plan` as required; `execution` and `review` are optional. A step-16c artifact passes validation even with empty `review` data. `step_order.json` treats them as fully distinct steps with different dependencies and consumers.
- **Evidence**: Registry aliases all resolve to same file. Required fields: only `plan` is step-specific required. Each step has its own prompt file.
- **Recommendation**: Option A (preferred): Add `allOf` conditions based on `id` pattern or `phase` discriminator to require `execution` for 16b and `review` for 16c. Option B: Create wrapper schemas per phase.

---

## MEDIUM

### AUDIT-017: `environmentName` and `stageName` are exact duplicates in core/collections
- **Severity**: MEDIUM
- **Category**: DRY
- **Source**: P1-A:FINDING-003
- **Location**: `schema/core/collections.schema.json` lines 198-216
- **Description**: Both defined with identical enum `["dev", "ci", "staging", "prod"]` and identical structure. `environmentName` used by Steps 02a and 16; `stageName` used by Step 07 only. No semantic distinction.
- **Evidence**: Lines 198-216: identical type, enum, and structure.
- **Recommendation**: Deprecate `stageName` in favor of `environmentName`. Update Step 07 reference. Related to AUDIT-008 (environment enum flexibility).

---

### AUDIT-018: HTTP method enum inconsistency between Step 05 and Step 15
- **Severity**: MEDIUM
- **Category**: DRY
- **Source**: P1-A:FINDING-004
- **Location**: `schema/05_interface_contracts.schema.json`:52-59, `schema/15_scaffold.schema.json`:57-65
- **Description**: Step 05 defines `method` as 5 HTTP verbs; Step 15 defines 7 (adds OPTIONS, HEAD). Since Step 15 generates routes from Step 05, the scaffold accepts methods that cannot be defined in the contract schema.
- **Evidence**: Step 05: `["GET", "POST", "PUT", "PATCH", "DELETE"]`. Step 15: `["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"]`.
- **Recommendation**: Extract `httpMethod` atom to `core/atoms.schema.json` with full 7-value enum. Reference from both schemas. Related to AUDIT-009 (genericity).

---

### AUDIT-019: Protocol enum inconsistency between Step 02 and Step 05
- **Severity**: MEDIUM
- **Category**: DRY
- **Source**: P1-A:FINDING-005
- **Location**: `schema/02_system_sketch.schema.json`:116-123, `schema/05_interface_contracts.schema.json`:41-46
- **Description**: Step 02: `["http", "grpc", "event", "rpc", "db", "file"]` (6 values). Step 05: `["http", "grpc", "ws", "mqtt"]` (4 values). Overlap on `http` and `grpc` only. Different abstraction levels (infrastructure vs. API).
- **Evidence**: Step 02 line 117; Step 05 line 42.
- **Recommendation**: Create clearly-named variants: `connectionProtocol` (Step 02) and `apiProtocol` (Step 05) in `core/atoms.schema.json` to make the intentional divergence explicit.

---

### AUDIT-020: `generation_quality` -- mandatory overhead with minimal value payload
- **Severity**: MEDIUM
- **Category**: BLOAT
- **Source**: P1-C:FINDING-C03
- **Location**: All 19 step schemas; consumers at `spec_quality_lint.py:180` and `prompt_schema_sync.py:27`
- **Description**: Required in all 19 schemas, IS actively consumed by 2 modules, and IS in `DRIFT_SENSITIVE_FIELDS`. However, its actual payload is just `{"assumptions": []}`. A migration script (`strip_generation_quality.py`) confirms it once had more fields. Removal would break prompt-schema sync.
- **Evidence**: `spec_quality_lint.py:180` checks presence. `prompt_schema_sync.py:27` lists it as drift-sensitive. `core/collections.schema.json:generationQuality` defines only `required: ["assumptions"]`.
- **Recommendation**: Keep as required (actively consumed, drift-sensitive). LOW priority consideration: flatten `assumptions` to top-level field to eliminate wrapper object. Migration cost is high.

---

### AUDIT-021: Step 05 `route` field name implies HTTP URL paths
- **Severity**: MEDIUM
- **Category**: GENERICITY
- **Source**: P1-D:FINDING-003
- **Location**: `schema/05_interface_contracts.schema.json`:48-50
- **Description**: `apis[].route` naming signals HTTP bias. For CLI tools = "command path", libraries = "module path", gRPC = "service/method path". Field is optional (not required), which mitigates impact.
- **Evidence**: `"route": { "type": "string" }` -- no constraints, optional.
- **Recommendation**: Rename to `path` or `identifier`. Accept both via deprecation alias if backward compatibility needed.

---

### AUDIT-022: Step 05 `request_schema_ref`/`response_schema_ref` assume request-response pattern
- **Severity**: MEDIUM
- **Category**: GENERICITY
- **Source**: P1-D:FINDING-004
- **Location**: `schema/05_interface_contracts.schema.json`:61-66
- **Description**: These field names assume synchronous request-response. Does not fit fire-and-forget events, streaming protocols, pub/sub systems, or CLI tools (stdin/stdout). Both are optional, mitigating the issue.
- **Evidence**: `"request_schema_ref": { "type": "string" }`, `"response_schema_ref": { "type": "string" }` -- both optional.
- **Recommendation**: Generalize to `input_schema_ref` and `output_schema_ref`. Works for all paradigms.

---

### AUDIT-023: Step 15 `service_skeleton` naming assumes web services
- **Severity**: MEDIUM
- **Category**: GENERICITY
- **Source**: P1-D:FINDING-006
- **Location**: `schema/15_scaffold.schema.json`:23-42
- **Description**: Named `service_skeleton` (implying running service) with `framework` described as "Web framework". For CLI/library/pipeline, "service" is misleading. Field is required. Only `framework`'s description is biased; `language` and `modules` are generic.
- **Evidence**: `framework` description: "Web framework (e.g., fastapi, nextjs, gin)."
- **Recommendation**: Rename to `project_skeleton`. Update `framework` description to include non-web examples. Naming-only change with no structural impact.

---

### AUDIT-024: Step 16 `checklist[].layer` enum is web-architecture-biased
- **Severity**: MEDIUM
- **Category**: GENERICITY
- **Source**: P1-D:FINDING-012
- **Location**: `schema/16_impl_context.schema.json`:315-327
- **Description**: Layer enum `["db", "model", "service", "api", "integration", "tests", "docs", "config", "security"]` assumes layered web architecture. Only `"tests"`, `"docs"`, `"config"`, `"security"` are truly generic. CLI, library, embedded, and data pipeline projects have different relevant layers.
- **Evidence**: Enum with 5 web-specific values (`db`, `model`, `service`, `api`, `integration`) and 4 generic values.
- **Recommendation**: Move layer values to canonical registry for project-specific extensibility, or change from closed enum to pattern-validated string.

---

### AUDIT-025: Step 16 `implemented_endpoints` naming assumes web service endpoints
- **Severity**: MEDIUM
- **Category**: GENERICITY
- **Source**: P1-D:FINDING-010
- **Location**: `schema/16_impl_context.schema.json`:1641-1646
- **Description**: Field name assumes "endpoints" (web concept). Structure is generic (array of traceIds). Only the name is biased. Required field.
- **Evidence**: `"implemented_endpoints": { "type": "array", "items": { "$ref": "...#traceId" } }` -- structure is generic.
- **Recommendation**: Rename to `implemented_interfaces` or `implemented_items`. Naming-only change.

---

### AUDIT-026: seed_manifest.schema.json missing `$schema` property definition
- **Severity**: MEDIUM (downgraded from CRITICAL -- masked by validator workaround)
- **Category**: STRUCTURE
- **Source**: P1-E:FINDING-001
- **Location**: `schema/seed_manifest.schema.json` (properties object, line 7)
- **Description**: Schema sets `additionalProperties: false` but does not define `$schema` as a property. The data file `spec/common/seed_manifest.json` includes `"$schema"`. The validator at `validate.py:144` strips `$schema` before validation, masking the error. Direct `jsonschema.validate()` would reject it.
- **Evidence**: Running validation without strip: "Additional properties are not allowed ('$schema' was unexpected)". Canon schemas correctly define `$schema`.
- **Recommendation**: Add `"$schema": { "type": "string", "format": "uri" }` to properties.

---

### AUDIT-027: No step schema defines `$schema` as a property
- **Severity**: MEDIUM (downgraded from HIGH -- masked by validator workaround)
- **Category**: STRUCTURE
- **Source**: P1-E:FINDING-002
- **Location**: All 19 step schemas
- **Description**: All step schemas set `additionalProperties: false` but none define `$schema` as a property. 2+ spec data files and 68+ test fixtures include `$schema` URIs. Validator strips `$schema` before validation, masking the incompatibility. Canon schemas correctly define `$schema`.
- **Evidence**: Every step schema returns `False` for `"$schema" in properties`.
- **Recommendation**: Add `"$schema": { "type": "string", "format": "uri" }` to all step schemas. Can be included in the `step_base.schema.json` proposed in AUDIT-004.

---

### AUDIT-028: URI naming inconsistency between core/canon schemas and step schemas
- **Severity**: MEDIUM
- **Category**: STRUCTURE
- **Source**: P1-E:FINDING-003, corroborated by P1-F:FINDING-013
- **Location**: `tools/schema_registry.json` -- all 29 entries
- **Description**: Two URI patterns coexist: versioned path (`core/atoms/1`) for 6 core/canon entries and filename pattern (`00_charter.schema.json`) for 23 step entries. P1-F confirms this inconsistency is not captured as a distinct issue in the research roadmap (subsumed by ALIGN-2).
- **Evidence**: `core/atoms.schema.json` `$id = "https://specdev.local/schema/core/atoms/1"` vs `00_charter.schema.json` `$id = "https://specdev.local/schema/00_charter.schema.json"`.
- **Recommendation**: Normalize to versioned path style. Requires updating `$id` in all step schemas, registry, data files, and fixtures. Do as part of ALIGN-2 URI migration or as a standalone normalization.

---

### AUDIT-029: Test fixture references non-existent schema `13b_database_schema`
- **Severity**: MEDIUM
- **Category**: STRUCTURE
- **Source**: P1-E:FINDING-005
- **Location**: `tests/fixtures/step_13/valid_extension.json:$schema`
- **Description**: References `https://specdev.local/schema/13b_database_schema.schema.json` but no such schema file exists. Not in `schema_registry.json`. No `*13b*` file exists.
- **Evidence**: `find devspec_toolkit -name "*13b*"` returns empty.
- **Recommendation**: Update fixture `$schema` to reference `13_extension_generator.schema.json`, or create the missing schema if planned.

---

### AUDIT-030: 22 of 25 canon/kinds/ data files missing `$schema` property
- **Severity**: MEDIUM
- **Category**: STRUCTURE
- **Source**: P1-E:FINDING-008
- **Location**: `canon/kinds/` -- 22 files lack `$schema`
- **Description**: Only 3 of 25 kind registry files include `$schema`. The remaining 22 have none. Validation pipeline cannot automatically determine which schema governs these files.
- **Evidence**: Missing in: `acronym.json`, `action.json`, `capability.json`, `command.json`, `completeness_dimension.json`, `dependency.json`, `entity.json`, `environment.json`, `event.json`, `governance_label.json`, `id_pattern.json`, `interface.json`, `metric.json`, `policy.json`, `risk_category.json`, `role.json`, `stage.json`, `status.json`, `tag.json`, `tech_stack.json`, `term.json`, `unit.json`.
- **Recommendation**: Add `"$schema": "https://specdev.local/schema/canon/kind/1"` to all 22 files.

---

### AUDIT-031: Canon schemas live outside `schema/` directory
- **Severity**: MEDIUM
- **Category**: STRUCTURE
- **Source**: P1-E:FINDING-009
- **Location**: `canon/kind.schema.json`, `canon/aliases.schema.json`
- **Description**: 2 schema files in `canon/` alongside data files; all other 24 schemas in `schema/`. Co-location with data may be intentional design (canon schemas validate canon data) but creates split requiring lookup in two directory trees.
- **Evidence**: 24 in `schema/` + 2 in `canon/` = 26 total.
- **Recommendation**: Two options: (A) Move to `schema/canon/` for single schema tree, or (B) Keep as intentional domain locality. Document the convention either way.

---

### AUDIT-032: `step_order.json` lacks a JSON schema for self-validation
- **Severity**: MEDIUM
- **Category**: STRUCTURE
- **Source**: P1-E:FINDING-011
- **Location**: `tools/step_order.json` (344 lines, consumed by 5+ modules)
- **Description**: Critical configuration file with no JSON schema to validate its own structure. Typos in step IDs, missing fields, or structural errors only caught at runtime.
- **Evidence**: No schema file or registry entry exists for step_order.json.
- **Recommendation**: Create `schema/step_order.schema.json` with validation for version, policy, steps array, upstream dependencies, downstream consumers, coverage thresholds. Register in `schema_registry.json`.

---

### AUDIT-033: ALIGN-4 (additionalProperties: false) achieved but no CI regression guard
- **Severity**: MEDIUM
- **Category**: RESEARCH
- **Source**: P1-F:FINDING-001
- **Location**: All 26 schema files
- **Description**: Every `type: "object"` definition has `additionalProperties: false`. Zero violations. ALIGN-4 "ACHIEVED" claim verified. However, NO CI lint, test, or hook enforces this invariant. Future additions could regress without detection.
- **Evidence**: Recursive analysis of all 26 files: 0 violations. No test in `tests/` asserts this. No validator enforces it.
- **Recommendation**: Create CI lint (pytest parametrized test or CLI subcommand) asserting `additionalProperties: false` on every object node across all schemas.

---

### AUDIT-034: 15 of 20 step/manifest schemas exceed ALIGN-5 3-level nesting target
- **Severity**: MEDIUM
- **Category**: RESEARCH
- **Source**: P1-F:FINDING-002
- **Location**: Multiple schema files
- **Description**: Only 6 of 20 schemas meet the 3-level maximum. Step 16 reaches depth 9 (not 19 as the roadmap claims). Step 14 reaches 7. Eight schemas at depth 4 are borderline. The roadmap's claim of "19 levels" and reference to step 16 as "scaffolding" are both incorrect.
- **Evidence**: Measured depths: Step 16 = 9, Step 14 = 7, Steps 04/05/11/12 = 5, 8 schemas at 4, 6 schemas at 3 or below. Roadmap says "19 levels" for "scaffolding" -- actually 9 levels for impl_context.
- **Recommendation**: (1) Correct roadmap: "19 levels" to "9 levels", "scaffolding" to "impl_context". (2) Add nesting depth CI lint. (3) Prioritize flattening steps 16 and 14.

---

### AUDIT-035: No CI lint for schema nesting depth regression
- **Severity**: MEDIUM
- **Category**: RESEARCH
- **Source**: P1-F:FINDING-011
- **Location**: No file (missing capability)
- **Description**: No test or lint enforces maximum nesting depth. Nesting can increase without detection. Not captured in research roadmap.
- **Evidence**: No reference to nesting depth enforcement in `tests/` or `tools/specdev_tools/`.
- **Recommendation**: Add parametrized pytest test measuring depth per schema, failing if any exceeds threshold (initially 9, ratchet down over time).

---

### AUDIT-036: No CI lint for description coverage regression
- **Severity**: MEDIUM
- **Category**: RESEARCH
- **Source**: P1-F:FINDING-012
- **Location**: No file (missing capability)
- **Description**: No test enforces minimum description coverage. Current 6.1% could decrease without detection. ALIGN-6 mentions this in "next steps" but no progress.
- **Evidence**: No reference to description coverage enforcement anywhere in codebase.
- **Recommendation**: Create `schema-description-lint` with configurable threshold. Set initially at 5%, ratchet up as descriptions are added.

---

### AUDIT-037: 19 of 56 existing descriptions are identical `_migration_notes` boilerplate
- **Severity**: MEDIUM
- **Category**: DESCRIPTION
- **Source**: P1-B:FINDING-002
- **Location**: `_migration_notes` in all 19 step schemas
- **Description**: 34% of existing descriptions are the same "Optional migration notes..." text on `_migration_notes`. This inflates coverage metrics. Excluding them, effective coverage is 37/845 = 4.4%.
- **Evidence**: All 19 step schemas: `"description": "Optional migration notes added during schema version upgrades."` (Step 16 minor variant).
- **Recommendation**: These descriptions are adequate for their purpose. Focus effort on the 808 properties that matter for spec generation.

---

### AUDIT-038: canon/ schemas and seed_manifest.schema.json have zero description coverage
- **Severity**: MEDIUM
- **Category**: DESCRIPTION
- **Source**: P1-B:FINDING-005
- **Location**: `canon/kind.schema.json` (0/4), `canon/aliases.schema.json` (0/3), `schema/seed_manifest.schema.json` (0/24), `schema/core/canon.schema.json` (0/31)
- **Description**: Four files have literally zero descriptions. Canon schemas define the canonical registry structure consumed by 3+ tools. Seed manifest defines the seed registry consumed by seed-lint.
- **Evidence**: Zero descriptions in any of these files.
- **Recommendation**: Add descriptions per P1-B draft descriptions.

---

### AUDIT-039: $ref-only properties at usage sites lack descriptions
- **Severity**: MEDIUM
- **Category**: DESCRIPTION
- **Source**: P1-B:FINDING-006
- **Location**: All 19 step schemas
- **Description**: The 10 common required fields appear as pure `$ref` pointers without step-specific descriptions. `owner` in step 00 means "charter owner" vs `owner` in step 12 means "CI config owner". JSON Schema Draft 2020-12 allows `description` alongside `$ref`.
- **Evidence**: `00_charter.schema.json:12`: `"owner": {"$ref": "...#owner"}` -- no description at usage site.
- **Recommendation**: Add step-specific descriptions at `$ref` usage sites. Can be templated across schemas.

---

### AUDIT-040: ALIGN-2 -- 534 specdev.local URIs across 70+ files; migration is HIGH effort
- **Severity**: MEDIUM
- **Category**: RESEARCH
- **Source**: P1-F:FINDING-005
- **Location**: All schema files, registry, tools, prompts, spec files
- **Description**: Current URL-based scheme (`https://specdev.local/schema/...`) has 534 occurrences across 70+ files. `.local` is reserved for mDNS (RFC 6762). `https://` prefix implies non-existent endpoint. Two inconsistent suffix conventions (`.schema.json` vs `/1`).
- **Evidence**: 459 in schemas, 29 in registry, 4 in Python code, 2 in spec files, 22 in prompts, 18 in migration templates.
- **Recommendation**: L effort confirmed. Migration script feasible. URN proposal: `urn:specdev:schema:{category}:{name}:{version}`. Prerequisite: ALIGN-1 DRY fixes to reduce URI count first.

---

## LOW

### AUDIT-041: `canonicalId` pattern duplicated between core/canon and core/collections
- **Severity**: LOW
- **Category**: DRY
- **Source**: P1-A:FINDING-008
- **Location**: `schema/core/canon.schema.json` line 39, `schema/core/collections.schema.json` line 95
- **Description**: Pattern `^cn:[a-z0-9.]+:[a-z_]+:[a-z0-9-]+$` defined in canon.schema.json as `$defs.canonicalId` and inlined in collections.schema.json `canonicalRef.properties.id`.
- **Evidence**: Same pattern in two files.
- **Recommendation**: Replace inline pattern in collections with `$ref` to `canon#canonicalId`.

---

### AUDIT-042: `owner` pattern inconsistency between core/atoms and core/canon
- **Severity**: LOW
- **Category**: DRY
- **Source**: P1-A:FINDING-009
- **Location**: `schema/core/atoms.schema.json` line 38, `schema/core/canon.schema.json` line 49
- **Description**: `atoms#owner`: `^[a-z][a-z0-9_-]*$` (allows underscores AND hyphens). `canon#owner`: `^[a-z][a-z0-9-]*$` (hyphens only). Different purposes (artifact owner vs. canon registry owner) but naming collision creates confusion.
- **Evidence**: Different patterns on identically-named anchors.
- **Recommendation**: Rename `canon#owner` to `canonOwner` to avoid naming collision. Safer than unifying patterns.

---

### AUDIT-043: `fr_id` in Step 16 inlines kebabId pattern instead of using $ref
- **Severity**: LOW
- **Category**: DRY
- **Source**: P1-A:FINDING-010
- **Location**: `schema/16_impl_context.schema.json` line 1753
- **Description**: `review.semantic_review.fr_coverage[].fr_id` inlines pattern `^[a-z0-9]+(?:-[a-z0-9]+)*$` instead of `$ref` to `atoms#kebabId`.
- **Evidence**: Same pattern as `core/atoms.schema.json` line 20.
- **Recommendation**: Replace with `"$ref": "https://specdev.local/schema/core/atoms/1#kebabId"`.

---

### AUDIT-044: `docs_policy` in seed_manifest -- well-consumed but semantically misplaced
- **Severity**: LOW
- **Category**: BLOAT
- **Source**: P1-C:FINDING-C05
- **Location**: `spec/common/seed_manifest.json:58-82`
- **Description**: `docs_policy` is consumed by 2 validators (NOT dead). However, it lives in `seed_manifest.json` which is semantically about seed documents. Docs policy is about project-level documentation governance -- architecturally confusing location.
- **Evidence**: `docs_lint.py:46-52` and `step_16.py:180` consume it actively.
- **Recommendation**: Consider moving to `step_order.json` or separate `docs_config.json`. LOW priority -- current approach works.

---

### AUDIT-045: `nested_order` in seed_manifest -- consumed but currently redundant
- **Severity**: LOW
- **Category**: BLOAT
- **Source**: P1-C:FINDING-C06
- **Location**: `spec/common/seed_manifest.json:11-20`
- **Description**: Consumed by `seed_lint.py` for referential integrity checks. However, current data has only 1 layer with the same 2 seeds as `global_seed_order`. The hierarchical grouping concept is architecturally sound but adds no current value.
- **Evidence**: Single layer "foundation" with same 2 seeds as `global_seed_order`.
- **Recommendation**: Make optional (not required) in schema. Will become valuable as projects grow beyond 2 seeds.

---

### AUDIT-046: Step 12 `environment_protection` assumes GitHub Environments
- **Severity**: LOW
- **Category**: GENERICITY
- **Source**: P1-D:FINDING-008
- **Location**: `schema/12_ci_gates.schema.json`:100-114
- **Description**: `required_reviewers` and `wait_timer_minutes` map to GitHub Actions Environment Protection Rules. Concepts exist across CI systems but field names are GitHub-flavored.
- **Evidence**: `required_reviewers: integer` and `wait_timer_minutes: integer`.
- **Recommendation**: LOW priority. Fields are conceptually generic. Update descriptions to be provider-agnostic.

---

### AUDIT-047: Step 16 `drift.checks[].target` enum partially web-biased
- **Severity**: LOW
- **Category**: GENERICITY
- **Source**: P1-D:FINDING-011
- **Location**: `schema/16_impl_context.schema.json`:1055-1064
- **Description**: Target enum `["api", "schema", "nfr", "invariant", "fixture", "config"]` includes "api" which implies network API. Most values are generic.
- **Evidence**: Enum mostly generic; only `"api"` is mildly web-biased.
- **Recommendation**: Consider adding `"interface"` as alias or renaming `"api"` to `"interface"`.

---

### AUDIT-048: Step 10 `evidence_source_by_phase` hardcodes deployment phases
- **Severity**: LOW
- **Category**: GENERICITY
- **Source**: P1-D:FINDING-013
- **Location**: `schema/10_governance.schema.json`:88-107
- **Description**: Required properties `["dev", "staging", "prod"]` mirror the environment bias in AUDIT-008. Libraries that are published (not deployed) have no "staging" or "prod" evidence source.
- **Evidence**: `"required": ["dev", "staging", "prod"]`.
- **Recommendation**: Make phases dynamic by referencing project environments, or use `additionalProperties: { "type": "string" }` with `minProperties: 1`. Related to AUDIT-008.

---

### AUDIT-049: Test fixture uses stale relative `$schema` path
- **Severity**: LOW
- **Category**: STRUCTURE
- **Source**: P1-E:FINDING-006
- **Location**: `tests/fixtures/step_00/00_charter.json:$schema`
- **Description**: Uses relative path `../../schema/00_charter.schema.json` instead of canonical URI. Only fixture using relative path.
- **Evidence**: Single file deviates from `specdev.local` convention.
- **Recommendation**: Update to `https://specdev.local/schema/00_charter.schema.json`.

---

### AUDIT-050: Test fixture uses GitHub raw URL instead of local URI
- **Severity**: LOW
- **Category**: STRUCTURE
- **Source**: P1-E:FINDING-007
- **Location**: `tests/fixtures/14_roadmap.json:$schema`
- **Description**: References `https://raw.githubusercontent.com/...` instead of `specdev.local` URI. Only fixture using a GitHub URL.
- **Evidence**: Single file deviates from local URI convention.
- **Recommendation**: Update to `https://specdev.local/schema/14_roadmap.schema.json`.

---

### AUDIT-051: ALIGN-10 (src/dist schema split) -- viable, Option C lowest effort
- **Severity**: LOW
- **Category**: RESEARCH
- **Source**: P1-F:FINDING-006
- **Location**: All 19 step schemas
- **Description**: Current required field saturation averages 87%. Candidate fields for src-mode optionality: `generation_quality`, `spec_refs_ingested`, `coverage_gaps`, canonical triad, `seed_refs`. Option C (CLI flag `--mode draft|final` that programmatically relaxes required arrays) is lowest effort and avoids schema duplication.
- **Evidence**: Only 2 defaults per schema. 10 common boilerplate fields account for most required entries. Step 00 has most flexibility at 67% required.
- **Recommendation**: Implement Option C after ALIGN-1 and ALIGN-3. Define `DRAFT_OPTIONAL_FIELDS` constant.

---

### AUDIT-052: Research roadmap ALIGN-5 depth claim is inaccurate
- **Severity**: LOW
- **Category**: RESEARCH
- **Source**: P1-F:FINDING-010
- **Location**: `WIP/future/research-alignment-roadmap.md`
- **Description**: Roadmap states "Step 16 (scaffolding) has 19 levels of nesting." Actual maximum is 9 levels. "Scaffolding" is wrong -- step 16 is `impl_context` (step 15 is `scaffold`). The "19" may derive from counting JSON indentation levels.
- **Evidence**: Automated measurement: max depth = 9 at `plan.spec_alignment.checklist[].implementation.actions[].allOf[0].then.target`.
- **Recommendation**: Correct roadmap. Reassess ALIGN-5 effort from XL to L.

---

## INFO

### AUDIT-053: `seed_refs` actively consumed -- confirmed NOT dead schema
- **Severity**: INFO
- **Category**: DRY
- **Source**: P1-A:FINDING-013
- **Location**: `tools/specdev_tools/validation/seed_lint.py`, `tools/specdev_tools/validation/spec_quality_lint.py`
- **Description**: Unlike `spec_refs_ingested` (AUDIT-002), `seed_refs` IS actively consumed by multiple modules. `seed_lint.py` validates hash integrity, required seeds, unknown seeds. Must remain required.
- **Evidence**: `seed_lint.py` line 149: `seed_refs = instance.get("seed_refs", [])`.
- **Recommendation**: No change. Include in base schema (AUDIT-004).

---

### AUDIT-054: Canonical triad architecture is sound
- **Severity**: INFO
- **Category**: DRY
- **Source**: P1-A:FINDING-012, P1-C:FINDING-C10 (consumer evidence)
- **Location**: All 19 step schemas + `schema/core/collections.schema.json`
- **Description**: The 3 required fields (`canonical_refs_used`, `canonical_proposals`, `canonical_conflicts`) represent distinct workflow phases (consumption, creation, resolution). All three are `DRIFT_SENSITIVE_FIELDS`. Actively consumed by 5 tool modules. Architecture should NOT be simplified. Per-schema duplication addressed by base schema (AUDIT-004). The 3 "Array" wrapper definitions in collections could be inlined (~18 LOC savings).
- **Evidence**: Consumers: `canonical/integrity.py`, `canonical/autofix.py`, `prompt_schema_sync.py`, `spec_quality_lint.py`, `step_13.py`.
- **Recommendation**: No simplification. Duplication addressed by AUDIT-004 base schema.

---

### AUDIT-055: Step 16 has 240 properties -- 228 without descriptions (28.2% of total gap)
- **Severity**: INFO
- **Category**: DESCRIPTION
- **Source**: P1-B:FINDING-007
- **Location**: `schema/16_impl_context.schema.json`
- **Description**: Largest schema (1,868 LOC, 31.1% of total). 240 properties, 12 with descriptions (5.0%). This single file accounts for 228 of 808 missing descriptions (28.2%).
- **Evidence**: P1-B provides complete draft descriptions for all 228 properties.
- **Recommendation**: Treat as dedicated batch in fix plan due to size.

---

### AUDIT-056: Schemas already generic enough for most project types
- **Severity**: INFO
- **Category**: GENERICITY
- **Source**: P1-D:FINDING-014
- **Location**: Steps 00, 01, 03, 04, 06, 07, 08, 09, 13, 13a, 14
- **Description**: These schemas are domain-neutral and work for any project type: charter (problem/metrics/stakeholders), capabilities (scope enum), glossary (terms/definitions), FRs (acceptance criteria), invariants (jsonlogic/cel/text), NFRs (quality attributes), fixtures (test modes), impl_plan (tech stack/milestones), extension_generator, completeness_assessment, roadmap. Steps 02 and 11 are mostly generic with minor enum gaps.
- **Evidence**: See P1-D cross-project compatibility matrix.
- **Recommendation**: No changes needed for these schemas.

---

### AUDIT-057: Flat schema directory structure adequate for current size
- **Severity**: INFO
- **Category**: STRUCTURE
- **Source**: P1-E:FINDING-012
- **Location**: `schema/` directory
- **Description**: With 20 step/manifest schemas, the flat layout with numeric prefixes provides sufficient organization. Restructuring into subfolders would require updating `$id` URIs, `$ref` references, registry entries, data files, and 68+ fixtures. Cost exceeds benefit at current scale.
- **Evidence**: 20 files with numeric prefixes + `core/` subdirectory.
- **Recommendation**: Do not restructure. Revisit if schema count exceeds ~40.

---

### AUDIT-058: `allowed_upstream_dependencies` and `downstream_consumers` -- well-consumed, complementary, not redundant
- **Severity**: INFO
- **Category**: BLOAT
- **Source**: P1-C:FINDING-C07
- **Location**: `tools/step_order.json`
- **Description**: `allowed_upstream_dependencies` consumed by 5 modules. Serves distinct purpose from `downstream_consumers`: permissions vs. actual usage. Cross-validated by `dag_lint.py`.
- **Evidence**: 5 consumers: `dag_lint.py`, `dependency_order_lint.py`, `extraction_intent_check.py`, `hallucination_lint.py`, `cli.py`.
- **Recommendation**: No changes needed.

---

### AUDIT-059: `coverage_thresholds` in step_order.json -- well-consumed, correct location
- **Severity**: INFO
- **Category**: BLOAT
- **Source**: P1-C:FINDING-C08
- **Location**: `tools/step_order.json:coverage_thresholds`
- **Description**: Consumed by 2 modules (`matrix.py`, `cli.py`). Enforces FR coverage thresholds. Location in step_order.json is appropriate.
- **Evidence**: `matrix.py:308-340` checks thresholds; graceful degradation implemented.
- **Recommendation**: No changes needed.

---

### AUDIT-060: `status_write_exemptions` -- consumed, critical cycle-prevention role
- **Severity**: INFO
- **Category**: BLOAT
- **Source**: P1-C:FINDING-C09
- **Location**: `tools/step_order.json:policy.status_write_exemptions`
- **Description**: Single consumer (`forward_replay_check.py`) justified by critical cycle-prevention purpose. Prevents infinite replay when step 16c writes milestone status back to steps 09/14.
- **Evidence**: `forward_replay_check.py:139-143`. Inline `_notes` documents rationale.
- **Recommendation**: No changes needed.

---

### AUDIT-061: seed_manifest.json merge into step_order.json -- NOT recommended
- **Severity**: INFO
- **Category**: BLOAT
- **Source**: P1-C:FINDING-C11
- **Location**: `spec/common/seed_manifest.json` vs `tools/step_order.json`
- **Description**: Two files serve distinct domains: seed_manifest is project-level data (varies per host repo) vs. step_order is toolkit-level config (constant across repos). Different lifecycles, different directories, different consumers. Merging would violate separation of project data from toolkit config.
- **Evidence**: Different load paths, different lifecycles. Submodule deployments keep them in different repos.
- **Recommendation**: Keep separate. `docs_policy` migration (AUDIT-044) is a separate concern.

---

### AUDIT-062: Registry is complete -- all schema files registered, no orphan entries
- **Severity**: INFO
- **Category**: STRUCTURE
- **Source**: P1-E:FINDING-013
- **Location**: `tools/schema_registry.json` (29 entries, 26 unique files)
- **Description**: All 26 schema files registered. No orphan entries. 3 alias entries (16a/16b/16c) map to same file. No unregistered schemas.
- **Evidence**: Automated check of all 29 entries: OK.
- **Recommendation**: No action needed.

---

### AUDIT-063: URI change impact -- 93+ files would need updating
- **Severity**: INFO
- **Category**: STRUCTURE
- **Source**: P1-E:FINDING-014
- **Location**: All files with `$schema` or `$ref` URIs
- **Description**: Any URI scheme change affects: 26 schema files, registry (29 entries), 2 spec data files, 4 canon data files, 60+ test fixtures, 6+ tool source files. Total: 93+ files.
- **Evidence**: 23 unique `$schema` values, 448 `$ref` URIs, 68+ fixtures with `$schema`.
- **Recommendation**: URI changes MUST be done as single atomic batch with migration script. Do NOT attempt manual changes across 93+ files.

---

### AUDIT-064: ALIGN-3, ALIGN-7, ALIGN-8, ALIGN-9 -- out of scope for schema audit
- **Severity**: INFO
- **Category**: RESEARCH
- **Source**: P1-F:FINDING-007, P1-F:FINDING-008, P1-F:FINDING-009
- **Location**: N/A
- **Description**: ALIGN-3 (structured errors), ALIGN-7 (--json output), ALIGN-8 (MCP tool), ALIGN-9 (pre-commit hooks) are tool/CLI-focused gaps with no direct schema impact. ALIGN-3 has partial P5 progress. ALIGN-7 at 7/25 commands.
- **Evidence**: P5 tools/tests audit has made progress on ALIGN-3 and ALIGN-7.
- **Recommendation**: No schema changes needed. Remain on research roadmap.

---

### AUDIT-065: `schema_registry.json` location in `tools/` is non-obvious but acceptable
- **Severity**: INFO
- **Category**: STRUCTURE
- **Source**: P1-E:FINDING-010
- **Location**: `tools/schema_registry.json`
- **Description**: Registry lives in `tools/` rather than `schema/`. `SchemaRegistry` class has fallback to `schema_registry.json` at repo root. Moving would require updating 6+ source files.
- **Evidence**: Primary lookup at `tools/schema_registry.json` with fallback.
- **Recommendation**: Keep in `tools/`. Include in any future config restructuring batch.

---

## Findings by Target File

| File | AUDIT IDs |
|---|---|
| `schema/core/collections.schema.json` | 002, 004, 008, 014, 017, 020, 041, 054 |
| `schema/core/atoms.schema.json` | 004, 014, 042 |
| `schema/core/canon.schema.json` | 014, 038, 041, 042 |
| `schema/core/errors.schema.json` | 014, 038 |
| `schema/16_impl_context.schema.json` | 004, 005, 006, 011, 016, 024, 025, 027, 043, 047, 055 |
| `schema/15_scaffold.schema.json` | 004, 012, 018, 023, 027 |
| `schema/05_interface_contracts.schema.json` | 004, 009, 010, 018, 019, 021, 022, 027 |
| `schema/02a_delivery_baseline.schema.json` | 004, 008, 027 |
| `schema/02_system_sketch.schema.json` | 004, 019, 027 |
| `schema/12_ci_gates.schema.json` | 004, 013, 027, 046 |
| `schema/11_redteam.schema.json` | 004, 006, 011, 027 |
| `schema/14_roadmap.schema.json` | 004, 006, 007, 027, 056 |
| `schema/09_impl_plan.schema.json` | 004, 007, 027, 056 |
| `schema/10_governance.schema.json` | 004, 027, 048 |
| `schema/00_charter.schema.json` | 004, 027, 056 |
| `schema/01_capabilities.schema.json` | 004, 027, 056 |
| `schema/03_glossary.schema.json` | 004, 027, 056 |
| `schema/04_fr_list.schema.json` | 004, 027, 056 |
| `schema/06_invariants.schema.json` | 004, 027, 056 |
| `schema/07_nfrs.schema.json` | 004, 017, 027, 056 |
| `schema/08_fixtures.schema.json` | 004, 027, 056 |
| `schema/13_extension_generator.schema.json` | 004, 027, 056 |
| `schema/13a_completeness_assessment.schema.json` | 004, 027, 056 |
| `schema/seed_manifest.schema.json` | 026, 038, 044, 045 |
| `canon/kind.schema.json` | 031, 038 |
| `canon/aliases.schema.json` | 031, 038 |
| `canon/kinds/*.json` (22 files) | 030 |
| `tools/schema_registry.json` | 016, 028, 062, 065 |
| `tools/step_order.json` | 032, 058, 059, 060, 061 |
| `tests/fixtures/step_13/valid_extension.json` | 029 |
| `tests/fixtures/step_00/00_charter.json` | 049 |
| `tests/fixtures/14_roadmap.json` | 050 |
| All 26 schema files | 001, 033, 034 |
| All 19 step schemas | 002, 003, 004, 020, 027, 037, 039, 051 |
| N/A (missing capabilities / out of scope) | 035, 036, 064 |
| `WIP/future/research-alignment-roadmap.md` | 052 |
| Multiple schemas (ambiguous names) | 015 |
| Multiple (URI migration) | 040, 063 |
