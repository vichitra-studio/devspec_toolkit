# P3-v2 Master Findings Review

**Date**: 2026-03-20
**Reviewer**: Deep Review Agent
**Document reviewed**: p3-out-master-findings-v2.md (101 findings)
**Source documents**: 7 R2 docs + P3 v1 (66 findings)

## Summary

- Total issues found: 32
- Critical: 5 (must fix before P4)
- Important: 14 (should fix before P4)
- Minor: 13 (can fix during P4)

---

## A. Coverage Gaps

### A.1 P1 Findings Missing from Cross-Reference Table

The v2 cross-reference table omits several P1 finding IDs that appear in the v1 document:

1. **P1-E #10 (Step 09 mis-sequencing)**: V1 maps this to "AUDIT-014 (sub-point)" but v2 cross-reference table skips P1-E #10, #11, #12, #13 entirely. These are listed in v1 but absent from the v2 cross-reference table (lines 1217-1227 skip from P1-E #9 directly to P1-E #14).
   - **Severity**: Minor -- the findings themselves ARE represented (as sub-points of AUDIT-014, AUDIT-032, AUDIT-015, AUDIT-013), but the cross-reference table is incomplete.

2. **P1-G #15 (governance_arch unreferenced)**: Present in v1 cross-reference (maps to AUDIT-025) but absent from v2 cross-reference table.
   - **Severity**: Minor -- finding is represented via AUDIT-025.

### A.2 R2 Findings: All 7 Documents Covered

Systematic mapping confirms all R2 findings are represented:

- **R2-A**: 12 findings (R2-A-001 through R2-A-012) -- all mapped in v2 cross-reference table (lines 1263-1274). Complete.
- **R2-B**: 16 findings (R2-B-001 through R2-B-016) -- all mapped (lines 1275-1290). Complete.
- **R2-C**: 12 findings (R2-C-001 through R2-C-012) plus E304 -- all mapped (lines 1291-1303). Complete.
- **R2-D**: 10 findings (R2-D2-001 through R2-D2-010) -- all mapped (lines 1304-1313). Complete.
- **R2-E**: 12 findings (R2-E-001 through R2-E-012) -- all mapped (lines 1314-1325). Complete.
- **R2-F**: 8 findings (R2-F2-001 through R2-F2-008) -- all mapped (lines 1326-1333). Complete.
- **R2-G**: 7 findings (R2-G-001 through R2-G-007) -- all mapped (lines 1334-1340). Complete.

**No R2 findings are dropped or lost.**

### A.3 P1 Findings Preservation

V1 had 66 findings (AUDIT-001 through AUDIT-066). V2 states 57 from P1, with 9 subsumed. However, the document says AUDIT-067 through AUDIT-103 (37 findings), but numbering only goes to AUDIT-101. This is an off-by-one or numbering gap:

- **CRITICAL (numbering)**: The summary table (line 21) says "AUDIT-067 through AUDIT-103" but the highest finding is AUDIT-101. There is no AUDIT-102 or AUDIT-103. The count of 37 "genuinely new" does not match. The actual new findings are AUDIT-067 through AUDIT-101 = 35 new findings, not 37. The math: 57 (P1) + 35 (R2 new) + 7 (merged R2 updates) = 99, not 101. Two findings seem unaccounted for, or the count in the summary is wrong.
  - **Severity**: Important -- the summary statistics are inconsistent with the actual document content and will confuse P4 planning.

### A.4 Missing R2-B Finding: R2-B-016

R2-B does not explicitly have a finding numbered R2-B-016 in the source document. The v2 cross-reference says "R2-B-016 (seed_manifest stops at 04)" mapped to AUDIT-082. However, reviewing the R2-B source document, there is no finding explicitly labeled R2-B-016. This appears to be an observation from the per-step analysis (section 1.5, discussing how `step_requirements` only covers steps 00-04) that was promoted to a finding during consolidation.
- **Severity**: Minor -- the content is valid, but the source ID is fabricated rather than drawn from an explicit finding in R2-B.

---

## B. Decision Consistency Issues

### B.1 AUDIT-075 May Conflict with Schema Evolution Practice

