---

# Review R8 Findings — Schema Tightening: Full Alignment with Hardened Prompts
Generated: 2026-03-02
Updated: 2026-03-03
Status: COMPLETE (all 14 findings implemented — 584/584 tests pass, validate-all OK, quality-lint OK)

## Part A: Findings

### Verified Findings (CONFIRMED by file inspection)

| ID | Sev | File | Finding | Impact |
|----|-----|------|---------|--------|
| A-R8-01 | CRIT | ALL 19 step schemas | `coverage_gaps` field missing from all step schemas. All prompts (00-16c) mandate `coverage_gaps[]` population in their "Coverage Gap Reporting" section. All schemas have `additionalProperties: false`. Any artifact following prompts WILL fail validation. | Blocks entire spec pipeline — no artifact can pass validation if it includes coverage_gaps as prompts instruct |
| A-R8-02 | CRIT | schema/16_impl_context.schema.json:291 | `milestone_ref` NOT defined in `plan.spec_alignment.checklist` item properties. Checklist items have `additionalProperties: false`. prompt_16a_impl_planner.md line 124: "Every checklist item MUST include a `milestone_ref` field." | 16a planner output will fail validation — checklist items with milestone_ref will be rejected |
| A-R8-03 | HIGH | schema/01_capabilities.schema.json:88-93 | `trace` not in capability items `required[]`. prompt_01_capabilities.md states trace MUST include at least one reference to FRs. Schema makes trace optional. | Capabilities without trace pass validation but violate prompt contract |
| A-R8-04 | HIGH | schema/07_nfrs.schema.json:95-106 | `trace` not in NFR items `required[]`. prompt_07_nfrs.md states trace references to FRs/APIs/components/invariants are required. Schema makes trace optional. | NFRs without trace pass validation but violate prompt contract |

### Evidence

**A-R8-01:**
- Grep across all `schema/*.schema.json`: zero matches for `coverage_gaps`
- Grep across all `prompts/prompt_*.md`: 11+ prompts contain "MUST be recorded in `coverage_gaps[]`"
- Example: `prompts/prompt_06_invariants.md:15` — "Any output field whose value cannot be traced to a specific upstream artifact or seed document MUST be recorded in `coverage_gaps[]`"
- Every schema file has `"additionalProperties": false` — undefined fields are rejected

**A-R8-02:**
- Schema: `schema/16_impl_context.schema.json` — checklist item properties include: `id, spec_ref, description, type, layer, checklist_status, linked_test_expectation, nfr_refs, fixture_ref, implementation`. No `milestone_ref`.
- `additionalProperties: false` on checklist items (line 291)
- Prompt: `prompts/prompt_16a_impl_planner.md:124` — "Every checklist item MUST include a `milestone_ref` field containing the `milestone_id` from Step 14 that owns the referenced task."

**A-R8-03:**
- Schema `required[]` for capability items: `[capability_id, verb, scope, capability_ref]` — no `trace`
- `trace` defined in properties (lines 69-73) but optional

**A-R8-04:**
- Schema `required[]` for NFR items does NOT include `trace`
- `trace` defined in properties (lines 76-80) but optional

### Refuted Findings (Phase 1 hallucinations corrected)

These were reported by Phase 1 investigation subagents but disproved during self-verification:

| Claimed Finding | Verification Result | Reason |
|-----------------|-------------------|--------|
| `execution` and `review` optional in 16_impl_context is a bug | REFUTED | Working as designed. Step 16a creates plan and leaves execution/review empty. Step 16b fills execution. Step 16c fills review. Schema correctly makes them optional at top level. |
| Step 05 `method`/`route` should be required | REFUTED | Prompt says "where applicable" — method/route are conditional on HTTP protocol. Schema correctly optional. |
| `plan.spec_alignment.checklist[*].type` enum missing from schema | REFUTED | `type` field EXISTS in checklist item properties. Phase 1B hallucinated this finding. |
| Multiple "missing structures" in Step 16 (timeout_constants, security.new_fixtures, delivery.dashboards, delivery.alerts, review.fixture_status, etc.) | REFUTED | V6 verification confirmed all sub-structures present in schema. Phase 1B hallucinated absence. |
| trace optional in Steps 04 and 06 | REFUTED | Trace IS required in both Step 04 (`fr_list.schema.json:93`) and Step 06 (`invariants.schema.json:88`). Phase 1A misread the schemas. |

