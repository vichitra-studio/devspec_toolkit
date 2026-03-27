# R2-E: Semantic Drift, Cross-Step Redundancy, and Distillation Quality

**Date**: 2026-03-20
**Scope**: All 22 prompts, schemas, validators, and step_order.json
**Method**: Systematic reading of every prompt, schema, and cross-artifact validator

---

## 1. Semantic Drift Analysis

### 1.1 Seed -> Step 00 (Charter)

**Prompt guidance (prompt_00, lines 53-56)**: Extraction Intent says to extract "Project scope boundaries, business objectives, target users, and high-level success criteria" from seed_overview.md. The Operating Flow (line 59) instructs: "Cross-check metrics against seed documents to align metric names and units; align segment terminology with seed document terminology."

**Drift controls**:
- Prompt line 67: "Ambiguity scrub: MUST replace any instance of 'improve', 'optimize', 'user-friendly', or 'fast' with a quantifiable target."
- Prompt line 83: "All metric names and units in `success_metrics` align with terminology used in the seed documents."
- Coverage Closure (lines 80-84) requires every seed requirement to be reflected or listed as out-of-scope.

**Drift risk**: LOW. This transition has the strongest terminology preservation instructions. However, no **validator** enforces that seed terminology was preserved. The Coverage Closure checklist is prompt-only; no machine check verifies seed-to-charter alignment. The `seed-lint` command checks file existence and staleness, not semantic preservation.

**Gap**: No validator checks whether charter `problem_statement` or `success_metrics` names match seed document terminology.

### 1.2 Step 00 -> Step 01 (Charter -> Capabilities)

**Prompt guidance (prompt_01, lines 47, 59-60)**:
- "Use canonical nouns/verbs from required seeds and charter language"
- Cross-Check: "Verify each capability exists in `spec/00_charter.json` `in_scope` or `goals`"
- Coverage Closure (lines 78-81): "Every goal and success metric in `spec/00_charter.json` is addressed by >=1 `capability_id`"

**Drift controls**:
- Line 66: "MUST use `capability-<verb>-<noun>` format when a matching term exists in charter goals"
- Line 106: "MUST use specific action verbs derived from `spec/00_charter.json` goals"

**Drift risk**: MEDIUM. The prompt mandates using charter verbs/nouns, but the capability `description` field is free-text with no terminological constraint. A capability could use entirely different vocabulary in its description while maintaining a nominal ID link. The `verb` field is a single word that must come from charter language, but `description` is unconstrained.

**Machine enforcement**: `cross_artifact_checks.py` checks capability coverage from Step 02 components back to Step 01, but nothing validates Step 01 capabilities trace back to Step 00 charter goals. The traceability matrix (`matrix.py`) checks FR->capability but not capability->charter.

### 1.3 Step 01 -> Step 04 (Capabilities -> FRs)

**Prompt guidance (prompt_04, lines 45-46, 89)**:
- "Capabilities `spec/01_capabilities.json` as the source of behaviors"
- "Glossary `spec/03_glossary.json` to anchor terms"
- Extraction Mandate: "Every capability ID from `01_capabilities.json` must map to >=1 FR"

**Drift risk**: HIGH. This is the highest-risk transition in the pipeline. Capabilities describe behaviors at a coarse granularity ("authenticate users"). FRs decompose these into specific behaviors ("The system shall authenticate a user and issue a session token"). The prompt says "use concrete verbs and measurable outcomes" but provides no guidance on **how to decompose** capabilities into FRs. The prompt says "ban should/could/fast/easy" (line 68) but does not instruct the LLM to use glossary terms (Step 03) in FR statements.

**Machine enforcement**: `cross_artifact_checks.py:check_step_04_integrity()` validates that FR trace references to capabilities resolve to real capability IDs. This is structural validation only -- it checks that `trace[].id` exists, not that the FR `statement` text preserves capability intent.

