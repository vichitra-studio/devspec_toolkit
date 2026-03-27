# Prompt Fix Report: P0 + P1-A

Applied: 2026-03-18

## P0 Fixes (p0-prompt-baseline.md)

### MUST_FIX

| ID | Issue | Fix Applied |
|----|-------|-------------|
| MF-1 | Python SyntaxError in command #12: f-string with backslash-escaped quotes inside braces | Rewrote to use pre-computed `e_codes`/`w_codes` variables outside f-string. Verified: command runs and outputs correct counts (77 total, 52 E, 25 W, 18 PROMOTABLE_PAIRS). |
| MF-2 | Unused `ast` import in command #12 | Removed `ast` from `import re, ast` line. |

### SHOULD_FIX

| ID | Issue | Fix Applied |
|----|-------|-------------|
| SF-1 | No resilience against missing venv/package | Added pip install fallback note: "If any Python import fails, ensure specdev_tools is installed: `pip install -e ./tools`" |
| SF-2 | No error handling guidance | Added instruction: "If any command fails, record the error message in the 'Actual' column and note it in the Drift section." |
| SF-3 | `--co` flag less discoverable than `--collect-only` | Replaced `--co` with `--collect-only`. |

### MINOR (skipped)

MI-1 through MI-3: Not applied (trivial/cosmetic, low impact).

---

## P1-A Fixes (p1-prompt-structure.md)

### MUST_FIX

| ID | Issue | Fix Applied |
|----|-------|-------------|
| MF-1 | json_utils.py LOC stated as 345, actual is 499 | Updated both occurrences (lines 22 and 68) from "345 LOC" to "499 LOC". Verified: `wc -l tools/core/json_utils.py` = 499. |

### SHOULD_FIX

| ID | Issue | Fix Applied |
|----|-------|-------------|
| SF-1 | ci.yml line count 119 vs actual 118 | Updated from "119 lines" to "118 lines". Verified: `wc -l .github/workflows/ci.yml` = 118. |
| SF-2 | No instruction to verify ground truth claims | Added note before Known Context section: "Verify all counts in 'Known Context from Ground Truth' against the live codebase. Report any discrepancies as findings." |
| SF-4 | trace_matrix.json not explicitly in read list | Added "read this file" annotation to the trace_matrix.json entry. |

### SHOULD_FIX (skipped)

SF-3 (init file empty/trivial annotation): Not applied -- the existing text already notes "0 LOC" for the empty file, which is sufficient.

### MINOR (skipped)

MI-1 through MI-4: Not applied (cosmetic/design-opinion items).

---

## Ground Truth Fix (p0-ground-truth-FINAL.md)

| Issue | Fix Applied |
|-------|-------------|
| json_utils.py LOC stated as 345, actual is 499 | Updated "345 lines" to "499 lines". |

---

## Verification

- Python command #12 tested end-to-end: outputs correct counts (77/52/25/18).
- json_utils.py line count verified: 499.
- ci.yml line count verified: 118.
