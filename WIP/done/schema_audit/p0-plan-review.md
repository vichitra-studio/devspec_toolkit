# P0 Plan Review: Schema Audit

**Date**: 2026-03-19
**Reviewer**: Claude Opus 4.6 (automated cross-reference review)
**Scope**: Audit plan (`00-AUDIT-PLAN.md`), baseline (`p0-baseline.md`), research roadmap, actual codebase

---

## BUGS

### BUG-001: Baseline atoms count is wrong (says 5, actual 6)
- **Severity**: HIGH
- **Details**: The baseline header in section 3 states "core/atoms.schema.json (56 LOC, **5 definitions**)" but the table immediately below lists 6 definitions (metadata, kebabId, timestamp, owner, tag, screamingSnakeId). The audit plan summary also repeats this error: "37 (5 atoms + 22 collections + 1 error + 9 canon)".
- **Evidence**: `python3 -c "import json; d=json.load(open('schema/core/atoms.schema.json')); print(len(d['$defs']))"` returns `6`.
- **Recommendation**: Fix baseline to "6 definitions". Fix total from 37 to 44 (6+28+1+9). Agents relying on baseline counts will otherwise mis-report.

### BUG-002: Baseline collections count is wrong (says 22, actual 28)
- **Severity**: HIGH
- **Details**: The baseline header says "core/collections.schema.json (521 LOC, **22 definitions**)" but the actual file has 28 `$defs` and the baseline table itself lists all 28 of them. The table and the header contradict each other.
- **Evidence**: `python3 -c "import json; d=json.load(open('schema/core/collections.schema.json')); print(len(d['$defs']))"` returns `28`.
- **Recommendation**: Fix header to "28 definitions". This also corrects the total core definitions from 37 to 44.

### BUG-003: Baseline total core definitions is wrong (says 37, actual 44)
- **Severity**: HIGH
- **Details**: Cascading from BUG-001 and BUG-002, the baseline and audit plan both cite "37 core definitions". Actual: 6 atoms + 28 collections + 1 error + 9 canon = 44.
- **Evidence**: Sum of verified counts from BUG-001 and BUG-002.
- **Recommendation**: Update all references to "37" with "44" in both baseline and audit plan.

### BUG-004: Audit plan summary inconsistency on LOC
- **Severity**: LOW
- **Details**: Audit plan summary table says "Total LOC: 6,074" (schema/ + canon/). Baseline section 2 says "Total: 6,015" for schema/ alone and section 17 says "6,015 (schema/) + 59 (canon/) = 6,074". These are consistent in the end, but the plan summary could mislead P1 agents who may think 6,074 is schema-only.
- **Evidence**: Audit plan line 31: "Total LOC | 6,074". Baseline line 55: schema/ alone is 6,015.
- **Recommendation**: Audit plan summary should clarify "(6,015 schema/ + 59 canon/)".

### BUG-005: Baseline says generation_quality is "present in 20 step schemas" then lists 19
- **Severity**: MEDIUM
- **Details**: Baseline section 6 opens with "Present in **20** step schemas: ALL step schemas (00 through 16)" but the table lists exactly 19 rows (00 through 16, including 02a and 13a). seed_manifest is explicitly noted as "Not in". The text says "20" but then says "All 19 step schemas" at the end. The "20" appears to be a typo.
- **Evidence**: Baseline line 235: "All 19 step schemas use identical $ref". Baseline line 233: "Present in 20 step schemas". Only 19 step schemas exist (00, 01, 02, 02a, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 13a, 14, 15, 16). Verified: `grep -l "generation_quality" schema/*.schema.json | wc -l` = 19.
- **Recommendation**: Fix to "19 step schemas".

---

## GAPS

### GAP-001: spec_refs_ingested is completely dead code -- no validator reads it
- **Severity**: CRITICAL
- **Details**: User point #5 asks whether `seed_refs` and `spec_refs_ingested` are needed. The audit plan (P1-A) correctly asks if they "serve a real validation purpose" but does not highlight the critical asymmetry: `seed_refs` IS actively validated by `seed_lint.py` (hash verification, required seed checks, unknown seed detection), while `spec_refs_ingested` is **never read by any tool code at all**. Zero grep hits in `tools/specdev_tools/`. It only appears in test fixture data as empty arrays. The plan treats them as a pair but they have completely different validation status.
- **Evidence**: `grep -r "spec_refs_ingested" tools/specdev_tools/` returns zero results. `grep -r "seed_refs" tools/specdev_tools/` returns 11+ hits across seed_lint.py, matrix.py, and spec_quality_lint.py.
- **Recommendation**: P1-A agents must be explicitly told: "seed_refs is actively validated; spec_refs_ingested has zero tool code consumers -- confirm this and flag as dead schema." Without this, agents may incorrectly assume both have similar usage.

