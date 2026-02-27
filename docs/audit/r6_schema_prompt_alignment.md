<review_prompt id="R6" areas="6,12,13" runs_after="R1,R2,R3,R4,R5" priority="P2-medium">
# Review R6: Schema–Prompt–Validator Alignment + Prompt Hardening + Toolkit Discovery

## Scope
**Prior reviews completed**: R1-R5. All canonical refs (R3), traceability codes (R4), and generation_quality changes (R5) are already in place.

This review is the **synthesis pass** — it closes the alignment gap between what prompts require, what schemas enforce, and what validators check.

Areas:
- **Area 13**: Schema–prompt contract misalignment (schema weaker than prompt requirements)
- **Area 6**: Prompt hardening — exhaustive upstream consumption, zero-inference, fallback rules
- **Area 12**: Toolkit discovery deficit — AI has zero awareness of downstream consumers and validation rules

**This is the largest review (~65 files across schemas, prompts, and validators).**

---

## Files Under Review

| Category | Files |
|----------|-------|
| All prompts | `prompts/prompt_00_*.md` through `prompts/prompt_16c_*.md` (23 files) |
| Step schemas | `schema/00_charter.schema.json` through `schema/16c_*.schema.json` (22+ files) |
| Step validators | `tools/specdev_tools/validation/validators/step_00.py` through `step_16.py` (note: `step_16.py` handles steps 16, 16a, 16b, 16c — separate files for 16a/16b/16c do NOT exist) |
| Pipeline DAG | `tools/step_order.json` (step_metadata section, lines 309-509) |
| Prompt generator | `tools/specdev_tools/generation/prompt_generator.py` |
| Key confirmed misalignments | `schema/00_charter.schema.json:182-193`, `schema/04_fr_list.schema.json:89-94` |

---

## Subagent Protocol (MANDATORY)

### Main Agent Rules
- **FORBIDDEN in main agent**: Read, Edit, Write, Grep, Glob, Bash for file content
- **All investigation MUST be delegated to subagents — no exceptions** (~65 files)
- Main agent: receive summaries, synthesize findings table, write task list, final report
- Token budget: < 8K tokens total for main agent across all phases

### Subagent Assignment

#### Phase 1 — Investigation (5 Explore subagents)

**Subagent A** (`Explore`, no isolation) — Schema Constraint Audit (Area 13):
```
For each of the confirmed schema misalignments, verify and then scan ALL step schemas.

CONFIRMED MISALIGNMENTS (verify first):
1. schema/00_charter.schema.json lines 182-193: Are "stakeholders" and "user_segments" in required[]?
2. schema/00_charter.schema.json: Does "success_metrics" array have minItems: 2?
   (prompt says ≥2, schema may have no minItems)
3. schema/04_fr_list.schema.json lines 89-94: Is "trace" in each FR item's required array?
4. schema/04_fr_list.schema.json line 48: Is "acceptance_criteria" minItems set to 2?
   (prompt says ≥2 for top FRs; schema may only have minItems:1)

SCAN ALL SCHEMAS for the same pattern:
- For each schema in schema/*.schema.json:
  a. List all fields NOT in the required array
  b. For each optional field, check if the corresponding prompt's Self-Audit Gate or
     Output Rules section treats it as mandatory
  c. For each array field without minItems, note it
  d. Check if additionalProperties: false is set on all objects

Produce a table:
| Schema | Field | Schema: optional | Prompt: mandatory | minItems gap |
```

**NOTE**: prompt_14_roadmap.md, prompt_16a_impl_planner.md, and prompt_16c_impl_reviewer.md were already modified by R4. When auditing these prompts, if seed-tech-stack and milestone_ref rules are already present, mark those items as RESOLVED — do NOT re-add them.

**Subagent B** (`Explore`, no isolation) — Phase I Prompt Hardening Audit (Area 6, steps 00-08):
```
Review prompts 00 through 08 against step_order.json declared dependencies.
For EACH prompt:

1. Read prompts/prompt_00_project_charter.md
2. Read prompts/prompt_01_capabilities.md
3. Read prompts/prompt_02_system_sketch.md
4. Read prompts/prompt_02a_delivery_baseline.md
5. Read prompts/prompt_03_glossary.md
6. Read prompts/prompt_04_functional_requirements.md
7. Read prompts/prompt_05_interface_contracts.md
8. Read prompts/prompt_06_invariants.md
9. Read prompts/prompt_07_nfrs.md
10. Read prompts/prompt_08_fixtures.md

For each prompt, check against step_order.json required_spec_inputs:
a. Are ALL declared upstream inputs listed in the prompt?
b. For each listed input, are specific extraction instructions given?
c. Are there vague phrases: "consider", "if appropriate", "as needed", "may include"? List them.
d. Is the Two-Phase Clarify→Emit protocol present with Self-Audit Gate score threshold?
e. Does the prompt instruct use of canon/manifest.json for controlled vocabularies?

Report per prompt: PASS / FAIL with specific missing elements.
```

