# R2-F: Schema Description Format Analysis

**Date**: 2026-03-20
**Scope**: All 927 `description` fields across 30+ JSON Schema files
**Method**: Direct code reading of all consumers + statistical analysis of existing descriptions

---

## 1. Consumer Analysis

### 1.1 Who reads schema `description` fields?

| Consumer | Reads descriptions? | How? | What it needs |
|---|---|---|---|
| **LLMs via prompts** | Indirectly | Prompts tell LLMs to "read the schema" — LLMs see raw JSON Schema including `description` fields. Prompts also have their own field-by-field guidance that duplicates/extends schema descriptions. | Semantics, constraints, reasoning, forbidden patterns |
| **prompt_generator.py** | Yes | `_extract_required_fields()` extracts `prop_schema.get("description", "")` and passes it to migration templates as `FIELD_DESCRIPTION` | Short semantic summary |
| **prompt_schema_sync.py** | No | Compares `required`, property names, drift-sensitive fields, canonical refs. Never reads `description`. | N/A |
| **validate.py** | No | Delegates to jsonschema which uses `type`, `enum`, `pattern`, `required`, etc. Never reads `description`. | N/A |
| **spec_quality_lint.py** | No | Scans spec *data* values for placeholders, vague language. Never reads schema descriptions. | N/A |
| **canonical/lint.py** | No | Validates manifest structure. Never reads descriptions. | N/A |
| **canonical/integrity.py** | No | Walks spec files for `cn:` refs and `*_ref` fields. Never reads descriptions. | N/A |
| **SchemaRegistry (registry.py)** | No | Maps URIs to file paths, loads/resolves schemas. Never reads descriptions. | N/A |
| **schema_registry.json** | No | Static URI-to-path mapping, no descriptions anywhere. | N/A |
| **Humans** | Yes | Developers read schemas directly to understand field semantics. | Definition, constraints, examples |
| **Migration templates** | Indirectly | Templates reference field names and types but do not systematically surface descriptions. | N/A |
| **Documentation generators** | None exist | No tooling generates docs from schema descriptions. | N/A |

### 1.2 Key Finding: Two Primary Consumers

**The only consumers that actually read `description` fields are:**

1. **LLMs reading raw JSON Schema** — the primary consumer. When a prompt says "MUST read the schema before generating output", the LLM ingests the entire schema JSON, including every `description` field. This is the highest-leverage consumption path.

2. **`prompt_generator.py`** — extracts descriptions for migration prompts via `_extract_required_fields()`. This surfaces descriptions as `FIELD_DESCRIPTION` in migration template context, but the migration templates do not currently use `{{FIELD_DESCRIPTION}}` placeholders (grep found zero matches). So this consumer exists in code but is dormant.

3. **Human developers** — a secondary consumer reading schemas for understanding.

**No validator, linter, or tool reads `description` for functional purposes.** Descriptions are purely semantic/documentary.

---

## 2. Current Quality Spectrum

### 2.1 Statistical Profile

- **Total descriptions**: 927 (after filtering trivially short ones: 963 raw)
- **Mean length**: 62 characters
- **Longest**: 184 characters (step_order.schema.json `allowed_upstream_dependencies`)
- **Descriptions under 30 chars**: 46 (~5%)
- **Descriptions under 60 chars with no purpose/reason language**: 425 (~46%)

### 2.2 Quality Tiers

**Tier 1 — Gold: Informative, Contextual, Constraint-Aware**

These descriptions tell you WHAT, WHY, and HOW the field is constrained:

```
"Lowercase kebab-case identifier used as the universal ID format across all
 spec artifacts (e.g., 'fr-user-login', 'api-session-create')."
```
(136 chars — atoms.schema.json `kebabId`)

- States what it is (lowercase kebab-case identifier)
- States what it's used for (universal ID format across all spec artifacts)
- Gives examples

```
"Typed cross-reference linking one spec artifact to another for traceability.
 External traces require an owner and note."
```
(collections.schema.json `traceRef`)

- States the purpose (cross-reference for traceability)
- States a conditional constraint (external traces require owner and note)

