# R2 Document Review -- Round 2

**Date**: 2026-03-20
**Reviewer**: Claude Opus 4.6 (1M context)
**Prior Review**: r2-review.md (26 findings, 3 fixes applied)
**Scope**: All 7 R2 documents re-read in full, 13 decisions re-checked, 12 spot-checks against codebase

---

## Prior Fix Verification

| Fix | Status | Notes |
|-----|--------|-------|
| R2-B S1.1 reframe | FIXED | Section 1.1 heading changed from "What the templates miss" to "Requirement categories that seeds may not explicitly cover". Body text now includes Decision 7 framing: "Seeds are PRD/system design input, not specs... the critical question is whether step prompts guide LLMs to extract or derive them." Correct. |
| R2-E-002 cross-ref | FIXED | R2-E-002 line 274 now includes: "Per Decision 6... See R2-G-005, R2-G-006... No NL tooling needed (Decision 5)." All three cross-references present and accurate. |
| R2-C-008 elevation | FIXED | R2-C-008 heading now reads "MEDIUM -> elevate to HIGH, cross-ref R2-C-002". Body references Decision 12 and Decision 13. Recommendation connects machine-computed coverage to blocking gate. Correct. |

**No regressions from fixes.**

---

## Summary

| Type | CRIT | HIGH | MED | LOW | Total |
|------|------|------|-----|-----|-------|
| Decision Inconsistency | 0 | 0 | 1 | 0 | 1 |
| Completeness Gap | 0 | 0 | 2 | 1 | 3 |
| Codebase Mismatch | 0 | 0 | 0 | 1 | 1 |
| Cross-Doc Inconsistency | 0 | 0 | 0 | 1 | 1 |
| **Total** | **0** | **0** | **3** | **3** | **6** |

---

## Findings

### FINDING-R2R2-001: R2-B Summary line 549 still frames the issue as seed template deficiency (Decision 7 violation)

- **Type**: Decision Inconsistency
- **Severity**: MEDIUM
- **Document**: r2-B-seed-to-spec-integrity.md
- **Decision**: #7 (Seeds are PRD, not specs)
- **Location**: Line 549, Summary section, bullet 1
- **Claim**: "Seed templates lack dedicated sections for compliance, data lifecycle, and operational requirements (R2-B-001). These gaps propagate irreversibly."
- **Problem**: The Section 1.1 body text and the R2-B-001 finding were correctly patched to reframe from "templates miss" to "step prompts must compensate." But the Summary section (line 549) still uses the old framing: "Seed templates lack dedicated sections." This directly contradicts Decision 7 and the patched R2-B-001 finding which says the real issue is that step prompts don't guide extraction.
- **Fix**: Rewrite line 549 to: "Step prompts do not guide LLMs to extract compliance, data lifecycle, and operational requirements from seed input (R2-B-001). These extraction gaps propagate irreversibly."

### FINDING-R2R2-002: No R2 finding addresses prompt-schema-sync tooling implications of Decision 1

- **Type**: Completeness Gap
- **Severity**: MEDIUM
- **Document**: All R2 documents
- **Decision**: #1 (Schema sole owner of field descriptions)
- **Location**: N/A -- missing coverage
- **Claim**: Decision 1 says all field semantics move to schemas and prompts contain zero field-level guidance. The toolkit has an existing `prompt-schema-sync` command (`tools/specdev_tools/generation/prompt_schema_sync.py`) that currently validates prompt Output Contract JSON against schemas.
- **Problem**: Once Decision 1 is implemented (field guidance deleted from prompts, enriched in schemas), the prompt-schema-sync tool's purpose and scope will change significantly. It currently checks that prompt examples are schema-valid. After Decision 1, it may need to verify that prompts do NOT contain field-level guidance (reverse lint), or it may become obsolete for some checks. No R2 finding addresses this tooling impact.
- **Fix**: P4 should include a review of `prompt_schema_sync.py` scope post-Decision-1. Not a new R2 finding needed -- this is a P4 implementation detail. Note it in the P4 fix plan under Decision 1 implementation.

