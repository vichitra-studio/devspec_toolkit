<review_prompt id="R4" areas="1,2" runs_after="R1,R2,R3" priority="P1-high">
# Review R4: Traceability Chain — Seed→Roadmap + Roadmap→Implementation Coverage

## Scope
Two areas sharing `traceability_closure.py` and step validators:
- **Area 1**: Seed documents don't propagate through pipeline — consumption validated but content not enforced
- **Area 2**: FR→milestone→implementation binding missing — uncovered FRs and orphan milestones undetected

Fix in dependency order within this review:
1. Add missing E-codes to `errors.py` first
2. Extend `traceability_closure.py` with new checks
3. Extend thin step validators with traceability enforcement

**Prior reviews completed**: R1, R2, R3. Validation infra is sound and canonical lifecycle is in place.

---

## Files Under Review

| File | Area | Key Lines |
|------|------|-----------|
| `tools/specdev_tools/validation/traceability_closure.py` | 1, 2 | 67-76 |
| `tools/specdev_tools/core/errors.py` | 2 | full (61 LOC) — add E561/E562/E563 |
| `tools/step_order.json` | 1 | 451-459 (step 14 seed inputs) |
| `tools/specdev_tools/validation/seed_lint.py` | 1 | 178-193 |
| `tools/specdev_tools/validation/validators/step_04.py` | 2 | full (21 LOC) |
| `tools/specdev_tools/validation/validators/step_06.py` | 2 | full (16 LOC) |
| `tools/specdev_tools/validation/validators/step_07.py` | 2 | full (20 LOC) |
| `tools/specdev_tools/validation/validators/step_08.py` | 2 | full (16 LOC) |
| `tools/specdev_tools/validation/validators/step_12.py` | 2 | full (21 LOC) |
| `tools/specdev_tools/validation/validators/step_13a.py` | 2 | full (17 LOC) |
| `prompts/prompt_14_roadmap.md` | 1, 2 | check seed consumption instructions |
| `tools/specdev_tools/validation/validators/step_16.py` | 2 | shared validator for 16/16a/16b/16c — check milestone binding |
| `prompts/prompt_16a_impl_planner.md` | 2 | check roadmap binding |
| `prompts/prompt_16b_impl_coder.md` | 2 | check roadmap binding |
| `prompts/prompt_16c_impl_reviewer.md` | 2 | check roadmap binding |
| `tests/test_traceability_closure.py` | 1, 2 | existing test file — extend for E561/E562/E563 |
| `tests/test_error_code_coverage.py` | 2 | existing test file — must pass after new error codes added |

---

## Subagent Protocol (MANDATORY)

### Main Agent Rules
- **FORBIDDEN in main agent**: Read, Edit, Write, Grep, Glob, Bash for file content
- Main agent ONLY: spawn subagents, read text summaries, task sequencing, final report
- All file investigation → Explore subagents
- All code changes → general-purpose subagents with worktree isolation
- Token budget for main agent: < 5K tokens per session

### Subagent Assignment

#### Phase 1 — Investigation (3 Explore subagents)

**Subagent A** (`Explore`, no isolation) — Traceability Closure Audit:
```
Read these files completely:
1. tools/specdev_tools/validation/traceability_closure.py (full file, ~121 LOC)
   - Lines 67-76: What does it collect? FR IDs? Capability traces? Milestone assignments?
   - Does it check: FR assigned to milestone? Milestone has FR refs? 13a checklist item → roadmap?
   - Does it emit E561 (uncovered FR), E562 (orphan milestone), E563 (checklist-roadmap mismatch)?
2. tools/specdev_tools/core/errors.py (full file, 61 LOC)
   - Do E561, E562, E563 exist? What is the highest E5xx code currently defined?
   - What is the error definition format?
3. tools/step_order.json lines 440-470 (step 14 metadata region)
   - What does required_seed_inputs list for step 14?
   - Is seed-tech-stack included or only seed-overview?
4. tools/specdev_tools/validation/seed_lint.py lines 170-200
   - Lines 178-193: _collect_required_seeds() — does it validate that seeds are consumed
     (content reflected in output) or only that declared seed_refs exist as files?
Report: exact gaps with code quotes.
```

