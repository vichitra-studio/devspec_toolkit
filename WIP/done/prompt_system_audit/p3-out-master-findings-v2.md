# P3 Master Findings v2 -- Prompt System Audit

**Date**: 2026-03-20
**Input**: P3 v1 (66 findings from P1) + R2 (75 findings from architectural review)
**Design Decisions**: 13 locked decisions from post-P1 discussion
**Output**: 101 findings (AUDIT-001 through AUDIT-101)

## Summary

| Severity | Count | From P1 (001-066) | From R2 (067-101) | Updated per Design Decisions |
|----------|-------|--------------------|--------------------|-----------------------------|
| CRITICAL | 9 | 6 | 3 | 3 |
| HIGH | 23 | 17 | 6 | 6 |
| MEDIUM | 42 | 26 | 16 | 3 |
| LOW | 20 | 13 | 7 | 0 |
| INFO | 7 | 4 | 3 | 0 |
| **Total** | **101** | **66** | **35** | **12** |

Notes:
- P1 findings: AUDIT-001 through AUDIT-066 (66 entries). 1 subsumed at AUDIT level (AUDIT-036 → AUDIT-026). 8 P1 agent-level findings were absorbed into existing AUDIT entries as sub-points during initial P1→P3v1 consolidation (never had independent AUDIT IDs).
- R2 findings: AUDIT-067 through AUDIT-101 (35 genuinely new entries)
- Total: 66 P1 entries + 35 R2 entries = 101
- 12 existing P3 findings had proposed fixes updated per design decisions

---

## Design Decisions Reference

These 13 locked decisions override P3 proposed fixes where they conflict. P4 must respect these.

1. **Schema is sole owner of field descriptions** -- ALL field semantics go to schemas. Prompts contain zero field-level guidance.
2. **Cross-step relationships derivable from DAG** -- remove from prompts, add directive to shared_expectations.
3. **`allowed_upstream_dependencies` delete and derive at runtime** -- 275 LOC removed from step_order.json.
4. **Pairwise completeness chain applies universally** -- capability->FR->milestone->task, ALL transitions. Not FR-specific.
5. **No NL tooling for semantic drift** -- prompt guidance + ID enforcement only.
6. **Glossary step -> canon population step** -- Step 03 populates `cn:project:` canons. Toolkit canons stay pre-populated with enums. Dedicated batch.
7. **Seed blind spots are misframed** -- prompt synthesis quality issue, not seed template issue. Seeds are PRD/system design.
8. **Don't steer agent analysis** -- process learning.
9. **Schema enrichment before prompt extraction** -- critical ordering constraint.
10. **Self-Audit Gate decomposition** -- threshold (shared), gating items (per-prompt), coverage closure (shared).
11. **No rigid description format** -- three-tier DEPTH model. Tier 3 must replace all prompt field guidance.
12. **Step 13a redesign as machine-computed coverage** -- aggregation point for pairwise completeness. Blocking gate.
13. **Pipeline validates validity not completeness** -- fix via pairwise checks at each transition.

---

## Findings

### CRITICAL

#### AUDIT-001: Discovery Phase Prompts (01-10) Lack Synthesis Reasoning Frameworks
- **Severity**: CRITICAL
- **Status**: corroborated by R2-A, R2-E
- **Source**: P1-B #17, P1-B #18, P1-B #5, P1-B #6, P1-B #1, R2-A-004, R2-A-008, R2-E-009
- **Owner**: prompts
- **Target**: `prompts/prompt_01_capabilities.md` through `prompts/prompt_10_governance.md`
- **Evidence**: 14 of 22 prompts use generic "Synthesize -> Clarify -> Emit" flow with no step-specific reasoning. R2-A confirms: Discovery Phase averages 54% step-reasoning vs Trinity's 81%; Discovery has 30% boilerplate vs Trinity's 11%. R2-E grades Discovery Phase distillation quality as B-/B vs Implementation Phase A-/A. Steps 04, 07 have the largest challenge-vs-guidance gap. R2-A-004: root cause is that boilerplate consumes 30% of Discovery prompts, leaving less room for reasoning.
- **Impact**: LLMs produce inconsistent quality across Discovery Phase steps. Requirements quality degrades through pipeline before implementation begins.
- **Proposed Fix**: Propagate Trinity Loop patterns to Discovery Phase: (1) replace generic operating flows with step-specific named phases (e.g., Step 04: "Enumerate -> Decompose -> Falsify -> Trace -> Emit"), (2) add categorized forbidden actions for Steps 04-07, (3) add weak-vs-strong examples tables to Steps 04-08, (4) add failure modes with causes/fixes. Priority: Steps 04 and 07 first (highest downstream impact). Extract boilerplate from Discovery Phase first to free space (R2-A-004).
- **Batch**: 4

#### AUDIT-002: No Prompt Addresses Conflicting Upstream Inputs
- **Severity**: CRITICAL
- **Status**: corroborated by R2-B-012 [Updated per R2/Decision 2]
- **Source**: P1-B #3, R2-B-012
- **Owner**: prompts + shared_expectations
- **Target**: All 22 prompts, most critically Steps 04, 05, 06, 07, 09
- **Evidence**: No prompt distinguishes between "missing information" (ask gap question) and "contradictory information" (requires resolution). R2-B-012 provides concrete examples: charter says "SOC2 compliant" but no capability addresses audit logging; seed_tech_stack says "single binary" but capability requires message queue.
- **Impact**: LLMs silently resolve contradictions by picking one input over another without surfacing the conflict.
- **Proposed Fix**: Add "Conflict Resolution" protocol to `shared_expectations.md` (Decision 2): "When two upstream artifacts contradict: (1) Identify the conflict explicitly. (2) Apply upstream precedence: seed > charter > capabilities > architecture > delivery > glossary. (3) If same-level conflict, add a Gap Question. (4) Never silently resolve." Add cross-step relationship handling directive to shared_expectations.
- **Batch**: 2

#### AUDIT-003: No Prompt Explains How to Identify Implicit Requirements
- **Severity**: CRITICAL
- **Status**: corroborated by R2-B-008 [Updated per R2/Decision 7]
- **Source**: P1-B #4, R2-B-008
- **Owner**: prompts
- **Target**: `prompts/prompt_04_functional_requirements.md`, `prompts/prompt_05_interface_contracts.md`, `prompts/prompt_06_invariants.md`
- **Evidence**: Step 04 says "Build a private Context Ledger" but provides no checklist of FR categories to discover. R2-B-008 provides detailed implicit FR categories: error handling, authorization, input validation, audit logging, idempotency, pagination, concurrency.
- **Impact**: LLMs produce FRs covering only explicitly stated behaviors, missing standard production requirements.
- **Proposed Fix**: Add "Implicit Requirements Discovery" checklists to Steps 04, 05, 06. Per Decision 7, this is a prompt synthesis quality issue -- seeds are PRD/system design and should remain flexible. The fix is enriching step prompts with extraction guidance and category checklists, NOT adding rigid sections to seed templates.
- **Batch**: 4

#### AUDIT-004: Step 16c Reviewer Has No Machine Enforcement for Roadmap Deliverable Completion
- **Severity**: CRITICAL
- **Status**: verified [Updated per R2/Decision 4/13]
- **Source**: P1-E #14, R2-C (16c analysis)
- **Owner**: validators
- **Target**: `prompts/prompt_16c_impl_reviewer.md`, `tools/specdev_tools/validation/validators/step_16.py`
- **Evidence**: No validator checks that `verdict: verified` implies roadmap deliverables are satisfied. R2-C confirms: semantic_review is not enforced, fr_coverage completeness is not checked.
- **Impact**: A reviewer can mark implementation as verified without confirming roadmap deliverables are met.
- **Proposed Fix**: Per Decision 4 (universal pairwise chain) and Decision 13 (pipeline validates validity not completeness): Add pairwise completeness check at the 16c transition -- when `review.verdict == "verified"`, verify that `fr_coverage` entries cover all `fr_refs` from the corresponding Step 14 milestone. This is part of the universal pairwise completeness enforcement.
- **Batch**: 5

#### AUDIT-005: Step 09 -> 14 Deliverable Traceability Is Partial
- **Severity**: CRITICAL
- **Status**: corroborated by R2-E-011 [Updated per R2/Decision 4/13]
- **Source**: P1-E #15, R2-E-011
- **Owner**: validators
- **Target**: `tools/specdev_tools/validation/validators/step_14.py:41-49`, `schema/09_impl_plan.schema.json`
- **Evidence**: `step_14.py` validates `source_milestones` ID existence only (E590). Does not load Step 09 deliverables to compare. R2-E-011 confirms: a Step 09 milestone with 5 deliverables can be referenced with only 2, silently dropping 3.
- **Impact**: Deliverables defined in the implementation plan can be silently dropped in the roadmap.
- **Proposed Fix**: Per Decision 4/13: Add pairwise completeness lint check (W566 INCOMPLETE_MILESTONE_DECOMPOSITION) at the 09->14 transition: for each Step 14 milestone, load `source_milestones` from Step 09, collect all deliverable IDs, verify each appears in Step 14.
- **Batch**: 5

#### AUDIT-020: All 19 Migration Templates Have Significant Schema Drift
- **Severity**: CRITICAL
- **Status**: verified
- **Source**: P1-G #2
- **Owner**: migration templates
- **Target**: `prompts/migration/template_*.md` (all 19 files)
- **Evidence**: Templates describe field names not matching current schemas. `template_charter.md` lists `project_name`, `vision`, `goals`, `constraints` -- schema requires `problem_statement`, `success_metrics`, `stakeholders`, `user_segments`.
- **Impact**: AI-assisted migrations receive incorrect field guidance, producing invalid artifacts.
- **Proposed Fix**: Regenerate all 19 templates from current schemas. Each template's "Required Changes" section should list actual schema `required` fields and property names.
- **Batch**: 8

#### AUDIT-067: No Coverage Completeness Enforcement at ANY Transition
- **Severity**: CRITICAL
- **Status**: new from R2 [Per Decision 4/13]
- **Source**: R2-C-001, R2-E-012
- **Owner**: validators
- **Target**: `tools/specdev_tools/validation/` (pipeline-wide)
- **Evidence**: The system validates that cross-references are valid (referenced ID exists) but NEVER validates that every upstream ID is covered downstream. This applies universally: capabilities can have no FRs, FRs can have no fixtures, FRs can have no milestones, milestones can have no roadmap tasks, tasks can have no implementation.
- **Impact**: The core promise of the spec-to-impl chain -- that every requirement is implemented -- is not machine-enforceable at any transition point.
- **Proposed Fix**: Per Decision 4 (universal pairwise chain) and Decision 13 (pipeline validates validity not completeness): Implement pairwise completeness checks at each transition in the COMPLETE chain from R2-C-001:
  1. capability -> FR (W-code): every capability has >= 1 FR
  2. FR -> API (W-code): every externally-observable FR has >= 1 API
  3. FR -> fixture (W-code): every FR has >= 1 fixture
  4. FR -> milestone (W-code): every FR appears in >= 1 milestone
  5. milestone -> task (W-code): every milestone FR is covered by >= 1 task
  Each check is an incremental extension of existing traceability infrastructure. No NL tooling (Decision 5) -- ID-level enforcement only.
- **Batch**: 5

