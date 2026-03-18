# P1-C: Hardcoding, Assumptions & Magic Values — Findings

## Executive Summary
Schema URIs are hardcoded in 2 validator files (step_01, step_02) and 3 canonical modules. Step numbers are hardcoded in all 23 _load_* functions. Version strings are inconsistent across 4 locations. Multiple magic numbers lack named constants.

---

### FINDING-H1: Schema URIs Hardcoded in Validators
- **Severity**: high
- **Category**: HARDCODED_VALUE
- **Location**: validators/step_01.py:57, validators/step_02.py:127
- **Current value**: `"https://specdev.local/schema/01_capabilities.schema.json"`, `"https://specdev.local/schema/02_system_sketch.schema.json"`
- **Should be**: Loaded from schema_registry.json via the $schema field in the artifact
- **Recommendation**: Remove — validate.py already resolves schemas via registry. These validators shouldn't re-do schema validation.

### FINDING-H2: Schema URIs Hardcoded in Canonical Modules
- **Severity**: medium
- **Category**: HARDCODED_VALUE
- **Location**: canonical/lint.py:15-17
- **Current value**: `CANON_ALIASES_SCHEMA_URI = "https://specdev.local/schema/canon/aliases/1"` etc.
- **Should be**: These are canonical constants for the canonical subsystem — partially justified. But should come from a config or schema_registry.json.
- **Recommendation**: Load from schema_registry.json keys rather than hardcoding

### FINDING-H3: Step File Prefixes Hardcoded in All Loaders
- **Severity**: medium
- **Category**: HARDCODED_VALUE
- **Location**: All 23 _load_* functions across validators
- **Current value**: `fn.startswith("04_")`, `fn.startswith("05_")`, etc.
- **Should be**: Derived from step_order.json or a registry mapping step ID -> filename pattern
- **Recommendation**: Shared loader should accept step prefix as parameter

### FINDING-H4: KNOWN_STAGES Hardcoded Instead of Loading from Canon
- **Severity**: medium
- **Category**: HARDCODED_VALUE
- **Location**: hallucination_lint.py:13, step_07.py:9
- **Current value**: `{"dev", "ci", "staging", "prod"}`
- **Should be**: Loaded from canon/kinds/stage.json (step_07 does load canonical stages as fallback, but hallucination_lint doesn't)
- **Recommendation**: Both should load from canon; use hardcoded only as fallback

### FINDING-H5: DEFAULT_COMMAND_PREFIXES Hardcoded
- **Severity**: low
- **Category**: HARDCODED_VALUE
- **Location**: hallucination_lint.py:14-18
- **Current value**: 20 command prefixes hardcoded as a set
- **Should be**: Partially justified — these are loaded from tools/command_prefixes.json and merged. The hardcoded set is the default fallback.
- **Recommendation**: Acceptable pattern, but document that command_prefixes.json extends (not replaces) defaults

### FINDING-H6: allowed_pr_rules Hardcoded in hallucination_lint
- **Severity**: medium
- **Category**: HARDCODED_VALUE
- **Location**: hallucination_lint.py:116-120
- **Current value**: `{"validate", "validate-all", "matrix", "fixtures-lint", ...}` — 14 allowed values
- **Should be**: Derived from CLI subcommand list or a config file
- **Recommendation**: Extract to a shared constant or load from CLI registration

### FINDING-H7: Version Strings Inconsistent
- **Severity**: high
- **Category**: HARDCODED_VALUE
- **Location**: CLAUDE.md:9, pyproject.toml:7, tools/README.md:1, docs/developers/getting_started.md:65
- **Current value**: "0.3.0", "0.4.0", "v3 Full", "0.3.0"
- **Should be**: Single source of truth in pyproject.toml (0.4.0), all others derive
- **Recommendation**: Update all references to 0.4.0

### FINDING-H8: ASSUMPTION_THRESHOLD Magic Number
- **Severity**: low
- **Category**: MAGIC_NUMBER
- **Location**: spec_quality_lint.py:114
- **Current value**: `ASSUMPTION_THRESHOLD = 10` (defined inline in function)
- **Should be**: Module-level constant
- **Recommendation**: Move to module level

### FINDING-H9: Content Derivation Threshold Default
- **Severity**: low
- **Category**: MAGIC_NUMBER
- **Location**: hallucination_lint.py:335
- **Current value**: `threshold: int = 5` as function parameter default
- **Should be**: Named constant with documentation explaining why 5
- **Recommendation**: Extract to CONTENT_DERIVATION_MIN_OVERLAP = 5

### FINDING-H10: VALID_CHECKLIST_TYPES/LAYERS Hardcoded in step_16
- **Severity**: medium
- **Category**: HARDCODED_VALUE
- **Location**: validators/step_16.py:7-8
- **Current value**: `frozenset({"behavior", "constraint", "validation", ...})`, `frozenset({"db", "model", "service", ...})`
- **Should be**: These enum values should ideally be in the schema or canon/kinds/
- **Recommendation**: Consider adding to schema as enum constraints, or to canonical registry

### FINDING-H11: Filesystem Path Assumptions
- **Severity**: medium
- **Category**: ASSUMPTION
- **Location**: All _load_* functions, validate.py, cli.py
- **Description**: Hardcoded path segments: "spec/", "canon/", "schema/", "tools/", "prompts/" appear ~50 times across source files
- **Should be**: Most are parameterized via --repo-root, but the internal structure (spec/, canon/, tools/) is assumed
- **Recommendation**: Acceptable for toolkit internals, but document the assumed directory structure

### FINDING-H12: Error Code E142 Not in errors.py
- **Severity**: high
- **Category**: HALLUCINATION
- **Location**: validators/step_14.py:79
- **Current value**: `f"E142 TECH_STACK_MISMATCH: ..."` — E142 is not in ERROR_CODES dict
- **Should be**: Either register E142 in errors.py or use an existing code
- **Recommendation**: Register E142 in errors.py ERROR_CODES dict

### FINDING-H13: Error Code E141 Not in errors.py
- **Severity**: high
- **Category**: HALLUCINATION
- **Location**: validators/step_14.py:126
- **Current value**: `f"E141 TASK_DEPENDENCY_CYCLE: ..."` — E141 is not in ERROR_CODES dict
- **Should be**: Either register E141 or use E585 (DAG_CIRCULAR_DEPENDENCY)
- **Recommendation**: Register E141 or map to E585

### FINDING-H14: Error Code E320 Not in errors.py
- **Severity**: high
- **Category**: HALLUCINATION
- **Location**: validators/step_13.py:32,40,50
- **Current value**: `f"E320 Extension ..."` — E320 is not in ERROR_CODES dict
- **Should be**: Registered in errors.py
- **Recommendation**: Register E320 in errors.py

## Exclusions Applied
- DRY violations in _load_* functions (P1-B1 scope)
- Test fixture hardcoded values (intentional)
- Schema $id values in schema files (source of truth)
