# P1-D: Self-Audit Gate & Scoring -- Findings

## Summary
- Total findings: 9
- Critical: 0 | High: 3 | Medium: 3 | Low: 2 | Info: 1

## Gate Inventory

25 gate headings across 22 prompt files. 3 files (16a, 16b, 16c) have two gate headings each.

| Step | Heading Text | Line | Gate Item Count | Gate Items Summary |
|------|-------------|------|----------------|-------------------|
| 00 | `## Self-Audit Gate (do not output)` | 69 | 6 | Problem statement, scope 3+, stakeholders, segments, metrics 2+, owner |
| 01 | `## Self-Audit Gate` | 68 | 4 | Charter goals mapped, verb/scope/owner, pre/postconditions, no duplicates |
| 02 | `## Self-Audit Gate` | 74 | 4 | Capability-component mapping, trace coverage, connections protocol/auth, external boundaries |
| 02a | `## Self-Audit Gate` | 69 | 4 | Four environments, CI gates, secrets names-only, compliance labels |
| 03 | `## Self-Audit Gate` | 70 | 3 | Key nouns present, metric units, no duplicates |
| 04 | `## Self-Audit Gate` | 70 | 4 | Capability-FR mapping, acceptance criteria 2+, pre/postconditions, traces |
| 05 | `## Self-Audit Gate` | 60 | 5 | HTTP/gRPC identifiers, request/response schemas, security, access control, access control gap questions |
| 06 | `## Self-Audit Gate` | 67 | 3 | FR/NFR invariant coverage, expression validity, lifecycle state transitions |
| 07 | `## Self-Audit Gate` | 63 | 2 | NFR completeness (metric/target/unit/method/owner), glossary alignment |
| 08 | `## Self-Audit Gate` | 68 | 2 | FR fixture coverage, input/expected alignment |
| 09 | `## Self-Audit Gate` | 64 | 4 | Tech versions/rationale, tech_stack alignment, dependencies, gap questions for dates |
| 10 | `## Self-Audit Gate` | 70 | 4 | Versioning strategy, PR rules, reviewer disciplines, gap questions |
| 11 | `## Self-Audit Gate` | 88 | 6 | target_ids non-empty, valid IDs, mitigations structured, edge_cases structured, domain-specific, access control gap |
| 12 | `## Self-Audit Gate` | 66 | 3 | Core validations + requires, coverage thresholds, gap questions |
| 13 | `## Self-Audit Gate` | 71 | 5 | Naming check (ext_), overlap check, library bloat, redefinition, flow check |
| 13a | `## Self-Audit Gate (do not output)` | 83 | 4 | Can read 00/01/04/05, identification of gaps, ratings, extension check |
| 14 | `## Self-Audit Gate` | 73 | 3 | Specs justify roadmap, high-priority items accounted, score threshold |
| 15 | `## Self-Audit Gate` | 72 | 3 | Route map match, public APIs/paths/methods, service skeleton |
| 16 | `# Self-Audit Gate` | 179 | 6 | commit_hash valid, active items have implementation, target_file_patterns explicit, docs_impact, deferred_reason, no anchor conflicts |
| 16a (1st) | `## Self-Audit Gate (Score Threshold)` | 78 | 0 | Score threshold only -- no step-specific items |
| 16a (2nd) | `## Self-Audit Gate` | 269 | 4+3 | Generic Coverage Closure (upstream IDs, placeholders, hallucination) + Extraction Mandate |
| 16b (1st) | `## Self-Audit Gate (Score Threshold)` | 180 | 0 | Score threshold only -- no step-specific items |
| 16b (2nd) | `## Self-Audit Gate` | 213 | 5+3 | Checklist coverage, file existence, spec_ref test coverage, no silent skips, ambiguity surfacing + generic checklist |
| 16c (1st) | `## Self-Audit Gate (Score Threshold)` | 234 | 0 | Score threshold only -- no step-specific items |
| 16c (2nd) | `## Self-Audit Gate` | 268 | 5+3 | Checklist-finding coverage, FR coverage in semantic_review, test file existence, no unverified complete items, unverifiable coverage + generic checklist |