#### AUDIT-068: Step 13a Is Aspirational, Not Automated
- **Severity**: CRITICAL
- **Status**: new from R2 [Per Decision 12]
- **Source**: R2-C-002, R2-C-008
- **Owner**: validators + schema
- **Target**: `prompts/prompt_13a_completeness_assessment.md`, `schema/13a_completeness_assessment.schema.json`, `tools/specdev_tools/validation/validators/step_13a.py`
- **Evidence**: The completeness assessment is an AI-generated subjective report, not a machine-computed analysis. Schema has subjective 0-10 score. No structured coverage metrics. No blocking gate prevents proceeding to Step 14 with known gaps. R2-C-008 confirms: even with redesign, the blocking gate is separately needed.
- **Impact**: The "final quality gate before implementation" is neither automated nor enforced.
- **Proposed Fix**: Per Decision 12: Redesign 13a as machine-computed coverage. Create `specdev completeness-check` linter that computes FR->API, FR->fixture, API->fixture coverage ratios. Add structured schema fields for coverage dimensions with minimum thresholds. 13a becomes aggregation point for all pairwise completeness checks (Decision 4). Add blocking threshold in step_order.json or CI gates.
- **Design Note**: step_order.json has NO gate concept today -- it defines ordering and replay policy only. Implementing a blocking gate requires NEW infrastructure design: (1) a gate schema in step_order.json or a separate gates config, (2) CLI enforcement logic that prevents step N+1 emission when gate N fails, (3) a bypass mechanism for development iteration. This is not a simple config addition but a new capability requiring dedicated design work.
- **Batch**: 5

#### AUDIT-069: Step 16c Semantic Review Not Enforced for Verified Verdict
- **Severity**: CRITICAL
- **Status**: new from R2 (codebase-verified bug)
- **Source**: R2-C-003
- **Owner**: validators
- **Target**: `tools/specdev_tools/validation/validators/step_16c.py`
- **Evidence**: Prompt says `semantic_review` with `fr_coverage` is REQUIRED when verdict=verified. Validator enters semantic_review block with `if isinstance(semantic_review, dict)` -- if absent, the block is skipped entirely. No error raised for missing semantic_review on verified verdict. Codebase-verified in r2-review.md FINDING-013.
- **Impact**: The final review gate can be passed without proving that requirements were met.
- **Proposed Fix**: Add E-code validation: when verdict=="verified", `review.semantic_review` must exist, `fr_coverage` must be non-empty, and every FR in the checklist must appear in fr_coverage.
- **Batch**: 1 (moved from Batch 7 -- this is a ~10 LOC codebase bug in step_16c.py that should not wait behind 6 batches)

---

### HIGH

#### AUDIT-006: ~1,924 LOC of Extractable/Deletable Content Across 22 Prompts
- **Severity**: HIGH
- **Status**: corroborated by R2-A [Updated per R2/Decision 1/2/9]
- **Source**: P1-A #1-#4, P1-A #6, P1-A #9, P1-B #1, R2-A-003, R2-D2-001
- **Owner**: prompts + shared_expectations
- **Target**: All 22 `prompts/prompt_*.md` files, `docs/prompts/shared_expectations.md`
- **Evidence**: R2-A refined P1 estimate: 1,312 LOC boilerplate (23%) + 500 LOC schema duplication (9%) + 69 LOC DAG duplication (1%) + 43 LOC canon duplication (1%) = 1,924 LOC (34%) removable. 1,924 LOC breakdown: ~1,312 extractable boilerplate (to shared_expectations), ~612 deletable schema duplication (Quick Reference, Field-by-Field sections). R2-D identifies 10 specific boilerplate blocks totaling ~1,032 LOC extractable to shared_expectations.md.
- **Impact**: Token budget wasted on repeated content. Maintenance: changes to shared rules require editing 22 files.
- **Proposed Fix**: Per Decision 9 (schema enrichment first): Phase 1: Enrich schema descriptions with prompt field guidance (Decision 1). Phase 2: Extract 10 boilerplate blocks (Path Variables, Hardening Protocol, Canonical Registry+Binding, Metadata Contract, Schema Authority, Coverage Closure tail, Self-Audit threshold, Output Rules, Default Role+Task, Tool Execution base) to shared_expectations.md. Phase 3: Delete schema-dup, DAG-dup, canon-dup content from prompts. Add cross-step relationship directive to shared_expectations (Decision 2).
- **Batch**: 0 (schema enrichment), then 2 (shared_expectations extraction)

#### AUDIT-007: Canonical Registry Step 12 Variant Contains Rules That Should Apply to All Prompts
- **Severity**: HIGH
- **Status**: corroborated by R2-D2-006
- **Source**: P1-A #2, R2-D2-006
- **Owner**: prompts
- **Target**: `prompts/prompt_12_ci_gates.md:163`, all 22 prompts
- **Evidence**: Step 12's Canonical Registry adds deprecated-check rules and explicit proposal field requirements absent from 21 prompts.
- **Impact**: 21 of 22 prompts lack guidance on deprecated canonical handling.
- **Proposed Fix**: Adopt Step 12's expanded version as universal standard when extracting to shared_expectations.md.
- **Batch**: 2

#### AUDIT-008: Quick Reference Is a Strict Subset of Field-by-Field AND Pure Schema Duplication
- **Severity**: HIGH
- **Status**: corroborated by R2-A-005, R2-A-007 [Updated per R2/Decision 1]
- **Source**: P1-A #7, P1-F #6-#9, R2-A-005, R2-A-007
- **Owner**: prompts
- **Target**: 17 prompts with Quick Reference sections
- **Evidence**: R2-A-005 confirms Quick Reference is pure schema duplication in 16 of 22 prompts. R2-A-007 confirms Field-by-Field sections also restate schema descriptions verbatim in 18 prompts. Both are third copies of truth (schema + Field-by-Field + Quick Reference).
- **Impact**: LLMs following Quick Reference miss required fields; creates drift when schemas evolve.
- **Proposed Fix**: Per Decision 1 (schema is sole owner): DELETE Quick Reference sections entirely from all prompts. DELETE Field-by-Field schema-duplicated content. Schema descriptions are the sole owner of field semantics. After schema enrichment (Decision 9/11), prompts contain zero field-level guidance.
- **Batch**: 0 (schema enrichment first), then 4 (prompt deletion)

#### AUDIT-009: Self-Audit Gate Score "< 0.9" Is Undefined and Unfalsifiable
- **Severity**: HIGH
- **Status**: corroborated [Updated per R2/Decision 10]
- **Source**: P1-D #1, P1-D #6, R2-D2-003
- **Owner**: prompts + shared_expectations
- **Target**: All 22 prompts, `docs/agents/agents.md:30`
- **Evidence**: R2-D2-003 confirms: Self-Audit Gate naturally decomposes into three concerns -- threshold protocol (universal), gating items (step-specific), coverage closure (universal).
- **Impact**: Gate is non-deterministic.
- **Proposed Fix**: Per Decision 10 (3-concern decomposition): (1) Extract threshold protocol to shared_expectations.md: replace "score < 0.9" with deterministic boolean "If ANY gating item below cannot be satisfied, enter Clarify mode." (2) Keep gating items per-prompt (step-specific). (3) Extract coverage closure tail to shared_expectations.md. Keep coverage closure body per-prompt.
- **Batch**: 6

#### AUDIT-010: Self-Audit Gate Conflates Input Sufficiency with Output Quality
- **Severity**: HIGH
- **Status**: corroborated [Updated per R2/Decision 10]
- **Source**: P1-D #2, P1-A #5, R2-D Section 3
- **Owner**: prompts
- **Target**: All 22 prompts
- **Evidence**: Gate items mix input-sufficiency checks with output-quality checks and anti-pattern checks. No validator references Self-Audit Gate.
- **Impact**: LLMs unclear about WHEN to evaluate the gate.
- **Proposed Fix**: Per Decision 10: Clarify gate purpose as pre-emission input sufficiency check (gating items). Move anti-pattern checks to Negative Constraints section. Move output-quality checks to Coverage Closure body (step-specific).
- **Batch**: 6

#### AUDIT-011: Coverage Closure Structurally Coupled to Self-Audit Gate
- **Severity**: HIGH
- **Status**: verified [Updated per R2/Decision 10]
- **Source**: P1-D #9, R2-D2-003
- **Owner**: prompts
- **Target**: All 22 prompts
- **Evidence**: R2-D2-003 confirms the clean split: threshold + gating items are pre-emit; coverage closure body + tail are post-generation.
- **Impact**: Conflation obscures two separate checks with different evaluation timing.
- **Proposed Fix**: Per Decision 10: Promote Coverage Closure to sibling heading. Self-Audit Gate = input sufficiency = Clarify/Emit decision. Coverage Closure = output completeness = post-generation validation.
- **Batch**: 6

#### AUDIT-013: No Lint for FR -> API Coverage Completeness (Steps 04 -> 05)
- **Severity**: HIGH
- **Status**: verified [Updated per R2/Decision 4/13]
- **Source**: P1-E #9
- **Owner**: validators
- **Target**: `tools/specdev_tools/validation/traceability_closure.py`
- **Evidence**: FR->API link covered only by W592 aggregate threshold and E590 generic broken-reference. No per-FR coverage check.
- **Impact**: Individual FRs can lack API coverage without lint warning.
- **Proposed Fix**: Per Decision 4 (universal pairwise chain): Add W564 UNCOVERED_FR_API as part of the pairwise completeness enforcement at the FR->API transition. Part of the universal chain: cap->FR->API->fixture->milestone->task.
- **Batch**: 5

#### AUDIT-014: Step 09 Milestone Schema Lacks `depends_on` Field
- **Severity**: HIGH
- **Status**: verified
- **Source**: P1-E #1
- **Owner**: schema
- **Target**: `schema/09_impl_plan.schema.json:34-86`
- **Evidence**: Step 09 milestones have no `depends_on` field despite prompt guidance requiring explicit dependency ordering.
- **Impact**: Milestone dependency relationships are inexpressible in schema.
- **Proposed Fix**: Add optional `depends_on` array to Step 09 milestone schema. Add cycle-detection validator.
- **Batch**: 0

#### AUDIT-015: Step 14 Tasks Lack Direct FR Binding
- **Severity**: HIGH
- **Status**: verified [Updated per R2/Decision 4]
- **Source**: P1-E #2
- **Owner**: schema
- **Target**: `schema/14_roadmap.schema.json:87-183`
- **Evidence**: Task schema has no `fr_refs` or `trace` field. For a milestone with 10 FRs and 15 tasks, no machine-checkable way to verify every FR has a task.
- **Impact**: FR-to-task coverage within milestones is unverifiable by lint.
- **Proposed Fix**: Per Decision 4: Add optional `fr_refs` array to task objects. Add pairwise completeness validator checking every FR in `milestone.fr_refs` is referenced by at least one task. Part of the universal chain.
- **Note**: The schema change portion (adding `fr_refs` to Step 14 task schema) should be done in Batch 0 with other schema structural changes. The pairwise validation logic stays in Batch 5. If Batch 5 introduces schema changes after prompts have already been updated (Batch 4), those prompts may reference fields that do not yet exist.
- **Batch**: 5 (schema change in Batch 0; validation logic in Batch 5)

#### AUDIT-016: Semantic Drift Has No Dedicated Validator
- **Severity**: HIGH
- **Status**: verified [Updated per R2/Decision 5]
- **Source**: P1-E #3, P1-E #7, R2-E Section 1
- **Owner**: validators + prompts
- **Target**: `tools/specdev_tools/validation/` (entire directory)
- **Evidence**: No validator checks description consistency for traced IDs across steps. R2-E documents drift risk at each transition: HIGH for cap->FR (Step 04), MEDIUM-HIGH for FR->API (Step 05).
- **Impact**: An API can claim to trace to `fr-user-login` while implementing different behavior.
- **Proposed Fix**: Per Decision 5 (no NL tooling): Strengthen prompt guidance for Steps 05, 06, 07 to say "use exact description text from Step 04 for traced FRs." Practically: the FR ID and its `statement` must appear verbatim in the trace `note` field. ID-level enforcement only. No semantic comparison validators.
- **Batch**: 4

#### AUDIT-017: `docs_policy` Has Zero Functional Consumers After docs_lint.py Removal
- **Severity**: HIGH
- **Status**: verified
- **Source**: P1-C #1
- **Owner**: config + schema
- **Target**: `spec/common/seed_manifest.json:58-82`, `schema/seed_manifest.schema.json:115-169`
- **Evidence**: Only `step_16.py:180` reads `doc_paths` sub-field. All other fields have zero consumers.
- **Impact**: 22 lines dead config + ~55 lines dead schema definition.
- **Proposed Fix**: Extract `doc_paths` to top-level. Remove entire `docs_policy` block and schema definition. Update `step_16.py:180`.
- **Migration Note**: Removing `docs_policy` is a BREAKING change for host repos that have `docs_policy` in their seed_manifest.json. Requires: (1) update `tests/fixtures/seed_manifest/` test fixtures, (2) changelog entry documenting the breaking change, (3) migration guide for host repos.
- **Batch**: 1

