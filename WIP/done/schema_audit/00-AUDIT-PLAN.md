# Schema Audit Plan

**Date**: 2026-03-19
**Scope**: `schema/`, `canon/`, `tools/schema_registry.json`, `tools/step_order.json`, `spec/common/seed_manifest.json`
**Branch**: `codex/canonical-drift-review-plan`
**Baseline**: `WIP/schema_audit/p0-baseline.md`

---

## Phase Architecture

```
P0: Baseline Capture (COMPLETE — p0-baseline.md)
  ↓
P1 (Parallel): 6 Deep Review Agents (single container each)
  ↓
P3: Consolidation + Deduplication
  ↓
P4: Fix Plan (dependency-ordered batches)
  ↓
P5–P7: Execution → Verification → Follow-up
```

---

## P0 Baseline Summary

| Metric | Value |
|---|---|
| Schema files | 26 (24 in schema/ + 2 in canon/) |
| Total LOC | 6,072 (6,015 schema/ + 57 canon/) |
| Core definitions | 44 (6 atoms + 28 collections + 1 error + 9 canon) |
| $ref usage | 448 total, 100% core adoption |
| Description coverage | **6.1%** (56/919 properties) |
| Unique enum definitions | ~61 (approximate — P1-A to recount) |
| Duplicate properties (diff structures) | 30+ |
| Web-service term occurrences | 39 |
| Largest schema | 16_impl_context (1,868 LOC, 31.1%) |

---

## P1 Agent Scopes (6 Agents, Single Container)

Each agent runs once in a single container. P3 consolidates findings across agents.

### P1-A: DRY & Reusability

**User points**: #1 (enums in common dictionary), #5 (seed_refs/spec_refs_ingested needed?), #6 (canonical refs bloat)

**Exclusive scope**:
- Enum consolidation: ~61 enum definitions across schemas (approximate — recount using recursive traversal including `allOf/if` branches). Which should be centralized in core/?
- The 10 common required fields repeated in all 19 step schemas — can this be a shared base schema?
- `status` (13 variants), `severity` (9 variants), `type` (11 variants) — which can be unified?
- `method` enum inconsistency: 05 has 5 HTTP verbs, 15 has 7 — which is canonical?
- `protocol` enum inconsistency: 02 has 6 values, 05 has 4
- `seed_refs` and `spec_refs_ingested` — are they needed in every schema? Do they serve the traceability pipeline?
  - **Key asymmetry**: `seed_refs` IS actively validated by `seed_lint.py` (hash verification, required seed checks, unknown seed detection — 11+ hits in tool code). `spec_refs_ingested` has **ZERO tool code consumers** — `grep -r "spec_refs_ingested" tools/specdev_tools/` returns nothing. Confirm this and flag as dead schema if verified.
- Canonical triad (`canonical_refs_used`, `canonical_proposals`, `canonical_conflicts`) — architectural assessment: is it over-engineered? Could it be simplified? (P1-C owns the "is it consumed?" question; P1-A owns "can the architecture be simplified?")
- Inline patterns duplicating $ref-able definitions (e.g., fr_id in step 16 inlines the pattern instead of $ref)
- **Drift-sensitive fields check**: Before proposing removal of any field, check `tools/specdev_tools/generation/prompt_schema_sync.py` `DRIFT_SENSITIVE_FIELDS` tuple — removing a drift-sensitive field will break prompt-schema sync validation. Current drift-sensitive fields: `dependencies`, `trace`, `generation_quality`, `canonical_refs_used`, `canonical_proposals`, `canonical_conflicts`.

