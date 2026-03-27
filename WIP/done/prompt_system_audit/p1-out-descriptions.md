# P1-F: Schema Description Quality & Prompt-Schema Alignment -- Findings

## Summary
- Total findings: 18
- Critical: 0 | High: 3 | Medium: 8 | Low: 5 | Info: 2

## Methodology

Sampled 68 descriptions across 8 schemas (00_charter, 02_system_sketch, 05_interface_contracts, 07_nfrs, 09_impl_plan, 14_roadmap, 16_impl_context, core/atoms + core/collections + core/canon). Evaluated each description on 5 axes:
1. **Specificity**: Does it tell an LLM what to produce?
2. **Unambiguity**: Could two LLMs interpret differently?
3. **Constraint surfacing**: Does the description mention constraints enforced by the schema?
4. **Examples**: Are examples provided where field name alone is insufficient?
5. **Relationship clarity**: Does it explain connections to other fields/upstream artifacts?

## Description Quality Assessment

### Overall Quality Rating: GOOD (7.5/10)

The descriptions across all 26 schemas are notably consistent in style and thoroughness. The bulk-added descriptions from commit 547c1f2 are NOT boilerplate -- they follow a coherent pattern of (purpose + constraint + context). The enum extraction in c498c93 improved quality further by centralizing enum definitions with their own descriptions in atoms.schema.json.

### Quality Breakdown by Schema Category

#### Core Schemas (atoms, collections, canon, errors, step_base): 8/10
- **atoms.schema.json**: Excellent. Every $defs entry has a description that explains purpose AND where it is used (e.g., `httpMethodFull` says "Extended HTTP method set including OPTIONS and HEAD for scaffold interface mappings"). `kebabId` includes examples array. `owner` correctly references canon/kinds/owner.json.
- **collections.schema.json**: Strong. `traceRef` explains external trace requirements. `canonicalRef` explains binding semantics. `dependencyItem` conditional requirements for external type are documented.
- **canon.schema.json**: Strong. Lifecycle states are well-documented with progression semantics. `entry` has comprehensive descriptions including conditional requirements.
- **errors.schema.json**: Concise and clear. Severity levels documented with operational semantics.
- **step_base.schema.json**: Good. `canonical_refs_used` describes validation behavior. `_migration_notes` explains origin.

#### Step Schemas 00-08 (Discovery Phase): 8/10
- Consistently high quality. Descriptions reference constraint values (minLength, minItems), give examples in parentheses, and explain upstream relationships.
- Best examples: `02_system_sketch` tags enum describes each category (criticality, data sensitivity, tenancy, lifecycle). `04_fr_list` acceptance_criteria explains fixture_ref purpose.

#### Step Schemas 09-12 (Mid-Pipeline): 7.5/10
- `09_impl_plan`: Good but Quick Reference in prompt is inaccurate (see FINDING-006).
- `10_governance`: Strong descriptions for commit_message_rules and review_policy.
- `11_redteam`: Category description covers all 5 values well.
- `12_ci_gates`: Security sub-object has clear token_permissions description with example.

#### Step Schemas 13-16 (Implementation Phase): 7/10
- `14_roadmap`: Complex schema, descriptions adequate but some nested task fields could be more specific.
- `15_scaffold`: Previously below 100%, now good. `build_status` describes all 3 enum values with parenthetical meanings.
- `16_impl_context`: Largest schema (~1600 lines). Descriptions are consistent but some deep nesting has generic descriptions (see FINDING-003).

#### Previously Below 100% Schemas (02_system_sketch, 15_scaffold, 16_impl_context, canon, collections): 7.5/10
- These were the focus schemas. Newly-added descriptions are NOT bulk-generated filler. They follow the same quality standards as the rest. Specific assessment:
  - `02_system_sketch`: Tags enum was already well-described. Component type references atoms. No quality gaps found.
  - `15_scaffold`: `interface_map` items have clear descriptions. `build_status` enum values are explained.
  - `16_impl_context`: Large schema with many descriptions added. Quality is consistent but see findings below for a few weak spots.
  - `canon`: All lifecycle fields well-documented. `aliasStatus` and `entryStatus` explain each enum value.
  - `collections`: `environmentConfig` oneOf branches each have type descriptions. `techStack` categories are described.

