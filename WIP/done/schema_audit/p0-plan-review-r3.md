# P0 Plan Review -- Round 3

**Date**: 2026-03-19
**Reviewer**: Claude Opus 4.6 (automated third-pass review)
**Scope**: Verify all R1 (26) and R2 (13) findings were addressed; find residual bugs, gaps, and regressions introduced by R2 fixes

---

## Verification of R1 Fixes (26 findings)

All 26 R1 findings were addressed in the revision log. Spot-checked against actual baseline/plan text:

- BUG-001/002/003 (core definition counts): VERIFIED -- baseline section 3 headers now show 6 atoms, 28 collections, total 44. Plan summary matches.
- BUG-004 (LOC clarification): VERIFIED -- plan says "(6,015 schema/ + 57 canon/)". (Note: was initially 59, then corrected by R2 IFIX-001.)
- BUG-005 (generation_quality 20 vs 19): VERIFIED -- baseline section 6 now says "Present in 19 step schemas".
- GAP-001 through GAP-007: VERIFIED -- all added to P1 agent scopes with baseline facts.
- ASSUM-001/002/003: VERIFIED -- qualifications added.
- MISS-001 through MISS-004: VERIFIED -- additional questions added to P1 agents.
- AMBIG-001 (dual-container): VERIFIED -- removed entirely; single container per agent.
- AMBIG-002/003: VERIFIED -- severity clarified; primary ownership assigned.
- HALLUC-001: VERIFIED -- constraint note added about counting table items.
- REG-001/002: VERIFIED -- notes added.

## Verification of R2 Fixes (13 findings)

All 13 R2 findings were addressed in the revision log. Spot-checked:

- IFIX-001 (canon LOC 59 to 57): VERIFIED -- baseline and plan now show 57 canon LOC, total 6,072.
- BUG-001 ($ref 468 to 448): VERIFIED -- baseline section 4 total is now 448.
- BUG-002 (registry 31 to 29): VERIFIED -- baseline section 10 says 29 entries. Plan P1-E says 29.
- BUG-003 (enum ~61 + caveat): VERIFIED -- both baseline and plan say ~61 with caveat for P1-A to recount.
- BUG-004 (downstream_consumers 14/10 to 13/9): VERIFIED -- baseline section 12 says 13 and 9.
- BUG-005 (seed_refs/spec_refs 20 to 19): VERIFIED -- sections 7 and 8 fixed.
- IFIX-001 through GAP-004, ASSUM-001, AMBIG-001, MISS-001: All VERIFIED as addressed.

---

## NEW FINDINGS

### BUG-001: Baseline step schemas LOC subtotal is wrong (says 4,090, actual is 4,936)

- **Severity**: MEDIUM
- **Details**: Baseline section 2 table says "Step schemas (00-16) | 19 | 4,090". Summing the per-file LOC from section 1's tree listing (which match `wc -l` output) gives 4,936. The difference is 846 LOC. The overall total of 6,015 is correct (4,936 + 154 + 925 = 6,015), which means the subtotal is wrong but the total is right. This was not caught in R1 or R2.
- **Evidence**: Section 1 individual LOC values: 202+138+331+110+114+139+220+134+152+119+152+178+181+184+122+152+271+169+1868 = 4,936. Section 2 table says 4,090. Verified with `wc -l schema/*.schema.json` (excluding seed_manifest and core/).
- **Impact**: P1 agents looking at section 2 for LOC distribution will get a wrong impression of step schema vs. core schema proportions. The error makes step schemas appear 17% smaller than they are.
- **Recommendation**: Fix baseline section 2 table from "4,090" to "4,936".

### BUG-002: Baseline step 16 enum header says "30", table has 25 rows, actual count is 27