### G-Series Findings (discovered during implementation plan review)

| ID | Sev | File | Finding | Resolution |
|----|-----|------|---------|------------|
| G1 | HIGH | schema/09_impl_plan.schema.json | `milestones` not in top-level `required[]` — prompt mandates milestones array | Added to `required[]` |
| G2 | HIGH | schema/09_impl_plan.schema.json | `deliverables` and `status` not in milestone items `required[]` — prompt mandates both | Added to milestone items `required[]`. No fixture breakage (empty arrays satisfy required without minItems) |
| G5 | HIGH | schema/14_roadmap.schema.json | `acceptance_criteria` required on task items but prompt says MAY omit | Removed from task items `required[]`. `invalid_task_acceptance_criteria.json` still fails on `text` minLength |
| G6 | MED | schema/14_roadmap.schema.json | Task assumptions `minLength: 15` but prompt says `>=10` | Changed to `minLength: 10` |
| G9 | INFO | schema/16_impl_context.schema.json | `milestone_ref` not required on checklist items | Intentional — shared schema across 16a/16b/16c; W581/E582 validators enforce for 16a |
| G10 | HIGH | schema/13a_completeness_assessment.schema.json | `missing_elements[*].category` is untyped string — prompt mandates specific enum values | Added `enum: ["traceability", "completeness", "quality", "ambiguity"]` |
| G11 | HIGH | schema/13a_completeness_assessment.schema.json | `specification_source` not in missing_elements items `required[]` — prompt mandates it | Added to `required[]` |
| G13 | HIGH | schema/core/collections.schema.json | `generationQuality.assumptions` not required — all prompts mandate assumptions array | Added `required: ["assumptions"]` to generationQuality definition |
| G14 | MED | tests/fixtures/ (all invalid) | Invalid fixtures would gain additional "missing coverage_gaps" error, polluting diagnostic purity | Added `coverage_gaps: []` to all invalid fixtures |

### Post-R8 Cleanup Findings

| ID | Sev | File(s) | Finding | Resolution |
|----|-----|---------|---------|------------|
| A-R8-11 | MED | 19 step schemas | Mixed `$ref` addressing: 189 cross-schema refs used JSON Pointer syntax (`#/$defs/name`) while all 32 definitions in `collections.schema.json` declare `$anchor`, making anchor syntax (`#name`) the canonical convention | Normalized all 189 cross-schema refs from `#/$defs/` to anchor `#` syntax. Local self-refs in `canon.schema.json` (12) and `16_impl_context.schema.json` (7) untouched. |
| A-R8-12 | MED | tools/specdev_tools/generation/prompt_schema_sync.py | W580 SUBSTEP_DRIFT false positives: validator warned when 16b/16c Output Contracts contain upstream keys (`plan`, `execution`). This is by design — Trinity Loop steps accumulate upstream sections. | Updated W580 logic to only check forward drift (keys from later substeps). Upstream keys are expected and no longer trigger warnings. Added `_SUBSTEP_ORDER` constant. |

### MED Severity Findings (contextual, not blocking)

