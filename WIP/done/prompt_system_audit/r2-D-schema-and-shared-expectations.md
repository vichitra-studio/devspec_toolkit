# R2-D: Schema Description Enrichment Assessment & shared_expectations.md Architecture Design

**Date**: 2026-03-20
**Scope**: Schema description quality for prompt content migration; shared_expectations.md redesign
**Files Reviewed**: 5 schemas, 10+ prompts, shared_expectations.md, master findings, core/atoms, core/collections, canon/manifest

---

## Part 1: Schema Description Enrichment Assessment

### 1.1 Per-Schema Evaluation

#### schema/04_fr_list.schema.json (114 LOC)

**Current description quality**: ADEQUATE but THIN. Descriptions answer WHAT but rarely WHY or FORBIDDEN.

| Field | Current Description | Missing From Description (present in prompt) |
|---|---|---|
| `statement` | "Clear statement of the functional requirement, minimum 20 characters." | Prompt says: "MUST use outcome-oriented phrasing; MUST NOT include implementation details (function names, DB tables, internal method signatures) or multiple behaviors." None of this is in the schema description. |
| `acceptance_criteria` (array) | "Testable criteria that define when this requirement is satisfied, at least 2 required." | Prompt says: "exact observable outcome; include inputs and expected outputs/state changes." Missing forbidden pattern: "DO NOT leave acceptance criteria vague ('it works')." |
| `acceptance_criteria[*].text` | "Descriptive text of the acceptance criterion, minimum 15 characters." | Prompt says: use "Given-When-Then" phrasing. Missing: "include inputs and expected outputs/state changes." |
| `functional_requirements` (array) | "Array of functional requirements derived from capabilities, each with acceptance criteria and trace links." | Missing: "each FR describes exactly one behavior" (the one-behavior-per-FR rule). |
| `fr_id` | "Unique kebab-case identifier for this functional requirement (e.g., 'fr-user-login')." | Prompt says: "fr-<behavior>; one behavior per FR." Missing: "IDs are stable and descriptive (avoid renaming once referenced downstream)." |
| `trace` | "Traceability links back to upstream capabilities or charter items." | Prompt says: "MUST map every FR to its originating capability." Forbidden: "DO NOT trace to non-existent IDs." Missing: object structure mandate. |
| `rationale` | "Explanation of why this requirement exists and what business need it addresses." | Prompt: "tie to business value or risk." Adequate but could be richer. |
| `preconditions` | "Conditions that must hold before this requirement can be exercised." | Prompt: "set when environment or state boundaries exist." Missing when-to-include guidance. |

**Verdict**: 6 of 8 key fields have prompt guidance that should migrate to schema descriptions.

#### schema/05_interface_contracts.schema.json (188 LOC)

| Field | Current Description | Missing From Description (present in prompt) |
|---|---|---|
| `api_id` | "Unique kebab-case identifier for this API (e.g., 'api-session-create')." | Prompt: "api-<resource>-<action>; stable across codegen and monitoring." |
| `security` | "Authentication/authorization mechanism for this API: none, api-key, oauth2, jwt, or mTLS." | Prompt: "MUST NOT use `none` for APIs that access authenticated resources, PII, or state-mutating operations." This is a critical semantic constraint absent from the schema description. |
| `errors` | "Array of error states that this API may return." | Prompt: "MUST include at least one error state for every non-GET mutating operation." Forbidden: "DO NOT use generic error names like 'Error'." |
| `path` | "URL path for this API endpoint (e.g., '/api/v1/sessions')." | Prompt: "concrete path and verb for HTTP; use gRPC service/method names for grpc." |
| `version` | "API version string in vN or vN.N format (e.g., 'v1', 'v2.1')." | Prompt: "MUST bump version when request/response formats or semantics change materially." |
| `input_schema_ref` | "Reference to the JSON Schema defining the request body structure." | Prompt: "MUST use machine-resolvable locations when schema files exist in the repository." |

**Verdict**: `security` and `errors` have the largest description-vs-prompt gap. The `security` forbidden pattern (no `none` for authenticated/PII/mutating) is critical domain knowledge absent from the schema.

#### schema/09_impl_plan.schema.json (122 LOC)