**Critical gap**: The prompt tells the LLM to "anchor terms" with the glossary but the schema has no field that binds FR field values to glossary term_ids. The `trace` field can reference glossary terms, but the `statement` text is free-text. An LLM could write an FR statement using entirely different vocabulary than the glossary defines.

### 1.4 Step 04 -> Step 05 (FRs -> APIs)

**Prompt guidance (prompt_05, lines 71-74)**:
- Coverage Closure: "Every FR that specifies an observable external behavior is covered by >=1 `api_id`"
- "All `trace` entries on APIs reference valid `fr_id` values"
- "All resource and action names align with `term_id` values from `spec/03_glossary.json`"

**Drift risk**: MEDIUM-HIGH. The prompt says API resource/action names should align with glossary terms (line 74), but this is a Coverage Closure checklist item (prompt-only), not schema-enforced. The API `name` field is free-text. An API named "Create Session" could drift from the glossary term "authentication" and the FR statement "authenticate a user". The prompt instructs `api-<resource>-<action>` naming (line 99), which provides structural consistency but not semantic consistency.

**Machine enforcement**: The matrix command (`matrix.py`) validates FR-to-API trace integrity. No validator checks that API `name` or `path` terminology aligns with glossary terms.

### 1.5 Steps 04-07 -> Step 09 (Specs -> Impl Plan)

**Prompt guidance (prompt_09, lines 41-50)**:
- Extraction Intent lists all upstream specs, but the key field is `milestones[].deliverables` which uses `traceRef` objects pointing to FR/API IDs.
- Line 96: "NO Orphan Milestones: Do not create milestones that do not link to at least one FR or API in `deliverables`"

**Drift risk**: LOW for structural traceability (IDs preserved), HIGH for descriptive content. Milestone `name` and `risks` are free-text. The prompt says "milestones should map to delivered FRs/APIs and passing CI gates" (line 62) but does not require milestone descriptions to use charter/glossary terminology. A milestone could be named "Sprint 1 Backend" with no semantic connection to the FRs it delivers.

**Machine enforcement**: Step 14 validator checks `source_milestones` reference validity. No validator checks that milestone `name` or description uses consistent terminology.

### 1.6 Step 09 -> Step 14 (Impl Plan -> Roadmap)

**Prompt guidance (prompt_14, lines 55, 89-90)**:
- "milestones decomposed from Step 09 milestone IDs via source_milestones"
- Extraction Mandate: "Every FR ID from `04_functional_requirements.json` must appear in >=1 milestone's `fr_refs`"
- Schema enforces: `source_milestones` (required), `fr_refs` (required), `capability_refs` (required)

**Drift risk**: LOW for ID-level traceability (schema-enforced), MEDIUM for descriptive content. The `user_story` field is free-text and could describe something different from the FRs listed in `fr_refs`. Task `description` fields are also free-text.

**Machine enforcement**: `step_14.py` validates `source_milestones` existence, `fr_refs` format pattern, `capability_refs` format pattern. Per P3 finding AUDIT-005, it does NOT check that Step 09 deliverables are fully decomposed into Step 14 deliverables.

### 1.7 Step 14 -> Steps 16a/16b/16c (Roadmap -> Trinity Loop)

**Prompt guidance (prompt_16a, lines 76, 127-133)**:
- "Every `tasks[].task_id` from `14_roadmap.json` MUST map to at least one checklist item"
- "Create >=1 checklist item where `spec_ref.id == task_id`"
- Every checklist item includes `milestone_ref` back to Step 14 milestone_id

**Drift risk**: LOW. This is the strongest traceability in the pipeline. The Trinity Loop prompts (16a/16b/16c) are the most rigorous, requiring structured `spec_ref` objects with `commit_hash`, `line_range`, and concrete `linked_test_expectation`. The `spec_ref.id` must literally equal the `task_id` from the roadmap.

**Machine enforcement**: The 16a prompt forbids using fr_id or cap_id as spec_ref.id -- it must be the literal task_id. However, no schema constraint or validator enforces this; it is prompt-only.

---

## 2. Cross-Step Redundancy Map

