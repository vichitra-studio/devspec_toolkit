<review_prompt id="R3" areas="3,5" runs_after="R1,R2" priority="P1-high">
# Review R3: Canonical System — Alias Lifecycle + Cross-Artifact Drift Detection

## Scope
Two areas that share the `canonical/` module and alias resolution logic:
- **Area 5**: Deprecated alias lifecycle — no sunset dates, no escalation, autofix ignores deprecated aliases
- **Area 3**: Semantic drift detection — no partial drift detection, thin validators for complex steps

Fix Area 5 first (alias lifecycle infrastructure), then Area 3 (drift detection depends on correct lifecycle state).

**Prior reviews completed**: R1, R2. Validation infrastructure is sound.

---

## Files Under Review

| File | Area | Key Lines |
|------|------|-----------|
| `tools/specdev_tools/canonical/registry.py` | 5 | 107-108 (alias_is_deprecated), 129 (W110 emission), 135 (W120 emission) |
| `tools/specdev_tools/canonical/autofix.py` | 5 | 129 (resolve_alias, no deprecated logic) |
| `canon/aliases.json` | 5 | full — check structure for lifecycle fields |
| `canon/manifest.json` | 5 | check deprecated_since pattern |
| `tools/specdev_tools/canonical/integrity.py` | 3 | 62-66, 110-114, 162-169, 214-243, 296-300 |
| `tools/specdev_tools/core/errors.py` | 3 | full — add E211 before integrity.py task |
| `tools/specdev_tools/validation/forward_replay_check.py` | 3 | structural vs semantic check verification |
| `tools/specdev_tools/validation/validators/step_04.py` | 3 | full (current LOC — may have changed) |
| `tools/specdev_tools/validation/validators/step_06.py` | 3 | full (current LOC) |
| `tools/specdev_tools/validation/validators/step_07.py` | 3 | full (current LOC) |
| `tools/specdev_tools/validation/validators/step_08.py` | 3 | full (current LOC) |
| `tools/specdev_tools/validation/validators/step_12.py` | 3 | full (current LOC) |
| `tools/specdev_tools/validation/validators/step_13a.py` | 3 | full (current LOC) |
| `tests/test_canonical_integrity.py` | 3 | existing test file — extend for E211 |
| `tests/test_canonical_registry.py` | 5 | existing test file — extend for lifecycle methods |
| `tests/test_error_code_coverage.py` | 3, 5 | existing test file — must pass after E211 added |

---

## Subagent Protocol (MANDATORY)

### Main Agent Rules
- **FORBIDDEN in main agent**: Read, Edit, Write, Grep, Glob, Bash for file content
- Main agent ONLY: spawn subagents, read text summaries, create tasks, final report
- Token budget for main agent: < 5K tokens per session

### Subagent Assignment

#### Phase 1 — Investigation (3 Explore subagents)

**Subagent A** (`Explore`, no isolation) — Canonical Lifecycle Audit:
```
Read these files completely:
1. canon/aliases.json — what fields does each alias entry have? Is deprecated_since or
   sunset_date present in any entry? What status values exist?
2. canon/manifest.json — does it have deprecated_since, sunset_date, or replacement fields?
   What is the deprecation pattern used?
3. tools/specdev_tools/canonical/registry.py lines 100-145
   - alias_is_deprecated() — what does it check? Returns bool only?
   - W110 emission (line 128) — what triggers it? What message?
   - W120 emission (verified: line 135, not 134) — what triggers it? What message?
   - Is there any code path where W110/W120 escalates to an error?
4. tools/specdev_tools/canonical/autofix.py — full file
   - Does line 129 call resolve_alias?
   - Is there ANY logic for deprecated aliases specifically (suggest replacement, warn, etc.)?
Report: exact alias.json schema, exact warning codes with messages, confirm no escalation path exists.
```

