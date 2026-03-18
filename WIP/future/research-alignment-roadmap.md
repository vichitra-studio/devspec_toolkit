# Research Alignment Roadmap

This document tracks the 10 research alignment gaps identified during the P2 audit phase. Each item represents a strategic improvement opportunity aligned with industry best practices for schema-driven, LLM-consumable spec systems.

---

## Status Legend

| Status | Meaning |
|--------|---------|
| PARTIAL | Some progress made in the P4 fix plan |
| PLANNED | Fully addressed in P4 fix plan |
| FUTURE | Not addressed in P4; requires separate initiative |
| ACHIEVED | Already done; no gap exists |

---

## ALIGN-1: $ref/$defs DRY Authoring

- **Status:** FUTURE
- **Gap:** MEDIUM
- **Effort:** M (Medium)
- **Quick Win:** NO
- **Description:** JSON Schema files in `schema/` repeat common patterns (e.g., id format constraints, owner enums, trace_type definitions) instead of using `$ref` to shared `$defs` blocks in `schema/core/`. While `schema/core/` has atoms, collections, and errors, many step schemas inline definitions that could reference these shared components.
- **P4 Progress:** None. The DRY fixes in P4 target Python code duplication, not schema duplication.
- **Next Steps:**
  1. Audit all step schemas for repeated inline definitions
  2. Extract common patterns to `schema/core/atoms.schema.json`
  3. Replace inline definitions with `$ref` references
  4. Run `validate-all` to verify no breakage
- **Prerequisites:** None
- **Estimated Effort:** 2-3 days

---

## ALIGN-2: URN-based $id (URL to URN Migration)

- **Status:** FUTURE
- **Gap:** LARGE
- **Effort:** L (Large)
- **Quick Win:** NO
- **Description:** All schemas use URL-style `$id` values like `https://specdev.local/schema/01_capabilities.schema.json`. Research suggests URN-style identifiers (e.g., `urn:specdev:schema:01-capabilities`) are more portable and less confusing (no actual HTTP endpoint exists). This would affect schema_registry.json, all schema files, all validators that reference schemas, and all prompts.
- **P4 Progress:** None.
- **Next Steps:**
  1. Design URN naming convention
  2. Create migration script
  3. Update schema_registry.json
  4. Update all 24 schema files
  5. Update validators that reference schema URIs
  6. Update prompts
- **Prerequisites:** ALIGN-1 (cleaner to do after $ref consolidation)
- **Estimated Effort:** 1-2 weeks

---

## ALIGN-3: Structured Error Objects

- **Status:** PARTIAL
- **Gap:** LARGE
- **Effort:** L (Large)
- **Quick Win:** Partial (see AUDIT-007)
- **Description:** All validators and linters return `list[str]` error messages. The `SpecError` dataclass exists in `core/errors.py` (with code, message, path fields) but is never used. Structured errors would enable: machine-parsable output, severity filtering, JSON path context for LLM self-correction, and clean W-to-E promotion without string manipulation.
- **P4 Progress:**
  - FIX-017 registers missing error codes (AUDIT-001, 038, 039)
  - FIX-025 improves W-to-E promotion robustness (AUDIT-033)
  - FIX-030 adds `--json` output foundation (AUDIT-025)
  - The infrastructure for structured errors is documented but the full migration (21 validators + 17 linters to SpecError) is deferred
- **Next Steps:**
  1. Phase 1: Modify SpecError to include severity field
  2. Phase 2: Update one validator (e.g., step_04) as proof of concept
  3. Phase 3: Migrate all validators (batch by batch)
  4. Phase 4: Migrate all linters
  5. Phase 5: Update CLI output layer to render SpecError to string/JSON
- **Prerequisites:** P4 Batch 2 (error system fixes)
- **Estimated Effort:** 2-3 weeks

---

## ALIGN-4: additionalProperties: false

- **Status:** ACHIEVED
- **Gap:** NONE
- **Effort:** N/A
- **Quick Win:** YES (already done)
- **Description:** All schemas already use `additionalProperties: false` to prevent extraneous fields. This was verified during the audit.
- **P4 Progress:** N/A — no gap exists.
- **Next Steps:** None. Maintain this constraint for new schemas.

---

## ALIGN-5: Max 3-Level Nesting

- **Status:** FUTURE
- **Gap:** FUNDAMENTAL (step_16 has 19 levels)
- **Effort:** XL (Extra Large)
- **Quick Win:** NO
- **Description:** Research recommends max 3-level nesting for LLM-friendly schemas. Step 16 (scaffolding) has 19 levels of nesting — this is fundamental to its tree structure and cannot be flattened without redesigning the spec format. Other steps generally stay within 4-5 levels.
- **P4 Progress:** None.
- **Next Steps:**
  1. Analyze which steps exceed 3 levels
  2. Determine if any can be flattened without losing semantics
  3. For step_16, consider a flat list representation with parent references instead of nested trees
  4. Create a breaking-change migration plan if proceeding
- **Prerequisites:** ALIGN-1, ALIGN-3 (do smaller changes first)
- **Estimated Effort:** 3-4 weeks (mostly design, some migration)

---

## ALIGN-6: 100% Property Descriptions

