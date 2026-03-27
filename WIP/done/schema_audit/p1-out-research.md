# P1-F: Research Alignment -- Findings

## Summary
- Total findings: 14
- Critical: 0 | High: 3 | Medium: 5 | Low: 3 | Info: 3

---

## Findings

### FINDING-001: ALIGN-4 (additionalProperties: false) is CONFIRMED ACHIEVED -- but no CI regression guard exists
- **Severity**: MEDIUM
- **Category**: RESEARCH
- **Location**: All 26 schema files
- **Description**: Automated recursive analysis of all 26 schema files (24 in `schema/` + 2 in `canon/`) confirms that every `type: "object"` definition with `properties` or `patternProperties` has `additionalProperties: false`. Zero violations found at any nesting depth. The ALIGN-4 "ACHIEVED" claim in the research roadmap is **verified accurate**. However, there is NO CI lint, test, or pre-commit hook that enforces this invariant. A future schema addition could regress this without detection.
- **Evidence**: Python script recursed into all `properties`, `items`, `allOf`, `anyOf`, `oneOf`, `if/then/else`, and `$defs` blocks across all 26 files. Result: 0 violations. No test in `tests/` asserts this property (searched for `additionalProperties` in test files -- only found in mock schemas with `True` values in `test_cli.py`). No validator in `tools/specdev_tools/` checks this property (only `schema_differ.py` references it for diff logic, not enforcement).
- **Recommendation**: Create a CI lint (e.g., `schema-strictness-lint`) that asserts `additionalProperties: false` on every `type: "object"` node across all schema files. Can be a simple pytest parametrized test or a new CLI subcommand.

---

### FINDING-002: ALIGN-5 nesting depth -- 15 of 20 step/manifest schemas exceed 3 levels; step 16 reaches 9
- **Severity**: HIGH
- **Category**: RESEARCH
- **Location**: Multiple schema files (see table below)
- **Description**: The research roadmap states "step_16 has 19 levels" for ALIGN-5 and classifies it as FUNDAMENTAL/XL effort. Actual measured nesting depths are lower than the roadmap claims (9, not 19), but still significantly exceed the 3-level target. Only 5 of 20 step/manifest schemas meet the 3-level maximum.

**Measured nesting depths (object/array levels)**:

| Schema | Max Depth | Deepest Path |
|---|---|---|
| 16_impl_context | 9 | `plan.spec_alignment.checklist[].implementation.actions[].allOf[].then.target` |
| 14_roadmap | 7 | `milestones[].tasks[].acceptance_criteria[].criterion_id` |
| 04_fr_list | 5 | `functional_requirements[].acceptance_criteria[].criterion_id` |
| 05_interface_contracts | 5 | `apis[].parameters[].name` |
| 11_redteam | 5 | `threats[].mitigations[].type` |
| 12_ci_gates | 5 | `jobs[].steps[].id` |
| 01_capabilities | 4 | `capabilities[].trace` |
| 02_system_sketch | 4 | `components[].tags` |
| 06_invariants | 4 | `rules[].expression` |
| 07_nfrs | 4 | `nfrs[].conditions[]` |
| 08_fixtures | 4 | `fixtures[].steps[]` |
| 09_impl_plan | 4 | `milestones[].deliverables[]` |
| 13_extension_generator | 4 | `extensions[].rules[]` |
| 13a_completeness_assessment | 4 | `missing_elements[].affected_items[]` |
| 00_charter | 3 | (within limit) |
| 02a_delivery_baseline | 2 | (within limit) |
| 03_glossary | 3 | (within limit) |
| 10_governance | 3 | (within limit) |
| 15_scaffold | 3 | (within limit) |
| seed_manifest | 3 | (within limit) |

**Schemas within 3-level limit**: 00_charter, 02a_delivery_baseline, 03_glossary, 10_governance, 15_scaffold, seed_manifest (6 of 20)

**Schemas at depth 4** (borderline -- could possibly be flattened): 01, 02, 06, 07, 08, 09, 13, 13a (8 schemas)

**Schemas at depth 5+** (require structural redesign): 04, 05, 11, 12, 14, 16 (6 schemas)

- **Evidence**: The roadmap's claim of "19 levels" for step 16 appears to be a measurement error. Actual maximum is 9 levels at `plan.spec_alignment.checklist[].implementation.actions[].allOf[0].then.target`. Step 14 reaches 7 levels at `milestones[].tasks[].acceptance_criteria[].criterion_id`.
- **Recommendation**: (1) Correct the roadmap's "19 levels" claim to "9 levels". (2) Prioritize flattening step 16 and step 14 first (highest depths). (3) Depth-4 schemas are borderline and may not justify the effort/risk of restructuring. (4) Consider a "max nesting depth" CI lint to prevent regression.

