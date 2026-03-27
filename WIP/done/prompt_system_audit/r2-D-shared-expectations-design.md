# R2-D2: shared_expectations.md Design from Evidence

**Date**: 2026-03-20
**Analyst**: Claude Opus 4.6 (1M context)
**Scope**: Evidence-based redesign of shared_expectations.md from duplication analysis of all 22 prompts
**Input**: All 22 prompts (5,727 LOC), current shared_expectations.md (51 LOC), step_order.json, docs/agents/manifest.json, R2-A content classification

---

## 1. Duplication Inventory

### Method
Every section of every prompt was compared textually across all 22 prompts to identify identical, near-identical, and thematically similar blocks. The R2-A classification was used as a starting index and verified against the actual prompt content.

### 1.1 Identical Blocks (exact text, 22/22 prompts)

#### Block A: Path Variables Table (7 LOC x 22 = 154 LOC)
```
| Variable | Description |
|---|---|
| `$PRODUCT_ROOT` | Root of the consumer/product repository |
| `$TOOLKIT_ROOT` | Root of the devspec_toolkit directory |
| `$SPEC_DIR` | `$PRODUCT_ROOT/spec` — where spec artifacts live |
| `$SCHEMA_DIR` | `$TOOLKIT_ROOT/schema` — where JSON Schemas live |
```
- **Appears in**: All 22 prompts
- **Identical in**: 22/22
- **Function**: Reference/context
- **LOC impact**: 154

#### Block B: Hardening Protocol (4 LOC x 22 = 88 LOC)
```
- fail-closed preflight: verify required fields, allowed enums, referenced IDs, and command/tool existence before emitting JSON.
- No-Invention Rules: do not invent IDs, enums, commands, files, metrics, stages, or canonical mappings that are not grounded in provided inputs.
- Completeness Closure: run a final closure pass to confirm required sections, trace/canonical closure, and seed coverage are complete.
- blocker report: if required inputs are missing, conflicting, or ambiguous after clarification, stop and return a blocker report instead of speculative output.
```
- **Appears in**: All 22 prompts
- **Identical in**: 22/22
- **Function**: Protocol/constraint
- **LOC impact**: 88

#### Block C: Canonical Registry (Required Input) (5 LOC x 22 = 110 LOC)
```
Before generating output, you MUST load and search `canon/manifest.json` for existing canonical entries. Use this registry to:
1. Bind `*_ref` fields to existing canonical IDs (`cn:<namespace>:<kind>:<slug>`)
2. Resolve aliases via `canon/aliases.json`
3. Propose new entries in `canonical_proposals` when no match exists
4. Flag conflicts in `canonical_conflicts` when ambiguous matches are found
```
- **Appears in**: All 22 prompts
- **Identical in**: 21/22 (Step 12 has a slightly expanded version with deprecated-check rule)
- **Function**: Protocol/constraint
- **LOC impact**: 110

#### Block D: Canonical Binding Rules (4 LOC x 22 = 88 LOC)
```
1. `canonical_refs_used` is REQUIRED and must list every canonical ID referenced by any `*_ref` field in this artifact.
2. `canonical_proposals` is OPTIONAL. Populate it for any new term, metric, entity, role, etc. that does not exist in the registry.
3. `canonical_conflicts` is OPTIONAL. Populate it when a field value matches multiple canonical entries or contradicts an existing definition.
4. For each `*_ref` field in the schema: if the semantic content exists, the ref MUST be populated. This is not optional.
```
- **Appears in**: All 22 prompts
- **Identical in**: 22/22
- **Function**: Protocol/constraint
- **LOC impact**: 88

#### Block E: Metadata Contract (3 LOC x 22 = 66 LOC)
```
This step's output artifact MUST include every field listed in the schema's `required[]` array (see Schema Authority). Do NOT add fields not defined in the schema. Refer to the schema for the complete list of required fields, types, and structural constraints — do NOT restate them here.
```
- **Appears in**: All 22 prompts
- **Identical in**: 22/22
- **Function**: Constraint
- **LOC impact**: 66

### 1.2 Near-Identical Blocks (same structure, parameterized by step name/schema)

#### Block F: Schema Authority (6 LOC x 22 = 132 LOC)
```
The schema at `schema/NN_name.schema.json` is the authoritative source for all
field definitions, types, required vs optional markers, enum values, patterns, and minItems rules.
MUST read the schema before generating output. Do NOT guess field names, types, or valid values —
all structural constraints are defined in the schema. Do NOT output fields not defined in the schema.
```
- **Appears in**: All 22 prompts
- **Identical in**: 22/22 except schema filename varies
- **Function**: Constraint/protocol
- **LOC impact**: 132

