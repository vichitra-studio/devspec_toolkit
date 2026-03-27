# R2-C: Spec-to-Implementation Integrity Chain Analysis

**Scope**: Steps 08-16c (13 steps total) -- the full chain from fixtures to verified implementation
**Date**: 2026-03-20
**Methodology**: Read every prompt, schema, and validator for Steps 08-16c; traced enforcement mechanisms; identified gaps between prompt guidance and machine enforcement.

---

## 1. Per-Step Analysis

### Step 08 -- Fixtures

**What the prompt guides well:**
- Coverage Closure demands fixtures for every FR acceptance criterion, every API (contract mode), every error-severity invariant (negative case), and every performance NFR (benchmark/load).
- Explicit target requirement: every fixture MUST have `targets` referencing upstream IDs.
- Self-correction clause: verify target IDs actually exist before emitting.

**What the validator enforces:**
- `step_08.py` validates target ID patterns (`fr-*`, `api-*`, `nfr-*`, `inv-*`).
- Cross-step validation: loads FR IDs from Step 04, API IDs from Step 05, invariant IDs from Step 06, NFR IDs from Step 07 and checks each target resolves.
- Fixture ID uniqueness and `fix-*` naming convention.
- Schema enforces `minItems: 1` on `fixtures`, and `targets` is required with `minItems: 1`.

**What is missing (ENFORCED vs HOPED):**
- **No FR coverage completeness check**: The validator verifies that referenced IDs exist, but does NOT verify that every FR has at least one fixture. The prompt says "every FR acceptance criterion must have >=1 fixture" but no validator or linter checks this. The `fixtures-lint` command exists but checks targets resolve, not that coverage is complete.
- **No API coverage completeness check**: Same gap -- referencing is validated, completeness is not.
- **No invariant negative-case enforcement**: Prompt says every error-severity invariant needs a negative fixture. Nothing enforces this.
- **No mode diversity enforcement**: Prompt says to mix modes (unit, contract, e2e, redteam). Nothing validates mode coverage.
- **No edge/failure scenario coverage**: Prompt says "happy-path, edge, and failure" but no validator counts scenario types.

**Severity**: HIGH -- Fixtures are the basis for Step 16c evidence verification, and there is no machine enforcement that coverage is complete.

---

### Step 09 -- Implementation Plan

**What the prompt guides well:**
- Coverage Closure: every capability must appear in a milestone's deliverables or be scoped out.
- Tech stack must be structured (object with arrays), have versions and rationale.
- No orphan milestones (must link to FR or API).
- Cross-check tech stack against capabilities.

**What the validator enforces:**
- Milestone ID uniqueness and date ordering.
- Milestone date format (ISO).
- Cross-ref: capability IDs in deliverables validated against Step 01.
- No enforcement of FR coverage or milestone deliverable completeness.

**What is missing:**
- **No FR-to-milestone coverage check**: Prompt says "every FR in at least one milestone" but `step_09.py` does not check this. FRs can silently drop out of the implementation plan.
- **No tech stack version format validation**: Prompt says "no latest, no stable" but the validator does not enforce this.
- **No acceptance criteria enforcement per milestone**: Schema has no field for acceptance criteria on milestones (only `deliverables`, `risks`, `spikes`).
- **No `depends_on` for milestones**: The schema supports milestone ordering via dates but has no explicit dependency graph for milestones (unlike tasks in Step 14).

**Severity**: HIGH -- FRs can be silently dropped between Steps 04 and 09.

---

### Step 10 -- Governance

**What the prompt guides well:**
- Commit message regex pattern with `require_spec_ids` flag.
- PR rules must include core validation commands.
- Spec-first policy explicitly declared.
- Extraction intent: encode every charter constraint as a governance rule.

**What the validator enforces:**
- Regex compilation check on commit pattern.
- `pr_rules` values checked against allowed enum set.
- Owner enum validation.
- Trace type validation.

**What is missing:**
- **No verification that governance rules are enforceable**: The validator checks that `pr_rules` use valid command names but does NOT check that CI gates (Step 12) actually implement them. The governance-to-CI-gate link is HOPED, not ENFORCED.
- **No commit message pattern coverage check**: If `require_spec_ids: true`, the pattern should capture FR/API IDs, but nothing validates the regex actually matches `fr-*` or `api-*` patterns.
- **No reviewer coverage validation**: Prompt says reviewers should cover cross-functional disciplines, but the field is a free-form array with no validation.
- **Branch strategy is not in the schema**: Prompt mentions aligning branch strategy with milestones, but there is no schema field for this.

**Severity**: MEDIUM -- Governance defines rules but cannot guarantee they are enforced downstream.

---

### Step 11 -- Red Team

**What the prompt guides well:**
- Every public API must have at least one threat.
- Every threat MUST have `target_ids` linking to API or component.
- Mitigations must use `traceRef` structure linking to invariants/NFRs/FRs.
- Category taxonomy is strict (5 values).
- Edge cases must be structured with IDs.

