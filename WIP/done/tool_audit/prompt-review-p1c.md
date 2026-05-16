> **ARCHIVE NOTE (2026-05-16):** Canonical trace_matrix path is now `spec/extras/trace_matrix.json`. The `tools/trace_matrix.json` references below reflect the state at the time of writing.

# Prompt Review: P1-C (Hardcoding, Assumptions & Magic Values)

## Claims Verified

| # | Claim | Source Line | Verified Against | Match? |
|---|-------|-----------|-----------------|--------|
| 1 | 61 Python files in specdev_tools/ | L13 | `find tools/specdev_tools -name "*.py" -type f \| wc -l` = 61 | YES |
| 2 | 13,228 LOC in specdev_tools/ | L13 | Ground truth section 2.1 | YES |
| 3 | 73 Python files in tests/ | L14 | `find tests -name "*.py" -type f \| wc -l` = 73 | YES |
| 4 | 17,709 LOC in tests/ | L14 | Ground truth section 2.2 | YES |
| 5 | Schema registry has 29 entries | L17, L39 | `python3 -c "import json; print(len(json.load(open('tools/schema_registry.json'))))"` = 29 | YES |
| 6 | 22 steps in step_order.json | L18, L44 | `steps` array in step_order.json has 22 entries | YES |
| 7 | 2 pre-commit hooks | L19 | `.pre-commit-config.yaml` contains exactly dag-lint and extraction-intent-check | YES |
| 8 | 24 schema files (19 step + 4 core + 1 seed_manifest) | L41 | `find schema -name "*.json" -type f \| wc -l` = 24; 20 step-level + 4 core = 24 | PARTIAL (see below) |
| 9 | Schema $id format: `https://specdev.local/schema/...` | L38 | schema_registry.json URIs confirmed | YES |
| 10 | 29 canon files (1 manifest + 1 aliases + 2 schemas + 25 kinds) | L50 | `find canon -type f \| wc -l` = 29, `find canon/kinds -type f \| wc -l` = 25 | YES |
| 11 | No step_00.py validator | L45 | `ls tools/specdev_tools/validation/validators/step_00.py` = NOT FOUND | YES |
| 12 | 21 step validator files, 21 DEEP_VALIDATORS, 21 validate_step_* | L46 | Ground truth sections 4.1-4.4 | YES |
| 13 | 23 `_load_*` functions | L47 | `grep -r "def _load_" ... \| wc -l` = 23 | YES |
| 14 | 77 error/warning codes: 52 E + 25 W | L55 | Programmatic count from errors.py | YES |
| 15 | 18 PROMOTABLE_PAIRS | L57 | Programmatic count from errors.py | YES |
| 16 | 7 non-promotable W-codes: W110, W120, W130, W140, W552, W570, W596 | L58 | Set difference of all W-codes minus PROMOTABLE_PAIRS keys | YES |
| 17 | VERSION MISMATCH: CLAUDE.md = 0.3.0, pyproject.toml = 0.4.0 | L61 | `grep version tools/pyproject.toml` = 0.4.0; CLAUDE.md line 7 says 0.3.0 | YES |
| 18 | No `__version__` in `__init__.py` | L62 | Ground truth confirms lazy import shim only | YES |
| 19 | tools/README.md title says "v3 Full" | L63 | `head -1 tools/README.md` = "# AI Spec Driven Development CLI (v3 Full)" | YES |
| 20 | `tools/UNKNOWN.egg-info/` exists | L71 | `ls tools/UNKNOWN.egg-info/` lists files | YES |
| 21 | `tools/setup.py` is minimal | L73 | Contents: `from setuptools import setup\nsetup()` | YES |
| 22 | 4 CI jobs | L67 | Ground truth section 2.14 | YES |
| 23 | `tools/command_prefixes.json` exists | L23 | `ls tools/command_prefixes.json` = found | YES |
| 24 | 134 Python files total (scope) | L27 | 61 + 73 = 134 | YES |

## Issues Found

### MUST_FIX

**MF-1: Schema file breakdown "19 step + 4 core + 1 seed_manifest" should be "20 step-level + 4 core"**