| Information | Steps Where Present | Type | Assessment |
|---|---|---|---|
| **Tech Stack** | Step 02 (components.type), Step 02a (environments.runtime), Step 09 (tech_stack), Step 14 (tech_stack), Step 15 (project_skeleton) | 5 steps | **Accidental duplication for 09->14**. Prompt 14 line 94 says "In most cases, copy the `tech_stack` from `spec/09_impl_plan.json`." This is copy-paste, not distillation. Steps 02/02a capture different aspects (architecture-level vs runtime). Step 15 consumes Step 09 to set language/framework. |
| **Milestone data** | Step 09 (milestones), Step 14 (milestones) | 2 steps | **Intentional distillation**. Step 09 milestones are strategic (deliverables as traceRefs). Step 14 milestones add `user_story`, `tasks`, `acceptance_criteria`, `fr_refs`, `capability_refs`. Step 14 decomposes Step 09 milestones into executable units. However, `name`, `target_date`, `risks`, `spikes`, `deliverables`, `status` are duplicated fields with potentially different values. |
| **FR references** | Step 04 (definition), Step 08 (targets), Step 09 (deliverables), Step 14 (fr_refs), Step 16a (spec_ref) | 5 steps | **Intentional traceability**. Each step references FR IDs; none re-defines FRs. This is the design working correctly. |
| **Success metrics** | Step 00 (success_metrics), Step 07 (nfrs.metric/target/unit) | 2 steps | **Intentional distillation**. Charter captures business-level metrics; NFRs make them operationally measurable with specific stages and measurement methods. |
| **Acceptance criteria** | Step 04 (FR acceptance_criteria), Step 14 (task acceptance_criteria) | 2 steps | **Risky duplication**. Step 04 defines acceptance criteria at the FR level. Step 14 defines acceptance criteria at the task level. The prompt does not explain the relationship. Task acceptance criteria could restate, refine, or contradict FR acceptance criteria. No validator checks consistency. |
| **Error definitions** | Step 01 (error_states), Step 05 (errors), Step 06 (invariants), Step 08 (negative fixtures) | 4 steps | **Intentional multi-perspective coverage** but no validator checks consistency. A capability error_state could describe a failure mode differently than the API error it maps to. |
| **Dependencies** | Step 09 (dependencies), Step 14 (dependencies) | 2 steps | **Accidental duplication**. Step 14 has its own `dependencies` field that could diverge from Step 09 dependencies. The prompt says to copy tech_stack from Step 09 but says nothing about copying dependencies. |
| **Migration plan** | Step 09 (migration_plan), Step 14 (migration_plan) | 2 steps | **Accidental duplication**. Both are free-text strings. Prompt 14 line 179 says "Use a short string describing how legacy work is migrated, or `none`" without referencing Step 09's migration_plan. |
| **Scope boundaries** | Step 00 (in_scope/out_of_scope), Step 01 (scope per capability), Step 16 (scope_in/scope_out), Step 16a (scope_in/scope_out) | 4 steps | **Intentional refinement** at each level but no validator checks consistency between them. |
| **Glossary terms** | Step 03 (definition), consumed by Steps 04, 05, 07 | 1+3 steps | **See Section 5** -- consumption is weaker than expected. |

---

## 3. Distillation Quality Grades

