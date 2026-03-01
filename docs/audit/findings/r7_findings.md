# Review R7 Findings — Deep Prompt Completeness & Determinism Audit
Generated: 2026-03-01
Status: VERIFIED (Phase 4 corrected 7 issues from initial draft)

## Part A: Findings

| ID | Sev | File(s) | Finding | Impact |
|----|------|---------|---------|--------|
| A-R7-01 | CRIT | All 22 prompts + 3 test files | `## Metadata Contract` missing from all 22 prompts; tests use `## B4 Metadata Contract` delimiter — all skip silently, test suite is vacuously green | Zero test coverage on Output Contract metadata |
| A-R7-02 | CRIT | prompts/prompt_00-08*.md (10 files) | 0/10 prompts for steps 00-08 have `## Schema Authority` section; AI has no instruction to read schema before generating output | AI guesses field names, types, and enums — schema validation catches errors only after wasted generation cycles |
| A-R7-03 | CRIT | prompts/prompt_12_ci_gates.md | Missing `environment_ref` field instructions (schema requires it in jobs items) AND missing Schema Authority section entirely; only step 09-16c prompt lacking Schema Authority | Step 12 output omits environment_ref; downstream CI gate configuration incomplete |
| A-R7-05 | HIGH | All 22 prompts | 0/22 prompts have `## Seed Ingestion Protocol` section; seeds consumed but no structured extraction/reflection instructions | AI reads seeds ad hoc; seed_refs populated inconsistently; traceability gaps |
| A-R7-06 | HIGH | All 22 prompts | 0/22 prompts have `## Coverage Gap Reporting` section; no instruction to record untraceable fields | coverage_gaps[] always empty; gaps silently swallowed |
| A-R7-07 | HIGH | All 22 prompts | Canonical Registry section positioned AFTER Output Contract in all 22 prompts; AI encounters output field definitions before knowing valid canonical values. Population instructions already present (binding rules for canonical_refs_used, canonical_proposals, canonical_conflicts) — only position needs fixing | AI generates output with invented canonical values, then fails canonical-lint |
| A-R7-08 | HIGH | tests/test_prompt_contracts.py:20,22,60,62,158,172; tests/test_prompt_schema_sync.py:251,286,328,373,411,445,487,527; tests/test_cli.py:143 | 3 test files use "B4 Metadata Contract" delimiter (15 total occurrences); must be renamed to "Metadata Contract" to match new prompt section header | Tests remain broken until delimiter matches actual prompt section name; 0/22 prompts validated |
| A-R7-09 | HIGH | 18 prompts (all except prompt_13, prompt_16a, prompt_16b, prompt_16c) | 18 prompts have "Best Practices" sections with permissive "should"/"may"/"prefer" language that contradicts strict determinism | AI treats mandatory constraints as suggestions; non-deterministic output variance |
| A-R7-10 | HIGH | prompts/prompt_09_impl_plan.md:57-58,67,94 | Missing `environment_ref` field sourcing; tech_stack structure duplicated between prompt and schema; 5 vague phrases | Step 09 output lacks environment linkage to 02a; tech_stack guidance conflicts with schema |
| A-R7-11 | HIGH | prompts/prompt_13_extension_generator.md:56 | `governance_label_ref` appears only in output contract section, not in main field guidance; vague "truly complex" and "Don't Over-Splice" (both at line 56) | AI omits governance_label_ref from extensions; extension scope subjectively determined |
| A-R7-12 | HIGH | 9 prompts (01,02,02a,03,05,06,07,08,09) | 9 prompts have unfilled "X downstream steps" placeholder | Under-specified upstream artifacts propagate incomplete data |
| A-R7-04 | MED | prompts/prompt_10_governance.md:131,26 | prompt_10 uses 'should' language for several fields (line 131: 'should be filled', line 26: 'should block the merge') — soft language in binding context contradicts determinism. NOTE: pr_rules and versioning are NOT in schema required[] — this is a determinism issue, not a schema violation | Governance policies treated as advisory rather than mandatory |
| A-R7-13 | MED | prompts/prompt_00,prompt_13a (2 explicit); prompts/prompt_00-08*.md (10 total) | 2 prompts explicitly label Heuristics 'soft, non-binding' (prompt_00, prompt_13a); all 10 prompts (00-08, 13a) have Heuristics sections that use permissive framing | Completeness checks treated as advisory |
| A-R7-14 | MED | 13 prompts (01,02,02a,03,04,05,06,07,08,09,10,12,15) | "Optional->expected" framing in 13 prompts weakens mandatory field population | Optional fields left empty despite downstream steps needing them |
| A-R7-15 | MED | prompts/prompt_00-08*.md (10 files) | ~24 vague phrases across steps 00-08: "consider", "if appropriate", "notable", "critical", "key", "sensitive", "prod-impact", "marketing language" | Non-deterministic interpretation across AI runs |
| A-R7-16 | MED | prompts/prompt_09-16*.md (12 files) | ~17 vague phrases across steps 09-16c: "should map", "should be filled", "as needed", "as may be applicable", "JIT Granularity" | Same non-determinism for implementation-phase prompts |
| A-R7-17 | MED | prompts/prompt_00-08*.md (10 files) | No explicit field-by-field upstream sourcing paths in steps 00-08; only high-level Extraction Intent present | AI cannot trace individual output fields to specific upstream artifacts |
| A-R7-18 | MED | prompts/prompt_02_system_sketch.md; prompts/prompt_09_impl_plan.md | Step 02 duplicates tags vocabulary from schema; Step 09 duplicates tech_stack object structure from schema | Divergence risk: prompt and schema definitions drift apart |