**Subagent B** (`Explore`, no isolation) — Roadmap Prompt Audit:
```
Read these prompt files and answer for each:
1. prompts/prompt_14_roadmap.md
   - Does it explicitly list all 5 upstream inputs per step_order.json:
     09_impl_plan.json, 00_charter.json, 04_functional_requirements.json,
     13_extension_generator.json, 13a_completeness_assessment.json?
   - For each listed input, does it specify WHAT to extract?
   - Does it require that every FR from step_04 appears in at least one milestone?
   - Does it mention seed-tech-stack as a required input?
2. prompts/prompt_16a_impl_planner.md
   - Does it require mapping back to roadmap milestone IDs?
   - Does it define what to do when a milestone has no implementation plan?
3. prompts/prompt_16b_impl_coder.md
   - Does it reference roadmap milestone the code implements?
4. prompts/prompt_16c_impl_reviewer.md
   - Does it verify all milestone deliverables are implemented?
Report: for each prompt, list what's present vs missing for complete upstream consumption.
```

**Subagent C** (`Explore`, no isolation) — Step Validator Coverage for Traceability:
```
Read all 6 thin validators, step_14, and the shared Trinity Loop validator:
- tools/specdev_tools/validation/validators/step_04.py
- tools/specdev_tools/validation/validators/step_06.py
- tools/specdev_tools/validation/validators/step_07.py
- tools/specdev_tools/validation/validators/step_08.py
- tools/specdev_tools/validation/validators/step_12.py
- tools/specdev_tools/validation/validators/step_13a.py
- tools/specdev_tools/validation/validators/step_14.py (check if exists)
- tools/specdev_tools/validation/validators/step_16.py (CONFIRMED EXISTS — handles 16, 16a, 16b, 16c via shared validator)

Note: step_16a.py, step_16b.py, step_16c.py do NOT exist as separate files. All Trinity Loop
steps (16, 16a, 16b, 16c) route to step_16.py in validate.py. Any traceability gaps for
the Trinity Loop must be addressed in step_16.py only.

For each validator that exists, answer:
- Does it enforce that FRs from step_04 are present in this step's output?
- Does it enforce roadmap↔implementation binding?
- Does it check milestone assignment coverage?
For step_16.py specifically:
- Does it differentiate between 16a (planner), 16b (coder), 16c (reviewer) behaviors?
- Does it check for milestone_ref field binding?
Report: exact coverage gaps per step.
```

#### Phase 2 — Implementation (after Phase 1)

**Subagent D** (`general-purpose`, isolation: `worktree`) — Add Missing Error Codes:
```
Based on Phase 1 findings, add missing error codes to tools/specdev_tools/core/errors.py:
1. E561: UNCOVERED_FR — FR defined in step_04 not assigned to any milestone in step_14
2. E562: ORPHAN_MILESTONE — milestone in step_14 with no FR references
3. E563: CHECKLIST_ROADMAP_MISMATCH — checklist item in step_13a has no corresponding roadmap entry
Use the exact error definition format found in the existing errors.py entries.
Do not modify any existing error codes.
Run: python -c "from specdev_tools.core.errors import E561, E562, E563; print('OK')"
(adjust import path to match actual module structure)
```

**Subagent E** (`general-purpose`, isolation: `worktree`) — Extend Traceability Closure:
```
Based on Phase 1 findings, extend tools/specdev_tools/validation/traceability_closure.py:
1. Add FR milestone coverage check (emits E561):
   - Collect all FR IDs from step_04 artifact
   - Collect all FR refs from milestones in step_14 artifact
   - Emit E561 for each FR not referenced by any milestone
2. Add orphan milestone check (emits E562):
   - For each milestone in step_14, verify it references at least one FR
   - Emit E562 for milestones with empty FR ref list
3. Add checklist→roadmap check (emits E563):
   - Collect all checklist items from step_13a
   - Verify each has a corresponding entry referenced in step_14 milestones
   - Emit E563 for checklist items with no roadmap trace
Note: emit as W-codes if SPECDEV_WARNINGS_AS_ERRORS is not set (consistent with existing W560 pattern).
Run: pytest tests/ -k traceability -v and confirm pass.
```

