# R1: Test Hygiene + Invariant Engine Soundness — Implementation Plan

## Context

Review R1 addresses two isolated, zero-dependency fix areas identified in the codebase audit:
- **Area 4**: Legacy "B4" naming in test function names across 5 test files (broader than the 2 files noted in the review — investigation found 10 function/docstring occurrences across 5 files)
- **Area 8**: 6 confirmed bugs in `tools/specdev_tools/validation/invariants.py` (66 LOC) — silent failures, file handle leaks, missing operators, and no way to distinguish "violated" from "unsupported"

Additionally: the CLI entry point (`cli.py:221`) has the same bare-open file handle leak, and there are **zero dedicated tests** for the invariant engine.

### How `_tiny_eval` works

`_tiny_eval` is a custom, zero-dependency dict-expression evaluator (40 LOC) using the pattern `{operator: [args]}`. The schema's `language` field enum `["jsonlogic", "cel", "text"]` labels this format. There is no external library — it's hand-rolled Python supporting 10 operators: `>=`, `<=`, `>`, `<`, `==`, `and`, `or`, `not`, `in`, `contains`, plus `var` for context lookups. `run_invariants()` walks spec files, finds rules where `language == "jsonlogic"`, and evaluates their `expression` strings using `_tiny_eval`.

---

## Verification Review — Gaps Found & Resolved

| # | Gap | Resolution |
|---|-----|------------|
| 1 | **W590 registered but never emitted** — `invariants.py` is an evaluator (returns data), NOT a linter (returns error strings). Adding W590 to `errors.py` without emit logic is dead code. | **Removed T1 entirely.** The `evaluable` field in the result dict IS the signal. No W-code needed. |
| 2 | **`startswith("{")` fix rationale** — original plan cited "array-form JSONLogic" but the codebase doesn't follow any external spec. | **Reframed:** The fix prevents false positives from unparsed JSON strings starting with `[`. Without parsing, `bool("[...]")` = `True` → false positive. |
| 3 | **`empty` operator** — not from any external spec. It's an operator the project's own fixture (`valid_full.json:20`) uses but `_tiny_eval` doesn't support. | **Keep the fix.** It's a missing operator for the project's own expression format. |
| 4 | **`"## B4 Metadata Contract"` missing from ALL 33 prompt files** — tests that split on this string skip silently. | **Out of scope for R1.** Documented in Known Issues. |
| 5 | **Schema confirms `language` is required** (enum: `jsonlogic`, `cel`, `text`) and `expression` is always `type: string`. | **Keep defensive default** `rule.get("language", "jsonlogic")` for backward compat. `cel` and `text` rules → `evaluable=False`. |

---

## Task Breakdown (9 tasks, one file each)

### Dependency Graph

```
Wave 1 (all parallel — no dependencies):
  T3  cli.py                       — fix file handle leak
  T4a test_schema_contracts.py     — rename 4 B4 functions
  T4b test_prompt_contracts.py     — rename 1 B4 function
  T4c test_spec_quality_lint.py    — rename 1 B4 function
  T4d test_migration_templates.py  — rename 1 B4 function + docstring
  T4e test_prompt_schema_sync.py   — rename 2 B4 functions

Wave 2 (independent of Wave 1):
  T2  invariants.py                — fix all 6 bugs

Wave 3 (depends on T2):
  T7  test_invariants.py           — new file, dedicated test coverage

Wave 4 (depends on all above):
  T8  docs/audit/findings/         — write r1_plan.md

Final: full suite gate
```

---

### T2: Fix 6 bugs in invariants.py

**File**: `tools/specdev_tools/validation/invariants.py`
**Subagent**: `general-purpose` (worktree isolation — riskiest task)
**Blocked by**: None
**No new dependencies.** Only uses stdlib `os` and `json`.

IDEMPOTENCY: Read file FIRST. If any fix is already present, skip it and note "pre-existing fix".

**Fix 1 — Bug 6: Guard comparisons against None operands (lines 22-26)**
Replace individual comparison operator lines with a consolidated guarded block:
```python
            if op in (">=", "<=", ">", "<", "==", "!="):
                if any(v is None for v in vals[:2]):
                    return None  # unresolved var → not evaluable
                if op == ">=": return vals[0] >= vals[1]
                if op == "<=": return vals[0] <= vals[1]
                if op == ">":  return vals[0] > vals[1]
                if op == "<":  return vals[0] < vals[1]
                if op == "==": return vals[0] == vals[1]
                if op == "!=": return vals[0] != vals[1]
```
This adds `!=` (Bug 5 — missing operator) and returns `None` instead of raising `TypeError` when operands are `None` from unresolved var paths.