| ID | Sev | File | Finding | Impact | Action |
|----|-----|------|---------|--------|--------|
| A-R8-05 | MED | schema/05_interface_contracts.schema.json | `apis[*].trace` optional but prompt says populate trace references. However, trace is a downstream reference that may not exist at creation time. | Minor — artifacts without trace are still valid at this step | Leave optional; document rationale |
| A-R8-06 | MED | schema/01_capabilities.schema.json | `owner`, `inputs`, `outputs`, `preconditions`, `postconditions`, `error_states` optional but prompt implies they should be present for non-trivial capabilities | Minor — these are conditional recommendations, not unconditional MUST | Leave optional; prompt language is guidance not mandate |
| A-R8-07 | MED | schema/04_fr_list.schema.json | `rationale`, `preconditions`, `postconditions` optional but prompt treats as important | Minor — prompt recommends but doesn't mandate | Leave optional |
| A-R8-08 | MED | schema/02a_delivery_baseline.schema.json | `secrets` and `compliance` optional but prompt treats as important | Minor — not all projects have secrets/compliance | Leave optional |
| A-R8-09 | MED | schema/05_interface_contracts.schema.json | `errors[]` on APIs optional but prompt says MUST for mutating operations | Conditional — only applies to non-GET mutating APIs | Leave optional; validator can enforce conditionally in R9 |
| A-R8-10 | MED | Various | `minItems` gaps on optional arrays across several schemas | Minor — prompts imply minimums but schemas don't enforce | Leave for R9 conditional validation |

## Part B: Implementation Plan

### Key Design Decisions

1. **coverage_gaps**: Define reusable type in `schema/core/collections.schema.json`, then `$ref` from all 19 step schemas. Add to `required[]` with `minItems: 0` (empty array allowed).
2. **milestone_ref**: Add to `plan.spec_alignment.checklist` item properties in `schema/16_impl_context.schema.json`. Type: string with kebab-case pattern.
3. **trace tightening**: Add `trace` to `required[]` in Steps 01 and 07. Verify no breakage against existing artifacts (none exist for these steps).
4. **Existing artifact**: `spec/05_interface_contracts.json` must be updated with `coverage_gaps: []` to avoid breakage.
5. **Test fixtures**: All valid fixtures must be updated with `coverage_gaps: []`.
6. **MED findings**: Intentionally left as-is with documented rationale. Conditional enforcement deferred to R9 (validator overhaul).

### Subagent Implementation Strategy

Tasks are grouped for parallel subagent execution. Each subagent runs in a worktree.

- **Subagent 1** (worktree): T01 — Core schema update
- **Subagent 2** (worktree): T02-T11 — Steps 00-08 schemas (parallel-safe, no shared files)
- **Subagent 3** (worktree): T12-T20 — Steps 09-16c schemas
- **Subagent 4** (worktree): T21-T22 — Test fixtures + existing artifact
- **Subagent 5** (no isolation): T23 — Full validation run
- **Subagent 6** (no isolation): T24-T25 — Documentation

Subagents 2 and 3 can run in parallel after Subagent 1 completes. Subagent 4 runs after BOTH Subagents 2 AND 3 have fully completed (all T02-T20 done). Subagent 5 after 4. Subagent 6 after 5.

### Atomic Task Table

