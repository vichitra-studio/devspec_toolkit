# P3 Master Findings -- Prompt System Audit

**Date**: 2026-03-20
**Input**: 7 P1 agent outputs (105 raw findings)
**Output**: 66 deduplicated findings (AUDIT-001 through AUDIT-066)

## Summary

| Severity | Count | Corroborated | Verified |
|----------|-------|--------------|----------|
| CRITICAL | 6 | 1 | 5 |
| HIGH | 17 | 4 | 13 |
| MEDIUM | 26 | 4 | 22 |
| LOW | 13 | 0 | 13 |
| INFO | 4 | 0 | 4 |
| **Total** | **66** | **9** | **57** |

---

## Deduplication Log

| P1 Findings | Merged Into | Rationale |
|---|---|---|
| P1-A #1 (Hardening Protocol bloat) + P1-D #5 (gate generic checklist extractable) | AUDIT-006 | Both identify extractable identical content; A owns dedup, D confirms gate-specific items stay |
| P1-A #5 (Coverage Closure no validator) + P1-D #9 (Coverage Closure coupled to gate) | AUDIT-010, AUDIT-011 | Separate findings: A=no machine enforcement (kept as AUDIT-010), D=structural coupling design issue (kept as AUDIT-011) |
| P1-B #1 (boilerplate dominates synthesis) + P1-A #12 (projected extractable LOC) | AUDIT-006 (info), AUDIT-001 | B's observation about boilerplate crowding synthesis merged into AUDIT-001; A's LOC projection kept as INFO in AUDIT-065 |
| P1-B #5 (Operating Flow homogeneity) + P1-B #2 (generic role) | Separate: AUDIT-001, AUDIT-028 | Different fixes -- role text vs flow phases |
| P1-C #9 (46 docs unreferenced) + P1-G #12 (no step-to-doc map) + P1-G #16 (shared_expectations lacks doc guidance) | AUDIT-025, AUDIT-026 | C=mechanism/config (AUDIT-025), G=content evaluation (AUDIT-026). G16 merged into AUDIT-026 |
| P1-C #4 (allowed_upstream derivable) + P1-E context | AUDIT-023 | Single owner: C |
| P1-C #7 (Seed/Context/Extraction triple redundancy) + P1-B #10 (Extraction Intent lacks priority) | Separate: AUDIT-018, AUDIT-031 | Different concerns: redundancy vs prioritization |
| P1-D #1 (score undefined) + P1-D #6 (agents.md dual condition) | AUDIT-009 | Same root cause: scoring methodology undefined. D6 becomes sub-point |
| P1-D #2 (dual role confusion) + P1-D #9 (Coverage Closure coupling) | Separate: AUDIT-010, AUDIT-011 | D2=gate purpose confusion, D9=structural coupling |
| P1-F #6 (prompt 09 Quick Ref) + P1-F #9 (prompt 09 milestone fields) | AUDIT-041 | Same prompt, same section, same fix |
| P1-F #7 (prompt 00 Quick Ref) + P1-A #7 (Quick Ref subset of Field-by-Field) | Separate: AUDIT-042, AUDIT-008 | F7=specific missing fields (AUDIT-042), A7=structural redundancy (AUDIT-008) |
| P1-G #2 (template schema drift) + P1-G #4 (no interpolation) | Separate: AUDIT-020, AUDIT-049 | Different fixes |
| P1-G #5 (extension_schemas unreferenced) + P1-C #15 (doc-awareness gap) | AUDIT-025 sub-point | G5 is a specific instance of the general doc-awareness gap |
| P1-G #14 (migration lacks step prompt ref) + P1-G #11 (templates lack prompt ref) + P1-G #18 (consolidation opportunity) | AUDIT-045 | All three address template-to-prompt integration gap |
| P1-E #3 (semantic drift no validator) + P1-E #7 (steps vulnerable to drift) | AUDIT-016 | E7 provides the risk analysis; E3 provides the finding |
| P1-E #14 (16c no roadmap deliverable check) + P1-E #15 (09->14 deliverable partial) | Separate: AUDIT-004, AUDIT-005 | Different links in the chain |

---

## Findings

### CRITICAL

#### AUDIT-001: Discovery Phase Prompts (01-10) Lack Synthesis Reasoning Frameworks
- **Severity**: CRITICAL
- **Status**: corroborated
- **Source**: P1-B #17, P1-B #18, P1-B #5, P1-B #6, P1-B #1
- **Owner**: P1-B (Synthesis Quality)
- **Target**: `prompts/prompt_01_capabilities.md` through `prompts/prompt_10_governance.md`
- **Evidence**: 14 of 22 prompts use generic "Synthesize -> Clarify -> Emit" flow with no step-specific reasoning. Steps 04/07 have the largest challenge-vs-guidance gap. Step 04 feeds 13 downstream steps (most of any) but has the same operating flow as Step 03 (Glossary). Trinity Loop prompts (16a/16b/16c) demonstrate the gold standard with named phases, categorized forbidden actions, failure modes, and evidence binding -- none of which exist in Discovery Phase prompts.
- **Impact**: LLMs produce inconsistent quality across Discovery Phase steps. Decomposition granularity varies wildly between runs. Steps 04, 05, 06, 07 require domain reasoning that the prompts do not scaffold.
- **Proposed Fix**: Propagate Trinity Loop patterns to Discovery Phase: (1) replace generic operating flows with step-specific named phases (e.g., Step 04: "Enumerate -> Decompose -> Falsify -> Trace -> Emit"), (2) add categorized forbidden actions for Steps 04-07, (3) add weak-vs-strong examples tables to Steps 04-08, (4) add failure modes with causes/fixes. Priority: Steps 04 and 07 first (highest downstream impact).

#### AUDIT-002: No Prompt Addresses Conflicting Upstream Inputs
- **Severity**: CRITICAL
- **Status**: verified
- **Source**: P1-B #3
- **Owner**: P1-B (Synthesis Quality)
- **Target**: All 22 prompts, most critically `prompts/prompt_04_functional_requirements.md`, `prompts/prompt_05_interface_contracts.md`, `prompts/prompt_06_invariants.md`, `prompts/prompt_07_nfrs.md`, `prompts/prompt_09_impl_plan.md`
- **Evidence**: No prompt distinguishes between "missing information" (ask gap question) and "contradictory information" (requires resolution). Step 04 says "If any upstream ID cannot be traced: add a gap question" but does not address when two upstream specs contradict each other. Step 09 says "Do not introduce technologies not listed in capabilities" but does not address when a capability implies a technology contradicting seed_tech_stack constraints.
- **Impact**: LLMs silently resolve contradictions by picking one input over another without surfacing the conflict to the user. This can propagate incorrect assumptions through all downstream steps.
- **Proposed Fix**: Add a "Conflict Resolution" section to Steps 04, 05, 06, 07, 09 specifying: (1) how to detect conflicts, (2) upstream precedence rules, (3) when to flag as Gap Question vs resolve locally. Consider adding to `shared_expectations.md` as a universal protocol.

#### AUDIT-003: No Prompt Explains How to Identify Implicit Requirements
- **Severity**: CRITICAL
- **Status**: verified
- **Source**: P1-B #4
- **Owner**: P1-B (Synthesis Quality)
- **Target**: `prompts/prompt_04_functional_requirements.md`, `prompts/prompt_05_interface_contracts.md`, `prompts/prompt_06_invariants.md`
- **Evidence**: Step 04 says "Build a private Context Ledger of candidate FRs" but does not explain how to discover FRs implied but not stated (error handling, pagination, rate limiting, session management, audit logging). Step 06 says "MUST include data integrity constraints implied by entities" but lacks a systematic discovery method.
- **Impact**: LLMs produce FRs that cover only explicitly stated behaviors, missing standard production requirements. Fixtures and NFRs downstream inherit these gaps.
- **Proposed Fix**: Add "Implicit Requirements Discovery" checklists to Steps 04, 05, 06 (e.g., "For every mutating FR: consider idempotency, conflict handling, audit trail. For every list FR: consider pagination, filtering, sorting."). Add invariant discovery checklist to Step 06.

