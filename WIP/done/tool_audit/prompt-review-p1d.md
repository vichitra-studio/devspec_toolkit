# Prompt Review: P1-D (Test Quality, Fixtures & Coverage Analysis)

## Claims Verified

| # | Claim | Source Line | Verified Against | Match? |
|---|-------|-----------|-----------------|--------|
| 1 | conftest.py LOC = 46 | L12 | `wc -l tests/conftest.py` = 46 | YES |
| 2 | integration/conftest.py LOC = 40 | L13 | `wc -l tests/integration/conftest.py` = 40 | YES |
| 3 | 50 unit test files | L14 | `find tests -name "test_*.py" -maxdepth 1 \| wc -l` = 50 | YES |
| 4 | 14,690 unit test LOC | L14 | Ground truth section 2.2 | YES |
| 5 | 21 integration test files | L15 | `find tests/integration -name "test_*.py" \| wc -l` = 21 | YES |
| 6 | 2,933 integration test LOC | L15 | Ground truth section 2.2 | YES |
| 7 | 133 test fixture files | L16 | `find tests/fixtures -type f \| wc -l` = 133 | YES |
| 8 | 22 fixture directories + 1 top-level file | L16, L27 | `find tests/fixtures -maxdepth 1 -type d` = 22 subdirs + `tests/fixtures/14_roadmap.json` top-level | YES |
| 9 | 130 JSON + 3 non-JSON fixture files | L28 | `find tests/fixtures -name "*.json" -type f \| wc -l` = 130; 3 non-JSON in dependency_order/ (.md, 2x .txt) | YES |
| 10 | spec/ has 3 files (.gitkeep, 05_interface_contracts.json, common/seed_manifest.json) | L17, L30-34 | `find spec -type f \| sort` = exactly these 3 | YES |
| 11 | 830 tests, 830 passed, 36.16s | L19, L24 | Ground truth section 1 | YES |
| 12 | 73 total test Python files (50 + 21 + 2) | L19, L25 | `find tests -name "*.py" -type f \| wc -l` = 73 | YES |
| 13 | 17,709 total test LOC | L19 | Ground truth section 2.2 | YES |
| 14 | conftest.py uses `parents[1]`, integration/conftest.py uses `parents[2]` | L53-55 | Direct file reads confirm: `Path(__file__).resolve().parents[1]` and `parents[2]` | YES |
| 15 | Shared fixtures (5): repo_root, schema_root, spec_root, canon_root, fixtures_root | L57 | Both conftest files define exactly these 5 fixtures | YES |
| 16 | migration_prompts_root only in tests/conftest.py | L58 | integration/conftest.py has 5 fixtures; top-level has 6 (adds migration_prompts_root) | YES |
| 17 | test_step_11.py does file I/O from spec/ | L62-73 | Direct read of test_step_11.py confirms load_json_file calls at lines 58-94 | YES |
| 18 | test_r9_cli.py = 286 LOC | L38 | `wc -l tests/test_r9_cli.py` = 286 | YES |
| 19 | test_r9_cross_step.py = 1047 LOC | L39 | `wc -l tests/test_r9_cross_step.py` = 1047 | YES |
| 20 | test_r9_forward_replay.py = 648 LOC | L43 | `wc -l tests/test_r9_forward_replay.py` = 648 | YES |
| 21 | test_r9_hallucination.py = 584 LOC | L44 | `wc -l tests/test_r9_hallucination.py` = 584 | YES |
| 22 | R9 tasks: T18, T20, T22, T24, T26, T28 | L50 | `grep -r "R9/T" tools/specdev_tools/` confirms T18, T20, T22, T24, T26, T28 | YES |
| 23 | errors.py = 186 LOC | L79 | `wc -l tools/specdev_tools/core/errors.py` = 186 | YES |
| 24 | governance.py = 37 LOC | L82, L118 | `wc -l tools/specdev_tools/validation/governance.py` = 37 | YES |
| 25 | json_utils.py = 345 LOC | L85 | `wc -l tools/core/json_utils.py` = **499** | **NO** |

## Issues Found

### MUST_FIX

**MF-1: json_utils.py LOC is wrong (345 claimed, 499 actual)**

- **Location**: L85 ("tools/core/json_utils.py (345 -- standalone, outside specdev_tools package)")
- **Problem**: The file is 499 lines, not 345. This error originates from the ground truth document (section on tools/core/json_utils.py) and was propagated into this prompt. The agent using this prompt will have an incorrect baseline for coverage analysis of this module.
- **Impact**: Medium. An agent assessing test coverage for json_utils.py would underestimate the untested surface area by ~31%.
- **Fix**: Change "345" to "499".

**MF-2: Validation module count "18 modules" is ambiguous/incorrect**

- **Location**: L80 ("tools/specdev_tools/validation/: 18 modules + validators/ (21 step files + __init__.py)")
- **Problem**: `find tools/specdev_tools/validation -maxdepth 1 -name "*.py" -not -name "__init__.py" \| wc -l` returns 17, not 18. The count of 18 only works if you include `__init__.py`, but then saying "+ validators/" separately creates a double-counting ambiguity because `validators/__init__.py` is also a file. The phrasing "18 modules + validators/" suggests 18 non-init modules plus the validators subpackage.
- **Fix**: Change to "17 modules + __init__.py + validators/ (21 step files + __init__.py)" or simply "18 .py files (including __init__.py) + validators/ subpackage".

