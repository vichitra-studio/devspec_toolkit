# Prompt System Audit — Master Plan

## Scope

Full audit of `prompts/`, `docs/prompts/`, `docs/agents/`, seed templates, `spec/common/seed_manifest.json`, related schema descriptions, and cross-step traceability — against 18 user concerns.

## Repo Root

```
/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/
```

## User Concerns (18 points)

1. Prompts too mechanical — insufficient natural language synthesis guidance for LLMs
2. JSON schema descriptions — quality, clarity, specificity, completeness
3. Coverage Gap Reporting — is it needed?
4. Context To Ingest / Extraction Intent / Seed Ingestion Protocol — can we optimise? Are they justified?
5. Which prompts mention which seed docs
6. Self-Audit Gate / generation_quality — needed or token burden?
7. Canonical Registry section — same for all steps? Can it be shared?
8. Quick Reference / Field-by-Field Guidance / Metadata Contract / Output Contract / Output Rules — needed? Schema-enforced?
9. prompt-context downstream consumers — required/useful?
10. Common prompt sections → shared expectations
11. seed_manifest.json — required? docs_policy purpose? Replace with step_order.json? Lazy-loading docs? Agent doc awareness?
12. Step 09 milestone sequencing / Step 14 task decomposition — dependency resolution
13. Tech stack capture — which step is the source of truth?
14. Per-step intent, purpose, goal — does the prompt provide enough guidance context?
15. Trace matrix update frequency
16. Semantic drift across steps + end-to-end requirement integrity (seed → charter → FR → roadmap → impl → test)
17. Self-explanatory prompts + requirement translation completeness + test/evidence binding
18. Detailed review report + implementation plan (= P3 + P4 output)

## Phases

| Phase | Name | Agents | Depends On | Description |
|-------|------|--------|------------|-------------|
| P0 | Baseline Capture | Inline | — | Capture prompt LOC, sections, seed refs, consumers, test baseline |
| P1 | Parallel Deep Review | 7 agents (P1-A through P1-G) | P0 | Each agent owns an exclusive scope; no overlap |
| P3 | Consolidation | 1 agent | P1 | Merge all findings, deduplicate, rank by severity |
| P4 | Fix Plan | 1 agent | P3 | Produce ordered fix list with dependency batches |
| P5 | Fix Execution | N agents | P4 | Apply fixes per the plan |
| P6 | Verification | 1 agent | P5 | Re-run baseline, confirm all 1,344 tests still pass |
| P7 | Follow-up | — | P6 | Track deferred items from P3 master findings |

## Phase Dependencies

```
P0 → P1 (7 parallel) → P3 → P4 → P5 → P6 → P7
```

> **Note**: P2 is skipped. It was used as a research alignment phase in the schema audit and is not needed here. Numbering preserved for consistency.

## Output File Naming

- Prompt files: `p{N}-prompt-{concern}.md`
- Output files: `p{N}-out-{concern}.md`

---

## Key Codebase Facts (ALL from verified P0 baseline, Rev 3)

### Prompt System

| Metric | Value |
|--------|-------|
| Step prompt files | 22 |
| Step prompt total LOC | 5,727 |
| Step prompt total words | ~46,021 |
| Estimated token footprint | ~61K tokens |
| Migration template files | 19 (steps 00–16; no 16a/16b/16c) |
| Migration template total LOC | 851 |
| Verified-identical boilerplate LOC | 748 (34 lines/file × 22 files) |
| Near-identical boilerplate LOC | ~227 (Tool Execution 161 + Metadata Contract 66) |
| Total duplicated content | ~975 lines (~17.0% of prompt LOC) |
| JSON blocks in prompts | 29 total |
| shared_expectations.md LOC | 51 |

### Section Frequencies

| Section (universal, 22/22) | Level |
|-----------------------------|-------|
| Schema Authority, Path Variables, Purpose, Tool Execution | H2 |
| Hardening Protocol, Canonical Registry, Canonical Binding Rules, Metadata Contract | H2 |
| Self-Audit Gate (25 total headings, 3 files have duplicates) | Mixed |
| Role, Output Contract, Schema Reference | H1 |
| Extraction Intent, Coverage Closure | H3 |

### Seed & Config

| Metric | Value |
|--------|-------|
| Seed template files | 2 (seed_templates/seed_overview.md, seed_templates/seed_tech_stack.md) |
| seed_manifest.json step_requirements | Steps 00–04 only; steps 05–16c have none |
| docs_policy consumers | 1 (step_16.py reads doc_paths only); README fields have 0 consumers |
| allowed_upstream_dependencies consumers | 5 modules |
| Docs referenced by any prompt | 7 paths (3 are host-repo paths, 3 are example-only) |
| Docs NEVER referenced by prompts | 46 of 53 |
| canon/manifest.json referenced by | ALL 22/22 prompts |

