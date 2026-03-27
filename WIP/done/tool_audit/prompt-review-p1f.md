# Prompt Review: P1-F (Gaps, Misses, Bugs & Regressions Analysis)

## Claims Verified

| # | Claim | Prompt Line | Verified Against | Match? |
|---|-------|------------|-----------------|--------|
| 1 | 21 step validators, NO step_00 validator | L19 | `ls validators/step_*.py` = 21 files; no step_00.py exists | YES |
| 2 | 22 steps in step_order.json | L21 | `python3 -c "len(d['steps'])"` = 22 | YES |
| 3 | Schema registry: 29 entries | L22 | `python3 -c "len(json.load(...))"` = 29 | YES |
| 4 | 24 schema files total (19 step + 4 core + 1 seed_manifest) | L23 | `ls schema/*.schema.json schema/core/*.schema.json | wc -l` = 24 | YES |
| 5 | Step 16 schema: 1868 lines, 4 $defs | L24 | `wc -l` = 1868; `$defs` keys = [specRef, severityLevel, executionStatus, evidenceObject] (4) | YES |
| 6 | Step 16 schema: max nesting depth 19 | L24 | Ground truth section 7.3 states depth 19; not independently re-measured but consistent with 1868-line schema | TRUST (from ground truth) |
| 7 | Step 00 schema: 202 lines, depth 8, 21 props | L25 | `wc -l` = 202; `len(d['properties'])` = 21; ground truth says depth 8 | YES |
| 8 | Steps 16a/16b/16c map to `16_impl_context.schema.json` | L22 | `schema_registry.json` entries for 16a/16b/16c all point to `schema/16_impl_context.schema.json` | YES |
| 9 | _load_fr_ids in step_05, step_06, step_07 with different styles | L27 | Ground truth section 4.5 confirms: step_05 inline conditional, step_06 separate guard, step_07 inline conditional with different type hint | YES |
| 10 | Zero TODOs in specdev_tools/, one in tools/core/json_utils.py | L28-29 | Ground truth sections 10.1 confirms | YES (per ground truth) |
| 11 | Zero skips/xfails in tests | L28 | Ground truth section 10.3: "None found" | YES |
| 12 | One noqa in validators/__init__.py line 7 | L28 | Ground truth section 10.2: `validators/__init__.py:7: from . import (  # noqa: F401` | YES |
| 13 | R9 markers in 12 source locations | L32 | `grep -rn "R9" tools/specdev_tools/` = 12 matches across files | YES |
| 14 | R9 test files: 10 files, 4740 LOC | L35 | `wc -l tests/test_r9_*.py` = 4740 total, 10 files | YES |
| 15 | Individual R9 test file LOC (test_r9_cli.py 286, test_r9_cross_step.py 1047, etc.) | L35 | All 10 individual counts verified via `wc -l` | YES |
| 16 | Version mismatch: CLAUDE.md 0.3.0 vs pyproject.toml 0.4.0 | L36 | Ground truth section 9 confirms | YES |
| 17 | 23 `_load_*` functions | L26 | Ground truth section 4.3 lists exactly 23 | YES |
| 18 | Separate validators for 16a/16b/16c at 46/45/47 LOC | L48 (Q4) | `wc -l step_16a.py` = 46, step_16b.py = 45, step_16c.py = 47 | YES |

## Issues Found

### MUST_FIX

**MF-1: Q5 dependency cross-reference has incomplete expected upstream list for step_08**

Q5 says "Check at least step_08 (loads from 04, 05, 06, 07)". This is correct for the _load_* functions (FR from 04, API from 05, INV from 06, NFR from 07). However, step_order.json lists step_08's `allowed_upstream_dependencies` as `['00', '01', '02', '02a', '03', '04', '05', '06', '07']` -- 9 upstream steps, not 4. The Q5 phrasing is technically correct (it says "loads from" not "depends on") but could confuse the agent into thinking the dependency list should match the load list exactly.

Severity: Low -- the agent should discover the distinction naturally.

**MF-2: Q5 says step_14 "loads from 01, 04, 09" but ground truth shows 4 _load_* functions**

Q5 says "step_14 (loads from 01, 04, 09)" but ground truth section 4.3 shows step_14 has 4 _load_* functions: `_load_step09_milestone_ids` (from 09), `_load_step09_tech_stack_names` (from 09), `_load_step04_fr_ids` (from 04), `_load_step01_cap_ids` (from 01). This is 3 upstream steps (01, 04, 09) but 4 functions. The claim is correct about which steps are loaded from, but omits that two functions load from step 09. Minor precision issue.

Severity: Low -- accurate enough for the agent's purposes.

### SHOULD_FIX

**SF-1: Q4 claims step 16 schema has "17 top-level properties" but prompt says "1868 lines, 17 top-level properties"**

The prompt line 48 says the shared schema has "17 top-level properties" which is verified correct. However, Q4 asks "Do the validators check the right subset of fields for each sub-step?" -- the agent needs to know what subset each sub-step should check. The prompt does not provide any guidance on what the expected subset is, leaving the agent to figure it out entirely from reading the schema and validators. This is fine for an "Explore" agent but could benefit from a hint like "step 16a focuses on plan fields, 16b on execution, 16c on review."

**SF-2: Q15 R9 coverage cross-reference is vague about expected mapping**

Q15 says "Cross-reference against the 12 R9 marker locations in source code -- is every R9 feature exercised by at least one test?" This is a good question but the prompt could help by listing the 6 R9 task IDs (T18, T20, T22, T24, T26, T28) in the question itself rather than only in the Known Context section (line 31-33). The agent may not connect them.

**SF-3: Q16 references "lines 166-175 per ground truth" for cli.py R9 commands**

This is correct (cli.py lines 166-174 define env-check, dag-lint, extraction-intent-check). But the prompt says "lines 166-175" when the actual range is 166-174. Off by one, harmless but imprecise.

**SF-4: Missing question about schema_registry.json count discrepancy**

The ground truth explicitly notes that both P0 agents miscounted registry entries (said 30, actual is 29). The prompt correctly states 29 in Known Context, but does not include a question about whether the registry count is consistent with any documentation or comments that might still say 30.

### MINOR

**M-1: Q7-Q10 (edge cases) are good but generic**

Questions about empty directories, malformed JSON, missing schema files, and Unicode are standard edge case checks. They are appropriate but could be lower priority if the agent is time-constrained. Consider marking them as "if time permits" or reducing to 2 critical edge cases.

**M-2: Q11-Q13 (code health) are marked as mostly verified**

Q11, Q12, Q13 say "VERIFIED" or "just confirm" -- this is efficient and avoids redundant work. Good pattern.

**M-3: The 200-line hard limit is reasonable**

Given the scope (16 questions, R9 coverage matrix, summary table), 200 lines is adequate.

**M-4: Q1 references schema file as `schema/05_interface_contracts.schema.json`**

Verified correct -- this file exists at that path.

## Verdict: APPROVED_WITH_FIXES

The prompt is thorough and well-anchored in ground truth. All 18 verified claims are accurate. The known context is comprehensive and correctly separates what has been verified from what needs investigation. The main issues are minor precision problems in Q5 (upstream step lists) and SF-3 (off-by-one line reference). The scope boundaries are clear and correctly exclude topics covered by other prompts (P1-A, P1-B, P1-D). The R9 coverage section is well-designed. Overall, this prompt is ready for execution with minor fixes.