**Subagent B** (`Explore`, no isolation) — Drift Detection Audit:
```
Read tools/specdev_tools/canonical/integrity.py fully. Focus on:
1. Lines 62-66, 110-114: E210 CROSS_ARTIFACT_DRIFT error emission points
   - What conditions trigger E210? Quote the exact condition.
   - What is the detection algorithm?
2. Lines 214-243: _collect_observed_semantics() function
   - What data structure does it return? (dict, list, set?)
   - For each collected reference, what fields does it store per artifact?
   - Could it detect PARTIAL drift? (e.g., 2 artifacts updated to new term, 1 still uses old term)
     To answer this: determine if the return value groups references BY ARTIFACT or by term only.
     If grouped by artifact: partial drift detection is feasible (compare per-artifact term usage).
     If grouped by term only: partial drift detection requires restructuring the return value.
3. Lines 162-169: canonical refs mismatch variant — what does this check?
4. Lines 296-300: Unresolved canonical semantic variant
Answer EXPLICITLY:
  (a) Can the current structure detect partial drift without restructuring? YES/NO + reason.
  (b) If NO: what minimal change to _collect_observed_semantics() return structure enables partial drift?
  (c) Estimate lines of code change required (< 20 LOC? 20-50 LOC? > 50 LOC?)
This determines whether E211 partial drift can be added incrementally or requires a larger change.
```

**Subagent C** (`Explore`, no isolation) — Thin Validator Audit:
```
Read all 6 thin validators completely:
- tools/specdev_tools/validation/validators/step_04.py (21 LOC)
- tools/specdev_tools/validation/validators/step_06.py (16 LOC)
- tools/specdev_tools/validation/validators/step_07.py (20 LOC)
- tools/specdev_tools/validation/validators/step_08.py (16 LOC)
- tools/specdev_tools/validation/validators/step_12.py (21 LOC)
- tools/specdev_tools/validation/validators/step_13a.py (17 LOC)
Also read tools/specdev_tools/validation/forward_replay_check.py lines 30-60.
For each validator, answer:
1. What does it actually check?
2. For step_04 (FR list): does it check that fr_ids are referenced in step_05/step_06?
3. For step_06 (invariants): does it check expression validity or just ID uniqueness?
4. For forward_replay_check: does it verify semantic content or only file existence/structure?
Report: for each validator, list what's checked vs what's missing for semantic drift detection.
```

#### Phase 2 — Implementation (after Phase 1)

**Subagent D** (`general-purpose`, isolation: `worktree`) — Alias Lifecycle Infrastructure:
```
Based on Phase 1 findings, implement alias lifecycle enforcement:

1. canon/aliases.json: Add lifecycle fields to each entry.
   VERIFIED STRUCTURE: manifest.json uses `"lifecycle": {"introduced_at": "..."}`.
   aliases.json currently has no lifecycle fields at all (only kind/normalized/target_id/status).
   Define the lifecycle extension as follows — this is a new addition, not a mirror of manifest:
     "lifecycle": {
       "introduced_at": null,       (ISO 8601 date string or null)
       "deprecated_since": null,    (ISO 8601 date string or null; set for deprecated aliases)
       "sunset_date": null,         (ISO 8601 date string or null; set when deprecation expires)
       "replacement": null          (canonical term ID string or null; set for deprecated aliases)
     }
   Add this `lifecycle` block to ALL entries. Set all fields to null for currently active aliases.
   This extends the manifest.json pattern (which uses lifecycle.introduced_at) consistently.

2. tools/specdev_tools/canonical/registry.py:
   - Modify alias_is_deprecated() to also return the sunset_date if present
   - Add alias_is_sunset(alias_key) method: returns True if sunset_date is set and is in the past
   - Modify W120 emission to include sunset_date in the message
   - Add escalation: if alias_is_sunset() is True, emit E-code instead of W120
     (use next available E-code in the E1xx range, or E125 if free)

3. tools/specdev_tools/canonical/autofix.py:
   - Add logic at/near line 129: when resolve_alias() finds a deprecated alias,
     suggest the replacement from aliases.json["replacement"] field
   - Format suggestion as: "Replace deprecated alias '<old>' with canonical '<replacement>'"

Run: pytest tests/ -k canonical -v and confirm pass.
```