#### Block G: Role Paragraph (2 LOC x 18 = 36 LOC)
```
You are a senior specification author and validator. Your job is to emit a single JSON artifact for **Step N · Name** that is machine-checkable and immediately consumable by CI and generators. You do not write examples, tutorials, or comments. You only output the canonical JSON that matches the schema.
```
- **Appears in**: 18 of 22 prompts (Steps 00-10, 12-15)
- **Near-identical in**: 18/18 (varies only by step name)
- **Exceptions**: Step 11 has a security-specialist role. Steps 13, 16, 16a, 16b, 16c have specialized roles.
- **Function**: Role assignment
- **LOC impact**: 36

#### Block H: Task Section (5 LOC x 18 = 90 LOC)
```
- **Input context:** previously authored spec artifacts (Charter, Capabilities, Glossary, FRs, etc.) available to you in the workspace; organizational constraints; known IDs for cross-references.
- **Objective:** produce a complete, falsifiable artifact for **Step N · Name**.
- **Output type:** one JSON document conforming to the referenced step schema.
- **Determinism:** when unspecified, choose the minimal valid value that preserves falsifiability and traceability.
- **Traceability:** if this step has `trace` or `links`, connect to at least one upstream or downstream artifact.
```
- **Appears in**: 18 of 22 prompts (Steps 00-10, 12-15)
- **Near-identical in**: 18/18 (varies only by step name; Step 02 has slightly different traceability line)
- **Function**: Task framing
- **LOC impact**: 90

#### Block I: Seed Order & Mandatory Sources (3 LOC x 12 = 36 LOC)
```
- Read `spec/common/seed_manifest.json` first; follow `global_seed_order` and `step_requirements["NN"]`.
- Ingest required seeds in order before any other context.
- If a required seed is missing or stale, stop and request it before proceeding.
```
- **Appears in**: 12 of 22 prompts (Steps 00-04, 06 through 10 is inconsistent -- actually Steps 00, 01, 02, 02a, 03, 04)
- **Near-identical in**: All that have it (varies only by step number)
- **Function**: Protocol
- **LOC impact**: 36

#### Block J: Output Rules (8 LOC x 18 = 144 LOC)
```
1. Write the final JSON artifact directly to disk at the step path under `spec/` (or runner-provided path).
2. The JSON must validate against the referenced step schema listed in `Schema Reference`.
3. All IDs must be unique kebab-case strings.
4. Use concrete verbs and measurable outcomes; avoid adjectives that are not testable.
5. Include explicit preconditions, postconditions, and error states where applicable to the schema.
6. Set `owner` to one of: `api`, `ui`, `system`, `ops`, `data`, `product`, `business`, `engineering`.
7. If the schema supports `trace` or `links`, include at least one reference to connect artifacts across steps.
8. Do not include any fields outside the schema. `additionalProperties` is false everywhere.
```
- **Appears in**: 18 of 22 prompts (Steps 00-15, with minor variations)
- **Identical in**: ~14/18 (minor wording variations in 4)
- **Exceptions**: Steps 16-16c have different output rules
- **Function**: Constraint
- **LOC impact**: 144

#### Block K: Tool Execution (3 LOC x 22 = 66 LOC base)
```
Validate the generated JSON:
```bash
./tools/run_specdev.sh validate <path_to_artifact> --repo-root ./devspec_toolkit
```
```
- **Appears in**: All 22 prompts
- **Identical base in**: 22/22
- **Variations**: Steps 06, 08, 10, 13a have additional step-specific commands
- **Function**: Reference/procedure
- **LOC impact**: 66 base + ~20 step-specific

#### Block L: Schema Reference (3 LOC x 22 = 66 LOC)
```
- Schema URI: vc:NN-name
- Schema File: schema/NN_name.schema.json
- Schema Registry: tools/schema_registry.json
```
- **Appears in**: All 22 prompts
- **Identical structure**: 22/22 (varies only by schema URI and filename)
- **Function**: Reference
- **LOC impact**: 66

#### Block M: Coverage Closure Tail (3 LOC x 22 = 66 LOC)
```
- [ ] Every upstream ID referenced in extraction intent has been consumed
- [ ] No placeholder tokens remain (TBD, TODO, FIXME, XXX)
- [ ] All required fields populated from actual upstream data (not hallucinated)
```
- **Appears in**: All 22 prompts (at the end of Coverage Closure section)
- **Identical in**: 22/22 (minor wording: some say "from ingested context" instead of "in extraction intent")
- **Function**: Constraint/checklist
- **LOC impact**: 66

#### Block N: DAG Downstream Consumers Line (1 LOC x 22 = 22 LOC)
```
Run `specdev prompt-context NN` to see downstream consumers. This prompt's output feeds N downstream steps.
```
- **Appears in**: All 22 prompts (line 3)
- **Identical structure**: 22/22 (varies by step number and count)
- **Function**: Reference (derivable from step_order.json)
- **LOC impact**: 22

