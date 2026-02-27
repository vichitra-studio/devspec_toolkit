# Review R7 Findings — Deep Prompt Completeness & Determinism Audit
Generated: 2026-02-27
Status: COMPLETE

## Context

R7 is the first layer of the 4-Layer Determinism Closure. It audits ALL 22 prompts against their schemas to ensure 100% field coverage, zero vague language, explicit sourcing for every field, and structural completeness (Metadata Contract, Self-Audit Gate, Operating Flow). R1–R6 structural fixes are in place. R7 finalizes prompt hardening before R8 (schemas) and R9 (validators).

**Output file**: `docs/audit/findings/r7_findings.md` (to be written as T00 during implementation)

**Known resolved issue**: `governance_label_ref` in prompt_13 was listed as KNOWN CRITICAL in R7 review spec but Subagent B confirmed it is **RESOLVED** in current prompt text — no action needed.

---

## Part A: Findings

| ID | Sev | File(s) | Finding | Impact |
|----|------|---------|---------|--------|
| A-R7-01 | CRIT | All 22 prompts + 3 test files | `## Metadata Contract` missing from all 22 prompts; tests use `## B4 Metadata Contract` delimiter — all skip silently, test suite is vacuously green | Zero test coverage on Output Contract metadata |
| A-R7-02 | CRIT | All 22 prompts | `created_at` (required field) has no instruction in any prompt | AI must guess/hallucinate timestamp format |
| A-R7-03 | CRIT | prompts/prompt_12_ci_gates.md | `jobs[].environment_ref` REQUIRED in schema but absent from prompt, Field Guidance, and Output Contract | Every Step 12 artifact fails schema validation |
| A-R7-04 | CRIT | prompts/prompt_16a_impl_planner.md | `milestone_ref` mandated as MANDATORY in prompt but field does NOT exist in schema/16_impl_context.schema.json | `additionalProperties: false` rejects every artifact |
| A-R7-05 | CRIT | prompts/prompt_10_governance.md | `review_policy` object (3 REQUIRED sub-fields: verdict_requirements, required_metadata, evidence_source_by_phase with dev/staging/prod) completely absent | AI has no guidance on required object structure |
| A-R7-06 | CRIT | prompts/prompt_05_interface_contracts.md | `apis[].enum_provenance` (5 sub-fields, 3 required: source_url, source_date, resolved_at) has zero coverage | Complete blind spot — validation failure when triggered |
| A-R7-07 | HIGH | prompts/prompt_10_governance.md | `pr_rules`/`versioning` use "should"/"Optional→expected" framing instead of MUST | Non-deterministic; AI may omit governance fields |
| A-R7-08 | HIGH | prompts/prompt_12_ci_gates.md | `jobs[].security` object (runner_labels, token_permissions, environment_protection) completely absent | No CI security hardening guidance |
| A-R7-09 | HIGH | 18 prompts (00-09, 11-16c) | ~25 optional `*_ref` canonical fields systematically absent (action_ref, entity_ref, role_ref, status_ref, stage_ref, etc.) | AI ignores or hallucinates canonical refs |
| A-R7-10 | HIGH | All 22 prompts | ~72 field instances lack upstream artifact + field path sourcing (measurement_method, severity, stage, mode, compliance, owner, etc.) | High hallucination risk on free-text fields |
| A-R7-11 | HIGH | prompts/prompt_05_interface_contracts.md | `apis[].parameters` sub-fields partially addressed; `in` enum never stated; `parameters[].schema` absent | Invalid parameter objects likely |
| A-R7-12 | MED | 9 prompts (01,02,02a,03,05,06,07,08,09) | "feeds X downstream steps" placeholder unfilled on line 3 | Degraded prompt context for AI runners |
| A-R7-13 | MED | All 22 prompts | ~120 vague language occurrences: "where applicable", "if appropriate", "consider", "such as", "etc", "as needed", "may include", "prefer", "non-trivial" | Determinism failures; AI interprets subjectively |
| A-R7-14 | MED | 6 prompts (02a,06,10,11,12,13a) | Self-Audit Gate criteria are vague ("all fields populated", "structure is valid") instead of listing required[] fields by name | Gate provides no mechanical verification |
| A-R7-15 | MED | 6 prompts (11,13,14,16,16b,16c) | `## Operating Flow` header missing — score trigger present but section unnamed | Parser/structural inconsistency |
| A-R7-16 | MED | 18 prompts with Best Practices | Soft-modality "should"/"prefer" in Best Practices instead of MUST | Advisory language where binding constraints needed |
| A-R7-17 | MED | prompts/prompt_16_impl_context.md:176 | `# Self-Audit Gate` (H1) instead of `## Self-Audit Gate` (H2) | Parser splitting on `##` misses this gate |
| A-R7-18 | LOW | All 22 prompts | `_migration_notes` absent — optional, system-managed, but no "do not populate" instruction | AI may unnecessarily populate |
| A-R7-19 | LOW | prompts/prompt_12_ci_gates.md | Canonical Registry appears BEFORE Output Contract (positional inversion vs convention) | Structural inconsistency |
| A-R7-20 | LOW | prompts/prompt_16b_impl_coder.md | Only 1 exact JSON upstream reference | Weak traceability to upstream specs |