---

### FINDING-003: ALIGN-6 description coverage confirmed at 6.1% -- 863 properties missing descriptions
- **Severity**: HIGH
- **Category**: RESEARCH
- **Location**: All 26 schema files
- **Description**: The P0 baseline's 6.1% coverage figure (56/919 properties with descriptions) is confirmed by the research roadmap's ALIGN-6 assessment. Core schema description coverage is notably poor:

| Core File | Properties WITH description | Properties WITHOUT | Coverage |
|---|---|---|---|
| core/atoms.schema.json | 2 (`metadata`, `owner`) | 4 (`kebabId`, `timestamp`, `tag`, `screamingSnakeId`) | 33% |
| core/collections.schema.json | 5 | 46 | 9.8% |
| core/canon.schema.json | 0 | 38 | 0% |
| core/errors.schema.json | 0 | 3 | 0% |

Since core definitions are referenced 448 times across all schemas via `$ref`, adding descriptions at the core level would propagate to all consumers. This is the highest-leverage fix for ALIGN-6.

**Methodology note**: The P0 counts are approximate. A definitive count requires clarifying: (a) whether `$defs` properties count (they should -- they are referenced via `$ref`), (b) whether `patternProperties` patterns count, (c) how `allOf/if/then` branches are handled. P1-B owns the definitive count.
- **Evidence**: `core/atoms.schema.json` lines 17-25: `kebabId` has no description despite being the most-referenced definition (60+ uses). `core/errors.schema.json`: zero descriptions on any of its 3 properties (`code`, `message`, `severity`). `core/canon.schema.json`: zero descriptions on all 38 properties including complex objects like `entry` and `alias`.
- **Recommendation**: (1) Prioritize core/ descriptions first (44 definitions, 448 downstream references). (2) Add a CI lint that fails on schemas with <50% description coverage, then ratchet up threshold over time. (3) P1-B should provide the definitive property inventory with drafted descriptions.

---

### FINDING-004: ALIGN-1 -- 2 confirmed inline pattern duplications in step 16; 2 duplicate enum sets across files
- **Severity**: MEDIUM
- **Category**: RESEARCH
- **Location**: `schema/16_impl_context.schema.json`, `schema/11_redteam.schema.json`, `schema/14_roadmap.schema.json`, `schema/09_impl_plan.schema.json`
- **Description**: ALIGN-1 identifies `$ref/$defs` DRY authoring gaps. Automated analysis found:

**Inline pattern duplications (should use `$ref` to core/atoms):**
1. `schema/16_impl_context.schema.json`: `plan.spec_alignment.checklist[].milestone_ref` inlines pattern `^[a-z0-9]+(?:-[a-z0-9]+)*$` instead of `$ref` to `atoms#kebabId`
2. `schema/16_impl_context.schema.json`: `review.semantic_review.fr_coverage[].fr_id` inlines pattern `^[a-z0-9]+(?:-[a-z0-9]+)*$` instead of `$ref` to `atoms#kebabId`

**Duplicate enum sets across files (should be extracted to core/):**
1. `["low", "medium", "high", "critical"]` appears in 3 files: `11_redteam` (threats[].severity), `14_roadmap` (milestones[].risk_status), `16_impl_context` ($defs.severityLevel). Could be `core/collections#severityLevel` or `core/atoms#severityLevel`.
2. `["deferred", "done", "in_progress", "pending"]` appears in 2 files: `09_impl_plan` (milestones[].status), `14_roadmap` (milestones[].status). Could be `core/collections#milestoneStatus`.

**Step 16 `$defs` extraction candidates** (4 local definitions, 7 local `$ref` uses):
- `specRef`: object -- similar to but different from `core/collections#traceRef` (adds `line_range`, `commit_hash`, changes `type` enum)
- `severityLevel`: enum -- duplicated in 3 schemas (see above)
- `executionStatus`: enum `["passed", "failed", "blocked", "partial"]` -- unique to step 16
- `evidenceObject`: object -- unique to step 16

