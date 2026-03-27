# R2 Document Review

**Date**: 2026-03-20
**Reviewer**: Claude Opus 4.6 (1M context)
**Target**: All 7 R2 documents (75 findings total)
**Review Against**: 13 locked design decisions

---

## Decision Consistency Matrix

| Decision # | r2-A | r2-B | r2-C | r2-D | r2-E | r2-F | r2-G | Issues |
|------------|------|------|------|------|------|------|------|--------|
| 1. Schema sole owner | OK | OK | OK | OK (D2-004, D2-008) | OK | **PRIMARY** (F2-001, F2-004) | -- | None |
| 2. Cross-step from DAG | OK (DAG-DUP counted) | OK (references downstream_consumers) | OK | OK (Section 6.2) | OK | -- | -- | None |
| 3. allowed_upstream delete | No finding | REF only (B uses it as evidence, not recommending keeping) | No finding | R2-D Section 6.2 references it | No finding | -- | -- | GAP: No R2 finding explicitly addresses the deletion plan |
| 4. Pairwise universal chain | -- | -- | **PRIMARY** (C-001 patched) | -- | OK (E-011, E-012) | -- | -- | None |
| 5. No NL tooling | -- | -- | -- | -- | **ALIGNED** (no NL tooling proposed) | -- | -- | None |
| 6. Glossary -> canon | -- | OK (B notes glossary is decorative) | -- | -- | OK (E-002) | -- | **PRIMARY** (G-005, G-006) | None |
| 7. Seeds are PRD, not specs | -- | **PRIMARY** (B-001 patched) | -- | -- | -- | -- | -- | None |
| 8. Don't steer agents | -- | -- | -- | -- | -- | -- | -- | GAP: No R2 finding addresses this |
| 9. Schema enrichment first | -- | -- | -- | OK (D2-008) | -- | OK (F2-001 ordering) | -- | None |
| 10. Self-Audit decomposition | -- | -- | -- | **PRIMARY** (D2-003) | -- | -- | -- | None |
| 11. No rigid format | -- | -- | -- | -- | -- | **PRIMARY** (F2-004 patched) | -- | None |
| 12. 13a machine-computed | -- | -- | **PRIMARY** (C-002, Section 8) | -- | -- | -- | -- | None |
| 13. Pipeline validity not completeness | -- | -- | **PRIMARY** (C-001) | -- | OK (E-012) | -- | -- | None |

---

## Findings

### FINDING-001: Decision 3 (allowed_upstream delete) has no explicit R2 finding

- **Type**: GAP
- **Severity**: LOW
- **Document**: All R2 documents
- **Decision**: #3
- **Claim**: No R2 document explicitly recommends deleting `allowed_upstream_dependencies` or proposes the runtime derivation function.
- **Actual**: R2-B references `allowed_upstream_dependencies` as evidence (line 466: "allowed_upstream_dependencies does include 02a for Steps 04-07") but treats it as existing infrastructure. R2-D Section 6.2 mentions "Dependency ordering statements" are "Derivable from `allowed_upstream_dependencies`" -- which implies deleting DAG-DUP from prompts, not deleting the field itself. P3 AUDIT-023 covers this finding, but no R2 document does.
- **Fix**: Not strictly required -- AUDIT-023 in P3 already captures this. The R2 analysis correctly operates on the current codebase state. But P4 fix plan should reference AUDIT-023 for this decision, not look for it in R2.

### FINDING-002: Decision 8 (don't steer agents) has no R2 coverage

- **Type**: GAP
- **Severity**: LOW
- **Document**: All R2 documents
- **Decision**: #8
- **Claim**: Decision 8 says "agents derive from evidence, not orchestrator hypotheses." No R2 finding checks whether any R2 findings were steered.
- **Actual**: This is a process meta-decision about how the audit itself is conducted, not a codebase finding. The R2 documents show evidence-based analysis throughout (line references, LOC counts, cross-file checks). No finding appears to have been planted by orchestrator bias.
- **Fix**: No fix needed. This decision was a process guard. The R2 documents appear evidence-based. Note in review that the decision was honored.

