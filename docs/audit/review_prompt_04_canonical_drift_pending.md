<review_prompt>
# Deep Dive System Review: Canonical Drift, Traceability Closure & Prompt Hardening
# Pending Items Only — R7 Focus

---

## Review Status Overview (R1–R7)

> Areas 1, 2, 5, 7, 8, 9, 10, 11 are **RESOLVED** — omitted from this prompt. See `review_prompt_04_canonical_drift.md` for full history.

**Pending (this review)**:

| Area | Title | Status | Covered By | Summary |
|------|-------|--------|-----------|---------|
| 3 | Semantic Drift Across Steps | **PARTIALLY ADDRESSED** | R3 | Forward replay semantic content remains structural-only post-R2 |
| 4 | B0-B8 Cleanup & Repo Hygiene | **PARTIALLY ADDRESSED** | R1 | `## B4 Metadata Contract` header absent from all 22 prompt files silently voids Output Contract test suite; broader hygiene not done |
| 6 | Holistic Prompt Hardening | **PARTIALLY ADDRESSED** | R4 + R6 | 6a–6f core hardening pending across all 22 prompts |
| 12 | Toolkit Discovery Deficit | **DISMISSED** | R6 | Inline consumer tables, validation gate summaries, enrichment mechanism pending |
| 13 | Schema–Prompt Contract Alignment | **PARTIALLY ADDRESSED** | R6 | 20 step schemas (01, 02, 02a, 03, 05–16c) unaudited |

---

## Context: Goal & Intent of Changes
**You must evaluate the system against these specific definitions of success:**

### 1. Problem Statement
The DevSpec Toolkit (v0.3.0) has structural gaps in thirteen interconnected areas: seed-to-roadmap traceability, roadmap-to-implementation completeness, cross-step semantic drift detection, test suite hygiene (legacy B* naming), canonical alias lifecycle enforcement, prompt hardening against hallucination and assumption, schema validation path robustness, invariant engine soundness, generation quality self-report trust, environment-dependent validation behavior, submodule integration path integrity, toolkit discovery deficit in prompts, and schema-prompt contract misalignment. These gaps are not isolated — they form a dependency chain where upstream weaknesses (e.g., thin validators, missing traceability checks, untrusted self-reports, git-root mismatch in the primary deployment model) propagate downstream into unreliable implementation artifacts. Additionally, the AI agents generating artifacts have near-zero awareness of the toolkit infrastructure beyond the single prompt they receive — they cannot see downstream consumers, validation rules, or the pipeline DAG, producing artifacts that are structurally valid but poorly optimized for downstream extraction.

### 2. Goal
Produce a **complete, dependency-ordered remediation plan** that closes all identified gaps with zero rework. Every fix must be grounded in verified file paths and line numbers. The plan must be executable by an AI agent without further human consultation.

### 3. Intent
Treat this as a **structural integrity audit** — not a feature review. The question is not "does each piece work in isolation?" but "does the entire pipeline guarantee that upstream requirements flow through every step to implementation without loss, drift, or hallucination?"

### 4. Purpose
Ensure the DevSpec Toolkit enforces a **deterministic, lossless pipeline** from seed documents through roadmap to implementation, where every prompt eliminates assumptions, every validator catches semantic drift, and every canonical reference is lifecycle-managed.

---

## Role
You are a **Principal Systems Architect** and **Specification Integrity Auditor** with deep expertise in schema-driven development pipelines, AI prompt engineering, and deterministic workflow enforcement. Your task is to perform a rigorous, evidence-based review of the `devspec_toolkit` repository and produce two deliverables: a Detailed Review Report (Part A) and a Dependency-Ordered Implementation Plan (Part B).

---

## Repository Context

### Toolkit Structure
```
devspec_toolkit/
├── schema/                          # JSON Schemas for every step + core/ (atoms, collections, errors)
├── canon/                           # Canonical registry (manifest.json, aliases.json)
├── tools/
│   ├── specdev_tools/
│   │   ├── cli.py                   # Entry point
│   │   ├── core/                    # errors, registry, trace_types, changelog_parser
│   │   ├── validation/
│   │   │   ├── validate.py          # Main validation orchestrator
│   │   │   ├── validators/          # Per-step validators (step_00.py .. step_16c.py)
│   │   │   ├── seed_lint.py         # Seed document linter
│   │   │   ├── quality_lint.py      # Spec quality linter
│   │   │   ├── hallucination_lint.py # Hallucination detection
│   │   │   ├── traceability_closure.py # FR/API/NFR traceability
│   │   │   ├── dependency_order_lint.py # Step ordering
│   │   │   ├── forward_replay_check.py # Forward replay validation
│   │   │   ├── invariants_check.py  # Invariant enforcement
│   │   │   ├── governance_check.py  # Commit governance
│   │   │   └── matrix.py            # Trace matrix generation
│   │   ├── canonical/
│   │   │   ├── lint.py              # Canonical ref linter
│   │   │   ├── integrity.py         # Cross-artifact drift (E210)
│   │   │   ├── registry.py          # Canonical registry + alias resolution
│   │   │   └── autofix.py           # Canonical autofix suggestions
│   │   ├── generation/              # Prompt generator, schema sync, differ
│   │   └── migration/               # Planner, runner
│   ├── schema_registry.json         # Step name → JSON Schema path map
│   ├── step_order.json              # Strict waterfall dependency DAG
│   └── trace_matrix.json            # Generated traceability matrix
├── prompts/                         # Deterministic prompt contracts (prompt_00..prompt_16c)
│   ├── prompt_00_project_charter.md
│   ├── prompt_01_capabilities.md
│   ├── prompt_02_system_sketch.md
│   ├── prompt_02a_delivery_baseline.md
│   ├── prompt_03_glossary.md
│   ├── prompt_04_functional_requirements.md
│   ├── prompt_05_interface_contracts.md
│   ├── prompt_06_invariants.md
│   ├── prompt_07_nfrs.md
│   ├── prompt_08_fixtures.md
│   ├── prompt_09_impl_plan.md
│   ├── prompt_10_governance.md
│   ├── prompt_11_redteam.md
│   ├── prompt_12_ci_gates.md
│   ├── prompt_13_extension_generator.md
│   ├── prompt_13a_completeness_assessment.md
│   ├── prompt_14_roadmap.md
│   ├── prompt_15_scaffold.md
│   ├── prompt_16_impl_context.md
│   ├── prompt_16a_impl_planner.md
│   ├── prompt_16b_impl_coder.md
│   └── prompt_16c_impl_reviewer.md
├── spec/                            # Generated spec artifacts (NN_name.json + NN_name.guide.md)
├── tests/                           # pytest suite
│   ├── fixtures/                    # Per-step valid/invalid JSON fixtures
│   ├── integration/                 # Step-level integration scripts
│   ├── test_schema_contracts.py     # Schema contract tests (contains B4 naming)
│   ├── test_prompt_contracts.py     # Prompt contract tests (contains B4 naming)
│   └── ...
├── docs/
│   ├── audit/                       # Prior review prompts (01_system, 02_tooling, 03_docs)
│   ├── agents/                      # Agent protocol (manifest.json)
│   └── developers/                  # Developer documentation
└── canon/
    ├── manifest.json                # Canonical vocabulary registry
    └── aliases.json                 # Alias → canonical mappings with status
```