### GAP-002: coverage_gaps is barely used -- only step_12 validator reads it
- **Severity**: HIGH
- **Details**: `coverage_gaps` is required in all 19 step schemas and the audit plan (P1-A, P1-C) asks "Is coverage_gaps validated or consumed by any tool?" but does not provide the baseline answer. The actual answer is: ONLY `tools/specdev_tools/validation/validators/step_12.py` reads `coverage_gaps` (to validate upstream_item_id references). No other validator, linter, or generator reads it. The spec_quality_lint.py does NOT include `coverage_gaps` in its common required field checks (only 8 of 10 fields are checked). This is a critical data point P1 agents need.
- **Evidence**: `grep -r "coverage_gaps" tools/specdev_tools/` returns only 3 hits, all in `validators/step_12.py`. spec_quality_lint.py checks 8 fields (id, owner, created_at, seed_refs, generation_quality, canonical_refs_used, canonical_proposals, canonical_conflicts) -- it skips both `spec_refs_ingested` and `coverage_gaps`.
- **Recommendation**: Explicitly tell P1-C agents that `coverage_gaps` is only consumed by one step-specific validator and is NOT part of the quality lint common field check.

### GAP-003: spec_quality_lint checks 8 of 10 common required fields
- **Severity**: HIGH
- **Details**: The baseline (section 15) identifies 10 common required fields. The spec_quality_lint.py `_check_required_top_level()` only validates 8 of them, omitting `spec_refs_ingested` and `coverage_gaps`. This is either a bug in the linter or evidence that those two fields were known to be less important. Neither the plan nor baseline flags this discrepancy.
- **Evidence**: `tools/specdev_tools/validation/spec_quality_lint.py` lines 175-184 check: id, owner, created_at, seed_refs, generation_quality, canonical_refs_used, canonical_proposals, canonical_conflicts. Missing: spec_refs_ingested, coverage_gaps.
- **Recommendation**: Add this as a finding P1-C should surface. It is evidence supporting removal/optionality of those two fields.

### GAP-004: generation_quality IS used -- plan understates its usage
- **Severity**: MEDIUM
- **Details**: The audit plan (P1-C) frames generation_quality as potentially "cargo cult" and asks "Is this used by any validator? Does any tool read it?" The answer is YES: (1) spec_quality_lint.py checks its presence in all spec files, (2) prompt_schema_sync.py lists it as a DRIFT_SENSITIVE_FIELD meaning schema-prompt drift is flagged if it changes, (3) a migration script exists (`strip_generation_quality.py`) showing it was previously more complex. The plan should instruct P1-C to weigh these actual usages rather than assume it is unused.
- **Evidence**: `tools/specdev_tools/generation/prompt_schema_sync.py` line 27: `DRIFT_SENSITIVE_FIELDS` includes `"generation_quality"`. `tools/specdev_tools/validation/spec_quality_lint.py` line 180 checks for its presence. `tools/specdev_tools/migration/scripts/strip_generation_quality.py` exists.
- **Recommendation**: P1-C agents should be told: "generation_quality is actively checked by spec_quality_lint and prompt_schema_sync. The question is whether the field's VALUE (just `assumptions: []`) justifies its mandatory status, not whether it is consumed."

### GAP-005: No agent scope covers the prompt_schema_sync drift-sensitive fields
- **Severity**: MEDIUM
- **Details**: `prompt_schema_sync.py` defines `DRIFT_SENSITIVE_FIELDS = ("dependencies", "trace", "generation_quality", "canonical_refs_used", "canonical_proposals", "canonical_conflicts")`. This is a critical piece of the architecture: it means changes to these schema fields trigger prompt-schema drift errors. No P1 agent scope explicitly covers analyzing prompt_schema_sync and its implications for which fields can safely be removed.
- **Evidence**: `tools/specdev_tools/generation/prompt_schema_sync.py` lines 24-31.
- **Recommendation**: P1-A or P1-C should be instructed to check prompt_schema_sync.py for any field they consider removing, to understand the downstream impact on prompt-schema sync validation.

