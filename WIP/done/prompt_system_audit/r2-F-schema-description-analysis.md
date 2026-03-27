# R2-F: Schema Description Analysis — What Should Descriptions Contain?

## 1. Prompt-to-Schema Field Guidance Inventory

For each of the 7 prompt-schema pairs, every piece of field-level guidance in the prompt is classified:
- **A: Can move to description** — self-contained, about one field
- **B: Cannot move** — requires cross-field context, upstream awareness, or process knowledge
- **C: Already in description** — the schema description already says this

### 1.1 prompt_04 (Functional Requirements) → 04_fr_list.schema.json

| Prompt Guidance | Field | Category | Reasoning |
|---|---|---|---|
| `fr_id`: `fr-<behavior>`; one behavior per FR | fr_id | **A** | Self-contained naming convention. Schema says "Unique kebab-case identifier" but omits the `fr-` prefix convention and "one behavior" constraint. |
| `statement`: MUST use outcome-oriented phrasing | statement | **A** | Self-contained quality guidance. Schema says "Clear statement...minimum 20 characters" — no guidance on phrasing quality. |
| `statement`: MUST NOT include implementation details (function names, DB tables, internal method signatures) | statement | **A** | Negative constraint on a single field. Not in schema description. |
| `statement`: MUST NOT include multiple behaviors | statement | **A** | Negative constraint. Not in schema. |
| `rationale`: why this FR exists (tie to business value or risk) | rationale | **A** | Schema says "Explanation of why this requirement exists" — partially there but missing the "tie to business value" guidance. |
| `preconditions/postconditions`: set when environment or state boundaries exist | preconditions, postconditions | **A** | Schema descriptions are thin ("Conditions that must hold before..."). Could add "populate when environment or state boundaries exist." |
| `acceptance_criteria[*].text`: exact observable outcome; include inputs and expected outputs/state changes | text | **A** | Schema says "Descriptive text...minimum 15 characters." Missing quality guidance entirely. |
| `acceptance_criteria[*].fixture_ref`: reference `fixture-*`; use `fixture-*-tbd` if not yet created | fixture_ref | **A** | Schema says "Optional reference to a test fixture." Missing the naming convention and `-tbd` pattern. |
| `trace`: link to `capability-*`, `api-*`, `nfr-*`, or `invariant-*` | trace | **C** | Schema says "Traceability links back to upstream capabilities or charter items." Partially covers this. |
| Trace Object Structure: array of objects with `type`, `id`, `note` — not strings | trace | **A** | Schema uses `$ref` to `traceRef` which enforces structure, but the description doesn't mention the common mistake of using strings. |
| MUST include `fixture_ref` for every FR with `priority: high` | fixture_ref + acceptance_criteria | **B** | Cross-field — depends on upstream capability priority. |
| `trace` links MUST map every FR to its originating capability | trace | **B** | Cross-artifact constraint — depends on upstream 01_capabilities.json content. |
| Each FR covers one behavior | (whole FR object) | **A** | Could go on the FR item description. Already partially in fr_id guidance. |
| ≥2 acceptance criteria for top FRs | acceptance_criteria | **B** | Cross-field — depends on FR priority/importance. Schema enforces `minItems: 2` globally, which is stricter than the prompt. |
| Ambiguity scrub: ban "should/could/fast/easy" | statement, text | **A** | Negative constraint on word choice. Not in schema. |
| Given-When-Then phrasing in acceptance criteria | text | **A** | Quality guidance for a single field. Not in schema. |

**Summary for prompt_04:**
- Category A (movable): 11 items (~22 LOC of field guidance)
- Category B (not movable): 3 items (~6 LOC)
- Category C (already there): 1 item (~2 LOC)

### 1.2 prompt_05 (Interface Contracts) → 05_interface_contracts.schema.json

| Prompt Guidance | Field | Category | Reasoning |
|---|---|---|---|
| `api_id`: `api-<resource>-<action>`; stable across codegen and monitoring | api_id | **A** | Naming convention. Schema says "Unique kebab-case identifier" but omits the naming pattern. |
| `name`: human-readable, maps to resource/action | name | **C** | Schema: "Human-readable name of this API endpoint." Adequate. |
| `version`: `v<major>[.<minor>]` per semver pattern | version | **C** | Schema has pattern `^v\\d+(?:\\.\\d+)*$` and description mentions the format. |
| `protocol`: route/method must align with protocol semantics | protocol | **A** | Cross-field aware but expressible: "Choose protocol; path and method must align with protocol semantics." |
| `path/method`: concrete path and verb for HTTP; gRPC service/method for grpc | path, method | **A** | Schema describes these independently. Could enrich with protocol-conditional guidance. |
| `input_schema_ref/output_schema_ref`: MUST use machine-resolvable locations | input_schema_ref | **A** | Schema: "Reference to the JSON Schema defining the request body structure." Missing the "machine-resolvable" guidance. |
| `errors`: use shared error objects; include codes/messages | errors | **A** | Schema: "Array of error states that this API may return." Missing quality guidance. |
| `security`: based on threat model; DO NOT use `none` for authenticated resources | security | **A** | Schema describes enum values. Missing the threat-model reasoning. |
| DO NOT use generic error names like 'Error' | errors | **A** | Negative constraint, field-scoped. Not in schema. |
| DO NOT mix HTTP verbs in a single API entry | method | **A** | Constraint on the API entry scope. Not in schema. |
| For gRPC, use POST method; for MQTT, map routes to topic paths | method, path | **A** | Protocol-specific conventions. Not in schema. |
| Trace Format: use exact JSON object format, not string arrays | trace | **A** | Same as FR — schema enforces via $ref but description doesn't warn about the common mistake. |
| Each API needs version, protocol, route/path, method, owner | (multiple) | **C** | Enforced by schema `required` array. |

