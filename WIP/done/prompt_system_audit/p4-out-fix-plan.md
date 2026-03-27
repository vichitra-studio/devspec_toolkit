# P4 Fix Plan -- Prompt System Audit

**Date**: 2026-03-20
**Input**: p3-out-master-findings-v2.md (101 findings, reviewed R1-R3)
**Design Decisions**: 13 locked (see master findings)
**Execution Strategy**: 9 sequential batches (0a-0c, 1-8), atomic tasks within batches run in parallel

---

## Execution Summary

| Batch | Tasks | Findings Addressed | Dependencies | Estimated Scope |
|-------|-------|--------------------|--------------|-----------------|
| 0a | 5 | AUDIT-014, 015(schema), 075, 084, 086 | None | 5 schema files + test fixtures |
| 0b | 22 | AUDIT-071, 051, 052, 053, 054, 055, 057, 066 | 0a | 21 schema files (description enrichment) |
| 0c | 1 | AUDIT-008(schema deletion prep), 041, 042, 043 | 0b | 17 prompt files (delete Quick Reference) |
| 1 | 10 | AUDIT-017, 023, 035, 069, 076, 082, 088 | None (parallel with Batch 0). Internal deps: 1-02/1-03 depend on 1-01; 1-05 depends on 1-04 | Mixed config/validator fixes |
| 2 | 5 | AUDIT-002, 006(extract), 007, 018, 026, 091, 101 | 0b, 0c | shared_expectations.md + 22 prompts |
| 3 | 5 | AUDIT-072, 073, 074, 095, 096, 100 | 0 (independent of Batch 2 per master findings) | Canon pipeline + glossary redesign |
| 4 | 15 | AUDIT-001, 003, 008(prompt), 016, 019, 027-031, 038-040, 044, 056, 058, 062, 079-081, 083, 085, 092, 097 | 0b, 0c, 2 | 22 prompt files (synthesis enrichment) |
| 5 | 7 | AUDIT-004, 005, 013, 015(validator), 067, 068 | 4 | Pairwise completeness + 13a redesign |
| 6 | 4 | AUDIT-009, 010, 011, 012, 037, 050 | 2, 4 | Self-Audit Gate redesign |
| 7 | 12 | AUDIT-022, 024, 032-034, 070, 077, 078, 087, 093, 094, 098 | 0-6 | Validator/lint fixes |
| 8 | 10 | AUDIT-020, 021, 025, 045-049, 059-061, 064, 089, 090, 099 | 0-7 | Docs + migration templates |

**Total**: 96 high-level tasks addressing 101 findings (3 N/A, some findings span multiple batches). Multi-file tasks (0c-01, 2-02, 2-03, 2-04, 4-07, 4-08, 4-09, 4-10, 4-11, 6-01, 6-04) MUST be split into per-file sub-tasks for P5 execution

---

## Batch 0a: Structural Schema Changes

These add/modify schema structure (new fields, new required entries). Must precede description enrichment.

### Task 0a-01: Add `depends_on` to Step 09 milestone schema
- **Addresses**: AUDIT-014
- **File**: `schema/09_impl_plan.schema.json`
- **Change**: Add optional `depends_on` array to milestone items:
  ```json
  "depends_on": {
    "description": "IDs of milestones that must complete before this milestone can begin. Used for dependency ordering and cycle detection.",
    "type": "array",
    "items": { "$ref": "vc:core:atoms#kebabId" },
    "uniqueItems": true
  }
  ```
  Add inside the milestone object `properties` block (near `milestone_id`, `name`, etc.).
- **Test gate**: `pytest tests/integration/test_step_09.py -v && pytest tests/fixtures/step_09/ -v`
- **Dependencies**: None
- **Fixture update**: Update `tests/fixtures/step_09/valid_complete.json` to include a `depends_on` example.

### Task 0a-02: Add `fr_refs` to Step 14 task schema
- **Addresses**: AUDIT-015 (schema portion)
- **File**: `schema/14_roadmap.schema.json`
- **Change**: Add optional `fr_refs` array to task objects (inside `milestones[].tasks[]` items):
  ```json
  "fr_refs": {
    "description": "Functional requirement IDs this task addresses. Enables pairwise completeness checks verifying every milestone FR has at least one implementing task.",
    "type": "array",
    "items": { "$ref": "vc:core:atoms#kebabId" },
    "uniqueItems": true
  }
  ```
- **Test gate**: `pytest tests/integration/test_step_14.py -v`
- **Dependencies**: None
- **Fixture update**: Update `tests/fixtures/step_14/valid_roadmap.json` to include `fr_refs` on at least one task.

### Task 0a-03: Add `in_scope`, `out_of_scope`, `assumptions`, `risks` to charter required array
- **Addresses**: AUDIT-075
- **File**: `schema/00_charter.schema.json`
- **Change**: Modify the `required` array (line 182) from:
  `["problem_statement", "success_metrics", "stakeholders", "user_segments"]`
  to:
  `["problem_statement", "in_scope", "out_of_scope", "assumptions", "risks", "success_metrics", "stakeholders", "user_segments"]`
  These fields already exist in the schema properties with `minItems` constraints. This just makes them required.
- **Test gate**: `pytest tests/fixtures/step_00/ -v && pytest tests/integration/ -k "step_00 or charter" -v`
- **Dependencies**: None
- **Fixture update**: Verify `tests/fixtures/step_00/` fixtures include all newly-required fields. Update any valid fixtures that lack them. Consider adding `tests/fixtures/step_00/invalid_missing_scope.json` for negative testing.
- **BREAKING**: Host repos with charters missing these fields will fail validation. Changelog entry required.

### Task 0a-04: Add `trace` to Step 05 API item required array
- **Addresses**: AUDIT-084
- **File**: `schema/05_interface_contracts.schema.json`
- **Change**: Add `"trace"` to the required array at line 170. Current required: `["api_id", "name", "version", "protocol", "owner", "interface_ref"]`. New: add `"trace"`.
  Verify `trace` property already exists in the API item schema. If not, add:
  ```json
  "trace": {
    "description": "Traceability links connecting this API to upstream functional requirements.",
    "$ref": "vc:core:collections#traceArray"
  }
  ```
- **Test gate**: `pytest tests/integration/test_step_05.py -v && pytest tests/fixtures/step_05/ -v`
- **Dependencies**: None
- **Fixture update**: Update `tests/fixtures/step_05/valid_rest_api.json` to include `trace` if missing. Add `tests/fixtures/step_05/invalid_missing_trace.json`.
- **BREAKING**: Host repos with traceless API specs will fail. Changelog entry required.

### Task 0a-05: Strengthen owner validation via canon or enum
- **Addresses**: AUDIT-086
- **File**: `schema/core/atoms.schema.json`
- **Change**: Replace the owner regex pattern `^[a-z][a-z0-9_-]*$` with an enum constraint listing the 8 canonical owners. At atoms.schema.json line ~38-42, change from pattern-only to:
  ```json
  "owner": {
    "description": "Team or role responsible for this artifact. Must be one of the 8 canonical owner values.",
    "type": "string",
    "enum": ["api", "ui", "system", "ops", "data", "product", "business", "engineering"]
  }
  ```
- **Test gate**: `pytest tests/ -k "owner" -v` and verify no existing fixtures use non-standard owners.
- **Dependencies**: None
- **Decision**: Use enum for correctness. Host repos that need custom owners can override atoms.schema.json.
- **BREAKING**: Existing specs with non-standard owners will fail. Changelog entry required.

---

## Batch 0b: Schema Description Enrichment

Three-tier DEPTH model (Decision 11). Focus on Tier 3 (semantic/LLM-facing) fields first -- those where prompts currently duplicate guidance. Not all 925 descriptions need enrichment; prioritize fields where prompts contain Field-by-Field guidance that will be deleted.

### Task 0b-01: Enrich Step 00 charter schema descriptions
- **Addresses**: AUDIT-071
- **File**: `schema/00_charter.schema.json`
- **Change**: Enrich descriptions for semantic fields:
  - `problem_statement`: Tier 3 -- "Concise description of the problem this project aims to solve. Must identify the affected users/stakeholders, the current pain point, and the business impact. Minimum 20 characters. Avoid solution-language; focus on the problem space."
  - `in_scope`: Tier 2 -- "Items explicitly within the boundaries of this project. Each item should be a concrete deliverable, capability, or integration point. At least 3 required to ensure scope is meaningfully bounded."
  - `out_of_scope`: Tier 2 -- "Items explicitly excluded from this project. Use to prevent scope creep and set stakeholder expectations. At least 3 required."
  - `assumptions`: Tier 2 -- "Assumptions made during project scoping that could affect delivery if invalidated. Each should be falsifiable and monitorable."
  - `risks`: Tier 2 -- "Known risks that could impact project success or timeline. Each should be specific enough to have a mitigation strategy."
  - `success_metrics`: Tier 3 -- enrich the metric item descriptions (metric_id, name, target, baseline, measurement_method, measurement_frequency).
  - `stakeholders`: Tier 2 -- enrich role/needs items.
  - `user_segments`: Tier 3 -- enrich segment_id, description, jobs_to_be_done.
- **Test gate**: `pytest tests/integration/ -k "step_00 or charter" -v`
- **Dependencies**: 0a-03

