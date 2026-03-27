# P0 Schema Audit Baseline Report

**Date**: 2026-03-19
**Scope**: `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/schema/`
**Branch**: `codex/canonical-drift-review-plan`

---

## 1. Full Recursive Tree of schema/

```
schema/
  00_charter.schema.json                          5,271 bytes    202 LOC
  01_capabilities.schema.json                     4,068 bytes    138 LOC
  02_system_sketch.schema.json                    8,262 bytes    331 LOC
  02a_delivery_baseline.schema.json               3,107 bytes    110 LOC
  03_glossary.schema.json                         3,175 bytes    114 LOC
  04_fr_list.schema.json                          4,140 bytes    139 LOC
  05_interface_contracts.schema.json              6,190 bytes    220 LOC
  06_invariants.schema.json                       3,738 bytes    134 LOC
  07_nfrs.schema.json                             4,159 bytes    152 LOC
  08_fixtures.schema.json                         3,282 bytes    119 LOC
  09_impl_plan.schema.json                        4,159 bytes    152 LOC
  10_governance.schema.json                       4,648 bytes    178 LOC
  11_redteam.schema.json                          4,793 bytes    181 LOC
  12_ci_gates.schema.json                         5,435 bytes    184 LOC
  13_extension_generator.schema.json              3,644 bytes    122 LOC
  13a_completeness_assessment.schema.json         4,144 bytes    152 LOC
  14_roadmap.schema.json                          8,393 bytes    271 LOC
  15_scaffold.schema.json                         4,279 bytes    169 LOC
  16_impl_context.schema.json                    54,950 bytes  1,868 LOC
  seed_manifest.schema.json                       3,855 bytes    154 LOC
  core/
    atoms.schema.json                             1,404 bytes     56 LOC
    canon.schema.json                             6,764 bytes    316 LOC
    collections.schema.json                      12,030 bytes    521 LOC
    errors.schema.json                              705 bytes     32 LOC
```

**Summary**:
- **24 schema files** total (20 step/manifest schemas + 4 core schemas)
- **1 subdirectory**: `core/` (4 files)
- **Total file size**: 160,595 bytes
- **Total LOC**: 6,015

---

## 2. Total LOC Across All Schema Files

| Category | Files | LOC |
|---|---|---|
| Step schemas (00-16) | 19 | 4,936 |
| seed_manifest.schema.json | 1 | 154 |
| core/ schemas | 4 | 925 |
| **TOTAL** | **24** | **6,015** |

**Note**: 16_impl_context.schema.json alone accounts for 1,868 LOC (31.1% of all schema LOC).

---

## 3. schema/core/ Files -- Reusable Definitions

### core/atoms.schema.json (56 LOC, 6 definitions)

| Definition | $anchor | Type | Pattern/Format | Description |
|---|---|---|---|---|
| `metadata` | metadata | object | patternProperties: `^[a-zA-Z0-9_]+$` -> string | Generic key-value store for extra context |
| `kebabId` | kebabId | string | `^[a-z0-9]+(?:-[a-z0-9]+)*$` | Kebab-case identifier |
| `timestamp` | timestamp | string | format: date-time | ISO 8601 timestamp |
| `owner` | owner | string | `^[a-z][a-z0-9_-]*$` | Artifact owner, validated against canon |
| `tag` | tag | string | `^[A-Za-z0-9_.:-]{1,64}$` | Short tag |
| `screamingSnakeId` | screamingSnakeId | string | `^[A-Z0-9_]+$` | SCREAMING_SNAKE identifier |

### core/collections.schema.json (521 LOC, 28 definitions)

