<review_prompt id="R7" layer="L1" gaps="1,2,3,4,5" runs_after="R1,R2,R3,R4,R5,R6" priority="P0-critical">
# Review R7: Deep Prompt Completeness & Determinism Audit

## Scope
**Prior reviews completed**: R1-R6. All structural fixes (hygiene, validation infra, canonical drift, traceability, generation quality, schema-prompt alignment) are in place.

This review is the **first layer** of the 4-Layer Determinism Closure. It audits ALL 22 prompts to answer one question:

> **"If an AI follows this prompt perfectly, will the resulting spec artifact be 100% complete, correct, assumption-free, hallucination-free, and semantically faithful to upstream?"**

### Gaps Closed

| # | Gap | Severity |
|---|-----|----------|
| 1 | No `## Schema Authority` directive in any prompt — AI has no instruction to read the schema before generating output; structural constraints (types, enums, required markers, patterns, minItems) are undefined or duplicated in prompt text | CRITICAL |
| 2 | 3 prompts (12, 13, 10) produce schema-failing output | CRITICAL |
| 3 | No sourcing instructions for free-text fields — AI can fabricate content | CRITICAL |
| 4 | `## Metadata Contract` missing from all 22 prompts — Output Contract tests skip all real prompts (tests search for `## B4 Metadata Contract` which no prompt has) | CRITICAL |
| 5 | 5 cross-cutting boilerplate issues affect 17+ prompts | HIGH |

### Why R7 Runs First

Prompts are the **source of truth** for what an AI should produce. Schemas (R8) enforce prompt requirements. Validators (R9) catch what schemas can't. If we fix schemas or validators first, then change prompts, everything downstream needs rework. R7 finalizes core prompt hardening. After R7, the only permitted prompt modifications are narrow **bidirectional coherence adjustments** in R8 (e.g., aligning a prompt's Field-by-Field section when a schema reveals structural constraints the prompt didn't account for).

---

## Files Under Review

| Category | Files |
|----------|-------|
| All prompts | `prompts/prompt_00_*.md` through `prompts/prompt_16c_*.md` (22 files) |
| Step schemas (reference) | `schema/00_charter.schema.json` through `schema/16_impl_context.schema.json` (19 step schemas). **NOTE**: Steps 16a, 16b, 16c share `schema/16_impl_context.schema.json` via schema_registry.json — there are no separate schema files for these steps. |
| Test files (B4→Metadata Contract rename) | `tests/test_prompt_contracts.py` (6 occurrences), `tests/test_prompt_schema_sync.py` (8 occurrences), `tests/test_cli.py` (1 occurrence) — 3 files, 15 total occurrences |
| Step order metadata | `tools/step_order.json` |

---

## 6 Evaluation Dimensions (per prompt)

Every prompt is audited against these 6 dimensions:

| # | Dimension | Question | Pass Criteria |
|---|-----------|----------|---------------|
| 1 | **Completeness** | Does the prompt have a `## Schema Authority` directive AND sourcing instructions for all fields requiring upstream derivation? | (a) Prompt has a dedicated `## Schema Authority` section naming the schema file; (b) all fields whose values must be derived from upstream artifacts have explicit sourcing instructions |
| 2 | **No Schema Duplication** | Does the prompt avoid repeating schema constraints? | Prompt contains no field type annotations, enum value lists, pattern strings, minItems values, or sub-field definitions — all structural constraints are delegated to the schema via the Schema Authority directive |
| 3 | **Assumption Prevention** | Does the prompt tell the AI where to source EVERY piece of information? | Every output field traces to a specific upstream artifact + field path |
| 4 | **Hallucination Prevention** | Does the prompt bind every output field to a specific upstream artifact or seed? | Every free-text field has a sourcing instruction, not just ID fields |
| 5 | **Semantic Capture** | Does the prompt ensure meaning flows from upstream? | Instructions say "extract the intent and rationale from [field] in [artifact]", not just "copy the ID" |
| 6 | **Determinism** | Given identical inputs, would two different AIs produce structurally identical output? | Fields with subjective interpretation identified and constrained |