**Subagent F** (`general-purpose`, isolation: `worktree`) — Seed Consumption Validation:
```
Based on Phase 1 findings, extend seed validation:
1. tools/step_order.json lines 451-459: If seed-tech-stack is missing from step_14's
   required_seed_inputs (verify in Phase 1), add it. Only modify if confirmed missing.
2. tools/specdev_tools/validation/seed_lint.py lines 178-193:
   - Current: _collect_required_seeds() validates that declared seed_refs exist as files
   - Add: a lightweight content consumption check — for each declared seed_ref, verify that
     at least one field in the spec artifact's content contains a token that appears in the seed
     document (basic co-occurrence check). This is heuristic but catches completely unused seeds.
   - Emit W-code (W140 if free) for declared seed_ref with zero content overlap with the artifact.
Note: Do not attempt deep semantic content validation — heuristic co-occurrence is sufficient
and avoids false positives.
Run: pytest tests/ -k seed -v and confirm pass.
```

**Subagent G** (`general-purpose`, isolation: `worktree`) — Prompt Updates for Traceability:
```
Based on Phase 1 Subagent B findings, make targeted additions to roadmap and trinity prompts.
Rules: Only add missing required inputs — do not rewrite existing prompt sections.

1. prompts/prompt_14_roadmap.md:
   - If seed-tech-stack is not listed as a required input, add it to the upstream inputs section
   - If any of the 5 declared upstream inputs lacks explicit extraction instructions, add a
     concise bullet per missing input: "From [artifact]: extract [specific fields]"
   - Add rule: "Every FR ID from 04_functional_requirements.json must appear in at least one
     milestone's fr_refs array. Milestones with zero fr_refs are invalid."

2. prompts/prompt_16a_impl_planner.md:
   - Add: "Reference the roadmap milestone ID this plan implements in the milestone_ref field."

3. prompts/prompt_16c_impl_reviewer.md:
   - Add: "Verify all deliverables listed in the referenced milestone are addressed."

Only add content — do not remove or reformat existing prompt text.
```

#### Phase 3 — Integration (after Phase 2)

**Subagent H** (`general-purpose`, no isolation):
```
Run full validation suite:
1. pytest tests/ --tb=short -q
2. ./tools/run_specdev.sh validate-all spec --repo-root ./devspec_toolkit
3. SPECDEV_WARNINGS_AS_ERRORS=1 ./tools/run_specdev.sh validate-all spec --repo-root ./devspec_toolkit
4. mkdir -p spec/extras && ./tools/run_specdev.sh matrix spec --repo-root ./devspec_toolkit --out spec/extras/trace_matrix.json
Report: pass/fail counts and any new E561/E562/E563 emitted on the spec directory.
```

---

## Investigation Checklist

### Area 1 — Seed→Roadmap
- [ ] Does step_14 in step_order.json declare seed-tech-stack as required?
- [ ] Does seed_lint validate content consumption or only file existence?
- [ ] Does prompt_14 explicitly instruct consuming all 5 upstream artifacts?
- [ ] Is there any end-to-end seed→FR→roadmap chain validator?

### Area 2 — Roadmap→Implementation
- [ ] Do E561/E562/E563 exist in errors.py?
- [ ] Does traceability_closure.py detect uncovered FRs?
- [ ] Does it detect orphan milestones?
- [ ] Does it detect checklist→roadmap mismatches?
- [ ] Do step_16a/16b/16c validators enforce milestone binding?

---

## Deliverables

> **Format**: Use compact tables from `docs/audit/review_protocol.md`. No verbose prose.

### Part A: Findings
```
| ID | Sev | File:Line | Finding | Impact |
|----|-----|-----------|---------|--------|
| A-R4-01 | CRIT/HIGH/MED/LOW | path:line | description | impact |
```
Evidence blocks (CRIT/HIGH only): exact quoted code, one block per finding.

### Part B: Implementation Plan
Atomic tasks — one file per task. See `review_protocol.md` for sequencing rules and table format.