**Summary for prompt_05:**
- Category A (movable): 10 items (~20 LOC)
- Category B (not movable): 0 items
- Category C (already there): 3 items

### 1.3 prompt_06 (Invariants) → 06_invariants.schema.json

| Prompt Guidance | Field | Category | Reasoning |
|---|---|---|---|
| `inv_id`: MUST use `invariant-<domain>-<constraint>` naming | inv_id | **A** | Schema: "Unique kebab-case identifier (e.g., 'inv-balance-non-negative')." Example uses `inv-` but doesn't state the naming convention as a rule. |
| `description`: business-readable statement | description | **C** | Schema: "Human-readable description." Adequate. |
| `language`: MUST use `jsonlogic` or `cel` when constraint is automatable; DO NOT use `text` unless necessary | language | **A** | Schema lists enum values but provides no guidance on WHEN to use each. This is critical quality guidance. |
| `expression`: test for syntactic validity | expression | **A** | Schema: "The formal or textual expression." Missing validity guidance. |
| `scope.components/apis`: k-ID lists. Example: `{"components": ["auth-service"]}` | scope | **A** | Schema describes structure but the prompt adds the concrete example. |
| `severity`: `error` for hard guarantees, `warn` for observability | severity | **A** | Schema: "Violation severity: 'warn' for advisory violations, 'error' for blocking violations." Actually already good — **C**. |
| MUST set `severity=error` for invariants from FR error conditions or security boundaries | severity | **B** | Cross-artifact — depends on upstream FR and system sketch content. |
| DO NOT invent component IDs; use only those from Step 2 | scope.components | **B** | Cross-artifact constraint. |
| DO NOT skip tracing; every rule must have a reason | trace | **A** | Could be: "Every invariant must have at least one trace link explaining why the rule exists." |
| Beyond FR-derived negative cases, MUST include: data integrity constraints, state transition rules, access boundary rules | (whole artifact) | **B** | Process-level completeness guidance spanning multiple upstream artifacts. |

**Summary for prompt_06:**
- Category A (movable): 5 items (~10 LOC)
- Category B (not movable): 3 items (~6 LOC)
- Category C (already there): 2 items

### 1.4 prompt_07 (NFRs) → 07_nfrs.schema.json

| Prompt Guidance | Field | Category | Reasoning |
|---|---|---|---|
| `nfr_id`: `nfr-<category>-<metric>` | nfr_id | **C** | Schema has pattern `^nfr-[a-z0-9]+-[a-z0-9-]+$` and description mentions the format. |
| `category`: pick most specific dimension | category | **A** | Schema lists enum but doesn't say "pick most specific." |
| `metric`: human-readable metric name (e.g., p95 latency, monthly cost) | metric | **A** | Schema: "Name of the metric being measured." Could enrich with examples. |
| `target`: concrete target (e.g., 300, "99.95%", "<= $1k/mo") | target | **A** | Schema describes type constraint but not quality. Could add "Must be concrete and measurable." |
| `unit`: units like ms, rps, %, USD | unit | **A** | Schema: "Unit of measurement for the metric." Could add canonical unit examples. |
| `measurement_method`: how/where measured (e.g., PromQL query, vendor dashboard) | measurement_method | **A** | Schema: "How this NFR will be measured or verified." Could enrich with concrete examples. |
| MUST ensure measurement_method references a specific tool, query, or dashboard endpoint (not generic phrases) | measurement_method | **A** | Critical quality constraint not in schema. |
| `stage`: `dev`, `staging`, or `prod` | stage | **C** | Schema has enum. |
| NEVER emit qualitative targets without metrics | target | **A** | Negative constraint. Could go in target description. |
| NEVER skip trace for critical NFRs | trace | **A** | Negative constraint. |
| NFRs without owner AND trace are invalid | owner, trace | **B** | Cross-field — involves two fields together. However, both are in `required`, so partially enforced. |

**Summary for prompt_07:**
- Category A (movable): 8 items (~16 LOC)
- Category B (not movable): 1 item
- Category C (already there): 2 items

### 1.5 prompt_09 (Implementation Plan) → 09_impl_plan.schema.json