| Field | Current Description | Missing From Description (present in prompt) |
|---|---|---|
| `tech_stack` | "Technology stack for the implementation, including languages, frameworks, infrastructure, and tools." | Prompt: "MUST be an object (not array). Each item must have `name`, `version`, and `rationale`." Forbidden: "Do NOT use 'latest' or 'stable'. Do NOT provide tech_stack as a list of strings." |
| `milestones` | "Ordered list of implementation milestones with deliverables and status tracking." | Prompt: "MUST populate `target_date` when milestones have ordering dependencies." Forbidden: "NO Orphan Milestones: Do not create milestones that do not link to at least one FR or API in deliverables." |
| `migration_plan` | "High-level strategy for migrating from existing systems or data to the new implementation." | Prompt: "MUST include migration_plan when any component_id in 02_system_sketch.json has status: deprecated." This conditional requirement is absent from the schema description. |
| `milestones[*].risks` | "Known risks that could delay or block this milestone." | Prompt: "concrete bullets (e.g., perf unknowns, vendor limits, schema evolution)." Missing specificity guidance. |

**Verdict**: `tech_stack` has the largest gap -- the prompt's structural requirements and forbidden patterns are absent from the schema description.

#### schema/14_roadmap.schema.json (252 LOC)

| Field | Current Description | Missing From Description (present in prompt) |
|---|---|---|
| `milestones` | "Ordered roadmap milestones with user stories, tasks, and deliverables." | Prompt: "Each milestone corresponds to exactly one user story." This is a critical structural constraint absent from the description. |
| `tasks[*].description` | "Description of the task (must contain at least two words)." | Prompt: "Use imperative verb form in description (e.g., 'Implement authentication module')." |
| `tasks[*].depends_on` | "task_ids this task depends on (within same milestone). Must not create cycles." | Good -- cycle prohibition is already in the description. |
| `fr_refs` | "FR IDs from spec/04_fr_list.json that this milestone delivers." | Prompt: "If this milestone has deliverables, fr_refs MUST be non-empty... A milestone with deliverables but no fr_refs is a traceability gap and a red flag." This conditional requirement is absent. |
| `source_milestones` | "Upstream Step 09 milestone IDs this roadmap milestone maps to." | Prompt: "Every milestone must include source_milestones that map to Step 09 IDs." Already present but could emphasize that it's a REQUIRED traceability link. |
| `migration_plan` | "High-level strategy for migrating from existing systems or data." | Prompt: "If not 'none', use at least three words and keep it under 40 words." |
| `dependencies` items | Via $ref to dependencyItem | Prompt: "For external dependencies: owner and note are required." Already in schema via if/then, but description doesn't explain this. |

**Verdict**: The `milestones` "one user story per milestone" rule and `fr_refs` non-empty conditional are the largest gaps.

#### schema/16_impl_context.schema.json (~400 LOC)

| Field | Current Description | Missing From Description (present in prompt) |
|---|---|---|
| `commit_hash` | "Full 40-character git commit hash pinning this reference. Must not be all zeros." | Good -- the not-all-zeros constraint IS in the description (and in the schema via `not` pattern). |
| `evidence.content` | "The evidence content itself (minimum 20 characters, must contain non-whitespace)." | Good -- constraints are in description. |
| `plan.status` | "Whether this plan is actively being worked on or deferred." | Missing: Prompt says deferred plans must have `deferred_reason`. |
| `checklist[*].type` | "Classification of the checklist item: behavior, constraint, validation, metadata, performance, logging, docs, or security." | Missing: When to use each type. Prompt provides no guidance either -- both are thin here. |
| `checklist[*].layer` | "Architecture layer this checklist item applies to." | Same gap as `type` -- no guidance on when to use each value. |

**Verdict**: Step 16 schema descriptions are the RICHEST of all schemas reviewed. The `$defs` section in particular has well-constrained descriptions with forbidden patterns already embedded (e.g., commit_hash not-all-zeros). This is the gold standard the other schemas should follow.

### 1.2 What Should Migrate From Prompts to Schema Descriptions

Below are specific, implementable migration items ordered by impact:

#### TIER 1 -- Critical Semantic Constraints (should migrate immediately)