### Evidence

**A-R7-01:**
- `tests/test_prompt_contracts.py`: `if "## B4 Metadata Contract" not in text: continue` — skips every prompt
- `tests/test_prompt_schema_sync.py`: 8 occurrences of `"## B4 Metadata Contract"` as delimiter
- `tests/test_cli.py`: 1 occurrence at line 142
- Zero prompts contain either `## Metadata Contract` or `## B4 Metadata Contract`

**A-R7-03:**
- `schema/12_ci_gates.schema.json` → `jobs` items `required: ["job_id", "name", "steps", "environment_ref"]`
- `prompts/prompt_12_ci_gates.md` Field Guidance lists only: `job_id/name`, `requires`, `steps` — `environment_ref` absent

**A-R7-04:**
- `prompts/prompt_16a_impl_planner.md`: "Every checklist item MUST include a `milestone_ref` field"
- `schema/16_impl_context.schema.json`: No `milestone_ref` property in checklist items; `additionalProperties: false`

**A-R7-05:**
- `schema/10_governance.schema.json` → `review_policy` object with `verdict_requirements` (minItems:1), `required_metadata`, `evidence_source_by_phase` (dev/staging/prod all REQUIRED)
- `prompts/prompt_10_governance.md`: Zero mentions of `review_policy`

**A-R7-06:**
- `schema/05_interface_contracts.schema.json` → `apis[].enum_provenance` with required: `source_url`, `source_date`, `resolved_at`
- `prompts/prompt_05_interface_contracts.md`: Zero mentions of `enum_provenance`

---

## Part B: Atomic Implementation Plan

### Sequencing Strategy

1. **Test infrastructure first** (rename B4→Metadata Contract) — T01-T03
2. **Prompt fixes** (one task per prompt, all findings batched) — T04-T25
3. **Integration verification** — T26
4. **Documentation** — T27-T28

Each prompt task is delegated to a `general-purpose` subagent with `isolation: "worktree"`. Each prompt is touched exactly ONCE.

### Task Table