### Sample Assessment (68 descriptions evaluated)

| Category | Count | Verdict |
|----------|-------|---------|
| Genuinely helpful (specific, actionable) | 51 | 75% |
| Adequate (correct but could be more specific) | 14 | 21% |
| Boilerplate/generic | 3 | 4% |

The 3 borderline boilerplate descriptions:
1. `collections.schema.json` -- `stringArray.items.description`: "A string entry in the array" -- too generic, but acceptable for a truly generic collection.
2. `16_impl_context.schema.json` -- multiple `status_ref` descriptions: "Canonical reference for the [X] status in the registry" -- repetitive across many sections but technically accurate.
3. `collections.schema.json` -- `anyJson` variants: "JSON object value", "JSON number value" etc. -- inherently generic but correct for a catch-all type.

## Prompt-Schema Spot Checks

### Prompt 00 (Project Charter)

**Schema required fields** (step-specific): `problem_statement`, `success_metrics`, `stakeholders`, `user_segments`
**Step-base required**: `id`, `owner`, `created_at`, `canonical_refs_used`

**Output Contract analysis**:
- Contains: `id`, `owner`, `created_at`, `title`, `problem_statement`, `stakeholders`, `user_segments`, `success_metrics`, `canonical_refs_used`
- Missing from Output Contract: none of the required fields are missing.
- **ISSUE**: Output Contract omits optional fields `in_scope`, `out_of_scope`, `assumptions`, `risks`, `links` -- but prompt text and checklist strongly encourage them. This is acceptable since they are schema-optional.
- Quick Reference says "Required: `id`, `owner`, `created_at`, `problem_statement`, `success_metrics`" -- this omits `stakeholders` and `user_segments` which ARE required by schema. **See FINDING-007.**

### Prompt 05 (Interface Contracts)

**Schema required fields** (step-specific): `apis`
**Per-API required**: `api_id`, `name`, `version`, `protocol`, `owner`, `interface_ref`

**Output Contract analysis**:
- Contract shows: `id`, `owner`, `created_at`, `apis: []`, `canonical_refs_used: []`
- Empty `apis` array -- acceptable as a skeleton.
- Quick Reference says "Required Fields: each API needs `api_id`, `name`, `version`, `protocol`, and `owner`" -- this omits `interface_ref` which IS required by schema. **See FINDING-008.**

### Prompt 09 (Implementation Plan)

**Schema required fields** (step-specific): `tech_stack`, `milestones`, `trace`
**Per-milestone required**: `milestone_id`, `name`, `deliverables`, `status`

**Output Contract analysis**:
- Contract shows: `id`, `owner`, `created_at`, `tech_stack`, `milestones`, `migration_plan`, `dependencies`, `trace`, `canonical_refs_used`
- All required fields present. Good.
- Quick Reference says "Required: `tech_stack`" -- omits `milestones` and `trace` which ARE required by schema. **See FINDING-009.**
- Quick Reference says milestones have "optional `target_date`" -- correct per schema, `target_date` is NOT in milestone required.
- BUT Quick Reference omits `deliverables` and `status` from milestone required fields -- these ARE required. **See FINDING-009.**

### Prompt 14 (Roadmap)

**Schema required fields** (step-specific): `tech_stack`, `milestones`
**Per-milestone required**: `milestone_id`, `name`, `target_date`, `user_story`, `source_milestones`, `tasks`, `deliverables`, `fr_refs`, `capability_refs`

**Output Contract analysis**:
- Contract includes all required milestone fields: `milestone_id`, `name`, `user_story`, `source_milestones`, `tasks`, `deliverables`, `target_date`, `fr_refs`, `capability_refs`. Good.
- Contract includes `$schema` field with note about stripping during validation. Good.
- Output Contract does NOT include `status` for milestones -- but `status` is NOT in schema required (only the 9 fields listed). Correct.
- **ISSUE**: `dependencies` in Output Contract is missing but it is NOT required. Acceptable.
- No Quick Reference section issues found specific to required fields.

### Prompt 16 (Impl Context)

**Schema required fields** (step-specific): `plan.status` is the only absolute required.
**Plan.spec_alignment.checklist items required**: `id`, `spec_ref`, `description`, `linked_test_expectation`

