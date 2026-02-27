# Review Series Index — DevSpec Toolkit v0.3.0 Structural Audit

Decomposition of `review_prompt_04_canonical_drift.md` into 6 executable reviews.
All reviews run **sequentially**: R1 → R2 → R3 → R4 → R5 → R6 (one at a time).

---

## Execution Order

```
R1 (Areas 4,8) → R2 (Areas 7,10,11) → R3 (Areas 3,5) → R4 (Areas 1,2) → R5 (Area 9) → R6 (Areas 6,12,13)
```

Each review assumes all prior reviews have been completed and their changes committed.

| Order | ID | File | Areas | Priority | Notes |
|-------|----|------|-------|----------|-------|
| 1 | R1 | `r1_hygiene_invariants.md` | 4, 8 | P0 | Zero deps, quick wins |
| 2 | R2 | `r2_validation_infrastructure.md` | 7, 10, 11 | P0 | Infra foundation for R3-R6 |
| 3 | R3 | `r3_canonical_drift.md` | 3, 5 | P1 | Canonical lifecycle + drift |
| 4 | R4 | `r4_traceability_chain.md` | 1, 2 | P1 | Traceability chain |
| 5 | R5 | `r5_generation_quality.md` | 9 | P1 | Decision gate → schema change |
| 6 | R6 | `r6_schema_prompt_alignment.md` | 6, 12, 13 | P2 | Synthesis — closes all gaps |

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

These files are modified by more than one review. Sequential execution (R1→R6) ensures each review reads the current state left by prior reviews.

| File | Modified by | What each review does |
|------|-------------|----------------------|
| `tools/specdev_tools/core/errors.py` | R3, R4, R5 | R3 adds E211. R4 adds E561/562/563. R5 marks E511 deprecated. Each review reads current state first. |
| `prompts/prompt_14_roadmap.md` | R4, R6 | R4 adds seed-tech-stack + extraction rules. R6 hardens further. R6 marks R4's changes as RESOLVED. |
| `prompts/prompt_16a_impl_planner.md` | R4, R6 | R4 adds milestone_ref rule. R6 hardens further. |
| `prompts/prompt_16c_impl_reviewer.md` | R4, R6 | R4 adds deliverable check rule. R6 hardens further. |

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