| Step | Transformation | Grade | Notes |
|---|---|---|---|
| 00 (Charter) | Seed -> structured | **B+** | Clear extraction intent; "ambiguity scrub" rule; coverage closure checklist. Missing: no worked example of transformation. |
| 01 (Capabilities) | Charter goals -> capabilities | **B** | Cross-check rule present. Missing: no guidance on decomposition granularity (how many capabilities per goal?). |
| 02 (System Sketch) | Capabilities -> components | **B** | Responsibility mapping guided. Missing: no guidance on how to decide component boundaries. |
| 02a (Delivery Baseline) | Sketch -> environments | **B-** | Parity rule for staging/prod. Missing: no guidance on deriving env config from sketch components. |
| 03 (Glossary) | Charter+Caps -> terms | **B** | Coverage formula stated. Missing: no guidance on domain decomposition strategy. |
| 04 (FRs) | Capabilities -> requirements | **C+** | Says "one behavior per FR" but does not explain HOW to decompose capabilities into FRs. AUDIT-001/003 apply. This is the most critical distillation in the pipeline (feeds 13 downstream steps) with the least transformation guidance. |
| 05 (APIs) | FRs -> interfaces | **B** | Maps each FR with external behavior to an API. Schema ref and error enumeration guided. |
| 06 (Invariants) | FRs+APIs -> rules | **B+** | Systematic discovery guidance: "data integrity constraints, state transition rules, access boundary rules." Best discovery methodology in Discovery Phase. |
| 07 (NFRs) | Charter metrics -> targets | **B** | Unit/measurement alignment guided. Missing: no guidance on deriving targets (what makes 200ms the right number?). |
| 08 (Fixtures) | FRs+APIs+Invariants -> tests | **B** | Coverage formula (FR criterion -> fixture) is clear. Missing: no guidance on test data selection. |
| 09 (Impl Plan) | All specs -> tech+milestones | **C+** | Cross-check for tech_stack. Missing: no guidance on how to group FRs into milestones. Milestone creation is left to LLM judgment. |
| 10 (Governance) | Charter+ImplPlan -> policies | **B-** | PR rules enumerated. Missing: no guidance on how organizational context translates to governance. |
| 11 (Red Team) | APIs+Sketch -> threats | **A-** | Best distillation guidance in the pipeline. "Attack -> Trace -> Mitigate" flow with weak-vs-strong examples, taxonomy, and specific coverage rules per threat category. |
| 12 (CI Gates) | Governance+Baseline -> jobs | **B** | Maps governance rules to CI jobs. DAG creation guided. |
| 13 (Extension Generator) | All specs -> extension manifest | **B+** | "Analyze -> Filter -> Plan" with clear criteria (">=3 dedicated schema sections"). |
| 13a (Completeness) | All specs -> gap assessment | **B** | Scoring rubric with deduction rules. |
| 14 (Roadmap) | ImplPlan+All -> execution plan | **B-** | "One Milestone = One User Story" rule. Missing: no guidance on deriving user stories from FRs. Tech stack is "copy from Step 09" -- no distillation. |
| 15 (Scaffold) | APIs+ImplPlan -> code skeleton | **B** | 1:1 mapping to APIs. Missing: no guidance on module decomposition. |
| 16 (Impl Context) | Roadmap -> Trinity Anchor | **A-** | Highly structured checklist-driven architecture. 13 field definitions with rules. |
| 16a (Impl Planner) | Roadmap -> checklist | **A** | Best in pipeline. Named phases, categorized forbidden actions, failure modes, roadmap-to-checklist coverage mandate, atomicity rules. |
| 16b (Impl Coder) | Plan -> execution | **A** | Evidence-bound execution with strict scope control. |
| 16c (Impl Reviewer) | Execution -> review | **A** | Evidence-based audit with semantic review, verdict gates, and roadmap sync side-effect. |

**Pattern**: Discovery Phase (Steps 00-12) averages B-/B. Implementation Phase (Steps 14-16c) averages A-/A. The quality gap is significant -- the steps that define the system (and where drift has the highest impact) have the weakest transformation guidance.

---

## 4. Pipeline Blind Spots

### 4.1 Security Model (Authentication, Authorization, Access Control)

**Coverage**: Scattered across Steps 02 (connection auth), 05 (API security), 06 (invariants), 07 (NFRs category:security), 11 (red team).

**Gap**: No single step captures a coherent security model. Authentication flows are described in capabilities (Step 01) and FRs (Step 04), but the authorization model (who can do what) is implicit. Step 11 (Red Team) identifies threats but does not define the positive security model. The pipeline lacks a "Security Architecture" step that would consolidate:
- Identity model (users, roles, service accounts)
- Permission model (RBAC, ABAC, resource-level)
- Token lifecycle (issuance, refresh, revocation)
- Trust boundaries (consolidated from Step 02)