### Task 0b-02: Enrich Step 01 capabilities schema descriptions
- **Addresses**: AUDIT-071
- **File**: `schema/01_capabilities.schema.json`
- **Change**: Enrich Tier 3 fields: `capability_id`, `name`, `description` (capability description), `goal_id`, `success_metric_refs`. Enrich so LLMs understand quality expectations without prompt Field-by-Field guidance.
- **Test gate**: `pytest tests/integration/ -k "step_01" -v`
- **Dependencies**: None

### Task 0b-03: Enrich Step 04 FR schema descriptions
- **Addresses**: AUDIT-071
- **File**: `schema/04_fr_list.schema.json`
- **Change**: This is the highest-priority schema for enrichment. Enrich:
  - `statement` (Tier 3): "Clear, falsifiable statement of a single system behavior. Must describe WHAT the system does, not HOW. Structure: subject + verb + object + measurable condition. Example: 'The system shall return a 401 Unauthorized response within 200ms when an expired token is presented.' Minimum 20 characters."
  - `acceptance_criteria[].text` (Tier 3): "Testable criterion text that can be objectively verified. Must be specific enough to write an automated test. Avoid subjective terms like 'fast', 'good', 'user-friendly'. Include concrete thresholds, expected behaviors, and boundary conditions."
  - `preconditions` (Tier 2): "Conditions that must hold before this requirement can be exercised. Each should reference a specific system state or prior action."
  - `postconditions` (Tier 2): "Conditions guaranteed after successful fulfillment. Each should describe a verifiable system state change."
  - `rationale` (Tier 2): "Explanation of why this requirement exists. Must trace to a business need, user story, or compliance requirement."
  - `priority` (Tier 1): enrich with decision guidance.
- **Test gate**: `pytest tests/integration/ -k "step_04" -v`
- **Dependencies**: None

### Task 0b-04: Enrich Step 05 interface contracts schema descriptions
- **Addresses**: AUDIT-071
- **File**: `schema/05_interface_contracts.schema.json`
- **Change**: Enrich API item fields: `api_id`, `name`, `protocol`, `endpoints[].path`, `endpoints[].method`, `endpoints[].request_body`, `endpoints[].responses`, `trace`. Focus on Tier 3 for `endpoints` and `responses`.
- **Test gate**: `pytest tests/integration/test_step_05.py -v`
- **Dependencies**: 0a-04

### Task 0b-05: Enrich Step 06 invariants schema descriptions
- **Addresses**: AUDIT-071
- **File**: `schema/06_invariants.schema.json`
- **Change**: Enrich `invariant_id`, `statement`, `language`, `expression`, `owner`, `scope`, `enforcement_point`. Tier 3 for `statement` and `expression`.
- **Test gate**: `pytest tests/integration/ -k "step_06" -v`
- **Dependencies**: None

### Task 0b-06: Enrich Step 07 NFRs schema descriptions
- **Addresses**: AUDIT-071
- **File**: `schema/07_nfrs.schema.json`
- **Change**: Enrich `nfr_id`, `name`, `category`, `target`, `measurement_method`, `measurement_frequency`, `baseline`. Tier 3 for `target` and `measurement_method` -- these are the highest-drift fields per R2-F analysis.
- **Test gate**: `pytest tests/integration/ -k "step_07" -v`
- **Dependencies**: None

### Task 0b-07: Enrich Step 09 impl plan schema descriptions
- **Addresses**: AUDIT-071
- **File**: `schema/09_impl_plan.schema.json`
- **Change**: Enrich milestone fields including new `depends_on`. Enrich `tech_stack` (Tier 2), `milestones[].deliverables` (Tier 3), `milestones[].status` (Tier 1).
- **Test gate**: `pytest tests/integration/ -k "step_09" -v`
- **Dependencies**: 0a-01

### Task 0b-08: Enrich Step 14 roadmap schema descriptions
- **Addresses**: AUDIT-071
- **File**: `schema/14_roadmap.schema.json`
- **Change**: Enrich milestone and task fields including new `fr_refs` on tasks. Enrich `tasks[].acceptance_criteria` (Tier 3), `tasks[].status` (Tier 1), `milestones[].target_date` (Tier 1). Differentiate `dependencyObjectList` description from Step 09's `dependencyList` (AUDIT-057).
- **Test gate**: `pytest tests/integration/test_step_14.py -v`
- **Dependencies**: 0a-02

### Task 0b-09: Enrich Step 16 impl context schema descriptions
- **Addresses**: AUDIT-071, AUDIT-054, AUDIT-055
- **File**: `schema/16_impl_context.schema.json`
- **Change**: (1) Differentiate 14+ `status_ref` descriptions with expected `kind` value or example ID per location (AUDIT-054). (2) Add enum constraint to `emergent_ambiguities[].severity` matching the planning severity enum (AUDIT-055). (3) Enrich Tier 3 fields for evidence, semantic review.
- **Test gate**: `pytest tests/integration/test_step_16.py -v`
- **Dependencies**: None

### Task 0b-10: Enrich core atoms schema descriptions
- **Addresses**: AUDIT-052, AUDIT-071
- **File**: `schema/core/atoms.schema.json`
- **Change**: Add `examples` array to `owner` listing 8 standard owners (AUDIT-052). Enrich `kebabId`, `isoDate`, `semVer` descriptions with format guidance.
- **Test gate**: `pytest tests/unit/core/ -v`
- **Dependencies**: 0a-05

### Task 0b-11: Enrich core collections schema descriptions
- **Addresses**: AUDIT-051, AUDIT-053
- **File**: `schema/core/collections.schema.json`
- **Change**: (1) Add `examples` array to `traceRef.type` listing common values like "derives-from", "implements", "tests" (AUDIT-051). (2) Clarify distinction between `stageName` and `environmentName` in descriptions -- stage = deployment pipeline phase, environment = runtime target (AUDIT-053). Add note that Batch 3 may consolidate.
- **Test gate**: `pytest tests/unit/core/ -v`
- **Dependencies**: None

### Task 0b-12: Enrich Step 02 system sketch schema descriptions
- **Addresses**: AUDIT-066, AUDIT-071
- **File**: `schema/02_system_sketch.schema.json`
- **Change**: Update `connection.schema_ref` description to explain `-tbd` placeholder convention (AUDIT-066). Enrich component and connection field descriptions.
- **Test gate**: `pytest tests/integration/ -k "step_02" -v`
- **Dependencies**: None

### Task 0b-13: Enrich Step 02a delivery baseline schema descriptions
- **Addresses**: AUDIT-071
- **File**: `schema/02a_delivery_baseline.schema.json`
- **Change**: Apply three-tier DEPTH model. Focus on Tier 3 for semantic content fields.
- **Test gate**: `pytest tests/integration/test_step_02a.py -v`
- **Dependencies**: None

### Task 0b-14: Enrich Step 03 glossary schema descriptions
- **Addresses**: AUDIT-071
- **File**: `schema/03_glossary.schema.json`
- **Change**: Apply three-tier DEPTH model. Focus on `term`, `definition`, `domain` (Tier 3).
- **Test gate**: `pytest tests/integration/ -k "step_03" -v`
- **Dependencies**: None

### Task 0b-15: Enrich Step 08 fixtures schema descriptions
- **Addresses**: AUDIT-071
- **File**: `schema/08_fixtures.schema.json`
- **Change**: Apply three-tier DEPTH model. Focus on `targets`, `test_data`, `expected_outcomes` (Tier 3).
- **Test gate**: `pytest tests/integration/ -k "step_08" -v`
- **Dependencies**: None

### Task 0b-16: Enrich Step 10 governance schema descriptions
- **Addresses**: AUDIT-071
- **File**: `schema/10_governance.schema.json`
- **Change**: Apply three-tier DEPTH model. Focus on `pr_rules`, `review_checklist` (Tier 2).
- **Test gate**: `pytest tests/integration/test_step_10.py -v`
- **Dependencies**: None

### Task 0b-17: Enrich Step 11 red team schema descriptions
- **Addresses**: AUDIT-071
- **File**: `schema/11_redteam.schema.json`
- **Change**: Apply three-tier DEPTH model. Focus on `threat_id`, `target_ids`, `mitigations` (Tier 3).
- **Test gate**: `pytest tests/integration/ -k "step_11" -v`
- **Dependencies**: None

### Task 0b-18: Enrich Step 12 CI gates schema descriptions
- **Addresses**: AUDIT-071
- **File**: `schema/12_ci_gates.schema.json`
- **Change**: Apply three-tier DEPTH model. Focus on `jobs`, `dependencies`, `triggers` (Tier 2).
- **Test gate**: `pytest tests/integration/ -k "step_12" -v`
- **Dependencies**: None

### Task 0b-19: Enrich Step 13 extension generator schema descriptions
- **Addresses**: AUDIT-071
- **File**: `schema/13_extension_generator.schema.json`
- **Change**: Apply three-tier DEPTH model. Focus on `required_schema_sections` (Tier 2).
- **Test gate**: `pytest tests/ -k "step_13" -v`
- **Dependencies**: None

### Task 0b-20: Enrich Step 13a completeness assessment schema descriptions
- **Addresses**: AUDIT-071
- **File**: `schema/13a_completeness_assessment.schema.json`
- **Change**: Apply three-tier DEPTH model. Focus on scoring dimensions (Tier 3, will be redesigned in Batch 5).
- **Test gate**: `pytest tests/integration/ -k "step_13a" -v`
- **Dependencies**: None

