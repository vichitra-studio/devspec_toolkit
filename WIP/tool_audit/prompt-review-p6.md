# Prompt Review: P6 -- Verification Review

Reviewed: 2026-03-18
Reviewed against: p0-ground-truth-FINAL.md, p0-baseline.md, live codebase

---

## Claims Verified

| Claim | Source Line | Verified Against | Match? |
|-------|-----------|-----------------|--------|
| Tests collected: 830 | L33 | p0-baseline.md (830), p0-ground-truth-FINAL.md (830), live `pytest --collect-only` | YES |
| Tests passed: 830 | L34 | p0-baseline.md (830), p0-ground-truth-FINAL.md (830) | YES |
| Source files: 61 | L35 | p0-baseline.md (61), live `find ... \| wc -l` = 61 | YES |
| Source LOC: 13,228 | L36 | p0-baseline.md (13,228), p0-ground-truth-FINAL.md (13,228) | YES |
| Test files: 73 | L37 | p0-baseline.md (73), p0-ground-truth-FINAL.md (73) | YES |
| Test LOC: 17,709 | L38 | p0-baseline.md (17,709), p0-ground-truth-FINAL.md (17,709) | YES |
| `_load_*` functions: 23 | L39 | p0-baseline.md (23), live `grep` = 23 | YES |
| Error codes: 77 (52 E + 25 W) | L40 | p0-baseline.md (77, 52 E, 25 W), live script = 77 | YES |
| Schema registry entries: 29 | L41 | p0-baseline.md (29), p0-ground-truth-FINAL.md (29, corrected from agents' 30), live = 29 | YES |
| CLI subcommands: 25 | L42 | p0-baseline.md (25), live `grep -c` = 25 | YES |
| Version pyproject.toml: 0.4.0 | L43 | p0-baseline.md (0.4.0), p0-ground-truth-FINAL.md (0.4.0) | YES |
| Version CLAUDE.md: 0.3.0 (mismatch) | L44 | p0-baseline.md (0.3.0 mismatch), CLAUDE.md line "Current version: **0.3.0**" | YES |
| Repo root path | L4 | Live codebase | YES |
| Venv name devspec_env | L65 | MEMORY.md | YES |
| Output path p6-out-verification.md | L130 | Consistent with pipeline | YES |

---

## Issues Found

### MUST_FIX

**MF-1: Error code counting command only finds codes in errors.py, misses codes defined elsewhere**

Lines 111-117: The error code counting command reads only `tools/specdev_tools/core/errors.py`. The baseline of 77 happens to be correct for the current codebase, but if P5 fixes add error codes in other files, this command would miss them. More importantly, the regex `\"[EW]\d{3}\"` matches only double-quoted codes. If any code uses single quotes, it would be missed.

Severity elevated to MUST_FIX because the command must produce accurate "after" metrics. Verify the regex matches the actual quote style in errors.py.

Fix: Verify that all error codes in errors.py use double quotes (they do currently). Add a note: "This command assumes all error codes are defined in errors.py with double quotes. If P5 moved error definitions, adjust the path."

**MF-2: Missing "Tests skipped" and "Tests xfail" in Baseline Numbers table**

The Baseline Numbers table (lines 30-44) omits "Tests skipped" and "Tests xfail" which are both 0 in p0-baseline.md. However, the output template (lines 152-153) includes rows for "Tests failed" and "Tests skipped". The baseline table should include all metrics that appear in the output template for consistency, otherwise the agent has no authoritative "before" value for skipped/failed tests.

Fix: Add to the Baseline Numbers table:
- Tests failed: 0
- Tests skipped: 0

**MF-3: Task 5 "After Metrics" commands do not cover all baseline metrics**

The p0-baseline.md tracks 36 metrics. The Task 5 commands (lines 92-124) only collect 9 of them:
- Source LOC
- Test LOC
- Test collection count
- `_load_*` count
- Source file count
- Test file count
- Error code count
- Schema registry entries
- CLI subcommands

Missing from Task 5 but present in p0-baseline.md and the output template:
- pyproject.toml version (simple `grep` or `python3 -c`)
- CLAUDE.md version
- PROMOTABLE_PAIRS count
- E-code / W-code breakdown (the command gives total only, not split)

The output "Metrics: Before / After" table (lines 183-188) only has 6 rows, which is a subset of what baseline tracks. This is acceptable IF intentional, but should be documented.

Fix: Either add commands for the missing metrics or explicitly state: "Only the metrics listed below are re-measured. Other baseline metrics (version, PROMOTABLE_PAIRS, E/W split) are assumed unchanged unless a FIX task specifically targeted them."

**MF-4: Task 4 references `p2-out-research-alignment.md` but this file is not listed in Inputs**

Line 84 says "Cross-reference P2 alignment items against executed fixes" and references `p2-out-research-alignment.md`. But the Inputs table (lines 22-27) does not list this file. An agent following the Inputs table strictly would not know to read it.

Fix: Add `p2-out-research-alignment.md` to the Inputs table with purpose "Research alignment items to cross-reference".

### SHOULD_FIX

**SF-1: Regression classification for test count increase is not defined**

Line 70 defines what to do if test count decreased but does not define classification for test count increase. If P5 added tests (e.g., Batch 3), is the increase EXPECTED? The prompt should state: "If test count increased, verify new tests correspond to CREATE tasks or test-adding fixes. Mark as EXPECTED."

**SF-2: REGRESSED status has no remediation protocol**

Line 59 defines `REGRESSED` as a possible classification but there is no instruction for what to do when a finding is classified as REGRESSED. Should the agent attempt to fix it? Revert the change? Just report it?

Fix: Add: "For REGRESSED findings, include the regression details (traceback, behavioral change) in the Regression Report section. Do not attempt to fix -- this is a reporting phase only."

**SF-3: No instruction to handle P5 execution report showing DEFERRED tasks**

If P5 deferred tasks, P6 needs to handle them. Task 1 (line 52) says "For every AUDIT-NNN in the master findings that was mapped to a FIX-NNN" but does not explicitly state how to classify a DEFERRED fix. The NOT_RESOLVED definition (line 58) says "not executed (DEFERRED/FAIL)" which covers it, but the agent might not notice this parenthetical.

Fix: Make the DEFERRED handling more prominent: "If the corresponding FIX-NNN has status DEFERRED or FAIL in the P5 execution report, classify as NOT_RESOLVED."

**SF-4: DRY Verification (Task 3) uses `grep -rn` which is a shell command, not the available Grep tool**

Line 76 instructs the agent to run `grep -rn "def _load_" ...`. Depending on the agent environment, the Grep tool abstraction may need to be used instead. This is minor since the Bash tool can run grep, but inconsistent with best practices noted in the agent system prompt.

Fix: Note that either the Grep tool or Bash-invoked grep is acceptable for this measurement.

**SF-5: Output template "Remaining Work" section has no structure guidance**

Line 191 says "[List of NOT_RESOLVED, PARTIALLY_RESOLVED, and DEFERRED items that need future attention]" but does not specify a table format or what columns to include. This will produce inconsistent output across runs.

Fix: Provide a table template: `| Item | Status | Original Finding | Suggested Next Step |`

### MINOR

**MI-1: Baseline Numbers table uses "29" for schema registry entries**

This is CORRECT (verified against p0-ground-truth-FINAL.md which corrected both agents' "30" down to 29, and confirmed live with `python3 -c` returning 29). No fix needed -- just noting this was checked.

**MI-2: The "After Metrics" section title says "identical to P0 baseline collection" but commands differ**

Line 89 says "Run these EXACT commands (identical to P0 baseline collection)" but P0 may have used different commands. Since we do not have the P0 collection script for comparison, this claim cannot be verified. The commands themselves are correct and produce accurate results, so this is cosmetic.

**MI-3: No timestamp field in the output template**

Similar to P5, adding a "Verified at: [timestamp]" header would improve traceability.

**MI-4: Output template omits schema registry and CLI subcommand rows**

The "Metrics: Before / After" table in the output template (lines 183-188) has 6 rows but Task 5 collects 9 metrics. The schema registry entries, CLI subcommands, and test collection count are collected but have no row in the output table.

Fix: Add the missing rows to the output template to match the collected metrics.

---

## Verdict: APPROVED_WITH_FIXES

The prompt is well-structured and the baseline numbers are accurate -- all 12 numeric claims in the Baseline Numbers table match p0-baseline.md and p0-ground-truth-FINAL.md exactly (verified against live codebase). The MUST_FIX items are: (1) missing metrics commands for complete before/after comparison, (2) a missing input file reference for Task 4, (3) incomplete baseline table for test failure/skip counts, and (4) error code regex fragility. These are additive fixes that do not require restructuring. Once addressed, the prompt is ready for use.
