# P0 Prompt System Audit — Baseline Report

**Date**: 2026-03-20
**Scope**: `prompts/`, `docs/prompts/`, `docs/agents/`, related schema descriptions, `spec/common/seed_manifest.json`, `tools/step_order.json`
**Branch**: `codex/canonical-drift-review-plan`

---

## 1. Prompt File Inventory

### Step Prompts (22 files)

| File | LOC | Words | H2 Sections | H3 Sections |
|------|-----|-------|-------------|-------------|
| prompt_00_project_charter.md | 245 | 2,091 | 19 | 2 |
| prompt_01_capabilities.md | 208 | 1,836 | 19 | 2 |
| prompt_02_system_sketch.md | 228 | 2,163 | 22 | 2 |
| prompt_02a_delivery_baseline.md | 200 | 1,746 | 19 | 2 |
| prompt_03_glossary.md | 192 | 1,678 | 19 | 2 |
| prompt_04_functional_requirements.md | 222 | 1,898 | 19 | 2 |
| prompt_05_interface_contracts.md | 183 | 1,887 | 17 | 2 |
| prompt_06_invariants.md | 205 | 1,842 | 17 | 2 |
| prompt_07_nfrs.md | 216 | 1,815 | 17 | 2 |
| prompt_08_fixtures.md | 206 | 1,885 | 17 | 2 |
| prompt_09_impl_plan.md | 240 | 1,982 | 17 | 2 |
| prompt_10_governance.md | 188 | 1,809 | 17 | 2 |
| prompt_11_redteam.md | 254 | 2,331 | 20 | 2 |
| prompt_12_ci_gates.md | 211 | 2,023 | 21 | 2 |
| prompt_13_extension_generator.md | 170 | 1,636 | 13 | 2 |
| prompt_13a_completeness_assessment.md | 203 | 1,789 | 17 | 2 |
| prompt_14_roadmap.md | 322 | 2,470 | 15 | 18 |
| prompt_15_scaffold.md | 189 | 1,846 | 17 | 2 |
| prompt_16_impl_context.md | 498 | 2,783 | 22 | 2 |
| prompt_16a_impl_planner.md | 392 | 3,065 | 24 | 8 |
| prompt_16b_impl_coder.md | 430 | 2,504 | 20 | 7 |
| prompt_16c_impl_reviewer.md | 525 | 2,942 | 23 | 8 |

**Totals**: 5,727 LOC | ~46,021 words | 22 files
**Estimated token footprint**: ~61K tokens (46,021 words ÷ 0.75)

### Migration Templates (19 files)

| Metric | Value |
|--------|-------|
| Files | 19 (steps 00–16; no 16a/16b/16c) |
| Total LOC | 851 |
| Avg LOC/file | ~45 |
| Uniform structure | Yes (all 6 identical H2 sections) |

### Support Documents

| File | LOC |
|------|-----|
| docs/prompts/shared_expectations.md | 51 |
| docs/agents/agents.md | 99 |
| docs/agents/manifest.json | 81 |
| docs/architecture/governance_architecture.md | 207 |

---

## 2. Section Frequency Matrix

### H1 sections appearing in ALL or MOST prompts

| Section | Occurrences | Notes |
|---------|-------------|-------|
| Role | 22/22 | |
| Output Contract | 22/22 | |
| Schema Reference | 22/22 | |
| Output Rules | 20/22 | prompt_12 uses H2; prompt_16 has no Output Rules heading |
| Task | 19/22 | Missing from 12, 16, 16a |
| Clarification Questions | 18/22 | Missing from 13, 14, 16b, 16c |

### H2 sections appearing in ALL 22 prompts (100%)

| Section | Occurrences | Verified Identical (md5) |
|---------|-------------|-------------------------|
| Schema Authority | 22/22 | — |
| Path Variables | 22/22 | — |
| Purpose | 22/22 | No (step-specific) |
| Tool Execution | 22/22 | — |
| Hardening Protocol | 22/22 | **Yes** (22/22 same md5) |
| Canonical Registry (Required Input) | 22/22 | 21/22 same md5 (1 variant in step 12) |
| Canonical Binding Rules | 22/22 | **Yes** (22/22 same md5) |
| Metadata Contract | 22/22 | No (each includes step-specific Output Contract) |

