# P1-C: Hardcoding, Assumptions & Magic Values Analysis

Agent Type: Explore (very thorough)
Repo Root: /Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/

## Objective

Find hardcoded values, magic strings/numbers, implicit assumptions, and hallucinated references across the codebase. Focus ONLY on hardcoding concerns -- not DRY violations (P1-B), test quality (P1-D), or separation of concerns (P1-B2).

## Scope

All files in:
- `tools/specdev_tools/` (61 Python files, 13,228 LOC)
- `tests/` (73 Python files, 17,709 LOC)

Plus these config/doc files:
- `tools/schema_registry.json` (29 entries)
- `tools/step_order.json` (22 steps)
- `.pre-commit-config.yaml` (2 hooks)
- `CLAUDE.md`
- `tools/pyproject.toml`
- `tools/requirements.txt`
- `tools/command_prefixes.json`
- `scripts/templates/run_specdev.sh`

## CRITICAL: Grep-First Strategy

Do NOT read all 134 Python files sequentially. Instead:

1. **Search first** (in priority order):
   1. Version strings (`"0.3.0"`, `"0.4.0"`, semver patterns)
   2. Hardcoded step numbers (`"04_"`, literal step numbers)
   3. Hardcoded paths (`"spec/"`, `"/schema/"`, `"canon/"`, `"prompts/"`)
   4. Error messages without codes (raw string messages)
   5. Magic numbers/thresholds (numeric literals, score thresholds)
   6. Raw regex patterns, hardcoded enums, `"specdev.local"`
2. **Read matches**: only open files with 2+ suspicious matches
3. **Analyze context**: determine if hardcoding is justified (e.g., a test fixture value) or problematic (e.g., a production path assumption)

## Known Context (from verified ground truth)

Use these facts to calibrate your analysis:

### Schema System
- Schema `$id` format: `https://specdev.local/schema/...` (URL-based, not URN)
- Schema registry has 29 entries (both P0 agents miscounted as 30)
- Steps 16a, 16b, 16c all map to `schema/16_impl_context.schema.json`
- 24 schema files total (19 step + 1 seed_manifest + 4 core)

### Step System
- Step numbers: `00, 01, 02, 02a, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 13a, 14, 15, 16, 16a, 16b, 16c` (22 steps)
- No step_00.py validator exists (Step 00 has no deep validator)
- 21 step validator files, 21 DEEP_VALIDATORS entries, 21 validate_step_* entry points
- 23 `_load_*` functions across validators

### Canon System
- 29 canon files (1 manifest + 1 aliases.json + 2 schemas + 25 kind files)
- 25 kind files in `canon/kinds/`
- Owner enum validated against `canon/kinds/owner.json`

### Error System
- 77 total error/warning codes: 52 E-codes + 25 W-codes
- Error code families: 1xx (canonical integrity), 2xx (cross-artifact drift), 3xx (proof/review closure), 4xx (canonical registry), 5xx (spec content quality), 59x (R9 cross-step validation, sub-family within 5xx)
- 18 PROMOTABLE_PAIRS (W->E promotion)
- 7 non-promotable W-codes: W110, W120, W130, W140, W552, W570, W596

### Version Info
- **VERSION MISMATCH**: CLAUDE.md claims `0.3.0`, pyproject.toml has `0.4.0`
- No `__version__` string in `__init__.py` (only lazy import shim)
- tools/README.md title says "v3 Full"

### CI/Pre-commit
- 2 pre-commit hooks: dag-lint, extraction-intent-check (both trigger on `tools/step_order.json` or `prompts/prompt_*.md`)
- 4 CI jobs: validate, redteam, deploy-staging, deploy-prod
- CI env: `SPECDEV_WARNINGS_AS_ERRORS=1`, `SPECDEV_REPLAY_DIFF_ERROR_MODE=error`

### Packaging
- `tools/UNKNOWN.egg-info/` exists (orphaned/stale)
- `tools/specdev_tools.egg-info/` exists
- `tools/setup.py` is minimal: `from setuptools import setup; setup()`

## Questions (19)

### Hardcoded Values (7)
1. Which source files contain hardcoded step numbers as string literals (e.g., `"04"`, `"16a"`) outside of test fixtures? Are these loaded from `step_order.json` or inlined?
2. Which files hardcode file path patterns like `"NN_name.json"` or `"spec/NN_"` instead of deriving them from the registry or step_order?
3. Which files hardcode schema URIs (`https://specdev.local/schema/...`) instead of reading from `schema_registry.json`?
4. Which files hardcode field names that should come from schema introspection (e.g., `"functional_requirements"`, `"apis"`, `"invariants"`)?
5. Which files hardcode canonical category names (owner values, NFR categories, trace types) instead of loading from `canon/kinds/`?
6. Which files emit error messages as raw strings without using error codes from `errors.py`?
7. Do the pre-commit hooks hardcode the Python module path or repo-root assumption?

### Assumptions (6)
8. Which files assume the `NN_name.json` file naming convention without validating it? What happens if a file doesn't match?
9. Which files hardcode filesystem paths (e.g., `spec/`, `canon/`, `schema/`, `prompts/`) instead of accepting them as parameters?
10. Which validators assume step_order ordering without loading `step_order.json`? (e.g., "step 04 comes before step 05")
11. Are there Python version assumptions? OS-specific path handling? (`os.path` vs `pathlib`)
12. Which files assume the `canon/` directory structure (e.g., `canon/kinds/` subdirectory, `manifest.json` location)?
13. Do any files assume the schema `$id` format (URL vs URN) without checking?

### Hallucinations (3)
14. Are there error messages referencing wrong step numbers or nonexistent step names?
15. Do any validators check for fields that don't exist in the corresponding schema? (Cross-reference with schema files)
16. Are there references to deprecated or removed features (e.g., old step names, removed CLI commands)?

### Version Strings (1)
17. Search for ALL version strings across the codebase (`0.3.0`, `0.4.0`, `1.0.0`, `v3`, any semver pattern). Are they consistent? List every location.

### Magic Numbers (2)
18. Which files contain numeric thresholds without named constants? (e.g., coverage percentages, length limits, timeout values, score thresholds like the 0.9 Self-Audit Gate)
19. Which files contain raw regex patterns that could be centralized? (List the patterns and where they appear)

## Output Format

Write findings to: `WIP/tool_audit/p1-out-hardcoding.md`

Use this format for each finding:

```
### FINDING-H{N}: {short title}

- **Severity**: critical | high | medium | low | info
- **Category**: HARDCODED_VALUE | ASSUMPTION | HALLUCINATION | MAGIC_NUMBER
- **Location**: {file}:{line} (or {file} if spread across file)
- **Description**: {what is hardcoded/assumed/hallucinated}
- **Current value**: {the literal value found}
- **Should be**: {what it should reference or how it should be sourced}
- **Recommendation**: {specific fix}
```

**Limit**: 200 lines maximum. Prioritize critical and high severity findings. Group related minor findings.

## Exclusions

Do NOT report:
- DRY violations (duplicate `_load_fr_ids` etc.) -- that is P1-B scope
- Test quality issues (weak assertions, missing coverage) -- that is P1-D scope
- Separation of concerns (validation/ importing from canonical/) -- that is P1-B2 scope
- Hardcoded values in test fixtures that are intentionally fixture data
- Schema `$id` values in schema files themselves (those ARE the source of truth)
