# P2: Research Alignment Gap Analysis — Findings

## Executive Summary
The toolkit is well-aligned on collect-all validation (iter_errors) and additionalProperties:false. Major gaps: no src/dist schema split, URL-based $id (not URN), flat string errors (not structured), no WriteValidatedJSON MCP tool, minimal property descriptions, and excessive nesting depth in step_16 schema (19 levels vs target 3).

---

### ALIGNMENT-1: Schema $ref Usage
- **Current State**: 24 schema files use $ref extensively. step_04 has 20 $ref occurrences, step_08 has 16. Core atoms provide 6 shared $defs. Only step_16 uses local $defs (4 defs).
- **Target State**: JSON Schema 2020-12 with $ref/$defs DRY authoring in schemas/src/, build-time dereference to schemas/dist/
- **Gap Size**: MEDIUM
- **Migration Effort**: M (1-2 weeks)
- **Dependencies**: Need json-dereference-cli tooling, CI pipeline changes
- **Quick Win?**: NO — requires new build step
- **Recommendation**: Phase 1: add schemas/src/ with $defs extraction. Phase 2: add CI dereference step. No changes to existing schema content needed first.

### ALIGNMENT-2: Schema $id Format (URL vs URN)
- **Current State**: URL-based: `https://specdev.local/schema/...`. Used in 29 registry entries, all schema files, canonical lint constants.
- **Target State**: URN-based: `urn:devspec:step-04` for path-independence
- **Gap Size**: LARGE
- **Migration Effort**: L (month) — affects schema_registry.json (29 entries), all 24 schema files, canonical/lint.py (3 URIs), step_01.py, step_02.py, and any test fixtures referencing URIs
- **Dependencies**: Schema build pipeline should exist first
- **Quick Win?**: NO — breaking change across entire schema system
- **Recommendation**: Defer until src/dist split is in place. Then migrate URIs in a single coordinated PR.