**Subagent C** (`Explore`, no isolation) — Phase II Prompt Hardening Audit (Area 6, steps 09-16c):
```
Review prompts 09 through 16c against step_order.json declared dependencies.
For EACH prompt:

1. Read prompts/prompt_09_impl_plan.md
2. Read prompts/prompt_10_governance.md
3. Read prompts/prompt_11_redteam.md
4. Read prompts/prompt_12_ci_gates.md
5. Read prompts/prompt_13_extension_generator.md
6. Read prompts/prompt_13a_completeness_assessment.md
7. Read prompts/prompt_14_roadmap.md (already partially updated in R4)
8. Read prompts/prompt_15_scaffold.md
9. Read prompts/prompt_16_impl_context.md
10. Read prompts/prompt_16a_impl_planner.md (partially updated in R4)
11. Read prompts/prompt_16b_impl_coder.md
12. Read prompts/prompt_16c_impl_reviewer.md (partially updated in R4)

Same checks as Subagent B above. Also:
- For Trinity Loop (16a/16b/16c): do they reference roadmap milestone IDs? (added in R4)
- Does prompt_14 now include seed-tech-stack? (added in R4)

Report per prompt: PASS / FAIL with specific missing elements. Mark R4-already-fixed items as RESOLVED.
```

**Subagent D** (`Explore`, no isolation) — Toolkit Discovery Audit (Area 12):
```
Audit what the AI knows vs what it could know from step_order.json.

1. Read tools/step_order.json lines 309-509 (step_metadata section)
   - For step 04: how many downstream steps consume its output? List them with extraction_intent.
   - For step 00: how many downstream steps consume its output?
   - Are all 22 steps' extraction_intent entries present and non-empty?

2. For step 04 specifically, read prompts/prompt_04_functional_requirements.md:
   - Does it mention that 12 downstream steps consume its output?
   - Does it list what each downstream step extracts?

3. Read tools/specdev_tools/generation/prompt_generator.py:
   - Does it have {{VAR}} template rendering?
   - Does it have _extract_required_fields() or similar?
   - Could it be extended to inject downstream consumer tables?

4. Estimate token cost of enrichment:
   - For a step with 5 downstream consumers, each with a 1-2 line extraction_intent:
     approximately how many tokens would a "Downstream Consumers" section add per prompt?
   - Is there a simpler approach: a separate "toolkit-context.md" file agents are told to read?

Report: downstream consumer counts per step, extraction_intent completeness, enrichment feasibility.
```

**Subagent E** (`Explore`, no isolation) — Schema-Validator Gap Analysis (Area 13d):
```
IMPORTANT: R3 Phase 2 may have expanded thin validators up to 60 LOC. Do NOT assume validators
are still < 25 LOC. Instead, read the CURRENT state of each validator and classify it yourself.

For each step validator, compare schema vs validator coverage.
Focus on steps where schema enforcement is the weakest relative to prompt requirements.
Priority order: step_04, step_06, step_07, step_08, step_12, step_13a, step_14, step_16.

For each thin validator:
1. List what the schema enforces (required fields, minItems, patterns)
2. List what the validator checks (from code)
3. List what the prompt requires (from prompt_NN file)
4. Gap = prompt requires X, schema doesn't enforce X, validator doesn't check X

Specifically check:
- Does any validator check cross-field constraints? (e.g., "if type=api then endpoint is required")
- Do any schemas have inline type definitions instead of $ref to schema/core/?
  (search for "type": "object" with "properties" nested directly instead of using $ref)

Report: gap table per step, list of inlined type definitions (should use $ref instead).
```

#### Phase 2 — Implementation (after Phase 1)

Execute subagents in this order: F → G → H → I. Subagent I depends on schema changes from F, so F must complete first. G and H are independent but run sequentially for simplicity.

**Subagent F** (`general-purpose`, isolation: `worktree`) — Schema Tightening (Area 13):
```
Based on Phase 1 Subagent A findings, tighten schemas for confirmed misalignments.
For each gap found:
- Add fields to "required" arrays where prompt treats them as mandatory
- Add minItems constraints where prompt specifies minimum counts
- Do NOT tighten constraints that would break existing valid spec artifacts in spec/
  (run validate-all after each change to check)

Priority order:
1. schema/00_charter.schema.json: add stakeholders, user_segments to required if missing
2. schema/00_charter.schema.json: add minItems:2 to success_metrics if missing
3. schema/04_fr_list.schema.json: add trace to FR item required if missing
4. Additional schemas per Phase 1 findings — handle HIGH severity misalignments only

For each schema change: run ./tools/run_specdev.sh validate spec/NN_*.json --repo-root ./devspec_toolkit
to confirm no regressions on existing artifacts.
Run: pytest tests/ -k schema -v
```