- **Status:** FUTURE
- **Gap:** LARGE
- **Effort:** M (Medium)
- **Quick Win:** YES
- **Description:** Many schema properties lack `description` fields. LLMs perform better when every property has a clear description explaining its purpose, constraints, and examples. This is mechanical work — audit each property, add descriptions.
- **P4 Progress:** None.
- **Next Steps:**
  1. Script to find all properties without descriptions
  2. Add descriptions to `schema/core/` atoms first
  3. Add descriptions to step schemas (00-16c)
  4. Add `description` requirement to schema CI lint
- **Prerequisites:** None
- **Estimated Effort:** 3-5 days

---

## ALIGN-7: --json Output for All Commands

- **Status:** PARTIAL
- **Gap:** MEDIUM
- **Effort:** M (Medium)
- **Quick Win:** Partial (see AUDIT-025)
- **Description:** Only 2 of 25 CLI commands support `--json` output. CI pipelines and LLM agents need machine-parsable output from all validation commands.
- **P4 Progress:**
  - FIX-030 adds `--json` flag to top-level parser and implements JSON output for `validate`, `validate-all`, `canonical-lint`, `seed-lint`, `docs-lint` (5 commands)
  - After P4: 7 of 25 commands will support `--json`
- **Next Steps:**
  1. Add `--json` to remaining validation commands (quality-lint, hallucination-lint, fixtures-lint, etc.)
  2. Add `--json` to generation commands
  3. Add `--json` to canonical commands
  4. Define standard JSON output schema for all commands
- **Prerequisites:** P4 Batch 3 (FIX-030)
- **Estimated Effort:** 1-2 weeks

---

## ALIGN-8: WriteValidatedJSON MCP Tool

- **Status:** FUTURE
- **Gap:** LARGE
- **Effort:** M (Medium)
- **Quick Win:** NO
- **Description:** Create an MCP (Model Context Protocol) tool that combines schema validation + file write in one atomic operation. This would allow LLMs to write spec artifacts with immediate validation feedback, reducing the clarify-emit-validate loop.
- **P4 Progress:** None.
- **Next Steps:**
  1. Design MCP tool interface (input: step name, JSON content; output: validation results + file path)
  2. Implement using existing `validate_file()` + file write
  3. Add rollback on validation failure
  4. Package as MCP server
- **Prerequisites:** ALIGN-3 (structured errors make MCP responses cleaner)
- **Estimated Effort:** 1-2 weeks

---

## ALIGN-9: Pre-commit Hook Coverage

- **Status:** PARTIAL
- **Gap:** SMALL
- **Effort:** S (Small)
- **Quick Win:** YES
- **Description:** Current pre-commit hooks run a subset of validations. Coverage could be expanded to catch more issues before commit.
- **P4 Progress:**
  - FIX-050 adds pytest job to CI (AUDIT-067)
  - Pre-commit hook expansion is documented but not implemented in P4
- **Next Steps:**
  1. Audit current `.pre-commit-config.yaml` hooks
  2. Add `validate-all` hook for changed spec files
  3. Add `canonical-lint` hook for changed canon files
  4. Add `seed-lint` hook for changed spec files
  5. Ensure hooks are fast (< 5 seconds) by targeting only changed files
- **Prerequisites:** P4 Batch 6 (CI stabilized)
- **Estimated Effort:** 1-2 days

---

## ALIGN-10: src/dist Schema Split

- **Status:** FUTURE
- **Gap:** LARGE
- **Effort:** L (Large)
- **Quick Win:** NO
- **Description:** Maintain separate "source" schemas (permissive, for authoring) and "distribution" schemas (strict, for validation). Source schemas allow drafts and partial artifacts; distribution schemas require all fields and cross-references to be complete. This enables incremental authoring while maintaining strict validation at CI gates.
- **P4 Progress:** None.
- **Next Steps:**
  1. Design the src/dist schema split model
  2. Determine which fields are optional in src vs required in dist
  3. Create tooling to generate dist schemas from src schemas
  4. Update CLI to support `--mode src|dist` flag
  5. Update CI to use dist mode
- **Prerequisites:** ALIGN-1, ALIGN-3 (cleaner with consolidated schemas and structured errors)
- **Estimated Effort:** 3-4 weeks

---

## Priority Order (Recommended)

Based on impact/effort ratio:

1. **ALIGN-6** (property descriptions) — High LLM impact, mechanical work, no breaking changes
2. **ALIGN-9** (pre-commit hooks) — Small effort, immediate CI quality improvement
3. **ALIGN-7** (--json) — Continue from P4 partial progress, high CI/LLM value
4. **ALIGN-3** (structured errors) — Continue from P4 partial progress, foundational for ALIGN-7/8
5. **ALIGN-1** ($ref/$defs DRY) — Schema quality, enables ALIGN-2
6. **ALIGN-8** (MCP tool) — Depends on ALIGN-3
7. **ALIGN-2** (URN $id) — Depends on ALIGN-1
8. **ALIGN-10** (src/dist split) — Large effort, design-heavy
9. **ALIGN-5** (nesting) — Fundamental constraint, may require spec format redesign
10. **ALIGN-4** — Already achieved, no action needed