---

## Subagent Protocol (MANDATORY)

### Main Agent Rules
- **FORBIDDEN in main agent**: Read, Edit, Write, Grep, Glob, Bash for file content
- **All investigation MUST be delegated to subagents — no exceptions** (~44 files)
- Main agent: receive summaries, synthesize findings table, create task list, final report
- Token budget: < 5K tokens total for main agent across all phases

### Subagent Assignment

#### Phase 1 — Investigation (3 Explore subagents, launch together)

**Subagent A** (`Explore`, no isolation) — Prompts 00-08 Field Coverage Audit:
```
For EACH prompt in steps 00-08, perform the 4-point audit:

1. Read the corresponding prompt file (prompts/prompt_NN_*.md)
2. Read the corresponding schema file (schema/NN_*.schema.json) for reference only
3. Audit the prompt on four points:
   a. Does the prompt have a `## Schema Authority` section naming the schema file and stating it is authoritative? (SCHEMA DELEGATION)
   b. Does the prompt avoid duplicating schema constraints — no field type annotations, no enum value lists, no pattern strings, no sub-field structure definitions? (NO DUPLICATION)
   c. For fields whose values must be derived from upstream artifacts (free-text content, IDs generated from upstream data, references), does the prompt specify WHERE to source the value — specific upstream artifact + field path? (ASSUMPTION PREVENTION)
   d. Does the prompt contain vague language allowing subjective interpretation? Flag: "consider", "if appropriate", "as needed", "may include", "such as", "etc", "prefer", "should" (in binding context) (DETERMINISM)

Prompts to audit:
- prompts/prompt_00_project_charter.md + schema/00_charter.schema.json
- prompts/prompt_01_capabilities.md + schema/01_capabilities.schema.json
- prompts/prompt_02_system_sketch.md + schema/02_system_sketch.schema.json
- prompts/prompt_02a_delivery_baseline.md + schema/02a_delivery_baseline.schema.json
- prompts/prompt_03_glossary.md + schema/03_glossary.schema.json
- prompts/prompt_04_functional_requirements.md + schema/04_fr_list.schema.json
- prompts/prompt_05_interface_contracts.md + schema/05_interface_contracts.schema.json
- prompts/prompt_06_invariants.md + schema/06_invariants.schema.json
- prompts/prompt_07_nfrs.md + schema/07_nfrs.schema.json
- prompts/prompt_08_fixtures.md + schema/08_fixtures.schema.json

Produce a table per prompt:
Schema Authority section present: Y/N

| Field (needs sourcing) | Sourcing Instruction? | Vague Language? |
|------------------------|----------------------|-----------------|
(Only fields requiring upstream derivation need a row — not every schema field.)

Summary: Schema Authority directive present (Y/N); fields missing sourcing instructions (count); vague phrase occurrences (count); schema constraint duplication instances (count, list offending text).
```

**Subagent B** (`Explore`, no isolation) — Prompts 09-16c Field Coverage Audit:
```
Same 4-point audit as Subagent A, for steps 09-16c.

Prompts to audit:
- prompts/prompt_09_impl_plan.md + schema/09_impl_plan.schema.json
- prompts/prompt_10_governance.md + schema/10_governance.schema.json
- prompts/prompt_11_redteam.md + schema/11_redteam.schema.json
- prompts/prompt_12_ci_gates.md + schema/12_ci_gates.schema.json
- prompts/prompt_13_extension_generator.md + schema/13_extension_generator.schema.json
- prompts/prompt_13a_completeness_assessment.md + schema/13a_completeness_assessment.schema.json
- prompts/prompt_14_roadmap.md + schema/14_roadmap.schema.json
- prompts/prompt_15_scaffold.md + schema/15_scaffold.schema.json
- prompts/prompt_16_impl_context.md + schema/16_impl_context.schema.json
- prompts/prompt_16a_impl_planner.md + schema/16_impl_context.schema.json (shared schema — 16a/16b/16c all use this file via schema_registry.json)
- prompts/prompt_16b_impl_coder.md + schema/16_impl_context.schema.json (shared schema)
- prompts/prompt_16c_impl_reviewer.md + schema/16_impl_context.schema.json (shared schema)

