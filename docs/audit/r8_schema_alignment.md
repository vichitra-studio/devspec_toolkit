<review_prompt id="R8" layer="L2" gaps="6,7,8,9,10" runs_after="R7" priority="P0-critical">
# Review R8: Schema Tightening — Full Alignment with Hardened Prompts

## Scope
**Prior reviews completed**: R1-R7. All prompts are now hardened with 100% field coverage, explicit sourcing instructions, and zero vague language.

This review is the **second layer** of the 4-Layer Determinism Closure. It closes ALL 83 schema-prompt misalignments so that every field R7-hardened prompts declare MUST is `required` in the schema, every enumerated value set has `enum` constraints, and `minItems` matches prompt minimums.

### Gaps Closed

| # | Gap | Severity |
|---|-----|----------|
| 6 | 83 schema-prompt misalignments (30 HIGH) across 19 step schemas | CRITICAL |
| 7 | `additionalProperties:false` schemas reject prompt-required fields (e.g., step_16a `milestone_ref`) | CRITICAL |
| 8 | Sourcing instructions exist only in prompt prose — schema `description` fields are empty or contain only operational text. Prompts duplicate schema constraints (types, enums, required) creating maintenance drift. No single source of truth for field derivation guidance. | CRITICAL |
| 9 | `canon/manifest.json` has `source_refs` field on 90+ entries but it's unused. `canonicalRef` schema object exists in `collections.schema.json` but prompts manually say "do not populate" instead of schemas/tooling enforcing this. No canonical contract defines which `*_ref` fields are auto-resolved vs AI-populated. | HIGH |
| 10 | `coverage_gaps` is currently optional or absent in most step schemas. It must be required with `minItems: 0` (empty array allowed) and each entry must have a structured format: `{upstream_item_id: string, source_step: string, reason: string}` with `additionalProperties: false`. This is explicitly called out in the pending 13-extra review as "an R8 change" but was not included in the original R8 specification. | HIGH |

### Why R8 Runs After R7

Schemas enforce what prompts demand. R7 finalized prompts (source of truth). R8 tightens schemas to match. If we tightened schemas first, then changed prompts, schemas would need rework. No schema changes after R8.

---

## Files Under Review

| Category | Files |
|----------|-------|
| Step schemas | `schema/00_charter.schema.json` through `schema/16_impl_context.schema.json` (19 step schemas + seed_manifest = 20 files). **NOTE**: Steps 16a, 16b, 16c share `schema/16_impl_context.schema.json` via schema_registry.json — there are no separate schema files for these steps. |
| Core schemas (reference) | `schema/core/*.schema.json` |
| R7-hardened prompts (reference) | `prompts/prompt_00_*.md` through `prompts/prompt_16c_*.md` (22 files) |
| Existing spec artifacts (breakage check) | `spec/*.json` |
| Test fixtures | `tests/fixtures/` |
| Step validators (limited adjustments) | `tools/specdev_tools/validation/validators/step_*.py` |
| Canonical registry | `canon/manifest.json` — canonical registry (source_refs population) |
| Core schemas (extension) | `schema/core/collections.schema.json` — canonicalRef schema extension |
| Core schemas (extension) | `schema/core/canon.schema.json` — canonical entry schema (source_refs, binding_mode) |

---

## Known HIGH-Severity Targets

From prior subagent audit (R6 Phase 1), these schemas have the most misalignments:

| Step | Schema File | Gap Count | HIGH | Key Issues |
|------|-------------|-----------|------|------------|
| 05 (APIs) | `schema/05_interface_contracts.schema.json` | 7 | 4 | `route`, `method`, `trace`, `security` optional but prompt says MUST |
| 16/16a/16b/16c | `schema/16_impl_context.schema.json` (shared) | 7+5+5 | 5+2+4 | Steps 16a/16b/16c share this schema. `review`, `findings.metadata`, `milestone_ref` optional/rejected; `execution`, `evidence` optional. `milestone_ref` REQUIRED by prompt_16a but `additionalProperties:false` REJECTS it — P0 bug. |
| 04 (FRs) | `schema/04_fr_list.schema.json` | 4 | 2 | `trace` optional on FR items but prompt says MUST; `acceptance_criteria` minItems gap (R6 confirmed: lines 89-94) |
| 01 (Caps) | `schema/01_capabilities.schema.json` | 5 | 2 | `owner` and `trace` on capability items optional |
| 09 (Impl Plan) | `schema/09_impl_plan.schema.json` | 5 | 2 | `milestones` and `deliverables` optional |