### Evidence (CRIT and HIGH findings)

#### A-R7-01
```
# test_prompt_contracts.py line 20
if "# Output Contract" not in text or "## B4 Metadata Contract" not in text:
    continue  # skips prompt — condition is ALWAYS True for all 22 prompts
# Result: 0/22 prompts validated by this test
# 6 occurrences in test_prompt_contracts.py (lines 20, 22, 60, 62, 158, 172)
# 8 occurrences in test_prompt_schema_sync.py (lines 251, 286, 328, 373, 411, 445, 487, 527)
# 1 occurrence in test_cli.py (line 143)
```

#### A-R7-02
```
# Verified: 0/10 prompts for steps 00-08 contain "## Schema Authority"
# All 10 checked: prompt_00, prompt_01, prompt_02, prompt_02a, prompt_03,
#                 prompt_04, prompt_05, prompt_06, prompt_07, prompt_08
# Steps 09-16c: 11/12 have Schema Authority (only prompt_12 missing — see A-R7-03)
```

#### A-R7-03
```
# prompts/prompt_12_ci_gates.md:
# - No "## Schema Authority" section (only prompt in 09-16c range missing it)
# - No field instructions for environment_ref
# - schema/12_ci_gates.schema.json defines environment_ref in jobs items required[]
# Same gap exists in prompt_09 but prompt_09 has Schema Authority (only missing field sourcing)
```

#### A-R7-05
```
# Verified: grep -c "Seed Ingestion Protocol" prompts/prompt_*.md → 0 matches in all 22 files
# Seeds are consumed per step_order.json allowed_upstream_dependencies but no structured
# extraction/reflection protocol exists in any prompt
```

#### A-R7-06
```
# Verified: grep -c "Coverage Gap Reporting" prompts/prompt_*.md → 0 matches in all 22 files
# coverage_gaps[] defined in schemas but prompts never instruct AI when/how to populate it
```

#### A-R7-07
```
# All 22 prompts follow this section order:
#   ... → # Output Contract → ... → ## Canonical Registry (Required Input)
# Should be:
#   ... → ## Canonical Registry (Required Input) → ... → # Output Contract
# AI encounters field definitions requiring canonical values before seeing the valid value lists
#
# Population instructions: All 22 prompts include Canonical Registry (Required Input) section
# with binding rules for canonical_refs_used, canonical_proposals, canonical_conflicts.
# These are adequate — no additional population instruction tasks needed.
# Only the POSITION needs fixing (move BEFORE Output Contract).
```