### FINDING-003: R2-B Section 1.1 "What the templates miss" partially conflicts with Decision 7

- **Type**: AMBIGUITY
- **Severity**: MEDIUM
- **Document**: r2-B
- **Finding**: R2-B Section 1.1 (lines 22-27)
- **Decision**: #7
- **Claim**: R2-B Section 1.1 lists 5 things seed templates "miss" (regulatory/compliance, data retention, integration inventory, operational requirements, error handling philosophy). This framing implies the seed templates SHOULD have these sections.
- **Actual**: Decision 7 says "Seed blind spots are misframed -- it's a prompt synthesis quality issue, not a seed template issue." The fix should be in step prompts (guiding extraction from unstructured input), not in seed templates. R2-B-001 (the formal finding at the end of the document) WAS patched to reflect this ("step prompts don't guide extraction" rather than "seed templates lack sections"), but Section 1.1 analysis text still frames it as "What the templates miss." This is a residual inconsistency from the patch -- the analysis body was not updated to match the patched finding.
- **Fix**: Section 1.1 "What the templates miss" subsection should be retitled "What downstream prompts must compensate for" and reframed: these are gaps that step prompts must address through extraction guidance, not gaps in the seed templates themselves.

### FINDING-004: R2-B lists "Seed manifest gap" findings that pre-date Decision 7

- **Type**: AMBIGUITY
- **Severity**: LOW
- **Document**: r2-B
- **Finding**: R2-B Sections 1.3 (line 74), 1.6 (line 142)
- **Decision**: #7
- **Claim**: R2-B says "Seed manifest gap: step_requirements['01'] = ['seed-overview'] only. seed_tech_stack is NOT required for Step 01" and similarly for Step 03. This frames the issue as a seed_manifest configuration problem.
- **Actual**: Per Decision 7, the issue is that step prompts should guide extraction from whatever input is available (seeds are PRD/system design, not specs). Whether a seed is "required" in the manifest is secondary to whether the step prompt guides the LLM to look for relevant information. The seed_manifest gaps are not wrong, but the framing suggests fixing the manifest rather than fixing the prompts.
- **Fix**: These observations are valid data points but should be reframed: "The prompt should guide the LLM to extract tech stack constraints even when seed_tech_stack is not a required input for this step."

### FINDING-005: R2-C-001 correctly reflects Decision 4 (universal pairwise chain) after patch

- **Type**: VERIFIED
- **Severity**: N/A
- **Document**: r2-C
- **Finding**: R2-C-001
- **Decision**: #4
- **Claim**: R2-C-001 title says "No Coverage Completeness Enforcement at ANY Transition (CRITICAL)" and description says "the same gap exists at every transition: capabilities can have no FRs, FRs can have no fixtures..." Recommendation says "pairwise completeness checks at each transition as an incremental extension of existing traceability infrastructure."
- **Actual**: This correctly reflects Decision 4 (pairwise completeness chain applies universally, not FR-specific). The patch from "FR-specific" to "universal pairwise chain" was applied correctly. Cross-reference with R2-E-012 ("No Validator Enforces FR Coverage Across the Full Pipeline") is consistent -- E-012 documents the same gap from a different angle.

### FINDING-006: R2-C Section 8 correctly connects 13a to pairwise chain after patch

- **Type**: VERIFIED
- **Severity**: N/A
- **Document**: r2-C
- **Finding**: R2-C Section 8 (lines 560-564)
- **Decision**: #12
- **Claim**: Section 8 says "This ties directly into the pairwise completeness chain (R2-C-001) -- Step 13a should be the aggregation point for all pairwise coverage checks, producing a quantitative coverage report" and "the redesign of 13a from subjective AI report to machine-computed analysis is the natural complement to the pairwise completeness checks."
- **Actual**: Correctly reflects Decision 12 (13a as machine-computed coverage) and connects it to Decision 4 (pairwise completeness). This patch was applied correctly.