### SHOULD_FIX

**SF-1: spec/ file I/O section should note load_json_file's graceful handling**

- **Location**: L75 ("The `load_json_file` function likely returns None or handles missing files gracefully.")
- **Problem**: The word "likely" is an assumption. The actual code (verified in test_step_11.py lines 14-29) shows the function prints a warning and returns `None` when the file doesn't exist. This is a verified fact, not a guess. The prompt should state it definitively.
- **Fix**: Change "likely returns None or handles missing files gracefully" to "returns None and prints a warning when the file doesn't exist (verified in test_step_11.py:14-29)".

**SF-2: Question 5 (integration conftest deletion) contains a misleading framing**

- **Location**: L106 ("Can the integration conftest be deleted entirely, with tests inheriting from the top-level conftest?")
- **Problem**: The question's parenthetical note correctly identifies that `REPO_ROOT` resolution differs by necessity (`parents[1]` vs `parents[2]`), but the main question asks if the integration conftest can be "deleted entirely." This is a leading question that implies it might be deletable, when the `parents[N]` difference makes it structurally necessary (pytest fixtures are resolved relative to the conftest file location). The agent could waste tokens exploring a non-viable option.
- **Fix**: Reframe to: "Given that both conftest files exist primarily to set REPO_ROOT at different directory depths, could they be refactored to share a common helper? Or is the duplication justified by pytest's fixture scoping model?"

**SF-3: R9 test overlap pairs (Q14) should mention LOC for comparison targets**

- **Location**: L120-126
- **Problem**: The prompt provides R9 file LOC counts (L38-47) but doesn't provide LOC for the comparison targets (e.g., `test_forward_replay_check.py`, `test_hallucination_lint.py`). Without these, the agent must read each file to understand scope, which wastes tokens.
- **Fix**: Add LOC counts for comparison targets. From ground truth: `test_forward_replay_check.py` (320), `test_hallucination_lint.py` (320), `test_spec_quality_lint.py` (140), `test_validate_integration.py` (419), `test_cli.py` (1801).

**SF-4: Source module coverage section missing some modules**

- **Location**: L78-85
- **Problem**: The list includes core/, validation/, canonical/, generation/, migration/, cli.py, and json_utils.py but omits:
  - `tools/specdev_tools/__init__.py` (45 LOC) -- contains lazy import shim
  - `tools/specdev_tools/validation/_extraction_intent_parser.py` (124 LOC) -- prefixed with `_` so easily missed
  - `tools/specdev_tools/validation/extraction_intent_check.py` (118 LOC)
  - `tools/specdev_tools/validation/dag_lint.py` (195 LOC)

  These are all modules that need test coverage analysis. The prompt says "18 modules" for validation/ which would include them, but listing them explicitly would help the agent.
- **Fix**: Either list all 17 validation modules explicitly or note that the "18 modules" includes `__init__.py`, `_extraction_intent_parser.py`, `extraction_intent_check.py`, `dag_lint.py`, etc.

### MINOR

**M-1: "zero skips/xfails" mentioned twice**

- **Location**: L19 and L164
- **Problem**: L19 says "830 tests (all passing, zero skips/xfails)" and then L164 says "Do NOT report: Zero skips/xfails (this is known context, not a finding)". This is redundant -- the exclusion in L164 is sufficient.
- **Fix**: Remove "zero skips/xfails" from L19 to save tokens, or keep both if belt-and-suspenders is intentional.

**M-2: Question 22 about inline JSON blobs is very open-ended**

- **Location**: L137
- **Problem**: Asking "Are there inline JSON blobs in test files that duplicate existing files in tests/fixtures/?" across 71 test files is extremely broad. Without specific files to check, the agent will need to scan all 71 test files against 133 fixture files -- a combinatorial explosion.
- **Fix**: Narrow scope: "Check the 10 largest unit test files (by LOC) for inline JSON blobs that could be extracted to tests/fixtures/."

**M-3: 200-line output limit may be tight for 22 questions**

- **Location**: L156
- **Problem**: Same issue as P1-C. 22 questions across 73 test files + 133 fixtures with a 200-line limit is aggressive. The finding format is ~7 lines per finding, allowing ~28 findings max.
- **Fix**: Increase to 300 lines or reduce questions to 18 (drop M-priority items like Q22).

## Verdict: APPROVED_WITH_FIXES

The prompt is well-structured with accurate Known Context for nearly all claims. The conftest comparison is correct and detailed. Test file counts (50 unit, 21 integration, 2 conftest) are all verified accurate. Fixture counts (133 files, 22 directories, 130 JSON + 3 non-JSON) are all correct. The two must-fix items are: (1) json_utils.py LOC is wrong by 154 lines (a ground truth propagation error), and (2) the validation module count is ambiguous. Neither is fatal but both could mislead the analysis agent.
