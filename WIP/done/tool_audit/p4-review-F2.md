# P4 Fix Plan Final Review (Agent F2 — Implementation Focus)

## Code Feasibility Assessment

### Batch 0: Foundation Modules

| Module | Functions to Extract | Signatures Verified? | Import Path Works? |
|--------|---------------------|---------------------|-------------------|
| core/loaders.py | `load_upstream_ids`, `load_sibling_artifact`, `check_cross_step_refs`, `KEBAB_ID_RE`, `kebab_id_re()`, `load_json_artifact` | YES — see analysis below | YES — `from specdev_tools.core.loaders import ...` follows existing pattern (cf. `from specdev_tools.core.errors import ...`) |
| validation/linter_utils.py | `collect_ids_and_refs`, `iter_json`, `is_reference_context`, `DERIVATION_STOPWORDS`, `CONTENT_STOPWORDS`, `tokenize_free_text`, `check_no_duplicates` | YES — found exact duplicates in hallucination_lint.py and spec_quality_lint.py | YES — `from specdev_tools.validation.linter_utils import ...` works since validation/ is a package |
| core/config.py | `SpecdevConfig`, `get_config()` | YES — verified 12 `os.environ.get("SPECDEV_*")` calls across cli.py, validate.py, forward_replay_check.py | YES — same path as loaders.py |

**Signature analysis for `load_upstream_ids`:**

The plan proposes: `load_upstream_ids(toolkit_root: Path, step_prefix: str, array_key: str, id_field: str, *, fallback_keys: tuple[str,...] = ()) -> set[str]`

Actual existing signatures verified:
- `_load_fr_ids(toolkit_root: str) -> Optional[Set[str]]` — in step_05, step_06, step_07, step_08, step_12, step_13a (6 copies)
- `_load_api_ids(toolkit_root: str) -> Optional[Set[str]]` — in step_05, step_06, step_08, step_11, step_13a, step_15 (note: step_05 has `_load_fr_ids` but no `_load_api_ids`; it validates apis internally)
- `_load_capability_ids(toolkit_root: str) -> Optional[Set[str]]` — in step_04, step_09
- `_load_nfr_ids(toolkit_root: str) -> Optional[Set[str]]` — in step_08, step_12
- `_load_inv_ids(toolkit_root: str) -> Optional[Set[str]]` — in step_08

**ISSUE 1 (MUST_FIX): Return type mismatch.** All existing loaders return `Optional[Set[str]]` (None when file not found). The plan says `load_upstream_ids` returns `set[str]` (empty set on file-not-found). This changes semantics: callers currently check `if fr_ids is None` to emit W590 warnings. The plan's `check_cross_step_refs` helper would need to handle this, but calling code that does `if fr_ids is None: errors.append("W590...")` will silently stop emitting W590 warnings. FIX-001 must either: (a) return `Optional[set[str]]` to preserve None semantics, or (b) the description for each consumer FIX (004-013) must explicitly note that the None/W590 pattern is replaced by `check_cross_step_refs`.

**ISSUE 2 (SHOULD_FIX): step_14 loaders have different signature.** Step_14's `_load_step09_milestone_ids(toolkit_root: str, artifact_path: str | None)` takes two parameters and resolves candidates using artifact_path. The plan's `load_sibling_artifact(artifact_path: Path, sibling_prefix: str, array_key: str, id_field: str)` drops `toolkit_root` entirely. But step_14 loaders check BOTH artifact_path sibling AND toolkit_root/spec/ as fallback. The plan description says "resolves sibling files relative to artifact_path" but the actual code falls back to toolkit_root. `load_sibling_artifact` needs `toolkit_root` as a fallback parameter.

**ISSUE 3 (MINOR): step_08 has `_load_inv_ids` not mentioned.** FIX-007 lists replacing `_load_fr_ids`, `_load_api_ids`, `_load_nfr_ids` in step_08 but step_08 also has `_load_inv_ids` (line 130). The AUDIT refs mention AUDIT-018 (upstream_map pattern) which covers inv_ids, but the explicit list of replacements in FIX-007 item 3 says `_load_nfr_ids` when there are actually 4 loaders in step_08. The description should explicitly list all 4.

**ISSUE 4 (MINOR): `_load_api_ids` count discrepancy.** The plan says "all 5 `_load_api_ids` copies" but I found 6: step_06, step_08, step_11, step_13a, step_15, plus validate.py has its own `_load_component_ids`/`_load_capability_ids` (different pattern). The count should be verified.

### Batch 1: Import Chain Analysis

**Current import patterns in validators:**
- All validators use absolute stdlib imports (`import json`, `import os`, `import re`)
- No validators currently import from `specdev_tools.core.*` — they are standalone modules
- No relative imports used in validators
- `from __future__ import annotations` is consistently used

**Proposed new imports:**
- `from specdev_tools.core.loaders import load_upstream_ids, KEBAB_ID_RE` — works with package structure
- `from specdev_tools.validation.linter_utils import ...` — works for hallucination_lint, spec_quality_lint, forward_replay_check