This is partially addressed by Step 13 (Extension Generator) which can propose a security extension, but only if the LLM identifies the need.

### 4.2 Data Model / Entity Relationships

**Coverage**: Implicit in API schemas (Step 05 `input_schema_ref`/`output_schema_ref`), glossary entities (Step 03), and invariants (Step 06).

**Gap**: No step captures an explicit entity-relationship model. The glossary defines terms but not relationships between entities. Invariants define constraints but not the schema. API contracts reference schemas but do not define them inline. A data model would be derived during implementation, but by then the spec pipeline has no artifact governing it. Again, Step 13 may propose a database extension, but this is optional.

### 4.3 Deployment Topology

**Coverage**: Step 02a (Delivery Baseline) captures environments (dev/ci/staging/prod) with basic runtime/region config. Step 02 (System Sketch) has components with types (service, db, queue, etc.).

**Gap**: No step captures deployment topology: which components run where, how many instances, load balancing strategy, failover configuration. This is critical for NFR achievability but left to implementation.

### 4.4 Observability (Logging, Monitoring, Alerting)

**Coverage**: Step 07 (NFRs) captures measurement_method. Step 16a/16c (Trinity Loop) has `plan.delivery` for dashboards and alerts.

**Gap**: No Discovery Phase step captures observability requirements systematically. `measurement_method` in NFRs says "how to measure" but not "what to log" or "what dashboards to build." The Trinity Loop's `plan.delivery` section is per-milestone, not a system-wide observability plan.

### 4.5 Error Taxonomy

**Coverage**: Step 01 (error_states), Step 05 (API errors), Step 06 (invariants).

**Gap**: No step defines a system-wide error taxonomy. API errors are per-endpoint. Capability error_states are per-capability. Invariant violations are per-rule. There is no "error catalog" that provides consistent error codes, categories, and user-facing messages across the system. Step 13 could propose one, but it would not be a standard pipeline artifact.

### 4.6 Configuration Management

**Coverage**: Step 02a (secrets names), Step 16b (config_validation).

**Gap**: No step captures application configuration: feature flags, environment-specific settings, configuration schema, defaults vs overrides. Secrets are names only in Step 02a. Configuration management is deferred to implementation.

### 4.7 Third-Party Integration Contracts

**Coverage**: Step 02 captures external components with `type: external`. Step 05 captures internal APIs only.

**Gap**: Step 05 (Interface Contracts) focuses on APIs the system exposes. It does not capture APIs the system *consumes* from third parties. External integration contracts (expected request/response formats, auth requirements, rate limits, SLAs) are not formalized in any step. This information must be reverse-engineered from Step 02 connections and Step 11 threat analysis.

### 4.8 User Interface Specification

**Coverage**: None explicitly. Step 01 capabilities may describe UI behaviors. Step 04 FRs may describe user-facing flows.

**Gap**: No step captures UI wireframes, interaction flows, accessibility requirements, or frontend component architecture. The pipeline is heavily backend/API-centric.

---

## 5. Terminological Consistency Assessment

### 5.1 Glossary Consumption by Downstream Steps

The `downstream_consumers` in `step_order.json` shows Step 03 (Glossary) feeds only 3 steps: `["04", "05", "07"]`.

**Prompt references to glossary**:
- Step 04 (line 46): "Glossary `spec/03_glossary.json` to anchor terms" -- vague instruction, no enforcement
- Step 05 (line 45): Extraction Intent mentions "Term IDs, canonical resource names, and action vocabulary to align all route paths, request/response field names"
- Step 05 (line 74): Coverage Closure: "All resource and action names align with `term_id` values from `spec/03_glossary.json`" -- prompt-only, no validator
- Step 07: Extraction Intent mentions "Canonical term IDs, unit definitions, and domain vocabulary to align all NFR metric names"
- Step 08 (line 121): "reusing `term_id` values from `spec/03_glossary.json`" -- in Best Practices, not mandatory