NOTE: Steps 16a, 16b, 16c do NOT have separate schema files. The schema_registry.json maps
all three to schema/16_impl_context.schema.json. When auditing field coverage, compare each
prompt against the SAME schema but note which sections/definitions within it apply to each step.
This is a known design constraint — if different steps need different required fields, R8 may
need to split this schema or add conditional validation.

KNOWN CRITICAL ISSUES to verify:
- prompt_12: `environment_ref` missing from prompt but required by schema
- prompt_13: `governance_label_ref` missing from prompt but required by schema
- prompt_10: treats `pr_rules`/`versioning` as optional ("should") but schema requires them

Produce same table format as Subagent A.

NOTE: prompts 14, 16a, and 16c were partially updated by R4. Mark R4-already-fixed items as RESOLVED.
```

**Subagent C** (`Explore`, no isolation) — Cross-Cutting Systemic Audit:
```
Audit cross-cutting patterns across ALL 22 prompts. This is NOT per-field — it's structural.

1. METADATA CONTRACT SECTION:
   - For each of the 22 prompt files, search for `## Metadata Contract` (exact header)
   - Also search for `## B4 Metadata Contract` (legacy header name from R1-era test stubs)
   - Report: how many prompts have NEITHER section? (Expected: all 22 lack it)
   - Check test files that parse prompts using "B4 Metadata Contract" as delimiter:
     a. tests/test_prompt_contracts.py (6 occurrences of "B4 Metadata Contract") — what header does it search for?
     b. tests/test_prompt_schema_sync.py (8 occurrences) — what header does it search for?
     c. tests/test_cli.py (1 occurrence) — what header does it search for?
   - NOTE: tests/test_prompt_output_contract.py and tests/test_prompt_completeness.py do NOT exist.
     R1 findings (docs/audit/findings/r1_plan.md) documented "B4 Metadata Contract" as out of scope.

2. SELF-AUDIT GATE:
   - For each prompt, does it have a Self-Audit Gate section?
   - Does the gate list criteria that map 1:1 to schema required[] fields?
   - Or are criteria vague ("all fields populated", "structure is valid")?

3. CLARIFY→EMIT PROTOCOL:
   - For each prompt, is the Two-Phase protocol present?
   - Does it specify the 0.9 score threshold?
   - Is the format correct (Clarify first, then Emit)?

4. UPSTREAM REFERENCE CONSISTENCY:
   - For each prompt, does it reference upstream artifacts by exact filename?
   - Or does it use vague references ("the charter", "previous specs")?

5. BOILERPLATE ISSUES (check all 22 prompts):
   a. Generic Task Preamble — does it contain "You can work on any step" or similar
      contradiction with strict waterfall ordering? Count occurrences.
   b. "X downstream steps" placeholder — find prompts with unfilled placeholders.
   c. Canonical Registry instruction position — is it BEFORE or AFTER Output Contract?
   d. "Best Practices" sections — find prompts with soft-modality language.
   e. Template variables ({{VAR}}) — are any unreplaced?

Report: per-issue count, affected files, severity assessment.
```

#### Phase 2 — Implementation (after Phase 1)

Execute implementation subagents sequentially. Each subagent runs its own tests.

**P0 — Metadata Contract Fix (prerequisite for all other prompt work)**

**Subagent D** (`general-purpose`, isolation: `worktree`) — Rename B4 Metadata Contract in tests:
```
In test files, rename ALL occurrences of "B4 Metadata Contract" → "Metadata Contract".

