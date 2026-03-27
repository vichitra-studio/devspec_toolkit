# P1-E: End-to-End Requirement Integrity & Semantic Drift -- Findings

## Summary
- Total findings: 14
- Critical: 2 | High: 5 | Medium: 4 | Low: 2 | Info: 1

## Traceability Chain Analysis

### Link-by-Link Enforcement Inventory

The primary requirement chain is: seed -> 00 -> 01 -> 02 -> 02a -> 03 -> 04 -> 05 -> 06 -> 07 -> 08 -> 09 -> 14 -> 16a -> 16b -> 16c. Below is the enforcement status for each critical link.

#### Link 1: Seed -> 00 (Charter)
- **Enforcement**: Prompt-only (seed_manifest.json step_requirements + Extraction Intent)
- **Prompt guidance**: "Read `spec/common/seed_manifest.json` first; follow `global_seed_order` and `step_requirements["00"]`"
- **Lint**: seed-lint validates seed_manifest.json exists and seed files are referenced, but does NOT validate that content was actually extracted
- **Can requirements silently drop?** YES -- no lint verifies that specific seed content items appear in the charter
- **Risk**: LOW (charter is human-reviewed root document)

#### Link 2: 00 -> 01 (Charter -> Capabilities)
- **Enforcement**: LINT (E560 via traceability_closure.py line 97)
- **What it checks**: Every goal_id in 00_charter.json has at least one capability with trace type "charter-goal" pointing to it
- **Prompt guidance**: Coverage Closure requires "Every goal and success metric in `spec/00_charter.json` is addressed by >=1 `capability_id`"
- **Can requirements silently drop?** NO for goals (E560 catches orphans). YES for success_metrics (not checked by lint)

#### Link 3: 01 -> 04 (Capabilities -> FRs)
- **Enforcement**: LINT (E560 via traceability_closure.py line 137)
- **What it checks**: Every capability_id has at least one FR with trace type "capability" pointing to it
- **Prompt guidance**: Extraction Mandate: "Every capability ID from `01_capabilities.json` must map to >=1 FR"
- **Additional**: cross_artifact_checks.py check_step_04_integrity validates FR traces resolve to real capability IDs
- **Can requirements silently drop?** NO -- double coverage (lint + mandate)

#### Link 4: 04 -> 14 (FRs -> Roadmap)
- **Enforcement**: LINT (W561 via traceability_closure.py line 141)
- **What it checks**: Every fr_id appears in at least one milestone's fr_refs array
- **Prompt guidance**: Extraction Mandate: "Every FR ID from `04_functional_requirements.json` must appear in >=1 milestone's `fr_refs`"
- **Schema**: fr_refs is required on milestones (schema line 208-217)
- **Validator**: step_14.py validates fr_refs exist in Step 04 (E590)
- **Can requirements silently drop?** NO -- W561 catches uncovered FRs

#### Link 5: 14 -> 16a (Roadmap -> Implementation Planner)
- **Enforcement**: LINT (W562 + W563 via traceability_closure.py lines 144-151)
- **What it checks**: W562 = every milestone_id in roadmap has at least one checklist item; W563 = every task_id has at least one checklist item
- **Prompt guidance**: Extraction Mandate: "Every milestone from `14_roadmap.json` must appear in >=1 checklist item"; Roadmap-to-Checklist Coverage section is detailed
- **Can requirements silently drop?** NO -- W562/W563 catch orphaned milestones/tasks

#### Link 6: 16a -> 16b (Planner -> Coder)
- **Enforcement**: Prompt-only (structural -- same JSON artifact)
- **What it checks**: 16b reads checklist from plan.spec_alignment.checklist and fills implementation slots
- **Prompt guidance**: "Iterate Checklist Items" -- detailed operating flow
- **Can requirements silently drop?** PARTIALLY -- if a checklist item is silently skipped during execution, the coder can mark status without proper evidence (16c catches this)

#### Link 7: 16b -> 16c (Coder -> Reviewer)
- **Enforcement**: Prompt-only (structural -- same JSON artifact)
- **What it checks**: 16c audits each checklist item's implementation status and evidence
- **Prompt guidance**: Audit Checklist (6-point mandatory checklist per item)
- **Can requirements silently drop?** NO -- reviewer must check every item, semantic_review.fr_coverage required for verdict:verified

