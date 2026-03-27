# P2: Research Alignment Gap Analysis (Run B)

## Executive Summary

The toolkit partially aligns with research recommendations. Strong: collect-all validation (iter_errors), additionalProperties:false, kebab-case naming. Gaps: flat string errors (not structured), URL-based $id (not URN), no build/dereference pipeline, minimal schema descriptions, deep nesting (step 16 = 19 levels), and no WriteValidatedJSON MCP tool. Most gaps are medium effort to close.

## Findings

### ALIGNMENT-1: Schema $ref Usage
- **Current State**: Schemas use `$ref` extensively to core schemas. step_04 has 20 $ref, step_08 has 16, step_12 has 17. No step schemas use local `$defs` except step_16 (4 $defs).
- **Target State**: Full `$ref`/`$defs` DRY authoring with build-time dereference.
- **Gap Size**: MEDIUM
- **Migration Effort**: M (1-2 weeks)
- **Dependencies**: Build pipeline (ALIGNMENT-6) must exist first.
- **Quick Win?**: NO -- requires build tooling.
- **Recommendation**: Phase 1: Identify repeated object structures across schemas and extract to shared `$defs` in core schemas. Phase 2: Implement build pipeline.

### ALIGNMENT-2: Schema $id Format (URL vs URN)
- **Current State**: URL-based: `https://specdev.local/schema/...`. Referenced in schema_registry.json (29 entries), all schema files, and 5 source files (step_01, step_02, canonical/lint.py).
- **Target State**: URN-based: `urn:devspec:step-04` for path-independence.
- **Gap Size**: MEDIUM
- **Migration Effort**: M (1-2 weeks)
- **Dependencies**: None, but breaks all existing spec files that reference `$schema` URIs.
- **Quick Win?**: NO -- breaking change affecting all spec files.
- **Recommendation**: Defer to next major version. Add URN support as alternative resolution path in SchemaRegistry first.

### ALIGNMENT-3: Structured Error Objects
- **Current State**: All errors are flat strings. SpecError dataclass exists in errors.py but is unused by validators. --json output exists for 2 commands.
- **Target State**: Structured: `{ code, path, message, allowed, received }`. All commands support --json.
- **Gap Size**: LARGE
- **Migration Effort**: L (month)
- **Dependencies**: Requires touching all 21 validators, all linters, validate.py, cli.py.
- **Quick Win?**: Partially -- extend --json to more commands (S effort) without restructuring internals.
- **Recommendation**: Phase 1 (S): Add --json to all validation commands using current flat format. Phase 2 (L): Migrate validators to return SpecError objects, update pipeline.

### ALIGNMENT-4: Nesting Depth for LLM Consumption
- **Current State**: Nesting varies: step_00=8, step_05=10, step_16=19. Target: max 3 levels.
- **Target State**: Max 3-level nesting for LLM grammar compilation.
- **Gap Size**: LARGE
- **Migration Effort**: XL (rewrite of schemas)
- **Dependencies**: Would require restructuring all step schemas and all existing spec files.
- **Quick Win?**: NO -- fundamental schema architecture change.
- **Recommendation**: Not feasible for existing schemas. For new schemas or LLM-facing views, create flattened "LLM projection" schemas that dereference and flatten nested structures.

### ALIGNMENT-5: Schema Description Coverage
- **Current State**: Minimal. step_04 has 1 description, step_08 has 2, step_12 has 6. Most properties lack descriptions.
- **Target State**: 100% of properties have descriptions for LLM context.
- **Gap Size**: LARGE
- **Migration Effort**: M (1-2 weeks) -- mechanical but tedious.
- **Dependencies**: None.
- **Quick Win?**: YES -- additive, no breaking changes.
- **Recommendation**: Add descriptions to all schema properties. Start with most-used schemas (steps 00-08). Can be AI-assisted.

### ALIGNMENT-6: Build Pipeline (src/dist dereference)
- **Current State**: No build pipeline. Single `schema/` directory. No Makefile. CI does validation but no compilation.
- **Target State**: `schemas/src/` -> `schemas/dist/` with pre-commit auto-regen and CI staleness check.
- **Gap Size**: FUNDAMENTAL
- **Migration Effort**: M (1-2 weeks)
- **Dependencies**: None, but all consumers must switch to dist/ schemas.
- **Quick Win?**: NO -- new infrastructure.
- **Recommendation**: Phase 1: Add a simple `make schemas` target using json-dereference-cli. Phase 2: Add pre-commit hook and CI staleness check. Phase 3: Migrate consumers to dist/ schemas.

### ALIGNMENT-7: Enum Usage vs Free-form Strings
- **Current State**: Schemas use `additionalProperties: false` consistently (step_04 has 3 instances, step_08 has 2, step_12 has 7). Some enums exist (e.g., method in step_05/15). But many string fields that could be constrained are free-form.
- **Target State**: Enum over free-form strings wherever possible. Canon/kinds/ already has 25 kind files that could constrain schema enums.
- **Gap Size**: MEDIUM
- **Migration Effort**: M (1-2 weeks)
- **Dependencies**: Canon registry alignment.
- **Quick Win?**: Partially -- add enums to obviously constrained fields (owner, stage, trace type).
- **Recommendation**: Audit all string fields against canon/kinds/ entries. Add enum constraints where appropriate. This is the same direction as FINDING-H5/H6 from P1-C.

### ALIGNMENT-8: WriteValidatedJSON MCP Tool
- **Current State**: No MCP tool. Agents run CLI commands manually. Validation output is human-readable text.
- **Target State**: Atomic validate+write MCP tool for agent self-correction within maxTurns.
- **Gap Size**: FUNDAMENTAL
- **Migration Effort**: M (1-2 weeks for MVP)
- **Dependencies**: Structured errors (ALIGNMENT-3) for agent-consumable output.
- **Quick Win?**: NO -- new tool development.
- **Recommendation**: MVP: Python function that takes JSON content + target path, validates against schema, writes if valid, returns structured errors if not. Wrap as MCP tool. Does not require full structured error migration (can parse flat strings initially).

### ALIGNMENT-9: Pre-commit Hook Coverage
- **Current State**: 2 hooks: dag-lint, extraction-intent-check. Both trigger on step_order.json or prompt files.
- **Target State**: Additional hooks: schema staleness check, validate-all, canonical-lint.
- **Gap Size**: SMALL
- **Migration Effort**: S (days)
- **Dependencies**: None.
- **Quick Win?**: YES -- just add entries to .pre-commit-config.yaml.
- **Recommendation**: Add canonical-lint and validate-all as pre-commit hooks. Add schema staleness check once build pipeline exists.

## ALIGNMENT MATRIX

| # | Research Pattern | Current State | Gap | Effort | Quick Win |
|---|-----------------|---------------|-----|--------|-----------|
| 1 | $ref/$defs DRY authoring | $ref used, minimal $defs | MEDIUM | M | NO |
| 2 | URN-based $id | URL-based | MEDIUM | M | NO |
| 3 | Structured error objects | Flat strings | LARGE | L | Partial |
| 4 | Max 3-level nesting | Up to 19 levels | LARGE | XL | NO |
| 5 | 100% description coverage | ~5% coverage | LARGE | M | YES |
| 6 | src/dist build pipeline | No build pipeline | FUNDAMENTAL | M | NO |
| 7 | Enum over free-form | Partial | MEDIUM | M | Partial |
| 8 | WriteValidatedJSON MCP | None | FUNDAMENTAL | M | NO |
| 9 | Pre-commit coverage | 2 hooks | SMALL | S | YES |