Files and exact occurrence counts (verified via grep):
- tests/test_prompt_contracts.py — 6 occurrences (lines 20, 22, 60, 62, 158, 172)
  These are string delimiters used to split prompt file content: text.split("## B4 Metadata Contract")
- tests/test_prompt_schema_sync.py — 8 occurrences (lines 251, 286, 328, 373, 411, 445, 487, 527)
  These are in test fixture strings: "## B4 Metadata Contract\n"
- tests/test_cli.py — 1 occurrence (line 142)
  Test fixture string: "## B4 Metadata Contract\n"

Total: 3 files, 15 occurrences. Replace ALL with "Metadata Contract" (drop the "B4 " prefix).
Also search for "B4_Metadata" or "b4_metadata" variants (none expected, but verify).

IMPORTANT: docs/audit/findings/r1_plan.md (line 210) explicitly says "DO NOT rename" these.
That instruction was for R1 scope only — R7 IS the review that performs this rename.

After changes: run pytest tests/test_prompt_contracts.py tests/test_prompt_schema_sync.py tests/test_cli.py -v
Expected: tests should still pass (they currently skip all real prompts because no prompt
has the "## B4 Metadata Contract" header, so renaming to "## Metadata Contract" changes
WHICH header tests look for — the real fix comes in Subagent E which adds the section).
```

**Subagent E** (`general-purpose`, isolation: `worktree`) — Add Metadata Contract to ALL prompts:
```
For each of the 22 prompt files (prompts/prompt_00_*.md through prompts/prompt_16c_*.md):
1. Check if `## Metadata Contract` section already exists
2. If missing, add it BEFORE the `## Output Contract` section (or at end if no Output Contract)

The Metadata Contract section must contain:
- $schema URI for this step
- spec_version field requirement
- generation_quality fields (if applicable to this step)
- Any step-specific metadata fields from the schema

Template:
```markdown
## Metadata Contract

Every artifact produced by this step MUST include:
- `"$schema"`: `"<URI from schema registry for this step>"`
- `"spec_version"`: current specdev version string
- `"generation_quality"`: object with `confidence_score` (0.0-1.0), `coverage_assessment`, `known_gaps[]`, `recommendations[]`
```

Adapt per step based on what the schema actually requires for metadata fields.
Read the schema for each step to get the correct $schema URI and metadata fields.

After changes: run pytest tests/test_prompt_contracts.py -v to verify Metadata Contract detection.
```

**P0 — Per-Prompt Field Coverage (based on Phase 1 findings)**

**Subagent F** (`general-purpose`, isolation: `worktree`) — Prompts 00-08 field coverage fixes:
```
Based on Phase 1 Subagent A findings, for each prompt in steps 00-08 with missing field guidance:

1. Add `## Schema Authority` section to each prompt (first section after the prompt header, before any other section):
   ## Schema Authority
   The schema at `$SCHEMA_DIR/<step_schema>.schema.json` is the authoritative source for all
   field definitions, types, required vs optional markers, enum values, patterns, and minItems rules.
   MUST read the schema before generating output. Do NOT guess field names, types, or valid values —
   all structural constraints are defined in the schema. Do NOT output fields not defined in the schema.

2. For fields whose values must be derived from upstream artifacts (free-text content, IDs, refs):
   - Add sourcing instruction: specific upstream artifact filename + field path
   - For free-text: `DO NOT fabricate — derive from [upstream artifact] → [field path]`
   - Do NOT add field type annotations, enum value lists, or structural constraints — the schema covers those

3. Remove any existing schema constraint duplication found in Phase 1:
   - Field type annotations ("string, enum: X|Y|Z")
   - Explicit pattern strings ("^[A-Z0-9]{2,}$")
   - Sub-field definitions ("required sub-fields: source_url, source_date...")
   - minItems restatements

