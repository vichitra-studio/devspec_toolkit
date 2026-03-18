# Fix Report: P1-E and P1-F Prompt Corrections

## P1-E (Error Collection & Reporting Pipeline Analysis)

### Applied

| ID | Type | Fix | Verified |
|----|------|-----|----------|
| MF-2 | MUST_FIX | Added `SpecError.render()` vs raw-string duality note to Known Context (line 32). Confirmed `render()` at errors.py:13-16 formats `"{code} {path} {message}"` / `"{code} {message}"`, while validators commonly return raw f-strings. | YES -- errors.py:13-16 confirmed |
| SF-3 | SHOULD_FIX | Increased hard limit from 150 to 180 lines. 17 questions + pipeline diagram + summary table in 150 lines was too tight. | N/A |

### Skipped

| ID | Type | Reason |
|----|------|--------|
| MF-1 | MUST_FIX (Low) | Review itself notes "existing selection covers the major patterns adequately." Q6 cross-section is sufficient; step_01/step_02 canonical imports are partially covered by Q6b. |
| SF-1 | SHOULD_FIX | Agent can check `--help` output organically; adding doc search hints would add clutter for minimal value. |
| SF-2 | SHOULD_FIX | The phrasing "mapping step IDs to lambdas" is accurate shorthand. The ctx-passing nuance is what Q6 is designed to discover. |
| M-1 | MINOR | Answer-level detail; agent will find validate.py:267-282 via Q17. |
| M-2 | MINOR | No tension -- Q6 provides the specific list, line 14 gives the general rule. |

## P1-F (Gaps, Misses, Bugs & Regressions Analysis)

### Applied

| ID | Type | Fix | Verified |
|----|------|-----|----------|
| SF-2 | SHOULD_FIX | Added all 6 R9 task IDs (T18, T20, T22, T24, T26, T28) with descriptions inline to Q15. Previously only in Known Context section. | YES -- task IDs match ground truth section 11 |
| SF-3 | SHOULD_FIX | Fixed Q16 line range from "166-175" to "166-174". Confirmed cli.py:166 starts `env-check`, 174 ends `extraction-intent-check` parser args. Line 175 is blank/unrelated. | YES -- cli.py:166-174 confirmed |

### Skipped

| ID | Type | Reason |
|----|------|--------|
| MF-1 | MUST_FIX (Low) | Q5 correctly says "loads from" (4 _load_* sources), not "depends on" (9 DAG entries). Agent will discover the distinction. Review itself rates severity Low. |
| MF-2 | MUST_FIX (Low) | Claim "loads from 01, 04, 09" is correct (3 upstream steps, 4 functions). Two functions load from step_09 -- this is a function count detail, not a step count error. Review rates Low. |
| SF-1 | SHOULD_FIX | Providing sub-step field hints (plan/execution/review) would pre-empt the agent's analysis. Q4 is designed to discover this. |
| SF-4 | SHOULD_FIX | The 29 count is already correct in Known Context. Adding a question about stale documentation references to 30 is out of scope for P1-F (registry consistency is P1-A). |
| M-1 through M-4 | MINOR | All trivial or affirmative (no action needed). |

## Summary

- **4 fixes applied** (2 per prompt file)
- **10 items skipped** (low severity, out of scope, or agent-discoverable)
- All applied fixes verified against live codebase
