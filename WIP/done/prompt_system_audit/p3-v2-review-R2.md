# P3-v2 Master Findings Review -- Round 2

**Date**: 2026-03-20
**Reviewer**: Deep Review Agent (R2)
**Document reviewed**: p3-out-master-findings-v2.md (post-fix)
**Prior review**: p3-v2-review.md (32 issues)

## Prior Fix Verification

- Fixes verified: 30/32
- Fixes with issues: 2

### Critical Fix Verification

| # | Issue | Status | Notes |
|---|-------|--------|-------|
| C1 | AUDIT-069 moved to Batch 1 | VERIFIED | Line 155: "Batch: 1 (moved from Batch 7...)" and Batch 1 summary includes 069. |
| C2 | Batch 0 sub-batch guidance added | VERIFIED | Lines 1386-1389: Three sub-batches (0a structural, 0b descriptions, 0c Quick Reference deletion). Addresses the blocking concern. |
| C3 | Summary statistics fixed (35 new, AUDIT-067-101) | VERIFIED | Line 21: "35 genuinely new findings from R2 (AUDIT-067 through AUDIT-101)" -- corrected from the prior "37" and "067-103" errors. |
| C4 | AUDIT-067 has complete pairwise chain | VERIFIED | Lines 126-131: Lists all 5 transitions (cap->FR, FR->API, FR->fixture, FR->milestone, milestone->task). |
| C5 | AUDIT-068 has design note about new infrastructure | VERIFIED | Lines 143: "Design Note" paragraph explains step_order.json has no gate concept today and new infrastructure is needed. |

### Important Fix Verification (14 issues)

All 14 important fixes from the prior review have been applied:

| Issue | Status |
|-------|--------|
| AUDIT-075 migration note | VERIFIED (line 416) |
| AUDIT-076 moved to Batch 1 | VERIFIED (line 719) |
| AUDIT-088 moved to Batch 1 | VERIFIED (line 854) |
| AUDIT-016 clarified ("FR ID and statement must appear verbatim in trace note field") | VERIFIED (line 269) |
| AUDIT-086 implementation note added | VERIFIED (lines 831) |
| AUDIT-071 Batch 0 scope clarified | VERIFIED (line 371: "Not all 925 descriptions need enrichment...focus on fields where prompts currently duplicate guidance") |
| AUDIT-036 subsumed correctly | VERIFIED (line 558: "SUBSUMED by AUDIT-026" with Batch N/A) |
| AUDIT-053/095 coordination note | VERIFIED (line 932 and 1068 cross-reference each other) |
| AUDIT-082/034 cross-reference | VERIFIED (line 785 and 542 cross-reference each other) |
| AUDIT-015 schema change note for Batch 0 | VERIFIED (lines 258: "schema change portion should be done in Batch 0") |
| AUDIT-084 migration note | VERIFIED (line 808) |
| AUDIT-017 migration note | VERIFIED (line 281) |
| Subsumed findings table added | VERIFIED (lines 1402-1416: explicit list of 9 subsumed P1 findings) |
| R2-B-016 source clarification | VERIFIED (line 1315: "Note: R2-B-016 was promoted from R2-B section 1.5 observation, not an explicit numbered finding in R2-B source") |

### Minor Fix Verification (13 issues)

All 13 minor fixes verified as applied:

| Issue | Status |
|-------|--------|
| P1-E #10-13 in cross-reference table | VERIFIED (lines 1246-1249) |
| P1-G #15 in cross-reference table | VERIFIED (line 1271) |
| AUDIT-091 relationship to 006/026 clarified | VERIFIED (line 885) |
| AUDIT-006 extract vs delete clarification | VERIFIED (line 167) |
| AUDIT-023 migration note | VERIFIED (line 337) |
| R2-C-012 mapping | VERIFIED (line 1327) |
| R2-C E304 mapping | VERIFIED (line 1328) |
| AUDIT-093 early-batch note | VERIFIED (line 1045) |
| Batch summary multi-batch note | VERIFIED (line 1384) |
| Batch execution order notes | VERIFIED (lines 1391-1400) |
| AUDIT-040 split notation | VERIFIED (line 609) |
| AUDIT-008 split notation | VERIFIED (line 192) |
| AUDIT-065 refined status | VERIFIED (line 1140) |

### Fixes with Issues

**1. Summary Table "From P1" / "From R2" Arithmetic (partially fixed)**

The prior review (C3) asked for the "37 new" and "067-103" range to be fixed. Those specific numbers are now correct (35 new, 067-101). However, the summary table's per-severity "From P1" and "From R2" columns still have a conceptual issue:

- The table says From P1 = 57, From R2 = 44. Total = 101. Check.
- The notes say "57 P1 active + 9 P1 subsumed + 35 R2 new = 101". But 57 + 9 + 35 = 101 treats subsumed findings as separate entries.
- In reality: AUDIT-001 through AUDIT-066 = 66 entries, all present in the document. Only AUDIT-036 is marked as subsumed among these. The other 8 "subsumed" items in the subsumed table (P1-B #7, P1-B #13, etc.) never had AUDIT IDs -- they were absorbed during the original P1-to-P3v1 consolidation.
- So the accurate count is: 66 P1 entries (65 active + 1 subsumed) + 35 R2 entries = 101. The "From P1 = 57" figure conflates two different consolidation phases (P1 agent-level absorption and AUDIT-level subsumption).

**Severity**: Minor. The total (101) and the individual finding entries are all correct. The per-column breakdown in the summary table is misleading but does not affect P4 planning.

**2. (No second issue with remaining fixes -- all others are clean.)**

---

## New Issues Found

- Total: 8
- Critical: 0
- Important: 3
- Minor: 5

---

## A. Coverage Gaps

### A.1 All R2 Documents Covered -- No New Gaps Found

Spot-checked R2-A (12 findings), R2-C (12+E304), R2-G (7 findings) against the cross-reference table. All are mapped. No P1 findings appear to have been lost during the fix pass.

### A.2 No P1 Findings Lost

All 66 AUDIT IDs (001-066) are present in the v2 document. AUDIT-036 is correctly marked as subsumed. No regression from the fix pass.

---

## B. Decision Consistency

### B.1 No New Decision Conflicts Found

All 13 design decisions were checked against the fixed findings. The prior review's concerns (B.1-B.4) have been addressed with migration notes and implementation notes. No new contradictions introduced by the fixes.

---

## C. Hallucinations -- Codebase Spot-Checks

### C.1 AUDIT-069 (semantic_review not enforced) -- VERIFIED CORRECT
`step_16c.py` lines 34-35: `semantic_review = review.get("semantic_review")` followed by `if isinstance(semantic_review, dict):`. If absent, the block is skipped. No error for missing semantic_review when verdict=verified. Finding is accurate.

### C.2 AUDIT-076 (verdict enum mismatch) -- VERIFIED CORRECT
`step_16c.py` line 13: `VALID_VERDICTS = frozenset({"verified", "needs_work", "blocked", "deferred"})`. "rejected" is absent. Finding is accurate.

### C.3 AUDIT-092 (minItems:2 vs >=1) -- VERIFIED CORRECT
`schema/04_fr_list.schema.json` line 46: `"minItems": 2` on `acceptance_criteria`. Finding is accurate.

### C.4 AUDIT-088 (E304 all roadmap tasks) -- VERIFIED CORRECT
`step_16.py` lines 313-318: iterates `for milestone in roadmap_data.get("milestones", []) for task in milestone.get("tasks", [])`. Collects ALL task IDs, not filtered by active milestone. Finding is accurate.

### C.5 AUDIT-093 (Step 13 pattern bug) -- VERIFIED CORRECT
`step_13.py` line 28: checks `required_schema_sections` entries against `_STEP_PATTERN` which matches `^[0-9]{2}[a-z]?_`. Domain sections like "tables" or "indexes" would fail this check. Finding is accurate.

### C.6 AUDIT-074 (canon entries count) -- MINOR DISCREPANCY
AUDIT-074 says "All 74 entries." Codebase: `canon/manifest.json` has 74 entries. R2-G source says 72. The finding uses the correct codebase number (74). No issue with v2.

### C.7 No Hallucinations Found
All 6 codebase spot-checks confirm the findings are accurate. The document has excellent evidentiary grounding.

---

## D. Ambiguities

### D.1 No New Ambiguities Found

The prior review's ambiguity concerns (D.1-D.4) have all been addressed:
- AUDIT-067 now lists the complete 5-transition pairwise chain.
- AUDIT-068 now has a design note about the blocking gate requiring new infrastructure.
- AUDIT-091 relationship to AUDIT-006/026 is now clarified.
- AUDIT-071 Batch 0 scope is now explicitly scoped to prompt-duplicated fields first.

---

## E. Duplicates / Conflicts

No new duplicate or conflict issues found beyond those already identified and addressed in the prior review.

---

## F. Regression Risks

No new regression risks introduced by the fix pass. The prior review's regression concerns (F.1-F.5) have been addressed with migration notes where applicable.

---

## G. Batch Assignment Issues

### G.1 AUDIT-007 Missing from Batch 2 Summary Table [Important]

AUDIT-007 (Canonical Registry Step 12 Variant) is assigned "Batch: 2" in its individual entry (line 181), but it does NOT appear in the Batch 2 row of the Batch Summary table (line 1375). The Batch 2 row lists only: "AUDIT-002, 006 (extraction part), 018, 026, 091, 101" (6 items). AUDIT-007 is missing.

This means:
- Batch 2 count should be 7, not 6.
- The total unique findings across all batches is 100 (not 101) because AUDIT-007 falls through the cracks.

**Fix**: Add AUDIT-007 to the Batch 2 row: "AUDIT-002, 006 (extraction part), 007, 018, 026, 091, 101" and update count to 7.

### G.2 Batch 1 Size After Moves Is Reasonable [No Issue]

After moving AUDIT-069, 076, and 088 to Batch 1, the batch has 7 items (017, 023, 035, 069, 076, 082, 088). These are all config/validator changes with no inter-dependencies. The batch is not overloaded.

### G.3 Batch Dependencies After Moves Are Valid [No Issue]

AUDIT-069 (step_16c.py bug), AUDIT-076 (verdict enum sync), and AUDIT-088 (E304 scope bug) have no dependencies on Batch 0 schema work. Their placement in Batch 1 is correct.

---

## H. Internal Consistency

### H.1 Summary Table "From P1" / "From R2" Column Meaning [Minor]

As detailed in the Prior Fix Verification section: the "From P1 = 57" and "From R2 = 44" split does not match the AUDIT ID ranges (001-066 = 66 P1, 067-101 = 35 R2). The 57/44 split appears to come from counting 66 - 9 "subsumed" = 57, and 35 + 9 = 44. But the 9 "subsumed" entries include 8 items that never had AUDIT IDs (they were absorbed during P1 agent-level consolidation, not during v1-to-v2). Only AUDIT-036 was actually subsumed at the AUDIT ID level.

The total (101) is correct. Individual entries are all present and correct. This is a labeling/arithmetic issue in the summary table only.

**Fix**: Either:
- (a) Change to "From P1 = 66, From R2 = 35" to match AUDIT ID ranges, or
- (b) Add a footnote explaining that "From P1 = 57" excludes 8 P1 agent-level findings absorbed into existing AUDIT entries during initial consolidation, plus 1 AUDIT-level subsumption (AUDIT-036).

### H.2 "Updated per Design Decisions = 12" Column -- Not Verified in Detail [Minor]

The summary table says 12 findings were "Updated per Design Decisions" (3+6+3+0+0 = 12). I did not verify each of the 12 against the individual findings, but spot-checking 5 (AUDIT-002, 003, 004, 009, 071) confirms they all carry "[Updated per...]" tags. Likely correct.

### H.3 Batch Count Total vs Finding Count [Important]

The Batch Summary table sums to: 18+7+6+6+24+6+6+12+15+3 = 103. The document notes multi-batch findings account for the difference (AUDIT-008 in Batch 0+4, AUDIT-015 in Batch 0+5, AUDIT-040 in Batch 0+4). That's 3 double-counted findings: 103-3 = 100. But we have 101 findings. The gap of 1 is AUDIT-007, which is missing from the Batch 2 row (see G.1 above). With AUDIT-007 added to Batch 2: 103+1 = 104 total batch slots, minus 3 double-counted = 101. Correct.

### H.4 Cross-Reference Tables Complete [No Issue]

Both P1 and R2 cross-reference tables are complete. All source findings are mapped. The R2-B-016 note (promoted from observation, not an explicit finding) is correctly documented.

### H.5 Subsumed Findings Table Accurate [Minor]

The table lists 9 entries. 1 (AUDIT-036) is a v1-to-v2 subsumption. 8 others (P1-B #7, #13, #16; P1-E #10-13; P1-G #15) are P1 agent-level findings absorbed during the original P1-to-P3v1 consolidation. The table conflates these two different consolidation phases under one "subsumed" label. This is related to the H.1 summary math issue.

**Fix**: Add a note to the subsumed table distinguishing: "AUDIT-036 was subsumed during v1-to-v2 consolidation. The remaining 8 entries are P1 agent-level findings that were absorbed into existing AUDIT entries as sub-points during the original P1-to-P3v1 consolidation (they never had independent AUDIT IDs)."

---

## Summary Assessment

The document is in good shape after the R1 fix pass. The 32 prior issues were addressed thoroughly. The remaining issues are:

| # | Category | Severity | Description |
|---|----------|----------|-------------|
| 1 | G.1 | Important | AUDIT-007 missing from Batch 2 summary table (finding falls through cracks) |
| 2 | H.1 | Minor | Summary table "From P1"/"From R2" columns don't match AUDIT ID ranges |
| 3 | H.3 | Important | Batch count totals off by 1 due to AUDIT-007 omission |
| 4 | H.5 | Minor | Subsumed findings table conflates two consolidation phases |
| 5 | Prior C3 | Minor | Summary notes math "57 + 9 + 35 = 101" is technically misleading |
| 6 | G.1 (count) | Important | Batch 2 count should be 7, not 6 |
| 7 | H.2 | Minor | "Updated per Design Decisions = 12" not fully verified (spot-check OK) |
| 8 | H.1 (alt) | Minor | AUDIT-006 batch annotation inconsistency: finding says "Batch: 0, then 2" but Batch 0 summary does not list AUDIT-006 (only Batch 2 does) -- this is consistent with the multi-batch note but slightly confusing |

**Recommendation**: Fix items 1, 3, and 6 (all the same root cause: add AUDIT-007 to Batch 2 table and update count). The remaining 5 items are minor clarity improvements that can be deferred to P4 or fixed as a quick pass. The document is ready to proceed to P4 (fix plan generation) after the AUDIT-007 batch table fix.