**What the validator enforces:**
- `threat_id` uniqueness.
- `target_ids` presence validation (errors if empty).
- Target type validation: only `api` or `component` allowed.
- Cross-ref: target IDs validated against Step 02 components and Step 05 APIs.
- Mitigation type validation against allowed set.
- Mitigation must have description or ref.

**What is missing:**
- **No API coverage completeness check**: Prompt says "every public API must have at least one threat" but the validator does NOT check that every API in Step 05 is covered. It only validates that referenced IDs exist.
- **No severity distribution validation**: Nothing ensures critical APIs have high/critical severity threats.
- **No red team output consumption by Step 16c**: The prompt says threats should feed into review criteria, but there is no schema field in Step 16 that references threat IDs. Step 16c's `security_status` section references "plan.security.new_fixtures" but does NOT cross-reference Step 11 threat IDs.
- **No edge case minimum count enforcement**: Prompt says "at least 3 distinct non-malicious failure modes" but nothing enforces this.

**Severity**: MEDIUM -- Attack surface coverage is aspirational, not enforced.

---

### Step 12 -- CI Gates

**What the prompt guides well:**
- Must include governance-check, invariants-check, fixtures-lint, validate-all, matrix as job steps.
- Coverage thresholds must reflect NFR commitments.
- Job DAG must be acyclic.
- Every `pr_rule` from Step 10 must have a corresponding CI job.
- Every CI gate from Step 02a delivery baseline must be implemented.

**What the validator enforces:**
- Job ID uniqueness.
- Job step structure (must have `id` and `command`).
- `requires` references validated against existing job IDs.
- DAG cycle detection.
- Cross-ref: FR and NFR IDs found in jobs validated against Steps 04/07.

**What is missing:**
- **No governance-to-CI completeness check**: Prompt says every `pr_rule` from Step 10 should have a CI job, but the validator does NOT cross-reference Step 10's `pr_rules` against Step 12's job steps.
- **No delivery baseline gate coverage**: Prompt says every `ci_gate` from Step 02a should be implemented as a job. Not validated.
- **No command existence validation**: Validator does not check that `command` values reference real tools/scripts.
- **No coverage threshold enforcement**: `coverage_thresholds` is optional in the schema and not validated against NFR targets.

**Severity**: MEDIUM -- CI gates can be incomplete relative to governance rules and still pass validation.

---

### Step 13 -- Extension Generator

**What the prompt guides well:**
- Naming convention enforcement (`ext_NN_topic.json`).
- Filter rule: only create extensions for domains needing >=3 dedicated schema sections.
- Justification must reference specific component_id or nfr_id.
- Traceability: extensions link back to FRs/NFRs.

**What the validator enforces:**
- Extension ID uniqueness.
- `required_schema_sections` must be present (but schema pattern check is against step pattern `NN_*`, which is actually wrong for extension sections -- e.g., "tables" would fail this check).
- Justification must be non-empty.
- Governance label ref cross-validated against Step 10.
- Verification rules/keywords check in schema_design_guidelines.

**What is missing:**
- **Schema section pattern mismatch**: The validator checks `required_schema_sections` against `^[0-9]{2}[a-z]?_` which expects step-level patterns, but the prompt says sections like "tables", "indexes", "relationships" -- these would fail the validator. This appears to be a bug.
- **No downstream tracking**: Nothing ensures that extensions declared in Step 13 are actually created and used in Steps 14-16.

**Severity**: LOW-MEDIUM -- Extension generation is mostly a planning step.

---

### Step 13a -- Completeness Assessment (CRITICAL CHECKPOINT)

**What the prompt guides well:**
- Evaluates all steps 00-12 plus extensions.
- Checks FR-to-API traceability, fixture coverage, glossary completeness.
- Extension verification: checks that manifest entries exist as files on disk.
- Scoring rubric with impact deductions.
- "Deep Traceability": FRs -> APIs -> Fixtures chain.
- TBD/TODO detection lowers score.

**What the validator enforces:**
- Element ID kebab-case validation.
- Impact score bounds check.
- Completeness score bounds check and consistency (< 100 requires non-empty missing_elements).
- Cross-ref: FR and API IDs in missing_elements validated against Steps 04/05.

**What is CRITICALLY missing:**
- **Step 13a is an AI-generated artifact, not a machine-computed report**: The completeness assessment is produced by the same AI generating the specs. It is NOT an independent, automated coverage analysis. The AI can claim 10/10 completeness while gaps exist.
- **No automated FR-to-fixture coverage computation**: The prompt says to check FR->API->Fixture coverage, but this is manual/AI-driven, not computed by a linter. The `matrix` command generates a trace matrix, but no linter checks its completeness score.
- **No feedback loop mechanism**: Prompt asks "what happens if gaps are found" -- the answer is NOTHING machine-enforced. Step 13a produces a report; no gate blocks the pipeline from proceeding to Step 14 with known gaps.
- **No automated extension file existence check**: Prompt says to verify extensions exist on disk, but the validator does not do this -- only the AI is told to check.
- **The schema has no field for cross-step traceability metrics**: `missing_elements` is free-form. There is no structured field for "FR coverage %" or "API fixture coverage %" that could be validated.