**Corrected count**: 25 gate headings across 22 files (matches audit plan). The 3 duplicate-gate files each have one "(Score Threshold)" gate with zero step-specific items and one standard gate with full content.

## Token Cost Analysis

| Section | Total Words | Estimated Tokens (~1.33 tokens/word) |
|---------|------------|--------------------------------------|
| Self-Audit Gate (all 25 headings) | 6,613 | ~8,818 |
| -- of which: Score Threshold gates (3x, ~8 words each) | 24 | ~32 |
| -- of which: Coverage Closure subsections (22x) | ~3,300 | ~4,400 |
| -- of which: Step-specific gating items (22x) | ~3,289 | ~4,386 |

**Context**: These 6,613 words are consumed on every prompt invocation. The Coverage Closure subsections share substantial boilerplate (the 3-item generic checklist "Every upstream ID... / No placeholder tokens... / All required fields..." appears verbatim in all 22 prompts = ~660 words of pure duplication). Token cost assessment is deferred to P1-A for deduplication analysis.

## Findings

### FINDING-001: Score threshold "< 0.9" is undefined and unfalsifiable
- **Severity**: HIGH
- **Category**: GATE
- **Location**: All 22 prompts (e.g., `prompts/prompt_00_project_charter.md:70`)
- **Description**: Every prompt says "If score < 0.9, output clarifying questions only" but no prompt defines what the score IS, how it is computed, what scale it uses, or how gating items map to the numeric value. The LLM is asked to evaluate a score against a threshold that has no defined calculation methodology. This makes the gate non-deterministic -- different LLM invocations or models will produce different scores for identical inputs.
- **Evidence**: `prompt_00_project_charter.md:70`: "If score < 0.9, output clarifying questions only -- do not emit JSON." No prompt anywhere defines: score = f(gating_items). The agents.md protocol (line 30) adds: "If the private completeness score is < 0.9 or any gating item is missing" -- this is the only place that hints at a dual condition, but still provides no scoring formula.
- **Recommendation**: Replace the numeric threshold with a deterministic boolean: "If ANY gating item below cannot be satisfied from available context, enter Clarify mode -- output gap questions only, do not emit JSON." This preserves the flow-control function while eliminating the undefined scoring. The agents.md protocol already includes "or any gating item is missing" as an alternative, making the numeric score redundant.

### FINDING-002: Dual role confusion -- quality gate vs flow control mechanism
- **Severity**: HIGH
- **Category**: GATE
- **Location**: All 22 prompts, `docs/agents/agents.md:29-33`
- **Description**: The Self-Audit Gate serves two conflicting purposes: (1) a quality gate (LLM self-checks its output completeness) and (2) a flow control mechanism (determines whether to enter Clarify or Emit phase). The agents.md protocol treats it as flow control (Phase A vs Phase B decision), while the prompt text treats it as a pre-emission quality checklist. These are different concerns: flow control should be about input sufficiency ("do I have enough information?"), while quality gating should be about output correctness ("is my output complete?"). Mixing them creates ambiguity about WHEN the gate is applied.
- **Evidence**: `agents.md:29-30`: "Apply the Self-Audit Gate. If the private completeness score is < 0.9 or any gating item is missing: Output only a short, bulleted list of targeted gap questions." This frames it as an INPUT sufficiency check. But gate items like `prompt_00:76` "Success metrics include unit+target+measurement_method... for >=2 metrics" are OUTPUT quality checks -- they describe properties of the artifact being generated, not properties of the input context.
- **Recommendation**: Clarify the gate's purpose as a **pre-emission input sufficiency check**: "Before generating output, verify you have sufficient information to satisfy all gating items. If any item cannot be satisfied from available context, enter Clarify mode." This aligns with agents.md's flow-control framing and makes the gate testable: the LLM checks inputs, not its own output.