**IMPORTANT**: Steps 16a, 16b, 16c do NOT have separate schema files. The schema_registry.json maps all three to `schema/16_impl_context.schema.json`. When tightening this shared schema, changes affect all four steps (16, 16a, 16b, 16c). If different steps need different required fields, R8 must either (a) add conditional validation in the validator, or (b) split the schema. This is a Phase 1 investigation question.

---

## R7↔R8 Coherence Protocol

Schema and prompt are tightly coupled. R7 runs first (prompt is source of truth), but R8 may discover schema realities that require prompt corrections:

| Scenario | Action |
|----------|--------|
| Schema adds a field definition (e.g., step_16a `milestone_ref`) | R7 prompt already covers it → no change needed |
| Schema has enum values the prompt doesn't list | Update prompt to enumerate all valid values from schema |
| Schema nesting differs from prompt's Field-by-Field | Update prompt to match actual schema structure |
| Schema cannot be tightened without breaking artifacts | Prompt must be relaxed to match schema reality, with documented rationale |

After R8 completes, re-run R7's `test_prompt_contracts.py` and `test_prompt_schema_sync.py` to confirm bidirectional coherence.

R7 adds `## Coverage Gap Reporting` instructions to all prompts. R8 must ensure every step schema has `coverage_gaps` in `required[]` with the matching structured entry format. The prompt instructs population; the schema enforces structure.

---

## Subagent Protocol (MANDATORY)

### Main Agent Rules
- **FORBIDDEN in main agent**: Read, Edit, Write, Grep, Glob, Bash for file content
- **All investigation MUST be delegated to subagents — no exceptions**
- Main agent: receive summaries, synthesize findings table, create task list, final report
- Token budget: < 5K tokens total for main agent across all phases

### Subagent Assignment

#### Phase 1 — Investigation (2 Explore subagents, launch together)

**Subagent A** (`Explore`, no isolation) — Steps 00-08 Schema-Prompt Comparison:
```
For EACH step 00 through 08, compare the schema against the R7-hardened prompt:

1. Read the schema file (schema/NN_*.schema.json)
2. Read the corresponding R7-hardened prompt (prompts/prompt_NN_*.md)
3. For each field in the prompt's Field-by-Field Specification section:
   a. Is this field in the schema's `required[]`? If prompt says MUST but schema says optional → FLAG
   b. Does the prompt enumerate values? Does the schema have a matching `enum`? → FLAG if missing
   c. Does the prompt specify a minimum count? Does the schema have matching `minItems`? → FLAG if missing
   d. Does the schema have `additionalProperties: false`? Does it reject any prompt-required field? → FLAG as P0

4. Check breakage: Read existing spec/NN_*.json artifacts. Would tightening the schema
   (adding to required[], adding enum, adding minItems) break existing valid artifacts?
   Report: field, proposed change, breakage risk (yes/no/unknown).

5. Bidirectional coherence: Does the schema have constraints NOT reflected in the R7 prompt?
   (e.g., schema has a valid enum value the prompt doesn't mention, schema nesting differs)
   Report these as prompt-update candidates.

Produce a table per schema:
| Field Path | Prompt Says | Schema Says | Gap Type | Breakage Risk | Action |
|------------|-------------|-------------|----------|---------------|--------|

Summary: total gaps, HIGH gaps, breakage risks.

Additional investigation: Audit all 19 step schemas for presence and structure of `coverage_gaps`. Record which schemas have it, which don't, and whether existing definitions match the target structure: `{upstream_item_id: string, source_step: string, reason: string}` with `additionalProperties: false`.
```