### H2 sections appearing in MOST prompts

| Section | Occurrences |
|---------|-------------|
| Self-Audit Gate (various heading variants) | 22/22 — All 22 files contain at least one Self-Audit Gate. 3 files (16a, 16b, 16c) contain two. 24 total gate headings across 22 files. |
| Negative Constraints | 18/22 |
| Field-by-Field Guidance | 18/22 |
| Common Pitfalls | 17/22 |
| Best Practices | 18/22 |
| Step-Specific Completeness Checklist | 16/22 |
| Quick Reference | 17/22 |
| Heuristics For Completeness | 18/22 |
| Operating Flow: Synthesize → Clarify → Emit | 14/22 (standard variant only; total across all Operating Flow variants is 17/22 at H2, plus additional H1 variants in 16/16a/16b/16c) |

### H3 sections appearing in ALL 22 prompts

| Section | Occurrences |
|---------|-------------|
| Extraction Intent | 22/22 |
| Coverage Closure | 22/22 |

### H2 sections appearing in FEW prompts

| Section | Occurrences | Steps |
|---------|-------------|-------|
| Seed Order & Mandatory Sources | 6/22 | 00, 01, 02, 02a, 03, 04 |
| Context To Ingest | 6/22 | 00, 01, 02, 02a, 03, 04 |
| FORBIDDEN ACTIONS | 4/22 | 16 (H1), 16a, 16b, 16c (H2) |
| Hallucination Vectors | 1/22 | 12 only |
| When To Use This Prompt | 1/22 | 16 only |
| Philosophy: Shift Left | 1/22 | 11 only |
| Taxonomy of Threats | 1/22 | 11 only |

> **Caveat**: All 22 prompts use H1 (`#`) for structural framework sections (Role, Task, Output Rules, etc.), giving standard prompts 5–7 H1 headings. Prompts 13a, 16, 16a, 16b, 16c additionally use H1 for content sections (Operating Flow, Field Definitions, FORBIDDEN ACTIONS, etc.), giving them 8–13 H1 headings. The H2 counts in Section 1 reflect sub-sections within these H1 blocks across all files.

---

## 3. Verified-Identical Boilerplate LOC

These sections have identical content across all prompts (verified by md5 hash comparison):

| Section | Lines/file | Total LOC (×22) |
|---------|-----------|-----------------|
| Schema Authority | 7 | 154 |
| Path Variables | 8 | 176 |
| Hardening Protocol | 6 | 132 |
| Canonical Registry (21/22 identical) | 7 | 154 |
| Canonical Binding Rules | 6 | 132 |
| **Subtotal (verified identical)** | **34** | **748** |

Additionally, these sections are near-identical (minor step-name swaps):
- Tool Execution: avg ~7 lines/file, 161 total (includes step-specific validation commands mixed with generic content)
- Metadata Contract header: 3 lines/file, 66 total

**Conservative boilerplate estimate**: 748 lines verified-identical + ~227 near-identical (Tool Execution 161 + Metadata Contract 66) = **~975 lines of duplicated content** (~17.0% of 5,727 total prompt LOC)

---

## 4. Self-Audit Gate Analysis

| Metric | Value |
|--------|-------|
| Prompts with "score < 0.9" text | 22/22 |
| Prompts with "Score Threshold" heading variant | 3 (16a, 16b, 16c) |
| Prompts with "do not output" heading variant | 2 (00, 13a) |
| Prompts with gate appearing twice | 3 (16a, 16b, 16c — have both "Score Threshold" and standard gate) |
| Total gate headings across all files | 24 (22 files, 3 with duplicates) |
| Scoring methodology defined | **0/22** — no prompt explains how to compute the score |
| Gate item count range | 3 items (step 14) to 8 items (step 00). Note: 16a/16b/16c use mixed format. |
| Generation_quality field in prompts | **0/22** — not a prompt section; was an R5 audit concept (decision: not implementing) |

---

## 5. Seed Document References

### Direct seed doc references in prompts

| Seed Document | Referenced By |
|---------------|--------------|
| docs/seed/seed_overview.md | prompt_00, prompt_01 |
| docs/seed/seed_tech_stack.md | prompt_00, prompt_02, prompt_02a |
| seed_manifest.json | prompt_00, prompt_01, prompt_02, prompt_02a, prompt_03, prompt_04, prompt_16a, prompt_16b, prompt_16c |