**Output Contract analysis**:
- Contract shows full `plan` object with `status: "active"`, `summary`, `docs_impact`, `spec_alignment` with `checklist`, `ambiguities`, `solution`, `context`, `review_requirements`.
- Checklist items include all required fields: `id`, `spec_ref`, `description`, `linked_test_expectation`, plus `nfr_refs`, `fixture_ref`, `implementation`.
- Contract does NOT include `canonical_refs_used` -- which IS required by step_base. **See FINDING-010.**
- Quick Reference table is informative and matches schema.

## Findings

### FINDING-001: traceRef.type description lacks valid values list
- **Severity**: MEDIUM
- **Category**: DESCRIPTION
- **Location**: schema/core/collections.schema.json:62
- **Description**: The `traceRef.type` field description says "Trace type -- validated against canon/kinds/trace_type.json entries" but does not enumerate the allowed values. While validated at runtime, an LLM generating artifacts cannot know valid values from the description alone.
- **Evidence**: `"description": "Trace type -- validated against canon/kinds/trace_type.json entries."` -- compared to e.g. `owner` which also says "validated against canon/kinds/owner.json entries" but at least the owner atom shows pattern `^[a-z][a-z0-9_-]*$`.
- **Recommendation**: Add an examples array or enumerate common trace types (fr, api, nfr, inv, fixture, doc, capability, component) in the description text, or add a comment about reading the canon file.

### FINDING-002: atoms.owner description lacks valid values
- **Severity**: MEDIUM
- **Category**: DESCRIPTION
- **Location**: schema/core/atoms.schema.json:42
- **Description**: The `owner` atom description says "validated against canon/kinds/owner.json entries" but does not list the allowed values. Multiple prompts hardcode the list (api, ui, system, ops, data, product, business, engineering) but the schema description alone is insufficient for LLM generation.
- **Evidence**: Description: `"Artifact owner -- validated against canon/kinds/owner.json entries."` Contrast with prompts which list all 8 values explicitly.
- **Recommendation**: Either add an `examples` array to the atom (like `kebabId` has) listing the 8 standard owners, or reference the prompt guidance. The pattern `^[a-z][a-z0-9_-]*$` is too permissive to guide generation.

### FINDING-003: 16_impl_context deep-nested status_ref descriptions are repetitive
- **Severity**: LOW
- **Category**: DESCRIPTION
- **Location**: schema/16_impl_context.schema.json (multiple locations: lines 240, 517, 688, 938, 979, 1008, 1059, 1085, 1161, 1189, 1262, 1357, 1531, 1532)
- **Description**: At least 14 `status_ref` and `command_ref` fields across the impl_context schema all use nearly identical descriptions: "Canonical reference for the [X] status/command in the registry." While technically correct, this provides zero disambiguation between the different contexts where these refs appear.
- **Evidence**: `docs_impact.status_ref`: "Canonical reference for the docs impact status in the registry." vs `drift.status_ref`: "Canonical reference for the drift status in the registry." -- An LLM cannot distinguish what kind values or IDs are appropriate for each.
- **Recommendation**: Add the expected `kind` value or example `id` to each status_ref description. E.g., "Canonical reference (kind: status) for the docs_impact status, e.g. cn:core:status:required."

### FINDING-004: stageName and environmentName overlap without clarification
- **Severity**: MEDIUM
- **Category**: DESCRIPTION
- **Location**: schema/core/collections.schema.json:247 and schema/core/collections.schema.json:256
- **Description**: `environmentName` and `stageName` have identical enum values (`dev`, `ci`, `staging`, `prod`) and very similar descriptions. The distinction between "deployment environment" and "pipeline stage" is not clear enough for an LLM to know which to use when.
- **Evidence**: `environmentName`: "Deployment environment name. One of dev, ci, staging, or prod." vs `stageName`: "Pipeline stage name indicating the deployment target. One of dev, ci, staging, or prod." -- The wording "deployment target" in stageName makes it sound identical to environmentName.
- **Recommendation**: Clarify that `stageName` is used specifically for NFR `stage` fields (delivery phase) while `environmentName` is for infrastructure environment configs in Step 02a. Or consolidate into one if they are truly interchangeable.

