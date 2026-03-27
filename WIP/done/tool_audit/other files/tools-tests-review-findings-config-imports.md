# Findings: Configuration, Environment, Logging, and Import Patterns
**Source**: T-tools-tests-review-002
**Criteria**: A4, A6, A8, A9, E3, F6
**Date**: 2026-03-11

---

## SPECDEV_* Environment Variable Scatter — Master Table

All `os.getenv` / `os.environ.get` call sites across `tools/specdev_tools/`:

| Env Var | File | Line | Read method | Parsing |
|---|---|---|---|---|
| `SPECDEV_WARNINGS_AS_ERRORS` | `cli.py` | 18 | `os.getenv` | boolean via `in {"1","true","yes"}` |
| `SPECDEV_WARNINGS_AS_ERRORS` | `cli.py` | 705 | `os.getenv` | boolean via `in {"1","true","yes"}` |
| `SPECDEV_WARNINGS_AS_ERRORS` | `validation/validate.py` | 269 | `os.getenv` | boolean via `in {"1","true","yes"}` |
| `SPECDEV_PROMOTE_CODES` | `cli.py` | 706 | `os.getenv` | raw string |
| `SPECDEV_PROMOTE_CODES` | `validation/validate.py` | 270 | `os.getenv` | string + `.split(",")` |
| `SPECDEV_MATRIX_STRICT` | `cli.py` | 233 | `os.getenv` | boolean via `in {"1","true","yes"}` |
| `SPECDEV_MATRIX_STRICT` | `cli.py` | 736 | `os.getenv` | raw string (display only) |
| `SPECDEV_REPLAY_BASE_REF` | `cli.py` | 734 | `os.getenv` | raw string (display only) |
| `SPECDEV_REPLAY_BASE_REF` | `validation/validate.py` | 484 | `os.getenv` | string |
| `SPECDEV_REPLAY_DIFF_ERROR_MODE` | `validation/validate.py` | 238 | `os.getenv` | string |
| `SPECDEV_STALENESS_THRESHOLD` | `validation/forward_replay_check.py` | 86 | `os.environ.get` | `int()` parse |
| `CI` (non-SPECDEV) | `validation/validate.py` | 240 | `os.getenv` | boolean via `in {"1","true","yes"}` |

**Totals**: 7 distinct env vars (6 SPECDEV_* + 1 `CI`), 12 call sites, spread across 3 files.

---

## print() Usage — Per-File Counts

All `print()` calls across `tools/specdev_tools/`:

| File | Total print() | To stderr (`file=sys.stderr`) | To stdout |
|---|---|---|---|
| `tools/specdev_tools/cli.py` | 111 | 19 | 92 |
| `tools/specdev_tools/validation/validate.py` | 2 | 2 | 0 |
| `tools/specdev_tools/generation/prompt_schema_sync.py` | 2 | 0 | 2 |
| `tools/specdev_tools/migration/scripts/strip_generation_quality.py` | 3 | 0 | 3 |
| All other files | 0 | 0 | 0 |
| **Total** | **118** | **21** | **97** |

`import logging` / `logging.` usage: present in **1 file only** — `tools/specdev_tools/migration/planner.py:10,28`. Even there, only `logger = logging.getLogger(__name__)` is defined; no `logger.debug/info/warning/error` calls appear in that file.

---

## A4 — Configuration Centralization

### FINDING A4-001: No centralized config module; env vars read across 3 files with duplicated parsing

**Severity**: Medium
**Files**: `tools/specdev_tools/cli.py:18,233,705,706,734,736`, `validation/validate.py:238,240,269,270,484`, `validation/forward_replay_check.py:86`

Industry standard is a single `config.py` or `settings.py` module that reads all environment variables once and exports typed values (e.g., `WARNINGS_AS_ERRORS: bool`, `PROMOTE_CODES: frozenset[str]`). Currently:

- The boolean parse pattern `.strip().lower() in {"1", "true", "yes"}` is duplicated identically in `cli.py:18`, `cli.py:705`, and `validate.py:269` for `SPECDEV_WARNINGS_AS_ERRORS`.
- `SPECDEV_PROMOTE_CODES` is read in `cli.py:706` (raw string) and `validate.py:270` (parsed via `.split(",")`).
- `SPECDEV_MATRIX_STRICT` is read in `cli.py:233` (boolean) and `cli.py:736` (raw string).
- `SPECDEV_STALENESS_THRESHOLD` uses `os.environ.get` (not `os.getenv`) diverging from the style used in all other call sites.

If the accepted truthy values or defaults change, all sites must be updated consistently.

---

### FINDING A4-002: SPECDEV_WARNINGS_AS_ERRORS read in both cli.py and validate.py — divergence risk

**Severity**: Medium
**Files**: `tools/specdev_tools/cli.py:18`, `tools/specdev_tools/validation/validate.py:269`

`cli.py` wraps the read in a function `_warnings_as_errors()` (line 18). `validate.py` inlines the identical logic at line 269 without calling that function. The two copies are logically equivalent today, but if one is updated the other may drift.

---

### FINDING A4-003: SPECDEV_STALENESS_THRESHOLD uses os.environ.get instead of os.getenv

**Severity**: Low
**File**: `tools/specdev_tools/validation/forward_replay_check.py:86`

```python
staleness_threshold = int(os.environ.get("SPECDEV_STALENESS_THRESHOLD", "3"))
```

Every other env var read in the codebase uses `os.getenv(...)`. This one uses `os.environ.get(...)`. The behavior is identical but the style is inconsistent. The default value (3) is also undocumented outside this source line.

---

## E3 — Configuration Centralization (Duplicate Summary)

### FINDING E3-001: Duplicate SPECDEV_WARNINGS_AS_ERRORS and SPECDEV_PROMOTE_CODES parsing in cli.py and validate.py

**Severity**: Medium
**Files**: `cli.py:18,705` vs `validate.py:269` for `SPECDEV_WARNINGS_AS_ERRORS`; `cli.py:706` vs `validate.py:270` for `SPECDEV_PROMOTE_CODES`

The `validate.py` copy of the promotion logic (lines 269–290) is the authoritative one that drives actual W→E promotion during validation runs. The `cli.py` copies are: (a) a helper function `_warnings_as_errors()` used to decide exit codes, and (b) display code in the `env-check` handler. These three separate reads create three locations where the interpretation of the env var can diverge. A shared config accessor would eliminate this.

---

## A6 — Import Hygiene

### PASS A6-001: __init__.py uses lazy loading with deprecation warnings for all 22 re-exports

**File**: `tools/specdev_tools/__init__.py`

- `__all__ = []` — `from specdev_tools import *` imports nothing.
- `__getattr__` hook uses `importlib.import_module` — modules load on first access, not at import time.
- All 22 entries in `_MOVED` emit a `DeprecationWarning` directing callers to canonical subpackage paths.
- No eager top-level imports of subpackages.

This is correct lazy-import practice. Re-export count: 22 shims, all deprecated.

---

### FINDING A6-002: Bidirectional import coupling between validation and generation subpackages

**Severity**: Medium
**Files**:
- `tools/specdev_tools/validation/validate.py:20` — `from ..generation.prompt_schema_sync import run_prompt_schema_sync` (eager, module-level)
- `tools/specdev_tools/generation/schema_differ.py:1256` — `from ..validation.validate import validate_dir` (deferred, inside function)
- `tools/specdev_tools/generation/schema_differ.py:1267` — `from ..validation.matrix import validate_trace_integrity` (deferred, inside function)

`validation/validate.py` imports from `generation` at module level. `generation/schema_differ.py` imports back from `validation` at runtime inside functions. This is a latent circular dependency. Currently safe only because `schema_differ.py` defers its imports. If either deferred import in `schema_differ.py` were moved to module level, the circular import would produce an `ImportError` at startup.

---

### FINDING A6-003: validate.py imports from generation subpackage at module level (eager)

**Severity**: Low
**File**: `tools/specdev_tools/validation/validate.py:20`