### FINDING-003: 16a/16b/16c duplicate gates serve no distinct purpose
- **Severity**: MEDIUM
- **Category**: GATE
- **Location**: `prompts/prompt_16a_impl_planner.md:78,269`, `prompts/prompt_16b_impl_coder.md:180,213`, `prompts/prompt_16c_impl_reviewer.md:234,268`
- **Description**: Each of the three Trinity Loop prompts has TWO Self-Audit Gate headings. The first (labeled "Score Threshold") contains ONLY the "score < 0.9" line with zero step-specific gating items. The second (labeled just "Self-Audit Gate") contains the actual step-specific Coverage Closure items. The first gate is entirely redundant -- it adds 8 words per file (24 words total) and no unique content. It appears to be an artifact of mechanical insertion (the R6 remediation task T09-T30 added "score < 0.9" to all prompts, but these three already had gate sections, resulting in duplication).
- **Evidence**: `prompt_16a_impl_planner.md:78-79`: `## Self-Audit Gate (Score Threshold)` / `If score < 0.9, output clarifying questions only -- do not emit JSON.` -- followed by FORBIDDEN ACTIONS (lines 81+), then at line 269: `## Self-Audit Gate` with actual Coverage Closure content. The first gate has no gating items, making it pure overhead.
- **Recommendation**: Remove the "(Score Threshold)" headings from 16a/16b/16c and merge the score threshold line into the existing Self-Audit Gate section. This eliminates 3 redundant headings and potential LLM confusion about which gate to evaluate.

### FINDING-004: Gate item counts vary widely without clear justification
- **Severity**: LOW
- **Category**: GATE
- **Location**: All 22 prompts
- **Description**: Gate item counts range from 2 (steps 07, 08) to 6 (steps 00, 11, 16). Some steps with complex output schemas have fewer gate items than simpler steps. Step 07 (NFRs) has only 2 gate items despite having 9 required fields and complex metric structures. Step 13 (Extension Generator) has 5 gate items that are not "gating items" at all -- they are anti-pattern checks ("Naming Check", "Overlap Check", "Library Bloat") that read like review criteria rather than input-sufficiency checks.
- **Evidence**: Step 07 gate items: (1) NFR completeness, (2) glossary alignment -- but the schema requires `nfr_id`, `name`, `category`, `metric`, `target`, `unit`, `measurement_method`, `severity`, `owner`, `trace`. Step 13 gate items are phrased as questions to the LLM about its OWN output quality ("Are any extensions redefining standard API routes?") rather than input-sufficiency checks.
- **Recommendation**: Normalize gate items to a consistent methodology: each should test whether required INPUT CONTEXT is available to produce the required output. Derive gate items from the step's upstream dependencies and schema `required[]` array, not from ad-hoc quality criteria. This is a design improvement, not a deduplication issue (P1-A scope).

### FINDING-005: Gate items are step-specific and cannot be fully templated
- **Severity**: INFO
- **Category**: GATE
- **Location**: All 22 prompts
- **Description**: Despite structural similarity, gate items ARE step-specific. Step 00 checks for problem statements and stakeholder roles; step 05 checks for HTTP/gRPC identifiers and access control models; step 11 checks for threat target_ids validity and mitigation structures. The per-prompt inclusion is justified for the step-specific items. However, three elements are generic and duplicated verbatim across all 22 prompts: (1) the "score < 0.9" line, (2) the Coverage Closure header/framework, and (3) the 3-item generic checklist (upstream IDs consumed, no placeholders, no hallucination).
- **Evidence**: The 3-item generic checklist appears verbatim in all 22 prompts: "- [ ] Every upstream ID from ingested context has been consumed / - [ ] No placeholder tokens remain (TBD, TODO, FIXME, XXX) / - [ ] All required fields populated from actual upstream data (not hallucinated)". This is ~30 words x 22 = 660 words of pure duplication.
- **Recommendation**: The step-specific gate items should remain per-prompt. The generic boilerplate (score threshold line, generic 3-item checklist) should be extracted to `shared_expectations.md` per P1-A deduplication analysis. The Coverage Closure subsection framework could be templatized with only the step-specific verification items remaining per-prompt.