### seed_manifest.json `step_requirements` mapping

| Step | Required Seeds |
|------|---------------|
| 00 | seed-overview, seed-tech-stack |
| 01 | seed-overview |
| 02 | seed-tech-stack |
| 02a | seed-tech-stack |
| 03 | seed-overview |
| 04 | seed-overview |
| 05–16c | **(none declared)** |

**Key fact**: Steps 05–16c have no seed requirements declared in seed_manifest.json and no direct seed doc references in their prompts. All information passes through the waterfall via upstream spec artifacts.

> **Note**: `docs/seed/seed_overview.md` and `docs/seed/seed_tech_stack.md` are HOST REPO paths resolved via the `$SEED_DIR` path variable. They do not exist in the devspec_toolkit repo — they exist in the product repo that vendors the toolkit as a submodule.

---

## 6. Documentation Reference Coverage

### Docs referenced by ANY prompt

| Doc Path | Referenced By |
|----------|--------------|
| docs/prompts/shared_expectations.md | 00, 01, 02, 02a, 03, 04, 16b, 16c (8/22) |
| docs/developers/reference.md | 00 only (1/22) |
| docs/seed/seed_overview.md | 00, 01 (2/22) — HOST REPO path via `$SEED_DIR` |
| docs/seed/seed_tech_stack.md | 00, 02, 02a (3/22) — HOST REPO path via `$SEED_DIR` |
| canon/manifest.json | ALL 22/22 (via Canonical Registry Required Input section) |
| docs/api/auth.md | appears in Output Contract examples only (not a real reference) |
| docs/ops/environment_data_and_secrets.md | appears in Output Contract examples only |
| docs/README.md | appears in Output Contract examples only |

### Docs NEVER referenced by any prompt (47/54 docs)

Notable unreferenced docs:
- `docs/agents/agents.md` — Agent Operations Contract
- `docs/agents/manifest.json` — Agent manifest
- `docs/architecture/governance_architecture.md` — Canonical trace type reference
- `docs/developers/getting_started.md` — Primary onboarding guide
- `docs/developers/extension_schemas.md` — Extension authoring guide
- `docs/developers/error-codes.md` — Error code reference
- `docs/developers/path_conventions.md` — Path variable definitions
- `docs/developers/workflows/*.md` — 6 workflow guides
- `docs/developers/tooling/*.md` — Coverage matrix, gap hunter checklist
- `docs/ops/toolkit_update_checklist.md` — Change management procedures

---

## 7. Extraction Intent Coverage

Upstream spec artifact references per prompt (from `spec/NN_*` patterns):

| Step | Upstream Spec Refs | Expected (from step_order) |
|------|-------------------|---------------------------|
| 00 | 0 | 0 (root step) |
| 01 | 7 | 1 (just 00) |
| 02 | 6 | 2 (00, 01) |
| 02a | 4 | 3 (00, 01, 02) |
| 03 | 5 | 4 (00–02a) |
| 04 | 4 | 5 (00–03) |
| 05 | 7 | 6 (00–04) |
| 06 | 5 | 7 (00–05) |
| 07 | 6 | 8 (00–06) |
| 08 | 7 | 9 (00–07) |
| 09 | 7 | 10 (00–08) |
| 10 | 4 | 11 (00–09) |
| 11 | 6 | 12 (00–10) |
| 12 | 4 | 13 (00–11) |
| 13 | 5 | 14 (00–12) |
| 13a | 2 | 15 (00–13) |
| 14 | 6 | 16 (00–13a) |
| 15 | 4 | 17 (00–14) |
| 16 | 4 | 18 (00–15) |
| 16a | 2 | 19 (00–16) |
| 16b | 0 | 20 (00–16a) |
| 16c | 3 | 21 (00–16b) |

**Note**: The "Expected" column is `allowed_upstream_dependencies` count. The actual Extraction Intent references are far fewer than allowed upstream — prompts selectively reference only the most relevant upstream steps, not all allowed ones. The `downstream_consumers` map in step_order.json captures the actual curated subset.