```python
from ..generation.prompt_schema_sync import run_prompt_schema_sync
```

This top-level import loads the entire `generation.prompt_schema_sync` module whenever `validation.validate` is imported. Given that `schema_differ.py` (in `generation`) already imports from `validation` at runtime, this eager import completes a soft circular path that works today only due to Python's module caching behavior.

---

## A8 — Error Handling and Propagation

### PASS A8-001: SpecError dataclass and SpecdevError exception hierarchy defined in core/errors.py

**File**: `tools/specdev_tools/core/errors.py`

`core/errors.py` defines:
- `SpecError` — frozen dataclass with `code`, `message`, `path` fields and a `render()` method. Used for structured lint output.
- `SpecdevError(Exception)` — base exception for toolkit errors.
- `SubmoduleDetectionError(SpecdevError)` — includes a detailed docstring listing typical causes (detached HEAD, wrong `--repo-root`) and resolution steps.
- `SchemaRegistryError(SpecdevError)` — captures the failing URI as an attribute; docstring lists resolution steps.
- `make_error()` — factory that validates error codes against `ERROR_CODES` dict; raises `ValueError` on unknown code.

The hierarchy is shallow but purposeful. Docstrings are notably thorough.

---

### FINDING A8-002: SpecdevError exception hierarchy defined but never raised in validation pipeline

**Severity**: Medium
**File**: `tools/specdev_tools/core/errors.py:144-186`

`SpecdevError`, `SubmoduleDetectionError`, and `SchemaRegistryError` are defined but no `raise` of any of these classes appears in the validation pipeline. The validation layer exclusively uses string-list returns (`list[str]`). The exception classes appear aspirational — they were likely intended for a future refactor toward typed exception propagation. Currently they are unreachable dead code in production paths.

---

### FINDING A8-003: validate_file outer except clause collapses six distinct exception types into E520

**Severity**: Medium
**File**: `tools/specdev_tools/validation/validate.py:177`

```python
except (OSError, json.JSONDecodeError, ValueError, KeyError, AttributeError, TypeError) as e:
    return [f"E520 UNRESOLVED_INPUT {path}: validation_input_error {type(e).__name__}: {str(e)}"]
```

Six unrelated exception types are merged into a single E520 output. A file-not-found (`OSError`), a malformed JSON body (`json.JSONDecodeError`), a missing dict key (`KeyError`), and a type coercion failure (`TypeError`) all produce the same error code. Callers cannot distinguish failure categories. The type name is preserved as a string but is not machine-parseable for routing or suppression.

---

### FINDING A8-004: _run_deep_validation swallows all exceptions as an unstructured string

**Severity**: Low
**File**: `tools/specdev_tools/validation/validate.py:411-414`

```python
try:
    return validator(data, repo_root, context)
except Exception as e:
    return [f"Deep Validation Critical Error: {str(e)}"]
```

The message `"Deep Validation Critical Error: ..."` does not conform to the `EXXX CODE path: detail` format used everywhere else. It is not a registered error code, so it is not filterable, promotable, or suppressible via SPECDEV_PROMOTE_CODES. The original traceback is discarded.

---

### FINDING A8-005: Error propagation terminates at string boundary; SpecdevError hierarchy unused in pipeline

**Severity**: Low / Design
**Files**: all validators and `validation/validate.py`

All validators return `list[str]`. Exceptions are converted to strings at the validator boundary. `cli.py` receives only opaque strings — there is no typed exception it can branch on. The `SpecdevError` classes are defined in `core/errors.py` but are never caught or re-raised in the path from `validate_file` through `validate_dir` to `cli.py`. This makes it impossible for CLI error handlers to distinguish, for example, a schema registry failure from a deep validation crash without string parsing.

---

### PASS A8-006: All subprocess calls in validate.py use check=False, timeout=10, and returncode checking

**File**: `tools/specdev_tools/validation/validate.py:440,463,502,513,527`

All five `subprocess.run` calls wrap with `check=False`, `timeout=10`, and catch `TimeoutExpired` and `OSError`. Return codes are inspected before consuming output. This is correct defensive practice.