**Subagent G** (`general-purpose`, isolation: `worktree`) — Prompt Hardening (Area 6):
```
Based on Phase 1 Subagents B and C findings, add missing upstream consumption instructions
to the highest-priority prompts.

Rules:
- Only add to prompts with CRITICAL or HIGH gaps (per Part A findings)
- Additions must be additive — no removal of existing content
- Use this standard section format for missing upstream inputs:

## Upstream Input Extraction
| Artifact | Extract | Use in |
|----------|---------|--------|
| 00_charter.json | project_name, objectives[] | step metadata |
| ... | ... | ... |

- Replace vague phrases: "consider X" → "you MUST include X if [condition]"
- For each prompt missing the Two-Phase protocol: add it using the existing pattern from a prompt that has it (copy, don't invent)

Focus on prompts with the most downstream consumers first (step 04, step 00, step 09).
Do not attempt to harden all 23 prompts in one pass — focus on P0/P1 severity gaps only.
```

**Subagent H** (`general-purpose`, isolation: `worktree`) — Toolkit Discovery Enrichment (Area 12):
```
Based on Phase 1 Subagent D findings, implement a minimal toolkit discovery mechanism.

Approach: Create a new CLI command `specdev prompt-context <step>` that prints a
downstream consumer table for a given step. This is less invasive than modifying all prompts.

1. Add command to tools/specdev_tools/cli.py:
   `specdev prompt-context 04` → prints:
   "## Downstream Consumers of step_04
   | Downstream Step | Extraction Intent |
   |-----------------|------------------|
   | step_05 | Extract FR behaviors and acceptance criteria for API design |
   | step_06 | Extract FR conditions for invariant specification |
   | ... |"

2. Implement by reading step_order.json step_metadata and finding all steps where
   required_spec_inputs includes the queried step.

3. Add a note to EACH prompt's header section (add 2 lines, do not rewrite):
   "Run `specdev prompt-context NN` to see downstream consumers of this step's output."

This is lower-cost than injecting full tables into every prompt, but makes the data accessible.
Run: ./tools/run_specdev.sh --help to verify the new command appears.
```

**Subagent I** (`general-purpose`, isolation: `worktree`) — Validator Gap Closure (Area 13d):
```
Based on Phase 1 Subagent E findings, add cross-field validators for the highest-severity gaps.

For each gap where:
- Prompt requires X
- Schema cannot express X (cross-field constraint, conditional requirement)
- Validator doesn't check X

Add the constraint to the per-step validator. Rules:
- Each validator remains under 80 LOC
- Only implement constraints for HIGH/CRITICAL severity gaps
- Add a docstring comment explaining what each check enforces and why the schema can't

Fix any inlined type definitions found in Phase 1 (replace with $ref to schema/core/).
Run: pytest tests/ --tb=short -q
```

#### Phase 3 — Final Integration (after Phase 2)

**Subagent J** (`general-purpose`, no isolation):
```
Run complete toolkit validation suite:
1. pytest tests/ --tb=short -q (expect: all pass)
2. ./tools/run_specdev.sh validate-all spec --repo-root ./devspec_toolkit
3. SPECDEV_WARNINGS_AS_ERRORS=1 ./tools/run_specdev.sh validate-all spec --repo-root ./devspec_toolkit
4. ./tools/run_specdev.sh canonical-integrity spec --repo-root ./devspec_toolkit
5. ./tools/run_specdev.sh seed-lint spec --repo-root ./devspec_toolkit
6. ./tools/run_specdev.sh hallucination-lint spec --repo-root ./devspec_toolkit

Report: complete pass/fail summary. This is the final integration gate for the entire R1-R6 review series.
Flag any regressions from prior reviews (R1-R5 changes that interact badly with R6 changes).
```

---

## Investigation Checklist

### Area 13 — Schema-Prompt Alignment
- [ ] Are stakeholders/user_segments in schema/00_charter.schema.json required[]?
- [ ] Does success_metrics have minItems:2?
- [ ] Is FR item trace field required in schema/04_fr_list.schema.json?
- [ ] Are any step schemas using inlined type definitions instead of $ref to schema/core/?
- [ ] Is additionalProperties:false set on all objects in all schemas?

