# Review Series Index — DevSpec Toolkit v0.3.0 Structural Audit

## Series 1: Structural Audit (R1-R6)

Decomposition of `review_prompt_04_canonical_drift.md` into 6 executable reviews.

## Series 2: 4-Layer Determinism Closure (R7-R9)

Closes all semantic gaps across prompts (L1), schemas (L2), validators (L3), and CI gates (L4).

All reviews run **sequentially**: R1 → R2 → R3 → R4 → R5 → R6 → R7 → R8 → R9 (one at a time).

---

## Execution Order

```
Series 1: R1 (Areas 4,8) → R2 (Areas 7,10,11) → R3 (Areas 3,5) → R4 (Areas 1,2) → R5 (Area 9) → R6 (Areas 6,12,13)
Series 2: R7 (L1: Prompts) → R8 (L2: Schemas) → R9 (L3+L4: Validators+CI)
```

Each review assumes all prior reviews have been completed and their changes committed.

### Series 1: Structural Audit

| Order | ID | File | Areas | Priority | Notes |
|-------|----|------|-------|----------|-------|
| 1 | R1 | `r1_hygiene_invariants.md` | 4, 8 | P0 | Zero deps, quick wins |
| 2 | R2 | `r2_validation_infrastructure.md` | 7, 10, 11 | P0 | Infra foundation for R3-R6 |
| 3 | R3 | `r3_canonical_drift.md` | 3, 5 | P1 | Canonical lifecycle + drift |
| 4 | R4 | `r4_traceability_chain.md` | 1, 2 | P1 | Traceability chain |
| 5 | R5 | `r5_generation_quality.md` | 9 | P1 | Decision gate → schema change |
| 6 | R6 | `r6_schema_prompt_alignment.md` | 6, 12, 13 | P2 | Synthesis — closes all gaps |

### Series 2: 4-Layer Determinism Closure

| Order | ID | File | Layer | Gaps Closed | Priority | Est. Tasks | Notes |
|-------|----|------|-------|-------------|----------|-----------|-------|
| 7 | R7 | `r7_prompt_completeness.md` | L1 (Prompts) | 1-5 | P0-critical | 30-35 | 6-dimension audit, Metadata Contract, sourcing, vague→precise |
| 8 | R8 | `r8_schema_alignment.md` | L2 (Schemas) | 6-7 | P0-critical | 20-25 | 83 schema-prompt gaps → 0, additionalProperties fixes |
| 9 | R9 | `r9_validator_ci_closure.md` | L3+L4 (Validators+CI) | 8-15 | P0-critical | 30-35 | Cross-step IDs, extraction_intent, content derivation, W→E promotion |

---

## Phase Structure (all reviews)

Every review runs these phases in strict order:

| Phase | What | Who | When |
|-------|------|-----|------|
| 1 | File investigation | Explore subagents | Start |
| 2 | Implementation | general-purpose subagents (worktree isolation) | After Phase 1 |
| 3 | Integration test run | general-purpose subagent | After Phase 2 |
| 4 | Self-verification loop | general-purpose subagent | After Phase 3 |
| 5 | Write findings to file | general-purpose subagent | After Phase 4 VERIFIED |
| 6 | Post-implementation verify | Explore subagent | After all tasks executed |

Full protocol specification: `docs/audit/review_protocol.md`

---

## Subagent Protocol Summary (applies to all reviews)

### Main Agent
- **Forbidden**: Read, Edit, Write, Grep, Glob, Bash for file content
- **Allowed**: Spawn subagents, read text summaries, create TaskList, write final report
- **Token budget**: < 5K tokens per review session
- **Decision gates** (e.g., R5 option selection) are legitimate main-agent work

### Investigation (Phase 1)
- Use `Explore` subagent (fast, read-only, no isolation)
- Multiple Explore subagents can launch together for independent file groups

### Implementation (Phase 2)
- Use `general-purpose` subagent with `isolation: "worktree"`
- One worktree per logical change (separate subagents for separate files)
- Each subagent runs its own pytest at the end before reporting

### Integration (Phase 3)
- Use `general-purpose` subagent (no isolation) for final test runs
- Always run full pytest + relevant CLI commands as acceptance gate

---

## Shared Files Across Reviews