AUDIT-075 proposes adding `in_scope`, `out_of_scope`, `assumptions`, `risks` to the charter schema `required` array. This is a **breaking change** -- any existing valid charter that omits these fields would fail validation after the change. The finding does not note this as a regression risk or propose a migration path.
- **Severity**: Important -- needs migration plan or deprecation period note.
- **Related decisions**: None of the 13 decisions explicitly address this. Decision 13 (pipeline validates validity not completeness) could arguably push back on making these required, since they could be seen as completeness concerns rather than validity.

### B.2 AUDIT-069 Batch Assignment May Be Wrong

AUDIT-069 (semantic review not enforced for verified verdict) is assigned to **Batch 7** (validators). However, AUDIT-004 (roadmap deliverable completion not enforced, also a step 16c validator issue) is in **Batch 5** (pairwise completeness). Both are Step 16c validator bugs with similar character. AUDIT-069 is a CRITICAL finding in Batch 7 while AUDIT-004 (also CRITICAL) is in Batch 5. The inconsistency in batch placement means the most critical validation bug (AUDIT-069, a pure codebase bug) will be fixed AFTER more complex pairwise completeness work.
- **Severity**: Important -- AUDIT-069 is a simple bug fix that should be in an earlier batch.

### B.3 AUDIT-016 Proposed Fix Is Incomplete Given Decision 5

AUDIT-016 proposes "Strengthen prompt guidance for Steps 05, 06, 07 to say 'use exact description text from Step 04 for traced FRs.'" This is consistent with Decision 5 (no NL tooling). However, "use exact description text" is impractical -- an API's name and an FR's statement are inherently different text. The fix should specify what "exact text" means (e.g., "the FR ID and its `statement` must appear verbatim in the API's trace `note` field").
- **Severity**: Minor -- ambiguous fix wording.

### B.4 AUDIT-086 Owner Validation Approach Needs Clarification

AUDIT-086 says "Either enforce owner values against canon (preferred) or add enum constraint to schema." The proposed fix of enforcing against canon is consistent with the overall canon strategy, but the current `atoms#owner` uses a regex pattern (`^[a-z][a-z0-9_-]*$`). Converting this to canon-enforcement requires the canonical-lint infrastructure to check ALL `owner` fields in ALL specs, which is a larger change than adding an enum. The finding understates implementation complexity.
- **Severity**: Minor -- implementation note needed.

### B.5 Decision 3 Implementation Note

AUDIT-023 says to "Delete the JSON field" for `allowed_upstream_dependencies`, consistent with Decision 3. The codebase check confirms the field still has content (line 41 of step_order.json). The batch assignment (Batch 1) is correct. No issues found.

---

## C. Hallucinations

### C.1 AUDIT-075 Charter Schema Required Array -- VERIFIED CORRECT

The finding claims schema requires only `problem_statement`, `success_metrics`, `stakeholders`, `user_segments`. Codebase verification at `schema/00_charter.schema.json:182-186` confirms this is correct -- `in_scope`, `out_of_scope`, `assumptions`, `risks` are NOT in the `required` array. The finding is accurate.

### C.2 AUDIT-069 Semantic Review Enforcement -- VERIFIED CORRECT

Codebase check of `step_16c.py` confirms: line 34-35 uses `semantic_review = review.get("semantic_review")` followed by `if isinstance(semantic_review, dict):`. If absent, block is skipped. No error for missing semantic_review when verdict=verified. Finding is accurate.

### C.3 AUDIT-076 Verdict Mismatch -- VERIFIED CORRECT

`step_16c.py` line 13: `VALID_VERDICTS = frozenset({"verified", "needs_work", "blocked", "deferred"})`. "rejected" is not in this set. Finding is accurate.

### C.4 AUDIT-084 Trace Optional in Step 05 -- VERIFIED CORRECT

`schema/05_interface_contracts.schema.json:170-177` has `required: ["api_id", "name", "version", "protocol", "owner", "interface_ref"]`. `trace` is NOT required. Finding is accurate.

### C.5 AUDIT-017 docs_policy Consumers -- VERIFIED CORRECT

Grep confirms only `step_16.py:180` reads `docs_policy.doc_paths`. Finding is accurate.

### C.6 AUDIT-006 LOC Estimate -- POTENTIAL OVERCOUNT