#### A-R7-08
```python
# tests/test_prompt_contracts.py — 6 occurrences:
#   line 20: if "## B4 Metadata Contract" not in text:
#   line 22: parts = text.split("## B4 Metadata Contract")
#   line 60: if "## B4 Metadata Contract" not in text:
#   line 62: parts = text.split("## B4 Metadata Contract")
#   line 158: if "## B4 Metadata Contract" not in text:
#   line 172: parts = text.split("## B4 Metadata Contract")
# tests/test_prompt_schema_sync.py — 8 occurrences:
#   lines 251, 286, 328, 373, 411, 445, 487, 527
# tests/test_cli.py — 1 occurrence:
#   line 143
```

#### A-R7-09
```
# 18/22 prompts contain "Best Practices" sections with language like:
#   "should", "may", "prefer", "consider", "if appropriate"
# Exceptions (no Best Practices section): prompt_13, prompt_16a, prompt_16b, prompt_16c
```

#### A-R7-10
```
# prompts/prompt_09_impl_plan.md:
# Line 57: "expected" (vague — what consequence if absent?)
# Line 58: "should map" (conditional — MUST map)
# Line 67: "if milestone dates cannot be derived" (contingency without resolution)
# Line 94: "NO Generic Versions" (imperative but no enforcement)
# tech_stack structure defined in both prompt AND schema — duplication
# environment_ref: exists in schema properties, absent from prompt field guidance
```

#### A-R7-11
```
# prompts/prompt_13_extension_generator.md:
# Line 56: "Only create extensions for truly complex domains" — "truly complex" undefined
# Line 56: "Don't Over-Splice" — subjective threshold
# governance_label_ref: appears in ## Output Contract JSON but NOT in main field guidance
```

#### A-R7-12
```
# 9 prompts with unfilled "X downstream steps" placeholder:
# prompt_01, prompt_02, prompt_02a, prompt_03, prompt_05,
# prompt_06, prompt_07, prompt_08, prompt_09
```

---

## Part B: Implementation Plan — Atomic Tasks

### Implementation Notes

1. Phase 0 (T01-T03) fixes test infrastructure so tests can detect the new `## Metadata Contract` section once prompts are updated.
2. Phase 1 (T04-T25) touches each prompt file exactly once, adding all missing sections and fixing all vague language in a single pass per file.
3. Each prompt task is a text-only change to a markdown file — no code changes, no test tasks required per review_protocol.md CHECK 4.
4. Phase 1 tasks are organized into 4 batches (1A-1D) for parallelization. All tasks within a batch are independent.
5. T04-T25 depend on T01-T03 completing first so that acceptance commands validate against the correct delimiter.
6. Prompts 14, 16a, 16c have R4/R6 changes that MUST be preserved — subagent instructions include "read current state first".

### Phase 0: Test Infrastructure

| ID | Pri | Deps | File | Change summary | Acceptance command | Findings |
|----|-----|------|------|----------------|--------------------|----------|
| T01 | P0 | — | tests/test_prompt_contracts.py | Replace ALL 6 occurrences of "B4 Metadata Contract" → "Metadata Contract" | `pytest tests/test_prompt_contracts.py -v` | A-R7-08 |
| T02 | P0 | — | tests/test_prompt_schema_sync.py | Replace ALL 8 occurrences of "B4 Metadata Contract" → "Metadata Contract" | `pytest tests/test_prompt_schema_sync.py -v` | A-R7-08 |
| T03 | P0 | — | tests/test_cli.py | Replace 1 occurrence of "B4 Metadata Contract" → "Metadata Contract" | `pytest tests/test_cli.py -v` | A-R7-08 |