**Methodology caveat**: Upstream Spec Refs were counted by `grep -c 'spec/[0-9]'`, which matches spec artifact filenames like `spec/00_charter.json`. This pattern (a) counts refs anywhere in the file, not just the Extraction Intent section, and (b) misses references like `spec/impl_context/{step_id}.json` that don't start with a digit. For example, prompt_16b has 7 `spec/` refs but 0 `spec/[0-9]` matches.

**Extraction Mandate sections**: 3 of 22 prompts (04, 14, 16a) contain explicit Extraction Mandate subsections that define hard coverage rules (e.g., 'every FR_ID must appear in ≥1 milestone fr_refs'). These correspond to lint-enforced traceability links in Section 15.

---

## 8. Config File Consumer Analysis

### seed_manifest.json consumers

| Field | Consumers | Count |
|-------|-----------|-------|
| seeds | seed_lint.py | 1 |
| global_seed_order | seed_lint.py | 1 |
| nested_order | seed_lint.py (lines 261-264) | 1 |
| step_requirements | seed_lint.py | 1 |
| docs_policy | step_16.py (reads doc_paths) | 1 |
| docs_policy.readme_* | **0** — docs_lint.py was REMOVED in prior audit | 0 |

**Key fact**: `docs_policy` is partially dead. `step_16.py` reads `docs_policy.doc_paths` only. The README-related fields (`readme_required`, `root_readme_required`, `readme_depth_default`, `readme_depth_by_scope`) have zero consumers since `docs_lint.py` was deleted.

### step_order.json consumers

| Field | Consumers | Count |
|-------|-----------|-------|
| steps | Multiple (core ordering) | many |
| policy | forward_replay_check.py | 1 |
| status_write_exemptions | forward_replay_check.py | 1 |
| allowed_upstream_dependencies | cli.py, dependency_order_lint.py, extraction_intent_check.py, hallucination_lint.py, dag_lint.py | 5 |
| coverage_thresholds | cli.py, matrix.py | 2 |
| downstream_consumers | cli.py (prompt-context), dag_lint.py, forward_replay_check.py | 3 |

---

## 9. Schema Description Coverage (Post-Schema-Audit)

| Metric | Value |
|--------|-------|
| **Total properties** | **925** |
| **Described** | **925** |
| **Coverage** | **100%** |

> Description coverage was closed to 100% in commit `547c1f2`. The counting methodology used 925 total properties across all schema files including nested `$defs`, `allOf`, `if/then/else` branches.

---

## 10. Test Suite Baseline

| Metric | Value |
|--------|-------|
| Tests collected | 1,344 |
| Tests passed | 1,344 |
| Tests failed | 0 |
| Test run time | 25.16s |
| Prompt-related test files | 15 |
| Key prompt test files | test_prompt_contracts.py, test_prompt_schema_sync.py, test_prompt_generator.py |

### prompt-sync validation status

```
specdev prompt-sync spec --repo-root . → OK
```

---

## 11. Prompt Infrastructure Tools

| Tool | LOC | Purpose |
|------|-----|---------|
| prompt_schema_sync.py | 526 | Bidirectional prompt ↔ schema alignment checking |
| prompt_generator.py | exists | Prompt template generation |
| cli.py (prompt-context) | ~50 | Show downstream consumers for a step |

### Drift-Sensitive Fields (prompt_schema_sync.py)

```python
DRIFT_SENSITIVE_FIELDS = (
    "dependencies",
    "trace",
    "canonical_refs_used",
)
```

---

## 12. Role Description Variants

| Role Text | Steps |
|-----------|-------|
| "senior specification author and validator" (or close variant) | 00–10, 12, 15 |
| "senior program manager and architect" | 14 |
| "senior security architect and Red Team specialist" | 11 |
| "Principal Software Architect and Technical Program Manager" | 13 |
| "senior specification auditor and quality control expert" | 13a |
| "senior software architect" | 16, 16a |
| "senior implementation engineer" | 16b |
| "senior technical reviewer" | 16c |

---

## 13. Operating Flow Variants