**Severity**: CRITICAL -- This is the last quality gate before implementation begins, and it is entirely aspirational. An AI can produce a perfect score with real gaps, and nothing blocks progression.

---

### Step 14 -- Roadmap

**What the prompt guides well:**
- Every FR must appear in >=1 milestone's `fr_refs`.
- One milestone = one user story.
- Tasks must be atomic with acceptance criteria.
- Source milestones must reference Step 09 milestone IDs.
- Capability refs must reference Step 01.
- Dependency management (depends_on with cycle detection).

**What the validator enforces:**
- Milestone ID uniqueness and date ordering.
- Source milestone cross-ref against Step 09 IDs.
- FR ref cross-ref against Step 04 IDs.
- Capability ref cross-ref against Step 01 IDs.
- Task ID uniqueness within milestones.
- Task dependency cycle detection (DFS).
- Tech stack mismatch detection against Step 09.
- External dependency structure validation (owner/note required).

**What is missing:**
- **No FR coverage completeness check**: The validator checks that referenced FR IDs exist in Step 04, but does NOT check that every FR in Step 04 appears in at least one milestone's `fr_refs`. FRs can be silently dropped.
- **No acceptance criteria validation on tasks**: Tasks have optional `acceptance_criteria` in the schema, but the validator does not check that non-trivial tasks have them.
- **No milestone-to-deliverable consistency**: Prompt says milestones with deliverables must have non-empty `fr_refs`, but the validator does not enforce this.

**Severity**: HIGH -- The FR coverage mandate is prompt-only. FRs can fall through the 04->14 transition without detection.

---

### Step 15 -- Scaffold

**What the prompt guides well:**
- Every API from Step 05 must have a corresponding interface_map entry.
- Every component from Step 02 must have a scaffold module.
- Validators must include schema validation and type-check commands.
- Build status must not be "green" without running validators.

**What the validator enforces:**
- Build status enum validation.
- Green status requires non-empty validators.
- Interface ref uniqueness.
- Interface ref kebab-case format.
- Method enum validation.
- Cross-ref: interface_ref validated against Step 05 API IDs.

**What is missing:**
- **No API completeness check**: Validator checks that referenced APIs exist, but NOT that every API has a scaffold route. APIs can be silently missing from the scaffold.
- **No component-to-module mapping**: Prompt says every component should have a scaffold directory. Nothing validates this.
- **No validator content validation**: Validators are free-form strings; nothing checks they are real commands.
- **No test directory scaffolding check**: Prompt mentions test directories for fixtures but nothing enforces this.

**Severity**: MEDIUM -- Scaffold can diverge from the spec without detection.

---

### Step 16 -- Implementation Context (Trinity Anchor)

**What the prompt guides well:**
- Comprehensive field definitions for plan, checklist, ambiguities, drift, security, delivery, docs.
- Checklist items must have `spec_ref` with commit_hash (40-char SHA, not all zeros).
- `linked_test_expectation` is CRITICAL -- concrete test identifier per checklist item.
- `target_file_patterns` constrains what files can be modified.
- Drift check against active milestone contexts.
- Docs impact required when code changes are present.

**What the validator enforces (step_16.py -- base validator used by 16a/16b/16c):**
- Checklist type/layer enum validation.
- NFR refs and fixture_ref required for proof-requiring types (behavior, constraint, validation, perf, security).
- Verified items must have actions with evidence.
- File scope check: touched files must match target_file_patterns.
- Docs impact enforcement: code changes require docs_impact.status = "required".
- Behavior-validation pairing per roadmap task (E307).
- Command-to-proof linkage: test commands must appear in execution_results with status=passed (E301).
- Verified review without proof closure (E302).
- CI gate violation: verdict=verified requires ci_status=green (E303).
- Roadmap-to-checklist coverage: every task_id in roadmap must have a checklist item (E304).
- Milestone ref binding validation (W581/E582).
- Planned-unexecuted diff (E305).
- Semantic review FR cross-ref against Step 04 (E306).

**This is the most well-enforced step.** The validator has significant depth.

**What is still missing:**
- **No commit_hash validity verification**: Schema enforces 40-char hex pattern and blocks all-zeros, but nothing checks the hash exists in git.
- **No linked_test_expectation existence check**: The validator does not verify that the test file/command actually exists in the codebase.
- **E304 roadmap coverage checks ALL roadmap tasks, not just the current milestone**: This means Step 16 for milestone 1 would fail if milestone 2's tasks aren't in the checklist, unless the artifact only includes the current milestone's roadmap. This is a potential issue for iterative implementation.