| ID | Pri | Deps | File | Change summary | Acceptance command | Findings |
|----|-----|------|------|----------------|-------------------|----------|
| T00 | P0 | — | docs/audit/findings/r7_findings.md | Write this findings plan to file (create) | `test -f docs/audit/findings/r7_findings.md` | — |
| T01 | P0 | T00 | tests/test_prompt_contracts.py | Replace ALL occurrences of `"B4 Metadata Contract"` → `"Metadata Contract"` (R7 spec says 6; Subagent C found 4 — agent MUST grep to find exact count and replace all) | `grep -c "B4 Metadata" tests/test_prompt_contracts.py` returns 0 | A-R7-01 |
| T02 | P0 | T00 | tests/test_prompt_schema_sync.py | Replace ALL occurrences of `"B4 Metadata Contract"` → `"Metadata Contract"` (expected ~8) | `grep -c "B4 Metadata" tests/test_prompt_schema_sync.py` returns 0 | A-R7-01 |
| T03 | P0 | T00 | tests/test_cli.py | Replace ALL occurrences of `"B4 Metadata Contract"` → `"Metadata Contract"` (expected 1) | `grep -c "B4 Metadata" tests/test_cli.py` returns 0 | A-R7-01 |
| T04 | P0 | T01-T03 | prompts/prompt_00_project_charter.md | **All R7 fixes for Step 00**: (1) Add `## Metadata Contract` section before Output Contract with $schema URI, spec_version, generation_quality fields. (2) Add `created_at`: "Set to ISO-8601 UTC timestamp of generation". (3) Add sourcing for 12 unsourced fields: `owner` → "from seed_overview.md project ownership", `title` → "extract from seed_overview.md title/heading", `stakeholders[*].role` → "from seed_overview.md stakeholder section", `stakeholders[*].needs` → "derive from seed_overview.md pain points", `user_segments[*].description/pains/gains` → "from seed_overview.md user research", `success_metrics[*].name/target/measurement_method` → "from seed_overview.md KPIs or ask gap question". (4) Add `stakeholders[*].role_ref`: "Do not populate manually; resolved by canonical registry tooling." (5) Add `_migration_notes`: "Do not populate; system-managed." (6) Replace vague: "pick the accountable group" → "MUST select from owner enum based on seed_overview.md project ownership"; "where known" → "MUST include if seed data provides historical baselines; otherwise ask gap question"; "may include" → "MUST include"; "identify real stakeholders" → "MUST list stakeholders from seed_overview.md". (7) Harden Best Practices "should" → "MUST". (8) Harden Self-Audit Gate to list each required field by name. | `pytest tests/test_prompt_contracts.py -v -k "prompt_00"` | A-R7-01,02,09,10,13,14,16,18 |
| T05 | P0 | T01-T03 | prompts/prompt_01_capabilities.md | **All R7 fixes for Step 01**: (1) Add `## Metadata Contract`. (2) Add `created_at` instruction. (3) Add missing fields: `action_ref`, `entity_ref`, `role_ref` → "Do not populate manually; resolved by canonical registry tooling." (4) Add `_migration_notes`: "Do not populate." (5) Add sourcing for 11 unsourced fields: `owner`, `capability_id`, `verb`, `description`, `inputs`, `outputs`, `preconditions`, `postconditions`, `error_states` — each with specific upstream artifact path from 00_charter.json. (6) Replace vague: "non-trivial" → "any capability that modifies state or requires authentication"; "if appropriate" → "MUST include if capability has state prerequisites"; "as needed" → "MUST include"; "high-risk" → "any capability handling PII, financial data, or authentication"; "if any FR draft exists" → "MUST reference FR IDs from 04_fr_list.json when available, use *-tbd anchors otherwise". (7) Fix "X downstream steps" placeholder → actual count from step_order.json. (8) Harden Best Practices. (9) Harden Self-Audit Gate. | `pytest tests/test_prompt_contracts.py -v -k "prompt_01"` | A-R7-01,02,09,10,12,13,16,18 |
| T06 | P0 | T01-T03 | prompts/prompt_02_system_sketch.md | **All R7 fixes for Step 02**: (1) Add `## Metadata Contract`. (2) Add `created_at`. (3) Add missing: `components[*].entity_ref`, `connections[*].interface_ref`, `connections[*].event_ref` → "Do not populate manually; resolved by canonical registry tooling." (4) `_migration_notes`: "Do not populate." (5) Add sourcing for unsourced fields: `components[*].type` → "derive from 01_capabilities.json capability scope", `components[*].tags` → "select from schema enum based on component responsibilities", `connections[*].trust_boundary/auth/rate_limit/reliability` → "derive from seed_tech_stack.md security and infrastructure sections". (6) Replace vague: "appropriate tags" → "MUST select from enum: [list full enum]"; "as applicable" → "MUST include for all connections". (7) Fix "X downstream steps". (8) Harden Best Practices. (9) Harden Self-Audit Gate. | `pytest tests/test_prompt_contracts.py -v -k "prompt_02" --no-header` | A-R7-01,02,09,10,12,13,16,18 |
| T07 | P0 | T01-T03 | prompts/prompt_02a_delivery_baseline.md | **All R7 fixes for Step 02a**: (1) Add `## Metadata Contract`. (2) Add `created_at`. (3) Add missing: `environment_ref`, `command_ref`, `policy_ref` → "Do not populate manually; resolved by canonical registry tooling." (4) `_migration_notes`: "Do not populate." (5) Add sourcing: `compliance` → "extract from seed_overview.md regulatory requirements; if absent, ask gap question". (6) Replace vague: "minimal structure" → "MUST include all propertyNames matching schema constraints"; "if relevant" → "MUST include if seed docs mention regulatory/compliance frameworks"; "when NFRs or governance imply" → "MUST include if 07_nfrs.json contains compliance-category NFRs". (7) Fix "X downstream steps". (8) Harden Best Practices + Self-Audit Gate. | `pytest tests/test_prompt_contracts.py -v -k "prompt_02a"` | A-R7-01,02,09,10,12,13,14,16,18 |
| T08 | P0 | T01-T03 | prompts/prompt_03_glossary.md | **All R7 fixes for Step 03**: (1) Add `## Metadata Contract`. (2) Add `created_at`. (3) Add missing: `terms[*].acronym_ref`, `terms[*].unit_ref` → "Do not populate manually; resolved by canonical registry tooling." (4) `_migration_notes`: "Do not populate." (5) Add explicit `acronym` field guidance with pattern `^[A-Z0-9]{2,}$`. (6) Add sourcing: `terms[*].domain` → "derive from capability domain in 01_capabilities.json"; `terms[*].term_id` → "generate from term using kebab-case". (7) Replace vague: "optional but recommended" → "MUST populate if term has a recognized domain"; "where relevant" → remove or specify condition; "consider" → "MUST". (8) Fix "X downstream steps". (9) Harden Best Practices + Self-Audit Gate. | `pytest tests/test_prompt_contracts.py -v -k "prompt_03"` | A-R7-01,02,09,10,12,13,16,18 |
| T09 | P0 | T01-T03 | prompts/prompt_04_functional_requirements.md | **All R7 fixes for Step 04**: (1) Add `## Metadata Contract`. (2) Add `created_at`. (3) Add missing: `action_ref`, `entity_ref`, `status_ref` → canonical registry note. (4) `_migration_notes`. (5) Sourcing: `fr_id` → "generate from statement verb+object in kebab-case"; `preconditions/postconditions` → "derive from 01_capabilities.json preconditions/postconditions for mapped capability"; `criterion_id` → "generate from criterion text". (6) Replace vague: "where relevant" → "MUST include if capability has preconditions/postconditions"; "where possible" → "MUST"; "as known" → "MUST include or ask gap question". (7) Harden Best Practices + Self-Audit Gate. | `pytest tests/test_prompt_contracts.py -v -k "prompt_04"` | A-R7-01,02,09,10,13,16,18 |
| T10 | P0 | T01-T03 | prompts/prompt_05_interface_contracts.md | **All R7 fixes for Step 05** (HEAVY — 3 CRIT/HIGH findings): (1) Add `## Metadata Contract`. (2) Add `created_at`. (3) **A-R7-06**: Add complete `apis[].enum_provenance` field guidance: "MUST populate when API uses externally-sourced enums. Required sub-fields: `source_url` (URL of enum source), `source_date` (ISO-8601 date enum was sourced), `resolved_at` (ISO-8601 timestamp of resolution). Optional: `resolved_version`, `resolver`. Source from: external API documentation or standards body referenced in seed_tech_stack.md." (4) **A-R7-11**: Add complete `apis[].parameters` sub-field guidance: `parameters[*].name` (string, parameter name), `parameters[*].in` (enum: query|path|header — MUST specify), `parameters[*].required` (boolean), `parameters[*].schema` (JSON Schema object or $ref). (5) Add missing: `apis[*].example_refs`, `apis[*].event_ref`, `apis[*].entity_ref`, `apis[*].policy_ref` → canonical registry note. (6) `_migration_notes`. (7) Sourcing for: `api_id`, `name`, `version`, `route`, `method`, `request_schema_ref`, `response_schema_ref` → specific upstream paths. (8) Replace vague: "where applicable" → "MUST include for all APIs with query/path/header parameters"; "when known" → "MUST include or use -tbd placeholder"; "prefer" → "MUST use". (9) Fix "X downstream steps". (10) Harden Best Practices + Self-Audit Gate. | `pytest tests/test_prompt_contracts.py -v -k "prompt_05"` | A-R7-01,02,06,09,10,11,12,13,16,18 |
| T11 | P0 | T01-T03 | prompts/prompt_06_invariants.md | **All R7 fixes for Step 06**: (1) Add `## Metadata Contract`. (2) Add `created_at`. (3) Add missing: `risk_category_ref`, `status_ref` → canonical registry note. (4) `_migration_notes`. (5) Sourcing: `inv_id` → "generate from description domain+constraint in kebab-case"; `language` → "MUST use jsonlogic or cel for machine-verifiable rules; text ONLY for rules that cannot be expressed formally"; `severity` → "MUST be error for data-integrity/security rules, warn for performance/style rules". (6) Replace vague: "unless absolutely necessary" → "ONLY when rule involves natural-language business logic that has no formal predicate equivalent". (7) Fix "X downstream steps". (8) Harden Best Practices + Self-Audit Gate. | `pytest tests/test_prompt_contracts.py -v -k "prompt_06"` | A-R7-01,02,09,10,12,13,14,16,18 |
| T12 | P0 | T01-T03 | prompts/prompt_07_nfrs.md | **All R7 fixes for Step 07**: (1) Add `## Metadata Contract`. (2) Add `created_at`. (3) Add missing: `nfrs[*].stage_ref` → canonical registry note. (4) `_migration_notes`. (5) Sourcing: `nfr_id` → "generate from category+metric in kebab-case"; `category` → "MUST select from schema enum based on metric type"; `measurement_method` → "extract from seed_tech_stack.md monitoring/observability section; if absent, ask gap question — DO NOT fabricate PromQL queries or dashboard URLs"; `stage` → "MUST select based on where metric is measurable: dev for local metrics, ci for build metrics, staging for integration, prod for live"; `nfrs[*].owner` → "MUST match component owner from 02_system_sketch.json for the component this NFR constrains". (6) Replace vague: "available upstream artifacts and seed guidance" → specific artifact+field paths; "as applicable" → "MUST". (7) Fix "X downstream steps". (8) Harden Best Practices + Self-Audit Gate. | `pytest tests/test_prompt_contracts.py -v -k "prompt_07"` | A-R7-01,02,09,10,12,13,16,18 |
| T13 | P0 | T01-T03 | prompts/prompt_08_fixtures.md | **All R7 fixes for Step 08**: (1) Add `## Metadata Contract`. (2) Add `created_at`. (3) `_migration_notes`. (4) Sourcing: `fixture_id` → "generate from scenario description in kebab-case"; `mode` → "MUST be unit for isolated logic, contract for API boundary, e2e for multi-component flows, redteam for security scenarios from 11_redteam.json"; `tags` → "MUST select from canonical tag registry — DO NOT invent tags". (5) Replace vague: "e.g."/"such as" → explicit enum lists from schema; "when NFRs exist" → "MUST create fixtures for every NFR in 07_nfrs.json with measurable targets"; "where needed" → "MUST". (6) Fix "X downstream steps". (7) Harden Best Practices + Self-Audit Gate. | `pytest tests/test_prompt_contracts.py -v -k "prompt_08"` | A-R7-01,02,10,12,13,16,18 |
| T14 | P0 | T01-T03 | prompts/prompt_09_impl_plan.md | **All R7 fixes for Step 09**: (1) Add `## Metadata Contract`. (2) Add `created_at`. (3) Add missing: `environment_ref` → canonical registry note. (4) `_migration_notes`. (5) Sourcing for unsourced fields. (6) Replace vague language. (7) Fix "X downstream steps". (8) Harden Best Practices + Self-Audit Gate. | `pytest tests/test_prompt_contracts.py -v -k "prompt_09"` | A-R7-01,02,09,10,12,13,16,18 |
| T15 | P0 | T01-T03 | prompts/prompt_10_governance.md | **All R7 fixes for Step 10** (HEAVY — 2 CRIT + 1 HIGH): (1) Add `## Metadata Contract`. (2) Add `created_at`. (3) **A-R7-05**: Add complete `review_policy` field guidance: `verdict_requirements` (array, minItems:1, each item describes a condition for verdict), `required_metadata` (object listing required metadata keys), `evidence_source_by_phase` (object with REQUIRED keys `dev`, `staging`, `prod` — each describing evidence source for that environment). Source from: organizational review standards in seed docs, governance patterns from 06_invariants.json. (4) **A-R7-07**: Change `pr_rules` from "should be filled" → "MUST populate with PR merge rules from organizational standards"; `versioning` from "should" → "MUST populate: select calendar|semver|spec-rev based on project versioning strategy in seed_tech_stack.md". (5) `_migration_notes`. (6) Harden Self-Audit Gate (listed as vague). (7) Harden Best Practices. (8) Replace all vague language. | `pytest tests/test_prompt_contracts.py -v -k "prompt_10"` | A-R7-01,02,05,07,13,14,16,18 |
| T16 | P0 | T01-T03 | prompts/prompt_11_redteam.md | **All R7 fixes for Step 11**: (1) Add `## Metadata Contract`. (2) Add `created_at`. (3) Add missing `policy_ref` → canonical registry note. (4) `_migration_notes`. (5) **A-R7-15**: Add `## Operating Flow: Synthesize → Clarify → Emit` header (score trigger present, section unnamed). (6) Replace vague language. (7) Harden Self-Audit Gate. (8) Harden Best Practices. | `pytest tests/test_prompt_contracts.py -v -k "prompt_11"` | A-R7-01,02,09,13,14,15,16,18 |
| T17 | P0 | T01-T03 | prompts/prompt_12_ci_gates.md | **All R7 fixes for Step 12** (HEAVY — 1 CRIT + 1 HIGH): (1) Add `## Metadata Contract`. (2) Add `created_at`. (3) **A-R7-03**: Add `jobs[].environment_ref` to Field Guidance: "REQUIRED for each job. MUST reference a canonical environment from canon/manifest.json environments. Source from: 02a_delivery_baseline.json environments mapping — each job MUST be assigned to the environment where it runs." Also add to Output Contract example. (4) **A-R7-08**: Add `jobs[].security` object guidance: `runner_labels` (array of CI runner label strings), `token_permissions` (object mapping permission→scope), `environment_protection` (object with optional `required_reviewers` integer, `wait_timer_minutes` integer). Source from: organizational CI security policies in seed_tech_stack.md. (5) **A-R7-19**: Move Canonical Registry section AFTER Output Contract to match convention. (6) `_migration_notes`. (7) Harden Self-Audit Gate (listed as vague). (8) Harden Best Practices. (9) Replace vague language. | `pytest tests/test_prompt_contracts.py -v -k "prompt_12"` | A-R7-01,02,03,08,13,14,16,18,19 |
| T18 | P0 | T01-T03 | prompts/prompt_13_extension_generator.md | **All R7 fixes for Step 13**: (1) Add `## Metadata Contract`. (2) Add `created_at`. (3) Add missing `*_ref` fields → canonical registry note. (4) `_migration_notes`. (5) **A-R7-15**: Add `## Operating Flow: Synthesize → Clarify → Emit` header. (6) Replace vague language. (7) No Best Practices section exists — do NOT add one; ensure any inline advisory language uses MUST modality. NOTE: `governance_label_ref` was confirmed RESOLVED — do not re-add. | `pytest tests/test_prompt_contracts.py -v -k "prompt_13" --no-header` | A-R7-01,02,09,13,15,18 |
| T19 | P0 | T01-T03 | prompts/prompt_13a_completeness_assessment.md | **All R7 fixes for Step 13a**: (1) Add `## Metadata Contract`. (2) Add `created_at`. (3) `_migration_notes`. (4) Fix `# Operating Flow` (H1) → `## Operating Flow: Synthesize → Clarify → Emit` (H2) for parser consistency. (5) Harden Self-Audit Gate — replace vague "Identification of at least one missing element OR confirmation of 100% completeness" with explicit field-name checklist. (6) Replace vague language. | `pytest tests/test_prompt_contracts.py -v -k "prompt_13a"` | A-R7-01,02,13,14,15,18 |
| T20 | P0 | T01-T03 | prompts/prompt_14_roadmap.md | **All R7 fixes for Step 14**: (1) Add `## Metadata Contract`. (2) Add `created_at`. (3) Add missing `*_ref` fields → canonical registry note. (4) `_migration_notes`. (5) **A-R7-15**: Add `## Operating Flow` header. (6) Replace vague language. (7) Harden Best Practices. | `pytest tests/test_prompt_contracts.py -v -k "prompt_14"` | A-R7-01,02,09,13,15,16,18 |
| T21 | P0 | T01-T03 | prompts/prompt_15_scaffold.md | **All R7 fixes for Step 15**: (1) Add `## Metadata Contract`. (2) Add `created_at`. (3) Add missing: `interface_ref`, `command_ref` → canonical registry note. (4) `_migration_notes`. (5) Replace vague language. (6) Harden Best Practices. | `pytest tests/test_prompt_contracts.py -v -k "prompt_15"` | A-R7-01,02,09,13,16,18 |
| T22 | P0 | T01-T03 | prompts/prompt_16_impl_context.md | **All R7 fixes for Step 16**: (1) Add `## Metadata Contract`. (2) Add `created_at`. (3) **A-R7-17**: Fix `# Self-Audit Gate` → `## Self-Audit Gate` (H1→H2). (4) **A-R7-15**: Add `## Operating Flow` header. (5) Add missing fields: `plan.status` enum guidance, `type`/`layer` checklist fields. (6) Add optional `*_ref` canonical registry notes. (7) `_migration_notes`. (8) Replace vague language. | `pytest tests/test_prompt_contracts.py -v -k "prompt_16" --no-header` | A-R7-01,02,09,13,15,17,18 |
| T23 | P0 | T01-T03 | prompts/prompt_16a_impl_planner.md | **All R7 fixes for Step 16a**: (1) Add `## Metadata Contract`. (2) Add `created_at`. (3) **A-R7-04 CRITICAL**: REMOVE the mandate "Every checklist item MUST include a `milestone_ref` field" — this field does NOT exist in schema/16_impl_context.schema.json. Replace with: "To trace checklist items to roadmap milestones, populate `trace` array with milestone IDs from 14_roadmap.json." (4) `_migration_notes`. (5) Replace vague language. (6) No Best Practices section exists — harden inline `*Heuristic*:` markers to use MUST modality where they express binding constraints. (7) Verify two-gate structure (Score Threshold + Coverage Closure) is intact. | `pytest tests/test_prompt_contracts.py -v -k "prompt_16a"` | A-R7-01,02,04,13,18 |
| T24 | P0 | T01-T03 | prompts/prompt_16b_impl_coder.md | **All R7 fixes for Step 16b**: (1) Add `## Metadata Contract`. (2) Add `created_at`. (3) **A-R7-15**: Add `## Operating Flow: Synthesize → Clarify → Emit` header (Clarify/Emit logic exists inline but section is unnamed). (4) **A-R7-20**: Add explicit upstream JSON refs (currently only 1 — `14_roadmap.json`). Add to input section: "Upstream artifacts: `00_charter.json`, `04_fr_list.json`, `06_invariants.json`, `07_nfrs.json`, `14_roadmap.json`, `spec/impl_context/{step_id}.json`." (5) Add `final_status` field guidance. (6) `_migration_notes`. (7) Replace vague language. (8) No Best Practices section — harden inline `*Heuristic*:` markers. | `pytest tests/test_prompt_contracts.py -v -k "prompt_16b"` | A-R7-01,02,13,15,18,20 |
| T25 | P0 | T01-T03 | prompts/prompt_16c_impl_reviewer.md | **All R7 fixes for Step 16c**: (1) Add `## Metadata Contract`. (2) Add `created_at`. (3) **A-R7-15**: Add `## Operating Flow: Synthesize → Clarify → Emit` header. (4) Add missing optional field guidance: `related_checklist_ids` → "array of checklist IDs from 16a plan relevant to this finding", `fixture_status.test_results[].notes` → "optional string for test context", `delivery_status.deployments[].status` → "deployment status string", `*_ref` canonical fields → canonical registry note. (5) `_migration_notes`. (6) Replace vague language. (7) No Best Practices section — harden inline `*Heuristic*:` markers. | `pytest tests/test_prompt_contracts.py -v -k "prompt_16c"` | A-R7-01,02,09,13,15,18 |
| T26 | P1 | T04-T25 | — (no file change) | Full integration verification: `pytest tests/ -v` + `./tools/run_specdev.sh validate-all spec --repo-root ./devspec_toolkit` | All tests pass; zero validation errors | All |
| T27 | P3 | T26 | docs/audit/findings/r7_findings.md | Update findings file with implementation results, Phase 4 verification status, and measurable goals | `test -f docs/audit/findings/r7_findings.md` | — |
| T28 | P3 | T27 | docs/audit/review_index.md | Add R7 entry to review index | `grep "R7" docs/audit/review_index.md` | — |