### GAP-006: No P1 agent scope covers the canon/ directory structure adequately
- **Severity**: MEDIUM
- **Details**: The `canon/` directory contains not just 2 schema files but also `aliases.json`, `manifest.json`, and a `kinds/` subdirectory. The baseline (section 17) mentions only the 2 schema files. The audit plan (P1-E) asks whether canon schemas should move to `schema/canon/` but does not account for the data files (`aliases.json`, `manifest.json`, `kinds/`) that also live in `canon/`. Moving schemas alone without considering data file co-location could be problematic.
- **Evidence**: `ls canon/` returns: `aliases.json  aliases.schema.json  kind.schema.json  kinds  manifest.json`.
- **Recommendation**: P1-E should inventory the full `canon/` directory contents (data + schema) and consider whether the separation of schema and data files is intentional design vs. accidental.

### GAP-007: User point #4 on docs_policy is partially addressed but lacks depth
- **Severity**: MEDIUM
- **Details**: User asks "docs_policy -- does it solve any purpose?" P1-C covers this but the plan does not capture that docs_policy IS actively used by TWO validators: (1) `docs_lint.py` reads `readme_required`, `root_readme_required`, `readme_depth_default`, `readme_depth_by_scope`, `scope`, `exclusions` from it; (2) `validators/step_16.py` reads `docs_policy.doc_paths` to validate docs_impact paths. The agents need this baseline data.
- **Evidence**: `tools/specdev_tools/validation/docs_lint.py` lines 46-52. `tools/specdev_tools/validation/validators/step_16.py` lines 180-183.
- **Recommendation**: P1-C scope should explicitly note: "docs_policy IS consumed by docs_lint.py and step_16 validator -- the question is whether it belongs in seed_manifest vs. step_order.json, not whether it is dead."

---

## ASSUMPTIONS

### ASSUM-001: "100% core adoption" claim needs qualification
- **Severity**: MEDIUM
- **Details**: Baseline section 4 claims "100% core adoption" for $ref usage. This is true in the sense that every step schema has at least one `$ref` to core/. But it obscures the fact that step 16 has 7 local `$defs` references that COULD potentially be extracted to core/ (specRef, evidenceObject, executionStatus, severityLevel). The "100%" metric could mislead P1-A agents into thinking DRY is already maxed out.
- **Evidence**: Baseline section 4 notes 16_impl_context has "7 local (#) refs" but the summary says "100% core/ adoption".
- **Recommendation**: Qualify: "100% of step schemas reference core/, but step 16 has 7 local $defs that are candidates for core/ extraction."

### ASSUM-002: ALIGN-4 (additionalProperties: false) "ACHIEVED" claim is correct but fragile
- **Severity**: LOW
- **Details**: The research roadmap claims ALIGN-4 is "ACHIEVED" and the baseline does not verify this. Automated verification confirms: no schema object with `properties` is missing `additionalProperties: false`. However, there is no CI lint to enforce this for future schema changes.
- **Evidence**: Script scan of all schema files found zero objects with `properties` but no `additionalProperties`.
- **Recommendation**: P1-F should note this is correct today but should recommend a CI lint to prevent regression.

### ASSUM-003: Baseline description coverage count may be off
- **Severity**: LOW
- **Details**: The baseline claims 56 properties have descriptions and 863 do not (6.1% coverage). This was not independently verified by this review. The exact count depends on whether you count properties inside `$defs`, nested objects, and array item schemas. P1-B agents should be given clear counting rules.
- **Evidence**: Baseline section 5 shows per-file counts. The methodology for counting is not documented (e.g., do `$defs` properties count? do inherited `$ref` descriptions count?).
- **Recommendation**: P1-B agents should be instructed on exact counting methodology: "Count every `properties` key at every nesting level. A property has a description if it contains a `description` key directly or if its `$ref` target has one."

---

## MISSES