The roadmap states "no P4 progress" for ALIGN-1. This is confirmed. All inline duplication identified in P0 baseline (section 16: fr_id inconsistency, section 14: severityLevel overlap) remains.
- **Evidence**: `schema/16_impl_context.schema.json` `$defs` section defines 4 local definitions with 7 internal `$ref` uses. Two of these (`specRef.type` and `severityLevel`) have overlapping but not identical enum values with definitions in other schemas. The `specRef.type` enum is `["fr", "api", "nfr", "inv", "fixture", "doc", "code"]` while `11_redteam` mitigations uses `["fr", "api", "nfr", "inv", "fixture", "doc", "capability"]` -- they differ in the last value (`code` vs `capability`).
- **Recommendation**: (1) Extract `severityLevel` to `core/collections.schema.json` -- this is the highest-value extraction (3 consumers). (2) Replace 2 inline kebabId patterns in step 16 with `$ref` to `atoms#kebabId`. (3) Extract `milestoneStatus` enum to core/. (4) Defer `specRef`/`evidenceObject` extraction until `traceRef` is evaluated (P1-A scope). (5) Note: `specRef.type` and `mitigations[].type` overlap should be reconciled before extraction.

---

### FINDING-005: ALIGN-2 -- 459 specdev.local URIs in schemas + 33 in tools/prompts/spec files; migration is HIGH effort
- **Severity**: MEDIUM
- **Category**: RESEARCH
- **Location**: All schema files, `tools/schema_registry.json`, `tools/specdev_tools/canonical/lint.py`, `prompts/`, `spec/`
- **Description**: The research roadmap classifies ALIGN-2 (URL to URN migration) as LARGE gap / L effort. The actual blast radius is:

| Location | specdev.local occurrences |
|---|---|
| Schema files (26 files) | 459 |
| `tools/schema_registry.json` | 29 |
| Python tool code | 4 (in `cli.py` and `canonical/lint.py`) |
| Spec data files | 2 (in `spec/05_interface_contracts.json`, `spec/common/seed_manifest.json`) |
| Prompt files | 22 (in `prompts/prompt_*.md`) |
| Migration templates | 18 (in `prompts/migration/template_*.md`) |
| **Total** | **534** |

The current scheme uses two inconsistent URI patterns:
- Step schemas: `https://specdev.local/schema/NN_name.schema.json` (includes `.schema.json` suffix)
- Core schemas: `https://specdev.local/schema/core/{name}/1` (version-suffixed, no extension)
- Canon schemas: `https://specdev.local/schema/canon/{name}/1` (version-suffixed, no extension)

The `SchemaRegistry` class (`tools/specdev_tools/core/registry.py`) uses the `referencing` library's `Registry` + `Resource` pattern for `$ref` resolution. URIs are used as keys in a dictionary lookup against `schema_registry.json`. No HTTP resolution is attempted -- the `.local` TLD is intentionally non-routable.

**Current risks of URL-based scheme:**
1. `.local` is reserved for mDNS (RFC 6762) -- technically a misuse
2. `https://` prefix implies an endpoint that does not exist -- confusing for new contributors
3. Inconsistent suffix conventions (`.schema.json` vs `/1`) create cognitive load
4. LLMs may attempt HTTP resolution of these URIs

- **Evidence**: `tools/specdev_tools/core/registry.py` lines 60-69: `load()` method resolves URI to local file path via `schema_registry.json` dictionary lookup. No HTTP client is involved. `tools/specdev_tools/canonical/lint.py` lines 28-30: Three hardcoded `specdev.local` URIs for canon schema loading.
- **Recommendation**: (1) Confirm the roadmap's assessment: this is indeed L effort (534 occurrences across 70+ files). (2) The inconsistent URI suffix pattern (`*.schema.json` vs `/1`) should be resolved as part of any URI migration. (3) A migration script is feasible since all URI occurrences follow predictable patterns. (4) URN format proposal: `urn:specdev:schema:{category}:{name}:{version}` (e.g., `urn:specdev:schema:step:00-charter:1`, `urn:specdev:schema:core:atoms:1`). (5) Prerequisite: ALIGN-1 (consolidate `$ref` first to reduce URI count).

---

### FINDING-006: ALIGN-10 (src/dist schema split) -- feasibility assessment: VIABLE but requires design decisions
- **Severity**: LOW
- **Category**: RESEARCH
- **Location**: All 19 step schemas
- **Description**: The research roadmap classifies ALIGN-10 as LARGE gap / L effort. Current state assessment:

**Required field saturation is high**: Most step schemas require 11-14 of their properties (out of 12-21 total). On average, 87% of properties are required. This means a "source" (permissive) schema would need to make many fields optional.