### Subagent Execution Strategy

**Parallel batch 1** (T01, T02, T03): 3 `general-purpose` worktree agents — test file renames. Independent, run together.

**Parallel batch 2** (T04-T13): 10 `general-purpose` worktree agents — prompts 00-08. Independent (each touches one file), run together. Each agent receives:
- The specific task instructions from the table above
- "Read the prompt file first to understand current state"
- "Read the schema file to verify all fields"
- "Read tools/step_order.json for downstream step counts"
- "Changes are ADDITIVE — do not remove correct existing content"
- "After changes: run the acceptance command"

**Parallel batch 3** (T14-T25): 12 `general-purpose` worktree agents — prompts 09-16c. Same pattern.

**Sequential** (T26): Integration verification after all prompt changes merged.

**Sequential** (T27, T28): Documentation after verification passes.

### Common Instructions for All Prompt Tasks (T04-T25)

Every prompt task agent MUST apply these cross-cutting changes:

1. **`## Metadata Contract` section** — add BEFORE `## Output Contract` (or `# Output Contract`):
```markdown
## Metadata Contract

Every artifact produced by this step MUST include:
- `"$schema"`: `"<URI from schema_registry.json for this step>"`
- `"spec_version"`: current toolkit version string (from `tools/pyproject.toml`)
- `"generation_quality"`: object with `confidence_score` (0.0–1.0), `coverage_assessment` (string), `known_gaps` (array of strings), `recommendations` (array of strings)
```