### FINDING-005: nfr_id has bespoke pattern instead of using kebabId atom
- **Severity**: LOW
- **Category**: DESCRIPTION
- **Location**: schema/07_nfrs.schema.json:24
- **Description**: The `nfr_id` field uses an inline pattern `^nfr-[a-z0-9]+-[a-z0-9-]+$` instead of referencing `kebabId` atom. The description says 'nfr-<category>-<name>' format but the pattern actually requires exactly one hyphen-separated segment after `nfr-` before additional segments. This is inconsistent with other ID fields that use `$ref: kebabId`.
- **Evidence**: Pattern `^nfr-[a-z0-9]+-[a-z0-9-]+$` requires at least 3 segments (nfr + category + name) while most other IDs use the generic kebabId pattern `^[a-z0-9]+(?:-[a-z0-9]+)*$`.
- **Recommendation**: The description is helpful and explains the expected format well. The inline pattern is intentional to enforce the nfr- prefix and multi-segment structure. No change needed to description; note as a design difference only.

### FINDING-006: Prompt 09 Quick Reference omits required fields
- **Severity**: HIGH
- **Category**: DESCRIPTION
- **Location**: prompts/prompt_09_impl_plan.md:133
- **Description**: Quick Reference says "Required: `tech_stack`" but schema requires `tech_stack`, `milestones`, AND `trace`. Also, milestone required fields (`milestone_id`, `name`, `deliverables`, `status`) are not fully listed -- only `milestone_id` and `name` are shown.
- **Evidence**: Schema 09_impl_plan.schema.json line 113-117: `"required": ["tech_stack", "milestones", "trace"]`. Milestone required (line 79-84): `["milestone_id", "name", "deliverables", "status"]`. Prompt says only "Required: `tech_stack`" and lists milestones as "`milestone_id`, `name`, optional `target_date`, `risks`, `spikes`" -- omitting `deliverables` and `status`.
- **Recommendation**: Update Quick Reference to: "Required: `tech_stack`, `milestones`, `trace`. Per milestone: `milestone_id`, `name`, `deliverables`, `status`."

### FINDING-007: Prompt 00 Quick Reference omits stakeholders and user_segments
- **Severity**: HIGH
- **Category**: DESCRIPTION
- **Location**: prompts/prompt_00_project_charter.md:142
- **Description**: Quick Reference says "Required: `id`, `owner`, `created_at`, `problem_statement`, `success_metrics`" but schema also requires `stakeholders` and `user_segments`.
- **Evidence**: Schema 00_charter.schema.json lines 182-187: `"required": ["problem_statement", "success_metrics", "stakeholders", "user_segments"]`. Prompt Quick Reference omits `stakeholders` and `user_segments`.
- **Recommendation**: Update Quick Reference to include all required fields: "Required: `id`, `owner`, `created_at`, `problem_statement`, `success_metrics`, `stakeholders`, `user_segments`."

### FINDING-008: Prompt 05 Quick Reference omits interface_ref from required
- **Severity**: HIGH
- **Category**: DESCRIPTION
- **Location**: prompts/prompt_05_interface_contracts.md:134
- **Description**: Quick Reference says "Required Fields: each API needs `api_id`, `name`, `version`, `protocol`, and `owner`" but schema also requires `interface_ref`.
- **Evidence**: Schema 05_interface_contracts.schema.json lines 170-177: `"required": ["api_id", "name", "version", "protocol", "owner", "interface_ref"]`. Prompt omits `interface_ref`.
- **Recommendation**: Update Quick Reference to include `interface_ref`.

### FINDING-009: Prompt 09 milestone required field list incomplete
- **Severity**: MEDIUM
- **Category**: DESCRIPTION
- **Location**: prompts/prompt_09_impl_plan.md:134
- **Description**: Prompt lists milestone fields as "`milestone_id`, `name`, optional `target_date`, `risks`, `spikes`" -- this both omits required fields (`deliverables`, `status`) and lists optional fields (`risks`, `spikes`) without marking them as optional, creating a misleading impression.
- **Evidence**: Schema milestone required: `["milestone_id", "name", "deliverables", "status"]`. `target_date`, `risks`, `spikes` are NOT required. Prompt text conflates required and optional.
- **Recommendation**: Restructure to: "Per milestone required: `milestone_id`, `name`, `deliverables`, `status`. Optional: `target_date`, `risks`, `spikes`, `status_ref`."