### FINDING-R2R2-003: No R2 finding addresses glossary schema redesign for Decision 6

- **Type**: Completeness Gap
- **Severity**: MEDIUM
- **Document**: r2-G-canon-audit.md
- **Decision**: #6 (Glossary step becomes canon population step)
- **Location**: R2-G findings section
- **Claim**: Decision 6 says Step 03 populates `cn:project:` canons. R2-G-005 addresses the missing acceptance tooling. R2-G-006 addresses enforcement via canonical-lint.
- **Problem**: Neither R2-G nor any other R2 document addresses whether the `03_glossary.schema.json` needs redesign. Currently it emits a `terms` array with `term_id`, `term`, `definition`, `domain`, etc. If Step 03 becomes a canon population step, it would need to emit `canonical_proposals` (which `step_base.schema.json` already provides) or a hybrid output. The glossary schema may need to be deprecated, replaced, or extended. R2-G Section "What's needed" mentions "Step 03 prompt rewrite -- emit canonical_proposals array instead of glossary.json, or emit both during transition" but this is not captured as a formal finding with files and severity.
- **Fix**: This is an implementation detail for P4, not a missing R2 finding per se. The R2-G "What's needed" section already identifies it. P4 should formalize the Step 03 schema transition plan. LOW priority -- R2-G adequately signals the issue even without a numbered finding.

### FINDING-R2R2-004: R2-B-009 glossary lifecycle_states claim is confirmed accurate against codebase

- **Type**: Codebase Mismatch (verified as correct)
- **Severity**: LOW (informational)
- **Document**: r2-B-seed-to-spec-integrity.md
- **Decision**: N/A
- **Location**: R2-B-009, confirmed by `schema/03_glossary.schema.json`
- **Claim**: R2-B-009 says prompt_06 references "entities with lifecycle stages defined in the glossary" but the glossary schema has no `lifecycle_states` field.
- **Verification**: `schema/03_glossary.schema.json` has fields: `term_id`, `term`, `acronym`, `definition`, `domain`, `units`, `term_ref`, `acronym_ref`, `unit_ref`. No `lifecycle_states` field exists. Prompt_06 line 50 says "Entity definitions, lifecycle states, and domain term IDs" and line 56 says "state transition rules for entities with lifecycle stages defined in the glossary." The prompt references structure that does not exist in the schema.
- **Note**: This was already verified in r2-review.md. Confirming it remains accurate -- no regression.

### FINDING-R2R2-005: R2-A and R2-D give different boilerplate LOC totals

- **Type**: Cross-Document Inconsistency
- **Severity**: LOW
- **Document**: r2-A-content-classification.md, r2-D-shared-expectations-design.md
- **Location**: R2-A summary table row "BOILERPLATE" vs R2-D Section 1.4 summary
- **Claim**: R2-A says BOILERPLATE is 1,312 LOC (23%). R2-D Section 1.4 identifies 16 blocks totaling ~1,226 LOC. R2-D Section 4.2 says the extraction eliminates ~1,032 LOC.
- **Problem**: Three different numbers for boilerplate: 1,312 (R2-A), 1,226 (R2-D inventory), 1,032 (R2-D extractable). These are not contradictory -- R2-A counts all boilerplate LOC, R2-D inventories blocks, R2-D extraction is what actually moves to shared_expectations (some near-identical blocks have step-specific variations that stay). But the relationship between these numbers is not documented. A reader could see 1,312 vs 1,032 and wonder where 280 LOC went.
- **Fix**: Minor. R2-D could note: "The 1,032 LOC extraction target is a subset of R2-A's 1,312 LOC boilerplate total. The difference (~280 LOC) consists of near-identical blocks with step-specific variations that must remain per-prompt (subset-applicable blocks G, H, I, J where overrides exist)." This is a documentation clarity issue, not an error.

### FINDING-R2R2-006: No R2 finding addresses 13a schema redesign implications of Decision 12