Rules:
- Additions are ADDITIVE — do not remove correct sourcing/workflow content
- Never add schema constraint details to the prompt
- Replace vague phrases:
  "consider X" → "MUST include X if [specific condition]"
  "may include" → "MUST include"
  "if appropriate" → "if [specific condition from upstream artifact]"
  "such as" / "e.g." → specify the upstream artifact to read for valid options (do NOT list schema enum values)
  "etc" → remove or reference upstream artifact

After changes: run pytest tests/ -k prompt -v
```

**Subagent G** (`general-purpose`, isolation: `worktree`) — Prompts 09-16c field coverage fixes:
```
Same as Subagent F, but for steps 09-16c.

Based on Phase 1 Subagent B findings, for each prompt in steps 09-16c with missing field guidance:

KNOWN CRITICAL FIXES:
- prompt_12: Add explicit `environment_ref` field instructions with sourcing from 02a_delivery_baseline.json
- prompt_10: Change "should include pr_rules" → "MUST include pr_rules" (schema requires it)
- prompt_10: Change "should include versioning" → "MUST include versioning" (schema requires it)

NOTE: `governance_label_ref` in prompt_13 is RESOLVED in current prompt text — do NOT re-add.

Same rules as Subagent F: additive only, source every free-text field, replace vague language. Add `## Schema Authority` section to each prompt. Remove any schema constraint duplication (field type annotations, enum value lists, pattern strings, sub-field structures).

NOTE: prompts 14, 16a, 16c were updated by R4 — read current state first, preserve R4 changes.

After changes: run pytest tests/ -k prompt -v
```

**P1 — Cross-Cutting Boilerplate Fixes**

**Subagent H** (`general-purpose`, isolation: `worktree`) — Cross-cutting boilerplate fixes:
```
Based on Phase 1 Subagent C findings, fix cross-cutting issues in ALL 22 prompts:

1. GENERIC TASK PREAMBLE: If a prompt contains language contradicting strict waterfall ordering
   (e.g., "You can work on any step"), replace with step-specific context:
   "This is Step NN in a strict forward-only waterfall. It depends on [list upstream steps]."

2. UNFILLED PLACEHOLDERS: Replace "X downstream steps" with actual step names from
   tools/step_order.json → step_metadata → downstream_consumers.

3. CANONICAL REGISTRY POSITION: If Canonical Registry instructions appear AFTER Output Contract,
   move them BEFORE Output Contract (AI needs to know the registry before producing output).

4. BEST PRACTICES: Replace soft-modality "Best Practices" sections with mandatory rules:
   "Best practice: X" → "MUST: X"
   "Consider doing X" → "MUST do X when [condition]"

5. SELF-AUDIT GATE: Harden criteria to map 1:1 to schema required[] fields.
   Generic "all fields populated" → explicit checklist of each required field by name.

After changes: run pytest tests/ -k prompt -v
```

**P1 — Test Updates**

**Subagent I** (`general-purpose`, isolation: `worktree`) — Update test expectations:
```
After all prompt changes, update test files to match new prompt structure:

1. tests/test_prompt_contracts.py — verify it uses `## Metadata Contract` header (from Subagent D)
2. tests/test_prompt_schema_sync.py — verify it uses `## Metadata Contract` header
3. Any other test files that parse prompt structure — update expectations

Run: pytest tests/ -v
All tests must pass. If any test fails due to R7 prompt changes, fix the test to match
the new prompt structure (R7 prompts are authoritative).
```

#### Phase 3 — Integration Test Run

**Subagent J** (`general-purpose`, no isolation) — Full integration verification:
```
Run the complete validation suite to confirm R7 changes don't break anything:

1. pytest tests/ -v
2. ./tools/run_specdev.sh validate-all spec --repo-root ./devspec_toolkit
3. ./tools/run_specdev.sh spec-quality-lint spec --repo-root ./devspec_toolkit
4. ./tools/run_specdev.sh hallucination-lint spec --repo-root ./devspec_toolkit