### Spec Pipeline (Steps 00–16c)
The workflow is a **strict forward-only waterfall**. Any upstream change requires full replay of all downstream steps. Steps are numbered: `00 01 02 02a 03 04 05 06 07 08 09 10 11 12 13 13a 14 15 16 16a 16b 16c`.

| Phase | Steps | Purpose |
|---|---|---|
| Phase 0 | Seed docs | `seed_overview.md` + `seed_tech_stack.md` before any formal specs |
| Phase I · Discovery | 00–12 | Charter → Capabilities → System Sketch → Glossary → FRs → APIs → Invariants → NFRs → Fixtures → Impl Plan → Governance → Red Team → CI Gates |
| Phase II · Impl | 13–16c | Extension Generator → Completeness Assessment → Roadmap → Scaffold → Trinity Loop (16a plan / 16b code / 16c review) |

### Prior Review History
- **Review 01 (System)**: Architecture, schema design, error taxonomy, validation pipeline
- **Review 02 (Tooling)**: CLI commands, validators, linters, canonical tools, generation/migration
- **Review 03 (Documentation)**: Docs coverage, audience clarity, context preservation
- **This Review (04)**: Cross-cutting structural integrity — traceability, drift, prompts, hygiene, engine soundness, self-report trust, environment determinism, submodule integration, toolkit discovery, schema-prompt alignment
- **This Review (R7 — Pending)**: Continuation of Review 04. Five areas remain: semantic drift (forward replay only), test hygiene (B4 Metadata Contract header), prompt hardening (6a–6f), toolkit discovery (consumer tables/enrichment), schema-prompt alignment (20 unaudited steps).

---

## Review Objectives

You must investigate and report on the **five remaining areas** below. For each area, the "Verified Starting Points" and "Remaining Gaps" are confirmed open items — use them as anchors but **do not treat them as exhaustive**. You must independently verify each gap and discover additional gaps through your own exploration.

---

### Area 3: Semantic Drift Across Steps

> **STATUS: PARTIALLY ADDRESSED — Pending items listed below**
> E211 PARTIAL_DRIFT with artifact-level precision added (R3 T07/T08). Thin validators for steps 06, 07, 08, 12, 13a expanded (R3 T09–T14a). Step 04 semantic checks added (R6 T05/T06). Forward replay semantic content validation remains unverified.

> **Semantic drift must be addressed at all three layers**: L1 generation (prompts + sourcing), L2 schema (structural enforcement), L3 validators (drift detection). R9 closes the validator layer (W594 content derivation via token co-occurrence, W595 downstream staleness in forward_replay_check.py). The generation layer is addressed by Artifact Hydration (see new area — future improvement, out of scope).

**Question**: Does the toolkit detect when the same concept drifts in meaning, naming, or scope as it flows through the pipeline?

**What to examine**:
- `tools/specdev_tools/canonical/integrity.py` — The E210 `CROSS_ARTIFACT_DRIFT` detection system:
  - Lines 62-66, 110-114: E210 error emission points
  - Lines 214-243: `_collect_observed_semantics()` — gathers `_ref` fields for drift analysis. Check whether this detects **partial drift** (e.g., 2 of 3 references updated to a new term, 1 still using the old term).
  - Lines 162-169: Canonical refs mismatch variant
  - Lines 296-300: Unresolved canonical semantic variant
- `tools/specdev_tools/validation/forward_replay_check.py` — Does it check semantic correctness of replayed artifacts, or only file existence and structural validity?
- Cross-reference: If step 04 defines `fr-user-login` and step 05 references it as `fr-login`, is this caught? Where?

**Verified Starting Points**:
| Gap | File | Detail |
|-----|------|--------|
| Forward replay may be structural only | `validation/forward_replay_check.py` | Verify whether it checks semantic content or only file existence |

