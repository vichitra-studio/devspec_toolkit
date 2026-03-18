# Tools & Tests Deep Audit — Master Plan

## Scope

Full audit of `tools/specdev_tools/` and `tests/` against 9 dimensions plus research alignment.

## Repo Root

```
/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/
```

## Review Dimensions

1. **Wiring** — CLI subcommands wired to correct handlers; registry entries resolve; imports chain correctly
2. **Structure** — Package layout, module boundaries, dependency direction, naming consistency
3. **DRY / SoC** — Duplicated logic (especially `_load_*` functions), separation of concerns across subpackages
4. **Hardcoding** — Magic strings, hardcoded paths, inline constants that should be configurable
5. **Redundancy** — Dead code, unused imports, orphaned modules, stale packaging artifacts
6. **Test Fixtures** — Fixture coverage per step, fixture quality, missing edge cases, fixture/schema alignment
7. **Error Collection** — Error/warning code completeness, promotion pairs, `SpecError` usage consistency
8. **Gaps / Regressions** — Missing validators, untested paths, known issues, coverage holes
9. **Research Alignment** — Alignment with JSON Schema 2020-12, src/dist split, allErrors, WriteValidatedJSON, URN-based `$id`, pre-commit hooks

## Phases

| Phase | Name | Agents | Depends On | Description |
|-------|------|--------|------------|-------------|
| P0 | Baseline Capture | Inline (no agent) | — | Capture test count, LOC, pass/fail baseline |
| P1 | Parallel Deep Review | 7 agents (P1-A through P1-F) | P0 | Each agent owns an exclusive scope; no file overlap for same purpose |
| P2 | Research Alignment | 1 agent | P0 (runs parallel with P1) | External best-practice comparison |
| P3 | Consolidation | 1 agent | P1 + P2 | Merge all findings, deduplicate, rank by severity |
| P4 | Fix Plan | 1 agent | P3 | Produce ordered fix list with effort estimates |
| P5 | Fix Execution | N agents | P4 | Apply fixes per the plan |
| P6 | Verification | 1 agent | P5 | Re-run baseline, confirm all 830 tests still pass, verify fixes |

## Phase Dependencies

```
P0 → P1 (7 parallel) + P2 (1 parallel) → P3 → P4 → P5 → P6
```

## Output File Naming

- Prompt files: `p{N}-prompt-{concern}.md`
- Output files: `p{N}-out-{concern}.md`

## Existing WIP (unverified prior art)

8 files in `WIP/tools-tests-review-findings-*.md` (approximately 1550 lines total), plus `tools-tests-review-plan-c1.md` and `tools-tests-review-impl-review-c1.md`. These are unverified and may contain stale or inaccurate claims. Agents should use them as hints only, not as ground truth.

---

## Key Codebase Facts (ALL from verified ground truth)

### Test Suite

| Metric | Value |
|--------|-------|
| Tests collected | 830 |
| Tests passed | 830 |
| Tests failed | 0 |
| Tests skipped | 0 |
| Tests xfail | 0 |
| `pytest.mark.skip` / `pytest.mark.xfail` usage | 0 |
| Test run time | 36.16s |

### File Counts

| Category | Count |
|----------|-------|
| Source files (`specdev_tools/`) | 61 |
| Source LOC (`specdev_tools/`) | 13,228 |
| Test `.py` files (all) | 73 |
| Test LOC (all) | 17,709 |
| Unit test files (`tests/test_*.py`) | 50 |
| Unit test LOC | 14,690 |
| Integration test files (`tests/integration/test_*.py`) | 21 |
| Integration test LOC | 2,933 |
| Conftest files | 2 (46 + 40 LOC) |
| Schema files | 24 (19 step + 4 core + 1 seed_manifest) |
| Schema registry entries | 29 |
| Steps in step_order.json | 22 |
| Canon files | 29 (1 manifest + 1 aliases.json + 2 schemas + 25 kind files) |
| Prompt files | 41 (22 step prompts + 19 migration templates) |
| Script files | 6 |
| Spec files | 3 |
| Test fixture files | 133 (across 22 directories + 1 top-level file) |
| Test fixture directories | 22 |

### CLI

| Metric | Value |
|--------|-------|
| CLI subcommands | 25 |
| Align sub-actions | 7 (status, diff, plan, apply, prompts, rollback, validate) |
| `--json` flag commands | 2 (validate, traceability-check) |

### Validators

| Metric | Value |
|--------|-------|
| Step validator files | 21 (no step_00.py — Step 00 has no deep validator) |
| DEEP_VALIDATORS entries | 21 |
| `_load_*` functions | 23 |
| `validate_step_*` entry points | 21 |

### Error System

| Metric | Value |
|--------|-------|
| `errors.py` LOC | 186 |
| Total error/warning codes | 77 |
| E-codes | 52 |
| W-codes | 25 |
| PROMOTABLE_PAIRS | 18 |
| Non-promotable W-codes | 7 (W110, W120, W130, W140, W552, W570, W596) |
| `warnings.warn` occurrences | 12 |
| Exception classes | 3 (SpecdevError, SubmoduleDetectionError, SchemaRegistryError) |

### Version

| Metric | Value |
|--------|-------|
| `pyproject.toml` version | 0.4.0 |
| `CLAUDE.md` version claim | 0.3.0 |
| **Version mismatch** | **Yes** — CLAUDE.md says 0.3.0, pyproject.toml says 0.4.0 |
| `__init__.py` `__version__` | Not defined (only lazy import shim, 45 lines) |

### Code Health