| Definition | $anchor | Type | Notes |
|---|---|---|---|
| `kebabIdArray` | kebabIdArray | array of kebabId | minItems: 1, uniqueItems: true |
| `stringArray` | stringArray | array of string | No constraints |
| `link` | link | object | properties: rel, href, spec_ref; required: rel, href |
| `traceId` | traceId | $ref kebabId | Simple alias |
| `traceRef` | traceRef | object | properties: type, id, note; required: type, id; conditional: external requires owner+note |
| `canonicalRef` | canonicalRef | object | properties: id, kind, version, label, alias_used, note; required: id, kind |
| `canonicalRefArray` | canonicalRefArray | array of canonicalRef | |
| `canonicalProposal` | canonicalProposal | object | properties: temp_id, kind, proposed_label, definition, source_field, suggested_namespace; required: 5 fields |
| `canonicalProposalArray` | canonicalProposalArray | array of canonicalProposal | |
| `canonicalConflict` | canonicalConflict | object | properties: field_path, input_value, candidate_ids, reason; required: all 4 |
| `canonicalConflictArray` | canonicalConflictArray | array of canonicalConflict | |
| `environmentName` | environmentName | string enum | ["dev", "ci", "staging", "prod"] |
| `stageName` | stageName | string enum | ["dev", "ci", "staging", "prod"] |
| `environmentConfig` | environmentConfig | object | Dynamic keys, values can be string/number/boolean/array/object |
| `techStackItem` | techStackItem | object | properties: name, version, notes, rationale, tech_stack_ref; required: name, version |
| `techStackList` | techStackList | array of techStackItem | |
| `techStack` | techStack | object | properties: languages, frameworks, infrastructure, tools; required: languages, frameworks |
| `dependencyItem` | dependencyItem | object | properties: type (milestone/external), id, owner, note, dependency_ref; conditional: external requires owner+note |
| `dependencyList` | dependencyList | array of string or dependencyItem | Mixed types allowed |
| `dependencyObjectList` | dependencyObjectList | array of dependencyItem | Strict object-only variant |
| `generationQuality` | generationQuality | object | required: assumptions (stringArray) |
| `seedRef` | seedRef | object | properties: seed_id, path, section, note, hash (SHA-256), version; required: seed_id |
| `seedRefArray` | seedRefArray | array of seedRef | minItems: 0 |
| `specRefIngested` | specRefIngested | object | properties: step_id (pattern `^\d{2}[a-z]?$`), artifact_id, hash; required: step_id, artifact_id |
| `specRefsIngestedArray` | specRefsIngestedArray | array of specRefIngested | |
| `coverageGap` | coverageGap | object | properties: upstream_item_id, source_step, reason (minLength: 10); required: all 3 |
| `coverageGapsArray` | coverageGapsArray | array of coverageGap | minItems: 0 |
| `anyJson` | anyJson | oneOf | object, array, string, number, integer, boolean, null |

### core/errors.schema.json (32 LOC, 1 definition)

| Definition | $anchor | Type | Notes |
|---|---|---|---|
| `errorState` | errorState | object | properties: code (kebabId), message (string), severity (enum: info/warn/error/fatal); required: code, message |

### core/canon.schema.json (316 LOC, 9 definitions)

| Definition | $anchor | Type | Notes |
|---|---|---|---|
| `canonicalId` | canonicalId | string | Pattern: `^cn:[a-z0-9.]+:[a-z_]+:[a-z0-9-]+$` |
| `semver` | semver | string | Pattern: `^\d+\.\d+\.\d+$` |
| `owner` | owner | string | Pattern: `^[a-z][a-z0-9-]*$` |
| `entryStatus` | entryStatus | string enum | ["active", "deprecated", "sunset", "retired"] |
| `lifecycle` | lifecycle | object | introduced_at (required), deprecated_since, sunset_after, retired_at, replaced_by, deprecation_note |
| `aliasLifecycle` | aliasLifecycle | object | deprecated_since (required), sunset_date, replaced_by |
| `entry` | entry | object | id, kind, preferred_label, definition, version, status, owners, constraints, examples, tags, aliases, source_refs, lifecycle; required: 8 fields; conditional validation by status |
| `aliasStatus` | aliasStatus | string enum | ["active", "deprecated"] |
| `alias` | alias | object | kind, normalized, target_id, status, lifecycle; required: 4 fields; deprecated requires lifecycle |

**Total core definitions**: 44 (6 atoms + 28 collections + 1 error + 9 canon)

---

## 4. $ref Usage Audit