| ID | Pri | Deps | File | Change Summary | Acceptance Command | Findings |
|----|-----|------|------|----------------|-------------------|----------|
| T01 | P0 | — | schema/core/collections.schema.json | Add `coverageGap` definition: `{type: object, required: [upstream_item_id, source_step, reason], properties: {upstream_item_id: {type: string}, source_step: {type: string, pattern: "^[0-9]{2}[a-c]?$"}, reason: {type: string, minLength: 10}}, additionalProperties: false}`. Add `coverageGapsArray` definition: `{type: array, items: {$ref: "#/definitions/coverageGap"}, minItems: 0}` | `python -c "import json; d=json.load(open('schema/core/collections.schema.json')); assert 'coverageGap' in d.get('definitions', d.get('$defs', {})), 'missing coverageGap'"` | A-R8-01 |
| T02 | P0 | T01 | schema/00_charter.schema.json | Add `coverage_gaps` property using `$ref` to core coverageGapsArray. Add `coverage_gaps` to `required[]`. | `python -c "import json; d=json.load(open('schema/00_charter.schema.json')); assert 'coverage_gaps' in d['properties']; assert 'coverage_gaps' in d['required']"` | A-R8-01 |
| T03 | P0 | T01 | schema/01_capabilities.schema.json | Add `coverage_gaps` to properties and required[]. Also add `trace` to capability items `required[]` array. | `python -c "import json; d=json.load(open('schema/01_capabilities.schema.json')); assert 'coverage_gaps' in d['required']"` | A-R8-01, A-R8-03 |
| T04 | P0 | T01 | schema/02_system_sketch.schema.json | Add `coverage_gaps` to properties and required[]. | Same pattern as T02 | A-R8-01 |
| T05 | P0 | T01 | schema/02a_delivery_baseline.schema.json | Add `coverage_gaps` to properties and required[]. | Same pattern | A-R8-01 |
| T06 | P0 | T01 | schema/03_glossary.schema.json | Add `coverage_gaps` to properties and required[]. | Same pattern | A-R8-01 |
| T07 | P0 | T01 | schema/04_fr_list.schema.json | Add `coverage_gaps` to properties and required[]. | Same pattern | A-R8-01 |
| T08 | P0 | T01 | schema/05_interface_contracts.schema.json | Add `coverage_gaps` to properties and required[]. | Same pattern | A-R8-01 |
| T09 | P0 | T01 | schema/06_invariants.schema.json | Add `coverage_gaps` to properties and required[]. | Same pattern | A-R8-01 |
| T10 | P0 | T01 | schema/07_nfrs.schema.json | Add `coverage_gaps` to properties and required[]. Also add `trace` to NFR items `required[]` array. | Same pattern | A-R8-01, A-R8-04 |
| T11 | P0 | T01 | schema/08_fixtures.schema.json | Add `coverage_gaps` to properties and required[]. | Same pattern | A-R8-01 |
| T12 | P0 | T01 | schema/09_impl_plan.schema.json | Add `coverage_gaps` to properties and required[]. | Same pattern | A-R8-01 |
| T13 | P0 | T01 | schema/10_governance.schema.json | Add `coverage_gaps` to properties and required[]. | Same pattern | A-R8-01 |
| T14 | P0 | T01 | schema/11_redteam.schema.json | Add `coverage_gaps` to properties and required[]. | Same pattern | A-R8-01 |
| T15 | P0 | T01 | schema/12_ci_gates.schema.json | Add `coverage_gaps` to properties and required[]. | Same pattern | A-R8-01 |
| T16 | P0 | T01 | schema/13_extension_generator.schema.json | Add `coverage_gaps` to properties and required[]. | Same pattern | A-R8-01 |
| T17 | P0 | T01 | schema/13a_completeness_assessment.schema.json | Add `coverage_gaps` to properties and required[]. | Same pattern | A-R8-01 |
| T18 | P0 | T01 | schema/14_roadmap.schema.json | Add `coverage_gaps` to properties and required[]. | Same pattern | A-R8-01 |
| T19 | P0 | T01 | schema/15_scaffold.schema.json | Add `coverage_gaps` to properties and required[]. | Same pattern | A-R8-01 |
| T20 | P0 | T01 | schema/16_impl_context.schema.json | Add `coverage_gaps` to properties and required[]. Add `milestone_ref` (type: string, pattern: `^[a-z0-9]+(?:-[a-z0-9]+)*$`) to `plan.spec_alignment.checklist` item properties. | `python -c "import json; d=json.load(open('schema/16_impl_context.schema.json')); assert 'coverage_gaps' in d['required']"` | A-R8-01, A-R8-02 |
| T21 | P1 | T02-T20 | tests/fixtures/ (valid fixtures only) | Add `"coverage_gaps": []` to ALL ~122 valid step fixtures in `tests/fixtures/step_00/` through `tests/fixtures/step_16/` (valid/ subdirectories only). Do NOT modify: invalid fixtures, `tests/fixtures/canonical/`, `tests/fixtures/migration/`, or `tests/fixtures/seed_manifest/`. | `pytest tests/ -k "valid" --tb=short -q` | A-R8-01 |
| T22 | P1 | T08 | spec/05_interface_contracts.json | Add `"coverage_gaps": []` AND `"spec_refs_ingested": []` to existing spec artifact. The `spec_refs_ingested` field is a pre-existing missing required field (schema requires it but artifact lacks it). Both must be added before validation will pass. | `./tools/run_specdev.sh validate spec/05_interface_contracts.json --repo-root ./devspec_toolkit` | A-R8-01 |
| T23 | P1 | T21,T22 | — (validation only) | Run full validation suite: `pytest tests/ -v` + `./tools/run_specdev.sh validate-all spec --repo-root ./devspec_toolkit` + `./tools/run_specdev.sh spec-quality-lint spec --repo-root ./devspec_toolkit`. All must pass. | All three commands exit 0 | All |
| T24 | P3 | T23 | CHANGELOG.md | Add R8 entry: "Schema tightening — added `coverage_gaps` to all 19 step schemas, added `milestone_ref` to 16_impl_context checklist items, promoted `trace` to required in Steps 01 and 07" | — | — |
| T25 | P3 | T23 | docs/audit/review_index.md | Add R8 entry with date, status, gap count, link to findings file | — | — |

