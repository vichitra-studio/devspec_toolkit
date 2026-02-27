<review_prompt id="R1" areas="4,8" depends_on="none" priority="P0-quickwins">
# Review R1: Test Hygiene + Invariant Engine Soundness

## Scope
This review covers two isolated, zero-dependency fix areas:
- **Area 4**: Legacy B* batch naming in test suite (2 confirmed files)
- **Area 8**: Invariant evaluation engine bugs (1 file, 65 LOC)

No cross-dependencies with other reviews. Execute first for immediate, safe wins.

---

## Files Under Review

| File | Area | LOC | Issue |
|------|------|-----|-------|
| `tests/test_schema_contracts.py` | 4 | 777 | B4 naming on line 19 |
| `tests/test_prompt_contracts.py` | 4 | 192 | B4 naming on line 17 |
| `tests/` (all files) | 4 | — | Search for any B0-B8 pattern |
| `tools/specdev_tools/validation/invariants.py` | 8 | 65 | 3 bugs: lines 5-65 |

---

## Subagent Protocol (MANDATORY)

### Main Agent Rules
- **FORBIDDEN in main agent**: Read, Edit, Write, Grep, Glob, Bash for file content
- Main agent ONLY: spawn subagents, read their text summaries, write task list, final report
- All file reads, all code changes → subagents only
- Token budget for main agent per session: < 5K tokens

### Subagent Assignment

#### Phase 1 — Investigation (2 Explore subagents)

**Subagent A** (`Explore`, no isolation):
```
Task: Audit all test files in tests/ for legacy batch naming.
Files to read: tests/test_schema_contracts.py, tests/test_prompt_contracts.py, all other test files
Search for: any function/class/docstring/comment containing B[0-8] or b[0-8] pattern
Also check: tests/fixtures/ for any B*-named fixture files or directories
Report back: exact file:line for every occurrence found
```

**Subagent B** (`Explore`, no isolation):
```
Task: Audit invariants.py for the 3 confirmed bugs.
File to read: tools/specdev_tools/validation/invariants.py (full file, 65 LOC)
Verify each bug:
1. Line 40: _tiny_eval returns None for unknown operators — confirm None propagates to bool(None)=False at line 63
2. Line 51: json.load(open(p, ...)) — confirm missing `with` statement (file handle leak)
3. Line 57: heuristic startswith("{") — confirm array-form JSONLogic expressions would be missed
4. Line 64: result dict — confirm no field distinguishes "violated" vs "unsupported expression"
Report back: confirmed/refuted for each bug with exact code quote
```

#### Phase 2 — Implementation (after Phase 1)

Use worktree isolation for all code changes.

**Subagent C** (`general-purpose`, isolation: `worktree`):
```
Task: Rename all legacy B4/B* test functions discovered in Phase 1.
Changes required:
- tests/test_schema_contracts.py:19 — rename test_all_step_schemas_include_b4_top_level_fields
  → test_all_step_schemas_include_generation_metadata_fields
- tests/test_prompt_contracts.py:17 — rename test_output_contract_examples_include_b4_fields
  → test_output_contract_examples_include_required_output_fields
- Any additional occurrences found in Phase 1
After rename: run `pytest tests/test_schema_contracts.py tests/test_prompt_contracts.py -v`
and confirm tests still pass. Report pass/fail.
```

