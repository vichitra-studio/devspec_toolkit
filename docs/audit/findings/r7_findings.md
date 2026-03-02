# Review R7 Findings — Prompt Completeness & Determinism Audit
Generated: 2026-03-02
Status: VERIFIED (Phase 1 investigation verified; 2 false positives corrected; downstream counts corrected to `downstream_consumers`; seed ingestion authority corrected to `seed_manifest.json`; Gap #3 deferred to R8; Gap #9 verified non-issue)

## Part A: Findings

| ID | Sev | File(s) | Finding | Impact |
|----|-----|---------|---------|--------|
| A-R7-01 | CRIT | All 22 prompts (0/22 have `## Schema Authority`) | No `## Schema Authority` section in any prompt; AI has no instruction to read schema before generating output | Structural constraints undefined; AI guesses field names, types, enums; schema validation catches errors only after wasted generation cycles |
| A-R7-02 | CRIT | All 22 prompts (0/22 have `## Metadata Contract`) | No `## Metadata Contract` section in any prompt; no prompt defines expected output metadata structure (generation_quality with assumptions array, step-level required fields) | Output artifacts missing mandatory metadata guidance; AI has no instruction on generation_quality population |
| A-R7-03 | CRIT | tests/test_prompt_contracts.py (6), tests/test_prompt_schema_sync.py (8), tests/test_cli.py (1) — 15 total | Test files use legacy "B4 Metadata Contract" header; tests silently skip ALL 22 prompts because no prompt has the "## B4 Metadata Contract" header | Zero test coverage on prompt contracts; test suite is vacuously green |
| A-R7-04 | CRIT | prompts/prompt_12_ci_gates.md | `environment_ref` is REQUIRED by schema/12_ci_gates.schema.json (in jobs[*].required[]) but prompt contains NO mention of `environment_ref` in field-by-field guidance | AI will produce schema-failing output; CI gate definitions missing environment linkage |
| A-R7-05 | HIGH | prompts/prompt_13_extension_generator.md | `governance_label_ref` appears ONLY in Output Contract example JSON (line 109); NOT mentioned in Field-by-Field Guidance section | AI omits governance_label_ref from extensions; no population instructions with sourcing from Step 10 governance |
| A-R7-06 | HIGH | All 22 prompts (~73 instances total) | Vague language across all prompts: "consider", "may include", "if appropriate", "such as", "prefer", "should" in binding contexts, "optional->expected", indefinite metrics | Non-deterministic interpretation across AI runs; mandatory constraints treated as suggestions |
| A-R7-07 | HIGH | 9 prompts (01,02,02a,03,05,06,07,08,09) | 9 prompts have unfilled "X downstream steps" placeholder on line 3; prompt_00 ("8") and prompt_04 ("13") are already correct per `downstream_consumers` in `step_order.json` | Under-specified upstream impact; AI cannot assess downstream consequences of incomplete output |
| A-R7-08 | HIGH | 21/22 prompts (all except prompt_12) | `## Canonical Registry` section positioned AFTER `## Output Contract` in 21/22 prompts (prompt_12 already has correct order: Registry at line 88, Output Contract at line 154); AI encounters output field definitions before knowing valid canonical values | AI generates output with invented canonical values, then fails canonical-lint |
| A-R7-09 | HIGH | Prompts 00-04 (need Seed Ingestion Protocol); Prompts 05-16c (no seed requirements) | No formal `## Seed Ingestion Protocol` section; `spec/common/seed_manifest.json` -> `step_requirements` defines seed consumption: steps 00-04 have seed requirements; steps 05-16c have NONE. Steps 00-04 have partial "Extraction Intent" sections but no formal protocol; steps 05-16c MUST set seed_refs=[] | Seeds consumed ad hoc; seed_refs populated inconsistently; traceability gaps |
| A-R7-10 | HIGH | All 22 prompts | No formal `## Coverage Gap Reporting` section; no prompt instructs when/how to populate `coverage_gaps[]` field with `{upstream_item_id, source_step, reason}` | coverage_gaps[] always empty; untraceable fields silently swallowed |
| A-R7-11 | ~~MED~~ → R8 | 8 prompts (09,10,11,12,13,13a,16,16a) — 10 fields total | ~~Missing explicit sourcing instructions for specific fields~~ — **Deferred to R8**: R8 adds `description` fields to schemas with per-field sourcing guidance extracted from prompt Field-by-Field sections. `prompt_generator.py` reads these via `FIELD_DESCRIPTION`. Free-text sourcing is a schema concern, not a prompt concern. | Addressed by R8 schema `description` fields |

### Evidence (CRIT and HIGH findings)

#### A-R7-01
```
# Verified: 0/22 prompts contain "## Schema Authority"
# All 22 checked: prompt_00 through prompt_16c
# All prompts reference schemas in various ways but none have a dedicated
# authority delegation section instructing AI to read the schema first
```

#### A-R7-02
```
# Verified: 0/22 prompts contain "## Metadata Contract"
# No prompt has a section delegating to the schema's required[] array for metadata field completeness
```

#### A-R7-03
```python
# tests/test_prompt_contracts.py — 6 occurrences:
#   line 20:  if "## B4 Metadata Contract" not in text:
#   line 22:  parts = text.split("## B4 Metadata Contract")
#   line 60:  if "## B4 Metadata Contract" not in text:
#   line 62:  parts = text.split("## B4 Metadata Contract")
#   line 158: if "## B4 Metadata Contract" not in text:
#   line 172: parts = text.split("## B4 Metadata Contract")
# tests/test_prompt_schema_sync.py — 8 occurrences:
#   lines 251, 286, 328, 373, 411, 445, 487, 527
# tests/test_cli.py — 1 occurrence:
#   line 143
# Result: All tests silently skip because no prompt has "## B4 Metadata Contract"
```

#### A-R7-04
```
# prompts/prompt_12_ci_gates.md:
#   - No field instructions for environment_ref
#   - schema/12_ci_gates.schema.json defines environment_ref in jobs items required[]
#   - REQUIRED field completely absent from prompt guidance
```

#### A-R7-05
```
# prompts/prompt_13_extension_generator.md:
#   - governance_label_ref appears ONLY in Output Contract example JSON (line 109)
#   - NOT mentioned in Field-by-Field Guidance section
#   - Needs explicit population instructions with sourcing from Step 10 governance
```

#### A-R7-06 — Per-Prompt Vague Language Counts
```
| Prompt | Count | Key Instances (line numbers) |
|--------|-------|------------------------------|
| 00     | 6     | 40 (high-level scoping), 56 (cross-check), 62 (include baselines...when), 63 (infer), 64 (remove improve/optimize), 80 (ensure grounded) |
| 01     | 5     | 54 (verify feasibility), 60 (if FR draft exists), 61 (prefer), 104 (avoid generic verbs), 106 (avoid UI-centric names) |
| 02     | 6     | 56 (align connection), 62 (optional->expected), 62 (require auth for partner), 63 (external integrations), 66 (avoid generic), 67 (specify data domains) |
| 02a    | 5     | 58 (include secrets...when), 59 (staging MUST mirror), 60 (map gates to), 93 (not TBD), 111 (minimal structure) |
| 03     | 6     | 51 (normalize to canonical), 59 (coverage hint), 60 (avoid circular), 61 (specify inclusions), 107 (testable or observable), 123 (let new terms leak) |
| 04     | 5     | 61 (avoid should/could), 100 (avoid implementation details), 110 (outcome-oriented phrasing), 122-124 (may include) |
| 05     | 6     | 40 (optional->expected provide schema refs), 41 (at least one error state), 42 (avoid none for sensitive), 52 (if access control unclear), 95 (when specifying trace), 114 (DO NOT use generic error names) |
| 06     | 5     | 39 (consider: data integrity), 46 (use jsonlogic for data predicates), 47 (set severity=error for hard guarantees), 56 (if glossary defines...verify), 104 (DO NOT use text unless absolutely necessary) |
| 07     | 6     | 35 (practically measurable), 36 (if measurement_method cannot be practically implemented), 41 (optional->expected), 42 (measurement_method that is queryable), 101 (qualitative statements), 105 (orphans no owner) |
| 08     | 5     | 44 (optional->expected add targets), 45 (add smoke tags for critical flows), 97 (precise expected payload), 105 (minimal but sufficient), 114 (remain stable) |
| 09     | 4     | 34 (unless explicitly justified as a Spike), 36 (ask Gap Questions), 41 (optional->expected), 51 (if milestone dates cannot be derived) |
| 10     | 3     | 46 (optional->expected), 83 (do not use lazy policies), 107 (flip spec_first_policy to true) |
| 11     | 3     | 36 (add gap questions), 38 (ask Gap Questions), 64 (prefer linking to existing inv/nfr IDs) |
| 12     | 2     | 40 (optional->expected), 46 (ambiguity scrub: make each rule testable) |
| 13     | 2     | 50 (only create extensions for truly complex domains), heuristic on "deep" complexity |
| 13a    | 0     | (none — well structured) |
| 14     | 1     | 72 (lighter task detail) |
| 15     | 1     | 100 (validators list includes needed checks) |
| 16     | 2     | 46 (proactively identify security threats), 150 (does not conflict with) |
| 16a    | 0     | (none — exceptionally rigorous with FORBIDDEN actions) |
| 16b    | 0     | (none — highly deterministic) |
| 16c    | 0     | (none — clear verdict gates) |
```

#### A-R7-07 — Downstream Count Verification (using `downstream_consumers` from `step_order.json`)
```
# downstream_consumers = DIRECT downstream steps (not transitive closure)
# Source: tools/step_order.json -> downstream_consumers
| Prompt | Current Text | Correct Count | downstream_consumers |
|--------|-------------|---------------|----------------------|
| 00     | "feeds 8 downstream steps"  | 8 (CORRECT)  | [01,03,04,07,09,10,13a,14] |
| 01     | "feeds X downstream steps"  | 7  | [02,03,04,09,13,13a,14] |
| 02     | "feeds X downstream steps"  | 6  | [02a,05,09,11,13,15] |
| 02a    | "feeds X downstream steps"  | 1  | [12] |
| 03     | "feeds X downstream steps"  | 3  | [04,05,07] |
| 04     | "feeds 13 downstream steps" | 13 (CORRECT) | [05,06,07,08,09,11,13,13a,14,15,16,16a,16c] |
| 05     | "feeds X downstream steps"  | 9  | [06,08,09,11,13,13a,15,16,16a] |
| 06     | "feeds X downstream steps"  | 3  | [08,11,16a] |
| 07     | "feeds X downstream steps"  | 5  | [08,09,11,13,16a] |
| 08     | "feeds X downstream steps"  | 2  | [13a,16a] |
| 09     | "feeds X downstream steps"  | 3  | [10,14,16] |
| 10     | (no X placeholder)          | 1  | [12] |
| 11     | (no X placeholder)          | 1  | [16a] |
| 12     | (no X placeholder)          | 0  | [] (leaf node) |
| 13     | (no X placeholder)          | 2  | [13a,14] |
| 13a    | (no X placeholder)          | 1  | [14] |
| 14     | (no X placeholder)          | 5  | [15,16,16a,16b,16c] |
| 15     | (no X placeholder)          | 0  | [] (leaf node) |
| 16     | (no X placeholder)          | 3  | [16a,16b,16c] |
| 16a    | (no X placeholder)          | 1  | [16b] |
| 16b    | (no X placeholder)          | 1  | [16c] |
| 16c    | (no X placeholder)          | 0  | [] (leaf node) |
```

#### A-R7-08
```
# 21/22 prompts follow this section order (prompt_12 is the exception — already correct):
#   ... -> ## Output Contract -> ... -> ## Canonical Registry
# Per R7 spec: AI needs registry knowledge BEFORE producing output
# Example: prompt_00 has Output Contract at line 169, Canonical Registry at line 224
# Exception: prompt_12 has Canonical Registry at line 88, Output Contract at line 154 (CORRECT order)
# Must be reordered in 21 prompts: ## Canonical Registry BEFORE ## Output Contract
# Section content stays unchanged — only position changes
```

#### A-R7-09
```
# Verified: 0/22 prompts contain "## Seed Ingestion Protocol"
# Authoritative source: spec/common/seed_manifest.json -> step_requirements
# Step 00: requires seed-overview, seed-tech-stack
# Step 01: requires seed-overview
# Step 02: requires seed-tech-stack
# Step 02a: requires seed-tech-stack
# Step 03: requires seed-overview
# Step 04: requires seed-overview
# Steps 05-16c: NO seed requirements — seed_refs MUST be []
# Steps 00-04 have partial "### Extraction Intent" sections (need formalization into Seed Ingestion Protocol)
```

#### A-R7-10
```
# Verified: 0/22 prompts contain "## Coverage Gap Reporting"
# coverage_gaps[] defined in schemas but no prompt instructs AI when/how to populate
# Many prompts have "Coverage Closure" sections but these verify coverage —
# they do NOT instruct on populating the coverage_gaps[] output field
```

#### A-R7-11 — Deferred to R8 (Schema `description` Fields)
```
# DEFERRED TO R8: R8 Phase 3 (Subagent H) adds `description` fields to all 19 step
# schemas with sourcing guidance. prompt_generator.py reads these via FIELD_DESCRIPTION.
# Per-field sourcing instructions belong in schema metadata, not prompt prose.
# Original fields identified (now handled by R8):
# Step 09: 2 fields (tech_stack values beyond capabilities, spike justification)
# Step 10: 1 field (reviewer roles sourcing)
# Step 11: 1 field (threat discovery method)
# Step 12: 2 fields (environment_ref, ci_gate definition)
# Step 13: 1 field (governance_label_ref population)
# Step 13a: 1 field (artifact file locations for Phase 1 audit)
# Step 16: 1 field (existing_structures discovery method)
# Step 16a: 1 field (coding_examples source location)
# NOTE: A-R7-04 (environment_ref MISSING from prompt) and A-R7-05 (governance_label_ref
# missing from Field-by-Field) are SEPARATE findings — they are about fields completely
# absent from the prompt, not about sourcing instruction quality. Those remain R7 scope.
```

---

## Verified Non-Issues

Items from R7 spec that were investigated and found to be non-gaps:

| # | Investigated Item | Verdict | Reason |
|---|-------------------|---------|--------|
| 1 | Step 10 `pr_rules`/`versioning` required by schema | NOT A GAP | VERIFIED OPTIONAL in schema (not in required[]). Prompt's "optional->expected" language is appropriate. |
| 2 | Step 11 off-topic Step 09 reference | NOT A GAP | NOT FOUND in prompt_11. Initial audit hallucinated this. |
| 3 | Self-Audit Gates vague | NOT A GAP | ALL 22 prompts have SPECIFIC, measurable criteria (not vague). |
| 4 | Clarify->Emit Protocol missing | NOT A GAP | ALL 22 prompts have it with 0.9 threshold. |
| 5 | Upstream References use vague names | NOT A GAP | ALL 22 use exact filenames (spec/NN_*.json). |
| 6 | Canonical Output Fields lack instructions (Gap #9) | NOT A GAP | ALL 22 prompts have explicit `canonical_refs_used`, `canonical_proposals`, `canonical_conflicts` population instructions (e.g., prompt_04:208–220). `toolkit_optimisation.txt` confirms prompt-level canonical enforcement is handled. Remaining issues (trace_types hardcoding, enforcement layer inconsistency) are tooling/governance concerns for later reviews. |
| 7 | Schema Constraint Duplication | NOT A GAP | 0 instances across all 22 prompts. |
| 8 | Template Variables unreplaced | NOT A GAP | 0 unreplaced {{VAR}} patterns. |
| 9 | Generic Task Preamble contradictions | NOT A GAP | 0 instances of "You can work on any step" contradiction. |

---

## Part B: Implementation Plan — Atomic Tasks

### Common Changes Template

**For ALL 22 prompts, apply these changes (in this order within each file):**

**1. Add `## Schema Authority` section** — Insert as FIRST section after the prompt header/preamble (before any other ## section):
```markdown
## Schema Authority

The schema at `schema/<STEP_SCHEMA>.schema.json` is the authoritative source for all field definitions, types, required vs optional markers, enum values, patterns, and minItems rules. MUST read the schema before generating output. Do NOT guess field names, types, or valid values — all structural constraints are defined in the schema. Do NOT output fields not defined in the schema.
```

**2. Add `## Metadata Contract` section** — Insert BEFORE `## Output Contract`:
```markdown
## Metadata Contract

This step's output artifact MUST include every field listed in the schema's `required[]` array (see Schema Authority). Do NOT add fields not defined in the schema. Refer to the schema for the complete list of required fields, types, and structural constraints — do NOT restate them here.
```

**3. Move `## Canonical Registry` section** — Move from its current position (after Output Contract) to BEFORE `## Output Contract`. Keep content unchanged.

**4. Add `## Coverage Gap Reporting` section** — Insert after `## Seed Ingestion Protocol` (or after `## Schema Authority` if no seed section):
```markdown
## Coverage Gap Reporting

Any output field whose value cannot be traced to a specific upstream artifact or seed document MUST be recorded in `coverage_gaps[]` with:
- `upstream_item_id`: the ID of the upstream item that should have provided the data
- `source_step`: the step number where the data was expected
- `reason`: why the value could not be traced

This is DISTINCT from the Clarify->Emit protocol: ambiguous requirements trigger clarification questions; untraceable content triggers `coverage_gaps[]` population.
```

**5. Fix vague language** — Apply these replacements:
- "consider X" -> "MUST include X if [specific condition from upstream artifact]"
- "may include" -> "MUST include"
- "if appropriate" -> "if [specific condition from upstream artifact]"
- "such as" / "e.g." -> reference the upstream artifact to read for valid options
- "etc" -> remove entirely or reference upstream artifact
- "prefer X" -> "MUST use X when [specific condition]"
- "should X" (in binding context) -> "MUST X"
- "optional->expected" -> "MUST populate when [condition from upstream artifact is met]"
- Indefinite metrics ("minimal", "crisp", "sufficient") -> testable thresholds

**6. Fill "X downstream steps" placeholder** — Replace "feeds X downstream steps" on line 3 with the DIRECT downstream consumer count from `step_order.json` -> `downstream_consumers` (NOT the transitive closure from `allowed_upstream_dependencies`). Steps 00 and 04 already have correct values (8 and 13 respectively).

**7. Add/formalize `## Seed Ingestion Protocol`** — For steps 00-04 ONLY (as defined in `spec/common/seed_manifest.json` -> `step_requirements`). Steps 05-16c have NO seed requirements and MUST set `seed_refs` to `[]`:
```markdown
## Seed Ingestion Protocol

This step's seed requirements are defined in `spec/common/seed_manifest.json` -> `step_requirements`.

1. **Read**: Read `spec/common/seed_manifest.json` and identify seeds listed under this step's `step_requirements`
2. **Ingest**: Read each required seed document at its `path` listed in the manifest's `seeds[]` array, in the order defined by `global_seed_order`
3. **Extract**: Extract the specific fields relevant to this step's output as described in the `### Extraction Intent` section
4. **Populate**: Populate `seed_refs[]` with actually-used seed IDs and content hashes
```

### Phase 0: Test File Renames (P0 — prerequisite for all prompt work)

| ID | Pri | Deps | File | Change Summary | Acceptance Command | Findings |
|----|-----|------|------|----------------|-------------------|----------|
| T01 | P0 | — | tests/test_prompt_contracts.py | Replace all 6 occurrences of "B4 Metadata Contract" -> "Metadata Contract" | `pytest tests/test_prompt_contracts.py -v` | A-R7-03 |
| T02 | P0 | — | tests/test_prompt_schema_sync.py | Replace all 8 occurrences of "B4 Metadata Contract" -> "Metadata Contract" | `pytest tests/test_prompt_schema_sync.py -v` | A-R7-03 |
| T03 | P0 | — | tests/test_cli.py | Replace 1 occurrence of "B4 Metadata Contract" -> "Metadata Contract" | `pytest tests/test_cli.py -v` | A-R7-03 |

### Phase 1: Prompt Hardening (P0 — all changes per prompt in one task)

All tasks in Phase 1 depend on T01-T03. All Phase 1 tasks are independent of each other.

| ID | Pri | Deps | File | Step-Specific Changes (beyond common template) | Acceptance Command | Findings |
|----|-----|------|------|-------------------------------------------------|-------------------|----------|
| T04 | P0 | T01-T03 | prompts/prompt_00_project_charter.md | Schema: 00_charter.schema.json; Downstream: 8 (CORRECT, no change needed); Vague: 6 instances (lines 40,56,62,63,64,80); Seeds: seed-overview, seed-tech-stack — add Seed Ingestion Protocol | `pytest tests/ -k "prompt and 00" -v` | A-R7-01,02,06,08,09,10 |
| T05 | P0 | T01-T03 | prompts/prompt_01_capabilities.md | Schema: 01_capabilities.schema.json; Downstream: fill "X" -> "7"; Vague: 5 instances (lines 54,60,61,104,106); Seeds: seed-overview — add Seed Ingestion Protocol | `pytest tests/ -k "prompt and 01" -v` | A-R7-01,02,06,07,08,09,10 |
| T06 | P0 | T01-T03 | prompts/prompt_02_system_sketch.md | Schema: 02_system_sketch.schema.json; Downstream: fill "X" -> "6"; Vague: 6 instances (lines 56,62,62,63,66,67); Seeds: seed-tech-stack — add Seed Ingestion Protocol | `pytest tests/ -k "prompt and 02" -v` | A-R7-01,02,06,07,08,09,10 |
| T07 | P0 | T01-T03 | prompts/prompt_02a_delivery_baseline.md | Schema: 02a_delivery_baseline.schema.json; Downstream: fill "X" -> "1"; Vague: 5 instances (lines 58,59,60,93,111); Seeds: seed-tech-stack — add Seed Ingestion Protocol | `pytest tests/ -k "prompt and 02a" -v` | A-R7-01,02,06,07,08,09,10 |
| T08 | P0 | T01-T03 | prompts/prompt_03_glossary.md | Schema: 03_glossary.schema.json; Downstream: fill "X" -> "3"; Vague: 6 instances (lines 51,59,60,61,107,123); Seeds: seed-overview — add Seed Ingestion Protocol | `pytest tests/ -k "prompt and 03" -v` | A-R7-01,02,06,07,08,09,10 |
| T09 | P0 | T01-T03 | prompts/prompt_04_functional_requirements.md | Schema: 04_fr_list.schema.json; Downstream: 13 (CORRECT, no change needed); Vague: 5 instances (lines 61,100,110,122,124); Seeds: seed-overview — add Seed Ingestion Protocol | `pytest tests/ -k "prompt and 04" -v` | A-R7-01,02,06,08,09,10 |
| T10 | P0 | T01-T03 | prompts/prompt_05_interface_contracts.md | Schema: 05_interface_contracts.schema.json; Downstream: fill "X" -> "9"; Vague: 6 instances (lines 40,41,42,52,95,114); No seed requirements — seed_refs MUST be []; NO Seed Protocol | `pytest tests/ -k "prompt and 05" -v` | A-R7-01,02,06,07,08,10 |
| T11 | P0 | T01-T03 | prompts/prompt_06_invariants.md | Schema: 06_invariants.schema.json; Downstream: fill "X" -> "3"; Vague: 5 instances (lines 39,46,47,56,104); No seed requirements — seed_refs MUST be []; NO Seed Protocol | `pytest tests/ -k "prompt and 06" -v` | A-R7-01,02,06,07,08,10 |
| T12 | P0 | T01-T03 | prompts/prompt_07_nfrs.md | Schema: 07_nfrs.schema.json; Downstream: fill "X" -> "5"; Vague: 6 instances (lines 35,36,41,42,101,105); No seed requirements — seed_refs MUST be []; NO Seed Protocol | `pytest tests/ -k "prompt and 07" -v` | A-R7-01,02,06,07,08,10 |
| T13 | P0 | T01-T03 | prompts/prompt_08_fixtures.md | Schema: 08_fixtures.schema.json; Downstream: fill "X" -> "2"; Vague: 5 instances (lines 44,45,97,105,114); No seed requirements — seed_refs MUST be []; NO Seed Protocol | `pytest tests/ -k "prompt and 08" -v` | A-R7-01,02,06,07,08,10 |
| T14 | P0 | T01-T03 | prompts/prompt_09_impl_plan.md | Schema: 09_impl_plan.schema.json; Downstream: fill "X" -> "3"; Vague: 4 instances (lines 34,36,41,51); No seed requirements — seed_refs MUST be []; NO Seed Protocol | `pytest tests/ -k "prompt and 09" -v` | A-R7-01,02,06,07,08,10 |
| T15 | P0 | T01-T03 | prompts/prompt_10_governance.md | Schema: 10_governance.schema.json; Downstream: 1; Vague: 3 instances (lines 46,83,107); No seed requirements — seed_refs MUST be []; NOTE: pr_rules/versioning are OPTIONAL in schema — do NOT change to MUST | `pytest tests/ -k "prompt and 10" -v` | A-R7-01,02,06,08,10 |
| T16 | P0 | T01-T03 | prompts/prompt_11_redteam.md | Schema: 11_redteam.schema.json; Downstream: 1; Vague: 3 instances (lines 36,38,64); No seed requirements — seed_refs MUST be [] | `pytest tests/ -k "prompt and 11" -v` | A-R7-01,02,06,08,10 |
| T17 | P0 | T01-T03 | prompts/prompt_12_ci_gates.md | Schema: 12_ci_gates.schema.json; Downstream: 0 (leaf node); Vague: 2 instances (lines 40,46); **CRITICAL: Add `environment_ref` field guidance with sourcing from spec/02a_delivery_baseline.json -> environments[]**; No seed requirements — seed_refs MUST be []; **NOTE: Canonical Registry already BEFORE Output Contract — no reposition needed (A-R7-08 exception)** | `pytest tests/ -k "prompt and 12" -v` | A-R7-01,02,04,06,10 |
| T18 | P0 | T01-T03 | prompts/prompt_13_extension_generator.md | Schema: 13_extension_generator.schema.json; Downstream: 2; Vague: 2 instances (line 50, heuristic); **Add `governance_label_ref` population instructions in Field-by-Field section with sourcing from spec/10_governance.json**; No seed requirements — seed_refs MUST be [] | `pytest tests/ -k "prompt and 13" -v` | A-R7-01,02,05,06,08,10 |
| T19 | P0 | T01-T03 | prompts/prompt_13a_completeness_assessment.md | Schema: 13a_completeness_assessment.schema.json; Downstream: 1; Vague: 0; No seed requirements — seed_refs MUST be [] | `pytest tests/ -k "prompt and 13a" -v` | A-R7-01,02,08,10 |
| T20 | P0 | T01-T03 | prompts/prompt_14_roadmap.md | Schema: 14_roadmap.schema.json; Downstream: 5; Vague: 1 (line 72 "lighter"); R4-updated — preserve R4 changes; No seed requirements — seed_refs MUST be [] | `pytest tests/ -k "prompt and 14" -v` | A-R7-01,02,06,08,10 |
| T21 | P0 | T01-T03 | prompts/prompt_15_scaffold.md | Schema: 15_scaffold.schema.json; Downstream: 0 (leaf node); Vague: 1 (line 100); No seed requirements — seed_refs MUST be [] | `pytest tests/ -k "prompt and 15" -v` | A-R7-01,02,06,08,10 |
| T22 | P0 | T01-T03 | prompts/prompt_16_impl_context.md | Schema: 16_impl_context.schema.json; Downstream: 3; Vague: 2 (lines 46,150); No seed requirements — seed_refs MUST be [] | `pytest tests/ -k "prompt and 16" -v` | A-R7-01,02,06,08,10 |
| T23 | P0 | T01-T03 | prompts/prompt_16a_impl_planner.md | Schema: 16_impl_context.schema.json (SHARED); Downstream: 1; Vague: 0; R4-updated — preserve R4 changes; No seed requirements — seed_refs MUST be [] | `pytest tests/ -k "prompt and 16a" -v` | A-R7-01,02,08,10 |
| T24 | P0 | T01-T03 | prompts/prompt_16b_impl_coder.md | Schema: 16_impl_context.schema.json (SHARED); Downstream: 1; Vague: 0; No seed requirements — seed_refs MUST be [] | `pytest tests/ -k "prompt and 16b" -v` | A-R7-01,02,08,10 |
| T25 | P0 | T01-T03 | prompts/prompt_16c_impl_reviewer.md | Schema: 16_impl_context.schema.json (SHARED); Downstream: 0 (leaf node); Vague: 0; R4-updated — preserve R4 changes; No seed requirements — seed_refs MUST be [] | `pytest tests/ -k "prompt and 16c" -v` | A-R7-01,02,08,10 |

### Phase 2: Integration Verification (P1)

| ID | Pri | Deps | File | Change Summary | Acceptance Command | Findings |
|----|-----|------|------|----------------|-------------------|----------|
| T26 | P1 | T04-T25 | (verify only) | Run full prompt test suite | `pytest tests/ -k prompt -v` | — |
| T27 | P1 | T26 | (verify only) | Run full validation suite | `pytest tests/ -v && ./tools/run_specdev.sh validate-all spec --repo-root ./devspec_toolkit` | — |

### Phase 3: Documentation (P3)

| ID | Pri | Deps | File | Change Summary | Acceptance Command | Findings |
|----|-----|------|------|----------------|-------------------|----------|
| D01 | P3 | T27 | docs/audit/review_index.md | Add R7 entry with completion date, findings count (11 findings: 4 CRIT, 6 HIGH, 1 deferred to R8), task count (25 code + 2 verify + 1 doc = 28), status | `grep "R7" docs/audit/review_index.md` | — |

---

## Verification Status

- CHECK 1 Assumptions: PASS — All findings verified by Phase 1 Explore subagents + verification subagent. Corrected 2 items: Step 10 pr_rules confirmed OPTIONAL; Step 11 off-topic reference confirmed non-existent.
- CHECK 2 References: PASS — All file:line references from Phase 1 subagents who read actual files. Verification subagent confirmed Step 10 schema required[], Step 13 governance_label_ref location, downstream counts, canonical registry position.
- CHECK 3 Atomic: PASS — Each task modifies exactly one file. 25 code tasks + 2 verify tasks + 1 doc task = 28 total.
- CHECK 4 Tests: PASS — Each prompt task (T04-T25) has acceptance command. Phase 0 tasks (T01-T03) have per-file test commands. Phase 2 (T26-T27) provides full integration coverage.
- CHECK 5 Docs: PASS — D01 covers review_index.md update. No new error codes, CLI commands, or schema versions introduced.
- CHECK 6 Deps: PASS — T01-T03 have no deps. T04-T25 depend on T01-T03 (earlier in table). T26 depends on T04-T25. T27 depends on T26. D01 depends on T27. No forward references.
- CHECK 7 Orphans: PASS — All 11 findings mapped to tasks:
  - A-R7-01 -> T04-T25 (Schema Authority)
  - A-R7-02 -> T04-T25 (Metadata Contract)
  - A-R7-03 -> T01-T03 (test rename)
  - A-R7-04 -> T17 (environment_ref)
  - A-R7-05 -> T18 (governance_label_ref)
  - A-R7-06 -> T04-T25 (vague language per-prompt)
  - A-R7-07 -> T04-T25 (downstream counts)
  - A-R7-08 -> T04-T16, T18-T25 (canonical registry position — T17/prompt_12 excluded, already correct)
  - A-R7-09 -> T04-T09 (seed ingestion protocol for steps 00-04); T10-T25 (seed_refs=[] enforcement for steps 05-16c)
  - A-R7-10 -> T04-T25 (coverage gap reporting)
  - A-R7-11 -> Deferred to R8 (schema `description` fields provide per-field sourcing)
- Total findings: 11 (4 CRIT, 6 HIGH, 0 MED, 1 deferred to R8)
- Total tasks: 25 code + 2 verification + 1 doc = 28

OVERALL: VERIFIED

---

## Subagent Execution Strategy

**Batch A** (1 subagent, isolation: worktree): T01 + T02 + T03 (test file renames — 3 files, simple string replacement)

**Batch B** (1 subagent, isolation: worktree): T04-T08 (prompts 00-03 — seed-consuming steps per seed_manifest.json; formalize Seed Ingestion Protocol)

**Batch C** (1 subagent, isolation: worktree): T09-T13 (prompts 04-08 — T09 is last seed-consuming step; T10-T13 have no seed requirements, seed_refs=[])

**Batch D** (1 subagent, isolation: worktree): T14-T18 (prompts 09-13 — includes CRITICAL fixes for prompt_12 and prompt_13)

**Batch E** (1 subagent, isolation: worktree): T19-T25 (prompts 13a-16c — includes R4-preserved prompts)

**Batch F** (1 subagent, no isolation): T26-T27 (integration verification)

**Batch G** (1 subagent, no isolation): D01 (documentation)

Batches B-E can run in parallel after Batch A completes. Batch F runs after B-E complete. Batch G runs after F.

---

## Residual Notes

1. **Step 10 pr_rules/versioning**: R7 review spec (gap #2) stated "schema requires them" but verification confirmed they are OPTIONAL. The implementation MUST NOT change "should" to "MUST" for these fields. Vague language fix applies only to the "optional->expected" phrasing and "lazy policies" language.

2. **Step 11 off-topic reference**: R7 review spec mentioned Step 09 tech stack language in prompt_11 but verification found NO such text. This was a false positive in the initial audit.

3. **Seed Ingestion Protocol scope**: Per `spec/common/seed_manifest.json` -> `step_requirements`, only steps 00-04 have seed requirements. Steps 00-04 already have "### Extraction Intent" sections. Implementation MUST formalize these into the 4-step Seed Ingestion Protocol (read manifest -> ingest seeds -> extract fields -> populate seed_refs). Steps 05-16c have NO seed requirements and MUST set seed_refs=[] — do NOT add Seed Ingestion Protocol to these steps.

4. **R4-preserved prompts**: Steps 14, 16a, 16c were updated by R4. Implementation MUST read current state and preserve R4 changes. Additions are ADDITIVE only.

5. **Canonical Registry position**: 21/22 prompts need the `## Canonical Registry` section moved BEFORE `## Output Contract`. prompt_12 already has the correct order (Registry at line 88, Output Contract at line 154) — no repositioning needed for that file. The section content stays unchanged — only its position in the document changes.

6. **Seed ingestion authority**: `spec/common/seed_manifest.json` -> `step_requirements` is the authoritative source for which seeds each step must consume. Only steps 00-04 have seed requirements. Steps 05-16c MUST set `seed_refs` to `[]`. The `### Extraction Intent` sections in prompts describe what to extract from upstream artifacts (including seeds for steps 00-04) but are NOT the authority for which seeds to consume -- `seed_manifest.json` is.

7. **Vague language line numbers**: Vague language line numbers in A-R7-06 were captured from Phase 1 subagents that read the actual files. However, implementation subagents MUST verify line numbers against the current file state before editing, as line offsets may shift when earlier sections (Schema Authority, Metadata Contract) are inserted. Always search for the actual vague phrase text rather than relying solely on line numbers.

8. **Gap #3 deferred to R8**: Free-text field sourcing instructions are NOT added by R7. R8 (Schema Alignment) adds `description` fields to all step schemas with per-field sourcing guidance (WHERE to source the value, HOW to derive it). `prompt_generator.py` reads these via `FIELD_DESCRIPTION`. This means R8 MUST run after R7 to complete the sourcing coverage. A-R7-04 (environment_ref missing) and A-R7-05 (governance_label_ref missing from Field-by-Field) remain R7 scope — they address fields completely absent from prompts, not sourcing quality.

9. **Gap #9 verified non-issue**: All 22 prompts already have explicit population instructions for `canonical_refs_used`, `canonical_proposals`, `canonical_conflicts`. The `toolkit_optimisation.txt` confirms prompt-level canonical enforcement is handled. Remaining canonical concerns (trace_types hardcoding, enforcement layer inconsistency across Schema/Hallucination Lint/Canonical Integrity) are tooling/governance issues for later reviews, not prompt completeness issues.

---

## Section Templates for Implementation

Subagents implementing T04-T25 MUST use these exact section templates, adapted per step:

### Schema Authority (add as FIRST section after prompt header)
```markdown
## Schema Authority

The schema at `schema/<NN_step_name>.schema.json` is the authoritative source for all
field definitions, types, required vs optional markers, enum values, patterns, and minItems rules.
MUST read the schema before generating output. Do NOT guess field names, types, or valid values —
all structural constraints are defined in the schema. Do NOT output fields not defined in the schema.
```

### Seed Ingestion Protocol (add after Extraction Intent, for steps 00-04 ONLY per `seed_manifest.json`)
```markdown
## Seed Ingestion Protocol

This step's seed requirements are defined in `spec/common/seed_manifest.json` -> `step_requirements`.

1. **Read**: Read `spec/common/seed_manifest.json` and identify seeds listed under this step's `step_requirements`
2. **Ingest**: Read each required seed document at its `path` listed in the manifest's `seeds[]` array, in the order defined by `global_seed_order`
3. **Extract**: Extract the specific fields relevant to this step's output as described in the `### Extraction Intent` section
4. **Populate**: Populate `seed_refs[]` with actually-used seed IDs and content hashes
```

### Coverage Gap Reporting (add after Seed Ingestion Protocol or Schema Authority)
```markdown
## Coverage Gap Reporting

Any output field whose value cannot be traced to a specific upstream artifact or seed document
MUST be recorded in `coverage_gaps[]` with:
- `upstream_item_id`: the ID of the upstream item that should have provided the data
- `source_step`: the step number where the data was expected
- `reason`: why the value could not be traced

This is DISTINCT from the Clarify->Emit protocol: ambiguous requirements trigger clarification
questions; untraceable content triggers `coverage_gaps[]` population.
```

### Metadata Contract (add BEFORE Output Contract)
```markdown
## Metadata Contract

This step's output artifact MUST include every field listed in the schema's `required[]` array (see Schema Authority). Do NOT add fields not defined in the schema. Refer to the schema for the complete list of required fields, types, and structural constraints — do NOT restate them here.
```

---

## D01 Reference: review_index.md Entry Format

For task D01, add R7 to the review_index.md using this data:
- Review ID: R7
- File: `r7_prompt_completeness.md`
- Layer: L1 (Prompts)
- Gaps Closed: 1,2,4,5,7,8 (Gap 3 deferred to R8; Gap 9 verified non-issue)
- Priority: P0-critical
- Findings: 11 (4 CRIT, 6 HIGH, 1 deferred to R8)
- Tasks: 28 (25 code + 2 verification + 1 doc)
- Status: Findings written, implementation pending
