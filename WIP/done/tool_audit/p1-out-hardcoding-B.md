# P1-C: Hardcoding, Assumptions & Magic Values Analysis (Run B)

## Executive Summary

Found significant hardcoding in step number literals across validators, hardcoded step file prefixes (e.g., `"04_"`, `"05_"`), schema URIs in step_01/step_02 validators, STEP_NAMES dict in cli.py, and version string drift. Most hardcoded file patterns in validators are load-bearing (they identify which upstream artifact to read) but could be centralized. Magic numbers exist in quality lint (vague language regex) and step_16 validators (checklist type/layer enums).

## Findings

### FINDING-H1: Hardcoded step file prefixes in all _load_* functions
- **Severity**: high
- **Category**: HARDCODED_VALUE
- **Location**: 23 _load_* functions across 13 validator files
- **Description**: Every _load_* function hardcodes a step file prefix like `"04_"`, `"05_"`, `"06_"`, `"07_"`, `"01_"`, `"02_"` as string literals to scan the spec directory.
- **Current value**: `fn.startswith("04_") and fn.endswith(".json")` (and variants)
- **Should be**: Derived from step_order.json or schema_registry.json mapping
- **Recommendation**: Create a shared `find_step_artifact(spec_dir, step_id) -> Path | None` helper that resolves step ID to file path via registry or naming convention. This also addresses the DRY concern (P1-B1).

### FINDING-H2: Hardcoded schema URIs in step_01 and step_02 validators
- **Severity**: medium
- **Category**: HARDCODED_VALUE
- **Location**: `validators/step_01.py:57`, `validators/step_02.py:127`
- **Description**: These validators hardcode `"https://specdev.local/schema/01_capabilities.schema.json"` and similar URIs to load schemas for redundant validation (already flagged in P1-A FINDING-S9).
- **Current value**: `registry.load("https://specdev.local/schema/01_capabilities.schema.json")`
- **Should be**: Not needed at all (validate.py already does schema validation)
- **Recommendation**: Remove the redundant schema validation from these validators entirely.

### FINDING-H3: Hardcoded canonical schema URIs in canonical/lint.py
- **Severity**: low
- **Category**: HARDCODED_VALUE
- **Location**: `canonical/lint.py:15-17`
- **Description**: Three canonical schema URIs are hardcoded as module-level constants.
- **Current value**: `CANON_ALIASES_SCHEMA_URI = "https://specdev.local/schema/canon/aliases/1"` etc.
- **Should be**: These are stable constants for the canon system and are the source of truth. Acceptable hardcoding.
- **Recommendation**: No change needed -- these define the canonical URIs.

### FINDING-H4: STEP_NAMES hardcoded in cli.py prompt-context command
- **Severity**: medium
- **Category**: HARDCODED_VALUE
- **Location**: `cli.py:666-675`
- **Description**: 22-entry dict mapping step IDs to human-readable names. Will drift if steps change.
- **Current value**: `STEP_NAMES = {"00": "Project Charter", "01": "Capabilities", ...}`
- **Should be**: Loaded from a data file or derived from step_order.json metadata
- **Recommendation**: Add step names to step_order.json or a separate metadata file.

### FINDING-H5: Hardcoded checklist types and layers in step_16.py
- **Severity**: medium
- **Category**: HARDCODED_VALUE
- **Location**: `validators/step_16.py:7-8`
- **Description**: VALID_CHECKLIST_TYPES (9 values) and VALID_CHECKLIST_LAYERS (9 values) are hardcoded frozensets.
- **Current value**: `frozenset({"behavior", "constraint", "validation", "metadata", "perf", "logging", "docs", "security", "config"})`
- **Should be**: Defined in the schema (as enum) or in canon/kinds/
- **Recommendation**: These are schema-level constraints that should live in the 16_impl_context.schema.json. Move to schema enum or canon kind.

