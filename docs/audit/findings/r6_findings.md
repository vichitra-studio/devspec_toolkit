---
# Review R6 Findings — Schema–Prompt–Validator Alignment + Prompt Hardening + Toolkit Discovery
Generated: 2026-02-27
Status: VERIFIED (Phase 4 passed 1/3 iterations)

## Part A: Findings

| ID | Sev | File:Line | Finding | Impact |
|----|-----|-----------|---------|--------|
| A-R6-01 | HIGH | schema/00_charter.schema.json:182-193 | `stakeholders` and `user_segments` absent from required[]; both defined as optional properties | Charter artifacts can omit stakeholder data; 8 downstream consumers (01,03,04,07,09,10,13a,14) may operate on incomplete charter |
| A-R6-02 | HIGH | schema/00_charter.schema.json:99-150 | `success_metrics` array has no minItems; empty `[]` passes schema | Steps 07, 09, 14 that extract metrics receive empty data without schema-level error |
| A-R6-03 | HIGH | schema/04_fr_list.schema.json:89-94 | `trace` field absent from FR item required[]; trace links optional per schema | Traceability chain silently broken across 13 downstream consumers of step_04 (05,06,07,08,09,11,13,13a,14,15,16,16a,16c) |
| A-R6-04 | MED | schema/04_fr_list.schema.json:48 | `acceptance_criteria` minItems:1; prompt contract specifies ≥2 for primary FRs | Single-AC FRs pass schema; step_11 red-team and step_12 CI gates operate on thin criteria |
| A-R6-05 | HIGH | tools/specdev_tools/validation/validators/step_04.py:1-25 | step_04 validator (25 LOC) only checks fr_id format/uniqueness; no trace presence check, no capability_ref cross-validation | Invalid FRs pass validation for highest-fanout step (13 downstream consumers) |
| A-R6-06 | MED | tools/specdev_tools/cli.py:628-631 | No `prompt-context` command; downstream consumer data in step_order.json not CLI-accessible | Authors cannot query downstream impact of a step without manual JSON inspection |
| A-R6-07 | MED | prompts/*.md (all 23 prompts) | Self-Audit Gate section present in all prompts but no numeric score threshold; CLAUDE.md specifies "score < 0.9" | AI runners may skip clarification phase without clear numeric gate |
| A-R6-08 | LOW | prompts/prompt_04_functional_requirements.md | Prompt does not mention its 13 downstream consumers or what each extracts | Authors may underestimate impact of under-specified FRs on downstream steps |

### Evidence (HIGH findings)

#### A-R6-01
```json
// schema/00_charter.schema.json lines 182-193
"required": [
  "id", "owner", "created_at", "seed_refs", "spec_refs_ingested",
  "problem_statement", "success_metrics",
  "generation_quality", "canonical_refs_used",
  "canonical_proposals", "canonical_conflicts"
]
// "stakeholders" defined at lines 46-67 as optional property
// "user_segments" defined at lines 68-98 as optional property
// Neither appears in required[]
```

#### A-R6-02
```json
// schema/00_charter.schema.json lines 99-150
"success_metrics": {
  "type": "array",
  // minItems: ABSENT — empty array [] is valid per schema
  "items": { "required": ["metric_id", "name", "target", "unit", "measurement_method", "unit_ref"] }
}
```

#### A-R6-03
```json
// schema/04_fr_list.schema.json lines 89-94
"required": [
  "fr_id",
  "statement",
  "acceptance_criteria",
  "capability_ref"
]
// "trace" defined as property but ABSENT from required[]
// 13 downstream consumers: 05,06,07,08,09,11,13,13a,14,15,16,16a,16c
```

#### A-R6-05
```python
# tools/specdev_tools/validation/validators/step_04.py (25 LOC total)
# validate_step_04(instance, toolkit_root):
#   - fr_id pattern: ^fr-[a-z0-9]+(?:-[a-z0-9]+)*$
#   - Duplicate fr_id detection
# MISSING:
#   - trace presence check (each FR item must have non-empty trace array)
#   - capability_ref cross-validation against spec/01_capabilities.json (if present)
```

---

## Part B: Implementation Plan — Atomic Tasks

**Implementation note (T03a/T03b/T04)**: The schema acceptance tests (pytest) are run AFTER fixtures
are updated. T01/T02 acceptance is JSON syntax check only — running pytest before fixture updates
would fail since the new required fields don't exist in existing fixtures yet.

**Implementation note (T05/T06)**: `tests/fixtures/step_04/invalid_bad_trace.json` tests malformed
trace FORMAT, not missing trace. T06's missing-trace negative test uses inline dict data in the
test function body.

**Implementation note (T05 capability_ref)**: cross-validation runs only when `spec/01_capabilities.json`
exists (matches pattern of step_07.py). Toolkit's own spec/ lacks this file — test coverage uses
a temp fixture written to a tmpdir in T06.

| ID | Pri | Deps | File | Change summary | Acceptance command | Findings |
|----|-----|------|------|----------------|--------------------|----------|
| T01 | P0 | — | `schema/00_charter.schema.json` | Add `stakeholders`, `user_segments` to required[]; add `minItems: 2` to success_metrics | `python -c "import json; json.load(open('schema/00_charter.schema.json'))"` | A-R6-01, A-R6-02 |
| T02 | P0 | — | `schema/04_fr_list.schema.json` | Add `trace` to FR item required[]; change acceptance_criteria minItems from 1 to 2 | `python -c "import json; json.load(open('schema/04_fr_list.schema.json'))"` | A-R6-03, A-R6-04 |
| T03a | P0 | T01 | `tests/fixtures/step_00/00_charter.json` | Add `stakeholders` array (≥1 item), `user_segments` array (≥1 item); ensure ≥2 success_metrics items | `python -c "import json; json.load(open('tests/fixtures/step_00/00_charter.json'))"` | A-R6-01, A-R6-02 |
| T03b | P0 | T01 | `tests/fixtures/step_00/valid_strict.json` | Add `stakeholders` array (≥1 item), `user_segments` array (≥1 item); ensure ≥2 success_metrics items | `pytest tests/test_schema_contracts.py -v -k step_00` | A-R6-01, A-R6-02 |
| T04 | P0 | T02 | `tests/fixtures/step_04/valid_comprehensive.json` | Add `trace` array (non-empty) to each FR item; ensure each FR has ≥2 acceptance_criteria items | `pytest tests/test_schema_contracts.py -v -k step_04` | A-R6-03, A-R6-04 |
| T05 | P0 | T02 | `tools/specdev_tools/validation/validators/step_04.py` | Add trace presence check (each FR item must have non-empty trace); add capability_ref cross-validation against spec/01_capabilities.json if present; keep ≤80 LOC; add docstring per check | `pytest tests/test_step_validators_03_10.py -v` | A-R6-05 |
| T06 | P0 | T04, T05 | `tests/test_step_validators_03_10.py` | Add: test_step04_rejects_fr_missing_trace (inline dict, no trace field); test_step04_rejects_fr_empty_trace (inline dict, trace:[]); test_step04_accepts_valid_fr_with_trace (inline dict); test_step04_capability_ref_cross_validation (writes tmp spec/01 fixture) | `pytest tests/test_step_validators_03_10.py -v && pytest tests/ -k step_04 --tb=short -q` | A-R6-05 |
| T07 | P1 | — | `tools/specdev_tools/cli.py` | Add `prompt-context <step>` subcommand with `--repo-root` arg; reads tools/step_order.json step_metadata; prints markdown table of downstream consumers with extraction_intent | `./tools/run_specdev.sh --help \| grep prompt-context && ./tools/run_specdev.sh prompt-context 04 --repo-root ./devspec_toolkit` | A-R6-06 |
| T08 | P1 | T07 | `tests/test_cli.py` | Add: test_prompt_context_step04 (≥13 downstream rows); test_prompt_context_step00 (≥8 rows); test_prompt_context_unknown_step (error exit); test_prompt_context_output_format (markdown table) | `pytest tests/test_cli.py -v -k prompt_context` | A-R6-06 |
| T09 | P2 | T07 | `prompts/prompt_00_project_charter.md` | Add 2-line header note: "Run `specdev prompt-context 00` to see downstream consumers."; add to Self-Audit Gate section: "If score < 0.9, output clarifying questions only — do not emit JSON." | — | A-R6-06, A-R6-07 |
| T10 | P2 | T07 | `prompts/prompt_01_capabilities.md` | Same pattern for step 01 | — | A-R6-06, A-R6-07 |
| T11 | P2 | T07 | `prompts/prompt_02_system_sketch.md` | Same for step 02 | — | A-R6-06, A-R6-07 |
| T12 | P2 | T07 | `prompts/prompt_02a_delivery_baseline.md` | Same for step 02a | — | A-R6-06, A-R6-07 |
| T13 | P2 | T07 | `prompts/prompt_03_glossary.md` | Same for step 03 | — | A-R6-06, A-R6-07 |
| T14 | P2 | T07 | `prompts/prompt_04_functional_requirements.md` | Same for step 04 + add note in header: "This step has 13 downstream consumers — see `specdev prompt-context 04`." | — | A-R6-06, A-R6-07, A-R6-08 |
| T15 | P2 | T07 | `prompts/prompt_05_interface_contracts.md` | Same for step 05 | — | A-R6-06, A-R6-07 |
| T16 | P2 | T07 | `prompts/prompt_06_invariants.md` | Same for step 06 | — | A-R6-06, A-R6-07 |
| T17 | P2 | T07 | `prompts/prompt_07_nfrs.md` | Same for step 07 | — | A-R6-06, A-R6-07 |
| T18 | P2 | T07 | `prompts/prompt_08_fixtures.md` | Same for step 08 | — | A-R6-06, A-R6-07 |
| T19 | P2 | T07 | `prompts/prompt_09_impl_plan.md` | Same for step 09 | — | A-R6-06, A-R6-07 |
| T20 | P2 | T07 | `prompts/prompt_10_governance.md` | Same for step 10 | — | A-R6-06, A-R6-07 |
| T21 | P2 | T07 | `prompts/prompt_11_redteam.md` | Same for step 11 | — | A-R6-06, A-R6-07 |
| T22 | P2 | T07 | `prompts/prompt_12_ci_gates.md` | Same for step 12 | — | A-R6-06, A-R6-07 |
| T23 | P2 | T07 | `prompts/prompt_13_extension_generator.md` | Same for step 13 | — | A-R6-06, A-R6-07 |
| T24 | P2 | T07 | `prompts/prompt_13a_completeness_assessment.md` | Same for step 13a | — | A-R6-06, A-R6-07 |
| T25 | P2 | T07 | `prompts/prompt_14_roadmap.md` | Same for step 14 — R4 already added milestone_ref; add only prompt-context note + gate threshold | — | A-R6-06, A-R6-07 |
| T26 | P2 | T07 | `prompts/prompt_15_scaffold.md` | Same for step 15 | — | A-R6-06, A-R6-07 |
| T27 | P2 | T07 | `prompts/prompt_16_impl_context.md` | Same for step 16 | — | A-R6-06, A-R6-07 |
| T28 | P2 | T07 | `prompts/prompt_16a_impl_planner.md` | Same for step 16a — R4 already added milestone_ref binding; add only prompt-context note + gate threshold | — | A-R6-06, A-R6-07 |
| T29 | P2 | T07 | `prompts/prompt_16b_impl_coder.md` | Same for step 16b — R4 already added milestone context; add only prompt-context note + gate threshold | — | A-R6-06, A-R6-07 |
| T30 | P2 | T07 | `prompts/prompt_16c_impl_reviewer.md` | Same for step 16c — R4 already added deliverable verification; add only prompt-context note + gate threshold | — | A-R6-06, A-R6-07 |
| D01 | P3 | T01, T02 | `CHANGELOG.md` | Add R6 schema changes: stakeholders/user_segments now required (step_00); success_metrics minItems:2 (step_00); trace now required on FR items (step_04); acceptance_criteria minItems:2 (step_04) | `./tools/run_specdev.sh changelog --validate 0.3.0 --repo-root ./devspec_toolkit` | A-R6-01,02,03,04 |
| D02 | P3 | T07 | `docs/developers/tools/prompt_context.md` | Create new file following pattern of `docs/developers/tools/align.md`; document `prompt-context <step> [--repo-root PATH]` with usage, args, example output table | — | A-R6-06 |
| D03 | P3 | D02 | `docs/developers/index.md` | Add link to `prompt_context.md` under the tools section (follows existing link pattern for align.md, schema_differ.md) | — | A-R6-06 |

---

## Verification Status

- CHECK 1 Assumptions: PASS — all HIGH findings backed by exact quoted evidence; A-R6-07 (23 prompts)
  extrapolated from 6/6 uniform sample, noted in CHECK 2
- CHECK 2 References: PASS — all File:Line refs verified by exploration agents; A-R6-07 pattern
  (no numeric threshold) confirmed in 6/6 sampled prompts (extrapolated to 23, noted)
- CHECK 3 Atomic: PASS — every task modifies exactly 1 file; T03a=00_charter.json,
  T03b=valid_strict.json, T04=valid_comprehensive.json all separate
- CHECK 4 Tests: PASS — T06 covers T05 (validator); T08 covers T07 (CLI); T09-T30 are prompt text
  changes (no tests needed); fixture updates T03a/T03b/T04 run pytest as acceptance
- CHECK 5 Docs: PASS — D01 covers schema changes (T01/T02); D02+D03 cover CLI change (T07)
- CHECK 6 Deps: PASS
  T01,T02: no deps; T03a,T03b→T01; T04→T02; T05→T02; T06→T04+T05;
  T07: no deps; T08→T07; T09-T30→T07; D01→T01+T02; D02→T07; D03→D02
- CHECK 7 Orphans: PASS
  A-R6-01→T01,T03a,T03b | A-R6-02→T01,T03a,T03b | A-R6-03→T02,T04,T05
  A-R6-04→T02,T04 | A-R6-05→T05,T06 | A-R6-06→T07,T08,T09-T30,D02,D03
  A-R6-07→T09-T30 | A-R6-08→T14
- CHECK 8 No R1-R5 rework: PASS — T25/T28/T29/T30 touch R4-modified prompts but are
  additive-only (different lines from R4 additions)

- Total findings: 8 (3 HIGH, 3 MED, 1 LOW — 0 CRIT)
- Total tasks: 30 code/config + 3 doc = 33 tasks
  - P0: T01,T02,T03a,T03b,T04,T05,T06 (7 tasks — blocking)
  - P1: T07,T08 (2 tasks)
  - P2: T09-T30 (22 tasks — parallelizable)
  - P3: D01,D02,D03 (3 tasks)

---

## Subagent Execution Strategy

Phase 1 — P0 (parallel F+G, then H):
  - Subagent F (worktree): T01 → T03a → T03b
  - Subagent G (worktree): T02 → T04
  - Subagent H (worktree, after G): T05 → T06 (also runs `pytest tests/ -k step_04 --tb=short -q` to catch any other inline step_04 test data)

Phase 2 — P1 (sequential):
  - Subagent I (worktree): T07 → T08

Phase 3 — P2 (parallel after T07):
  - Subagent J: T09-T19 (prompts 00-09, 11 files)
  - Subagent K: T20-T30 (prompts 10-16c, 11 files)

Phase 4 — P3 (after all code tasks):
  - Subagent L: D01 → D02 → D03

---

## Fixture Structure (Verified by Glob)

```
tests/fixtures/step_00/
  00_charter.json          ← T03a (valid — update: add stakeholders, user_segments, 2nd metric)
  valid_strict.json        ← T03b (valid — same updates)
  invalid_strict.json      ← DO NOT modify (invalid fixture, unchanged)
  test_01_cap.json         ← capabilities data used in cross-step tests — NOT a charter, no action

tests/fixtures/step_04/
  valid_comprehensive.json ← T04 (valid — add trace to each FR item, 2nd AC where missing)
  invalid_bad_trace.json   ← DO NOT modify (tests malformed trace FORMAT — still invalid after T02)
```

---

## Next Steps

All implementation tasks (T01-D03) listed in Part B above are staged and ready for parallel
subagent execution. Start with Phase 1 (P0 blocking tasks) using the subagent strategy outlined.
