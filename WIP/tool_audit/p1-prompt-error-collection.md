# P1-E: Error Collection & Reporting Pipeline Analysis

Agent Type: Explore (very thorough)
Repo Root: /Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/

## Objective

Audit how errors are collected, propagated, and reported end-to-end. The critical question is NOT "first-error vs collect-all" (already verified: validators collect-all AND validate.py uses iter_errors). It's: does the full pipeline preserve collect-all behavior, and is the error format LLM-consumable?

## Exclusive Scope

- `tools/specdev_tools/cli.py` — error handling, output formatting, exit codes ONLY
- `tools/specdev_tools/validation/validate.py` — error aggregation ONLY (not module structure — P1-B2 covers that)
- Spot-check 5-6 validators for error return patterns (don't read all 21)
- Spot-check 4-5 linters for error return patterns
- `tools/specdev_tools/core/errors.py` — error codes, PROMOTABLE_PAIRS
- `tools/specdev_tools/canonical/integrity.py`, `tools/specdev_tools/canonical/lint.py` — their error return patterns

## Scope Boundary

For validate.py and cli.py: ONLY error collection/propagation/formatting. Do NOT assess module responsibility or import structure (P1-B2), or test quality (P1-D).

## Known Context (from ground truth — DO NOT re-verify these)

- validate.py line 136 uses `iter_errors()` — VERIFIED, skip this question
- Validator dispatch dict is named `DEEP_VALIDATORS` (21 entries mapping step IDs to lambdas)
- 77 error codes total: 52 E-codes, 25 W-codes
- 18 PROMOTABLE_PAIRS: W550->E550, W560->E560, W561->E561, W562->E562, W563->E563, W571->E571, W572->E572, W573->E573, W580->E580, W581->E581, W150->E150, W590->E590, W591->E591, W592->E592, W593->E593, W594->E594, W595->E595, W597->E597
- 7 non-promotable W-codes: W110, W120, W130, W140, W552, W570, W596
- `--json` flag exists on `validate` and `traceability-check` only (2 of 25 commands)
- cli.py has `_print_and_exit_if_errors()` and `_is_warning_message()`
- errors.py is 186 LOC with SpecError dataclass, make_error() factory, 3 exception classes (SpecdevError, SubmoduleDetectionError, SchemaRegistryError). Note: `SpecError.render()` (errors.py:13-16) formats as `"{code} {path} {message}"` or `"{code} {message}"`, but many validators return raw f-strings (e.g., `f"E510 ..."`) instead of SpecError objects — this dual-format pattern is a key area to investigate
- R9 added W->E promotion via PROMOTABLE_PAIRS at validate.py line 267
- 12 `warnings.warn` call sites across the codebase (listed in ground truth section 10.4)
- cli.py is 757 LOC with 25 subcommands
- validate.py is 537 LOC
- canonical/integrity.py is 640 LOC, canonical/lint.py is 472 LOC

## Questions

### Error Collection (5 questions — Q1 already answered, start at Q2)

Q2. After schema validation via `iter_errors()`, does `validate_file()` continue to run deep validators even if schema errors exist? Or does it short-circuit? What is the exact branching logic?

Q3. How are errors aggregated across stages within a single file validation (schema errors + deep validator errors + canonical integrity errors + prompt-sync errors)? Is there a single accumulator list, or multiple separate lists?

Q4. Are there any code paths where errors could be swallowed (caught exceptions that don't re-raise or append to error list)? Check try/except blocks in validate.py and the validators you spot-check.

Q5. For `validate-all`: when validating multiple files, does it stop on first file error or continue through all files? How are per-file errors combined?

Q6. In the deep validators you spot-check (pick step_05, step_08, step_14, step_16, step_16a), do they all return lists of strings? Or do some return different types (SpecError objects, tuples, dicts, None)?

Q6b. What error return type do canonical/integrity.py and canonical/lint.py use? Are they consistent with the validator pattern (list of strings)?

### Error Propagation (4 questions)

Q7. What is the exact return type of `validate_file()`? Is it a list of strings, a list of SpecError, a tuple of (errors, warnings), or something else? Trace the return type from validate_file through to CLI output.

Q8. Does `_print_and_exit_if_errors()` lose any information during formatting? For example, does it strip error codes, collapse multi-line messages, or discard structured data?

Q9. For the 2 commands with `--json`: what is the JSON output schema? Is it documented? Does it include error codes, paths, severity?

Q10. For the 23 commands WITHOUT `--json`: is there any machine-parsable output format, or is it purely human-readable text?

### Error Format (4 questions)

Q11. Are errors flat strings or structured objects when returned by validators/linters? If flat strings, do they embed error codes in a consistent pattern (e.g., `"[E510] message"` or `"E510: message"`)? Check the actual format in at least 3 validators (step_03, step_06, step_12 — chosen for different complexity levels) and 2 linters (seed_lint, hallucination_lint — chosen for different error patterns).

Q12. Is the error message format consistent across all validators and linters you check? Or do different modules use different formatting patterns?

Q13. For an LLM consuming error output to self-correct: how actionable are the messages? Do they include the field path, the expected value, and the actual value? Or just a generic description?

Q14. Can errors be programmatically grouped by severity (error vs warning) from the output? How does the pipeline distinguish E-codes from W-codes in output?

### CLI Error Handling (4 questions)

Q15. How does cli.py handle exceptions from subcommands? Is there a global try/except, per-command error handling, or does it let exceptions propagate to traceback?

Q16. Are exit codes consistent across commands? (0 = success, 1 = validation errors, 2 = usage errors?) Or is the mapping ad-hoc?

Q17. Does warning promotion (SPECDEV_WARNINGS_AS_ERRORS, SPECDEV_PROMOTE_CODES) work at all levels — schema errors, deep validator errors, linter errors, canonical errors? Or only at specific stages?

Q18. The `_is_warning_message()` function — does it use regex or string matching? Could it misclassify an error that happens to contain a W-code substring?

## Output Format

Write to: `WIP/tool_audit/p1-out-error-collection.md`

### Finding Format

```
### FINDING-E{N}: {title}

- **Severity**: Critical | High | Medium | Low
- **Category**: FIRST_ERROR_ONLY | SWALLOWED_ERROR | FORMAT_INCONSISTENCY | PROPAGATION_BUG | MISSING_JSON | LLM_UNFRIENDLY
- **Location**: {file}:{line}
- **Current behavior**: {what happens now}
- **Expected behavior**: {what should happen}
- **Recommendation**: {specific fix}
```

### Output Structure

1. Executive summary (5 lines max)
2. Pipeline diagram (text-based, showing error flow from validator -> validate.py -> cli.py -> stdout)
3. Findings (numbered FINDING-E1 through FINDING-EN)
4. Summary table of all findings with severity and category

**Hard limit: 180 lines.**