**Questions**:
1. List every enum that appears in 2+ schemas with different values. Propose unified core enums.
2. Which inline property definitions could be extracted to core/atoms or core/collections?
3. Is the common 10-field boilerplate better served by JSON Schema `allOf` composition with a base schema?
4. Do `seed_refs` and `spec_refs_ingested` serve a real validation purpose or are they just audit metadata? (Note: `spec_refs_ingested` appears to have zero tool consumers — verify and confirm.)
5. Is the canonical triad (refs_used + proposals + conflicts) architecturally sound, or can it be simplified? (Consumer analysis is P1-C's scope.)
6. For any field proposed for removal, does it appear in `prompt_schema_sync.py` `DRIFT_SENSITIVE_FIELDS`? What is the downstream impact?
7. If proposing an `allOf` base schema for common fields, verify that no validator relies on schema-level field enumeration (as opposed to data-level field access). Key consumers: `spec_quality_lint.py`, `canonical/integrity.py`, `canonical/autofix.py`, `seed_lint.py`.

**Output**: `p1-out-dry.md`

---

### P1-B: Descriptions & LLM Context

**User point**: #2 (mandatory descriptions for every field)

**Exclusive scope**:
- 863 properties missing descriptions (93.9% gap)
- Inventory every property in every schema that lacks a `"description"` field
- Group by schema file with exact property paths
- Assess: which properties are self-evident (e.g., `id`, `owner`) vs. which absolutely need descriptions for LLM context?
- Review existing 56 descriptions for quality — are they helpful or boilerplate?
- Check core/ definitions — do atoms, collections, canon, errors have descriptions on their anchors?

**Questions**:
1. Produce a complete inventory: file → property_path → has_description (true/false)
2. For properties without descriptions, draft a one-line description for each
3. Which properties are ambiguous without a description? Rank by LLM confusion risk.
4. Should descriptions live at the $ref target (core/) or at the $ref usage site (step schema)?
5. Are there properties where the name alone is sufficient and a description would be noise?

**Output**: `p1-out-descriptions.md`

---

### P1-C: Bloat & Over-Engineering

**User points**: #3 (generation_quality needed?), #4 (seed_manifest.json, docs_policy, step_order.json optimization)

**Exclusive scope**:
- `generation_quality`: Required in all 19 step schemas. Only has `assumptions` (string array). **Baseline fact**: it IS actively consumed — `spec_quality_lint.py` checks its presence in all spec files, and `prompt_schema_sync.py` lists it as a `DRIFT_SENSITIVE_FIELD` (schema-prompt drift is flagged if it changes). A migration script (`strip_generation_quality.py`) also exists. The question is NOT "is it dead?" but rather: **does a field containing only `assumptions: []` justify mandatory status in every step schema?**
- `spec_refs_ingested`: Required in all 19 step schemas. **Baseline fact**: `grep -r "spec_refs_ingested" tools/specdev_tools/` returns ZERO results. No tool code reads this field. It only appears in test fixtures as empty arrays. `spec_quality_lint.py` checks 8 of 10 common required fields but deliberately SKIPS `spec_refs_ingested` (and `coverage_gaps`). **Investigate and confirm this is dead schema.**
- `coverage_gaps` (primary ownership — P1-A defers to P1-C): Required in all 19 step schemas. **Baseline fact**: ONLY `tools/specdev_tools/validation/validators/step_12.py` reads `coverage_gaps` (to validate `upstream_item_id` references). No other validator, linter, or generator reads it. `spec_quality_lint.py` skips it in its common required field checks (checks 8/10 fields, omitting `spec_refs_ingested` and `coverage_gaps`). **Is one step-specific consumer enough to justify mandatory presence in all 19 schemas?**
- `seed_manifest.json` at `spec/common/`:
  - `docs_policy` field — **Baseline fact**: IS consumed by TWO validators: (1) `docs_lint.py` reads `readme_required`, `root_readme_required`, `readme_depth_default`, `readme_depth_by_scope`, `scope`, `exclusions`; (2) `validators/step_16.py` reads `docs_policy.doc_paths` to validate docs_impact paths. The question is whether `docs_policy` belongs in seed_manifest vs. step_order.json, NOT whether it is dead.
  - `nested_order` — **Baseline fact**: IS consumed by `seed_lint.py` (lines 263-266: iterates `nested_order` layers to validate that referenced `seed_ids` exist in the seed registry). It is NOT dead. The question is whether its structure/location is optimal, not whether it is dead.
  - Can seed_manifest be absorbed into step_order.json?
- `step_order.json`:
  - `allowed_upstream_dependencies` — **Baseline fact**: IS actively consumed by 5 tool modules (`dependency_order_lint.py`, `dag_lint.py`, `extraction_intent_check.py`, `hallucination_lint.py`, `cli.py`). It is NOT dead. The question is whether it is redundant with `downstream_consumers`.
  - `coverage_thresholds` — **Baseline fact**: IS consumed by 2 modules (`matrix.py`, `cli.py`). It IS enforced. The question is whether its location in step_order.json is optimal.
  - `status_write_exemptions` — **Baseline fact**: IS consumed by 1 module (`forward_replay_check.py`). It IS enforced.
- Is the canonical triad genuinely needed in every step or could it be optional? (Consumer analysis — P1-A owns the architectural simplification question.)

**Questions**:
1. For each field under review, trace: which Python module reads it? Which validator checks it? What happens if it's removed?
2. Can seed_manifest be merged into step_order.json? What would the combined schema look like?
3. Given that `generation_quality` IS consumed by quality lint and prompt_schema_sync drift detection, does the field's minimal VALUE (`assumptions: []`) justify its mandatory status?
4. Which fields in step_order.json are actually consumed vs. dead config?
5. For any field proposed for removal, check if it appears in any `prompts/prompt_NN_*.md` file — prompt references must be updated alongside schema changes.
6. `spec_quality_lint.py` checks 8 of 10 common required fields (skips `spec_refs_ingested` and `coverage_gaps`). Is this an intentional signal that those two fields were known to be less important, or a bug in the linter?

**Output**: `p1-out-bloat.md`

---

### P1-D: Genericity & Domain Bias

**User point**: #7 (web-service bias vs. generic software)

**Exclusive scope**:
- 39 web-service term occurrences across schemas
- Step 05 (interface_contracts) — hardcodes HTTP method enum, protocol enum, parameter locations (query/path/header)
- Step 15 (scaffold) — `route_map` with HTTP methods, `api_ref`, service_skeleton
- Step 02 (system_sketch) — protocol includes "http", "grpc" but also "event", "rpc", "db", "file"
- Step 12 (ci_gates) — `token_permissions` is GitHub Actions-specific
- Step 16 (impl_context) — `implemented_endpoints`, drift check targets
- Step 02a (delivery_baseline) — uses `$ref` to `core/collections#environmentName` which hardcodes `[dev, ci, staging, prod]` (the enum is in core, not inline in 02a)

**Questions**:
1. Which schemas would break for a CLI tool, a desktop app, a mobile app, an embedded system, a data pipeline, or a library/SDK?
2. Can Step 05 be generalized from "API contracts" to "interface contracts" (covering CLI interfaces, event schemas, file formats)?
3. Can Step 15 be generalized from "scaffold" (service + routes) to "project skeleton" (any software structure)?
4. Should protocol/method/environment enums be extensible (via canonical registry) rather than hardcoded?
5. Is the `route_map` concept inherently web-specific, or can it be abstracted?
6. Which schemas are already generic enough for any project type?

**Output**: `p1-out-genericity.md`

---

### P1-E: Structure & Registry

**User points**: #8 (schema subfolder organization), #9 (registry completeness + location)

**Exclusive scope**:
- Current structure: `schema/` (20 flat files) + `schema/core/` (4 files) + `canon/` (2 files outside schema/)
- Should step schemas be grouped into subfolders by phase? (e.g., `schema/discovery/`, `schema/impl/`, `schema/governance/`)
- 2 canon schemas (`canon/kind.schema.json`, `canon/aliases.schema.json`) live outside `schema/` — should they move to `schema/canon/`? Note: `canon/` also contains data files (`aliases.json`, `manifest.json`, `kinds/` subdirectory). Consider whether schema-data co-location is intentional design or accidental when proposing moves.
- `schema_registry.json` lives in `tools/` — should it live in `schema/` alongside the schemas it indexes?
- Registry completeness: 29 entries. Are all 26 schema files registered? Are there orphan entries? (29 entries map to 26 unique files — 16a, 16b, 16c are aliases to 16.)
- URI scheme: `https://specdev.local/schema/` — is this the right pattern? (See ALIGN-2 in research roadmap)
- Steps 16a, 16b, 16c all point to same file — is this correct or should they have distinct schemas?
- `seed_manifest.schema.json` is in `schema/` but the actual manifest is in `spec/common/` — is this confusing?
- **Note**: Spec data files under `spec/` include `$schema` properties pointing to schema URIs (e.g., `spec/common/seed_manifest.json` has `"$schema": "https://specdev.local/schema/seed_manifest.schema.json"`). Any schema URI changes (ALIGN-2) or schema file moves require updating these `$schema` references in all data files.

**Questions**:
1. Propose a subfolder structure for schema/ that groups related schemas logically
2. Should canon schemas move under schema/? What are the implications for existing $ref paths? Account for data files (`aliases.json`, `manifest.json`, `kinds/`) that also live in `canon/`.
3. Where should schema_registry.json live and why?
4. Are all schemas registered? Are there dangling registry entries?
5. Should 16a/16b/16c have their own schemas or is reusing 16 correct?
6. `tools/step_order.json` lacks a JSON schema to validate its own structure — should one be created? (Especially relevant if seed_manifest fields are absorbed into it.)
7. Validate that `spec/common/seed_manifest.json` conforms to `schema/seed_manifest.schema.json`. Does the schema accurately reflect the real data structure?

**Output**: `p1-out-structure.md`

---

### P1-F: Research Alignment

**User point**: #10 (align with research-alignment-roadmap.md)

**Exclusive scope**:
- Read `WIP/future/research-alignment-roadmap.md` completely
- Assess current schema state against each ALIGN-N gap:
  - ALIGN-1: $ref/$defs DRY authoring — how much inline duplication remains?
  - ALIGN-2: URN-based $id — current URL-based scheme risks
  - ALIGN-4: additionalProperties: false — verify 100% coverage claim
  - ALIGN-5: Max 3-level nesting — measure actual nesting depths per schema
  - ALIGN-6: 100% property descriptions — confirmed 6.1% by P0
  - ALIGN-10: src/dist schema split — current state assessment
  - ALIGN-3 (structured errors), ALIGN-7 (--json output), ALIGN-8 (MCP tool), ALIGN-9 (pre-commit hooks): These are tool/CLI-focused and not directly schema-related. Acknowledge their existence but mark as **out-of-scope for this schema audit**.
- Cross-reference with P0 baseline findings
- Identify any NEW research gaps not in the roadmap

**Questions**:
1. For each ALIGN-N, what is the current state vs. target state?
2. Which ALIGN-N items are now partially resolved by the tools/tests audit?
3. Are there schema-specific gaps not captured in the research roadmap?
4. What is the recommended priority order for schema-specific fixes?
5. Verify: does every schema have `additionalProperties: false` at all object levels? If yes, note that there is no CI lint to prevent regression — recommend one.
6. For description counting (ALIGN-6): count every `properties` key at every nesting level. A property has a description if it contains a `description` key directly or if its `$ref` target has one. Do `$defs` properties count? Document the methodology used.

**Output**: `p1-out-research.md`

---

## P1 Agent Protocol

### Output format (per agent)

```markdown
# P1-{X}: {Title} — Findings

## Summary
- Total findings: N
- Critical: N | High: N | Medium: N | Low: N | Info: N

## Findings

### FINDING-{NNN}: {Title}
- **Severity**: CRITICAL | HIGH | MEDIUM | LOW | INFO
- **Category**: DRY | DESCRIPTION | BLOAT | GENERICITY | STRUCTURE | RESEARCH
- **Location**: {file}:{line} or {file}:{property_path}
- **Description**: {what is wrong}
- **Evidence**: {concrete example from the schema}
- **Recommendation**: {specific fix}
```

### Severity Criteria

| Severity | Criteria |
|---|---|
| CRITICAL | Breaks validation, data loss, security issue, blocks LLM usage |
| HIGH | >50 LOC total duplication (sum of all occurrences of a single duplicated pattern), missing critical descriptions, architectural concern |
| MEDIUM | Moderate DRY violation, partial description gaps, inconsistency |
| LOW | Style issues, naming, minor inconsistency |
| INFO | Observations, future considerations |

### Constraints
- Each agent operates ONLY within its exclusive scope
- No code changes — read-only analysis
- Cite exact file paths and line numbers
- Use current branch state for all code tracing — do not assume historical validator signatures (P5 audit may have changed them via SpecError migration)
- Use P0 baseline numbers as ground truth (but count items in tables rather than trusting header summaries — headers were corrected in rev 1 but tables are the authoritative source)

---

## P3 Consolidation Rules

1. **Cross-agent reconciliation**:
   - Multiple agents report same finding → **corroborated** (keep most detailed version, cross-reference others)
   - Single agent finds it → **verified genuine** (valid if evidenced)
   - Severity disagreement across agents → resolve to higher unless lower has justification

2. **Deduplication across agents**: If P1-A and P1-C both find the same issue (e.g., canonical triad), keep in the primary agent's scope (per ownership assignments in P1 scopes) and cross-reference from the other agent.

3. **Output**: `p3-out-master-findings.md` with AUDIT-NNN IDs, grouped by severity then by target file.

---

## P4 Fix Plan Rules

- **One task = one file** (exception: moving files requires source + destination)
- **Batch ordering**: Foundation (new core definitions) → Consumer updates → Structure moves → Description additions → Registry updates
- **Test gate**: `pytest tests/ -x --tb=short` after each batch
- **Gate protocol**: On failure, revert specific file, identify root cause, defer task

---

## Timeline Estimate

| Phase | Work |
|---|---|
| P0 | COMPLETE (re-verify if P5 batches 4-5 modify schemas) |
| P1 | 6 agents × 1 container = 6 agent runs |
| P3 | 1 consolidation agent |
| P4 | 1 fix plan agent |
| P5 | Batch execution (estimated 5-7 batches) |
| P6 | Verification pass |
| P7 | Follow-up items |

---

## Revision Log

**Rev 1** (2026-03-19) — Fixes from `p0-plan-review.md` (26 findings)

| Finding ID | Fix Applied |
|---|---|
| BUG-001 | Baseline: atoms count 5 → 6 |
| BUG-002 | Baseline: collections count 22 → 28 |
| BUG-003 | Baseline + Plan: total core definitions 37 → 44 |
| BUG-004 | Plan: clarified Total LOC as "(6,015 schema/ + 59 canon/)" |
| BUG-005 | Baseline: generation_quality "20 step schemas" → "19 step schemas" |
| GAP-001 | Plan P1-A: added explicit note that `spec_refs_ingested` has ZERO tool consumers |
| GAP-002 | Plan P1-C: added baseline fact that `coverage_gaps` only consumed by step_12.py |
| GAP-003 | Plan P1-C: added note that spec_quality_lint checks 8/10 common fields, skips `spec_refs_ingested` and `coverage_gaps` |
| GAP-004 | Plan P1-C: reframed `generation_quality` from "is it dead?" to "does its minimal value justify mandatory status?" — noted active consumption by spec_quality_lint and prompt_schema_sync |
| GAP-005 | Plan P1-A: added drift-sensitive fields check requirement; agents must consult prompt_schema_sync.py before proposing removals |
| GAP-006 | Plan P1-E: added note about canon/ data files (aliases.json, manifest.json, kinds/) that must be considered alongside schema moves |
| GAP-007 | Plan P1-C: added baseline facts about docs_policy consumption by docs_lint.py and step_16 validator |
| ASSUM-001 | Baseline: qualified "100% core adoption" with note about step 16's 7 local $defs extraction candidates |
| ASSUM-002 | Plan P1-F: added instruction to recommend CI lint for additionalProperties regression prevention |
| ASSUM-003 | Plan P1-F: added description counting methodology instructions |
| MISS-001 | Plan P1-A: added question 7 requiring allOf compatibility check against existing validators |
| MISS-002 | Plan P1-C: added question 5 requiring prompt file cross-reference for proposed field removals |
| MISS-003 | Plan P1-E: added question 6 about whether step_order.json should have its own schema |
| MISS-004 | Plan P1-E: added question 7 to validate seed_manifest.json against its schema |
| AMBIG-001 | Plan: dropped dual-container protocol entirely — single container per agent (6 runs, not 12). Removed all A/B output file references. Updated P3 reconciliation rules. |
| AMBIG-002 | Plan: clarified HIGH severity ">50 LOC" as "sum of all occurrences of a single duplicated pattern" |
| AMBIG-003 | Plan: assigned primary ownership — `coverage_gaps` consumer analysis to P1-C, canonical triad architecture to P1-A. Removed duplicate coverage_gaps question from P1-A. |
| HALLUC-001 | Addressed via BUG-001/002/003. Added constraint note: "count items in tables rather than trusting header summaries." |
| REG-001 | Plan: P0 row notes "re-verify if P5 batches 4-5 modify schemas" |
| REG-002 | Plan: P1 agent constraint updated to note agents should use current branch state for validator signatures |

**Rev 2** (2026-03-19) — Fixes from `p0-plan-review-r2.md` (13 findings: 1 HIGH, 6 MEDIUM, 6 LOW)

| Finding ID | Fix Applied |
|---|---|
| BUG-001 (HIGH) | Baseline + Plan: $ref total 468 → 448 (header matched to table sum) |
| BUG-002 | Baseline + Plan P1-E: schema registry entries 31 → 29 |
| BUG-003 | Baseline + Plan: enum count 61 → ~61 (approximate; added caveat for P1-A to recount including allOf/if branches) |
| BUG-004 | Baseline: downstream_consumers counts — Step 04: 14→13, Step 08: 10→9 |
| BUG-005 | Baseline sections 7+8: seed_refs/spec_refs_ingested "19 step schemas + 16_impl_context = 20" → "19 step schemas (00 through 16, including 02a and 13a)" |
| IFIX-001 | Baseline + Plan: canon LOC 59→57, total LOC 6,074→6,072 |
| GAP-001 | Plan P1-F: added ALIGN-3, ALIGN-7, ALIGN-8, ALIGN-9 acknowledgment as out-of-scope for schema audit |
| GAP-002 | Plan P1-C: added baseline fact that `nested_order` IS consumed by `seed_lint.py` (not dead) |
| GAP-003 | Plan P1-C: added baseline facts for `allowed_upstream_dependencies` (5 consumers), `coverage_thresholds` (2 consumers), `status_write_exemptions` (1 consumer) — all actively consumed |
| GAP-004 | Plan P1-E: added note about `$schema` properties in spec data files requiring update if URIs change |
| ASSUM-001 | Baseline section 5: added caveat that description coverage counts are approximate and methodology-dependent |
| AMBIG-001 | Addressed via BUG-002 (registry entries 31→29 in P1-E scope) |
| MISS-001 | Addressed via GAP-003 (step_order.json field consumer baseline facts added to P1-C) |

**Rev 3** (2026-03-19) — Fixes from `p0-plan-review-r3.md` (4 findings: 1 MEDIUM, 3 LOW)

| Finding ID | Fix Applied |
|---|---|
| BUG-001 (MEDIUM) | Baseline section 2: step schemas LOC subtotal 4,090 → 4,936 (matched to sum of per-file values in section 1; overall total 6,015 was already correct) |
| BUG-002 | Baseline section 14: step 16 enum header "30 enum definitions" → "~27 enum definitions" |
| BUG-003 | Baseline section 14 caveat: expanded from step 16-only to mention both step 02 and step 16 have 2 additional allOf/if enums not in tables (with specific property paths) |
| GAP-001 | Plan P1-D: clarified step 02a "hardcoded environments" → uses `$ref` to `core/collections#environmentName` (enum is in core, not inline in 02a) |