### 1.3 Thematically Similar Blocks (same function, different content)

#### Block O: Self-Audit Gate Structure
- **Appears in**: All 22 prompts
- **Structure**: "If score < 0.9, output clarifying questions only -- do not emit JSON" + step-specific gating items
- **The threshold line** is identical in 20/22 prompts (Steps 11 and 16 have slight variations in positioning)
- **Gating items** are step-specific and NOT duplicated
- **Function**: Protocol (threshold) + Guidance (gating items)

#### Block P: Operating Flow Header
- **Appears in**: All 22 prompts
- **Structure**: All follow "Synthesize -> Clarify -> Emit" pattern or variant
- **Content**: Step-specific (not duplicated)
- **The "Build a private Context Ledger... Do not output it" instruction** appears in 15/22 prompts

#### Block Q: Owner Enum List
- **Appears in**: 18 of 22 prompts (in Output Rules and often repeated in Field-by-Field)
- **Identical**: `api`, `ui`, `system`, `ops`, `data`, `product`, `business`, `engineering`
- **Average repetitions per prompt**: 1.5 (some prompts list it 2-3 times)
- **Function**: Constraint (schema-duplicated -- the enum is in schema)
- **LOC impact**: ~40 total

### 1.4 Summary: Duplicated Content Inventory

| Block | Type | Prompts | Identity | Total LOC | Function |
|-------|------|---------|----------|-----------|----------|
| A: Path Variables | Identical | 22/22 | 100% | 154 | Reference |
| B: Hardening Protocol | Identical | 22/22 | 100% | 88 | Protocol |
| C: Canonical Registry | Identical | 21/22 | 95% | 110 | Protocol |
| D: Canonical Binding Rules | Identical | 22/22 | 100% | 88 | Protocol |
| E: Metadata Contract | Identical | 22/22 | 100% | 66 | Constraint |
| F: Schema Authority | Near-identical | 22/22 | ~95% | 132 | Constraint |
| G: Role Paragraph | Near-identical | 18/22 | ~90% | 36 | Role |
| H: Task Section | Near-identical | 18/22 | ~90% | 90 | Framing |
| I: Seed Order | Near-identical | 6/22 | ~95% | 36 | Protocol |
| J: Output Rules | Near-identical | 18/22 | ~85% | 144 | Constraint |
| K: Tool Execution | Near-identical | 22/22 | ~80% | 66+ | Reference |
| L: Schema Reference | Near-identical | 22/22 | ~95% | 66 | Reference |
| M: Coverage Closure Tail | Identical | 22/22 | 100% | 66 | Checklist |
| N: DAG Line | Near-identical | 22/22 | ~90% | 22 | Reference |
| O: Self-Audit threshold | Identical | 20/22 | ~90% | 22 | Protocol |
| Q: Owner Enum | Identical | 18/22 | 100% | ~40 | Schema-dup |
| **Total** | | | | **~1,226** | |

---

## 2. Classification: Universal vs Subset vs Misplaced vs Deletable

### 2.1 Universal (applies to all 22 steps) -- EXTRACT to shared_expectations.md