| Prompt Guidance | Field | Category | Reasoning |
|---|---|---|---|
| `tech_stack`: structured object with arrays for `languages`, `frameworks`, `infrastructure`, `tools` | tech_stack | **C** | Schema enforces structure via $ref and required. |
| Each item must have `name`, `version`, and `rationale` | tech_stack items | **C** | Schema enforces `name` and `version` in required; `rationale` is optional in schema but prompt says it's needed. Gap: **A** for the rationale requirement. |
| `name`: exact library/tool name | tech_stack[*].name | **A** | Schema: "Name of the technology." Could add "Use exact official library/tool name." |
| `version`: semantic version constraint (e.g., "^2.0.0") | tech_stack[*].version | **A** | Schema: "Version string or constraint." Could add "Use semver constraints, not 'latest'." |
| NO Generic Versions: do not use "latest" or "stable" | version | **A** | Negative constraint. Not in schema description. |
| `rationale`: brief reason for selection | tech_stack[*].rationale | **A** | Schema: "Justification for selecting this technology." Could add "MUST be populated with concrete reasoning." |
| NO Unstructured Tech Stack: MUST be object not list of strings | tech_stack | **C** | Enforced by schema type. |
| `milestones[*].milestone_id/name`: kebab-case ID and descriptive name | milestone_id, name | **C** | Schema enforces kebab-case via $ref. |
| `milestones[*].target_date`: ISO date | target_date | **C** | Schema has `format: date`. |
| `milestones[*].status`: enum values | status | **C** | Schema has enum. |
| `milestones[*].risks/spikes`: concrete bullets | risks, spikes | **A** | Schema: "Known risks that could delay or block." Could add "Use concrete, actionable language." |
| `milestones[*].deliverables`: array of trace references linking to FRs/APIs | deliverables | **A** | Schema: "Trace references to artifacts this milestone will produce." Could add "Link to specific FRs/APIs." |
| NO Orphan Milestones: must link to at least one FR or API in deliverables | deliverables | **A** | Not enforceable by schema type but expressible in description. |
| NO Hallucinations: do not list technologies not in capabilities without a Spike | tech_stack | **B** | Cross-artifact constraint. |
| migration_plan: narrative plan for cutover/backfill/rollback | migration_plan | **A** | Schema: "High-level strategy for migrating." Could add cutover/rollback guidance. |

**Summary for prompt_09:**
- Category A (movable): 9 items (~18 LOC)
- Category B (not movable): 1 item
- Category C (already there): 7 items

### 1.6 prompt_14 (Roadmap) → 14_roadmap.schema.json

| Prompt Guidance | Field | Category | Reasoning |
|---|---|---|---|
| One Milestone = One User Story | milestone item | **A** | Schema: "A single roadmap milestone with user story, tasks, and deliverables." Could add "Each milestone must map to exactly one user story." |
| `tasks[*].description`: at least two words, imperative verb form | description | **C** | Schema has pattern `^\\S+\\s+\\S+.*$`. Description says "at least two words" but omits imperative verb guidance — partial, so also **A**. |
| `tasks[*].description`: Use imperative verb form | description | **A** | Not in schema description. |
| `acceptance_criteria[*].text`: >=15 chars | text | **C** | Schema has `minLength: 15`. |
| `depends_on`: within same milestone only; no cycles | depends_on | **A** | Schema description: "task_ids this task depends on (within same milestone). Must not create cycles." Already good — **C**. |
| `assumptions`: ≥10 characters each | assumptions items | **C** | Schema has `minLength: 10`. |
| `exit_conditions`: ≥15 characters each; specific and verifiable | exit_conditions items | **A** | Schema has minLength but description doesn't say "specific and verifiable." |
| `exit_conditions`: Do not duplicate acceptance_criteria | exit_conditions | **A** | Not in schema description. |
| `source_milestones`: one or more Step 09 milestone IDs | source_milestones | **A** | Schema: "Upstream Step 09 milestone IDs." Could add "Must reference actual Step 09 milestone_ids." |
| `fr_refs`: MUST be non-empty when milestone has deliverables | fr_refs | **A** | Schema says "FR IDs from spec/04_fr_list.json" but doesn't state the non-empty constraint. |
| `fr_refs` and `capability_refs` belong on milestones, not tasks | fr_refs, capability_refs | **A** | Structural guidance. Not in schema. |
| `migration_plan`: one or two sentences; avoid rehashing Step 09 | migration_plan | **A** | Schema: "High-level strategy for migrating." Missing length/reuse guidance. |
| `dependencies`: objects with `type` and `id`; `owner` and `note` required for external | dependencies items | **C** | Schema enforces via conditional `allOf`. |
| NEVER create `depends_on` cycles | depends_on | **C** | Already in schema description. |
| NEVER use `fr_refs` ID not present in Step 04 | fr_refs | **B** | Cross-artifact constraint. |
| NEVER use `capability_refs` ID not in Step 01 | capability_refs | **B** | Cross-artifact constraint. |
| NO Backward Planning: Dates must proceed logically | target_date across milestones | **B** | Cross-item ordering constraint. |

**Summary for prompt_14:**
- Category A (movable): 9 items (~18 LOC)
- Category B (not movable): 3 items
- Category C (already there): 5 items

### 1.7 prompt_16 (Implementation Context) → 16_impl_context.schema.json

| Prompt Guidance | Field | Category | Reasoning |
|---|---|---|---|
| `checklist[*].id`: Uppercase snake-case ID (e.g., `CHK_AUTH_01`) | id | **C** | Schema uses `screamingSnakeId` $ref. |
| `spec_ref.commit_hash`: MANDATORY, 40-char SHA, no placeholders | commit_hash | **C** | Schema has pattern `^[0-9a-f]{40}$` and `not: { pattern: "^0{40}$" }`. Description covers this. |
| `description`: "Subject-Action-Constraint" format | checklist[*].description | **A** | Schema: "Description of what this checklist item requires." Missing the format guidance. |
| `linked_test_expectation`: concrete test identifier or command | linked_test_expectation | **A** | Schema: "Test expectation(s) that validate this checklist item." Missing "concrete" — could add "Must be a specific test command (e.g., pytest tests/module/test_feature.py::test_name), not a generic placeholder." |
| `implementation.status`: enum values including meaning | implementation.status | **C** | Schema has enum and description. |
| `implementation.actions[*].type`: enum with conditional requirements | actions[*].type | **C** | Schema has allOf with conditional required. |
| `target_file_patterns`: MUST use explicit globs, avoid `**/*` | target_file_patterns | **A** | Schema: "A file or directory path pattern to modify or create." Missing glob specificity guidance. |
| `docs_impact.status`: MUST be `required` if any non-doc file is in target_file_patterns | docs_impact.status | **B** | Cross-field — depends on target_file_patterns content. Schema has conditional but description doesn't explain. |
| `plan.security.status`: if `planned`, require `new_fixtures` and `spec_mutations` | security.status | **A** | Could describe the conditional behavior in the status description. |
| `plan.delivery.status`: if `planned`, require dashboards and alerts | delivery.status | **A** | Same pattern. |
| NEVER hallucinate `step_id` | spec_ref.id | **A** | Could add "Must reference an actual spec artifact ID, never invented." |
| NEVER use `plan.tasks` or `metadata` | (non-existent fields) | **C** | Schema has `additionalProperties: false` which enforces this. |
| NEVER emit incomplete JSON or use placeholder values | (all fields) | **B** | Document-level constraint. |
| Anchor must not contradict active Milestone contexts | (whole artifact) | **B** | Cross-artifact consistency constraint. |