- **Type**: Completeness Gap
- **Severity**: LOW
- **Document**: r2-C-spec-to-impl-integrity.md
- **Decision**: #12 (13a as machine-computed coverage)
- **Location**: R2-C-002 and Section 8
- **Claim**: Decision 12 redesigns 13a from subjective AI report to machine-computed analysis. R2-C-002 identifies the current schema lacks structured coverage metrics. R2-C Section 8 proposes "structured schema fields for coverage dimensions with minimum thresholds."
- **Problem**: R2-C-002 mentions the need for schema redesign but does not specify what the new `13a_completeness_assessment.schema.json` should look like. The current schema has `completeness_rating.current` (subjective 0-10), `missing_elements` (free-form), and `element_ids` with cross-refs. For machine-computed coverage, it would need fields like `fr_coverage_percent`, `api_fixture_coverage_percent`, `pairwise_completeness` per transition, etc. This is an implementation detail but P4 needs guidance.
- **Fix**: P4 should include 13a schema redesign as a task under Decision 12. The R2-C Section 8 provides sufficient direction -- "structured schema fields for coverage dimensions with minimum thresholds." No new R2 finding needed.

---

## Decision Consistency Verification (Fresh Pass)

### Decision 1 (Schema sole owner): PASS
All 7 documents consistent. R2-F2-001 explicitly says "schemas are the sole owner of field semantics, period." R2-A correctly categorizes 500 LOC as SCHEMA-DUP for deletion. R2-D2-004 correctly says schema-dup goes to schemas, not shared_expectations. No document suggests "fixing prompts to match schemas" -- they all say "delete from prompts, enrich schemas."

### Decision 2 (Cross-step from DAG): PASS
R2-A identifies DAG-DUP as 69 LOC (1%) for deletion. R2-D Section 6.2 says "Derivable from downstream_consumers." No document proposes keeping DAG info in prompts.

### Decision 3 (allowed_upstream delete): PASS (gap noted in r1 review)
No R2 document explicitly covers this. r1 review FINDING-001 noted this as a LOW gap. Still accurate -- AUDIT-023 covers it.

### Decision 4 (Universal pairwise): PASS
R2-C-001 says "at ANY Transition" (universal). R2-E-012 says "Full Pipeline." Both consistent with universal pairwise chain. No finding frames completeness as FR-specific.

### Decision 5 (No NL tooling): PASS
R2-E proposes only ID-level enforcement. R2-E-002 now explicitly says "No NL tooling needed (Decision 5)." No document proposes semantic comparison validators.

### Decision 6 (Glossary to canon): PASS
R2-G-005, R2-G-006 address infrastructure. R2-E-002 cross-references Decision 6 and R2-G. R2-B-007 identifies glossary as decorative -- consistent with repurposing it.

### Decision 7 (Seeds are PRD): PARTIAL (FINDING-R2R2-001)
R2-B-001 correctly reframed. Section 1.1 correctly reframed. But Summary line 549 still uses old framing. See FINDING-R2R2-001.

### Decision 8 (Don't steer agents): PASS
r1 review noted this is a process meta-decision. All R2 documents show evidence-based analysis. No steering detected.

### Decision 9 (Schema enrichment first): PASS
R2-D2-008 explicitly says "First: Enrich schema descriptions with prompt guidance. Then: Extract boilerplate." Correct ordering.

### Decision 10 (Self-Audit decomposition): PASS
R2-D2-003 exactly matches three-concern decomposition. No inconsistency.

### Decision 11 (No rigid format): PASS
R2-F2-004 says "three tiers describe DEPTH, not FORMAT." Consistent.

### Decision 12 (13a machine-computed): PASS
R2-C-002, R2-C Section 8 both propose machine-computed coverage. Consistent.

### Decision 13 (Pipeline validity not completeness): PASS
R2-C-001 proposes pairwise completeness as extension of existing infrastructure. R2-E-012 documents the gap. Both consistent with "fix via pairwise checks."

---

## Cross-Document Consistency Verification