**Subagent E** (`general-purpose`, isolation: `worktree`) — Partial Drift Detection:
```
PREREQUISITE: Read Phase 1 Subagent B findings before writing any code.
  - If Subagent B answered (a) YES (feasible without restructuring): proceed with incremental add.
  - If Subagent B answered (a) NO (requires restructuring): implement the minimal structural change
    it described, then add the partial drift check on top.

Based on Phase 1 Subagent B findings, add partial drift detection to canonical/integrity.py:

The core problem: _collect_observed_semantics() gathers all canonical refs across artifacts.
But if 2/3 artifacts use new term and 1/3 still uses old term, this partial inconsistency
may not be caught.

Add partial drift detection:
1. After collecting all observed semantics, group references by conceptual entity
   (same entity referenced with different canonical terms across artifacts)
2. For each group where multiple canonical terms map to the same entity:
   - If the set of terms used is {old_term, new_term} where old_term is deprecated:
     → emit E211 with message indicating partial drift: N artifacts still use old_term
3. E211 error code MUST already exist in core/errors.py (added by T01 in this review).
   If E211 is not in errors.py when you read it, STOP and report the dependency is unmet.

Note: do not redesign the entire drift detection algorithm. Implement exactly the minimal change
described by Phase 1 Subagent B. If Subagent B estimated > 50 LOC change, file an implementation
note and reduce scope to flagging the gap without full fix.

Run: pytest tests/test_canonical_integrity.py -v and confirm pass.
```

**Subagent F** (`general-purpose`, isolation: `worktree`) — Thin Validator Enhancements:
```
Based on Phase 1 Subagent C findings, add semantic checks to the thin validators.
Rules:
- Each validator should remain under 60 LOC (add only what's missing, not a full rewrite)
- Use existing error emission patterns from adjacent validators

Enhancements:
1. step_04.py: Add cross-ref check — verify that FR IDs defined in step 04 are referenced
   by at least one trace entry across the artifact. If an FR has no trace, emit W-code.
2. step_06.py: Add expression validity check — for each invariant expression, verify it
   uses only supported operators (cross-reference with _tiny_eval supported set from R1 fixes).
   Emit warning for expressions with unsupported operators.
3. step_07.py: Add NFR completeness check — verify category and threshold fields are present
   on each NFR item, not just ID uniqueness.
4. step_08.py: Verify fixture target IDs exist in referenced step artifacts (basic referential
   integrity check using spec directory scan).
5. step_12.py: Verify job dependencies in step_12 reference valid job IDs within the same artifact.
6. step_13a.py: Verify impact_scores are in valid range (0.0-1.0) and completeness_scores
   are percentages (0-100).

Run: pytest tests/ -k "step_0" -v and confirm pass.
```

#### Phase 3 — Integration (after Phase 2)

**Subagent G** (`general-purpose`, no isolation):
```
Run full validation suite:
1. pytest tests/ --tb=short -q
2. ./tools/run_specdev.sh canonical-lint canon --repo-root ./devspec_toolkit
3. ./tools/run_specdev.sh canonical-integrity spec --repo-root ./devspec_toolkit
Report: all pass/fail results. Flag any new errors introduced by Phase 2 changes.
```

---

## Investigation Checklist

### Area 5 — Canonical Lifecycle
- [ ] Does aliases.json support deprecated_since/sunset_date/replacement fields?
- [ ] Does alias_is_deprecated() return only bool (no metadata)?
- [ ] Are W110/W120 ever escalated to errors anywhere in the codebase?
- [ ] Does autofix suggest replacements for deprecated aliases?
- [ ] Is orphan detection implemented (canonical terms in manifest never referenced by specs)?

### Area 3 — Semantic Drift
- [ ] Can _collect_observed_semantics() detect partial drift (subset of refs updated)?
- [ ] Does E210 fire when only 1 of N references still uses the old term?
- [ ] Does forward_replay_check verify semantic content or only structural validity?
- [ ] Do step_04/06/07/08/12/13a validators check cross-artifact referential integrity?

---

## Deliverables

> **Format**: Use compact tables from `docs/audit/review_protocol.md`. No verbose prose.

### Part A: Findings
```
| ID | Sev | File:Line | Finding | Impact |
|----|-----|-----------|---------|--------|
| A-R3-01 | CRIT/HIGH/MED/LOW | path:line | description | impact |
```
Evidence blocks (CRIT/HIGH only): exact quoted code, one block per finding.