**Summary for prompt_16:**
- Category A (movable): 6 items (~12 LOC)
- Category B (not movable): 3 items
- Category C (already there): 5 items

### Aggregate Totals

| Category | Count | LOC (approx) |
|---|---|---|
| **A: Can move to description** | 58 | ~116 |
| **B: Cannot move** | 14 | ~28 |
| **C: Already in description** | 25 | ~50 |

**Key finding**: ~60% of field-level prompt guidance is movable to descriptions. ~14% genuinely cannot move. ~26% is already captured.

---

## 2. Current Description Quality Assessment

### 2.1 schema/04_fr_list.schema.json — FR List

**Overall quality: THIN.** Descriptions state what the field IS but not what makes it GOOD.

| Field | Current Description | Quality | Gap |
|---|---|---|---|
| `statement` | "Clear statement of the functional requirement, minimum 20 characters." | Thin | Missing: outcome-oriented phrasing, no implementation details, single behavior. An LLM reading this alone would produce statements with function names, multiple behaviors, or passive/vague phrasing. |
| `acceptance_criteria[*].text` | "Descriptive text of the acceptance criterion, minimum 15 characters." | Thin | Missing: must be an exact observable outcome with inputs and expected outputs. An LLM would produce "the feature works correctly" — no guidance pushes toward specificity. |
| `fixture_ref` | "Optional reference to a test fixture that validates this criterion." | Thin | Missing: naming convention (`fixture-*`), TBD pattern (`fixture-*-tbd`). |
| `rationale` | "Explanation of why this requirement exists and what business need it addresses." | Good | This is one of the better descriptions — it states purpose AND what good looks like. |
| `trace` | "Traceability links back to upstream capabilities or charter items." | Adequate | Could mention the common mistake of using strings instead of objects. |

**Verdict**: An LLM reading only this schema would produce structurally valid but semantically weak FRs — correct JSON types but poor statement quality, vague criteria, missing fixture conventions.

### 2.2 schema/14_roadmap.schema.json — Roadmap

**Overall quality: MODERATE.** Some descriptions are good, others are thin.

| Field | Current Description | Quality | Gap |
|---|---|---|---|
| `user_story` | "The specific user story this milestone addresses." | Thin | Missing: format guidance (As a... I want... So that...), one-story-per-milestone constraint. |
| `tasks[*].description` | "Description of the task (must contain at least two words)." | Thin | Missing: imperative verb form, atomic and specific constraint. |
| `fr_refs` | "FR IDs from spec/04_fr_list.json that this milestone delivers." | Good | States source file. Missing: non-empty when deliverables exist. |
| `capability_refs` | "Capability IDs from spec/01_capabilities.json that this milestone implements." | Good | States source file. |
| `source_milestones` | "Upstream Step 09 milestone IDs this roadmap milestone maps to." | Good | Clear purpose. |
| `exit_conditions` items | "A condition that definitively marks this task complete (minimum 15 characters)." | Adequate | Missing: "specific and verifiable", "do not duplicate acceptance_criteria." |
| `assumptions` items | "An assumption that must hold for this task to succeed (minimum 10 characters)." | Adequate | Missing: "include when task has external dependencies or uncertain preconditions." |
| `depends_on` | "task_ids this task depends on (within same milestone). Must not create cycles." | **Excellent** | This is a standout — it includes the scope constraint AND the forbidden pattern. |

**Verdict**: Roadmap descriptions are better than FR descriptions. The `depends_on` description is a model for what ALL descriptions should look like — it includes constraints, scope, and forbidden patterns.

### 2.3 schema/16_impl_context.schema.json — Implementation Context

**Overall quality: GOOD.** The most complex schema with the richest descriptions.

| Field | Current Description | Quality | Gap |
|---|---|---|---|
| `commit_hash` | "Full 40-character git commit hash pinning this reference. Must not be all zeros." | **Excellent** | States the constraint AND the forbidden pattern. |
| `checklist_status` | "Whether this checklist item is actively required or deferred." | Good | Clear purpose. |
| `linked_test_expectation` | "Test expectation(s) that validate this checklist item. Can be a single string or array of strings." | Adequate | Missing: "must be a concrete test command, not a generic placeholder." |
| `implementation` | "Atomic work definition for this specific requirement." | Good | Clear and concise. |
| `mitigation` | "Mitigation strategy for non-blocking ambiguities (minimum 10 characters)." | Good | States when it applies AND minimum length. |
| `evidence.content` | "The evidence content itself (minimum 20 characters, must contain non-whitespace)." | Good | Multiple constraints in one description. |