#### AUDIT-004: Step 16c Reviewer Has No Machine Enforcement for Roadmap Deliverable Completion
- **Severity**: CRITICAL
- **Status**: verified
- **Source**: P1-E #14
- **Owner**: P1-E (Traceability/Integrity)
- **Target**: `prompts/prompt_16c_impl_reviewer.md`, `tools/specdev_tools/validation/validators/step_16.py`
- **Evidence**: Prompt says "Before marking a milestone complete, verify all deliverables" and "MUST also update `spec/14_roadmap.json`". No validator checks that `verdict: verified` implies roadmap deliverables are satisfied. `status_write_exemptions` in step_order.json allows Steps 09/14 status updates without triggering forward-replay, but nothing validates correctness.
- **Impact**: A reviewer can mark implementation as verified without confirming roadmap deliverables are met. This is the critical handoff where discovery specs meet implementation reality.
- **Proposed Fix**: Add validator in `step_16.py`: when `review.verdict == "verified"`, check that `review.semantic_review.fr_coverage` entries cover all `fr_refs` from the corresponding Step 14 milestone.

#### AUDIT-005: Step 09 -> 14 Deliverable Traceability Is Partial
- **Severity**: CRITICAL
- **Status**: verified
- **Source**: P1-E #15
- **Owner**: P1-E (Traceability/Integrity)
- **Target**: `tools/specdev_tools/validation/validators/step_14.py:41-49`, `schema/09_impl_plan.schema.json`
- **Evidence**: `step_14.py` validates `source_milestones` ID existence only (E590). Does not load Step 09 milestone deliverables to compare against Step 14 deliverables. A Step 09 milestone with 5 deliverables can be referenced by Step 14 via `source_milestones` with only 2 deliverables, silently dropping 3.
- **Impact**: Deliverables defined in the implementation plan can be silently dropped when decomposed into the roadmap, creating phantom coverage.
- **Proposed Fix**: Add lint check (W566 INCOMPLETE_MILESTONE_DECOMPOSITION): for each Step 14 milestone, load `source_milestones` from Step 09, collect all deliverable IDs, verify each appears in Step 14 milestone's deliverables or fr_refs.

#### AUDIT-020: All 19 Migration Templates Have Significant Schema Drift
- **Severity**: CRITICAL (restored from P1-G CRITICAL; originally downgraded to HIGH with insufficient justification. Templates are the primary input to `specdev align prompts`, a documented workflow. ALL 19 templates describe field names and structures that do not match current schemas, meaning every AI-assisted migration receives incorrect field guidance. Per consolidation rules, severity disagreement resolves to higher unless lower has explicit justification.)
- **Status**: verified
- **Source**: P1-G #2
- **Owner**: P1-G (Documentation)
- **Target**: `prompts/migration/template_*.md` (all 19 files)
- **Evidence**: Templates describe field names not matching current schemas. `template_charter.md` lists `project_name`, `vision`, `goals`, `constraints` -- schema requires `problem_statement`, `success_metrics`, `stakeholders`, `user_segments`. `template_frs.md` uses `requirements` instead of `functional_requirements`. `template_governance.md` uses `commit_rules`, `branch_rules`, `roles` instead of `spec_first_policy`, `commit_message_rules`.
- **Impact**: AI-assisted migrations receive incorrect field guidance, producing invalid artifacts.
- **Proposed Fix**: Regenerate all 19 templates from current schemas. Each template's "Required Changes" section should list actual schema `required` fields and property names.

---

### HIGH

#### AUDIT-006: ~927 LOC of Extractable Boilerplate Across 22 Prompts
- **Severity**: HIGH
- **Status**: corroborated
- **Source**: P1-A #1, P1-A #2, P1-A #3, P1-A #4, P1-A #6, P1-A #9, P1-B #1
- **Owner**: P1-A (Bloat)
- **Target**: All 22 `prompts/prompt_*.md` files, `docs/prompts/shared_expectations.md`
- **Evidence**: Verified-identical sections: Hardening Protocol (132 LOC), Canonical Registry (154 LOC), Canonical Binding Rules (132 LOC), Path Variables (176 LOC), Metadata Contract (66 LOC). Near-identical: generic Coverage Closure checklist (66 LOC), generic Output Rules (~75 LOC), Tool Execution (~66 LOC). Quick Reference redundancy (~60 LOC). Total ~927 LOC extractable from 5,727 total (~16% reduction). P1-B corroborates that boilerplate crowds out synthesis guidance (~40-50% of each prompt is shared content).
- **Impact**: Token budget wasted on repeated content. Maintenance burden: changes to shared rules require editing 22 files. Dilutes step-specific synthesis guidance.
- **Proposed Fix**: Phase 1: Extract Hardening Protocol + Canonical Registry + Canonical Binding Rules + Path Variables to `shared_expectations.md` (594 LOC, zero risk). Phase 2: Extract Metadata Contract + generic Output Rules + generic Coverage Closure + Tool Execution (273 LOC). Phase 3: Evaluate Quick Reference removal. Ensure all 22 prompts reference `shared_expectations.md`. Merge step 12's Canonical Registry variant rules into the shared version.

#### AUDIT-007: Canonical Registry Step 12 Variant Contains Rules That Should Apply to All Prompts
- **Severity**: HIGH
- **Status**: verified
- **Source**: P1-A #2
- **Owner**: P1-A (Bloat)
- **Target**: `prompts/prompt_12_ci_gates.md:163`, all 22 prompts
- **Evidence**: Step 12's Canonical Registry adds: (1) deprecated canonical checking with `replaced_by`, (2) explicit `temp_id`/`proposed_label`/`definition`/`source_field` fields for proposals, (3) "NEVER leave a `*_ref` field empty", (4) "NEVER use a deprecated canonical without checking `replaced_by`". These rules are absent from the standard 21-prompt version.
- **Impact**: 21 of 22 prompts lack guidance on deprecated canonical handling and explicit proposal field requirements.
- **Proposed Fix**: Merge step 12's additional rules into the shared Canonical Registry section before extraction to `shared_expectations.md`.