**Steps that do NOT reference the glossary**: Steps 06 (Invariants), 09 (Impl Plan), 10 (Governance), 11 (Red Team), 12 (CI Gates), 13, 13a, 14, 15, 16, 16a, 16b, 16c. This means 15 of 19 downstream steps do not actively consume glossary terms.

**The glossary pitfall note** (prompt_03, line 126) says: "Every domain noun introduced in steps 04-16c MUST have a corresponding `term_id` in this glossary; downstream steps MUST NOT introduce terms not defined here." This is an aspirational statement with zero enforcement.

**Machine enforcement**: `cross_artifact_checks.py:check_step_04_integrity()` validates that FR trace references to glossary term_ids resolve. But this only checks `trace[].id` values with type "glossary" or prefix "term-" -- it does NOT check that FR `statement` text uses glossary-defined terms. No validator checks Steps 05-16c for glossary consistency.

**Assessment**: The glossary is effectively a standalone artifact. Its consumption is prompt-guided but not machine-enforced. Downstream steps can and likely do introduce terminology not in the glossary.

### 5.2 Canonical Registry Enforcement

Every prompt includes a "Canonical Registry" section requiring `*_ref` fields to bind to `canon/manifest.json` entries. The `canonical-lint` and `canonical-integrity` CLI commands enforce this. This provides a parallel vocabulary control mechanism to the glossary, but for structured canonical values (units, environments, stages, etc.) rather than domain prose terms.

**Assessment**: Canonical refs provide strong structural vocabulary control. Glossary provides weak prose vocabulary control. The gap is in natural-language fields (statements, descriptions, rationale) where drift occurs through paraphrasing.

---

## 6. ID Stability Analysis

### 6.1 ID Patterns

All IDs use kebab-case (`atoms.schema.json` `kebabId` pattern: `^[a-z0-9]+(?:-[a-z0-9]+)*$`). ID prefixes are enforced per step:
- `cap-*` (capabilities), `fr-*` (FRs), `api-*` (APIs), `inv-*` / `invariant-*` (invariants), `nfr-*` (NFRs), `fixture-*` (fixtures), `milestone-*` (milestones), `task-*` (tasks), `threat-*` (threats), `ec-*` (edge cases), `ext-*` (extensions)

### 6.2 ID Preservation Across Steps

**Schema-enforced**: Step 14 `fr_refs` uses pattern `^fr-[a-z0-9-]+$` and `capability_refs` uses `^cap-[a-z0-9-]+$`. Step 14 `source_milestones` are kebabIdArray. These enforce correct ID format but not that IDs exist in upstream artifacts (that requires cross-artifact validation).

**Validator-enforced**: `cross_artifact_checks.py` validates:
- Step 02 component traces -> Step 01 capability IDs
- Step 04 FR traces -> Step 01 capability IDs and Step 03 glossary term_ids

**Not enforced**:
- Step 05 API trace -> Step 04 FR IDs (matrix command checks this, but as a separate linting step)
- Step 09 milestone deliverables -> Step 04/05 IDs (no validator)
- Step 14 fr_refs -> Step 04 FR IDs (pattern check only, no existence check in validator)
- Step 14 capability_refs -> Step 01 capability IDs (pattern check only)

### 6.3 ID Rename During Replay

The pipeline requires "full forward replay on change" (step_order.json policy). If a capability ID changes from `cap-user-login` to `cap-user-authenticate`, all downstream steps must be replayed. The prompts instruct "IDs are stable and descriptive (avoid renaming once referenced downstream)" (prompt_04, line 107). However, no validator detects that a previously-existing ID has been removed in a replay -- the forward-replay check detects file-level changes (via git diff) but not ID-level changes within files.

**Gap**: ID stability is prompt-guided but not machine-enforced. An LLM replaying Step 04 after an upstream change could silently rename FR IDs, breaking downstream references that the forward-replay check would not catch until those downstream steps are also replayed and validated.

---

## 7. Findings

