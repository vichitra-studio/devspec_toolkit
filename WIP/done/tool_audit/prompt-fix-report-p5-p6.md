# Prompt Fix Report: P5 and P6

Applied: 2026-03-18

---

## P5: Parallel Fix Execution

### MUST_FIX Applied

| ID | Issue | Fix Applied |
|----|-------|-------------|
| MF-1 | PLAN_ERROR missing from Output Status enum | Added `PLAN_ERROR` and `DEFERRED` to per-task Status enum: `PASS | FAIL | PLAN_ERROR | DEFERRED` |
| MF-2 | DEFERRED missing from per-task Output | Covered by MF-1 fix (both added to same enum) |
| MF-3 | DELETE operations have no revert instruction | Added DELETE revert (`git checkout -- <target-file>`) in new "Revert by Change Type" section and in Failure Protocol |
| MF-4 | MOVE operations lack two-file revert | Added MOVE revert (`git checkout -- <source>` + `rm <destination>`) in both "Revert by Change Type" section and Failure Protocol |

### SHOULD_FIX Applied

| ID | Issue | Fix Applied |
|----|-------|-------------|
| SF-1 | No dependency verification gate | Added step 0 to Instructions: verify all dependencies have status PASS before executing; report BLOCKED if any are FAIL/DEFERRED |
| SF-2 | No cross-task conflict handling | Added note to Retry Protocol: if test gate traceback points to another task's file, report FAIL with CROSS_TASK_CONFLICT in Notes |
| SF-3 | Cross-batch same-file targeting lacks merge note | Added to step 1 of Instructions: "When your target file was modified by a task in an earlier batch, you are working on the already-modified version. Do not attempt to revert earlier changes." |
| SF-4 | LOC delta not defined for CREATE/DELETE | Skipped (MINOR-level impact; the example in the report template already demonstrates the convention) |

### MINOR Skipped

| ID | Reason |
|----|--------|
| MI-1 | Cosmetic -- "830+" is intentionally approximate |
| MI-2 | Markdown rendering concern -- does not affect agent behavior |
| MI-3 | Timestamp in report template -- low priority |

---

## P6: Verification Review

### MUST_FIX Applied

| ID | Issue | Fix Applied |
|----|-------|-------------|
| MF-1 | Error code regex fragile (double-quote only) | Updated regex to match both single and double quotes; added E/W breakdown output |
| MF-2 | Missing baseline rows for Tests failed/skipped | Added `Tests failed: 0` and `Tests skipped: 0` to Baseline Numbers table |
| MF-3 | Task 5 missing version, PROMOTABLE_PAIRS, E/W split commands | Added commands for: pyproject.toml version, CLAUDE.md version, PROMOTABLE_PAIRS count, E/W code breakdown |
| MF-4 | p2-out-research-alignment.md missing from Inputs | Added to Inputs table with purpose "Research alignment items to cross-reference" |

### SHOULD_FIX Applied

| ID | Issue | Fix Applied |
|----|-------|-------------|
| SF-1 | Test count increase classification undefined | Added: "If count increased, verify new tests correspond to CREATE tasks or test-adding fixes in P5. Mark as EXPECTED if so." |
| SF-2 | REGRESSED status has no remediation protocol | Added inline: "For REGRESSED findings, include regression details in the Regression Report section. Do not attempt to fix -- this is a reporting phase only." |
| SF-3 | DEFERRED handling not prominent enough | Added explicit instruction: "If the corresponding FIX-NNN has status DEFERRED or FAIL in the P5 execution report, classify as NOT_RESOLVED." |
| SF-4 | grep -rn vs Grep tool inconsistency | Skipped (both approaches work; Bash tool can run grep) |
| SF-5 | Remaining Work section has no structure | Added table template with columns: Item, Status, Original Finding, Suggested Next Step |

### MINOR Applied (trivial)

| ID | Issue | Fix Applied |
|----|-------|-------------|
| MI-4 | Output template missing schema registry and CLI subcommand rows | Added both rows to the Metrics: Before / After output table |

### MINOR Skipped

| ID | Reason |
|----|--------|
| MI-1 | Correct value, no fix needed |
| MI-2 | Cosmetic claim mismatch -- commands themselves are correct |
| MI-3 | Timestamp -- low priority |

---

## Files Modified

- `WIP/tool_audit/p5-prompt-fix-execution.md` -- 4 MUST_FIX + 3 SHOULD_FIX applied
- `WIP/tool_audit/p6-prompt-verification.md` -- 4 MUST_FIX + 4 SHOULD_FIX + 1 MINOR applied
