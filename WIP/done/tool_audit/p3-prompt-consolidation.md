# P3: Consolidation + WIP Cross-Check

Agent Type: general-purpose
**READ-ONLY -- do NOT modify source files. Write ONLY to the output file.**
Repo Root: /Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/

---

## Objective

Merge all P1 + P2 findings into a deduplicated, severity-ranked master findings document. Cross-check against existing WIP review findings to identify confirmations, contradictions, and gaps.

---

## Prerequisites

Runs AFTER P1 (7 agents x 2 containers = 14 output files) and P2 (1 agent x 2 containers = 2 output files) complete.

---

## Inputs -- New Findings (16 files from P1 + P2, 8 per container)

### Container A

- `WIP/tool_audit/p1-out-structure.md`
- `WIP/tool_audit/p1-out-dry-validators.md`
- `WIP/tool_audit/p1-out-soc-linters.md`
- `WIP/tool_audit/p1-out-hardcoding.md`
- `WIP/tool_audit/p1-out-test-quality.md`
- `WIP/tool_audit/p1-out-error-collection.md`
- `WIP/tool_audit/p1-out-gaps-regressions.md`
- `WIP/tool_audit/p2-out-research-alignment.md`

### Container B

- `WIP/tool_audit/p1-out-structure-B.md`
- `WIP/tool_audit/p1-out-dry-validators-B.md`
- `WIP/tool_audit/p1-out-soc-linters-B.md`
- `WIP/tool_audit/p1-out-hardcoding-B.md`
- `WIP/tool_audit/p1-out-test-quality-B.md`
- `WIP/tool_audit/p1-out-error-collection-B.md`
- `WIP/tool_audit/p1-out-gaps-regressions-B.md`
- `WIP/tool_audit/p2-out-research-alignment-B.md`

---

## Inputs -- Existing WIP (10 files from prior review cycle; note: `tools-tests-review-goal.md` is a planning document, not findings -- exclude it)

- `WIP/tools-tests-review-findings-cli-package.md`
- `WIP/tools-tests-review-findings-config-imports.md`
- `WIP/tools-tests-review-findings-hardcoded.md`
- `WIP/tools-tests-review-findings-pipeline.md`
- `WIP/tools-tests-review-findings-test-quality.md`
- `WIP/tools-tests-review-findings-test-structure.md`
- `WIP/tools-tests-review-findings-validation-arch.md`
- `WIP/tools-tests-review-findings-validators-dry.md`
- `WIP/tools-tests-review-plan-c1.md`
- `WIP/tools-tests-review-impl-review-c1.md`

---

## Inputs -- Baseline

- `WIP/tool_audit/p0-ground-truth-FINAL.md`

Key baseline numbers for reference:
- **830** tests collected, 830 passed, 0 failures
- **61** source files in specdev_tools/, **13,228** LOC
- **73** test files, **17,709** LOC (50 unit + 21 integration + 2 conftest)
- **23** `_load_*` functions across validators/
- **21** step validator files, **21** DEEP_VALIDATORS entries
- **77** error codes (52 E-codes, 25 W-codes, 18 PROMOTABLE_PAIRS)
- **29** schema registry entries, **22** steps, **25** CLI subcommands
- **133** test fixture files across **22** fixture directories

---

## Tasks

### Task 1: Deduplicate New Findings (Dual-Container Reconciliation)

- Read all 16 P1/P2 output files (8 from Container A, 8 from Container B).
- Assign sequential IDs: `AUDIT-001`, `AUDIT-002`, ... (3-digit, zero-padded).
- **Dual-Container Reconciliation Rules:**
  - When A and B both report the same finding: mark as **corroborated**. Keep the version with more detail.
  - When A and B disagree on severity: resolve to the higher severity unless the lower-severity version provides evidence-based justification.
  - When only one container found a finding: mark as **verified genuine** if valid, with a note on which container missed it.
- **Source attribution format:** `A:{id}, B:{id}; C:{resolution}` (e.g., `A:DV1, B:DV1; C:corroborated` or `A:SL2; C:verified genuine, B missed`).
- Each AUDIT-NNN gets: Source (which P1/P2 file(s) + container attribution), Category, Location (file path), Description, Recommendation.
- **Category values:** Use descriptive UPPER_SNAKE_CASE categories. Examples: `DRY_VIOLATION`, `BUG`, `COVERAGE_GAP`, `HARDCODED_VALUE`, `SOC_BREACH`, `LAYER_VIOLATION`, `REGISTRY_INCONSISTENCY`, `SCHEMA_VALIDATOR_MISMATCH`, `REDUNDANCY`, `CODE_HEALTH`, etc.
- **False positives:** Identify findings that are incorrect, not actionable, or positive confirmations. Document in a "Dropped Findings" table with reason (FALSE_POSITIVE, NOT_A_FINDING, or EXCLUDED).

