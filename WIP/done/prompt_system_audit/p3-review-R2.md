# P3 Consolidation Review — Round 2

**Date**: 2026-03-20
**Target**: `WIP/prompt_system_audit/p3-out-master-findings.md` (post-fix)
**Prior Review**: `WIP/prompt_system_audit/p3-review.md` (8 findings, all fixed)

## Prior Fix Verification

| R1 Finding | Status | Notes |
|------------|--------|-------|
| FINDING-001 (104→105 raw findings) | FIXED | Line 4 now reads "105 raw findings" |
| FINDING-002 (AUDIT-032 hallucination re linked_test_expectation) | FIXED | AUDIT-032 now correctly states schema DOES require `linked_test_expectation` (lines 371-373). Finding narrowed to remaining prompt-only gaps. No regression. |
| FINDING-003 (AUDIT-020 severity downgrade) | FIXED | AUDIT-020 restored to CRITICAL with detailed justification (line 98). Placed correctly in CRITICAL section. |
| FINDING-004 (AUDIT-012 severity upgrade) | FIXED | AUDIT-012 reverted to MEDIUM with explanation (line 286). Placed correctly in MEDIUM section. |
| FINDING-005 (AUDIT-008 upgrade reasoning) | FIXED | Added clarifying text "Quick Reference actively omits required schema fields, causing LLMs to produce invalid JSON" (line 132). |
| FINDING-006 (P1-F #11 weak absorption into AUDIT-054) | FIXED | P1-F #11 now mapped to new AUDIT-066 with proper finding body (lines 659-667). Cross-reference table updated (line 794). |
| FINDING-007 (summary table counts) | FIXED | Summary table updated to 66 total (6 CRIT, 17 HIGH, 26 MED, 13 LOW, 4 INFO). Verified correct by manual count. |
| FINDING-008 (corroborated/verified inflation) | FIXED | Summary table now shows Corroborated=9, Verified=57. Verified correct by checking each finding's status in the body. |

**All 8 R1 fixes verified. No regressions from the fixes themselves.**

---

## Summary

| Type | CRIT | HIGH | MED | LOW | Total |
|------|------|------|-----|-----|-------|
| BUG | 1 | 0 | 0 | 0 | 1 |
| GAP | 0 | 0 | 0 | 0 | 0 |
| ASSUMPTION | 0 | 0 | 0 | 0 | 0 |
| AMBIGUITY | 0 | 0 | 0 | 0 | 0 |
| HALLUCINATION | 0 | 0 | 0 | 0 | 0 |
| **Total** | **1** | **0** | **0** | **0** | **1** |

---

## Findings

### FINDING-R2-001: Deduplication Log Contains 6 Wrong AUDIT ID References
- **Type**: BUG
- **Severity**: CRITICAL
- **Section**: Deduplication Log (lines 22-40)
- **Claim**: The dedup log maps P1 finding merges to specific AUDIT IDs.
- **Actual**: 6 of 16 dedup log entries reference the wrong AUDIT IDs. The cross-reference table at the bottom of the document (lines 711-819) is correct in all cases, but the dedup log was not updated to match. Specific errors:

  1. **Line 27**: `P1-B #5 (Operating Flow homogeneity) + P1-B #2 (generic role) | Separate: AUDIT-002, AUDIT-003` — Should be **AUDIT-001, AUDIT-028**. AUDIT-002 is "Conflicting Upstream Inputs" (P1-B #3) and AUDIT-003 is "Implicit Requirements" (P1-B #4). The cross-reference table correctly maps P1-B #5 -> AUDIT-001 and P1-B #2 -> AUDIT-028.

  2. **Line 30**: `P1-C #7 + P1-B #10 | Separate: AUDIT-024, AUDIT-019` — Should be **AUDIT-018, AUDIT-031**. AUDIT-024 is seed ordering bug (P1-C #8) and AUDIT-019 is extraction mandates (P1-E #4). Cross-reference: P1-C #7 -> AUDIT-018, P1-B #10 -> AUDIT-031.

  3. **Line 35**: `P1-G #2 (template schema drift) + P1-G #4 (no interpolation) | Separate: AUDIT-046, AUDIT-050` — Should be **AUDIT-020, AUDIT-049**. AUDIT-046 is template_frs wrong filename (P1-G #3) and AUDIT-050 is gate item count variance (P1-D #4). Cross-reference: P1-G #2 -> AUDIT-020, P1-G #4 -> AUDIT-049.

  4. **Line 37**: `P1-G #14 + P1-G #11 + P1-G #18 | AUDIT-047` — Should be **AUDIT-045**. AUDIT-047 is workflow_bootstrap_legacy (P1-G #8). Cross-reference: P1-G #11, #14, #18 all -> AUDIT-045.

  5. **Line 38**: `P1-E #3 + P1-E #7 | AUDIT-029` — Should be **AUDIT-016**. AUDIT-029 is "No Weak-vs-Strong Examples" (P1-B #8). Cross-reference: P1-E #3 -> AUDIT-016, P1-E #7 -> AUDIT-016.

  6. **Line 39**: `P1-E #14 + P1-E #15 | Separate: AUDIT-032, AUDIT-033` — Should be **AUDIT-004, AUDIT-005**. AUDIT-032 is Trinity evidence binding (P1-E #6) and AUDIT-033 is Step 14 matrix trigger (P1-E #5). Cross-reference: P1-E #14 -> AUDIT-004, P1-E #15 -> AUDIT-005.

- **Fix**: Update all 6 dedup log entries to use the correct AUDIT IDs as shown above. The cross-reference table is the source of truth.

---

## Verified Correct

The following items were verified during this review and confirmed accurate:

### Coverage Audit
All 105 P1 findings accounted for:
- P1-A: 12/12 mapped (verified against source headings)
- P1-B: 18/18 mapped (verified against source headings)
- P1-C: 15/15 mapped (verified against source headings)
- P1-D: 9/9 mapped (verified against source headings)
- P1-E: 15/15 mapped (verified against source headings; confirmed 15 findings despite header claiming 14)
- P1-F: 18/18 mapped (verified against source headings)
- P1-G: 18/18 mapped (verified against source headings)

### Summary Table Accuracy
- CRITICAL=6, HIGH=17, MEDIUM=26, LOW=13, INFO=4, Total=66: **Correct** (manually counted from body)
- Corroborated=9, Verified=57: **Correct** (verified each finding's status label)
- AUDIT-001 through AUDIT-066 with no ID gaps: **Correct**

### Codebase Spot-Checks (14 findings verified)
1. **AUDIT-032**: `schema/16_impl_context.schema.json:554-558` confirms `linked_test_expectation` IS in `required` array. Finding correctly updated.
2. **AUDIT-021**: `STEP_TO_TEMPLATE` in `constants.py:15-35` confirmed: maps "00" through "16" only, no 16a/16b/16c.
3. **AUDIT-014**: `schema/09_impl_plan.schema.json` confirmed: zero `depends_on` matches.
4. **AUDIT-046**: `prompts/migration/template_frs.md:33` confirmed: references `spec/04_functional_requirements.json` (wrong name).
5. **AUDIT-036**: Grep for `shared_expectations` in `prompts/` returned exactly 8 files, matching claim.
6. **AUDIT-009**: Grep for `score.*0.9`, `Self-Audit`, `Coverage Closure` in `tools/specdev_tools/` returned zero matches. No validator exists.
7. **AUDIT-024**: `seed_lint.py:61-62` confirmed: `global_seed_order` seeds are unioned into required set.
8. **AUDIT-022**: `traceability_closure.py:84-97` confirmed: extracts only `goal_id`, not `success_metrics`.
9. **AUDIT-019**: Grep for `Extraction Mandate` in `prompts/` returned exactly 3 files (04, 14, 16a).
10. **AUDIT-066**: `schema/02_system_sketch.schema.json:117-120` confirmed: `schema_ref` description does not mention `-tbd` placeholder.
11. **AUDIT-020**: CRITICAL severity correctly restored; placed in CRITICAL section; justification is substantive.
12. **AUDIT-012**: MEDIUM severity correctly restored; placed in MEDIUM section; rationale is sound.
13. **AUDIT-006**: LOC estimates consistent with P0 baseline (748 verified-identical + ~179 near-identical).
14. **AUDIT-017**: Confirmed `step_16.py` is only consumer of `doc_paths`; no consumer for other `docs_policy` fields.

### Deduplication Quality
All merges reviewed in the finding BODIES are correct:
- P1-D #1 + P1-D #6 -> AUDIT-009: Sound merge, same root cause.
- P1-F #6 + P1-F #9 -> AUDIT-041: Sound merge, same prompt/section.
- P1-E #3 + P1-E #7 -> AUDIT-016 (in body): Sound merge, risk analysis + finding.
- P1-G #11 + P1-G #14 + P1-G #18 -> AUDIT-045 (in body): Sound merge, template-prompt integration gap.

The merge logic is correct in the finding bodies and cross-reference table. Only the dedup LOG section has stale/wrong AUDIT IDs.

### Severity Assignments
Post-fix severity assignments verified as appropriate:
- AUDIT-020 at CRITICAL: Justified (all 19 templates have schema drift, templates are primary migration input).
- AUDIT-012 at MEDIUM: Justified (formatting redundancy, 8 words per file, single-agent).
- AUDIT-008 at HIGH: Justified (corroborated, missing fields cause validation failures).
- All other severities consistent with consolidation rules.

### Consolidation Rules Compliance
1. Multi-agent findings correctly labeled "corroborated": 9 findings confirmed.
2. Single-agent findings correctly labeled "verified": 57 findings confirmed.
3. Severity resolution: No remaining violations after R1 fixes.
4. Dedup by primary ownership: All findings have clear owner attribution.

### No Hallucinations Detected
All spot-checked claims (14 of 66) match actual codebase state. The R1 hallucination in AUDIT-032 has been fully corrected.

---

## Regression Check

- AUDIT-020 move from HIGH to CRITICAL: Clean. Summary table updated. Cross-reference table unaffected.
- AUDIT-012 move from HIGH to MEDIUM: Clean. Summary table updated. Cross-reference table unaffected.
- AUDIT-066 addition: Properly placed in LOW section, properly numbered, cross-reference table has correct entry (line 794). Total counts updated to 66.
- Output count change from 65 to 66: Header (line 5), summary table (line 16) all show 66. Consistent.
- No surrounding content broken by any fix.