**Subagent B** (`Explore`, no isolation) — Steps 09-16c Schema-Prompt Comparison:
```
Same comparison as Subagent A, for steps 09 through 16c.

KNOWN P0 ISSUES to verify and include:
- schema/16_impl_context.schema.json (shared by 16/16a/16b/16c): `additionalProperties:false`
  rejects `milestone_ref` which prompt_16a requires. This is a schema BUG — field definition
  must be added. Also: `review`, `findings.metadata`, `remediation_task` (prompt_16c),
  `execution`, `evidence`, `critical_evidence` (prompt_16b) are optional but prompts say MUST.
- schema/05_interface_contracts.schema.json: `route`, `method`, `trace`, `security` are
  optional but R7 prompt says MUST.
- schema/04_fr_list.schema.json: `trace` on FR items optional; `acceptance_criteria` minItems gap.

NOTE: Steps 16a, 16b, 16c do NOT have separate schema files. All three map to
schema/16_impl_context.schema.json via schema_registry.json. When auditing, compare each
step's prompt against the SAME schema file but note which definitions/sections apply.

Also check: for schemas with `additionalProperties: false`, list ALL fields the R7 prompt
mentions that are NOT defined in the schema. Each is a potential rejection bug.

Produce same table format as Subagent A.
```

#### Phase 2 — Implementation (after Phase 1, sequential)

**Subagent C** (`general-purpose`, isolation: `worktree`) — P0 Schema Fixes (additionalProperties rejection):
```
Fix schemas where `additionalProperties: false` rejects prompt-required fields.
These are P0 because the schema literally cannot accept valid AI output.

Based on Phase 1 findings, for each schema with rejection bugs:
1. Add the missing field definition to the schema's `properties`
2. Add the field to `required[]` if the R7 prompt says MUST
3. Use appropriate types and constraints from the prompt's Field-by-Field section
4. Validate: ./tools/run_specdev.sh validate-all spec --repo-root ./devspec_toolkit

KNOWN P0:
- schema/16_impl_context.schema.json: Add `milestone_ref` field definition (used by prompt_16a
  but rejected by additionalProperties:false). This is the shared schema for steps 16/16a/16b/16c.
  When adding fields, verify the addition doesn't conflict with other steps using this schema.

Additional P0s from Phase 1 findings.

After changes: run pytest tests/ -k schema -v
```

**Subagent D** (`general-purpose`, isolation: `worktree`) — Steps 00-08 Schema Tightening:
```
For each schema in steps 00-08 with HIGH gaps from Phase 1:

1. Add fields to `required[]` where R7 prompt says MUST and schema says optional
2. Add `enum` constraints where R7 prompt enumerates allowed values
3. Add `minItems: N` where R7 prompt says "at least N"
4. Do NOT tighten beyond what prompts demand
5. After EACH schema change: ./tools/run_specdev.sh validate spec/NN_*.json --repo-root ./devspec_toolkit
   If validation fails against existing artifacts, REVERT and document as "cannot tighten without breakage"

Focus on HIGH severity gaps first. MED gaps only if time permits and no breakage risk.

After all changes: pytest tests/ -k schema -v
```

**Subagent E** (`general-purpose`, isolation: `worktree`) — Steps 09-16c Schema Tightening:
```
Same as Subagent D, for steps 09-16c.

KNOWN HIGH targets:
- schema/05_interface_contracts.schema.json: add route, method, trace, security to required[]
- schema/16_impl_context.schema.json (shared): This is the ONLY schema for steps 16/16a/16b/16c.
  Tightening requires careful analysis of which fields apply to which step:
  - prompt_16c requires: review, findings.metadata, remediation_task
  - prompt_16b requires: execution, evidence, critical_evidence
  - prompt_16 requires: plan.summary, plan.spec_alignment, plan.docs_impact
  If fields are step-specific, they may need to remain optional in the shared schema and
  be enforced by step-specific validators in R9 instead. Flag for Phase 1 investigation.
- schema/04_fr_list.schema.json: add trace to FR item required[]
- schema/09_impl_plan.schema.json: add milestones, deliverables to required[]

After EACH change: validate against existing spec artifacts.
After all changes: pytest tests/ -k schema -v
```

**Subagent F** (`general-purpose`, isolation: `worktree`) — Test Fixture Updates:
```
After schema tightening, some test fixtures may fail validation.

1. Run: pytest tests/ -v 2>&1 | grep FAILED
2. For each failing fixture in tests/fixtures/:
   a. Read the fixture file
   b. Read the updated schema
   c. Add the newly-required fields with valid values
   d. Re-run the specific test to confirm it passes

Do NOT modify "invalid" fixtures (tests/fixtures/invalid/) — they should remain invalid.
Only fix "valid" fixtures that now fail due to tighter schemas.

After all changes: pytest tests/ -v (full suite must pass)
```

