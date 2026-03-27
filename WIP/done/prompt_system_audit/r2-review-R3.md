# R2 Document Review -- Round 3 (Final)

**Date**: 2026-03-20
**Reviewer**: Claude Opus 4.6 (1M context)
**Prior Reviews**: r2-review.md (R1: 26 issues, 3 fixes applied), r2-review-R2.md (R2: 6 issues, 1 fix applied)
**Scope**: All 7 R2 documents re-read end-to-end, 13 decisions re-checked, 18 codebase spot-checks

---

## Round 2 Fix Verification

| Fix | Status | Notes |
|-----|--------|-------|
| R2-B line 549 reframe | VERIFIED FIXED | Line 549 now reads: "Step prompts don't guide extraction of compliance, data lifecycle, and operational requirements from seed docs (R2-B-001). These gaps propagate irreversibly." The old "Seed templates lack dedicated sections" phrasing is gone. Correctly reflects Decision 7. |

---

## Summary

| Type | CRIT | HIGH | MED | LOW | Total |
|------|------|------|-----|-----|-------|
| Numeric Inaccuracy | 0 | 0 | 0 | 1 | 1 |
| Completeness Gap | 0 | 0 | 1 | 0 | 1 |
| **Total** | **0** | **0** | **1** | **1** | **2** |

---

## Findings

### FINDING-R3-001: R2-G canon entry count is 74, not 72

- **Type**: Numeric Inaccuracy
- **Severity**: LOW
- **Document**: r2-G-canon-audit.md
- **Location**: Section header "25 kinds, 72 total entries"
- **Claim**: R2-G states "25 kinds, 72 total entries" in the canon inventory header.
- **Codebase**: `grep '"id": "cn:' canon/manifest.json | wc -l` returns 74. All 74 entries use the `cn:core:` namespace (confirmed: `grep 'cn:project:' canon/manifest.json` returns 0 matches). The 25 kinds count is correct (25 files in `canon/kinds/`).
- **Assessment**: The entry count is off by 2. This may be due to entries added after R2-G was written (the branch has unstaged changes to `canon/manifest.json`). It does not affect any finding's validity or severity. The R2-G-001 assessment of auth-domain-specific entries, the R2-G-002 namespace finding, and the R2-G-003 owner validation finding all remain accurate regardless of whether the total is 72 or 74.
- **Fix**: Update the header to "25 kinds, 74 total entries" and adjust the Pre-Population Assessment counts accordingly (likely the extra 2 entries fall into the "must pre-populate" or "sensible defaults" category). No finding changes needed.

### FINDING-R3-002: No R2 finding addresses E304 milestone scoping as an actionable fix

- **Type**: Completeness Gap
- **Severity**: MEDIUM
- **Document**: r2-C-spec-to-impl-integrity.md
- **Location**: Step 16a section (line ~291) and Step 16 section (line ~271)
- **Claim**: R2-C identifies the E304 scope issue twice: "E304 roadmap coverage checks ALL roadmap tasks, not just the current milestone" (Step 16 analysis) and "E304 only fires when a roadmap exists, but the check compares ALL roadmap tasks against the checklist, not just the active milestone's tasks" (Step 16a analysis). R1 review FINDING-023 also flagged this as needing codebase verification.
- **Codebase verification**: Confirmed against `tools/specdev_tools/validation/validators/step_16.py` lines 304-338. The code iterates `for milestone in roadmap_data.get("milestones", []) for task in milestone.get("tasks", [])` -- collecting ALL tasks across ALL milestones. There is no filtering by active milestone.
- **Assessment**: This is mentioned as an observation in two places within R2-C but never captured as a numbered finding with severity, file path, and proposed fix. It is a real usability bug: iterative implementation (one milestone at a time) would fail E304 because tasks from future milestones are not yet in the checklist. R2-C Section 3 (Trinity Loop Deep Dive) calls it a "potential issue for iterative implementation" but stops short of making it actionable. R1-review FINDING-023 noted it needs verification but did not escalate it to a finding either. R2-review had no finding on it.
- **Proposed fix for R2-C**: Add a numbered finding R2-C-012 (or equivalent):
  - **Title**: E304 Compares Against ALL Roadmap Tasks Instead of Active Milestone
  - **Location**: `tools/specdev_tools/validation/validators/step_16.py` lines 313-318
  - **Severity**: MEDIUM
  - **Description**: E304 collects task IDs from all milestones in `14_roadmap.json`, not just the milestone being implemented. This makes iterative Trinity Loop execution impossible without deferred-status workarounds.
  - **Recommendation**: Filter `roadmap_task_ids` to only include tasks from milestones matching the current `milestone_ref` in the checklist, or from milestones whose `status` is not "done".

---

## Codebase Spot-Checks (18 items)

