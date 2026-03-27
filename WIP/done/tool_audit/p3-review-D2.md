# P3 Review (Agent D2)

## Completeness Check
- Test Quality findings in A: 9, in B: 9 → in P3: 9 (T1-T9 all accounted; A:T6 dropped as FALSE_POSITIVE per B:T7 confirmation; B:T8 json_utils added as AUDIT-032; B:T9 integration count low not given own AUDIT ID but partially folded into coverage discussion)
- Error Collection findings in A: 8, in B: 8 → in P3: 10 (E1-E8 from both runs mapped; A:E6 correctly omitted as PASS; B:E6 correctly omitted as PASS)
- Gaps/Regressions findings in A: 7, in B: 8 → in P3: 8 (G1-G7 from A all present; B:G3 merged into AUDIT-001; B:G5/G7/G8 correctly dropped as positive confirmations)
- Research Alignment findings in A: 10, in B: 9 → in P3: 10 (all 10 ALIGN items in P3 table; B:ALIGNMENT-7 enum-vs-freeform captured as AUDIT-042)
- Total coverage assessment: COMPLETE (with 2 minor omissions noted below in SHOULD_FIX)

## Verification Results (5+ MEDIUM+ checked)
| AUDIT ID | Claim | Verified? | Evidence |
|----------|-------|-----------|----------|
| AUDIT-001 | E141, E142, E320 not registered in errors.py | YES | `grep` for E141/E142/E320 in errors.py returns zero matches. Confirmed at step_14.py:79 (E142), step_14.py:126 (E141), step_13.py:32,40,50 (E320). |
| AUDIT-011 | hallucination_lint uses `n["id"]` instead of `n["nfr_id"]` | YES | hallucination_lint.py:277 uses `n["id"]`. Schema 07_nfrs.schema.json line 30 defines `nfr_id` as the key within nfrs array items. step_08.py uses `nfr.get("nfr_id")`. Genuine bug. |
| AUDIT-014 | W->E promotion only in validate_dir, not validate_file | YES | validate.py:267-289 contains promotion logic. validate_file() (lines 86-178) has no promotion code. Confirmed. |
| AUDIT-038 | W550 reused with different semantics | YES | seed_lint.py:253 emits `W550 UNDECLARED_SEED`. errors.py registers W550 as `SEMANTIC_COVERAGE_SKIP`. Different meanings sharing one code. |
| AUDIT-050 | governance.py file handle leak | YES | governance.py:11 uses `json.load(open(p, "r", encoding="utf-8"))` without `with` statement or explicit close. Confirmed resource leak. |
| AUDIT-005 | Layer violation: validation/ imports from generation/ | YES | validate.py:20 imports `run_prompt_schema_sync` from `..generation.prompt_schema_sync`. Confirmed. |

## File:Line Spot-Checks (5+)
| AUDIT ID | Referenced Location | Exists? | Content Matches? |
|----------|-------------------|---------|-----------------|
| AUDIT-001 | validators/step_14.py:79 | YES | Line 79: `f"E142 TECH_STACK_MISMATCH: roadmap uses tech '{name}'..."` -- matches claim |
| AUDIT-001 | validators/step_13.py:32 | YES | Line 32: `f"E320 Extension '{ext_id}' required_schema_sections[{j}] ..."` -- matches claim |
| AUDIT-011 | hallucination_lint.py:277 | YES | Line 277: `{n["id"] for n in data.get("nfrs", []) if isinstance(n, dict) and "id" in n}` -- uses `n["id"]` not `n["nfr_id"]`, matches claim |
| AUDIT-050 | governance.py:12 | OFFSET_BY_1 | Line 11 (not 12): `json.load(open(p, "r", encoding="utf-8"))` -- content matches, line number off by 1 |
| AUDIT-038 | seed_lint.py:253 | YES | Line 253: `f"W550 UNDECLARED_SEED on-disk seed '{fn}' not declared..."` -- matches claim |
| AUDIT-005 | validate.py:20 | YES | Line 20: `from ..generation.prompt_schema_sync import run_prompt_schema_sync` -- matches claim |

## WIP Cross-Check Verification

### WIP:findings-test-quality.md
P3 correctly maps key WIP findings:
- B3-01 (parametrization gap) -- not given own AUDIT ID but this is a methodology recommendation, not a code-level finding. Defensible omission.
- B4-02 (conftest duplication) -- mapped to AUDIT-028. Correct.
- B4-03 (fixture caching) -- mapped to AUDIT-060. Correct.
- B5-02 (7 modules with zero test files) -- mapped to AUDIT-013, AUDIT-031. Correct.
- B7-01 (test_no_numeric_suffix_collision has no assertion) -- noted in P3 Contradiction Details item 2 as "valid but extremely minor." Correctly handled.

**Gap found**: B4-01 (all conftest fixtures use default function scope, no session scoping) is a MEDIUM finding in the WIP that has no corresponding AUDIT entry. This is a test quality improvement that could save setup overhead across 830 tests.