### Traceability

| Metric | Value |
|--------|-------|
| Lint-enforced traceability links | 4–5 of 9 (E560, W561, W562, W563) (counting methodology: each distinct E/W code enforcing a specific step-to-step link) |
| Partial lint links | 1 (W592 threshold) |
| Prompt-only links | 3 (Seed→00, 04→05 per-item, 16c→09/14) |
| Schema description coverage | 925/925 = 100% |

### Tests

| Metric | Value |
|--------|-------|
| Tests collected | 1,344 |
| Tests passed | 1,344 |
| prompt-sync status | OK |

---

## Prior Audit Impact

The schema audit and tools/tests audit made changes that affect the prompt system. P1 agents must account for these:

1. **Enum extraction to $defs** (commit c498c93): 17 inline enums extracted into 14 shared `$defs` atoms via `$ref`. Output Contract examples in prompts may reference old inline enum structures.
2. **Description coverage closed to 100%** (commit 547c1f2): 925/925 properties now have descriptions. P1-F should focus on description QUALITY, not quantity.
3. **generation_quality removed**: Removed from all 19 step schemas, `spec_quality_lint.py`, and `DRIFT_SENSITIVE_FIELDS`. P1-D should check for stale prompt/doc references.
4. **docs_lint.py removed** (commit 7b37adb): `docs_policy` in seed_manifest has partial dead consumers. P1-C should account for this.
5. **Error code migration**: Tools/tests audit migrated error handling to `SpecError`. Validator signatures may have changed.

---

## P1 Agent Scopes (7 Agents, Single Container)

Each agent runs once in a single container. P3 consolidates findings across agents.

### P1-A: Prompt Bloat & Shared Expectations

**User points**: #3 (coverage gap reporting), #7 (canonical registry same for all), #8 (quick reference, field-by-field, metadata contract, output rules — schema-enforced?), #10 (common sections → shared expectations)

**Exclusive scope**:
- Quantify boilerplate: for each of the ~975 duplicated lines, categorise as (a) truly identical, (b) near-identical with step-name swaps, (c) structurally similar but with step-specific content
- Coverage Gap Reporting / Coverage Closure section: present in 22/22 prompts. Is it enforced by any validator? Is it redundant with Self-Audit Gate? Does removing it lose any unique information?
- Canonical Registry (21/22 identical, 1 step-12 variant) + Canonical Binding Rules (22/22 identical): can this be fully extracted to shared_expectations.md? Check if any step has step-specific canonical instructions.
- Quick Reference: present in 17/22. Compare content against Field-by-Field Guidance in same prompts — is it a strict subset? Can it be removed without information loss?
- Metadata Contract: present in 22/22. Compare against Output Contract JSON examples — is the info already there?
- Output Rules: 20/22 at H1. Which rules are generic (applicable to all steps) vs step-specific? Can generic rules move to shared_expectations.md?
- Hardening Protocol (22/22, verified identical): can it move to shared_expectations.md?
- Schema Authority + Path Variables + Tool Execution: can they move to shared_expectations.md?
- shared_expectations.md is currently 51 LOC — what should its target content be after absorbing shared sections?
- **Baseline fact**: `docs/prompts/shared_expectations.md` exists and is referenced by 8/22 prompts. It currently covers: DoR/guardrails, working increment, checks, canonical reuse rules, canonical resolution protocol, one-go quality protocol, step-order policy, failure modes.

**Questions**:
1. For each shared section (Hardening Protocol, Canonical Registry, Canonical Binding Rules, Schema Authority, Path Variables, Tool Execution, Coverage Closure, generic Output Rules, Metadata Contract), would extracting to shared_expectations.md lose any step-specific information? List any exceptions.
2. Is Coverage Gap Reporting consumed by any validator? What unique value does it add beyond Self-Audit Gate?
3. Is Quick Reference a strict information subset of Field-by-Field Guidance in every prompt where both exist?
4. Which Output Rules items are truly generic (identical meaning across all 22 prompts) vs step-specific?
5. What is the projected LOC reduction per prompt after extraction? What is the projected new size of shared_expectations.md?
6. Are there any prompts where removing a "boilerplate" section would actually remove step-specific guidance that happens to be embedded within the shared structure?
7. What is unique about step 12's Canonical Registry section? Is it a meaningful variant or a copy error?

**Output**: `p1-out-bloat.md`

---

### P1-B: Synthesis Guidance & Step Intent