```
"Full 40-character git commit hash pinning this reference. Must not be all zeros."
```
(16_impl_context.schema.json `commit_hash`)

- States format constraint (40-character)
- States purpose (pinning this reference)
- States forbidden pattern (must not be all zeros)

```
"Progress status for milestones: pending (not started), in_progress, done, or deferred."
```
(atoms.schema.json `milestoneStatus`)

- Lists enum values with a parenthetical clarification for non-obvious ones

**Tier 2 — Adequate: Informative but Missing WHY or Constraints**

```
"Human-readable name of the milestone."
```
(09_impl_plan.schema.json, 14_roadmap.schema.json)

- States what it is, but not why it matters or any constraints.

```
"Current progress status of the milestone."
```
- Restates field name with minimal added value. Does not list the enum values.

```
"Architecture layer this checklist item applies to."
```
- Acceptable for orientation. Does not list the 9 enum values.

**Tier 3 — Tautological: Restates the field name**

```
"The specific user story this milestone addresses."
```
(14_roadmap.schema.json `user_story`)

```
"Summary of the requirements in this theme."
```
(16_impl_context.schema.json `summary`)

```
"The command that was executed."
```
(16_impl_context.schema.json `command`)

```
"File path where the evidence was captured."
```
(16_impl_context.schema.json `path`)

These descriptions add zero information that the field name didn't already convey.

### 2.3 The "Gold Standard" Schema (Step 16) Is Not Consistently Gold

Step 16 (`16_impl_context.schema.json`) is the largest schema (600+ lines) and has the widest range of description quality within a single file:

- **Good**: `commit_hash` ("Full 40-character git commit hash... Must not be all zeros.")
- **Good**: `evidenceObject` ("Evidence proving that a requirement or check was satisfied.")
- **Good**: `linked_test_expectation` ("Test expectation(s) that validate this checklist item. Can be a single string or array of strings.")
- **Tautological**: `path` ("File path where the evidence was captured.")
- **Tautological**: `command` ("The command that was executed.")
- **Tautological**: `code` ("The example code itself.")

The quality variation within Step 16 suggests there was no systematic description standard — quality correlates with how "tricky" a field is rather than following a consistent template.

### 2.4 Cross-Schema Comparison

| Schema | Avg Description Quality | Notes |
|---|---|---|
| `core/atoms.schema.json` | High | Enum values listed inline, usage context provided. Best overall consistency. |
| `core/collections.schema.json` | High | Purpose and conditional constraints stated. |
| `04_fr_list.schema.json` | Medium | Functional but formulaic ("... for this functional requirement"). |
| `09_impl_plan.schema.json` | Medium | Adequate but many "Human-readable X of Y" patterns. |
| `14_roadmap.schema.json` | Medium-High | Better than 04/09, includes some constraint info. |
| `16_impl_context.schema.json` | Variable (Low-High) | Best peaks, worst troughs. Quality correlates with field complexity. |

---

## 3. Pattern Discovery

### 3.1 What the Best Descriptions Do

Analyzing the top quartile of descriptions, five natural patterns emerge:

**Pattern A — Definition + Purpose**
```
"<What it is> <used for/used by/that drives/enabling> <purpose>."
```
Example: "Lowercase kebab-case identifier used as the universal ID format across all spec artifacts."

**Pattern B — Definition + Enum Values**
```
"<What it is>: <value1> (<clarification>), <value2>, <value3>."
```
Example: "Progress status for milestones: pending (not started), in_progress, done, or deferred."

**Pattern C — Definition + Conditional Constraint**
```
"<What it is>. <Condition> requires/must/forbidden <constraint>."
```
Example: "Typed cross-reference... External traces require an owner and note."
Example: "Full 40-character git commit hash... Must not be all zeros."

**Pattern D — Definition + Format/Example**
```
"<What it is> (e.g., '<example>')."
```
Example: "Line range in the source file (e.g., 'L10-L25')."

**Pattern E — Inheritance/Context Note**
```
"Inherits <what> from <where>."
```
Example: "Inherits shared step-base properties ($schema, id, owner, created_at, canonical_refs_used)."

### 3.2 What the Best Descriptions DON'T Do