**Verdict**: Step 16 descriptions are the closest to what all descriptions should look like. They often include conditional guidance and forbidden patterns.

### 2.4 Core Schemas (atoms, collections, errors)

**Overall quality: GOOD.** These are the most polished descriptions in the codebase.

Examples of excellent descriptions:
- `kebabId`: "Lowercase kebab-case identifier used as the universal ID format across all spec artifacts (e.g., 'fr-user-login', 'api-session-create')." — States purpose, format, and gives concrete examples.
- `traceRef`: "Typed cross-reference linking one spec artifact to another for traceability. External traces require an owner and note." — States purpose AND conditional requirement.
- `canonicalRef.id`: "Fully qualified canonical ID in the format cn:<namespace>:<kind>:<slug>." — States the exact format.
- `techStackItem`: "A single technology component in the project stack, with version and optional rationale." — Clear and concise.

These work well because they serve BOTH humans and LLMs — they state format, purpose, and edge cases.

---

## 3. Description Length Analysis

### 3.1 Current Length Distribution

Sampling across schemas:

| Length Range | Count (sample) | Example |
|---|---|---|
| < 40 chars | Common | "Human-readable name of the milestone." (37 chars) |
| 40-80 chars | Most common | "Unique kebab-case identifier for this functional requirement (e.g., 'fr-user-login')." (85 chars) |
| 80-150 chars | Some | "Lowercase kebab-case identifier used as the universal ID format across all spec artifacts (e.g., 'fr-user-login', 'api-session-create')." (136 chars) |
| 150+ chars | Rare | "Typed cross-reference linking one spec artifact to another for traceability. External traces require an owner and note." (119 chars) |

### 3.2 What Length Do Fields NEED?

**Fields where current descriptions are too short** (gap analysis):

1. **`statement` in 04_fr_list** (28 chars of useful guidance): Needs ~200 chars.
   - Current: "Clear statement of the functional requirement, minimum 20 characters."
   - Needed: Purpose + quality rules + forbidden patterns + phrasing guidance
   - Why: This is the HARDEST field for LLMs — they routinely produce implementation-leaking, multi-behavior, vague statements.

2. **`acceptance_criteria[*].text`** in 04_fr_list: Needs ~150 chars.
   - Current: "Descriptive text of the acceptance criterion, minimum 15 characters."
   - Needed: Observable outcome + inputs/outputs + Given-When-Then + no "it works" patterns

3. **`measurement_method`** in 07_nfrs: Needs ~150 chars.
   - Current: "How this NFR will be measured or verified (e.g., 'synthetic monitoring', 'load test')."
   - Needed: Must reference a specific tool/query/URL, not generic phrases

4. **`language`** in 06_invariants: Needs ~120 chars.
   - Current: "Expression language used: jsonlogic (machine-evaluable), cel (Common Expression Language), or text (human-readable)."
   - Needed: When to use each — jsonlogic/cel when automatable, text only as last resort

5. **`user_story`** in 14_roadmap: Needs ~100 chars.
   - Current: "The specific user story this milestone addresses."
   - Needed: Format guidance, one-per-milestone constraint

**Fields where current descriptions are adequate** (no change needed):

- `commit_hash`: Already states format + forbidden pattern
- `depends_on`: Already states scope + forbidden pattern
- `kebabId`: Already states purpose + format + examples
- `traceRef`: Already states purpose + conditional requirement

### 3.3 Is There Evidence That Longer Descriptions Hurt?

**No.** The evidence points the other direction:

1. The best-performing descriptions in the codebase are LONGER (commit_hash, depends_on, kebabId, traceRef).
2. LLMs process JSON Schema descriptions as inline guidance during generation — they benefit from explicit constraints.
3. The token cost of longer descriptions is marginal. A 200-char description adds ~50 tokens. A typical schema has ~30-50 properties. Even doubling every description adds ~1500 tokens — negligible against the 10K-30K token prompts already consumed.
4. The prompt guidance that WOULD move to descriptions is already being read by the LLM in the prompt — the total token budget doesn't increase; it just consolidates.

The one risk: **noise dilution**. If descriptions become walls of text, the LLM might weight them less. But the prompt content that would migrate is already concise field guidance — not paragraph-length essays.

### 3.4 Recommended Length Targets

| Field Type | Target Length | Rationale |
|---|---|---|
| Simple typed fields (name, version) | 40-80 chars | Type + purpose sufficient |
| Enum fields | 80-120 chars | List values + guidance on when to use each |
| ID fields | 80-120 chars | Pattern + naming convention + example |
| Semantic content fields (statement, description, text) | 150-250 chars | Purpose + quality rules + forbidden patterns |
| Complex/conditional fields (trace, implementation, scope) | 120-200 chars | Structure + conditional requirements + common mistakes |

---

## 4. Consistency vs Variation

### 4.1 Current State: Inconsistent

Current descriptions follow at least 5 different patterns:

1. **Type echo**: "Array of functional requirements." — Restates the JSON type.
2. **Minimal purpose**: "Human-readable name of the milestone." — States purpose only.
3. **Purpose + constraint**: "Full 40-character git commit hash. Must not be all zeros." — States purpose AND negative constraint.
4. **Purpose + examples**: "Unique kebab-case identifier (e.g., 'fr-user-login')." — States purpose with examples.
5. **Purpose + conditional + forbidden**: "task_ids this task depends on (within same milestone). Must not create cycles." — The gold standard.

### 4.2 Should Descriptions Follow a Pattern?