### Task 0b-21: Enrich Step 15 scaffold schema descriptions
- **Addresses**: AUDIT-071
- **File**: `schema/15_scaffold.schema.json`
- **Change**: Apply three-tier DEPTH model. Focus on `files`, `method`, `interface_ref` (Tier 2).
- **Test gate**: `pytest tests/integration/ -k "step_15" -v`
- **Dependencies**: None

### Task 0b-22: Enrich seed_manifest schema descriptions
- **Addresses**: AUDIT-071
- **File**: `schema/seed_manifest.schema.json`
- **Change**: Enrich `global_seed_order`, `step_requirements`, and remaining fields with Tier 2 descriptions.
- **Test gate**: `pytest tests/ -k "seed_manifest" -v`
- **Dependencies**: None

---

## Batch 0c: Quick Reference Section Deletion

Per Decision 1: DELETE Quick Reference sections from all prompts. Schema descriptions (enriched in 0b) are the sole owner of field semantics.

### Task 0c-01: Delete Quick Reference sections from all 17 prompts
- **Addresses**: AUDIT-008, AUDIT-041, AUDIT-042, AUDIT-043
- **Files**: All 17 prompt files with Quick Reference sections (one task per file, but grouped here for clarity):
  - `prompts/prompt_00_project_charter.md`
  - `prompts/prompt_01_capabilities.md`
  - `prompts/prompt_02_system_sketch.md`
  - `prompts/prompt_02a_delivery_baseline.md`
  - `prompts/prompt_03_glossary.md`
  - `prompts/prompt_04_functional_requirements.md`
  - `prompts/prompt_05_interface_contracts.md`
  - `prompts/prompt_06_invariants.md`
  - `prompts/prompt_07_nfrs.md`
  - `prompts/prompt_08_fixtures.md`
  - `prompts/prompt_09_impl_plan.md`
  - `prompts/prompt_10_governance.md`
  - `prompts/prompt_11_redteam.md`
  - `prompts/prompt_12_ci_gates.md`
  - `prompts/prompt_13a_completeness_assessment.md`
  - `prompts/prompt_15_scaffold.md`
  - `prompts/prompt_16_impl_context.md`
- **Change**: For each file, find the `## Quick Reference` (or `### Quick Reference`) heading and delete everything from that heading to the next heading of equal or higher level. This removes ~500 LOC of schema-duplicated content across all prompts.
- **Test gate**: `pytest tests/unit/generation/test_prompt_contracts.py -v && pytest tests/unit/generation/test_prompt_schema_sync.py -v`
- **Dependencies**: 0b (schema descriptions must be enriched BEFORE deleting prompt field guidance)
- **Note**: This is 17 file edits. For P5 execution, this MUST be split into 17 sub-tasks (0c-01a through 0c-01q), each modifying one file. All run in parallel.

---

## Batch 1: Config Cleanup + Codebase Bugs

These have NO dependencies on Batch 0 and can be executed in parallel with Batch 0.

### Task 1-01: Remove `docs_policy` from seed_manifest schema and data
- **Addresses**: AUDIT-017
- **File**: `schema/seed_manifest.schema.json`
- **Change**: Remove the entire `docs_policy` property definition (~55 lines). Keep `doc_paths` if it exists as a standalone field; otherwise extract it to top-level.
- **Test gate**: `pytest tests/ -k "seed_manifest" -v`
- **Dependencies**: None
- **Follow-up files**: `spec/common/seed_manifest.json` (remove `docs_policy` block), `tests/fixtures/seed_manifest/valid_minimal.json`, `tests/fixtures/seed_manifest/invalid_missing_required.json`, `tools/specdev_tools/validation/validators/step_16.py` (update `doc_paths` reference at line ~180).
- **BREAKING**: Changelog entry required.

### Task 1-02: Remove `docs_policy` from seed_manifest data file
- **Addresses**: AUDIT-017
- **File**: `spec/common/seed_manifest.json`
- **Change**: Remove the `docs_policy` JSON block (~22 lines). Extract `doc_paths` to top-level if needed by step_16.py consumer.
- **Test gate**: `./tools/run_specdev.sh seed-lint spec --repo-root .`
- **Dependencies**: 1-01

### Task 1-03: Update seed_manifest test fixtures for docs_policy removal
- **Addresses**: AUDIT-017
- **File**: `tests/fixtures/seed_manifest/valid_minimal.json` and `tests/fixtures/seed_manifest/invalid_missing_required.json`
- **Change**: Remove `docs_policy` from fixture files. Add `doc_paths` at top level if step_16 requires it.
- **Test gate**: `pytest tests/ -k "seed_manifest" -v`
- **Dependencies**: 1-01

### Task 1-04: Derive `allowed_upstream_dependencies` at runtime
- **Addresses**: AUDIT-023
- **File**: `tools/specdev_tools/core/registry.py` (or create `tools/specdev_tools/core/step_order.py`)
- **Change**: Add `derive_allowed_upstream(step_id: str, steps: list[str]) -> list[str]` function that returns all steps preceding `step_id` in the ordered `steps` array. Under strict_waterfall, this is simply `steps[:steps.index(step_id)]`.
- **Test gate**: `pytest tests/unit/core/ -v` (add test for `derive_allowed_upstream`)
- **Dependencies**: None

### Task 1-05: Migrate 5 consumers of `allowed_upstream_dependencies` to derived function
- **Addresses**: AUDIT-023
- **Files**: 5 consumer files -- each must be updated atomically:
  1. `tools/specdev_tools/cli.py` -- replace `step_order["allowed_upstream_dependencies"]` lookups
  2. `tools/specdev_tools/validation/hallucination_lint.py` -- replace
  3. `tools/specdev_tools/validation/extraction_intent_check.py` -- replace
  4. `tools/specdev_tools/validation/dependency_order_lint.py` -- replace
  5. `tools/specdev_tools/validation/dag_lint.py` -- replace
- **Change**: Import and call `derive_allowed_upstream()` instead of reading from JSON. After ALL consumers migrated, delete `allowed_upstream_dependencies` from `tools/step_order.json` (~275 lines). Update `schema/step_order.schema.json` to remove the field.
- **Test gate**: `pytest tests/ -v` (full suite -- this is a cross-cutting change)
- **Dependencies**: 1-04
- **Note**: This is technically 7 files. Execute consumer migrations first, then JSON deletion. Consider splitting into sub-tasks per consumer.

### Task 1-06: Delete `nested_order` from seed_manifest
- **Addresses**: AUDIT-035
- **Files**: `spec/common/seed_manifest.json`, `schema/seed_manifest.schema.json`
- **Change**: Remove `nested_order` block (~9 lines) from data file. Remove from schema definition. Verify no consumers reference it (search codebase for `nested_order`).
- **Test gate**: `pytest tests/ -k "seed" -v`
- **Dependencies**: None

### Task 1-07: Fix Step 16c semantic_review enforcement bug
- **Addresses**: AUDIT-069
- **File**: `tools/specdev_tools/validation/validators/step_16c.py`
- **Change**: After the verdict check (line 31), add enforcement for verified verdict:
  ```python
  # When verdict is "verified", semantic_review with fr_coverage is REQUIRED
  if verdict == "verified":
      if not isinstance(semantic_review, dict):
          errors.append(make_error("E520", "Step 16c: verdict is 'verified' but 'review.semantic_review' is missing"))
      elif not semantic_review.get("fr_coverage"):
          errors.append(make_error("E520", "Step 16c: verdict is 'verified' but 'review.semantic_review.fr_coverage' is empty"))
  ```
  Move the `semantic_review = review.get("semantic_review")` line before this block.
- **Test gate**: `pytest tests/integration/test_step_16.py -v`
- **Dependencies**: None
- **Fixture update**: Add `tests/fixtures/step_16/invalid_verified_no_semantic_review.json` fixture.

### Task 1-08: Fix verdict enum mismatch between prompt and validator
- **Addresses**: AUDIT-076
- **File**: `prompts/prompt_16c_impl_reviewer.md`
- **Change**: Find the verdict enum reference (line ~131) that says "verified/deferred/rejected" and change to "verified/needs_work/blocked/deferred" to match the validator's `VALID_VERDICTS` set. The validator's set is more granular and correct.
- **Test gate**: `pytest tests/unit/generation/test_prompt_contracts.py -v`
- **Dependencies**: None

### Task 1-09: Fix E304 active milestone filtering bug
- **Addresses**: AUDIT-088
- **File**: `tools/specdev_tools/validation/validators/step_16.py`
- **Change**: At lines 313-318, the E304 check collects task IDs from ALL milestones. Change to filter by the current `milestone_ref`:
  ```python
  # Get milestone_ref from the artifact
  milestone_ref = data.get("milestone_ref", "")
  roadmap_task_ids = set()
  for milestone in roadmap_data.get("milestones", []):
      mid = milestone.get("milestone_id", "")
      mstatus = milestone.get("status", "")
      if milestone_ref:
          # If milestone_ref is set, only include tasks from that milestone
          if mid != milestone_ref:
              continue
      else:
          # If milestone_ref is absent (first Trinity cycle), include only
          # milestones that are not yet done (active/in-progress)
          if mstatus in ("done", "completed"):
              continue
      for task in milestone.get("tasks", []):
          tid = task.get("task_id")
          if tid:
              roadmap_task_ids.add(tid)
  ```