V2 says "1,924 LOC (34%) removable" citing R2-A-003. The R2-A source document (line 318-335) confirms 1312 boilerplate + 500 schema-dup + 69 DAG-dup + 43 canon-dup = 1924. However, the earlier P1 estimate (AUDIT-065 in v1) was ~927 LOC. The R2-A analysis is more detailed and methodical, but the 500 LOC "schema duplication" number includes Field-by-Field sections that will be DELETED (per Decision 1), not "extracted." The finding mixes extraction (to shared_expectations) with deletion (schema-dup, Quick Reference) into a single "removable" count. This is not a hallucination but could be misleading.
- **Severity**: Minor -- clarify distinction between "extract to shared_expectations" (~1312 LOC) and "delete as schema duplication" (~612 LOC).

### C.7 AUDIT-023 -- "275 Lines" Claim

The finding says `allowed_upstream_dependencies` is "275 lines." The codebase has the field starting at line 41 of step_order.json. Given 22 steps with arrays of increasing size, 275 lines is plausible but I did not count precisely. Not flagged as a hallucination.

### C.8 AUDIT-088 E304 All-Roadmap-Tasks Bug

AUDIT-088 claims E304 checks ALL roadmap tasks instead of active milestone. The source (R2-C analysis and r2-review-R3 FINDING-R3-002) provides line references. I did not read step_16.py lines 313-318 directly, but the R2 source documents this as codebase-verified. Likely accurate.

### C.9 AUDIT-093 Step 13 Pattern Bug

The finding claims `step_13.py` checks `required_schema_sections` against a step-format pattern. The R2-C source (R2-C-010) provides this evidence. This should be spot-checked against the actual validator but is labeled "codebase-verified" in R2.

### C.10 No Hallucinations Found in Remaining Spot-Checks

The 10+ findings spot-checked against actual codebase files are all accurate. The document has good evidentiary grounding.

---

## D. Ambiguities

### D.1 AUDIT-067 "Pairwise Completeness" Scope Is Unclear

AUDIT-067 says to implement pairwise completeness checks at "each transition: capability->FR (W-code), FR->fixture (W-code), FR->milestone (W-code), milestone->task (W-code)." But the full chain also includes FR->API, API->fixture, API->scaffold. The finding lists a partial chain. The complete chain from R2-C-001 is: capability->FR, FR->API, FR->fixture, FR->milestone, milestone->task. The finding is ambiguous about which transitions are in scope.
- **Severity**: Important -- P4 needs a definitive list of pairwise checks to implement.

### D.2 AUDIT-068 "Blocking Gate" Mechanism Undefined

AUDIT-068 proposes "Add blocking threshold in step_order.json or CI gates" but does not specify HOW this works. step_order.json has no concept of blocking gates today -- it defines ordering and replay policy. This is a new capability that needs design, not just a finding.
- **Severity**: Important -- needs design decision or at minimum a note about scope.

### D.3 AUDIT-091 Relationship to AUDIT-006 and AUDIT-026 Is Confusing

AUDIT-091 (shared_expectations design, 82 LOC, 11 sections) overlaps heavily with AUDIT-006 (extractable boilerplate) and AUDIT-026 (shared_expectations lacks doc guidance). All three are in Batch 2. It is unclear whether AUDIT-091 is the "design spec" for the work described by AUDIT-006 and AUDIT-026, or a separate finding.
- **Severity**: Minor -- add a note clarifying AUDIT-091 is the design blueprint; AUDIT-006 provides the extraction list; AUDIT-026 provides the content gaps.

### D.4 AUDIT-071 Scope Is Very Broad

AUDIT-071 says "All step schemas (7 analyzed in detail, all 22 need review)" and the fix is to enrich ALL schema descriptions. This is an enormous amount of work (925 descriptions to review). The batch assignment (Batch 0) implies this happens first, before everything else. The finding should clarify whether Batch 0 means enriching ALL 925 descriptions or a targeted subset (e.g., Tier 3 semantic fields first).
- **Severity**: Important -- Batch 0 scope needs explicit scoping or it becomes a multi-week blocker.

---

## E. Duplicates / Conflicts

### E.1 AUDIT-036 Is Subsumed by AUDIT-026

AUDIT-036 ("shared_expectations.md referenced by only 8 of 22 prompts") is explicitly marked "[Subsumed by AUDIT-026]" (line 544). Yet it still has its own finding entry, batch assignment (Batch 2), and proposed fix. This creates confusion -- is it a live finding or not? If subsumed, it should be marked as such without its own batch assignment.
- **Severity**: Minor -- clarify that AUDIT-036 is subsumed and will be resolved by AUDIT-026. Remove from batch counting.