**Default values are minimal**: Only 2 defaults exist per schema (`canonical_proposals: []`, `canonical_conflicts: []`). No other properties have defaults.

**Candidate fields for src-mode optionality** (fields that could be omitted during drafting):
- `generation_quality` (boilerplate, always `{assumptions: []}`)
- `spec_refs_ingested` (zero tool consumers per P0 baseline)
- `coverage_gaps` (only consumed by step_12 validator)
- `canonical_refs_used`, `canonical_proposals`, `canonical_conflicts` (the canonical triad -- adds friction during initial authoring)
- `seed_refs` (requires hash computation during authoring)

**Implementation approaches**:
- Option A: Single schema with `if/then` blocks that toggle required arrays based on a `$mode` property
- Option B: Separate `schema/src/` and `schema/dist/` directories with generated dist schemas
- Option C: CLI flag (`--mode draft|final`) that programmatically relaxes required arrays at validation time

- **Evidence**: Property analysis shows `seed_manifest.schema.json` has 9/9 required (100%), while `00_charter.schema.json` has 14/21 (67%) -- the most "flexible" schema. The 10 common boilerplate fields account for 10/11 required fields in most schemas, meaning step-specific content is often just 1-3 required fields.
- **Recommendation**: (1) Option C (CLI flag) is the lowest-effort approach and does not require schema duplication. (2) Define a `DRAFT_OPTIONAL_FIELDS` constant listing the 6 candidate fields above. (3) When `--mode draft` is used, programmatically remove those fields from the `required` array before validation. (4) Defer to after ALIGN-1 and ALIGN-3 (as the roadmap suggests).

---

### FINDING-007: ALIGN-3 (structured errors) -- partially resolved by P5 tools/tests audit; out of scope for schema audit
- **Severity**: INFO
- **Category**: RESEARCH
- **Location**: `tools/specdev_tools/core/errors.py`
- **Description**: ALIGN-3 targets migration from `list[str]` to `SpecError` dataclass returns across all validators and linters. The P5 tools/tests audit (batches 0-3, 6 completed) has made partial progress on this -- `SpecError` is now imported and used by `validate.py` (line 31: `from ..core.errors import PROMOTABLE_PAIRS, SpecError, make_error`). However, the full migration (21 validators + 17 linters) is not complete. **This is a tool-focused gap, not a schema gap -- out of scope for this schema audit.**
- **Recommendation**: Acknowledge ALIGN-3 progress from P5. No schema changes needed.

---

### FINDING-008: ALIGN-7 (--json output) -- partially resolved by P5; out of scope for schema audit
- **Severity**: INFO
- **Category**: RESEARCH
- **Location**: `tools/specdev_tools/cli.py`
- **Description**: ALIGN-7 targets `--json` output for all CLI commands. Per the research roadmap, P4 FIX-030 added `--json` to 5 commands, bringing total to 7/25. The P5 tools/tests audit may have extended this further. **This is a CLI/tool-focused gap, not a schema gap -- out of scope for this schema audit.**
- **Recommendation**: Acknowledge ALIGN-7 progress. No schema changes needed.

---

### FINDING-009: ALIGN-8 (MCP tool) and ALIGN-9 (pre-commit hooks) -- out of scope for schema audit
- **Severity**: INFO
- **Category**: RESEARCH
- **Location**: N/A
- **Description**: ALIGN-8 (WriteValidatedJSON MCP tool) and ALIGN-9 (pre-commit hook coverage) are tool/CI-focused gaps with no direct schema impact. Both are acknowledged as out of scope per the audit plan.
- **Recommendation**: No schema changes needed. These items remain on the research roadmap for future tool initiatives.

---

### FINDING-010: Research roadmap ALIGN-5 depth claim is inaccurate -- "19 levels" should be "9 levels"
- **Severity**: LOW
- **Category**: RESEARCH
- **Location**: `WIP/future/research-alignment-roadmap.md` line 97
- **Description**: The research roadmap states "Step 16 (scaffolding) has 19 levels of nesting." Automated measurement shows the actual maximum nesting depth is **9 levels**, not 19. The deepest path is `plan.spec_alignment.checklist[].implementation.actions[].allOf[0].then.target`. The "19" figure may have been derived from counting JSON indentation levels rather than semantic object/array nesting levels, or it may have been hallucinated. Additionally, the roadmap refers to step 16 as "scaffolding" -- step 16 is `impl_context`, not scaffolding (step 15 is `scaffold`).
- **Evidence**: Python script measuring object/array nesting depth recursively through `properties`, `items`, `allOf`, `if/then/else`, and `$defs` returns max depth = 9 for `schema/16_impl_context.schema.json`.
- **Recommendation**: Correct the roadmap: (1) Change "19 levels" to "9 levels". (2) Change "scaffolding" to "impl_context". (3) Reassess the ALIGN-5 effort from XL to L (9 levels is significant but not as extreme as 19).

