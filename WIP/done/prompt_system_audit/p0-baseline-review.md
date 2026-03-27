# P0 Baseline Review — Findings

**Date**: 2026-03-20
**Reviewer**: general-purpose agent
**Target**: `WIP/prompt_system_audit/p0-baseline.md`

## Summary

| Type | CRIT | HIGH | MED | LOW | Total |
|------|------|------|-----|-----|-------|
| BUG | 1 | 3 | 4 | 2 | 10 |
| GAP | 0 | 1 | 2 | 0 | 3 |
| ASSUMPTION | 0 | 0 | 1 | 0 | 1 |
| AMBIGUITY | 0 | 0 | 2 | 1 | 3 |
| HALLUCINATION | 0 | 2 | 1 | 0 | 3 |
| **Total** | **1** | **6** | **10** | **3** | **20** |

---

## Findings

### FINDING-001: Heuristics For Completeness count is wrong
- **Type**: BUG
- **Severity**: MEDIUM
- **Section**: 2 (Section Frequency Matrix)
- **Claim**: "Heuristics For Completeness" appears in 16/22 prompts
- **Actual**: grep returns 18 files (18/22)
- **Fix**: Change 16/22 to 18/22

### FINDING-002: Operating Flow count note is misleading
- **Type**: BUG
- **Severity**: MEDIUM
- **Section**: 2 (Section Frequency Matrix)
- **Claim**: "Operating Flow: Synthesize → Clarify → Emit" appears in 14/22
- **Actual**: 14/22 is correct for this specific variant. Total Operating Flow headings (all variants combined at H2) is 17/22. H1-level variants in 16/16a/16b/16c are not counted.
- **Fix**: Add clarification that 14/22 is for the standard variant only. Total across all variants is higher.

### FINDING-003: FORBIDDEN ACTIONS count/list inconsistency
- **Type**: BUG
- **Severity**: HIGH
- **Section**: 2 (Section Frequency Matrix)
- **Claim**: "FORBIDDEN ACTIONS | 3/22 | 16, 16a, 16b, 16c" — count says 3 but lists 4 steps
- **Actual**: At H2 level: 16a, 16b, 16c (3 files). Prompt 16 uses H1 (`# FORBIDDEN ACTIONS`).
- **Fix**: Change to "4/22 | 16 (H1), 16a, 16b, 16c (H2)" or remove step 16 from the list and keep 3/22.

### FINDING-004: Boilerplate line counts inflated by 1 per section
- **Type**: BUG
- **Severity**: HIGH
- **Section**: 3 (Boilerplate LOC)
- **Claim**: SA=8, PV=9, HP=7, CR=8, CBR=7, subtotal=39 lines/file, total=861
- **Actual**: sed captures the next heading line. Actual content lines: SA=7, PV=8, HP=6, CR=7, CBR=6, subtotal=34/file, total=748. Conservative estimate ~948 not ~1,061. Percentage ~16.6% not 18.5%.
- **Fix**: Correct all line counts, totals, and percentages.

### FINDING-005: "do not output" heading variant attributed to wrong prompts
- **Type**: BUG
- **Severity**: HIGH
- **Section**: 4 (Self-Audit Gate Analysis)
- **Claim**: "Prompts with 'do not output' heading variant: 2 (16a, 16b)"
- **Actual**: `## Self-Audit Gate (do not output)` appears in prompt_00 and prompt_13a, NOT 16a/16b.
- **Fix**: Change to "2 (00, 13a)". Note 16a/16b/16c have "Score Threshold" variant and have the gate twice.

### FINDING-006: Self-Audit Gate item count range is wrong
- **Type**: BUG
- **Severity**: MEDIUM
- **Section**: 4 (Self-Audit Gate Analysis)
- **Claim**: "3 items (step 02a) to 12 items (step 16)"
- **Actual**: Minimum ~3 items (step 14), maximum ~8 items (step 00). Neither step 02a nor step 16 is an extreme.
- **Fix**: Change to "3 items (step 14) to 8 items (step 00)". Note 16a/16b/16c use mixed format.