#### AUDIT-018: Seed Order, Context To Ingest, and Extraction Intent Triple Redundancy
- **Severity**: HIGH
- **Status**: verified
- **Source**: P1-C #7
- **Owner**: prompts
- **Target**: `prompts/prompt_00_project_charter.md:39-55`, similarly in prompts 01-04
- **Evidence**: Steps 00-04 have three overlapping sections for seed references. ~72 lines of redundant content.
- **Impact**: Maintenance risk: updating seed references requires 3 edits.
- **Proposed Fix**: Merge Seed Order and Context To Ingest into Extraction Intent for steps 00-04.
- **Batch**: 2

#### AUDIT-019: Extraction Mandate Covers Only 3 of 22 Steps
- **Severity**: HIGH
- **Status**: verified [Updated per R2/Decision 4]
- **Source**: P1-E #4
- **Owner**: prompts
- **Target**: Steps 05, 08, 09 prompts
- **Evidence**: Only Steps 04, 14, 16a have hard "every upstream ID must be consumed" rules.
- **Impact**: Requirements can silently drop at Steps 05, 08, 09.
- **Proposed Fix**: Per Decision 4: Add Extraction Mandates as the prompt-level complement to pairwise completeness validators. Step 05: "Every FR with observable external behavior must map to >=1 API." Step 08: "Every high-priority FR must have >=1 fixture." Step 09: "Every capability must appear in >=1 milestone deliverable."
- **Batch**: 4

#### AUDIT-021: Missing Migration Templates for Steps 16a, 16b, 16c
- **Severity**: HIGH
- **Status**: verified
- **Source**: P1-G #1
- **Owner**: migration templates
- **Target**: `tools/specdev_tools/core/constants.py:15-35`, `prompts/migration/`
- **Evidence**: `STEP_TO_TEMPLATE` has no entries for 16a/16b/16c.
- **Impact**: `specdev align prompts` cannot generate migration guidance for Trinity Loop artifacts.
- **Proposed Fix**: Create `template_impl_planner.md`, `template_impl_coder.md`, `template_impl_reviewer.md`. Add mappings.
- **Batch**: 8

#### AUDIT-022: 00 -> 01 Lint Link Misses Success Metrics
- **Severity**: HIGH
- **Status**: verified
- **Source**: P1-E #8
- **Owner**: validators
- **Target**: `tools/specdev_tools/validation/traceability_closure.py:82-97`
- **Evidence**: E560 checks `goal_id` maps to capability but `success_metrics` not checked.
- **Impact**: Success metrics can be silently dropped from traceability chain.
- **Proposed Fix**: Extend E560 to check each `success_metric` ID is traced.
- **Batch**: 7

#### AUDIT-023: `allowed_upstream_dependencies` Is 275 Lines of Fully Derivable Data
- **Severity**: HIGH
- **Status**: verified [Updated per Decision 3]
- **Source**: P1-C #4
- **Owner**: config
- **Target**: `tools/step_order.json:41-315`
- **Evidence**: Under `strict_waterfall` policy, the field is fully derivable. 5 consumers.
- **Impact**: 275 lines of redundant data that must be kept in sync.
- **Proposed Fix**: Per Decision 3: Add `derive_allowed_upstream(step_id)` function. Migrate 5 consumers. Delete the JSON field. Update `step_order.schema.json`.
- **Migration Note**: All 5 consumers (cli.py, hallucination_lint.py, extraction_intent_check.py, dependency_order_lint.py, dag_lint.py) must be migrated ATOMICALLY. If any consumer is missed, it will fail with a KeyError at runtime. Requires test coverage for all 5 consumers verifying they work with derived data.
- **Batch**: 1

#### AUDIT-024: `_collect_required_seeds` Conflates Ordering with Membership
- **Severity**: HIGH
- **Status**: verified
- **Source**: P1-C #8, P1-C #14
- **Owner**: validators
- **Target**: `tools/specdev_tools/validation/seed_lint.py:61-62`
- **Evidence**: Function unions `global_seed_order` into every step's requirements. Step 01 incorrectly requires `seed-tech-stack`.
- **Impact**: Seed validation enforces false requirements on steps.
- **Proposed Fix**: Change to use `global_seed_order` for ordering only, not membership expansion.
- **Batch**: 7

#### AUDIT-070: Evidence Quality Not Validated in Trinity Loop
- **Severity**: HIGH
- **Status**: new from R2
- **Source**: R2-C-004
- **Owner**: validators
- **Target**: `tools/specdev_tools/validation/validators/step_16.py`
- **Evidence**: Validator checks evidence EXISTS on verified items (E301) but does not validate evidence quality. An evidence string of "done" (>=20 chars with padding) passes validation. Prompt demands verbatim stdout/stderr with success markers.
- **Impact**: Requirements can be marked "verified" with fabricated or insufficient evidence.
- **Proposed Fix**: Add evidence content validation: check for success marker keywords or structured evidence_binding.
- **Batch**: 7

#### AUDIT-071: Schema Must Be Sole Owner of All Field-Level Semantics
- **Severity**: HIGH
- **Status**: new from R2 [Per Decision 1/9/11]
- **Source**: R2-F2-001, R2-F2-002, R2-F2-008
- **Owner**: schemas
- **Target**: All step schemas (7 analyzed in detail, all 22 need review)
- **Evidence**: R2-F identifies 58 of 97 field-level guidance items (60%) as self-contained and movable to descriptions. Current descriptions are too thin for semantic content fields -- `statement` in 04_fr_list says "minimum 20 characters" with no quality guidance. R2-F2-008: the hardest LLM fields (statement, acceptance_criteria.text, measurement_method, language) have the thinnest descriptions.
- **Impact**: LLMs reading only schemas produce structurally valid but semantically weak output.
- **Proposed Fix**: Per Decision 1/9/11: Enrich all schema descriptions using three-tier DEPTH model (Tier 1: 40-80 chars for simple fields; Tier 2: 80-150 for structured; Tier 3: 150-250+ for semantic content). Tier 3 must be rich enough to replace all prompt Field-by-Field guidance. This MUST happen before prompt extraction (Decision 9). R2-F Section 6 provides 10 concrete migration examples.
- **Scope**: Prioritize Tier 3 (semantic/LLM-facing) fields first, then Tier 2 (structured), then Tier 1 (simple). Not all 925 descriptions need enrichment in Batch 0 -- focus on fields where prompts currently duplicate guidance. This prevents Batch 0 from becoming a multi-week blocker.
- **Batch**: 0

#### AUDIT-072: Glossary Is Structurally Decorative -- No Machine Enforcement
- **Severity**: HIGH
- **Status**: new from R2 [Per Decision 6]
- **Source**: R2-B-007, R2-E-002, R2-G-006
- **Owner**: canon + validators + prompt
- **Target**: All prompts for Steps 04-07; `canon/manifest.json`; `tools/specdev_tools/canonical/`
- **Evidence**: Every downstream prompt tells LLM to align with glossary terms, but: no schema field requires glossary term_id references, no validator checks terminological alignment, canonical_lint checks canonical refs but not glossary terms. R2-G-006: "Once glossary terms are in canon, canonical-lint enforces automatically."
- **Impact**: Terminological drift across the spec chain. Same concept can have different names in different steps.
- **Proposed Fix**: Per Decision 6: Step 03 becomes canon population step emitting `cn:project:` namespace canons. Once project terms are in canon, canonical-lint automatically enforces them in all downstream steps. No NL tooling needed (Decision 5). Requires R2-G-005 (canon-accept tooling) as prerequisite.
- **Batch**: 3

#### AUDIT-073: No Tooling to Accept canonical_proposals into Registry
- **Severity**: HIGH
- **Status**: new from R2
- **Source**: R2-G-005
- **Owner**: tooling
- **Target**: `tools/specdev_tools/canonical/` (new command needed)
- **Evidence**: `canonical_proposals` schema exists in `step_base.schema.json`. Every step can propose new terms. But no CLI command promotes proposals into `canon/manifest.json`. This is the critical missing piece for glossary->canon merge (Decision 6).
- **Impact**: Pipeline-populated canons cannot be integrated into the registry.
- **Proposed Fix**: Build `specdev canon-accept --from spec/03_glossary.json` command. Schema changes: none needed (infrastructure is 80% built).
- **Batch**: 3

#### AUDIT-074: No Canon Namespace Separation Between Toolkit and Project
- **Severity**: HIGH
- **Status**: new from R2
- **Source**: R2-G-002
- **Owner**: canon
- **Target**: `canon/manifest.json` (all 74 entries)
- **Evidence**: All entries use `cn:core:`. Pattern supports `cn:project:` but none are used. No convention documented.
- **Impact**: Cannot distinguish toolkit-mechanical canons from project-specific canons. Blocks Decision 6 implementation.
- **Proposed Fix**: Establish convention: `cn:core:` = toolkit (pre-populated), `cn:project:` = pipeline-populated from Step 03. Document in canon README. Move 18 auth-domain-specific entries to starter-kit/examples.
- **Batch**: 3

#### AUDIT-075: Charter Schema Does Not Require in_scope, out_of_scope, assumptions, or risks
- **Severity**: HIGH
- **Status**: new from R2
- **Source**: R2-B-003
- **Owner**: schema
- **Target**: `schema/00_charter.schema.json`
- **Evidence**: Schema requires only `problem_statement`, `success_metrics`, `stakeholders`, `user_segments`. Prompt completeness checklist treats `in_scope` (min 3), `out_of_scope`, `assumptions`, `risks` as essential. Schema allows valid charter without any scope boundaries or risk register.
- **Impact**: Root anchor for every downstream step can pass validation with no scope boundaries.
- **Proposed Fix**: Add `in_scope`, `out_of_scope`, `assumptions`, `risks` to schema `required` array.
- **Migration Note**: This is a BREAKING schema change. Existing charters missing these fields will fail validation. Migration: update test fixtures at `tests/fixtures/step_00/`. Breaking for host repos -- requires changelog entry and migration guide.
- **Batch**: 0

---

### MEDIUM

#### AUDIT-012: 16a/16b/16c Have Redundant Duplicate Self-Audit Gate Headings
- **Severity**: MEDIUM
- **Status**: verified [Updated per Decision 10]
- **Source**: P1-D #3
- **Owner**: prompts
- **Target**: `prompts/prompt_16a_impl_planner.md`, `prompts/prompt_16b_impl_coder.md`, `prompts/prompt_16c_impl_reviewer.md`
- **Evidence**: Each Trinity Loop prompt has TWO Self-Audit Gate headings. First contains only "score < 0.9" with zero step-specific items.
- **Impact**: LLM confusion about which gate to evaluate.
- **Proposed Fix**: Per Decision 10: Remove "(Score Threshold)" headings. Merge threshold into shared_expectations reference.
- **Batch**: 6

#### AUDIT-025: 46 of 53 Docs Are Never Referenced by Any Prompt
- **Severity**: MEDIUM
- **Status**: corroborated
- **Source**: P1-C #9, P1-C #15, P1-G #12, P1-G #5
- **Owner**: config
- **Target**: `docs/**/*.md` (53 files), `prompts/prompt_*.md` (22 files)
- **Evidence**: Only 7 docs referenced by prompts.
- **Impact**: AI agents lack context that would improve output quality.
- **Proposed Fix**: Create `step_docs` map. Surface in prompts as optional context.
- **Batch**: 8