Required task sequence for this review (strict order — errors first):
1. `tools/specdev_tools/core/errors.py` — add E561, E562, E563 (code, P0, no deps) → `python -c "from specdev_tools.core.errors import *"`
   ⚠️ R3 already added E211 to this file. Read the current state of errors.py first. Add E561/E562/E563 after the existing codes. Do not touch E511 (R5 handles that).
2. `tests/test_error_code_coverage.py` — add E561/E562/E563 coverage assertions (test, P0, deps: T01) → `pytest tests/test_error_code_coverage.py -v`
3. `tools/step_order.json` — add seed-tech-stack to step 14 required_seed_inputs if missing (data, P0) → `./tools/run_specdev.sh validate-all spec --repo-root ./devspec_toolkit`
4. `tools/specdev_tools/validation/seed_lint.py` — add content co-occurrence check (code, P1, deps: T03) → `pytest tests/ -k seed -v`
   Heuristic definition (implement exactly this — no guessing):
   - Tokenize the seed document: split on whitespace and punctuation, lowercase, remove stop words, keep tokens ≥ 4 characters
   - Tokenize the spec artifact's string field values (title, description, rationale fields only — not IDs)
   - co-occurrence = at least 3 distinct seed tokens appear in the artifact's text fields
   - If fewer than 3 seed tokens appear: emit W140 "seed ref declared but ≤2 seed tokens found in artifact text"
   - Threshold of 3 is conservative to minimize false positives; do not make it configurable in this pass
5. `tools/specdev_tools/validation/traceability_closure.py` — add E561/E562/E563 checks (code, P1, deps: T01) → `pytest tests/test_traceability_closure.py -v`
6. `tests/test_traceability_closure.py` — extend with E561/E562/E563 test cases (test, P0, deps: T01, T05) → `pytest tests/test_traceability_closure.py -v`
7. `tools/specdev_tools/validation/validators/step_16.py` — add milestone_ref check if Phase 1C finds it missing (code, P1, deps: T01) → `pytest tests/test_step_validators_core.py -v`
8. `prompts/prompt_14_roadmap.md` — add missing upstream extraction instructions (content, P1, deps: T03) → manual review only
9. `prompts/prompt_16a_impl_planner.md` — add milestone_ref rule (content, P1) → manual review only
10. `prompts/prompt_16c_impl_reviewer.md` — add deliverable check rule (content, P1) → manual review only
11. Documentation: `CHANGELOG.md` entry for new error codes; check `docs/developers/` for an error-codes reference file and update it if it exists

---

## Anti-Patterns
- Do not implement deep semantic seed→content tracing — heuristic co-occurrence is sufficient
- Do not emit E561/E562 as hard errors by default — use W-codes unless SPECDEV_WARNINGS_AS_ERRORS=1
- Do not add FR coverage checks to thin validators that already have them from R3
- Prompt updates must be additive only — never remove existing prompt instructions

---

## Phase 4: Self-Verification Loop

After drafting Part A + Part B, launch before writing to file.

**Subagent V1** (`general-purpose`, no isolation): Run all 7 checks from `docs/audit/review_protocol.md` (Phase 4).
- If NEEDS REVISION: revise and re-run. Max 3 iterations.
- If VERIFIED after any iteration: proceed to Phase 5.

---

## Phase 5: Write Findings to File

**Output file**: `docs/audit/findings/r4_findings.md`

**Subagent W1** (`general-purpose`, no isolation): Write verified findings using the format in `docs/audit/review_protocol.md` (Phase 5).

---

## Phase 6: Post-Implementation Verification

Run in a separate session after all Part B tasks are executed.

**Subagent P1** (`Explore`, no isolation): Run all checks from `docs/audit/review_protocol.md` (Phase 6).
Key commands for this review:
```
pytest tests/ -k "traceability or seed" -v
pytest tests/ --tb=short -q
./tools/run_specdev.sh validate-all spec --repo-root ./devspec_toolkit
SPECDEV_WARNINGS_AS_ERRORS=1 ./tools/run_specdev.sh validate-all spec --repo-root ./devspec_toolkit
mkdir -p spec/extras && ./tools/run_specdev.sh matrix spec --repo-root ./devspec_toolkit --out spec/extras/trace_matrix.json
```

</review_prompt>