These files are modified by more than one review. Sequential execution (R1→R9) ensures each review reads the current state left by prior reviews.

| File | Modified by | What each review does |
|------|-------------|----------------------|
| `tools/specdev_tools/core/errors.py` | R3, R4, R5, R9 | R3 adds E211. R4 adds E561/562/563. R5 marks E511 deprecated. R9 adds E/W590-595 (cross-step, extraction_intent, coverage, vague, derivation, staleness). |
| `prompts/prompt_14_roadmap.md` | R4, R6, R7 | R4 adds seed-tech-stack. R6 hardens. R7 completes field coverage + sourcing. |
| `prompts/prompt_16a_impl_planner.md` | R4, R6, R7 | R4 adds milestone_ref. R6 hardens. R7 completes field coverage. |
| `prompts/prompt_16c_impl_reviewer.md` | R4, R6, R7 | R4 adds deliverable check. R6 hardens. R7 completes field coverage. |
| All 22 prompts | R6, R7, R8 | R6 partial hardening. R7 adds Metadata Contract, Field-by-Field, sourcing to all. R8 narrow bidirectional coherence adjustments only (aligning prompts where schema reveals structural constraints R7 didn't account for). |
| 19 step schemas (`schema/16_impl_context.schema.json` shared by 16/16a/16b/16c) | R6, R8 | R6 tightens 2 schemas. R8 tightens all to match R7 prompts. |
| `tools/specdev_tools/validation/validate.py` | R2, R9 | R2 fixes infra. R9 adds dynamic W→E promotion + extraction_intent wiring. |
| `tools/specdev_tools/validation/validators/step_*.py` (8 files) | R9 | R9 adds cross-step ID checks to steps 05, 06, 08, 09, 12, 13, 13a, 15. |
| `tools/step_order.json` | R6, R9 | R6 adds step_metadata. R9 populates extraction_intent for step 00, adds coverage_thresholds + content_derivation config. |
| `tests/test_prompt_contracts.py`, `test_prompt_schema_sync.py`, `test_cli.py` | R7 | R7 renames "B4 Metadata Contract" → "Metadata Contract" in all test file delimiters (3 files, 15 occurrences). |

**Rule for shared files**: Each review's subagent instructions include "read current state first" so changes from prior reviews are preserved.

---

## Output Files

Each review writes its findings to `docs/audit/findings/`:

| Review | Output File | Contents |
|--------|-------------|---------|
| R1 | `findings/r1_findings.md` | B* rename tasks + invariant engine fixes |
| R2 | `findings/r2_findings.md` | $ref paths + env behavior + submodule fix |
| R3 | `findings/r3_findings.md` | Alias lifecycle + partial drift detection |
| R4 | `findings/r4_findings.md` | E561/562/563 + seed consumption + traceability |
| R5 | `findings/r5_findings.md` | Decision record + generation_quality schema change |
| R6 | `findings/r6_findings.md` | Schema-prompt gaps + prompt hardening + discovery |
| R7 | `findings/r7_findings.md` | Prompt field coverage, Metadata Contract, sourcing, vague→precise |
| R8 | `findings/r8_findings.md` | Schema-prompt gaps closed, additionalProperties fixes, bidirectional coherence |
| R9 | `findings/r9_findings.md` | Cross-step IDs, extraction_intent, content derivation, W→E promotion, env-check |

All findings use the compact table format defined in `review_protocol.md`.

---

## Areas Cross-Reference

All 13 areas from the original `review_prompt_04_canonical_drift.md` are covered:

| Original Area | Review | Grouping Rationale |
|---------------|--------|-------------------|
| Area 1: Seed→Roadmap Traceability | R4 | Both areas share traceability_closure.py |
| Area 2: Roadmap→Implementation | R4 | Same file set as Area 1 |
| Area 3: Semantic Drift | R3 | All in canonical/ directory |
| Area 4: B* Test Hygiene | R1 | Isolated, no deps |
| Area 5: Canonical Alias Lifecycle | R3 | Same directory as Area 3 |
| Area 6: Prompt Hardening | R6 | Synthesis pass — needs all prior fixes |
| Area 7: Schema Validation Paths | R2 | All touch validate.py |
| Area 8: Invariant Engine | R1 | Isolated single file |
| Area 9: Generation Quality | R5 | Decision-first, isolated schema change |
| Area 10: Environment Behavior | R2 | Same files as Area 7 and 11 |
| Area 11: Submodule Integration | R2 | Same files as Area 7 and 10 |
| Area 12: Toolkit Discovery | R6 | Synthesis pass — needs step_order fixes |
| Area 13: Schema-Prompt Alignment | R6 | Synthesis pass — needs all schema fixes |

---

## 4-Layer Determinism Closure — Gap Inventory (R7-R9)

R1-R6 fixed structural issues. R7-R9 close **semantic gaps** across the 4-layer enforcement model:

| Layer | Role | Review | State After R6 | State After Closure |
|-------|------|--------|-----------------|---------------------|
| L1 — Prompts | Generation-side | R7 | ~70% field coverage, vague language, no sourcing | 100% coverage, zero vague, explicit sourcing |
| L2 — Schemas | Structural gate | R8 | 83 misalignments, 30 HIGH, rejection bugs | 0 HIGH, 0 rejection bugs |
| L3 — Validators | Semantic gate | R9 | 8/16 lack cross-step checks, no content propagation | 16/16 cross-step, content derivation active |
| L4 — CI Gates | Enforcement | R9 | 4 W-codes promotable | ALL W-codes promotable (dynamic pairing) |

### Gap Cross-Reference

| # | Gap | Severity | Layer | Review |
|---|-----|----------|-------|--------|
| 1 | Prompts don't cover 100% of schema fields | CRITICAL | L1 | R7 |
| 2 | 3 prompts produce schema-failing output | CRITICAL | L1 | R7 |
| 3 | No sourcing instructions for free-text fields | CRITICAL | L1 | R7 |
| 4 | Metadata Contract missing from all prompts | CRITICAL | L1 | R7 |
| 5 | Cross-cutting boilerplate issues in 17+ prompts | HIGH | L1 | R7 |
| 6 | 83 schema-prompt misalignments (30 HIGH) | CRITICAL | L2 | R8 |
| 7 | additionalProperties:false rejects prompt-required fields | CRITICAL | L2 | R8 |
| 8 | 8 of 16 validators have zero cross-step ID validation | CRITICAL | L3 | R9 |
| 9 | Content propagation absent | CRITICAL | L3 | R9 |
| 10 | extraction_intent inert | HIGH | L3 | R9 |
| 11 | Vague language scanning limited to assumptions | HIGH | L3 | R9 |
| 12 | hallucination_lint lacks content derivation | HIGH | L3 | R9 |
| 13 | Forward replay is ID-only | MED | L3 | R9 |
| 14 | Coverage metrics have no thresholds | MED | L3 | R9 |
| 15 | W→E promotion covers only 4 codes | MED | L4 | R9 |

### Cascade Order

```
R7 (L1: Prompts — source of truth)
  → R8 (L2: Schemas — tighten to match hardened prompts)
    → R9 (L3+L4: Validators + CI — build against final prompts and schemas)
```

Each layer is finalized before the next begins. Zero rework. ~80-95 total tasks.

**R7↔R8 Bidirectional Coherence**: R7 finalizes core prompt hardening. R8 may make narrow prompt adjustments where schema reality differs from R7's assumptions (e.g., adding missing enum values from schema, fixing structural nesting). These adjustments are scoped to bidirectional coherence only — no re-hardening or new field coverage.

### Verified Counts

| Item | Count | Notes |
|------|-------|-------|
| Prompt files | 22 | `prompts/prompt_00_*.md` through `prompts/prompt_16c_*.md` |
| Step schema files | 19 | `schema/00_charter.schema.json` through `schema/16_impl_context.schema.json`; steps 16a/16b/16c share `16_impl_context` |
| Total schema files | 20 | 19 step schemas + `schema/seed_manifest.schema.json` |
| B4 Metadata Contract refs | 15 | 3 test files: `test_prompt_contracts.py` (6), `test_prompt_schema_sync.py` (8), `test_cli.py` (1) |
| Existing error codes (E) | 22 | E110-E582 |
| Existing warning codes (W) | 15 | W110-W581, W140 |
| New R9 error codes | 12 | E590-E595 + W590-W595 |