### Part B: Implementation Plan
Atomic tasks — one file per task. See `review_protocol.md` for sequencing rules and table format.

Required task sequence for this review (strict order — error codes first):
1. `tools/specdev_tools/core/errors.py` — add E211 (code, P0, no deps) → `python -c "from specdev_tools.core.errors import *"`
   ⚠️ CROSS-REVIEW NOTE: R4 will also modify this file (add E561/562/563) and R5 will mark E511 deprecated. All are additive changes. R3 runs first, adds only E211. Do not preemptively add R4/R5 codes here.
2. `tests/test_error_code_coverage.py` — add E211 coverage assertion (test, P0, deps: T01) → `pytest tests/test_error_code_coverage.py -v`
3. `canon/aliases.json` — add lifecycle fields (deprecated_since, sunset_date, replacement) following manifest.json pattern (data, P0, no deps) → `./tools/run_specdev.sh canonical-lint canon --repo-root ./devspec_toolkit`
4. `tools/specdev_tools/canonical/registry.py` — add sunset enforcement + E125 escalation (code, P1, deps: T03) → `pytest tests/test_canonical_registry.py -v`
5. `tools/specdev_tools/canonical/autofix.py` — deprecated alias replacement logic (code, P1, deps: T04) → `pytest tests/test_canonical_registry.py -v`
6. `tools/specdev_tools/canonical/integrity.py` — partial drift detection E211 (code, P1, deps: T01) → `pytest tests/test_canonical_integrity.py -v`
7. `tests/test_canonical_integrity.py` — extend with E211 partial drift test cases (test, P1, deps: T01, T06) → `pytest tests/test_canonical_integrity.py -v`
8. `tools/specdev_tools/validation/validators/step_04.py` — add cross-ref trace check (code, P2) → `pytest tests/test_step_validators_core.py -v`
9. `tools/specdev_tools/validation/validators/step_06.py` — add expression validity check (code, P2) → `pytest tests/test_step_validators_core.py -v`
10. `tools/specdev_tools/validation/validators/step_07.py` — add NFR completeness check (code, P2) → `pytest tests/test_step_validators_core.py -v`
11. `tools/specdev_tools/validation/validators/step_08.py` — add fixture target ref check (code, P2) → `pytest tests/test_step_validators_core.py -v`
12. `tools/specdev_tools/validation/validators/step_12.py` — add job dependency check (code, P2) → `pytest tests/test_step_validators_03_10.py -v`
13. `tools/specdev_tools/validation/validators/step_13a.py` — add score range checks (code, P2) → `pytest tests/test_step_validators_03_10.py -v`
14. Documentation: check `docs/developers/` for error-codes and canonical reference files; update if present (D prefix tasks, P3)

---

## Anti-Patterns
- Do not redesign the alias schema — extend it incrementally
- Do not change E210's existing trigger conditions — add E211 as a new code
- Do not make thin validators verbose — max 60 LOC each, additive only
- Do not add orphan detection (canonical terms never referenced) in this review — that's R4 scope

---

## Phase 4: Self-Verification Loop

After drafting Part A + Part B, launch before writing to file.

**Subagent V1** (`general-purpose`, no isolation): Run all 7 checks from `docs/audit/review_protocol.md` (Phase 4).
- If NEEDS REVISION: revise and re-run. Max 3 iterations.
- If VERIFIED after any iteration: proceed to Phase 5.

---

## Phase 5: Write Findings to File

**Output file**: `docs/audit/findings/r3_findings.md`

**Subagent W1** (`general-purpose`, no isolation): Write verified findings using the format in `docs/audit/review_protocol.md` (Phase 5).

---

## Phase 6: Post-Implementation Verification

Run in a separate session after all Part B tasks are executed.

**Subagent P1** (`Explore`, no isolation): Run all checks from `docs/audit/review_protocol.md` (Phase 6).
Key commands for this review:
```
pytest tests/ -k "canonical or integrity" -v
pytest tests/ --tb=short -q
./tools/run_specdev.sh canonical-lint canon --repo-root ./devspec_toolkit
./tools/run_specdev.sh canonical-integrity spec --repo-root ./devspec_toolkit
```

</review_prompt>