### R2-E-001: Capability-to-FR Decomposition Lacks Transformation Guidance
- **Severity**: HIGH
- **Location**: `prompts/prompt_04_functional_requirements.md` lines 58-63
- **Description**: Step 04 is the most critical distillation point in the pipeline (feeds 13 downstream steps) but its Operating Flow ("Build a private Context Ledger of candidate FRs") provides no methodology for how to decompose capabilities into FRs. No examples, no granularity guidance, no decomposition patterns. Reinforces existing AUDIT-001 and AUDIT-003.
- **Impact**: FR quality varies wildly between runs. Some LLMs produce 3 FRs, others produce 30 for the same input. Downstream steps inherit this variance.

### R2-E-002: Glossary Is Not Machine-Enforced in Downstream Steps
- **Severity**: HIGH
- **Location**: `tools/specdev_tools/validation/cross_artifact_checks.py`, `step_order.json` downstream_consumers
- **Description**: The glossary (Step 03) feeds only 3 steps in the DAG. 15 downstream steps do not consume it. The only machine enforcement is FR trace->glossary term resolution in Step 04. No validator checks that natural-language fields (statements, descriptions, user_stories) in Steps 04-16c use glossary-defined terms. The glossary's aspiration ("downstream steps MUST NOT introduce terms not defined here") is unenforceable.
- **Impact**: Semantic drift through synonym introduction. The same concept can have different names in different steps.
- **Cross-reference**: Per Decision 6, the glossary step is being repurposed as canon population (Step 03 → `cn:project:` namespace). Once project terms are in canon, canonical-lint enforces them automatically across all downstream steps. See R2-G-005, R2-G-006 for the infrastructure gaps and feasibility assessment. No NL tooling needed (Decision 5) — enforcement is via canonical ID references, not natural language matching.

### R2-E-003: Tech Stack Duplicated Across Steps 09 and 14 Without Integrity Check
- **Severity**: MEDIUM
- **Location**: `schema/09_impl_plan.schema.json`, `schema/14_roadmap.schema.json`
- **Description**: Both Step 09 and Step 14 have `tech_stack` fields with identical structure. Prompt 14 says "copy from Step 09" but no validator checks that Step 14 tech_stack matches Step 09. Step 14 could diverge silently.
- **Impact**: Implementation could use tech stack from Step 14 roadmap that contradicts Step 09 impl plan decisions.

### R2-E-004: Acceptance Criteria Duplicated Between Steps 04 and 14 With No Consistency Check
- **Severity**: MEDIUM
- **Location**: `schema/04_fr_list.schema.json` (FR acceptance_criteria), `schema/14_roadmap.schema.json` (task acceptance_criteria)
- **Description**: Step 04 defines acceptance criteria per FR. Step 14 defines acceptance criteria per task. The relationship between these is undefined. Task acceptance criteria could restate, refine, or contradict FR acceptance criteria. No prompt explains whether task criteria should reference or extend FR criteria.
- **Impact**: Ambiguity about which acceptance criteria are authoritative for implementation verification.

### R2-E-005: Migration Plan and Dependencies Duplicated Between Steps 09 and 14
- **Severity**: LOW
- **Location**: `schema/09_impl_plan.schema.json`, `schema/14_roadmap.schema.json`
- **Description**: Both steps have `migration_plan` (free-text string) and `dependencies` fields. Prompt 14 does not reference Step 09's versions of these fields. They could diverge.
- **Impact**: Low, as Step 14 is authoritative for execution, but creates confusion about which version to trust.

### R2-E-006: No Step Captures Consumed Third-Party API Contracts
- **Severity**: MEDIUM
- **Location**: Pipeline-wide
- **Description**: Step 05 (Interface Contracts) captures APIs the system exposes. No step captures APIs the system consumes from external services (identified in Step 02 as `type: external` components). External integration contracts (schemas, auth, SLAs, rate limits) have no formal home.
- **Impact**: Third-party integration issues discovered during implementation with no spec-level artifact to reference.