---

### Step 16a -- Implementation Planner

**What the prompt guides well:**
- Every roadmap task_id must map to >=1 checklist item.
- Acceptance criteria -> test expectation binding.
- Behavior + validation type pairing per task.
- Explicit file boundaries via target_file_patterns.
- Forbidden: checklist items for tasks outside active milestone scope.

**What the validator enforces (step_16a.py on top of step_16.py):**
- Plan status is required.
- Checklist ID uniqueness.
- Active items must have spec_ref.id.
- All step_16 base validations (E301-E307).

**What is missing:**
- **No validation that every roadmap task has a checklist item at 16a time**: E304 only fires when a roadmap exists, but the check compares ALL roadmap tasks against the checklist, not just the active milestone's tasks. This could cause false positives for iterative planning.
- **No acceptance criteria count enforcement**: Prompt says "if a task has N acceptance_criteria, create >=N checklist items". Not validated.

---

### Step 16b -- Implementation Coder

**What the prompt guides well:**
- Requirement-first execution: iterate checklist, fill implementation slots.
- Strict scope control: files must be within target_file_patterns.
- Evidence binding: verbatim stdout/stderr, not paraphrased.
- Must run every command in review_requirements.test_commands.
- Emergent ambiguities logged as blockers.
- Docs impact enforcement.

**What the validator enforces (step_16b.py on top of step_16.py):**
- Execution section must exist.
- Execution results must be an array.
- No duplicate execution result commands.
- Result status enum validation.
- All step_16 base validations.

**What is missing:**
- **No evidence content quality validation**: The validator checks evidence EXISTS on verified items, but does not check that it contains success markers ("PASSED", "OK", exit code 0) as the prompt demands.
- **No scope violation detection in execution.files_touched**: The base step_16 checks implementation.files_touched against target_file_patterns, but execution.files_touched is NOT checked against target_file_patterns by the validator.
- **No test command completeness check at 16b level**: The base E301 checks test commands against execution_results, but only when execution_results is non-empty and plan is active. During mid-execution, this could be skipped.

---

### Step 16c -- Implementation Reviewer

**What the prompt guides well:**
- Evidence-based audit: every verified item must have evidence.
- Verdict gates: cannot be "verified" if ci_status=red, if blocking findings exist, or if evidence is missing.
- Semantic review: fr_coverage for every FR in scope with evidence_summary.
- Remediation tasks for blocking/major findings.
- Roadmap sync side-effect: verified verdict triggers status updates to Steps 09/14.
- Fixture status scoreboard.
- Ratings rubric (0-5 scale).
- Hallucinated features detection.
- Documentation completeness gating.

**What the validator enforces (step_16c.py on top of step_16.py):**
- Verdict enum validation.
- Duplicate FR ID detection in semantic review.
- All step_16 base validations (including E302 unproven verified, E303 CI gate).

**What is CRITICALLY missing:**
- **No enforcement that semantic_review exists when verdict=verified**: The prompt says it is required, but the validator does not check for its presence. An implementation can be marked "verified" without any FR coverage analysis.
- **No enforcement of fr_coverage completeness**: The validator checks for duplicate FR IDs but does NOT check that every FR referenced in the checklist appears in fr_coverage.
- **No enforcement that satisfied: true has evidence_summary**: The prompt forbids `satisfied: true` without evidence, but the validator does not check this.
- **No remediation task enforcement for blocking/major findings**: The prompt says blocking/major findings MUST have remediation_task. Not validated.
- **No ratings threshold enforcement**: The prompt says verdict "verified" requires rating 4-5, but the validator does not check this.
- **No fixture_status.test_results validation**: The prompt says to list test results for critical fixtures, but nothing validates completeness or consistency.
- **No roadmap sync side-effect validation**: The prompt says to update Steps 09/14 status to "done" on verified verdict. Nothing checks this happened.
- **`rejected` is not in the valid verdicts set**: The prompt defines verdicts as "verified", "deferred", "rejected" but `step_16c.py` has `VALID_VERDICTS = {"verified", "needs_work", "blocked", "deferred"}` -- "rejected" is not valid, and "needs_work" and "blocked" are not in the prompt.

**Severity**: CRITICAL -- The review gate, which is the final defense against requirement leakage, has significant enforcement gaps.

---

## 2. Per-Transition Analysis

### 04 -> 08 (FRs -> Fixtures)
**Gap**: No automated check that every FR has fixture coverage. FRs can exist with zero fixtures.
**Enforced**: Fixture targets must reference valid FR IDs.

### 08 -> 09 (Fixtures -> Impl Plan)
**Gap**: No check that fixture coverage informs milestone planning. Milestones can omit FRs that have no fixtures.
**Enforced**: Step 09 ingests Step 08 per extraction intent, but nothing validates the ingestion happened.