### FINDING-010: Prompt 16 Output Contract missing canonical_refs_used
- **Severity**: MEDIUM
- **Category**: DESCRIPTION
- **Location**: prompts/prompt_16_impl_context.md:265-365
- **Description**: The Output Contract JSON example does not include `canonical_refs_used` which is required by step_base schema. An LLM following the Output Contract as a template would produce invalid JSON.
- **Evidence**: step_base.schema.json line 47-51: `"required": ["id", "owner", "created_at", "canonical_refs_used"]`. Output Contract in prompt shows `id`, `owner`, `created_at` but no `canonical_refs_used`.
- **Recommendation**: Add `"canonical_refs_used": []` to the Output Contract example.

### FINDING-011: connection.schema_ref pattern description unclear
- **Severity**: LOW
- **Category**: DESCRIPTION
- **Location**: schema/02_system_sketch.schema.json:120
- **Description**: The `schema_ref` field has pattern `^(?:-tbd|(file://|https://|glossary:|api:).+)$` and description says "Reference to the schema governing data exchanged over this connection." The pattern supports `-tbd` as a valid value but the description does not explain this placeholder convention.
- **Evidence**: Pattern includes `-tbd` but description only says "Reference to the schema." An LLM would not know that `-tbd` is the accepted placeholder when schema is not yet defined.
- **Recommendation**: Add to description: "Use '-tbd' if the exchange schema is not yet defined. Supported prefixes: file://, https://, glossary:, api:."

### FINDING-012: 14_roadmap dependencies uses dependencyObjectList but 09_impl_plan uses dependencyList
- **Severity**: MEDIUM
- **Category**: DESCRIPTION
- **Location**: schema/14_roadmap.schema.json:228 vs schema/09_impl_plan.schema.json:93
- **Description**: Step 14 requires `dependencyObjectList` (structured objects only) while Step 09 uses `dependencyList` (allows mixed strings and objects). Neither schema description explains this difference or why dependencies must be structured in the roadmap but can be simple strings in the impl plan.
- **Evidence**: Step 09: `"$ref": "vc:core:collections#dependencyList"` (mixed). Step 14: `"$ref": "vc:core:collections#dependencyObjectList"` (objects only). Both have description "External or internal dependencies required by the [plan/roadmap]." -- identical wording, different validation.
- **Recommendation**: Step 14 description should note: "Unlike Step 09, roadmap dependencies must be structured objects (not simple strings) to enforce owner and note fields for external dependencies."

### FINDING-013: canonicalRef.version lacks format guidance
- **Severity**: LOW
- **Category**: DESCRIPTION
- **Location**: schema/core/collections.schema.json:118
- **Description**: The `version` field in `canonicalRef` has description "Semantic version of the canonical entry at the time of reference" but no pattern constraint. The canonical registry's own `semver` $def enforces `^\d+\.\d+\.\d+$` but canonicalRef.version is a plain string.
- **Evidence**: `canon.schema.json` `semver` anchor: `"pattern": "^\\d+\\.\\d+\\.\\d+$"`. `canonicalRef.version`: `"type": "string"` with no pattern.
- **Recommendation**: Either add the same pattern to canonicalRef.version, or describe the expected format: "Semantic version string in MAJOR.MINOR.PATCH format matching the canonical entry's version."

### FINDING-014: 16_impl_context.execution.emergent_ambiguities.severity lacks enum
- **Severity**: MEDIUM
- **Category**: DESCRIPTION
- **Location**: schema/16_impl_context.schema.json:1638
- **Description**: The `severity` field in `emergent_ambiguities` is just `"type": "string"` with description "Severity of the emergent ambiguity" -- no enum constraint, unlike the planning `ambiguities.severity` which is constrained to `["blocking", "non_blocking"]`. An LLM could produce any string value.
- **Evidence**: Planning ambiguities severity (line 638): `"enum": ["blocking", "non_blocking"]`. Emergent ambiguities severity (line 1638): `"type": "string"` only. Same concept, different constraints, no description explaining this inconsistency.
- **Recommendation**: Either add the same enum constraint, or document in the description why emergent ambiguities have free-form severity: "Free-form severity string for emergent ambiguities discovered during execution (unlike planning ambiguities which use blocking/non_blocking)."