- **Test gate**: `pytest tests/integration/test_step_16.py -v`
- **Dependencies**: None
- **Fixture update**: Add/update `tests/fixtures/step_16/e304_roadmap/` fixtures to test milestone filtering.

### Task 1-10: Update downstream_consumers for Step 02a
- **Addresses**: AUDIT-082
- **File**: `tools/step_order.json`
- **Change**: Update `downstream_consumers["02a"]` from `["12"]` to reflect actual consumption. Based on prompt Extraction Intent analysis, Steps 04-07 reference 02a. Update to: `["04", "05", "06", "07", "12"]`. Alternatively, if 02a is not truly consumed (just referenced), remove 02a from those prompts' Extraction Intent instead.
- **Test gate**: `./tools/run_specdev.sh dag-lint --repo-root .`
- **Dependencies**: None

---

## Batch 2: shared_expectations.md Extraction

Depends on Batch 0 (schema enrichment complete, Quick Reference deleted). This batch creates the shared_expectations.md redesign and begins boilerplate extraction from prompts.

### Task 2-01: Redesign shared_expectations.md
- **Addresses**: AUDIT-002, AUDIT-006, AUDIT-007, AUDIT-026, AUDIT-091, AUDIT-101
- **File**: `docs/prompts/shared_expectations.md`
- **Change**: Replace current 51-LOC document with ~82-LOC redesign per R2-D Section 4. Include these 11 sections:
  1. **Path Variables** -- the 4-row table (from all 22 prompts)
  2. **Schema Authority** -- "The schema is the sole owner of all field definitions..." (from all 22 prompts)
  3. **Canonical Registry + Binding** -- adopt Step 12's expanded version with deprecated-check rules (AUDIT-007)
  4. **Hardening Protocol** -- "Output Hardening Protocol" standardized version
  5. **Default Role + Task** -- generic role/task template (prompts override with step-specific)
  6. **Output Rules** -- "one JSON document", "do not return fenced JSON", determinism rule
  7. **Seed Order** -- "Read seed_manifest.json first; follow global_seed_order"
  8. **Self-Audit Gate Protocol** -- threshold only: "If ANY gating item below cannot be satisfied, enter Clarify mode" (Decision 10)
  9. **Step-Order Policy** -- "strict forward-only waterfall; upstream change requires full replay"
  10. **Tool Execution** -- validate command template
  11. **Conflict Resolution Protocol** -- NEW per Decision 2: "When two upstream artifacts contradict: (1) Identify explicitly. (2) Apply precedence: seed > charter > capabilities > architecture > delivery > glossary. (3) If same-level, add Gap Question. (4) Never silently resolve."
  12. **Context Ledger** -- "Before emitting output, build a private synthesis ledger" (AUDIT-101)
  13. **Cross-Step Relationships** -- "Cross-step relationships are derivable from step_order.json DAG" (Decision 2)
- **Test gate**: Manual review -- file exists, ~80-120 LOC, 11-13 sections.
- **Dependencies**: 0b, 0c

### Task 2-02: Add shared_expectations inheritance reference to all 22 prompts
- **Addresses**: AUDIT-006, AUDIT-026
- **Files**: All 22 `prompts/prompt_*.md` files
- **Change**: Add at the top of each prompt (after the first `#` heading):
  ```markdown
  > **Inherits**: `$TOOLKIT_ROOT/docs/prompts/shared_expectations.md` -- all directives apply unless explicitly overridden below.
  ```
  For the 14 prompts that don't currently reference shared_expectations, this is a new addition. For the 8 that already reference it inline, update the reference to the new location/format.
- **Test gate**: `pytest tests/unit/generation/test_prompt_contracts.py -v`
- **Dependencies**: 2-01
- **Note**: 22 file edits. For P5 execution, MUST be split into 22 sub-tasks (one per file). All run in parallel after 2-01.