### 09 -> 10 (Impl Plan -> Governance)
**Gap**: No check that governance rules align with the delivery timeline from Step 09.
**Enforced**: Step 10 ingests Step 09 per extraction intent.

### 09 -> 14 (Impl Plan -> Roadmap)
**Gap**: No FR coverage completeness check at the transition. Step 14 validator checks that referenced FR IDs exist but not that ALL FR IDs are referenced.
**Enforced**: Source milestones cross-ref validated. Tech stack mismatch detected.

### 10 -> 12 (Governance -> CI Gates)
**Gap**: No automated check that every `pr_rule` in Step 10 has a corresponding CI job in Step 12.
**Enforced**: Step 12 ingests Step 10 per extraction intent.

### 11 -> 16c (Red Team -> Review)
**Gap**: No schema field in Step 16 that references threat IDs from Step 11. Red team output is consumed via `plan.security` but the link to specific threats is informal.
**Enforced**: Nothing.

### 13a -> 14 (Completeness -> Roadmap)
**Gap**: Step 13a can identify gaps, but nothing blocks Step 14 from proceeding without addressing them. The feedback loop is purely advisory.
**Enforced**: Nothing.

### 14 -> 16a (Roadmap -> Plan)
**Gap**: E304 checks roadmap task coverage but compares against ALL tasks, not just the active milestone.
**Enforced**: Every roadmap task_id must appear in checklist.

### 16a -> 16b (Plan -> Code)
**Gap**: No enforcement that the coder followed the plan exactly. The coder can add/skip actions.
**Enforced**: File scope via target_file_patterns (base step_16).

### 16b -> 16c (Code -> Review)
**Gap**: No enforcement that semantic_review covers every FR. Verdict "verified" can be issued without complete FR coverage analysis.
**Enforced**: E302 (proof closure), E303 (CI gate).

---

## 3. Trinity Loop Deep Dive

The Trinity Loop (16a -> 16b -> 16c) is the most sophisticated part of the pipeline:

**Strengths:**
1. Checklist-driven architecture with atomic requirements.
2. Evidence binding: actions must have evidence objects.
3. Command-to-proof linkage: test commands must appear in execution_results.
4. CI gate enforcement: verdict=verified requires ci_status=green.
5. Roadmap coverage: E304 ensures roadmap tasks map to checklist items.
6. Behavior-validation pairing: E307 ensures both types exist per task.

**Weaknesses:**
1. **Evidence quality is not machine-checked**: Validator checks evidence EXISTS but not that it PROVES the requirement. An evidence string of "test passed" satisfies the validator even without actual test output.
2. **Semantic review is optional**: Despite being described as CRITICAL in the prompt, the validator does not require it for verified verdict.
3. **No inter-loop consistency**: If 16c finds bugs and spawns remediation tasks, nothing ensures those tasks are picked up in the next 16a cycle. The feedback loop is prompt-driven, not schema-driven.
4. **Verdict enum mismatch between prompt and validator**: Prompt says "verified/deferred/rejected", validator says "verified/needs_work/blocked/deferred".
5. **No test existence verification**: `linked_test_expectation` values are strings that may reference non-existent tests.

---

## 4. Evidence/Test Binding Assessment

**Deterministic aspects:**
- Schema requires `commit_hash` as 40-char hex, blocks all-zeros.
- Schema requires `line_range` as `L\d+-L\d+`.
- Evidence object requires `type` enum and `content` with minLength 20.
- E301 enforces test commands appear in execution_results with status=passed.
- E302 enforces proof closure for verified verdict.
- E303 enforces ci_status=green for verified verdict.

**Aspirational aspects:**
- Evidence content quality (verbatim stdout vs paraphrased).
- Test existence in codebase.
- Commit hash existence in git.
- Evidence actually proving the requirement (semantic correctness).
- Coverage completeness (every FR tested, not just claimed).

**Verdict**: Evidence binding is **partially deterministic**. The structural requirements are strong (evidence must exist, test commands must pass), but the semantic requirements are not machine-checkable. An AI can fabricate passing test evidence.

---

## 5. Documentation Update Enforcement

**Enforced:**
- step_16.py validates that `docs_impact.status = "required"` when code changes are present.
- Docs_touched must be non-empty when required.
- Doc paths validated against seed_manifest doc_paths patterns.
- Docs_touched paths must be in target_file_patterns.

**Not enforced:**
- Step 16c does not validate that docs were actually updated (only that they were planned).
- No validator checks that docs listed in docs_touched are modified in execution.files_touched.
- No validator checks documentation content quality or freshness.

**Verdict**: Documentation enforcement is at the **planning level** (Step 16a plans docs updates) but not at the **execution level** (Step 16b/16c do not verify docs were actually written).

---

## 6. End-to-End Trace Example: `fr-password-reset`