### FINDING-007: Frequency matrix blind to H1-level headings in 5 prompts
- **Type**: GAP
- **Severity**: HIGH
- **Section**: 2 (Section Frequency Matrix)
- **Claim**: Matrix counts H2 sections only
- **Actual**: Prompts 13a, 16, 16a, 16b, 16c use H1 for major sections. This means sections like FORBIDDEN ACTIONS, Field Definitions, Operating Flow in these prompts are undercounted.
- **Fix**: Add caveat that prompts 13a, 16, 16a, 16b, 16c use H1 for major sections. Section 1 H2 counts for these prompts reflect sub-sections, not major sections.

### FINDING-008: Seed doc paths referenced by prompts don't exist in repo
- **Type**: AMBIGUITY
- **Severity**: MEDIUM
- **Section**: 5, 6 (Seed References, Doc References)
- **Claim**: `docs/seed/seed_overview.md` and `docs/seed/seed_tech_stack.md` listed as referenced
- **Actual**: `docs/seed/` directory does not exist in the repo. These are phantom path references — prompts tell agents to read files that don't exist (they exist in the HOST repo, not the toolkit repo).
- **Fix**: Add note: "These seed doc paths are HOST REPO paths, not toolkit paths. They do not exist in the devspec_toolkit repo — they exist in the product repo that vendors the toolkit as a submodule."

### FINDING-009: Role grouping for step 14 is wrong
- **Type**: BUG
- **Severity**: MEDIUM
- **Section**: 12 (Role Description Variants)
- **Claim**: Step 14 grouped with "senior specification author and validator"
- **Actual**: Step 14 uses "senior program manager and architect" — a distinct role.
- **Fix**: Remove 14 from first group. Add row: "senior program manager and architect | 14"

### FINDING-010: Operating Flow table missing step 11 and step 15
- **Type**: BUG
- **Severity**: LOW
- **Section**: 13 (Operating Flow Variants)
- **Claim**: "Synthesize → Clarify → Emit | 00–12 (standard 3-step)"
- **Actual**: Step 11 uses "Attack → Trace → Mitigate" (distinct). Step 15 also uses the standard pattern. Correct range: 00–10, 12, 15.
- **Fix**: Change to "00–10, 12, 15". Add "Attack → Trace → Mitigate | 11".

### FINDING-011: Missing Operating Flow variant for step 11
- **Type**: GAP
- **Severity**: MEDIUM
- **Section**: 13 (Operating Flow Variants)
- **Claim**: Table lists 7 patterns, omits step 11
- **Actual**: Step 11 has unique "Attack → Trace → Mitigate" not in table.
- **Fix**: Add row.

### FINDING-012: Step 16b stop conditions count
- **Type**: BUG
- **Severity**: LOW
- **Section**: 13 (Operating Flow Variants)
- **Claim**: "4 stop conditions"
- **Actual**: 3 stop conditions (a, b, c)
- **Fix**: Change to "3 stop conditions"

### FINDING-013: Section 7 Expected column verified correct
- **Type**: AMBIGUITY (resolved)
- **Severity**: LOW
- **Section**: 7 (Extraction Intent Coverage)
- **Claim**: Expected values from `allowed_upstream_dependencies`
- **Actual**: All values match step_order.json. No fix needed.
- **Fix**: None.

### FINDING-014: Step 07 downstream consumer count wrong
- **Type**: BUG
- **Severity**: MEDIUM
- **Section**: 16 (Downstream Consumers)
- **Claim**: "07 | 4 | 08, 09, 11, 13, 16a"
- **Actual**: List has 5 entries but count says 4.
- **Fix**: Change count to 5.

### FINDING-015: Traceability enforcement undercounted
- **Type**: GAP
- **Severity**: MEDIUM
- **Section**: 15 (Cross-Step Traceability Enforcement)
- **Claim**: "Only 1 of 9 traceability links has lint enforcement (E561)"
- **Actual**: E560 (TRACEABILITY_GAP) in traceability_closure.py enforces charter→capability AND capability→FR links. E561 covers FR coverage. W562 covers orphan milestones. W563 covers checklist-roadmap mismatch. At least 3-4 links are lint-enforced.
- **Fix**: Update table to show E560 for "Step 00 → Step 01" and "Step 01 → Step 04". Change summary to "at least 3 of 9 links have lint enforcement."