1. **`04_fr_list.schema.json` > `statement` description**: Add "MUST use outcome-oriented phrasing. MUST NOT include implementation details (function names, DB tables, internal method signatures) or multiple behaviors."
   - Source: `prompts/prompt_04_functional_requirements.md` lines 111, 132-133

2. **`04_fr_list.schema.json` > `functional_requirements` items description**: Add "Each FR describes exactly one behavior."
   - Source: `prompts/prompt_04_functional_requirements.md` line 102

3. **`05_interface_contracts.schema.json` > `security` description**: Add "MUST NOT use 'none' for APIs that access authenticated resources, PII, or state-mutating operations."
   - Source: `prompts/prompt_05_interface_contracts.md` line 58

4. **`05_interface_contracts.schema.json` > `errors` description**: Add "MUST include at least one error state for every non-GET mutating operation. Do not use generic error names like 'Error'."
   - Source: `prompts/prompt_05_interface_contracts.md` lines 56, 125

5. **`09_impl_plan.schema.json` > `tech_stack` description**: Add "Must be an object with `languages`, `frameworks`, `infrastructure`, `tools` arrays -- not a flat list. Do not use 'latest' or 'stable' for versions."
   - Source: `prompts/prompt_09_impl_plan.md` lines 94-98

6. **`14_roadmap.schema.json` > `milestones` items description**: Add "Each milestone corresponds to exactly one user story decomposed into atomic sub-tasks."
   - Source: `prompts/prompt_14_roadmap.md` line 21, line 92

7. **`14_roadmap.schema.json` > `fr_refs` description**: Add "If this milestone has deliverables, fr_refs MUST be non-empty. A milestone with deliverables but empty fr_refs is a traceability gap."
   - Source: `prompts/prompt_14_roadmap.md` line 162

#### TIER 2 -- Behavioral Guidance (should migrate in second pass)

8. **`04_fr_list.schema.json` > `acceptance_criteria[*].text` description**: Add "Use Given-When-Then phrasing. Include specific inputs and expected outputs/state changes."
   - Source: `prompts/prompt_04_functional_requirements.md` lines 68, 114

9. **`04_fr_list.schema.json` > `fr_id` description**: Add "Use pattern fr-<behavior>. IDs are stable -- avoid renaming once referenced downstream."
   - Source: `prompts/prompt_04_functional_requirements.md` lines 110, 107

10. **`05_interface_contracts.schema.json` > `api_id` description**: Add "Use pattern api-<resource>-<action>. Must be stable across codegen and monitoring."
    - Source: `prompts/prompt_05_interface_contracts.md` line 99

11. **`05_interface_contracts.schema.json` > `version` description**: Add "MUST bump version when request/response formats or semantics change materially."
    - Source: `prompts/prompt_05_interface_contracts.md` line 57

12. **`09_impl_plan.schema.json` > `migration_plan` description**: Add "Required when any component in 02_system_sketch.json has status: deprecated or is being replaced."
    - Source: `prompts/prompt_09_impl_plan.md` line 61

13. **`14_roadmap.schema.json` > `tasks[*].description` description**: Add "Use imperative verb form (e.g., 'Implement authentication module')."
    - Source: `prompts/prompt_14_roadmap.md` line 137

### 1.3 Proposed Description Format Pattern

Three-sentence pattern for enriched descriptions:

```
Sentence 1: WHAT the field is.
Sentence 2: Constraints beyond what type/enum/pattern enforce.
Sentence 3: Forbidden patterns or common mistakes.
```

**Example -- current `statement` description:**
```
"Clear statement of the functional requirement, minimum 20 characters."
```

**Example -- enriched `statement` description:**
```
"Clear statement of the functional requirement, minimum 20 characters. MUST use outcome-oriented phrasing with concrete verbs and measurable outcomes; describes exactly one behavior per FR. MUST NOT include implementation details (function names, DB tables, internal method signatures), vague adjectives, or multiple behaviors."
```

**Feasibility**: JSON Schema string descriptions have no length limit. The enriched format adds 20-60 words per field. For a schema with 15-20 fields, this adds ~400-1200 words -- acceptable for LLM consumption and negligible for validator performance.

### 1.4 Limitations -- What Cannot Live in Schema Descriptions

The following categories of prompt guidance CANNOT migrate to schema descriptions:

1. **Cross-field relationships with upstream context**: "MUST include migration_plan when any component in 02_system_sketch.json has status: deprecated." This references a different file. Schema descriptions can mention the rule, but enforcement stays in prompts/validators.

2. **Holistic document-level guidance**: "Each milestone corresponds to exactly one user story" is a document-level structural constraint. It CAN go in the description of the `milestones` array, but it cannot be schema-enforced.

3. **Operating flow / reasoning scaffolds**: "Build a private Context Ledger" and step-specific reasoning phases are LLM behavioral instructions, not field semantics.

4. **Extraction intents and upstream consumption rules**: Which upstream artifacts to read and what to extract from them is runtime context, not field metadata.

5. **Conflict resolution protocols**: How to handle contradictory inputs is a process rule, not a field constraint.

6. **Self-Audit Gate items**: Input sufficiency checks are decision-making guidance, not field descriptions.

**Summary**: Schema descriptions can absorb ~60-70% of the "Field-by-Field Guidance" and "Negative Constraints" sections. The remaining ~30-40% (cross-step context, reasoning scaffolds, operating flow) stays in prompts.

### 1.5 Canonical Fields Assessment

Fields validated against canon (`owner`, `traceRef.type`, etc.) currently use a hybrid approach:

- **`owner` (atoms.schema.json)**: Description says "validated against canon/kinds/owner.json entries." Does NOT enumerate values. This is CORRECT -- delegating to canon avoids staleness.
- **`traceRef.type` (collections.schema.json)**: Description says "validated against canon/kinds/trace_type.json entries." Uses pattern `^[a-z][a-z0-9_]*$` but no enum. CORRECT.
- **Enum fields (`milestoneStatus`, `httpMethod`, etc.)**: These have inline enums in the schema. They are NOT canon-validated; they are schema-enforced. CORRECT for fixed vocabularies.

**Recommendation**: Continue the current pattern. Schema descriptions for canon-validated fields should point to the canon kind file, not enumerate values. This prevents drift between schema descriptions and canon entries.

---

## Part 2: shared_expectations.md Architecture Design

### 2.1 Current State Assessment

- **Location**: `docs/prompts/shared_expectations.md`
- **Size**: 51 LOC
- **Referenced by**: 8 of 22 prompts (00, 01, 02, 02a, 03, 04, 16b, 16c)
- **Content**: Definition of Ready reference, Working Increment, Checks, Canonical Reuse Rules, Canonical Resolution Protocol, one-go Quality Protocol, Step-Order Policy, Failure Modes
- **Problem**: Undersized. Contains ~30% of what should be shared. 14 prompts don't reference it. The prompts that DO reference it also contain duplicate content (Canonical Binding Rules, Hardening Protocol) that repeats what shared_expectations says differently.

### 2.2 What Should Be in shared_expectations.md

Based on reading all 22 prompts, the following sections are candidates for extraction:

| Section | Occurrence | LOC per instance | Total extractable LOC | Status |
|---|---|---|---|---|
| Schema Authority block | 22/22 | 4 | 88 | Identical across all prompts |
| Path Variables table | 22/22 | 8 | 176 | Identical across all prompts |
| Hardening Protocol | 22/22 | 4 | 88 | Identical (except Step 12 variant) |
| Canonical Registry (Required Input) | 22/22 | 7 | 154 | Near-identical (Step 12 has extras) |
| Canonical Binding Rules | 22/22 | 6 | 132 | Identical across all prompts |
| Metadata Contract | 22/22 | 3 | 66 | Identical across all prompts |
| Generic Output Rules (items 1-3, 6, 8) | 22/22 | 5 | 110 | Identical across all prompts |
| Tool Execution (validate command) | 22/22 | 3 | 66 | Near-identical |
| Generic Role statement | 18/22 | 2 | 36 | Near-identical (Trinity prompts differ) |
| Generic Task block | 18/22 | 5 | 90 | Near-identical |
| Self-Audit Gate protocol | 22/22 | 2 | 44 | Frame is identical; items are step-specific |
| Coverage Closure checklist (last 3 items) | 22/22 | 3 | 66 | Identical across all prompts |
| Conflict Resolution Protocol | 0/22 | 0 | 0 | NEW -- needed per AUDIT-002 |
| Implicit Requirements Discovery | 0/22 | 0 | 0 | NEW -- needed per AUDIT-003 |
| **Total extractable** | | | **~1,116** | |