---

## A9 — Logging

### FINDING A9-001: Zero logging module usage in CLI and validation layer

**Severity**: Medium

`import logging` appears in exactly one file across all of `tools/specdev_tools/`:
- `tools/specdev_tools/migration/planner.py:10,28` — only `logger = logging.getLogger(__name__)` is defined. No `logger.debug/info/warning/error` calls appear in that file.

There is no logging configuration anywhere (no `logging.basicConfig`, no handler setup, no level configuration). The entire CLI, validation, canonical, and generation layers use only `print()`.

---

### FINDING A9-002: 118 print() calls; no configurable verbosity; diagnostic messages mixed with structured output

**Severity**: Medium
**Per-file counts**: see master table above (cli.py: 111, validate.py: 2, prompt_schema_sync.py: 2, strip_generation_quality.py: 3)

The 92 stdout print() calls in `cli.py` are appropriate for a CLI tool — they are the primary user-facing output channel. The issues are:

1. **No verbosity control**: debug-level messages (e.g., "specdev: forward-replay check skipped", git timeout warnings) are emitted unconditionally via `print(..., file=sys.stderr)`. There is no `--quiet` or `--verbose` flag and no way to suppress or amplify diagnostic messages without code changes.

2. **Library-level print() calls**: `generation/prompt_schema_sync.py:494-496` uses `print(err)` and `print("OK")` inside a function (`run_prompt_schema_sync`) that is imported and called by `validate.py`. This means a library function produces side-effectful terminal output rather than returning structured data. This is inconsistent with the rest of the validation layer.

3. **Inline sys import for diagnostics**: `validate.py:243` does `import sys as _sys` inside a conditional block solely to call `print(..., file=_sys.stderr)`. A logger call would not require this.

---

## F6 — Environment Assumptions

### FINDING F6-001: CI environment assumed via undocumented os.getenv("CI") with silent behavior change

**Severity**: Low
**File**: `tools/specdev_tools/validation/validate.py:240`

```python
in_ci = os.getenv("CI", "").strip().lower() in {"1", "true", "yes"}
mode = "error" if (in_ci or _is_git_repo(root)) else "ignore"
```

The `CI` variable is not documented in the toolkit's env var table (CLAUDE.md lists only SPECDEV_* vars). Its presence silently changes forward-replay behavior from `ignore` to `error` mode. A developer running locally with `CI=1` set in their shell (e.g., from a previous session) would get different validation behavior than expected without any indication.

The fallback path — calling `_is_git_repo(root)` — makes a synchronous subprocess call to `git rev-parse`. If `git` is absent from `PATH`, the `OSError` is caught and `False` is returned silently (validate.py:468-469), causing forward-replay to be silently skipped. This could mask real validation failures.

---

### PASS F6-002: All git subprocess calls in validate.py guarded with timeout and exception handling

**File**: `tools/specdev_tools/validation/validate.py` — `_detect_git_root`, `_is_git_repo`, `_git_ref_exists`, `_git_upstream_branch`, `_git_current_branch`

All five git helper functions use `check=False`, `timeout=10`, and catch both `TimeoutExpired` and `OSError`. Return values are safe defaults (`False`, `None`, or the `repo_root` fallback). Git absence does not raise unhandled exceptions.

---

### FINDING F6-003: schema_differ.py git subprocess calls lack timeout parameter

**Severity**: Medium
**File**: `tools/specdev_tools/generation/schema_differ.py:888,970,976,983`

The backup and pre-migration validation functions call `subprocess.run(["git", ...])` without a `timeout` argument:

```python
# Line 970 — no timeout=
subprocess.run(
    ["git", "add", "-A"],
    cwd=spec_dir.parent,
    capture_output=True,
    check=False,
)
```

In a slow filesystem or if `git` hangs waiting for credentials or SSH, these calls will block indefinitely. Compare with `validate.py` which consistently uses `timeout=10` for all git calls. Additionally, the `git add -A` call stages ALL files in the working tree, not just spec files — this is a destructive side effect that could pollute a user's git index.