#### AUDIT-008: Quick Reference Is a Strict Subset of Field-by-Field in 15 of 17 Prompts
- **Severity**: HIGH (resolved to HIGH from P1-A MEDIUM because P1-F corroborates with specific missing-field errors in prompts 00, 05, 09. Quick Reference actively omits required schema fields, causing LLMs to produce invalid JSON. P1-F individual findings #6, #7, #8 were originally rated HIGH, elevating the combined finding from redundancy concern (MEDIUM) to redundancy that actively causes validation failures (HIGH).)
- **Status**: corroborated
- **Source**: P1-A #7, P1-F #6, P1-F #7, P1-F #8, P1-F #9
- **Owner**: P1-A (Bloat) + P1-F (Descriptions)
- **Target**: 17 prompts with Quick Reference sections
- **Evidence**: P1-A: In 15 prompts where both Quick Reference and Field-by-Field exist, Quick Reference is a strict information subset. P1-F: Quick Reference sections in prompts 00, 05, 09 actively omit required schema fields (prompt 00 omits `stakeholders`/`user_segments`; prompt 05 omits `interface_ref`; prompt 09 omits `milestones`/`trace`/`deliverables`/`status`). Quick Reference is both redundant AND inaccurate.
- **Impact**: LLMs following Quick Reference as a checklist will miss required fields, producing invalid JSON. The redundancy with Field-by-Field creates ~55-70 LOC of unnecessary duplication.
- **Proposed Fix**: Either (a) remove Quick Reference from standard prompts (00-15) since Field-by-Field is always present and more complete, or (b) if kept, fix all missing required fields immediately. Keep Quick Reference for Step 16 where it serves a different structural purpose (table format).

#### AUDIT-009: Self-Audit Gate Score "< 0.9" Is Undefined and Unfalsifiable
- **Severity**: HIGH
- **Status**: corroborated
- **Source**: P1-D #1, P1-D #6
- **Owner**: P1-D (Self-Audit Gate)
- **Target**: All 22 prompts, `docs/agents/agents.md:30`
- **Evidence**: Every prompt says "If score < 0.9, output clarifying questions only" but no prompt defines the score calculation. `agents.md:30` adds a dual condition "or any gating item is missing" that no prompt includes. The boolean fallback in agents.md makes the numeric score redundant.
- **Impact**: Gate is non-deterministic -- different LLM runs produce different scores for identical inputs. An LLM could assign 0.95 despite a missing gating item and proceed to Emit.
- **Proposed Fix**: Replace "score < 0.9" with deterministic boolean: "If ANY gating item below cannot be satisfied from available context, enter Clarify mode." Add the agents.md boolean fallback to all prompts. This preserves flow-control value while eliminating undefined scoring.

#### AUDIT-010: Self-Audit Gate Conflates Input Sufficiency with Output Quality
- **Severity**: HIGH
- **Status**: corroborated
- **Source**: P1-D #2, P1-A #5
- **Owner**: P1-D (Self-Audit Gate)
- **Target**: All 22 prompts
- **Evidence**: Gate items mix input-sufficiency checks ("All charter goals map to capabilities" -- checks input exists) with output-quality checks ("Success metrics include unit+target for >=2 metrics" -- checks output properties). Step 13 gate items are phrased as anti-pattern checks ("Are extensions redefining standard API routes?") which are output review criteria, not input checks. P1-A confirms: no validator in `tools/specdev_tools/` references Self-Audit Gate, Coverage Closure, or "score < 0.9". Purely prompt-driven.
- **Impact**: LLMs unclear about WHEN to evaluate the gate (before or after generation). Quality checks on ungenerated output conflate planning with execution.
- **Proposed Fix**: Clarify gate purpose as **pre-emission input sufficiency check**. Move anti-pattern checks to Negative Constraints section. Move output-quality checks to a post-generation validation section or Coverage Closure.

#### AUDIT-011: Coverage Closure Structurally Coupled to Self-Audit Gate
- **Severity**: HIGH
- **Status**: verified
- **Source**: P1-D #9
- **Owner**: P1-D (Self-Audit Gate)
- **Target**: All 22 prompts (Coverage Closure as `### Coverage Closure` under `## Self-Audit Gate`)
- **Evidence**: Coverage Closure checks output completeness (did I consume all upstream IDs?) while Self-Audit Gate checks input sufficiency (can I produce this artifact?). By nesting Coverage Closure under Self-Audit Gate, both are evaluated at the same moment. An LLM might skip Coverage Closure if gate items pass, or treat Coverage Closure failures as Clarify triggers when they should be post-generation validation.
- **Impact**: Conflation obscures that these are two separate checks with different evaluation timing.
- **Proposed Fix**: Promote Coverage Closure to a sibling heading (`## Coverage Closure`) rather than a subsection. Self-Audit Gate = input sufficiency = Clarify/Emit decision. Coverage Closure = output completeness = post-generation validation.

#### AUDIT-013: No Lint for FR -> API Coverage Completeness (Steps 04 -> 05)
- **Severity**: HIGH
- **Status**: verified
- **Source**: P1-E #9
- **Owner**: P1-E (Traceability/Integrity)
- **Target**: `tools/specdev_tools/validation/traceability_closure.py` (absent check)
- **Evidence**: FR->API link covered only by W592 aggregate threshold (default 80%) and E590 generic broken-reference. No W-code equivalent to W561 (FR->roadmap) exists for FR->API. Prompt_05 Coverage Closure says "Every FR that specifies observable external behavior is covered by >=1 api_id" but lint does not enforce this per-FR.
- **Impact**: Individual FRs can lack API coverage without any lint warning, as long as aggregate percentage stays above threshold.
- **Proposed Fix**: Add W564 UNCOVERED_FR_API to `traceability_closure.py`: for each FR in `04_fr_list.json`, verify at least one API in `05_interface_contracts.json` has a trace with `type: "fr"` and matching ID. Exclude FRs tagged `internal-only` or `deferred`.

#### AUDIT-014: Step 09 Milestone Schema Lacks `depends_on` Field
- **Severity**: HIGH
- **Status**: verified
- **Source**: P1-E #1
- **Owner**: P1-E (Traceability/Integrity)
- **Target**: `schema/09_impl_plan.schema.json:34-86`
- **Evidence**: Step 09 milestones have no `depends_on` field. Prompt says "All dependencies between milestones are explicit -- no implicit ordering assumptions" but schema provides no field to express this. Step 14 tasks DO have `depends_on` (schema/14_roadmap.schema.json:152-158).
- **Impact**: Milestone dependency relationships are inexpressible in the schema, relying on implicit array ordering.
- **Proposed Fix**: Add optional `depends_on` array to Step 09 milestone schema. Add cycle-detection validator in a new `step_09.py` similar to Step 14's `_check_task_dependency_cycles`.

#### AUDIT-015: Step 14 Tasks Lack Direct FR Binding
- **Severity**: HIGH
- **Status**: verified
- **Source**: P1-E #2
- **Owner**: P1-E (Traceability/Integrity)
- **Target**: `schema/14_roadmap.schema.json:87-183`
- **Evidence**: Task schema has `task_id`, `description`, `acceptance_criteria`, `status`, `depends_on`, `assumptions`, `exit_conditions` -- no `fr_refs` or `trace` field. `fr_refs` exists only at milestone level. For a milestone with 10 FRs and 15 tasks, no machine-checkable way to verify every FR has a task.
- **Impact**: FR-to-task coverage within milestones is unverifiable by lint.
- **Proposed Fix**: Add optional `fr_refs` array to task objects. Add validator checking every FR in `milestone.fr_refs` is referenced by at least one task.

#### AUDIT-016: Semantic Drift Has No Dedicated Validator
- **Severity**: HIGH
- **Status**: verified
- **Source**: P1-E #3, P1-E #7
- **Owner**: P1-E (Traceability/Integrity)
- **Target**: `tools/specdev_tools/validation/` (entire directory)
- **Evidence**: No validator checks description consistency for traced IDs across steps. E590 checks ID existence, E555 checks IDs not dropped, W595 checks content staleness -- none validate semantic alignment. Steps 05, 09, 14 are highest drift risk (translate FRs into APIs/milestones/tasks with free-text descriptions).
- **Impact**: An API can claim to trace to `fr-user-login` while implementing different behavior. Milestone descriptions can reinterpret FR requirements.
- **Proposed Fix**: Strengthen prompt guidance for Steps 05, 06, 07 to say "use exact description text from Step 04 for traced FRs." Consider W-code that flags when description on a trace ref differs significantly from source artifact's description.

#### AUDIT-017: `docs_policy` Has Zero Functional Consumers After docs_lint.py Removal
- **Severity**: HIGH
- **Status**: verified
- **Source**: P1-C #1
- **Owner**: P1-C (Config)
- **Target**: `spec/common/seed_manifest.json:58-82`, `schema/seed_manifest.schema.json:115-169`
- **Evidence**: Only `step_16.py:180` reads `doc_paths` sub-field. `readme_required`, `root_readme_required`, `readme_depth_default`, `readme_depth_by_scope`, `scope`, `exclusions` have zero consumers since `docs_lint.py` was deleted.
- **Impact**: 22 lines of dead config + ~55 lines of dead schema definition maintained for no purpose.
- **Proposed Fix**: Extract `doc_paths` to a top-level field. Remove entire `docs_policy` block and schema definition. Update `step_16.py:180` to read from new location.

#### AUDIT-018: Seed Order, Context To Ingest, and Extraction Intent Triple Redundancy in Steps 00-04
- **Severity**: HIGH
- **Status**: verified
- **Source**: P1-C #7
- **Owner**: P1-C (Config)
- **Target**: `prompts/prompt_00_project_charter.md:39-55`, similarly in prompts 01-04
- **Evidence**: Steps 00-04 have three overlapping sections: Seed Order & Mandatory Sources (6/22), Context To Ingest (6/22), and Extraction Intent (22/22). Seed docs appear in all three. Steps 05-16c have only Extraction Intent -- no redundancy.
- **Impact**: ~72 lines of redundant content across 6 prompts. Maintenance risk: updating seed references requires editing 3 sections.
- **Proposed Fix**: Merge Seed Order and Context To Ingest into Extraction Intent for steps 00-04. Add one line: "Read `spec/common/seed_manifest.json` first; ingest seeds in `step_requirements['NN']` order before other context."

#### AUDIT-019: Extraction Mandate Covers Only 3 of 22 Steps
- **Severity**: HIGH
- **Status**: verified
- **Source**: P1-E #4
- **Owner**: P1-E (Traceability/Integrity)
- **Target**: `prompts/prompt_05_interface_contracts.md`, `prompts/prompt_08_fixtures.md`, `prompts/prompt_09_impl_plan.md`
- **Evidence**: Only Steps 04, 14, 16a have Extraction Mandates (hard "every upstream ID must be consumed" rules). Steps 05 (FR->API), 08 (FR->fixture), 09 (cap->milestone) lack mandates despite being critical traceability links.
- **Impact**: Requirements can silently drop at Steps 05, 08, 09 without the LLM being required to enumerate gaps.
- **Proposed Fix**: Add Extraction Mandates to: Step 05 ("Every FR with observable external behavior must map to >=1 API"), Step 08 ("Every high-priority FR must have >=1 fixture"), Step 09 ("Every capability ID must appear in >=1 milestone deliverable").

#### AUDIT-021: Missing Migration Templates for Steps 16a, 16b, 16c
- **Severity**: HIGH
- **Status**: verified
- **Source**: P1-G #1
- **Owner**: P1-G (Documentation)
- **Target**: `tools/specdev_tools/core/constants.py:15-35`, `prompts/migration/`
- **Evidence**: `STEP_TO_TEMPLATE` has no entries for 16a/16b/16c. `docs/agents/manifest.json` defines `step_config` for all three. Migration planner assigns `template=None`, causing runner to generate minimal prompts.
- **Impact**: `specdev align prompts` cannot generate migration guidance for Trinity Loop artifacts -- the most complex artifacts in the system.
- **Proposed Fix**: Create `template_impl_planner.md`, `template_impl_coder.md`, `template_impl_reviewer.md`. Add mappings to `STEP_TO_TEMPLATE`.

#### AUDIT-022: 00 -> 01 Lint Link Misses Success Metrics
- **Severity**: HIGH
- **Status**: verified
- **Source**: P1-E #8
- **Owner**: P1-E (Traceability/Integrity)
- **Target**: `tools/specdev_tools/validation/traceability_closure.py:82-97`
- **Evidence**: E560 checks every `goal_id` maps to a capability but `success_metrics` are not checked. A success metric like "reduce page load to <200ms" can exist in Step 00 without any capability or NFR tracing to it. Prompt_01 Coverage Closure says "Every goal AND success metric is addressed" but lint only checks goals.
- **Impact**: Success metrics can be silently dropped from the traceability chain.
- **Proposed Fix**: Extend E560 to check each `success_metric` ID is traced from at least one capability or NFR.

#### AUDIT-023: `allowed_upstream_dependencies` Is 275 Lines of Fully Derivable Data
- **Severity**: HIGH
- **Status**: verified
- **Source**: P1-C #4
- **Owner**: P1-C (Config)
- **Target**: `tools/step_order.json:41-315`
- **Evidence**: Under `strict_waterfall` policy, `allowed_upstream_dependencies[N]` = `steps[0..indexOf(N)-1]`. Pattern holds for all 22 steps with zero exceptions. 5 consumers: `cli.py`, `hallucination_lint.py`, `extraction_intent_check.py`, `dependency_order_lint.py`, `dag_lint.py`. Derivation: `steps[:steps.index(step_id)]`.
- **Impact**: 275 lines of redundant data that must be kept in sync with `steps` array.
- **Proposed Fix**: Add `derive_allowed_upstream(step_id)` function to a shared utility. Migrate 5 consumers. Remove or deprecate the JSON field. Update `step_order.schema.json`.

#### AUDIT-024: `_collect_required_seeds` Conflates Ordering with Membership
- **Severity**: HIGH
- **Status**: verified
- **Source**: P1-C #8, P1-C #14
- **Owner**: P1-C (Config)
- **Target**: `tools/specdev_tools/validation/seed_lint.py:61-62`
- **Evidence**: `_collect_required_seeds()` unions `global_seed_order` into every mapped step's requirements. Step 01 requires only `seed-overview` per `step_requirements` but the function returns `{"seed-overview", "seed-tech-stack"}` via `global_seed_order`. Already identified as bug in `WIP/trans/seed_update_plan.md:73`.
- **Impact**: Seed validation enforces false requirements on steps. Step 01 incorrectly requires `seed-tech-stack`.
- **Proposed Fix**: Change `_collect_required_seeds()` to use `global_seed_order` only for ordering, not for expanding requirements. Return only seeds in `step_requirements[step_id]`, sorted by `global_seed_order`.

---

### MEDIUM

#### AUDIT-012: 16a/16b/16c Have Redundant Duplicate Self-Audit Gate Headings
- **Severity**: MEDIUM (reverted to P1-D original MEDIUM; the upgrade to HIGH was editorial judgment from a single agent without cross-agent corroboration. The issue is a formatting/structural redundancy -- 8 words of redundant content per file -- not a functional defect. Potential LLM confusion is plausible but not evidence-based.)
- **Status**: verified
- **Source**: P1-D #3
- **Owner**: P1-D (Self-Audit Gate)
- **Target**: `prompts/prompt_16a_impl_planner.md:78,269`, `prompts/prompt_16b_impl_coder.md:180,213`, `prompts/prompt_16c_impl_reviewer.md:234,268`
- **Evidence**: Each Trinity Loop prompt has TWO Self-Audit Gate headings. The first "(Score Threshold)" contains ONLY "score < 0.9" with zero step-specific items. The second has actual Coverage Closure content. The first gate is entirely redundant (8 words per file, no unique content).
- **Impact**: LLM confusion about which gate to evaluate. Artifact of mechanical R6 remediation insertion.
- **Proposed Fix**: Remove "(Score Threshold)" headings from 16a/16b/16c. Merge threshold line into existing Self-Audit Gate section.

#### AUDIT-025: 46 of 53 Docs Are Never Referenced by Any Prompt
- **Severity**: MEDIUM
- **Status**: corroborated
- **Source**: P1-C #9, P1-C #15, P1-G #12, P1-G #5
- **Owner**: P1-C (Config) for mechanism, P1-G (Docs) for content
- **Target**: `docs/**/*.md` (53 files), `prompts/prompt_*.md` (22 files)
- **Evidence**: Only 7 docs referenced by prompts. High-value unreferenced docs: `governance_architecture.md` (steps 10, 12), `extension_schemas.md` (step 13), `path_conventions.md` (step 15), `error-codes.md` (steps 16b, 16c), `spec_to_impl.md` (steps 16a-16c), `discovery.md` (steps 00-04). No lazy-loading mechanism exists.
- **Impact**: AI agents lack context that would improve output quality for specific steps.
- **Proposed Fix**: Create a `step_docs` map (in `step_order.json` or new `tools/doc_map.json`) mapping steps to relevant docs. Enhance `prompt-context` or add `doc-context` command. Surface in prompts as optional context.

#### AUDIT-026: shared_expectations.md Lacks Documentation Resource Guidance
- **Severity**: MEDIUM
- **Status**: corroborated
- **Source**: P1-G #16, P1-G #12
- **Owner**: P1-G (Documentation)
- **Target**: `docs/prompts/shared_expectations.md`
- **Evidence**: 51 lines covering DoR, quality protocol, canonical reuse, step-order policy. No section addresses available documentation resources or step-to-doc relevance. Agent orchestrators have no way to discover which docs improve a step's output.
- **Impact**: Agents cannot discover relevant documentation without browsing manually.
- **Proposed Fix**: Add "Documentation Resources" section listing key docs and their step relevance.

#### AUDIT-027: No Granularity Guidance for Steps 04, 05, 07
- **Severity**: MEDIUM
- **Status**: verified
- **Source**: P1-B #6
- **Owner**: P1-B (Synthesis Quality)
- **Target**: `prompts/prompt_04_functional_requirements.md`, `prompts/prompt_05_interface_contracts.md`, `prompts/prompt_07_nfrs.md`
- **Evidence**: Step 04 says "each FR describes exactly one behavior" but does not define what constitutes "one behavior." Step 07 provides no framework for setting realistic numeric targets when baseline data is absent.
- **Impact**: Wildly inconsistent outputs between LLM runs (5 FRs vs 50 for the same system).
- **Proposed Fix**: Add granularity heuristics: Step 04: "Aim for 3-8 FRs per in-scope capability. If an FR requires >3 components, it may be too broad." Step 07: "For latency: target p95 < 500ms reads, < 1000ms writes as starting point."

#### AUDIT-028: Generic Role Definition for 14 of 22 Steps
- **Severity**: MEDIUM
- **Status**: verified
- **Source**: P1-B #2
- **Owner**: P1-B (Synthesis Quality)
- **Target**: 14 prompts using "senior specification author and validator"
- **Evidence**: Steps 00-10, 12, 15 share identical role text. Step 11's distinct role ("senior security architect... think like an attacker") primes adversarial reasoning. Step 04's generic role primes form-filling.
- **Impact**: Generic role provides no synthesis context for step-specific reasoning challenges.
- **Proposed Fix**: Give each step a role priming its reasoning mode. Step 04: "senior requirements engineer who decomposes capabilities into falsifiable behavioral specifications." Step 06: "systems reliability engineer who identifies invariants preventing data corruption."

#### AUDIT-029: No Weak-vs-Strong Examples in 19 of 22 Prompts
- **Severity**: MEDIUM
- **Status**: verified
- **Source**: P1-B #8
- **Owner**: P1-B (Synthesis Quality)
- **Target**: All prompts except 11, 13
- **Evidence**: Only Step 11 has a concrete weak-vs-strong examples table. This single table communicates quality bar more effectively than paragraphs of prose rules. 19 prompts lack this.
- **Impact**: LLMs cannot calibrate output quality without concrete examples of good vs bad output.
- **Proposed Fix**: Add 3-5 row weak-vs-strong tables to at minimum Steps 04, 05, 06, 07, 08.

#### AUDIT-030: Coverage Closure Checklist Is Mechanical, Not Reasoning-Oriented
- **Severity**: MEDIUM
- **Status**: verified
- **Source**: P1-B #9
- **Owner**: P1-B (Synthesis Quality)
- **Target**: All 22 prompts' Coverage Closure sections
- **Evidence**: Universal checklist items ("Every upstream ID consumed", "No placeholders", "No hallucination") are traceability checks, not reasoning checks. Missing: "Does every capability have both happy-path AND error-path FRs?"
- **Impact**: Structural completeness verified but logical completeness not checked.
- **Proposed Fix**: Add 2-3 step-specific reasoning verification items to each Coverage Closure section.

#### AUDIT-031: Extraction Intent Lacks Priority Grouping
- **Severity**: MEDIUM
- **Status**: verified
- **Source**: P1-B #10
- **Owner**: P1-B (Synthesis Quality)
- **Target**: Late-stage prompts (12, 14, 15, 16, 16a, 16b, 16c)
- **Evidence**: Step 14 lists 16 upstream artifacts. Step 16b lists 20. Each gets one-line description with equal weight. LLM cannot distinguish "must deeply analyze" from "reference for consistency."
- **Impact**: Shallow processing of critical inputs; deep processing of peripheral inputs.
- **Proposed Fix**: Group extraction intents into "Primary Sources" and "Reference Sources."

#### AUDIT-032: Trinity Loop Evidence Binding Is Partially Prompt-Enforced Only
- **Severity**: MEDIUM
- **Status**: verified
- **Source**: P1-E #6
- **Owner**: P1-E (Traceability/Integrity)
- **Target**: `prompts/prompt_16b_impl_coder.md`, `prompts/prompt_16c_impl_reviewer.md`, `tools/specdev_tools/validation/validators/step_16.py`
- **Evidence**: Schema DOES require `linked_test_expectation` on checklist items (`schema/16_impl_context.schema.json` lines 554-558: `required: ["id", "spec_ref", "description", "linked_test_expectation"]`). However, `evidence` on verified actions is NOT schema-required, and `ci_status: green` for `verdict: verified` has no cross-field validation. These two enforcement gaps remain prompt-only.
- **Impact**: Artifacts with missing evidence on verified actions, or red CI status with verified verdict, pass schema validation. The `linked_test_expectation` gap originally cited in P1-E #6 is already schema-enforced and is NOT a gap.
- **Proposed Fix**: Add validator in `step_16.py`: (1) verified actions have `evidence` with non-empty `content`, (2) `verdict: verified` requires `fixture_status.ci_status: green`. Note: `linked_test_expectation` is already schema-required and needs no additional validator.

#### AUDIT-033: Step 14 Does Not Trigger Trace Matrix Update
- **Severity**: MEDIUM
- **Status**: verified
- **Source**: P1-E #5
- **Owner**: P1-E (Traceability/Integrity)
- **Target**: `tools/specdev_tools/validation/matrix.py:170-305`
- **Evidence**: Trace matrix built from Steps 04/05/07/08 only. Step 14's `fr_refs` on milestones are not included. W561 catches uncovered FRs separately, but the matrix lacks milestone coverage view.
- **Impact**: Single-pane traceability view incomplete -- cannot see which FRs are scheduled vs unscheduled.
- **Proposed Fix**: Add "milestone_coverage" column to trace matrix from Step 14 `fr_refs`. Low priority since W561 already catches uncovered FRs.

#### AUDIT-034: No Validator Enforces Tech Stack Consistency Across Steps 02, 09, 14
- **Severity**: MEDIUM
- **Status**: verified
- **Source**: P1-C #10, P1-C #13
- **Owner**: P1-C (Config)
- **Target**: `prompts/prompt_09_impl_plan.md:53-54`, `tools/specdev_tools/validation/`
- **Evidence**: Tech stack flows: `seed_tech_stack.md` -> Step 02 -> Step 09 -> Step 14. Step 09 cross-checks against `01_capabilities.json` (not Step 02). No validator checks alignment between steps. Step 09 extraction intent omits technology choices from Step 02.
- **Impact**: Technology decisions can drift silently across the pipeline.
- **Proposed Fix**: (1) Update Step 09 extraction intent for `02_system_sketch.json` to include technology choices. (2) Consider `tech-stack-lint` or integration into `spec-quality-lint`.

#### AUDIT-035: `nested_order` Provides Zero Value Beyond `global_seed_order`
- **Severity**: MEDIUM
- **Status**: verified
- **Source**: P1-C #2
- **Owner**: P1-C (Config)
- **Target**: `spec/common/seed_manifest.json:11-19`, `tools/specdev_tools/validation/seed_lint.py:261-264`
- **Evidence**: Single entry "foundation" containing same 2 seeds as `global_seed_order`. Redundant validation. Prior audit (FIX-063, FIX-076) already decided to remove. Approved but not executed.
- **Impact**: 9 lines of dead config + redundant validation logic.
- **Proposed Fix**: Execute already-decided removal: delete `nested_order` from data, schema, and `seed_lint.py` consumer.

#### AUDIT-036: shared_expectations.md Referenced by Only 8 of 22 Prompts
- **Severity**: MEDIUM
- **Status**: corroborated
- **Source**: P1-A #10, P1-A #11
- **Owner**: P1-A (Bloat)
- **Target**: `docs/prompts/shared_expectations.md`, 14 prompts not referencing it
- **Evidence**: Referenced by 8 prompts (00, 01, 02, 02a, 03, 04, 16b, 16c). 14 prompts miss it entirely. Current content (51 LOC) overlaps with inline sections using different wording (e.g., "one-go Quality Protocol" vs "Hardening Protocol").
- **Impact**: Inconsistent guidance: 8 prompts get double-stated rules, 14 get no shared reference.
- **Proposed Fix**: After extraction (AUDIT-006), add universal reference to `shared_expectations.md` in all 22 prompts. Reconcile wording to eliminate double-statements.

#### AUDIT-037: Step 13 Gate Items Are Anti-Pattern Checks, Not Input-Sufficiency Checks
- **Severity**: MEDIUM
- **Status**: verified
- **Source**: P1-D #7
- **Owner**: P1-D (Self-Audit Gate)
- **Target**: `prompts/prompt_13_extension_generator.md:72-77`
- **Evidence**: Five gate items phrased as output review criteria ("Are extensions redefining standard API routes?", "Are you creating extensions for already-expressible items?"). These ask the LLM to review its OWN planned output. Other steps' gate items check input availability.
- **Impact**: Gate conflates input-sufficiency with output review, creating inconsistent gate semantics.
- **Proposed Fix**: Move anti-pattern items to Negative Constraints section. Replace with input-sufficiency checks: "Extension candidates grounded in domain requirements not expressible in core steps 00-15" and "Interface contracts from Step 05 available for overlap detection."

#### AUDIT-038: Step 05 Lacks API Design Reasoning Framework
- **Severity**: MEDIUM
- **Status**: verified
- **Source**: P1-B #11
- **Owner**: P1-B (Synthesis Quality)
- **Target**: `prompts/prompt_05_interface_contracts.md:48-53`
- **Evidence**: Step 05 feeds 9 downstream steps but uses generic operating flow. No guidance on resource naming, URL structure, pagination, error schema, status codes. LLM must make REST design decisions with no domain scaffolding.
- **Impact**: Inconsistent API designs across LLM runs; no standards for common patterns.
- **Proposed Fix**: Add "REST Design Heuristics" section: resource naming from glossary, CRUD mapping, standard error shape, pagination pattern, nested vs flat routes.

#### AUDIT-039: Step 06 Lacks Systematic Invariant Discovery Method
- **Severity**: MEDIUM
- **Status**: verified
- **Source**: P1-B #12
- **Owner**: P1-B (Synthesis Quality)
- **Target**: `prompts/prompt_06_invariants.md:55-59`
- **Evidence**: Lists categories of invariants but no systematic discovery method. "MUST include data integrity constraints implied by entities" tells WHAT but not HOW.
- **Impact**: LLMs miss implicit invariants not derivable from surface-level FR analysis.
- **Proposed Fix**: Add invariant discovery checklist: "For each entity: states? transitions? quantities? bounds? references? cascade rules? For each API: mutations? idempotency? trust boundaries? access rules?"

#### AUDIT-040: Output Contract Examples Contradict Prompt Guidance
- **Severity**: MEDIUM
- **Status**: verified
- **Source**: P1-B #14
- **Owner**: P1-B (Synthesis Quality)
- **Target**: `prompts/prompt_07_nfrs.md:190`, `prompts/prompt_01_capabilities.md:186`
- **Evidence**: Step 07 example uses `"measurement_method": "automated monitoring"` despite prompt explicitly banning "generic phrases like 'automated monitoring'." Step 01 example uses `"capability_id": "capability-authentication"` but guidance requires "capability-<verb>-<object>" format.
- **Impact**: LLMs that follow examples over prose rules produce invalid output.
- **Proposed Fix**: Fix examples to comply with prompt rules. Step 07: use concrete PromQL/monitoring query. Step 01: use `"capability-authenticate-user"`.

#### AUDIT-041: Prompt 09 Quick Reference Omits Multiple Required Fields
- **Severity**: MEDIUM
- **Status**: verified
- **Source**: P1-F #6, P1-F #9
- **Owner**: P1-F (Schema Descriptions)
- **Target**: `prompts/prompt_09_impl_plan.md:133-134`
- **Evidence**: Quick Reference says "Required: `tech_stack`" -- omits `milestones` and `trace`. Milestone required fields list shows `milestone_id`, `name` -- omits `deliverables` and `status`. Schema: `required: ["tech_stack", "milestones", "trace"]`, milestone required: `["milestone_id", "name", "deliverables", "status"]`.
- **Impact**: LLMs following Quick Reference produce invalid JSON missing required fields.
- **Proposed Fix**: Update to: "Required: `tech_stack`, `milestones`, `trace`. Per milestone: `milestone_id`, `name`, `deliverables`, `status`."

#### AUDIT-042: Prompt 00 Quick Reference Omits `stakeholders` and `user_segments`
- **Severity**: MEDIUM
- **Status**: verified
- **Source**: P1-F #7
- **Owner**: P1-F (Schema Descriptions)
- **Target**: `prompts/prompt_00_project_charter.md:142`
- **Evidence**: Quick Reference: "Required: `id`, `owner`, `created_at`, `problem_statement`, `success_metrics`". Schema: `required: ["problem_statement", "success_metrics", "stakeholders", "user_segments"]`.
- **Impact**: LLMs may omit `stakeholders` and `user_segments` from charter output.
- **Proposed Fix**: Add `stakeholders`, `user_segments` to Quick Reference required list.

#### AUDIT-043: Prompt 05 Quick Reference Omits `interface_ref`
- **Severity**: MEDIUM
- **Status**: verified
- **Source**: P1-F #8
- **Owner**: P1-F (Schema Descriptions)
- **Target**: `prompts/prompt_05_interface_contracts.md:134`
- **Evidence**: Quick Reference: "each API needs `api_id`, `name`, `version`, `protocol`, and `owner`". Schema: `required: ["api_id", "name", "version", "protocol", "owner", "interface_ref"]`.
- **Impact**: LLMs omit `interface_ref` from API entries, causing validation failure.
- **Proposed Fix**: Add `interface_ref` to Quick Reference required fields.

#### AUDIT-044: Prompt 16 Output Contract Missing `canonical_refs_used`
- **Severity**: MEDIUM
- **Status**: verified
- **Source**: P1-F #10
- **Owner**: P1-F (Schema Descriptions)
- **Target**: `prompts/prompt_16_impl_context.md:265-365`
- **Evidence**: Output Contract JSON omits `canonical_refs_used` which is required by `step_base.schema.json` (`required: ["id", "owner", "created_at", "canonical_refs_used"]`).
- **Impact**: LLMs following Output Contract template produce invalid JSON.
- **Proposed Fix**: Add `"canonical_refs_used": []` to Output Contract example.

#### AUDIT-045: Migration Templates Lack Reference to Step Prompts
- **Severity**: MEDIUM
- **Status**: corroborated
- **Source**: P1-G #11, P1-G #14, P1-G #18
- **Owner**: P1-G (Documentation)
- **Target**: `prompts/migration/template_*.md` (all 19), `tools/specdev_tools/migration/runner.py:198-244`
- **Evidence**: Templates do not reference corresponding step prompts. Migration runner renders templates without including step prompt field-level coverage. AI-assisted migrations operate with significantly less guidance than fresh generation.
- **Impact**: Migrations produce lower-quality output than fresh generation despite being more complex operations.
- **Proposed Fix**: Add "Full Generation Reference" section to each template linking to step prompt. Enhance `_render_prompt()` to include step prompt field-by-field section.

#### AUDIT-046: template_frs.md References Wrong Artifact Filename
- **Severity**: MEDIUM
- **Status**: verified
- **Source**: P1-G #3
- **Owner**: P1-G (Documentation)
- **Target**: `prompts/migration/template_frs.md:33`
- **Evidence**: References `spec/04_functional_requirements.json` -- canonical name is `spec/04_fr_list.json` per `schema_registry.json` entry `vc:04-fr-list`.
- **Impact**: Validation command in template will fail.
- **Proposed Fix**: Change to `spec/04_fr_list.json`.

#### AUDIT-047: workflow_bootstrap_legacy.md Uses Outdated Patterns
- **Severity**: MEDIUM
- **Status**: verified
- **Source**: P1-G #8
- **Owner**: P1-G (Documentation)
- **Target**: `docs/developers/workflows/workflow_bootstrap_legacy.md`
- **Evidence**: Pre-Clarify/Emit protocol. Artifact names `docs/project_overview.md` and `docs/tech_stack.md` not part of current seed system. Line 69: "Convert docs/tech_stack.md into spec/01_capabilities.json" -- capabilities derive from seed_overview, not tech_stack.
- **Impact**: Users following this workflow produce artifacts using wrong conventions.
- **Proposed Fix**: Rewrite to use current seed paths, two-phase protocol, correct step mappings.

#### AUDIT-048: workflow_feature_extension.md Uses Pre-Clarify/Emit Patterns
- **Severity**: MEDIUM
- **Status**: verified
- **Source**: P1-G #9
- **Owner**: P1-G (Documentation)
- **Target**: `docs/developers/workflows/workflow_feature_extension.md`
- **Evidence**: Lines 41-46 instruct copying generic prompts rather than using canonical step prompts with Clarify/Emit protocol.
- **Impact**: Feature extensions bypass Self-Audit Gate and Coverage Closure.
- **Proposed Fix**: Update to reference canonical step prompts and two-phase protocol.

#### AUDIT-049: Migration Templates Use No Interpolation Variables Despite ADR
- **Severity**: MEDIUM
- **Status**: verified
- **Source**: P1-G #4
- **Owner**: P1-G (Documentation)
- **Target**: `prompts/migration/template_*.md` (all 19), `docs/ops/adr_template_engine.md`
- **Evidence**: ADR describes Handlebars `{{VAR}}` syntax. Zero templates contain `{{` markers. Runner reads templates as static markdown.
- **Impact**: Templates cannot be context-aware; ADR describes unimplemented capability.
- **Proposed Fix**: Either implement interpolation variables in templates or update ADR to clarify templates are static.

---

### LOW

#### AUDIT-050: Gate Item Counts Vary Widely Without Justification
- **Severity**: LOW
- **Status**: verified
- **Source**: P1-D #4
- **Owner**: P1-D (Self-Audit Gate)
- **Target**: All 22 prompts
- **Evidence**: Range from 2 items (steps 07, 08) to 6 items (steps 00, 11, 16). Step 07 has 2 gate items despite 9 required schema fields and complex metric structures.
- **Impact**: Inconsistent gate rigor across steps.
- **Proposed Fix**: Normalize gate items to consistent methodology derived from upstream dependencies and schema `required[]` array.

#### AUDIT-051: traceRef.type Description Lacks Valid Values List
- **Severity**: LOW (resolved down from P1-F MEDIUM; canon file reference is present, just not enumerated)
- **Status**: verified
- **Source**: P1-F #1
- **Owner**: P1-F (Schema Descriptions)
- **Target**: `schema/core/collections.schema.json:62`
- **Evidence**: Description says "validated against canon/kinds/trace_type.json entries" but does not enumerate common values. LLM generating artifacts cannot know valid values from description alone.
- **Proposed Fix**: Add examples array or enumerate common trace types in description.

#### AUDIT-052: atoms.owner Description Lacks Valid Values
- **Severity**: LOW (resolved down from P1-F MEDIUM; same pattern as AUDIT-051)
- **Status**: verified
- **Source**: P1-F #2
- **Owner**: P1-F (Schema Descriptions)
- **Target**: `schema/core/atoms.schema.json:42`
- **Evidence**: Description says "validated against canon/kinds/owner.json entries" but does not list the 8 standard owners. Prompts hardcode the list but schema description is insufficient for standalone generation.
- **Proposed Fix**: Add `examples` array listing 8 standard owners (like `kebabId` already has).

#### AUDIT-053: stageName and environmentName Have Identical Enum but Unclear Distinction
- **Severity**: LOW (resolved down from P1-F MEDIUM; functionally correct, just unclear)
- **Status**: verified
- **Source**: P1-F #4
- **Owner**: P1-F (Schema Descriptions)
- **Target**: `schema/core/collections.schema.json:247,256`
- **Evidence**: Both have enum `[dev, ci, staging, prod]`. Descriptions nearly identical: "Deployment environment name" vs "Pipeline stage name indicating the deployment target."
- **Proposed Fix**: Clarify: `stageName` for NFR `stage` fields (delivery phase), `environmentName` for infrastructure configs in Step 02a. Or consolidate.

#### AUDIT-054: 16_impl_context Deep-Nested status_ref Descriptions Repetitive
- **Severity**: LOW
- **Status**: verified
- **Source**: P1-F #3
- **Owner**: P1-F (Schema Descriptions)
- **Target**: `schema/16_impl_context.schema.json` (14+ locations)
- **Evidence**: 14 `status_ref` and `command_ref` fields use nearly identical descriptions: "Canonical reference for the [X] status in the registry." No disambiguation of expected `kind` or ID.
- **Proposed Fix**: Add expected `kind` value or example ID to each status_ref description.

#### AUDIT-055: emergent_ambiguities.severity Lacks Enum Constraint
- **Severity**: LOW
- **Status**: verified
- **Source**: P1-F #14
- **Owner**: P1-F (Schema Descriptions)
- **Target**: `schema/16_impl_context.schema.json:1638`
- **Evidence**: Planning `ambiguities.severity` constrained to `["blocking", "non_blocking"]`. Emergent `ambiguities.severity` is unconstrained `string`. Same concept, different constraints.
- **Proposed Fix**: Add enum constraint or document why emergent ambiguities use free-form severity.

#### AUDIT-056: Prompt 00 Output Contract Omits in_scope/out_of_scope Despite minItems:3
- **Severity**: LOW
- **Status**: verified
- **Source**: P1-F #16
- **Owner**: P1-F (Schema Descriptions)
- **Target**: `prompts/prompt_00_project_charter.md:186-244`
- **Evidence**: Schema has `minItems: 3` on `in_scope`/`out_of_scope`. Not in `required` but Self-Audit Gate says they must have >=3 items. Output Contract omits them entirely.
- **Impact**: Contradictory signal: gate expects them, contract omits them.
- **Proposed Fix**: Add `in_scope` and `out_of_scope` to Output Contract example with 3+ placeholder items.

#### AUDIT-057: dependencyList vs dependencyObjectList Difference Undocumented
- **Severity**: LOW
- **Status**: verified
- **Source**: P1-F #12
- **Owner**: P1-F (Schema Descriptions)
- **Target**: `schema/14_roadmap.schema.json:228` vs `schema/09_impl_plan.schema.json:93`
- **Evidence**: Step 14 requires structured objects only (`dependencyObjectList`). Step 09 allows mixed strings/objects (`dependencyList`). Both have identical description text.
- **Proposed Fix**: Step 14 description should note: "Unlike Step 09, roadmap dependencies must be structured objects to enforce owner and note fields."

#### AUDIT-058: No Cross-Step Consistency Verification Guidance
- **Severity**: LOW
- **Status**: verified
- **Source**: P1-B #15
- **Owner**: P1-B (Synthesis Quality)
- **Target**: All prompts
- **Evidence**: Prompts check traceability (forward/backward) but not cross-artifact consistency between sibling steps (e.g., FRs and APIs telling a consistent story).
- **Proposed Fix**: Add "Cross-Artifact Consistency" check to Steps 04-08 prompts.

#### AUDIT-059: ADR Template Engine Doc Has Stale Template Count
- **Severity**: LOW
- **Status**: verified
- **Source**: P1-G #7
- **Owner**: P1-G (Documentation)
- **Target**: `docs/ops/adr_template_engine.md:31,38`
- **Evidence**: States "14 templates" -- actual count is 19.
- **Proposed Fix**: Update to 19.

#### AUDIT-060: docs/README.md Missing Several Doc References
- **Severity**: LOW
- **Status**: verified
- **Source**: P1-G #10
- **Owner**: P1-G (Documentation)
- **Target**: `docs/README.md`
- **Evidence**: "For Developers" table has 4 entries. Full developer doc set has 15+ files. Missing links to error-codes, path_conventions, workflows, tools, governance_architecture.
- **Proposed Fix**: Add missing doc links organized by category.

#### AUDIT-061: workflow_align.md and workflow_migration.md Reference Wrong Venv Name
- **Severity**: LOW
- **Status**: verified
- **Source**: P1-G #17
- **Owner**: P1-G (Documentation)
- **Target**: `docs/developers/workflows/workflow_align.md:38`, `docs/developers/workflows/workflow_migration.md`
- **Evidence**: References `source dev_env/bin/activate`. Correct name is `devspec_env`.
- **Proposed Fix**: Update `dev_env` to `devspec_env`.

#### AUDIT-066: connection.schema_ref `-tbd` Placeholder Convention Not Documented in Description
- **Severity**: LOW
- **Status**: verified
- **Source**: P1-F #11
- **Owner**: P1-F (Schema Descriptions)
- **Target**: `schema/02_system_sketch.schema.json:120`
- **Evidence**: The `schema_ref` field has pattern `^(?:-tbd|(file://|https://|glossary:|api:).+)$` supporting `-tbd` as a valid value, but the description says only "Reference to the schema governing data exchanged over this connection." The `-tbd` placeholder convention is not explained; an LLM would not know that `-tbd` is the accepted placeholder when the exchange schema is not yet defined.
- **Impact**: LLMs generating system sketch connections may not know how to handle undefined schemas, potentially producing invalid values or omitting the field.
- **Proposed Fix**: Update description to: "Reference to the schema governing data exchanged over this connection. Use '-tbd' if the exchange schema is not yet defined. Supported prefixes: file://, https://, glossary:, api:."

---

### INFO

#### AUDIT-062: Prompt Output Contracts Inconsistently Include $schema Field
- **Severity**: INFO
- **Status**: verified
- **Source**: P1-F #18
- **Owner**: P1-F (Schema Descriptions)
- **Target**: Multiple prompt Output Contract sections
- **Evidence**: Prompt 14 includes `"$schema": "vc:14-roadmap"` with note about stripping. Prompts 00, 05, 09, 16 omit it. Not a validation issue (step_base makes it optional) but inconsistent.
- **Proposed Fix**: Standardize: either all include `$schema` or none do.

#### AUDIT-063: generation_quality Fully Purged -- Verified Complete
- **Severity**: INFO
- **Status**: verified
- **Source**: P1-D #8
- **Owner**: P1-D (Self-Audit Gate)
- **Target**: N/A (verification finding)
- **Evidence**: 0 matches in prompts/, schema/, tools/. 4 test matches are negative assertions confirming field is NOT required. Purge complete and verified.
- **Proposed Fix**: None needed. Historical records in `docs/audit/` should be preserved.

#### AUDIT-064: audit/ Docs Are Historical but Not Marked as Archived
- **Severity**: INFO
- **Status**: verified
- **Source**: P1-G #13
- **Owner**: P1-G (Documentation)
- **Target**: `docs/audit/` (20+ files)
- **Evidence**: All from v0.3.0 structural audit (R1-R9). Not living documents.
- **Proposed Fix**: Consider adding `_ARCHIVED.md` marker or moving to `docs/audit/archive/`.

#### AUDIT-065: Projected Extraction Summary -- ~927 LOC Recoverable
- **Severity**: INFO
- **Status**: verified
- **Source**: P1-A #12
- **Owner**: P1-A (Bloat)
- **Target**: All 22 prompts + `shared_expectations.md`
- **Evidence**: Hardening Protocol 132 + Canonical Registry 154 + Canonical Binding Rules 132 + Path Variables 176 + Metadata Contract 66 + generic Coverage Closure 66 + generic Output Rules ~75 + Tool Execution ~66 + Quick Reference ~60 = ~927 LOC. Current: 5,727 LOC. After: ~4,800 LOC (~16% reduction). shared_expectations.md grows from 51 to ~130-160 LOC.
- **Proposed Fix**: Implement in three phases per AUDIT-006.

---

## Cross-Reference: P1 Finding to AUDIT-NNN Mapping

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
| P1-B | #1 Boilerplate dominates | AUDIT-006 (corroboration), AUDIT-001 |
| P1-B | #2 Generic role | AUDIT-028 |
| P1-B | #3 Conflicting inputs | AUDIT-002 |
| P1-B | #4 Implicit requirements | AUDIT-003 |
| P1-B | #5 Operating Flow homogeneity | AUDIT-001 |
| P1-B | #6 No granularity guidance | AUDIT-027 |
| P1-B | #7 Step 00 seed extraction | (absorbed into AUDIT-001 context) |
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
| P1-C | #3 step_requirements 00-04 only | (informational, no finding needed) |
| P1-C | #4 allowed_upstream derivable | AUDIT-023 |
| P1-C | #5 coverage_thresholds OK | (no finding -- correctly placed) |
| P1-C | #6 downstream_consumers OK | (no finding -- correctly placed) |
| P1-C | #7 Triple redundancy | AUDIT-018 |
| P1-C | #8 Seed ordering bug | AUDIT-024 |
| P1-C | #9 46 docs unreferenced | AUDIT-025 |
| P1-C | #10 Tech stack consistency | AUDIT-034 |
| P1-C | #11 prompt-context useful | (no finding -- confirmed useful) |
| P1-C | #12 seed_manifest vs step_order | (no finding -- separation justified) |
| P1-C | #13 Step 09 extraction omits tech | AUDIT-034 (sub-point) |
| P1-C | #14 global_seed_order conflation | AUDIT-024 |
| P1-C | #15 Doc-awareness gap | AUDIT-025 |
| P1-D | #1 Score undefined | AUDIT-009 |
| P1-D | #2 Dual role confusion | AUDIT-010 |
| P1-D | #3 16a/16b/16c duplicate gates | AUDIT-012 |
| P1-D | #4 Gate item count variance | AUDIT-050 |
| P1-D | #5 Gate items step-specific | AUDIT-006 (generic checklist extraction) |
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
| P1-E | #11 Anchor drift no enforcement | (absorbed into AUDIT-032 context) |
| P1-E | #12 Proposed W565 | AUDIT-015 (sub-point) |
| P1-E | #13 Proposed W564 | AUDIT-013 (sub-point) |
| P1-E | #14 16c no roadmap check | AUDIT-004 |
| P1-E | #15 09->14 partial | AUDIT-005 |
| P1-F | #1 traceRef.type values | AUDIT-051 |
| P1-F | #2 owner values | AUDIT-052 |
| P1-F | #3 status_ref repetitive | AUDIT-054 |
| P1-F | #4 stageName vs environmentName | AUDIT-053 |
| P1-F | #5 nfr_id pattern | (no finding -- intentional design) |
| P1-F | #6 Prompt 09 Quick Ref | AUDIT-041 |
| P1-F | #7 Prompt 00 Quick Ref | AUDIT-042 |
| P1-F | #8 Prompt 05 Quick Ref | AUDIT-043 |
| P1-F | #9 Prompt 09 milestone fields | AUDIT-041 |
| P1-F | #10 Prompt 16 canonical_refs | AUDIT-044 |
| P1-F | #11 schema_ref -tbd | AUDIT-066 |
| P1-F | #12 dependency type difference | AUDIT-057 |
| P1-F | #13 canonicalRef.version | (no finding -- low impact) |
| P1-F | #14 emergent severity | AUDIT-055 |
| P1-F | #15 stringArray generic | (no finding -- generic by design) |
| P1-F | #16 in_scope/out_of_scope | AUDIT-056 |
| P1-F | #17 environment_protection | (no finding -- adequate) |
| P1-F | #18 $schema inconsistency | AUDIT-062 |
| P1-G | #1 Missing 16a/16b/16c templates | AUDIT-021 |
| P1-G | #2 Template schema drift | AUDIT-020 |
| P1-G | #3 template_frs wrong filename | AUDIT-046 |
| P1-G | #4 No interpolation | AUDIT-049 |
| P1-G | #5 extension_schemas unreferenced | AUDIT-025 |
| P1-G | #6 agents.md not in prompts | (no finding -- correctly positioned) |
| P1-G | #7 ADR stale count | AUDIT-059 |
| P1-G | #8 bootstrap legacy outdated | AUDIT-047 |
| P1-G | #9 feature extension outdated | AUDIT-048 |
| P1-G | #10 README missing links | AUDIT-060 |
| P1-G | #11 Templates lack prompt ref | AUDIT-045 |
| P1-G | #12 No step-to-doc map | AUDIT-025, AUDIT-026 |
| P1-G | #13 audit/ not archived | AUDIT-064 |
| P1-G | #14 Migration no step prompt | AUDIT-045 |
| P1-G | #15 governance_arch unreferenced | AUDIT-025 |
| P1-G | #16 shared_expectations no docs | AUDIT-026 |
| P1-G | #17 Wrong venv name | AUDIT-061 |
| P1-G | #18 Template consolidation | AUDIT-045 |