### FINDING-H6: KNOWN_STAGES hardcoded in step_07 and hallucination_lint
- **Severity**: medium
- **Category**: HARDCODED_VALUE
- **Location**: `validators/step_07.py:9`, `validation/hallucination_lint.py:13`
- **Description**: Both files define `KNOWN_STAGES = {"dev", "ci", "staging", "prod"}` as fallback. step_07 loads canonical stages and falls back; hallucination_lint just uses the hardcoded set initially.
- **Current value**: `{"dev", "ci", "staging", "prod"}`
- **Should be**: Always loaded from `canon/kinds/stage.json`
- **Recommendation**: Make the canonical load the primary path with explicit error on failure rather than silent fallback.

### FINDING-H7: Version string mismatch (already flagged in P1-A)
- **Severity**: high
- **Category**: HARDCODED_VALUE
- **Location**: `CLAUDE.md:9` (0.3.0), `pyproject.toml:7` (0.4.0), `docs/developers/getting_started.md:65` (0.3.0)
- **Description**: Three different version claims across documentation.
- **Current value**: 0.3.0 in CLAUDE.md and getting_started.md, 0.4.0 in pyproject.toml
- **Should be**: Single source of truth (pyproject.toml), referenced everywhere else
- **Recommendation**: Update all documentation to 0.4.0. Consider adding `__version__` to __init__.py.

### FINDING-H8: Hardcoded spec field names in validators
- **Severity**: low
- **Category**: ASSUMPTION
- **Location**: All validators
- **Description**: Validators hardcode field names like `"functional_requirements"`, `"apis"`, `"rules"`, `"nfrs"`, `"fixtures"`, `"milestones"`, `"capabilities"`. These match the corresponding schema definitions but are not derived from schemas.
- **Current value**: String literals like `instance.get("functional_requirements", [])`
- **Should be**: This is acceptable -- validators are tightly coupled to their schema by design. Schema introspection would add complexity without value.
- **Recommendation**: No change. Document the coupling.

### FINDING-H9: Hardcoded command prefixes in hallucination_lint
- **Severity**: low
- **Category**: HARDCODED_VALUE
- **Location**: `validation/hallucination_lint.py:14-17`
- **Description**: DEFAULT_COMMAND_PREFIXES is a 20-element set of known CLI tool names.
- **Current value**: `{"python", "python3", "bash", "sh", "npm", ...}`
- **Should be**: Loaded from `tools/command_prefixes.json` (which exists and has 20 entries!)
- **Recommendation**: Load from command_prefixes.json instead of hardcoding. This is the exact use case for that file.

### FINDING-H10: Hardcoded filesystem paths (spec/, canon/, prompts/, schema/)
- **Severity**: low
- **Category**: ASSUMPTION
- **Location**: Throughout codebase (validators, linters, cli.py)
- **Description**: Most modules assume `spec/`, `canon/`, `prompts/`, `schema/` subdirectories relative to repo_root. This is passed as parameter at the CLI level but hardcoded within validators.
- **Current value**: `os.path.join(toolkit_root, "spec")`, `os.path.join(root, "canon")`, etc.
- **Should be**: Acceptable for a toolkit that defines its own directory structure. All paths are relative to repo_root.
- **Recommendation**: No change needed for spec/canon/schema paths. They are structural constants.

### FINDING-H11: Vague quantifier regex has subjective word list
- **Severity**: low
- **Category**: MAGIC_NUMBER
- **Location**: `validation/spec_quality_lint.py:14-18`
- **Description**: VAGUE_QUANTIFIER_RE has a hardcoded list of ~18 "vague" words. The word list is subjective and could produce false positives.
- **Current value**: Pattern includes: few, some, many, several, various, fast, reliable, easy, hard, quick, appropriate, adequate, sufficient, reasonable, significant, typical, generally, usually
- **Should be**: Configurable or loaded from a data file for tuning
- **Recommendation**: Consider making the word list configurable via step_order.json or a dedicated config.

## Exclusions Applied

- Hardcoded values in test fixtures (intentional fixture data) -- not reported
- Schema $id values in schema files themselves (source of truth) -- not reported
- DRY violations in _load_* functions -- reported in P1-B1
- Separation of concerns issues -- reported in P1-B2
