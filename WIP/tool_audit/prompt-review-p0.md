# Prompt Review: P0 — Baseline Capture

## Claims Verified

| Claim | Source Line | Verified Against | Match? |
|-------|-----------|-----------------|--------|
| Tests collected: 830 | L88 | `pytest tests/ --co -q` | YES |
| Source files: 61 | L88 | `find tools/specdev_tools -name '*.py' \| wc -l` | YES |
| Source LOC: 13,228 | L89 | `find ... \| xargs wc -l \| tail -1` | YES |
| Test .py files: 73 | L90 | `find tests -name '*.py' \| wc -l` | YES |
| Schema registry entries: 29 | L96 | `python3 -c "import json; print(len(...))"` | YES |
| CLI subcommands: 25 | L97 | `grep -c 'sub.add_parser' tools/specdev_tools/cli.py` | YES |
| pyproject.toml version: 0.4.0 | L104 | `grep 'version' tools/pyproject.toml` | YES |
| Test fixture files: 133 | L102 | `find tests/fixtures -type f \| wc -l` | YES |
| Schema files: 24 | L103 | `find schema -name '*.schema.json' \| wc -l` | YES |
| PROMOTABLE_PAIRS: 18 | L101 | Python import + len() | YES |

## Issues Found

### MUST_FIX

**MF-1: Error code counting command has Python SyntaxError**

- **Location**: Lines 48-58, command #12
- **Problem**: The f-string expressions use `\"` (backslash-escaped double quotes) inside f-string curly braces, which is a SyntaxError in all Python 3 versions:
  ```python
  print(f'E-codes: {len([c for c in codes if c.startswith("\"E")])}')
  ```
  Error: `SyntaxError: f-string expression part cannot include a backslash`
- **Impact**: Command #12 will crash and produce no output. An agent following this prompt literally will fail on this step.
- **Fix**: Replace the f-string comprehension with a pre-computed variable:
  ```python
  e_codes = [c for c in codes if c[1] == 'E']
  w_codes = [c for c in codes if c[1] == 'W']
  print(f'E-codes: {len(e_codes)}')
  print(f'W-codes: {len(w_codes)}')
  ```

**MF-2: Unused `ast` import in error code command**

- **Location**: Line 50
- **Problem**: `import re, ast` — `ast` is never used in the command. While not a crash, it signals the command was not tested end-to-end.
- **Fix**: Remove `ast` from the import.

### SHOULD_FIX

**SF-1: No resilience against venv not being active**

- **Location**: Lines 3-5, 10-11
- **Problem**: The prompt says "Assumes venv `devspec_env` is active" and provides `source devspec_env/bin/activate` — but command #12 uses `from specdev_tools.core.errors import PROMOTABLE_PAIRS` which requires the package to be installed. If the venv is not active or specdev_tools is not installed, this will fail with an ImportError. The prompt does not instruct the agent on how to handle this failure.
- **Fix**: Add a note: "If any Python import fails, ensure specdev_tools is installed: `pip install -e ./tools`"

**SF-2: No error handling guidance**

- **Problem**: The prompt provides 15 commands but no guidance on what to do if a command fails. An agent encountering a failure on command #12 (guaranteed to fail — see MF-1) has no fallback instructions.
- **Fix**: Add a section: "If any command fails, record the error in the 'Actual' column and note it in the Drift section."

**SF-3: `--co` flag may confuse agents unfamiliar with pytest**

- **Location**: Line 14
- **Problem**: `pytest tests/ --co -q` uses the `--co` shorthand for `--collect-only`. While valid, it is less discoverable. Minor readability concern.
- **Fix**: Use `--collect-only` for clarity.

### MINOR

**MI-1: Template column header says "Expected (from ground truth)" but ground truth file is not referenced**

- **Location**: Lines 84-104
- **Problem**: The template includes expected values from the ground truth but does not tell the agent where the ground truth file is. An agent cannot verify whether the "Expected" values are correct without knowing the source.
- **Fix**: Add a line: "Expected values sourced from `WIP/tool_audit/p0-ground-truth-FINAL.md`"

**MI-2: No timestamp format specified**

- **Location**: Line 79
- **Problem**: `{timestamp}` placeholder has no format guidance. Agents may use inconsistent formats.
- **Fix**: Specify ISO 8601: `{YYYY-MM-DDTHH:MM:SSZ}`

**MI-3: Missing `--branch` or branch detection command**

- **Location**: Line 80
- **Problem**: Template expects `{branch}` but no command to capture it is in the commands list.
- **Fix**: Add `git rev-parse --abbrev-ref HEAD` to the commands section.

## Gaps

1. **No command to verify tests pass**: Command #1 uses `pytest tests/ -q 2>&1 | tail -3` which shows the last 3 lines of quiet output, but this may not capture individual failures if the summary wraps. Consider `pytest tests/ -q --tb=no 2>&1 | tail -1` for a cleaner pass/fail line.
2. **No hash/commit capture**: The baseline should record the exact commit SHA for reproducibility. Add `git rev-parse HEAD`.
3. **Missing ground truth reference for validation**: The prompt tells the agent to compare against expected values but does not provide the ground truth file path for cross-reference.

## Verdict: APPROVED_WITH_FIXES

The P0 prompt is structurally sound and its expected values match the live codebase. However, **MF-1 is a blocking bug** — command #12 will crash due to a Python SyntaxError. This must be fixed before the prompt can be used reliably. All other issues are minor or advisory.