**Subagent G** (`general-purpose`, isolation: `worktree`) — Bidirectional Prompt Coherence Fixes:
```
Based on Phase 1 bidirectional coherence findings, fix prompts where schemas revealed
constraints the R7 prompt didn't account for:

1. Schema has enum values the prompt doesn't list → add to prompt's Field-by-Field section
2. Schema nesting differs from prompt's Field-by-Field → update prompt structure
3. Schema cannot be tightened without breakage → relax prompt language, add rationale comment

For each prompt change:
- Read the CURRENT prompt state (includes R7 changes)
- Make MINIMAL changes — only what bidirectional coherence requires
- Do not re-harden or re-audit — only align prompt to schema reality

After changes: run pytest tests/test_prompt_schema_sync.py -v
```

**Subagent H** (`general-purpose`, isolation: `worktree`) — Schema Sourcing via `description`:
```
Populate standard JSON Schema `description` fields across all 19 step schemas with sourcing
guidance extracted from R7a prompt Field-by-Field sections.

`description` is schema metadata (like code comments) — it never appears in output artifacts.
`prompt_generator.py` already reads these via `FIELD_DESCRIPTION`.

For each step schema:
1. Read the corresponding R7a-hardened prompt's Field-by-Field section
2. Extract sourcing guidance (WHERE to get the value, HOW to derive it)
3. Populate the schema field's `description` with that sourcing text
4. Keep existing operational descriptions — append sourcing guidance

Example:
{
  "fr_id": {
    "type": "string",
    "pattern": "^[a-z0-9]+(?:-[a-z0-9]+)*$",
    "description": "Source from 01_capabilities.json → capabilities[].capability_id. Generate using kebab-case from verb+object of the capability statement."
  }
}

After all changes: pytest tests/ -k schema -v
```

**Subagent I** (`general-purpose`, isolation: `worktree`) — Canonical Binding Contract:
```
Extend canonical infrastructure with binding mode support:

1. Add `binding_mode` to canonicalRef schema in `schema/core/collections.schema.json`:
   - "auto" — tooling resolves this ref post-generation
   - "explicit" — AI must populate this ref during generation

2. Populate `source_refs` in `canon/manifest.json` entries where applicable

3. Schema validation can then enforce: auto-binding refs MUST be empty in AI output
   (tooling fills them post-generation)

After changes: pytest tests/ -v
```

**Subagent J** (`general-purpose`, isolation: `worktree`) — Validator Adjustments (limited):
```
After schema tightening, check if any validators reference fields that changed:

1. Read each step validator in tools/specdev_tools/validation/validators/step_*.py
2. If a validator checks a field that is now required[] (was optional), the check is
   still valid but may be redundant — leave it (defense in depth)
3. If a validator references a field name that was RENAMED in schema tightening,
   update the field name reference
4. Do NOT do a full validator overhaul — that's R9

This subagent may have nothing to do if schema tightening only added to required[] without renaming.

After changes: pytest tests/ -v
```