| Pattern | Steps |
|---------|-------|
| Synthesize → Clarify → Emit | 00–10, 12, 13a, 15 (standard 3-step; 13a at H1) |
| Attack → Trace → Mitigate | 11 |
| Analyze → Filter → Plan | 13 |
| Ingest → Synthesize → Sequence → Decompose → Emit | 14 (5-step) |
| 8-step with Drift Check | 16 |
| 7-step with Drift Check | 16a |
| Requirement-First Execution (3 stop conditions) | 16b |
| Evidence-Based Audit with Audit Checklist | 16c |

---

## 14. Output Contract Complexity

| Step | JSON Blocks | Estimated Contract LOC |
|------|-------------|----------------------|
| Steps 00–12 | 1 each | 15–40 lines |
| Step 13 | 1 | 25 lines |
| Step 13a | 1 | 30 lines |
| Step 14 | 1 | 50 lines |
| Step 15 | 1 | 35 lines |
| Step 16 | 1 | 80+ lines (largest) |
| Step 16a | 1 | 60 lines |
| Step 16b | 5 (input + output + failure variants) | 100+ lines |
| Step 16c | 4 (input + output + verdict variants) | 120+ lines |
| **Total JSON blocks** | **29** | — |

---

## 15. Cross-Step Traceability Enforcement

| Link | Enforcement Mechanism | Type |
|------|----------------------|------|
| Seed → Step 00 | Prompt says "extract from seed" | **Prompt-only (no lint)** |
| Step 00 → Step 01 | Prompt says "every charter goal → ≥1 capability"; E560 TRACEABILITY_GAP lint | **Lint-enforced** (E560) |
| Step 01 → Step 04 | Extraction Mandate in prompt; E560 TRACEABILITY_GAP + W561 FR_UNCOVERED lint | **Lint-enforced** (E560, W561) |
| Step 04 → Step 05 | Prompt says "every FR with API → interface"; W592 threshold-based coverage check | **Partial lint** (W592 threshold; per-item is prompt-only) |
| Step 04 → Step 14 | Extraction Mandate; W561 FR_UNCOVERED lint (FR must appear in milestone fr_refs) | **Lint-enforced** (W561) |
| Step 14 → Step 16a | Roadmap-to-Checklist Coverage mandate; W562 ORPHAN_MILESTONE + W563 CHECKLIST_ROADMAP_MISMATCH | **Lint-enforced** (W562, W563) |
| Step 16a → Step 16b | Checklist drives execution | **Schema-enforced** |
| Step 16b → Step 16c | Execution audited by reviewer | **Schema-enforced** |
| Step 16c → Steps 09/14 | Crucial Side Effect: update milestone status | **Prompt-only** |

**Key gap**: At least 5 of 9 traceability links have full lint enforcement (E560, W561, W562, W563), 1 has partial lint enforcement (W592 threshold), and the remaining 3 rely on prompt instructions. W-codes are warnings by default, promotable to E-codes with `SPECDEV_WARNINGS_AS_ERRORS=1`.

---

## 16. Downstream Consumers (from step_order.json)

| Step | Consumer Count | Consumers |
|------|---------------|-----------|
| 00 | 8 | 01, 03, 04, 07, 09, 10, 13a, 14 |
| 01 | 7 | 02, 03, 04, 09, 13, 13a, 14 |
| 02 | 6 | 02a, 05, 09, 11, 13, 15 |
| 02a | 1 | 12 |
| 03 | 3 | 04, 05, 07 |
| 04 | 13 | 05–09, 11, 13, 13a, 14, 15, 16, 16a, 16c |
| 05 | 9 | 06, 08, 09, 11, 13, 13a, 15, 16, 16a |
| 06 | 3 | 08, 11, 16a |
| 07 | 5 | 08, 09, 11, 13, 16a |
| 08 | 9 | 09, 13, 13a, 14, 15, 16, 16a, 16b, 16c |
| 09 | 3 | 10, 14, 16 |
| 10 | 1 | 12 |
| 11 | 7 | 13, 14, 15, 16, 16a, 16b, 16c |
| 12 | 6 | 13a, 14, 16, 16a, 16b, 16c |
| 13 | 2 | 13a, 14 |
| 13a | 1 | 14 |
| 14 | 5 | 15, 16, 16a, 16b, 16c |
| 15 | 3 | 16, 16a, 16b |
| 16 | 3 | 16a, 16b, 16c |
| 16a | 1 | 16b |
| 16b | 1 | 16c |
| 16c | 0 | (terminal) |