### R2-A categories align with R2-D extraction list: PASS
R2-A identifies 5 removable categories. R2-D Section 2 maps each to its destination (SCHEMA-DUP->schemas, DAG-DUP->step_order, CANON-DUP->canon, BOILERPLATE->shared_expectations). Categories are consistent.

### R2-C and R2-E overlapping findings: PASS (improved from r1)
R2-E-012 and R2-C-001 are the same underlying issue. r1 review noted missing cross-reference. These are separate documents with overlapping scope -- the overlap is acknowledged but not cross-referenced in R2-E. This was noted as LOW in r1 and remains unchanged. Acceptable for P4 consolidation.

### R2-F and R2-A agree on schema-dup: PASS
R2-A counts 500 LOC SCHEMA-DUP. R2-F Section 1 identifies 58 movable items (~116 LOC) across 7 schemas sampled. Extrapolating to all 22 prompts/schemas is consistent with 500 LOC total.

### R2-G glossary-canon aligns with R2-E glossary findings: PASS
R2-E-002 says glossary feeds only 3 steps, enforcement is decorative. R2-G-006 says once in canon, canonical-lint enforces automatically. R2-E-002 now cross-references R2-G-006. Consistent.

### R2-A boilerplate LOC vs R2-D boilerplate LOC: MINOR INCONSISTENCY (FINDING-R2R2-005)
Three different numbers (1,312 / 1,226 / 1,032) are technically consistent but the relationship is not documented.

---

## Evidence Spot-Checks (12 items)

| # | Claim (Document) | Source Verified | Status |
|---|---|---|---|
| 1 | R2-C-005: VALID_VERDICTS = {"verified", "needs_work", "blocked", "deferred"} | `step_16c.py` line 13 | CONFIRMED |
| 2 | R2-C-005: Prompt says "rejected" as verdict | `prompt_16c_impl_reviewer.md` line 134 | CONFIRMED -- "rejected" in prompt table, not in validator |
| 3 | R2-C-010: _STEP_PATTERN checks against `^[0-9]{2}[a-z]?_` | `step_13.py` line 13 | CONFIRMED |
| 4 | R2-C-003: semantic_review check is conditional on isinstance(dict) | `step_16c.py` lines 34-46 | CONFIRMED -- no requirement for presence when verdict=verified |
| 5 | R2-B: downstream_consumers["03"] = ["04", "05", "07"] | `step_order.json` line 326 | CONFIRMED |
| 6 | R2-B: downstream_consumers["02a"] = ["12"] only | `step_order.json` line 325 | CONFIRMED |
| 7 | R2-B-009: glossary schema has no lifecycle_states field | `03_glossary.schema.json` lines 21-64 | CONFIRMED -- no such field |
| 8 | R2-F2-002: statement description is thin | `04_fr_list.schema.json` line 27 | CONFIRMED -- "Clear statement...minimum 20 characters." No quality guidance |
| 9 | R2-F2-002: acceptance_criteria text description is thin | `04_fr_list.schema.json` line 57 | CONFIRMED -- "Descriptive text...minimum 15 characters." |
| 10 | R2-E-002: R2-G cross-reference present | `r2-E` line 274 | CONFIRMED -- Decision 5, 6, R2-G-005, R2-G-006 all referenced |
| 11 | R2-C-008: elevated to HIGH with Decision 12/13 refs | `r2-C` lines 619-624 | CONFIRMED |
| 12 | R2-B Section 1.1: reframed from "What templates miss" | `r2-B` lines 21-29 | CONFIRMED -- correct framing with Decision 7 note |

All 12 spot-checks passed.

---

## Actionability Assessment

### Findings with specific files and changes (actionable for P4):