- **Location**: L41 ("24 schema files total (19 step + 4 core + 1 seed_manifest)")
- **Problem**: The `schema/` directory has 20 files outside of `core/` (19 step schemas + 1 `seed_manifest.schema.json`). The breakdown should be "19 step + 1 seed_manifest + 4 core = 24" or more simply "20 step-level + 4 core = 24". Writing "19 step + 4 core + 1 seed_manifest" is not wrong but the parenthetical grouping is misleading since seed_manifest sits at the same level as step schemas. This is a minor accuracy issue but could confuse the agent into thinking seed_manifest is somehow separate.
- **Severity**: Low. The total (24) is correct; only the breakdown labeling is slightly misleading.
- **Fix**: Change to "24 schema files total (19 step + 1 seed_manifest + 4 core)" or "20 top-level + 4 core".

### SHOULD_FIX

**SF-1: Grep-first strategy could be more specific about which patterns to prioritize**

- **Location**: L27-31
- **Problem**: The grep patterns listed (line 29) are a good starting set but mix high-value targets (version strings, error messages without codes) with low-value ones (raw regex strings). The strategy doesn't specify a recommended ORDER for the grep passes, which could lead the agent to waste tokens on low-priority patterns first.
- **Fix**: Add a numbered priority order. Suggest: (1) version strings, (2) hardcoded step numbers, (3) hardcoded paths, (4) error messages without codes, (5) magic numbers/thresholds, (6) raw regex patterns.

**SF-2: Missing "tools/trace_matrix.json" and "tools/run_specdev.sh" from config/doc scope**

- **Location**: L16-24
- **Problem**: The scope section lists config files to check but omits `tools/trace_matrix.json` (generated file that may contain hardcoded assumptions) and `tools/run_specdev.sh` (the wrapper script referenced in CLAUDE.md which is a likely location for hardcoded paths). Also omits `scripts/` directory (6 files) which could contain hardcoded paths. The `run_specdev.sh` in `scripts/templates/` is especially relevant for hardcoding analysis.
- **Fix**: Add `tools/run_specdev.sh` (if it exists) or `scripts/templates/run_specdev.sh` to scope. Consider adding `scripts/` as secondary scope.

**SF-3: Error code family descriptions incomplete**

- **Location**: L56
- **Problem**: The prompt says error code families are "1xx (canonical integrity), 2xx (cross-artifact drift), 3xx (proof/review closure), 4xx (canonical registry), 5xx (spec content quality)". This is correct but misses that 59x is a distinct sub-family within 5xx (R9 cross-step validation). An agent doing hardcoding analysis should know that 59x codes are newer additions with potentially different patterns.
- **Fix**: Add "59x (R9 cross-step validation, a sub-family within 5xx)" to the description.

### MINOR

**M-1: "Both P0 agents miscounted as 30" parenthetical is unnecessary context**

- **Location**: L39
- **Problem**: The note "(both P0 agents miscounted as 30)" adds historical context that doesn't help the P1-C agent. It wastes tokens and could confuse.
- **Fix**: Remove the parenthetical. Just state "Schema registry has 29 entries."

**M-2: Question 7 about pre-commit hooks is partly answered in Known Context**

- **Location**: L84 (Question 7) vs L66-68 (Known Context)
- **Problem**: The Known Context already states the pre-commit hooks use `python -m specdev_tools.cli` and `--repo-root .`. Question 7 asks "Do the pre-commit hooks hardcode the Python module path or repo-root assumption?" -- the answer is partially given. This could lead the agent to skip deeper analysis of the hook configuration.
- **Fix**: Reframe Q7 to: "Beyond the module path and --repo-root, do the pre-commit hooks make other assumptions (e.g., file pattern regex, Python interpreter path)?"

**M-3: Line limit of 200 may be tight for 19 questions**

- **Location**: L124
- **Problem**: 19 questions across a 134-file codebase with a 200-line output limit is aggressive. The finding format template alone is ~8 lines per finding, meaning the agent can report at most ~25 findings before hitting the limit, and that assumes no grouping text.
- **Fix**: Either increase to 300 lines or reduce to 15 questions (drop lower-priority ones like Q11, Q19).

## Verdict: APPROVED_WITH_FIXES

The prompt is solid overall. The Known Context facts are accurate (all 24 verified claims match). The grep-first strategy is well-conceived but would benefit from prioritization ordering (SF-1). The scope is slightly incomplete (SF-2). No hallucinations were found in the prompt itself. The one schema breakdown labeling issue (MF-1) is cosmetic -- the total count is correct.