- They don't repeat the field name as the sole content
- They don't use markdown formatting (bold, headers, links)
- They don't span multiple paragraphs
- They don't include JSON examples within the description string
- They don't exceed ~185 characters (natural ceiling)
- They don't explain cross-field relationships (that requires prompt-level guidance)

### 3.3 Natural Length Distribution

| Length Bucket | Count | % | Character |
|---|---|---|---|
| < 30 chars | 46 | 5% | Usually tautological |
| 30-60 chars | ~380 | 41% | Minimal but functional |
| 60-100 chars | ~350 | 38% | Good sweet spot |
| 100-150 chars | ~130 | 14% | Rich, contextual |
| 150+ chars | ~20 | 2% | Max richness, approaching unwieldy |

The sweet spot is **60-120 characters**: long enough for definition + one additional signal (purpose, constraint, or enum list), short enough to not bloat schema files.

---

## 4. Prompt-to-Schema Gap Analysis

### 4.1 What Prompts Say That Schemas Don't

Reading prompts 04, 09, 14, and 16 against their schemas reveals three categories of gap:

#### Category 1: Field-Level Constraints (COULD fit in descriptions)

| Prompt | Field | Prompt Guidance | Schema Description |
|---|---|---|---|
| 04 | `statement` | "MUST use outcome-oriented phrasing; MUST NOT include implementation details (function names, DB tables)" | "Clear statement of the functional requirement, minimum 20 characters." |
| 04 | `acceptance_criteria[*].text` | "exact observable outcome; include inputs and expected outputs/state changes" | "Descriptive text of the acceptance criterion, minimum 15 characters." |
| 09 | `tech_stack` items | "Each item must have name, version, and rationale. NO generic versions like 'latest'." | "Technology stack for the implementation, including languages, frameworks, infrastructure, and tools." |
| 14 | `tasks[*].description` | "Use imperative verb form. Must be atomic and specific." | "Description of the task (must contain at least two words)." |
| 16 | `spec_ref.commit_hash` | "MANDATORY. Do not use placeholders." | "Full 40-character git commit hash pinning this reference. Must not be all zeros." (already good!) |

These are per-field forbidden patterns and phrasing requirements that fit naturally into a description string of 80-150 characters.

#### Category 2: Cross-Field Relationships (CANNOT fit in descriptions)

| Prompt | Guidance | Why it doesn't fit |
|---|---|---|
| 04 | "Every in-scope capability maps to >=1 FR" | Cross-field: relates `functional_requirements` array to external `01_capabilities.json` |
| 09 | "Do not introduce technologies not listed in capabilities unless a Spike exists" | Cross-field + cross-artifact: relates `tech_stack` to `01_capabilities.json` + `milestones[*].spikes` |
| 14 | "fr_refs MUST be non-empty if milestone has deliverables" | Cross-field within same object: relates `fr_refs` to `deliverables` |
| 16 | "Anchor MUST NOT contradict any checklist ID in active Milestone contexts" | Cross-artifact: relates this file to `spec/impl_context/*.json` |

These are inherently relational constraints spanning multiple fields or multiple files. A single `description` string cannot encode them without becoming a paragraph.

#### Category 3: Process Guidance (SHOULD NOT go in descriptions)

| Prompt | Guidance | Why it stays in prompts |
|---|---|---|
| All | "Self-Audit Gate: if score < 0.9, output clarifying questions only" | Process flow, not field semantics |
| All | "Seed Order & Mandatory Sources" | Ingestion sequence, not field definition |
| All | "Coverage Closure: verify every upstream requirement..." | Validation ritual, not field semantics |
| 09 | "Cross-Check: Verify tech_stack against capabilities" | Multi-artifact review step |

### 4.2 Gap Quantification