---

### FINDING-011: NEW GAP -- No CI lint for schema nesting depth regression
- **Severity**: MEDIUM
- **Category**: RESEARCH
- **Location**: No file (missing capability)
- **Description**: There is no CI check or test that enforces a maximum nesting depth across schema files. As new schemas are added or existing ones extended, nesting depth can increase without detection. This gap is not captured in the research roadmap.
- **Evidence**: Searched `tests/` and `tools/specdev_tools/` for any reference to nesting depth measurement or enforcement. None found.
- **Recommendation**: Add a parametrized pytest test or CLI lint that measures nesting depth per schema and fails if any schema exceeds a configured threshold (initially 9 to match current maximum, then ratchet down as schemas are refactored).

---

### FINDING-012: NEW GAP -- No CI lint for description coverage regression
- **Severity**: MEDIUM
- **Category**: RESEARCH
- **Location**: No file (missing capability)
- **Description**: There is no CI check or test that enforces minimum description coverage on schema files. The current 6.1% coverage could decrease further without detection. This gap is not captured in the research roadmap (ALIGN-6 mentions adding a CI lint in its "next steps" but it is classified as FUTURE with no progress).
- **Evidence**: Searched `tests/` and `tools/specdev_tools/` for any reference to description coverage measurement or enforcement. None found.
- **Recommendation**: Create a `schema-description-lint` that counts properties with/without descriptions per schema file and fails below a configurable threshold. Initially set threshold to 5% (just above current floor for most schemas) and ratchet up as descriptions are added.

---

### FINDING-013: NEW GAP -- URI pattern inconsistency between step schemas and core/canon schemas
- **Severity**: LOW
- **Category**: RESEARCH
- **Location**: All schema `$id` values; `tools/schema_registry.json`
- **Description**: The `$id` URI scheme uses two distinct patterns that are not documented or justified:

| Pattern | Used By | Example |
|---|---|---|
| `https://specdev.local/schema/{filename}.schema.json` | 20 step/manifest schemas | `https://specdev.local/schema/00_charter.schema.json` |
| `https://specdev.local/schema/{path}/{version}` | 6 core/canon schemas | `https://specdev.local/schema/core/atoms/1` |

The step schema pattern includes the `.schema.json` extension in the URI. The core/canon pattern uses a version number suffix (`/1`) without the file extension. This inconsistency is not identified in the research roadmap as a distinct issue -- it is subsumed by ALIGN-2 (URN migration) but should be resolved regardless of whether URN migration proceeds.

- **Evidence**: `schema/00_charter.schema.json` line 2: `"$id": "https://specdev.local/schema/00_charter.schema.json"`. `schema/core/atoms.schema.json` line 3: `"$id": "https://specdev.local/schema/core/atoms/1"`. The `/1` version suffix in core schemas implies a versioning scheme that step schemas do not follow.
- **Recommendation**: If ALIGN-2 (URN migration) proceeds, this inconsistency is resolved naturally. If ALIGN-2 is deferred, consider normalizing to one pattern. The versioned pattern (`/1`) is preferable as it supports future schema versioning.

---

### FINDING-014: NEW GAP -- `specRef.type` enum in step 16 vs `mitigations[].type` in step 11 are almost-but-not-quite identical
- **Severity**: HIGH
- **Category**: RESEARCH
- **Location**: `schema/16_impl_context.schema.json` `$defs.specRef.type`, `schema/11_redteam.schema.json` `threats[].mitigations[].type`
- **Description**: Two schemas define nearly identical "reference type" enums with a single-value divergence:

| Schema | Property | Enum Values |
|---|---|---|
| 16_impl_context | `$defs.specRef.type` | `["fr", "api", "nfr", "inv", "fixture", "doc", "code"]` |
| 11_redteam | `threats[].mitigations[].type` | `["fr", "api", "nfr", "inv", "fixture", "doc", "capability"]` |

Six values are shared; step 16 uses `code` while step 11 uses `capability`. This is a DRY violation that also creates semantic confusion: are `code` and `capability` the same concept? If not, should both enums include both values?