**Fix 2 — Bug 5: Add `empty` operator (after `contains` block, before final `return None`)**
The project's fixture (`valid_full.json:20`) uses `{"not": {"empty": {"var": "auth-token"}}}` but `_tiny_eval` has no `empty` handler.
```python
            if op == "empty":
                v = vals[0]
                return v is None or v == "" or v == [] or v == {}
```

**Fix 3 — Bug 2: File handle leak (line 50)**
Replace:
```python
                try:
                    data = json.load(open(p, "r", encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
```
With:
```python
                try:
                    with open(p, "r", encoding="utf-8") as fh:
                        data = json.load(fh)
                except (OSError, json.JSONDecodeError):
                    continue
```

**Fix 4 — Bug 3: Parse string expressions starting with `[` (line 57)**
Replace `expr.strip().startswith("{")` with `expr.strip()[:1] in ("{", "[")`.

**Why:** Without this fix, an expression string like `"[{...}]"` won't be parsed by `json.loads()`. The raw string passes to `_tiny_eval`, which sees a string (line 7) and returns it unchanged. `bool("[{...}]")` = `True` → **false positive**. The fix ensures the string is at least parsed as JSON.

**Fix 5 — Bug 4: Add `evaluable` field + handle non-evaluable languages (lines 54-64)**
Replace the rule loop body:
```python
                for rule in data.get("rules", []):
                    lang = rule.get("language", "jsonlogic")
                    expr = rule.get("expression")
                    evaluable = True
                    if lang != "jsonlogic":
                        ok = None
                        evaluable = False
                    else:
                        try:
                            parsed = (json.loads(expr)
                                      if isinstance(expr, str) and expr.strip()[:1] in ("{", "[")
                                      else expr)
                            ok = _tiny_eval(parsed, sample)
                        except (TypeError, ValueError, IndexError, KeyError, AttributeError):
                            ok = None
                            evaluable = False
                    if evaluable and not isinstance(ok, bool):
                        evaluable = False  # unknown op (None), unresolved var, or non-boolean result
                    out.append({
                        "inv_id": rule.get("inv_id"),
                        "description": rule.get("description"),
                        "result": bool(ok) if evaluable else False,
                        "evaluable": evaluable,
                    })
```

**Key design choice: `isinstance(ok, bool)`** — stricter than just checking `ok is None`. This catches:
- `ok = None` → unknown operator or unresolved var (Bug 1)
- `ok = [...]` → list result from parsed array expression
- `ok = "string"` → unparsed expression
- Allows only `ok = True/False` through as valid evaluation results

**Fix 6 — Bug 1: `_tiny_eval` returning None for unknown ops**
Handled by Fix 5 — the `isinstance(ok, bool)` check catches `None` returns and sets `evaluable=False`.

**Verify**:
```bash
pytest tests/ -x -q
python -c "
from specdev_tools.validation.invariants import _tiny_eval
assert _tiny_eval({'>=': [None, 5]}, {}) is None     # Bug 6: None-safe
assert _tiny_eval({'empty': [None]}, {}) == True      # Bug 5: empty
assert _tiny_eval({'empty': ['hello']}, {}) == False   # Bug 5: non-empty
assert _tiny_eval({'!=': [1, 2]}, {}) == True          # Bug 5: != operator
assert _tiny_eval({'bogus': [1]}, {}) is None          # Bug 1: unknown op
print('All checks passed')
"
```

---

### T3: Fix file handle leak in cli.py

**File**: `tools/specdev_tools/cli.py` (line 221)
**Subagent**: `general-purpose` (trivial edit)

Replace:
```python
        sample = json.load(open(args.sample, "r", encoding="utf-8"))
```
With:
```python
        with open(args.sample, "r", encoding="utf-8") as fh:
            sample = json.load(fh)
```

**Indentation**: `res = run_invariants(...)` and `print(...)` stay OUTSIDE the `with` block. `json.load()` fully deserializes before `with` exits, so `sample` is a standalone dict.

**Verify**: `python -c "import ast; ast.parse(open('tools/specdev_tools/cli.py').read()); print('Syntax OK')"`

---

### T4a: Rename B4 functions in test_schema_contracts.py

**File**: `tests/test_schema_contracts.py`
**Subagent**: `general-purpose`