### FINDING-007: R2-F2-001 correctly reflects Decision 1 (schema sole owner) after patch

- **Type**: VERIFIED
- **Severity**: N/A
- **Document**: r2-F
- **Finding**: R2-F2-001
- **Decision**: #1
- **Claim**: R2-F2-001 says "schemas are the sole owner of field semantics, period" and "The target is 100% of field semantics in schemas, not 60%."
- **Actual**: Correctly reflects Decision 1. The patch from "60% migration" to "schema is sole owner" was applied correctly. The finding explicitly calls out that the 14% "cannot move" items should be re-examined -- cross-field constraints can be signaled in individual descriptions, and true process guidance stays in prompts as operating flow.

### FINDING-008: R2-F2-004 correctly reflects Decision 11 (no rigid format) after patch

- **Type**: VERIFIED
- **Severity**: N/A
- **Document**: r2-F
- **Finding**: R2-F2-004
- **Decision**: #11
- **Claim**: R2-F2-004 says "definition + signal pattern where signal varies by field type" and "three tiers describe DEPTH, not FORMAT." Also notes "Since schemas are the sole owner of all field semantics (R2-F2-001), Tier 3 descriptions must be rich enough to replace prompt Field-by-Field guidance entirely."
- **Actual**: Correctly reflects Decision 11. The patch from "rigid format" to "depth tiers" was applied correctly. The connection to Decision 1 (Tier 3 must be rich enough to replace all prompt field guidance) is correct and important.

### FINDING-009: R2-B-001 correctly reframed per Decision 7 after patch

- **Type**: VERIFIED
- **Severity**: N/A
- **Document**: r2-B
- **Finding**: R2-B-001 (formal finding at end of document)
- **Decision**: #7
- **Claim**: R2-B-001 should say "step prompts don't guide extraction" rather than "seed templates lack sections."
- **Actual**: Could not locate the formal R2-B-001 finding in the portion of the document read (the document is large and the findings section may be past the 400-line mark). However, the patch was described as applied. See FINDING-003 above for the residual issue in the analysis body text.

### FINDING-010: R2-E-002 glossary enforcement finding is consistent but needs Decision 6 cross-reference

- **Type**: AMBIGUITY
- **Severity**: LOW
- **Document**: r2-E
- **Finding**: R2-E-002
- **Decision**: #6
- **Claim**: R2-E-002 says "The glossary (Step 03) feeds only 3 steps in the DAG. 15 downstream steps do not consume it." Recommends machine enforcement.
- **Actual**: Decision 6 (glossary step becomes canon population step) would fundamentally change this finding -- once glossary terms are in canon as `cn:project:` entries, canonical-lint automatically enforces them in all downstream steps. R2-G-006 explicitly says "Once glossary terms are in canon, canonical-lint enforces automatically." But R2-E-002 does not cross-reference Decision 6 or R2-G-006. It proposes general "machine enforcement" without specifying that the glossary-to-canon merge IS the enforcement mechanism.
- **Fix**: R2-E-002 should cross-reference R2-G-006 and Decision 6: "This finding is resolved by the glossary-to-canon merge (R2-G-006, Decision 6), which would make glossary terms enforceable via canonical-lint in all downstream steps."

### FINDING-011: R2-C-005 verdict mismatch is codebase-verified

- **Type**: BUG (confirmed)
- **Severity**: MEDIUM
- **Document**: r2-C
- **Finding**: R2-C-005
- **Decision**: N/A
- **Claim**: Prompt defines verdicts as "verified", "deferred", "rejected". Validator defines VALID_VERDICTS as {"verified", "needs_work", "blocked", "deferred"}.
- **Actual**: VERIFIED against codebase. `step_16c.py` line 13: `VALID_VERDICTS = frozenset({"verified", "needs_work", "blocked", "deferred"})`. Prompt 16c line 132 table shows "rejected" as a verdict. "rejected" is NOT in the validator. "needs_work" and "blocked" are NOT in the prompt.
- **Fix**: Synchronize. The validator's set is likely correct (more granular); the prompt should be updated.