This gap is **not captured in the research roadmap** but overlaps with ALIGN-1 (DRY) and is related to the P0 baseline finding in section 16 (duplicate property definitions). It represents a deeper issue: the toolkit has no canonical "reference type" enum despite multiple schemas needing one.

- **Evidence**: `schema/16_impl_context.schema.json` `$defs.specRef`: `"type": {"type": "string", "enum": ["fr", "api", "nfr", "inv", "fixture", "doc", "code"]}`. `schema/11_redteam.schema.json` `threats.items.properties.mitigations.items.properties.type`: `{"type": "string", "enum": ["fr", "api", "nfr", "inv", "fixture", "doc", "capability"]}`. Note: `core/collections#traceRef` also has a `type` property but uses `$ref` to a trace_type pattern rather than an enum, creating a third variant of "reference type."
- **Recommendation**: (1) Define a canonical `referenceType` enum in `core/collections.schema.json` that includes ALL valid reference type values: `["fr", "api", "nfr", "inv", "fixture", "doc", "code", "capability"]`. (2) Both step 11 and step 16 should `$ref` this shared definition. (3) If `code` and `capability` are step-specific and should not be in the shared enum, use `allOf` with the base enum plus step-specific extensions. (4) Coordinate with P1-A (DRY scope) which owns the architectural decision for this extraction.

---

## Cross-Reference: Research Roadmap vs Schema Audit

| ALIGN-N | Roadmap Status | Schema Audit Verification | Finding |
|---|---|---|---|
| ALIGN-1 | FUTURE | Confirmed: 2 inline patterns + 2 duplicate enums remain | FINDING-004 |
| ALIGN-2 | FUTURE | Confirmed LARGE: 534 URI occurrences across 70+ files | FINDING-005 |
| ALIGN-3 | PARTIAL | Out of scope (tool-focused); partial P5 progress noted | FINDING-007 |
| ALIGN-4 | ACHIEVED | **VERIFIED**: 0 violations across all 26 schemas; no CI guard | FINDING-001 |
| ALIGN-5 | FUTURE | Roadmap claim INCORRECT: 9 levels (not 19); 15/20 schemas exceed 3 | FINDING-002, -010 |
| ALIGN-6 | FUTURE | Confirmed: 6.1% coverage (56/919); core/ is worst at 0-33% | FINDING-003 |
| ALIGN-7 | PARTIAL | Out of scope (CLI-focused) | FINDING-008 |
| ALIGN-8 | FUTURE | Out of scope (tool-focused) | FINDING-009 |
| ALIGN-9 | PARTIAL | Out of scope (CI-focused) | FINDING-009 |
| ALIGN-10 | FUTURE | Viable; Option C (CLI flag) is lowest effort | FINDING-006 |

## New Gaps Not in Roadmap

| Gap | Description | Finding |
|---|---|---|
| No CI lint for additionalProperties regression | ALIGN-4 achieved but unguarded | FINDING-001 |
| No CI lint for nesting depth regression | Nesting can grow without detection | FINDING-011 |
| No CI lint for description coverage regression | Coverage can decrease without detection | FINDING-012 |
| Inconsistent $id URI patterns | Step vs core/canon use different conventions | FINDING-013 |
| Nearly-identical reference type enums | `specRef.type` vs `mitigations[].type` diverge by 1 value | FINDING-014 |

## Recommended Priority for Schema-Specific Fixes

1. **ALIGN-6** (descriptions) -- Highest LLM impact, no breaking changes, mechanical work. Start with core/ (44 definitions, 448 downstream refs).
2. **ALIGN-1** (DRY: inline patterns + duplicate enums) -- 2 inline fixes + 2 enum extractions. Low risk, immediate quality win.
3. **ALIGN-4 CI guard** -- Simple pytest test, prevents regression of achieved state.
4. **ALIGN-5 CI guard** -- Simple pytest test, prevents nesting regression while structural fixes are planned.
5. **ALIGN-13 URI consistency** -- Normalize `$id` patterns before any ALIGN-2 URN migration.
6. **ALIGN-14 reference type enum** -- Extract unified `referenceType` to core/. Requires semantic decision on `code` vs `capability`.
7. **ALIGN-2** (URN migration) -- Large effort, defer until after items 1-6.
8. **ALIGN-10** (src/dist split) -- Design-heavy, defer until after ALIGN-1 and ALIGN-3.
9. **ALIGN-5** (nesting reduction) -- Most disruptive, requires spec format redesign for step 16.