#### AUDIT-026: shared_expectations.md Lacks Documentation Resource Guidance
- **Severity**: MEDIUM
- **Status**: corroborated [Updated per R2/Decision 2]
- **Source**: P1-G #16, P1-G #12, R2-D2-002
- **Owner**: shared_expectations
- **Target**: `docs/prompts/shared_expectations.md`
- **Evidence**: R2-D2-002: current 51-LOC document is referenced by only 8/22 prompts and its content is redundant with inline boilerplate. Effectively dead weight.
- **Impact**: Agents cannot discover relevant documentation.
- **Proposed Fix**: Per Decision 2: Redesign shared_expectations.md per R2-D Section 4 (~82 LOC, 11 sections). Establish explicit inclusion model: each prompt opens with inheritance reference and precedence rule.
- **Batch**: 2

#### AUDIT-027: No Granularity Guidance for Steps 04, 05, 07
- **Severity**: MEDIUM
- **Status**: verified
- **Source**: P1-B #6
- **Owner**: prompts
- **Target**: `prompts/prompt_04_functional_requirements.md`, `prompts/prompt_05_interface_contracts.md`, `prompts/prompt_07_nfrs.md`
- **Evidence**: Step 04 says "one behavior" but does not define what constitutes "one behavior."
- **Impact**: Wildly inconsistent outputs between LLM runs.
- **Proposed Fix**: Add granularity heuristics.
- **Batch**: 4

#### AUDIT-028: Generic Role Definition for 14 of 22 Steps
- **Severity**: MEDIUM
- **Status**: verified
- **Source**: P1-B #2, R2-D2-005
- **Owner**: prompts
- **Target**: 14 prompts using "senior specification author and validator"
- **Evidence**: R2-D2-005: 18 of 22 use generic role; 4 have specialized roles (11, 16, 16a-c).
- **Impact**: Generic role provides no synthesis context.
- **Proposed Fix**: Give each step a role priming its reasoning mode. Extract default role to shared_expectations; specialized prompts override.
- **Batch**: 4

#### AUDIT-029: No Weak-vs-Strong Examples in 19 of 22 Prompts
- **Severity**: MEDIUM
- **Status**: corroborated by R2-A-008
- **Source**: P1-B #8, R2-A-008
- **Owner**: prompts
- **Target**: All prompts except 11, 13
- **Evidence**: R2-A-008 confirms Step 11 is ONLY Discovery Phase prompt with examples. Steps 04-08 would benefit most.
- **Impact**: LLMs cannot calibrate output quality.
- **Proposed Fix**: Add 3-5 row weak-vs-strong tables to Steps 04, 05, 06, 07, 08.
- **Batch**: 4

#### AUDIT-030: Coverage Closure Checklist Is Mechanical, Not Reasoning-Oriented
- **Severity**: MEDIUM
- **Status**: verified
- **Source**: P1-B #9
- **Owner**: prompts
- **Target**: All 22 prompts' Coverage Closure sections
- **Evidence**: Universal items are traceability checks, not reasoning checks.
- **Impact**: Structural completeness verified but logical completeness not.
- **Proposed Fix**: Add 2-3 step-specific reasoning verification items per Coverage Closure.
- **Batch**: 4

#### AUDIT-031: Extraction Intent Lacks Priority Grouping
- **Severity**: MEDIUM
- **Status**: corroborated by R2-A-010
- **Source**: P1-B #10, R2-A-010
- **Owner**: prompts
- **Target**: Late-stage prompts (12, 14, 15, 16, 16a, 16b, 16c)
- **Evidence**: Step 14 lists 16 upstream artifacts; Step 16b lists 20. Each gets one-line description with equal weight. R2-A-010: granularity varies across prompts.
- **Impact**: Shallow processing of critical inputs.
- **Proposed Fix**: Group extraction intents into "Primary Sources" and "Reference Sources." Standardize format per R2-A-010.
- **Batch**: 4

#### AUDIT-032: Trinity Loop Evidence Binding Is Partially Prompt-Enforced Only
- **Severity**: MEDIUM
- **Status**: verified
- **Source**: P1-E #6
- **Owner**: validators
- **Target**: `tools/specdev_tools/validation/validators/step_16.py`
- **Evidence**: `evidence` on verified actions is NOT schema-required. `ci_status: green` for `verdict: verified` has no cross-field validation beyond E303.
- **Impact**: Artifacts with missing evidence on verified actions pass schema validation.
- **Proposed Fix**: Add validator: (1) verified actions have `evidence` with non-empty `content`, (2) `verdict: verified` requires `fixture_status.ci_status: green`.
- **Batch**: 7

#### AUDIT-033: Step 14 Does Not Trigger Trace Matrix Update
- **Severity**: MEDIUM
- **Status**: verified
- **Source**: P1-E #5
- **Owner**: validators
- **Target**: `tools/specdev_tools/validation/matrix.py:170-305`
- **Evidence**: Trace matrix built from Steps 04/05/07/08 only. Step 14 `fr_refs` not included.
- **Impact**: Single-pane traceability view incomplete.
- **Proposed Fix**: Add "milestone_coverage" column to trace matrix.
- **Batch**: 7

#### AUDIT-034: No Validator Enforces Tech Stack Consistency Across Steps 02, 09, 14
- **Severity**: MEDIUM
- **Status**: corroborated by R2-B-015, R2-E-003
- **Source**: P1-C #10, P1-C #13, R2-B-015, R2-E-003
- **Owner**: validators
- **Target**: Prompts for Steps 04-07; validators
- **Evidence**: R2-B-015: no downstream step validates tech stack coherence after Step 02. R2-E-003: Steps 09 and 14 both have `tech_stack` with identical structure; prompt 14 says "copy from Step 09" but no validator checks.
- **Impact**: Technology decisions drift silently across the pipeline.
- **Proposed Fix**: Add tech-stack coherence check or integrate into spec-quality-lint.
- **Note**: See also AUDIT-082 (Step 02a downstream consumption). Both address delivery baseline information not flowing downstream. Fixes are complementary.
- **Batch**: 7

#### AUDIT-035: `nested_order` Provides Zero Value Beyond `global_seed_order`
- **Severity**: MEDIUM
- **Status**: verified
- **Source**: P1-C #2
- **Owner**: config
- **Target**: `spec/common/seed_manifest.json:11-19`
- **Evidence**: Single entry "foundation" containing same 2 seeds as `global_seed_order`. Redundant.
- **Impact**: 9 lines dead config.
- **Proposed Fix**: Delete `nested_order` from data, schema, and consumer.
- **Batch**: 1

#### AUDIT-036: shared_expectations.md Referenced by Only 8 of 22 Prompts
- **Severity**: MEDIUM
- **Status**: SUBSUMED by AUDIT-026 -- resolved via AUDIT-026, no separate action needed
- **Source**: P1-A #10, P1-A #11, R2-D2-002
- **Owner**: prompts
- **Target**: `docs/prompts/shared_expectations.md`, 14 prompts not referencing it
- **Evidence**: R2-D2-002: 8 prompts reference it but still contain all boilerplate inline.
- **Impact**: Inconsistent guidance.
- **Proposed Fix**: Resolved via AUDIT-026 (shared_expectations redesign). After extraction (AUDIT-006/026), universal reference with explicit inclusion model will be added to all 22 prompts.
- **Batch**: N/A (subsumed by AUDIT-026, Batch 2)

#### AUDIT-037: Step 13 Gate Items Are Anti-Pattern Checks, Not Input-Sufficiency Checks
- **Severity**: MEDIUM
- **Status**: verified
- **Source**: P1-D #7
- **Owner**: prompts
- **Target**: `prompts/prompt_13_extension_generator.md:72-77`
- **Evidence**: Five gate items phrased as output review criteria.
- **Impact**: Gate conflates input-sufficiency with output review.
- **Proposed Fix**: Move anti-pattern items to Negative Constraints. Replace with input-sufficiency checks.
- **Batch**: 6

#### AUDIT-038: Step 05 Lacks API Design Reasoning Framework
- **Severity**: MEDIUM
- **Status**: verified
- **Source**: P1-B #11
- **Owner**: prompts
- **Target**: `prompts/prompt_05_interface_contracts.md:48-53`
- **Evidence**: No guidance on resource naming, URL structure, pagination, error schema.
- **Impact**: Inconsistent API designs across runs.
- **Proposed Fix**: Add "REST Design Heuristics" section.
- **Batch**: 4

#### AUDIT-039: Step 06 Lacks Systematic Invariant Discovery Method
- **Severity**: MEDIUM
- **Status**: verified
- **Source**: P1-B #12
- **Owner**: prompts
- **Target**: `prompts/prompt_06_invariants.md:55-59`
- **Evidence**: Lists categories but no systematic discovery method.
- **Impact**: LLMs miss implicit invariants.
- **Proposed Fix**: Add invariant discovery checklist.
- **Batch**: 4

#### AUDIT-040: Output Contract Examples Contradict Prompt Guidance
- **Severity**: MEDIUM
- **Status**: corroborated by R2-B-010, R2-B-011 [Updated per Decision 1]
- **Source**: P1-B #14, R2-B-010, R2-B-011
- **Owner**: prompts
- **Target**: `prompts/prompt_07_nfrs.md:190`, `prompts/prompt_01_capabilities.md:186`, `prompts/prompt_06_invariants.md:177-180`
- **Evidence**: Step 07 example uses "automated monitoring" despite banning generic phrases. Step 06 example uses `language: "text"` despite guidance to use jsonlogic/CEL.
- **Impact**: LLMs following examples over prose rules produce invalid output.
- **Proposed Fix**: Per Decision 1: DELETE Quick Reference and Field-by-Field sections. Fix remaining Output Contract examples to comply with schema constraints. Reduce Output Contracts to minimal valid examples (15-25 LOC max).
- **Batch**: 0 (schema enrichment), then 4 (prompt fixes)

#### AUDIT-041: Prompt 09 Quick Reference Omits Multiple Required Fields
- **Severity**: MEDIUM
- **Status**: verified [Updated per Decision 1]
- **Source**: P1-F #6, P1-F #9
- **Owner**: prompts
- **Target**: `prompts/prompt_09_impl_plan.md:133-134`
- **Evidence**: Quick Reference omits `milestones`, `trace`, `deliverables`, `status`.
- **Impact**: LLMs following Quick Reference produce invalid JSON.
- **Proposed Fix**: Per Decision 1: DELETE Quick Reference section entirely. Schema is the authoritative source.
- **Batch**: 0 (after schema enrichment)

#### AUDIT-042: Prompt 00 Quick Reference Omits `stakeholders` and `user_segments`
- **Severity**: MEDIUM
- **Status**: verified [Updated per Decision 1]
- **Source**: P1-F #7
- **Owner**: prompts
- **Target**: `prompts/prompt_00_project_charter.md:142`
- **Evidence**: Omits required schema fields.
- **Impact**: LLMs may omit required fields.
- **Proposed Fix**: Per Decision 1: DELETE Quick Reference section entirely.
- **Batch**: 0

#### AUDIT-043: Prompt 05 Quick Reference Omits `interface_ref`
- **Severity**: MEDIUM
- **Status**: verified [Updated per Decision 1]
- **Source**: P1-F #8
- **Owner**: prompts
- **Target**: `prompts/prompt_05_interface_contracts.md:134`
- **Evidence**: Omits `interface_ref` from required fields.
- **Impact**: LLMs omit `interface_ref`, causing validation failure.
- **Proposed Fix**: Per Decision 1: DELETE Quick Reference section entirely.
- **Batch**: 0

#### AUDIT-044: Prompt 16 Output Contract Missing `canonical_refs_used`
- **Severity**: MEDIUM
- **Status**: verified
- **Source**: P1-F #10
- **Owner**: prompts
- **Target**: `prompts/prompt_16_impl_context.md:265-365`
- **Evidence**: Output Contract JSON omits `canonical_refs_used` required by `step_base.schema.json`.
- **Impact**: LLMs produce invalid JSON.
- **Proposed Fix**: Add `"canonical_refs_used": []` to Output Contract example.
- **Batch**: 4

