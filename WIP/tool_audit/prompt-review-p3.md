# Prompt Review: P3 -- Consolidation + WIP Cross-Check

Reviewed: 2026-03-18
Prompt file: `WIP/tool_audit/p3-prompt-consolidation.md`
Reviewed against: `p0-ground-truth-FINAL.md`, `p3-out-master-findings.md`, live codebase

---

## Claims Verified

| Claim | Source Line | Verified Against | Match? |
|-------|-----------|-----------------|--------|
| 830 tests collected, 830 passed | P3 line 54 | p0-ground-truth L13-14 | YES |
| 61 source files, 13,228 LOC | P3 line 55 | p0-ground-truth L15-16 | YES |
| 73 test files, 17,709 LOC | P3 line 56 | p0-ground-truth L17-18 | YES |
| 50 unit + 21 integration + 2 conftest | P3 line 56 | p0-ground-truth L19-21 | YES |
| 23 _load_* functions | P3 line 57 | p0-ground-truth L36 | YES |
| 21 step validator files, 21 DEEP_VALIDATORS | P3 line 58 | p0-ground-truth L34-35 | YES |
| 77 error codes (52 E, 25 W, 18 PROMOTABLE) | P3 line 59 | p0-ground-truth L38-41 | YES |
| 29 schema registry entries | P3 line 60 | p0-ground-truth L23 | YES |
| 22 steps, 25 CLI subcommands | P3 line 60 | p0-ground-truth L24, L31 | YES |
| 133 test fixture files, 22 fixture dirs | P3 line 61 | p0-ground-truth L29-30 | YES |
| P1 produces 7 agents | P3 line 17 | P1 output files (7 A-files) | PARTIAL -- see MUST_FIX #1 |
| P2 produces 1 agent | P3 line 17 | P2 output files (1 A-file) | PARTIAL -- see MUST_FIX #1 |
| 8 input files from P1+P2 | P3 line 21 | Actual on-disk files | NO -- 16 files exist (8 A + 8 B) |
| 10 WIP files | P3 line 34 | Glob of WIP/tools-tests-review-*.md | ACCEPTABLE -- 11 files exist but `goal.md` is not a findings file |

---

## Issues Found

### MUST_FIX

**MF-1: P3 prompt omits all Container B output files (8 files missing from input list)**

The prompt lists 8 P1/P2 input files, all from Container A:
- `p1-out-structure.md`, `p1-out-dry-validators.md`, etc.

But the actual P1/P2 execution produced **16 files** -- 8 from Container A and 8 from Container B (`-B` suffix):
- `p1-out-structure-B.md`
- `p1-out-dry-validators-B.md`
- `p1-out-soc-linters-B.md`
- `p1-out-hardcoding-B.md`
- `p1-out-test-quality-B.md`
- `p1-out-error-collection-B.md`
- `p1-out-gaps-regressions-B.md`
- `p2-out-research-alignment-B.md`

The actual P3 output (`p3-out-master-findings.md`) references both "A:" and "B:" findings extensively (e.g., "A:DV1, B:DV1; C:corroborated"), confirming the agent needed and used both containers' outputs. The prompt either:
- (a) Was written before the dual-container strategy was decided, or
- (b) Assumed the P3 agent would discover the B-files on its own.

Either way, this is a gap. The P3 agent had to improvise to find the B-files. If the prompt is reused, a less capable agent might only process Container A output.

**Fix:** Add all 8 B-files to the input list. Update "8 files from P1 + P2" to "16 files from P1 + P2 (8 per container)". Update Task 1 to describe the dual-container dedup strategy.

---

**MF-2: No instructions for dual-container reconciliation methodology**

The prompt says "When two findings describe the same issue, keep the version with the most detail" -- this was written for cross-agent dedup within a single container. The actual execution required a more sophisticated reconciliation:
- Cross-container agreement (A:DV1 + B:DV1 = corroborated)
- Cross-container disagreement with severity resolution (e.g., "A:SL2(high), B:SL2(medium); C:resolved to HIGH")
- Findings unique to one container (e.g., "A:G5; C:verified genuine, B missed entirely")

The P3 output invented the "A:, B:, C:" attribution system and the "corroborated / resolved to / verified genuine / B missed" vocabulary. None of this was in the prompt.

**Fix:** Add a "Dual-Container Reconciliation" section with explicit instructions for:
- When A and B agree: mark "corroborated"
- When A and B disagree on severity: state resolution rule (e.g., take higher severity unless evidence-based)
- When only one container found it: mark as verified/genuine with note on which missed
- Required source attribution format: `A:{id}, B:{id}; C:{resolution}`

---

**MF-3: P3 prompt says "Runs AFTER P1 (7 agents) and P2 (1 agent)" -- should be "P1 (7 agents x 2 containers) and P2 (1 agent x 2 containers)"**

The prerequisite section does not mention the dual-container execution model at all. This compounds MF-1.

**Fix:** Update Prerequisites to: "Runs AFTER P1 (7 agents x 2 containers = 14 output files) and P2 (1 agent x 2 containers = 2 output files) complete."

---

### SHOULD_FIX

**SF-1: No false-positive handling instructions**

The P3 output includes a "Dropped Findings" section with 6 false positives. The prompt has no instructions for identifying or documenting false positives. The agent had to invent the FALSE_POSITIVE / NOT_A_FINDING / EXCLUDED taxonomy.