---

### FINDING F6-004: .git existence check uses is-directory test; false-negative in git submodule repos

**Severity**: Low
**File**: `tools/specdev_tools/generation/schema_differ.py:882-883` and `964-965`

```python
git_dir = spec_dir.parent / ".git"
if not git_dir.exists():
    warnings.append("Not a Git repo - Git backup will be skipped")
```

In a git submodule, `.git` is a **file** (containing `gitdir: ../../../.git/modules/...`), not a directory. The check `.git` uses `Path.exists()` which returns `True` for files too, but the variable name `git_dir` and the semantic intent suggest directory presence. More critically, `spec_dir.parent / ".git"` checks the parent of the spec directory — but in the toolkit's own deployment, the spec directory lives inside `devspec_toolkit/`, so `spec_dir.parent` is the toolkit root, and the actual `.git` file/directory would be at the host repo root one level up. This can produce a false "Not a Git repo" warning on submodule installations where backup ought to work.

---

### PASS F6-005: venv activation check at CLI entry point

**File**: `tools/specdev_tools/cli.py:37-42`

`check_venv()` compares `sys.prefix != sys.base_prefix` — the standard CPython approach for detecting virtualenv activation. Called at the start of `main()` before any subcommand logic. Returns a clear error message and exits with code 1 if not activated.

---

## Summary Table

| Criterion | Record | Severity | Title |
|---|---|---|---|
| A4 | FINDING A4-001 | Medium | No centralized config module; 12 os.getenv call sites across 3 files with duplicated parsing |
| A4 | FINDING A4-002 | Medium | SPECDEV_WARNINGS_AS_ERRORS read 3 times with identical inline parse logic |
| A4 | FINDING A4-003 | Low | SPECDEV_STALENESS_THRESHOLD uses os.environ.get, inconsistent with all other sites |
| E3 | FINDING E3-001 | Medium | Duplicate SPECDEV_WARNINGS_AS_ERRORS and SPECDEV_PROMOTE_CODES parsing in cli.py and validate.py |
| A6 | PASS A6-001 | — | __init__.py: 22 deprecated shims with lazy loading and DeprecationWarning; __all__ = [] |
| A6 | FINDING A6-002 | Medium | Bidirectional import coupling between validation (eager) and generation (deferred) subpackages |
| A6 | FINDING A6-003 | Low | validate.py imports from generation at module level — eager, completes soft circular path |
| A8 | PASS A8-001 | — | SpecError dataclass + SpecdevError hierarchy with thorough docstrings in core/errors.py |
| A8 | FINDING A8-002 | Medium | SpecdevError hierarchy defined but never raised; exception classes are unreachable dead code |
| A8 | FINDING A8-003 | Medium | validate_file broad except collapses OSError/JSONDecodeError/KeyError/TypeError into single E520 |
| A8 | FINDING A8-004 | Low | _run_deep_validation swallows all exceptions as unstructured non-code string |
| A8 | FINDING A8-005 | Low | Error propagation terminates at string boundary; no typed exceptions reach cli.py |
| A8 | PASS A8-006 | — | All subprocess calls in validate.py use check=False, timeout=10, returncode checks |
| A9 | FINDING A9-001 | Medium | Zero logging module usage in CLI/validation layer; only planner.py has import (unused) |
| A9 | FINDING A9-002 | Medium | 118 print() calls; 97 to stdout; no configurable verbosity; library-level prints in prompt_schema_sync |
| F6 | FINDING F6-001 | Low | CI env var undocumented; silent behavior change; git-absence causes silent forward-replay skip |
| F6 | PASS F6-002 | — | All git subprocess calls in validate.py guarded with timeout=10 + exception handling |
| F6 | FINDING F6-003 | Medium | schema_differ.py git subprocess calls lack timeout; git add -A stages entire working tree |
| F6 | FINDING F6-004 | Low | .git check uses directory-presence test; false-negative on git submodule installations |
| F6 | PASS F6-005 | — | venv activation verified at CLI entry via sys.prefix != sys.base_prefix |