### WIP:findings-test-structure.md
P3 correctly maps key WIP findings:
- B2 (R9 test duplication) -- mapped to AUDIT-027. P3 correctly notes "240+ of 246 R9 tests are actually unique" which matches B2's detailed analysis.
- B6 (no test markers) -- mapped to AUDIT-067. Correct.
- B8 (spec/ as test data) -- mapped to AUDIT-010 (test_step_11.py). Correct.
- E4 (conftest duplication + helper duplication) -- conftest mapped to AUDIT-028. The broader helper duplication (_make_repo, _write_spec patterns across 4-5 files each) has no dedicated AUDIT entry but is a lower-severity organizational issue.

### WIP:findings-pipeline.md
P3 correctly maps key WIP findings:
- D1 (CI no test job) -- mapped to AUDIT-067. Correct.
- D2 (no property-based testing) -- mapped to AUDIT-068. Correct.

**Gap found**: D5 (declarative rules vs imperative Python for linters, MEDIUM) and D6 (no golden file/snapshot testing, MEDIUM) are not represented in P3 findings at all. These are methodology/architecture recommendations, so their omission is partially defensible, but they should at minimum be noted in the research alignment or cross-check report.

### WIP:findings-validation-arch.md
P3 correctly maps key WIP findings:
- C2 (make_error/SpecError unused) -- mapped to AUDIT-007. Correct.
- C2 (E141/E142 unregistered) -- mapped to AUDIT-001. Correct.
- C2 (E310 name mismatch) -- mapped to AUDIT-039. Correct.
- C3 (W550 reused) -- mapped to AUDIT-038. Correct.
- C4 (step_01/step_02 re-run schema) -- mapped to AUDIT-009. Correct.
- C7 (validate_file does not apply promotion) -- mapped to AUDIT-014. Correct.
- E2 (duplicate-ID pattern in 11 validators) -- mapped to AUDIT-041. Correct.
- E6 (linter pattern duplication ~143 LOC) -- mapped to AUDIT-012 and AUDIT-040. Correct.

**Observation**: C4 finding about seed_lint.py calling validate_file() recursively (creating nested validation) has no dedicated AUDIT entry. This is a MODERATE finding in the WIP. It is architecturally notable but relatively low impact.

## Issues Found

### MUST_FIX
None.

### SHOULD_FIX
1. **AUDIT-050 line number is off by 1**: P3 states governance.py:12 but the file handle leak is at line 11 (`json.load(open(p, "r", encoding="utf-8"))`). Minor inaccuracy in reference.
2. **Missing WIP findings D5 and D6 from pipeline analysis**: WIP:findings-pipeline.md contains two MEDIUM-severity GAP findings (D5: declarative rules for linters, D6: golden file/snapshot testing) that are not represented anywhere in P3. These are methodology recommendations rather than code bugs, but the WIP Cross-Check Report table for pipeline.md claims "10" total items with only "3 CONFIRMED" and "1 CONTRADICTED" and "1 MISSED_BY_AUDIT" = 6 accounted. The remaining 4 items (D3-PASS, D4-PARTIAL, D5-GAP, D6-GAP) need clearer disposition in the cross-check -- particularly D5 and D6 which are actionable GAP findings, not PASS records.
3. **Missing WIP finding B4-01 (fixture scope)**: WIP:findings-test-quality.md B4-01 is a MEDIUM finding about conftest fixtures lacking session scoping. Not captured in P3. Should at minimum be noted as an INFO or folded into AUDIT-028.
4. **B:T9 (low integration test count) dropped without explanation**: Container B's T9 finding about low integration test count relative to source complexity has no AUDIT entry and no explicit "dropped" notation. Should be in the Dropped Findings table if intentionally excluded.

### MINOR
1. **AUDIT-032 LOC discrepancy**: P3 says json_utils.py is 345 LOC. Ground truth (from Agent B source) says 499 LOC per `wc -l`, though the ground truth file inventory does not list this file (it is outside specdev_tools/). The P1-B source says 345 LOC. Minor inconsistency -- either the line counts differ or the two are measuring differently.
2. **P3 summary says "76 A + 73 B raw findings"**: Cross-reference report says "Container A total findings: 76, Container B total findings: 73." This is consistent. However, several of these are INFO/PASS records (B:G5, G7, G8 are positive confirmations), so the "raw findings" label is slightly misleading since some are non-findings.
3. **AUDIT-004 LOC count**: P3 says validate.py is 537 LOC. Ground truth confirms 537 LOC. Consistent.
4. **WIP:validation-arch C4 finding about seed_lint recursive validation**: No AUDIT entry. Very low impact but architecturally noteworthy. Could be noted as INFO in future revisions.

## Verdict
APPROVED_WITH_FIXES

The P3 master findings document is comprehensive and well-structured. The 68 findings are properly numbered (AUDIT-001 through AUDIT-068) with no gaps in sequence. All CRITICAL and HIGH findings are accurately documented and verified against the live codebase. The Research Alignment table correctly captures all 10 gap areas from both P2 runs. The severity resolution methodology (using cross-reference C's recommendations) is sound.

The SHOULD_FIX items are:
- 2 MEDIUM WIP pipeline findings (D5 declarative rules, D6 golden file testing) need explicit disposition in the WIP cross-check
- 1 line number correction (AUDIT-050: governance.py:11, not :12)
- 1 missing WIP finding (B4-01 fixture scope) needs disposition
- 1 dropped finding (B:T9) needs explicit notation

None of these affect the integrity of the 68 findings already documented. The core findings, severity assignments, recommendations, and ground truth alignment are all sound.