### FINDING-016: Schema description coverage numbers are stale
- **Type**: HALLUCINATION
- **Severity**: HIGH
- **Section**: 9 (Schema Description Coverage)
- **Claim**: "667/713 = 93.5%" with 5 schemas below 100%
- **Actual**: Commit `547c1f2` message says "close description coverage to 100% (925/925 properties)". The baseline numbers are from a stale counting script with a `$defs` parsing bug.
- **Fix**: Re-run with corrected script. Expected result: 925/925 = 100%. Update "below 100%" table accordingly.

### FINDING-017: nested_order line reference slightly off
- **Type**: BUG
- **Severity**: LOW
- **Section**: 8 (Config Consumers)
- **Claim**: "nested_order | seed_lint.py (lines 263-266)"
- **Actual**: Lines 261 and 264.
- **Fix**: Change to "lines 261-264"

### FINDING-018: Seed doc paths are HOST repo paths, not toolkit paths
- **Type**: HALLUCINATION
- **Severity**: MEDIUM
- **Section**: 5 (Seed References)
- **Claim**: Lists docs/seed/seed_overview.md and docs/seed/seed_tech_stack.md as referenced
- **Actual**: These are $PRODUCT_ROOT paths that exist in the host repo, not the toolkit. The toolkit contains the prompt references but not the files.
- **Fix**: Add note clarifying these are host repo paths resolved via $SEED_DIR path variable.

### FINDING-019: Section 14 JSON block counts verified correct
- **Type**: ASSUMPTION (resolved)
- **Severity**: MEDIUM
- **Section**: 14 (Output Contract Complexity)
- **Claim**: Steps 00-12 = 1 each, 16b = 5, 16c = 4, total = 29
- **Actual**: All verified correct.
- **Fix**: None.

### FINDING-020: Total property count contradicts git log
- **Type**: HALLUCINATION
- **Severity**: HIGH
- **Section**: 9 (Schema Description Coverage)
- **Claim**: Total properties = 713
- **Actual**: Git log says 925 properties. The 713 count is from a script that missed properties inside `$defs`, `allOf`, `if/then/else`, and deep nesting.
- **Fix**: Document and use the same methodology as the commit that achieved 100%. Total should be 925/925.

### FINDING-021: Self-Audit Gate counting adds to more than 22
- **Type**: AMBIGUITY
- **Severity**: MEDIUM
- **Section**: 2, 4
- **Claim**: "19 standard + 3 Score Threshold + 2 do not output = 22/22"
- **Actual**: Some files have duplicate gates (16a, 16b, 16c each have 2). The 19+3+2=24 total headings, but "22/22" means "present in all 22 files" which is correct.
- **Fix**: Clarify: "All 22 files contain at least one Self-Audit Gate. 3 files (16a, 16b, 16c) contain two. 24 total gate headings across 22 files."

---

## Verified Correct Claims

- Section 1: All LOC, word counts, H2/H3 counts verified correct
- Section 1 totals: 5,727 LOC, 22 files, 45,021 words confirmed
- Section 2: All 22/22 sections confirmed; partial counts confirmed (except FINDING-001)
- Section 3: md5 identity for Hardening Protocol (22/22) and Canonical Binding Rules (22/22) confirmed
- Section 4: "score < 0.9" in 22/22 confirmed; generation_quality 0/22 confirmed
- Section 5: Seed reference mappings correct; step_requirements correct
- Section 7: All extraction intent counts and expected values verified
- Section 8: All consumer claims verified (except line number in FINDING-017)
- Section 10: 1,344 tests, 0 failures, prompt-sync OK all confirmed
- Section 11: 526 LOC, DRIFT_SENSITIVE_FIELDS content confirmed
- Section 14: All JSON block counts confirmed; total 29 confirmed
- Section 16: All downstream_consumers entries match step_order.json (except count in FINDING-014)
- Migration templates: 19 files, 851 LOC confirmed
- Support documents: All LOC counts confirmed