**Subagent J2** (`general-purpose`, isolation: `worktree`) — `coverage_gaps` Schema Enforcement (Gap #10):
```
Add `coverage_gaps` to every step schema's `required[]` array with `minItems: 0`.
Define the array item schema as:
{
  "type": "object",
  "required": ["upstream_item_id", "source_step", "reason"],
  "properties": {
    "upstream_item_id": { "type": "string" },
    "source_step": { "type": "string", "pattern": "^[0-9]{2}[a-c]?$" },
    "reason": { "type": "string", "minLength": 10 }
  },
  "additionalProperties": false
}

Steps:
1. Check if `schema/core/collections.schema.json` already defines a reusable `coverageGap`
   type. If so, use `$ref` to it. If not, define it in `schema/core/collections.schema.json`
   first, then reference it from all step schemas.
2. For each of the 19 step schemas, add `coverage_gaps` to `properties` (as an array of
   the above item schema with `minItems: 0`) and to `required[]`.
3. Validate: ./tools/run_specdev.sh validate-all spec --repo-root ./devspec_toolkit
4. Update test fixtures in tests/fixtures/ to include `coverage_gaps: []` where missing.

After all changes: pytest tests/ -v
```

#### Phase 3 — Integration Test Run

**Subagent K** (`general-purpose`, no isolation) — Full integration verification:
```
Run the complete validation suite:

1. pytest tests/ -v
2. ./tools/run_specdev.sh validate-all spec --repo-root ./devspec_toolkit
3. ./tools/run_specdev.sh spec-quality-lint spec --repo-root ./devspec_toolkit
4. ./tools/run_specdev.sh hallucination-lint spec --repo-root ./devspec_toolkit
5. pytest tests/test_prompt_contracts.py tests/test_prompt_schema_sync.py -v
   (bidirectional coherence check from R7)

All must pass. Report any failures with exact error messages.
```

#### Phase 4 — Self-Verification

**Subagent L** (`Explore`, no isolation) — Verify R8 goals met:
```
After all implementation is complete, verify measurable goals:

1. Re-run the Phase 1 schema-prompt comparison for ALL schemas.
   Count remaining HIGH misalignments. Target: 0.
   Count remaining MED misalignments. Target: <5.

2. Search all schemas for `additionalProperties: false` combined with prompt-required
   fields not defined in schema. Target: 0 rejection bugs.

3. Confirm existing spec/ artifacts still pass validate-all.

4. Confirm prompt↔schema sync tests pass (bidirectional coherence).

Report: per-goal pass/fail with counts.
```

#### Phase 5 — Findings Report

**Subagent M** (`general-purpose`, no isolation) — Write findings:
```
Write findings to docs/audit/findings/r8_findings.md using compact table format.

Include:
- Part A: Findings table (all schema-prompt gaps found, with severity and resolution status)
- Part B: Implementation summary (schemas changed, fields tightened, breakage incidents)
- Part C: Bidirectional coherence fixes (prompts updated to match schema reality)
- Part D: Measurable goals verification (from Phase 4)
- Part E: Residual issues (MED gaps left intentionally, with rationale)

Also update docs/audit/review_index.md to add R8 entry.
Update CHANGELOG with schema tightening changes (fields promoted to required, additionalProperties fixes, breakage incidents).
```

---

## Key Design Decisions

- Schema tightening MUST NOT break existing valid `spec/` artifacts — validate before committing
- Schema follows **prompt authority** — only tighten to match what R7 prompts now demand
- `additionalProperties:false` schemas that reject prompt-required fields are P0 bugs
- Validator adjustments in R8 are limited to schema-field changes only (full overhaul is R9)
- **Bidirectional coherence**: any schema change that invalidates an R7 prompt must trigger a prompt update in the same review
- MED severity gaps MAY be left as intentional flexibility with documented rationale

---

## Measurable Goals

| Metric | Before R8 | After R8 |
|--------|-----------|----------|
| Schema-prompt HIGH misalignments | 30 | **0** |
| Schema-prompt MED misalignments | 27 | **<5** (intentional flexibility) |
| Fields required by prompt but rejected by schema | 2+ | **0** |
| Existing spec/ artifacts pass validate-all | yes | **yes** |
| Prompt↔schema sync tests pass | unknown | **yes** |
| Schemas with required coverage_gaps (minItems: 0) | unknown/19 | **19/19** |

---

## Anti-Patterns

- Do NOT tighten schemas beyond what prompts demand — schema follows prompt authority
- Do NOT break existing spec artifacts — always validate first, revert if breakage
- Do NOT do full validator overhaul — that's R9
- Do NOT modify prompts beyond narrow bidirectional coherence corrections (adding missing enum values from schema, fixing structural nesting to match schema reality, relaxing language when schema cannot be tightened). Do NOT re-harden, re-audit, or add new field coverage — R7 prompt hardening is complete.
- Do NOT add `additionalProperties: false` to schemas that don't already have it — only fix existing rejections

---

## Dependencies

| Direction | Review | Relationship |
|-----------|--------|-------------|
| Requires | R7 | Prompts must be hardened before schemas can tighten to match |
| Requires | R1-R6 | All structural fixes must be in place |
| Blocks | R9 | Validators build against R8-tightened schemas |
</review_prompt>