### Area 6 — Prompt Hardening
- [ ] For each prompt, do upstream inputs have explicit extraction instructions?
- [ ] Are vague phrases (consider, if appropriate, may include) present?
- [ ] Is the Clarify→Emit Two-Phase protocol present in all prompts?
- [ ] Does each prompt specify the Self-Audit Gate score threshold?

### Area 12 — Toolkit Discovery
- [ ] Does step_order.json have extraction_intent for all 22 steps?
- [ ] Does any prompt mention downstream consumers?
- [ ] Does prompt_generator.py support template enrichment?
- [ ] What is the estimated token cost of downstream consumer table injection?

---

## Deliverables

> **Format**: Use compact tables from `docs/audit/review_protocol.md`. No verbose prose.

### Part A: Findings
```
| ID | Sev | File:Line | Finding | Impact |
|----|-----|-----------|---------|--------|
| A-R6-01 | CRIT/HIGH/MED/LOW | path:line | description | impact |
```
Evidence blocks (CRIT/HIGH only): exact quoted code or schema excerpt, one block per finding.

### Part B: Implementation Plan
Atomic tasks — one file per task. See `review_protocol.md` for sequencing rules and table format.

Required task sequence for this review:
1. Schema tightening: one task per schema file with confirmed misalignment (HIGH+ only)
2. `tools/specdev_tools/cli.py` — add `prompt-context` command (code) → `pytest tests/test_cli.py -v`
3. Step validators with cross-field gaps: one task per validator file
4. Prompt hardening: one task per prompt file with CRITICAL/HIGH gaps (P0/P1 only)
5. Prompt context note: one task per prompt file adding `prompt-context` reference (P2)
6. `tests/test_cli.py` — add tests for `prompt-context` command (test, P0, deps: cli.py task)
7. Tests: one task per modified validator → existing test files are `tests/test_step_validators_core.py`, `tests/test_step_validators_03_10.py`
8. Documentation: one task for `docs/developers/` CLI reference (check existing files first), one for schema-change migration notes in `CHANGELOG.md`

Note: with 22 schemas + 23 prompts, this review will have the most tasks. Prune to HIGH+ severity only to keep the plan executable. Mark MED/LOW findings as "track only" with no task.

---

## Anti-Patterns
- Do not tighten schemas in ways that break existing valid spec artifacts in spec/
- Do not rewrite prompts — add missing sections, replace vague phrases, do not restructure
- Do not inject full downstream consumer tables into prompts — use the `prompt-context` command approach
- Do not duplicate validator logic that the schema already enforces
- Prompt hardening P0: fix missing upstream extraction rules. P1: fix vague language. P2: add Clarify→Emit if missing.
- This review is SYNTHESIS — reference R1-R5 fixes rather than re-implementing them

---

## Phase 4: Self-Verification Loop

After drafting Part A + Part B, launch before writing to file.

**Subagent V1** (`general-purpose`, no isolation): Run all 7 checks from `docs/audit/review_protocol.md § Phase 4`.

Extra check for this review:
- CHECK 8 — No rework with R1-R5: verify no task modifies a file already changed in R1-R5.
  If overlap found, mark as "dependent on R-N fix" and note the prior task ID instead of re-implementing.
- If NEEDS REVISION: revise and re-run. Max 3 iterations.
- If VERIFIED after any iteration: proceed to Phase 5.

---

## Phase 5: Write Findings to File

**Output file**: `docs/audit/findings/r6_findings.md`

**Subagent W1** (`general-purpose`, no isolation): Write verified findings using the format in `docs/audit/review_protocol.md § Phase 5`.

---

## Phase 6: Post-Implementation Verification

This is the **final integration gate** for the entire R1-R6 audit series.

**Subagent P1** (`Explore`, no isolation): Run all checks from `docs/audit/review_protocol.md § Phase 6`.
Key commands for this review:
```
pytest tests/ --tb=short -q
./tools/run_specdev.sh validate-all spec --repo-root ./devspec_toolkit
SPECDEV_WARNINGS_AS_ERRORS=1 ./tools/run_specdev.sh validate-all spec --repo-root ./devspec_toolkit
./tools/run_specdev.sh canonical-integrity spec --repo-root ./devspec_toolkit
./tools/run_specdev.sh seed-lint spec --repo-root ./devspec_toolkit
./tools/run_specdev.sh hallucination-lint spec --repo-root ./devspec_toolkit
./tools/run_specdev.sh dependency-order-lint --repo-root ./devspec_toolkit
```

Also produce a cross-review summary:
- List all findings from R1-R6 with their resolution status
- Confirm no finding from any prior review is unaddressed
- Confirm all 13 original areas from `review_prompt_04_canonical_drift.md` are covered

</review_prompt>