### FINDING-006: agents.md defines a dual condition that prompts do not reflect
- **Severity**: MEDIUM
- **Category**: GATE
- **Location**: `docs/agents/agents.md:30`, all 22 prompts
- **Description**: The agents.md protocol (line 30) states: "If the private completeness score is < 0.9 **or any gating item is missing**". This dual condition (score OR boolean) means a single missing gating item should trigger Clarify mode regardless of score. However, no prompt includes this boolean fallback -- they all say only "If score < 0.9". An LLM following the prompt text (not agents.md) could assign a 0.95 score despite a missing gating item and proceed to Emit mode, violating the agents.md protocol.
- **Evidence**: `agents.md:30`: "If the private completeness score is < 0.9 or any gating item is missing:" vs `prompt_01_capabilities.md:69`: "If score < 0.9, output clarifying questions only -- do not emit JSON." The "or any gating item is missing" clause is absent from all 22 prompts.
- **Recommendation**: Add the boolean fallback to all prompts: "If ANY gating item below cannot be satisfied, OR if overall completeness confidence is below 0.9, enter Clarify mode." Better yet, replace the score entirely with the boolean gate per FINDING-001.

### FINDING-007: Step 13 gate items are anti-pattern checks, not input-sufficiency checks
- **Severity**: MEDIUM
- **Category**: GATE
- **Location**: `prompts/prompt_13_extension_generator.md:72-77`
- **Description**: Step 13's gate items are phrased as output review criteria, not input-sufficiency checks. Items like "Are any extensions redefining standard API routes already in 05_interface_contracts.json?" and "Are you creating extensions for items already expressible in existing step schemas?" ask the LLM to review its OWN planned output for anti-patterns. This is fundamentally different from checking whether input context is sufficient. These items belong in a "Negative Constraints" or "Common Pitfalls" section (which step 13 already has, but separately).
- **Evidence**: Lines 72-76: Five items phrased as questions about the LLM's own output quality (Naming Check, Overlap Check, Library Bloat, Redefinition, flow check). Compare with step 01 gate items: "All in-scope charter goals map to at least one capability" -- this is an input-sufficiency check (do I have charter goals to map?).
- **Recommendation**: Move the anti-pattern items to the existing Negative Constraints section or a new "Pre-Emission Validation" section. Replace the gate items with input-sufficiency checks like: "All extension candidates are grounded in domain requirements not expressible in core steps 00-15" and "Interface contracts from step 05 are available for overlap detection."

### FINDING-008: generation_quality is fully purged from prompts, schemas, and tools
- **Severity**: LOW
- **Category**: GATE
- **Location**: N/A (verification finding)
- **Description**: `generation_quality` has been completely removed from all active code paths. No prompt references it. No schema defines it. No tool reads or writes it. The only remaining references are in: (1) historical audit/review documents under `docs/audit/` (expected -- these document the removal decision), (2) `WIP/trans/` working documents (stale), (3) four test assertions in `tests/unit/generation/test_schema_contracts.py` and `tests/unit/validation/linters/test_spec_quality_lint.py` that assert generation_quality is NOT required (negative tests confirming the removal).
- **Evidence**: Grep results: 0 matches in `prompts/`, 0 matches in `schema/`, 0 matches in `tools/`. 4 matches in `tests/` are all negative assertions: `self.assertFalse(any("missing top-level 'generation_quality'" in e ...))`. These tests verify the field is NOT required, confirming the purge is complete and tested.
- **Recommendation**: No action needed. The purge is complete and verified by negative test assertions. The `docs/audit/` references are historical records and should be preserved.

