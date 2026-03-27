# P0 Plan Review — Round 2

**Date**: 2026-03-19
**Reviewer**: Claude Opus 4.6 (automated second-pass review)
**Scope**: Verify all 26 R1 findings were addressed; find residual bugs, gaps, and regressions

---

## INCOMPLETE FIXES (R1 findings not fully addressed)

### IFIX-001: Canon LOC still wrong — says 59, actual is 57
- **Severity**: LOW
- **R1 Finding**: BUG-004 asked for LOC clarification. The fix added "(6,015 schema/ + 59 canon/)" to the plan summary.
- **Problem**: The canon LOC figure of 59 is wrong. Actual: `canon/aliases.schema.json` = 26 LOC, `canon/kind.schema.json` = 31 LOC, total = 57 LOC. This means total LOC is 6,072, not 6,074.
- **Evidence**: `wc -l canon/aliases.schema.json canon/kind.schema.json` returns 26 + 31 = 57.
- **Impact**: P1 agents will cite wrong totals. Minor but propagates.
- **Recommendation**: Fix plan summary to "(6,015 schema/ + 57 canon/)" and total to 6,072. Fix baseline summary table similarly.

---

## BUGS (new or residual)

### BUG-001: Baseline $ref total says 468, table sums to 448
- **Severity**: HIGH
- **Details**: Baseline section 4 summary line says "**TOTAL** | **468**" but summing every row in the per-file table yields exactly 448. This is the same class of header-vs-table inconsistency that R1 caught for atoms/collections counts (BUG-001/002/003), but this instance was NOT caught in R1.
- **Evidence**: Per-file counts verified against actual files — all 24 individual row counts match reality. Their sum: 23+22+20+18+14+20+21+17+17+16+21+17+17+17+14+14+27+17+65+11+0+14+25+1 = 448. Including canon/ (4 more $ref) would give 452, still not 468.
- **Impact**: P1-A and P1-F agents use this total as a baseline metric. 468 overstates by 20.
- **Recommendation**: Fix baseline summary to "**TOTAL** | **448**" (schema/ only) or "**452**" (including canon/). Update plan summary line accordingly.

### BUG-002: Baseline schema registry says 31 entries, actual is 29
- **Severity**: MEDIUM
- **Details**: Baseline section 10 opens with "**31 entries** mapping URI to file path" but the table that follows lists exactly 29 entries. Actual `tools/schema_registry.json` has 29 keys, confirmed programmatically.
- **Evidence**: `python3 -c "import json; print(len(json.load(open('tools/schema_registry.json'))))"` returns 29. Counting the 29 rows in the baseline table confirms 29.
- **Impact**: P1-E agent ("Registry completeness: 31 entries. Are all 26 schema files registered?") will start from wrong count. The question should reference 29, not 31.
- **Recommendation**: Fix baseline to "29 entries". Fix plan P1-E scope to match.