#### AUDIT-045: Migration Templates Lack Reference to Step Prompts
- **Severity**: MEDIUM
- **Status**: corroborated
- **Source**: P1-G #11, P1-G #14, P1-G #18
- **Owner**: migration templates
- **Target**: `prompts/migration/template_*.md` (all 19)
- **Evidence**: Templates do not reference corresponding step prompts.
- **Impact**: Migrations produce lower-quality output than fresh generation.
- **Proposed Fix**: Add "Full Generation Reference" section. Enhance `_render_prompt()`.
- **Batch**: 8

#### AUDIT-046: template_frs.md References Wrong Artifact Filename
- **Severity**: MEDIUM
- **Status**: verified
- **Source**: P1-G #3
- **Owner**: migration templates
- **Target**: `prompts/migration/template_frs.md:33`
- **Evidence**: References `spec/04_functional_requirements.json`; correct is `spec/04_fr_list.json`.
- **Impact**: Validation command in template will fail.
- **Proposed Fix**: Change to `spec/04_fr_list.json`.
- **Batch**: 8

#### AUDIT-047: workflow_bootstrap_legacy.md Uses Outdated Patterns
- **Severity**: MEDIUM
- **Status**: verified
- **Source**: P1-G #8
- **Owner**: docs
- **Target**: `docs/developers/workflows/workflow_bootstrap_legacy.md`
- **Evidence**: Pre-Clarify/Emit protocol. Wrong artifact names.
- **Impact**: Users following this workflow produce artifacts using wrong conventions.
- **Proposed Fix**: Rewrite to use current seed paths and two-phase protocol.
- **Batch**: 8

#### AUDIT-048: workflow_feature_extension.md Uses Pre-Clarify/Emit Patterns
- **Severity**: MEDIUM
- **Status**: verified
- **Source**: P1-G #9
- **Owner**: docs
- **Target**: `docs/developers/workflows/workflow_feature_extension.md`
- **Evidence**: Instructs copying generic prompts rather than using canonical step prompts.
- **Impact**: Feature extensions bypass Self-Audit Gate and Coverage Closure.
- **Proposed Fix**: Update to reference canonical step prompts.
- **Batch**: 8

#### AUDIT-049: Migration Templates Use No Interpolation Variables Despite ADR
- **Severity**: MEDIUM
- **Status**: verified
- **Source**: P1-G #4
- **Owner**: migration templates
- **Target**: `prompts/migration/template_*.md` (all 19)
- **Evidence**: ADR describes `{{VAR}}` syntax. Zero templates use it.
- **Impact**: Templates cannot be context-aware.
- **Proposed Fix**: Implement interpolation or update ADR.
- **Batch**: 8

#### AUDIT-076: Verdict Enum Mismatch Between Prompt and Validator
- **Severity**: MEDIUM
- **Status**: new from R2 (codebase-verified bug)
- **Source**: R2-C-005
- **Owner**: prompt + validator
- **Target**: `prompts/prompt_16c_impl_reviewer.md` line 131, `tools/specdev_tools/validation/validators/step_16c.py` line 13
- **Evidence**: Prompt defines verdicts as "verified/deferred/rejected". Validator: "verified/needs_work/blocked/deferred". "rejected" not in validator; "needs_work"/"blocked" not in prompt.
- **Impact**: AI using "rejected" will fail validation with unhelpful error.
- **Proposed Fix**: Synchronize. The validator's set is likely correct (more granular); update prompt.
- **Batch**: 1 (moved from Batch 7 -- simple codebase bug, verdict enum mismatch with no dependencies)

#### AUDIT-077: No Governance-to-CI Cross-Validation
- **Severity**: MEDIUM
- **Status**: new from R2
- **Source**: R2-C-006
- **Owner**: validators
- **Target**: Steps 10 -> 12 transition
- **Evidence**: Step 10 defines `pr_rules`. Step 12 defines CI jobs. Nothing validates every pr_rule has a corresponding CI job.
- **Impact**: Governance is advisory without CI enforcement.
- **Proposed Fix**: Add cross-step linter verifying pr_rules -> CI job mapping.
- **Batch**: 7

#### AUDIT-078: No API-to-Threat Coverage Validation
- **Severity**: MEDIUM
- **Status**: new from R2
- **Source**: R2-C-007
- **Owner**: validators
- **Target**: `tools/specdev_tools/validation/validators/step_11.py`
- **Evidence**: Prompt says "every public API must have at least one threat." Validator checks targets are valid but not that every API is covered.
- **Impact**: Security gaps in threat model undetected.
- **Proposed Fix**: Add coverage check loading API IDs from Step 05.
- **Batch**: 7

#### AUDIT-079: Step 00 Extraction Intent Narrower Than seed_tech_stack Structure
- **Severity**: MEDIUM
- **Status**: new from R2 [Per Decision 7]
- **Source**: R2-B-002
- **Owner**: prompts
- **Target**: `prompts/prompt_00_project_charter.md` lines 55-56
- **Evidence**: Extraction intent says "Hardware/legacy constraints" but seed_tech_stack contains security boundaries (4.1), distribution constraints (4.2), resilience requirements (4.3), dependency inventory (5.x).
- **Impact**: LLM extracts only hardware/legacy, missing security posture and resilience.
- **Proposed Fix**: Per Decision 7 (prompt synthesis issue, not seed issue): Expand extraction intent to cover all seed_tech_stack sections.
- **Batch**: 4

#### AUDIT-080: Step 01 Coverage Closure Does Not Check user_segments JTBD
- **Severity**: MEDIUM
- **Status**: new from R2
- **Source**: R2-B-004
- **Owner**: prompts
- **Target**: `prompts/prompt_01_capabilities.md` lines 78-81
- **Evidence**: Coverage Closure checks goals and success_metrics but not `user_segments[].jobs_to_be_done`.
- **Impact**: Capabilities implied by user needs but not business goals silently omitted.
- **Proposed Fix**: Add JTBD coverage check to Coverage Closure.
- **Batch**: 4

#### AUDIT-081: Step 01 Lacks Cross-Cutting Capability Discovery Guidance
- **Severity**: MEDIUM
- **Status**: new from R2
- **Source**: R2-B-005
- **Owner**: prompts
- **Target**: `prompts/prompt_01_capabilities.md`
- **Evidence**: No guidance on cross-cutting capabilities (security, observability, audit, error handling).
- **Impact**: Cross-cutting capabilities left to LLM inference.
- **Proposed Fix**: Add "Cross-Cutting Capability Checklist" section.
- **Batch**: 4

#### AUDIT-082: Step 02a Has Near-Zero Downstream Consumption
- **Severity**: MEDIUM
- **Status**: new from R2
- **Source**: R2-B-006
- **Owner**: config
- **Target**: `tools/step_order.json` downstream_consumers["02a"]
- **Evidence**: downstream_consumers shows 02a feeds ONLY Step 12. Steps 04-07 prompts reference 02a in Extraction Intent but 02a not listed as feeding them.
- **Impact**: Delivery baseline invisible to Steps 04-07 that need it.
- **Proposed Fix**: Update downstream_consumers to reflect actual consumption, or remove 02a from those prompts' Extraction Intent.
- **Note**: See also AUDIT-034 (tech stack consistency). Both address the same root issue of delivery baseline information not flowing downstream. Fixes are complementary.
- **Batch**: 1

#### AUDIT-083: Step 06 References Glossary Lifecycle States That Don't Exist
- **Severity**: MEDIUM
- **Status**: new from R2 (codebase-verified)
- **Source**: R2-B-009
- **Owner**: prompt + schema
- **Target**: `prompts/prompt_06_invariants.md` lines 50, 56, 72; `schema/03_glossary.schema.json`
- **Evidence**: Prompt references "entities with lifecycle stages defined in the glossary" but glossary schema has no `lifecycle_states` field. Terms have only term_id, term, definition, domain, units.
- **Impact**: Prompt directs LLM to extract structure that doesn't exist; leads to confusion or hallucination.
- **Proposed Fix**: Rewrite prompt_06 to derive state transition invariants from "entity state fields described in FR preconditions/postconditions" instead of non-existent glossary structure.
- **Batch**: 4

#### AUDIT-084: Traceability Required by Prompt but Optional in Step 05 Schema
- **Severity**: MEDIUM
- **Status**: new from R2
- **Source**: R2-B-013
- **Owner**: schema
- **Target**: `schema/05_interface_contracts.schema.json`
- **Evidence**: Prompt says trace links are required. Schema does NOT require `trace` on API items -- only api_id, name, version, protocol, owner, interface_ref are required.
- **Impact**: Schema-valid but trace-free API contract breaks integrity chain.
- **Proposed Fix**: Add `trace` to the required array in API item schema.
- **Migration Note**: This is a BREAKING schema change. Adding `trace` to Step 05 required array will fail validation for existing API contract specs missing trace links. Migration: verify `tests/fixtures/step_05/` fixtures include trace. Breaking for host repos -- requires changelog entry.
- **Batch**: 0

#### AUDIT-085: Acceptance Criteria Duplicated Between Steps 04 and 14 Without Consistency Check
- **Severity**: MEDIUM
- **Status**: new from R2
- **Source**: R2-E-004
- **Owner**: prompts + validators
- **Target**: `schema/04_fr_list.schema.json`, `schema/14_roadmap.schema.json`
- **Evidence**: FR acceptance_criteria (Step 04) and task acceptance_criteria (Step 14) are undefined in relationship. Task criteria could restate, refine, or contradict FR criteria.
- **Impact**: Ambiguity about which acceptance criteria are authoritative.
- **Proposed Fix**: Add prompt guidance explaining relationship. Consider validator for consistency.
- **Batch**: 4

#### AUDIT-086: Owner Validation Is Documentation-Only
- **Severity**: MEDIUM
- **Status**: new from R2
- **Source**: R2-G-003
- **Owner**: schema
- **Target**: `schema/core/atoms.schema.json` lines 38-42
- **Evidence**: `atoms#owner` uses regex `^[a-z][a-z0-9_-]*$`. The 8 owner canon entries exist but nothing validates against them. Any lowercase string passes.
- **Impact**: Owner field has no effective constraint. "foobar" is valid.
- **Proposed Fix**: Either enforce owner values against canon (preferred) or add enum constraint to schema.
- **Implementation Note**: Converting owner from regex to canon-enforcement requires canonical-lint to check ALL owner fields in ALL specs. This is a larger change than adding a simple enum -- it requires the canonical-lint infrastructure to traverse every spec file and validate every `owner` field against the canon registry.
- **Batch**: 0

#### AUDIT-087: Execution files_touched Not Scope-Checked
- **Severity**: MEDIUM
- **Status**: new from R2
- **Source**: R2-C-009
- **Owner**: validators
- **Target**: `tools/specdev_tools/validation/validators/step_16.py`
- **Evidence**: Base step_16 checks `implementation.files_touched` against `target_file_patterns` but NOT `execution.files_touched`.
- **Impact**: Scope creep in execution undetected.
- **Proposed Fix**: Extend file scope check to include `execution.files_touched`.
- **Batch**: 7

#### AUDIT-088: E304 Compares Against ALL Roadmap Tasks Instead of Active Milestone
- **Severity**: MEDIUM
- **Status**: new from R2 (codebase-verified)
- **Source**: R2-C (Step 16 and 16a analysis), r2-review-R3 FINDING-R3-002
- **Owner**: validators
- **Target**: `tools/specdev_tools/validation/validators/step_16.py` lines 313-318
- **Evidence**: E304 collects task IDs from all milestones in `14_roadmap.json`, not just the active milestone. Iterates `for milestone in roadmap_data.get("milestones", []) for task in milestone.get("tasks", [])`. Codebase-verified in R3 review.
- **Impact**: Iterative Trinity Loop execution impossible without workarounds -- Step 16 for milestone 1 fails if milestone 2's tasks are not in checklist.
- **Proposed Fix**: Filter `roadmap_task_ids` to only include tasks from milestones matching the current `milestone_ref`, or from milestones whose status is not "done".
- **Batch**: 1 (moved from Batch 7 -- codebase bug that makes iterative Trinity Loop execution impossible, no dependencies)