| Line | Old Name | New Name |
|------|----------|----------|
| 19 | `test_all_step_schemas_include_b4_top_level_fields` | `test_all_step_schemas_include_metadata_top_level_fields` |
| 41 | `test_b4_expected_canonical_ref_kinds_exist_per_step` | `test_expected_canonical_ref_kinds_exist_per_step` |
| 213 | `test_validate_file_enforces_b4_top_level_fields_for_step_artifacts` | `test_validate_file_enforces_metadata_top_level_fields_for_step_artifacts` |
| 266 | `test_validate_file_enforces_b4_even_with_nonstandard_filename` | `test_validate_file_enforces_metadata_even_with_nonstandard_filename` |

**Verify**: `pytest tests/test_schema_contracts.py -v` + `grep -cn "b4\|B4" tests/test_schema_contracts.py` → 0

---

### T4b: Rename B4 function in test_prompt_contracts.py

**File**: `tests/test_prompt_contracts.py`
**Subagent**: `general-purpose`

| Line | Old Name | New Name |
|------|----------|----------|
| 17 | `test_output_contract_examples_include_b4_fields` | `test_output_contract_examples_include_metadata_fields` |

**DO NOT rename** string literals `"## B4 Metadata Contract"` on lines 20, 22, 60, 62, 158, 172. These are section delimiters used to parse prompt file content.

**Verify**: `pytest tests/test_prompt_contracts.py -v` + `grep -c "def.*b4" tests/test_prompt_contracts.py` → 0 + `grep -c "B4 Metadata Contract" tests/test_prompt_contracts.py` → 6 (unchanged)

---

### T4c: Rename B4 function in test_spec_quality_lint.py

**File**: `tests/test_spec_quality_lint.py`
**Subagent**: `general-purpose`

| Line | Old Name | New Name |
|------|----------|----------|
| 54 | `test_detects_missing_b4_top_level_fields` | `test_detects_missing_metadata_top_level_fields` |

**Verify**: `pytest tests/test_spec_quality_lint.py -v`

---

### T4d: Rename B4 references in test_migration_templates.py

**File**: `tests/test_migration_templates.py`
**Subagent**: `general-purpose`

| Line | Old | New |
|------|-----|-----|
| 76 | `"""Templates reference canonical schema URIs and B4 fields."""` | `"""Templates reference canonical schema URIs and metadata fields."""` |
| 90 | `test_templates_include_b4_fields` | `test_templates_include_metadata_fields` |

**Verify**: `pytest tests/test_migration_templates.py -v` + `grep -cn "b4\|B4" tests/test_migration_templates.py` → 0

---

### T4e: Rename B4 functions in test_prompt_schema_sync.py

**File**: `tests/test_prompt_schema_sync.py`
**Subagent**: `general-purpose`

| Line | Old Name | New Name |
|------|----------|----------|
| 152 | `test_detects_missing_b4_property_when_not_declared_anywhere` | `test_detects_missing_metadata_property_when_not_declared_anywhere` |
| 226 | `test_b4_text_mention_does_not_bypass_missing_property_check` | `test_metadata_text_mention_does_not_bypass_missing_property_check` |

**DO NOT rename** string literals `"## B4 Metadata Contract\n"` on lines 251, 286, 328, 373, 411, 445, 487, 527. These are test fixture data simulating prompt content.

**Verify**: `pytest tests/test_prompt_schema_sync.py -v` + `grep -c "def.*b4" tests/test_prompt_schema_sync.py` → 0 + `grep -c "B4 Metadata Contract" tests/test_prompt_schema_sync.py` → 8 (unchanged)

---

### T7: Create dedicated invariant engine tests

**File**: `tests/test_invariants.py` (NEW)
**Subagent**: `general-purpose`
**Blocked by**: T2

Create comprehensive test file with two test classes:

**`TinyEvalTests`** (unit tests for `_tiny_eval`):
- Literal passthrough: int, str, bool, None each return themselves
- `var` resolution: nested paths like `{"var": "user.name"}`
- `var` missing: returns `None`
- All comparison operators: `>=`, `<=`, `>`, `<`, `==`, `!=`
- **Bug 6 regression**: comparison with `None` operand → returns `None`, no TypeError
- Logical operators: `and`, `or`, `not`
- Collection operators: `in`, `contains`
- **Bug 5 regression**: `empty` operator — `None`/`""`/`[]`/`{}` → True; `"hello"`/`[1]` → False
- **Bug 1 regression**: unknown operator → returns `None`
- List passthrough
- Nested expression with multiple operators