**User points**: #1 (prompts too mechanical), #14 (per-step intent/purpose/goal and guidance adequacy)

**Exclusive scope**:
- For EACH of the 22 steps, produce a structured assessment:
  1. **Step intent**: What is this step supposed to achieve? (derived from Purpose section + pipeline context)
  2. **Synthesis challenge**: What is the hard reasoning problem the LLM must solve at this step?
  3. **Guidance quality**: Rate as STRONG / ADEQUATE / THIN based on: does the prompt explain HOW to reason, not just WHAT to output?
  4. **Missing guidance**: What specific synthesis guidance is absent? (e.g., conflict resolution, implicit requirement extraction, prioritisation, scope decisions)
  5. **Anti-pattern coverage**: Does the prompt warn against common LLM failure modes specific to this step?
- Read ALL 22 prompts in full. For each, read the Operating Flow, Heuristics, Best Practices, Common Pitfalls, Negative Constraints, and FORBIDDEN ACTIONS sections.
- Identify which prompts are STRONG vs THIN using the rating criteria above. Then compare patterns: what do STRONG prompts do differently from THIN ones? (Do not presume ratings — determine them independently.)
- Read `seed_templates/seed_overview.md` and `seed_templates/seed_tech_stack.md` to understand the quality and structure of seed inputs that Step 00 must process.
- **Baseline facts**: Steps with unique operating flows: 11 (Attack→Trace→Mitigate), 13 (Analyze→Filter→Plan), 14 (5-step), 16/16a (Drift Check), 16b (Requirement-First), 16c (Evidence-Based Audit). Steps with distinct roles: 11, 13, 13a, 14, 16, 16a, 16b, 16c.

**Questions**:
1. For each of the 22 steps, what is the synthesis challenge and does the prompt adequately address it?
2. Which steps have the largest gap between the difficulty of the synthesis challenge and the guidance provided?
3. What patterns from the highest-rated prompts could be applied to the lowest-rated ones?
4. Does any prompt explain HOW to handle conflicting upstream inputs? Which ones should?
5. Does any prompt explain HOW to identify implicit requirements not stated in upstream specs? Which ones should?
6. For Step 00 specifically: given the rich seed templates (seed_overview.md has deep-dive coaching prompts, seed_tech_stack.md has system-type-specific guidance), does the Step 00 prompt provide enough guidance to extract all the structured information from these documents?

**Output**: `p1-out-synthesis.md`

---

### P1-C: Seed Manifest, Config Optimisation & Doc Awareness

**User points**: #4 (context to ingest / extraction intent / seed ingestion overlap), #5 (seed doc matrix), #9 (prompt-context utility), #11 (seed_manifest.json, docs_policy, step_order.json, lazy-loading, agent doc awareness), #13 (tech stack source of truth)

**Exclusive scope**:
- **seed_manifest.json assessment**:
  - `docs_policy`: README fields have 0 consumers (docs_lint.py removed). `step_16.py` reads only `doc_paths`. Is docs_policy justified? Should it be removed or trimmed to just `doc_paths`?
  - `nested_order`: consumed by seed_lint.py (lines 261-264). Has exactly 1 entry ("foundation") for 2 seeds. Over-engineering?
  - `step_requirements`: only covers steps 00-04. The original vision was to map contextual docs to steps — this got lost. Should it be expanded to cover steps 05-16c with relevant doc references?
  - Can seed_manifest.json be partially replaced by step_order.json? Which fields are seed-specific vs pipeline-config?
- **step_order.json assessment**:
  - `allowed_upstream_dependencies` (~276 lines, 5 consumers): is it derivable from `steps` array under strict_waterfall policy? Can it be replaced by a function?
  - `coverage_thresholds` (2 consumers): is it enforced? Is its location optimal?
  - `downstream_consumers` (3 consumers): curated, NOT derivable — assess utility.
- **Context To Ingest / Extraction Intent / Seed Ingestion Protocol overlap**:
  - Steps 00-04 have 3 overlapping sections: Seed Order & Mandatory Sources (6/22), Context To Ingest (6/22), Extraction Intent (22/22). Quantify the overlap. Can the first two be eliminated?
- **Doc awareness gap**:
  - 46 of 53 docs are never referenced by any prompt. Key unreferenced docs: agents.md, governance_architecture.md, getting_started.md, extension_schemas.md, error-codes.md, path_conventions.md, 6 workflow guides.
  - Do agents currently read ANY of these docs during step execution? Check agents.md protocol.
  - Propose a lazy-loading mechanism: which docs should be available to which steps, and under what conditions?
