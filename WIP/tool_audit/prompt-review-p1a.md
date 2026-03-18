# Prompt Review: P1-A — Structure & Wiring Analysis

## Claims Verified

| Claim | Source Line | Verified Against | Match? |
|-------|-----------|-----------------|--------|
| cli.py is 757 LOC | L16 | `wc -l tools/specdev_tools/cli.py` = 757 | YES |
| 25 subcommand registrations | L16 | `grep -c 'sub.add_parser' cli.py` = 25 | YES |
| __init__.py (top-level) is 45 LOC | L17 | `wc -l` = 45 | YES |
| core/__init__.py is 12 LOC | L17 | `wc -l` = 12 | YES |
| migration/__init__.py is 18 LOC | L17 | `wc -l` = 18 | YES |
| validators/__init__.py is 11 LOC | L17 | `wc -l` = 11 | YES |
| 29 schema registry entries | L19 | `python3 -c "import json; print(len(...))"` = 29 | YES |
| 22 steps in step_order.json | L20 | Ground truth + step list | YES |
| errors.py is 186 LOC | L21 | `wc -l` = 186 | YES |
| registry.py is 85 LOC | L21 | `wc -l` = 85 | YES |
| trace_types.py is 53 LOC | L21 | `wc -l` = 53 | YES |
| changelog_parser.py is 394 LOC | L21 | `wc -l` = 394 | YES |
| json_utils.py is 345 LOC | L22 | `wc -l` = **499** | **NO** |
| command_prefixes.json has 20 prefixes | L23 | Parsed JSON: 20 items in `allowed_prefixes` | YES |
| tools/context/ is empty | L23 | `ls tools/context/` shows nothing | YES |
| 29 canon files | L25 | `find canon -type f \| wc -l` = 29 | YES |
| 25 kinds in canon/kinds/ | L25 | `find canon/kinds -type f \| wc -l` = 25 | YES |
| 41 prompt files (22+19) | L26 | `find prompts -type f \| wc -l` = 41 | YES |
| 2 pre-commit hooks | L27 | `.pre-commit-config.yaml` has dag-lint + extraction-intent-check | YES |
| ci.yml has 119 lines | L33 | `wc -l` = **118** | **NO** |
| 4 CI jobs | L33 | `yaml.safe_load` shows 4 job keys | YES |
| setup.py is stub | L18 | `cat tools/setup.py` = `from setuptools import setup; setup()` | YES |
| 4 deps in requirements.txt | L30 | `cat tools/requirements.txt` = 4 lines | YES |
| No __version__ in __init__.py | L49 | `grep '__version__'` returns nothing | YES |
| 21 step validator files | L38 | `find ... step_*.py \| wc -l` = 21 | YES |
| No step_00 validator | L46 | `ls ... step_00.py` exits 1 (not found) | YES |
| 21 DEEP_VALIDATORS entries | L39 | `grep -c 'lambda instance'` = 21 | YES |
| 7 align sub-actions | L41 | `choices=[...]` in cli.py has 7 items | YES |
| 2 --json flag subcommands | L44 | `grep -n '\-\-json' cli.py` shows lines 54, 117 | YES |
| UNKNOWN.egg-info has 4 files | L32 | `ls \| wc -l` = 4 | YES |
| specdev_tools.egg-info has 6 files | L32 | `ls \| wc -l` = 6 | YES |

## Issues Found

### MUST_FIX

**MF-1: json_utils.py LOC count is wrong — 499, not 345**

- **Location**: Line 22
- **Problem**: The prompt states `tools/core/json_utils.py (345 LOC)`. Actual line count is 499. This is a 44% discrepancy.
- **Source of error**: The ground truth document also states 345 LOC, meaning this error was inherited from the ground truth consolidation (possibly the file was modified between ground truth capture and now).
- **Impact**: An agent reading this file will encounter a substantially larger file than expected. If the agent uses 345 as a "budget" or verification check, it will flag a false discrepancy.
- **Fix**: Update to `tools/core/json_utils.py (499 LOC)`.

### SHOULD_FIX

**SF-1: ci.yml line count is 118, not 119**

- **Location**: Line 33
- **Problem**: The prompt says "119 lines" but `wc -l .github/workflows/ci.yml` returns 118. Off by one.
- **Impact**: Low — unlikely to cause agent confusion, but factual inaccuracy undermines trust in the prompt's precision.
- **Fix**: Update to "118 lines".