### 2.3 Proposed Table of Contents

```markdown
# Shared Expectations (Universal Prompt Protocols)

## 1. Schema Authority Protocol
   - Schema is authoritative for fields, types, enums, patterns
   - MUST read schema before generating output
   - Do NOT guess or invent fields
   [Source: identical block in all 22 prompts]
   [Applicability: ALL steps]

## 2. Path Variables
   - $PRODUCT_ROOT, $TOOLKIT_ROOT, $SPEC_DIR, $SCHEMA_DIR
   [Source: identical table in all 22 prompts]
   [Applicability: ALL steps]

## 3. Canonical Binding Protocol
   ### 3.1 Registry Loading
   - Load canon/manifest.json and canon/aliases.json
   - Search for existing entries before populating *_ref fields
   [Source: "Canonical Registry (Required Input)" in all 22 prompts]

   ### 3.2 Binding Rules
   - canonical_refs_used is REQUIRED
   - canonical_proposals for new terms
   - canonical_conflicts for ambiguous matches
   - *_ref fields MUST be populated when semantic content exists
   [Source: "Canonical Binding Rules" in all 22 prompts]

   ### 3.3 Resolution Protocol
   - Deterministic order: exact match > alias > proposal
   - Multiple matches -> canonical_conflicts
   - No match -> canonical_proposals
   [Source: existing shared_expectations.md]

   ### 3.4 Deprecated Handling (from Step 12 variant)
   - Check replaced_by before using deprecated canonicals
   - NEVER leave a *_ref field empty when a matching entry exists
   [Source: prompt_12_ci_gates.md lines 170-171, per AUDIT-007]
   [Applicability: ALL steps]

## 4. Hardening Protocol
   - Fail-closed preflight
   - No-Invention Rules
   - Completeness Closure
   - Blocker report
   [Source: identical block in all 22 prompts]
   [Applicability: ALL steps]

## 5. Output Rules (Universal)
   - Write JSON directly to disk at spec path
   - JSON must validate against step schema
   - All IDs must be unique kebab-case strings
   - Owner enum values
   - additionalProperties is false everywhere
   - Do not include fields outside the schema
   [Source: Output Rules items 1-3, 6, 8 in all 22 prompts]
   [Applicability: ALL steps]

## 6. Metadata Contract
   - Output MUST include every field in schema's required[] array
   - Do NOT add fields not defined in schema
   - Do NOT restate schema constraints in prompts
   [Source: identical block in all 22 prompts]
   [Applicability: ALL steps]

## 7. Clarify-Emit Protocol
   ### 7.1 Self-Audit Gate (Input Sufficiency)
   - If ANY gating item cannot be satisfied from available context,
     enter Clarify mode
   - Gating items are defined per-step in each prompt
   - DO NOT emit JSON when gating items fail
   [Source: all 22 prompts, redesigned per AUDIT-009]

   ### 7.2 Coverage Closure (Post-Generation Validation)
   - Every upstream ID consumed OR explicitly listed in out_of_scope
   - No placeholder tokens remain (TBD, TODO, FIXME, XXX)
   - All required fields populated from actual upstream data (not hallucinated)
   - All trace/links IDs resolve to IDs present in referenced upstream spec
   [Source: all 22 prompts, promoted to sibling heading per AUDIT-011]
   [Applicability: ALL steps]

## 8. Conflict Resolution Protocol [NEW]
   - Detection: when two upstream specs provide contradictory values
     for the same semantic field
   - Precedence: later step number takes precedence unless charter
     explicitly constrains
   - Action: flag as Gap Question with both sources cited
   - DO NOT silently resolve by picking one input
   [Source: NEW, per AUDIT-002]
   [Applicability: Steps 04, 05, 06, 07, 09, 14 (multi-input steps)]

## 9. Implicit Requirements Discovery [NEW]
   - For every mutating FR: consider idempotency, conflict handling, audit trail
   - For every list FR: consider pagination, filtering, sorting
   - For every authenticated endpoint: consider session management, rate limiting
   - For every data store: consider backup, migration, data retention
   [Source: NEW, per AUDIT-003]
   [Applicability: Steps 04, 05, 06 (requirement-producing steps)]

## 10. Traceability Rules (Universal)
   - Trace arrays use object format: {"type": "...", "id": "...", "note": "..."}
   - DO NOT use simple strings or string arrays for trace fields
   - Include at least one reference to connect artifacts across steps
   - Use concrete verbs and measurable outcomes
   [Source: Output Rules items 4, 5, 7 in all 22 prompts]
   [Applicability: ALL steps with trace fields]

## 11. Tool Execution
   - Validate command template
   - Seed manifest reading protocol
   [Source: Tool Execution in all 22 prompts]
   [Applicability: ALL steps]

## 12. Step-Order Policy
   - Forward-only execution model
   - Any change at step N requires full replay through N+1...end
   [Source: existing shared_expectations.md]
   [Applicability: ALL steps]

## 13. Failure Modes (Universal)
   - Over-broad scope or vague statements
   - Broken references to other steps
   - Hidden assumptions not captured
   [Source: existing shared_expectations.md]
   [Applicability: ALL steps]
```

