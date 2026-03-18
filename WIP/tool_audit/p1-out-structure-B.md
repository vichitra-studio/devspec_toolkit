# P1-A: Structure & Wiring Analysis (Run B)

## Executive Summary

25 CLI subcommands verified wired; 29 schema registry entries resolve correctly; 22 steps in step_order.json match pipeline expectations. Key issues: version mismatch (0.3.0 vs 0.4.0), stale UNKNOWN.egg-info, STEP_NAMES hardcoded in cli.py, and validators/__init__.py only re-exports 3 of 21 modules.

## Findings

### FINDING-S1: Version mismatch across documentation
- **Severity**: high
- **Category**: DOCUMENTATION
- **Location**: `CLAUDE.md:9`, `tools/pyproject.toml:7`, `tools/README.md` ("v3 Full")
- **Description**: CLAUDE.md claims version 0.3.0, pyproject.toml declares 0.4.0, tools/README.md title says "v3 Full". No `__version__` in `__init__.py`.
- **Evidence**: `CLAUDE.md:9` "Current version: **0.3.0**"; `pyproject.toml:7` `version = "0.4.0"`
- **Recommendation**: Update CLAUDE.md to 0.4.0, add `__version__ = "0.4.0"` to `__init__.py`, update README title.

### FINDING-S2: STEP_NAMES dict hardcoded in cli.py
- **Severity**: medium
- **Category**: HARDCODING (STRUCTURE-adjacent)
- **Location**: `tools/specdev_tools/cli.py:666-675`
- **Description**: cli.py prompt-context command has a hardcoded STEP_NAMES dict mapping step IDs to display names. This is the only source of step display names in the codebase and will drift if steps are added/renamed.
- **Evidence**: 22-entry dict literal at line 666 of cli.py
- **Recommendation**: Extract to a shared constant or load from step_order.json metadata.

### FINDING-S3: validators/__init__.py only re-exports step_16a/16b/16c
- **Severity**: low
- **Category**: STRUCTURE
- **Location**: `tools/specdev_tools/validation/validators/__init__.py` (11 LOC)
- **Description**: The `__init__.py` only explicitly imports step_16a, step_16b, step_16c with noqa F401. All other 18 validators are imported directly in validate.py. This inconsistency suggests the init was added for a specific reason (16a/b/c depend on step_16) but the pattern is not documented.
- **Evidence**: Lines 7-11 import only 3 modules; validate.py imports all 21 individually.
- **Recommendation**: Either import all validators in __init__.py or none. Current state is confusing but not broken.

### FINDING-S4: Orphaned UNKNOWN.egg-info directory
- **Severity**: low
- **Category**: PACKAGING
- **Location**: `tools/UNKNOWN.egg-info/`
- **Description**: Stale egg-info from a previous build with misconfigured setup.py. Should be gitignored.
- **Evidence**: Exists alongside `tools/specdev_tools.egg-info/`.
- **Recommendation**: Add `*.egg-info/` to .gitignore and remove the UNKNOWN directory.

### FINDING-S5: trace_matrix.json is stale generated artifact
- **Severity**: low
- **Category**: PACKAGING
- **Location**: `tools/trace_matrix.json`
- **Description**: All-zero counters, last modified 2025-02-22. CI regenerates it every run (ci.yml line 76). Should be gitignored.
- **Evidence**: CI uploads it as an artifact; the checked-in version has zero data.
- **Recommendation**: Add to .gitignore or remove from tracking.

### FINDING-S6: Empty tools/context/ directory
- **Severity**: info
- **Category**: STRUCTURE
- **Location**: `tools/context/`
- **Description**: Empty directory with no references in the codebase. Appears unused.
- **Evidence**: No imports or path references to `tools/context/` found in any source file.
- **Recommendation**: Remove or document its intended purpose.

### FINDING-S7: validate.py imports from generation package (layer tension)
- **Severity**: medium
- **Category**: IMPORTS
- **Location**: `tools/specdev_tools/validation/validate.py:20`
- **Description**: validate.py imports `run_prompt_schema_sync` from `generation.prompt_schema_sync`. This creates a validation->generation dependency, which inverts the expected layering (generation depends on core, validation orchestrates everything).
- **Evidence**: Line 20: `from ..generation.prompt_schema_sync import run_prompt_schema_sync`
- **Recommendation**: Accept as architectural decision (validate.py is the orchestrator) or move prompt_schema_sync to validation/.

### FINDING-S8: Lazy import shim in __init__.py has 22 entries
- **Severity**: info
- **Category**: STRUCTURE
- **Location**: `tools/specdev_tools/__init__.py` (45 LOC)
- **Description**: The `_MOVED` dict provides backward-compatible lazy imports for 22 module names. All entries map to valid current module paths. The shim is necessary if external consumers imported directly from the top-level package.
- **Evidence**: All 22 entries in `_MOVED` resolve to existing modules.
- **Recommendation**: Keep for now; consider removal in a future major version bump.

### FINDING-S9: step_01 and step_02 validators re-do schema validation
- **Severity**: medium
- **Category**: STRUCTURE
- **Location**: `tools/specdev_tools/validation/validators/step_01.py:56-74`, `step_02.py:127`
- **Description**: step_01 and step_02 validators load the schema registry and run `Draft202012Validator.iter_errors()` internally, duplicating what `validate.py:validate_file()` already does before calling deep validators.
- **Evidence**: step_01.py line 56-74 constructs a full validator and runs iter_errors. validate.py already runs iter_errors at line 136 before calling DEEP_VALIDATORS.
- **Recommendation**: Remove redundant schema validation from step_01 and step_02 deep validators.

### FINDING-S10: CLI subcommands documented in CLAUDE.md vs actual
- **Severity**: medium
- **Category**: DOCUMENTATION
- **Location**: `CLAUDE.md`
- **Description**: CLAUDE.md lists CLI commands but omits several: `canonical-autofix`, `prompt-context`, `canon-schema-alignment`, `env-check`, `changelog`, and `align validate`. The `align rollback` action is also undocumented.
- **Evidence**: cli.py has 25 subcommands; CLAUDE.md documents ~18.
- **Recommendation**: Update CLAUDE.md to list all 25 subcommands.

## PASS

- All 29 schema_registry.json entries resolve to existing schema files on disk (20 step schemas + 4 core + 2 canon + 1 seed_manifest, with 16a/b/c sharing 16's schema).
- All 22 steps in step_order.json match the steps referenced in schema_registry.json.
- 21 DEEP_VALIDATORS entries correctly match the 21 validator files (no step_00 validator, as expected).
- cli.py uses lazy imports (inside command blocks), not eager loading.
- The `align` subcommand correctly wires all 7 actions (status, diff, plan, apply, prompts, rollback, validate) to handler functions.
- The subpackage split (core/, canonical/, generation/, validation/, migration/) is well-justified and cleanly layered.
- Pre-commit hooks correctly reference `python -m specdev_tools.cli` with `--repo-root .`.
- pyproject.toml dependencies match requirements.txt (jsonschema, pyyaml, jsonschema-specifications, pyjwt).
