# P2: Research Alignment Gap Analysis

Agent Type: Explore (very thorough)
Repo Root: /Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/

## Objective

Compare current toolkit against target architecture from research. Identify gaps and migration opportunities. The research documents are large (133KB total) — all relevant recommendations are pre-digested below. Do NOT re-read the research files.

## Research Summary (embed — DO NOT make the agent re-read the 133KB research docs)

Source documents (in /Users/vichitracollective/vc-code/vc_agent/WIP/research/):
1. agent-migration-patterns.md
2. json-schema-dry-patterns.md
3. json-schema-migration-summary.md
4. json-schema-research-report.md
5. json-schema-standards.md
6. json-validation-tooling.md

The research recommends these target patterns:

### Schema DRY Pattern
- JSON Schema 2020-12 with `$ref`/`$defs` DRY authoring in `schemas/src/`, build-time dereference to `schemas/dist/`
- Pre-commit hook auto-regenerates dist; CI staleness check as backup
- URN-based `$id` (e.g., `urn:devspec:step-04`) for path-independence

### Validation & Error Handling
- AJV `allErrors: true` or Python `jsonschema` `iter_errors()` — collect ALL errors
- Structured error objects: `{ path: "$.records[3].severity", message: "...", allowed: [...], received: "..." }`
- WriteValidatedJSON MCP tool for agent self-correction: atomic validate+write, agent self-corrects within maxTurns
- Replaces LLM-based output validators with deterministic tools (~0 tokens)

### LLM Constraints
- Anthropic grammar compiler re-expands `$ref`/`$defs` multiplicatively — MUST pre-dereference before sending to LLM
- `additionalProperties: false` on all objects
- `enum` over free-form strings; `description` on every field
- Max 3-level nesting, under 50 fields per schema

### Migration Pattern
- Strangler fig: dual-write/shadow-read, leaf-to-root order
- One migration per PR for rollback safety
- 6 phases per agent: schema def -> MCP tool -> agent behavior -> skill shim -> verify -> cleanup

### Tooling Stack
- `json-dereference-cli` / `@apidevtools/json-schema-ref-parser` for dereferencing
- `check-jsonschema` (Python) for pre-commit hooks
- `ajv-cli` for CLI validation
- Naming: kebab-case filenames, PascalCase `$defs`, `snake_case` properties

## Known Current State (ALL from verified ground truth — DO NOT re-verify)

### Schema Architecture
- 24 schema files: 19 step schemas + 1 seed_manifest schema + 4 core schemas, all in single `schema/` directory (core schemas under `schema/core/`)
- Checked schemas (steps 00, 05, 16) use `$ref` to core schemas. Other step schemas likely do too but are not verified — spot-check in Q1.
- `$defs` usage: Of the 3 schemas checked (00, 05, 16), only step 16 uses local `$defs` (4 defs: specRef, severityLevel, executionStatus, evidenceObject). Other schemas not yet verified — spot-check in Q2.
- Core atoms provides 6 shared `$defs` with `$anchor`: metadata, kebabId, timestamp, owner, tag, screamingSnakeId
- `$id` format: URL-based `https://specdev.local/schema/...`, NOT URN
- `additionalProperties: false` confirmed at root and nested objects (checked on step 00 and step 05)
- Nesting depth: step 00 = 8, step 05 = 10, step 16 = 19 (exceeds 3-level target)
- `description` on properties: minimal (step 00 has description only on `_migration_notes`; step 05 has on `enum_provenance` and `resolver`)
- Schema registry: 29 entries in `tools/schema_registry.json`, URL-based keys

### Validation Pipeline
- validate.py line 136 uses `iter_errors()` — collect-all IS implemented at JSON Schema level
- Errors returned as flat strings, NOT structured objects
- `--json` flag on `validate` and `traceability-check` only (2 of 25 subcommands)
- 77 error codes (52 E, 25 W), 18 PROMOTABLE_PAIRS for W->E promotion
- No WriteValidatedJSON MCP tool or equivalent

### Build/CI Pipeline
- `.pre-commit-config.yaml`: 2 hooks only (dag-lint, extraction-intent-check)
- No build/dereference step, no Makefile
- No `schemas/src/` vs `schemas/dist/` split
- CI: 4 jobs in `.github/workflows/ci.yml` (validate, redteam, deploy-staging, deploy-prod)
- CI runs 14 validation steps including prompt-sync, canonical-lint, canonical-integrity, validate-all, etc.
- No schema staleness check in CI

### Packaging & Tooling
- Python package with setuptools, entry point `specdev = specdev_tools.cli:main`
- Dependencies: jsonschema>=4.21.1, pyyaml>=6.0.1, jsonschema-specifications>=2023.12.1, pyjwt>=2.8.0
- No json-dereference-cli, no check-jsonschema, no ajv-cli in dependencies