### ALIGNMENT-3: Error Objects (Flat Strings vs Structured)
- **Current State**: Validators return list[str]. SpecError dataclass exists (code, message, path) but is NEVER used by validators or linters. Errors embed codes inconsistently (some have codes, some don't).
- **Target State**: Structured error objects: `{ path: "$.records[3].severity", message: "...", allowed: [...], received: "..." }`
- **Gap Size**: LARGE
- **Migration Effort**: L (month) — 21 validators + 17 linters all return list[str]; need to migrate to list[SpecError]
- **Dependencies**: None (can start immediately)
- **Quick Win?**: Partial — can start by making SpecError the return type for new code, adding render() for backward compat
- **Recommendation**: Phase 1: enforce SpecError for all new validators. Phase 2: migrate existing validators. Phase 3: add --json structured output using SpecError fields.

### ALIGNMENT-4: additionalProperties: false
- **Current State**: Confirmed applied at root and nested objects. 137 total `additionalProperties: false` occurrences across 24 schema files. Step_16 has 57 occurrences alone.
- **Target State**: `additionalProperties: false` on ALL objects
- **Gap Size**: NONE
- **Migration Effort**: S (done)
- **Dependencies**: None
- **Quick Win?**: YES — already achieved
- **Recommendation**: No action needed. Continue enforcing in new schemas.

### ALIGNMENT-5: Schema Nesting Depth
- **Current State**: Step 00 = depth 8, Step 05 = depth 10, Step 16 = depth 19. Target is max 3 levels for LLM consumption.
- **Target State**: Max 3-level nesting
- **Gap Size**: FUNDAMENTAL
- **Migration Effort**: XL (rewrite) — step_16 schema is 1868 lines with deeply nested checklist/execution structures
- **Dependencies**: Would require fundamental restructuring of the impl_context artifact
- **Quick Win?**: NO
- **Recommendation**: Accept deep nesting in step_16 (it's a complex artifact). Focus on pre-dereferencing for LLM consumption rather than flattening the schema itself.

### ALIGNMENT-6: Property Descriptions
- **Current State**: Minimal. step_04 has 1 description across all properties. Most schemas lack descriptions entirely.
- **Target State**: 100% description coverage on all properties
- **Gap Size**: LARGE
- **Migration Effort**: M (1-2 weeks) — mechanical addition to all 24 schema files
- **Dependencies**: None
- **Quick Win?**: YES — additive change, no breaking modifications
- **Recommendation**: High-value quick win. LLMs perform significantly better with described properties. Add descriptions to all 24 schemas, prioritizing steps 00-08.

### ALIGNMENT-7: --json Output Coverage
- **Current State**: 2 of 25 commands support --json (validate, traceability-check)
- **Target State**: All commands support structured JSON output
- **Gap Size**: MEDIUM
- **Migration Effort**: M (1-2 weeks)
- **Dependencies**: Structured errors (ALIGNMENT-3) would make this much easier
- **Quick Win?**: Partial — can add --json to remaining commands with current flat-string format
- **Recommendation**: Add --json to all validation commands using a shared formatter. Upgrade to structured format when SpecError migration completes.

### ALIGNMENT-8: WriteValidatedJSON MCP Tool
- **Current State**: No equivalent exists. Validation and file writing are separate manual steps.
- **Target State**: Atomic validate+write tool for agent self-correction within maxTurns
- **Gap Size**: LARGE
- **Migration Effort**: M (1-2 weeks for MVP)
- **Dependencies**: Structured errors, --json output
- **Quick Win?**: YES for MVP — could wrap validate_file + write in a single CLI command
- **Recommendation**: MVP: `specdev write-validated spec/04_fr_list.json --max-turns 3` that validates, returns structured errors, accepts corrected JSON. Full MCP integration later.

### ALIGNMENT-9: Pre-commit Schema Hooks
- **Current State**: 2 hooks only (dag-lint, extraction-intent-check). No schema validation hooks.
- **Target State**: Pre-commit hook auto-regenerates dist; CI staleness check
- **Gap Size**: MEDIUM
- **Migration Effort**: S (days) — add validate-all as pre-commit hook
- **Dependencies**: None for basic hook; src/dist split needed for staleness check
- **Quick Win?**: YES — adding validate-all hook is trivial
- **Recommendation**: Add validate-all and canonical-lint as pre-commit hooks immediately

### ALIGNMENT-10: Build Pipeline (src/dist Schema Split)
- **Current State**: No build step. Single schema/ directory. No Makefile. No json-dereference-cli.
- **Target State**: schemas/src/ with $ref authoring -> schemas/dist/ with dereferenced output
- **Gap Size**: LARGE
- **Migration Effort**: L (month)
- **Dependencies**: None, but benefits from URN migration
- **Quick Win?**: NO — new infrastructure
- **Recommendation**: Phase 1: Add Makefile with dereference target. Phase 2: CI staleness check. Phase 3: LLM-specific dist with flattened nesting.

## ALIGNMENT MATRIX

| # | Research Pattern | Current State | Gap | Effort | Quick Win |
|---|-----------------|---------------|-----|--------|-----------|
| 1 | $ref/$defs DRY authoring | Good $ref usage, limited $defs | MEDIUM | M | NO |
| 2 | URN-based $id | URL-based (specdev.local) | LARGE | L | NO |
| 3 | Structured error objects | Flat strings, SpecError unused | LARGE | L | Partial |
| 4 | additionalProperties:false | Fully implemented | NONE | S | YES |
| 5 | Max 3-level nesting | Step 16 = depth 19 | FUNDAMENTAL | XL | NO |
| 6 | 100% property descriptions | Minimal (<5%) | LARGE | M | YES |
| 7 | --json all commands | 2/25 commands | MEDIUM | M | Partial |
| 8 | WriteValidatedJSON MCP | Not implemented | LARGE | M | YES (MVP) |
| 9 | Pre-commit schema hooks | 2 hooks only | MEDIUM | S | YES |
| 10 | src/dist schema split | Single directory | LARGE | L | NO |