### Step 08 (Fixtures)
- Prompt says: create >=1 fixture with target `{"type": "fr", "id": "fr-password-reset"}`.
- **What could fail**: No automated check that fr-password-reset HAS a fixture. If the AI omits it, `fixtures-lint` will NOT catch the gap (it only validates existing targets resolve, not coverage completeness).
- **Gap probability**: MEDIUM -- depends entirely on AI compliance.

### Step 09 (Impl Plan)
- Prompt says: fr-password-reset should appear in a milestone's deliverables.
- **What could fail**: No validator checks FR coverage. The AI could create milestones that omit this FR entirely.
- **Gap probability**: MEDIUM.

### Step 10 (Governance)
- Prompt says: commits must include spec IDs like `fr-password-reset`.
- **What could fail**: Even if the pattern requires spec IDs, the regex is not validated for FR-pattern compatibility. A dev could commit without referencing fr-password-reset and governance-check might not catch it if the pattern is too broad.
- **Gap probability**: LOW (pattern enforcement exists via governance-check CLI).

### Step 11 (Red Team)
- Prompt says: password reset should have threat analysis (authn category, credential stuffing, token expiry).
- **What could fail**: No check that fr-password-reset's associated APIs are covered by threats. If the AI omits password-reset threats, the validator only checks that listed threats have valid targets.
- **Gap probability**: MEDIUM.

### Step 12 (CI Gates)
- Prompt says: auth-related changes should have a gate.
- **What could fail**: CI gates are generic (validate-all, fixtures-lint). No FR-specific gates exist. Password reset is not individually gated.
- **Gap probability**: LOW (generic gates provide baseline coverage).

### Step 13a (Completeness Assessment)
- Prompt says: verify fr-password-reset has API, fixture, NFR coverage.
- **What could fail**: This is AI-generated, not machine-computed. If the AI misses the gap, nothing catches it.
- **Gap probability**: HIGH -- this is the checkpoint that should catch gaps from Steps 08-12, but it is not automated.

### Step 14 (Roadmap)
- Prompt says: fr-password-reset must appear in `fr_refs` of at least one milestone.
- **What could fail**: Validator checks that referenced FR IDs exist, but NOT that every FR is referenced. fr-password-reset can be silently dropped.
- **Gap probability**: MEDIUM.

### Step 15 (Scaffold)
- Prompt says: test files should be scaffolded for password reset.
- **What could fail**: No FR-to-scaffold mapping exists. Scaffold maps APIs, not FRs.
- **Gap probability**: HIGH -- scaffold is API-oriented, not FR-oriented.

### Step 16a (Plan)
- Prompt says: plan should reference fr-password-reset.
- **What could fail**: E304 checks roadmap tasks are covered, but if the roadmap already dropped fr-password-reset, the planner inherits the gap.
- **Gap probability**: Inherited from Step 14.

### Step 16b (Code)
- Prompt says: implement exactly what 16a planned.
- **What could fail**: If fr-password-reset was dropped at Step 14, it won't be in the plan, and 16b won't implement it.
- **Gap probability**: Inherited.

### Step 16c (Review)
- Prompt says: verify every implementation against its originating requirement.
- **What could fail**: Semantic review only covers FRs that appear in the checklist. If fr-password-reset was never planned, it won't appear in the review. The validator does NOT cross-reference Step 04 to find missing FRs.
- **Gap probability**: HIGH -- the review only verifies what was planned, not what SHOULD have been planned.

### Summary Trace
fr-password-reset can be silently dropped at:
1. **Step 08**: No fixture (no completeness check)
2. **Step 09**: Omitted from milestones (no FR coverage check)
3. **Step 13a**: Gap not detected (AI-generated, not automated)
4. **Step 14**: Not in fr_refs (no completeness check)
5. **Step 16c**: Not reviewed (only reviews what was planned)

**Earliest silent drop: Step 08 or Step 09. Last chance to catch: Step 13a (but it is not automated).**

---

## 7. Coverage Gap Matrix

| Transition | What Can Fall Through | Enforced? | Enforcement Mechanism |
|---|---|---|---|
| 04 -> 08 | FRs without fixtures | NO | Prompt only |
| 04 -> 09 | FRs without milestones | NO | Prompt only |
| 05 -> 08 | APIs without contract fixtures | NO | Prompt only |
| 05 -> 11 | APIs without threats | NO | Prompt only |
| 05 -> 15 | APIs without scaffold routes | PARTIAL | Cross-ref exists but not completeness |
| 06 -> 08 | Invariants without negative fixtures | NO | Prompt only |
| 07 -> 08 | NFRs without benchmark fixtures | NO | Prompt only |
| 09 -> 14 | Milestones without decomposition | PARTIAL | Source milestones validated |
| 10 -> 12 | Governance rules without CI gates | NO | Prompt only |
| 11 -> 16 | Threats without impl mitigations | NO | No schema link |
| 13a -> 14 | Gaps without remediation | NO | No blocking gate |
| 14 -> 16a | Tasks without checklist items | YES | E304 |
| 16a -> 16b | Plan items without implementation | YES | E305, E301 |
| 16b -> 16c | Implementation without evidence | YES | E302, E303 |