### Remaining Gaps

- **Forward replay semantic content** (`validation/forward_replay_check.py`): R2 fixed the path/git-root issues but did not add semantic content validation. The check still verifies file existence and structural schema validity only — it does not detect semantic regressions (e.g., a concept renamed in step 02 that contradicts step 01). This verified starting point was in scope for the original review and remains unresolved. Investigate whether `forward_replay_check.py` runs any semantic comparison or only structural checks post-R2.

→ Distilled to: R9 Gap 13 (FULLY COVERED)

---

### Area 4: B0-B8 Cleanup & Repo Hygiene

> **STATUS: PARTIALLY ADDRESSED — Pending items listed below**
> B4 function renames completed in 5 test files (R1 T4a–T4e). The `## B4 Metadata Contract` section header gap was explicitly filed as a Known Issue in R1 and deferred out of scope.

**Question**: Does the test suite contain legacy naming from prior project phases (B0-B8 batch naming) that should be cleaned up?

**What to examine**:
- Search ALL test files for any `B[0-8]` or `b[0-8]` references in test names, docstrings, comments, or fixture names.
- Check for:
  - Dead test fixtures in `tests/fixtures/` that are no longer referenced
  - Test files that duplicate coverage
  - Inconsistent test naming conventions across the suite
  - Test helper functions that could be shared but are duplicated
- `tests/test_prompt_contracts.py` and `tests/test_prompt_schema_sync.py` — These test files use `## B4 Metadata Contract` as a delimiter string. When the header is absent from prompt files, the test loops hit `continue` and skip silently, causing the entire Output Contract validation to vacuously pass. Verify whether this header exists in any prompt file, and whether these tests actually execute any validation loops.

**Verified Starting Points**:
| Gap | File | Detail |
|-----|------|--------|
| `## B4 Metadata Contract` header absent | `tests/test_prompt_contracts.py`, `tests/test_prompt_schema_sync.py` | Tests use this string as delimiter; absent → test loops skip silently → Output Contract validation vacuously passes |

### Remaining Gaps

- **`## B4 Metadata Contract` section header missing from all 22 prompt files** (`tests/test_prompt_contracts.py`, `tests/test_prompt_schema_sync.py`): Tests use this string as a delimiter. When it is absent, the test loops hit `continue` and skip silently. **The entire Output Contract validation in the test suite is vacuously passing — zero prompts are actually being tested for their output contract fields.** R7 resolves the B4-specific gap: rename `## B4 Metadata Contract` → `## Metadata Contract` in 3 test files (tests/test_prompt_contracts.py: 6 occurrences, tests/test_prompt_schema_sync.py: 8 occurrences, tests/test_cli.py: 1 occurrence) AND add `## Metadata Contract` section to all 22 prompt files. Reference R7 Subagents D and E for implementation. The broader hygiene checks (dead test fixtures, duplicate coverage, inconsistent naming conventions beyond B4) remain unresolved.

→ Distilled to: R7 Gaps 4 (Subagents D+E) (FULLY COVERED)

---

### Area 6: Holistic Prompt Hardening

> **STATUS: PARTIALLY ADDRESSED — Pending items listed below**
> Prompts 16a/16b/16c: milestone_ref binding rule, milestone context loading, deliverable verification added (R4 A-R4-07/08/09). All 22 prompts: `specdev prompt-context <step>` reference added (R6 T09–T30). All 22 prompts: Self-Audit Gate score threshold "If score < 0.9, output clarifying questions only" added (R6 T09–T30). Step 14 seed consumption verified complete (R4 A-R4-10). Core 6a/6b/6c/6d/6e/6f hardening remains pending across all prompts.

**Question**: Does every prompt (00–16c) guarantee complete, correct, assumption-free output that is fully compliant with seed documents, system requirements, and ALL upstream artifacts?

**This is the most critical and broadest area.** It is NOT limited to canonical reference enforcement — it covers the entire prompt contract for deterministic, lossless spec generation.

**What to examine for EVERY prompt** (`prompts/prompt_00_project_charter.md` through `prompts/prompt_16c_impl_reviewer.md`):

#### 6a. Exhaustive Upstream Input Consumption
- Does the prompt explicitly list ALL upstream artifacts it must consume (per `step_order.json` dependencies)?
- For each listed upstream artifact, does the prompt specify WHAT to extract and HOW to use it?
- Example: `step_order.json` declares that step 14 requires `09_impl_plan.json`, `00_charter.json`, `04_functional_requirements.json`, `13_extension_generator.json`, `13a_completeness_assessment.json`. Does `prompt_14_roadmap.md` contain explicit extraction instructions for each?

#### 6b. Deterministic Instructions (Zero-Inference Output)
- Are there any instructions that rely on agent judgment, inference, or "best effort"? These must be replaced with deterministic rules.
- Does the prompt use vague language like "consider", "if appropriate", "as needed", "relevant", "may include"? Each of these is a hallucination vector.
- Does the prompt have a `## Schema Authority` section delegating ALL structural constraints (types, enums, required markers, patterns, minItems) to the schema? Prompts must not duplicate schema constraints — field definitions, type annotations, enum value lists, and minItems restatements belong in the schema, not the prompt.
- Does the prompt eliminate vague language ("consider", "if appropriate", "as needed", "may include") and provide explicit sourcing instructions for synthesis fields (which upstream artifact, which field path)?

#### 6c. Seed Document Compliance
- Does every prompt that should reference seeds (per `step_order.json` `required_seed_inputs`) explicitly instruct the agent to:
  1. Read the seed document(s)
  2. Extract specific information from them
  3. Reflect that information in specific output fields
  4. Populate `seed_refs` with actually-used seed IDs?

