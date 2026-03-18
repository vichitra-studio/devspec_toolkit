# Prompt Review: P1-E (Error Collection & Reporting Pipeline Analysis)

## Claims Verified

| # | Claim | Prompt Line | Verified Against | Match? |
|---|-------|------------|-----------------|--------|
| 1 | validate.py line 136 uses `iter_errors()` | L25 | `validate.py:136` actual code: `errors = sorted(v.iter_errors(data_for_validation), key=lambda e: e.path)` | YES |
| 2 | 77 error codes total: 52 E, 25 W | L27 | `errors.py` parsed with regex: 52 E-codes, 25 W-codes, 77 total | YES |
| 3 | 18 PROMOTABLE_PAIRS listed | L28 | `errors.py:110-134` has exactly 18 W->E mappings | YES |
| 4 | 7 non-promotable W-codes: W110, W120, W130, W140, W552, W570, W596 | L29 | `errors.py` W-codes minus PROMOTABLE_PAIRS keys = {W110, W120, W130, W140, W552, W570, W596} | YES |
| 5 | errors.py is 186 LOC | L32 | `wc -l errors.py` = 186 | YES |
| 6 | 3 exception classes (SpecdevError, SubmoduleDetectionError, SchemaRegistryError) | L32 | `errors.py:144,149,169` define exactly these 3 classes | YES |
| 7 | `--json` flag on validate and traceability-check only (2 of 25) | L30 | `cli.py:54` (validate --json) and `cli.py:117` (traceability-check --json); no other `--json` args found | YES |
| 8 | cli.py has `_print_and_exit_if_errors()` and `_is_warning_message()` | L31 | `cli.py:25` and `cli.py:11` respectively | YES |
| 9 | cli.py is 757 LOC | L35 | `wc -l cli.py` = 757 | YES |
| 10 | validate.py is 537 LOC | L36 | `wc -l validate.py` = 537 | YES |
| 11 | canonical/integrity.py is 640 LOC, canonical/lint.py is 472 LOC | L37 | `wc -l` = 640 and 472 respectively | YES |
| 12 | R9 added W->E promotion at validate.py line 267 | L33 | `validate.py:267` comment: `# R9/T26: Dynamic W->E promotion using PROMOTABLE_PAIRS` | YES |
| 13 | 12 `warnings.warn` call sites | L34 | `grep -c "warnings.warn"` across specdev_tools/ = 12 | YES |
| 14 | SpecError dataclass with code, message, path fields | L32 (implicit via "make_error() factory") | `errors.py:7-11` exactly matches | YES |

## Issues Found

### MUST_FIX

**MF-1: Spot-check validator list in Q6 may miss important patterns**

Q6 says "pick step_05, step_08, step_14, step_16, step_16a". This is a good cross-section but omits any canonical-adjacent validators (e.g., step_01 and step_02 which import `core.trace_types`). Since Q6b covers canonical/integrity.py and canonical/lint.py separately, this is partially mitigated, but step_01/step_02 have unique import patterns (SchemaRegistry + trace_types) that differ from the simpler validators. Consider adding step_01 or step_02 to the spot-check list.

Severity: Low -- the existing selection covers the major patterns adequately.

**MF-2: Missing question about SpecError.render() vs raw string formatting**

The prompt asks about error format consistency (Q11, Q12) but does not mention `SpecError.render()` (errors.py:13-16) which formats as `"{code} {path} {message}"` or `"{code} {message}"`. The prompt should note that `make_error()` returns `SpecError` objects but many validators return raw strings (e.g., `f"E510 PLACEHOLDER_VALUE_FOUND ..."` directly). This dual-format pattern is a key finding the agent should look for, and the prompt currently gives no hint that it exists.

Severity: Medium -- the agent might discover this organically via Q11/Q12, but it is a central pipeline concern that deserves explicit attention.

### SHOULD_FIX

**SF-1: Q9 asks about JSON output schema for --json commands**

The prompt asks "Is it documented?" but does not point the agent to any known documentation location. The ground truth does not mention JSON output documentation either. The agent could waste time searching. Consider adding: "Check docs/developers/ and --help output."

**SF-2: Known context says "21 entries mapping step IDs to lambdas" but ground truth section 4.2 shows step_01 lambda includes `ctx.get("component_ids")`**

The prompt says "DEEP_VALIDATORS (21 entries mapping step IDs to lambdas)" which is correct, but the phrasing "mapping step IDs to lambdas" undersells the complexity -- some lambdas pass extra `ctx` arguments (step_01, step_02, step_03, step_14, step_16, step_16a-c). This matters for Q6 (error return types) because the ctx-passing pattern affects how errors flow.

**SF-3: Hard limit of 150 lines may be tight**

Given 17 questions spanning error collection, propagation, format, and CLI handling, plus a required pipeline diagram and summary table, 150 lines is aggressive. The agent may need to sacrifice depth. Consider 180-200 lines.

### MINOR

**M-1: Q17 mentions "warning promotion works at all levels"**

The phrasing "schema errors, deep validator errors, linter errors, canonical errors" is good but should note that promotion happens in `validate_file()` at the end (validate.py:267-282), meaning it operates on the accumulated `failures` list after all stages have run. This is an answer, not a question -- the agent will find it, but calling it out would save time.

**M-2: Scope boundary could be sharper about which validators to NOT read**

Line 14 says "spot-check 5-6 validators" and "don't read all 21" but doesn't say which validators to skip. The Q6 line provides a specific list, which is good. No action needed, just noting slight tension.

## Verdict: APPROVED_WITH_FIXES

The prompt is well-structured with clear scope boundaries and good ground-truth anchoring. The known context is accurate (all 14 claims verified). The main gap is the missing mention of `SpecError.render()` vs raw-string duality (MF-2), which is central to the error format analysis the prompt requests. The hard line limit (SF-3) may constrain output quality. All other issues are minor.