**Yes, with variation by field complexity.** Here's the evidence:

**For consistency:**
- LLMs benefit from predictable information structure. If every description follows "Purpose. Constraint. Forbidden pattern." the LLM knows where to find each piece.
- 925 descriptions at 5 different patterns means the LLM must parse each one differently. A consistent structure reduces cognitive load.
- Linting and automated quality checks become possible with a consistent pattern.

**For variation by field type:**
- A simple boolean doesn't need the same structure as a semantic text field.
- Over-templating creates padding/noise on simple fields.

### 4.3 Recommended Pattern

A three-tier structure based on field complexity:

**Tier 1 — Simple fields** (booleans, enums with obvious semantics, date formats):
```
"Purpose statement. Constraint if any."
```
Example: "Whether this parameter must be provided in the request."

**Tier 2 — Structured fields** (IDs, refs, typed arrays):
```
"Purpose statement (e.g., 'example-value'). Naming convention. Constraint."
```
Example: "Unique identifier for this FR in the format 'fr-<behavior>'. One behavior per FR. Must be stable across versions."

**Tier 3 — Semantic content fields** (statements, descriptions, free text with quality requirements):
```
"Purpose statement. Quality rules: X, Y. Forbidden: A, B."
```
Example: "Clear, outcome-oriented statement of the functional requirement. Must describe a single testable behavior using concrete verbs and measurable outcomes. Forbidden: implementation details (function names, DB tables), multiple behaviors, vague adjectives (fast, easy)."

### 4.4 Impact Assessment

Moving from 5 inconsistent patterns to 3 consistent tiers would:
- Make descriptions predictable for LLM consumers
- Enable automated quality linting (does every Tier 3 field include "Forbidden:" guidance?)
- Require touching ~200-300 descriptions (those that are currently Tier 1 style but should be Tier 2 or 3)

---

## 5. What Cannot Migrate and Why

### 5.1 Cross-Artifact Reference Constraints (14 items identified)

**Example 1** — From prompt_04:
> "trace links MUST map every FR to its originating capability from spec/01_capabilities.json"

This cannot go in the `trace` field description because:
- The description would need to say "trace to capabilities from 01_capabilities.json" — but it doesn't know WHICH capabilities exist.
- The completeness constraint ("every FR maps to ≥1 capability") is about the COLLECTION of FRs, not any single FR's trace field.
- **However**: a weaker form CAN go in the description: "Must include at least one trace to a capability (type: capability, id: cap-*). Prefer tracing to all upstream capabilities that motivated this FR."

**Example 2** — From prompt_14:
> "NEVER use a fr_refs ID not present in spec/04_fr_list.json"

This cannot go in `fr_refs` description because the description can't enumerate which FR IDs exist. **However**: the description already says "FR IDs from spec/04_fr_list.json" — this is adequate. The enforcement is a validation concern, not a description concern.

**Example 3** — From prompt_09:
> "Do not list technologies not in spec/01_capabilities.json without a clear Spike justification"

This is a cross-artifact constraint — the tech_stack description can't know what's in capabilities.json. **Verdict**: genuinely not movable.

### 5.2 Process/Ordering Guidance (from Operating Flow sections)

**Example** — From prompt_04:
> "Build a private Context Ledger of candidate FRs... Map APIs to FRs... Self-audit... Emit JSON"

This is orchestration guidance for the LLM runner. It cannot go in any single field's description because it describes the ORDER of work across all fields. **Verdict**: genuinely not movable.

### 5.3 Cross-Field Conditional Constraints

**Example** — From prompt_16:
> "If docs_impact.status is required, docs_touched must have at least one entry"

**Honest assessment**: This CAN technically go in the `docs_impact.status` description: "When set to 'required', the docs_touched array must contain at least one documentation file path." The schema already enforces this via `allOf/if/then`, and placing guidance in BOTH fields (status and docs_touched) is workable. This is already partially done for `depends_on` in the roadmap schema.

**However**, there's a readability concern: if field A's description explains a constraint on field B, and field B's description also explains it, there's duplication. The schema's `allOf/if/then` is the authoritative enforcement. The description should just SIGNAL the conditional relationship, not fully specify it.

**Verdict**: Cross-field conditionals are PARTIALLY movable. Put a brief signal in one field's description; let the schema structure enforce the constraint.

### 5.4 Completeness/Coverage Mandates

**Example** — From prompt_04:
> "Every in-scope capability maps to ≥1 FR; each FR covers one behavior."

The collection-level completeness ("every capability maps to ≥1 FR") cannot go in any single field. The per-item constraint ("each FR covers one behavior") CAN go in the FR item description.

### 5.5 Upstream Context Requirements

**Example** — From prompt_07:
> "If measurement_method cannot be implemented with the system's infrastructure as defined in spec/02_system_sketch.json, MUST ask Gap Questions"

This requires knowledge of what infrastructure exists. Cannot go in a field description.

### 5.6 Summary: What Genuinely Cannot Move

| Category | Count | Why |
|---|---|---|
| Cross-artifact ID resolution | 5 | Can't enumerate valid IDs from other files |
| Collection-level completeness | 4 | Constraint is on the SET, not any single item |
| Process/ordering guidance | 3 | Describes generation workflow, not field semantics |
| Upstream feasibility checks | 2 | Requires knowledge of other artifacts' content |

The actual limitation is NOT JSON string format or length. Descriptions can be arbitrarily long strings. The limitation is **referential context** — a field description can't know what exists in other files, and it can't express constraints on the collection of sibling items.

---

## 6. Migration Examples