#### AUDIT-089: No Consumed Third-Party API Contracts Artifact
- **Severity**: MEDIUM
- **Status**: new from R2
- **Source**: R2-E-006
- **Owner**: pipeline design
- **Target**: Pipeline-wide
- **Evidence**: Step 05 captures APIs the system exposes. No step captures APIs the system *consumes* from third parties (identified in Step 02 as `type: external`).
- **Impact**: Third-party integration issues discovered during implementation with no spec artifact.
- **Proposed Fix**: Document as future extension candidate. Step 13 may propose; not a blocking fix.
- **Batch**: 8

#### AUDIT-090: Security Model Scattered Across 5 Steps With No Consolidation
- **Severity**: MEDIUM
- **Status**: new from R2
- **Source**: R2-E-007
- **Owner**: pipeline design
- **Target**: Steps 02, 05, 06, 07, 11
- **Evidence**: Authentication, authorization, access control spread across 5 steps. No single "Security Architecture" artifact.
- **Impact**: Security model inconsistencies between steps.
- **Proposed Fix**: Document as future extension candidate. Step 13 may propose.
- **Batch**: 8

#### AUDIT-091: shared_expectations.md Design (82 LOC, 11 Sections)
- **Severity**: MEDIUM
- **Status**: new from R2 [Per Decision 2/10]
- **Source**: R2-D2-001, R2-D Section 4
- **Owner**: shared_expectations
- **Target**: `docs/prompts/shared_expectations.md`
- **Evidence**: R2-D provides evidence-based design: 11 sections (Path Variables, Schema Authority, Canonical Registry, Hardening Protocol, Default Role+Task, Output Rules, Seed Order, Self-Audit Gate Protocol, Step-Order Policy, Tool Execution, Failure Modes). Estimated ~82 LOC centralizing ~1,032 LOC from 22 prompts. Maintenance points reduced from 22 to 1.
- **Impact**: Design blueprint for AUDIT-006 and AUDIT-026 implementation. This is the design blueprint for shared_expectations.md. AUDIT-006 provides the extraction list, AUDIT-026 provides the content gaps.
- **Proposed Fix**: Per Decision 2/10: Implement shared_expectations.md per R2-D Section 4 design. Include conflict resolution protocol (Decision 2), cross-step relationship directive (Decision 2), Self-Audit Gate threshold (Decision 10), Coverage Closure tail (Decision 10).
- **Batch**: 2

---

### LOW

#### AUDIT-050: Gate Item Counts Vary Widely Without Justification
- **Severity**: LOW
- **Status**: verified
- **Source**: P1-D #4
- **Owner**: prompts
- **Target**: All 22 prompts
- **Evidence**: Range from 2 items (steps 07, 08) to 6 items (steps 00, 11, 16).
- **Impact**: Inconsistent gate rigor.
- **Proposed Fix**: Normalize per upstream dependencies and schema `required[]`.
- **Batch**: 6

#### AUDIT-051: traceRef.type Description Lacks Valid Values List
- **Severity**: LOW
- **Status**: verified
- **Source**: P1-F #1
- **Owner**: schema
- **Target**: `schema/core/collections.schema.json:62`
- **Evidence**: Says "validated against canon" but does not enumerate common values.
- **Proposed Fix**: Add examples array.
- **Batch**: 0

#### AUDIT-052: atoms.owner Description Lacks Valid Values
- **Severity**: LOW
- **Status**: verified
- **Source**: P1-F #2
- **Owner**: schema
- **Target**: `schema/core/atoms.schema.json:42`
- **Evidence**: Says "validated against canon" but does not list values.
- **Proposed Fix**: Add `examples` array listing 8 standard owners.
- **Batch**: 0

#### AUDIT-053: stageName and environmentName Have Identical Enum but Unclear Distinction
- **Severity**: LOW
- **Status**: corroborated by R2-G-004
- **Source**: P1-F #4, R2-G-004
- **Owner**: schema + canon
- **Target**: `schema/core/collections.schema.json:247,256`, `canon/kinds/stage.json`, `canon/kinds/environment.json`
- **Evidence**: R2-G-004: same 4 values in 3 locations (triple-maintained). Near-identical descriptions.
- **Proposed Fix**: Consolidate to single source -- either canon-driven or schema enum with canon as documentation.
- **Note**: Batch 3 AUDIT-095 may consolidate stage/environment entirely. Batch 0 work should be description-only to avoid rework if Batch 3 subsumes this finding.
- **Batch**: 0

#### AUDIT-054: 16_impl_context Deep-Nested status_ref Descriptions Repetitive
- **Severity**: LOW
- **Status**: verified
- **Source**: P1-F #3
- **Owner**: schema
- **Target**: `schema/16_impl_context.schema.json` (14+ locations)
- **Evidence**: 14 `status_ref` fields use nearly identical descriptions.
- **Proposed Fix**: Add expected `kind` value or example ID to each.
- **Batch**: 0

#### AUDIT-055: emergent_ambiguities.severity Lacks Enum Constraint
- **Severity**: LOW
- **Status**: verified
- **Source**: P1-F #14
- **Owner**: schema
- **Target**: `schema/16_impl_context.schema.json:1638`
- **Evidence**: Planning severity has enum; emergent severity is unconstrained string.
- **Proposed Fix**: Add enum constraint or document difference.
- **Batch**: 0

#### AUDIT-056: Prompt 00 Output Contract Omits in_scope/out_of_scope Despite minItems:3
- **Severity**: LOW
- **Status**: verified [Updated per Decision 1]
- **Source**: P1-F #16
- **Owner**: prompts
- **Target**: `prompts/prompt_00_project_charter.md:186-244`
- **Evidence**: Schema has `minItems: 3`. Gate expects them. Contract omits them.
- **Proposed Fix**: Per Decision 1: fix Output Contract examples. Also see AUDIT-075 for making these fields required.
- **Batch**: 4

#### AUDIT-057: dependencyList vs dependencyObjectList Difference Undocumented
- **Severity**: LOW
- **Status**: verified
- **Source**: P1-F #12
- **Owner**: schema
- **Target**: `schema/14_roadmap.schema.json:228`, `schema/09_impl_plan.schema.json:93`
- **Evidence**: Step 14 requires structured objects; Step 09 allows mixed. Same description text.
- **Proposed Fix**: Differentiate descriptions.
- **Batch**: 0

#### AUDIT-058: No Cross-Step Consistency Verification Guidance
- **Severity**: LOW
- **Status**: verified
- **Source**: P1-B #15
- **Owner**: prompts
- **Target**: All prompts
- **Evidence**: Prompts check traceability but not cross-artifact consistency between sibling steps.
- **Proposed Fix**: Add "Cross-Artifact Consistency" check to Steps 04-08.
- **Batch**: 4

#### AUDIT-059: ADR Template Engine Doc Has Stale Template Count
- **Severity**: LOW
- **Status**: verified
- **Source**: P1-G #7
- **Owner**: docs
- **Target**: `docs/ops/adr_template_engine.md:31,38`
- **Evidence**: States "14 templates"; actual is 19.
- **Proposed Fix**: Update to 19.
- **Batch**: 8

#### AUDIT-060: docs/README.md Missing Several Doc References
- **Severity**: LOW
- **Status**: verified
- **Source**: P1-G #10
- **Owner**: docs
- **Target**: `docs/README.md`
- **Evidence**: "For Developers" table has 4 entries; full set has 15+ files.
- **Proposed Fix**: Add missing doc links.
- **Batch**: 8

#### AUDIT-061: workflow_align.md and workflow_migration.md Reference Wrong Venv Name
- **Severity**: LOW
- **Status**: verified
- **Source**: P1-G #17
- **Owner**: docs
- **Target**: `docs/developers/workflows/workflow_align.md:38`, `docs/developers/workflows/workflow_migration.md`
- **Evidence**: References `dev_env`; correct is `devspec_env`.
- **Proposed Fix**: Update.
- **Batch**: 8

#### AUDIT-066: connection.schema_ref `-tbd` Placeholder Convention Not Documented
- **Severity**: LOW
- **Status**: verified
- **Source**: P1-F #11
- **Owner**: schema
- **Target**: `schema/02_system_sketch.schema.json:120`
- **Evidence**: Pattern supports `-tbd` but description doesn't explain it.
- **Proposed Fix**: Update description.
- **Batch**: 0

#### AUDIT-092: Step 04 Schema Requires minItems:2 but Prompt Says >=1
- **Severity**: LOW
- **Status**: new from R2
- **Source**: R2-B-014
- **Owner**: prompt
- **Target**: `prompts/prompt_04_functional_requirements.md` line 74
- **Evidence**: Gate says ">=1 acceptance criterion". Schema requires minItems:2. Schema is stricter.
- **Impact**: Minor confusion for LLMs.
- **Proposed Fix**: Update prompt to say ">=2 acceptance criteria" to match schema.
- **Batch**: 4

#### AUDIT-093: Step 13 Schema Section Pattern Bug
- **Severity**: LOW
- **Status**: new from R2 (codebase-verified bug)
- **Source**: R2-C-010
- **Owner**: validators
- **Target**: `tools/specdev_tools/validation/validators/step_13.py` line 13
- **Evidence**: Checks `required_schema_sections` against `^[0-9]{2}[a-z]?_` pattern (step format). Prompt uses domain sections like "tables", "indexes" that would fail.
- **Impact**: Valid extension schema sections flagged as errors.
- **Proposed Fix**: Remove or relax the pattern check.
- **Note**: This is a simple bug fix (~5 LOC) that could be moved to an earlier batch if convenient, but LOW severity makes it acceptable in Batch 7.
- **Batch**: 7

#### AUDIT-094: No Feedback Loop from 16c to 16a
- **Severity**: LOW
- **Status**: new from R2
- **Source**: R2-C-011
- **Owner**: validators
- **Target**: Step 16c schema and prompt
- **Evidence**: When 16c issues remediation tasks, nothing ensures they appear in next 16a cycle.
- **Impact**: Bug fixes from review can be silently dropped.
- **Proposed Fix**: Add validator checking previous 16c remediation tasks appear in current 16a checklist.
- **Batch**: 7

#### AUDIT-095: Stage/Environment Triple-Maintained
- **Severity**: LOW
- **Status**: new from R2
- **Source**: R2-G-004
- **Owner**: canon + schema
- **Target**: `canon/kinds/stage.json`, `canon/kinds/environment.json`, `schema/core/collections.schema.json`
- **Evidence**: Same 4 values in 3 locations.
- **Impact**: Triple maintenance burden.
- **Proposed Fix**: Consolidate to single source.
- **Note**: See also AUDIT-053 (Batch 0). This finding may subsume AUDIT-053 -- if Batch 3 consolidates stage/environment, Batch 0's description-only changes to AUDIT-053 become moot.
- **Batch**: 3

#### AUDIT-096: 25% of Canon Entries Are Auth-Domain Specific
- **Severity**: LOW
- **Status**: new from R2
- **Source**: R2-G-001
- **Owner**: canon
- **Target**: `canon/manifest.json`
- **Evidence**: 18 of 74 entries are auth-demo artifacts (capability:authenticate, entity:user/session, etc.).
- **Impact**: Meaningless for non-auth projects.
- **Proposed Fix**: Move to `canon/examples/` or starter-kit.
- **Batch**: 3

#### AUDIT-097: Migration Plan and Dependencies Duplicated Between Steps 09 and 14
- **Severity**: LOW
- **Status**: new from R2
- **Source**: R2-E-005
- **Owner**: prompts
- **Target**: `schema/09_impl_plan.schema.json`, `schema/14_roadmap.schema.json`
- **Evidence**: Both have `migration_plan` and `dependencies` with no cross-reference guidance.
- **Impact**: Creates confusion about authoritative version.
- **Proposed Fix**: Add prompt guidance clarifying Step 14 as authoritative for execution.
- **Batch**: 4