#### 6d. Fallback & Escalation Rules
- When information is missing or ambiguous in upstream artifacts, does the prompt specify:
  - A concrete fallback action (not "use your best judgment")?
  - An escalation mechanism (e.g., emit a clarification question, halt and report)?
- Does the prompt implement the Two-Phase **Clarify → Emit** protocol with a Self-Audit Gate score threshold?

#### 6e. Canonical Reference Enforcement
- Does the prompt instruct the agent to use ONLY terms from `canon/manifest.json` for controlled vocabularies?
- Does the prompt require `canonical_refs_used`, `canonical_proposals`, and `canonical_conflicts` in output?

#### 6f. Semantic Fidelity of Synthesis Fields
- Prompts currently give no guidance on how faithfully to render upstream meaning in synthesis fields (descriptions, rationale, intent, acceptance_criteria). An AI can reference the correct upstream artifact, pass sourcing checks, yet paraphrase or reinterpret the meaning — passing all structural validation while semantically drifting.
- Schema descriptions (R8 Subagent H) carry sourcing guidance for each field. Vague language elimination (6b) constrains synthesis field quality.
- Semantic completeness of synthesis fields is enforced by the combination of: (a) extraction_intent manifest injected into prompt (what must be covered), (b) E591 field-presence validator, (c) W594 token co-occurrence with upstream content, and (d) fresh LLM review comparing completed artifact against prompt in a clean session. No schema additions required for completeness enforcement.
- See Artifact Hydration area for the generation-layer optimization (future improvement, out of scope).

**Cross-reference with validators**: For each prompt, check whether the corresponding validator (`validation/validators/step_NN.py`) enforces the same requirements. If a prompt requires a field but the validator doesn't check it, that's a gap.

**Verified Starting Points**:
| Gap | File | Detail |
|-----|------|--------|
| Prompts lack exhaustive upstream consumption rules | All `prompts/prompt_*.md` | No systematic enforcement that every declared upstream input is consumed and reflected in output |
| Thin validators can't enforce prompt contracts | `validation/validators/step_04.py` (21 LOC) etc. | If the prompt requires 20 fields, but the validator only checks 3, the prompt contract is unenforceable |

### Remaining Gaps

- **6a (Exhaustive Upstream Input Consumption)**: No prompt explicitly lists all upstream artifacts it must consume *and* what specifically to extract from each, per `step_order.json` dependencies. Adding a 2-line CLI reference is not equivalent to per-artifact extraction instructions. Cross-reference Area 12: if extraction_intent injection (Area 12) is implemented, 6a is resolved as a consequence — the injected manifest IS the per-artifact extraction instruction. 6a and Area 12 are the same gap approached from different angles.
- **6b (Deterministic Instructions / Zero-Inference)**: Vague language ("consider", "if appropriate", "as needed", "may include", "where relevant") was not systematically eliminated across all 22 prompts. R6 added the gate threshold but did not audit or remove inference-reliant language.
- **6c (Seed Document Compliance)**: No prompt (beyond 16a/16b/16c) has explicit: read seed → extract specific fields → reflect in specific output fields → populate `seed_refs`.
- **6d (Fallback & Escalation)**: No prompt specifies a concrete fallback action when upstream data is missing beyond the generic <0.9 clarification gate. "Use your best judgment" equivalents remain. Additionally: when upstream content cannot be traced to any upstream artifact or seed, the prompt must explicitly route it — not silently omit, not silently include. The instruction must state: untraceable content MUST be added to `coverage_gaps[]` with the upstream item reference and reason. Clarify→Emit handles ambiguity; coverage_gaps handles untraceable content. These are distinct failure modes requiring distinct handling.
- **6e (Canonical Reference Enforcement)**: Per-prompt canonical enforcement instructions remain minimal outside the generic canonical registry section.
- **Validator–prompt contract gap**: Under R7/R8/R9, schema (R8) enforces structural requirements; validators (R9) enforce semantic requirements (cross-step ID resolution E590, content derivation W594, vague language W593). The residual gap is thin validators for complex steps — addressed in R9, not a prompt-validator framing issue.
- **coverage_gaps prompt enforcement**: No prompt currently specifies when and how to populate `coverage_gaps`. The instruction must be explicit across all prompts: "For every upstream item from the coverage manifest that your output does not address, you MUST add an entry to `coverage_gaps[]` with the upstream item ID, source step, and reason. Do NOT silently omit uncovered items. Do NOT include items you cannot trace." See Area 13 for schema-side enforcement.