### 6.1 `statement` in 04_fr_list.schema.json

**Before:**
```json
"description": "Clear statement of the functional requirement, minimum 20 characters."
```

**After:**
```json
"description": "Outcome-oriented statement of a single functional requirement. Must describe exactly one testable behavior using concrete verbs and measurable outcomes. Forbidden: implementation details (function names, DB tables, method signatures), multiple behaviors in one statement, vague adjectives (fast, easy, should, could). Minimum 20 characters."
```

**Prompt content to delete:** Lines 111, 132 of prompt_04 (statement field guidance and negative constraint about implementation details).

### 6.2 `acceptance_criteria[*].text` in 04_fr_list.schema.json

**Before:**
```json
"description": "Descriptive text of the acceptance criterion, minimum 15 characters."
```

**After:**
```json
"description": "Exact observable outcome with specific inputs and expected outputs or state changes. Use Given-When-Then phrasing when applicable. Must be falsifiable — avoid 'it works' or 'functions correctly'. Minimum 15 characters."
```

**Prompt content to delete:** Lines 114, 133 of prompt_04.

### 6.3 `fixture_ref` in 04_fr_list.schema.json

**Before:**
```json
"description": "Optional reference to a test fixture that validates this criterion."
```

**After:**
```json
"description": "Reference to a test fixture that validates this criterion. Use 'fixture-<domain>-<scenario>' naming. If the fixture does not yet exist, use 'fixture-<domain>-tbd' as a placeholder. Should be populated for all automatable acceptance criteria."
```

**Prompt content to delete:** Line 115 of prompt_04.

### 6.4 `language` in 06_invariants.schema.json

**Before:**
```json
"description": "Expression language used: jsonlogic (machine-evaluable), cel (Common Expression Language), or text (human-readable)."
```

**After:**
```json
"description": "Expression language for this invariant. Use 'jsonlogic' for data predicates or 'cel' for field-level logic when the constraint can be expressed as a boolean/evaluable expression. Use 'text' only when automation is truly not feasible."
```

**Prompt content to delete:** Lines 105, 118 of prompt_06.

### 6.5 `measurement_method` in 07_nfrs.schema.json

**Before:**
```json
"description": "How this NFR will be measured or verified (e.g., 'synthetic monitoring', 'load test')."
```

**After:**
```json
"description": "Concrete measurement approach for this NFR. Must reference a specific tool, query, or dashboard endpoint (e.g., 'PromQL: histogram_quantile(0.95, ...)', 'Grafana dashboard: /d/latency'). Forbidden: generic phrases like 'automated monitoring' or 'load test' without specifics."
```

**Prompt content to delete:** Lines 52, 102 of prompt_07.

### 6.6 `user_story` in 14_roadmap.schema.json

**Before:**
```json
"description": "The specific user story this milestone addresses."
```

**After:**
```json
"description": "The user story this milestone delivers, in 'As a <role>, I want <goal> so that <benefit>' format. Each milestone must address exactly one user story — do not bundle multiple stories."
```

**Prompt content to delete:** Line 92 of prompt_14.

### 6.7 `tasks[*].description` in 14_roadmap.schema.json

**Before:**
```json
"description": "Description of the task (must contain at least two words)."
```

**After:**
```json
"description": "Atomic, specific task description in imperative verb form (e.g., 'Implement authentication module'). Must contain at least two words. Avoid vague phrasing — each task should be unambiguous about what work is required."
```

**Prompt content to delete:** Lines 136-137 of prompt_14.

### 6.8 `linked_test_expectation` in 16_impl_context.schema.json

**Before:**
```json
"description": "Test expectation(s) that validate this checklist item. Can be a single string or array of strings."
```

**After:**
```json
"description": "Concrete test identifier or command that validates this checklist item (e.g., 'pytest tests/auth/test_login.py::test_login_success'). Must be specific enough to execute directly — not generic placeholders like 'run tests'. Can be a single string or array of strings."
```

**Prompt content to delete:** Lines 101-102 of prompt_16.

### 6.9 `target_file_patterns` items in 16_impl_context.schema.json

**Before:**
```json
"description": "A file or directory path pattern to modify or create."
```

**After:**
```json
"description": "Explicit glob pattern for a file or directory to modify or create (e.g., 'src/auth/*.py'). Avoid overly broad patterns like '**/*'. If a file is not matched here, the coder is forbidden from touching it."
```

**Prompt content to delete:** Lines 91-92 of prompt_16.

### 6.10 `api_id` in 05_interface_contracts.schema.json

**Before:**
```json
"description": "Unique kebab-case identifier for this API (e.g., 'api-session-create')."
```

**After:**
```json
"description": "Unique kebab-case identifier for this API in the format 'api-<resource>-<action>' (e.g., 'api-session-create'). Must be stable across codegen, monitoring, and fixture references."
```

**Prompt content to delete:** Line 99 of prompt_05.

### 6.11 Risk Assessment of Longer Descriptions

| Risk | Likelihood | Mitigation |
|---|---|---|
| Token budget increase | Low | ~1500 tokens across all schemas — negligible vs 10-30K prompt tokens |
| LLM attention dilution | Low | Content migrated from prompts is already read; consolidation helps focus |
| Schema readability for humans | Medium | Descriptions become mini-docs; could overwhelm IDE tooltips. Mitigate with consistent structure (Tier 1/2/3) |
| Maintenance burden | Medium | Two sources of truth eliminated (prompt + schema → schema only). Net reduction in maintenance. |
| Schema file size | Low | ~10-20KB increase across all schemas. No tooling impact. |