#### Link 8: 04 -> 05 (FRs -> Interface Contracts)
- **Enforcement**: Prompt-only + generic E590 (broken reference)
- **Prompt guidance**: Coverage Closure: "Every FR...that specifies an observable external behavior is covered by >=1 `api_id`"
- **Can requirements silently drop?** YES -- no specific lint validates FR-to-API completeness

#### Link 9: 05 -> 08 (Interface Contracts -> Fixtures)
- **Enforcement**: Prompt-only + fixtures-lint
- **Prompt guidance**: Coverage Closure: "Every `api_id` in `spec/05_interface_contracts.json` has >=1 contract-mode fixture"
- **Can requirements silently drop?** PARTIALLY -- fixtures-lint validates target IDs exist but not coverage completeness

#### Link 10: 09 -> 14 (Impl Plan -> Roadmap)
- **Enforcement**: LINT (E590 via step_14.py line 48 + E142 line 84)
- **What it checks**: source_milestones reference valid Step 09 IDs; tech_stack names match Step 09
- **Can requirements silently drop?** NO for milestone links; YES for deliverable-level coverage

#### Link 11: Coverage threshold (W592)
- **Enforcement**: W592/E592 via matrix.py _check_coverage_thresholds
- **What it checks**: FR->API coverage percentage meets threshold (default 80%)
- **Mode**: Warning by default, error when step_order.json sets mode:"error"
- **Scope**: Only checks fr_coverage (has API). Does not check fixture or NFR coverage

### Summary of Lint-Enforced Links (Definitive Count)

Using consistent methodology (one code = one enforced step-to-step link):

| Code | Link | Steps | Type |
|------|------|-------|------|
| E560 | charter_goal -> capability | 00 -> 01 | Error |
| E560 | capability -> FR | 01 -> 04 | Error |
| W561 | FR -> roadmap milestone | 04 -> 14 | Warning |
| W562 | roadmap milestone -> 16a checklist | 14 -> 16a | Warning |
| W563 | roadmap task -> 16a checklist | 14 -> 16a (task-level) | Warning |
| E590 | source_milestones -> Step 09 IDs | 09 -> 14 | Error |
| E590 | fr_refs -> Step 04 IDs | 14 -> 04 (reverse validation) | Error |
| E590 | capability_refs -> Step 01 IDs | 14 -> 01 (reverse validation) | Error |
| E142 | tech_stack names -> Step 09 | 09 -> 14 | Error |
| W592 | FR-to-API coverage threshold | 04 -> 05 (aggregate) | Warning |
| E555 | Semantic coverage regression | Any changed step | Error |
| W595 | Content staleness | upstream -> downstream | Warning |

**Definitive count**: 5 distinct forward chain links have dedicated lint enforcement (E560x2, W561, W562, W563). 1 has partial/aggregate enforcement (W592 for 04->05). 3 have reverse-validation enforcement (E590 for cross-ref integrity). 2 have change-detection enforcement (E555, W595).

**Resolution of baseline 4-vs-5 ambiguity**: The count is **5** if counting unique forward-chain step-to-step links with dedicated enforcement codes (00->01, 01->04, 04->14, 14->16a milestone, 14->16a task). It is **4** if W562 and W563 are merged as the same 14->16a link. The correct count using "unique step pairs" is **4 step-pair links** (since W562/W563 both enforce 14->16a). With W592 as partial, total is **4 full + 1 partial = 5 enforced links**.

---

## Findings

### FINDING-001: Step 09 Milestone Schema Lacks `depends_on` Field
- **Severity**: HIGH
- **Category**: INTEGRITY
- **Location**: `schema/09_impl_plan.schema.json`:34-86
- **Description**: Step 09 milestones have no `depends_on` field in the schema. Milestones can only be implicitly ordered by array position and `target_date`. There is no schema-level mechanism to express that milestone B requires milestone A's deliverables. The prompt says "All dependencies between milestones are explicit -- no implicit ordering assumptions" (prompt_09_impl_plan.md:77) but the schema provides no field to express this.
- **Evidence**: The schema defines milestone properties as: `milestone_id`, `name`, `target_date`, `status`, `risks`, `spikes`, `deliverables`. No `depends_on` or equivalent field exists. Compare with Step 14's task-level `depends_on` which does exist (schema/14_roadmap.schema.json:152-158).
- **Recommendation**: Add optional `depends_on` array to Step 09 milestone schema (items: kebab-case milestone IDs). Add a cycle-detection validator in step_09.py similar to step_14.py's `_check_task_dependency_cycles`. Update prompt_09_impl_plan.md to guide LLMs to populate it.