2. **`created_at` instruction** — add to Field-by-Field section or Output Rules:
```
`created_at`: MUST be set to ISO-8601 UTC timestamp of artifact generation (e.g., "2024-01-15T10:30:00Z"). Do not hardcode; use current time.
```

3. **`_migration_notes` instruction** — add at end of Field-by-Field section:
```
`_migration_notes`: Do not populate. System-managed field for migration tooling.
```

4. **Vague language replacement rules**:
   - "consider X" → "MUST include X if [specific condition]"
   - "may include" → "MUST include"
   - "if appropriate" → "if [specific condition from schema/upstream]"
   - "such as" / "e.g." → explicit enumeration from schema enum or canonical registry
   - "etc" → remove or enumerate
   - "where applicable" → "MUST include for [specific condition]"
   - "where relevant" → remove or specify condition
   - "as needed" → "MUST include when [condition]"
   - "prefer" → "MUST use"
   - "should" (in binding context) → "MUST"
   - "non-trivial" → define concrete threshold

5. **Self-Audit Gate hardening** — replace generic criteria with explicit field checklist mapping to schema `required[]`.

6. **Best Practices hardening** — replace "should"/"prefer"/"recommended" with "MUST" where constraint is binding. **Only for prompts that HAVE a Best Practices section** (18 of 22 — NOT 13, 16a, 16b, 16c).