#### AUDIT-098: ID Stability Not Machine-Enforced During Replay
- **Severity**: LOW
- **Status**: new from R2
- **Source**: R2-E-010
- **Owner**: validators
- **Target**: `tools/specdev_tools/validation/`
- **Evidence**: Forward-replay at file level. ID renames within files not detected early.
- **Impact**: Cascading validation failures rather than early detection.
- **Proposed Fix**: Consider ID-diff validator that detects removed IDs during replay.
- **Batch**: 7

---

### INFO

#### AUDIT-062: Prompt Output Contracts Inconsistently Include $schema Field
- **Severity**: INFO
- **Status**: verified
- **Source**: P1-F #18
- **Owner**: prompts
- **Target**: Multiple prompt Output Contract sections
- **Evidence**: Some include `$schema`, some omit.
- **Proposed Fix**: Standardize.
- **Batch**: 4

#### AUDIT-063: generation_quality Fully Purged -- Verified Complete
- **Severity**: INFO
- **Status**: verified
- **Source**: P1-D #8
- **Owner**: N/A
- **Target**: N/A
- **Evidence**: 0 matches in prompts/, schema/, tools/. Purge complete.
- **Proposed Fix**: None needed.
- **Batch**: N/A

#### AUDIT-064: audit/ Docs Are Historical but Not Marked as Archived
- **Severity**: INFO
- **Status**: verified
- **Source**: P1-G #13
- **Owner**: docs
- **Target**: `docs/audit/` (20+ files)
- **Evidence**: All from v0.3.0 structural audit. Not living documents.
- **Proposed Fix**: Add archive marker.
- **Batch**: 8

#### AUDIT-065: Projected Extraction Summary -- ~1,924 LOC Recoverable (Refined)
- **Severity**: INFO
- **Status**: refined by R2-A
- **Source**: P1-A #12, R2-A-003
- **Owner**: prompts
- **Target**: All 22 prompts + `shared_expectations.md`
- **Evidence**: P1 estimated ~927 LOC (16%). R2-A refined: 1,924 LOC (34%) -- 1,312 boilerplate + 500 schema-dup + 69 DAG-dup + 43 canon-dup.
- **Proposed Fix**: Implement per AUDIT-006.
- **Batch**: 0, 2

#### AUDIT-099: Data Model Has No Dedicated Artifact
- **Severity**: INFO
- **Status**: new from R2
- **Source**: R2-E-008
- **Owner**: pipeline design
- **Target**: Pipeline-wide
- **Evidence**: Entity relationships implicit across glossary, APIs, invariants. No explicit ER model.
- **Impact**: Data model decisions during implementation have no spec governance.
- **Proposed Fix**: Document as potential future extension.
- **Batch**: 8

#### AUDIT-100: canonical_proposals Infrastructure Supports Glossary-Canon Merge
- **Severity**: INFO
- **Status**: new from R2
- **Source**: R2-G-007
- **Owner**: canon
- **Target**: `schema/core/step_base.schema.json`
- **Evidence**: `canonicalProposal` has all fields needed (temp_id, kind, proposed_label, definition, source_field, suggested_namespace). Schema changes: none needed. Infrastructure is 80% built.
- **Proposed Fix**: Build acceptance tooling (AUDIT-073). Schema ready.
- **Batch**: 3

#### AUDIT-101: Context Ledger Protocol Is Universal But Appears As Step-Specific Prose
- **Severity**: INFO
- **Status**: new from R2
- **Source**: R2-D2-007
- **Owner**: prompts + shared_expectations
- **Target**: 15 of 22 prompts
- **Evidence**: "Build a private Context Ledger... Do not output it" appears in 15 prompts with step-specific names (Context Ledger, Coverage Ledger, Plan Ledger, etc.).
- **Impact**: Protocol instruction repeated as step-specific prose.
- **Proposed Fix**: Add single line to shared_expectations: "Before emitting output, build a private synthesis ledger." Keep step-specific ledger content per prompt.
- **Batch**: 2

---

## Cross-Reference Table

### P1 Findings -> AUDIT IDs

| P1 Agent | P1 Finding | AUDIT ID |
|----------|-----------|----------|
| P1-A | #1 Hardening Protocol | AUDIT-006 |
| P1-A | #2 Canonical Registry | AUDIT-006, AUDIT-007 |
| P1-A | #3 Canonical Binding Rules | AUDIT-006 |
| P1-A | #4 Schema Authority + Path Variables | AUDIT-006 |
| P1-A | #5 Coverage Closure no validator | AUDIT-010 |
| P1-A | #6 Metadata Contract | AUDIT-006 |
| P1-A | #7 Quick Reference subset | AUDIT-008 |
| P1-A | #8 Output Rules generic items | AUDIT-006 |
| P1-A | #9 Tool Execution near-identical | AUDIT-006 |
| P1-A | #10 shared_expectations 8/22 | AUDIT-036 |
| P1-A | #11 shared_expectations overlap | AUDIT-036 |
| P1-A | #12 Projected extraction | AUDIT-065 |
| P1-B | #1 Boilerplate dominates | AUDIT-006, AUDIT-001 |
| P1-B | #2 Generic role | AUDIT-028 |
| P1-B | #3 Conflicting inputs | AUDIT-002 |
| P1-B | #4 Implicit requirements | AUDIT-003 |
| P1-B | #5 Operating Flow homogeneity | AUDIT-001 |
| P1-B | #6 No granularity guidance | AUDIT-027 |
| P1-B | #7 Step 00 seed extraction | AUDIT-001 (context) |
| P1-B | #8 No weak-vs-strong examples | AUDIT-029 |
| P1-B | #9 Coverage Closure mechanical | AUDIT-030 |
| P1-B | #10 Extraction Intent no priority | AUDIT-031 |
| P1-B | #11 Step 05 API design | AUDIT-038 |
| P1-B | #12 Step 06 invariant discovery | AUDIT-039 |
| P1-B | #13 Given-When-Then framework | AUDIT-001 (sub-point) |
| P1-B | #14 Output Contract contradictions | AUDIT-040 |
| P1-B | #15 Cross-step consistency | AUDIT-058 |
| P1-B | #16 Seed template deep-dive | AUDIT-001 (sub-point) |
| P1-B | #17 Steps 04/07 largest gap | AUDIT-001 |
| P1-B | #18 Trinity Loop gold standard | AUDIT-001 |
| P1-C | #1 docs_policy dead | AUDIT-017 |
| P1-C | #2 nested_order redundant | AUDIT-035 |
| P1-C | #4 allowed_upstream derivable | AUDIT-023 |
| P1-C | #7 Triple redundancy | AUDIT-018 |
| P1-C | #8 Seed ordering bug | AUDIT-024 |
| P1-C | #9 46 docs unreferenced | AUDIT-025 |
| P1-C | #10 Tech stack consistency | AUDIT-034 |
| P1-C | #13 Step 09 extraction omits tech | AUDIT-034 |
| P1-C | #14 global_seed_order conflation | AUDIT-024 |
| P1-C | #15 Doc-awareness gap | AUDIT-025 |
| P1-D | #1 Score undefined | AUDIT-009 |
| P1-D | #2 Dual role confusion | AUDIT-010 |
| P1-D | #3 16a/16b/16c duplicate gates | AUDIT-012 |
| P1-D | #4 Gate item count variance | AUDIT-050 |
| P1-D | #5 Gate items step-specific | AUDIT-006 |
| P1-D | #6 agents.md dual condition | AUDIT-009 |
| P1-D | #7 Step 13 anti-pattern gates | AUDIT-037 |
| P1-D | #8 generation_quality purged | AUDIT-063 |
| P1-D | #9 Coverage Closure coupling | AUDIT-011 |
| P1-E | #1 Step 09 no depends_on | AUDIT-014 |
| P1-E | #2 Step 14 tasks no FR binding | AUDIT-015 |
| P1-E | #3 Semantic drift no validator | AUDIT-016 |
| P1-E | #4 Extraction Mandates 3/22 | AUDIT-019 |
| P1-E | #5 Step 14 no matrix trigger | AUDIT-033 |
| P1-E | #6 Trinity evidence prompt-only | AUDIT-032 |
| P1-E | #7 Drift-vulnerable steps | AUDIT-016 |
| P1-E | #8 00->01 misses metrics | AUDIT-022 |
| P1-E | #9 No FR->API lint | AUDIT-013 |
| P1-E | #10 Step 09 mis-sequencing | AUDIT-014 (sub-point) |
| P1-E | #11 Trinity evidence binding partial | AUDIT-032 (sub-point) |
| P1-E | #12 Step 14 tasks no FR binding | AUDIT-015 (sub-point) |
| P1-E | #13 FR->API lint | AUDIT-013 (sub-point) |
| P1-E | #14 16c no roadmap check | AUDIT-004 |
| P1-E | #15 09->14 partial | AUDIT-005 |
| P1-F | #1 traceRef.type values | AUDIT-051 |
| P1-F | #2 owner values | AUDIT-052 |
| P1-F | #3 status_ref repetitive | AUDIT-054 |
| P1-F | #4 stageName vs environmentName | AUDIT-053 |
| P1-F | #6 Prompt 09 Quick Ref | AUDIT-041 |
| P1-F | #7 Prompt 00 Quick Ref | AUDIT-042 |
| P1-F | #8 Prompt 05 Quick Ref | AUDIT-043 |
| P1-F | #9 Prompt 09 milestone fields | AUDIT-041 |
| P1-F | #10 Prompt 16 canonical_refs | AUDIT-044 |
| P1-F | #11 schema_ref -tbd | AUDIT-066 |
| P1-F | #12 dependency type difference | AUDIT-057 |
| P1-F | #14 emergent severity | AUDIT-055 |
| P1-F | #16 in_scope/out_of_scope | AUDIT-056 |
| P1-F | #18 $schema inconsistency | AUDIT-062 |
| P1-G | #1 Missing 16a/16b/16c templates | AUDIT-021 |
| P1-G | #2 Template schema drift | AUDIT-020 |
| P1-G | #3 template_frs wrong filename | AUDIT-046 |
| P1-G | #4 No interpolation | AUDIT-049 |
| P1-G | #5 extension_schemas unreferenced | AUDIT-025 |
| P1-G | #15 governance_arch unreferenced | AUDIT-025 |
| P1-G | #7 ADR stale count | AUDIT-059 |
| P1-G | #8 bootstrap legacy outdated | AUDIT-047 |
| P1-G | #9 feature extension outdated | AUDIT-048 |
| P1-G | #10 README missing links | AUDIT-060 |
| P1-G | #11 Templates lack prompt ref | AUDIT-045 |
| P1-G | #12 No step-to-doc map | AUDIT-025, AUDIT-026 |
| P1-G | #13 audit/ not archived | AUDIT-064 |
| P1-G | #14 Migration no step prompt | AUDIT-045 |
| P1-G | #16 shared_expectations no docs | AUDIT-026 |
| P1-G | #17 Wrong venv name | AUDIT-061 |
| P1-G | #18 Template consolidation | AUDIT-045 |

### R2 Findings -> AUDIT IDs