→ 6a: RESOLVED — Upstream extraction intent is now inline in all 22 prompts (### Extraction Intent sections). R9 Gap 10 validates prompt coverage against allowed_upstream_dependencies. Original R7 Gap 6 was dropped (Area 12 dismissed; data source removed from step_order.json).
→ 6b: Distilled to: R7 Gaps 1+5 (FULLY COVERED)
→ 6c: Distilled to: R7 Gap 7 (seed ingestion protocol)
→ 6d: Distilled to: R7 Gap 8 (coverage_gaps prompt instructions) + R8 Gap 10 (coverage_gaps schema enforcement)
→ 6e: Distilled to: R7 Gap 9 (canonical output fields)
→ 6f: Distilled to: R7+R8+R9 (FULLY COVERED across layers)

---

### Area 12: Toolkit Discovery Deficit in Prompts

> **STATUS: DISMISSED — See Distillation Status**
> `specdev prompt-context <step>` CLI command added (R6 T07/T08). 2-line header note referencing the CLI added to all 22 prompts (R6 T09–T30). Inline downstream consumer tables, per-prompt validation gate summaries, and build-time enrichment mechanism remain pending.

**Question**: Do the static prompts (`prompts/prompt_NN_*.md`) give the AI agent sufficient awareness of the toolkit infrastructure — downstream consumers, validation rules, pipeline DAG — to generate artifacts optimized for the full pipeline, or is the AI effectively flying blind past the single prompt it receives?

**Context**: When a user runs step 04, the AI receives `prompt_04_functional_requirements.md` and is told to read the schema, upstream artifacts, seeds, shared expectations, and the canonical registry. That is the AI's entire awareness of the toolkit. It has **zero knowledge** of:
- What downstream steps consume its output and what they extract (despite this being machine-readable in `step_order.json` step_metadata)
- What validation rules will be applied to its output (despite 13+ validators existing)
- The full error taxonomy (E1xx–E5xx, ~40+ codes) and what triggers each code
- The pipeline DAG and waterfall policy
- What other step prompts expect from artifacts this step produces

The data to close this gap already exists in `step_order.json` (step_metadata with extraction_intent per step) and the validation suite. The prompts simply don't surface it.

**What to examine**:

#### 12a. Downstream Consumer Awareness
- `tools/step_order.json` (lines 309-509) — The `step_metadata` section declares `required_spec_inputs` and `extraction_intent` for every step. For each step N, the `extraction_intent` entries in downstream steps describe exactly what those steps will extract from step N's output.
- For each prompt (`prompts/prompt_NN_*.md`):
  - Does the prompt tell the AI which downstream steps consume its output? (Expected: no prompt currently does this.)
  - Does the prompt tell the AI *what* downstream steps will extract? (Expected: no prompt currently does this.)
  - Example: `step_order.json` declares that 13 downstream steps consume step 04's output (steps 05, 06, 07, 08, 09, 11, 13, 13a, 14, 15, 16, 16a, 16c). Step 05's extraction_intent says "Extract FR behaviors and acceptance criteria for API design." Step 08 says "Extract acceptance criteria to derive fixture scenarios." Does `prompt_04_functional_requirements.md` mention any of this? (Expected: no.)
- Quantify the gap: For each step, count how many downstream consumers exist in `step_metadata` vs how many the prompt mentions.

#### 12b. Validation Awareness
- For each prompt, check whether it describes the specific validation checks that will run on the output:
  - Does it mention the error codes (E210, E510, E530, E560; schema validation is handled by the jsonschema library, not a custom error code) that apply to this step's output?
  - Does it describe what each validator checks in concrete terms?
  - Or does it just say "run validate" without specifying what the validator will look for?
- Cross-reference: For each step, map the validators that fire on its output (from `validate.py` routing logic) and compare against what the prompt tells the AI about validation.
- Example: Step 04's output is checked by schema validation (handled by the jsonschema library, not a custom error code), canonical drift (E210), placeholder scan (E510), hallucination lint (E530), and traceability closure (E560). Does `prompt_04_functional_requirements.md` mention these? (Expected: it mentions "run validate" but not the specific checks.)

#### 12c. Enrichment Mechanism Feasibility
- `tools/specdev_tools/generation/prompt_generator.py` — Already has `{{VAR}}` template rendering, `_extract_required_fields()`, and context injection for migration prompts. Assess whether this infrastructure can be extended for static prompt enrichment.
- `tools/step_order.json` — Assess whether `step_metadata.extraction_intent` is complete and accurate for all 22 steps. Are any extraction_intent entries missing, vague, or outdated?
- Propose a mechanism for build-time prompt enrichment:
  - A CLI command (e.g., `specdev prompt-enrich`) that reads `step_order.json` and the validator registry, then injects `<!-- TOOLKIT_CONTEXT:...:START/END -->` marked sections into each prompt with downstream consumer tables and validation gate summaries.
  - A pre-commit hook that triggers enrichment when source files (`step_order.json`, validators, schemas, canonical registry) are staged.
  - Idempotent injection using marker comments so re-runs replace only injected content.
- Assess the token cost: How many lines would the injected sections add per prompt? Is the additional context worth the token cost vs the improvement in artifact quality?

**Verified Starting Points**:
| Gap | File | Detail |
|-----|------|--------|
| Zero downstream consumer awareness | All `prompts/prompt_*.md` | No prompt tells the AI which steps consume its output or what they extract; `step_order.json` step_metadata has this data for all 22 steps |
| Validation described as "run validate" only | All `prompts/prompt_*.md` | Prompts say to run the validator but don't describe the ~6 specific checks (E210, E510, E530, E560, etc.; schema validation is handled by the jsonschema library, not a custom error code) that apply to each step's output |
| Extraction intent already machine-readable | `tools/step_order.json:309-509` | `step_metadata.extraction_intent` describes what each downstream step extracts from each upstream artifact — this data exists but is never surfaced to prompts |
| Template rendering infrastructure exists | `tools/specdev_tools/generation/prompt_generator.py` | `render_template()`, `_extract_required_fields()`, and `{{VAR}}` substitution already work for migration prompts; could be extended for static prompt enrichment |

### Remaining Gaps (R7 Closure)

- **No inline downstream consumer tables**: No prompt lists which steps N+k extract from its output, even though this data exists in `step_order.json` `step_metadata.extraction_intent` for all 22 steps. Adding a 2-line CLI reference is not equivalent — the AI must proactively run the CLI command; inline tables surface the data directly in the prompt context.
- **extraction_intent injection (mechanism for 12a/12c)**: `step_metadata.extraction_intent` in `tools/step_order.json` already declares what each downstream step extracts from upstream. Injecting this into each prompt at build time gives the AI both upstream consumption instructions (resolving 6a) and downstream awareness (resolving 12a) simultaneously. The `extraction_intent` entries should be extended with `synthesis_requirements` per synthesis field — declaring what the AI must address in each synthesis field. This becomes the single source of truth readable by both prompt generation tooling and validators (E591).
- **No per-prompt validation gate summary**: Error codes that fire on each step's output (e.g., E210, E510, E530, E560 for step 04; schema validation is handled by the jsonschema library, not a custom error code) are not mentioned in any prompt. The AI cannot optimize its output for checks it doesn't know about.
- **No build-time enrichment mechanism**: `<!-- TOOLKIT_CONTEXT:...:START/END -->` marker injection via `specdev prompt-enrich` or a pre-commit hook does not exist. `step_metadata.extraction_intent` in `tools/step_order.json` is machine-readable but never surfaced into prompt content at generation time.

→ 12a: DROPPED: Upstream extraction intent is now inline in all 22 prompts. Downstream dependencies derivable at runtime via traversal of allowed_upstream_dependencies in step_order.json.
→ 12b: DROPPED: Validation error codes are surfaced by tooling at validation time. Adding them to prompts increases token cost without proportional benefit. Better handled by runtime context system.
→ 12c: DROPPED / SUPERSEDED: toolkit_optimisation.txt explicitly rejects static prompt enrichment. Runtime context package (scope_resolver + extractor) is the locked architectural direction.

---

### Area 13: Schema–Prompt Contract Alignment

> **STATUS: PARTIALLY ADDRESSED — Pending items listed below**
> `schema/00_charter.schema.json`: `stakeholders` and `user_segments` added to `required[]`; `success_metrics` → `minItems: 2` (R6). `schema/04_fr_list.schema.json`: `trace` added to FR item `required[]`; `acceptance_criteria` → `minItems: 2` (R6). Corresponding fixtures (step_00, step_04) and step_04 validator updated (R6). 20 step schemas (01, 02, 02a, 03, 05–16c) remain unaudited.

> **Direction update (R7/R8)**: Under the R7/R8 model, schema follows prompt authority — R7 hardens prompts first (sourcing instructions, Schema Authority), R8 tightens schemas to match. The question is now: "do R8-tightened schemas enforce the structural requirements implied by R7 prompt sourcing instructions?" The 13a-13d audit methodology remains valid with this updated direction.

**Question**: Does each step's JSON Schema enforce the same requirements that its prompt demands, or is the schema systematically weaker than the prompt contract — allowing artifacts to pass validation while violating prompt instructions?

**Context**: The pipeline has three layers of enforcement: (1) the prompt instructs the AI what to produce, (2) the schema validates the JSON structure, (3) per-step validators run additional checks. If the prompt demands a field or constraint that the schema doesn't enforce, the requirement is only as strong as the AI's compliance — it becomes an honor-system rule with no automated verification. This is the opposite of deterministic.

**What to examine**:

#### 13a. Required vs Optional Field Alignment
For each step schema (`schema/NN_*.schema.json`), compare the schema's `required` array against what the corresponding prompt treats as mandatory. Look for fields that:
- The prompt says MUST be present, but the schema marks as optional (not in `required`).
- The prompt says are conditional ("include when X"), but the schema marks as required always.

> **Note**: These examples were resolved in R6 for steps 00 and 04. Use them as the methodology template for auditing the 20 remaining steps.

**Confirmed examples** (use these as anchors, then apply to ALL remaining 20 step schemas):
- `schema/00_charter.schema.json`: `stakeholders` — prompt says "Stakeholders include at least product/eng/ops/security roles with distinct needs" (Self-Audit Gate), schema does NOT list `stakeholders` in `required` (lines 182-193).
- `schema/00_charter.schema.json`: `user_segments` — prompt says "User segments include JTBD/pains/gains for primary personas" (Self-Audit Gate), schema does NOT list `user_segments` in `required`.
- `schema/04_fr_list.schema.json`: `trace` on FR items — prompt says "Traces to capability and (if known) API/NFR" and "include at least one reference to connect artifacts across steps" (Output Rules #7), schema does NOT list `trace` in the FR item's `required` array (lines 89-94).

#### 13b. Constraint Strength Alignment
For each step schema, compare numeric constraints (`minItems`, `minLength`, `minimum`, `maximum`, `pattern`, `enum`) against what the prompt requires:
- Does the schema enforce the same minimums the prompt states?
- Does the schema enforce `minItems` on arrays the prompt says must be non-empty?

> **Note**: These examples were resolved in R6 for steps 00 and 04. Use them as the methodology template for auditing the 20 remaining steps.

**Confirmed examples** (use these as anchors, then apply to ALL remaining 20 step schemas):
- `schema/00_charter.schema.json`: `success_metrics` — prompt says "≥2 metrics" (Self-Audit Gate line 71), schema has NO `minItems` on the array. One metric passes validation.
- `schema/04_fr_list.schema.json`: `acceptance_criteria` — prompt says "top FRs include ≥2" acceptance criteria (Self-Audit Gate line 65), schema has `minItems: 1` (line 48). One criterion passes validation.
- `schema/00_charter.schema.json`: `in_scope` and `out_of_scope` — prompt says "≥3 items each" (Self-Audit Gate line 68), schema has `minItems: 3` (lines 32, 36). **This one aligns** — use it as a positive control.

#### 13c. Cross-Schema Consistency
- Do all 22 step schemas use `$ref` to `schema/core/` for shared types (atoms, collections), or do some inline their own definitions?
- Are there steps that define local versions of types that exist in `schema/core/` (e.g., a local `traceRef` definition instead of referencing `collections.schema.json#traceRef`)?
- Is `additionalProperties: false` set consistently on all objects in all schemas? (Note: grep shows 143 occurrences across 24 files — verify there are no objects missing it.)

#### 13d. Schema-Validator Gap
- For each step, compare what the schema enforces vs what the per-step validator (`validation/validators/step_NN.py`) checks. Are validators checking things the schema already enforces (redundant), or are they checking things the schema cannot express (complementary)?
- Identify step validators that are thin (< 25 LOC) for complex steps. These are steps where the schema is likely the only enforcement, and any prompt requirement not in the schema is unenforced.

**What to recommend**: For each misalignment found, determine whether:
- (a) The **schema should be tightened** to match the prompt (add to `required`, add `minItems`, etc.)
- (b) The **prompt should be relaxed** to match the schema (the schema is intentionally flexible)
- (c) A **per-step validator** should enforce the prompt requirement that the schema cannot express (e.g., conditional requirements, cross-field constraints)

**Verified Starting Points**:
| Gap | File | Detail |
|-----|------|--------|
| 20 step schemas unaudited | `schema/01_*.schema.json` through `schema/16c_*.schema.json` (excluding 00, 04) | No prompt-vs-schema comparison done for steps: 01, 02, 02a, 03, 05, 06, 07, 08, 09, 10, 11, 12, 13, 13a, 14, 15, 16, 16a, 16b, 16c |

### Remaining Gaps

- **13a (Required vs Optional field alignment)**: No prompt-vs-schema comparison done for 20 unaudited steps (01, 02, 02a, 03, 05, 06, 07, 08, 09, 10, 11, 12, 13, 13a, 14, 15, 16, 16a, 16b, 16c). Fields the prompt treats as mandatory that the schema marks optional remain a silent pass risk.
- **13b (Constraint strength alignment)**: No `minItems`/`minLength`/`pattern`/`enum` comparisons done for the 20 unaudited steps. Prompts may state minimums the schema does not enforce.
- **13c (Cross-schema consistency)**: `additionalProperties: false` coverage and local type redefinitions not audited beyond the two fixed steps (00 and 04). Inline type definitions that duplicate `schema/core/` atoms remain undetected for 20 steps.
- **13d (Schema-Validator gap)**: Thin validator analysis (validator checks 3 fields, schema enforces 5, prompt requires 20) not performed for the 16 remaining complex steps. Steps where the validator is thin and the schema is weak are entirely reliant on the AI's honor-system compliance with the prompt.
- **coverage_gaps schema enforcement**: `coverage_gaps` is currently optional or absent in most step schemas, or loosely defined. Schema must: (a) mark `coverage_gaps` as required with `minItems: 0` (empty array valid, absent is not), (b) define each entry structure with `upstream_item_id` (string, required), `source_step` (string, required), `reason` (string, required), `additionalProperties: false`. Without schema enforcement, the 6d prompt instruction for coverage_gaps is honor-system only. This is an R8 change.

→ 13a: Distilled to: R8 Phase 1 Subagents A+B (FULLY COVERED)
→ 13b: Distilled to: R8 Phase 1 Subagents A+B (FULLY COVERED)
→ 13c: Distilled to: R8 Gap 7, Subagent C (FULLY COVERED)
→ 13d: Distilled to: R9 Gap 8, Subagents F+G (FULLY COVERED)
→ 13-extra (coverage_gaps): Distilled to: R8 Gap 10 (NEW — was missing from R8)

---

### Area 14: Artifact Hydration — Generation Efficiency Optimization

> **STATUS: FUTURE IMPROVEMENT — OUT OF SCOPE**
> Approach identified. Implementation details deferred. Does not block R7/R8/R9 determinism closure.

**What it is**: Pre-populate a scaffold artifact with everything deterministically derivable from upstream before AI authorship — reference IDs, canonical terms, traceability fields, schema metadata, coverage manifest. The AI fills only genuine synthesis fields.

**Why it is an optimization, not a correctness requirement**: Pipeline correctness is achieved by R7 (prompt hardening) + R8 (schema tightening) + R9 (validator closure) + fresh LLM review. Validators catch reference field errors (E590), token overlap checks catch content drift (W594), and the LLM review catches semantic completeness gaps. Hydration reduces validation iteration cycles — pre-populated reference fields cannot be wrong — but the system produces correct artifacts without it.

**Role of canonical refs**: Canonical term fields pre-populated from upstream artifacts. Vocabulary drift on controlled fields becomes structurally impossible for pre-populated fields.

**Role of coverage_gaps**: Pre-initialized with upstream coverage manifest. AI marks items covered by filling output entries; uncovered items remain for explicit declaration in coverage_gaps.

**Dependencies**: extraction_intent completeness in `tools/step_order.json` (Area 12). R7/R8/R9 must be complete.

**Scoped as**: R10. Builds on R7/R8/R9, does not replace them.

---

## Deliverables

You must produce TWO deliverables in a single response:

### Part A: Detailed Review Report

For each of the 5 areas, produce:

```markdown
## Area N: [Title]

### Findings
- **[Finding ID: A-N-01]**: [Description of finding]
  - **File**: [exact file path]
  - **Line(s)**: [line numbers]
  - **Evidence**: [what you observed — quote relevant code]
  - **Impact**: [what breaks or degrades because of this gap]
  - **Severity**: Critical | High | Medium | Low

### Verified Starting Points Status
- [Gap from table]: [CONFIRMED / RESOLVED / MODIFIED — with evidence]

### Discovered Gaps (not in starting points)
- [Any additional gaps you found during exploration]
```

**Rules for Part A**:
1. Every finding must include an exact file path and line number(s).
2. Every finding must include a direct code quote as evidence.
3. Do not speculate — if you cannot verify a gap, state that explicitly.
4. Classify severity based on pipeline impact: Critical = breaks determinism; High = allows silent data loss; Medium = allows drift; Low = hygiene/naming.

### Part B: Dependency-Ordered Implementation Plan

Produce a sequenced list of implementation tasks with **zero rework** — no task should require modifying files changed by a later task.

```markdown
## Implementation Plan

### Task N: [Title]
- **Priority**: P0 (blocker) | P1 (high) | P2 (medium) | P3 (low)
- **Depends on**: [Task IDs that must complete first, or "None"]
- **Files to modify**: [exact paths]
- **Changes**:
  1. [Specific change with file:line reference]
  2. [Specific change with file:line reference]
- **Acceptance criteria**:
  - [ ] [Testable criterion]
  - [ ] [Testable criterion]
- **Addresses findings**: [Finding IDs from Part A]
```

**Rules for Part B**:
1. **Strict dependency ordering**: If Task 5 modifies `registry.py` and Task 8 depends on a function added in Task 5, Task 8 must list Task 5 as a dependency.
2. **One logical change per task**: Do not bundle unrelated changes. A task can touch multiple files only if they are part of the same logical change.
3. **Every finding from Part A must map to at least one task in Part B**.
4. **Acceptance criteria must be machine-verifiable**: "Run `pytest tests/test_X.py` and all pass", not "code looks correct".
5. **Include test tasks**: For every code change, include the corresponding test file modifications or new test files.
6. **P0 tasks first**: Arrange by priority, then by dependency order within each priority level.

---

## Execution Instructions

> **Review Focus for This Pass (R7 — Pending Items)**:
> Only 5 areas remain in scope: 3, 4, 6, 12, 13.
> Areas 1, 2, 5, 7, 8, 9, 10, 11 are RESOLVED — do not investigate.

1. **Read before writing**: Read every file referenced in the Verified Starting Points before making any claims. Use the exact paths provided in the Repository Context section.
2. **Verify, then extend**: Confirm each starting point, then explore adjacent code for additional gaps.
3. **Cross-reference prompts ↔ validators ↔ schemas**: For every step, compare what the prompt requires, what the validator checks, and what the schema enforces. Gaps between these three are findings.
4. **Check `step_order.json` against prompts**: For every step, verify that the prompt's upstream input instructions match the step's declared dependencies.
5. **Run the tools if possible**: Execute `./tools/run_specdev.sh validate-all spec --repo-root .` and `./tools/run_specdev.sh canonical-integrity spec --repo-root .` to see current state.
6. **Be exhaustive on Area 6 (Prompt Hardening) AND Area 13 (Schema–Prompt Alignment)**: These are the highest-impact areas. Area 6: every prompt must be reviewed individually for 6a–6f — do not sample or skip. Area 13: every unaudited schema (20 steps: 01, 02, 02a, 03, 05–16c) must be compared against its corresponding prompt for 13a–13d.

---

## Anti-Patterns to Avoid

- **Do not speculate**: If you cannot read a file or verify a gap, say so explicitly. Do not invent findings.
- **Do not propose architectural rewrites**: The goal is targeted fixes within the existing architecture, not redesign.
- **Do not conflate areas**: Each finding belongs to exactly one area. If a finding spans areas, file it under the most impactful one and cross-reference.
- **Do not ignore thin validators**: A 16-line validator for a complex step (e.g., Invariants, NFRs) is almost certainly insufficient. Identify what's missing.
- **Do not treat warnings as acceptable**: Any warning-level finding with no escalation path is effectively permission to ignore that class of problem indefinitely.
- **Do not assume the AI knows the toolkit**: The AI generating an artifact sees only the prompt, the schema, and upstream artifacts it is told to read. It has no awareness of downstream consumers, validation rules, error codes, or the pipeline DAG unless the prompt explicitly surfaces this information. If data exists in `step_order.json` that would improve artifact quality, it should be in the prompt.
- **Do not assume schema validation catches prompt requirements**: If a prompt says "include ≥2 acceptance criteria" but the schema only enforces `minItems: 1`, the requirement is unenforceable by automation. Prompt requirements without schema backing are honor-system rules. Audit every prompt requirement against its schema constraint.

---

## Distillation Status

All pending items have been distilled into R7, R8, and R9 review specifications.

- **8 items FULLY COVERED** by existing R7/R8/R9 content
- **3 items PARTIALLY COVERED** — missing details added to R7 (Gaps 7-9). 2 original partially-covered items (R7 Gaps 6, 11) were dropped when Area 12 was dismissed.
- **1 item added as new gap**: R8 Gap 10 (coverage_gaps schema). **2 items DROPPED**: R7 Gap 10 (validation gates — tooling handles this), R9 Gap 18 (prompt-enrich — superseded by runtime context architecture)
- **Area 12 fully dismissed** — upstream extraction intent already inline in prompts, downstream derivable at runtime, validation gates handled by tooling, build-time enrichment superseded by runtime context architecture
- **2 corrections applied**: E200 hallucinated error code removed, "33 prompts" → "22 prompts"

No further pending items remain. This document is now fully resolved.

</review_prompt>