- **Severity**: LOW
- **Details**: Baseline section 14 header says "In 16_impl_context.schema.json (30 enum definitions)". The table immediately below lists exactly 25 rows. Recursive enumeration of the actual file yields 27 enums. The R2 fix (BUG-003) added a caveat note at the bottom of section 14 acknowledging the count is approximate, but did not fix the "30" in the header. The header, the table, and reality all disagree (30 vs 25 vs 27).
- **Evidence**: The 2 enums missing from the table are in `allOf/if` conditional blocks: (1) `.plan.spec_alignment.checklist[].implementation.actions[].allOf[0].if.type` = `["file_create", "file_edit"]`, and (2) `.review.findings[].allOf[0].if.severity` = `["blocking", "major"]`. These are subsets of parent enums used in conditional validation.
- **Recommendation**: Fix header from "30" to "27" (or "~27" if keeping approximate). Add the 2 missing allOf/if enum rows to the table. The caveat at the bottom of the section is adequate for the overall ~61 count but does not excuse the header being wrong by 3 in one direction and the table being wrong by 2 in the other.

### BUG-003: Baseline step 02 enum table also misses 2 allOf/if conditional enums

- **Severity**: LOW
- **Details**: The R2 caveat about allOf/if enums was written specifically about step 16 ("Step 16 may have 2 additional enums..."). However, step 02 (system_sketch) has the same issue: the baseline table lists 7 enums, but the actual recursive count is 9. The 2 missing enums are: (1) `connections[].allOf[0].if.trust_boundary` = `["partner", "public"]` and (2) `connections[].allOf[1].if.protocol` = `["event"]`. Both are in `allOf/if` blocks.
- **Evidence**: Recursive enum scan of `schema/02_system_sketch.schema.json` finds 9 enums. The baseline table under "In step schemas" lists only 7 for step 02. The R2 caveat mentions only step 16.
- **Impact**: The ~61 approximation in the summary is already qualified, but the step-specific tables are inaccurate. Total actual enum count is 65 (6 core + 32 non-core + 27 step-16), not ~61.
- **Recommendation**: Either (a) expand the R2 caveat to say "Step 02 and Step 16 each have 2 additional enums in allOf/if blocks not shown in the tables above" or (b) add the missing rows to both tables and update counts. Option (b) is cleaner.

### GAP-001: Plan P1-D says step 02a has "hardcoded environments" but 02a uses $ref to core

- **Severity**: LOW (minor inaccuracy, not a gap in scope)
- **Details**: Plan line 139 says "Step 02a (delivery_baseline) -- hardcoded environments: dev, ci, staging, prod". In reality, step 02a does not have an inline environment enum. It uses `$ref` to `core/collections.schema.json#environmentName`, which defines the enum `["dev", "ci", "staging", "prod"]`. The environments are technically hardcoded in the core definition, not in 02a itself. This is relevant to P1-D's genericity analysis because the fix point is core/collections (one place), not 02a.
- **Evidence**: `schema/02a_delivery_baseline.schema.json` contains zero inline `enum` arrays. It references `environmentName` via `$ref`. The actual enum is at `schema/core/collections.schema.json` in the `environmentName` definition.
- **Impact**: P1-D agent may waste time looking for an inline enum in 02a and not find it, or may miss that the fix for environment hardcoding is in core/collections (which would fix 02a and any other consumer simultaneously).
- **Recommendation**: Clarify P1-D scope: "Step 02a uses `$ref` to `core/collections#environmentName` which hardcodes `[dev, ci, staging, prod]` -- the enum is in core, not inline."

---

## INCOMPLETE FIXES

None. All R1 and R2 fixes were properly applied.

---

## CONTRADICTIONS

None found between agents or between plan and baseline.

---

## SCOPE OVERLAPS

No new scope overlaps found. The R1 AMBIG-003 fix properly assigned primary ownership (coverage_gaps to P1-C, canonical triad architecture to P1-A). Cross-references between agents are clear.

---

## HALLUCINATIONS

No hallucinated files, tools, functions, or features found. All references in the revised plan and baseline resolve to actual codebase artifacts.