### FINDING-002: Step 14 Tasks Lack Direct FR Binding
- **Severity**: HIGH
- **Category**: INTEGRITY
- **Location**: `schema/14_roadmap.schema.json`:87-183
- **Description**: Step 14 tasks have no `fr_refs` or `trace` field. The `fr_refs` and `capability_refs` fields exist only at the milestone level (lines 69-85). Individual tasks within a milestone cannot declare which specific FR they implement. This means for a milestone with 10 FRs and 15 tasks, there is no machine-checkable way to verify every FR has at least one task covering it.
- **Evidence**: Task schema (lines 90-183) has: `task_id`, `description`, `acceptance_criteria`, `status`, `depends_on`, `assumptions`, `exit_conditions`. No trace or FR reference field. The prompt says "Every FR in milestone's `fr_refs` has at least one task" but this is not schema-enforced.
- **Recommendation**: Add optional `fr_refs` array to task objects in Step 14 schema. Add a validator that checks every FR in `milestone.fr_refs` is referenced by at least one task within that milestone. Alternatively, add a W-code lint rule (see FINDING-012 for spec).

### FINDING-003: Semantic Drift Has No Dedicated Validator
- **Severity**: HIGH
- **Category**: INTEGRITY
- **Location**: `tools/specdev_tools/validation/` (entire directory)
- **Description**: There is no validator that checks whether a traced ID's semantic meaning is consistent across steps. A capability named "cap-user-auth" in Step 01 could be described as "User Authentication" there but referenced in Step 04 with a description about "Authorization". The only checks are: (a) E590 broken-reference (ID exists), (b) E555 semantic-coverage-regression (IDs not dropped between versions), (c) W595 content-staleness (upstream token changes). None of these validate that the *description* associated with a traced ID remains semantically aligned.
- **Evidence**: `_check_semantic_coverage` in forward_replay_check.py (line 236) only checks that IDs are not dropped between old and new versions of the same file. `validate_trace_integrity` in matrix.py checks that referenced IDs exist. Neither validates description consistency across steps.
- **Recommendation**: This is partially mitigated by the Glossary (Step 03) as the single vocabulary source and canonical registry enforcement. Adding a new lint rule that cross-references free-text descriptions for traced IDs across steps would be high-cost and potentially noisy. Instead, recommend strengthening prompt guidance for Steps 05, 06, 07 to explicitly say "use the exact description text from Step 04 for any traced FR" and consider a W-code that flags when a description field on a trace ref differs significantly from the source artifact's description.

### FINDING-004: Extraction Mandates Cover Only 3 of 22 Steps
- **Severity**: MEDIUM
- **Category**: INTEGRITY
- **Location**: `prompts/prompt_04_functional_requirements.md`:88-89, `prompts/prompt_14_roadmap.md`:88-89, `prompts/prompt_16a_impl_planner.md`:281-282
- **Description**: Only 3 steps have Extraction Mandates (hard requirements that every upstream ID must be consumed): Step 04 (cap->FR), Step 14 (FR->milestone), Step 16a (milestone->checklist). Steps along the requirement chain that should arguably have mandates but do not: Step 05 (FR->API), Step 06 (FR->invariant for negative cases), Step 08 (FR->fixture), Step 09 (cap->milestone deliverable).
- **Evidence**: Grep across all 22 prompts finds "Extraction Mandate" only in 3 files. Other steps have "Coverage Closure" (all 22 steps) which is softer guidance.
- **Recommendation**: Add Extraction Mandates to at least:
  - Step 05: "Every FR with observable external behavior from `04_fr_list.json` must map to >=1 API. List any FR not covered."
  - Step 08: "Every high-priority FR from `04_fr_list.json` must have >=1 fixture. List any uncovered."
  - Step 09: "Every capability ID from `01_capabilities.json` must appear in >=1 milestone deliverable. List any uncovered."