### Implementation Notes for Each Task

**T01 (collections.schema.json)**:
Read the file first. Find the `$defs` section (NOT `definitions` — this codebase uses `$defs`). Add two new definitions:
1. `coverageGap` — the individual gap entry object
2. `coverageGapsArray` — array of coverageGap with minItems: 0

The reference pattern for step schemas MUST be: `"$ref": "vc:core:collections#coverageGapsArray"` — this uses the `$anchor`-based syntax consistent with all other cross-schema refs (`#canonicalRefArray`, `#seedRefArray`, etc.). A-R8-11 normalized all 189 cross-schema refs to this anchor pattern.

**T02-T19 (step schemas)**:
For each step schema:
1. Read the file
2. Add `coverage_gaps` to `properties` using: `"$ref": "vc:core:collections#coverageGapsArray"`
3. Add `"coverage_gaps"` to the `required` array
4. For T03 (Step 01): Also find the capability items `required` array and add `"trace"`
5. For T10 (Step 07): Also find the NFR items `required` array and add `"trace"`

**T20 (16_impl_context.schema.json)**:
This is the most complex change:
1. Add `coverage_gaps` to top-level properties and required[]
2. Navigate to `plan.spec_alignment.checklist.items.properties`
3. Add `milestone_ref` property: `{"type": "string", "pattern": "^[a-z0-9]+(?:-[a-z0-9]+)*$"}`
4. Do NOT add milestone_ref to checklist items required[] (it's MUST per 16a prompt but other steps using this schema may not populate it — enforce in R9 validator instead)
5. Verify existing properties are undisturbed

**T21 (test fixtures)**:
DEPENDENCY: ALL schema tasks (T02-T20) must complete before T21 starts. Do not begin fixture updates until every step schema has been updated, because fixtures validate against the updated schemas.
1. List all directories in `tests/fixtures/step_*/valid/`
2. For each valid fixture JSON file:
   - Read the file
   - Add `"coverage_gaps": []` at the top level (alongside other top-level fields)
   - Write the file back
3. Do NOT touch files in `tests/fixtures/step_*/invalid/`, `tests/fixtures/canonical/`, `tests/fixtures/migration/`, or `tests/fixtures/seed_manifest/`
4. Expected count: ~122 files across step_00 through step_16

**T22 (existing artifact)**:
1. Read `spec/05_interface_contracts.json`
2. Add `"coverage_gaps": []` at the top level
3. Write back

**T23 (validation)**:
Run in sequence:
1. `pytest tests/ -v` — all tests must pass
2. `./tools/run_specdev.sh validate-all spec --repo-root ./devspec_toolkit` — all artifacts valid
3. `./tools/run_specdev.sh spec-quality-lint spec --repo-root ./devspec_toolkit` — quality checks pass
If any fail, report exact error messages.

### Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Schema `$ref` path format varies across schemas | T01 implementation must check existing `$ref` patterns before adding new references |
| Adding `trace` to required[] in Steps 01/07 breaks test fixtures | T21 runs after T03/T10 to fix fixtures. No existing spec artifacts for Steps 01/07. |
| Adding `coverage_gaps` to required[] breaks spec/05_interface_contracts.json | T22 adds `coverage_gaps: []` to artifact before T23 validation run |
| milestone_ref addition to 16_impl_context affects Steps 16/16a/16b/16c | Added to properties only (not required[]). Steps that don't use it simply won't populate it — schema accepts but doesn't require. |
| Valid test fixtures missing new required fields fail tests | T21 systematically updates all valid fixtures |

### Known Pre-Existing Issues (Not R8 Bugs — Noted for Awareness)

| Issue | File | Impact on R8 | Action |
|-------|------|-------------|--------|
| `seedRefArray` uses inconsistent $ref pattern (`#seedRefArray` instead of `#/$defs/seedRefArray`) across all step schemas | All step schemas | None — R8 uses correct `#/$defs/` pattern for new coverageGapsArray | Out of scope for R8; document for future cleanup |
| `spec/05_interface_contracts.json` missing required `spec_refs_ingested` field | spec/05_interface_contracts.json | T22 must add this field alongside coverage_gaps | Fixed in T22 |

## Verification Status

### Self-Verification Checks (Review Protocol Phase 4)

- CHECK 1 (No assumptions): **PASS** — All findings verified by file inspection. 5 Phase 1 hallucinations identified and removed.
- CHECK 2 (Verified references): **PASS** — All file:line references confirmed by Phase 4 verification subagent reading actual files.
- CHECK 3 (Atomic tasks): **PASS** — Each task modifies exactly one file (T21 is an exception: multiple fixture files in same directory, accepted per protocol note on fixture sets).
- CHECK 4 (Test coverage): **PASS** — T23 runs full test suite after all changes. T21 updates fixtures. No new code modules added (only schema changes).
- CHECK 5 (Documentation coverage): **PASS** — T24 (CHANGELOG) and T25 (review_index) cover all documentation needs. No error codes, CLI commands, or public API changes.
- CHECK 6 (Dependency resolution): **PASS** — T01 → T02-T20 → T21/T22 → T23 → T24/T25. All dependencies forward-pointing.
- CHECK 7 (Orphan findings): **PASS** — All 4 verified findings (A-R8-01 through A-R8-04) have corresponding tasks. MED findings (A-R8-05 through A-R8-10) documented as intentional — deferred to R9 with rationale.

### Metrics

- Total findings: 21 (2 CRIT, 2 HIGH original + 9 G-series [6 HIGH, 2 MED, 1 INFO] + 2 post-R8 cleanup [A-R8-11, A-R8-12] + 6 MED deferred)
- Findings implemented: 14 (4 original A-R8-01–04 + 8 G-series + 2 post-R8 cleanup)
- Findings deferred to R9: 6 (A-R8-05–10)
- G9 documented as intentional design (not a bug)
- Files modified: 19 step schemas + 1 core schema + 22 prompts + ~130 fixtures + 1 spec artifact + 1 validator + 1 test file + 3 docs = ~178
- Phase 1 hallucinations caught: 5 (execution/review, method/route, checklist type, missing structures, trace in 04/06)
- Tests: 584/584 pass, validate-all OK (warnings only), spec-quality-lint OK

## Residual Issues (MED — Deferred to R9)

| ID | Finding | Rationale for Deferral |
|----|---------|----------------------|
| A-R8-05 | trace optional in Step 05 APIs | Downstream reference may not exist at creation time; conditional enforcement needs validator logic |
| A-R8-06 | Multiple optional fields in Step 01 capabilities | Prompt language is guidance ("when applicable") not unconditional MUST; conditional enforcement = R9 |
| A-R8-07 | rationale/preconditions/postconditions optional in Step 04 | Same reasoning — conditional recommendations |
| A-R8-08 | secrets/compliance optional in Step 02a | Not all projects have these; schema correctly flexible |
| A-R8-09 | errors[] optional in Step 05 APIs | Conditional on non-GET mutating operations — validator enforcement in R9 |
| A-R8-10 | minItems gaps on optional arrays | Prompt implies minimums but doesn't unconditionally mandate — validator enforcement in R9 |

## Dependencies

| Direction | Review | Relationship |
|-----------|--------|-------------|
| Requires | R7 | Prompts hardened before schemas tighten to match |
| Requires | R1-R6 | All structural fixes in place |
| Blocks | R9 | Validators build against R8-tightened schemas. R9 implements conditional validation for MED findings deferred here. |