### 2.4 Interface Contract Between Prompts and shared_expectations.md

**Recommendation**: Explicit include directive at the top of every prompt.

Each prompt should begin with:

```markdown
# Step NN · Step Name

> **Prerequisite**: Read `$TOOLKIT_ROOT/docs/prompts/shared_expectations.md` first.
> It defines: Schema Authority, Path Variables, Canonical Binding, Hardening Protocol,
> Output Rules, Metadata Contract, Clarify-Emit Protocol, Conflict Resolution,
> Tool Execution, and Step-Order Policy. These apply to ALL steps and are not
> repeated here.
```

**What prompts KEEP after extraction**:

1. Purpose (step-specific)
2. Role (step-specific for Steps 11, 16, 16a, 16b, 16c)
3. Extraction Intent (step-specific)
4. Operating Flow (step-specific)
5. Self-Audit Gate ITEMS (step-specific, but protocol is shared)
6. Coverage Closure step-specific items (e.g., Extraction Mandate)
7. Field-by-Field Guidance (step-specific; partially absorbed by schema descriptions)
8. Negative Constraints (step-specific; partially absorbed by schema descriptions)
9. Best Practices (step-specific)
10. Common Pitfalls (step-specific)
11. Clarification Questions (step-specific)
12. Schema Reference (step-specific URI/file)
13. Output Contract (step-specific example)

### 2.5 Subset Applicability

Some protocols apply to subsets of steps. The design handles this with:

1. **Applicability tags** in shared_expectations.md: Each section ends with `[Applicability: ALL steps]` or `[Applicability: Steps 04, 05, 06]`.

2. **Conditional protocols**: "Conflict Resolution Protocol" applies to multi-input steps only. The section states which steps it applies to. Prompts for those steps include a one-line reference: "See Conflict Resolution Protocol in shared_expectations.md."

3. **Implicit Requirements Discovery**: Applies only to requirement-producing steps (04, 05, 06). Listed explicitly in the section.

This avoids the complexity of a conditional include system while keeping the governance document self-documenting.

### 2.6 Self-Audit Gate Redesign

**Current problems** (per AUDIT-009, AUDIT-010, AUDIT-011):
- "Score < 0.9" is undefined and unfalsifiable
- Gate mixes input sufficiency with output quality
- Coverage Closure is structurally coupled to the gate

**Proposed redesign**:

The Self-Audit Gate decomposes into THREE separate concerns:

1. **Input Sufficiency Gate** (BEFORE generation) -- stays in Self-Audit Gate
   - "If ANY gating item below cannot be satisfied from available context, enter Clarify mode."
   - Gating items are per-step (defined in each prompt)
   - Replaces numeric score with boolean AND of gating items
   - Pure input check: "Do I have what I need to produce this artifact?"

2. **Coverage Closure** (AFTER generation) -- promoted to sibling heading
   - "Before emitting, verify all upstream IDs consumed."
   - Universal checklist items in shared_expectations.md
   - Step-specific items (Extraction Mandate) in each prompt
   - Pure output check: "Did I consume everything I was supposed to?"

3. **Output Quality Checks** (AFTER generation) -- moved to Negative Constraints
   - Anti-pattern checks (e.g., "Are extensions redefining standard API routes?")
   - Quality criteria (e.g., "Success metrics include unit+target for >=2 metrics")
   - These are validation, not flow control