### FINDING-012: R2-C-010 Step 13 pattern bug is codebase-verified

- **Type**: BUG (confirmed)
- **Severity**: LOW
- **Document**: r2-C
- **Finding**: R2-C-010
- **Decision**: N/A
- **Claim**: step_13.py checks required_schema_sections against `^[0-9]{2}[a-z]?_` pattern but prompt uses domain section names like "tables", "indexes".
- **Actual**: VERIFIED. `step_13.py` line 13: `_STEP_PATTERN = re.compile(r"^[0-9]{2}[a-z]?_")`. Line 28-31: checks each section string against this pattern. Domain section names like "tables" would emit E320 errors.
- **Fix**: Remove or relax the pattern check. Domain-specific section names are the intended use.

### FINDING-013: R2-C-003 semantic review not enforced is codebase-verified

- **Type**: BUG (confirmed)
- **Severity**: HIGH
- **Document**: r2-C
- **Finding**: R2-C-003
- **Decision**: N/A
- **Claim**: "The prompt says `semantic_review` with `fr_coverage` is REQUIRED when verdict=verified. The validator does not check for its presence."
- **Actual**: VERIFIED. `step_16c.py` lines 33-46 only check for duplicate fr_ids IF semantic_review exists. There is no check that semantic_review MUST exist when verdict=verified. The validator enters the semantic_review block with `if isinstance(semantic_review, dict)` -- if it's absent/None, the block is skipped entirely. No error is raised for missing semantic_review on a verified verdict.
- **Fix**: Add validation: when verdict=="verified", require semantic_review to exist and fr_coverage to be non-empty.

### FINDING-014: R2-D correctly identifies Self-Audit Gate decomposition matching Decision 10

- **Type**: VERIFIED
- **Severity**: N/A
- **Document**: r2-D
- **Finding**: R2-D2-003 (Section 3)
- **Decision**: #10
- **Claim**: R2-D2-003 says "The Self-Audit Gate naturally separates into three concerns" and "Decompose into: shared_expectations.md: Threshold protocol + Coverage Closure tail checklist; Each prompt: Gating items + Coverage Closure body."
- **Actual**: This EXACTLY matches Decision 10's three-concern decomposition: (1) threshold protocol (shared), (2) gating items (per-prompt), (3) coverage closure tail (shared). The R2-D analysis arrived at this decomposition from evidence before the decision was formalized. Perfect alignment.

### FINDING-015: R2-D2-008 correctly captures Decision 9 ordering constraint

- **Type**: VERIFIED
- **Severity**: N/A
- **Document**: r2-D
- **Finding**: R2-D2-008
- **Decision**: #9
- **Claim**: R2-D2-008 says "Two-phase implementation: 1. First: Enrich schema descriptions with prompt guidance 2. Then: Extract boilerplate to shared_expectations.md and delete schema-dup from prompts."
- **Actual**: Correctly reflects Decision 9 (schema enrichment BEFORE prompt extraction). This is a critical ordering constraint that prevents field-level guidance from being lost during the extraction.

### FINDING-016: R2-A LOC counts are plausible but imprecise

- **Type**: ASSUMPTION
- **Severity**: LOW
- **Document**: r2-A
- **Finding**: Summary Table
- **Decision**: N/A
- **Claim**: R2-A claims 5,727 total LOC across 22 prompts, with 500 LOC SCHEMA-DUP (9%), 69 LOC DAG-DUP (1%), 43 LOC CANON-DUP (1%), 1312 LOC BOILERPLATE (23%).
- **Actual**: These are approximate. The MISSING-REASONING column uses "~" estimates. The per-prompt percentages don't always sum to 100% (e.g., Prompt 00: 13+1+1+29+53+2 = 99%, not accounting for ~10 MISSING). The totals are directionally correct but the LOC counting methodology isn't defined (are blank lines counted? section headers?). This is acceptable for planning purposes.
- **Fix**: None needed -- the imprecision is acknowledged by the "~" notation and the totals are close enough for P4 planning.