- **Tech stack source of truth**:
  - seed_tech_stack.md → Step 02 (system_sketch) → Step 09 (impl_plan) → Step 14 (roadmap). Is there a single source of truth or does tech stack get re-declared at each step? What enforces consistency?
- **prompt-context utility**: `specdev prompt-context NN` shows downstream consumers. 3 consumers (cli.py, dag_lint.py, forward_replay_check.py). Is this useful enough to keep?
- **Baseline facts**: Seed templates exist at `seed_templates/seed_overview.md` (170 LOC) and `seed_templates/seed_tech_stack.md` (231 LOC). These are HOST REPO templates copied during init. Prompts reference `docs/seed/seed_overview.md` and `docs/seed/seed_tech_stack.md` which are the host repo copies.

**Questions**:
1. For each field in seed_manifest.json: who reads it? What happens if removed? Is the location optimal?
2. Can `allowed_upstream_dependencies` be replaced by a derivation function? What is the exact derivation logic?
3. What is the overlap between Seed Order, Context To Ingest, and Extraction Intent in steps 00-04? Can the first two be removed?
4. Which of the 46 unreferenced docs would be valuable to which steps? Propose a mapping.
5. Can seed_manifest.json's `step_requirements` be expanded to include doc references per step (lazy-loading)?
6. Is there a validator that ensures Step 09 tech_stack is consistent with Step 02 system_sketch?
7. Is prompt-context useful enough to justify the `downstream_consumers` data structure?

**Output**: `p1-out-config.md`

---

### P1-D: Self-Audit Gate & Scoring

**User points**: #6 (self-audit gate / generation_quality — needed or token burden?)

**Exclusive scope**:
- Self-Audit Gate appears in ALL 22 prompts (25 total headings; 3 files have duplicates). Every one says "score < 0.9" but NO prompt defines the scoring methodology.
- `generation_quality` was removed from all 19 step schemas, from `spec_quality_lint.py`, and from `DRIFT_SENSITIVE_FIELDS` during the prior schema audit. Verify no prompt still references it and that no stale references remain in docs.
- Assess the Self-Audit Gate's actual function: is it a quality gate (LLM self-checks) or a flow control mechanism (Clarify vs Emit)?
- The two-phase protocol (Clarify → Emit) is defined in `docs/agents/agents.md`. How does the Self-Audit Gate interact with this protocol?
- Gate item count ranges from 3 (step 14) to 8 (step 00) — P1-D should recount using a consistent methodology (count explicit sub-items under 'Gating items to check' or equivalent). Are gate items step-specific and valuable, or generic and redundant?
- Steps 16a, 16b, 16c have the gate TWICE — why? Is the duplicate intentional?
- Token cost: ~100 words per prompt for Self-Audit Gate section × 22 prompts = ~2,200 words (~3K tokens). Is this justified?
- **Baseline fact**: `docs/agents/agents.md` defines the two-phase protocol (Phase A = Clarify if score < 0.9, Phase B = Emit). This is the only place that connects the score threshold to a behavioral decision (verified from codebase; not tracked in P0 baseline).

**Questions**:
1. Can the "score < 0.9" be replaced with a deterministic boolean gate ("if ANY gating item cannot be satisfied, enter Clarify mode")?
2. Are gate items step-specific enough to justify per-prompt inclusion, or should they be generated from a template?
3. What is the actual token cost of Self-Audit Gate + Coverage Closure across all 22 prompts?
4. Why do 16a/16b/16c have duplicate gates? Is one the "plan quality" gate and the other the "output quality" gate?
5. If the gate is kept, should it move to shared_expectations.md with only the gate items remaining per-prompt?
6. Has generation_quality been fully purged from prompts and docs? Do any stale references remain after the schema audit removal?

**Output**: `p1-out-gate.md`

### P1-A / P1-D Scope Boundary

P1-A owns the **deduplication** question for Self-Audit Gate and Coverage Closure: is the text identical across prompts? Can it be extracted to shared_expectations.md? What is the LOC savings?

P1-D owns the **design** question: is the gate mechanism effective? Are gate items valuable and step-specific? Should the score threshold be replaced with boolean logic? What is the token cost?

If both agents find issues with the same section, P1-A's finding addresses redundancy and P1-D's finding addresses effectiveness. P3 consolidation merges them.

Coverage Closure redundancy assessment belongs to P1-A. P1-D includes Coverage Closure only in aggregate token cost calculations.

---

### P1-E: End-to-End Requirement Integrity & Semantic Drift

**User points**: #12 (step 09 sequencing / step 14 decomposition), #15 (trace matrix), #16 (semantic drift + requirement integrity), #17 (self-explanatory prompts, requirement translation, test/evidence binding)