### FINDING-005: Step 14 Does Not Trigger Trace Matrix Update
- **Severity**: MEDIUM
- **Category**: INTEGRITY
- **Location**: `tools/specdev_tools/validation/matrix.py`:170-305
- **Description**: The trace matrix (`tools/trace_matrix.json`) is built from Steps 04, 05, 07, 08 artifacts. Step 14 introduces `fr_refs` and `capability_refs` on milestones, which is a traceability link from requirements to delivery schedule. However, the trace matrix does not include Step 14 data, so adding/removing FRs from milestones does not trigger matrix updates or integrity checks. The CLAUDE.md Validation Ritual says "If traceability changed: regenerate `matrix`" but the matrix command only reads Steps 04/05/07/08.
- **Evidence**: `build_trace_matrix` (matrix.py:170) walks spec_dir and builds fr_to_api, api_to_fixture, api_to_nfr, api_to_threat links. It never reads `fr_refs` from Step 14 milestones or Step 09 deliverables. Step 14's `fr_refs` are validated only by step_14.py (E590 cross-ref) and traceability_closure.py (W561 uncovered FR).
- **Recommendation**: Consider adding a "milestone_coverage" column to the trace matrix that shows which FRs are scheduled (from Step 14 fr_refs) vs which remain unscheduled. This would make the matrix a single pane for requirements-to-delivery traceability. Low priority -- W561 already catches uncovered FRs.

### FINDING-006: Trinity Loop (16a->16b->16c) Evidence Binding Is Prompt-Enforced Only
- **Severity**: MEDIUM
- **Category**: INTEGRITY
- **Location**: `prompts/prompt_16a_impl_planner.md`, `prompts/prompt_16b_impl_coder.md`, `prompts/prompt_16c_impl_reviewer.md`
- **Description**: The trinity loop has strong prompt-level enforcement for test/evidence binding:
  - 16a: Every checklist item requires `linked_test_expectation` (prompt line 152). Schema makes it optional (not in required array).
  - 16b: Must run every test_command and paste verbatim output (prompt lines 72-76). Must populate `evidence` object before marking verified (prompt line 78).
  - 16c: Cannot approve without evidence (FORBIDDEN rule, prompt line 241). Must verify ci_status == green (prompt line 137).

  However, none of these rules have corresponding validators in `tools/specdev_tools/validation/`. The schema does not require `linked_test_expectation`, does not require `evidence` on verified actions, and does not require `ci_status: green` for `verdict: verified`. All enforcement is prompt-level.
- **Evidence**: Schema `16_impl_context.schema.json` -- `linked_test_expectation` does not appear in any `required` array. `evidence` on actions is not required. `verdict` and `ci_status` have no cross-field validation.
- **Recommendation**: Add at least one validator in `tools/specdev_tools/validation/validators/step_16.py` that checks:
  1. Active checklist items have non-empty `linked_test_expectation`
  2. Verified actions have `evidence` with non-empty `content`
  3. If `verdict: verified`, then `fixture_status.ci_status` must be `green`
  These are the most critical invariants of the trinity loop and should have machine enforcement.

### FINDING-007: Steps Most Vulnerable to Semantic Drift
- **Severity**: HIGH
- **Category**: INTEGRITY
- **Location**: Multiple prompts
- **Description**: Analysis of each step's drift vulnerability:

  **HIGH DRIFT RISK**:
  - **Step 05 (Interface Contracts)**: Translates FRs into APIs. Prompt says "Map APIs to FRs" but no lint validates description consistency. An API can claim to trace to `fr-user-login` while implementing different behavior.
  - **Step 09 (Impl Plan)**: Ingests 10 upstream artifacts with complex extraction intent. Milestones reference FRs by ID in deliverables but milestone names/descriptions are free-text with no terminology enforcement.
  - **Step 14 (Roadmap)**: Creates user_stories and task descriptions that reinterpret FR requirements. No lint validates that task description text aligns with the FR's acceptance criteria.

  **MEDIUM DRIFT RISK**:
  - **Step 06 (Invariants)**: Derives rules from FR acceptance criteria. The `description` field on invariants is free-text; no check validates it aligns with the FR it traces to.
  - **Step 07 (NFRs)**: Derives targets from charter success metrics. Units alignment is checked via canonical registry, but semantic alignment of metric names is prompt-only.

  **LOW DRIFT RISK**:
  - **Steps 16a/16b/16c**: Use the same JSON artifact structure, so drift within a trinity cycle is structurally constrained.
  - **Steps 00-03**: Early steps with few upstream dependencies.

- **Evidence**: Prompt instructions say "use canonical nouns/verbs from required seeds" (prompt_01:47), "use exact glossary terms" (prompt_08:50), etc. But these are soft instructions with no machine validation.
- **Recommendation**: For highest-risk links (04->05, 04->14), add a semantic similarity check that compares the `description` or `statement` field of an FR with the descriptions of APIs/milestones that trace to it. Flag divergences > threshold as W-code warnings.

