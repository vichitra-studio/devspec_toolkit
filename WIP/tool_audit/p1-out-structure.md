# P1-A: Structure & Wiring — Findings

## Executive Summary
25 CLI subcommands correctly wired. 29 schema registry entries all resolve. Version mismatch (0.3.0 vs 0.4.0) is the top documentation issue. Lazy import shim is functional but oversized. One orphaned egg-info directory.

---

### FINDING-S1: Version Mismatch Across Documentation
- **Severity**: high
- **Category**: DOCUMENTATION
- **Location**: CLAUDE.md:9, tools/pyproject.toml:7, tools/README.md:1
- **Description**: Three different version claims: CLAUDE.md says 0.3.0, pyproject.toml says 0.4.0, tools/README.md title says "v3 Full"
- **Evidence**: `CLAUDE.md:9` "Current version: **0.3.0**", `pyproject.toml:7` version="0.4.0", `tools/README.md:1` "AI Spec Driven Development CLI (v3 Full)"
- **Recommendation**: Update CLAUDE.md to 0.4.0, update tools/README.md title to match

### FINDING-S2: No __version__ in Package
- **Severity**: medium
- **Category**: PACKAGING
- **Location**: tools/specdev_tools/__init__.py
- **Description**: No `__version__` string exposed. pyproject.toml has 0.4.0 but the package itself has no programmatic version accessor
- **Evidence**: __init__.py is 45 LOC of lazy-import shim with no version
- **Recommendation**: Add `__version__ = "0.4.0"` or use importlib.metadata

### FINDING-S3: Orphaned UNKNOWN.egg-info
- **Severity**: low
- **Category**: PACKAGING
- **Location**: tools/UNKNOWN.egg-info/
- **Description**: Stale egg-info directory alongside the correct specdev_tools.egg-info
- **Evidence**: 4 files in tools/UNKNOWN.egg-info/
- **Recommendation**: Delete and add to .gitignore

### FINDING-S4: Stale trace_matrix.json Checked In
- **Severity**: low
- **Category**: PACKAGING
- **Location**: tools/trace_matrix.json
- **Description**: Generated artifact with all-zero counters checked into repo. CI regenerates it every run.
- **Evidence**: Last modified 2025-02-22, empty matrix
- **Recommendation**: Add to .gitignore; it's a CI output artifact

### FINDING-S5: step_01 Validator Duplicates Schema Validation
- **Severity**: medium
- **Category**: WIRING
- **Location**: tools/specdev_tools/validation/validators/step_01.py:56-74
- **Description**: step_01.validate_step_01() performs full JSON Schema validation internally, but validate.py already runs schema validation before calling deep validators. This means step_01 artifacts get double schema validation.
- **Evidence**: step_01.py imports SchemaRegistry, Draft202012Validator, and runs iter_errors() independently. step_02.py does the same (line 127).
- **Recommendation**: Remove duplicate schema validation from step_01 and step_02; deep validators should only do semantic checks

### FINDING-S6: validate.py Cross-Package Import
- **Severity**: medium
- **Category**: IMPORTS
- **Location**: tools/specdev_tools/validation/validate.py:20
- **Description**: validate.py imports from generation.prompt_schema_sync — validation/ depends on generation/. This creates a bi-directional concern where validation orchestration triggers code generation checks.
- **Evidence**: `from ..generation.prompt_schema_sync import run_prompt_schema_sync` at line 20
- **Recommendation**: Move prompt_schema_sync to validation/ or make it a standalone check invoked by cli.py rather than validate.py

### FINDING-S7: Lazy Import Shim Has 23 Entries
- **Severity**: low
- **Category**: STRUCTURE
- **Location**: tools/specdev_tools/__init__.py
- **Description**: The _MOVED dict maps 23 module names for backward-compat lazy imports with deprecation warnings. This is functional but adds maintenance burden for every new module.
- **Evidence**: 23 entries in _MOVED dict covering all subpackages
- **Recommendation**: Audit whether any external consumers use these paths; if not, simplify

### FINDING-S8: CLAUDE.md Missing CLI Subcommands
- **Severity**: medium
- **Category**: DOCUMENTATION
- **Location**: CLAUDE.md
- **Description**: CLAUDE.md documents ~18 commands but the CLI has 25 subcommands. Missing from docs: canonical-autofix, prompt-context, canon-schema-alignment, traceability-check, changelog, align (partially documented), prompt-sync
- **Evidence**: CLI has 25 subcommands via add_parser calls in cli.py
- **Recommendation**: Update CLAUDE.md Core CLI Commands section

### FINDING-S9: STEP_NAMES Dict Hardcoded in cli.py
- **Severity**: low
- **Category**: STRUCTURE
- **Location**: tools/specdev_tools/cli.py:666-675
- **Description**: A 22-entry STEP_NAMES dict is hardcoded inline in the prompt-context handler. Should be derived from step_order.json or a shared constant.
- **Evidence**: Lines 666-675 define a literal dict mapping step numbers to names
- **Recommendation**: Extract to a shared constant or derive from step_order.json

### FINDING-S10: Pre-commit Hooks Use python -m Instead of Entry Point
- **Severity**: info
- **Category**: WIRING
- **Location**: .pre-commit-config.yaml
- **Description**: Pre-commit hooks invoke `python -m specdev_tools.cli` directly instead of the `specdev` entry point. This works but bypasses the installed entry point.
- **Evidence**: `entry: python -m specdev_tools.cli dag-lint --repo-root .`
- **Recommendation**: Use `specdev dag-lint --repo-root .` for consistency with documentation

## PASS

- All 25 CLI subcommands are correctly wired to handler functions; no dead code
- All 29 schema_registry.json entries resolve to existing schema files on disk
- step_order.json's 22 steps match schema_registry steps (16a/16b/16c share one schema, correctly)
- 21 DEEP_VALIDATORS entries match 21 validator files (no step_00 — correct, schema-only)
- align subcommand's 7 actions (status, diff, plan, apply, prompts, rollback, validate) all wired
- Subpackage split (core/, canonical/, generation/, validation/, migration/) is well-justified
- cli.py uses lazy imports for all subcommands (inside elif branches)
- pyproject.toml dependencies match requirements.txt
- All 8 __init__.py files are clean (no circular imports)
- Canon kinds directory (25 files) is well-structured