| Schema File | Total $ref | core/ refs | Local (#) refs | Other refs | References core/? |
|---|---|---|---|---|---|
| 00_charter.schema.json | 23 | 23 | 0 | 0 | YES |
| 01_capabilities.schema.json | 22 | 22 | 0 | 0 | YES |
| 02_system_sketch.schema.json | 20 | 20 | 0 | 0 | YES |
| 02a_delivery_baseline.schema.json | 18 | 18 | 0 | 0 | YES |
| 03_glossary.schema.json | 14 | 14 | 0 | 0 | YES |
| 04_fr_list.schema.json | 20 | 20 | 0 | 0 | YES |
| 05_interface_contracts.schema.json | 21 | 21 | 0 | 0 | YES |
| 06_invariants.schema.json | 17 | 17 | 0 | 0 | YES |
| 07_nfrs.schema.json | 17 | 17 | 0 | 0 | YES |
| 08_fixtures.schema.json | 16 | 16 | 0 | 0 | YES |
| 09_impl_plan.schema.json | 21 | 21 | 0 | 0 | YES |
| 10_governance.schema.json | 17 | 17 | 0 | 0 | YES |
| 11_redteam.schema.json | 17 | 17 | 0 | 0 | YES |
| 12_ci_gates.schema.json | 17 | 17 | 0 | 0 | YES |
| 13_extension_generator.schema.json | 14 | 14 | 0 | 0 | YES |
| 13a_completeness_assessment.schema.json | 14 | 14 | 0 | 0 | YES |
| 14_roadmap.schema.json | 27 | 27 | 0 | 0 | YES |
| 15_scaffold.schema.json | 17 | 17 | 0 | 0 | YES |
| 16_impl_context.schema.json | 65 | 58 | 7 | 0 | YES |
| seed_manifest.schema.json | 11 | 11 | 0 | 0 | YES |
| core/atoms.schema.json | 0 | 0 | 0 | 0 | NO (is core) |
| core/canon.schema.json | 14 | 2 | 12 | 0 | YES (partial) |
| core/collections.schema.json | 25 | 25 | 0 | 0 | YES (self + atoms) |
| core/errors.schema.json | 1 | 1 | 0 | 0 | YES |
| **TOTAL** | **448** | **429** | **19** | **0** | |

**Key findings**:
- All 20 step/manifest schemas reference core/ -- 100% adoption (but step 16 has 7 local `$defs` that are candidates for core/ extraction: specRef, evidenceObject, executionStatus, severityLevel)
- Only `16_impl_context.schema.json` uses local `#/$defs/` references (7 total: specRef, evidenceObject, executionStatus, severityLevel)
- `core/atoms.schema.json` is the only file with zero $ref references (leaf node)
- No schemas reference files outside the `specdev.local` URI scheme
- **Total $ref count**: 448 (429 core/ + 19 local #)

### Most-referenced core definitions (across step schemas):

| Core Definition | Usage Count |
|---|---|
| `atoms/1#kebabId` | 60+ |
| `collections/1#canonicalRef` | 50+ |
| `collections/1#canonicalRefArray` | 20 |
| `collections/1#generationQuality` | 20 |
| `collections/1#seedRefArray` | 20 |
| `collections/1#specRefsIngestedArray` | 20 |
| `collections/1#coverageGapsArray` | 20 |
| `collections/1#canonicalConflict` | 20 |
| `collections/1#canonicalProposal` | 20 |
| `atoms/1#owner` | 23 |
| `atoms/1#timestamp` | 20 |
| `collections/1#stringArray` | 29 |
| `collections/1#traceRef` | 14 |

---

## 5. Description Coverage

| Schema File | Properties WITH description | Properties WITHOUT description | Coverage % |
|---|---|---|---|
| 00_charter.schema.json | 1 | 35 | 2.8% |
| 01_capabilities.schema.json | 1 | 26 | 3.7% |
| 02_system_sketch.schema.json | 1 | 40 | 2.4% |
| 02a_delivery_baseline.schema.json | 1 | 18 | 5.3% |
| 03_glossary.schema.json | 1 | 20 | 4.8% |
| 04_fr_list.schema.json | 1 | 25 | 3.8% |
| 05_interface_contracts.schema.json | 3 | 37 | 7.5% |
| 06_invariants.schema.json | 1 | 23 | 4.2% |
| 07_nfrs.schema.json | 1 | 24 | 4.0% |
| 08_fixtures.schema.json | 1 | 19 | 5.0% |
| 09_impl_plan.schema.json | 1 | 26 | 3.7% |
| 10_governance.schema.json | 2 | 29 | 6.5% |
| 11_redteam.schema.json | 1 | 28 | 3.4% |
| 12_ci_gates.schema.json | 6 | 26 | 18.8% |
| 13_extension_generator.schema.json | 4 | 19 | 17.4% |
| 13a_completeness_assessment.schema.json | 1 | 24 | 4.0% |
| 14_roadmap.schema.json | 9 | 36 | 20.0% |
| 15_scaffold.schema.json | 3 | 24 | 11.1% |
| 16_impl_context.schema.json | 12 | 273 | 4.2% |
| seed_manifest.schema.json | 0 | 24 | 0.0% |
| core/atoms.schema.json | 0 | 0 | N/A |
| core/canon.schema.json | 0 | 38 | 0.0% |
| core/collections.schema.json | 5 | 46 | 9.8% |
| core/errors.schema.json | 0 | 3 | 0.0% |
| **TOTAL** | **56** | **863** | **6.1%** |

**Critical finding**: Only 56 of 919 total properties have descriptions. Coverage is 6.1%. Most schemas have exactly 1 property with a description (the `metadata` or `owner` inherited from core). The seed_manifest, core/canon, and core/errors schemas have 0% description coverage.

**Caveat**: These counts are approximate. The counting methodology (recursion strategy for `allOf`/`oneOf`/`if` branches, `patternProperties`, `$defs`) was not documented for P0. P1-B should perform its own definitive count using the methodology specified in the plan.

---

## 6. generation_quality

**Structure** (defined in `core/collections.schema.json#generationQuality`):
```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["assumptions"],
  "properties": {
    "assumptions": { "$ref": "...#stringArray" }
  }
}
```

**Present in 19 step schemas**: ALL step schemas (00 through 16) include `generation_quality` as a required top-level property via `$ref` to `collections/1#generationQuality`.

| Schema | Required? |
|---|---|
| 00_charter | YES |
| 01_capabilities | YES |
| 02_system_sketch | YES |
| 02a_delivery_baseline | YES |
| 03_glossary | YES |
| 04_fr_list | YES |
| 05_interface_contracts | YES |
| 06_invariants | YES |
| 07_nfrs | YES |
| 08_fixtures | YES |
| 09_impl_plan | YES |
| 10_governance | YES |
| 11_redteam | YES |
| 12_ci_gates | YES |
| 13_extension_generator | YES |
| 13a_completeness_assessment | YES |
| 14_roadmap | YES |
| 15_scaffold | YES |
| 16_impl_context | YES |

**Not in**: seed_manifest.schema.json, core/ schemas.

All 19 step schemas use identical `$ref` to `collections/1#generationQuality`. No schema overrides or extends the definition.

---

## 7. seed_refs and spec_refs_ingested

### seed_refs

**Structure** (defined in `core/collections.schema.json#seedRefArray`):
- Array of `seedRef` objects
- Each `seedRef` has: `seed_id` (required, kebabId), `path`, `section`, `note`, `hash` (SHA-256, pattern `^[0-9a-f]{64}$`), `version`
- `minItems: 0`

**Present in**: ALL 19 step schemas (00 through 16, including 02a and 13a). All are required.

### spec_refs_ingested

**Structure** (defined in `core/collections.schema.json#specRefsIngestedArray`):
- Array of `specRefIngested` objects
- Each `specRefIngested` has: `step_id` (required, pattern `^\d{2}[a-z]?$`), `artifact_id` (required, kebabId), `hash` (SHA-256)

**Present in**: ALL 19 step schemas (00 through 16, including 02a and 13a). All are required.

Both properties are always declared identically via `$ref` and always listed in the `required` array.

---

## 8. Canonical/Canon References in Schemas

Every step schema (19 files, 00 through 16 including 02a and 13a) includes these 3 canonical properties as required top-level fields:

| Property | $ref Target | Default |
|---|---|---|
| `canonical_refs_used` | `collections/1#canonicalRefArray` | none |
| `canonical_proposals` | inline array of `collections/1#canonicalProposal` | `[]` |
| `canonical_conflicts` | inline array of `collections/1#canonicalConflict` | `[]` |

**Additional canonical $ref usage in step schemas**:
- Many schemas have `_ref` suffix properties pointing to `canonicalRef` (e.g., `capability_ref`, `interface_ref`, `policy_ref`, `unit_ref`, `metric_ref`, `environment_ref`, `tag_ref`, `term_ref`, `risk_category_ref`, `governance_label_ref`, `tech_stack_ref`, `dependency_ref`)
- `16_impl_context.schema.json` has the most `canonicalRef` references: 28 occurrences

**Canon schema files** (in `schema/core/canon.schema.json`):
- Defines the canonical registry structure: entry, alias, lifecycle, status enums
- Referenced by `canon/kind.schema.json` and `canon/aliases.schema.json` (outside `schema/`)

---

## 9. Web-Service-Specific Terminology

Occurrences across all files in `schema/`:

| Term | Count | Files |
|---|---|---|
| `endpoint` | 2 | 16_impl_context (implemented_endpoints) |
| `route` | 3 | 15_scaffold (route_map) |
| `HTTP` | 0 | -- |
| `REST` | 0 | -- |
| `api_ref` | 2 | 15_scaffold |
| `method` | 10 | 05_interface_contracts, 15_scaffold, 16_impl_context |
| `url` | 5 | 05_interface_contracts (enum_provenance.source_url) |
| `path` | 14 | Multiple (generic path, 15_scaffold route path) |
| `request` | 1 | 05_interface_contracts |
| `response` | 1 | 05_interface_contracts |
| `header` | 1 | 05_interface_contracts (parameter "in" enum) |
| `status_code` | 0 | -- |
| `payload` | 0 | -- |
| **TOTAL** | **39** | |

**Schemas with web-service terminology** (non-trivially):
- `05_interface_contracts.schema.json` -- primary: method enum (GET/POST/PUT/PATCH/DELETE), protocol, parameters, security, request/response schemas
- `15_scaffold.schema.json` -- route_map with api_ref, path, method (GET/POST/PUT/DELETE/PATCH/OPTIONS/HEAD)
- `16_impl_context.schema.json` -- implemented_endpoints, drift check targets/methods
- `02_system_sketch.schema.json` -- protocol enum includes "http"

---

## 10. tools/schema_registry.json

**29 entries** mapping URI to file path:

| URI | File Path |
|---|---|
| `https://specdev.local/schema/core/atoms/1` | schema/core/atoms.schema.json |
| `https://specdev.local/schema/core/canon/1` | schema/core/canon.schema.json |
| `https://specdev.local/schema/canon/aliases/1` | canon/aliases.schema.json |
| `https://specdev.local/schema/canon/kind/1` | canon/kind.schema.json |
| `https://specdev.local/schema/core/collections/1` | schema/core/collections.schema.json |
| `https://specdev.local/schema/core/errors/1` | schema/core/errors.schema.json |
| `https://specdev.local/schema/00_charter.schema.json` | schema/00_charter.schema.json |
| `https://specdev.local/schema/01_capabilities.schema.json` | schema/01_capabilities.schema.json |
| `https://specdev.local/schema/02_system_sketch.schema.json` | schema/02_system_sketch.schema.json |
| `https://specdev.local/schema/03_glossary.schema.json` | schema/03_glossary.schema.json |
| `https://specdev.local/schema/04_fr_list.schema.json` | schema/04_fr_list.schema.json |
| `https://specdev.local/schema/05_interface_contracts.schema.json` | schema/05_interface_contracts.schema.json |
| `https://specdev.local/schema/06_invariants.schema.json` | schema/06_invariants.schema.json |
| `https://specdev.local/schema/07_nfrs.schema.json` | schema/07_nfrs.schema.json |
| `https://specdev.local/schema/08_fixtures.schema.json` | schema/08_fixtures.schema.json |
| `https://specdev.local/schema/09_impl_plan.schema.json` | schema/09_impl_plan.schema.json |
| `https://specdev.local/schema/10_governance.schema.json` | schema/10_governance.schema.json |
| `https://specdev.local/schema/11_redteam.schema.json` | schema/11_redteam.schema.json |
| `https://specdev.local/schema/12_ci_gates.schema.json` | schema/12_ci_gates.schema.json |
| `https://specdev.local/schema/13_extension_generator.schema.json` | schema/13_extension_generator.schema.json |
| `https://specdev.local/schema/13a_completeness_assessment.schema.json` | schema/13a_completeness_assessment.schema.json |
| `https://specdev.local/schema/14_roadmap.schema.json` | schema/14_roadmap.schema.json |
| `https://specdev.local/schema/15_scaffold.schema.json` | schema/15_scaffold.schema.json |
| `https://specdev.local/schema/16_impl_context.schema.json` | schema/16_impl_context.schema.json |
| `https://specdev.local/schema/16a_impl_context.schema.json` | schema/16_impl_context.schema.json |
| `https://specdev.local/schema/16b_impl_context.schema.json` | schema/16_impl_context.schema.json |
| `https://specdev.local/schema/16c_impl_context.schema.json` | schema/16_impl_context.schema.json |
| `https://specdev.local/schema/02a_delivery_baseline.schema.json` | schema/02a_delivery_baseline.schema.json |
| `https://specdev.local/schema/seed_manifest.schema.json` | schema/seed_manifest.schema.json |

**Key observations**:
- Steps 16a, 16b, 16c all map to the SAME file: `schema/16_impl_context.schema.json`
- 2 entries point to files OUTSIDE `schema/`: `canon/aliases.schema.json` and `canon/kind.schema.json`
- No entry for `02a` URI exists separately from `02a_delivery_baseline`

---

## 11. tools/seed_manifest.json

**File does not exist at `tools/seed_manifest.json`**.

The actual seed manifest is at: `spec/common/seed_manifest.json`

The schema for it is: `schema/seed_manifest.schema.json`

---

## 12. tools/step_order.json

**Full contents documented**:

- **version**: "1.0.0"
- **policy**:
  - mode: `strict_waterfall`
  - allow_self_dependency: false
  - allow_forward_dependency: false
  - require_full_forward_replay_on_change: true
  - status_write_exemptions: Steps 09 and 14 for `milestones[].status`

- **steps** (22 total): 00, 01, 02, 02a, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 13a, 14, 15, 16, 16a, 16b, 16c

- **allowed_upstream_dependencies**: Strict cumulative waterfall. Each step can depend on all prior steps.

- **downstream_consumers**: Maps each step to the steps that actively consume its output. Examples:
  - Step 04 (FRs) has the most consumers: 13 steps (05, 06, 07, 08, 09, 11, 13, 13a, 14, 15, 16, 16a, 16c)
  - Step 08 (Fixtures) feeds 9 steps
  - Step 16c has 0 downstream consumers (terminal)

- **coverage_thresholds**: fr_coverage: 80, mode: "warn"

---

## 13. research-alignment-roadmap.md

**Found at**: `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/WIP/future/research-alignment-roadmap.md`

This file exists in the WIP/future/ directory and is referenced in 4 WIP/tool_audit files:
- `WIP/tool_audit/P5-EXECUTION-STATE.md`
- `WIP/tool_audit/p5-batch6-report.md`
- `WIP/tool_audit/p4-out-fix-plan.md`
- `WIP/tool_audit/p4-review-D1.md`

---

## 14. All Enum Definitions

### In core/ schemas

| File | Property Path | Values |
|---|---|---|
| core/collections | environmentName | ["dev", "ci", "staging", "prod"] |
| core/collections | stageName | ["dev", "ci", "staging", "prod"] |
| core/collections | dependencyItem.type | ["milestone", "external"] |
| core/errors | errorState.severity | ["info", "warn", "error", "fatal"] |
| core/canon | entryStatus | ["active", "deprecated", "sunset", "retired"] |
| core/canon | aliasStatus | ["active", "deprecated"] |

### In step schemas

| File | Property Path | Values |
|---|---|---|
| 01_capabilities | capabilities[].scope | ["in", "out", "future"] |
| 02_system_sketch | components[].type | ["service", "db", "queue", "cache", "job", "ui", "lib", "external"] |
| 02_system_sketch | components[].tags[] | ["critical-path", "supporting", "external-dependency", "shared-platform", "stateful", "stateless", "realtime", "batch", "latency-sensitive", "throughput-sensitive", "pii", "phi", "pci", "confidential", "public-data", "multi-tenant", "single-tenant", "experimental", "legacy", "deprecated"] |
| 02_system_sketch | connections[].protocol | ["http", "grpc", "event", "rpc", "db", "file"] |
| 02_system_sketch | connections[].trust_boundary | ["internal", "partner", "public"] |
| 02_system_sketch | connections[].auth | ["none", "basic", "oauth2", "jwt", "mTLS", "key"] |
| 02_system_sketch | connections[].rate_limit.scope | ["ip", "client", "token", "global"] |
| 02_system_sketch | connections[].reliability | ["best-effort", "at-least-once", "exactly-once"] |
| 05_interface_contracts | apis[].protocol | ["http", "grpc", "ws", "mqtt"] |
| 05_interface_contracts | apis[].method | ["GET", "POST", "PUT", "PATCH", "DELETE"] |
| 05_interface_contracts | apis[].parameters[].in | ["query", "path", "header"] |
| 05_interface_contracts | apis[].security | ["none", "api-key", "oauth2", "jwt", "mTLS"] |
| 06_invariants | rules[].language | ["jsonlogic", "cel", "text"] |
| 06_invariants | rules[].severity | ["warn", "error"] |
| 07_nfrs | nfrs[].category | ["latency", "throughput", "availability", "durability", "cost", "security", "privacy", "maintainability", "usability", "portability", "energy"] |
| 08_fixtures | fixtures[].mode | ["unit", "contract", "e2e", "redteam"] |
| 09_impl_plan | milestones[].status | ["pending", "in_progress", "done", "deferred"] |
| 10_governance | pr_rules[] | ["validate", "validate-all", "matrix", "fixtures-lint", "invariants-check", "governance-check", "seed-lint", "docs-lint", "test", "build", "lint", "format", "audit", "security"] |
| 11_redteam | threats[].category | ["authn", "authz", "business_logic", "transport", "data_privacy"] |
| 11_redteam | threats[].mitigations[].type | ["fr", "api", "nfr", "inv", "fixture", "doc", "capability"] |
| 11_redteam | threats[].severity | ["low", "medium", "high", "critical"] |
| 12_ci_gates | jobs[].security.token_permissions.* | ["read", "write", "none"] |
| 13a_completeness | missing_elements[].category | ["traceability", "completeness", "quality", "ambiguity"] |
| 13a_completeness | missing_elements[].priority | ["high", "medium", "low"] |
| 14_roadmap | milestones[].status | ["pending", "in_progress", "done", "deferred"] |
| 14_roadmap | milestones[].risk_status | ["low", "medium", "high", "critical"] |
| 14_roadmap | milestones[].tasks[].status | ["pending", "in_progress", "done"] |
| 15_scaffold | route_map[].method | ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"] |
| 15_scaffold | build_status | ["pending", "green", "red"] |
| seed_manifest | seeds[].source_type | ["doc", "spec", "config", "other"] |

### In 16_impl_context.schema.json (~27 enum definitions)

| Property Path | Values |
|---|---|
| $defs.specRef.type | ["fr", "api", "nfr", "inv", "fixture", "doc", "code"] |
| $defs.severityLevel | ["low", "medium", "high", "critical"] |
| $defs.executionStatus | ["passed", "failed", "blocked", "partial"] |
| $defs.evidenceObject.type | ["log", "snippet", "screenshot", "reference"] |
| plan.status | ["active", "deferred"] |
| plan.docs_impact.status | ["required", "not_required"] |
| plan.spec_alignment.checklist[].type | ["behavior", "constraint", "validation", "metadata", "perf", "logging", "docs", "security"] |
| plan.spec_alignment.checklist[].layer | ["db", "model", "service", "api", "integration", "tests", "docs", "config", "security"] |
| plan.spec_alignment.checklist[].checklist_status | ["active", "deferred"] |
| plan.spec_alignment.checklist[].implementation.status | ["pending", "in_progress", "verified", "deferred"] |
| plan.spec_alignment.checklist[].implementation.actions[].type | ["file_create", "file_edit", "run_command", "manual_verification"] |
| plan.ambiguities[].source | ["spec", "code", "plan", "mixed", "review"] |
| plan.ambiguities[].severity | ["blocking", "non_blocking"] |
| plan.ambiguities[].status | ["resolved", "tracking", "deferred", "blocked"] |
| plan.drift.checks[].target | ["api", "schema", "nfr", "invariant", "fixture", "config"] |
| plan.drift.checks[].method | ["runtime-sample", "log-diff", "schema-diff", "trace-replay"] |
| execution.final_status.ci_status | ["green", "red"] |
| review.findings[].type | ["bug", "gap", "scope_creep", "style", "design", "tests", "docs"] |
| review.findings[].severity | ["blocking", "major", "minor", "nit"] |
| review.verdict | ["verified", "deferred", "rejected"] |
| review.fixture_status.test_results[].status | ["pass", "fail", "skip"] |
| review.fixture_status.ci_status | ["green", "red"] |
| review.security_status | ["green", "red"] |
| review.delivery_status.deployments[].env (allOf fallback) | ["dev", "staging", "prod"] |
| review.delivery_status.deployments[].status | ["pending", "success", "failed"] |

**Total unique enum definitions**: ~61 (6 core + ~30 step 00-15 + ~25 step 16). **Caveat**: This count is approximate. Step 02 and Step 16 each have 2 additional enums inside `allOf/if` conditional blocks not captured in the tables above (Step 02: `connections[].allOf[0].if.trust_boundary` and `connections[].allOf[1].if.protocol`; Step 16: `plan.spec_alignment.checklist[].implementation.actions[].allOf[0].if.type` and `review.findings[].allOf[0].if.severity`). P1-A should perform a definitive recount using recursive JSON traversal that includes conditional (`if`/`allOf`) branches.

---

## 15. All "required" Arrays

### Common required pattern (all 19 step schemas 00-16)

Every step schema has a top-level `required` array containing at minimum:
```
["id", "owner", "created_at", "seed_refs", "spec_refs_ingested", ..., "generation_quality",
 "canonical_refs_used", "canonical_proposals", "canonical_conflicts", "coverage_gaps"]
```

The 10 common required fields present in all step schemas:
1. `id`
2. `owner`
3. `created_at`
4. `seed_refs`
5. `spec_refs_ingested`
6. `generation_quality`
7. `canonical_refs_used`
8. `canonical_proposals`
9. `canonical_conflicts`
10. `coverage_gaps`

### Step-specific required fields (in addition to the 10 common)

| Step | Additional Required Fields |
|---|---|
| 00_charter | problem_statement, success_metrics, stakeholders, user_segments |
| 01_capabilities | capabilities |
| 02_system_sketch | components (connections conditional) |
| 02a_delivery_baseline | environments, ci_gates |
| 03_glossary | terms |
| 04_fr_list | functional_requirements |
| 05_interface_contracts | apis |
| 06_invariants | rules |
| 07_nfrs | nfrs |
| 08_fixtures | fixtures |
| 09_impl_plan | tech_stack, milestones, trace |
| 10_governance | spec_first_policy, commit_message_rules |
| 11_redteam | threats |
| 12_ci_gates | jobs |
| 13_extension_generator | extensions |
| 13a_completeness | missing_elements, completeness_rating |
| 14_roadmap | tech_stack, milestones |
| 15_scaffold | service_skeleton, route_map, validators, build_status (validators conditional) |
| 16_impl_context | plan |

### seed_manifest.schema.json required

```
["seed_manifest_id", "version", "created_at", "last_updated",
 "global_seed_order", "nested_order", "seeds", "step_requirements", "docs_policy"]
```

### core/ required arrays

| File | Context | Required Fields |
|---|---|---|
| core/collections | link | ["rel", "href"] |
| core/collections | traceRef | ["type", "id"] |
| core/collections | canonicalRef | ["id", "kind"] |
| core/collections | canonicalProposal | ["temp_id", "kind", "proposed_label", "definition", "source_field"] |
| core/collections | canonicalConflict | ["field_path", "input_value", "candidate_ids", "reason"] |
| core/collections | techStackItem | ["name", "version"] |
| core/collections | techStack | ["languages", "frameworks"] |
| core/collections | dependencyItem | ["type", "id"] |
| core/collections | generationQuality | ["assumptions"] |
| core/collections | seedRef | ["seed_id"] |
| core/collections | specRefIngested | ["step_id", "artifact_id"] |
| core/collections | coverageGap | ["upstream_item_id", "source_step", "reason"] |
| core/errors | errorState | ["code", "message"] |
| core/canon | registry (top-level) | ["registry_version", "entries", "aliases"] |
| core/canon | lifecycle | ["introduced_at"] |
| core/canon | aliasLifecycle | ["deprecated_since"] |
| core/canon | entry | ["id", "kind", "preferred_label", "definition", "version", "status", "owners", "lifecycle"] |
| core/canon | alias | ["kind", "normalized", "target_id", "status"] |

---

## 16. Duplicate Property Definitions (Different Structures)

Properties defined in multiple schemas with **structurally different definitions**:

### High-Impact Duplicates

| Property | Variants | Schemas |
|---|---|---|
| **`status`** | 13 variants | 09, 14, 16 (many sub-contexts), core/canon |
| **`severity`** | 9 variants | 06, 11, 16 (multiple sub-contexts), core/errors |
| **`type`** | 11 variants | 02, 11, 16 (multiple sub-contexts), core/collections |
| **`method`** | 3 variants | 05 (HTTP verbs 5), 15 (HTTP verbs 7), 16 (drift methods) |
| **`id`** | 4 variants | Most schemas (kebabId via $ref), 16 (screamingSnakeId), core/collections (canonicalId pattern) |
| **`description`** | 2 variants | Most: plain string; 14_roadmap: string with `^\S+\s+\S+.*$` pattern |
| **`protocol`** | 3 variants | 02 (6 values), 05 (4 values), 02 conditional |
| **`category`** | 3 variants | 07 (11 NFR categories), 11 (5 threat categories), 13a (4 assessment categories) |
| **`scope`** | 4 variants | 01 (enum), 02 (enum), 06 (object), seed_manifest ($ref) |
| **`owner`** | 2 variants | 23 schemas ($ref atoms/owner); core/collections (plain string) |

### Method enum inconsistency (notable)

| Schema | method values |
|---|---|
| 05_interface_contracts | ["GET", "POST", "PUT", "PATCH", "DELETE"] |
| 15_scaffold | ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"] |
| 16_impl_context (drift) | ["runtime-sample", "log-diff", "schema-diff", "trace-replay"] |

Step 15 adds OPTIONS and HEAD. Step 05 has PATCH before DELETE while Step 15 has DELETE before PATCH.

### fr_id inconsistency

| Schema | Definition |
|---|---|
| 04_fr_list | `$ref` to `atoms/1#kebabId` |
| 16_impl_context | Inline `pattern: "^[a-z0-9]+(?:-[a-z0-9]+)*$"` (same pattern but not using $ref) |

### dependencies inconsistency

| Schema | Definition |
|---|---|
| 09_impl_plan | `$ref` to `collections/1#dependencyList` (allows strings or objects) |
| 14_roadmap | `$ref` to `collections/1#dependencyObjectList` (objects only) |

---

## 17. Schemas NOT in schema/ Directory

### In canon/ directory (registered in schema_registry.json)

| File | $id |
|---|---|
| `canon/kind.schema.json` (32 LOC) | `https://specdev.local/schema/canon/kind/1` |
| `canon/aliases.schema.json` (27 LOC) | `https://specdev.local/schema/canon/aliases/1` |

Both reference `core/canon/1` definitions. They are registered in `tools/schema_registry.json`.

### In tests/fixtures/ (test data with $schema references)

Many test fixture JSON files in `tests/fixtures/` contain `$schema` URIs pointing to step schemas. These are test data, not schema definitions. Found in:
- `tests/fixtures/seed_manifest/` (2 files)
- `tests/fixtures/step_03/` (2 files)
- `tests/fixtures/step_04/` (2 files)
- `tests/fixtures/step_05/` (2 files)
- `tests/fixtures/step_10/` (4 files)
- `tests/fixtures/step_11/` (3 files)
- `tests/fixtures/step_16/` (13 files)

### Third-party (in devspec_env/)

Several JSON Schema metaschemas exist in `devspec_env/lib/python3.9/site-packages/jsonschema_specifications/schemas/` (draft4, draft6, draft7, draft201909, draft202012). These are part of the jsonschema Python package and are not project schemas.

---

## Summary Statistics

| Metric | Value |
|---|---|
| Total schema files | 24 (in schema/) + 2 (in canon/) = **26** |
| Total LOC | 6,015 (schema/) + 57 (canon/) = **6,072** |
| Total bytes | 160,595 (schema/) |
| Core definitions | 44 (6 atoms + 28 collections + 1 error + 9 canon) |
| Total $ref usage | 448 |
| Core $ref adoption | 100% of step schemas |
| Description coverage | 6.1% (56/919 properties) |
| Unique enum definitions | ~61 (approximate — see section 14 caveat) |
| Schemas with generation_quality | 19/19 step schemas (100%) |
| Schemas with seed_refs | 19/19 step schemas (100%) |
| Schemas with canonical triad | 19/19 step schemas (100%) |
| Web-service term occurrences | 39 |
| Duplicate properties with different structures | 30+ property names |
| Properties with method enum inconsistency | method (3 incompatible variants) |
| Largest schema | 16_impl_context.schema.json (1,868 LOC, 31.1% of total) |
| Smallest schema | core/errors.schema.json (32 LOC) |