| # | Claim | Source | File Checked | Result |
|---|-------|--------|--------------|--------|
| 1 | Total prompt LOC = 5,727 | R2-A summary table | `wc -l prompts/prompt_*.md` | CONFIRMED: 5727 total |
| 2 | Prompt 00 = 245 LOC | R2-A per-prompt table | `wc -l prompts/prompt_00_project_charter.md` | CONFIRMED: 245 |
| 3 | Prompt 14 = 322 LOC | R2-A per-prompt table | `wc -l prompts/prompt_14_roadmap.md` | CONFIRMED: 322 |
| 4 | Prompt 11 = 254 LOC | R2-A per-prompt table | `wc -l prompts/prompt_11_redteam.md` | CONFIRMED: 254 |
| 5 | VALID_VERDICTS = {verified, needs_work, blocked, deferred} | R2-C-005 | `step_16c.py` line 13 | CONFIRMED |
| 6 | Prompt 16c says "rejected" as verdict | R2-C-005 | `prompt_16c_impl_reviewer.md` line 134 | CONFIRMED |
| 7 | _STEP_PATTERN = `^[0-9]{2}[a-z]?_` | R2-C-010 | `step_13.py` line 13 | CONFIRMED |
| 8 | semantic_review check is conditional on isinstance(dict) | R2-C-003 | `step_16c.py` lines 34-35 | CONFIRMED: no presence requirement for verified verdict |
| 9 | downstream_consumers["03"] = ["04", "05", "07"] | R2-B | `step_order.json` line 326 | CONFIRMED |
| 10 | downstream_consumers["02a"] = ["12"] only | R2-B | `step_order.json` line 325 | CONFIRMED |
| 11 | Glossary schema has no lifecycle_states field | R2-B-009 | `schema/03_glossary.schema.json` lines 21-64 | CONFIRMED: fields are term_id, term, acronym, definition, domain, units, term_ref, acronym_ref, unit_ref |
| 12 | Prompt 06 references lifecycle states from glossary | R2-B-009 | `prompt_06_invariants.md` lines 50, 56, 72 | CONFIRMED: "lifecycle states" referenced 3 times |
| 13 | Charter schema required = [problem_statement, success_metrics, stakeholders, user_segments] | R2-B-003 | `schema/00_charter.schema.json` lines 182-186 | CONFIRMED: in_scope, out_of_scope, assumptions, risks NOT required |
| 14 | FR schema minItems:2 for acceptance_criteria | R2-B-014 | `schema/04_fr_list.schema.json` line 46 | CONFIRMED: minItems: 2 |
| 15 | Step 05 schema does NOT require trace | R2-B-013 | `schema/05_interface_contracts.schema.json` lines 170-177 | CONFIRMED: required = [api_id, name, version, protocol, owner, interface_ref] |
| 16 | Owner uses regex pattern, not enum | R2-G-003 | `schema/core/atoms.schema.json` lines 38-42 | CONFIRMED: pattern `^[a-z][a-z0-9_-]*$`, no enum constraint |
| 17 | Canon manifest has 74 entries, all cn:core: | R2-G | `canon/manifest.json` | 74 entries (R2-G says 72 -- MINOR DISCREPANCY, see FINDING-R3-001) |
| 18 | E304 collects ALL milestone tasks | R2-C E304 analysis | `step_16.py` lines 313-318 | CONFIRMED: iterates all milestones, no active-milestone filter |

**17 of 18 spot-checks passed. 1 minor numeric discrepancy (R2-G entry count: 74 vs claimed 72).**

---

## P4 Actionability Assessment

All major findings across the 7 R2 documents are actionable for P4. The two prior reviews confirmed this extensively and I concur. Specifically:

**Fully P4-ready findings** (names files, describes changes):
- R2-A-001 through R2-A-012: content classification with DELETE/EXTRACT/KEEP actions
- R2-B-001 through R2-B-016: per-step findings with file paths and proposed fixes
- R2-C-001 through R2-C-011: validator gaps with E-code proposals and file paths
- R2-D2-001 through R2-D2-008: shared_expectations design with block-by-block extraction plan
- R2-E-001 through R2-E-012: drift and redundancy findings with enforcement proposals
- R2-F Section 6: concrete before/after migration examples for 10 schema fields
- R2-G-001 through R2-G-007: canon infrastructure findings with specific tooling proposals

**Findings needing P4 design decisions** (observations without single-file fixes):
- R2-E-006 (consumed third-party API contracts): needs decision on new step vs extension
- R2-E-007 (scattered security model): needs consolidation decision
- R2-E-008 (no data model artifact): needs decision on pipeline scope

These are appropriately flagged in R2-E as MEDIUM-severity observations, not as code fixes. P4 can classify them as "prompt enrichment" or "future pipeline extension" without blocking.