| Metric | Value |
|--------|-------|
| TODO/FIXME in `specdev_tools/` | 0 (only regex patterns for detection) |
| TODO in `tools/core/json_utils.py` | 1 (outside specdev_tools package) |
| `noqa` / `pragma` | 1 (`validators/__init__.py:7`) |
| Pre-commit hooks | 2 (dag-lint, extraction-intent-check) |
| CI jobs | 4 (validate, redteam, deploy-staging, deploy-prod) |
| Stale packaging artifacts | `tools/UNKNOWN.egg-info/` (orphaned) |

### R9 Feature Round

| Metric | Value |
|--------|-------|
| R9 markers in source | 12 unique locations |
| R9 task IDs referenced | T18, T20, T22, T24, T26, T28 |
| New CLI commands from R9 | dag-lint, extraction-intent-check, env-check |
| R9 error code family | 59x (E590-E599, W590-W597) |

### Conftest Diff Summary

- `tests/conftest.py`: 46 LOC, 6 fixtures (`repo_root`, `schema_root`, `spec_root`, `canon_root`, `fixtures_root`, `migration_prompts_root`)
- `tests/integration/conftest.py`: 40 LOC, 5 fixtures (same minus `migration_prompts_root`)
- Key difference: `REPO_ROOT` uses `parents[1]` vs `parents[2]`; integration conftest is **missing** `migration_prompts_root` fixture

### Import Dependency Direction

```
core/       <- leaf dependency (depended on by all)
canonical/  <- depends on core/
generation/ <- depends on core/
validation/ <- depends on core/, canonical/, generation/
migration/  <- depends on core/, generation/
cli.py      <- depends on all subpackages
```

No circular cross-package dependencies.

### `_load_fr_ids` Implementation Differences

Three implementations across step_05, step_06, step_07 — functionally equivalent but differ in style:
- **step_05** (line 85): Inline conditional, variable `fr`, `Optional[Set[str]]` type hint
- **step_06** (line 117): Separate guard clause, variable `item`, intermediate `items`, `Optional[Set[str]]` type hint
- **step_07** (line 83): Inline conditional like step_05, variable `fr`, `set[str] | None` type hint

---

## Research Context Summary

The following external best practices should be evaluated against current implementation during P2:

1. **JSON Schema 2020-12** — Current schemas use `$id` URIs (`https://specdev.local/...`). Evaluate whether the draft version is explicit and whether 2020-12 features (`$dynamicRef`, `prefixItems`) are leveraged or should be.
2. **src/dist split** — Package layout uses flat `tools/specdev_tools/` rather than a `src/` layout. Evaluate impact on editable installs and test isolation.
3. **allErrors mode** — `validate.py` uses `iter_errors` (line 136). Evaluate whether `jsonschema` `allErrors`-equivalent behavior is correctly configured.
4. **WriteValidatedJSON** — Evaluate whether a write-with-validate pattern exists or should exist for spec artifact emission.
5. **URN-based `$id`** — Current `$id` values use `https://specdev.local/...` URLs. Evaluate whether URN-style identifiers would be more appropriate for non-resolvable schemas.
6. **Pre-commit hooks** — 2 hooks exist (dag-lint, extraction-intent-check). Evaluate coverage gaps (e.g., should validate-all or canonical-lint also be hooked?).

---

## P1 Agent Exclusive Scope Assignments

| Agent | Label | Exclusive Scope | Strategy | Does NOT Cover |
|-------|-------|----------------|----------|----------------|
| P1-A | Wiring & Structure | `cli.py`, all 8 `__init__.py` files, `schema_registry.json`, `step_order.json`, `command_prefixes.json`, package boundary verification, import graph | Trace each of 25 CLI subcommands to handler; verify all 29 registry entries resolve; confirm dependency direction (core <- canonical/generation <- validation/migration <- cli) | Validator internals, test files, error codes, hardcoded strings in non-init files |
| P1-B1 | DRY / SoC (Validators) | All 21 files in `validation/validators/` — the 23 `_load_*` functions and 21 `validate_step_*` entry points | Diff all `_load_*` implementations; identify extractable shared helpers; check SoC between schema validation and deep validation | Linter modules, canonical/, generation/, migration/, CLI wiring |
| P1-B2 | DRY / SoC (Linters & Others) | All non-validator files in `validation/` (18 files), all files in `canonical/` (5 files), `generation/` (4 files), `migration/` (5 files including scripts/) | Check for duplicated patterns across linters; verify canonical registry usage consistency; check generation/migration separation | Validator files (`step_*.py`), CLI wiring, test files |
| P1-C | Hardcoding | All 61 source files in `specdev_tools/` | **Grep-first strategy**: search for hardcoded paths, magic strings, inline constants, hardcoded URLs, numeric literals. Catalog every instance with file:line. | Does not assess architecture, test quality, or error system design — only catalogs hardcoded values |
| P1-D | Test Quality & Fixtures | All 73 test files, all 133 fixture files, both conftest files | Map test coverage to source modules; identify untested public functions; check fixture quality per step; verify conftest consistency (note: `migration_prompts_root` missing from integration conftest) | Source code internals (reads source only to verify test targets exist) |
| P1-E | Error Pipeline Flow | `core/errors.py` (186 LOC), all files importing from `core.errors`, all files using `SpecError`/`make_error`/`warnings.warn` (12 locations) | Trace error creation through collection to CLI output; verify all 77 codes are tested; check 18 promotion pairs; verify `warnings.warn` usage patterns | Does not assess test quality or fixture content — only error flow |
| P1-F | Schema-Validator Field Consistency | All 24 schema files, all 21 validator files (cross-reference both) | For each step: compare schema `required`/`properties` against validator field access; identify fields validated by schema only vs validator only; check enum consistency | Does not assess CLI wiring, test quality, error codes, or hardcoding — only schema-vs-validator alignment |