### E.2 AUDIT-040 and AUDIT-008 Overlap on Output Contract Examples

AUDIT-040 (Output Contract examples contradict guidance) proposes "DELETE Quick Reference and Field-by-Field sections" AND "Fix remaining Output Contract examples." AUDIT-008 (Quick Reference is schema duplication) also proposes deletion of Quick Reference. Both are partly in Batch 0 and partly in Batch 4. The overlap is acknowledged but the execution plan for Batch 4 will need to merge these.
- **Severity**: Minor -- not a conflict, just needs coordination note in P4.

### E.3 AUDIT-053 and AUDIT-095 Overlap on Stage/Environment

AUDIT-053 (stageName and environmentName identical enum, unclear distinction) is in Batch 0. AUDIT-095 (stage/environment triple-maintained) is in Batch 3. Both address the same root problem. AUDIT-095's fix (consolidate to single source) subsumes AUDIT-053's fix (clarify distinction OR consolidate). If Batch 3 consolidates them, Batch 0's clarification work is wasted.
- **Severity**: Important -- either move AUDIT-053 to Batch 3 to coordinate with AUDIT-095, or scope AUDIT-053 as description-only with a note that Batch 3 may consolidate.

### E.4 AUDIT-082 and AUDIT-034 Overlap on Step 02a Consumption

AUDIT-082 (02a near-zero downstream consumption) proposes updating `downstream_consumers` to include Steps 04-07. AUDIT-034 (tech stack consistency across steps) proposes adding a tech-stack coherence check. Both address the same root issue (delivery baseline information not flowing downstream). The fixes are complementary but should reference each other.
- **Severity**: Minor -- add cross-reference.

---

## F. Regression Risks

### F.1 AUDIT-075 Adding Required Fields to Charter Schema

Adding `in_scope`, `out_of_scope`, `assumptions`, `risks` to the charter schema's `required` array will break validation for any existing charter that omits these fields. The test fixtures at `tests/fixtures/step_00/` may need updating.
- **Severity**: Important -- needs fixture update plan.

### F.2 AUDIT-084 Adding `trace` to Step 05 Required Array

Adding `trace` to the Step 05 API items' `required` array will break any existing API contract JSON that lacks trace links. The existing test fixture at `tests/fixtures/step_05/valid_rest_api.json` may or may not include trace.
- **Severity**: Important -- needs fixture verification.

### F.3 AUDIT-023 Deleting `allowed_upstream_dependencies`

Deleting the `allowed_upstream_dependencies` field from step_order.json affects 5 consumers (the finding lists: `cli.py`, `hallucination_lint.py`, `extraction_intent_check.py`, `dependency_order_lint.py`, `dag_lint.py`). All must be migrated atomically. If any consumer is missed, it will fail with a KeyError at runtime.
- **Severity**: Important -- needs atomic migration with test coverage for all 5 consumers.

### F.4 AUDIT-017 Removing `docs_policy` Block

Removing `docs_policy` from seed_manifest requires updating `step_16.py:180` to read `doc_paths` from the new location. The test at `tests/fixtures/seed_manifest/` needs updating. Existing host repos using `docs_policy` in their seed_manifest.json will fail schema validation.
- **Severity**: Important -- breaking change for host repos. Needs migration guide or deprecation.

### F.5 AUDIT-071 Schema Description Enrichment

Enriching schema descriptions is additive and should not break tests. However, if any test asserts exact schema content (e.g., checking description strings), it could fail. The test at `tests/unit/canonical/test_canon_schema_alignment.py` may check schema structure.
- **Severity**: Minor -- low risk but verify no description-asserting tests exist.

---

## G. Batch Assignment Issues

### G.1 AUDIT-069 (CRITICAL) in Batch 7 Is Too Late

AUDIT-069 is a CRITICAL codebase bug (semantic_review not enforced for verified verdict). It is a ~10 LOC fix in `step_16c.py`. Assigning it to Batch 7 (validators, which depends on nothing) means a critical bug sits unfixed through 6 prior batches. This should be Batch 1 at the latest, or moved to a "hot-fixes" batch.
- **Severity**: Critical -- a CRITICAL finding should not wait for Batch 7.