### FINDING-015: collections.stringArray items description too generic
- **Severity**: LOW
- **Category**: DESCRIPTION
- **Location**: schema/core/collections.schema.json:23
- **Description**: The `stringArray` items description is "A string entry in the array." This is inherently generic because stringArray is reused across 20+ fields with very different semantics (risks, secrets, compliance items, exclusions, module names, etc.).
- **Evidence**: Used for `risks`, `secrets`, `compliance`, `in_scope`, `out_of_scope`, `assumptions`, `modules`, `exclusions`, etc. The generic description cannot help with any of these.
- **Recommendation**: No fix needed for the core definition (it IS generic by design). However, each usage site SHOULD override the items description via sibling `description` on the `$ref` usage. Most already do this adequately via the parent field description.

### FINDING-016: Prompt 00 Output Contract missing in_scope/out_of_scope despite schema minItems: 3
- **Severity**: MEDIUM
- **Category**: DESCRIPTION
- **Location**: prompts/prompt_00_project_charter.md:186-244
- **Description**: While `in_scope` and `out_of_scope` are not in the top-level `required` array, they DO have `minItems: 3` constraints. The Output Contract example omits them entirely, which could lead an LLM to skip them. The schema enforces minItems only when the field IS present, but the prompt's Self-Audit Gate says "In/out-of-scope each list >=3 specific items" suggesting they are always expected.
- **Evidence**: Schema: `in_scope` has `minItems: 3` but is not in `required`. Prompt checklist says they must have >=3 items. Output Contract omits them. This creates a contradictory signal.
- **Recommendation**: Add `in_scope` and `out_of_scope` to the Output Contract example with placeholder arrays of 3+ items to align with the self-audit gate expectations.

### FINDING-017: 12_ci_gates security.environment_protection lacks description depth
- **Severity**: INFO
- **Category**: DESCRIPTION
- **Location**: schema/12_ci_gates.schema.json:108
- **Description**: The `environment_protection` object description is "Environment protection rules for deployment gates" which is adequate but does not explain when to use it or what deployment scenarios require it.
- **Evidence**: The field is optional with no examples. CI teams may not know whether to populate it for staging vs production environments.
- **Recommendation**: Minor enhancement: "Environment protection rules for deployment gates. Typically configured for staging and production environments to enforce reviewer approval and deployment delays."

### FINDING-018: Prompt Output Contracts inconsistently include $schema field
- **Severity**: INFO
- **Category**: DESCRIPTION
- **Location**: Multiple prompt files
- **Description**: Prompt 14's Output Contract includes `"$schema": "vc:14-roadmap"` with an explicit note about stripping during validation. Prompts 00, 05, 09, and 16 do NOT include `$schema` in their Output Contracts. Since step_base defines `$schema` as a property (not required), this inconsistency is not a validation issue, but it creates divergent behavior across prompts.
- **Evidence**: prompt_14_roadmap.md:231 has `"$schema": "vc:14-roadmap"`. prompt_00/05/09/16 Output Contracts lack it.
- **Recommendation**: Standardize: either all Output Contracts include `$schema` or none do. Given prompt_14's explicit note about stripping, prefer including it everywhere.

## Summary Statistics

### Description Quality by Schema (out of 10)