**Protocol in shared_expectations.md** (Section 7):

```
## 7. Clarify-Emit Protocol

### Phase 1: Input Sufficiency Gate
Before generating output, evaluate ALL gating items defined in this step's
"Self-Audit Gate" section. If ANY gating item cannot be satisfied from
available context:
- Enter Clarify mode
- Output ONLY short bulleted gap questions grouped by field/topic
- Do NOT emit JSON
- Do NOT output code fences
- Wait for answers before proceeding

### Phase 2: Generation
Proceed with artifact generation using the Operating Flow defined
in this step's prompt.

### Phase 3: Coverage Closure
After generating the artifact but BEFORE writing to disk:
- [ ] Every upstream ID from extraction intent has been consumed
- [ ] No placeholder tokens remain (TBD, TODO, FIXME, XXX)
- [ ] All required fields populated from actual upstream data (not hallucinated)
- [ ] All trace/links IDs resolve to IDs in referenced upstream specs
- [ ] Step-specific closure items (defined per prompt) are satisfied

If any closure item fails, either fix the artifact or enter Clarify mode
for the specific gap.
```

### 2.7 Documentation Resource Guidance

**Current state**: 46 of 53 docs are never referenced by any prompt (per AUDIT-025). No prompt knows what documentation is available.

**Recommendation**: Do NOT add a full doc map to shared_expectations.md. Instead:

1. Add a short section pointing to the doc index:
   ```
   ## Available Documentation
   For documentation beyond seeds and schemas, consult
   `$TOOLKIT_ROOT/docs/` directory. Key references:
   - `docs/developers/reference.md` -- developer API reference
   - `docs/developers/extension_schemas.md` -- extension schema guide
   - `docs/developers/path_conventions.md` -- file path conventions
   - `docs/agents/manifest.json` -- agent protocol definitions
   ```

2. Step-specific doc references stay in individual prompts where relevant.

This keeps shared_expectations lean while addressing the discoverability gap.

### 2.8 Token Economics

**Current state**:
- Total prompt LOC: 5,927 (sum of all 22 prompts)
- shared_expectations.md: 51 LOC
- Extractable identical content: ~1,116 LOC across 22 prompts

**Projected state after extraction**:
- New shared_expectations.md: ~200-250 LOC (extracted + new Conflict Resolution + Implicit Discovery + Clarify-Emit redesign)
- Per-prompt reduction: ~40-55 LOC per prompt (varies; Steps 00-15 lose ~50 LOC each, Steps 16-16c lose ~35 LOC)
- New per-prompt addition: ~5 LOC (prerequisite directive)
- Total prompt LOC after: ~5,927 - 1,116 + 110 (directives) = ~4,921 LOC
- Net reduction: ~1,006 LOC (~17%)
- Per-session token savings: ~750-1,000 tokens (one shared_expectations load replaces per-prompt repetition)

**Net system LOC**: 5,927 + 51 = 5,978 (before) vs 4,921 + 250 = 5,171 (after). Net reduction: ~807 LOC (13.5%).

The real win is not LOC but **maintenance burden**: changes to shared protocols require editing 1 file instead of 22.

---

## Part 3: Findings

### R2-D-001: Schema Descriptions Are Coverage-Complete But Semantics-Thin
- **Severity**: HIGH
- **Evidence**: Of 5 schemas reviewed, 4 have fields where prompt guidance contains critical semantic constraints (forbidden patterns, conditional requirements, behavioral expectations) absent from schema descriptions. Step 16's schema is the exception -- its descriptions already include forbidden patterns and are the gold standard.
- **Impact**: LLMs reading only the schema (as Schema Authority directs) miss ~60% of the field-level guidance that currently lives only in prompts.
- **Proposed Fix**: Enrich descriptions using the three-sentence pattern (WHAT / CONSTRAINTS / FORBIDDEN) for the 13 TIER 1+2 fields identified in Section 1.2. Estimate: ~2 hours of work.