---

## ACTIONABILITY ASSESSMENT

The 6 P1 agent prompts are specific and actionable. Each has:
- Clear exclusive scope boundaries
- Numbered questions with concrete expected outputs
- Baseline facts to prevent redundant discovery
- Constraints on what is in/out of scope

One minor note: P1-B (Descriptions) has the broadest scope (919 properties to inventory) but the questions are well-structured. The methodology instructions from R1 ASSUM-003 fix give clear counting rules.

---

## Summary

| Category | Count | Critical | High | Medium | Low |
|----------|-------|----------|------|--------|-----|
| BUGS | 3 | 0 | 0 | 1 | 2 |
| GAPS | 1 | 0 | 0 | 0 | 1 |
| INCOMPLETE FIXES | 0 | 0 | 0 | 0 | 0 |
| CONTRADICTIONS | 0 | 0 | 0 | 0 | 0 |
| SCOPE OVERLAPS | 0 | 0 | 0 | 0 | 0 |
| HALLUCINATIONS | 0 | 0 | 0 | 0 | 0 |
| **TOTAL** | **4** | **0** | **0** | **1** | **3** |

### Assessment

The plan and baseline are in strong shape after two rounds of review. The 4 remaining issues are all LOW or MEDIUM severity:

1. **BUG-001** (MEDIUM): Step schemas LOC subtotal of 4,090 is wrong (actual: 4,936). The overall total is correct, so this is an internal inconsistency in the breakdown table. Should be fixed to avoid confusing P1 agents.

2. **BUG-002** (LOW): Step 16 enum header says "30", table has 25 rows, actual is 27. The approximate caveat at the bottom partially addresses this, but the header itself is still wrong.

3. **BUG-003** (LOW): Step 02 has the same allOf/if enum issue as step 16 (2 missing from table), but the R2 caveat only mentions step 16.

4. **GAP-001** (LOW): P1-D scope says 02a has "hardcoded environments" but the enum is in core via $ref, not inline in 02a.

### Verdict

These findings are minor. BUG-001 should be fixed before P1 launch (it is a factual error agents may cite). BUG-002, BUG-003, and GAP-001 are nice-to-fix but will not impair P1 agent work given the existing caveats about approximate counts and the instruction for P1-A to recount enums.

### What Was Verified

To establish confidence in "no more issues," here is what was checked against the actual codebase:

- Schema file count: 24 in schema/ + 2 in canon/ = 26 -- MATCHES
- Total LOC: `wc -l` on all files = 6,072 -- MATCHES plan/baseline
- Canon LOC: 26 + 31 = 57 -- MATCHES (R2 fix)
- Core definitions: 6 atoms + 28 collections + 1 error + 9 canon = 44 -- MATCHES
- Schema registry entries: 29 -- MATCHES (R2 fix)
- $ref total: 448 schema-only, 452 including canon -- MATCHES (R2 fix)
- Downstream consumers: step 04 = 13, step 08 = 9 -- MATCHES (R2 fix)
- Common required fields: 10 -- MATCHES
- seed_refs/spec_refs_ingested presence: 19 step schemas -- MATCHES (R2 fix)
- generation_quality presence: 19 step schemas -- MATCHES (R1 fix)
- DRIFT_SENSITIVE_FIELDS: 6 fields matching plan -- MATCHES
- `spec_refs_ingested` tool consumers: 0 -- MATCHES (confirmed zero grep hits)
- `coverage_gaps` tool consumers: only step_12.py -- MATCHES
- `nested_order` consumer: seed_lint.py lines 263-266 -- MATCHES (R2 fix)
- Enum count: 65 actual vs ~61 approximate in plan -- ACCEPTABLE (plan has caveat for P1-A to recount)
- Web-service term count: 39 -- MATCHES
- Research roadmap: 10 ALIGN items, 6 covered by P1-F, 4 marked out-of-scope -- MATCHES (R2 fix)