**Exclusive scope**:
- **End-to-end requirement chain**: Trace the full path seed → step 00 → step 01 → step 02 → step 02a → step 03 → step 04 → step 05 → step 06 → step 07 → step 08 → step 09 → step 14 → step 16a → step 16b → step 16c. Steps 10 (governance), 11 (red team), 12 (CI gates), 13 (extensions), 13a (completeness), and 15 (scaffold) are governance/security/extension steps — they are not in the primary requirement chain but should be checked for semantic consistency with the main chain.. For EACH link:
  1. What enforcement exists? (lint, schema, prompt-only)
  2. Can requirements silently drop at this link?
  3. What specific prompt guidance prevents drops?
- **Step 09 milestone sequencing**:
  - Does the schema have `depends_on` for milestones? (Check `schema/09_impl_plan.schema.json`)
  - Does the prompt guide the LLM to sequence milestones so dependencies are resolved?
  - Can a milestone that requires API X come after a milestone that delivers API X?
- **Step 14 task decomposition**:
  - Does the schema link tasks to specific FRs? (Check `schema/14_roadmap.schema.json`)
  - Does the prompt ensure every FR in a milestone's `fr_refs` has at least one task?
  - Can a milestone reference `fr-user-login` but have zero tasks implementing login?
  - Does `depends_on` for tasks enforce that dependencies within a milestone are resolved before the current task?
- **Semantic drift detection**:
  - Go through EVERY step (00 through 16c). For each step, check: does the prompt instruct the LLM to use exact terminology from upstream steps? Or can it paraphrase/reinterpret?
  - Is there a validator that checks semantic consistency of traced IDs across steps?
  - Can a capability in Step 01 be described differently in Step 04's FR, Step 05's API, and Step 07's NFR?
- **Test/evidence binding**:
  - Step 16a: does the prompt require specifying how each checklist item will be tested?
  - Step 16b: does the prompt require creating/updating test files for every code change?
  - Step 16c: does the prompt require verifying that tests exist and pass for every implementation?
  - Is the test suite updated as a mandatory side-effect of the trinity loop?
- **Trace matrix**: confirmed updated only when FRs/APIs/fixtures/NFRs change (steps 04, 05, 07, 08). Is this sufficient? Should step 14 (roadmap) also trigger a matrix update?
- **Step 16 priority**: Step 16 (impl_context) is the discovery-to-implementation handoff point and should receive extra scrutiny for traceability enforcement, even though it is not the terminal step in the primary chain.
- **Baseline facts**: 4–5 of 9 traceability links have full lint enforcement (E560, W561, W562, W563) (counting methodology: each distinct E/W code enforcing a specific step-to-step link), 1 has partial lint (W592), 3 are prompt-only. Extraction Mandate sections exist in 3/22 prompts (04, 14, 16a).

**Questions**:
1. For EACH of the 22 steps: what is the traceability input, what is the traceability output, and what enforcement exists?
2. Does Step 09 schema support milestone dependency ordering? If not, what schema change is needed?
3. Does Step 14 schema link tasks to specific FRs? If not, what schema change is needed?
4. Which steps are most vulnerable to semantic drift? Where would a drift lint add the most value?
5. Is the trinity loop (16a→16b→16c) airtight for test/evidence binding, or are there escape hatches?
6. Should Extraction Mandates (currently 3/22) be added to more steps? Which ones?
7. Does Step 14 need to trigger a trace matrix update?
8. Recount the lint-enforced traceability links using a consistent methodology: for each E/W code, identify the exact step-to-step link it enforces. Resolve the 4-vs-5 ambiguity.
9. If recommending new lint rules (e.g., semantic drift lint, milestone dependency lint), specify: what error code, what it checks, which files it reads, and what it reports. These feed directly into P4's 'Validator implementation' batch.

**Output**: `p1-out-integrity.md`

### P1-B / P1-E Scope Boundary

P1-B owns **guidance quality**: does the prompt explain HOW to reason about upstream inputs?

P1-E owns **traceability enforcement**: does the prompt ensure requirements are not dropped and terminology is consistent?

If both agents find issues with the same prompt's upstream handling, P1-B's finding addresses the reasoning guidance gap and P1-E's finding addresses the traceability enforcement gap. P3 consolidation merges them.

### P1-C / P1-G Scope Boundary

P1-C owns the **mechanism**: how should docs be loaded/referenced by prompts? (lazy-loading, seed_manifest expansion, etc.) P1-C should propose the mechanism in generic terms without assuming which specific docs are valuable.