### R2-E-007: Security Model Is Scattered Across 5 Steps With No Consolidation
- **Severity**: MEDIUM
- **Location**: Steps 02 (auth), 05 (security), 06 (invariants), 07 (security NFRs), 11 (threats)
- **Description**: Authentication, authorization, and access control information is distributed across 5 steps with no single authoritative view. The pipeline has no "Security Architecture" artifact. Step 13 may propose a security extension but this is discretionary.
- **Impact**: Security model inconsistencies between steps. An API security setting (Step 05) could contradict an invariant (Step 06) or a red team mitigation (Step 11) with no cross-check.

### R2-E-008: Data Model Has No Dedicated Artifact
- **Severity**: MEDIUM
- **Location**: Pipeline-wide
- **Description**: Entity relationships are implicit across glossary terms (Step 03), API schemas (Step 05), and invariants (Step 06). No step captures an explicit data model (entities, attributes, relationships, cardinality). This information emerges during implementation with no spec-level governance.
- **Impact**: Data model decisions made during implementation may not satisfy FRs or invariants. Schema evolution has no spec-level tracking.

### R2-E-009: Discovery Phase Prompts (00-12) Have Significantly Weaker Distillation Guidance Than Implementation Phase (16a-16c)
- **Severity**: HIGH
- **Location**: `prompts/prompt_00_project_charter.md` through `prompts/prompt_12_ci_gates.md`
- **Description**: Discovery Phase prompts use a generic "Synthesize -> Clarify -> Emit" flow with step-specific heuristics but no named decomposition phases, no categorized forbidden actions, no weak-vs-strong examples (except Step 11), and no failure mode tables. Implementation Phase prompts (16a/16b/16c) demonstrate that these patterns work. The quality gap is documented in AUDIT-001 but the drift implications are distinct: weak distillation guidance in Discovery Phase means requirements arrive at Implementation Phase already degraded.
- **Impact**: Requirements quality degrades through the pipeline before implementation even begins.

### R2-E-010: ID Stability Is Prompt-Guided But Not Machine-Enforced During Replay
- **Severity**: MEDIUM
- **Location**: `tools/specdev_tools/validation/`, `tools/step_order.json`
- **Description**: Forward-replay detection operates at the file level (git diff). If a Step 04 replay renames `fr-user-login` to `fr-user-authenticate`, the forward-replay check triggers downstream replay but no validator checks whether previously-existing IDs were removed or renamed. Downstream steps replayed with the old ID would fail validation, but this is a cascading failure rather than an early detection.
- **Impact**: ID renames during replay create cascading validation failures rather than early detection at the rename point.

### R2-E-011: Step 09 -> Step 14 Deliverable Decomposition Is Not Validated
- **Severity**: HIGH
- **Location**: `tools/specdev_tools/validation/validators/step_14.py`, reinforces AUDIT-005
- **Description**: Step 14 validator checks that `source_milestones` reference valid Step 09 milestone IDs, but does not verify that Step 09 milestone deliverables are fully represented in Step 14. A Step 09 milestone with 5 FR deliverables can be decomposed into a Step 14 milestone with only 2 fr_refs, silently dropping 3 FRs from the execution plan.
- **Impact**: FRs committed in the implementation plan can be silently dropped from the execution roadmap.

### R2-E-012: No Validator Enforces FR Coverage Across the Full Pipeline
- **Severity**: HIGH
- **Location**: Pipeline-wide
- **Description**: The intended FR lifecycle is: Capability (01) -> FR (04) -> API (05) -> Fixture (08) -> Milestone deliverable (09) -> Roadmap fr_ref (14) -> Checklist item (16a). Each link has partial enforcement: cross_artifact_checks validates 01->04 and some of 04->05 via matrix. But no single validator traces an FR from Step 01 through to Step 16a checklist coverage. The `matrix` command generates a coverage report but only covers FR->API->Fixture, not the full chain.
- **Impact**: An FR can be defined in Step 04, traced to a capability in Step 01, but silently dropped from fixtures (Step 08), milestones (Step 09), roadmap (Step 14), or implementation plan (Step 16a).