**Circular import risk:** LOW. The new core/loaders.py and core/config.py modules depend only on stdlib (json, os, re, pathlib). They don't import from validation/ or any other specdev_tools subpackage. The dependency flow is strictly: validators -> core (one-directional).

**conftest.py sys.path manipulation:** Both root and integration conftest.py add `TOOLS_DIR` to `sys.path`. This means `from specdev_tools.core.loaders import ...` will resolve correctly in tests. No issues.

### Batch 2: validate.py Refactor

**Function inventory (537 lines, 21 functions):**
- 4 public functions: `validate_file`, `validate_dir`, `_registry_for`, `_get_step_from_path`
- 5 loader helpers: `_load_json_artifact`, `_load_component_ids`, `_load_capability_ids`, `_load_nfrs_data`, `_load_monitoring_data`
- 1 context builder: `_build_validation_context`
- 1 deep validation dispatcher: `_run_deep_validation` + `DEEP_VALIDATORS` dict
- 5 git helpers: `_detect_git_root`, `_detect_spec_root`, `_is_git_repo`, `_resolve_replay_base_ref`, `_git_ref_exists`, `_git_upstream_branch`, `_git_current_branch`
- 1 utility: `_has_canonical_bootstrap_failure`, `_load_step_order`, `_get_prompt_path`

**FIX-025 risk assessment:**
The plan correctly identifies this as the highest-density file (9 findings). The recommended execution order (imports first, then logic, then docs) is sound. However:

**ISSUE 5 (SHOULD_FIX): FIX-025 attempts too many changes in one task.** 9 sub-steps touching the same 537-line file is risky for an agent. If any sub-step introduces a subtle bug, the test gate may not catch it until later. Consider splitting into 2-3 tasks: (a) loader replacements + config centralization (mechanical), (b) W->E promotion logic fix (behavioral), (c) documentation additions (safe). The plan acknowledges the density but does not split.

**ISSUE 6 (MINOR): validate.py loaders differ from validator loaders.** The loaders in validate.py (`_load_json_artifact`, `_load_component_ids`, etc.) take `(repo_root: str, file_path: str)` — a different signature than the validator loaders that take only `(toolkit_root: str)`. These validate.py loaders use `file_path` to resolve siblings (like step_14). FIX-025 item 3 says "replace with imports from core.loaders" but `load_upstream_ids` has a different interface. The plan needs to clarify whether `_build_validation_context` will use `load_sibling_artifact` or a different loader variant.

### Batch 4: Test Reorganization

**Import pattern analysis:**
- Tests use absolute imports: `from specdev_tools.validation.validators import ...`, `from specdev_tools.canonical.integrity import ...`
- No test imports other test files (grep confirmed: no `import test_` found)
- No relative imports in tests
- Root conftest.py adds `TOOLS_DIR` to `sys.path` at module level

**conftest.py propagation:** Pytest automatically discovers conftest.py in the root `tests/` directory and applies fixtures to all subdirectories. Creating `__init__.py` in each subdirectory (as planned) is correct for pytest discovery. No intermediate conftest.py files needed.

**ISSUE 7 (SHOULD_FIX): conftest.py REPO_ROOT resolution breaks after restructure.** Root conftest.py uses `Path(__file__).resolve().parents[1]` to find repo root. After FIX-038, tests move to `tests/unit/validation/validators/` (depth 4 from repo root). But conftest.py stays at `tests/conftest.py` (depth 1), so `parents[1]` still works. Integration conftest uses `parents[2]`. Both are fine as-is. HOWEVER: the plan mentions FIX-040 wants to "extract shared fixtures into a helper function that takes depth parameter" — this is unnecessary since conftest.py location doesn't change. The plan conflates fixture duplication (root vs integration conftest having identical fixtures) with path depth issues. The real fix for AUDIT-028 is simpler: just have integration/conftest.py import from root conftest or rely on pytest's automatic propagation (which already works — root conftest fixtures are available to all subdirs).

**ISSUE 8 (MINOR): `pyproject.toml` testpaths.** FIX-038 step 7 mentions checking `pyproject.toml` testpaths, but doesn't specify what to do if it's configured. Should verify and update if `testpaths = ["tests"]` is set (it would still work since the root is unchanged).

## Batch Gate Risk Assessment

| Batch | Risk Level | Key Concern | Mitigation in Plan? |
|-------|-----------|-------------|-------------------|
| Batch 0 | LOW | New modules only, no consumers yet | YES — gate runs full test suite, expects no regressions |
| Batch 1 | MEDIUM | 15 parallel import changes across validators | PARTIAL — each task has per-file test gates, but the None->empty-set return type change (Issue 1) could cause silent W590 regression across multiple files |
| Batch 2 | HIGH | FIX-025 changes 9 things in one 537-line file | PARTIAL — test gate exists but task is too dense for safe agent execution (Issue 5) |
| Batch 3 | LOW | Mostly documentation + layer violation completion | YES — full test suite gate |
| Batch 4 | MEDIUM | Moving 50 test files + renaming 10 | PARTIAL — plan correctly uses `pytest --collect-only` to verify discovery, but doesn't mention updating CI config if it references specific test paths |
| Batch 5 | LOW | New test files only, no modifications | YES — each file has its own test gate |
| Batch 6 | LOW | CI config + docs | YES — YAML validation gate |