### BUG-003: Baseline enum count says 61, actual is 65
- **Severity**: MEDIUM
- **Details**: Baseline section 14 summary says "**Total unique enum definitions**: 61 (6 core + 30 step 00-15 + 25 step 16)". Actual counts: 6 core + 31 step 00-15 (including seed_manifest's 1) + 27 step 16 = 64. Or if seed_manifest is counted separately: 6 core + 30 step 00-15 + 1 seed_manifest + 27 step 16 = 64. The baseline table for step 16 lists 25 entries but misses 2 enums inside `allOf/if` conditional blocks (action type in `if` and finding severity in `if`). The step 00-15 table appears to count seed_manifest's `source_type` enum as part of the 30, but also misses at least one from step 00-15 schemas.
- **Evidence**: Automated enum counting via recursive JSON traversal: step 16 has 27 enum arrays, not 25. Steps 00-15 have 31 (including seed_manifest), not 30.
- **Impact**: P1-A agents tasked with consolidating enums will have an incomplete inventory.
- **Recommendation**: Fix total to actual count. Add the 2 missing step 16 enums to the baseline table (both are conditional `if/allOf` blocks that duplicate parent enum subsets). Re-count step 00-15 enums.

### BUG-004: Baseline downstream_consumers counts are wrong
- **Severity**: LOW
- **Details**: Baseline section 12 states "Step 04 (FRs) has the most consumers: 14 steps" and "Step 08 (Fixtures) feeds 10 steps". Actual `downstream_consumers` in `step_order.json`: Step 04 has 13 consumers (not 14), Step 08 has 9 consumers (not 10).
- **Evidence**: `step_order.json` key `"04"` maps to array of 13 elements: `["05","06","07","08","09","11","13","13a","14","15","16","16a","16c"]`. Key `"08"` maps to 9 elements: `["09","13","13a","14","15","16","16a","16b","16c"]`.
- **Impact**: P1-E agents rely on these for structural analysis. Minor but sloppy.
- **Recommendation**: Fix to "13 steps" and "9 steps" respectively.

### BUG-005: Baseline section 7 double-counts seed_refs/spec_refs_ingested
- **Severity**: MEDIUM
- **Details**: Baseline section 7 says seed_refs and spec_refs_ingested are each "Present in: ALL 19 step schemas + `16_impl_context` = 20 schemas total." But `16_impl_context` IS one of the 19 step schemas — it is not a separate, additional schema. The correct count is 19, not 20. This error was present in the original baseline and was NOT caught or fixed by R1 (R1's BUG-005 only fixed the generation_quality count from 20 to 19, but did not address the identical error in section 7 for seed_refs/spec_refs_ingested).
- **Evidence**: There are exactly 19 step schema files (00 through 16, including 02a and 13a). `16_impl_context.schema.json` is step 16's schema. `seed_manifest.schema.json` does NOT have `seed_refs` or `spec_refs_ingested`. Verified: `grep -l seed_refs schema/*.schema.json | wc -l` returns 19.
- **Recommendation**: Fix section 7 from "ALL 19 step schemas + `16_impl_context` = 20 schemas total" to "ALL 19 step schemas (00 through 16, including 02a and 13a)." Apply same fix to section 8 which says "Every step schema (19 files + 16_impl_context = 20 total)".

---

## GAPS

### GAP-001: P1-F scope omits 4 of 10 ALIGN items (ALIGN-3, ALIGN-7, ALIGN-8, ALIGN-9)
- **Severity**: MEDIUM
- **Details**: P1-F "Research Alignment" explicitly lists ALIGN-1, ALIGN-2, ALIGN-4, ALIGN-5, ALIGN-6, ALIGN-10 for assessment. It omits ALIGN-3 (structured errors), ALIGN-7 (--json output), ALIGN-8 (MCP tool), and ALIGN-9 (pre-commit hooks). While ALIGN-3/7/8/9 are more tool-focused than schema-focused, P1-F's charter is to "assess current schema state against each ALIGN-N gap" and "identify NEW research gaps not in the roadmap." The agent should at least acknowledge these 4 exist and note they are out of scope for schema audit.
- **Evidence**: Plan line 186-192 lists only 6 of 10 ALIGN items. The research roadmap has 10 items total.
- **Recommendation**: Add a note to P1-F scope: "ALIGN-3, ALIGN-7, ALIGN-8, ALIGN-9 are tool/CLI-focused and not directly schema-related — acknowledge but mark as out-of-scope for this audit."

### GAP-002: P1-C asks if nested_order is dead, but it IS consumed by seed_lint.py
- **Severity**: MEDIUM
- **Details**: Plan P1-C scope line 108 asks "`nested_order` — is this used anywhere or dead?" The answer is already available: `seed_lint.py` lines 263-266 iterate `nested_order` layers to validate that referenced `seed_ids` exist. This is a baseline fact that should be provided to agents, same as was done for `docs_policy` (GAP-007 fix in R1). Without this, a P1-C agent will waste tokens re-discovering what is already known.
- **Evidence**: `tools/specdev_tools/validation/seed_lint.py` lines 263-266: `for layer in manifest.get("nested_order", []):` validates seed_id references.
- **Recommendation**: Add baseline fact to P1-C scope: "`nested_order` IS consumed by `seed_lint.py` (validates that referenced `seed_ids` exist in the seed registry). The question is whether its structure/location is optimal, not whether it is dead."

### GAP-003: P1-C asks about step_order.json fields but lacks baseline on allowed_upstream_dependencies consumers
- **Severity**: LOW
- **Details**: Plan P1-C scope asks "allowed_upstream_dependencies — is this consumed by any validator?" The answer is yes, by 5 different tool files: `dependency_order_lint.py`, `dag_lint.py`, `extraction_intent_check.py`, `hallucination_lint.py`, and `cli.py`. This should be provided as a baseline fact to prevent agents from wasting tokens on discovery.
- **Evidence**: `grep -r "allowed_upstream_dependencies" tools/specdev_tools/` returns hits in all 5 files listed above.
- **Recommendation**: Add baseline fact: "`allowed_upstream_dependencies` is actively consumed by 5 tool modules (dependency_order_lint, dag_lint, extraction_intent_check, hallucination_lint, cli). It is NOT dead. The question is whether it is redundant with `downstream_consumers`."

### GAP-004: No agent scope covers $schema property on spec data files
- **Severity**: LOW
- **Details**: The actual spec data files (e.g., `spec/common/seed_manifest.json`) include a `$schema` property pointing to their schema URI. If the URI scheme changes (ALIGN-2) or schemas are moved (P1-E reorganization), these `$schema` references in data files must also be updated. No P1 agent scope mentions checking data files for `$schema` references.
- **Evidence**: `spec/common/seed_manifest.json` line 2: `"$schema": "https://specdev.local/schema/seed_manifest.schema.json"`. All spec files in `spec/` likely have similar `$schema` references.
- **Recommendation**: P1-E should note: "Any schema URI changes require updating `$schema` properties in all spec data files under `spec/`."

---

## ASSUMPTIONS

### ASSUM-001: Description coverage numbers are methodology-dependent and not fully reliable
- **Severity**: LOW
- **Details**: R1's ASSUM-003 asked for counting methodology instructions, which were added to P1-F (line 202). However, the baseline's own numbers (56 with / 863 without / 6.1%) were generated with an unknown methodology and vary significantly depending on recursion strategy. An independent count using a straightforward recursive approach yields 55 with / 758 without / 6.8%. The discrepancy (919 vs 813 total properties) suggests the baseline counted something differently (possibly including `allOf`/`oneOf`/`if` branches, or `patternProperties` keys). The plan correctly tells P1-B to produce its own inventory, but agents should be warned the baseline totals are approximate.
- **Evidence**: Independent count: 55 descriptions found, 758 properties without descriptions. Largest discrepancy in step 16: baseline says 12 with / 273 without = 285 total; independent count says 11 with / 185 without = 196 total.
- **Recommendation**: Add caveat to baseline section 5 summary: "These counts are approximate. P1-B should perform its own definitive count using the methodology specified in the plan." Alternatively, document the exact counting methodology used in P0.

---

## REGRESSIONS

None found. The R1 fixes were cleanly applied without introducing new problems in the plan structure or agent scope definitions.

---

## HALLUCINATIONS

None found. All file paths, tool names, function references, and feature claims in the updated plan and baseline were verified against the actual codebase.

---

## AMBIGUITIES

### AMBIG-001: Plan P1-E says "Registry completeness: 31 entries" but actual registry has 29
- **Severity**: LOW (cascading from BUG-002)
- **Details**: The P1-E scope question "Registry completeness: 31 entries. Are all 26 schema files registered? Are there orphan entries?" uses the wrong count. With 29 entries mapping to 26 unique files (since 16a, 16b, 16c are aliases to 16), the question should use 29.
- **Recommendation**: Fix to "29 entries" in P1-E scope.

---

## MISSES

### MISS-001: Plan does not tell agents which step_order.json fields are actively consumed
- **Severity**: MEDIUM
- **Details**: P1-C asks agents to trace consumers for `allowed_upstream_dependencies`, `coverage_thresholds`, and `status_write_exemptions`. The answers are all knowable now and should be provided as baseline facts rather than requiring agent re-discovery:
  - `allowed_upstream_dependencies`: consumed by 5 modules (dependency_order_lint, dag_lint, extraction_intent_check, hallucination_lint, cli)
  - `coverage_thresholds`: consumed by 2 modules (matrix.py, cli.py)
  - `status_write_exemptions`: consumed by 1 module (forward_replay_check.py)
  - `downstream_consumers`: consumed by prompt-context command (per the `_notes` in step_order.json itself)
  All four are actively used. None are dead.
- **Evidence**: grep results against `tools/specdev_tools/` for each field name.
- **Recommendation**: Add these baseline facts to P1-C scope to eliminate redundant discovery work.

---

## Summary

| Category | Count | Critical | High | Medium | Low |
|----------|-------|----------|------|--------|-----|
| INCOMPLETE FIXES | 1 | 0 | 0 | 0 | 1 |
| BUGS | 5 | 0 | 1 | 3 | 1 |
| GAPS | 4 | 0 | 0 | 2 | 2 |
| ASSUMPTIONS | 1 | 0 | 0 | 0 | 1 |
| REGRESSIONS | 0 | 0 | 0 | 0 | 0 |
| HALLUCINATIONS | 0 | 0 | 0 | 0 | 0 |
| AMBIGUITIES | 1 | 0 | 0 | 0 | 1 |
| MISSES | 1 | 0 | 0 | 1 | 0 |
| **TOTAL** | **13** | **0** | **1** | **6** | **6** |

### Assessment

The R1 fixes were well-applied and the plan is substantially improved. The remaining issues fall into two categories:

1. **Baseline data quality (BUG-001 through BUG-005, IFIX-001)**: The baseline has 6 remaining numeric inaccuracies — all following the same pattern R1 identified: summary headers/counts disagree with the detailed tables or actual data. The tables themselves are accurate; only the aggregated counts are wrong. This is a systematic issue: whoever generated the baseline computed accurate per-item data but made errors in the roll-up summaries.

2. **Agent efficiency (GAP-002, GAP-003, MISS-001)**: Several fields the plan asks agents to investigate for "is this dead?" already have known answers from this review. Providing these as baseline facts would save significant agent tokens and prevent redundant discovery.

### Top Actions (before launching P1)

1. **Fix 6 numeric errors** in baseline: $ref total (448 not 468), registry entries (29 not 31), enum count (recount), downstream consumer counts (13/9 not 14/10), seed_refs/spec_refs_ingested presence (19 not 20), canon LOC (57 not 59)
2. **Add baseline facts for step_order.json field consumers** to P1-C scope (all 4 fields are actively consumed)
3. **Add baseline fact for nested_order** to P1-C scope (consumed by seed_lint.py)
4. **Add caveat** to description coverage numbers (methodology-dependent, approximate)