### MISS-001: No P1 agent checks whether the 10 common required fields should use allOf base schema
- **Severity**: HIGH
- **Details**: The audit plan (P1-A question 3) asks "Is the common 10-field boilerplate better served by JSON Schema allOf composition with a base schema?" but does not instruct agents to look at how existing validators depend on the current flat structure. If a base schema is introduced via `allOf`, validators that do `data.get("generation_quality")` would still work, but schema validation flow changes. The agents need to assess validator compatibility with any proposed restructuring.
- **Evidence**: spec_quality_lint.py, canonical/integrity.py, canonical/autofix.py, seed_lint.py all directly access top-level fields. An allOf restructuring preserves this at the data level but changes schema validation behavior.
- **Recommendation**: P1-A should be told: "If proposing allOf base schema, verify that no validator relies on schema-level field enumeration (as opposed to data-level field access)."

### MISS-002: No agent checks prompt files for schema field expectations
- **Severity**: MEDIUM
- **Details**: The `prompts/` directory contains prompt templates that reference specific schema fields (e.g., "include generation_quality with assumptions array"). If schema fields are removed or renamed, prompts must be updated. No P1 agent scope includes cross-referencing prompts with proposed schema changes.
- **Evidence**: `prompt_schema_sync.py` validates prompt-schema alignment and lists DRIFT_SENSITIVE_FIELDS. Removing fields from schema would trigger prompt-schema sync errors.
- **Recommendation**: Add to P1-C scope: "For any field proposed for removal, check if it appears in any `prompts/prompt_NN_*.md` file."

### MISS-003: No agent verifies whether step_order.json schema exists
- **Severity**: MEDIUM
- **Details**: `step_order.json` is a critical configuration file read by many validators (dependency_order_lint, dag_lint, extraction_intent_check, forward_replay_check, hallucination_lint, matrix, cli.py). But it has no JSON schema to validate its own structure. The audit plan (P1-C) asks about optimizing step_order.json but no agent checks whether it should have a schema.
- **Evidence**: `tools/step_order.json` has no corresponding schema file. `schema_registry.json` has no entry for step_order.
- **Recommendation**: P1-E should note: "step_order.json lacks a schema. Consider whether one should be created (especially if it absorbs seed_manifest fields)."

### MISS-004: No agent checks the seed_manifest.schema.json against its actual data file
- **Severity**: LOW
- **Details**: `seed_manifest.schema.json` exists in `schema/` but the actual data file is `spec/common/seed_manifest.json`. No agent scope includes validating that the actual seed_manifest.json conforms to its schema, or checking if the schema accurately reflects the real data structure.
- **Evidence**: Baseline section 11 notes the location mismatch but does not flag validation.
- **Recommendation**: P1-E or P1-C should validate: `validate spec/common/seed_manifest.json` against `schema/seed_manifest.schema.json`.

---

## AMBIGUITIES

### AMBIG-001: "Dual-container" protocol is underspecified
- **Severity**: MEDIUM
- **Details**: The audit plan says each P1 agent runs in "Container A and Container B independently" with "P3 reconciliation." But there is no instruction on what makes the two containers produce different results. If they both read the same codebase with the same instructions, they will produce near-identical findings. The plan does not specify: different prompts? different starting points? different exploration strategies?
- **Evidence**: Audit plan section "P1 Agent Protocol" specifies identical constraints for both containers.
- **Recommendation**: Either (a) remove dual-container and run each agent once, or (b) specify how A and B differ (e.g., A does top-down analysis, B does bottom-up from tool code; A prioritizes breadth, B prioritizes depth).

### AMBIG-002: Severity criteria for "HIGH" says ">50 LOC duplication" -- unclear denominator
- **Severity**: LOW
- **Details**: The severity table says HIGH = ">50 LOC duplication". But 50 LOC of what? Across all schemas? Within one schema? Per duplicated pattern? If a 3-line pattern is repeated 20 times, is that 60 LOC of duplication (HIGH) or 3 LOC per instance (LOW)?
- **Evidence**: Audit plan "Severity Criteria" table.
- **Recommendation**: Clarify: "HIGH = a single duplicated definition/pattern that, when summed across all occurrences, exceeds 50 LOC of schema text."

### AMBIG-003: P1-C and P1-A overlap on coverage_gaps and canonical triad
- **Severity**: MEDIUM
- **Details**: Both P1-A (DRY) and P1-C (Bloat) are asked about `coverage_gaps` and the canonical triad. P1-A asks "Is coverage_gaps validated or consumed by any tool?" P1-C asks the same thing verbatim. The "deduplication across agents" rule (P3) says to keep in "primary agent's scope" but does not define which agent is primary for overlapping questions.
- **Evidence**: P1-A scope line 58: "`coverage_gaps` -- is this used anywhere in validation code or is it dead schema?" P1-C scope line 110: "`coverage_gaps` (in every step schema) -- who reads this? Is it validated?"
- **Recommendation**: Assign primary ownership: coverage_gaps to P1-C (bloat), canonical triad architectural assessment to P1-A (DRY). Remove the duplicate from the non-primary scope.