| Finding | Names Files? | Describes Change? | P4-Ready? |
|---------|-------------|-------------------|-----------|
| R2-A-001 (Prompt 14 schema-dup) | Yes: prompt_14, schema/14_roadmap | Yes: delete Field-by-Field | Yes |
| R2-A-003 (1312 LOC boilerplate) | Yes: all 22 prompts | Yes: extract to shared_expectations | Yes |
| R2-B-001 (extraction guidance) | Yes: prompts 00, 04, 07 | Yes: add category checklists | Yes |
| R2-B-003 (schema required fields) | Yes: 00_charter.schema.json | Yes: add to required array | Yes |
| R2-B-008 (implicit FR discovery) | Yes: prompt_04 | Yes: add FR category checklist | Yes |
| R2-C-001 (pairwise completeness) | Yes: validators for steps 08,09,14 | Yes: add coverage checks | Yes |
| R2-C-002 (13a machine-computed) | Yes: prompt_13a, schema_13a, new linter | Yes: create specdev completeness-check | Yes |
| R2-C-003 (semantic review) | Yes: step_16c.py | Yes: add E-code for missing semantic_review | Yes |
| R2-C-005 (verdict mismatch) | Yes: prompt_16c, step_16c.py | Yes: synchronize enums | Yes |
| R2-C-010 (step_13 pattern) | Yes: step_13.py line 28 | Yes: relax/remove pattern | Yes |
| R2-D2-001 (extract boilerplate) | Yes: all 22 prompts + shared_expectations | Yes: detailed block-by-block plan | Yes |
| R2-F2-001 (enrich descriptions) | Yes: 7 schema files with 10 migration examples | Yes: before/after for each | Yes |
| R2-G-002 (namespace separation) | Yes: canon/manifest.json | Yes: establish cn:core vs cn:project | Yes |
| R2-G-005 (acceptance tooling) | Yes: new CLI command | Yes: specdev canon-accept | Yes |

### Findings that are observations without specific fix (need P4 design):

| Finding | Issue |
|---------|-------|
| R2-E-006 (no consumed API contracts) | Proposes new pipeline artifact -- needs design decision on whether to add step |
| R2-E-007 (security model scattered) | Proposes consolidation -- needs design decision on extension vs new step |
| R2-E-008 (no data model artifact) | Same pattern -- new step vs extension decision |
| R2-E-009 (Discovery quality gap) | Observation about quality delta -- actionable via R2-A-008 (add examples) |

These are MEDIUM severity findings that describe systemic issues. They are P4-addressable as "prompt enrichment" work rather than infrastructure changes.

---

## Verified Correct (Unchanged from r1 Review)

The following items from r1 review remain verified and accurate:

1. R2-C-005 verdict mismatch -- codebase confirmed
2. R2-C-010 step_13 pattern bug -- codebase confirmed
3. R2-C-003 semantic_review not enforced -- codebase confirmed
4. R2-B downstream_consumers for 03 -- step_order.json confirmed
5. R2-B Step 06 not consumer of 03 -- step_order.json confirmed
6. R2-G namespace support -- canonical ID pattern confirmed
7. R2-D Self-Audit Gate 20/22 threshold -- consistent with document analysis
8. R2-F statement description thinness -- schema confirmed
9. R2-F acceptance_criteria text thinness -- schema confirmed
10. allowed_upstream_dependencies still present -- step_order.json confirmed
11. R2-E-002 cross-reference added -- confirmed present
12. R2-C-008 elevated with Decision 12/13 refs -- confirmed present

---

## Overall Assessment

The 7 R2 documents are production-quality. The three fixes from r1 review were all applied correctly with no regressions. The fresh decision consistency pass found one residual Decision 7 violation (R2-B summary line 549 -- trivial text fix) and zero contradictions with any other decision. Cross-document consistency is good with one minor LOC accounting discrepancy.

**New findings this round: 6** (0 CRIT, 0 HIGH, 3 MED, 3 LOW). All MEDIUM findings are completeness gaps where implementation implications of locked decisions are not fully addressed in R2 -- these are P4 implementation details, not R2 analysis gaps.

**The R2 document set is ready for P4 consolidation.** The only required fix before consolidation is FINDING-R2R2-001 (one sentence in R2-B summary). The remaining 5 findings are informational notes for P4.