| Schema | Rating | Notes |
|--------|--------|-------|
| core/atoms.schema.json | 9/10 | Excellent; examples on kebabId, clear enum descriptions |
| core/collections.schema.json | 8/10 | Strong; only generic stringArray items weak |
| core/canon.schema.json | 9/10 | Thorough lifecycle documentation |
| core/errors.schema.json | 8/10 | Concise and clear |
| core/step_base.schema.json | 8/10 | Good validation behavior docs |
| 00_charter.schema.json | 8/10 | Good constraint surfacing |
| 01_capabilities.schema.json | 8/10 | Clear verb/scope/trace guidance |
| 02_system_sketch.schema.json | 8/10 | Tags enum well-described |
| 02a_delivery_baseline.schema.json | 8/10 | Environment config clear |
| 03_glossary.schema.json | 8/10 | Pattern+constraint in descriptions |
| 04_fr_list.schema.json | 8/10 | AC structure clear |
| 05_interface_contracts.schema.json | 7/10 | Good but missing some param context |
| 06_invariants.schema.json | 8/10 | Language enum well-described |
| 07_nfrs.schema.json | 8/10 | Target oneOf patterns clear |
| 08_fixtures.schema.json | 7/10 | Adequate |
| 09_impl_plan.schema.json | 7/10 | Good but prompt misalignment |
| 10_governance.schema.json | 8/10 | Detailed policy descriptions |
| 11_redteam.schema.json | 8/10 | Threat model well-documented |
| 12_ci_gates.schema.json | 7/10 | Security section could expand |
| 13_extension_generator.schema.json | 7/10 | Adequate |
| 13a_completeness_assessment.schema.json | 8/10 | Impact scale well-documented |
| 14_roadmap.schema.json | 7/10 | Complex; dependency difference undocumented |
| 15_scaffold.schema.json | 7/10 | Previously below 100%; now adequate |
| 16_impl_context.schema.json | 7/10 | Large; repetitive status_refs, missing enum on emergent severity |
| seed_manifest.schema.json | 8/10 | Clear step_requirements docs |
| step_order.schema.json | 9/10 | Excellent; downstream_consumers has usage note |

### Top 10 Most Ambiguous Descriptions (LLM Misinterpretation Risk)

1. **atoms.owner**: "validated against canon/kinds/owner.json entries" -- LLM cannot know valid values without reading that file
2. **traceRef.type**: "validated against canon/kinds/trace_type.json entries" -- same issue
3. **stageName vs environmentName**: identical enum, unclear distinction
4. **emergent_ambiguities.severity**: unconstrained string vs planning ambiguities enum
5. **canonicalRef.version**: no format guidance, just "Semantic version"
6. **schema_ref in connections**: `-tbd` placeholder not explained
7. **dependencyList vs dependencyObjectList**: same description, different validation
8. **stringArray.items**: "A string entry in the array" -- no semantic context
9. **Multiple status_ref fields in 16_impl_context**: all say "Canonical reference for the [X] status" without expected kind/ID hints
10. **14_roadmap source_milestones**: description says "Upstream Step 09 milestone IDs" but does not explain what happens if Step 09 has no milestones

### Prompt-Schema Alignment Summary

| Prompt | Quick Ref Accurate | Output Contract Complete | Issues |
|--------|-------------------|------------------------|--------|
| 00 | Missing 2 required fields | Missing in_scope/out_of_scope | FINDING-007, FINDING-016 |
| 05 | Missing interface_ref | Skeleton only (acceptable) | FINDING-008 |
| 09 | Missing milestones, trace; wrong milestone required | Complete | FINDING-006, FINDING-009 |
| 14 | Adequate | Complete | None |
| 16 | Adequate | Missing canonical_refs_used | FINDING-010 |

### Answers to Audit Questions

**Q1: How many descriptions are genuinely helpful vs boilerplate?**
Of 68 sampled: 51 (75%) genuinely helpful, 14 (21%) adequate, 3 (4%) borderline boilerplate. The 100% coverage push did NOT produce mass boilerplate.

**Q2: Which descriptions would an LLM most likely misinterpret?**
Top 10 listed above. The pattern of referencing canon/kinds/*.json files for valid values is the single biggest LLM-unfriendly pattern -- an LLM reading only the schema cannot determine valid values for `owner` or `traceRef.type`.

**Q3: Are there fields where description contradicts schema constraint?**
One case: `emergent_ambiguities.severity` has no enum constraint but the broader context strongly implies it should mirror the planning `ambiguities.severity` enum. Not a contradiction per se, but a consistency gap.

**Q4: Do Output Contract examples in prompts match current schema required fields?**
No. 4 of 5 checked prompts have Quick Reference or Output Contract gaps. FINDING-006 through FINDING-010 detail these. Prompt 14 is the only one fully aligned.

**Q5: Are there schema properties needing descriptions beyond bulk-added ones?**
No missing descriptions found -- coverage remains at 100%. Quality improvements recommended for ~10 descriptions per findings above.