**`RunInvariantsTests`** (integration tests using temp directories):
- Rule passes: `{"==": [1, 1]}` → `evaluable=True, result=True`
- Rule fails: `{"==": [1, 2]}` → `evaluable=True, result=False`
- **Bug 4 regression**: `cel` language rule → `evaluable=False`
- **Bug 4 regression**: `text` language rule → `evaluable=False`
- **Bug 3 regression**: expression starting with `[` is parsed (no false positive)
- **Bug 1+4 regression**: unknown operator → `evaluable=False`
- **Bug 4 regression**: result dict contains `evaluable` key
- **Bug 2 regression**: source code of `run_invariants` does not contain `json.load(open(`
- Real fixture test: load `tests/fixtures/step_06/valid_full.json` with sample data
- **Bug 6 regression (integration)**: rule with var pointing to missing key → `evaluable=False`

**Verify**: `pytest tests/test_invariants.py -v`

---

### T8: Write plan to findings directory

**File**: `docs/audit/findings/r1_plan.md` (NEW — directory to be created)
**Subagent**: `general-purpose`

Copy the finalized plan to the findings directory.

---

## Execution Strategy

### Wave 1 — Parallel (6 subagents, all independent)
Launch T3, T4a, T4b, T4c, T4d, T4e simultaneously.

### Wave 2 — Sequential (1 subagent)
Launch T2 (invariants.py fixes). Most complex task — worktree isolation.

### Wave 3 — Sequential (1 subagent)
After T2 completes, launch T7. Subagent MUST read the modified `invariants.py` before writing tests.

### Wave 4 — Sequential (1 subagent)
Launch T8 (write plan doc).

### Final Gate
```bash
pytest tests/ -v --tb=short
```
Full suite must pass with zero failures.

---

## Known Issues (out of scope for R1)

| Issue | Impact | Recommended Future Review |
|-------|--------|---------------------------|
| `"## B4 Metadata Contract"` section header missing from ALL 33 prompt files | Tests in `test_prompt_contracts.py` skip via `continue` — no Output Contract validation is happening | Prompt hygiene review |
| `_tiny_eval` only supports 12 operators (after fixes) | Expressions using unsupported operators → `evaluable=False`. Sufficient for current fixtures. | Operator expansion if specs start using more |
| `policy_ref` is required in schema but `run_invariants` doesn't check it | Evaluator only processes `expression`; `policy_ref` is governance | Governance review |

---

## Out of Scope (confirmed exclusions)

| Item | Reason |
|------|--------|
| `"## B4 Metadata Contract"` string literals in tests | Section delimiters, not naming |
| `B5` comment in `test_traceability_closure.py:155` | Version note, not batch naming |
| `test_cli.py:142` `"## B4 Metadata Contract"` | Fixture data, not naming |
| Adding operators beyond `empty` and `!=` | Only confirmed needed operators |
| Changing `run_invariants()` signature | Only add fields to result dict |
| External dependencies | All fixes use stdlib only |
| CHANGELOG update | Internal fixes, no version bump |

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| T2 breaks existing tests | Worktree isolation + immediate `pytest tests/ -x -q` |
| String literal renames break tests | "DO NOT rename" instructions + grep verification counts |
| T7 tests don't match T2 implementation | T7 blocked on T2; subagent reads modified file first |
| `evaluable` field breaks CLI output | CLI uses `json.dumps(res)` — extra key is additive |
| `isinstance(ok, bool)` too strict | Correct: bare `var` is not a boolean judgment; comparison/logic ops always return bool |

---

## Implementation Results

**Status: IMPLEMENTED** — All tasks completed, 444 tests passing (391 original + 53 new).

### Changes Made

| Task | File | Summary |
|------|------|---------|
| T2 | `tools/specdev_tools/validation/invariants.py` | 6 bug fixes (None-safe comparisons, `!=`/`empty` operators, file handle leak, `[` parsing, `evaluable` field, language handling) |
| T3 | `tools/specdev_tools/cli.py` | File handle leak fix at line 221 |
| T4a | `tests/test_schema_contracts.py` | 4 function renames |
| T4b | `tests/test_prompt_contracts.py` | 1 function rename |
| T4c | `tests/test_spec_quality_lint.py` | 1 function rename |
| T4d | `tests/test_migration_templates.py` | 1 function rename + 1 docstring |
| T4e | `tests/test_prompt_schema_sync.py` | 2 function renames |
| T7 | `tests/test_invariants.py` (NEW) | 53 tests — 43 unit + 10 integration, regression coverage for all 6 bugs |
| T8 | `docs/audit/findings/r1_plan.md` (NEW) | This document |