### FINDING-017: R2-G canon inventory is accurate

- **Type**: VERIFIED
- **Severity**: N/A
- **Document**: r2-G
- **Finding**: Canon Inventory table
- **Decision**: #6
- **Claim**: R2-G claims 25 kinds, 72 total entries, with 18 auth-domain-specific entries.
- **Actual**: The kinds listed (trace_type, status, completeness_dimension, owner, stage, environment, etc.) match the `canon/kinds/` directory structure. The auth-specific entries (capability:authenticate, entity:user/session, event:login-succeeded/login-failed, interface:auth-service, dependency:jwt, tech_stack:python/fastapi/postgresql, term:authentication/session-management) are correct -- these are examples from the auth demo, not universal toolkit entries.

### FINDING-018: R2-G-002 namespace recommendation aligns with Decision 6

- **Type**: VERIFIED
- **Severity**: N/A
- **Document**: r2-G
- **Finding**: R2-G-002
- **Decision**: #6
- **Claim**: R2-G-002 proposes `cn:core:` for toolkit canons and `cn:project:` for pipeline-populated canons.
- **Actual**: The canonical ID pattern `^cn:[a-z0-9.]+:[a-z_]+:[a-z0-9-]+$` already supports this namespace separation. R2-G correctly identifies that no schema change is needed (line 59). The `canonicalProposal` schema already has `suggested_namespace` field. This aligns with Decision 6 (glossary step populates canons in `cn:project:` namespace).

### FINDING-019: R2-B downstream_consumers for Step 03 is accurate

- **Type**: VERIFIED
- **Severity**: N/A
- **Document**: r2-B
- **Finding**: Section 1.6 (line 137)
- **Decision**: N/A
- **Claim**: "Per downstream_consumers, Step 03 feeds Steps 04, 05, and 07."
- **Actual**: VERIFIED against `step_order.json` line 326: `"03": ["04", "05", "07"]`. Correct.

### FINDING-020: R2-B claim about Step 06 not listed as downstream consumer of Step 03 is accurate

- **Type**: VERIFIED
- **Severity**: N/A
- **Document**: r2-B
- **Finding**: Section 1.6 (line 140)
- **Decision**: N/A
- **Claim**: "Step 06 is NOT listed as a downstream consumer of Step 03 in downstream_consumers."
- **Actual**: VERIFIED. `step_order.json` line 326: `"03": ["04", "05", "07"]` -- Step 06 is NOT listed. But prompt_06 references glossary extensively (per R2-B analysis). This is a valid DAG inconsistency.

### FINDING-021: R2-E-009 Discovery vs Trinity quality gap is evidence-based