### G.2 AUDIT-076 (MEDIUM, Codebase Bug) in Batch 7

AUDIT-076 (verdict enum mismatch) is another simple codebase bug. It requires changing either the prompt or the validator to synchronize enum values. This could be fixed in any early batch since it has no dependencies.
- **Severity**: Important -- should be Batch 1 or a hot-fix batch.

### G.3 AUDIT-093 (LOW, Codebase Bug) in Batch 7

AUDIT-093 (Step 13 schema section pattern bug) is a codebase-verified bug where valid input fails validation. Should be fixed early.
- **Severity**: Minor -- less urgent due to LOW severity, but still a bug that produces false positives.

### G.4 AUDIT-088 (MEDIUM, Codebase Bug) in Batch 7

AUDIT-088 (E304 checks all roadmap tasks instead of active milestone) is a codebase bug that makes iterative Trinity Loop execution impossible. This blocks practical use of the Trinity Loop.
- **Severity**: Important -- should be earlier than Batch 7 if Trinity Loop is actively used.

### G.5 Batch 0 Scope Risk

Batch 0 contains 17 findings. The most labor-intensive is AUDIT-071 (schema enrichment for all 22 schemas using three-tier DEPTH model). If this means touching all 925 descriptions, Batch 0 becomes a multi-week effort that blocks everything else (per Decision 9). Consider splitting Batch 0 into:
- Batch 0a: Schema structural changes (AUDIT-014, 075, 084, 086 -- adding fields, changing required arrays)
- Batch 0b: Schema description enrichment (AUDIT-071, 051, 052, 053, 054, 055, 057, 066 -- Tier 3 fields first, then Tier 2, then Tier 1)
- Batch 0c: Prompt Quick Reference deletion (AUDIT-008, 040, 041, 042, 043 -- can happen after 0b)
- **Severity**: Critical -- if Batch 0 is monolithic and takes weeks, it delays all 8 subsequent batches.

### G.6 Batch 5 Dependencies

Batch 5 (pairwise completeness) includes AUDIT-015 which adds `fr_refs` to Step 14 task schema. This is a schema change that should arguably be in Batch 0 (schema enrichment). If Batch 5 introduces schema changes after prompts have already been updated (Batch 4), those prompts may reference fields that do not yet exist.
- **Severity**: Important -- AUDIT-015 schema change should move to Batch 0.

### G.7 Batch Execution Order: Batch 3 Before Batch 2?

The batch execution order (line 1360-1368) puts Batch 3 (Glossary -> Canon) before Batch 2 (shared_expectations). This seems reasonable since they are independent. However, Batch 3 requires building new tooling (AUDIT-073: canon-accept command), which is more complex than Batch 2 (editing existing files). If resources are limited, swapping order would be more practical.
- **Severity**: Minor -- optimization suggestion, not a bug.

---

## H. Additional Observations

### H.1 Document Numbering Gap

The document claims AUDIT-001 through AUDIT-101 = 101 findings. But AUDIT IDs skip: there is no AUDIT-102 or AUDIT-103. The summary (line 21) claims "AUDIT-067 through AUDIT-103" which is wrong -- the range is AUDIT-067 through AUDIT-101. The 37 "genuinely new" count should be 35 (67 through 101 inclusive).
- **Severity**: Important -- fix the summary statistics to match actual content.

### H.2 V1 Had AUDIT-001 through AUDIT-066

V1 had findings AUDIT-001 through AUDIT-066 = 66 findings. V2 claims 57 from P1 + 9 subsumed = 66. This checks out. The 9 subsumed findings are not explicitly listed in v2 -- a "subsumed findings" table would help auditability.
- **Severity**: Minor -- add explicit list of the 9 subsumed P1 findings.

### H.3 Batch Count Verification

Summing the batch summary table: 17 + 4 + 7 + 6 + 24 + 6 + 6 + 15 + 15 + 2 = 102. But there are only 101 findings. Some findings appear in multiple batches (e.g., AUDIT-008 in Batch 0 and Batch 4, AUDIT-040 in Batch 0 and Batch 4, AUDIT-006 in Batch 0 and Batch 2). This double-counting inflates the per-batch totals. The batch summary should either: (a) assign each finding to exactly one batch (its primary batch), or (b) explicitly note multi-batch findings.
- **Severity**: Minor -- clarify multi-batch assignment convention.