### FINDING-009: Coverage Closure subsection is structurally coupled to Self-Audit Gate
- **Severity**: HIGH
- **Category**: GATE
- **Location**: All 22 prompts
- **Description**: Coverage Closure appears as a `### Coverage Closure` subsection under `## Self-Audit Gate` in all 22 prompts. It serves a different function from the gate itself: the gate checks input-sufficiency (can I produce this artifact?), while Coverage Closure checks output-completeness (did I consume all upstream IDs?). By nesting Coverage Closure under Self-Audit Gate, both checks are conflated into a single evaluation moment. An LLM might skip Coverage Closure if it passes the gate items, or might treat Coverage Closure failures as Clarify triggers when they should be Emit-phase validation failures.
- **Evidence**: In agents.md, Coverage Closure is referenced alongside Self-Audit Gate but with a distinct purpose: "For Steps 05-16c, context is resolved via `Coverage Closure` in the `Self-Audit Gate`" (line 27). The shared_expectations.md (line 7) also couples them: "Each step's prompt defines its specific Definition of Ready (DoR) within the Self-Audit Gate and Coverage Closure sections." The structural coupling obscures that these are two separate checks.
- **Recommendation**: The Coverage Closure content is step-specific and valuable. However, it should be structurally separated from the Self-Audit Gate to clarify that: (1) Self-Audit Gate = input sufficiency = Clarify/Emit decision, (2) Coverage Closure = output completeness = post-generation validation. This could be a sibling heading (`## Coverage Closure`) rather than a subsection (`### Coverage Closure` under `## Self-Audit Gate`). Note: the actual text extraction is P1-A scope; this finding addresses the design coupling.

## Design Assessment

### Is the Self-Audit Gate a quality gate or a flow control mechanism?

**Answer**: It is PRIMARILY a flow control mechanism that has been overloaded with quality gate responsibilities.

The agents.md protocol (Section 3, lines 29-33) defines the gate as the Phase A/Phase B decision point. Its core function is: "Do I have enough information to emit, or must I ask clarifying questions?" This is flow control.

However, gate items in individual prompts mix two concerns:
1. **Input sufficiency** (flow control): "All in-scope charter goals map to at least one capability" -- checks whether input data exists
2. **Output quality** (quality gate): "Success metrics include unit+target+measurement_method for >=2 metrics" -- checks whether the OUTPUT will meet quality standards

The flow control function is valuable and well-defined. The quality gate function is problematic because: (a) the scoring methodology is undefined, (b) quality checks on output that hasn't been generated yet conflate planning with execution, and (c) quality validation is better handled by schema validation and linters post-emission.

### Interaction with Two-Phase Protocol

The Self-Audit Gate is the decision mechanism for the Two-Phase Protocol (Clarify vs Emit). The protocol in agents.md is well-designed:
1. Read inputs
2. Prepare context
3. Apply gate -> Clarify if insufficient, Emit if sufficient
4. Validate post-emission

The gate fits cleanly into step 3. The problem is not the protocol but the gate's implementation: undefined scoring and mixed concerns. If the gate were simplified to a deterministic boolean ("can all gating items be satisfied?"), it would align perfectly with the protocol.

### Should the gate be kept?

**Yes**, but reformed. The gate provides genuine value as a flow-control mechanism:
- It prevents premature emission when context is insufficient
- It forces the LLM to enumerate gaps before guessing
- The step-specific gating items encode domain knowledge about what each step NEEDS

The reform should:
1. Replace "score < 0.9" with deterministic boolean logic
2. Separate input-sufficiency checks (gate) from output-completeness checks (Coverage Closure)
3. Move anti-pattern checks out of the gate into Negative Constraints
4. Extract the generic 3-item checklist to shared_expectations.md (P1-A scope)
5. Remove the 3 redundant "(Score Threshold)" headings from 16a/16b/16c