**Pattern**: Enforcement is STRONG within the Trinity Loop (14 -> 16a -> 16b -> 16c) but WEAK in the Discovery Phase (08 -> 13a). The biggest gaps are in **coverage completeness checks** -- the system validates that cross-references are valid but not that they are complete.

---

## 8. Step 13a Effectiveness Assessment

**Design intent**: Step 13a is positioned as the "final quality gate before coding" -- the explicit coverage verification checkpoint.

**Actual effectiveness**: LOW

**Reasons:**
1. **It is an AI-generated artifact, not a computed report**: The completeness assessment is produced by the same AI that might have created the gaps. There is no independent, automated coverage computation.
2. **No schema fields for quantitative coverage metrics**: The schema has `completeness_rating.current` (a subjective 0-10 score) but no fields for "FR coverage %", "API fixture coverage %", or "invariant test coverage %".
3. **No blocking gate**: Even if 13a identifies gaps (priority: "high"), nothing prevents Step 14 from being created. The pipeline proceeds.
4. **No automated extension file check**: The prompt says to verify extension files exist on disk, but the validator does not do this.
5. **The validator only checks cross-refs in missing_elements**: It validates that FR/API IDs referenced in gaps exist, but does not compute whether gaps exist.

**What would make 13a effective:**
- A machine-computed coverage report (like `matrix` + analysis) that generates the assessment, not an AI prompt. This ties directly into the pairwise completeness chain (R2-C-001) — Step 13a should be the aggregation point for all pairwise coverage checks, producing a quantitative coverage report.
- A blocking gate that prevents Step 14 generation if coverage < threshold.
- Structured schema fields for coverage dimensions with minimum thresholds.
- The redesign of 13a from subjective AI report to machine-computed analysis is the natural complement to the pairwise completeness checks — 13a becomes the "coverage dashboard" that aggregates all transition completeness metrics.

---

## 9. Findings

### R2-C-001: No Coverage Completeness Enforcement at ANY Transition (CRITICAL)

**Location**: Steps 08, 09, 14 (all transitions from Step 04), and equivalently at capability→FR, milestone→task, and task→impl transitions
**Description**: The system validates that cross-references are valid (the referenced ID exists) but NEVER validates that every upstream ID is covered downstream. This is not FR-specific — the same gap exists at every transition: capabilities can have no FRs, FRs can have no fixtures, FRs can have no milestones, milestones can have no roadmap tasks, tasks can have no implementation. The system validates reference validity but not reference completeness.
**Impact**: The core promise of the spec-to-impl chain — that every requirement is implemented — is not machine-enforceable at any transition point.
**Recommendation**: Implement pairwise completeness checks at each transition as an incremental extension of existing traceability infrastructure: capability→FR, FR→fixture, FR→milestone, milestone→task. Each check is simple; chained together they form the end-to-end lifecycle guarantee. No NL tooling needed — ID-level enforcement only.

### R2-C-002: Step 13a is Aspirational, Not Automated (CRITICAL)

**Location**: `prompts/prompt_13a_completeness_assessment.md`, `schema/13a_completeness_assessment.schema.json`, `tools/specdev_tools/validation/validators/step_13a.py`
**Description**: The completeness assessment is an AI-generated subjective report, not a machine-computed analysis. The schema has a subjective 0-10 score, no structured coverage metrics, and no blocking gate. The validator only checks ID format and cross-refs, not actual completeness.
**Impact**: The "final quality gate before implementation" is neither automated nor enforced.
**Recommendation**: Create a machine linter (e.g., `specdev completeness-check`) that computes FR->API, FR->fixture, API->fixture coverage ratios and outputs structured results. Add a blocking threshold in step_order.json or CI gates.

### R2-C-003: Step 16c Semantic Review Not Enforced (HIGH)

**Location**: `tools/specdev_tools/validation/validators/step_16c.py`
**Description**: The prompt says `semantic_review` with `fr_coverage` is REQUIRED when verdict=verified. The validator does not check for its presence. An implementation can be marked "verified" without any FR coverage analysis.
**Impact**: The final review gate can be passed without proving that requirements were met.
**Recommendation**: Add E-code validation: if verdict=verified, `review.semantic_review` must exist, `fr_coverage` must be non-empty, and every FR in the checklist must appear in fr_coverage.

### R2-C-004: Evidence Quality Not Validated (HIGH)

**Location**: `tools/specdev_tools/validation/validators/step_16.py`
**Description**: The validator checks that evidence EXISTS on verified items (E301) but does not validate evidence quality. The prompt demands verbatim stdout/stderr with success markers ("PASSED", "OK", exit code 0). An evidence string of "done" (>=20 chars with padding) would pass validation.
**Impact**: Requirements can be marked "verified" with fabricated or insufficient evidence.
**Recommendation**: Add evidence content validation: check for success marker keywords or structured evidence_binding with exit_code=0.