## Questions

### Schema Architecture (7 questions)

Q1. How extensively do current schemas use `$ref`? Spot-check 3 step schemas (`schema/04_fr_list.schema.json`, `schema/08_fixtures.schema.json`, `schema/12_ci_gates.schema.json`) — count `$ref` occurrences vs inline definitions. Is there significant duplication that `$defs` could eliminate?

Q2. Only step 16 uses local `$defs`. Are there repeated object structures in other schemas (e.g., the same "generation_quality" or "seed_refs" shape appearing in multiple schemas) that should be extracted to shared `$defs`?

Q3. `additionalProperties: false` is confirmed on step 00 and step 05. Spot-check 3-4 more schemas — is it consistently applied at ALL nested object levels, or only at root?

Q4. Nesting depth reaches 19 in step 16. For LLM structured-output consumption specifically, the research target is max 3 levels (this constraint applies to schemas sent to LLM grammar compilers, not necessarily to schemas validated only by Python `jsonschema`). Assess: which schemas exceed 3 levels? How deep are the most commonly used schemas (steps 00-08)? Which schemas are consumed by LLMs vs only by the Python validator?

Q5. Current schemas use `if/then/else` polymorphism (step 02, step 15, step 16, and core schemas `canon.schema.json`, `collections.schema.json`). The research warns that `if/then/else` must survive dereferencing intact. Count `if/then/else` usage across all schemas and assess whether the proposed `schemas/src/` -> `schemas/dist/` dereferencing pipeline would preserve these conditional structures.

Q6. Enum usage: spot-check 3-4 schemas for places where free-form strings are used but could be constrained to enums. The canonical registry (`canon/kinds/`) has 25 kind files — are schemas referencing these where appropriate?

Q7. Description coverage: the ground truth shows minimal `description` on properties. Spot-check 3 schemas — what percentage of properties have descriptions? The research identifies `description` on every field as one of the highest-leverage LLM compliance techniques (not just documentation -- it directly affects LLM schema adherence). (Target: 100%.)

### Validation Pipeline (4 questions)

Q8. (iter_errors already verified — note this.) To migrate from flat string errors to structured error objects `{ path, message, allowed, received }`: what would need to change in validators, validate.py, and cli.py? Estimate the scope.

Q9. The `--json` flag exists on 2 of 25 subcommands (`validate` and `traceability-check`). To extend JSON output to all subcommands: is there a common output pattern that could be abstracted, or does each subcommand format output differently? (Note: P1-E Q9-Q10 covers the current `--json` output format in detail. If P1-E has not run yet, independently inspect the two existing `--json` implementations in `cli.py`.)

Q10. The research describes a 5-layer validation architecture: (1) pre-commit source schema check, (2) pre-commit dist staleness check, (3) WriteValidatedJSON at write time, (4) agent self-correction loop, (5) skill orchestrator trust boundary. The toolkit currently has 2 pre-commit hooks + CI validation. How does the current pipeline map to these 5 layers? Which layers are missing, and which are partially covered?

Q11. What would a WriteValidatedJSON MCP tool implementation look like for this toolkit? What's the minimum viable version?

### Build Pipeline (3 questions)

Q12. What exists today for schema building/validation in the build pipeline? (CI does validation but no schema compilation/dereferencing.)

Q13. To implement `schemas/src/` -> `schemas/dist/` with `json-dereference-cli`: what is the migration path? How many files move? What references break?

Q14. To switch from URL-based `$id` (`https://specdev.local/schema/...`) to URN-based `$id` (`urn:devspec:...`): what files reference the current `$id` values and would need updating? (Check schema_registry.json, all schema files, validate.py, registry.py, and canon schemas such as `canon/aliases.schema.json` and `canon/kind.schema.json`.)

## Output Format

Write to: `WIP/tool_audit/p2-out-research-alignment.md`

### Finding Format

```
### ALIGNMENT-{N}: {title}

- **Current State**: {what toolkit does now, with specific evidence}
- **Target State**: {what research recommends}
- **Gap Size**: NONE | SMALL | MEDIUM | LARGE | FUNDAMENTAL
- **Migration Effort**: S (days) | M (1-2 weeks) | L (month) | XL (rewrite)
- **Dependencies**: {what else must change first}
- **Quick Win?**: YES / NO — can this be done without breaking changes?
- **Recommendation**: {specific steps to close the gap}
```

### Output Structure

1. Executive summary (5 lines max)
2. Findings (numbered ALIGNMENT-1 through ALIGNMENT-N)
3. Alignment matrix summary table:

```
## ALIGNMENT MATRIX

| # | Research Pattern | Current State | Gap | Effort | Quick Win |
|---|-----------------|---------------|-----|--------|-----------|
```

**Hard limit: 200 lines.**
