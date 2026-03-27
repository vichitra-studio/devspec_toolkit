# P3 Consolidation Review

**Date**: 2026-03-19
**Reviewer**: P3 Review Agent
**Target**: `WIP/schema_audit/p3-out-master-findings.md`
**Sources verified**: All 6 P1 files (p1-out-dry, p1-out-descriptions, p1-out-bloat, p1-out-genericity, p1-out-structure, p1-out-research)

---

## Verdict: MOSTLY CLEAN -- 5 issues found, 1 substantive

The consolidation is high quality. All 74 P1 findings are accounted for, severity/category breakdowns are internally consistent, and the dropped/merged table is well-reasoned. Five issues were identified, one of which is a substantive concern.

---

## Issues Found

### ISSUE-1: COUNT ERROR -- Pre-dedup total is 74, not 73

- **Type**: COUNT ERROR
- **Severity**: Minor (off-by-one)
- **Location**: Summary Statistics, "P1 findings (pre-dedup)" row
- **Details**: The P3 report states 73 pre-dedup findings. Actual count from P1 sources:
  - P1-A (DRY): 14
  - P1-B (Descriptions): 7
  - P1-C (Bloat): 11 (C01-C11; note: P1-C's own summary says "10" but the file contains 11 numbered findings)
  - P1-D (Genericity): 14
  - P1-E (Structure): 14
  - P1-F (Research): 14
  - **Total: 74**
- **Root cause**: P1-C's internal summary says "Total findings: 10" but the file contains 11 (FINDING-C01 through FINDING-C11). P3 likely used P1-C's stated summary (10) rather than the actual finding count (11).
- **Fix**: Change "P1 findings (pre-dedup)" from 73 to 74.

---

### ISSUE-2: BAD MERGE -- P1-F:007, P1-F:008, P1-F:009 collapsed into single AUDIT-064 without merge table entry

- **Type**: BAD MERGE / MISSING CROSS-REFERENCE
- **Severity**: Substantive
- **Location**: AUDIT-064, Dropped/Merged table
- **Details**: Three distinct P1-F findings were combined into AUDIT-064 without any entry in the Dropped/Merged Findings table:
  - P1-F:FINDING-007 (ALIGN-3 structured errors -- partial P5 progress)
  - P1-F:FINDING-008 (ALIGN-7 --json output -- partial progress)
  - P1-F:FINDING-009 (ALIGN-8 MCP tool + ALIGN-9 pre-commit hooks)

  These are three distinct research roadmap items covering different capabilities (error types, CLI output format, MCP tooling, pre-commit hooks). While all are "out of scope for schema audit," they address different tools/systems and could reasonably need separate tracking.

  This merge also breaks the count math: 74 raw - 8 dropped = 66 remaining, but only 65 AUDIT entries exist. The missing merge acknowledgment explains the discrepancy.

- **Fix**: Either (a) add P1-F:008 and P1-F:009 to the Dropped/Merged table with "Merged into AUDIT-064" and reason "All are out-of-scope tool/CI gaps; consolidated for brevity", or (b) split into AUDIT-064 (ALIGN-3), AUDIT-065 (ALIGN-7/8/9), and renumber current AUDIT-065 to AUDIT-066. Option (a) is simpler and updates the dropped count from 8 to 10 (and the pre-dedup from 74 to 74 remains, with 74 - 10 = 64... no that breaks too).

  Actually: to make the math work with option (a), the drop count becomes 9 (adding one of the two extra P1-F findings as merged), giving 74 - 9 = 65. Since AUDIT-064 absorbs 3 P1 findings but is only 1 AUDIT entry, 2 findings are effectively dropped. Add both P1-F:008 and P1-F:009 as merged into AUDIT-064. Then: 74 - 10 dropped = 64? No -- the formula is unique = raw - dropped_count, where dropped means "findings that do NOT get their own AUDIT entry." P1-F:008 and P1-F:009 don't have their own AUDIT entries, so they ARE dropped. Adding them to the table makes it 10 dropped, giving 74 - 10 = 64, which contradicts the 65 AUDIT entries.

  The cleanest fix: (1) Change pre-dedup to 74. (2) Add P1-F:008 to the Dropped/Merged table: "Merged into AUDIT-064 (P1-F:FINDING-007)" with reason "All out-of-scope tool/CI gaps consolidated." (3) Change duplicates merged/dropped from 8 to 9. (4) 74 - 9 = 65 unique. Math works.

  P1-F:009 covers BOTH ALIGN-8 and ALIGN-9 in a single P1 finding, and AUDIT-064 already mentions both, so that's fine as a 1:1 mapping (P1-F:009 -> AUDIT-064 alongside P1-F:007).

  So the actual dropped count is: 8 (currently listed) + 1 (P1-F:008) = 9. Pre-dedup = 74. 74 - 9 = 65. Correct.

---

### ISSUE-3: SEVERITY ERROR -- AUDIT-002 upgraded from HIGH to CRITICAL without sufficient justification

- **Type**: SEVERITY ERROR
- **Severity**: Debatable
- **Location**: AUDIT-002
- **Details**: Both P1-A:FINDING-002 and P1-C:FINDING-C01 rated `spec_refs_ingested` as HIGH severity. P3 upgraded to CRITICAL with justification "corroborated by 2 agents." Corroboration by multiple agents confirms accuracy but does not increase the technical impact of the finding. A dead required field with zero consumers is the same severity whether one agent or ten agents discover it. By contrast, AUDIT-001 (93.5% missing descriptions) is CRITICAL because of its actual impact on LLM hallucination risk.

  This is debatable rather than clearly wrong -- one could argue that a confirmed-dead required field in every schema is CRITICAL because it imposes mandatory overhead on every spec artifact and every prompt. But the original finders both rated it HIGH, and the upgrade reasoning ("corroborated") is not a valid severity-change justification.

- **Fix**: Either (a) keep CRITICAL but revise justification to focus on impact (e.g., "Dead required field in all 19 schemas imposes mandatory overhead on every spec artifact, prompt, and test fixture"), or (b) revert to HIGH. If reverted, CRITICAL count becomes 1, HIGH becomes 15.

---

### ISSUE-4: TARGET FILE TABLE GAPS -- Several AUDIT entries missing from target file rows

- **Type**: TARGET FILE TABLE GAPS
- **Severity**: Minor
- **Location**: "Findings by Target File" table at end of document
- **Details**: The following AUDIT-to-file mappings are absent from the target file table:

  1. **AUDIT-020** (`generation_quality` bloat) affects all 19 step schemas and `schema/core/collections.schema.json` (defines `generationQuality`). Missing from both the "All 19 step schemas" row and the `core/collections` row.

  2. **AUDIT-015** (ambiguous property names across schemas) affects multiple schemas (Steps 00, 02, 05, 06, 07, 09, 11, 12, 14, 16 at minimum). Not listed in the table at all -- no "Multiple schemas" catchall row for it.

  3. **AUDIT-051** (ALIGN-10 src/dist split) affects all 19 step schemas. Missing from the "All 19 step schemas" row.

  4. **AUDIT-056** (schemas already generic) has "Location: Steps 00, 01, 03, 04, 06, 07, 08, 09, 13, 13a, 14" but these individual step rows don't include 056.

  5. **AUDIT-064** (ALIGN-3/7/8/9 out of scope) has no target file and should be in the "N/A" row. Currently that row has `035, 036` only.

- **Fix**: Add the missing AUDIT IDs to the relevant rows. For AUDIT-015, add a "Multiple schemas" row or list under each affected step. Add 020, 051 to "All 19 step schemas" row. Add 064 to the "N/A" row.

---

### ISSUE-5: MISSING CROSS-REFERENCE -- P1-C:FINDING-C04 not listed in Dropped/Merged table explicitly

- **Type**: MISSING CROSS-REFERENCE (borderline)
- **Severity**: Minor
- **Location**: Dropped/Merged Findings table, last row
- **Details**: P1-C:FINDING-C04 ("spec_quality_lint.py checks 8/10 fields -- intentional signal") IS listed in the Dropped/Merged table as the last entry: "Reclassified as corroborating evidence, not standalone finding" merged into "AUDIT-002 and AUDIT-003." This is correct and present. However, the merge target "AUDIT-002 and AUDIT-003" is vague -- the finding specifically corroborates AUDIT-002 (`spec_refs_ingested` dead) and AUDIT-003 (`coverage_gaps` single consumer) by demonstrating the deliberate omission from the quality lint's check list. The P3 entries for AUDIT-002 and AUDIT-003 do reference this evidence (AUDIT-002 says "spec_quality_lint.py deliberately omits it"; AUDIT-003 says "spec_quality_lint.py deliberately skips it"), so the evidence IS incorporated even though the cross-reference is slightly imprecise.

- **Fix**: No fix needed. Noting for completeness that this was checked and confirmed correct.

---

## Verification Summary

| Check | Result |
|---|---|
| All P1-A findings (14) accounted for | PASS -- all 14 mapped to AUDIT entries |
| All P1-B findings (7) accounted for | PASS -- all 7 mapped to AUDIT entries |
| All P1-C findings (11) accounted for | PASS -- 8 standalone + 3 merged/dropped |
| All P1-D findings (14) accounted for | PASS -- all 14 mapped to AUDIT entries |
| All P1-E findings (14) accounted for | PASS -- all 14 mapped to AUDIT entries |
| All P1-F findings (14) accounted for | PASS -- 8 standalone + 5 merged + 1 UNDOCUMENTED MERGE (ISSUE-2) |
| Severity breakdown sums to 65 | PASS -- 2+14+24+12+13 = 65 |
| Category breakdown sums to 65 | PASS -- 14+7+8+14+14+8 = 65 |
| Pre-dedup count accurate | FAIL -- claims 73, actual is 74 (ISSUE-1) |
| Dropped/merged table complete | FAIL -- P1-F:008 missing (ISSUE-2) |
| No distorted findings | PASS -- spot-checked 15+ findings, all preserve original P1 intent |
| No hallucinated claims | PASS -- verified `spec_refs_ingested` zero grep, DRIFT_SENSITIVE_FIELDS contents against codebase |
| Severity changes justified | PARTIAL -- AUDIT-002 upgrade questionable (ISSUE-3); AUDIT-026/027 downgrades are reasonable |
| Target file table complete | FAIL -- 5 gaps identified (ISSUE-4) |

---

## Codebase Spot Checks

The following claims were verified against the actual codebase:

1. **`spec_refs_ingested` zero tool consumers** (AUDIT-002): `grep -r "spec_refs_ingested" tools/specdev_tools/` returns zero results. CONFIRMED.
2. **`DRIFT_SENSITIVE_FIELDS` contents** (AUDIT-002, AUDIT-020): Verified at `prompt_schema_sync.py:24-31`. Contains 6 fields: `dependencies`, `trace`, `generation_quality`, `canonical_refs_used`, `canonical_proposals`, `canonical_conflicts`. Does NOT contain `spec_refs_ingested` or `coverage_gaps`. CONFIRMED.
3. **P3 severity/category counts**: All sum correctly to 65. CONFIRMED.