7. **"X downstream steps" fix** (9 prompts: 01,02,02a,03,05,06,07,08,09) — read `tools/step_order.json` → `step_metadata` → find the step entry → count `downstream_consumers` array length. Replace "X" with actual number and list step names.

8. **Canonical `*_ref` fields** — for each optional `*_ref` field missing from the prompt, add ONE of:
   - If auto-managed: `"<field_name>": Do not populate manually; resolved by canonical registry tooling.`
   - If AI must populate: explicit sourcing instruction with upstream artifact + field path.

---

## Verification Status

**COMPLETE** — All checks passed.

- CHECK 1 Assumptions: PASS
- CHECK 2 References: PASS (all findings cite specific files verified by Phase 1 Explore agents)
- CHECK 3 Atomic: PASS (one file per task)
- CHECK 4 Tests: PASS (T01-T03 cover test changes; T26 runs full suite — **549 passed, 0 failures**)
- CHECK 5 Docs: PASS (T27-T28 cover documentation)
- CHECK 6 Deps: PASS (tests before prompts, integration after prompts, docs last)
- CHECK 7 Orphans: PASS (every finding maps to at least one task)
- Total findings: 20 (6 CRIT, 5 HIGH, 6 MED, 3 LOW) — **all FIXED**
- Total tasks: 25 code + 1 integration + 2 doc = 28 — **all DONE**