**Fix:** Add to Task 1: "Identify false positives -- findings that are incorrect, not actionable, or positive confirmations. Document in a 'Dropped Findings' table with reason."

---

**SF-2: No instructions for Research Alignment section**

The P3 output includes a "Research Alignment Gaps" table (ALIGN-1 through ALIGN-10) that is structurally distinct from the AUDIT-NNN findings. The prompt's output template has no section for this. The agent created it based on P2 output structure.

**Fix:** Add a "Research Alignment Gaps" section to the Required Structure template, noting these are strategic items from P2 that inform P4 batch 5 but are not AUDIT-NNN findings.

---

**SF-3: Category enum not defined**

The prompt says each finding gets a "Category" but only gives examples in the output template: `[DRY|Structure|Testing|Hardcoding|Error|Gap|Alignment]`. The actual output used a much richer set: `REGISTRY_INCONSISTENCY`, `DRY_VIOLATION`, `SOC_BREACH`, `LAYER_VIOLATION`, `DOCUMENTATION`, `LLM_UNFRIENDLY`, `FORMAT_INCONSISTENCY`, `SCHEMA_VALIDATOR_MISMATCH`, `SPEC_MISUSE`, `BUG`, `COVERAGE_GAP`, `PROPAGATION_BUG`, `HARDCODED_VALUE`, `MISSING_JSON`, `R9_OVERLAP`, `CONFTEST_DUP`, `ALIGNMENT_GAP`, `ABSTRACTION_MISSING`, `PACKAGING`, `REDUNDANCY`, `RESOURCE_LEAK`, `CODE_HEALTH`, `EDGE_CASE`, `DESIGN_NOTE`, `OBSERVABILITY`, `ROBUSTNESS`, `CI_GAP`, `TEST_METHODOLOGY`, `TEST_EFFICIENCY`, `TOKEN_WASTE`, `MAGIC_NUMBER`, `STRUCTURE`, `ASSUMPTION`.

**Fix:** Either define the full category enum or explicitly state "Use descriptive UPPER_SNAKE_CASE categories. Examples: DRY_VIOLATION, BUG, COVERAGE_GAP, HARDCODED_VALUE, etc."

---

**SF-4: WIP cross-check granularity is underspecified**

The prompt says "Match at the individual finding level. A WIP finding is a distinct recommendation or observation, typically one bullet or paragraph." But the WIP files have varying structures -- some use structured IDs (e.g., WIP:validators-dry C5), some use prose paragraphs, some use numbered lists. The actual P3 output matched at a coarser level (file-level summary rather than individual bullet).

The WIP Cross-Check Report in the output shows file-level totals (e.g., "findings-hardcoded.md: 29 items, 12 CONFIRMED") rather than individual item matching. The prompt says individual matching but the output shows aggregate matching. This ambiguity was resolved by the agent at execution time.

**Fix:** Clarify whether individual-item matching is required in the WIP Cross-Check Report table, or if file-level aggregation is acceptable. If individual: the report will be very long (113 rows). If aggregate: say so explicitly.

---

**SF-5: Target length "300-400 lines" was significantly exceeded**

The P3 output is 705 lines, nearly double the upper bound. The target was too low given 69 findings + WIP cross-check + research alignment gaps.

**Fix:** Update target length to "500-700 lines" or remove the target and say "Concise but thorough."

---

### MINOR

**MN-1: WIP file count says "10 files" -- actually 10 findings-relevant files (correct) but the goal.md file exists too**

The glob shows 11 `WIP/tools-tests-review-*.md` files. The prompt correctly excludes `tools-tests-review-goal.md` from the input list since it is not a findings file. However, the "(10 files from prior review cycle)" header could confuse an agent that discovers the 11th file.

**Fix:** Add a note: "Note: `tools-tests-review-goal.md` is a planning document, not findings -- exclude it."

---

**MN-2: Output template shows "From P1/P2: N new, N deduplicated" but actual output needed richer stats**

The actual output shows: "From P1/P2: 68 unique after deduplication (from 76 A + 73 B raw findings)". The template doesn't anticipate dual-container raw counts.

**Fix:** Update template to match dual-container format.

---

**MN-3: The "WIP Status" field in the findings template shows limited options**

Template shows: `CONFIRMED (WIP ref) | NEW | n/a`. The actual output used `CONFIRMED`, `NEW`, and for WIP-sourced additions `MISSED_BY_AUDIT -- added from WIP:xxx`. The `n/a` option was never used; `NEW` replaced it.

**Fix:** Update template options to: `CONFIRMED (WIP ref) | NEW | MISSED_BY_AUDIT -- added from WIP:xxx`

---

## Verdict: APPROVED_WITH_FIXES

The prompt successfully guided the P3 agent to produce a high-quality, comprehensive master findings document. However, the omission of Container B files from the input list (MF-1) is a significant gap that could cause a future execution to miss half the input data. The lack of dual-container reconciliation instructions (MF-2) forced the agent to invent methodology on the fly. Both must be fixed before reuse.

The 3 MUST_FIX items are all related to the same root cause: the prompt was written for a single-container execution model but the actual pipeline used dual containers. The SHOULD_FIX items address output format gaps that the agent handled well but shouldn't have to improvise.