### FINDING-008: 00 -> 01 Link Misses Success Metrics
- **Severity**: MEDIUM
- **Category**: INTEGRITY
- **Location**: `tools/specdev_tools/validation/traceability_closure.py`:82-97
- **Description**: E560 checks that every `goal_id` in the charter maps to at least one capability. However, charter `success_metrics` are not checked. A success metric like "reduce page load to <200ms" could exist in Step 00 without any capability or NFR tracing to it.
- **Evidence**: traceability_closure.py line 86 extracts only `goals[].goal_id`. The `success_metrics` array is not scanned. Prompt_01 Coverage Closure says "Every goal AND success metric in `spec/00_charter.json` is addressed by >=1 `capability_id`" (line 78) but lint only checks goals.
- **Recommendation**: Extend E560 to also check that each success_metric ID (if present) is traced from at least one capability or NFR. This aligns lint enforcement with prompt guidance.

### FINDING-009: No Lint for FR -> API Coverage Completeness
- **Severity**: HIGH
- **Category**: INTEGRITY
- **Location**: `tools/specdev_tools/validation/traceability_closure.py` (absent check)
- **Description**: The traceability chain from FR to API (Steps 04 -> 05) has no dedicated lint rule. W592 checks aggregate FR-to-API coverage percentage but does not identify WHICH specific FRs lack API coverage. There is no W-code equivalent to W561 (UNCOVERED_FR for roadmap) for the FR->API link.
- **Evidence**: traceability_closure.py checks: charter->cap (E560), cap->FR (E560), FR->roadmap (W561), roadmap->16a (W562/W563). The FR->API link is covered only by W592's aggregate threshold and E590's generic broken-reference check. Compare this with the prompt (prompt_05, Coverage Closure): "Every FR...that specifies an observable external behavior is covered by >=1 `api_id`".
- **Recommendation**: Add a W-code (suggest W564) that checks each FR with external behavior has at least one API trace. This closes the most significant gap in the lint-enforced chain. See FINDING-013 for specification.