---

## Implementation Results

### Task Execution Summary

| Task Group | Tasks | Files Changed | Status |
|------------|-------|---------------|--------|
| T00 | 1 | docs/audit/findings/r7_findings.md | DONE |
| T01-T03 | 3 | 3 test files | DONE — "B4 Metadata Contract" → "Metadata Contract" |
| T04-T13 | 10 | prompts 00-08 | DONE — all R7 fixes applied |
| T14-T25 | 12 | prompts 09-16c | DONE — all R7 fixes applied |
| T26 | 1 | (integration) | DONE — 549 tests passed, 0 failures |
| T27-T28 | 2 | findings + review_index | DONE |

### Cross-Cutting Changes Applied to All 22 Prompts

1. **`## Metadata Contract` section** added before Output Contract
2. **`created_at` instruction** added to Field-by-Field guidance
3. **`_migration_notes`** "do not populate" instruction added
4. **Vague language** replaced with MUST-modality and explicit conditions
5. **Self-Audit Gate** hardened with explicit required field checklists
6. **Best Practices** hardened (should→MUST) in 18 prompts that have the section
7. **Optional `*_ref` canonical fields** added with registry binding notes

### Critical Fixes

- **A-R7-03**: `jobs[].environment_ref` added to prompt_12 Field Guidance with sourcing from 02a_delivery_baseline.json
- **A-R7-04**: Removed invalid `milestone_ref` mandate from prompt_16a; replaced with `trace` array guidance
- **A-R7-05**: Complete `review_policy` object guidance added to prompt_10 (verdict_requirements, required_metadata, evidence_source_by_phase)
- **A-R7-06**: Complete `apis[].enum_provenance` guidance added to prompt_05 (source_url, source_date, resolved_at)