### Task 2: Cross-Check Against WIP

- Read all 10 WIP files.
- For each WIP finding, match by topic/description against AUDIT-NNN items. WIP files have no structured IDs -- match on content. In the WIP Cross-Check Report, report at the **file-level aggregate** (total items per file and how many confirmed/contradicted/stale/missed) rather than one row per individual bullet. This keeps the report manageable.
- Classify each WIP finding as one of:
  - **CONFIRMED**: Independently found by P1/P2 audit. Link to AUDIT-NNN.
  - **CONTRADICTED**: P1/P2 evidence shows WIP finding is incorrect or outdated.
  - **STALE**: WIP finding references code/patterns that no longer exist.
  - **MISSED_BY_AUDIT**: Valid WIP finding not covered by any P1/P2 agent. Add as new AUDIT-NNN entry.

### Task 3: Severity Ranking

Assign each AUDIT-NNN exactly one severity:
- **CRITICAL**: Breaks functionality, data loss, security issue
- **HIGH**: >50 LOC DRY violation, missing critical test coverage, architectural concern
- **MEDIUM**: Moderate code quality issue, partial DRY violation, inconsistency
- **LOW**: Style issues, naming conventions, minor inconsistency
- **INFO**: Observations, documentation notes, future considerations

### Task 4: Group by Target File

Create a table mapping each target file to its AUDIT-NNN findings. This enables one-task-per-file fix execution in P4.

---

## Output

**Write to:** `WIP/tool_audit/p3-out-master-findings.md`

### Required Structure

```
# P3: Master Findings

## Summary
- Total findings: NN
- By severity: CRITICAL: N, HIGH: N, MEDIUM: N, LOW: N, INFO: N
- From P1/P2: NN unique after deduplication (from NN A + NN B raw findings)
- From WIP cross-check: N confirmed, N contradicted, N stale, N missed_by_audit (added)
- Dropped: N false positives

## Findings by Severity

### CRITICAL
#### AUDIT-001: [Title]
- **Source:** p1-out-xxx.md
- **Category:** [UPPER_SNAKE_CASE, e.g. DRY_VIOLATION|BUG|COVERAGE_GAP|HARDCODED_VALUE|SOC_BREACH|etc.]
- **Location:** tools/specdev_tools/path/to/file.py
- **Description:** ...
- **Recommendation:** ...
- **WIP Status:** CONFIRMED (WIP ref) | NEW | MISSED_BY_AUDIT -- added from WIP:xxx

[repeat for each finding, grouped by severity]

## Findings by Target File

| Target File | Findings | Severities |
|-------------|----------|------------|
| tools/specdev_tools/validation/validators/step_XX.py | AUDIT-001, AUDIT-005 | HIGH, MEDIUM |
| ... | ... | ... |

## Dropped Findings (False Positives)

| # | Source | Original ID | Reason | Classification |
|---|--------|-------------|--------|----------------|
| 1 | p1-out-xxx.md | A:XX / B:XX | [why dropped] | FALSE_POSITIVE / NOT_A_FINDING / EXCLUDED |
| ... | ... | ... | ... | ... |

## Research Alignment Gaps

Strategic items from P2 that inform P4 batch 5 but are not AUDIT-NNN findings.

| ID | Gap | Current State | Quick Win | Related AUDIT |
|----|-----|--------------|-----------|---------------|
| ALIGN-1 | [description] | [current state] | YES / NO / Partial | AUDIT-NNN or n/a |
| ... | ... | ... | ... | ... |

## WIP Cross-Check Report

| WIP File | Total Items | CONFIRMED | CONTRADICTED | STALE | MISSED_BY_AUDIT | Notes |
|----------|-------------|-----------|--------------|-------|-----------------|-------|
| findings-validators-dry.md | NN | NN | NN | NN | NN | ... |
| ... | ... | ... | ... | ... | ... | ... |
```

**Target length:** 500-700 lines. Concise but thorough -- every finding gets an ID, every WIP item gets a status.