### R2-D-002: shared_expectations.md Is Undersized and Under-Referenced
- **Severity**: HIGH
- **Evidence**: 51 LOC covering ~30% of what should be shared. 14 of 22 prompts don't reference it. Prompts that DO reference it still contain duplicate content (Canonical Binding Rules, Hardening Protocol).
- **Impact**: ~1,116 LOC of extractable identical content repeated across 22 files. Maintenance burden: any change to shared protocols requires 22 edits.
- **Proposed Fix**: Expand to ~250 LOC with 13 sections as designed in Section 2.3. Add prerequisite directive to all 22 prompts.

### R2-D-003: Self-Audit Gate Requires Decomposition Into Three Concerns
- **Severity**: HIGH
- **Evidence**: Per AUDIT-009/010/011, the gate conflates input sufficiency (Clarify/Emit decision), output completeness (Coverage Closure), and output quality (anti-pattern checks). All three evaluate at different times but are structurally merged.
- **Impact**: LLMs unclear about WHEN to evaluate the gate. Coverage Closure failures incorrectly trigger Clarify mode instead of post-generation fixes.
- **Proposed Fix**: Decompose per Section 2.6. Input Sufficiency Gate = boolean AND of gating items (pre-generation). Coverage Closure = post-generation checklist (promoted to sibling heading). Output quality = Negative Constraints section.

### R2-D-004: Conflict Resolution Protocol Is Absent System-Wide
- **Severity**: HIGH
- **Evidence**: Per AUDIT-002, no prompt addresses contradictory upstream inputs. Zero of 22 prompts have conflict resolution guidance.
- **Impact**: LLMs silently resolve contradictions, propagating incorrect assumptions downstream.
- **Proposed Fix**: Add Section 8 to shared_expectations.md. Multi-input steps (04, 05, 06, 07, 09, 14) add one-line reference.

### R2-D-005: Schema Description Enrichment Must Not Duplicate Prompt Content
- **Severity**: MEDIUM
- **Design Decision**: When field-level guidance migrates to schema descriptions, the corresponding Field-by-Field Guidance in prompts should either (a) be removed and replaced with "See schema description for field constraints," or (b) be reduced to only cross-field and cross-step guidance. Option (b) is safer for the first pass.
- **Recommendation**: Option (b) -- keep Field-by-Field in prompts but strip content that is now in schema descriptions. This avoids a hard dependency on LLMs reading schema descriptions before prompt content.

### R2-D-006: Quick Reference Sections Should Be Removed After Schema Enrichment
- **Severity**: MEDIUM
- **Evidence**: Per AUDIT-008, Quick Reference is a strict subset of Field-by-Field in 15 of 17 prompts and actively omits required fields.
- **Impact**: Once schema descriptions are enriched and shared_expectations absorbs universal rules, Quick Reference serves no purpose and risks field omissions.
- **Proposed Fix**: Remove Quick Reference from Steps 00-15. Keep it for Step 16 where it serves a different structural purpose.

### R2-D-007: Extraction Intent Sections Cannot Be Absorbed By Schemas or shared_expectations
- **Severity**: INFO
- **Evidence**: Extraction Intent is step-specific and references concrete upstream file names, field names, and extraction logic. It is the most valuable step-specific content in each prompt.
- **Recommendation**: Extraction Intent stays in individual prompts. It cannot be shared or schematized. It should be strengthened with Extraction Mandates for Steps 05, 08, 09 (per AUDIT-019).

### R2-D-008: Implementation Order Matters
- **Severity**: INFO
- **Recommendation**: Execute in this order:
  1. **shared_expectations.md expansion** (zero risk -- adds content, no removals)
  2. **Prerequisite directive in all 22 prompts** (low risk -- adds 5 LOC each)
  3. **Schema description enrichment** (low risk -- only adds to descriptions)
  4. **Remove duplicate content from prompts** (medium risk -- requires testing)
  5. **Self-Audit Gate decomposition** (medium risk -- changes prompt structure)
  6. **Remove Quick Reference sections** (low risk after steps 1-4)

---

## Appendix: LOC Estimates

| Component | Current LOC | Projected LOC | Delta |
|---|---|---|---|
| shared_expectations.md | 51 | 250 | +199 |
| 22 prompts (total) | 5,927 | 4,921 | -1,006 |
| 5 schemas (description additions) | ~0 new | ~65 words added | +65 words |
| **System total** | 5,978 | 5,171 | **-807 (-13.5%)** |