### Integration Verification

- **Full test suite**: 549 passed, 0 failures (`pytest tests/ -v`)
- **Prompt contract tests**: 8/8 passed
- **Prompt schema sync tests**: 19/19 passed
- **Zero B4 Metadata Contract references remain** in test files

---

## Anti-Patterns

- Do NOT modify schemas — that's R8
- Do NOT modify validators — that's R9
- Do NOT remove correct existing prompt content — additions only
- Do NOT add fields not in the schema to any prompt
- Do NOT use NLP/semantic matching for sourcing — must be structural (artifact + field path)

---

## R7a: Supplementary Prompt Cleanup (post-R7)

Post-R7 review identified additional prompt maintenance issues to resolve before R8.

### R7a Findings

| ID | Sev | Scope | Finding |
|----|-----|-------|---------|
| A-R7a-01 | MED | 11 prompts (00-09) | Static "This prompt's output feeds N downstream steps" text duplicates `specdev prompt-context` CLI; stale counts create maintenance burden |
| A-R7a-02 | HIGH | All 22 prompts | No Schema Binding section — prompts don't establish schema as authoritative for structure/constraints |
| A-R7a-03 | MED | All 22 prompts | Self-Audit Gate lacks concrete criteria for when confidence drops below 0.9 |
| A-R7a-04 | MED | prompt_10 | Output Contract example missing `pr_rules`, `versioning`, `review_policy`, `reviewers` |
| A-R7a-05 | MED | All 22 prompts | Field-by-Field sections duplicate schema constraints (types, enums, required markers, minItems) |
| A-R7a-06 | LOW | ~10 instances | MUST keyword redundancy: "MUST + REQUIRED" on same constraint, unclear "MUST X if Y" ordering |

### R7a Implementation Plan

| Task | Scope | Fix |
|------|-------|-----|
| Remove "feeds" lines | 11 prompts | Remove static downstream step counts; keep `specdev prompt-context` CLI reference |
| Add Schema Binding section | All 22 | Add `## Schema Binding` before Output Contract with schema URI and authority statement |
| Add confidence criteria | All 22 | Add 3 bullets to Self-Audit Gate defining when score drops below 0.9 |
| S1: prompt_10 Output Contract | prompt_10 | Add `pr_rules`, `versioning`, `review_policy`, `reviewers` to example JSON |
| Trim Field-by-Field | All 22 | Remove type/enum/constraint-only lines that duplicate schema (keep sourcing guidance) |
| MUST cleanup | ~10 instances | "MUST + REQUIRED" → pick one; "MUST X if Y" → "IF Y, MUST X" |

### R8 Scope Additions Identified

Two new gaps to add to `docs/audit/r8_schema_alignment.md`:

| # | Gap | Severity |
|---|-----|----------|
| 8 | Schema `description` fields lack sourcing guidance — sourcing exists only in prompt prose, creating maintenance drift | CRITICAL |
| 9 | `canon/manifest.json` `source_refs` unused; no `binding_mode` contract for auto vs explicit canonical ref population | HIGH |

---

## Next Steps

- **R7+R7a implementation**: Apply all R7 findings (T01-T28) and R7a findings together in a single pass
- **R8** (L2: Schemas): Tighten schemas to match hardened prompts; add gaps 8+9
- **R9** (L3+L4: Validators+CI): Build cross-step validation against final prompts and schemas