All must pass. Report any failures with exact error messages.
```

#### Phase 4 — Self-Verification

**Subagent K** (`Explore`, no isolation) — Verify R7 goals met:
```
After all implementation is complete, verify measurable goals:

1. Search all 22 prompts for `## Schema Authority`. Count: target 22/22.
   Also verify 0 instances of schema constraint duplication (enum value lists, type annotations,
   regex patterns, sub-field structures, minItems restatements) in prompt text.

2. Search all 22 prompts for `## Metadata Contract`. Count: target 22/22.

3. Search all 22 prompts for vague phrases: "consider", "if appropriate", "as needed",
   "may include", "such as", "etc". Count: target 0.

4. For each prompt, count free-text fields without explicit sourcing instructions.
   Target: 0 across all prompts.

5. Verify prompts 10 and 12 no longer produce schema-failing output:
   - prompt_10: pr_rules and versioning are MUST (not should); review_policy has sourcing note
   - prompt_12: environment_ref has explicit instructions with sourcing
   - prompt_13: governance_label_ref RESOLVED (already present in current prompt — confirm still present)

Report: per-goal pass/fail with counts.
```

#### Phase 5 — Findings Report

**Subagent L** (`general-purpose`, no isolation) — Write findings:
```
Write findings to docs/audit/findings/r7_findings.md using compact table format from review_protocol.md.

Include:
- Part A: Findings table (all issues found in Phase 1, with severity and resolution status)
- Part B: Implementation summary (tasks executed, files changed)
- Part C: Measurable goals verification (from Phase 4)
- Part D: Residual issues (anything that couldn't be resolved, with rationale)

Also update docs/audit/review_index.md to add R7 entry.
```

---

## Key Design Decisions

- Every prompt MUST have a `## Schema Authority` section directing the LLM to read the schema for all structural constraints. Prompts provide sourcing guidance and workflow constraints — NOT schema field definitions, types, enums, or patterns.
- Every free-text field MUST have an explicit **sourcing instruction** with upstream artifact + field path
- Self-Audit Gate score criteria MUST be mechanically derivable from schema `required[]`
- Prompt updates are **additive** — no removal of correct content, only replace vague with precise
- `## Metadata Contract` replaces legacy `## B4 Metadata Contract` in all test files (3 files, 15 occurrences) and is added to all 22 prompts
- R7 prompts are **authoritative** — tests adapt to prompts, not the other way around

---

## Measurable Goals

| Metric | Before R7 | After R7 |
|--------|-----------|----------|
| Prompts with ## Schema Authority directive | 0/22 | **22/22** |
| Schema constraint duplication instances | unknown | **0** |
| Prompts missing Metadata Contract section | 22/22 | **0/22** |
| Vague language occurrences | ~120 total | **0** |
| Free-text fields without sourcing instructions | unknown | **0** |
| CRITICAL prompts that produce schema-failing output | 3 | **0** |

---

## Anti-Patterns

- Do NOT remove correct prompt content — only replace vague with precise
- Do NOT add schema field definitions, types, enum values, patterns, minItems, or sub-field structures to prompts — the schema is the authoritative source for all structural constraints
- Do NOT add fields not in schema — prompt must match schema exactly
- Do NOT use NLP/semantic matching — sourcing instructions must be structural (artifact + field path)
- Do NOT modify schemas in R7 — that's R8
- Do NOT modify validators in R7 — that's R9

---

## Dependencies

| Direction | Review | Relationship |
|-----------|--------|-------------|
| Requires | R1-R6 | All structural fixes must be in place |
| Blocks | R8 | Schemas tighten to match R7-hardened prompts |
| Blocks | R9 | Validators build against R7 prompts + R8 schemas |
</review_prompt>