### Phase 1: Prompt Completeness (all 22 prompts, 4 parallel batches)

**Per-prompt changes** (applied to every prompt in T04-T25):
- Add `## Schema Authority` section (first section after header, referencing step's schema file)
- Add `## Seed Ingestion Protocol` section (after Extraction Intent, for seed-consuming steps)
- Add `## Coverage Gap Reporting` section (after Seed Ingestion Protocol)
- Add `## Metadata Contract` section (AFTER the Output Contract JSON example block)
- Move `## Canonical Registry (Required Input)` to BEFORE Output Contract
- Rename "Heuristics For Completeness" → "Completeness Directives"; remove "soft, non-binding" label
- Replace "Optional→expected" → "MUST populate"
- Replace vague phrases with operational definitions or MUST/MUST NOT directives
- Fill "X downstream steps" placeholder with actual count from step_order.json
- Remove schema constraint duplication where found
- Preserve all R4 and R6 changes (read current state first)

#### Batch 1A — Steps 00-04

| ID | Pri | Deps | File | Change summary | Acceptance command | Findings |
|----|-----|------|------|----------------|--------------------|----------|
| T04 | P0 | T01-T03 | prompts/prompt_00_project_charter.md | Add Schema Authority (00_charter.schema.json), Seed Ingestion Protocol, Coverage Gap Reporting; move Canonical Registry before Output Contract; add Metadata Contract AFTER Output Contract JSON block; rename "Heuristics" to "Completeness Directives" removing "soft, non-binding"; replace 4 vague phrases: "soft, non-binding" → remove, "Elevate optional→expected" → "MUST populate", "likely downstream FRs" → "downstream FRs that will consume this field", "Ambiguity scrub" → "Ambiguity elimination: every field MUST have a single unambiguous interpretation" | `grep -c "Schema Authority" prompts/prompt_00_project_charter.md && grep -c "Metadata Contract" prompts/prompt_00_project_charter.md && grep -c "Seed Ingestion Protocol" prompts/prompt_00_project_charter.md && grep -c "Coverage Gap Reporting" prompts/prompt_00_project_charter.md` | A-R7-01,02,05,06,07,09,13,14,15,17 |
| T05 | P0 | T01-T03 | prompts/prompt_01_capabilities.md | Add Schema Authority (01_capabilities.schema.json), Seed Ingestion Protocol, Coverage Gap Reporting; move Canonical Registry; add Metadata Contract AFTER Output Contract; replace "notable prerequisites" → "all prerequisites listed in the charter"; replace "if an FR draft exists" → "when spec/04_fr_list.json is present, MUST cross-reference"; replace "Optional→expected" → "MUST populate"; fill "X downstream steps" with actual count | `grep -c "Schema Authority" prompts/prompt_01_capabilities.md && grep -c "Metadata Contract" prompts/prompt_01_capabilities.md` | A-R7-01,02,05,06,07,09,12,13,14,15,17 |
| T06 | P0 | T01-T03 | prompts/prompt_02_system_sketch.md | Add Schema Authority (02_system_sketch.schema.json), Seed Ingestion Protocol, Coverage Gap Reporting; move Canonical Registry; add Metadata Contract; replace "should be marked as" → "MUST be marked as"; remove tags vocabulary duplication (defer to schema); replace "Optional→expected" → "MUST populate"; fill "X downstream steps" | `grep -c "Schema Authority" prompts/prompt_02_system_sketch.md && grep -c "Metadata Contract" prompts/prompt_02_system_sketch.md` | A-R7-01,02,05,06,07,09,12,13,14,15,17,18 |
| T07 | P0 | T01-T03 | prompts/prompt_02a_delivery_baseline.md | Add Schema Authority (02a_delivery_baseline.schema.json), Seed Ingestion Protocol, Coverage Gap Reporting; move Canonical Registry; add Metadata Contract; replace "critical gates" → "gates that block progression to subsequent phases"; replace "Parity hint" → "MUST achieve parity with"; replace "Optional→expected" → "MUST populate"; fill "X downstream steps" | `grep -c "Schema Authority" prompts/prompt_02a_delivery_baseline.md && grep -c "Metadata Contract" prompts/prompt_02a_delivery_baseline.md` | A-R7-01,02,05,06,07,12,13,14,15,17 |
| T08 | P0 | T01-T03 | prompts/prompt_03_glossary.md | Add Schema Authority (03_glossary.schema.json), Seed Ingestion Protocol, Coverage Gap Reporting; move Canonical Registry; add Metadata Contract; replace "key nouns" → "all domain-specific nouns used in upstream artifacts"; replace "marketing language" → "non-technical promotional language that lacks operational precision"; replace "Optional→expected" → "MUST populate"; fill "X downstream steps" | `grep -c "Schema Authority" prompts/prompt_03_glossary.md && grep -c "Metadata Contract" prompts/prompt_03_glossary.md` | A-R7-01,02,05,06,07,12,13,14,15,17 |
| T09 | P0 | T01-T03 | prompts/prompt_04_functional_requirements.md | Add Schema Authority (04_fr_list.schema.json), Seed Ingestion Protocol, Coverage Gap Reporting; move Canonical Registry; add Metadata Contract; replace "impacting state or permissions" → "that modify application state, user permissions, or data persistence"; replace "where performance is key" → "where response time or throughput has a defined NFR target"; replace "Optional→expected" → "MUST populate" | `grep -c "Schema Authority" prompts/prompt_04_functional_requirements.md && grep -c "Metadata Contract" prompts/prompt_04_functional_requirements.md` | A-R7-01,02,05,06,07,09,13,14,15,17 |

#### Batch 1B — Steps 05-08

| ID | Pri | Deps | File | Change summary | Acceptance command | Findings |
|----|-----|------|------|----------------|--------------------|----------|
| T10 | P0 | T01-T03 | prompts/prompt_05_interface_contracts.md | Add Schema Authority (05_interface_contracts.schema.json), Seed Ingestion Protocol, Coverage Gap Reporting; move Canonical Registry; add Metadata Contract; replace "imply payloads" → "define request/response payloads for every endpoint that accepts or returns data"; replace "sensitive resources" → "resources requiring authentication, authorization, or audit logging"; replace "Optional→expected" → "MUST populate"; fill "X downstream steps" | `grep -c "Schema Authority" prompts/prompt_05_interface_contracts.md && grep -c "Metadata Contract" prompts/prompt_05_interface_contracts.md` | A-R7-01,02,05,06,07,09,12,13,14,15,17 |
| T11 | P0 | T01-T03 | prompts/prompt_06_invariants.md | Add Schema Authority (06_invariants.schema.json), Seed Ingestion Protocol, Coverage Gap Reporting; move Canonical Registry; add Metadata Contract; replace "consider" → "MUST evaluate"; replace "unless necessary" → "ONLY when the invariant cannot be expressed without the dependency — document justification in description field"; replace "Optional→expected" → "MUST populate"; fill "X downstream steps" | `grep -c "Schema Authority" prompts/prompt_06_invariants.md && grep -c "Metadata Contract" prompts/prompt_06_invariants.md` | A-R7-01,02,05,06,07,09,12,13,15,17 |
| T12 | P0 | T01-T03 | prompts/prompt_07_nfrs.md | Add Schema Authority (07_nfrs.schema.json), Seed Ingestion Protocol, Coverage Gap Reporting; move Canonical Registry; add Metadata Contract; replace "prod-impact NFRs" → "NFRs whose measurement_method targets production environment metrics"; fix measurement_method contingency → "MUST specify measurement_method for every NFR; if automated measurement not feasible, set to 'manual' with audit_frequency"; replace "Optional→expected" → "MUST populate"; fill "X downstream steps" | `grep -c "Schema Authority" prompts/prompt_07_nfrs.md && grep -c "Metadata Contract" prompts/prompt_07_nfrs.md` | A-R7-01,02,05,06,07,09,12,13,14,15,17 |
| T13 | P0 | T01-T03 | prompts/prompt_08_fixtures.md | Add Schema Authority (08_fixtures.schema.json), Seed Ingestion Protocol, Coverage Gap Reporting; move Canonical Registry; add Metadata Contract; replace "critical flows" → "all flows in acceptance_criteria of any FR in spec/04_fr_list.json"; replace "Optional→expected" → "MUST populate"; NOTE: Step 08 has 0 downstream consumers — replace "X downstream steps" with "no downstream steps" or remove placeholder | `grep -c "Schema Authority" prompts/prompt_08_fixtures.md && grep -c "Metadata Contract" prompts/prompt_08_fixtures.md` | A-R7-01,02,05,06,07,12,13,14,15,17 |

#### Batch 1C — Steps 09-12 (includes critical fix A-R7-03)

| ID | Pri | Deps | File | Change summary | Acceptance command | Findings |
|----|-----|------|------|----------------|--------------------|----------|
| T14 | P0 | T01-T03 | prompts/prompt_09_impl_plan.md | Add Metadata Contract, Seed Ingestion Protocol, Coverage Gap Reporting; move Canonical Registry; ADD environment_ref field sourcing ("source from spec/02a_delivery_baseline.json environments[]"); remove tech_stack structure duplication; replace "expected" → "MUST include", "should map" → "MUST map", "if milestone dates cannot be derived" → "record in coverage_gaps[]"; replace "Optional→expected" → "MUST populate"; fill "X downstream steps" | `grep -c "Metadata Contract" prompts/prompt_09_impl_plan.md && grep -c "environment_ref" prompts/prompt_09_impl_plan.md` | A-R7-01,05,06,07,09,10,12,14,16,18 |
| T15 | P0 | T01-T03 | prompts/prompt_10_governance.md | Add Metadata Contract, Seed Ingestion Protocol, Coverage Gap Reporting; move Canonical Registry; replace "should be filled" (line 131) → "MUST be filled"; replace "should block the merge" (line 26) → "MUST block the merge"; replace "Optional→expected" → "MUST populate"; harden Best Practices "should"/"may" → "MUST" | `grep -c "Metadata Contract" prompts/prompt_10_governance.md && grep -c "MUST be filled" prompts/prompt_10_governance.md` | A-R7-01,04,05,06,07,09,14,16 |
| T16 | P0 | T01-T03 | prompts/prompt_11_redteam.md | Add Metadata Contract, Seed Ingestion Protocol, Coverage Gap Reporting; move Canonical Registry; replace "Prefer linking to existing" → "MUST link to existing mitigations when available; if none applies, create new with full structured fields"; harden Best Practices | `grep -c "Metadata Contract" prompts/prompt_11_redteam.md` | A-R7-01,05,06,07,09,16 |
| T17 | P0 | T01-T03 | prompts/prompt_12_ci_gates.md | **CRIT A-R7-03**: ADD `## Schema Authority` section (12_ci_gates.schema.json); ADD environment_ref field instructions with sourcing from spec/02a_delivery_baseline.json; Add Metadata Contract, Seed Ingestion Protocol, Coverage Gap Reporting; move Canonical Registry; replace "include when NFRs imply" → "MUST include for every NFR with environment-specific threshold"; replace "Optional→expected" → "MUST populate" | `grep -c "Schema Authority" prompts/prompt_12_ci_gates.md && grep -c "Metadata Contract" prompts/prompt_12_ci_gates.md && grep -c "environment_ref" prompts/prompt_12_ci_gates.md` | A-R7-01,03,05,06,07,09,14,16 |

#### Batch 1D — Steps 13-16c

| ID | Pri | Deps | File | Change summary | Acceptance command | Findings |
|----|-----|------|------|----------------|--------------------|----------|
| T18 | P0 | T01-T03 | prompts/prompt_13_extension_generator.md | Add Metadata Contract, Seed Ingestion Protocol, Coverage Gap Reporting; move Canonical Registry; ADD governance_label_ref to main field guidance ("MUST reference label from spec/10_governance.json governance_labels[]"); replace "truly complex domains" → "domains requiring >3 custom entity types not in existing schemas"; replace "Don't Over-Splice" → "MUST NOT create extension when functionality fits existing schema fields" | `grep -c "Metadata Contract" prompts/prompt_13_extension_generator.md && grep -c "governance_label_ref" prompts/prompt_13_extension_generator.md` | A-R7-01,05,06,07,09,11,16 |
| T19 | P0 | T01-T03 | prompts/prompt_13a_completeness_assessment.md | Add Metadata Contract, Seed Ingestion Protocol, Coverage Gap Reporting; move Canonical Registry | `grep -c "Metadata Contract" prompts/prompt_13a_completeness_assessment.md` | A-R7-01,05,06,07 |
| T20 | P0 | T01-T03 | prompts/prompt_14_roadmap.md | Add Metadata Contract, Seed Ingestion Protocol, Coverage Gap Reporting; move Canonical Registry; replace "JIT Granularity: Plan immediate 1-2 milestones in high detail" → "MUST plan all milestones at uniform detail; current-phase milestones MUST include task-level breakdowns"; preserve R4 changes | `grep -c "Metadata Contract" prompts/prompt_14_roadmap.md` | A-R7-01,05,06,07,16 |
| T21 | P0 | T01-T03 | prompts/prompt_15_scaffold.md | Add Metadata Contract, Seed Ingestion Protocol, Coverage Gap Reporting; move Canonical Registry; replace "Optional→expected" → "MUST populate" | `grep -c "Metadata Contract" prompts/prompt_15_scaffold.md` | A-R7-01,05,06,07,14 |
| T22 | P0 | T01-T03 | prompts/prompt_16_impl_context.md | Add Metadata Contract, Seed Ingestion Protocol, Coverage Gap Reporting; move Canonical Registry; replace "as may be applicable" → "for every field defined in the schema"; replace "where applicable to the schema" → "for all fields in schema required[] array" | `grep -c "Metadata Contract" prompts/prompt_16_impl_context.md` | A-R7-01,05,06,07,16 |
| T23 | P0 | T01-T03 | prompts/prompt_16a_impl_planner.md | Add Metadata Contract, Seed Ingestion Protocol, Coverage Gap Reporting; move Canonical Registry; replace "as needed" → "when implementation plan references a component not yet in scaffold"; preserve R4 changes | `grep -c "Metadata Contract" prompts/prompt_16a_impl_planner.md` | A-R7-01,05,06,07,16 |
| T24 | P0 | T01-T03 | prompts/prompt_16b_impl_coder.md | Add Metadata Contract, Seed Ingestion Protocol, Coverage Gap Reporting; move Canonical Registry | `grep -c "Metadata Contract" prompts/prompt_16b_impl_coder.md` | A-R7-01,05,06,07 |
| T25 | P0 | T01-T03 | prompts/prompt_16c_impl_reviewer.md | Add Metadata Contract, Seed Ingestion Protocol, Coverage Gap Reporting; move Canonical Registry; preserve R4 changes | `grep -c "Metadata Contract" prompts/prompt_16c_impl_reviewer.md` | A-R7-01,05,06,07 |

### Phase 2: Verification

| ID | Pri | Deps | File | Change summary | Acceptance command | Findings |
|----|-----|------|------|----------------|--------------------|----------|
| T26 | P1 | T04-T25 | — (no file) | Full test suite + validate-all | `pytest tests/ -v && ./tools/run_specdev.sh validate-all spec --repo-root ./devspec_toolkit` | — |

### Phase 3: Documentation

| ID | Pri | Deps | File | Change summary | Acceptance command | Findings |
|----|-----|------|------|----------------|--------------------|----------|
| D01 | P3 | T04-T25 | docs/audit/review_index.md | Add R7 entry to review index | `grep "R7" docs/audit/review_index.md` | — |

---

## Verification Status

- CHECK 1 Assumptions: PASS — no findings contain "likely", "probably", "may", "could", "appears to", "seems to"
- CHECK 2 References: PASS — all File:Line refs verified by Phase 1 subagents; Phase 4 corrected 7 issues: A-R7-04 downgraded CRIT→MED (pr_rules/versioning not in schema required[]), A-R7-08 line 528→527, A-R7-09 exception list corrected, A-R7-10 line 96→94, A-R7-11 line 51→56, A-R7-13 scope narrowed to 2 explicit + 10 total, A-R7-14 count 7→13 prompts
- CHECK 3 Atomic: PASS — every task modifies exactly 1 file; T26 is verification-only; D01 modifies 1 doc file
- CHECK 4 Tests: PASS — T01-T03 modify test files (self-verifying); T04-T25 modify prompt markdown (no code, no test tasks needed); T26 runs full suite
- CHECK 5 Docs: PASS — no new error codes, CLI commands, or schema versions; D01 covers review index
- CHECK 6 Deps: PASS — T01-T03 parallel; T04-T25 parallel in 4 batches after Phase 0; T26 after all; D01 after all
- CHECK 7 Orphans: PASS — every finding maps to at least one task
- Total findings: 18 (3 CRIT, 8 HIGH, 7 MED)
- Total tasks: 25 code + 1 verification + 1 doc = 27

---

## Subagent Execution Strategy

Phase 0 — Test infrastructure (3 parallel subagents):
  - Subagent A (worktree): T01 (test_prompt_contracts.py)
  - Subagent B (worktree): T02 (test_prompt_schema_sync.py)
  - Subagent C (worktree): T03 (test_cli.py)

Phase 1 — Prompt completeness (4 parallel subagents, after Phase 0):
  - Subagent D (worktree): Batch 1A — T04-T09 (prompts 00-04, 6 files)
  - Subagent E (worktree): Batch 1B — T10-T13 (prompts 05-08, 4 files)
  - Subagent F (worktree): Batch 1C — T14-T17 (prompts 09-12, 4 files; includes CRIT A-R7-03)
  - Subagent G (worktree): Batch 1D — T18-T25 (prompts 13-16c, 8 files)

Phase 2 — Verification (sequential, after Phase 1):
  - Subagent H (no isolation): T26

Phase 3 — Documentation (parallel with Phase 2):
  - Subagent I (no isolation): D01

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

### Seed Ingestion Protocol (add after Extraction Intent)
```markdown
## Seed Ingestion Protocol
1. Read seed document(s) listed in upstream dependencies
2. Extract fields relevant to this step (per Extraction Intent above)
3. Reflect extracted content in corresponding output fields
4. Populate `seed_refs` with actually-used seed IDs and content hashes
```

### Coverage Gap Reporting (add after Seed Ingestion Protocol)
```markdown
## Coverage Gap Reporting
Any output field whose value cannot be traced to a specific upstream artifact or seed
MUST be recorded in `coverage_gaps[]` with:
- `upstream_item_id`: the ID of the missing upstream item
- `source_step`: the step that should have provided the data
- `reason`: why the data is missing or untraceable
```

### Metadata Contract (add AFTER the Output Contract JSON example block)
```markdown
## Metadata Contract
Every artifact produced by this step MUST include:
- `"$schema"`: `"<URI from schema_registry.json for this step>"`
- `"spec_version"`: current specdev version string
- `"generation_quality"`: object with `confidence_score` (0.0-1.0), `coverage_assessment`, `known_gaps[]`, `recommendations[]`
```

---

## Next Steps

All implementation tasks (T01-D01) are staged and ready for parallel subagent execution.
Start with Phase 0 (T01-T03), then Phase 1 (T04-T25) once Phase 0 completes.