| Block | Current LOC | Rationale |
|-------|-------------|-----------|
| A: Path Variables | 154 | 100% identical, zero step-specific content |
| B: Hardening Protocol | 88 | 100% identical, pipeline-level concern |
| C+D: Canonical Registry + Binding Rules | 198 | 100% identical (Step 12's extra line should become the standard) |
| E: Metadata Contract | 66 | 100% identical, schema-level concern |
| F: Schema Authority | 132 | Template with schema filename param |
| M: Coverage Closure Tail | 66 | 100% identical anti-hallucination checklist |
| O: Self-Audit Gate threshold | 22 | The "score < 0.9" line is protocol, not step guidance |
| **Subtotal** | **726** | |

### 2.2 Subset-Applicable (applies to a group of steps) -- EXTRACT with applicability marker

| Block | Applies To | Current LOC | Rationale |
|-------|-----------|-------------|-----------|
| G: Role Paragraph | Steps 00-10, 12-15 (18 steps) | 36 | Default role; 4 steps override with specialized roles |
| H: Task Section | Steps 00-10, 12-15 (18 steps) | 90 | Default task framing; 4 steps override |
| I: Seed Order | Steps 00-04 (6 steps) | 36 | Only seed-phase steps need this |
| J: Output Rules | Steps 00-15 (18 steps) | 144 | Discovery phase rules; Trinity steps have different rules |

### 2.3 Misplaced (better placed elsewhere)

| Content | Current Location | Better Location | Rationale |
|---------|-----------------|-----------------|-----------|
| Owner enum list | Output Rules (18 prompts) | Schema `owner` field description | Schema is authoritative for enums |
| Field-level enum values (protocols, auth, trust boundaries, modes, categories, stages) | Field-by-Field sections (varies) | Schema field descriptions | Schema is authoritative |
| DAG downstream consumer line | Line 3 of each prompt | Generated from step_order.json at runtime | Already derivable |
| Schema Reference (URI, file, registry) | Each prompt footer | Generated from schema_registry.json | Already derivable |

### 2.4 Deletable (redundant with existing authoritative sources)

| Content | Current LOC | Already Authoritative In | Action |
|---------|-------------|--------------------------|--------|
| All enum value lists (owner, protocol, auth, trust_boundary, mode, category, stage, severity, language, scope, status, risk_status, build_status) | ~300 across all prompts | Schema field descriptions + `$defs` | DELETE from prompts |
| Required field lists in Quick Reference | ~60 across all prompts | Schema `required[]` | DELETE from prompts |
| Field type descriptions matching schema | ~140 across all prompts | Schema field descriptions | DELETE from prompts |
| N: DAG downstream consumer counts | 22 | step_order.json `downstream_consumers` | DELETE from prompts |
| L: Schema Reference blocks | 66 | schema_registry.json | DELETE (or auto-generate) |
| K: Tool Execution base command | 66 | CLI help / CLAUDE.md | EXTRACT base; keep step-specific additions |

---

## 3. Self-Audit Gate Analysis

### 3.1 What It Actually Is

The Self-Audit Gate appears in all 22 prompts. It consists of two distinct concerns:

**Concern 1: The Threshold Protocol** -- A binary gate that says "if your confidence score is below 0.9, emit clarifying questions instead of JSON."

Evidence from prompts:
- 20/22 prompts use exactly: `If score < 0.9, output clarifying questions only — do not emit JSON.`
- Step 00 prefixes with `(do not output)` in the header
- Step 11 uses a checkbox format: `- [ ] Does every threat...`
- Step 16a uses: `If score < 0.9, output clarifying questions only — do not emit JSON.` under a `(Score Threshold)` header

**Concern 2: The Gating Items** -- Step-specific criteria that the agent must check before emitting. These vary widely:

| Step | Gating Items (summary) |
|------|----------------------|
| 00 | Problem statement names users/pain/impact; in/out-scope >= 3; stakeholders with needs; user segments with JTBD; success metrics with unit+target+method |
| 01 | All charter goals map to capabilities; each has verb+scope+owner+inputs/outputs; no duplicates |
| 02 | Each capability maps to component; connections have protocol/auth; external systems identified |
| 04 | Every capability has >= 1 FR; each FR has >= 1 criterion; traces present |
| 08 | Each high-priority FR has >= 1 fixture; negative fixtures exist; inputs align with schemas |
| 11 | Every threat has target_ids; all target_ids valid; mitigations structured; edge_cases have IDs |
| 16 | All spec_ref.commit_hash valid; target_file_patterns explicit; docs_impact consistent |
| 16a | Score Threshold only |
| 16b | Score Threshold only |
| 16c | Score Threshold only |

**Concern 3: Coverage Closure** -- A separate subsection (### Coverage Closure) that appears in all 22 prompts. It has:
- Step-specific coverage rules (e.g., "Every FR acceptance criterion has >= 1 fixture")
- The universal tail checklist (Block M: upstream IDs consumed, no placeholders, no hallucinations)

### 3.2 How It Varies

| Variant | Count | Description |
|---------|-------|-------------|
| Standard (threshold + gating items + coverage closure) | 15 | Steps 00-10, 12, 13, 13a, 15 |
| Threshold only (no separate gating items) | 3 | Steps 16a, 16b, 16c (gating is embedded in FORBIDDEN ACTIONS) |
| Checkbox format | 1 | Step 11 (uses `- [ ]` checkboxes instead of bullet prose) |
| Extended (includes verdict gates) | 1 | Step 16c (adds FORBIDDEN gates to verdict) |
| Score Threshold subheader | 2 | Steps 16a, 16b (explicit `(Score Threshold)` label) |

### 3.3 Decomposition Assessment

The Self-Audit Gate naturally separates into three concerns that have different scope:

1. **Threshold Protocol** (universal): "If score < 0.9, output clarifying questions only -- do not emit JSON." This is identical in 20/22 prompts and is a pipeline protocol. It belongs in shared_expectations.md.

2. **Gating Items** (step-specific): These are the substance -- they tell the agent WHAT to check for this specific step. They are never duplicated. They MUST stay in each prompt.

3. **Coverage Closure Tail** (universal): The 3-line checklist (upstream IDs consumed, no placeholders, no hallucinations) is identical in all 22 prompts. It belongs in shared_expectations.md.

4. **Coverage Closure Body** (step-specific): The step-specific coverage rules (e.g., "Every FR has >= 1 fixture") are never duplicated. They MUST stay in each prompt.

**Recommendation**: Decompose into:
- shared_expectations.md: Threshold protocol + Coverage Closure tail checklist
- Each prompt: Gating items + Coverage Closure body (step-specific rules)

This is a clean split with zero loss of step-specific reasoning.

---

## 4. Proposed shared_expectations.md Design

The design emerges directly from the duplication analysis. Sections are ordered by dependency (foundations first, protocols second, constraints third).

### Section 1: Path Variables (from Block A)
**Content**: The path variable table (identical in 22/22 prompts)
**Extracted from**: All 22 prompts
**Applicability**: Universal
**Rationale**: Zero variation, pure reference data

### Section 2: Schema Authority Protocol (from Block F + Block E)
**Content**: Schema is authoritative for field definitions, types, enums, required markers; do not guess; do not add fields not in schema. Metadata Contract: emit all required fields, do not add undefined fields.
**Extracted from**: All 22 prompts (Block F parameterized by schema filename in each prompt's Schema Reference)
**Applicability**: Universal
**Relation to Self-Audit**: This is a pre-emit constraint, not a gating item

### Section 3: Canonical Registry Protocol (from Blocks C + D)
**Content**: The full canonical loading, binding, alias resolution, proposal, and conflict protocol. Includes Step 12's additional deprecated-check rule (which should be universal).
**Extracted from**: All 22 prompts
**Applicability**: Universal
**Rationale**: 198 LOC of identical content. The existing shared_expectations.md already has a partial version (Canonical Reuse Rules + Canonical Resolution Protocol at 12 LOC). The prompt version is more complete and should replace it.

### Section 4: Hardening Protocol (from Block B)
**Content**: fail-closed preflight, No-Invention Rules, Completeness Closure, blocker report
**Extracted from**: All 22 prompts
**Applicability**: Universal
**Relation to existing**: The existing shared_expectations.md has a similar "one-go Quality Protocol" section (6 LOC). The prompt version (4 LOC) is more precise and should replace it.

### Section 5: Default Role & Task Framing (from Blocks G + H)
**Content**: Default role paragraph and task section with `{{STEP_NAME}}` parameter
**Extracted from**: 18 of 22 prompts
**Applicability**: Subset -- Steps 00-10, 12-15 (Discovery Phase + Extensions)
**Override**: Steps 11, 13, 16, 16a, 16b, 16c define their own role/task
**Mechanism**: "Unless this prompt defines its own Role/Task section, use the default from shared_expectations.md"

### Section 6: Output Rules (from Block J)
**Content**: The 8 standard output rules (write to disk, validate against schema, kebab-case IDs, concrete verbs, preconditions/postconditions, owner enum, trace links, additionalProperties false)
**Extracted from**: 18 of 22 prompts
**Applicability**: Subset -- Steps 00-15 (Discovery Phase + Extensions)
**Override**: Steps 16-16c have different output rules

### Section 7: Seed Order Protocol (from Block I)
**Content**: Read seed_manifest.json first; follow global_seed_order and step_requirements; stop if missing
**Extracted from**: 6 prompts (Steps 00-04, inconsistently present in later steps)
**Applicability**: Subset -- steps that ingest seeds
**Note**: This should probably apply to all steps that reference seed docs, not just 00-04

### Section 8: Self-Audit Gate Protocol (from Block O threshold + Block M tail)
**Content**:
- Threshold: "If score < 0.9, output clarifying questions only -- do not emit JSON."
- Operating flow: Clarify vs Emit modes (from agents/manifest.json)
- Universal closure checklist: upstream IDs consumed; no placeholder tokens; all fields from actual data
**Extracted from**: All 22 prompts (threshold) + All 22 prompts (closure tail)
**Applicability**: Universal
**What stays in each prompt**: Step-specific gating items and step-specific coverage closure rules

### Section 9: Step-Order Policy (keep from existing)
**Content**: Forward-only execution; any change at step N requires full replay downstream
**Currently in**: shared_expectations.md (3 LOC)
**Applicability**: Universal
**Note**: Already present and correct

### Section 10: Tool Execution Base Command (from Block K)
**Content**: The base validate command template
**Extracted from**: All 22 prompts
**Applicability**: Universal
**What stays in each prompt**: Step-specific additional commands (invariants-check, fixtures-lint, governance-check)

### 4.1 Proposed Table of Contents

```
# Shared Expectations

## 1. Path Variables
## 2. Schema Authority & Metadata Contract
## 3. Canonical Registry Protocol
   ### 3.1 Loading and Binding
   ### 3.2 Canonical Binding Rules
   ### 3.3 Resolution Protocol
## 4. Hardening Protocol
## 5. Default Role & Task Framing
## 6. Output Rules (Discovery Phase)
## 7. Seed Order Protocol
## 8. Self-Audit Gate Protocol
   ### 8.1 Threshold
   ### 8.2 Universal Coverage Closure Checklist
## 9. Step-Order Policy
## 10. Tool Execution
## 11. Failure Modes (Universal)
```

### 4.2 Estimated Size

| Section | Estimated LOC | Source |
|---------|--------------|--------|
| Path Variables | 7 | Block A |
| Schema Authority + Metadata Contract | 10 | Blocks F + E merged |
| Canonical Registry Protocol | 16 | Blocks C + D + existing shared_expectations canonical content merged |
| Hardening Protocol | 5 | Block B |
| Default Role & Task Framing | 10 | Blocks G + H with parameter markers |
| Output Rules | 10 | Block J |
| Seed Order Protocol | 4 | Block I |
| Self-Audit Gate Protocol | 8 | Block O threshold + Block M tail |
| Step-Order Policy | 4 | Existing |
| Tool Execution | 4 | Block K base |
| Failure Modes | 4 | Existing |
| **Total** | **~82** | |

This is a 60% increase from the current 51 LOC but centralizes 726 LOC of universal boilerplate and 306 LOC of subset-applicable boilerplate, eliminating ~1,032 LOC from the 22 prompts.

---

## 5. Interface Contract: How Prompts Reference shared_expectations

### 5.1 Current State

Only 8 of 22 prompts reference shared_expectations.md. They do it in two different ways:

**Pattern 1 (6 prompts: 00, 01, 02, 02a, 03, 04)**:
In the "Context To Ingest" section:
```
- Guides: Shared expectations `$TOOLKIT_ROOT/docs/prompts/shared_expectations.md`, developer reference.
```
This treats it as *one of many inputs to read*, not as an authoritative parent.

**Pattern 2 (2 prompts: 16b, 16c)**:
In the "Task" section:
```
- **Guide:** `$TOOLKIT_ROOT/docs/prompts/shared_expectations.md`.
```
This treats it as a guide document.

### 5.2 Problem

Neither pattern establishes a hierarchical relationship. The prompts duplicate the content anyway. Reading a reference doc is advisory, not binding. The boilerplate is still physically present in every prompt.

### 5.3 Recommended Model

**Explicit inclusion with precedence rule**. Each prompt should:

1. Open with a reference declaration (replacing the current `Context To Ingest` guide line):
   ```
   ## Shared Expectations
   This prompt inherits all rules from `$TOOLKIT_ROOT/docs/prompts/shared_expectations.md`.
   Where this prompt defines a section that overlaps with shared_expectations (e.g., Role, Task, Output Rules),
   this prompt's version takes precedence.
   ```

2. Delete all boilerplate blocks (A through E, M) that are now centralized.

3. Keep all step-specific content.

4. For subset-applicable blocks (G, H, I, J), either:
   - Rely on the shared default (and delete the local copy), OR
   - Include a local override (e.g., Step 11's specialized role)

### 5.4 Step-Specific Residuals After Extraction

After extracting shared content, each prompt retains only:
- Purpose statement (step-specific)
- Extraction Intent (step-specific)
- Operating Flow (step-specific)
- Heuristics for Completeness (step-specific)
- Self-Audit Gate gating items (step-specific)
- Coverage Closure body (step-specific)
- Step-Specific Completeness Checklist
- Field-by-Field Guidance (step-specific, with schema-dup removed)
- Negative Constraints (step-specific)
- Best Practices (step-specific)
- Common Pitfalls (step-specific)
- Clarification Questions (step-specific)
- Output Contract example (step-specific)
- Step-specific Tool Execution additions
- Step-specific role/task overrides (if any)

---

## 6. What Does NOT Belong in shared_expectations

### 6.1 Belongs in Schemas

| Content | Why Not shared_expectations | Where It Goes |
|---------|----------------------------|---------------|
| Owner enum values | Schema is authoritative for enums | Schema `owner` field `enum` + description |
| Protocol enum values (http, grpc, etc.) | Schema is authoritative | Schema field `enum` |
| Auth method enum values | Schema is authoritative | Schema field `enum` |
| Required field lists | Schema is authoritative | Schema `required[]` |
| Field type descriptions | Schema is authoritative | Schema field `description` |
| Trace object structure | Schema is authoritative | Schema `$defs.traceRef` |
| ID pattern constraints | Schema is authoritative | Schema field `pattern` |

**Total LOC removable from prompts**: ~500 (the SCHEMA-DUP category from R2-A)

### 6.2 Belongs in step_order.json (Already There)

| Content | Why Not shared_expectations |
|---------|----------------------------|
| Downstream consumer counts | Derivable from `downstream_consumers` |
| Dependency ordering statements | Derivable from `allowed_upstream_dependencies` |

**Total LOC removable**: ~69 (the DAG-DUP category from R2-A)

### 6.3 Belongs in canon/ (Already There)

| Content | Why Not shared_expectations |
|---------|----------------------------|
| Canonical ID format examples | Already in canon/manifest.json |
| Governance label values | Already in canon/kinds/governance_label.json |

**Total LOC removable**: ~43 (the CANON-DUP category from R2-A)

### 6.4 Belongs in schema_registry.json (Already There)

| Content | Why Not shared_expectations |
|---------|----------------------------|
| Schema URI mappings | Already in tools/schema_registry.json |
| Schema file paths | Already in tools/schema_registry.json |

**Total LOC removable**: ~66 (Block L)

### 6.5 Step-Specific Content That Should NOT Be Shared

The following categories look like they could be shared but should NOT be:

| Category | Why It Must Stay Per-Prompt |
|----------|---------------------------|
| Self-Audit gating items | Each step has fundamentally different completeness criteria |
| Coverage Closure body | Each step checks different upstream artifacts |
| Extraction Intent | Each step ingests different artifacts for different purposes |
| Operating Flow | Each step has a different synthesis methodology |
| Heuristics for Completeness | Domain-specific rules per step |
| Clarification Questions | Domain-specific per step |
| Output Contract example | Step-specific JSON structure |

---

## 7. Findings

### R2-D2-001: 1,032 LOC of boilerplate is duplicated across 22 prompts and should be centralized

**Severity**: Medium
**Evidence**: Blocks A-E, M are 100% identical across all 22 prompts (726 LOC). Blocks G, H, I, J are 85-95% identical across 18 prompts (306 LOC). Total: 1,032 LOC of boilerplate that should be maintained once.
**Impact**: Maintenance burden -- any change to canonical protocol, hardening rules, or output rules requires 22 synchronized edits.
**Recommendation**: Extract to shared_expectations.md as designed in Section 4.

### R2-D2-002: Current shared_expectations.md is referenced by only 8/22 prompts and its content is redundant with inline boilerplate

**Severity**: Medium
**Evidence**: 8 prompts reference it as a "Guide" but still contain all the boilerplate inline. The 14 prompts that don't reference it have the same boilerplate. The current 51-LOC document duplicates content from the prompts rather than replacing it.
**Impact**: shared_expectations.md is effectively dead weight -- ignored in practice.
**Recommendation**: Redesign per Section 4; establish the explicit inclusion model from Section 5.3.

### R2-D2-003: The Self-Audit Gate cleanly decomposes into universal protocol + step-specific criteria

**Severity**: Low (informational)
**Evidence**: The threshold protocol ("if score < 0.9") is identical in 20/22 prompts. The gating items are unique per step. The coverage closure tail is identical in 22/22 prompts. These are three distinct concerns that can be separated without loss.
**Recommendation**: Extract threshold + closure tail to shared_expectations.md; keep gating items + closure body in each prompt.

### R2-D2-004: ~500 LOC of schema-duplicated content in prompts should migrate to schema descriptions, not to shared_expectations

**Severity**: Medium
**Evidence**: R2-A identifies 500 LOC of SCHEMA-DUP content (enum values, field types, required lists, ID patterns). This content is NOT candidates for shared_expectations -- it belongs in the schema's `description` fields. See the R2-D schema assessment (separate document) for per-field migration analysis.
**Impact**: Schema descriptions that lack the prompt's SHOULD/MUST guidance create a gap when prompts are slimmed down.
**Recommendation**: Enrich schema descriptions BEFORE removing SCHEMA-DUP content from prompts.

### R2-D2-005: 4 prompts (11, 13, 16, 16a/b/c) have specialized roles that override the default

**Severity**: Low (informational)
**Evidence**:
- Step 11: "You are a senior security architect and 'Red Team' specialist"
- Step 13: "You are a Principal Software Architect and Technical Program Manager"
- Step 16: "You are a senior software architect producing the Step 16 Trinity Anchor"
- Step 16a: "You are a senior software architect and planning assistant"
- Step 16b: "You are a senior implementation engineer"
- Step 16c: "You are a senior technical reviewer"
**Impact**: The shared default Role can be inherited by 16 prompts; 6 prompts need local overrides.
**Recommendation**: shared_expectations.md provides the default; prompts with specialized roles include a "Role" section that takes precedence.

### R2-D2-006: The Canonical Registry section in Step 12 has an expanded version that should become the universal standard

**Severity**: Low
**Evidence**: Step 12 adds: "If no match exists: add an entry to `canonical_proposals` with `temp_id`, `kind`, `proposed_label`, `definition`, and `source_field`." and "NEVER use a deprecated canonical without checking `replaced_by` first." These are stricter and more complete than the standard version.
**Impact**: 21 prompts use a less complete canonical protocol.
**Recommendation**: Adopt Step 12's expanded version as the universal standard in shared_expectations.md.

### R2-D2-007: The "Context Ledger / Do not output it" instruction is a universal protocol that appears as step-specific prose

**Severity**: Low
**Evidence**: 15 of 22 prompts contain some variant of "Build a private Context Ledger... Do not output it." The pattern varies by step (Context Ledger, Coverage Ledger, Plan Ledger, CI Ledger, Governance Ledger, Scaffold Ledger) but the protocol is always the same: synthesize privately, do not emit intermediate work.
**Impact**: This is a protocol instruction, not step-specific guidance. The step-specific part is WHAT goes in the ledger.
**Recommendation**: Add a single line to shared_expectations.md: "Before emitting output, build a private synthesis ledger of candidate content. Do not output this ledger -- it is for internal reasoning only." Keep step-specific ledger content in each prompt.

### R2-D2-008: Extraction from prompts must be preceded by schema description enrichment

**Severity**: High
**Evidence**: Many Field-by-Field guidance items in prompts contain SHOULD/MUST rules that go beyond what the schema description currently states (see R2-D schema assessment). If boilerplate is extracted and schema-dup is deleted simultaneously, the step-specific SHOULD/MUST guidance currently embedded in Field-by-Field sections would be lost.
**Recommendation**: Two-phase implementation:
1. First: Enrich schema descriptions with prompt guidance (R2-D schema assessment)
2. Then: Extract boilerplate to shared_expectations.md and delete schema-dup from prompts

### R2-D2-009: Tool Execution commands are partially shared, partially step-specific

**Severity**: Low
**Evidence**: All 22 prompts have the base `validate` command. Steps 06, 08, 10, 13a add additional commands (invariants-check, fixtures-lint, governance-check, validate-all+matrix). The base command is shared; the additions are step-specific.
**Recommendation**: shared_expectations.md includes only the base validate command. Each prompt adds step-specific commands in a local "Tool Execution" section.

### R2-D2-010: The existing shared_expectations.md contains content not present in any prompt

**Severity**: Low (informational)
**Evidence**: The current shared_expectations.md has:
- "Working Increment" section (store JSON + guide under spec/) -- 3 LOC
- "Checks" section (schema validation, cross-step traceability, quality) -- 3 LOC
- "Failure Modes" section (over-broad scope, broken references, hidden assumptions) -- 3 LOC
These are valid guidance but not referenced by prompts.
**Recommendation**: Retain the Failure Modes and Working Increment content in the redesigned document, merged into appropriate sections.

---

## Appendix A: LOC Impact Summary

### Before (current state)
- 22 prompts: 5,727 LOC
- shared_expectations.md: 51 LOC
- **Total**: 5,778 LOC

### After (proposed state)
- 22 prompts: ~3,695 LOC (5,727 - 1,032 boilerplate - 500 schema-dup + some reference lines)
- shared_expectations.md: ~82 LOC
- Schema descriptions: +~100 LOC (enriched)
- **Total**: ~3,877 LOC
- **Net reduction**: ~1,900 LOC (33%)
- **Maintenance points for shared content**: 1 (was 22)

### Per-Prompt Reduction Estimate

| Prompt Group | Current Avg LOC | Boilerplate Removed | Schema-Dup Removed | Est. After LOC |
|-------------|----------------|---------------------|--------------------|--------------:|
| Discovery (00-12) | 215 | ~64 | ~22 | ~129 |
| Extensions (13-15) | 227 | ~55 | ~33 | ~139 |
| Trinity (16-16c) | 461 | ~50 | ~20 | ~391 |

## Appendix B: Comparison with Current shared_expectations.md

| Current Section | Kept/Replaced/Expanded | In Proposed Design |
|----------------|------------------------|-------------------|
| Definition of Ready (DoR) / Guardrails (6 LOC) | Replaced | Absorbed into Section 8: Self-Audit Gate Protocol |
| Working Increment (3 LOC) | Kept | Folded into Section 6: Output Rules |
| Checks (3 LOC) | Replaced | Absorbed into Section 2: Schema Authority |
| Canonical Reuse Rules (5 LOC) | Replaced | Expanded into Section 3: Canonical Registry Protocol |
| Canonical Resolution Protocol (5 LOC) | Replaced | Expanded into Section 3: Canonical Registry Protocol |
| one-go Quality Protocol (6 LOC) | Replaced | Replaced by Section 4: Hardening Protocol |
| Step-Order Policy (3 LOC) | Kept | Section 9: Step-Order Policy |
| Failure Modes (3 LOC) | Kept | Section 11: Failure Modes |
| **New sections** | | Sections 1, 5, 7, 10 (Path Variables, Default Role, Seed Order, Tool Execution) |