**SF-2: No explicit instruction to verify claims vs. live codebase**

- **Problem**: The prompt provides extensive "Known Context from Ground Truth" (lines 36-50) with specific numbers. However, it does not instruct the agent to verify these numbers against the live codebase. An agent might simply trust the ground truth values without checking, missing any drift.
- **Fix**: Add a note: "Verify all counts in 'Known Context' against the live codebase. Report any discrepancies as findings."

**SF-3: 8 init files listed but only 7 with LOC in the file list**

- **Location**: Line 17
- **Problem**: The prompt says "All 8 init files" and lists 8 paths, but `migration/scripts/__init__.py` is listed as "0 LOC". This is correct (the file is empty), but the prompt groups it with the others without noting this is an empty placeholder. The Q8 question asks about "all 8 init files" which could confuse an agent into expecting substantive content in all 8.
- **Impact**: Negligible — but the framing slightly overstates the number of init files worth auditing.
- **Fix**: Note which init files are empty/trivial (canonical/, generation/, validation/, migration/scripts/ are all 0-1 LOC).

**SF-4: Missing file read for `tools/trace_matrix.json`**

- **Location**: Line 31
- **Problem**: The prompt states "empty matrix with all-zero counters" and "last modified 2025-02-22" but does not include it in the explicit read list (lines 14-33). Since the file is referenced in Q21, the agent needs to read it, but it is only described, not listed as a file to read.
- **Fix**: Add `tools/trace_matrix.json` to the explicit read list.

### MINOR

**MI-1: "200 lines" output limit may be too tight**

- **Location**: Line 109
- **Problem**: The prompt asks 22 questions across 5 categories with a finding format that requires 6 fields per finding, plus a PASS section. If the agent finds 10+ issues, 200 lines is tight. The finding template alone is 8 lines per finding.
- **Fix**: Consider raising to 300 lines or adding "prioritize MUST_FIX findings if approaching limit."

**MI-2: Docs directory description is vague**

- **Location**: Line 29
- **Problem**: `docs/ directory (extensive subdirectory tree: README.md, agents/, architecture/, audit/, developers/, ops/, plans/, prompts/)` — this is a list of subdirs, but the prompt does not specify what the agent should look for in docs/. Q22 asks about documentation accuracy but only mentions CLAUDE.md and tools/README.md. The docs/ dir is listed as a file to read but without a clear audit question.
- **Fix**: Either remove docs/ from the read list (if Q22 covers documentation sufficiently) or add a specific question about docs/ contents.

**MI-3: Q17 asks to "draw" a dependency graph**

- **Location**: Line 78
- **Problem**: "Draw the inter-package dependency graph" — agents produce text, not visual diagrams. The word "draw" is ambiguous. The agent might attempt ASCII art, a structured list, or skip it entirely.
- **Fix**: Rephrase to "List the inter-package dependency edges as source -> target pairs" or "Describe the dependency graph as a list of edges."

**MI-4: Q7 asks a design judgment question**

- **Location**: Line 62
- **Problem**: "Should others (e.g., matrix, canonical-lint) also support it?" — this is a design opinion question, not an audit factual question. An audit agent should report what IS, not opine on what SHOULD BE.
- **Fix**: Rephrase to: "List all subcommands that produce structured data but lack a --json flag."

## Gaps

1. **No instruction to check `tools/step_order.json` content structure**: The prompt asks Q3 to verify step_order.json's list matches other sources, but does not instruct the agent to read step_order.json. It is listed in the read list (L20) but an agent might only check the step count (22) without examining the dependency edges.

2. **Missing Q about `scripts/` directory**: 6 script files are listed (L24) but no question specifically audits whether these scripts are functional, tested, or referenced. Q4 only checks run_specdev.sh.

3. **No question about test coverage of CLI wiring**: The prompt audits CLI wiring (Q1-Q7) but never asks whether there are tests that verify the wiring (e.g., integration tests that exercise each subcommand).

## Verdict: APPROVED_WITH_FIXES

The P1-A prompt is well-structured with thorough scope and precise questions. The file read list is comprehensive and the "Known Context from Ground Truth" section provides useful anchoring. However, **MF-1 is a factual error** (json_utils.py LOC is 499, not 345) that should be corrected before use. The CI line count (SF-1) is a minor off-by-one. The prompt's overall quality is high — the 22 questions cover wiring, structure, imports, packaging, and documentation systematically with minimal overlap.