P1-G owns the **content evaluation**: which docs are stale? Which are valuable? What is each doc's relationship to specific steps?

Since P1-C and P1-G run in parallel, P1-C cannot use P1-G's output. P3 consolidation must merge P1-G's doc valuations into P1-C's mechanism design. P4's fix plan must produce the final doc-to-step mapping by combining both agents' outputs.

---

### P1-F: Schema Description Quality & Prompt-Schema Alignment

**User points**: #2 (schema descriptions — quality, clarity, specificity, completeness)

**Exclusive scope**:
- Schema description coverage is 925/925 = 100% (post-schema-audit). The question is now QUALITY, not quantity.
- For each schema (26 total: 19 step + 5 core (atoms, canon, collections, errors, step_base) + seed_manifest + step_order), assess description quality:
  1. Are descriptions **specific** enough for an LLM to understand what value to produce? (vs generic boilerplate like "The ID of the item")
  2. Are descriptions **unambiguous**? Could two reasonable LLMs interpret them differently?
  3. Do descriptions include **constraints** that the schema enforces (min lengths, patterns, enums)?
  4. Do descriptions include **examples** where the field name alone is insufficient?
  5. Do descriptions explain **relationships** to other fields or upstream artifacts?
- Focus on the 5 schemas that were below 100% before the schema audit: 02_system_sketch, 15_scaffold, 16_impl_context, canon, collections (per schema audit commit `547c1f2`). Assess whether newly-added descriptions are high quality or bulk-generated.
- Check prompt-schema sync: `specdev prompt-sync` returns OK, but does the Output Contract JSON in each prompt accurately reflect the CURRENT schema? Spot-check 5 prompts against their schemas.
- **Baseline fact**: DRIFT_SENSITIVE_FIELDS = ("dependencies", "trace", "canonical_refs_used"). prompt-sync checks required fields, property drift for these 3 fields, canonical ref enforcement, and output contract validation.

**Questions**:
1. How many descriptions are genuinely helpful vs boilerplate? (Sample at least 50 descriptions across 5+ schemas)
2. Which descriptions would an LLM most likely misinterpret? List the top 10 ambiguous descriptions.
3. Are there fields where the description contradicts the schema constraint? (e.g., description says "optional" but schema has it in required)
4. Do Output Contract examples in prompts match current schema required fields? Spot-check 5 prompts.
5. Are there schema properties that need descriptions beyond what was bulk-added in the description coverage push?

**Output**: `p1-out-descriptions.md`

---

### P1-G: Migration Templates & Documentation Gaps

**User points**: #11 (agent doc awareness, repo documentation evaluation, extension_schemas relevance)

**Exclusive scope**:
- **Migration templates** (19 files, 851 LOC in `prompts/migration/`):
  - No templates for steps 16a, 16b, 16c — is this a gap or intentional?
  - Do templates align with current schemas? (schema changes from prior audits may have outpaced templates)
  - Are templates used by any tool? Check `tools/specdev_tools/migration/` for template consumers.
  - What is the purpose of migration templates vs step prompts?
- **Documentation evaluation** (53 files in `docs/`):
  - For EACH doc file, assess: (a) is it current or stale? (b) does it provide context useful to any step? (c) should it be referenced by a prompt or shared_expectations.md?
  - Key docs to evaluate in depth: `docs/agents/agents.md`, `docs/architecture/governance_architecture.md`, `docs/developers/getting_started.md`, `docs/developers/extension_schemas.md`, `docs/developers/error-codes.md`, `docs/developers/path_conventions.md`, `docs/developers/workflows/*.md`
  - `docs/audit/` (14 files): are these historical artifacts or living documents? Should agents reference them?
- **Extension schemas**: `docs/developers/extension_schemas.md` is relevant to Step 13 but not referenced by the prompt. What context would it add?
- **Step-specific docs**: are there docs that are specifically relevant to individual steps but not referenced?

**Questions**:
1. Are migration templates (16a, 16b, 16c) needed? What breaks without them?
2. Do migration templates reflect current schemas? List any drift.
3. Which of the 53 docs files are stale and should be archived vs current and should be referenced?
4. For each step, which docs (if any) would add valuable context if referenced?
5. Should `docs/agents/agents.md` be mandatory reading for all steps, or just 16a-16c?
6. What is the relationship between migration templates and step prompts? Can they be consolidated?

**Output**: `p1-out-docs.md`

---

## P1 Agent Protocol

### Output format (per agent)