---

## Revision Log

**Rev 1** (2026-03-20) — Fixes from `p0-baseline-review.md` (20 findings: 1 CRIT, 6 HIGH, 10 MED, 3 LOW)

| Finding | Fix Applied |
|---------|-------------|
| FINDING-001 | Section 2: Heuristics count 16 → 18 |
| FINDING-002 | Section 2: Clarified Operating Flow 14/22 is standard variant only |
| FINDING-003 | Section 2: FORBIDDEN ACTIONS 3/22 → 4/22 with H1/H2 note |
| FINDING-004 | Section 3: Corrected boilerplate line counts (39→34/file, 861→748 total, 18.5%→16.6%) |
| FINDING-005 | Section 4: "do not output" variant corrected to steps 00, 13a |
| FINDING-006 | Section 4: Gate item range corrected to 3 (step 14) – 8 (step 00) |
| FINDING-007 | Section 2: Added H1 heading caveat for prompts 13a, 16, 16a, 16b, 16c |
| FINDING-008 | Section 6: Added note about seed doc paths being HOST REPO paths |
| FINDING-009 | Section 12: Step 14 re-grouped as distinct role |
| FINDING-010 | Section 13: Operating Flow range corrected to 00–10, 12, 15 |
| FINDING-011 | Section 13: Added Attack → Trace → Mitigate for step 11 |
| FINDING-012 | Section 13: Step 16b stop conditions 4 → 3 |
| FINDING-013 | No fix needed (verified correct) |
| FINDING-014 | Section 16: Step 07 consumer count 4 → 5 |
| FINDING-015 | Section 15: Traceability enforcement updated (1 → 3 lint-enforced links) |
| FINDING-016/020 | Section 9: Schema coverage corrected to 925/925 = 100% |
| FINDING-017 | Section 8: nested_order lines 263-266 → 261-264 |
| FINDING-018 | Section 5: Added $SEED_DIR host repo path clarification |
| FINDING-019 | No fix needed (verified correct) |
| FINDING-021 | Section 2, 4: Clarified Self-Audit Gate counting (24 headings across 22 files) |

**Rev 2** (2026-03-20) — Fixes from second review (11 findings: 0 CRIT, 2 HIGH, 8 MED, 1 LOW)

| Finding | Fix Applied |
|---------|-------------|
| R2-001 | Section 1: Total words 45,021 → 46,021 |
| R2-002 | Section 3: Tool Execution avg 27→~7 lines/file, 591→161 total |
| R2-003 | Section 3: Metadata Contract 6→3 lines/file, 132→66 total |
| R2-004 | Section 2: H1 caveat reworded — all prompts use H1, 5 use more |
| R2-005 | Section 13: Added step 13a to standard Operating Flow |
| R2-006 | Section 7: Added methodology caveat for grep pattern limitations |
| R2-007 | Section 15: Traceability enforcement 3→5 links; added W561, W562, W563 |
| R2-008 | Section 2: Added H3 Extraction Intent (22/22) to frequency matrix |
| R2-009 | Section 2: Added Clarification Questions (18/22) to frequency matrix |
| R2-010 | Section 7: Added Extraction Mandate (3/22) note |
| R2-011 | Section 3: Conservative estimate recalculated to ~975 (~17.0%) |

**Rev 3** (2026-03-20) — Fixes from third review (8 findings: 0 CRIT, 0 HIGH, 2 MED, 6 LOW)

| Finding | Fix Applied |
|---------|-------------|
| R3-001 | Section 2: Best Practices 17 → 18 |
| R3-002 | Section 2: Quick Reference 16 → 17 |
| R3-003 | Section 2: Added Coverage Closure (22/22) to H3 table |
| R3-004 | Section 2: Added H1 frequency table (Role, Output Contract, Schema Reference, Output Rules, Task, Clarification Questions) |
| R3-005 | Covered by R3-004 |
| R3-006 | Section 15: Step 04→05 upgraded to partial lint (W592) |
| R3-007 | False alarm — no fix needed |
| R3-008 | Section 1: Added token footprint estimate (~61K tokens) |
| R3-009 | Section 6: Added canon/manifest.json (22/22) |