**One finding from this review needing P4 attention**:
- FINDING-R3-002 (E304 milestone scoping): needs a fix in `step_16.py` to filter by active milestone. This is directly actionable: modify the task collection loop to scope to the current milestone_ref.

---

## Decision Consistency Verification (Fresh Pass)

| # | Decision | Status | Evidence |
|---|----------|--------|----------|
| 1 | Schema sole owner | PASS | R2-F2-001 says "sole owner"; R2-A counts 500 LOC SCHEMA-DUP for deletion; R2-D2-004 says schema-dup goes to schemas not shared_expectations |
| 2 | Cross-step from DAG | PASS | R2-A counts 69 LOC DAG-DUP for deletion; R2-D Section 6.2 says derivable from downstream_consumers |
| 3 | allowed_upstream delete | PASS (gap noted in R1) | No R2 finding explicitly covers this; AUDIT-023 covers it per R1 FINDING-001 |
| 4 | Universal pairwise chain | PASS | R2-C-001 says "at ANY Transition"; R2-E-012 says "Full Pipeline" |
| 5 | No NL tooling | PASS | R2-E proposes only ID-level enforcement; R2-E-002 explicitly says "No NL tooling needed (Decision 5)" |
| 6 | Glossary to canon | PASS | R2-G-005/006 address infrastructure; R2-E-002 cross-references Decision 6 and R2-G |
| 7 | Seeds are PRD | PASS | R2-B Section 1.1 correctly reframed; R2-B-001 correctly reframed; R2-B summary line 549 now fixed |
| 8 | Don't steer agents | PASS | Process meta-decision; all R2 documents show evidence-based analysis |
| 9 | Schema enrichment first | PASS | R2-D2-008 explicitly states correct ordering |
| 10 | Self-Audit decomposition | PASS | R2-D2-003 exactly matches three-concern decomposition |
| 11 | No rigid format | PASS | R2-F2-004 says "depth tiers, not format" |
| 12 | 13a machine-computed | PASS | R2-C-002 and R2-C Section 8 propose machine-computed coverage |
| 13 | Pipeline validity not completeness | PASS | R2-C-001 proposes pairwise as extension of existing infrastructure |

All 13 decisions are consistently reflected across all 7 R2 documents. No contradictions found.

---

## Cross-Document Coherence

- **R2-A and R2-D boilerplate LOC**: R2-A says 1,312; R2-D inventory says ~1,226; R2-D extractable says ~1,032. R2 review noted this as FINDING-R2R2-005 (LOW). The numbers are consistent when accounting for subset-applicable blocks with step-specific overrides. No change needed.
- **R2-C-001 and R2-E-012 overlap**: Same underlying issue (no coverage completeness enforcement). R2-E-002 now cross-references R2-G-005/006 per R1 fix. R2-E-012 still does not cross-reference R2-C-001, as noted in R1 FINDING-026 (LOW). Acceptable for P4 consolidation.
- **R2-F migration examples and R2-A SCHEMA-DUP counts**: R2-F identifies 58 movable items across 7 sampled schemas. Extrapolating to all 22 is consistent with R2-A's 500 LOC total.
- **R2-G glossary findings and R2-E glossary findings**: R2-E-002 cross-references R2-G-005, R2-G-006, Decision 5, Decision 6. Consistent.

No new cross-document contradictions found.

---

## Verdict

**The R2 document set is ready for consolidation and P4.**

Justification:

1. **Decision alignment is complete.** All 13 decisions are consistently reflected. The last Decision 7 violation (R2-B summary line 549) was fixed between R2 and R3.

2. **Prior fixes verified.** The R1 fixes (3 patches) and R2 fix (1 patch) are all confirmed applied with no regressions.

3. **New findings are minimal and low-impact.** This round found 2 issues: one numeric inaccuracy (74 vs 72 canon entries, LOW) and one completeness gap (E304 milestone scoping not captured as a numbered finding, MEDIUM). Neither blocks consolidation.

4. **Codebase verification is strong.** 17 of 18 spot-checks passed with only 1 minor numeric discrepancy. All bug claims (verdict mismatch, step_13 pattern, semantic_review enforcement gap, E304 scope) are codebase-confirmed.

5. **P4 actionability is high.** Every major finding across all 7 documents names specific files and describes concrete changes. The 3 findings needing design decisions are correctly flagged as MEDIUM observations.

6. **Diminishing returns.** R1 found 26 issues (3 fixes). R2 found 6 issues (1 fix). R3 found 2 issues (0 fixes needed before consolidation). The review cycle has converged.

**Recommendation**: Apply FINDING-R3-001 (update R2-G entry count from 72 to 74) as a trivial text fix. Note FINDING-R3-002 (E304 milestone scoping) as a P4 task. Proceed to consolidation.