### FINDING-010: Step 09 Milestones Can Be Mis-Sequenced
- **Severity**: LOW
- **Category**: INTEGRITY
- **Location**: `schema/09_impl_plan.schema.json`:34-86, `tools/specdev_tools/validation/validators/` (no step_09 validator)
- **Description**: Step 09 milestones have `target_date` but no ordering validation. Unlike Step 14 which validates date ordering (step_14.py line 73), Step 09 has no step-specific validator that checks target_date ordering. A milestone delivering API X could have a later date than a milestone that consumes API X, with no validation error.
- **Evidence**: No `step_09.py` exists in `tools/specdev_tools/validation/validators/`. The prompt says "All dependencies between milestones are explicit" but the schema has no `depends_on` field and no validator enforces date ordering.
- **Recommendation**: Create `tools/specdev_tools/validation/validators/step_09.py` with at minimum target_date ordering validation (like Step 14's). Add `depends_on` support after schema change from FINDING-001.

### FINDING-011: Step 16 Anchor Drift Check Is Not Machine-Enforced
- **Severity**: LOW
- **Category**: INTEGRITY
- **Location**: `prompts/prompt_16_impl_context.md`:69, 177
- **Description**: The Step 16 anchor prompt says "MUST verify that no `checklist[].id`, `scope_in`, or `scope_out` value in this Anchor contradicts the corresponding values in any active Milestone context". This drift check is critical but entirely prompt-enforced. No validator compares the anchor artifact against per-milestone impl_context files.
- **Evidence**: No code in `tools/specdev_tools/validation/` performs anchor-vs-milestone drift comparison. The only Step 16 validation is schema-level (via step_base).
- **Recommendation**: Consider a new lint command `anchor-drift-check` that loads `spec/16_impl_context.json` and all `spec/impl_context/*.json` files, comparing scope_in/scope_out/checklist_id values for conflicts. Low priority since the trinity loop is typically a short-lived cycle.

### FINDING-012: Proposed Lint Rule -- FR-to-Task Coverage in Step 14
- **Severity**: INFO
- **Category**: INTEGRITY
- **Location**: N/A (new rule proposal)
- **Description**: Per FINDING-002, Step 14 milestones have `fr_refs` but tasks have no FR binding. A lint rule could validate that every FR in `fr_refs` is plausibly covered by at least one task's `acceptance_criteria.text` or `description` mentioning an FR-related keyword.

  **Proposed rule**:
  - **Error code**: W565
  - **Name**: MILESTONE_FR_TASK_GAP
  - **What it checks**: For each milestone, compare `fr_refs` count against tasks with non-empty `acceptance_criteria`. Warn if `|fr_refs| > |tasks with acceptance_criteria|` (more FRs than tasks with criteria)
  - **Files it reads**: `spec/14_roadmap.json`
  - **What it reports**: "Milestone '{mid}' has {n} fr_refs but only {m} tasks with acceptance_criteria -- potential uncovered FRs"
- **Recommendation**: Implement as a soft warning (W-code). This catches the most egregious case without requiring task-level FR binding in the schema.

### FINDING-013: Proposed Lint Rule -- FR-to-API Completeness
- **Severity**: INFO (rule proposal only)
- **Category**: INTEGRITY
- **Location**: N/A (new rule proposal)
- **Description**: Per FINDING-009, there is no dedicated lint for FR->API coverage. Proposed rule:

  **Proposed rule**:
  - **Error code**: W564
  - **Name**: UNCOVERED_FR_API
  - **What it checks**: For each FR in `spec/04_fr_list.json`, verify at least one API in `spec/05_interface_contracts.json` has a trace with `type: "fr"` and `id: <fr_id>`
  - **Files it reads**: `spec/04_fr_list.json`, `spec/05_interface_contracts.json`
  - **What it reports**: "FR '{fr_id}' has no corresponding API in interface contracts"
  - **Exclusions**: FRs tagged as `internal-only` or `deferred` in their metadata
  - **Implementation**: Add to `traceability_closure.py` alongside the existing W561 check. Load APIs, scan for FR-type trace refs, compare against FR ID set.
- **Recommendation**: Implement in traceability_closure.py. This is the single highest-value new lint rule for closing the integrity chain.

### FINDING-014: Step 16c Reviewer Does Not Validate Roadmap Deliverable Completion
- **Severity**: CRITICAL
- **Category**: INTEGRITY
- **Location**: `prompts/prompt_16c_impl_reviewer.md`:40
- **Description**: The prompt says "Before marking a milestone complete, verify all deliverables listed in `14_roadmap.json` for that milestone are satisfied by `execution_results`." It also says on verdict:verified, the reviewer "MUST also update: `spec/14_roadmap.json`: Set the corresponding milestone's status to `done`". However, there is NO validator or schema constraint that prevents a 16c reviewer from writing `verdict: verified` without checking roadmap deliverables. The roadmap sync side-effect (updating Step 09/14 status) has no machine enforcement.
- **Evidence**: No validator checks that when `verdict: verified` is set, the milestone's deliverables in Step 14 are actually satisfied. The status_write_exemptions in step_order.json (line 12-15) allow Steps 09 and 14 milestone status to be updated without triggering forward-replay, but nothing validates the update is correct.
- **Recommendation**: Add a validator that, when `review.verdict == "verified"` in a 16c artifact, checks that `review.semantic_review.fr_coverage` entries cover all fr_refs from the corresponding Step 14 milestone. This is the critical handoff point where discovery specifications meet implementation reality.

### FINDING-015: Step 09 -> 14 Deliverable Traceability Is Partial
- **Severity**: CRITICAL
- **Category**: INTEGRITY
- **Location**: `schema/09_impl_plan.schema.json`:67-72, `tools/specdev_tools/validation/validators/step_14.py`:41-49
- **Description**: Step 09 milestones have `deliverables` (array of traceRef), and Step 14 milestones have `source_milestones` (linking to Step 09 IDs) plus their own `deliverables`. The validator checks that `source_milestones` IDs exist in Step 09 (E590). However, there is NO validation that Step 14 milestones collectively cover all deliverables from the Step 09 milestones they reference. A Step 09 milestone could list 5 deliverables, and the Step 14 milestone referencing it via `source_milestones` could list only 2, silently dropping 3 deliverables.
- **Evidence**: step_14.py line 41-49 validates source_milestone ID existence only. It does not load Step 09 milestone deliverables and compare them against Step 14 deliverables. The prompt says "Decompose: Break down Step 09 technical milestones into atomic user stories for Step 14" but no lint validates completeness of this decomposition.
- **Recommendation**: Add a lint check that for each Step 14 milestone, loads its `source_milestones` from Step 09, collects all deliverable IDs from those Step 09 milestones, and verifies each appears in the Step 14 milestone's deliverables or fr_refs. Error code: W566 INCOMPLETE_MILESTONE_DECOMPOSITION.