```markdown
# P1-{X}: {Title} — Findings

## Summary
- Total findings: N
- Critical: N | High: N | Medium: N | Low: N | Info: N

## Findings

### FINDING-{NNN}: {Title}
- **Severity**: CRITICAL | HIGH | MEDIUM | LOW | INFO
- **Category**: BLOAT | SYNTHESIS | CONFIG | GATE | INTEGRITY | DESCRIPTION | DOCS
- **Location**: {file}:{line} or {file}:{section_name}
- **Description**: {what is wrong}
- **Evidence**: {concrete example from the code/prompt}
- **Recommendation**: {specific fix}
```

### Severity Criteria

| Severity | Criteria |
|---|---|
| CRITICAL | Breaks validation, causes requirement drops, security issue, blocks LLM from producing correct output |
| HIGH | >50 LOC total duplication, missing critical synthesis guidance, architectural concern, silent requirement loss |
| MEDIUM | Moderate redundancy, partial guidance gaps, inconsistency, suboptimal configuration |
| LOW | Style issues, naming, minor inconsistency, nice-to-have improvements |
| INFO | Observations, future considerations, design tradeoffs |

### Constraints
- Each agent operates ONLY within its exclusive scope
- No code changes — read-only analysis
- Cite exact file paths and line numbers
- Use current branch state for all code tracing — schema audit and tools/tests audit may have changed files
- Use P0 baseline (Rev 3) numbers as ground truth
- Read ALL 22 prompt files for agents that need cross-prompt analysis (P1-A, P1-B, P1-E)
- Read actual file content — do not assume based on names or prior knowledge
- Do NOT use /vc-review, /vc-plan, /vc-parallel-fix, or any vc-* skills/agents. Do NOT use Explore agents. Use only standard tools (Read, Grep, Glob, Bash).
- Prior audit decisions are authoritative. If a finding overlaps with work done in the schema audit (`WIP/done/schema_audit/`) or tools/tests audit (`WIP/done/tool_audit/`), cite the prior decision and assess whether the prompt system needs to ALIGN WITH the prior decision, rather than re-opening it.
- Step prompt files are at `prompts/prompt_NN_name.md` (22 files). Migration templates are at `prompts/migration/template_name.md` (19 files). Seed templates are at `seed_templates/` (2 files).

---

## P3 Consolidation Rules

1. **Cross-agent reconciliation**:
   - Multiple agents report same finding → **corroborated** (keep most detailed version, cross-reference others)
   - Single agent finds it → **verified genuine** (valid if evidenced)
   - Severity disagreement across agents → resolve to higher unless lower has justification

2. **Deduplication across agents**: If P1-A and P1-B both find the same issue (e.g., a prompt section is both bloat AND has thin guidance), keep in the primary agent's scope (per ownership assignments in P1 scopes) and cross-reference from the other agent.

3. **Output**: `p3-out-master-findings.md` with AUDIT-NNN IDs, grouped by severity then by target file.

4. **Constraints**: Do NOT use /vc-review, /vc-plan, /vc-parallel-fix, or any vc-* skills/agents. Do NOT use Explore agents.

5. P3 + P4 outputs collectively satisfy user concern #18 (detailed review report + implementation plan).

---

## P4 Fix Plan Rules

- **One task = one file** (exceptions: fixture sets in same directory, schema + fixture pairs, or prompt deduplication tasks that extract a shared section to shared_expectations.md — these may touch 1 target + N prompt files as a single logical task)
- **Batch ordering**: Foundation (shared_expectations.md) → Config cleanup (seed_manifest, step_order) → Prompt deduplication → Synthesis guidance additions → Schema changes → Validator implementation → Documentation updates
- **Dependency check**: If any prompt change depends on a schema change (e.g., references a new schema field), the schema change must be batched earlier. P4 must verify no forward dependencies exist within the batch order.
- **Test gate**: `source devspec_env/bin/activate && pytest tests/ -x --tb=short` after each batch
- **Gate protocol**: On failure, revert specific file, identify root cause, defer task
- **Constraints**: Do NOT use /vc-review, /vc-plan, /vc-parallel-fix, or any vc-* skills/agents. Do NOT use Explore agents. Fix plan must be directly consumable by a human orchestrating agents manually.
- **Sequencing rule**: Tasks must be sequenced so dependencies are always resolved before a task is picked. No rework. No forward references.

---

## P5 Execution Protocol

- Apply fixes per P4 plan, one batch at a time.
- Test gate after each batch: `source devspec_env/bin/activate && pytest tests/ -x --tb=short`
- On test failure: revert specific file, identify root cause, defer task.
- Constraints: Do NOT use /vc-review, /vc-plan, /vc-parallel-fix, or any vc-* skills/agents. Do NOT use Explore agents.

## P6 Verification Protocol