Across prompts 04, 09, 14, and 16:
- **Category 1 (field-level, fits in description)**: ~15-20 guidance items per prompt, of which ~5-8 are NOT already in the schema description
- **Category 2 (cross-field, doesn't fit)**: ~8-12 per prompt
- **Category 3 (process, stays in prompt)**: ~10-15 per prompt

Roughly **25-35% of prompt field-level guidance could be absorbed into schema descriptions**. The rest is inherently cross-field or procedural.

---

## 5. Format Recommendation

### 5.1 What the Evidence Supports

The evidence does NOT support a rigid template with named sub-fields (e.g., "Definition: ... | Constraint: ... | Example: ..."). The reasons:

1. **`description` is a plain string** — no structured parsing is possible
2. **No consumer parses description structure** — all consumers treat it as opaque text
3. **The best existing descriptions are natural prose** — they don't follow a template, they follow a pattern of "definition first, then whatever signal is most useful for this specific field"

The evidence DOES support a **prioritized information ordering** within a plain prose string:

### 5.2 Recommended Pattern: "Definition-first, signal-next"

```
<What this field IS>. <Most important additional signal for THIS field>.
```

The "additional signal" varies by field type:

| Field Characteristic | Additional Signal | Example |
|---|---|---|
| Has enum | List values, clarify non-obvious ones | "Progress status: pending (not started), in_progress, done, or deferred." |
| Has pattern/format | Show format + example | "ISO 8601 date-time string (e.g., '2025-10-16T22:06:04Z')." |
| Has forbidden patterns | State what's forbidden | "Clear requirement statement. Must not include implementation details (function names, DB tables)." |
| Has conditional constraints | State the condition | "Typed cross-reference for traceability. External traces require an owner and note." |
| Is a reference to another artifact | State what it references and why | "Kebab-case ID linking to an upstream capability from 01_capabilities.json." |
| Is purely structural | State purpose in the larger context | "Array of acceptance criteria that define when this requirement is satisfied." |
| Is a leaf value with obvious semantics | Keep it short, don't pad | "URL of the dashboard." (acceptable — no need to over-explain) |

### 5.3 Length Guideline

- **Target**: 60-120 characters
- **Minimum useful**: 30 characters (anything shorter is likely tautological and should be enriched)
- **Hard ceiling**: ~200 characters (beyond this, the description is trying to do too much and the information should live in prompts)
- **Exception**: Tautological descriptions for truly self-evident leaf fields (e.g., `url`, `name`) are acceptable at 20-30 characters IF the field name is unambiguous in context

### 5.4 What NOT to put in descriptions

1. **Cross-field validation rules** — these belong in prompts or in JSON Schema `if/then/else`
2. **Process instructions** ("run this command", "self-audit gate") — these belong in prompts
3. **Multi-paragraph explanations** — the string format makes these unwieldy
4. **Markdown formatting** — no consumer renders it
5. **JSON examples** — use JSON Schema `examples` array instead

---

## 6. Limitations

### 6.1 What Descriptions Cannot Carry

1. **Cross-field relationships**: "If field A is X, then field B must be Y" requires `if/then/else` in schema or prose in prompts
2. **Cross-artifact traceability rules**: "Every FR must map to a capability" is a pipeline-level constraint
3. **Ordering constraints**: "milestones must be in chronological order" is a semantic constraint beyond JSON Schema's expressiveness
4. **Style rules**: "Use imperative verb form" is a generation instruction, not a field definition
5. **Ingestion sequences**: Which upstream artifacts to read first is process, not schema

### 6.2 The Remaining Role of Prompts

Even with enriched descriptions, prompts must still carry:
- **Operating flow** (Clarify/Emit protocol)
- **Coverage closure** rules
- **Cross-field heuristics** (e.g., "MUST include migration_plan when any component has status: deprecated")
- **Best practices and common pitfalls** (contextual wisdom)
- **Negative constraints** that span multiple fields
- **Output Contract** examples

The proposal to make schemas "the single source of truth for field semantics" is achievable for **per-field semantics**. But prompts remain the authority for **inter-field, inter-artifact, and procedural semantics**.

### 6.3 Multi-Line Descriptions

The codebase uses exclusively single-line `description` strings (no `\n` characters found in any schema description). This is a de facto convention. Multi-line descriptions would work in JSON but would reduce readability of the schema files themselves and are not recommended.

---

## 7. Findings

### R2-F-001: Only Two Active Consumers Read Descriptions
**Severity**: Informational
**Evidence**: Code analysis of all tools in `specdev_tools/`. Only LLMs (via raw schema ingestion) and `prompt_generator.py` (dormant — templates don't use `{{FIELD_DESCRIPTION}}`) read descriptions. No validator, linter, or registry uses them.
**Implication**: Description format should optimize for LLM comprehension. There are no machine-parsing constraints to satisfy.

### R2-F-002: 46% of Descriptions Lack Purpose/Reasoning
**Severity**: Medium
**Evidence**: 425 of 927 descriptions under 60 chars contain no purpose/reason language (no "used for", "ensures", "prevents", etc.). These are functionally label-only.
**Implication**: Enriching these with a single purpose clause would significantly improve LLM comprehension without changing schema structure.

### R2-F-003: Enum Fields Frequently Omit Values from Description
**Severity**: Medium
**Evidence**: 26 enum fields have descriptions that do not list the allowed values. While the `enum` constraint is machine-enforced, LLMs reading descriptions miss this context when the description says only "Current status of X" without listing what the statuses are.
**Implication**: Descriptions for enum fields should list values, especially when value names are not self-explanatory.

### R2-F-004: Tautological Descriptions Exist But Are Not Pervasive
**Severity**: Low
**Evidence**: ~35 descriptions are near-tautological (restate field name). Concentrated in Step 16 leaf fields and milestone/task properties shared across Steps 09 and 14.
**Implication**: These should be enriched where the field has non-obvious semantics. For truly self-evident fields (`url`, `name` on obvious objects), brief descriptions are acceptable.

### R2-F-005: No Rigid Template Is Warranted — A Priority Ordering Suffices
**Severity**: Informational
**Evidence**: The best descriptions (atoms.schema.json, collections.schema.json) follow a natural "definition + most useful signal" pattern without a fixed structure. No consumer parses description internal structure. A rigid template would add process overhead without consumer benefit.
**Recommendation**: Adopt a "definition-first, signal-next" convention with field-type-specific guidance for what the "signal" should be (enum values, constraints, purpose, examples).

### R2-F-006: ~25-35% of Prompt Field Guidance Could Move Into Descriptions
**Severity**: Medium
**Evidence**: Comparing prompts 04/09/14/16 with their schemas, per-field forbidden patterns and phrasing constraints (e.g., "MUST use outcome-oriented phrasing", "NO generic versions like 'latest'") could fit in 80-150 character descriptions. Cross-field and procedural guidance cannot.
**Implication**: Enriching descriptions with these constraints would reduce prompt-schema drift and give LLMs field-level guidance even when prompts are not present.

### R2-F-007: The Gold Standard Is atoms.schema.json, Not Step 16
**Severity**: Informational
**Evidence**: `atoms.schema.json` has the most consistently high-quality descriptions: every enum field lists its values, every definition includes usage context, examples use `examples` array. Step 16 has the widest quality variance (best peaks, worst troughs).
**Recommendation**: Use `atoms.schema.json` as the exemplar for description style, not Step 16.

### R2-F-008: Natural Length Ceiling Is ~185 Characters
**Severity**: Informational
**Evidence**: The longest description is 184 characters. The sweet spot is 60-120 characters. Beyond ~150 characters, descriptions start trying to carry relational or procedural information that belongs elsewhere.
**Recommendation**: Target 60-120 characters. Flag descriptions over 150 for review. Do not exceed 200.

### R2-F-009: prompt_generator.py Extracts Descriptions But Templates Don't Use Them
**Severity**: Low
**Evidence**: `_extract_required_fields()` extracts `description` into `FIELD_DESCRIPTION` context variable. Migration templates in `prompts/migration/` contain zero `{{FIELD_DESCRIPTION}}` placeholders.
**Implication**: If descriptions are enriched, updating migration templates to surface `{{FIELD_DESCRIPTION}}` would complete the consumption pipeline. Currently this is dead code path.

### R2-F-010: Single-Line Convention Is Universal and Should Be Preserved
**Severity**: Informational
**Evidence**: Zero multi-line descriptions exist across 927 fields. All descriptions are single-line JSON strings.
**Recommendation**: Preserve this convention. Multi-line descriptions would reduce schema readability without consumer benefit.