### R2-C-005: Verdict Enum Mismatch Between Prompt and Validator (MEDIUM)

**Location**: `prompts/prompt_16c_impl_reviewer.md` line 131, `tools/specdev_tools/validation/validators/step_16c.py` line 13
**Description**: Prompt defines verdicts as "verified", "deferred", "rejected". Validator defines valid verdicts as "verified", "needs_work", "blocked", "deferred". "rejected" is not valid in the validator; "needs_work" and "blocked" are not described in the prompt.
**Impact**: If an AI follows the prompt and uses "rejected", the validator will fail with an unhelpful error.
**Recommendation**: Synchronize the prompt and validator enum values.

### R2-C-006: No Governance-to-CI Cross-Validation (MEDIUM)

**Location**: Steps 10 -> 12 transition
**Description**: Step 10 defines `pr_rules` (e.g., "validate-all", "fixtures-lint"). Step 12 defines CI jobs with commands. Nothing validates that every pr_rule has a corresponding CI job. Governance rules can be defined but never enforced in CI.
**Impact**: Governance is advisory without CI enforcement.
**Recommendation**: Add a cross-step linter that verifies every `pr_rules` entry in Step 10 maps to a Step 12 job step command.

### R2-C-007: No API-to-Threat Coverage Validation (MEDIUM)

**Location**: Step 11 validator (`step_11.py`)
**Description**: The prompt says "every public API must have at least one threat". The validator checks that threat targets are valid but not that every API is covered. APIs can have zero threat analysis.
**Impact**: Security gaps in the threat model are not detected.
**Recommendation**: Add a coverage check in `step_11.py` that loads all API IDs from Step 05 and verifies each appears in at least one threat's target_ids.

### R2-C-008: No Blocking Gate at Step 13a (MEDIUM → elevate to HIGH, cross-ref R2-C-002)

**Location**: `tools/step_order.json`
**Description**: Step 13a produces a completeness report, but step_order.json has no mechanism to block Step 14 generation if completeness is below threshold. The pipeline always proceeds regardless of gaps. This is the enforcement arm of R2-C-002 (Step 13a is aspirational, not automated) — even if 13a is redesigned as machine-computed coverage (Decision 12), it still needs a blocking gate to prevent downstream steps from proceeding with known gaps.
**Impact**: Known specification gaps propagate into implementation.
**Recommendation**: Add a completeness threshold in step_order.json policy or a CI gate that blocks roadmap generation when completeness < configured threshold. This should be part of the Step 13a redesign (R2-C-002) — the machine-computed coverage report becomes the input to the blocking gate. See also Decision 13 (pairwise completeness chain) — 13a becomes the aggregation point for all transition completeness checks.

### R2-C-009: Execution files_touched Not Scope-Checked (LOW-MEDIUM)

**Location**: `tools/specdev_tools/validation/validators/step_16.py`
**Description**: The base step_16 validator checks `implementation.files_touched` against `target_file_patterns` but does NOT check `execution.files_touched`. The coder could report touching files outside scope in the execution section without error.
**Impact**: Scope creep in execution goes undetected.
**Recommendation**: Extend the file scope check to include `execution.files_touched`.

### R2-C-010: Step 13 Schema Section Pattern Bug (LOW)

**Location**: `tools/specdev_tools/validation/validators/step_13.py` line 28-32
**Description**: The validator checks `required_schema_sections` entries against `^[0-9]{2}[a-z]?_` pattern (step schema format), but the prompt and example use domain sections like "tables", "indexes", "relationships", "vector_config" which would fail this pattern.
**Impact**: Valid extension schema sections would be flagged as errors.
**Recommendation**: Remove or fix the schema section pattern check -- these are domain-specific section names, not step references.

### R2-C-011: No Feedback Loop from 16c to 16a (LOW-MEDIUM)

**Location**: Step 16c prompt and schema
**Description**: When 16c issues remediation tasks (via `findings[].remediation_task`), nothing ensures these tasks are consumed by the next 16a cycle. The feedback loop exists only in the prompt's narrative, not in the schema or validators.
**Impact**: Bug fixes identified in review can be silently dropped.
**Recommendation**: Add a validator that checks whether previous 16c remediation tasks appear in the current 16a checklist (requires tracking across loop iterations).

### R2-C-012: No Roadmap Sync Verification After 16c Verified (LOW)

**Location**: Step 16c prompt
**Description**: The prompt says that on `verdict: verified`, the reviewer MUST update Steps 09/14 milestone statuses to "done". This side-effect is not validated. The step_order.json has `status_write_exemptions` for this pattern, but nothing checks the writes actually happened.
**Impact**: Roadmap and impl plan can show milestones as "pending" even after successful implementation.
**Recommendation**: Add a post-verification linter that checks milestone status consistency between Steps 09/14 and verified Step 16 artifacts.