---

## HALLUCINATIONS

### HALLUC-001: Baseline lists correct definitions but wrong counts
- **Severity**: HIGH
- **Details**: This is not a hallucination of non-existent items, but the baseline tables correctly list all definitions by name while the summary counts are wrong. The tables are trustworthy; the counts are not. Specifically: atoms header says 5 (table lists 6), collections header says 22 (table lists 28), total says 37 (should be 44).
- **Evidence**: See BUG-001, BUG-002, BUG-003.
- **Recommendation**: Trust the tables, fix the counts. P1 agents should be warned to count items rather than trust header summaries.

### HALLUC-002: No hallucinated files or features detected
- **Severity**: LOW (positive finding)
- **Details**: All file paths referenced in the baseline and audit plan were verified to exist. No phantom files, non-existent tools, or fabricated features were found.
- **Evidence**: All checked paths resolve: `schema_registry.json`, `step_order.json`, `spec/common/seed_manifest.json`, all schema files, all referenced Python modules.
- **Recommendation**: None needed.

---

## REGRESSIONS

### REG-001: P5 tools/tests audit schema changes may affect baseline numbers
- **Severity**: MEDIUM
- **Details**: `git log --oneline -10 -- schema/` shows recent schema changes from the P5 tools/tests audit (commits f42e487 "R8 schema tightening", ae0da32 "R6 schema-prompt-validator alignment", etc.). The baseline was captured on the same branch but should be re-verified after P5 batch completion. If P5 batches 4 or 5 (not yet complete per memory) modify schemas, the baseline will be stale.
- **Evidence**: Recent commits touching `schema/`: `f42e487 feat(schema): implement R8 schema tightening` (most recent).
- **Recommendation**: If P5 execution resumes and modifies schemas, re-run P0 baseline capture before starting P1.

### REG-002: SpecError migration from P5 may change how validators report schema field issues
- **Severity**: LOW
- **Details**: The P5 audit introduced `SpecError` as the error type for validators (commit 315789e). If validators that check schema fields (like spec_quality_lint.py) were modified during P5, the P1 agents' code tracing may find different function signatures than expected.
- **Evidence**: Commit 315789e "feat(tools): complete 9-point audit -- SpecError migration, --json output, test restructuring".
- **Recommendation**: P1 agents should use the current branch state, not historical assumptions about validator signatures.

---

## Summary

| Category | Count | Critical | High | Medium | Low |
|----------|-------|----------|------|--------|-----|
| BUGS | 5 | 0 | 3 | 1 | 1 |
| GAPS | 7 | 1 | 2 | 4 | 0 |
| ASSUMPTIONS | 3 | 0 | 0 | 1 | 2 |
| MISSES | 4 | 0 | 1 | 2 | 1 |
| AMBIGUITIES | 3 | 0 | 0 | 2 | 1 |
| HALLUCINATIONS | 2 | 0 | 1 | 0 | 1 |
| REGRESSIONS | 2 | 0 | 0 | 1 | 1 |
| **TOTAL** | **26** | **1** | **7** | **11** | **7** |

### Top Action Items (before launching P1)

1. **Fix baseline counts** (BUG-001/002/003): atoms=6, collections=28, total core defs=44
2. **Fix baseline generation_quality count** (BUG-005): 19, not 20
3. **Add GAP-001 context to P1-A scope**: spec_refs_ingested has ZERO tool code consumers
4. **Add GAP-002/003 context to P1-C scope**: coverage_gaps only used by step_12; quality lint checks 8/10 fields
5. **Add GAP-004 context to P1-C scope**: generation_quality IS used (quality lint + prompt_schema_sync drift detection)
6. **Add GAP-005 to P1-A or P1-C**: check prompt_schema_sync DRIFT_SENSITIVE_FIELDS before proposing removals
7. **Resolve AMBIG-001**: clarify dual-container differentiation or remove it
8. **Resolve AMBIG-003**: assign primary ownership of overlapping scope items