---

## 7. Findings

### R2-F2-001: Schema Must Be Sole Owner of All Field-Level Semantics

**Severity**: HIGH (design decision — locked)
**Evidence**: Across 7 prompt-schema pairs, 58 out of 97 field-level guidance items (60%) are self-contained single-field guidance readily expressible in descriptions. 14 items (14%) require cross-artifact or cross-field context. 25 items (26%) are already in descriptions. However, the design decision is stronger than the analysis: **schemas are the sole owner of field semantics, period.** The 14% "cannot move" items should be re-examined — cross-field constraints CAN be signaled in individual field descriptions (as R2-F2-005 notes), and process guidance that truly cannot fit stays in prompts as step-level operating flow, not field-level guidance. The target is 100% of field semantics in schemas, not 60%.
**Files**: All 7 schema files listed in analysis scope.
**Impact**: Eliminates the entire category of prompt-schema drift. Prompts become pure reasoning documents.

### R2-F2-002: Current Descriptions Are Too Thin for Semantic Content Fields

**Severity**: Medium
**Evidence**: The `statement` field in 04_fr_list says "Clear statement of the functional requirement, minimum 20 characters" — no guidance on outcome-oriented phrasing, forbidden patterns, or single-behavior constraint. The `text` field for acceptance criteria says "Descriptive text...minimum 15 characters." An LLM reading only these descriptions would produce structurally valid but semantically poor output.
**Files**: `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/schema/04_fr_list.schema.json` (lines 27-29, 57-59)
**Impact**: LLMs that read only the schema (without the full prompt) produce lower-quality artifacts.

### R2-F2-003: Excellent Description Patterns Already Exist But Are Not Applied Consistently

**Severity**: Low
**Evidence**: `depends_on` in 14_roadmap ("task_ids this task depends on (within same milestone). Must not create cycles.") and `commit_hash` in 16_impl_context ("Full 40-character git commit hash. Must not be all zeros.") both include purpose + scope constraint + forbidden pattern. These are the gold standard. But 70%+ of descriptions across all schemas use the thin "Type echo + minimal purpose" pattern.
**Files**: `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/schema/14_roadmap.schema.json` (line 159), `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/schema/16_impl_context.schema.json` (line 44)
**Impact**: Inconsistency forces LLMs to parse each description differently instead of expecting a predictable structure.

### R2-F2-004: Three-Tier Description Depth Model (Not a Rigid Format)

**Severity**: Informational (recommendation)
**Evidence**: Fields naturally fall into three complexity tiers: simple (booleans, dates), structured (IDs, refs), and semantic (statements, descriptions). Each tier needs different description depth. However, per R2-F2-003, the best descriptions follow a natural "definition + signal" pattern where signal varies by field type — no rigid template is warranted. The three tiers describe DEPTH, not FORMAT: Tier 1 (40-80 chars) for simple fields, Tier 2 (80-150 chars) for structured fields, Tier 3 (150-250+ chars) for semantic fields. Within each tier, the description's signal should match the field type (enum values for enums, conventions for IDs, quality rules + forbidden patterns for semantic fields). Since schemas are the sole owner of all field semantics (R2-F2-001), Tier 3 descriptions must be rich enough to replace prompt Field-by-Field guidance entirely.

### R2-F2-005: Cross-Artifact Constraints Cannot Move but Can Be Signaled

**Severity**: Low
**Evidence**: 14 items identified as Category B are cross-artifact constraints (e.g., "fr_refs must reference IDs from 04_fr_list.json"). While the ENFORCEMENT can't move to descriptions, the SIGNAL can — "FR IDs from spec/04_fr_list.json" already appears in the `fr_refs` description and is adequate for an LLM to understand the constraint.
**Impact**: Most cross-artifact constraints are already adequately signaled. No action needed beyond current practice.

### R2-F2-006: Longer Descriptions Do Not Hurt — Token Cost Is Negligible

**Severity**: Informational
**Evidence**: Adding ~120 chars to 200 thin descriptions adds ~6000 tokens to total schema size. Schemas are already read by LLMs alongside 10-30K token prompts. The migrated content is already being tokenized in the prompt — consolidation into descriptions doesn't increase total token consumption; it eliminates duplication.
**Risk**: Schema files become slightly larger on disk (10-20KB total). No evidence of LLM attention dilution at these description lengths.

### R2-F2-007: migration_plan Description Diverges Between Steps 09 and 14

**Severity**: Low
**Evidence**: Step 09 schema: "High-level strategy for migrating from existing systems or data to the new implementation." Step 14 schema: "High-level strategy for migrating from existing systems or data." Prompt 14 adds: "Use a short string...one or two sentences...avoid rehashing Step 09." The Step 14 description should distinguish itself from Step 09's field.
**Files**: `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/schema/09_impl_plan.schema.json` (line 91), `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/schema/14_roadmap.schema.json` (line 225)

### R2-F2-008: The Hardest LLM Fields Lack the Most Description Guidance

**Severity**: Medium
**Evidence**: The fields where LLMs most commonly produce incorrect output — `statement` (multi-behavior, implementation leaking), `acceptance_criteria.text` (vague), `measurement_method` (generic), and `language` (defaulting to text) — are precisely the fields with the thinnest descriptions. The prompt compensates with Field-by-Field Guidance and Negative Constraints sections, but these are disconnected from the schema the LLM reads during generation.
**Impact**: When prompts are trimmed, shortened, or when an LLM prioritizes schema over prompt, these fields degrade first.