| R2 Document | R2 Finding | AUDIT ID | Status |
|-------------|-----------|----------|--------|
| R2-A | R2-A-001 (Prompt 14 worst DRY) | AUDIT-008 | Merged -- supports case for Field-by-Field deletion |
| R2-A | R2-A-002 (Owner enum 43x) | AUDIT-086 | Merged into AUDIT-086 (owner validation) |
| R2-A | R2-A-003 (1312 LOC boilerplate) | AUDIT-006, AUDIT-065 | Merged -- refines LOC estimates |
| R2-A | R2-A-004 (Discovery 30% vs Trinity 11%) | AUDIT-001 | Merged -- root cause analysis |
| R2-A | R2-A-005 (Quick Ref pure schema-dup) | AUDIT-008 | Merged -- strengthens deletion case |
| R2-A | R2-A-006 (Prompt 16 Output 233 LOC) | AUDIT-040 | Merged -- Output Contract reduction |
| R2-A | R2-A-007 (Field-by-Field verbatim schema) | AUDIT-008, AUDIT-071 | Merged into AUDIT-008 and new AUDIT-071 |
| R2-A | R2-A-008 (Only Step 11 has examples) | AUDIT-029 | Merged -- corroborates |
| R2-A | R2-A-009 (DAG-DUP design smell) | AUDIT-006 | Merged -- part of extraction |
| R2-A | R2-A-010 (Extraction Intent inconsistent) | AUDIT-031 | Merged -- corroborates |
| R2-A | R2-A-011 (Schema Ref auto-generate) | AUDIT-006 | Merged -- deletable content |
| R2-A | R2-A-012 (Tool Exec mix shared/specific) | AUDIT-006 | Merged -- extraction detail |
| R2-B | R2-B-001 (Prompts lack extraction guidance) | AUDIT-003 | Merged -- corroborates per Decision 7 |
| R2-B | R2-B-002 (Step 00 narrow extraction) | AUDIT-079 | New |
| R2-B | R2-B-003 (Charter schema gaps) | AUDIT-075 | New |
| R2-B | R2-B-004 (JTBD not in coverage) | AUDIT-080 | New |
| R2-B | R2-B-005 (Cross-cutting caps) | AUDIT-081 | New |
| R2-B | R2-B-006 (02a narrow consumption) | AUDIT-082 | New |
| R2-B | R2-B-007 (Glossary decorative) | AUDIT-072 | New |
| R2-B | R2-B-008 (FR discovery framework) | AUDIT-003 | Merged -- corroborates |
| R2-B | R2-B-009 (Glossary lifecycle gap) | AUDIT-083 | New |
| R2-B | R2-B-010 (Step 06 Output Contract) | AUDIT-040 | Merged -- corroborates |
| R2-B | R2-B-011 (Step 07 measurement_method) | AUDIT-040 | Merged -- corroborates |
| R2-B | R2-B-012 (Conflict resolution absent) | AUDIT-002 | Merged -- corroborates |
| R2-B | R2-B-013 (Trace optional in schema) | AUDIT-084 | New |
| R2-B | R2-B-014 (minItems:2 vs >=1) | AUDIT-092 | New |
| R2-B | R2-B-015 (Tech stack coherence) | AUDIT-034 | Merged -- corroborates |
| R2-B | R2-B-016 (seed_manifest stops at 04) | AUDIT-082 | Absorbed into AUDIT-082 (Note: R2-B-016 was promoted from R2-B section 1.5 observation, not an explicit numbered finding in R2-B source) |
| R2-C | R2-C-001 (No completeness enforcement) | AUDIT-067 | New |
| R2-C | R2-C-002 (13a aspirational) | AUDIT-068 | New |
| R2-C | R2-C-003 (Semantic review not enforced) | AUDIT-069 | New |
| R2-C | R2-C-004 (Evidence quality) | AUDIT-070 | New |
| R2-C | R2-C-005 (Verdict enum mismatch) | AUDIT-076 | New |
| R2-C | R2-C-006 (Governance-to-CI gap) | AUDIT-077 | New |
| R2-C | R2-C-007 (API-to-threat gap) | AUDIT-078 | New |
| R2-C | R2-C-008 (13a blocking gate) | AUDIT-068 | Merged into AUDIT-068 |
| R2-C | R2-C-009 (Execution scope check) | AUDIT-087 | New |
| R2-C | R2-C-010 (Step 13 pattern bug) | AUDIT-093 | New |
| R2-C | R2-C-011 (16c feedback loop) | AUDIT-094 | New |
| R2-C | R2-C-012 (Roadmap sync) | AUDIT-094 | Absorbed -- related to feedback loop |
| R2-C | E304 milestone scope | AUDIT-088 | New (from R3 review) |
| R2-D | R2-D2-001 (1032 LOC boilerplate) | AUDIT-006, AUDIT-091 | Merged + new design finding |
| R2-D | R2-D2-002 (shared_exp dead weight) | AUDIT-026 | Merged -- corroborates |
| R2-D | R2-D2-003 (Self-Audit 3 concerns) | AUDIT-009, AUDIT-010, AUDIT-011 | Merged -- supports 3-concern decomposition |
| R2-D | R2-D2-004 (Schema-dup -> schema) | AUDIT-071 | Merged -- supports Decision 1 |
| R2-D | R2-D2-005 (4 specialized roles) | AUDIT-028 | Merged -- informs implementation |
| R2-D | R2-D2-006 (Step 12 canonical) | AUDIT-007 | Merged -- corroborates |
| R2-D | R2-D2-007 (Context Ledger universal) | AUDIT-101 | New |
| R2-D | R2-D2-008 (Schema enrich first) | AUDIT-071 | Merged -- captures Decision 9 constraint |
| R2-D | R2-D2-009 (Tool Exec partial shared) | AUDIT-006 | Merged |
| R2-D | R2-D2-010 (Existing content not in prompts) | AUDIT-026 | Absorbed |
| R2-E | R2-E-001 (Cap->FR lacks guidance) | AUDIT-001 | Merged -- corroborates |
| R2-E | R2-E-002 (Glossary not enforced) | AUDIT-072 | Merged -- per Decision 6 |
| R2-E | R2-E-003 (Tech stack duplicated 09/14) | AUDIT-034 | Merged -- corroborates |
| R2-E | R2-E-004 (Acceptance criteria dup) | AUDIT-085 | New |
| R2-E | R2-E-005 (Migration plan dup) | AUDIT-097 | New |
| R2-E | R2-E-006 (No consumed APIs) | AUDIT-089 | New |
| R2-E | R2-E-007 (Security scattered) | AUDIT-090 | New |
| R2-E | R2-E-008 (No data model) | AUDIT-099 | New |
| R2-E | R2-E-009 (Discovery vs Trinity quality) | AUDIT-001 | Merged -- corroborates |
| R2-E | R2-E-010 (ID stability) | AUDIT-098 | New |
| R2-E | R2-E-011 (09->14 decomposition) | AUDIT-005 | Merged -- corroborates |
| R2-E | R2-E-012 (FR pipeline coverage) | AUDIT-067 | Merged into AUDIT-067 |
| R2-F | R2-F2-001 (Schema sole owner) | AUDIT-071 | Merged/new |
| R2-F | R2-F2-002 (Descriptions too thin) | AUDIT-071 | Merged |
| R2-F | R2-F2-003 (Good patterns exist) | AUDIT-071 | Merged |
| R2-F | R2-F2-004 (Three-tier depth) | AUDIT-071 | Merged |
| R2-F | R2-F2-005 (Cross-artifact signals) | AUDIT-071 | Merged |
| R2-F | R2-F2-006 (Longer descriptions OK) | AUDIT-071 | Merged |
| R2-F | R2-F2-007 (migration_plan diverges) | AUDIT-097 | Absorbed into AUDIT-097 |
| R2-F | R2-F2-008 (Hardest fields thinnest) | AUDIT-071 | Merged |
| R2-G | R2-G-001 (Auth-domain entries) | AUDIT-096 | New |
| R2-G | R2-G-002 (No namespace separation) | AUDIT-074 | New |
| R2-G | R2-G-003 (Owner documentation-only) | AUDIT-086 | New |
| R2-G | R2-G-004 (Stage/env triple-maintained) | AUDIT-095 | New |
| R2-G | R2-G-005 (No canon-accept tool) | AUDIT-073 | New |
| R2-G | R2-G-006 (Glossary enforcement decorative) | AUDIT-072 | Merged |
| R2-G | R2-G-007 (canonical_proposals ready) | AUDIT-100 | New |

---

## Batch Summary

| Batch | Name | Findings | Count |
|-------|------|----------|-------|
| 0 | Schema enrichment | AUDIT-014, 015 (schema part), 051, 052, 053, 054, 055, 057, 066, 071, 075, 084, 086, 008 (schema part), 040 (schema part), 041, 042, 043 | 18 |
| 1 | Config cleanup + codebase bugs | AUDIT-017, 023, 035, 069, 076, 082, 088 | 7 |
| 2 | shared_expectations.md | AUDIT-002, 006 (extraction part), 007, 018, 026, 091, 101 | 7 |
| 3 | Glossary -> Canon | AUDIT-072, 073, 074, 095, 096, 100 | 6 |
| 4 | Prompt synthesis enrichment | AUDIT-001, 003, 008 (deletion part), 016, 019, 027, 028, 029, 030, 031, 038, 039, 040 (prompt part), 044, 056, 058, 062, 079, 080, 081, 083, 085, 092, 097 | 24 |
| 5 | Pairwise completeness + 13a redesign | AUDIT-004, 005, 013, 015 (validation part), 067, 068 | 6 |
| 6 | Self-Audit Gate redesign | AUDIT-009, 010, 011, 012, 037, 050 | 6 |
| 7 | Validator/lint fixes | AUDIT-022, 024, 032, 033, 034, 070, 077, 078, 087, 093, 094, 098 | 12 |
| 8 | Docs/templates | AUDIT-020, 021, 025, 045, 046, 047, 048, 049, 059, 060, 061, 064, 089, 090, 099 | 15 |
| N/A | No action needed | AUDIT-036 (subsumed by 026), 063, 065 | 3 |

**Note on multi-batch findings**: Some findings appear in multiple batches (e.g., AUDIT-008 in Batch 0 and 4, AUDIT-015 in Batch 0 and 5, AUDIT-040 in Batch 0 and 4). Each is listed in its primary batch for counting purposes; the secondary batch reference indicates work that depends on the primary batch completing first.

**Batch 0 implementation guidance** (recommended sub-batches to prevent Batch 0 from becoming a multi-week blocker):
- **Batch 0a**: Schema structural changes (AUDIT-014, 015 schema part, 075, 084, 086) -- adding fields, changing required arrays
- **Batch 0b**: Schema description enrichment (AUDIT-071, 051, 052, 053, 054, 055, 057, 066) -- Tier 3 fields first, then Tier 2, then Tier 1
- **Batch 0c**: Prompt Quick Reference deletion (AUDIT-008, 040, 041, 042, 043) -- can happen after 0b

**Batch execution order** (respects Decision 9 and inter-batch dependencies):
1. Batch 0 (Schema enrichment) -- MUST be first per Decision 9
2. Batch 1 (Config cleanup + codebase bugs) -- independent; includes critical/medium bug fixes moved from Batch 7
3. Batch 3 (Glossary -> Canon) -- independent but enables canonical enforcement. Note: Batch 3 (new tooling) is more complex than Batch 2; resource-constrained teams might swap order with Batch 2
4. Batch 2 (shared_expectations) -- after Batch 0 schema enrichment
5. Batch 4 (Prompt synthesis) -- after Batch 0 and 2
6. Batch 5 (Pairwise completeness) -- independent
7. Batch 6 (Self-Audit Gate) -- after Batch 2
8. Batch 7 (Validators) -- independent
9. Batch 8 (Docs/templates) -- last, lowest priority

### Subsumed P1 Findings

The following P1 findings were subsumed into other findings during consolidation. AUDIT-036 was subsumed during v1-to-v2 consolidation. The remaining 8 entries are P1 agent-level findings that were absorbed into existing AUDIT entries as sub-points during the original P1-to-P3v1 consolidation (they never had independent AUDIT IDs):

| Original P1 AUDIT ID | Subsumed By | Reason |
|----------------------|-------------|--------|
| AUDIT-036 | AUDIT-026 | shared_expectations redesign covers shared_expectations adoption |
| P1-B #7 | AUDIT-001 | Seed extraction context absorbed into synthesis reasoning |
| P1-B #13 | AUDIT-001 | Given-When-Then framework absorbed as sub-point |
| P1-B #16 | AUDIT-001 | Seed template deep-dive absorbed as sub-point |
| P1-E #10 | AUDIT-014 | Step 09 mis-sequencing absorbed as sub-point |
| P1-E #11 | AUDIT-032 | Trinity evidence binding absorbed as sub-point |
| P1-E #12 | AUDIT-015 | Step 14 FR binding absorbed as sub-point |
| P1-E #13 | AUDIT-013 | FR->API lint absorbed as sub-point |
| P1-G #15 | AUDIT-025 | governance_arch unreferenced absorbed into docs unreferenced |