## Research Alignment Roadmap Check

All 10 ALIGN items are present: ALIGN-1 through ALIGN-10.

**Accuracy of "P4 Progress" notes:**
- ALIGN-3 (Structured Errors): PARTIAL status correct. FIX-017 (error codes), FIX-025 (W->E promotion), FIX-030 (--json) are accurately cited.
- ALIGN-4 (additionalProperties): ACHIEVED status correct.
- ALIGN-7 (--json): PARTIAL status correct. FIX-030 adds --json to 5 commands.
- ALIGN-9 (Pre-commit): PARTIAL status correct. FIX-050 adds CI pytest job.

**Priority ordering assessment:**
The recommended order (ALIGN-6, 9, 7, 3, 1, 8, 2, 10, 5) is sensible. Placing ALIGN-6 (property descriptions) first is good — high impact, low risk. Placing ALIGN-5 (nesting) last is correct given its XL effort and breaking-change nature. The dependency chain ALIGN-1 -> ALIGN-2 and ALIGN-3 -> ALIGN-8 is correctly respected.

**One minor note:** ALIGN-4 is listed as item 10 in the priority order ("already achieved, no action needed"). It would be cleaner to exclude achieved items from the priority list entirely rather than ranking them last.

## Issues Found

### MUST_FIX

**MF-1: Return type semantic change (None vs empty set) in `load_upstream_ids`.**
FIX-001 specifies returning `set[str]` (empty on file-not-found), but all existing callers check `if fr_ids is None` to emit W590 warnings. The plan must either: (a) preserve `Optional[set[str]]` return type, or (b) explicitly document in every Batch 1 consumer FIX that the W590 emission pattern is replaced by `check_cross_step_refs`. Currently, some consumer FIX descriptions (FIX-004, FIX-005, FIX-006) say "replace _load_fr_ids with shared loader" without mentioning the W590 pattern change. If `check_cross_step_refs` handles W590, this must be stated explicitly in each consumer task since an implementing agent will not infer this.

### SHOULD_FIX

**SF-1: `load_sibling_artifact` missing `toolkit_root` fallback.**
Step_14 loaders use a two-candidate pattern: first artifact_path sibling, then toolkit_root/spec/ fallback. The proposed `load_sibling_artifact` signature only takes `artifact_path` with no toolkit_root fallback. Add `toolkit_root: Path | None = None` parameter.

**SF-2: FIX-025 is too dense for safe agent execution.**
9 sub-steps in one 537-line file. Split into at least 2 tasks: mechanical changes (loader replacement, config usage, documentation) and behavioral changes (W->E promotion fix, dedup ordering).

**SF-3: FIX-025 item 3 unclear on validate.py loader replacement.**
validate.py's `_load_json_artifact` and friends have a different interface (taking `file_path` for sibling resolution) than the validator loaders. The plan says "replace with imports from core.loaders" but doesn't specify which core.loaders function replaces `_load_json_artifact` or `_build_validation_context`. These are closer to the `load_sibling_artifact` pattern than `load_upstream_ids`.

**SF-4: step_08 `_load_inv_ids` not explicitly listed in FIX-007.**
step_08.py has 4 loaders (_load_fr_ids, _load_api_ids, _load_inv_ids, _load_nfr_ids) but FIX-007 only explicitly mentions 3. The _load_inv_ids replacement should be listed.

### MINOR

**M-1: `_load_api_ids` count may be off by 1.** Plan says 5 copies; codebase grep shows 6 file matches (step_06, step_08, step_11, step_13a, step_15, plus step_05 has a different pattern for api validation). Verify actual count.

**M-2: FIX-040 over-engineers conftest refactoring.** The "depth parameter" approach is unnecessary — pytest's fixture propagation already handles subdirectory access to root conftest fixtures. The simpler fix: remove duplicate fixtures from integration/conftest.py and rely on root conftest propagation.

**M-3: ALIGN-4 should be excluded from priority list.** It's already achieved; listing it as item 10 in priority order is confusing.

**M-4: pyproject.toml testpaths configuration.** FIX-038 should explicitly check and confirm `testpaths` config won't interfere with the restructured directory layout.

## Verdict: APPROVED_WITH_FIXES

The plan is comprehensive, well-structured, and demonstrates strong understanding of the codebase. The batch ordering and dependency graph are sound. The 3 SHOULD_FIX items (particularly SF-1 on the sibling loader fallback and SF-2 on FIX-025 density) should be addressed before execution to prevent implementation failures. The MUST_FIX on return type semantics is critical — without it, W590 warnings will silently disappear across 6+ validators after Batch 1.