### Task 2-03: Delete extracted boilerplate from all 22 prompts
- **Addresses**: AUDIT-006, AUDIT-018
- **Files**: All 22 `prompts/prompt_*.md` files
- **Change**: Delete the following sections that are now centralized in shared_expectations.md:
  - `## Path Variables` table (~5 LOC per prompt)
  - `## Schema Authority` paragraph (~4 LOC per prompt)
  - `## Tool Execution` block (~4 LOC per prompt)
  - Generic portions of `# Role` and `# Task` that match the default (keep step-specific overrides)
  - `## Seed Order & Mandatory Sources` (merge into Extraction Intent per AUDIT-018, for Steps 00-04)
  - `## Context To Ingest` (merge into Extraction Intent per AUDIT-018, for Steps 00-04)
  - Canonical Registry boilerplate (for 21 prompts that have the short version; Step 12's expanded version is now in shared_expectations)
  - Output Rules generic items
  - Hardening Protocol generic items
  Estimated ~1,000 LOC removed across 22 files.
- **Test gate**: `pytest tests/unit/generation/test_prompt_contracts.py -v && pytest tests/unit/generation/test_prompt_schema_sync.py -v`
- **Dependencies**: 2-01, 2-02
- **Note**: LARGE task. For P5 execution, MUST be split into 22 sub-tasks (one per prompt file). Each modifies ONE file. All run in parallel.

### Task 2-04: Delete Field-by-Field schema-duplicated content from prompts
- **Addresses**: AUDIT-008 (prompt portion)
- **Files**: 18 prompt files with Field-by-Field sections: `prompt_00_project_charter.md`, `prompt_01_capabilities.md`, `prompt_02_system_sketch.md`, `prompt_02a_delivery_baseline.md`, `prompt_03_glossary.md`, `prompt_04_functional_requirements.md`, `prompt_05_interface_contracts.md`, `prompt_06_invariants.md`, `prompt_07_nfrs.md`, `prompt_08_fixtures.md`, `prompt_09_impl_plan.md`, `prompt_10_governance.md`, `prompt_11_redteam.md`, `prompt_12_ci_gates.md`, `prompt_13_extension_generator.md`, `prompt_13a_completeness_assessment.md`, `prompt_14_roadmap.md`, `prompt_15_scaffold.md`
- **Change**: Delete `## Field-by-Field` or equivalent sections that restate schema descriptions verbatim. After Batch 0b schema enrichment, these are redundant. Keep any step-specific reasoning guidance that goes beyond schema descriptions (e.g., "derive this field by cross-referencing Step 04 FRs with Step 05 APIs").
- **Test gate**: `pytest tests/unit/generation/test_prompt_contracts.py -v`
- **Dependencies**: 0b, 0c, 2-01
- **Note**: Split per prompt file. Careful review needed to distinguish schema-dup from step-specific reasoning.

### Task 2-05: Merge seed triple redundancy in Steps 00-04
- **Addresses**: AUDIT-018
- **Files**: `prompts/prompt_00_project_charter.md`, `prompts/prompt_01_capabilities.md`, `prompts/prompt_02_system_sketch.md`, `prompts/prompt_03_glossary.md`, `prompts/prompt_04_functional_requirements.md`
- **Change**: For each of Steps 00-04, merge "Seed Order & Mandatory Sources", "Context To Ingest", and "Extraction Intent" into a single "Extraction Intent" section. The seed ordering info moves to shared_expectations; the context-to-ingest details fold into extraction intent entries.
- **Test gate**: `pytest tests/unit/generation/test_prompt_contracts.py -v`
- **Dependencies**: 2-01
- **Note**: Split per prompt file (5 sub-tasks).

---

## Batch 3: Glossary -> Canon Pipeline

Independent of Batch 2 (per master findings). Depends on Batch 0 for schema enrichment. Can run in parallel with Batch 2.

### Task 3-01: Document canon namespace convention
- **Addresses**: AUDIT-074
- **File**: `canon/README.md` (new file, or add to existing docs)
- **Change**: Document namespace convention:
  - `cn:core:` -- toolkit-mechanical canons (pre-populated, maintained by toolkit team)
  - `cn:project:` -- pipeline-populated canons from Step 03 glossary terms (populated during spec authoring)
  - `cn:starter:` -- example/demo canons (auth-domain, etc.)
  Document in a way that's discoverable by both humans and AI agents.
- **Test gate**: File exists with documented convention.
- **Dependencies**: None

### Task 3-02: Move auth-domain-specific canon entries to examples
- **Addresses**: AUDIT-096
- **File**: `canon/manifest.json`
- **Change**: Identify 18 auth-domain-specific entries (capability:authenticate, entity:user, entity:session, etc.) and either:
  (a) Move them to `canon/examples/auth_demo.json` (new file), or
  (b) Mark them with a `"starter_kit": true` flag, or
  (c) Remove them from manifest.json and document them in canon/README.md as starter examples.
  Preferred: option (a).
- **Test gate**: `pytest tests/unit/canonical/ -v`
- **Dependencies**: 3-01

### Task 3-03: Build `specdev canon-accept` CLI command
- **Addresses**: AUDIT-073, AUDIT-100
- **Files**: `tools/specdev_tools/canonical/accept.py` (new file), `tools/specdev_tools/cli.py` (add subcommand)
- **Change**: Build CLI command that reads `canonical_proposals` from a spec file and promotes them to `canon/manifest.json`:
  ```
  specdev canon-accept --from spec/03_glossary.json --namespace cn:project
  ```
  Implementation: (1) Load spec file, extract `canonical_proposals` array. (2) For each proposal, generate a canon entry with `cn:project:` namespace. (3) Append to manifest.json (or separate project canon file). (4) Report additions.
  The `canonicalProposal` schema in `step_base.schema.json` already has all needed fields (temp_id, kind, proposed_label, definition, source_field, suggested_namespace).
- **Test gate**: Add `tests/unit/canonical/test_canon_accept.py` with unit tests for the accept flow.
- **Dependencies**: 3-01

### Task 3-04: Redesign Step 03 prompt as canon population step
- **Addresses**: AUDIT-072
- **File**: `prompts/prompt_03_glossary.md`
- **Change**: Per Decision 6: Update Step 03 prompt to instruct LLM to:
  1. Define glossary terms as before (backward compatible)
  2. Additionally, emit `canonical_proposals` in the output JSON for each term that should become a project canon
  3. Add guidance: "Every glossary term should be proposed as a `cn:project:` canon entry. After emission, run `specdev canon-accept --from spec/03_glossary.json` to promote proposals to the registry."
  4. Add Coverage Closure item: "Every term in `terms` has a corresponding entry in `canonical_proposals`"
- **Test gate**: `pytest tests/unit/generation/test_prompt_contracts.py -v`
- **Dependencies**: 3-01, 3-03

### Task 3-05: Consolidate stage/environment triple maintenance
- **Addresses**: AUDIT-095, AUDIT-053 (subsumes Batch 0b description-only fix)
- **Files**: `canon/kinds/stage.json`, `canon/kinds/environment.json`, `schema/core/collections.schema.json`
- **Change**: Designate canon as the single source of truth for stage and environment values. In schema, either:
  (a) Replace inline enums with `$ref` to canon, or
  (b) Add `$comment` noting "authoritative values in canon/kinds/stage.json" and keep enum for validation.
  Preferred: (b) for now -- schema enum provides compile-time validation, canon provides documentation.
  Differentiate the two concepts clearly: stage = pipeline phase (build, test, deploy), environment = runtime target (dev, ci, staging, prod). If they truly represent the same concept, merge into one kind.
- **Test gate**: `pytest tests/unit/canonical/ -v`
- **Dependencies**: None

---

## Batch 4: Prompt Synthesis Enrichment

Depends on Batch 0 (schemas enriched, Quick Reference deleted) and Batch 2 (shared_expectations extracted, boilerplate removed). This is the largest batch -- it enriches the step-specific reasoning content of all 22 prompts.

### Task 4-01: Add synthesis reasoning framework to Step 04 (FRs)
- **Addresses**: AUDIT-001, AUDIT-003, AUDIT-027, AUDIT-029
- **File**: `prompts/prompt_04_functional_requirements.md`
- **Change**: Replace generic "Synthesize -> Clarify -> Emit" with step-specific named phases:
  "Enumerate -> Decompose -> Falsify -> Trace -> Emit"
  Add:
  1. **Implicit Requirements Discovery Checklist** (AUDIT-003): error handling, authorization, input validation, audit logging, idempotency, pagination, concurrency, rate limiting, data lifecycle.
  2. **Granularity Heuristics** (AUDIT-027): "One FR = one behavior = one subject + one verb + one measurable outcome. Split if: multiple subjects, multiple conditions, or 'and' joins distinct behaviors."
  3. **Weak-vs-Strong Examples** table (AUDIT-029): 5 rows showing weak FR statement vs strong FR statement.
  4. **Forbidden Actions** section: "Do not: combine multiple behaviors, use subjective language, reference implementation details."
- **Test gate**: `pytest tests/unit/generation/test_prompt_contracts.py -v`
- **Dependencies**: 0c, 2-03

### Task 4-02: Add synthesis reasoning framework to Step 05 (APIs)
- **Addresses**: AUDIT-001, AUDIT-003, AUDIT-038
- **File**: `prompts/prompt_05_interface_contracts.md`
- **Change**: Add:
  1. Step-specific phases: "Map -> Design -> Validate -> Trace -> Emit"
  2. **REST Design Heuristics** (AUDIT-038): resource naming, URL structure conventions, pagination patterns, error response schema, versioning strategy.
  3. **Implicit API Discovery**: every FR with external-observable behavior -> API; error handling FRs -> error response contracts; auth FRs -> auth endpoints.
  4. **Weak-vs-Strong Examples** table (AUDIT-029).
  5. **Extraction Mandate** (AUDIT-019): "Every FR with observable external behavior must map to >= 1 API."
- **Test gate**: `pytest tests/unit/generation/test_prompt_contracts.py -v`
- **Dependencies**: 0c, 2-03

### Task 4-03: Add synthesis reasoning framework to Step 06 (Invariants)
- **Addresses**: AUDIT-001, AUDIT-003, AUDIT-039, AUDIT-083
- **File**: `prompts/prompt_06_invariants.md`
- **Change**: Add:
  1. Step-specific phases: "Discover -> Formalize -> Verify -> Trace -> Emit"
  2. **Invariant Discovery Checklist** (AUDIT-039): state transition rules, uniqueness constraints, referential integrity, business rules, temporal ordering, capacity limits, authorization boundaries.
  3. **Weak-vs-Strong Examples** table (AUDIT-029).
  4. Fix glossary lifecycle references (AUDIT-083): replace "entities with lifecycle stages defined in the glossary" with "entity state fields described in FR preconditions/postconditions". Rewrite lines 50, 56, 72 to derive state transition invariants from FRs.
- **Test gate**: `pytest tests/unit/generation/test_prompt_contracts.py -v`
- **Dependencies**: 0c, 2-03

### Task 4-04: Add synthesis reasoning framework to Step 07 (NFRs)
- **Addresses**: AUDIT-001, AUDIT-027
- **File**: `prompts/prompt_07_nfrs.md`
- **Change**: Add:
  1. Step-specific phases: "Categorize -> Quantify -> Baseline -> Trace -> Emit"
  2. **Granularity Heuristics** (AUDIT-027): "One NFR = one measurable property + one target + one measurement method."
  3. **Weak-vs-Strong Examples** table (AUDIT-029): especially for `target` and `measurement_method` fields.
  4. Fix Output Contract example using "automated monitoring" (AUDIT-040 prompt portion).
- **Test gate**: `pytest tests/unit/generation/test_prompt_contracts.py -v`
- **Dependencies**: 0c, 2-03

### Task 4-05: Add synthesis reasoning to Step 08 (Fixtures)
- **Addresses**: AUDIT-001
- **File**: `prompts/prompt_08_fixtures.md`
- **Change**: Add:
  1. Step-specific phases: "Map -> Generate -> Validate -> Emit"
  2. **Weak-vs-Strong Examples** table (AUDIT-029).
  3. **Extraction Mandate** (AUDIT-019): "Every high-priority FR must have >= 1 fixture."
- **Test gate**: `pytest tests/unit/generation/test_prompt_contracts.py -v`
- **Dependencies**: 0c, 2-03

### Task 4-06: Add synthesis reasoning to Step 09 (Impl Plan)
- **Addresses**: AUDIT-001
- **File**: `prompts/prompt_09_impl_plan.md`
- **Change**: Add:
  1. Step-specific phases: "Scope -> Sequence -> Resource -> Trace -> Emit"
  2. **Extraction Mandate** (AUDIT-019): "Every capability must appear in >= 1 milestone deliverable."
  3. Reference new `depends_on` field for milestone ordering.
- **Test gate**: `pytest tests/unit/generation/test_prompt_contracts.py -v`
- **Dependencies**: 0c, 2-03

### Task 4-07: Enrich Steps 00-03 prompts with synthesis reasoning
- **Addresses**: AUDIT-001
- **Files**: `prompts/prompt_00_project_charter.md`, `prompts/prompt_01_capabilities.md`, `prompts/prompt_02_system_sketch.md`, `prompts/prompt_03_glossary.md`
- **Change**: For each:
  - Step 00: "Extract -> Scope -> Validate -> Emit" phases. Expand seed_tech_stack extraction intent (AUDIT-079).
  - Step 01: "Discover -> Cross-Cut -> Trace -> Emit" phases. Add Cross-Cutting Capability Checklist (AUDIT-081). Add JTBD coverage check to Coverage Closure (AUDIT-080).
  - Step 02: "Decompose -> Connect -> Verify -> Emit" phases.
  - Step 03: Already updated in Batch 3, minimal changes here.
- **Test gate**: `pytest tests/unit/generation/test_prompt_contracts.py -v`
- **Dependencies**: 0c, 2-03
- **Note**: 4 file edits. For P5 execution, MUST be split into 4 sub-tasks (one per file).

### Task 4-08: Enrich Steps 10-12 prompts with synthesis reasoning
- **Addresses**: AUDIT-001
- **Files**: `prompts/prompt_10_governance.md`, `prompts/prompt_11_redteam.md`, `prompts/prompt_12_ci_gates.md`
- **Change**: Add step-specific reasoning phases to each. Step 11 already has good examples; add to 10, 12.
- **Test gate**: `pytest tests/unit/generation/test_prompt_contracts.py -v`
- **Dependencies**: 0c, 2-03
- **Note**: 3 file edits. For P5 execution, MUST be split into 3 sub-tasks (one per file).

### Task 4-09: Add specialized roles to 14 generic-role prompts
- **Addresses**: AUDIT-028
- **Files**: 14 prompts using "senior specification author and validator"
- **Change**: Replace generic role with step-specific role priming. Examples:
  - Step 00: "senior product strategist and scope analyst"
  - Step 04: "senior requirements engineer specializing in falsifiable behavioral specifications"
  - Step 05: "senior API architect with REST/HTTP expertise"
  - Step 06: "formal methods analyst specializing in system invariants"
  - Step 07: "performance engineer and SLA analyst"
  - Step 08: "test architect specializing in fixture design"
  - Step 09: "technical program manager and delivery planner"
  Default role stays in shared_expectations; prompts override.
- **Test gate**: `pytest tests/unit/generation/test_prompt_contracts.py -v`
- **Dependencies**: 2-01 (default role in shared_expectations)
- **Note**: 14 file edits. For P5 execution, MUST be split into 14 sub-tasks (one per file). All run in parallel after 2-01.

### Task 4-10: Add reasoning items to Coverage Closure sections
- **Addresses**: AUDIT-030
- **Files**: All 22 prompts (Coverage Closure sections)
- **Change**: Add 2-3 step-specific reasoning verification items to each prompt's Coverage Closure body. Examples:
  - Step 04: "Every FR statement is falsifiable (has a test that could prove it wrong)"; "No two FRs describe overlapping behaviors"
  - Step 05: "Every endpoint has at least one error response defined"; "Resource naming is consistent across all APIs"
  - Step 07: "Every target has a baseline to measure against"; "No NFR uses subjective language"
- **Test gate**: `pytest tests/unit/generation/test_prompt_contracts.py -v`
- **Dependencies**: 2-03
- **Note**: 22 file edits. For P5 execution, MUST be split into 22 sub-tasks. All run in parallel.

### Task 4-11: Add extraction intent priority grouping to late-stage prompts
- **Addresses**: AUDIT-031
- **Files**: `prompts/prompt_12_ci_gates.md`, `prompts/prompt_14_roadmap.md`, `prompts/prompt_15_scaffold.md`, `prompts/prompt_16_impl_context.md`, `prompts/prompt_16a_impl_planner.md`, `prompts/prompt_16b_impl_coder.md`, `prompts/prompt_16c_impl_reviewer.md`
- **Change**: Group extraction intents into "Primary Sources" (directly consumed) and "Reference Sources" (context only). Example for Step 14:
  - Primary: Step 09 (milestones), Step 04 (FRs), Step 01 (capabilities)
  - Reference: Steps 05-08 (validation context), Steps 10-13 (governance context)
- **Test gate**: `pytest tests/unit/generation/test_prompt_contracts.py -v`
- **Dependencies**: 2-03, 2-05
- **Note**: 7 file edits. Split per file.

### Task 4-12: Add semantic drift prevention guidance
- **Addresses**: AUDIT-016
- **Files**: `prompts/prompt_05_interface_contracts.md`, `prompts/prompt_06_invariants.md`, `prompts/prompt_07_nfrs.md`
- **Change**: Per Decision 5 (no NL tooling): Add prompt guidance: "When tracing to an upstream FR, use the exact FR statement text in the trace `note` field. The FR ID and its `statement` must appear verbatim in the trace note. Do not paraphrase."
- **Test gate**: `pytest tests/unit/generation/test_prompt_contracts.py -v`
- **Dependencies**: 2-03

### Task 4-13: Fix Output Contract examples in prompts
- **Addresses**: AUDIT-040, AUDIT-044, AUDIT-056, AUDIT-062
- **Files**: Multiple prompts with Output Contract issues:
  - `prompts/prompt_07_nfrs.md`: fix "automated monitoring" example
  - `prompts/prompt_06_invariants.md`: fix `language: "text"` example
  - `prompts/prompt_01_capabilities.md`: fix example
  - `prompts/prompt_16_impl_context.md`: add `"canonical_refs_used": []` (AUDIT-044)
  - `prompts/prompt_00_project_charter.md`: add `in_scope`/`out_of_scope` to Output Contract (AUDIT-056)
  - All: standardize `$schema` inclusion (AUDIT-062)
- **Change**: Fix each Output Contract to comply with current schema constraints. Reduce to minimal valid examples (15-25 LOC max).
- **Test gate**: `pytest tests/unit/generation/test_prompt_contracts.py -v && pytest tests/unit/generation/test_prompt_schema_sync.py -v`
- **Dependencies**: 0a, 0b
- **Note**: Split into sub-tasks per file.

### Task 4-14: Add acceptance criteria relationship guidance
- **Addresses**: AUDIT-085
- **File**: `prompts/prompt_14_roadmap.md`
- **Change**: Add guidance explaining relationship between FR acceptance_criteria (Step 04) and task acceptance_criteria (Step 14): "Task acceptance_criteria REFINE FR acceptance_criteria -- they break high-level criteria into implementation-verifiable checks. They must not contradict FR criteria."
- **Test gate**: `pytest tests/unit/generation/test_prompt_contracts.py -v`
- **Dependencies**: 2-03

### Task 4-15: Add cross-artifact consistency checks and misc prompt fixes
- **Addresses**: AUDIT-058, AUDIT-092, AUDIT-097
- **Files**: Multiple prompts
- **Change**:
  - AUDIT-058: Add "Cross-Artifact Consistency" check to Steps 04-08 Coverage Closure: "No ID referenced by this step conflicts with the same ID in a sibling step."
  - AUDIT-092: Update Step 04 gate item from ">=1 acceptance criterion" to ">=2 acceptance criteria" to match schema `minItems: 2`.
  - AUDIT-097: Add to Step 14 prompt: "Step 14 is authoritative for execution-level migration_plan and dependencies. Step 09 provides the design-level version."
- **Test gate**: `pytest tests/unit/generation/test_prompt_contracts.py -v`
- **Dependencies**: 2-03

---

## Batch 5: Pairwise Completeness + Step 13a Redesign

Depends on Batch 4 (prompts have extraction mandates that complement these validators).

### Task 5-01: Implement capability -> FR pairwise completeness check
- **Addresses**: AUDIT-067 (transition 1)
- **File**: `tools/specdev_tools/validation/traceability_closure.py`
- **Change**: Add W568 UNCOVERED_CAPABILITY warning: for each capability in Step 01, verify at least one FR in Step 04 traces to it. Load both spec files, extract capability IDs, check FR trace links. (Note: W561 was already occupied by UNCOVERED_FR; W568 is the correct code as implemented.)
- **Test gate**: `pytest tests/unit/validation/ -k "traceability" -v`
- **Dependencies**: None

### Task 5-02: Implement FR -> API pairwise completeness check
- **Addresses**: AUDIT-013, AUDIT-067 (transition 2)
- **File**: `tools/specdev_tools/validation/traceability_closure.py`
- **Change**: Add W564 UNCOVERED_FR_API warning: for each FR with externally-observable behavior, verify at least one API in Step 05 traces to it.
- **Test gate**: `pytest tests/unit/validation/ -k "traceability" -v`
- **Dependencies**: None

### Task 5-03: Implement FR -> fixture and FR -> milestone completeness checks
- **Addresses**: AUDIT-067 (transitions 3, 4)
- **File**: `tools/specdev_tools/validation/traceability_closure.py`
- **Change**: Add W565 UNCOVERED_FR_FIXTURE and W566 UNCOVERED_FR_MILESTONE warnings.
- **Test gate**: `pytest tests/unit/validation/ -k "traceability" -v`
- **Dependencies**: None

### Task 5-04: Implement milestone -> task completeness check
- **Addresses**: AUDIT-005, AUDIT-067 (transition 5)
- **File**: `tools/specdev_tools/validation/traceability_closure.py`
- **Change**: Add W567 INCOMPLETE_MILESTONE_DECOMPOSITION warning: for each Step 14 milestone, load `source_milestones` from Step 09, collect all deliverable IDs, verify each appears in Step 14 tasks. Also check that every FR in `milestone.fr_refs` is referenced by at least one task's `fr_refs`.
- **Test gate**: `pytest tests/unit/validation/ -k "traceability" -v`
- **Dependencies**: 0a-02 (Step 14 tasks need `fr_refs` field)

### Task 5-05: Implement Step 16c FR coverage completeness check
- **Addresses**: AUDIT-004
- **File**: `tools/specdev_tools/validation/validators/step_16c.py`
- **Change**: When verdict == "verified", verify that `fr_coverage` entries cover all `fr_refs` from the corresponding Step 14 milestone. Load the roadmap, find the active milestone, compare FR sets.
- **Test gate**: `pytest tests/integration/test_step_16.py -v`
- **Dependencies**: Task 1-07 (semantic_review enforcement), Task 1-09 (milestone filtering)

### Task 5-06: Add pairwise completeness CLI command
- **Addresses**: AUDIT-067
- **Files**: `tools/specdev_tools/cli.py`, `tools/specdev_tools/validation/traceability_closure.py`
- **Change**: Add `specdev completeness-check spec --repo-root .` CLI command that runs all pairwise completeness checks in sequence and reports coverage ratios.
- **Test gate**: `pytest tests/unit/test_cli.py -v`
- **Dependencies**: Tasks 5-01 through 5-04

### Task 5-07: Redesign Step 13a as machine-computed coverage
- **Addresses**: AUDIT-068
- **Files**: `schema/13a_completeness_assessment.schema.json`, `prompts/prompt_13a_completeness_assessment.md`, `tools/specdev_tools/validation/validators/step_13a.py`
- **Change**: Per Decision 12:
  1. **Schema**: Replace subjective 0-10 scores with structured coverage dimensions: `fr_api_coverage`, `fr_fixture_coverage`, `fr_milestone_coverage`, `capability_fr_coverage`. Each is an object with `covered_count`, `total_count`, `ratio`, `uncovered_ids`.
  2. **Prompt**: Redesign as aggregation step that reads pairwise completeness output and structures it. LLM role shifts from subjective assessment to structured reporting.
  3. **Validator**: Validate coverage ratios against minimum thresholds. Add blocking gate concept (or document as future work per Design Note).
- **Test gate**: `pytest tests/integration/ -k "step_13a" -v`
- **Dependencies**: Tasks 5-01 through 5-06
- **Design Note**: The blocking gate (preventing Step 14 emission when 13a fails) requires NEW infrastructure. For this batch, implement the machine-computed coverage and threshold validation. The gate enforcement is a future capability.

---

## Batch 6: Self-Audit Gate Redesign

Depends on Batch 4 (prompts have step-specific content established).

### Task 6-01: Restructure Self-Audit Gate in all 22 prompts
- **Addresses**: AUDIT-009, AUDIT-010, AUDIT-011
- **Files**: All 22 `prompts/prompt_*.md`
- **Change**: Per Decision 10 (3-concern decomposition):
  1. Replace `## Self-Audit Gate` section with: reference to shared_expectations threshold + step-specific gating items only (input-sufficiency checks).
  2. Move anti-pattern checks to `## Negative Constraints` section.
  3. Promote Coverage Closure to sibling heading (not nested under Self-Audit Gate).
  Structure per prompt:
  ```markdown
  ## Self-Audit Gate
  > Per shared_expectations: if ANY item below cannot be satisfied, enter Clarify mode.
  - [step-specific input-sufficiency item 1]
  - [step-specific input-sufficiency item 2]
  - ...

  ## Negative Constraints
  - [anti-pattern 1]
  - ...

  ## Coverage Closure
  [step-specific coverage checks]
  [universal tail from shared_expectations]
  ```
- **Test gate**: `pytest tests/unit/generation/test_prompt_contracts.py -v`
- **Dependencies**: 2-01 (shared_expectations has threshold), 4-10 (Coverage Closure enrichment)
- **Note**: 22 file edits. For P5 execution, MUST be split into 22 sub-tasks. All run in parallel.

### Task 6-02: Remove duplicate Self-Audit Gate headings from Trinity Loop prompts
- **Addresses**: AUDIT-012
- **Files**: `prompts/prompt_16a_impl_planner.md`, `prompts/prompt_16b_impl_coder.md`, `prompts/prompt_16c_impl_reviewer.md`
- **Change**: Remove the first "(Score Threshold)" Self-Audit Gate heading from each Trinity prompt. Merge into the single restructured Self-Audit Gate from Task 6-01.
- **Test gate**: `pytest tests/unit/generation/test_prompt_contracts.py -v`
- **Dependencies**: 6-01

### Task 6-03: Fix Step 13 gate items
- **Addresses**: AUDIT-037
- **File**: `prompts/prompt_13_extension_generator.md`
- **Change**: Move the 5 anti-pattern gate items (lines 72-77) to Negative Constraints. Replace with input-sufficiency checks: "All referenced schemas exist", "Extension scope is within Step 13 boundaries", "Naming convention follows kebab-case pattern".
- **Test gate**: `pytest tests/unit/generation/test_prompt_contracts.py -v`
- **Dependencies**: 6-01

### Task 6-04: Normalize gate item counts
- **Addresses**: AUDIT-050
- **Files**: All 22 prompts
- **Change**: Review each prompt's Self-Audit Gate items and normalize based on: (1) number of upstream dependencies, (2) number of schema `required` fields, (3) step complexity. Target range: 3-5 items per step. Add items to steps with only 2; split compound items in steps with 6+.
- **Test gate**: `pytest tests/unit/generation/test_prompt_contracts.py -v`
- **Dependencies**: 6-01

---

## Batch 7: Validator/Lint Fixes

Depends on Batches 0-6 being stable. These are incremental validator improvements.

### Task 7-01: Extend E560 to check success_metrics traceability
- **Addresses**: AUDIT-022
- **File**: `tools/specdev_tools/validation/traceability_closure.py`
- **Change**: At lines 82-97, extend the 00->01 lint check to verify each `success_metric` ID from Step 00 is traced by at least one capability in Step 01.
- **Test gate**: `pytest tests/unit/validation/ -k "traceability" -v`
- **Dependencies**: None

### Task 7-02: Fix `_collect_required_seeds` ordering vs membership bug
- **Addresses**: AUDIT-024
- **File**: `tools/specdev_tools/validation/seed_lint.py`
- **Change**: At line 61-62, change `_collect_required_seeds` to use `global_seed_order` for ordering only, not membership expansion. The function should return only seeds listed in `step_requirements[step_id]`, ordered by `global_seed_order`.
- **Test gate**: `pytest tests/unit/validation/linters/test_seed_path_validation.py -v && pytest tests/unit/validation/linters/test_seed_strict_mode.py -v`
- **Dependencies**: None

### Task 7-03: Add evidence content validation for Trinity Loop
- **Addresses**: AUDIT-070
- **File**: `tools/specdev_tools/validation/validators/step_16.py`
- **Change**: Enhance E301 evidence check: beyond existence, validate that evidence content contains at least one success marker keyword (e.g., "PASS", "OK", "passed", "success", "0 failures") or is structured with `stdout`/`stderr` fields. Add W-code for suspiciously short evidence (<50 chars).
- **Test gate**: `pytest tests/integration/test_step_16.py -v`
- **Dependencies**: None

### Task 7-04: Add evidence binding for verified actions
- **Addresses**: AUDIT-032
- **File**: `tools/specdev_tools/validation/validators/step_16.py`
- **Change**: Add validator: (1) verified actions must have `evidence` with non-empty `content`, (2) `verdict: verified` requires `fixture_status.ci_status: green` (strengthen existing E303). Add W-code for verified action without evidence.
- **Test gate**: `pytest tests/integration/test_step_16.py -v`
- **Dependencies**: None

### Task 7-05: Add milestone_coverage to trace matrix
- **Addresses**: AUDIT-033
- **File**: `tools/specdev_tools/validation/matrix.py`
- **Change**: Extend trace matrix builder (lines 170-305) to include Step 14 `fr_refs` as a "milestone_coverage" column. Load Step 14, extract FR refs per milestone/task, add to matrix output.
- **Test gate**: `pytest tests/ -k "matrix" -v`
- **Dependencies**: None

### Task 7-06: Add tech stack coherence check
- **Addresses**: AUDIT-034
- **File**: `tools/specdev_tools/validation/spec_quality_lint.py`
- **Change**: Add W-code check: if Steps 09 and 14 both have `tech_stack`, verify they contain the same entries. Load both specs, compare `tech_stack` objects. Warn on mismatches.
- **Test gate**: `pytest tests/unit/validation/linters/test_spec_quality_lint.py -v`
- **Dependencies**: None

### Task 7-07: Add governance-to-CI cross-validation
- **Addresses**: AUDIT-077
- **File**: `tools/specdev_tools/validation/traceability_closure.py` (or new linter)
- **Change**: Add W-code: for each `pr_rule` in Step 10, verify a corresponding CI job in Step 12 enforces it.
- **Test gate**: `pytest tests/unit/validation/ -k "traceability" -v`
- **Dependencies**: None

### Task 7-08: Add API-to-threat coverage check
- **Addresses**: AUDIT-078
- **File**: `tools/specdev_tools/validation/validators/step_11.py`
- **Change**: Add W-code: load API IDs from Step 05, verify every public API is targeted by at least one threat in Step 11.
- **Test gate**: `pytest tests/unit/validation/ -k "step_11" -v`
- **Dependencies**: None

### Task 7-09: Extend file scope check to execution.files_touched
- **Addresses**: AUDIT-087
- **File**: `tools/specdev_tools/validation/validators/step_16.py`
- **Change**: Extend the existing `files_touched` scope check (which checks `implementation.files_touched`) to also check `execution.files_touched` against `target_file_patterns`.
- **Test gate**: `pytest tests/integration/test_step_16.py -v`
- **Dependencies**: None

### Task 7-10: Fix Step 13 section pattern validation bug
- **Addresses**: AUDIT-093
- **File**: `tools/specdev_tools/validation/validators/step_13.py`
- **Change**: At line 13, the `required_schema_sections` pattern check uses `^[0-9]{2}[a-z]?_` which rejects domain sections like "tables", "indexes". Relax to accept any non-empty string, or check only that the section name is a valid kebab-case identifier.
- **Test gate**: `pytest tests/ -k "step_13" -v`
- **Dependencies**: None

### Task 7-11: Add 16c -> 16a feedback loop validator
- **Addresses**: AUDIT-094
- **File**: `tools/specdev_tools/validation/validators/step_16a.py`
- **Change**: Add W-code: if previous 16c output exists with remediation tasks, check that current 16a checklist includes those task IDs.
- **Test gate**: `pytest tests/ -k "step_16a" -v`
- **Dependencies**: None

### Task 7-12: Add ID stability detection during replay
- **Addresses**: AUDIT-098
- **File**: `tools/specdev_tools/validation/forward_replay_check.py`
- **Change**: Add W-code: during forward-replay diff detection, identify removed IDs (IDs present in base ref but absent in current). Warn on ID removal to catch renames early.
- **Test gate**: `pytest tests/ -k "replay" -v`
- **Dependencies**: None

---

## Batch 8: Docs + Migration Templates

Depends on all previous batches being stable. These are documentation updates that reflect the final state.

### Task 8-01: Regenerate all 19 migration templates from current schemas
- **Addresses**: AUDIT-020
- **Files**: All 19 `prompts/migration/template_*.md` files
- **Change**: For each template, regenerate "Required Changes" section listing actual schema `required` fields and property names from current schemas. Fix field name mismatches (e.g., template_charter.md listing `project_name` when schema uses `problem_statement`).
- **Test gate**: `pytest tests/unit/migration/test_migration_templates.py -v`
- **Dependencies**: 0a (schema structural changes)
- **Note**: Split into sub-tasks per template file.

### Task 8-02: Create migration templates for Steps 16a, 16b, 16c
- **Addresses**: AUDIT-021
- **Files**: `prompts/migration/template_impl_planner.md` (new), `prompts/migration/template_impl_coder.md` (new), `prompts/migration/template_impl_reviewer.md` (new)
- **Change**: Create three new migration templates following the existing template pattern. Add `STEP_TO_TEMPLATE` entries in `tools/specdev_tools/core/constants.py`.
- **Test gate**: `pytest tests/unit/migration/test_migration_templates.py -v`
- **Dependencies**: None

### Task 8-03: Add step_docs map and surface in prompts
- **Addresses**: AUDIT-025
- **File**: `tools/step_order.json` (or new `tools/step_docs.json`)
- **Change**: Create mapping of step IDs to relevant documentation files. Surface in prompts as optional context references.
- **Test gate**: Manual verification.
- **Dependencies**: None

### Task 8-04: Add prompt references to migration templates
- **Addresses**: AUDIT-045
- **Files**: All 19 (soon 22) `prompts/migration/template_*.md`
- **Change**: Add "Full Generation Reference" section to each template referencing the corresponding step prompt.
- **Test gate**: `pytest tests/unit/migration/test_migration_templates.py -v`
- **Dependencies**: 8-01, 8-02

### Task 8-05: Fix template_frs.md artifact filename
- **Addresses**: AUDIT-046
- **File**: `prompts/migration/template_frs.md`
- **Change**: At line 33, change `spec/04_functional_requirements.json` to `spec/04_fr_list.json`.
- **Test gate**: Manual verification.
- **Dependencies**: None

### Task 8-06: Rewrite workflow_bootstrap_legacy.md
- **Addresses**: AUDIT-047
- **File**: `docs/developers/workflows/workflow_bootstrap_legacy.md`
- **Change**: Rewrite to use current seed paths, two-phase Clarify/Emit protocol, and canonical step prompts.
- **Test gate**: Manual verification.
- **Dependencies**: All prompt work complete.

### Task 8-07: Update workflow_feature_extension.md
- **Addresses**: AUDIT-048
- **File**: `docs/developers/workflows/workflow_feature_extension.md`
- **Change**: Update to reference canonical step prompts instead of "copying generic prompts."
- **Test gate**: Manual verification.
- **Dependencies**: All prompt work complete.

### Task 8-08: Implement migration template interpolation or update ADR
- **Addresses**: AUDIT-049
- **File**: `docs/ops/adr_template_engine.md` and/or `tools/specdev_tools/generation/prompt_generator.py`
- **Change**: Either implement `{{VAR}}` interpolation in `_render_prompt()` per the ADR, or update the ADR to reflect that interpolation is a future feature.
- **Test gate**: `pytest tests/unit/generation/ -v`
- **Dependencies**: 8-01

### Task 8-09: Fix miscellaneous doc issues
- **Addresses**: AUDIT-059, AUDIT-060, AUDIT-061, AUDIT-064
- **Files**:
  - `docs/ops/adr_template_engine.md`: update template count from 14 to 22 (AUDIT-059)
  - `docs/README.md`: add missing doc references (AUDIT-060)
  - `docs/developers/workflows/workflow_align.md` + `workflow_migration.md`: fix `dev_env` -> `devspec_env` (AUDIT-061)
  - `docs/audit/`: add archive marker to historical docs (AUDIT-064)
- **Test gate**: Manual verification.
- **Dependencies**: None

### Task 8-10: Document future extension candidates
- **Addresses**: AUDIT-089, AUDIT-090, AUDIT-099
- **File**: `docs/plans/future_extensions.md` (new or append to existing)
- **Change**: Document as future extension candidates:
  - Consumed third-party API contracts artifact (AUDIT-089)
  - Security model consolidation artifact (AUDIT-090)
  - Dedicated data model artifact (AUDIT-099)
- **Test gate**: File exists.
- **Dependencies**: None

---

## N/A Findings (No Action Required)

| Finding | Reason |
|---------|--------|
| AUDIT-036 | Subsumed by AUDIT-026 (Batch 2) -- shared_expectations redesign covers this |
| AUDIT-063 | Verified complete -- `generation_quality` already fully purged |
| AUDIT-065 | INFO -- extraction summary, not an action item; implemented via AUDIT-006 |

---

## Multi-Batch Findings Cross-Reference

These findings have work split across multiple batches:

| Finding | Batch 0 Work | Later Batch Work |
|---------|-------------|-----------------|
| AUDIT-006 | 0b (schema enrichment), 0c (Quick Reference deletion) | Batch 2 (shared_expectations extraction + boilerplate deletion) |
| AUDIT-008 | 0c (Quick Reference deletion from prompts) | Batch 4 (Field-by-Field deletion + Output Contract fixes) |
| AUDIT-015 | 0a (add `fr_refs` to Step 14 task schema) | Batch 5 (pairwise validation logic) |
| AUDIT-040 | 0b (schema descriptions fix examples) | Batch 4 (prompt Output Contract fixes) |
| AUDIT-053 | 0b (description differentiation) | Batch 3 (may subsume via consolidation in AUDIT-095) |
| AUDIT-071 | 0b (all schema description enrichment) | Batch 4 (prompts reference enriched schemas) |

---

## Risk Register

### R1: Batch 0b Scope Creep
**Risk**: 925 schema properties need description review. Could become multi-week blocker.
**Mitigation**: Prioritize Tier 3 fields (semantic/LLM-facing) in schemas where prompts currently duplicate guidance (Steps 00, 01, 04, 05, 06, 07, 09, 14, 16). Tier 1/Tier 2 fields can be enriched incrementally.

### R2: Breaking Schema Changes (Batch 0a)
**Risk**: Tasks 0a-03 (charter required), 0a-04 (Step 05 trace required), 0a-05 (owner enum) are breaking changes.
**Mitigation**: Update ALL test fixtures in the same task. Add changelog entries. Provide migration guidance for host repos.

### R3: Batch 2 shared_expectations Size
**Risk**: Extracting ~1,000 LOC of boilerplate from 22 prompts is error-prone.
**Mitigation**: Extract one block type at a time (e.g., all Path Variables first, then all Schema Authority). Run test suite after each block type.

### R4: Batch 5 Pairwise Completeness Scope
**Risk**: Universal pairwise chain (5 transitions) is a significant new capability.
**Mitigation**: Implement as W-codes (warnings) not E-codes (errors) initially. Graduate to E-codes after user feedback.

### R5: Batch 5 Step 13a Blocking Gate
**Risk**: Blocking gate requires new infrastructure (gate schema, enforcement logic, bypass mechanism).
**Mitigation**: Implement machine-computed coverage and threshold validation only. Defer gate enforcement to future batch. Document the gap.

### R6: Batch 4 Prompt Quality
**Risk**: Synthesis reasoning frameworks need domain expertise to write well.
**Mitigation**: Start with Steps 04 and 07 (highest downstream impact per R2-A). Iterate based on test results.

### R7: Prompt Contract Test Fragility
**Risk**: Batches 0c, 2, 4, and 6 substantially restructure prompts (delete/add/rename sections). `test_prompt_contracts.py` checks structural patterns and will break.
**Mitigation**: Each prompt restructuring task MUST update test expectations in the same sub-task or immediately after. Test gates in these batches serve as verification — if they fail, the task includes updating the test expectations as part of the fix.

### R8a: Test Suite Stability
**Risk**: Cross-cutting changes (Batches 0a, 1-05) may break tests in unexpected ways.
**Mitigation**: Run full test suite after each task. Fix test failures before proceeding to next task.

### R9: Host Repo Compatibility
**Risk**: Multiple breaking changes in Batch 0a. Host repos may not track changes.
**Mitigation**: Bundle breaking changes into a single version bump (0.5.0). Comprehensive changelog with migration instructions.

---

## Execution Checklist

- [ ] Batch 0a: 5 structural schema tasks
- [ ] Batch 0b: 22 description enrichment tasks
- [ ] Batch 0c: 1 Quick Reference deletion task (17 sub-tasks)
- [ ] Batch 1: 10 config/bug fix tasks (parallel with Batch 0)
- [ ] Batch 2: 5 shared_expectations tasks
- [ ] Batch 3: 5 canon pipeline tasks
- [ ] Batch 4: 15 prompt enrichment tasks
- [ ] Batch 5: 7 pairwise completeness tasks
- [ ] Batch 6: 4 Self-Audit Gate tasks
- [ ] Batch 7: 12 validator/lint tasks
- [ ] Batch 8: 10 docs/template tasks
- [ ] Full test suite green after each batch
- [ ] Changelog entries for breaking changes