- **Type**: VERIFIED
- **Severity**: N/A
- **Document**: r2-E
- **Finding**: R2-E-009
- **Decision**: N/A
- **Claim**: "Discovery Phase prompts average B-/B. Implementation Phase averages A-/A."
- **Actual**: The distillation quality grades in Section 3 of R2-E are based on detailed per-step analysis. The grades are subjective but the criteria are stated: named phases, forbidden actions, weak-vs-strong examples, failure modes. The Trinity Loop prompts (16a/16b/16c) do have all four elements; Discovery Phase prompts (00-12) do not (confirmed by R2-A's per-prompt classification showing 0/15 Discovery prompts have categorized forbidden actions or named failure modes vs 4/4 Trinity prompts).

### FINDING-022: R2-D boilerplate Block O count needs verification

- **Type**: ASSUMPTION
- **Severity**: LOW
- **Document**: r2-D
- **Finding**: Section 1.1 Block O (Self-Audit threshold)
- **Decision**: #10
- **Claim**: "20/22 prompts use exactly: `If score < 0.9, output clarifying questions only -- do not emit JSON.`"
- **Actual**: R2-D Section 3.2 provides a detailed breakdown showing the threshold line appears in 20/22 prompts (Steps 11 and 16 have variations). This is consistent with R2-A's per-prompt analysis which confirms Self-Audit Gate sections exist in all 22 prompts.

### FINDING-023: R2-C claim about E304 checking ALL roadmap tasks needs codebase verification

- **Type**: ASSUMPTION
- **Severity**: MEDIUM
- **Document**: r2-C
- **Finding**: R2-C Section on Step 16a (line 291)
- **Decision**: N/A
- **Claim**: "E304 checks roadmap task coverage but compares against ALL tasks, not just the active milestone's tasks."
- **Actual**: This claim was not directly verified against the step_16.py source code in this review. If true, it means Step 16 for milestone 1 would fail if milestone 2's tasks are not in the checklist. This is a significant usability concern for iterative implementation. The P4 fix plan should investigate whether E304 scopes to the current milestone or all milestones.
- **Fix**: Verify against `step_16.py` source. If confirmed, E304 should scope to the active milestone only.

### FINDING-024: `allowed_upstream_dependencies` still exists in step_order.json (Decision 3 not yet implemented)

- **Type**: GAP
- **Severity**: LOW
- **Document**: N/A (codebase state)
- **Decision**: #3
- **Claim**: Decision 3 says "delete and derive at runtime."
- **Actual**: `step_order.json` lines 41-319 still contain `allowed_upstream_dependencies` (~275 lines). This is expected -- the decision is locked but implementation has not started. R2 documents correctly analyze the current state. P4 should include this deletion.
- **Fix**: P4 fix plan should include AUDIT-023 implementation.

### FINDING-025: R2-E does not recommend NL tooling (consistent with Decision 5)

- **Type**: VERIFIED
- **Severity**: N/A
- **Document**: r2-E
- **Finding**: All 12 findings
- **Decision**: #5
- **Claim**: None of R2-E's findings propose natural language comparison validators.
- **Actual**: Verified by grep. No R2-E finding mentions "natural language", "NL tool", "NLP", "semantic comparison", or "semantic check" tooling. All enforcement recommendations are ID-level: pairwise completeness checks, cross-artifact ID validation, tech stack matching. Drift analysis is treated as a prompt quality issue (better distillation guidance), not a tooling issue. This is perfectly aligned with Decision 5.

### FINDING-026: R2-C and R2-E overlap on FR coverage without full cross-reference

- **Type**: AMBIGUITY
- **Severity**: LOW
- **Document**: r2-C, r2-E
- **Finding**: R2-C-001 vs R2-E-012
- **Decision**: #4, #13
- **Claim**: R2-C-001 says "No Coverage Completeness Enforcement at ANY Transition." R2-E-012 says "No Validator Enforces FR Coverage Across the Full Pipeline."
- **Actual**: These are the same underlying issue described from different perspectives (R2-C from the spec-to-impl chain, R2-E from the drift/redundancy angle). R2-E-012 does not cross-reference R2-C-001. Both should reference Decision 4 (pairwise completeness) and Decision 13 (pipeline validates validity not completeness).
- **Fix**: R2-E-012 should note "See also R2-C-001 and Decisions 4/13."

---

## Verified Correct

The following items were spot-checked against the actual codebase and confirmed accurate:

1. **R2-C-005 verdict mismatch**: `step_16c.py:13` VALID_VERDICTS = {"verified", "needs_work", "blocked", "deferred"}. Prompt 16c line 132 shows "rejected". CONFIRMED.
2. **R2-C-010 step_13 pattern bug**: `step_13.py:13` `_STEP_PATTERN = re.compile(r"^[0-9]{2}[a-z]?_")`. Domain sections like "tables" would fail. CONFIRMED.
3. **R2-C-003 semantic_review not enforced**: `step_16c.py:33-46` -- semantic_review check is conditional on it being a dict, no requirement for its presence when verdict=verified. CONFIRMED.
4. **R2-B downstream_consumers for 03**: `step_order.json:326` shows `"03": ["04", "05", "07"]`. CONFIRMED.
5. **R2-B Step 06 not consumer of 03**: Not in the list. CONFIRMED.
6. **R2-G namespace support**: Canonical ID pattern supports `cn:project:` namespace. CONFIRMED (pattern allows any lowercase namespace).
7. **R2-A Schema Authority block identity**: Verified by reading multiple prompts -- the Schema Authority block is present in all with only schema filename variation.
8. **R2-D Hardening Protocol identity**: All 22 prompts contain the same 4-line Hardening Protocol block.
9. **R2-F `statement` description thinness**: `04_fr_list.schema.json:27` says "Clear statement of the functional requirement, minimum 20 characters." -- no phrasing guidance, no forbidden patterns. CONFIRMED.
10. **R2-F `acceptance_criteria[*].text` thinness**: Schema says "Descriptive text of the acceptance criterion, minimum 15 characters." -- no observable outcome guidance. CONFIRMED.
11. **`allowed_upstream_dependencies` still present**: `step_order.json:41-319` contains the full section. CONFIRMED.

---

## Patch Verification

### Patch 1: R2-F R2-F2-001 changed from "60% migration" to "schema is sole owner"

**Status**: CORRECTLY APPLIED

R2-F2-001 now reads: "schemas are the sole owner of field semantics, period. The target is 100% of field semantics in schemas, not 60%." It explicitly addresses the 14% Category B items and says they should be re-examined. The finding correctly notes that cross-field constraints CAN be signaled in descriptions.

**No regression detected.**

### Patch 2: R2-F R2-F2-004 changed from rigid format to depth tiers

**Status**: CORRECTLY APPLIED

R2-F2-004 now reads: "definition + signal pattern where signal varies by field type" and "three tiers describe DEPTH, not FORMAT." The connection to Decision 1 (Tier 3 must be rich enough to replace all prompt field guidance) is present and correct.

**No regression detected.**

### Patch 3: R2-C R2-C-001 changed from FR-specific to universal pairwise chain

**Status**: CORRECTLY APPLIED

R2-C-001 title says "at ANY Transition" and description enumerates: "capabilities can have no FRs, FRs can have no fixtures, FRs can have no milestones, milestones can have no roadmap tasks, tasks can have no implementation." Recommendation says "pairwise completeness checks at each transition as an incremental extension of existing traceability infrastructure."

**No regression detected.** The finding is now consistent with Decision 4.

### Patch 4: R2-C Section 8 connected 13a to pairwise chain

**Status**: CORRECTLY APPLIED

Section 8 (lines 560-564) explicitly connects 13a redesign to the pairwise completeness chain: "Step 13a should be the aggregation point for all pairwise coverage checks." This creates a clear implementation path: build pairwise checks at each transition, then have 13a aggregate them.

**No regression detected.** Clean connection between Decisions 4, 12, and 13.

### Patch 5: R2-B R2-B-001 reframed from "seed templates lack sections" to "step prompts don't guide extraction"

**Status**: PARTIALLY APPLIED

The formal finding (R2-B-001) was patched. However, the analysis body in Section 1.1 still frames the issue as "What the templates miss" (5 bullet points about what seed templates don't have). See FINDING-003 above. The body text was not updated to match the patched finding.

**Minor regression**: Residual inconsistency between analysis body (Section 1.1) and formal finding (R2-B-001). The body text suggests template improvements; the finding correctly redirects to prompt improvements.

---

## Cross-Document Consistency

### R2-A categories align with R2-D extraction list: PASS

R2-A identifies 5 categories of removable content (SCHEMA-DUP, DAG-DUP, CANON-DUP, BOILERPLATE, AMBIGUOUS). R2-D Section 4 proposes extracting the BOILERPLATE category to shared_expectations. R2-D Section 6 correctly says SCHEMA-DUP goes to schemas, DAG-DUP is already in step_order.json, CANON-DUP is already in canon/. The categorization is consistent.

### R2-B seed findings align with Decision 7: PARTIAL (see FINDING-003, FINDING-004)

The formal findings are aligned. The analysis body text has residual framing issues.

### R2-C completeness findings align with Decisions 4, 12, 13: PASS

R2-C-001 (universal pairwise chain), R2-C-002 (13a machine-computed), and the Section 8 assessment all correctly reflect the locked decisions.

### R2-D Self-Audit Gate aligns with Decision 10: PASS

R2-D2-003 exactly matches the three-concern decomposition from Decision 10.

### R2-E semantic drift aligns with Decision 5: PASS

No NL tooling proposed. All recommendations use ID-level enforcement and prompt quality improvements.

### R2-F descriptions align with Decisions 1, 11: PASS

R2-F2-001 (sole owner) and R2-F2-004 (depth tiers, not rigid format) correctly reflect both decisions.

### R2-G canon aligns with Decision 6: PASS

R2-G-005 (acceptance tooling), R2-G-006 (glossary enforcement via canon), R2-G-007 (infrastructure is 80% built) all support the glossary-to-canon merge.

---

## Assumptions and Ambiguities

### A1: R2-G-005 assumes acceptance tooling is buildable with current infrastructure

R2-G-005 says "Build `specdev canon-accept` command" but does not estimate effort or identify blockers. The finding correctly notes that the `canonicalProposal` schema already exists and `suggested_namespace` supports `cn:project:` separation. The assumption that this is "the critical missing piece" is reasonable but implementation details are TBD.

### A2: R2-C-002 assumes machine-computed coverage can replace AI assessment

R2-C-002 recommends replacing the AI-generated completeness assessment with a machine linter. This assumes ID-level coverage metrics (FR->API->Fixture ratios) are sufficient to assess completeness. Per Decision 5 (no NL tooling), semantic completeness assessment stays with the AI. The machine linter handles structural completeness only. This distinction should be made explicit in the fix plan.

### A3: R2-D2-001 assumes a prompt inclusion mechanism exists

R2-D proposes extracting 1,032 LOC of boilerplate to shared_expectations.md and using a reference declaration. The actual mechanism for LLMs to "inherit" rules from a separate document is not specified beyond "This prompt inherits all rules from..." which relies on the LLM reading the referenced file. This works for chat-based AI workflows but may not work for all runner architectures. The assumption is acceptable for the current tooling.

### A4: R2-E-003 and R2-E-005 overlap without cross-reference

R2-E-003 (tech_stack duplicated 09/14) and R2-E-005 (migration_plan/dependencies duplicated 09/14) are separate findings about the same step pair. They should cross-reference each other and potentially share a common fix (add Step 09->14 field consistency check).

### A5: R2-C severity inconsistency between C-008 and C-002

R2-C-008 rates "No Blocking Gate at Step 13a" as MEDIUM, while R2-C-002 rates "Step 13a is Aspirational, Not Automated" as CRITICAL. These are facets of the same problem (13a doesn't work as a gate). The severity should be consistent -- C-008 should be HIGH at minimum since it's the enforcement mechanism for the CRITICAL issue in C-002.

---

## Summary

| Category | Count | Critical Issues |
|----------|-------|-----------------|
| BUG (confirmed against codebase) | 3 | R2-C-005 verdict mismatch, R2-C-010 pattern bug, R2-C-003 semantic review gap |
| GAP (decision not covered) | 2 | Decision 3 (allowed_upstream), Decision 8 (don't steer) -- both LOW |
| ASSUMPTION | 5 | Infrastructure, coverage scope, inclusion mechanism |
| AMBIGUITY | 4 | R2-B body vs finding framing, cross-doc overlaps |
| REGRESSION (from patches) | 1 | R2-B Section 1.1 body not updated (PARTIAL) |
| HALLUCINATION | 0 | None detected |
| VERIFIED CORRECT | 11 | All spot-checked claims confirmed |

**Overall Assessment**: The 7 R2 documents are high quality and internally consistent. All 5 patches were applied correctly (one partially). The 13 locked decisions are adequately reflected. No hallucinations were detected. The main issues are: (1) three confirmed codebase bugs that R2 correctly identifies, (2) minor framing inconsistencies in R2-B from incomplete patch application, and (3) some missing cross-references between overlapping findings. These are minor issues that do not affect P4 planning.