- Re-run P0 baseline metrics: prompt LOC, word counts, section frequencies, test count.
- Confirm 1,344+ tests pass (test count may increase if new tests added).
- Run `specdev prompt-sync spec --repo-root .` — must return OK.
- Run `specdev validate-all spec --repo-root .` — must pass.
- Produce delta report: what changed from P0 baseline.
- Constraints: Do NOT use /vc-review, /vc-plan, /vc-parallel-fix, or any vc-* skills/agents. Do NOT use Explore agents.

---

## Timeline Estimate

| Phase | Work |
|---|---|
| P0 | COMPLETE (Rev 3, 3 review rounds, 40 fixes applied) |
| P1 | 7 agents × 1 container = 7 agent runs (parallel) |
| P3 | 1 consolidation agent |
| P4 | 1 fix plan agent |
| P5 | Batch execution (estimated 5-8 batches) |
| P6 | Verification pass |
| P7 | Deferred items tracked in P3 master findings |

---

## Revision Log

**Rev 1** (2026-03-20) — Fixes from plan review (24 findings: 1 CRIT, 5 HIGH, 9 MED, 8 LOW, 1 verified-correct)

| Finding | Fix Applied |
|---------|-------------|
| 001 (HIGH) | P1-A: Canonical Registry corrected to 21/22; added Q7 about step 12 variant |
| 002 (CRIT) | P1-D: generation_quality status updated — already removed in schema audit |
| 003 (LOW) | P1-C: Seed template LOC corrected (171→170, 232→231) |
| 004 (MED) | Traceability count changed to "4–5 of 9"; added P1-E Q8 to resolve |
| 005 (LOW) | Added P2 skip note |
| 006 (LOW) | Added P7 Follow-up phase |
| 007 (MED) | P1 constraints: added "Do NOT use Explore agents" |
| 008 (LOW) | P1-D: gate item recount instruction added |
| 009 (HIGH) | Added P1-A/P1-D scope boundary section |
| 010 (MED) | Coverage Closure ownership clarified in boundary section |
| 011 (MED) | Added P1-B/P1-E scope boundary section |
| 012 (MED) | Added P1-C/P1-G scope boundary section |
| 013 (LOW) | P1-G: user point sub-numbering fixed |
| 014 (LOW) | P1-F: core schema count corrected to 5 |
| 015 (HIGH) | Added Prior Audit Impact section |
| 016 (HIGH) | P1 constraints: added prior audit decisions rule |
| 017 (HIGH) | P4: one-task-one-file exception for prompt deduplication |
| 018 (MED) | P4: added dependency check rule |
| 019 (MED) | Added P5/P6 protocol sections |
| 020 (LOW) | P1-D: agents.md baseline fact sourcing noted |
| 021 | No fix needed (verified correct) |
| 022 (LOW) | P3: added note that P3+P4 satisfy concern #18 |
| 023 (MED) | Addressed by FINDING-007 |
| 024 (MED) | P1-B: removed pre-judged STRONG/THIN examples |

**Rev 2** (2026-03-20) — Fixes from second plan review (4 findings: 0 CRIT, 0 HIGH, 1 MED, 3 LOW)

| Finding | Fix Applied |
|---------|-------------|
| R2-001 (MED) | P1-B Q3: removed pre-judged step numbers (11, 06, 07) |
| R2-002 (LOW) | P6: added agent constraint line |
| R2-003 (LOW) | P1-C: allowed_upstream_dependencies 274 → ~276 |
| R2-004 (LOW) | Revision log: severity count corrected (10 MED → 9 MED + 1 verified-correct) |

**Rev 3** (2026-03-20) — Fixes from third plan review (9 findings: 0 CRIT, 0 HIGH, 2 MED, 7 LOW)

| Finding | Fix Applied |
|---------|-------------|
| R3-001 (LOW) | Self-Audit Gate heading count 24 → 25 in two locations |
| R3-002 (LOW) | Docs file count 54 → 53; unreferenced 47/54 → 46/53 |
| R3-003 (MED) | P1-C/P1-G boundary: acknowledged parallel execution; deferred merge to P3/P4 |
| R3-004 (MED) | P1-E chain expanded to include steps 02, 02a, 03; governance steps noted as excluded |
| R3-005 (LOW) | Trace matrix triggers: added step 07 (NFRs) |
| R3-006 (LOW) | Added prompt/template file paths to P1 Agent Protocol |
| R3-007 (LOW) | P1-E: flagged step 16 as high-priority handoff point |
| R3-008 (LOW) | P1-E: added Q9 for validator specification format |
| R3-009 (LOW) | P1-F: sourced "5 schemas below 100%" claim to schema audit commit |