**Subagent D** (`general-purpose`, isolation: `worktree`):
```
IDEMPOTENCY: Read tools/specdev_tools/validation/invariants.py FIRST before any edits.
Check each bug: if already fixed (e.g., `with open(...)` already present, "evaluable" key already in result dict), skip that fix and note "pre-existing fix" in your report. Apply only the fixes still needed.

Task: Fix the invariant engine bugs in tools/specdev_tools/validation/invariants.py.
VERIFIED line numbers from codebase read:
- Line 40: _tiny_eval returns None (end of function, after all operator branches)
- Line 50: json.load(open(p, "r", encoding="utf-8")) — bare open without with
- Line 57: expr.strip().startswith("{") — array-form JSONLogic missed
- Lines 60-64: result dict has inv_id, description, result — no evaluable field

Fix 1 (line 40): When _tiny_eval encounters unknown operator, emit a warning instead of returning None.
  - Add a W-code emission (use existing warning pattern from codebase)
  - Return a sentinel (e.g., raise ValueError or return a typed result object)
Fix 2 (line 51): Replace `json.load(open(p, ...))` with `with open(p, ...) as f: json.load(f)`
Fix 3 (line 64): Add a field to the result dict: "evaluable": bool — True if expression used only
  supported operators, False if any unknown operator was encountered. This lets consumers
  distinguish "invariant violated" (evaluable=True, result=False) from "unsupported expression"
  (evaluable=False).
Fix 4 (lines 22-28): Add try/except around comparisons that may receive None from var resolution;
  emit specific warning about unresolved var path rather than silently catching TypeError.
After fixes: run `pytest tests/ -k invariant -v` and confirm all tests pass.
Report: exact code changes made, test results.
```

#### Phase 3 — Integration (after Phase 2)

**Subagent E** (`general-purpose`, no isolation):
```
Task: Verify no regressions from Phase 2 changes.
Run: pytest tests/ -v --tb=short
Report: full pass/fail summary. If failures exist, identify which test and why.
```

---

## Investigation Questions

### Area 4 Checklist
- [ ] Are there ANY B[0-8] patterns in test function names?
- [ ] Are there B[0-8] patterns in docstrings, comments, or variable names?
- [ ] Are there dead fixtures in `tests/fixtures/` not referenced by any test?
- [ ] Are there duplicate coverage tests across files?

### Area 8 Checklist
- [ ] Does `_tiny_eval` return `None` for all unrecognized operators? (line 40 confirmation)
- [ ] Does `run_invariants` use bare `open()` without context manager? (line 51)
- [ ] Does the heuristic `startswith("{")` miss array-form JSONLogic? (line 57)
- [ ] Is there any mechanism to distinguish "unsupported expression" from "violated invariant"? (line 64)
- [ ] Are there any other operators that should be supported but aren't?

---

## Deliverables

> **Format**: Use compact tables from `docs/audit/review_protocol.md`. No verbose prose.

### Part A: Findings
```
| ID | Sev | File:Line | Finding | Impact |
|----|-----|-----------|---------|--------|
| A-R1-01 | CRIT/HIGH/MED/LOW | path:line | description | impact |
```
Evidence blocks (CRIT/HIGH only): exact quoted code, one block per finding.

### Part B: Implementation Plan
Atomic tasks — one file per task. See `review_protocol.md` for sequencing rules and table format.

Required task sequence for this review:
1. `invariants.py` fix (code) → test task
2. `test_schema_contracts.py` rename → run renamed test
3. `test_prompt_contracts.py` rename → run renamed test
4. Any additional B* findings from Phase 1 → task per file

---

## Anti-Patterns
- Do not rename tests without running them first
- Do not add new operators to `_tiny_eval` beyond the confirmed supported set
- Do not change the public API of `run_invariants()` — only add fields to result dict
- Do not conflate "test hygiene" findings with schema or validator issues (those are R6)

---

## Phase 4: Self-Verification Loop

After drafting Part A + Part B, launch before writing to file.

**Subagent V1** (`general-purpose`, no isolation): Run all 7 checks from `docs/audit/review_protocol.md § Phase 4`.
- If NEEDS REVISION: revise and re-run. Max 3 iterations.
- If VERIFIED after any iteration: proceed to Phase 5.

---

## Phase 5: Write Findings to File

**Output file**: `docs/audit/findings/r1_findings.md`

**Subagent W1** (`general-purpose`, no isolation): Write verified findings using the format in `docs/audit/review_protocol.md § Phase 5`.

---

## Phase 6: Post-Implementation Verification

Run in a separate session after all Part B tasks are executed.

**Subagent P1** (`Explore`, no isolation): Run all checks from `docs/audit/review_protocol.md § Phase 6`.
Key commands for this review:
```
pytest tests/test_schema_contracts.py tests/test_prompt_contracts.py -v
pytest tests/ -k invariant -v
pytest tests/ --tb=short -q
```

</review_prompt>
